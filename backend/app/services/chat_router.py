"""
Agente roteador inteligente para chat de aprendizado de idiomas
Seleciona o melhor modelo baseado em contexto, modo de treino e disponibilidade
"""
from typing import Optional, Dict, List
from app.services.model_router import ModelRouter
from app.services.multi_service_model_router import MultiServiceModelRouter
from app.services.llm_service import LLMService, GeminiLLMService, OpenRouterLLMService, GroqLLMService, TogetherAILLMService
from app.models.database import UserProfile
import logging
import asyncio

logger = logging.getLogger(__name__)


class ChatRouter:
    """
    Roteador inteligente para chat de aprendizado de idiomas
    Seleciona modelos baseado em:
    - Modo de treino (writing vs conversation)
    - Nível de proficiência do usuário
    - Disponibilidade de modelos
    - Preferências do usuário
    """
    
    def __init__(
        self,
        gemini_service=None,
        openrouter_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        together_api_key: Optional[str] = None,
        token_usage_service=None
    ):
        self.gemini_service = gemini_service
        self.openrouter_api_key = openrouter_api_key
        self.groq_api_key = groq_api_key
        self.together_api_key = together_api_key
        self.token_usage_service = token_usage_service
        
        # Inicializa MultiServiceModelRouter para seleção dinâmica
        self.multi_service_router = MultiServiceModelRouter()
        
        # Inicializa serviços LLM disponíveis
        self.available_services: Dict[str, LLMService] = {}
        
        if gemini_service:
            self.available_services['gemini'] = GeminiLLMService(gemini_service)
        
        if openrouter_api_key:
            try:
                self.available_services['openrouter'] = OpenRouterLLMService(
                    openrouter_api_key,
                    token_usage_service
                )
            except Exception as e:
                logger.warning(f"Erro ao inicializar OpenRouter: {e}")
        
        if groq_api_key:
            try:
                self.available_services['groq'] = GroqLLMService(
                    groq_api_key,
                    token_usage_service
                )
            except Exception as e:
                logger.warning(f"Erro ao inicializar Groq: {e}")
        
        if together_api_key:
            try:
                self.available_services['together'] = TogetherAILLMService(
                    together_api_key,
                    token_usage_service
                )
            except Exception as e:
                logger.warning(f"Erro ao inicializar Together AI: {e}")
    
    def get_available_services(self) -> List[str]:
        """Retorna lista de serviços disponíveis"""
        return list(self.available_services.keys())
    
    def select_best_model(
        self,
        mode: str = "writing",
        user_profile: Optional[UserProfile] = None,
        preferred_service: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Seleciona o melhor modelo para o contexto do chat
        
        Args:
            mode: Modo de treino ('writing' ou 'conversation')
            user_profile: Perfil do usuário (opcional)
            preferred_service: Serviço preferido do usuário (opcional)
        
        Returns:
            Dict com 'service' e 'model' ou None se nenhum disponível
        """
        # Prioridade baseada em modo e disponibilidade
        service_priority = self._get_service_priority(mode, user_profile, preferred_service)
        
        # Tenta cada serviço em ordem de prioridade
        for service_name in service_priority:
            if service_name in self.available_services:
                service = self.available_services[service_name]
                
                # Verifica se serviço está disponível
                if not service.is_available():
                    continue
                
                # Para Gemini, usa o ModelRouter para selecionar modelo específico
                if service_name == 'gemini' and self.gemini_service:
                    model_name = self.gemini_service.model_router.get_next_model()
                    if model_name:
                        return {
                            'service': 'gemini',
                            'model': model_name
                        }
                else:
                    # Para outros serviços, usa MultiServiceModelRouter para seleção dinâmica
                    available_models = self._get_available_models_sync(service_name)
                    if service_name == 'openrouter':
                        model_name = self.multi_service_router.select_openrouter_model(
                            mode, available_models
                        )
                    elif service_name == 'groq':
                        model_name = self.multi_service_router.select_groq_model(
                            mode, available_models
                        )
                    elif service_name == 'together':
                        model_name = self.multi_service_router.select_together_model(
                            mode, available_models
                        )
                    else:
                        # Fallback para modelo padrão do serviço
                        model_name = getattr(service, 'model_name', service_name)
                    
                    return {
                        'service': service_name,
                        'model': model_name
                    }
        
        # Nenhum serviço disponível
        logger.warning("Nenhum serviço LLM disponível para chat")
        return None
    
    def _get_available_models_sync(self, service: str) -> Optional[List[str]]:
        """
        Obtém modelos disponíveis de forma síncrona (com fallback)
        
        Args:
            service: Nome do serviço
        
        Returns:
            Lista de modelos disponíveis ou None
        """
        # Tenta obter do cache primeiro
        cached_models = self.multi_service_router.get_cached_models(service)
        if cached_models:
            return cached_models
        
        # Se não tem cache, retorna None (será usado fallback)
        # O cache será preenchido quando necessário via endpoint async
        return None
    
    async def get_available_models(self, service: str) -> List[Dict]:
        """
        Obtém lista de modelos disponíveis para um serviço
        
        Args:
            service: Nome do serviço ('openrouter', 'groq', 'together')
        
        Returns:
            Lista de dicionários com informações dos modelos
        """
        from app.services.api_status_checker import ApiStatusChecker
        
        # Verifica cache primeiro
        cached_models = self.multi_service_router.get_cached_models(service)
        if cached_models:
            return [
                {'name': model, 'available': True}
                for model in cached_models
            ]
        
        # Busca modelos via ApiStatusChecker
        try:
            api_key = None
            if service == 'openrouter':
                api_key = self.openrouter_api_key
            elif service == 'groq':
                api_key = self.groq_api_key
            elif service == 'together':
                api_key = self.together_api_key
            
            if not api_key:
                return []
            
            status = await ApiStatusChecker.check_status(service, api_key)
            
            if status.get('is_valid') and status.get('available_models'):
                models = status['available_models']
                # Armazena no cache
                self.multi_service_router.set_cached_models(service, models)
                
                return [
                    {
                        'name': model,
                        'available': True,
                        'blocked': False
                    }
                    for model in models
                ]
        except Exception as e:
            logger.warning(f"Erro ao obter modelos de {service}: {e}")
        
        return []
    
    def _get_service_priority(
        self,
        mode: str,
        user_profile: Optional[UserProfile],
        preferred_service: Optional[str]
    ) -> List[str]:
        """
        Define prioridade de serviços baseado em contexto
        
        Para writing: prioriza modelos com melhor gramática (Gemini, OpenRouter)
        Para conversation: prioriza modelos rápidos (Groq, Together)
        """
        # Se usuário tem preferência, coloca primeiro
        priority = []
        if preferred_service and preferred_service in self.available_services:
            priority.append(preferred_service)
        
        if mode == "writing":
            # Modo escrita: prioriza modelos com melhor qualidade de texto
            writing_priority = ['gemini', 'openrouter', 'together', 'groq']
            for service in writing_priority:
                if service not in priority and service in self.available_services:
                    priority.append(service)
        else:
            # Modo conversa: prioriza modelos rápidos
            conversation_priority = ['groq', 'together', 'gemini', 'openrouter']
            for service in conversation_priority:
                if service not in priority and service in self.available_services:
                    priority.append(service)
        
        return priority
    
    def get_service(self, service_name: str) -> Optional[LLMService]:
        """Retorna serviço LLM pelo nome"""
        return self.available_services.get(service_name)
    
    def is_service_available(self, service_name: str) -> bool:
        """Verifica se serviço está disponível"""
        if service_name not in self.available_services:
            return False
        return self.available_services[service_name].is_available()
    
    def get_all_available_models(self) -> Dict[str, List[Dict]]:
        """
        Retorna todos os modelos disponíveis de todos os serviços
        Versão síncrona que usa cache
        
        Returns:
            Dict com modelos por serviço
        """
        result = {}
        
        # Gemini
        if 'gemini' in self.available_services and self.gemini_service:
            try:
                available_models = self.gemini_service.model_router.get_available_models()
                validated_models = self.gemini_service.model_router.get_validated_models()
                result['gemini'] = [
                    {
                        'name': model,
                        'available': model in validated_models,
                        'category': self.gemini_service.model_router.categorize_model(model)
                    }
                    for model in available_models
                ]
            except Exception as e:
                logger.warning(f"Erro ao obter modelos Gemini: {e}")
                result['gemini'] = []
        
        # Outros serviços (do cache)
        for service in ['openrouter', 'groq', 'together']:
            if service in self.available_services:
                cached_models = self.multi_service_router.get_cached_models(service)
                if cached_models:
                    result[service] = [
                        {'name': model, 'available': True}
                        for model in cached_models
                    ]
                else:
                    result[service] = []
        
        return result