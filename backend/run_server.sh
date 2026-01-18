#!/bin/bash

if [ -f "venv/bin/python" ]; then
    venv/bin/python -m uvicorn app.main:app --reload --log-level warning --no-access-log
elif [ -f "venv/Scripts/python.exe" ]; then
    venv/Scripts/python.exe -m uvicorn app.main:app --reload --log-level warning --no-access-log
else
    echo "Ambiente virtual não encontrado!"
    echo "Execute: python3 -m venv venv"
    echo "Depois: source venv/bin/activate"
    echo "E então: pip install -r requirements.txt"
    exit 1
fi
