# Arquitetura do Sistema

Este documento explica a estrutura técnica e arquitetura do sistema.

## Visão Geral

O sistema é construído com uma arquitetura moderna de **frontend e backend separados**, permitindo escalabilidade e manutenção facilitada.

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Frontend  │ ◄─────► │   Backend   │ ◄─────► │  PostgreSQL │
│   (React)   │  HTTP   │  (FastAPI)  │  SQL    │  (Database) │
└─────────────┘         └─────────────┘         └─────────────┘
                              │
                              ▼
                        ┌─────────────┐
                        │  External   │
                        │    APIs     │
                        │ (Gemini, etc)│
                        └─────────────┘
```

## Backend

### Framework
- **FastAPI** - Framework web moderno e rápido
- **Python 3.9+** - Linguagem principal
- **Uvicorn** - Servidor ASGI

### Estrutura de Diretórios

```
backend/
├── app/
│   ├── api/
│   │   └── routes/          # Endpoints da API
│   │       ├── video.py     # Rotas de vídeos
│   │       ├── jobs.py      # Rotas de trabalhos
│   │       ├── practice.py  # Rotas de prática
│   │       ├── api_keys.py  # Rotas de API keys
│   │       └── usage.py     # Rotas de uso
│   ├── models/
│   │   └── database.py      # Modelos SQLAlchemy
│   ├── schemas/
│   │   └── schemas.py       # Schemas Pydantic
│   ├── services/            # Lógica de negócio
│   │   ├── gemini_service.py
│   │   ├── translation_service.py
│   │   ├── llm_service.py
│   │   ├── token_usage_service.py
│   │   └── ...
│   ├── config.py            # Configurações
│   ├── database.py          # Conexão DB
│   └── main.py              # Aplicação principal
├── requirements.txt         # Dependências
└── .env                     # Variáveis de ambiente
```

### Camadas da Aplicação

#### 1. Camada de API (Routes)
- Recebe requisições HTTP
- Valida entrada com Pydantic
- Chama serviços apropriados
- Retorna respostas JSON

#### 2. Camada de Serviços
- Lógica de negócio
- Integração com APIs externas
- Processamento de dados
- Validações complexas

#### 3. Camada de Dados
- Modelos SQLAlchemy
- Queries ao banco
- Relacionamentos
- Migrações

### Banco de Dados

#### Modelos Principais

**Video**
- Armazena informações dos vídeos do YouTube
- Relacionamento com traduções e API keys

**Translation**
- Armazena traduções completas
- Segmentos de legendas
- Metadados de sincronização

**ApiKey**
- Chaves de API criptografadas
- Relacionamento com vídeos
- Status e validação

**Job**
- Trabalhos de tradução em background
- Status e progresso
- Logs de erro

**TokenUsage**
- Uso de tokens por serviço
- Estatísticas de consumo
- Histórico temporal

### Serviços de Tradução

#### Arquitetura de Fallback

```
Requisição de Tradução
    │
    ├─► Gemini Service (tenta primeiro)
    │   ├─► Sucesso → Retorna
    │   └─► Falha → Próximo
    │
    ├─► OpenRouter Service
    │   ├─► Sucesso → Retorna
    │   └─► Falha → Próximo
    │
    ├─► Groq Service
    │   ├─► Sucesso → Retorna
    │   └─► Falha → Próximo
    │
    └─► Together AI Service
        ├─► Sucesso → Retorna
        └─► Falha → Erro
```

#### Model Router
- Gerencia modelos disponíveis
- Valida modelos na inicialização
- Bloqueia modelos sem cota
- Roteamento inteligente

## Frontend

### Framework
- **React 18+** - Biblioteca de UI
- **TypeScript** - Tipagem estática
- **Vite** - Build tool moderna

### Estrutura de Diretórios

```
frontend/
├── src/
│   ├── components/          # Componentes React
│   │   ├── VideoTranslation/
│   │   ├── KnowledgePractice/
│   │   ├── ApiKeyManager/
│   │   ├── ApiUsage/
│   │   └── ...
│   ├── services/            # Serviços de API
│   │   ├── api.ts           # Cliente HTTP
│   │   └── storage.ts       # LocalStorage
│   ├── contexts/            # Context API
│   │   └── ThemeContext.tsx
│   ├── hooks/               # Custom hooks
│   │   ├── useJobPolling.ts
│   │   └── useVideoTranslation.ts
│   ├── App.tsx              # Componente principal
│   └── main.tsx             # Entry point
├── package.json
└── vite.config.ts
```

### Arquitetura de Componentes

#### Hierarquia

```
App
├── Sidebar (Navegação)
├── VideoTranslation (Tradução)
│   ├── VideoForm
│   ├── VideoList
│   └── VideoDetail
├── KnowledgePractice (Prática)
│   ├── PracticeConfig
│   ├── PracticeExercise
│   └── PracticeStats
├── ApiKeyManager (Chaves)
│   └── ApiKeyForm
└── ApiUsage (Estatísticas)
    └── UsageStats
```

### Estado e Dados

#### Gerenciamento de Estado
- **useState** - Estado local
- **useContext** - Estado global (tema)
- **localStorage** - Persistência
- **API calls** - Dados do servidor

#### Fluxo de Dados

```
Componente
    │
    ├─► useState (estado local)
    ├─► useContext (tema)
    ├─► localStorage (persistência)
    └─► API Service (dados remotos)
        │
        └─► Backend API
            └─► Database
```

## Comunicação Frontend-Backend

### Protocolo
- **HTTP/HTTPS** - Protocolo de comunicação
- **REST API** - Arquitetura de API
- **JSON** - Formato de dados

### Endpoints Principais

```
GET    /api/videos              # Lista vídeos
POST   /api/videos/check        # Verifica vídeo
POST   /api/videos/translate    # Inicia tradução
GET    /api/jobs/{id}           # Status do trabalho
GET    /api/practice/phrase     # Busca frase
POST   /api/practice/phrase/new-context  # Gera frase
POST   /api/practice/check-answer        # Verifica resposta
GET    /api/keys                # Lista chaves
POST   /api/keys/check          # Verifica chave
GET    /api/usage/stats         # Estatísticas
```

## Segurança

### Criptografia
- **Fernet (symmetric)** - Criptografia de chaves de API
- Chave única por instalação
- Armazenamento seguro

### Validação
- **Pydantic** - Validação de entrada
- Sanitização de dados
- Proteção SQL injection (SQLAlchemy)

### CORS
- Configuração de origens permitidas
- Credenciais controladas
- Headers customizados

## Processamento em Background

### Jobs Assíncronos
- Processamento não bloqueante
- Status em tempo real
- Retry automático
- Logs detalhados

### Polling
- Frontend consulta status periodicamente
- Atualização automática de UI
- Notificações de conclusão

## Logging e Monitoramento

### Sistema de Logs
- **Arquivo** - Todos os logs (INFO+)
- **Console** - Apenas erros (ERROR+)
- Rotação diária
- Formato estruturado

### Níveis de Log
- **DEBUG** - Informações detalhadas
- **INFO** - Eventos normais
- **WARNING** - Avisos (apenas arquivo)
- **ERROR** - Erros críticos
- **CRITICAL** - Falhas graves

## Escalabilidade

### Atual
- Processamento assíncrono
- Pool de conexões
- Cache quando possível
- Otimização de queries

### Futuro
- Horizontal scaling
- Load balancing
- Message queue (Redis/RabbitMQ)
- Microserviços

## Dependências Principais

### Backend
- `fastapi` - Framework web
- `sqlalchemy` - ORM
- `psycopg2` - Driver PostgreSQL
- `google-genai` - Gemini API
- `httpx` - Cliente HTTP
- `cryptography` - Criptografia

### Frontend
- `react` - Biblioteca UI
- `typescript` - Tipagem
- `vite` - Build tool
- `axios` - Cliente HTTP (se usado)

## Considerações de Performance

### Backend
- Queries otimizadas
- Índices no banco
- Lazy loading
- Connection pooling

### Frontend
- Code splitting
- Lazy loading de componentes
- Memoização quando necessário
- Otimização de re-renders

## Próximos Passos

Para começar a desenvolver ou contribuir, consulte:
- [Primeira Utilização](./02-primeira-utilizacao.md)
- [Exemplos de Uso](./03-exemplos.md)
- [Funcionalidades](./04-funcionalidades.md)
