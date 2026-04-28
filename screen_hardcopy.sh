#!/bin/bash
# Screen log dumper - restricted to read-only hardcopy operations
# Usage: screen_hardcopy.sh <session_name> <output_file>

if [ $# -ne 2 ]; then
    echo "Usage: $0 <session_name> <output_file>"
    exit 1
fi

SESSION="$1"
OUTPUT="$2"

# Validate inputs
if [[ "$SESSION" =~ [^a-zA-Z0-9._-] ]] || [[ "$OUTPUT" =~ [^a-zA-Z0-9._/-] ]]; then
    echo "Invalid characters in session name or output file"
    exit 1
fi

# Only allow hardcopy operations
screen -S "$SESSION" -X hardcopy -h "$OUTPUT" 2>/dev/null || \
screen -S "$SESSION" -X hardcopy "$OUTPUT" 2>/dev/null

# Limit output to last 2000 lines if file exists
if [ -f "$OUTPUT" ]; then
    tail -n 2000 "$OUTPUT" > "${OUTPUT}.tmp" && mv "${OUTPUT}.tmp" "$OUTPUT"
fi