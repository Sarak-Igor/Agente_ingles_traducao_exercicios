# Sobre o Sistema

## O que é?

O Sistema de Tradução de Vídeos do YouTube é uma plataforma completa e automatizada para traduzir legendas de vídeos do YouTube de forma rápida, precisa e eficiente. O sistema utiliza inteligência artificial e múltiplos serviços de tradução para garantir alta qualidade nas traduções.

## Principais Características

### 🤖 Automação Completa
- Extração automática de legendas do YouTube
- Tradução automática com múltiplos serviços
- Sincronização perfeita com o áudio original
- Processamento em background

### 🎯 Múltiplos Serviços de Tradução
O sistema suporta diversos serviços de tradução com fallback automático:
- **Google Gemini** - IA avançada da Google
- **OpenRouter** - Gateway para múltiplos modelos de IA
- **Groq** - Processamento ultra-rápido
- **Together AI** - Modelos open-source
- **Argos Translate** - Tradução offline
- **Deep Translator** - Google Translate e MyMemory
- **LibreTranslate** - Servidor próprio

### 📊 Gerenciamento de API Keys
- Armazenamento seguro e criptografado
- Verificação automática de cotas
- Monitoramento de uso de tokens
- Suporte a múltiplas chaves por serviço

### 📚 Treinamento de Inglês
- Prática com frases das músicas traduzidas
- Geração de frases em novos contextos
- Modo de palavras avulsas
- Estatísticas detalhadas
- Salvamento de sessões

### 🎨 Interface Moderna
- Design responsivo e intuitivo
- Tema claro e escuro
- Feedback visual em tempo real
- Progresso de tradução em tempo real

## Como Funciona?

### 1. Extração de Legendas
O sistema acessa o YouTube e extrai as legendas disponíveis do vídeo, seja em formato automático ou manual.

### 2. Processamento
As legendas são segmentadas e processadas, mantendo a sincronização com o áudio original.

### 3. Tradução
O sistema tenta traduzir usando os serviços configurados em ordem de prioridade, com fallback automático caso um serviço falhe.

### 4. Armazenamento
As traduções são salvas no banco de dados PostgreSQL, permitindo acesso rápido e histórico completo.

### 5. Visualização
A interface web permite visualizar, editar e exportar as traduções de forma intuitiva.

## Tecnologias Utilizadas

### Backend
- **FastAPI** - Framework web moderno e rápido
- **PostgreSQL** - Banco de dados relacional robusto
- **SQLAlchemy** - ORM para Python
- **Google Gemini API** - IA para tradução
- **Python 3.9+** - Linguagem principal

### Frontend
- **React** - Biblioteca para interfaces
- **TypeScript** - Tipagem estática
- **Vite** - Build tool moderna
- **CSS Variables** - Temas dinâmicos

## Casos de Uso

### Para Criadores de Conteúdo
- Traduzir vídeos para alcançar audiência internacional
- Criar legendas em múltiplos idiomas
- Melhorar acessibilidade do conteúdo

### Para Estudantes
- Praticar idiomas com conteúdo real
- Aprender vocabulário através de músicas
- Treinar tradução de forma interativa

### Para Empresas
- Localizar conteúdo de vídeo
- Criar versões multilíngue de treinamentos
- Automatizar processos de tradução

## Vantagens

✅ **Rápido** - Processamento em background, não bloqueia a interface  
✅ **Preciso** - Múltiplos serviços garantem qualidade  
✅ **Confiável** - Fallback automático em caso de falhas  
✅ **Seguro** - Chaves de API criptografadas  
✅ **Escalável** - Suporta múltiplos vídeos simultaneamente  
✅ **Flexível** - Configurável para diferentes necessidades  

## Próximos Passos

Consulte o guia de [Primeira Utilização](./02-primeira-utilizacao.md) para começar a usar o sistema.
