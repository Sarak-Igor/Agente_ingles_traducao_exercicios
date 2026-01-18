from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.database import ApiKey, Video
from app.services.encryption import encryption_service
from app.services.gemini_service import GeminiService
from app.services.model_router import ModelRouter
from app.services.api_status_checker import ApiStatusChecker
from typing import List, Optional
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/api/keys", tags=["api-keys"])
logger = logging.getLogger(__name__)


class ModelStatus(BaseModel):
    name: str
    available: bool
    blocked: bool
    status: str


class ApiKeyStatus(BaseModel):
    service: str
    is_valid: bool
    models_status: List[ModelStatus]
    available_models: List[str]
    blocked_models: List[str]
    error: Optional[str] = None


class ApiKeyCheckRequest(BaseModel):
    api_key: str
    service: str = "gemini"


@router.post("/check-status", response_model=ApiKeyStatus)
async def check_api_key_status(
    request: ApiKeyCheckRequest,
    db: Session = Depends(get_db)
):
    """
    Verifica status e cotas de uma chave de API
    Suporta: gemini, openrouter, groq, together
    """
    try:
        # Verifica Gemini (implementação específica)
        if request.service == "gemini":
            # Cria ModelRouter e GeminiService para validação
            model_router = ModelRouter(validate_on_init=False)
            gemini_service = GeminiService(
                request.api_key,
                model_router,
                validate_models=True
            )
            
            # Obtém status dos modelos
            models_status = []
            available_models = model_router.get_validated_models()
            blocked_models = model_router.get_blocked_models_list()
            
            # Cria status detalhado para cada modelo
            for model_name in ModelRouter.AVAILABLE_MODELS:
                is_available = model_name in available_models
                is_blocked = model_name in blocked_models
                
                models_status.append(ModelStatus(
                    name=model_name,
                    available=is_available,
                    blocked=is_blocked,
                    status="available" if is_available else ("blocked" if is_blocked else "unknown")
                ))
            
            return ApiKeyStatus(
                service=request.service,
                is_valid=len(available_models) > 0,
                models_status=models_status,
                available_models=available_models,
                blocked_models=blocked_models,
                error=None if len(available_models) > 0 else "Nenhum modelo disponível. Verifique suas cotas de API no console do Google Cloud."
            )
        
        # Outras APIs (OpenRouter, Groq, Together)
        elif request.service in ["openrouter", "groq", "together"]:
            status_result = await ApiStatusChecker.check_status(request.service, request.api_key)
            
            # Converte para o formato esperado
            models_status = [
                ModelStatus(
                    name=model.get("name", "unknown"),
                    available=model.get("available", False),
                    blocked=model.get("blocked", False),
                    status=model.get("status", "unknown")
                )
                for model in status_result.get("models_status", [])
            ]
            
            return ApiKeyStatus(
                service=request.service,
                is_valid=status_result.get("is_valid", False),
                models_status=models_status,
                available_models=status_result.get("available_models", []),
                blocked_models=status_result.get("blocked_models", []),
                error=status_result.get("error")
            )
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Serviço '{request.service}' não suportado. Serviços disponíveis: gemini, openrouter, groq, together"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        logger.error(f"Erro ao verificar status da chave API: {e}")
        
        # Se for erro de autenticação/chave inválida
        if '401' in error_str or '403' in error_str or 'invalid' in error_str.lower() or 'unauthorized' in error_str.lower():
            return ApiKeyStatus(
                service=request.service,
                is_valid=False,
                models_status=[],
                available_models=[],
                blocked_models=[],
                error="Chave de API inválida ou não autorizada"
            )
        
        return ApiKeyStatus(
            service=request.service,
            is_valid=False,
            models_status=[],
            available_models=[],
            blocked_models=[],
            error=f"Erro ao verificar status: {error_str}"
        )


@router.get("/list")
async def list_api_keys(
    db: Session = Depends(get_db)
):
    """
    Lista todas as chaves de API cadastradas (sem expor as chaves)
    """
    try:
        api_keys = db.query(ApiKey).all()
        
        result = []
        for key in api_keys:
            video = db.query(Video).filter(Video.id == key.video_id).first()
            result.append({
                "id": str(key.id),
                "service": key.service,
                "video_id": str(key.video_id),
                "video_title": video.title if video else None,
                "created_at": key.created_at.isoformat() if key.created_at else None
            })
        
        return {"api_keys": result, "total": len(result)}
    except Exception as e:
        logger.error(f"Erro ao listar chaves API: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar chaves: {str(e)}")
