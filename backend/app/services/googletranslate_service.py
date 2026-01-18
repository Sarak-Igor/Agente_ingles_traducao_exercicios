"""
Serviço de tradução usando Google Translate (googletrans library)
Open source, não requer API key, usa scraping da API pública do Google
"""
import logging
import time
from typing import Dict, Any
from app.services.translation_service import TranslationService

logger = logging.getLogger(__name__)


class GoogleTranslateService(TranslationService):
    """
    Implementação usando googletrans (biblioteca Python)
    
    Vantagens:
    - Não requer API key
    - Gratuito
    - Muitos idiomas
    
    Desvantagens:
    - Pode ser bloqueado se usar muito (rate limit)
    - Depende de scraping (pode quebrar se Google mudar)
    
    Instalação:
    pip install googletrans==4.0.0-rc1
    """
    
    # Mapeamento de códigos de idioma
    LANGUAGE_MAP = {
        'pt': 'pt',
        'en': 'en',
        'es': 'es',
        'fr': 'fr',
        'de': 'de',
        'it': 'it',
        'ja': 'ja',
        'ko': 'ko',
        'zh': 'zh-CN',
        'ru': 'ru',
        'pt-BR': 'pt',
        'en-US': 'en',
        'en-GB': 'en',
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._translator = None
        self._initialized = False
        self.delay = config.get('delay', 0.5)  # Delay entre requisições
    
    def _initialize(self):
        """Inicializa googletrans (lazy loading)"""
        if self._initialized:
            return
        
        try:
            from googletrans import Translator
            self._translator = Translator()
            self._initialized = True
            self.logger.info("Google Translate (googletrans) inicializado")
        except ImportError:
            raise ImportError(
                "googletrans não está instalado. "
                "Instale com: pip install googletrans==4.0.0-rc1"
            )
    
    def is_available(self) -> bool:
        """Verifica se googletrans está disponível"""
        try:
            self._initialize()
            # Testa tradução simples
            result = self._translator.translate('test', dest='pt', src='en')
            return result.text is not None
        except Exception as e:
            self.logger.warning(f"Google Translate não disponível: {e}")
            return False
    
    def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: str = "auto"
    ) -> str:
        """
        Traduz texto usando Google Translate
        
        Args:
            text: Texto a traduzir
            target_language: Idioma de destino
            source_language: Idioma de origem ('auto' para detectar)
        
        Returns:
            Texto traduzido
        """
        self._initialize()
        
        # Converte códigos de idioma
        target = self.LANGUAGE_MAP.get(target_language, target_language.split('-')[0])
        source = None
        if source_language and source_language != 'auto':
            source = self.LANGUAGE_MAP.get(source_language, source_language.split('-')[0])
        
        # Delay para evitar rate limit
        time.sleep(self.delay)
        
        # Traduz
        start_time = time.time()
        
        try:
            result = self._translator.translate(
                text,
                dest=target,
                src=source if source else None
            )
            
            elapsed = time.time() - start_time
            self.logger.info(
                f"Tradução Google: {len(text)} → {len(result.text)} caracteres "
                f"em {elapsed:.2f}s ({result.src or 'auto'} → {target})"
            )
            
            return result.text
            
        except Exception as e:
            self.logger.error(f"Erro ao traduzir com Google Translate: {e}")
            raise Exception(f"Erro ao traduzir com Google Translate: {str(e)}")
