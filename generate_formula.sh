#!/bin/bash
# Re-create venv to ensure clean state
rm -rf .brew_venv
python3 -m venv .brew_venv
source .brew_venv/bin/activate
pip install homebrew-pypi-poet bonza-mragent
# Use the binary directly to avoid path issues
./.brew_venv/bin/poet -f bonza-mragent
deactivate
rm -rf .brew_venv
