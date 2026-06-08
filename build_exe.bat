@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM  Build PSPC Viewer → standalone .exe  (Windows)
REM
REM  PyInstaller follows all imports automatically, so all .py files in this
REM  folder are bundled together — no extra flags needed.
REM ─────────────────────────────────────────────────────────────────────────

echo Installing / updating dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Building exe...
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "PSPCViewer" ^
  --add-data "README.md;." ^
  main.py

echo.
if exist dist\PSPCViewer.exe (
    echo  Done!  ^>  dist\PSPCViewer.exe
) else (
    echo  Build failed — check output above.
)
pause
