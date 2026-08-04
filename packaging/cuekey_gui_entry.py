"""PyInstaller entry point for the CueKey desktop app."""

import multiprocessing

from cuekey.gui import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
