@echo off
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -m uvicorn app.main:app --reload
) else (
    echo Ambiente virtual não encontrado!
    echo Execute: python -m venv venv
    echo Depois: venv\Scripts\activate
    echo E então: pip install -r requirements.txt
    exit /b 1
)
