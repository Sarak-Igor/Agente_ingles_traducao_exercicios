"""
Serviço de tradução usando LibreTranslate (open source)
Requer instância do LibreTranslate rodando (self-hosted ou pública)
"""
import httpx
import logging
import time
from typing import Dict, Any
from app.services.translation_service import TranslationService

logger = logging.getLogger(__name__)


class LibreTranslateService(TranslationService):
    """
    Implementação usando LibreTranslate (open source)
    
    Requer:
    - Instância do LibreTranslate rodando (local ou remota)
    - URL da API (ex: http://localhost:5000 ou https://libretranslate.com)
    - Opcional: API key se usar instância pública
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
        self.api_url = config.get('api_url', 'http://localhost:5000')
        self.api_key = config.get('api_key', None)
        self.timeout = config.get('timeout', 30.0)
        self.client = httpx.Client(timeout=self.timeout)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def is_available(self) -> bool:
        """Verifica se o serviço está disponível"""
        try:
            response = self.client.get(f"{self.api_url}/languages", timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            self.logger.warning(f"LibreTranslate não disponível: {e}")
            return False
    
    def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: str = "auto"
    ) -> str:
        """
        Traduz texto usando LibreTranslate
        
        Args:
            text: Texto a traduzir
            target_language: Idioma de destino
            source_language: Idioma de origem ('auto' para detectar)
        
        Returns:
            Texto traduzido
        """
        # Converte códigos de idioma
        target = self.LANGUAGE_MAP.get(target_language, target_language.split('-')[0])
        source = 'auto'
        if source_language and source_language != 'auto':
            source = self.LANGUAGE_MAP.get(source_language, source_language.split('-')[0])
        
        # Prepara requisição
        payload = {
            'q': text,
            'source': source,
            'target': target,
            'format': 'text'
        }
        
        if self.api_key:
            payload['api_key'] = self.api_key
        
        # Faz requisição
        start_time = time.time()
        try:
            response = self.client.post(
                f"{self.api_url}/translate",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            translated = result.get('translatedText', '')
            
            elapsed = time.time() - start_time
            self.logger.info(
                f"Tradução LibreTranslate: {len(text)} → {len(translated)} caracteres "
                f"em {elapsed:.2f}s"
            )
            
            return translated
            
        except httpx.HTTPStatusError as e:
            self.logger.error(f"Erro HTTP LibreTranslate: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Erro ao traduzir com LibreTranslate: {e.response.status_code}")
        except httpx.RequestError as e:
            self.logger.error(f"Erro de conexão LibreTranslate: {e}")
            raise Exception(f"Erro de conexão com LibreTranslate: {str(e)}")
        except Exception as e:
            self.logger.error(f"Erro inesperado LibreTranslate: {e}")
            raise
