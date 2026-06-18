#!/bin/bash

# Put .pythonlibs first so installed packages shadow the older Nix-store versions
export PYTHONPATH=/home/runner/workspace/.pythonlibs/lib/python3.12/site-packages:$PYTHONPATH

# Start Control Panel only — bots are managed by their own workflows
exec python3 /home/runner/workspace/extracted_project/control_panel/server.py
