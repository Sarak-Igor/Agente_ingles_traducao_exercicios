from sqlalchemy.orm import Session
from app.models.database import Job, Video, Translation, ApiKey
from app.schemas.schemas import SubtitleSegment, TranslationSegment
from app.services.youtube_service import YouTubeService
from app.services.translation_factory import TranslationServiceFactory
from app.services.encryption import encryption_service
from uuid import UUID
import json
import os


class JobService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_job(self, video_id: UUID = None) -> Job:
        """Cria um novo job"""
        job = Job(
            video_id=video_id,
            status="queued",
            progress=0,
            message="Aguardando processamento"
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
    
    def update_job(self, job_id: UUID, status: str, progress: int = None, message: str = None, error: str = None, translation_service: str = None):
        """Atualiza status de um job"""
        try:
            job = self.db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return None
            
            job.status = status
            if progress is not None:
                job.progress = progress
            if message:
                job.message = message
            if error:
                job.error = error
            if translation_service:
                job.translation_service = translation_service
            
            self.db.commit()
            return job
        except Exception as e:
            self.db.rollback()
            raise
    
    def get_job(self, job_id: UUID) -> Job:
        """Obtém um job pelo ID"""
        return self.db.query(Job).filter(Job.id == job_id).first()
    
    def process_translation_job(
        self,
        job_id: UUID,
        youtube_url: str,
        source_language: str,
        target_language: str,
        gemini_api_key: str
    ):
        """
        Processa uma tradução de vídeo em background
        Esta função deve ser executada em uma thread/processo separado
        """
        try:
            # Atualiza status para processing
            self.update_job(job_id, "processing", 10, "Extraindo legenda do YouTube...")
            
            # Extrai ID do vídeo
            youtube_service = YouTubeService()
            video_id = youtube_service.extract_video_id(youtube_url)
            
            # Verifica se vídeo já existe
            video = self.db.query(Video).filter(Video.youtube_id == video_id).first()
            if not video:
                # Busca informações do vídeo (título, duração)
                video_info = youtube_service.get_video_info(video_id)
                video = Video(
                    youtube_id=video_id,
                    title=video_info.get('title'),
                    duration=video_info.get('duration')
                )
                self.db.add(video)
                self.db.commit()
                self.db.refresh(video)
            else:
                # Se vídeo existe mas não tem título, tenta buscar
                if not video.title:
                    video_info = youtube_service.get_video_info(video_id)
                    if video_info.get('title'):
                        video.title = video_info.get('title')
                    if video_info.get('duration') and not video.duration:
                        video.duration = video_info.get('duration')
                    self.db.commit()
            
            # Atualiza job com video_id
            job = self.get_job(job_id)
            if job:
                job.video_id = video.id
                self.db.commit()
            
            # Extrai legenda
            self.update_job(job_id, "processing", 30, "Buscando legendas...")
            segments = youtube_service.get_transcript(video_id, [source_language])
            
            if not segments:
                raise Exception("Nenhuma legenda encontrada para este vídeo")
            
            # Traduz usando ferramenta de tradução (googletrans por padrão, mais rápido que Gemini)
            self.update_job(job_id, "processing", 50, f"Traduzindo {len(segments)} segmentos...")
            
            # Determina qual serviço usar (variável de ambiente ou padrão: googletrans)
            # IMPORTANTE: Prioriza ferramentas de tradução (não LLM) por padrão
            translation_service_name = os.getenv("TRANSLATION_SERVICE", "googletrans").lower()
            
            # Se estiver configurado para Gemini, força uso de ferramentas primeiro
            # Gemini só será usado como último recurso (fallback)
            force_tools_first = translation_service_name == "gemini"
            if force_tools_first:
                translation_service_name = "googletrans"  # Muda para ferramenta por padrão
            
            # Configuração do serviço de tradução
            translation_config = {}
            
            if translation_service_name == "googletrans":
                # googletrans: delay entre requisições (0.3s é suficiente)
                translation_config = {"delay": 0.3}
            elif translation_service_name == "argos" or translation_service_name == "argostranslate":
                # Argos: não precisa config
                translation_config = {}
            elif translation_service_name == "libretranslate":
                # LibreTranslate: URL da API
                libretranslate_url = os.getenv("LIBRETRANSLATE_URL", "http://localhost:5000")
                translation_config = {"api_url": libretranslate_url}
            elif translation_service_name == "gemini":
                # Se usar Gemini, precisa da API key
                # Salva chave de API criptografada (se não existir)
                existing_key = self.db.query(ApiKey).filter(
                    ApiKey.video_id == video.id,
                    ApiKey.service == "gemini"
                ).first()
                
                if not existing_key:
                    encrypted_key = encryption_service.encrypt(gemini_api_key)
                    api_key = ApiKey(
                        video_id=video.id,
                        service="gemini",
                        encrypted_key=encrypted_key
                    )
                    self.db.add(api_key)
                    self.db.commit()
                else:
                    encrypted_key = existing_key.encrypted_key
                
                decrypted_key = encryption_service.decrypt(encrypted_key)
                translation_config = {"api_key": decrypted_key}
            else:
                # Fallback para googletrans se serviço desconhecido
                translation_service_name = "googletrans"
                translation_config = {"delay": 0.3}
            
            # Cria serviço de tradução usando factory com fallback automático
            translation_service = None
            tried_services = []
            last_error = None
            selected_service_name = None
            
            # SEMPRE prioriza ferramentas de tradução sobre LLM
            # Ordem garantida: googletrans → argos → libretranslate → gemini (último recurso)
            
            # Lista de serviços para tentar (sempre ferramentas primeiro)
            services_to_try = []
            
            # 1. Adiciona ferramentas de tradução PRIMEIRO (não LLM)
            # Prioridade: deep-translator (mais estável) → googletrans → argos → libretranslate
            services_to_try.append(("deeptranslator", {"delay": 0.2}))
            services_to_try.append(("googletrans", {"delay": 0.3}))
            services_to_try.append(("argos", {}))
            libretranslate_url = os.getenv("LIBRETRANSLATE_URL", "http://localhost:5000")
            services_to_try.append(("libretranslate", {"api_url": libretranslate_url}))
            
            # 2. Por último, tenta Gemini (LLM) apenas como fallback se tiver API key
            if gemini_api_key:
                    # Salva chave de API se necessário
                    existing_key = self.db.query(ApiKey).filter(
                        ApiKey.video_id == video.id,
                        ApiKey.service == "gemini"
                    ).first()
                    
                    if not existing_key:
                        encrypted_key = encryption_service.encrypt(gemini_api_key)
                        api_key = ApiKey(
                            video_id=video.id,
                            service="gemini",
                            encrypted_key=encrypted_key
                        )
                        self.db.add(api_key)
                        self.db.commit()
                    else:
                        encrypted_key = existing_key.encrypted_key
                    
                    try:
                        decrypted_key = encryption_service.decrypt(encrypted_key)
                        # Adiciona db ao config para rastreamento de tokens
                        services_to_try.append(("gemini", {"api_key": decrypted_key, "db": self.db}))
                    except Exception as e:
                        pass
            
            # Tenta cada serviço até encontrar um disponível
            selected_service_name = None
            for service_name, service_config in services_to_try:
                try:
                    tried_services.append(service_name)
                    translation_service = TranslationServiceFactory.create(
                        service_name,
                        service_config
                    )
                    
                    # Verifica se está disponível
                    if translation_service.is_available():
                        selected_service_name = service_name
                        # Salva o nome do serviço no job
                        self.update_job(
                            job_id, 
                            "processing", 
                            50, 
                            f"Usando serviço de tradução: {service_name}",
                            translation_service=service_name
                        )
                        break
                    else:
                        translation_service = None
                        last_error = f"Serviço {service_name} não está disponível"
                        # Log mas continua tentando
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.debug(f"Serviço {service_name} não disponível, tentando próximo...")
                except ImportError as e:
                    # Se for erro de importação, tenta próximo
                    translation_service = None
                    last_error = f"{service_name} não instalado: {str(e)}"
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Serviço {service_name} não instalado, tentando próximo...")
                    continue
                except Exception as e:
                    # Se for outro erro, tenta próximo
                    translation_service = None
                    last_error = str(e)
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Erro ao usar {service_name}: {str(e)}, tentando próximo...")
                    continue
            
            # Se nenhum serviço funcionou
            if not translation_service:
                # Se não tentou Gemini ainda e tem API key, tenta como último recurso
                if "gemini" not in tried_services and gemini_api_key:
                    try:
                        # Salva chave de API se necessário
                        existing_key = self.db.query(ApiKey).filter(
                            ApiKey.video_id == video.id,
                            ApiKey.service == "gemini"
                        ).first()
                        
                        if not existing_key:
                            encrypted_key = encryption_service.encrypt(gemini_api_key)
                            api_key = ApiKey(
                                video_id=video.id,
                                service="gemini",
                                encrypted_key=encrypted_key
                            )
                            self.db.add(api_key)
                            self.db.commit()
                        else:
                            encrypted_key = existing_key.encrypted_key
                        
                        decrypted_key = encryption_service.decrypt(encrypted_key)
                        translation_service = TranslationServiceFactory.create(
                            "gemini",
                            {"api_key": decrypted_key, "db": self.db}
                        )
                        
                        if translation_service.is_available():
                            selected_service_name = "gemini"
                            self.update_job(
                                job_id, 
                                "processing", 
                                50, 
                                "Usando serviço de tradução: gemini (fallback)",
                                translation_service="gemini"
                            )
                        else:
                            translation_service = None
                    except Exception as e:
                        translation_service = None
                        last_error = f"Gemini também falhou: {str(e)}"
                
                # Se ainda não funcionou, lança erro
                if not translation_service:
                    error_msg = (
                        f"Nenhum serviço de tradução disponível. "
                        f"Tentados: {', '.join(tried_services)}. "
                    )
                    if "googletrans" in tried_services:
                        error_msg += "Instale: pip install googletrans==4.0.0-rc1 (pode ter conflito com httpx). "
                    error_msg += f"Último erro: {last_error}"
                    raise Exception(error_msg)
            
            # Callback para atualizar progresso durante tradução
            def update_progress(progress, message):
                # Ajusta progresso (50% a 90% = 40% do progresso total)
                adjusted_progress = 50 + int((progress / 100) * 40)
                self.update_job(job_id, "processing", adjusted_progress, message)
            
            # Traduz segmentos
            # Verifica se o serviço é Gemini (precisa de parâmetros especiais)
            is_gemini = (selected_service_name == "gemini" or 
                        hasattr(translation_service, 'gemini_service') or 
                        type(translation_service).__name__ == 'GeminiServiceAdapter')
            if is_gemini:
                # Gemini precisa de checkpoint_callback e outros parâmetros
                def save_checkpoint(group_index, translated_segments, blocked_models):
                    job = self.get_job(job_id)
                    if job:
                        segments_json = [
                            {
                                "start": seg.start,
                                "duration": seg.duration,
                                "original": seg.original,
                                "translated": seg.translated
                            }
                            for seg in translated_segments
                        ]
                        job.last_translated_group_index = group_index
                        job.partial_segments = segments_json
                        self.db.commit()
                
                translated_segments = translation_service.translate_segments(
                    segments,
                    target_language,
                    source_language,
                    progress_callback=update_progress,
                    checkpoint_callback=save_checkpoint,
                    start_from_index=0,
                    existing_translations=None,
                    max_gap=0.0  # NÃO agrupa - traduz cada segmento individualmente para sincronização perfeita
                )
            else:
                # Outros serviços usam interface padrão
                # CRÍTICO: Para manter sincronização perfeita, traduz segmentos individualmente
                # Não agrupa segmentos para evitar dessincronização
                # Cada segmento mantém seu timestamp original exato
                translated_segments = translation_service.translate_segments(
                    segments,
                    target_language,
                    source_language,
                    max_gap=0.0,  # NÃO agrupa - traduz cada segmento individualmente para sincronização perfeita
                    progress_callback=update_progress
                )
            
            # Salva tradução completa
            self.update_job(job_id, "processing", 90, "Salvando tradução...")
            
            # Converte para formato JSONB
            segments_json = [
                {
                    "start": seg.start,
                    "duration": seg.duration,
                    "original": seg.original,
                    "translated": seg.translated
                }
                for seg in translated_segments
            ]
            
            # Verifica se tradução já existe
            existing_translation = self.db.query(Translation).filter(
                Translation.video_id == video.id,
                Translation.source_language == source_language,
                Translation.target_language == target_language
            ).first()
            
            if existing_translation:
                existing_translation.segments = segments_json
            else:
                translation = Translation(
                    video_id=video.id,
                    source_language=source_language,
                    target_language=target_language,
                    segments=segments_json
                )
                self.db.add(translation)
            
            # Limpa campos de checkpoint (tradução completa)
            job = self.get_job(job_id)
            if job:
                job.last_translated_group_index = -1
                job.partial_segments = None
                job.blocked_models = None
            
            self.db.commit()
            
            # Completa job
            self.update_job(job_id, "completed", 100, "Tradução concluída com sucesso!")
            
        except Exception as e:
            error_str = str(e)
            # Se for erro de cota, mantém status como "processing" para permitir retomada
            if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'quota' in error_str.lower() or 'Cota excedida' in error_str:
                try:
                    # Mantém status como processing para permitir retomada
                    self.update_job(
                        job_id, 
                        "processing", 
                        None, 
                        f"Pausado: {error_str}. O progresso foi salvo e pode ser retomado.",
                        error=None  # Não marca como erro, apenas pausa
                    )
                except Exception:
                    self.db.rollback()
                # Não propaga erro - permite que o job seja retomado depois
                return
            else:
                # Outros erros: marca como erro
                try:
                    self.update_job(job_id, "error", message=f"Erro no processamento", error=error_str)
                except Exception:
                    self.db.rollback()
                raise
