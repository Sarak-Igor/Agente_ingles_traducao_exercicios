# Primeira Utilização

Este guia irá te ajudar a configurar e usar o sistema pela primeira vez.

## Passo 1: Instalação

### 1.1. Pré-requisitos

Certifique-se de ter instalado:
- Python 3.9 ou superior
- Node.js 18 ou superior
- PostgreSQL 12 ou superior
- npm ou yarn

### 1.2. Clonar o Repositório

```bash
git clone <url-do-repositorio>
cd Tradução
```

### 1.3. Instalar Dependências

Na raiz do projeto:

```bash
npm run install:all
```

Este comando instala automaticamente as dependências do backend e frontend.

## Passo 2: Configuração do Banco de Dados

### 2.1. Criar Banco de Dados

Acesse o PostgreSQL e crie um banco de dados:

```sql
CREATE DATABASE agente_traducao;
```

### 2.2. Configurar Variáveis de Ambiente

No diretório `backend`, copie o arquivo de exemplo:

```bash
cd backend
cp env.example .env
```

Edite o arquivo `.env` com suas configurações:

```env
DATABASE_URL=postgresql://usuario:senha@localhost:5432/agente_traducao
ENCRYPTION_KEY=sua_chave_fernet_aqui
```

**Importante:** Gere uma chave de criptografia:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Cole o resultado no campo `ENCRYPTION_KEY` do arquivo `.env`.

### 2.3. Inicializar Tabelas

Na raiz do projeto:

```bash
npm run init:db
```

Ou manualmente:

```bash
cd backend
python init_db.py
```

## Passo 3: Configurar API Keys (Opcional mas Recomendado)

### 3.1. Obter Chaves de API

Para melhor qualidade de tradução, configure pelo menos uma das seguintes:

- **Google Gemini**: https://makersuite.google.com/app/apikey
- **OpenRouter**: https://openrouter.ai/keys
- **Groq**: https://console.groq.com/keys
- **Together AI**: https://api.together.xyz/settings/api-keys

### 3.2. Adicionar Chaves no Sistema

1. Inicie o sistema (veja Passo 4)
2. Acesse a aba "Chaves API"
3. Clique em "Adicionar Chave"
4. Selecione o serviço e cole a chave
5. Clique em "Salvar"
6. Clique em "Verificar Cotas" para validar

## Passo 4: Iniciar o Sistema

### 4.1. Executar Backend e Frontend

Na raiz do projeto:

```bash
npm run dev
```

Este comando inicia automaticamente:
- Backend na porta 8000
- Frontend na porta 5173

### 4.2. Acessar a Interface

Abra seu navegador em:

```
http://localhost:5173
```

## Passo 5: Primeira Tradução

### 5.1. Adicionar um Vídeo

1. Na aba "Traduzir Vídeo", cole a URL do YouTube
2. Selecione o idioma de origem e destino
3. Clique em "Verificar Vídeo"

### 5.2. Iniciar Tradução

1. Após verificar, clique em "Iniciar Tradução"
2. Aguarde o processamento (pode levar alguns minutos)
3. O progresso será exibido em tempo real

### 5.3. Visualizar Resultado

1. Após concluir, a tradução aparecerá na lista
2. Clique no vídeo para ver os detalhes
3. Você pode visualizar, editar e exportar as legendas

## Passo 6: Usar o Treinamento de Inglês

### 6.1. Acessar a Aba

Clique em "Treinar Inglês" na barra lateral.

### 6.2. Escolher Modalidade

- **Frases das Músicas**: Praticar com frases dos vídeos traduzidos
- **Palavras em Novos Contextos**: Gerar frases novas com palavras aprendidas
- **Adicionar Palavras**: Praticar com palavras específicas

### 6.3. Configurar

1. Selecione a direção (Inglês → Português ou vice-versa)
2. Escolha a dificuldade
3. Selecione os vídeos (ou adicione palavras)
4. Clique em "Iniciar"

### 6.4. Praticar

1. Leia a frase/palavra exibida
2. Digite sua tradução
3. Clique em "Verificar" ou pressione Enter
4. Veja o resultado e continue para a próxima

## Dicas Importantes

### 💡 Performance
- Configure pelo menos uma API key para melhor qualidade
- Use Gemini para traduções mais precisas
- OpenRouter oferece acesso a múltiplos modelos

### 💡 Segurança
- Nunca compartilhe suas chaves de API
- Mantenha o arquivo `.env` seguro
- Use senhas fortes no banco de dados

### 💡 Otimização
- Traduções longas podem levar tempo
- O sistema processa em background
- Você pode fechar a aba e voltar depois

## Solução de Problemas Comuns

### Erro ao conectar ao banco
- Verifique se o PostgreSQL está rodando
- Confirme as credenciais no `.env`
- Certifique-se de que o banco foi criado

### Vídeo não encontrado
- Verifique se a URL está correta
- Certifique-se de que o vídeo tem legendas
- Tente vídeos em outros idiomas

### Tradução falha
- Verifique se há chaves de API configuradas
- Veja os logs no terminal para mais detalhes
- Tente com outro vídeo

## Próximos Passos

- Veja [Exemplos de Uso](./03-exemplos.md) para casos práticos
- Consulte [Funcionalidades](./04-funcionalidades.md) para recursos avançados
- Leia [Arquitetura](./05-arquitetura.md) para entender a estrutura técnica
