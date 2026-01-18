"""
Serviço de tradução usando deep-translator
Biblioteca mais estável e confiável que googletrans
"""
import logging
import time
from typing import Dict, Any
from app.services.translation_service import TranslationService

logger = logging.getLogger(__name__)


class DeepTranslatorService(TranslationService):
    """
    Implementação usando deep-translator
    
    Vantagens:
    - Mais estável que googletrans
    - Não requer API key
    - Muitos idiomas
    - Funciona melhor com Python 3.14
    
    Instalação:
    pip install deep-translator
    """
    
    # Mapeamento de códigos de idioma para Google Translator
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
    
    # Mapeamento específico para MyMemory (precisa de códigos completos)
    MYMEMORY_LANGUAGE_MAP = {
        'en': 'en-GB',      # Inglês padrão
        'pt': 'pt-BR',      # Português brasileiro (mais comum)
        'es': 'es-ES',      # Espanhol padrão
        'fr': 'fr-FR',      # Francês padrão
        'de': 'de-DE',      # Alemão padrão
        'it': 'it-IT',      # Italiano padrão
        'ja': 'ja-JP',      # Japonês
        'ko': 'ko-KR',      # Coreano
        'zh': 'zh-CN',      # Chinês simplificado
        'ru': 'ru-RU',      # Russo
        'pt-BR': 'pt-BR',   # Mantém se já for completo
        'en-US': 'en-US',   # Mantém se já for completo
        'en-GB': 'en-GB',   # Mantém se já for completo
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._translator = None
        self._initialized = False
        self.delay = config.get('delay', 0.2)  # Delay menor, mais rápido
        self.service = config.get('service', 'google')  # google, mymemory, etc.
    
    def _initialize(self):
        """Inicializa deep-translator (lazy loading)"""
        if self._initialized:
            return
        
        try:
            from deep_translator import GoogleTranslator, MyMemoryTranslator
            self._translator_class = GoogleTranslator
            self._mymemory_class = MyMemoryTranslator
            self._initialized = True
            self.logger.info(f"Deep Translator inicializado (serviço: {self.service})")
        except ImportError:
            raise ImportError(
                "deep-translator não está instalado. "
                "Instale com: pip install deep-translator"
            )
    
    def is_available(self) -> bool:
        """Verifica se deep-translator está disponível"""
        try:
            self._initialize()
            # Testa tradução simples
            translator = self._translator_class(source='en', target='pt')
            result = translator.translate('test')
            return result is not None and len(result) > 0
        except Exception as e:
            self.logger.warning(f"Deep Translator não disponível: {e}")
            return False
    
    def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: str = "auto"
    ) -> str:
        """
        Traduz texto usando deep-translator
        
        Args:
            text: Texto a traduzir
            target_language: Idioma de destino
            source_language: Idioma de origem ('auto' para detectar)
        
        Returns:
            Texto traduzido
        """
        self._initialize()
        
        # Converte códigos de idioma para Google Translator
        google_target = self.LANGUAGE_MAP.get(target_language, target_language.split('-')[0])
        google_source = 'en'  # Default
        if source_language and source_language != 'auto':
            google_source = self.LANGUAGE_MAP.get(source_language, source_language.split('-')[0])
        
        # Converte para códigos do MyMemory (precisa de códigos completos)
        mymemory_source = self.MYMEMORY_LANGUAGE_MAP.get(google_source, 'en-GB')
        mymemory_target = self.MYMEMORY_LANGUAGE_MAP.get(google_target, 'pt-BR')
        
        # Delay para evitar rate limit
        time.sleep(self.delay)
        
        # Traduz
        start_time = time.time()
        
        try:
            translated = None
            
            # Tenta Google Translator primeiro
            try:
                translator = self._translator_class(source=google_source, target=google_target)
                translated = translator.translate(text)
                
                # Verifica se retornou None (rate limit silencioso)
                if translated is None:
                    raise Exception("Google Translator retornou None (possível rate limit)")
                    
            except Exception as e:
                # Se falhar, tenta MyMemory com códigos completos
                self.logger.warning(f"Google Translator falhou, tentando MyMemory: {e}")
                try:
                    # MyMemory precisa de códigos completos (en-GB, pt-BR, etc.)
                    translator = self._mymemory_class(source=mymemory_source, target=mymemory_target)
                    translated = translator.translate(text)
                    
                    # Verifica se retornou None
                    if translated is None:
                        raise Exception("MyMemory Translator retornou None")
                except Exception as e2:
                    # Se MyMemory também falhar, propaga exceção para acionar fallback automático
                    raise Exception(f"Ambos os serviços falharam. Google: {str(e)}, MyMemory: {str(e2)}")
            
            # Validação final antes de usar
            if translated is None:
                raise Exception("Tradução retornou None após todas as tentativas")
            
            if not isinstance(translated, str):
                raise Exception(f"Tradução retornou tipo inválido: {type(translated)}")
            
            elapsed = time.time() - start_time
            # Determina qual serviço foi usado (Google ou MyMemory)
            # Se chegou aqui, translated não é None, então foi bem-sucedido
            # Usa google_source/target por padrão (se MyMemory foi usado, já está em mymemory_source/target)
            self.logger.info(
                f"Tradução Deep Translator: {len(text)} → {len(translated)} caracteres "
                f"em {elapsed:.2f}s ({google_source} → {google_target})"
            )
            
            return translated
            
        except Exception as e:
            self.logger.error(f"Erro ao traduzir com Deep Translator: {e}")
            raise Exception(f"Erro ao traduzir com Deep Translator: {str(e)}")
