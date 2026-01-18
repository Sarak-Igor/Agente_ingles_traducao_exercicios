"""
Serviço de tradução usando Argos Translate (open source, offline)
Não requer API keys, funciona completamente offline
"""
import logging
from typing import Dict, Any
from app.services.translation_service import TranslationService

logger = logging.getLogger(__name__)


class ArgosTranslateService(TranslationService):
    """
    Implementação usando Argos Translate
    
    Argos Translate é 100% open source e funciona offline
    Não requer API keys ou conexão com internet (após instalar modelos)
    
    Instalação:
    pip install argostranslate
    
    Primeiro uso (baixa modelos):
    import argostranslate.package
    import argostranslate.translate
    argostranslate.package.update_package_index()
    available_packages = argostranslate.package.get_available_packages()
    package_to_install = next(
        filter(
            lambda x: x.from_code == "en" and x.to_code == "pt", available_packages
        )
    )
    argostranslate.package.install_from_path(package_to_install.download())
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
        'zh': 'zh',
        'ru': 'ru',
        'pt-BR': 'pt',
        'en-US': 'en',
        'en-GB': 'en',
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._argos = None
        self._initialized = False
    
    def _initialize(self):
        """Inicializa Argos Translate (lazy loading)"""
        if self._initialized:
            return
        
        try:
            import argostranslate.package
            import argostranslate.translate
            self._argos = argostranslate.translate
            self._initialized = True
            self.logger.info("Argos Translate inicializado com sucesso")
        except ImportError:
            raise ImportError(
                "Argos Translate não está instalado. "
                "Instale com: pip install argostranslate"
            )
    
    def is_available(self) -> bool:
        """Verifica se Argos Translate está disponível"""
        try:
            self._initialize()
            # Verifica se há pelo menos um modelo instalado
            try:
                installed_languages = self._argos.get_installed_languages()
                return len(installed_languages) > 0
            except (AttributeError, TypeError) as e:
                # Problema com versão do argostranslate ou Python 3.14
                self.logger.warning(f"Argos Translate: problema de compatibilidade - {e}")
                return False
        except ImportError:
            return False
        except Exception as e:
            self.logger.warning(f"Argos Translate não disponível: {e}")
            return False
    
    def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: str = "auto"
    ) -> str:
        """
        Traduz texto usando Argos Translate
        
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
        source = 'en'  # Default
        if source_language and source_language != 'auto':
            source = self.LANGUAGE_MAP.get(source_language, source_language.split('-')[0])
        
        # Detecta idioma se necessário
        if source_language == 'auto':
            try:
                # Argos Translate não tem detecção automática robusta
                # Tenta detectar usando googletrans se disponível, senão assume 'en'
                try:
                    from googletrans import Translator
                    translator = Translator()
                    detected = translator.detect(text)
                    source = detected.lang if detected else 'en'
                except:
                    source = 'en'  # Fallback
            except Exception:
                source = 'en'  # Fallback
        
        # Verifica se modelo está disponível
        from_code = self._argos.get_language_from_code(source)
        to_code = self._argos.get_language_from_code(target)
        
        if not from_code or not to_code:
            raise Exception(
                f"Modelo de tradução não disponível: {source} → {target}. "
                f"Instale com: argostranslate.package.install_from_path(...)"
            )
        
        # Traduz
        import time
        start_time = time.time()
        
        try:
            translated = self._argos.translate(text, from_code, to_code)
            
            elapsed = time.time() - start_time
            self.logger.info(
                f"Tradução Argos: {len(text)} → {len(translated)} caracteres "
                f"em {elapsed:.3f}s ({source} → {target})"
            )
            
            return translated
            
        except Exception as e:
            self.logger.error(f"Erro ao traduzir com Argos: {e}")
            raise Exception(f"Erro ao traduzir com Argos Translate: {str(e)}")
