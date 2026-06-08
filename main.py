"""
main.py — entry point for PSPC Viewer.

Run:
    python main.py
    python main.py PS315.pspc          # open a file directly

Build standalone .exe:
    build_exe.bat                      # uses PyInstaller
"""
import tkinter as tk
import os
import sys

from viewer import PSPCViewer


def main():
    root = tk.Tk()

    # Optional window icon (no crash if missing)
    icon = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(__file__)), "icon.ico")
    try:
        root.iconbitmap(icon)
    except Exception:
        pass

    app = PSPCViewer(root)

    # Support drag-and-drop / OS file association / CLI argument
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        root.after(300, lambda: app._open(sys.argv[1]))

    root.mainloop()


if __name__ == "__main__":
    main()
