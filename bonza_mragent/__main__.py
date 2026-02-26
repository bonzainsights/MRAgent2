"""
bonza_mragent.__main__ — allows `python -m bonza_mragent` to work.

This is the recommended fallback on Windows when the pip Scripts dir
is not on PATH. Users can always run:
    python -m bonza_mragent
instead of just:
    mragent
"""
import sys
from pathlib import Path

# Ensure the project root (site-packages or repo root) is on sys.path
_HERE = Path(__file__).parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from main import main

if __name__ == "__main__":
    sys.exit(main())
