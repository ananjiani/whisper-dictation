{
  description = "System-wide dictation with whisper";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    { self, nixpkgs, uv2nix, pyproject-nix, pyproject-build-systems, ... }:
    let
      inherit (nixpkgs) lib;

      # Support multiple systems
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
      overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };
      pyprojectOverrides = _final: _prev:
        {
          # Implement build fixups here.
          # Note that uv2nix is _not_ using Nixpkgs buildPythonPackage.
          # It's using https://pyproject-nix.github.io/pyproject.nix/build.html
        };
    in {
      apps = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          setupScript = pkgs.writeScriptBin "setup" ''
            #!${pkgs.bash}/bin/bash
            set -euo pipefail

            # Check if already setup
            if [ ! -d "whisper_dictation" ]; then
                echo "✓ Project already initialized"
                exit 0
            fi

            # Get project name from directory
            PROJECT_DIR=$(basename "$PWD")
            whisper_dictation=$(echo "$PROJECT_DIR" | sed 's/[-.]/_/g' | sed 's/[^a-zA-Z0-9_]//g' | tr '[:upper:]' '[:lower:]')

            # Validate project name
            if [[ ! "$whisper_dictation" =~ ^[a-z][a-z0-9_]*$ ]]; then
                echo "Error: Invalid project name '$whisper_dictation'. Must start with a letter and contain only letters, numbers, and underscores."
                exit 1
            fi

            # Get author info from git as fallback
            GIT_NAME=$(${pkgs.git}/bin/git config user.name 2>/dev/null || echo "")
            GIT_EMAIL=$(${pkgs.git}/bin/git config user.email 2>/dev/null || echo "")

            # Interactive prompts with git config as fallback
            echo "Project name: $whisper_dictation"
            echo
            if [ -n "$GIT_NAME" ]; then
                read -p "Author name [$GIT_NAME]: " INPUT_NAME
                AUTHOR_NAME=''${INPUT_NAME:-$GIT_NAME}
            else
                read -p "Author name: " AUTHOR_NAME
                AUTHOR_NAME=''${AUTHOR_NAME:-"Ammar Nanjiani"}
            fi

            if [ -n "$GIT_EMAIL" ]; then
                read -p "Author email [$GIT_EMAIL]: " INPUT_EMAIL
                AUTHOR_EMAIL=''${INPUT_EMAIL:-$GIT_EMAIL}
            else
                read -p "Author email: " AUTHOR_EMAIL
                AUTHOR_EMAIL=''${AUTHOR_EMAIL:-"ammar.nanjiani@gmail.com"}
            fi

            read -p "Project description (optional): " DESCRIPTION
            DESCRIPTION=''${DESCRIPTION:-"System-wide dictation with whisper"}

            echo
            echo "Setting up project..."

            # Initialize git repository if not already initialized
            if [ ! -d ".git" ]; then
                echo "Initializing git repository..."
                ${pkgs.git}/bin/git init
                echo "Adding flake.nix to git..."
                ${pkgs.git}/bin/git add flake.nix
                echo "✓ Initialized git repository"
            fi

            # Update all files
            echo "Updating template files with project details..."
            ${pkgs.findutils}/bin/find . -type f -name "*.py" -o -name "*.toml" -o -name "*.md" -o -name "*.nix" -o -name "*.ini" -o -name "justfile" | \
            while read -r file; do
                if [[ "$file" != *"/.git/"* ]] && [[ "$file" != *"/uv.lock" ]] && [[ "$file" != *"/flake.lock" ]] && [[ "$(basename "$file")" != "setup" ]]; then
                    ${pkgs.gnused}/bin/sed -i "s/whisper_dictation/$whisper_dictation/g" "$file"
                    ${pkgs.gnused}/bin/sed -i "s/Ammar Nanjiani/$AUTHOR_NAME/g" "$file"
                    ${pkgs.gnused}/bin/sed -i "s/ammar.nanjiani@gmail.com/$AUTHOR_EMAIL/g" "$file"
                    ${pkgs.gnused}/bin/sed -i "s/System-wide dictation with whisper/$DESCRIPTION/g" "$file"
                    # Update flake description
                    ${pkgs.gnused}/bin/sed -i "s/System-wide dictation with whisper/$DESCRIPTION/g" "$file"
                fi
            done
            echo "✓ Updated template files"

            # Make hook scripts executable
            echo "Making hook scripts executable..."
            ${pkgs.findutils}/bin/find .claude/hooks -name "*.sh" -type f -exec chmod +x {} \; 2>/dev/null || true
            echo "✓ Hook scripts made executable"

            # Rename directory
            echo "Renaming whisper_dictation directory to $whisper_dictation..."
            mv whisper_dictation "$whisper_dictation"
            echo "✓ Renamed directory"

            # Install dependencies
            echo "Installing Python dependencies..."
            ${pkgs.uv}/bin/uv sync
            echo "✓ Dependencies installed"

            # Install pre-commit hooks
            echo "Setting up pre-commit hooks..."
            ${pkgs.pre-commit}/bin/pre-commit install
            echo "✓ Pre-commit hooks installed"

            # Create setup complete marker
            touch .setup-complete

            # Success message
            echo
            echo "✅ Project '$whisper_dictation' initialized successfully!"
            echo
            echo "Next steps:"
            echo "  • Run 'just test' to verify setup"
            echo "  • Start coding in $whisper_dictation/"
            echo "  • Update README.md with project specifics"
            echo "  • Run 'just' to see available commands"
          '';
        in {
          setup = {
            type = "app";
            program = "${setupScript}/bin/setup";
          };
        });

      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python313;

          # Construct package set
          pythonSet =
            # Use base package set from pyproject.nix builders
            (pkgs.callPackage pyproject-nix.build.packages {
              inherit python;
            }).overrideScope (lib.composeManyExtensions [
              pyproject-build-systems.overlays.default
              overlay
              pyprojectOverrides
            ]);
        in {
          default = pkgs.mkShell {
            buildInputs = [
              # Python and package management
              python
              pkgs.uv

              # Development tools
              pkgs.ruff
              pkgs.just
              pkgs.watchexec
              pkgs.git
              pkgs.pre-commit
            ]
            ++ (with pkgs.python313Packages; [
              mypy
              python-lsp-server
              python-lsp-ruff
              pylsp-mypy
            ]);

            env = {
              UV_PYTHON_DOWNLOADS = "never";
              UV_PYTHON = python.interpreter;
            };

            shellHook = ''
              # Check if this is a fresh template
              if [ -d "whisper_dictation" ] && [ ! -f ".setup-complete" ]; then
                echo "═══════════════════════════════════════════════════════════"
                echo "🚀 Welcome! This is a fresh Python project template."
                echo "   Run 'nix run .#setup' to initialize your project."
                echo "═══════════════════════════════════════════════════════════"
                echo ""
              fi

              echo "🐍 Python Development Environment"
              echo "Python: ${python.version}"
              echo ""
              echo "Available commands:"
              echo "  just          - Show available development tasks"
              echo "  just install  - Install Python dependencies"
              echo "  just test     - Run tests"
              echo "  just lint     - Run linters"
              echo "  just check    - Run all checks"
              echo ""
              echo ""

              # Set up environment
              unset PYTHONPATH
              export PYTHONPATH="$PWD:$PYTHONPATH"
            '';
          };
        });
    };
}
