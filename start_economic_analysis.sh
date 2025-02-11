#!/bin/bash

# Find Python 3
PYTHON=$(command -v python3)
if [ -z "$PYTHON" ]; then
    PYTHON=$(command -v python)
fi

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3 not found. Please install Python 3."
    exit 1
fi

# Find the EconomicAnalysis directory
APP_DIR="$HOME/EconomicAnalysis"
if [ ! -d "$APP_DIR" ]; then
    echo "Error: EconomicAnalysis directory not found in $HOME"
    echo "Please enter the full path to your EconomicAnalysis directory:"
    read -r APP_DIR
    if [ ! -d "$APP_DIR" ]; then
        echo "Error: Invalid directory"
        exit 1
    fi
fi

# Run the application
cd "$APP_DIR" || exit 1
"$PYTHON" run.py 