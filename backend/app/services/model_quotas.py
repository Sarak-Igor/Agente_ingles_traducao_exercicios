"""
Configuração de cotas e preços por modelo
"""
from typing import Optional

# Limites diários de tokens para modelos gratuitos (free tier)
FREE_TIER_QUOTAS = {
    # Gemini models
    'gemini-1.5-flash': 1_000_000,  # 1M tokens/dia
    'gemini-1.5-pro': 500_000,      # 500K tokens/dia
    'gemini-2.0-flash': 1_000_000,  # 1M tokens/dia
    'gemini-2.5-flash': 1_000_000,  # 1M tokens/dia
    'gemini-2.5-pro': 500_000,      # 500K tokens/dia
    'models/gemini-1.5-flash': 1_000_000,
    'models/gemini-1.5-pro': 500_000,
    'models/gemini-2.0-flash': 1_000_000,
    'models/gemini-2.5-flash': 1_000_000,
    'models/gemini-2.5-pro': 500_000,
    
    # Groq models (free tier)
    'llama-3.1-8b-instant': 30_000,  # 30K tokens/dia
    'llama-3.1-70b-versatile': 30_000,
    'mixtral-8x7b-32768': 30_000,
    
    # Together AI models (free tier)
    'meta-llama/Llama-3-8b-chat-hf': 180_000,  # 180K tokens/dia
    
    # OpenRouter models (free tier - geralmente limitado)
    'openai/gpt-3.5-turbo': 50_000,  # 50K tokens/dia
}

# Preços por modelo para contas pagas (em USD por 1 milhão de tokens)
# Formato: {model_name: {'input': preço_input, 'output': preço_output}}
MODEL_PRICING = {
    # Gemini models
    'gemini-1.5-flash': {
        'input': 0.075 / 1_000_000,   # $0.075 por 1M tokens
        'output': 0.30 / 1_000_000     # $0.30 por 1M tokens
    },
    'gemini-1.5-pro': {
        'input': 0.50 / 1_000_000,     # $0.50 por 1M tokens
        'output': 1.50 / 1_000_000      # $1.50 por 1M tokens
    },
    'gemini-2.0-flash': {
        'input': 0.075 / 1_000_000,
        'output': 0.30 / 1_000_000
    },
    'gemini-2.5-flash': {
        'input': 0.075 / 1_000_000,
        'output': 0.30 / 1_000_000
    },
    'gemini-2.5-pro': {
        'input': 0.50 / 1_000_000,
        'output': 1.50 / 1_000_000
    },
    'models/gemini-1.5-flash': {
        'input': 0.075 / 1_000_000,
        'output': 0.30 / 1_000_000
    },
    'models/gemini-1.5-pro': {
        'input': 0.50 / 1_000_000,
        'output': 1.50 / 1_000_000
    },
    'models/gemini-2.0-flash': {
        'input': 0.075 / 1_000_000,
        'output': 0.30 / 1_000_000
    },
    'models/gemini-2.5-flash': {
        'input': 0.075 / 1_000_000,
        'output': 0.30 / 1_000_000
    },
    'models/gemini-2.5-pro': {
        'input': 0.50 / 1_000_000,
        'output': 1.50 / 1_000_000
    },
    
    # Groq models
    'llama-3.1-8b-instant': {
        'input': 0.20 / 1_000_000,     # $0.20 por 1M tokens
        'output': 0.20 / 1_000_000
    },
    'llama-3.1-70b-versatile': {
        'input': 0.59 / 1_000_000,     # $0.59 por 1M tokens
        'output': 0.79 / 1_000_000
    },
    'mixtral-8x7b-32768': {
        'input': 0.24 / 1_000_000,
        'output': 0.24 / 1_000_000
    },
    
    # Together AI models
    'meta-llama/Llama-3-8b-chat-hf': {
        'input': 0.20 / 1_000_000,
        'output': 0.20 / 1_000_000
    },
    
    # OpenRouter models (preços variam, usando médias)
    'openai/gpt-3.5-turbo': {
        'input': 0.50 / 1_000_000,
        'output': 1.50 / 1_000_000
    },
    'openai/gpt-4': {
        'input': 2.50 / 1_000_000,
        'output': 10.00 / 1_000_000
    },
    'openai/gpt-4-turbo': {
        'input': 2.50 / 1_000_000,
        'output': 10.00 / 1_000_000
    },
}

def get_model_quota_limit(model_name: str) -> Optional[int]:
    """
    Retorna o limite diário de tokens para um modelo gratuito
    """
    # Tenta encontrar o modelo exato
    if model_name in FREE_TIER_QUOTAS:
        return FREE_TIER_QUOTAS[model_name]
    
    # Tenta encontrar por substring (para modelos com prefixos diferentes)
    for model, limit in FREE_TIER_QUOTAS.items():
        if model_name.endswith(model) or model.endswith(model_name):
            return limit
    
    # Retorna None se não encontrar (modelo não tem cota gratuita definida)
    return None

def get_model_pricing(model_name: str) -> Optional[dict]:
    """
    Retorna o preço por token para um modelo pago
    """
    # Tenta encontrar o modelo exato
    if model_name in MODEL_PRICING:
        return MODEL_PRICING[model_name]
    
    # Tenta encontrar por substring
    for model, pricing in MODEL_PRICING.items():
        if model_name.endswith(model) or model.endswith(model_name):
            return pricing
    
    # Retorna preço padrão se não encontrar
    return {
        'input': 1.00 / 1_000_000,  # $1.00 por 1M tokens (padrão conservador)
        'output': 3.00 / 1_000_000   # $3.00 por 1M tokens (padrão conservador)
    }
