#!/bin/bash

# Ensure .pythonlibs packages shadow any conflicting Nix-store packages
export PYTHONPATH=/home/runner/workspace/.pythonlibs/lib/python3.12/site-packages

exec /home/runner/workspace/.pythonlibs/bin/python3 /home/runner/workspace/extracted_project/control_panel/server.py
