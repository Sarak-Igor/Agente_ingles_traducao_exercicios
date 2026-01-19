"""
Roteador de modelos para serviços LLM não-Gemini
Seleciona modelos dinamicamente baseado em modo (writing/conversation) e disponibilidade
"""
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class MultiServiceModelRouter:
    """
    Roteador inteligente para seleção de modelos de outras APIs
    Similar ao ModelRouter do Gemini, mas para OpenRouter, Groq e Together
    """
    
    # Modelos padrão em ordem de prioridade para cada serviço
    OPENROUTER_DEFAULT_MODELS_WRITING = [
        "openai/gpt-4",  # Melhor qualidade
        "openai/gpt-3.5-turbo",  # Balanceado
        "anthropic/claude-3-haiku",  # Alternativa
        "google/gemini-pro",  # Alternativa
        "meta-llama/llama-3-8b-instruct"  # Fallback
    ]
    
    OPENROUTER_DEFAULT_MODELS_CONVERSATION = [
        "openai/gpt-3.5-turbo",  # Rápido e eficiente
        "anthropic/claude-3-haiku",  # Muito rápido
        "openai/gpt-4",  # Se precisar qualidade
        "google/gemini-pro",  # Alternativa
        "meta-llama/llama-3-8b-instruct"  # Fallback
    ]
    
    GROQ_DEFAULT_MODELS_WRITING = [
        "llama-3.3-70b-versatile",  # Melhor qualidade
        "mixtral-8x7b-32768",  # Alternativa
        "llama-3.1-70b-versatile",  # Alternativa
        "llama-3.1-8b-instant"  # Fallback
    ]
    
    GROQ_DEFAULT_MODELS_CONVERSATION = [
        "llama-3.1-8b-instant",  # Mais rápido
        "llama-3.1-70b-versatile",  # Se precisar qualidade
        "llama-3.3-70b-versatile",  # Alternativa
        "mixtral-8x7b-32768"  # Fallback
    ]
    
    TOGETHER_DEFAULT_MODELS_WRITING = [
        "meta-llama/Llama-3-70b-chat-hf",  # Melhor qualidade
        "meta-llama/Llama-3-8b-chat-hf",  # Fallback
        "mistralai/Mixtral-8x7B-Instruct-v0.1"  # Alternativa
    ]
    
    TOGETHER_DEFAULT_MODELS_CONVERSATION = [
        "meta-llama/Llama-3-8b-chat-hf",  # Mais rápido
        "meta-llama/Llama-3-70b-chat-hf",  # Se precisar qualidade
        "mistralai/Mixtral-8x7B-Instruct-v0.1"  # Alternativa
    ]
    
    def __init__(self):
        """Inicializa o roteador"""
        # Cache de modelos disponíveis por serviço
        self._models_cache: Dict[str, Dict] = {}
        self._cache_timestamp: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(hours=1)  # Cache válido por 1 hora
    
    def select_openrouter_model(
        self,
        mode: str,
        available_models: Optional[List[str]] = None
    ) -> str:
        """
        Seleciona melhor modelo OpenRouter baseado no modo
        
        Args:
            mode: 'writing' ou 'conversation'
            available_models: Lista de modelos disponíveis (opcional)
        
        Returns:
            Nome do modelo selecionado
        """
        if available_models:
            # Filtra modelos disponíveis pela lista de prioridade
            if mode == "writing":
                priority_list = self.OPENROUTER_DEFAULT_MODELS_WRITING
            else:
                priority_list = self.OPENROUTER_DEFAULT_MODELS_CONVERSATION
            
            # Tenta encontrar primeiro modelo da lista de prioridade que está disponível
            for model in priority_list:
                if model in available_models:
                    return model
            
            # Se nenhum da lista de prioridade está disponível, retorna o primeiro disponível
            if available_models:
                return available_models[0]
        
        # Fallback: retorna modelo padrão baseado no modo
        if mode == "writing":
            return self.OPENROUTER_DEFAULT_MODELS_WRITING[0]
        else:
            return self.OPENROUTER_DEFAULT_MODELS_CONVERSATION[0]
    
    def select_groq_model(
        self,
        mode: str,
        available_models: Optional[List[str]] = None
    ) -> str:
        """
        Seleciona melhor modelo Groq baseado no modo
        
        Args:
            mode: 'writing' ou 'conversation'
            available_models: Lista de modelos disponíveis (opcional)
        
        Returns:
            Nome do modelo selecionado
        """
        if available_models:
            # Filtra modelos disponíveis pela lista de prioridade
            if mode == "writing":
                priority_list = self.GROQ_DEFAULT_MODELS_WRITING
            else:
                priority_list = self.GROQ_DEFAULT_MODELS_CONVERSATION
            
            # Tenta encontrar primeiro modelo da lista de prioridade que está disponível
            for model in priority_list:
                if model in available_models:
                    return model
            
            # Se nenhum da lista de prioridade está disponível, retorna o primeiro disponível
            if available_models:
                return available_models[0]
        
        # Fallback: retorna modelo padrão baseado no modo
        if mode == "writing":
            return self.GROQ_DEFAULT_MODELS_WRITING[0]
        else:
            return self.GROQ_DEFAULT_MODELS_CONVERSATION[0]
    
    def select_together_model(
        self,
        mode: str,
        available_models: Optional[List[str]] = None
    ) -> str:
        """
        Seleciona melhor modelo Together baseado no modo
        
        Args:
            mode: 'writing' ou 'conversation'
            available_models: Lista de modelos disponíveis (opcional)
        
        Returns:
            Nome do modelo selecionado
        """
        if available_models:
            # Filtra modelos disponíveis pela lista de prioridade
            if mode == "writing":
                priority_list = self.TOGETHER_DEFAULT_MODELS_WRITING
            else:
                priority_list = self.TOGETHER_DEFAULT_MODELS_CONVERSATION
            
            # Tenta encontrar primeiro modelo da lista de prioridade que está disponível
            for model in priority_list:
                if model in available_models:
                    return model
            
            # Se nenhum da lista de prioridade está disponível, retorna o primeiro disponível
            if available_models:
                return available_models[0]
        
        # Fallback: retorna modelo padrão baseado no modo
        if mode == "writing":
            return self.TOGETHER_DEFAULT_MODELS_WRITING[0]
        else:
            return self.TOGETHER_DEFAULT_MODELS_CONVERSATION[0]
    
    def get_cached_models(self, service: str) -> Optional[List[str]]:
        """
        Retorna modelos em cache para um serviço
        
        Args:
            service: Nome do serviço ('openrouter', 'groq', 'together')
        
        Returns:
            Lista de modelos ou None se cache expirado/inexistente
        """
        if service not in self._models_cache:
            return None
        
        if service not in self._cache_timestamp:
            return None
        
        # Verifica se cache ainda é válido
        if datetime.now() - self._cache_timestamp[service] > self._cache_ttl:
            return None
        
        return self._models_cache[service].get('models', None)
    
    def set_cached_models(self, service: str, models: List[str]):
        """
        Armazena modelos em cache
        
        Args:
            service: Nome do serviço
            models: Lista de modelos disponíveis
        """
        self._models_cache[service] = {'models': models}
        self._cache_timestamp[service] = datetime.now()
    
    def clear_cache(self, service: Optional[str] = None):
        """
        Limpa cache de modelos
        
        Args:
            service: Nome do serviço (None para limpar todos)
        """
        if service:
            self._models_cache.pop(service, None)
            self._cache_timestamp.pop(service, None)
        else:
            self._models_cache.clear()
            self._cache_timestamp.clear()
