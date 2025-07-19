{
  description = "Minimal whisper dictation tool";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};

          # Create Python environment with all needed packages
          pythonEnv = pkgs.python313.withPackages (ps: with ps; [
            # Runtime dependency
            faster-whisper

            # Development tools
            mypy
            python-lsp-server
            python-lsp-ruff
            pylsp-mypy

            # Testing
            pytest
            pytest-cov
            pytest-asyncio
            pytest-mock
            pytest-timeout
            pytest-xdist
            hypothesis
          ]);
        in
        {
          default = pkgs.mkShell {
            buildInputs = [
              # Python with all packages
              pythonEnv

              # Development tools
              pkgs.ruff          # Python linter/formatter
              pkgs.just          # Command runner
              pkgs.watchexec     # File watcher
              pkgs.git           # Version control
              pkgs.pre-commit    # Git hooks
            ];

            shellHook = ''
              echo "🎤 Whisper Dictation Development Environment"
              echo ""
              echo "Available commands:"
              echo "  just          - Show available development tasks"
              echo "  just test     - Run tests"
              echo "  just lint     - Run linters"
              echo "  just check    - Run all checks"
              echo ""
              echo "Whisper dictation:"
              echo "  ./whisper_dictation.py begin  - Start recording"
              echo "  ./whisper_dictation.py end    - Stop and transcribe"
              echo ""

              # Set up environment
              export PYTHONPATH="$PWD:$PYTHONPATH"

              # Install pre-commit hooks if not already installed
              if [ -f .pre-commit-config.yaml ] && [ ! -f .git/hooks/pre-commit ]; then
                echo "Installing pre-commit hooks..."
                pre-commit install
              fi
            '';
          };
        });
    };
}
