#!/bin/bash

# Force uv site-packages first to shadow conflicting Nix-store packages
export PYTHONPATH=/home/runner/workspace/.pythonlibs/lib/python3.12/site-packages:$PYTHONPATH

exec /home/runner/workspace/.pythonlibs/bin/python3 /home/runner/workspace/extracted_project/control_panel/server.py
