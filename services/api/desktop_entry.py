"""PyInstaller entry point for the free single-project desktop .exe.

Thin launcher so the spec has a stable script to analyze; all logic lives in
aec_api.desktop (SQLite + local mode + serves the bundled SPA on 127.0.0.1:8765).
"""
from aec_api.desktop import main

if __name__ == "__main__":
    main()
