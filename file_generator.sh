#!/bin/bash
text="Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur."

if [ $# -ne 1 ]; then
  echo "Usage: $0 <fileSize>"
  exit 1
fi

yes "$text" | head -c $1 > "experiments/${1}.txt" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "Invalid number of bytes: ${1}"
    rm -f "experiments/${1}.txt"
fi