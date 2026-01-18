from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from typing import List, Dict
from app.schemas.schemas import SubtitleSegment
import re
import logging

logger = logging.getLogger(__name__)


class YouTubeService:
    @staticmethod
    def extract_video_id(url: str) -> str:
        """Extrai o ID do vídeo de uma URL do YouTube"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, str(url))
            if match:
                return match.group(1)
        
        raise ValueError("URL do YouTube inválida")
    
    @staticmethod
    def get_transcript(video_id: str, language_codes: List[str] = None) -> List[SubtitleSegment]:
        """
        Extrai a transcrição do vídeo do YouTube
        
        Args:
            video_id: ID do vídeo do YouTube
            language_codes: Lista de códigos de idioma para tentar (ex: ['en', 'en-US', 'pt'])
        
        Returns:
            Lista de segmentos de legenda com start, duration e text
        """
        if language_codes is None:
            language_codes = ['en', 'en-US', 'en-GB', 'pt', 'pt-BR', 'es', 'fr']
        
        # Cria instância da API (versão 1.2.3+ requer instância)
        yt_api = YouTubeTranscriptApi()
        
        transcript_data = None
        last_error = None
        
        # Tenta obter transcrição usando o método fetch() com idiomas específicos
        try:
            # Usa fetch() com lista de idiomas (tenta na ordem de prioridade)
            fetched_transcript = yt_api.fetch(video_id, languages=language_codes)
            # Converte FetchedTranscript para lista de dicionários
            transcript_data = fetched_transcript.to_raw_data()
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            last_error = e
            # Se não encontrou com idiomas específicos, tenta listar e pegar qualquer legenda disponível
            try:
                # Lista todas as legendas disponíveis
                transcript_list = yt_api.list(video_id)
                
                # Tenta encontrar legenda manual nos idiomas desejados
                try:
                    transcript = transcript_list.find_manually_created_transcript(language_codes)
                    fetched = transcript.fetch()
                    transcript_data = fetched.to_raw_data()
                except NoTranscriptFound:
                    # Se não encontrou manual, tenta gerada automaticamente
                    try:
                        transcript = transcript_list.find_generated_transcript(language_codes)
                        fetched = transcript.fetch()
                        transcript_data = fetched.to_raw_data()
                    except NoTranscriptFound:
                        # Última tentativa: pega qualquer legenda disponível
                        available_transcripts = list(transcript_list)
                        if available_transcripts:
                            transcript = available_transcripts[0]
                            fetched = transcript.fetch()
                            transcript_data = fetched.to_raw_data()
                        else:
                            raise Exception("Nenhuma legenda disponível para este vídeo")
            except Exception as final_error:
                error_msg = str(last_error) if last_error else str(final_error)
                raise Exception(f"Não foi possível encontrar legendas para o vídeo: {error_msg}")
        except VideoUnavailable as e:
            raise Exception(f"Vídeo não disponível: {str(e)}")
        except Exception as e:
            # Se for outro tipo de erro, tenta a abordagem alternativa
            last_error = e
            try:
                transcript_list = yt_api.list(video_id)
                available_transcripts = list(transcript_list)
                if available_transcripts:
                    transcript = available_transcripts[0]
                    fetched = transcript.fetch()
                    transcript_data = fetched.to_raw_data()
                else:
                    raise Exception(f"Não foi possível encontrar legendas para o vídeo: {str(e)}")
            except Exception as final_error:
                error_msg = str(last_error) if last_error else str(final_error)
                raise Exception(f"Não foi possível encontrar legendas para o vídeo: {error_msg}")
        
        # Converte para formato padronizado
        segments = []
        for item in transcript_data:
            start = item.get('start', 0)
            duration = item.get('duration', 0)
            text = item.get('text', '').strip()
            
            if text:  # Ignora segmentos vazios
                # Detecta se é música (padrões comuns em legendas musicais)
                # Se não tem notas musicais mas parece música, adiciona marcadores
                is_likely_music = (
                    not '♪' in text and  # Não tem notas musicais ainda
                    (
                        len(text.split()) <= 15 or  # Frases curtas (comum em músicas)
                        any(word in text.lower() for word in ['oh', 'yeah', 'baby', 'love', 'heart', 'soul']) or
                        text.endswith(('...', '…'))  # Frases incompletas (comum em músicas)
                    )
                )
                
                # Se parece música e não tem notas musicais, adiciona marcadores
                # Isso ajuda a alinhar a tradução mesmo quando o YouTube não fornece notas
                if is_likely_music and not text.startswith('♪') and not text.endswith('♪'):
                    # Adiciona nota musical no início se não tiver
                    if not text.strip().startswith('♪'):
                        text = '♪ ' + text.strip()
                
                segments.append(SubtitleSegment(
                    start=round(start, 2),
                    duration=round(duration, 2),
                    text=text
                ))
        
        return segments
    
    @staticmethod
    def get_video_info(video_id: str) -> Dict:
        """
        Obtém informações básicas do vídeo do YouTube
        Retorna título e duração usando yt-dlp (preferencial) ou scraping
        """
        try:
            # Método 1: Tenta usar yt-dlp (mais confiável)
            try:
                import yt_dlp
                
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'skip_download': True,
                }
                
                url = f"https://www.youtube.com/watch?v={video_id}"
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', None)
                    duration = info.get('duration', None)
                    
                    if title:
                        logger.info(f"Título obtido via yt-dlp para {video_id}: {title[:50]}...")
                    
                    return {
                        "video_id": video_id,
                        "title": title,
                        "duration": duration
                    }
            except ImportError:
                logger.warning("yt-dlp não está instalado. Tentando método alternativo...")
            except Exception as e:
                logger.warning(f"Erro ao usar yt-dlp: {e}. Tentando método alternativo...")
            
            # Método 2: Tenta usar scraping HTML (fallback)
            try:
                import requests
                from bs4 import BeautifulSoup
                
                url = f"https://www.youtube.com/watch?v={video_id}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Tenta encontrar título na tag <title>
                    title_tag = soup.find('title')
                    if title_tag:
                        title = title_tag.text.replace(' - YouTube', '').strip()
                        if title and title != 'YouTube':
                            logger.info(f"Título obtido via scraping para {video_id}: {title[:50]}...")
                            return {
                                "video_id": video_id,
                                "title": title,
                                "duration": None
                            }
                    
                    # Tenta encontrar no meta tag og:title
                    og_title = soup.find('meta', property='og:title')
                    if og_title and og_title.get('content'):
                        title = og_title.get('content').strip()
                        if title and title != 'YouTube':
                            logger.info(f"Título obtido via og:title para {video_id}: {title[:50]}...")
                            return {
                                "video_id": video_id,
                                "title": title,
                                "duration": None
                            }
            except ImportError:
                logger.warning("requests/beautifulsoup4 não estão instalados")
            except Exception as e:
                logger.warning(f"Erro ao fazer scraping: {e}")
            
            # Fallback: retorna None se não conseguir obter
            logger.warning(f"Não foi possível obter título para vídeo {video_id}")
            return {
                "video_id": video_id,
                "title": None,
                "duration": None
            }
        except Exception as e:
            # Em caso de erro inesperado, retorna None mas não propaga exceção
            # Isso permite que o processamento continue mesmo se não conseguir o título
            logger.error(f"Erro inesperado ao obter informações do vídeo {video_id}: {e}")
            return {
                "video_id": video_id,
                "title": None,
                "duration": None
            }
