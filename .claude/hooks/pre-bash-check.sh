#!/usr/bin/env bash

# Claude Code PreToolUse hook for Bash command validation
# This hook runs before Bash commands are executed

set -e

# Read JSON from stdin
JSON_INPUT=$(cat)

# Parse the command from JSON using jq
COMMAND=$(echo "$JSON_INPUT" | jq -r '.tool_input.command // empty')

# Output JSON to control execution
output_json() {
    local continue="$1"
    local message="$2"
    echo "{\"continue\": $continue, \"decision_feedback\": \"$message\"}"
}

# Exit if no command
if [ -z "$COMMAND" ]; then
    exit 0
fi

# Get current working directory from session if available
PWD=$(echo "$JSON_INPUT" | jq -r '.cwd // empty')

# Check for pip usage instead of uv
if [[ "$COMMAND" =~ pip[[:space:]]+install ]] && [[ ! "$COMMAND" =~ pip[[:space:]]+install[[:space:]]+-e ]]; then
    output_json "false" "❌ Use 'uv add <package>' instead of pip install. For dev dependencies, use 'uv add --dev <package>'"
    exit 0
fi

if [[ "$COMMAND" =~ pip[[:space:]]+uninstall ]]; then
    output_json "false" "❌ Use 'uv remove <package>' instead of pip uninstall"
    exit 0
fi

# Suggest using just commands instead of direct tool usage
if [[ "$COMMAND" =~ ^[[:space:]]*pytest[[:space:]]* ]] && [[ ! "$COMMAND" =~ just[[:space:]]+test ]]; then
    output_json "true" "💡 Tip: Consider using 'just test' instead of running pytest directly"
    exit 0
fi

if [[ "$COMMAND" =~ ^[[:space:]]*ruff[[:space:]]+check ]] && [[ ! "$COMMAND" =~ just[[:space:]]+lint ]]; then
    output_json "true" "💡 Tip: Consider using 'just lint' instead of running ruff directly"
    exit 0
fi

if [[ "$COMMAND" =~ ^[[:space:]]*ruff[[:space:]]+format ]] && [[ ! "$COMMAND" =~ just[[:space:]]+format ]]; then
    output_json "true" "💡 Tip: Consider using 'just format' instead of running ruff directly"
    exit 0
fi

if [[ "$COMMAND" =~ ^[[:space:]]*mypy[[:space:]]+ ]] && [[ ! "$COMMAND" =~ just[[:space:]]+typecheck ]]; then
    output_json "true" "💡 Tip: Consider using 'just typecheck' instead of running mypy directly"
    exit 0
fi

# Check for python vs python3 (prefer explicit python3 or use from nix)
if [[ "$COMMAND" =~ ^[[:space:]]*python[[:space:]]+ ]] && [[ ! "$COMMAND" =~ python3 ]] && [[ ! "$COMMAND" =~ "python -m" ]]; then
    output_json "true" "💡 Tip: Consider using 'python3' or 'python -m PROJECT_NAME' for clarity"
    exit 0
fi

# Warn about global installs
if [[ "$COMMAND" =~ install[[:space:]]+-g ]] || [[ "$COMMAND" =~ install[[:space:]]+--global ]]; then
    output_json "true" "⚠️ Warning: Global installs may conflict with Nix environment"
    exit 0
fi

# Check for common file reading patterns that should use Read tool
if [[ "$COMMAND" =~ ^[[:space:]]*cat[[:space:]]+ ]] && [[ ! "$COMMAND" =~ [\|\>] ]]; then
    output_json "true" "💡 Tip: Consider using the Read tool instead of 'cat' for better file viewing"
    exit 0
fi

# Check for pytest without proper directory
if [[ "$COMMAND" =~ pytest ]] && [[ ! "$COMMAND" =~ just[[:space:]]+test ]] && [[ ! -f "pyproject.toml" ]] && [[ "$PWD" != *"PROJECT_NAME"* ]]; then
    output_json "true" "💡 Tip: Make sure you're in the project root directory when running pytest"
    exit 0
fi

# Allow command to proceed
exit 0
