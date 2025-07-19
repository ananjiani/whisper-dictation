#!/usr/bin/env bash

# Claude Code PreToolUse hook for Edit/Write safety checks
# This hook runs before Edit, MultiEdit, or Write tools are used

set -e

# Read JSON from stdin
JSON_INPUT=$(cat)

# Parse tool name and file path from JSON using jq
TOOL_NAME=$(echo "$JSON_INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(echo "$JSON_INPUT" | jq -r '.tool_input.file_path // empty')

# Output JSON to control execution
output_json() {
    local continue="$1"
    local message="$2"
    echo "{\"continue\": $continue, \"decision_feedback\": \"$message\"}"
}

# Exit if no file path
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Get the filename
FILENAME=$(basename "$FILE_PATH")

# Check for lock files
if [[ "$FILENAME" == "uv.lock" ]]; then
    output_json "false" "❌ Don't edit uv.lock directly. Use 'uv add/remove' or 'just update' to manage dependencies"
    exit 0
fi

if [[ "$FILENAME" == "flake.lock" ]]; then
    output_json "false" "❌ Don't edit flake.lock directly. Use 'nix flake update' to update lock file"
    exit 0
fi

# Check for generated/cache files
if [[ "$FILE_PATH" == *"__pycache__"* ]] || [[ "$FILE_PATH" == *.pyc ]]; then
    output_json "false" "❌ Don't edit generated Python cache files"
    exit 0
fi

if [[ "$FILE_PATH" == *"htmlcov"* ]] || [[ "$FILE_PATH" == *".coverage"* ]]; then
    output_json "false" "❌ Don't edit generated coverage files. Run 'just test-cov' to regenerate"
    exit 0
fi

if [[ "$FILE_PATH" == *".pytest_cache"* ]] || [[ "$FILE_PATH" == *".mypy_cache"* ]] || [[ "$FILE_PATH" == *".ruff_cache"* ]]; then
    output_json "false" "❌ Don't edit tool cache files"
    exit 0
fi

# Check for build artifacts
if [[ "$FILE_PATH" == *"dist/"* ]] || [[ "$FILE_PATH" == *"build/"* ]] || [[ "$FILE_PATH" == *.egg-info/* ]]; then
    output_json "false" "❌ Don't edit build artifacts. Use 'just build' to regenerate"
    exit 0
fi

# Warn about pyproject.toml dependency editing
if [[ "$FILENAME" == "pyproject.toml" ]] && [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "MultiEdit" ]]; then
    # Try to check if editing dependencies section
    OLD_STRING=$(echo "$JSON_INPUT" | jq -r '.tool_input.old_string // empty' 2>/dev/null || echo "")
    if [[ "$OLD_STRING" == *"dependencies"* ]] || [[ "$OLD_STRING" == *"[tool.uv]"* ]]; then
        output_json "true" "⚠️ Consider using 'uv add/remove' for dependency management instead of manual edits"
        exit 0
    fi
fi

# Suggest MultiEdit for multiple changes to the same file
if [[ "$TOOL_NAME" == "Edit" ]]; then
    # Check if this file was recently edited (simple heuristic - could be improved)
    output_json "true" "💡 Tip: Use MultiEdit tool if you need to make multiple changes to this file"
    exit 0
fi

# Allow the edit to proceed
exit 0
