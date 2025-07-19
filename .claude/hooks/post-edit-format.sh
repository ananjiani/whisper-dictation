#!/usr/bin/env bash

# Claude Code PostToolUse hook for auto-formatting after file edits
# This hook runs after Edit, MultiEdit, or Write tools are used

set -e

# Read JSON from stdin
JSON_INPUT=$(cat)

# Parse tool name and file path from JSON using jq
TOOL_NAME=$(echo "$JSON_INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(echo "$JSON_INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')

# Exit if no file path (some tools might not have it)
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Only process files that exist
if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Format Python files using just command
if [[ "$FILE_PATH" == *.py ]]; then
    # Find the project root (where justfile exists)
    PROJECT_ROOT="$FILE_PATH"
    while [ "$PROJECT_ROOT" != "/" ]; do
        PROJECT_ROOT=$(dirname "$PROJECT_ROOT")
        if [ -f "$PROJECT_ROOT/justfile" ]; then
            cd "$PROJECT_ROOT"
            just format 2>/dev/null || true
            break
        fi
    done
fi

# Always exit successfully to not block Claude Code
exit 0
