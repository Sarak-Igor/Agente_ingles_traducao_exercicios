#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const backendDir = path.join(__dirname, '..', 'backend');
const isWindows = os.platform() === 'win32';

// Detecta o Python do ambiente virtual
let pythonPath;

if (isWindows) {
  const venvPython = path.join(backendDir, 'venv', 'Scripts', 'python.exe');
  if (fs.existsSync(venvPython)) {
    pythonPath = venvPython;
  }
} else {
  const venvPython = path.join(backendDir, 'venv', 'bin', 'python');
  if (fs.existsSync(venvPython)) {
    pythonPath = venvPython;
  }
}

if (!pythonPath) {
  console.error('❌ ERRO: Ambiente virtual não encontrado!');
  console.error('');
  console.error('Execute os seguintes comandos:');
  console.error('  cd backend');
  if (isWindows) {
    console.error('  python -m venv venv');
    console.error('  venv\\Scripts\\activate');
  } else {
    console.error('  python3 -m venv venv');
    console.error('  source venv/bin/activate');
  }
  console.error('  pip install -r requirements.txt');
  process.exit(1);
}

// Executa uvicorn
const args = ['-m', 'uvicorn', 'app.main:app', '--reload'];
const proc = spawn(pythonPath, args, {
  cwd: backendDir,
  stdio: 'inherit',
  shell: false
});

proc.on('error', (err) => {
  console.error('Erro ao executar:', err);
  process.exit(1);
});

proc.on('exit', (code) => {
  process.exit(code || 0);
});
