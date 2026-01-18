"""
Factory para criar serviços de tradução
Permite trocar facilmente entre diferentes provedores
"""
from typing import Dict, Any, Optional, List
from app.services.translation_service import TranslationService
from app.services.libretranslate_service import LibreTranslateService
import logging

# Import condicional do GeminiService
try:
    from app.services.gemini_service import GeminiService
except ImportError:
    GeminiService = None

logger = logging.getLogger(__name__)


class TranslationServiceFactory:
    """
    Factory para criar instâncias de serviços de tradução
    """
    
    @staticmethod
    def create(
        service_type: str,
        config: Dict[str, Any]
    ) -> TranslationService:
        """
        Cria uma instância do serviço de tradução especificado
        
        Args:
            service_type: Tipo de serviço ('gemini', 'libretranslate', etc.)
            config: Configuração do serviço (API keys, URLs, etc.)
        
        Returns:
            Instância do serviço de tradução
        
        Raises:
            ValueError: Se o tipo de serviço não for suportado
        """
        service_type = service_type.lower()
        
        if service_type == 'gemini':
            if GeminiService is None:
                raise ImportError("GeminiService não está disponível. Verifique se google-genai está instalado.")
            return GeminiServiceAdapter(config)
        elif service_type == 'libretranslate':
            return LibreTranslateService(config)
        elif service_type == 'argos' or service_type == 'argostranslate':
            from app.services.argos_translate_service import ArgosTranslateService
            return ArgosTranslateService(config)
        elif service_type == 'googletrans' or service_type == 'googletranslate':
            from app.services.googletranslate_service import GoogleTranslateService
            return GoogleTranslateService(config)
        elif service_type == 'deeptranslator' or service_type == 'deep-translator':
            from app.services.deep_translator_service import DeepTranslatorService
            return DeepTranslatorService(config)
        else:
            raise ValueError(f"Tipo de serviço não suportado: {service_type}")
    
    @staticmethod
    def create_auto_fallback(
        preferred_service: str,
        fallback_services: list,
        configs: Dict[str, Dict[str, Any]]
    ) -> TranslationService:
        """
        Cria um serviço com fallback automático
        
        Tenta usar o serviço preferido, se falhar tenta os fallbacks em ordem
        
        Args:
            preferred_service: Serviço preferido
            fallback_services: Lista de serviços de fallback
            configs: Configurações para cada serviço
        
        Returns:
            Serviço com fallback
        """
        return FallbackTranslationService(
            preferred_service,
            fallback_services,
            configs
        )


class GeminiServiceAdapter(TranslationService):
    """
    Adapter para usar GeminiService com a interface TranslationService
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        api_key = config.get('api_key')
        if not api_key:
            raise ValueError("api_key é obrigatório para Gemini")
        
        from app.services.model_router import ModelRouter
        model_router = ModelRouter(config.get('blocked_models', []))
        
        if GeminiService is None:
            raise ImportError("GeminiService não está disponível. Verifique se google-genai está instalado.")
        
        # Passa db se disponível no config para rastreamento de tokens
        db = config.get('db')
        self.gemini_service = GeminiService(api_key, model_router, db=db)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def is_available(self) -> bool:
        """Verifica se Gemini está disponível"""
        # Gemini geralmente está disponível se tem API key
        return self.config.get('api_key') is not None
    
    def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: str = "auto"
    ) -> str:
        """Traduz usando Gemini"""
        return self.gemini_service._translate_text_with_router(
            text,
            target_language,
            source_language
        )
    
    def translate_segments(
        self,
        segments,
        target_language: str,
        source_language: str = "auto",
        max_gap: float = 1.5,
        progress_callback=None,
        checkpoint_callback=None,
        start_from_index: int = 0,
        existing_translations=None
    ):
        """
        Traduz segmentos usando GeminiService diretamente
        Mantém compatibilidade com a interface mas usa a implementação do Gemini
        """
        return self.gemini_service.translate_segments(
            segments,
            target_language,
            source_language,
            progress_callback=progress_callback,
            checkpoint_callback=checkpoint_callback,
            start_from_index=start_from_index,
            existing_translations=existing_translations
        )


class FallbackTranslationService(TranslationService):
    """
    Serviço que tenta múltiplos provedores em ordem de fallback
    """
    
    def __init__(
        self,
        preferred_service: str,
        fallback_services: list,
        configs: Dict[str, Dict[str, Any]]
    ):
        super().__init__()
        self.services = []
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Cria serviços em ordem de prioridade
        all_services = [preferred_service] + fallback_services
        
        for service_type in all_services:
            if service_type in configs:
                try:
                    service = TranslationServiceFactory.create(
                        service_type,
                        configs[service_type]
                    )
                    if service.is_available():
                        self.services.append(service)
                        self.logger.info(f"Serviço {service_type} disponível e adicionado")
                    else:
                        self.logger.warning(f"Serviço {service_type} não está disponível")
                except Exception as e:
                    self.logger.warning(f"Erro ao criar serviço {service_type}: {e}")
        
        if not self.services:
            raise ValueError("Nenhum serviço de tradução disponível")
        
        self.logger.info(f"Fallback configurado com {len(self.services)} serviços")
    
    def is_available(self) -> bool:
        """Verifica se pelo menos um serviço está disponível"""
        return len(self.services) > 0
    
    def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: str = "auto"
    ) -> str:
        """
        Tenta traduzir usando serviços em ordem de prioridade
        """
        last_error = None
        
        for idx, service in enumerate(self.services):
            try:
                self.logger.info(f"Tentando traduzir com serviço {idx + 1}/{len(self.services)}")
                result = service.translate_text(text, target_language, source_language)
                self.logger.info(f"Tradução bem-sucedida com serviço {idx + 1}")
                return result
            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"Serviço {idx + 1} falhou: {str(e)}. "
                    f"{'Tentando próximo...' if idx < len(self.services) - 1 else 'Sem mais serviços disponíveis'}"
                )
                continue
        
        # Se chegou aqui, todos falharam
        raise Exception(
            f"Todos os serviços de tradução falharam. "
            f"Último erro: {str(last_error)}"
        )
