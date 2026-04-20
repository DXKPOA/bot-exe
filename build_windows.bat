@echo off
chcp 65001 >nul
setlocal

if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --clean --noconfirm PlayGridAI.spec

echo.
echo Build complete. EXE is in dist\PlayGridAI.exe
pause
