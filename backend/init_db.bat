@echo off
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe init_db.py
) else (
    echo Ambiente virtual não encontrado!
    exit /b 1
)
