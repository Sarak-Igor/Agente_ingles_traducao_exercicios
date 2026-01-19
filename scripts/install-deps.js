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
  process.exit(1);
}

console.log('📦 Instalando dependências no venv...');
console.log(`Python: ${pythonPath}`);

// Instala os pacotes usando o pip do venv
const args = ['-m', 'pip', 'install', 'python-jose[cryptography]', 'passlib[bcrypt]'];
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
  if (code === 0) {
    console.log('✅ Dependências instaladas com sucesso!');
  } else {
    console.error('❌ Erro ao instalar dependências');
  }
  process.exit(code || 0);
});
