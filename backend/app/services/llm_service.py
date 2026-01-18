"""
Serviço base para LLMs (Large Language Models)
Interface comum para diferentes provedores
"""
from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class LLMService(ABC):
    """Interface base para serviços LLM"""
    
    @abstractmethod
    def generate_text(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """
        Gera texto usando o LLM
        
        Args:
            prompt: Prompt para o modelo
            max_tokens: Número máximo de tokens (opcional)
            
        Returns:
            Texto gerado pelo modelo
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Verifica se o serviço está disponível"""
        pass


class OpenRouterLLMService(LLMService):
    """Serviço LLM usando OpenRouter"""
    
    def __init__(self, api_key: str, token_usage_service=None):
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.token_usage_service = token_usage_service
        self.model_name = "openai/gpt-3.5-turbo"  # Modelo padrão
    
    def is_available(self) -> bool:
        """Verifica se a chave está configurada"""
        return bool(self.api_key and self.api_key.strip())
    
    def generate_text(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Gera texto usando OpenRouter"""
        import httpx
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "https://github.com",
                        "X-Title": "Translation System",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "openai/gpt-3.5-turbo",  # Modelo padrão (pode ser configurável)
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": max_tokens or 500
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        result = data["choices"][0]["message"]["content"].strip()
                        
                        # Captura informações de uso de tokens
                        input_tokens = 0
                        output_tokens = 0
                        total_tokens = 0
                        
                        if "usage" in data:
                            usage = data["usage"]
                            input_tokens = usage.get("prompt_tokens", 0)
                            output_tokens = usage.get("completion_tokens", 0)
                            total_tokens = usage.get("total_tokens", 0)
                        
                        # Registra uso de tokens se o serviço estiver disponível
                        if self.token_usage_service and (input_tokens > 0 or output_tokens > 0 or total_tokens > 0):
                            try:
                                self.token_usage_service.record_usage(
                                    service='openrouter',
                                    model=self.model_name,
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                    total_tokens=total_tokens if total_tokens > 0 else None,
                                    requests=1
                                )
                            except Exception as e:
                                logger.debug(f"Erro ao registrar tokens do OpenRouter: {e}")
                        
                        return result
                    else:
                        raise Exception("Resposta vazia do OpenRouter")
                elif response.status_code == 401:
                    raise Exception("Chave de API OpenRouter inválida")
                elif response.status_code == 402:
                    raise Exception("Sem créditos suficientes no OpenRouter")
                else:
                    raise Exception(f"Erro do OpenRouter: Status {response.status_code}")
        except httpx.TimeoutException:
            raise Exception("Timeout ao conectar com OpenRouter")
        except Exception as e:
            logger.error(f"Erro ao gerar texto com OpenRouter: {e}")
            raise


class GroqLLMService(LLMService):
    """Serviço LLM usando Groq"""
    
    def __init__(self, api_key: str, token_usage_service=None):
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1"
        self.token_usage_service = token_usage_service
        self.model_name = "llama-3.1-8b-instant"  # Modelo padrão
    
    def is_available(self) -> bool:
        """Verifica se a chave está configurada"""
        return bool(self.api_key and self.api_key.strip())
    
    def generate_text(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Gera texto usando Groq"""
        import httpx
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.1-8b-instant",  # Modelo rápido e eficiente
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": max_tokens or 500,
                        "temperature": 0.7
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        result = data["choices"][0]["message"]["content"].strip()
                        
                        # Captura informações de uso de tokens
                        input_tokens = 0
                        output_tokens = 0
                        total_tokens = 0
                        
                        if "usage" in data:
                            usage = data["usage"]
                            input_tokens = usage.get("prompt_tokens", 0)
                            output_tokens = usage.get("completion_tokens", 0)
                            total_tokens = usage.get("total_tokens", 0)
                        
                        # Registra uso de tokens se o serviço estiver disponível
                        if self.token_usage_service and (input_tokens > 0 or output_tokens > 0 or total_tokens > 0):
                            try:
                                self.token_usage_service.record_usage(
                                    service='groq',
                                    model=self.model_name,
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                    total_tokens=total_tokens if total_tokens > 0 else None,
                                    requests=1
                                )
                            except Exception as e:
                                logger.debug(f"Erro ao registrar tokens do Groq: {e}")
                        
                        return result
                    else:
                        raise Exception("Resposta vazia do Groq")
                elif response.status_code == 401:
                    raise Exception("Chave de API Groq inválida")
                else:
                    raise Exception(f"Erro do Groq: Status {response.status_code}")
        except httpx.TimeoutException:
            raise Exception("Timeout ao conectar com Groq")
        except Exception as e:
            logger.error(f"Erro ao gerar texto com Groq: {e}")
            raise


class TogetherAILLMService(LLMService):
    """Serviço LLM usando Together AI"""
    
    def __init__(self, api_key: str, token_usage_service=None):
        self.api_key = api_key
        self.base_url = "https://api.together.xyz/v1"
        self.token_usage_service = token_usage_service
        self.model_name = "meta-llama/Llama-3-8b-chat-hf"  # Modelo padrão
    
    def is_available(self) -> bool:
        """Verifica se a chave está configurada"""
        return bool(self.api_key and self.api_key.strip())
    
    def generate_text(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Gera texto usando Together AI"""
        import httpx
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "meta-llama/Llama-3-8b-chat-hf",  # Modelo eficiente
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": max_tokens or 500,
                        "temperature": 0.7
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        result = data["choices"][0]["message"]["content"].strip()
                        
                        # Captura informações de uso de tokens
                        input_tokens = 0
                        output_tokens = 0
                        total_tokens = 0
                        
                        if "usage" in data:
                            usage = data["usage"]
                            input_tokens = usage.get("prompt_tokens", 0)
                            output_tokens = usage.get("completion_tokens", 0)
                            total_tokens = usage.get("total_tokens", 0)
                        
                        # Registra uso de tokens se o serviço estiver disponível
                        if self.token_usage_service and (input_tokens > 0 or output_tokens > 0 or total_tokens > 0):
                            try:
                                self.token_usage_service.record_usage(
                                    service='together',
                                    model=self.model_name,
                                    input_tokens=input_tokens,
                                    output_tokens=output_tokens,
                                    total_tokens=total_tokens if total_tokens > 0 else None,
                                    requests=1
                                )
                            except Exception as e:
                                logger.debug(f"Erro ao registrar tokens do Together AI: {e}")
                        
                        return result
                    else:
                        raise Exception("Resposta vazia do Together AI")
                elif response.status_code == 401:
                    raise Exception("Chave de API Together AI inválida")
                else:
                    raise Exception(f"Erro do Together AI: Status {response.status_code}")
        except httpx.TimeoutException:
            raise Exception("Timeout ao conectar com Together AI")
        except Exception as e:
            logger.error(f"Erro ao gerar texto com Together AI: {e}")
            raise


class GeminiLLMService(LLMService):
    """Adapter para usar GeminiService como LLMService"""
    
    def __init__(self, gemini_service):
        self.gemini_service = gemini_service
    
    def is_available(self) -> bool:
        """Verifica se o serviço está disponível"""
        return self.gemini_service is not None
    
    def generate_text(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Gera texto usando Gemini diretamente"""
        try:
            # Usa o cliente Gemini diretamente para enviar o prompt
            # Sem wrapper de tradução, apenas geração de texto
            max_retries = 3
            tried_models = []
            
            for attempt in range(max_retries):
                # Revalida modelos se necessário
                if self.gemini_service.model_router.should_revalidate():
                    try:
                        logger.info("Revalidando modelos disponíveis...")
                        self.gemini_service.model_router.validate_available_models(self.gemini_service.client)
                    except Exception as e:
                        logger.debug(f"Erro ao revalidar modelos: {e}")
                
                # Obtém próximo modelo disponível
                validated_models = self.gemini_service.model_router.get_validated_models()
                exclude = set(tried_models)
                exclude.update(self.gemini_service.model_router.blocked_models)
                
                available_validated = [m for m in validated_models if m not in exclude]
                if available_validated:
                    model_name = available_validated[0]
                else:
                    model_name = self.gemini_service.model_router.get_next_model(exclude_models=tried_models)
                
                if not model_name:
                    blocked = self.gemini_service.model_router.get_blocked_models_list()
                    validated = self.gemini_service.model_router.get_validated_models()
                    raise Exception(
                        f"Todos os modelos estão indisponíveis. "
                        f"Modelos bloqueados: {blocked}. "
                        f"Modelos validados: {validated}. "
                        f"Verifique suas cotas de API."
                    )
                
                tried_models.append(model_name)
                
                try:
                    response = self.gemini_service.client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    
                    # Extrai texto da resposta
                    result = None
                    if hasattr(response, 'text'):
                        result = response.text.strip()
                    elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'content'):
                            if hasattr(candidate.content, 'parts') and len(candidate.content.parts) > 0:
                                result = candidate.content.parts[0].text.strip()
                            elif hasattr(candidate.content, 'text'):
                                result = candidate.content.text.strip()
                    
                    if result:
                        # Registra sucesso
                        self.gemini_service.model_router.record_success(model_name)
                        
                        # Captura tokens (se disponível)
                        input_tokens = 0
                        output_tokens = 0
                        total_tokens = 0
                        
                        try:
                            if hasattr(response, 'usage_metadata'):
                                usage = response.usage_metadata
                                if hasattr(usage, 'prompt_token_count'):
                                    input_tokens = usage.prompt_token_count
                                if hasattr(usage, 'candidates_token_count'):
                                    output_tokens = usage.candidates_token_count
                                if hasattr(usage, 'total_token_count'):
                                    total_tokens = usage.total_token_count
                        except:
                            pass
                        
                        # Registra uso de tokens
                        if self.gemini_service.token_usage_service and (input_tokens > 0 or output_tokens > 0 or total_tokens > 0):
                            self.gemini_service.token_usage_service.record_usage(
                                service='gemini',
                                model=model_name,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                total_tokens=total_tokens if total_tokens > 0 else None,
                                requests=1
                            )
                        
                        # Remove aspas se presentes
                        result = result.strip('"').strip("'").strip()
                        return result
                        
                except Exception as e:
                    error_str = str(e)
                    
                    # Se for erro de cota, bloqueia modelo e tenta próximo
                    if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'quota' in error_str.lower():
                        self.gemini_service.model_router.record_error(model_name, 'quota')
                        self.gemini_service.model_router.block_model(model_name, 'quota_exceeded')
                        if attempt < max_retries - 1:
                            continue
                    
                    # Para outros erros, propaga
                    raise
            
            raise Exception("Nenhum modelo disponível após todas as tentativas")
            
        except Exception as e:
            logger.error(f"Erro ao gerar texto com Gemini: {e}")
            raise
