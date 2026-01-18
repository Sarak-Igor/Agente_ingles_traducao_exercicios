# Sistema de Tradução de Vídeos do YouTube

Sistema completo para tradução de legendas de vídeos do YouTube com múltiplos serviços de tradução e interface web moderna.

## 📋 Pré-requisitos

### Backend
- Python 3.9 ou superior
- PostgreSQL 12 ou superior
- pip (gerenciador de pacotes Python)

### Frontend
- Node.js 18 ou superior
- npm ou yarn

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone <url-do-repositorio>
cd Tradução
```

### 2. Configuração do Backend

#### 2.1. Criar ambiente virtual

**Windows:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

#### 2.2. Instalar dependências

```bash
pip install -r requirements.txt
```

#### 2.3. Configurar variáveis de ambiente

Copie o arquivo `env.example` (na raiz do projeto) para `.env`:

**Windows:**
```bash
copy env.example .env
```

**Linux/Mac:**
```bash
cp env.example .env
```

Edite o arquivo `.env` na raiz do projeto com suas configurações:

```env
# Database - OBRIGATÓRIO
DATABASE_URL=postgresql://usuario:senha@localhost:5432/nome_do_banco

# Security - OBRIGATÓRIO
# Gere uma chave usando: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=sua_chave_fernet_aqui

# Server - OPCIONAL (valores padrão)
HOST=0.0.0.0
PORT=8000

# CORS - OPCIONAL
FRONTEND_URL=http://localhost:5173

# Redis - OPCIONAL (para cache)
# REDIS_URL=redis://localhost:6379
```

**Importante:** Gere uma chave de criptografia única:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

#### 2.4. Criar banco de dados

Crie o banco de dados PostgreSQL:

```sql
CREATE DATABASE nome_do_banco;
```

#### 2.5. Inicializar tabelas

```bash
python init_db.py
```

### 3. Configuração do Frontend

#### 3.1. Instalar dependências

```bash
cd frontend
npm install
```

#### 3.2. Configurar variáveis de ambiente (opcional)

Crie um arquivo `.env` no diretório `frontend` se precisar alterar a URL da API:

```env
VITE_API_URL=http://localhost:8000
```

### 4. Executar o sistema

#### Opção 1: Executar tudo junto (recomendado para desenvolvimento)

Na raiz do projeto:

```bash
npm run dev
```

Este comando detecta automaticamente o ambiente virtual e usa o Python correto.

#### Opção 2: Executar separadamente

**Backend:**
```bash
cd backend
venv\Scripts\activate  # Windows
# ou
source venv/bin/activate  # Linux/Mac

uvicorn app.main:app --reload
```

Ou use o script auxiliar:
```bash
# Windows
cd backend
run_server.bat

# Linux/Mac
cd backend
chmod +x run_server.sh
./run_server.sh
```

**Frontend:**
```bash
cd frontend
npm run dev
```

## 📁 Estrutura do Projeto

```
.
├── .env                   # Variáveis de ambiente (não versionado)
├── env.example            # Exemplo de configuração
├── .gitignore            # Arquivos ignorados pelo Git
├── package.json          # Scripts npm da raiz
├── backend/
│   ├── app/
│   │   ├── api/          # Rotas da API
│   │   ├── models/       # Modelos do banco de dados
│   │   ├── schemas/      # Schemas Pydantic
│   │   ├── services/     # Serviços de negócio
│   │   ├── config.py     # Configurações
│   │   ├── database.py   # Conexão com banco
│   │   └── main.py       # Aplicação FastAPI
│   ├── init_db.py        # Script de inicialização do banco
│   └── requirements.txt  # Dependências Python
├── frontend/
│   ├── src/
│   │   ├── components/   # Componentes React
│   │   ├── hooks/        # Custom hooks
│   │   └── services/     # Serviços de API
│   └── package.json      # Dependências Node
├── docs/                  # Documentação completa
└── README.md
```

## 📚 Documentação

Para informações detalhadas sobre o sistema, consulte a [documentação completa](./docs/).

- [Sobre o Sistema](./docs/01-sobre-o-sistema.md) - O que é e como funciona
- [Primeira Utilização](./docs/02-primeira-utilizacao.md) - Guia passo a passo
- [Exemplos de Uso](./docs/03-exemplos.md) - Casos de uso práticos
- [Funcionalidades](./docs/04-funcionalidades.md) - Recursos disponíveis
- [Arquitetura](./docs/05-arquitetura.md) - Estrutura técnica

## 🔧 Configuração Avançada

### Serviços de Tradução

O sistema suporta múltiplos serviços de tradução com fallback automático:

1. **Google Gemini** (requer API key)
2. **OpenRouter** (requer API key)
3. **Groq** (requer API key)
4. **Together AI** (requer API key)
5. **Argos Translate** (offline, requer instalação de modelos)
6. **Deep Translator** (Google Translate, MyMemory)
7. **LibreTranslate** (opcional, requer servidor próprio)
8. **Google Translate (googletrans)** (fallback)

### Instalar Modelos Argos Translate (Opcional)

Para usar tradução offline com Argos Translate:

```bash
cd backend
python -c "import argostranslate.package; argostranslate.package.update_package_index(); packages = argostranslate.package.get_available_packages(); package = [p for p in packages if p.from_code == 'en' and p.to_code == 'pt'][0]; argostranslate.package.install_from_path(package.download())"
```

## 🐛 Solução de Problemas

### Erro de conexão com banco de dados

- Verifique se o PostgreSQL está rodando
- Confirme as credenciais no arquivo `.env`
- Certifique-se de que o banco de dados foi criado

### Erro de módulo não encontrado

- Ative o ambiente virtual
- Reinstale as dependências: `pip install -r requirements.txt`

### Frontend não conecta ao backend

- Verifique se o backend está rodando na porta 8000
- Confirme a variável `VITE_API_URL` no frontend
- Verifique as configurações de CORS no backend

## 📝 Scripts Disponíveis

### Backend
- `npm run init:db` - Inicializa as tabelas do banco de dados (detecta automaticamente o ambiente virtual)
- `python init_db.py` - Inicializa as tabelas (requer ambiente virtual ativado)

### Frontend
- `npm run dev` - Inicia servidor de desenvolvimento
- `npm run build` - Gera build de produção
- `npm run preview` - Preview do build de produção

### Raiz do Projeto
- `npm run dev` - Inicia backend e frontend simultaneamente
- `npm run install:all` - Instala dependências de ambos os projetos
- `npm run init:db` - Inicializa o banco de dados

## 🔒 Segurança

- **NUNCA** commite o arquivo `.env` no repositório
- Gere uma chave de criptografia única para cada ambiente
- Use senhas fortes para o banco de dados
- Em produção, configure HTTPS e variáveis de ambiente seguras

## 📄 Licença

MIT

## 👨‍💻 Desenvolvedor

**Desenvolvido por Igor Sarak - Todos os direitos reservados**

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor, abra uma issue ou pull request.
