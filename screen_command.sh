#!/bin/bash
# Screen command sender - restricted to stuff commands only
# Usage: screen_command.sh <session_name> <command>

if [ $# -ne 2 ]; then
    echo "Usage: $0 <session_name> <command>"
    exit 1
fi

SESSION="$1"
COMMAND="$2"

# Validate inputs
if [[ "$SESSION" =~ [^a-zA-Z0-9._-] ]]; then
    echo "Invalid session name"
    exit 1
fi

# Disallow newline injection
if [[ "$COMMAND" =~ [\n\r\t] ]]; then
    echo "Invalid command characters"
    exit 1
fi

# Limit command length
if [ ${#COMMAND} -gt 1000 ]; then
    echo "Command too long"
    exit 1
fi

# Send command to screen session
screen -S "$SESSION" -X stuff "$COMMAND\n" 2>/dev/null