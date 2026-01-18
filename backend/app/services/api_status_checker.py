"""
Serviço para verificar status e cotas de diferentes APIs
"""
from typing import Dict, List, Optional
import httpx
import logging

logger = logging.getLogger(__name__)


class ApiStatusChecker:
    """Classe base para verificação de status de APIs"""
    
    @staticmethod
    async def check_openrouter_status(api_key: str) -> Dict:
        """
        Verifica status da chave OpenRouter
        OpenRouter não tem endpoint público de quota, então fazemos uma chamada de teste
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Primeiro, tenta listar modelos públicos (sem auth) para ver estrutura
                # Depois, tenta com auth para validar a chave
                
                # Tenta fazer uma chamada de teste muito pequena para validar a chave
                test_response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://github.com",
                        "X-Title": "Translation System",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "openai/gpt-3.5-turbo",
                        "messages": [{"role": "user", "content": "test"}],
                        "max_tokens": 1
                    }
                )
                
                # Se a chamada de teste funcionar, a chave é válida
                if test_response.status_code == 200:
                    # Agora tenta listar modelos disponíveis
                    models_response = await client.get(
                        "https://openrouter.ai/api/v1/models",
                        headers={
                            "HTTP-Referer": "https://github.com",
                            "X-Title": "Translation System"
                        }
                    )
                    
                    models = []
                    if models_response.status_code == 200:
                        models_data = models_response.json()
                        if isinstance(models_data, dict):
                            models = models_data.get("data", [])
                        elif isinstance(models_data, list):
                            models = models_data
                    
                    # Limita a modelos mais populares
                    popular_models = [
                        "openai/gpt-4",
                        "openai/gpt-3.5-turbo",
                        "anthropic/claude-3-haiku",
                        "google/gemini-pro",
                        "meta-llama/llama-3-8b-instruct"
                    ]
                    
                    return {
                        "is_valid": True,
                        "models_status": [
                            {
                                "name": model_id,
                                "available": True,
                                "blocked": False,
                                "status": "available"
                            }
                            for model_id in popular_models
                        ],
                        "available_models": popular_models,
                        "blocked_models": [],
                        "error": None,
                        "info": "Chave válida. OpenRouter oferece acesso a múltiplos modelos."
                    }
                elif test_response.status_code == 401:
                    return {
                        "is_valid": False,
                        "models_status": [],
                        "available_models": [],
                        "blocked_models": [],
                        "error": "Chave de API inválida ou não autorizada"
                    }
                elif test_response.status_code == 402:
                    return {
                        "is_valid": False,
                        "models_status": [],
                        "available_models": [],
                        "blocked_models": [],
                        "error": "Sem créditos suficientes na conta OpenRouter"
                    }
                else:
                    error_text = test_response.text[:200] if hasattr(test_response, 'text') else ""
                    return {
                        "is_valid": False,
                        "models_status": [],
                        "available_models": [],
                        "blocked_models": [],
                        "error": f"Erro ao verificar: Status {test_response.status_code}. {error_text}"
                    }
        except httpx.TimeoutException:
            return {
                "is_valid": False,
                "models_status": [],
                "available_models": [],
                "blocked_models": [],
                "error": "Timeout ao conectar com OpenRouter. Verifique sua conexão."
            }
        except Exception as e:
            logger.error(f"Erro ao verificar OpenRouter: {e}")
            return {
                "is_valid": False,
                "models_status": [],
                "available_models": [],
                "blocked_models": [],
                "error": f"Erro ao conectar: {str(e)}"
            }
    
    @staticmethod
    async def check_groq_status(api_key: str) -> Dict:
        """
        Verifica status da chave Groq
        Groq não tem endpoint público de quota, então fazemos uma chamada de teste
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Tenta listar modelos para verificar se a chave é válida
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    models_data = response.json()
                    models = models_data.get("data", [])
                    
                    return {
                        "is_valid": True,
                        "models_status": [
                            {
                                "name": model.get("id", "unknown"),
                                "available": True,
                                "blocked": False,
                                "status": "available"
                            }
                            for model in models
                        ],
                        "available_models": [model.get("id") for model in models],
                        "blocked_models": [],
                        "error": None,
                        "info": f"{len(models)} modelos disponíveis"
                    }
                elif response.status_code == 401:
                    return {
                        "is_valid": False,
                        "models_status": [],
                        "available_models": [],
                        "blocked_models": [],
                        "error": "Chave de API inválida ou não autorizada"
                    }
                else:
                    return {
                        "is_valid": False,
                        "models_status": [],
                        "available_models": [],
                        "blocked_models": [],
                        "error": f"Erro ao verificar: Status {response.status_code}"
                    }
        except Exception as e:
            logger.error(f"Erro ao verificar Groq: {e}")
            return {
                "is_valid": False,
                "models_status": [],
                "available_models": [],
                "blocked_models": [],
                "error": f"Erro ao conectar: {str(e)}"
            }
    
    @staticmethod
    async def check_together_status(api_key: str) -> Dict:
        """
        Verifica status da chave Together AI
        Together AI não tem endpoint público de quota, então fazemos uma chamada de teste
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Tenta listar modelos para verificar se a chave é válida
                response = await client.get(
                    "https://api.together.xyz/v1/models",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    models_data = response.json()
                    
                    # Together AI pode retornar lista direta ou objeto com 'data'
                    if isinstance(models_data, list):
                        models = models_data
                    elif isinstance(models_data, dict):
                        models = models_data.get("data", [])
                    else:
                        models = []
                    
                    # Extrai nomes dos modelos
                    model_names = []
                    for model in models[:15]:  # Limita a 15 modelos
                        if isinstance(model, dict):
                            name = model.get("id") or model.get("name") or model.get("model_id")
                        elif isinstance(model, str):
                            name = model
                        else:
                            continue
                        
                        if name:
                            model_names.append(name)
                    
                    return {
                        "is_valid": True,
                        "models_status": [
                            {
                                "name": name,
                                "available": True,
                                "blocked": False,
                                "status": "available"
                            }
                            for name in model_names
                        ],
                        "available_models": model_names,
                        "blocked_models": [],
                        "error": None,
                        "info": f"{len(model_names)} modelos disponíveis"
                    }
                elif response.status_code == 401:
                    return {
                        "is_valid": False,
                        "models_status": [],
                        "available_models": [],
                        "blocked_models": [],
                        "error": "Chave de API inválida ou não autorizada"
                    }
                else:
                    return {
                        "is_valid": False,
                        "models_status": [],
                        "available_models": [],
                        "blocked_models": [],
                        "error": f"Erro ao verificar: Status {response.status_code}"
                    }
        except Exception as e:
            logger.error(f"Erro ao verificar Together AI: {e}")
            return {
                "is_valid": False,
                "models_status": [],
                "available_models": [],
                "blocked_models": [],
                "error": f"Erro ao conectar: {str(e)}"
            }
    
    @staticmethod
    async def check_status(service: str, api_key: str) -> Dict:
        """
        Verifica status de uma API baseado no serviço
        
        Args:
            service: Nome do serviço ('gemini', 'openrouter', 'groq', 'together')
            api_key: Chave de API
            
        Returns:
            Dict com informações de status
        """
        if service == "openrouter":
            return await ApiStatusChecker.check_openrouter_status(api_key)
        elif service == "groq":
            return await ApiStatusChecker.check_groq_status(api_key)
        elif service == "together":
            return await ApiStatusChecker.check_together_status(api_key)
        else:
            return {
                "is_valid": False,
                "models_status": [],
                "available_models": [],
                "blocked_models": [],
                "error": f"Serviço '{service}' não suportado para verificação de status"
            }
