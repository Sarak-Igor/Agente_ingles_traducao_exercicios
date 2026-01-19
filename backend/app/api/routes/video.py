from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.schemas.schemas import (
    VideoProcessRequest,
    VideoProcessResponse,
    SubtitlesResponse,
    VideoCheckResponse
)
from app.models.database import Video, Translation, User
from app.services.youtube_service import YouTubeService
from app.services.job_service import JobService
from app.services.encryption import encryption_service
from app.api.routes.auth import get_current_user
from uuid import UUID
import concurrent.futures
import threading

router = APIRouter(prefix="/api/video", tags=["video"])

# Thread pool para processamento assíncrono
executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)


def run_job_in_background(
    job_id: UUID,
    user_id: UUID,
    youtube_url: str,
    source_language: str,
    target_language: str,
    gemini_api_key: str
):
    """Executa job em thread separada com sua própria sessão do banco"""
    # Cria uma nova sessão para esta thread
    db = SessionLocal()
    try:
        job_service = JobService(db)
        job_service.process_translation_job(
            job_id, user_id, youtube_url, source_language, target_language, gemini_api_key
        )
    finally:
        # Garante que a sessão seja fechada
        db.close()


@router.post("/process", response_model=VideoProcessResponse)
async def process_video(
    request: VideoProcessRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Inicia processamento de tradução de vídeo"""
    try:
        # Extrai ID do vídeo
        youtube_service = YouTubeService()
        video_id = youtube_service.extract_video_id(str(request.youtube_url))
        
        # Verifica se já existe tradução para este usuário
        video = db.query(Video).filter(
            Video.youtube_id == video_id,
            Video.user_id == current_user.id
        ).first()
        if video:
            existing = db.query(Translation).filter(
                Translation.video_id == video.id,
                Translation.user_id == current_user.id,
                Translation.source_language == request.source_language,
                Translation.target_language == request.target_language
            ).first()
            
            if existing:
                # Se force_retranslate for True, deleta a tradução existente
                if request.force_retranslate:
                    db.delete(existing)
                    db.commit()
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="Tradução já existe para este vídeo e idiomas. Use force_retranslate=true para retraduzir."
                    )
        
        # Cria job associado ao usuário
        job_service = JobService(db)
        job = job_service.create_job(user_id=current_user.id)
        
        # Executa processamento em background (a thread criará sua própria sessão)
        executor.submit(
            run_job_in_background,
            job.id,
            current_user.id,
            str(request.youtube_url),
            request.source_language,
            request.target_language,
            request.gemini_api_key
        )
        
        return VideoProcessResponse(
            job_id=job.id,
            status="queued",
            message="Processamento iniciado"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar vídeo: {str(e)}")


@router.get("/{video_id}/subtitles", response_model=SubtitlesResponse)
async def get_subtitles(
    video_id: UUID,
    source_language: str,
    target_language: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna legendas e tradução de um vídeo"""
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.user_id == current_user.id
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")
    
    translation = db.query(Translation).filter(
        Translation.video_id == video_id,
        Translation.user_id == current_user.id,
        Translation.source_language == source_language,
        Translation.target_language == target_language
    ).first()
    
    if not translation:
        raise HTTPException(status_code=404, detail="Tradução não encontrada")
    
    # Converte JSONB para lista de TranslationSegment
    from app.schemas.schemas import TranslationSegment
    segments = [
        TranslationSegment(**seg) for seg in translation.segments
    ]
    
    return SubtitlesResponse(
        video_id=video_id,
        source_language=source_language,
        target_language=target_language,
        segments=segments
    )


@router.get("/check", response_model=VideoCheckResponse)
async def check_video(
    youtube_url: str,
    source_language: str,
    target_language: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verifica se vídeo já foi traduzido"""
    try:
        youtube_service = YouTubeService()
        video_id = youtube_service.extract_video_id(youtube_url)
        
        video = db.query(Video).filter(
            Video.youtube_id == video_id,
            Video.user_id == current_user.id
        ).first()
        if not video:
            return VideoCheckResponse(exists=False)
        
        translation = db.query(Translation).filter(
            Translation.video_id == video.id,
            Translation.user_id == current_user.id,
            Translation.source_language == source_language,
            Translation.target_language == target_language
        ).first()
        
        if translation:
            return VideoCheckResponse(
                exists=True,
                translation_id=translation.id,
                video_id=video.id
            )
        
        return VideoCheckResponse(exists=False, video_id=video.id)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/all")
async def delete_all_videos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deleta todos os vídeos do usuário atual e todos os dados relacionados (traduções, API keys, jobs)"""
    try:
        # Conta vídeos e traduções antes de deletar para mensagem informativa
        videos_count = db.query(Video).filter(Video.user_id == current_user.id).count()
        translations_count = db.query(Translation).filter(Translation.user_id == current_user.id).count()
        
        if videos_count == 0:
            return {
                "message": "Nenhum vídeo encontrado para deletar.",
                "deleted_videos": 0,
                "deleted_translations": 0
            }
        
        # Deleta todos os vídeos do usuário (cascade vai deletar traduções, api_keys e jobs relacionados)
        db.query(Video).filter(Video.user_id == current_user.id).delete()
        db.commit()
        
        return {
            "message": f"Todos os vídeos deletados com sucesso. {videos_count} vídeo(s) e {translations_count} tradução(ões) removida(s).",
            "deleted_videos": videos_count,
            "deleted_translations": translations_count
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar todos os vídeos: {str(e)}")


@router.delete("/{video_id}/translation")
async def delete_translation(
    video_id: UUID,
    source_language: str,
    target_language: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deleta uma tradução específica de um vídeo"""
    try:
        video = db.query(Video).filter(
            Video.id == video_id,
            Video.user_id == current_user.id
        ).first()
        if not video:
            raise HTTPException(status_code=404, detail="Vídeo não encontrado")
        
        translation = db.query(Translation).filter(
            Translation.video_id == video_id,
            Translation.user_id == current_user.id,
            Translation.source_language == source_language,
            Translation.target_language == target_language
        ).first()
        
        if not translation:
            raise HTTPException(status_code=404, detail="Tradução não encontrada")
        
        db.delete(translation)
        db.commit()
        
        return {"message": "Tradução deletada com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar tradução: {str(e)}")


@router.delete("/{video_id}")
async def delete_video(
    video_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deleta um vídeo e todas as suas traduções e dados relacionados"""
    try:
        video = db.query(Video).filter(
            Video.id == video_id,
            Video.user_id == current_user.id
        ).first()
        if not video:
            raise HTTPException(status_code=404, detail="Vídeo não encontrado")
        
        # Conta traduções antes de deletar para mensagem informativa
        translations_count = db.query(Translation).filter(
            Translation.video_id == video_id,
            Translation.user_id == current_user.id
        ).count()
        
        # Deleta o vídeo (cascade vai deletar traduções, api_keys e jobs relacionados)
        db.delete(video)
        db.commit()
        
        return {
            "message": f"Vídeo deletado com sucesso. {translations_count} tradução(ões) removida(s).",
            "deleted_translations": translations_count
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar vídeo: {str(e)}")


@router.post("/{video_id}/update-title")
async def update_video_title(
    video_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Atualiza o título de um vídeo buscando do YouTube"""
    try:
        video = db.query(Video).filter(
            Video.id == video_id,
            Video.user_id == current_user.id
        ).first()
        if not video:
            raise HTTPException(status_code=404, detail="Vídeo não encontrado")
        
        # Busca título do YouTube
        youtube_service = YouTubeService()
        video_info = youtube_service.get_video_info(video.youtube_id)
        
        if video_info.get('title'):
            video.title = video_info.get('title')
            if video_info.get('duration') and not video.duration:
                video.duration = video_info.get('duration')
            db.commit()
            return {"message": "Título atualizado com sucesso", "title": video.title}
        else:
            return {"message": "Não foi possível obter o título do YouTube", "title": None}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar título: {str(e)}")


@router.get("/list")
async def list_videos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0
):
    """Lista todos os vídeos traduzidos do usuário atual"""
    try:
        videos = db.query(Video).join(Translation).filter(
            Video.user_id == current_user.id,
            Translation.user_id == current_user.id
        ).distinct().offset(offset).limit(limit).all()
        
        result = []
        for video in videos:
            translations = db.query(Translation).filter(
                Translation.video_id == video.id,
                Translation.user_id == current_user.id
            ).all()
            for translation in translations:
                # Se não tem título, tenta buscar do YouTube
                title = video.title
                if not title:
                    try:
                        youtube_service = YouTubeService()
                        video_info = youtube_service.get_video_info(video.youtube_id)
                        if video_info.get('title'):
                            title = video_info.get('title')
                            # Atualiza no banco para próxima vez
                            video.title = title
                            db.commit()
                    except Exception:
                        pass
                
                result.append({
                    "video_id": str(video.id),
                    "youtube_id": video.youtube_id,
                    "title": title or f"Vídeo {video.youtube_id}",
                    "source_language": translation.source_language,
                    "target_language": translation.target_language,
                    "translation_id": str(translation.id),
                    "created_at": translation.created_at.isoformat() if translation.created_at else None
                })
        
        return {"videos": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
