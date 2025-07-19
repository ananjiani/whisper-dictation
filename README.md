# whisper_dictation

Add your project description here.

## Quick Start

This project uses Nix for development environment management and `uv` for Python dependency management.

### Prerequisites

- [Nix](https://nixos.org/download.html) with flakes enabled
- (Optional) [direnv](https://direnv.net/) for automatic environment activation

### Development Setup

1. **Enter the development environment:**
   ```bash
   nix develop
   ```

   Or with direnv:
   ```bash
   echo "use flake" > .envrc
   direnv allow
   ```

2. **Install Python dependencies:**
   ```bash
   just install
   ```

3. **Set up pre-commit hooks (recommended):**
   ```bash
   just install-hooks
   ```

## Development Workflow

### Common Commands

Run `just` to see all available commands:

```bash
just            # Show available commands
just test       # Run all tests
just test-fast  # Run only fast tests
just lint       # Run linters
just format     # Format code
just check      # Run all checks (lint, typecheck, test)
just watch-test # Watch files and run tests on changes
```

### Running the Application

```bash
just run        # Run with default arguments
just run --help # Show CLI help
```

Or directly:
```bash
python -m whisper_dictation --help
```

### Testing

Tests are organized with markers:
- `unit`: Fast unit tests with no external dependencies
- `integration`: Tests that may use external resources
- `slow`: Tests that take longer to run

```bash
just test-unit        # Run only unit tests
just test-integration # Run only integration tests
just test-cov        # Run tests with coverage report
```

### Code Quality

The project uses:
- **ruff** for linting and formatting
- **mypy** for type checking
- **pre-commit** for automated checks before commits

### Project Structure

```
whisper_dictation/
├── whisper_dictation/          # Main package
│   ├── __init__.py
│   └── __main__.py       # CLI entry point
├── tests/                # Test files
│   ├── conftest.py      # Pytest configuration
│   └── test_*.py        # Test modules
├── pyproject.toml       # Project configuration
├── pytest.ini           # Pytest configuration
├── justfile            # Development commands
├── flake.nix           # Nix environment
└── README.md           # This file
```

## License

[Add your license here]
