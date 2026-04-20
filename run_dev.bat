@echo off
chcp 65001 >nul
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install flask requests
if not exist .env copy .env.example .env
python app.py
