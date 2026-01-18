#!/bin/bash

if [ -f "venv/bin/python" ]; then
    venv/bin/python init_db.py
elif [ -f "venv/Scripts/python.exe" ]; then
    venv/Scripts/python.exe init_db.py
else
    echo "Ambiente virtual não encontrado!"
    exit 1
fi
