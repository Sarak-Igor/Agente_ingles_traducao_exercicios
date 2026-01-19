"""
Rotas de API para chat de aprendizado de idiomas
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.database import User, ChatSession, ChatMessage, UserProfile, ApiKey
from app.schemas.schemas import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionWithMessages
)
from app.services.chat_router import ChatRouter
from app.services.chat_service import ChatService
from app.services.gemini_service import GeminiService
from app.services.model_router import ModelRouter
from app.services.token_usage_service import TokenUsageService
from app.services.encryption import encryption_service
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_gemini_service(user_id: UUID, db: Session, validate_models: bool = True) -> Optional[GeminiService]:
    """
    Obtém serviço Gemini para um usuário específico
    Valida modelos disponíveis na inicialização
    
    Args:
        user_id: ID do usuário
        db: Sessão do banco de dados
        validate_models: Se True, valida modelos disponíveis na inicialização
    """
    try:
        api_key_record = db.query(ApiKey).filter(
            ApiKey.user_id == user_id,
            ApiKey.service == "gemini"
        ).first()
        
        if not api_key_record:
            return None
        
        decrypted_key = encryption_service.decrypt(api_key_record.encrypted_key)
        
        # Cria ModelRouter sem validação inicial (será validado no GeminiService)
        model_router = ModelRouter(validate_on_init=False)
        
        # Cria GeminiService que validará modelos na inicialização
        # Passa db para rastreamento de tokens
        return GeminiService(decrypted_key, model_router, validate_models=validate_models, db=db)
    except Exception as e:
        logger.error(f"Erro ao obter GeminiService: {e}")
        return None


def get_chat_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ChatService:
    """Cria serviço de chat com configuração de API keys do banco de dados"""
    
    # 1. Gemini - busca do banco de dados
    gemini_service = None
    try:
        gemini_service = get_gemini_service(current_user.id, db, validate_models=False)
    except Exception as e:
        logger.warning(f"Erro ao obter Gemini Service: {e}")
    
    # 2. OpenRouter - busca do banco de dados
    openrouter_key = None
    try:
        api_key_record = db.query(ApiKey).filter(
            ApiKey.user_id == current_user.id,
            ApiKey.service == "openrouter"
        ).first()
        if api_key_record:
            openrouter_key = encryption_service.decrypt(api_key_record.encrypted_key)
    except Exception as e:
        logger.warning(f"Erro ao obter OpenRouter API key: {e}")
    
    # 3. Groq - busca do banco de dados
    groq_key = None
    try:
        api_key_record = db.query(ApiKey).filter(
            ApiKey.user_id == current_user.id,
            ApiKey.service == "groq"
        ).first()
        if api_key_record:
            groq_key = encryption_service.decrypt(api_key_record.encrypted_key)
    except Exception as e:
        logger.warning(f"Erro ao obter Groq API key: {e}")
    
    # 4. Together - busca do banco de dados
    together_key = None
    try:
        api_key_record = db.query(ApiKey).filter(
            ApiKey.user_id == current_user.id,
            ApiKey.service == "together"
        ).first()
        if api_key_record:
            together_key = encryption_service.decrypt(api_key_record.encrypted_key)
    except Exception as e:
        logger.warning(f"Erro ao obter Together API key: {e}")
    
    # 5. Cria ChatRouter com serviços encontrados
    chat_router = ChatRouter(
        gemini_service=gemini_service,
        openrouter_api_key=openrouter_key,
        groq_api_key=groq_key,
        together_api_key=together_key,
        token_usage_service=TokenUsageService(db)
    )
    
    return ChatService(chat_router, db)


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cria nova sessão de chat"""
    try:
        # Obtém perfil do usuário
        user_profile = db.query(UserProfile).filter(
            UserProfile.user_id == current_user.id
        ).first()
        
        # Cria serviço de chat
        chat_service = get_chat_service(db, current_user)
        
        # Cria sessão
        session = chat_service.create_session(
            user_id=str(current_user.id),
            mode=session_data.mode,
            language=session_data.language,
            user_profile=user_profile,
            preferred_service=session_data.preferred_service,
            preferred_model=session_data.preferred_model
        )
        
        return ChatSessionResponse(
            id=session.id,
            mode=session.mode,
            language=session.language,
            model_service=session.model_service,
            model_name=session.model_name,
            is_active=session.is_active,
            message_count=session.message_count,
            session_context=session.session_context,
            created_at=session.created_at,
            updated_at=session.updated_at
        )
    except Exception as e:
        logger.error(f"Erro ao criar sessão de chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar sessão: {str(e)}"
        )


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista sessões de chat do usuário"""
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.created_at.desc()).limit(50).all()
    
    return [
        ChatSessionResponse(
            id=s.id,
            mode=s.mode,
            language=s.language,
            model_service=s.model_service,
            model_name=s.model_name,
            is_active=s.is_active,
            message_count=s.message_count,
            session_context=s.session_context,
            created_at=s.created_at,
            updated_at=s.updated_at
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=ChatSessionWithMessages)
async def get_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna sessão de chat com mensagens"""
    from uuid import UUID
    
    session = db.query(ChatSession).filter(
        ChatSession.id == UUID(session_id),
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sessão não encontrada"
        )
    
    chat_service = get_chat_service(db, current_user)
    messages = chat_service.get_session_messages(str(session.id))
    
    return ChatSessionWithMessages(
        id=session.id,
        mode=session.mode,
        language=session.language,
        model_service=session.model_service,
        model_name=session.model_name,
        is_active=session.is_active,
        message_count=session.message_count,
        session_context=session.session_context,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            ChatMessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                content_type=m.content_type,
                audio_url=m.audio_url,
                transcription=m.transcription,
                grammar_errors=m.grammar_errors,
                vocabulary_suggestions=m.vocabulary_suggestions,
                difficulty_score=m.difficulty_score,
                feedback_type=m.feedback_type,
                created_at=m.created_at
            )
            for m in messages
        ]
    )


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    session_id: str,
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Envia mensagem na sessão de chat"""
    from uuid import UUID
    
    # Verifica se sessão pertence ao usuário
    session = db.query(ChatSession).filter(
        ChatSession.id == UUID(session_id),
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sessão não encontrada"
        )
    
    if not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sessão não está ativa"
        )
    
    try:
        chat_service = get_chat_service(db, current_user)
        
        # Envia mensagem
        response = chat_service.send_message(
            session_id=session_id,
            content=message_data.content,
            content_type=message_data.content_type,
            transcription=message_data.transcription
        )
        
        return ChatMessageResponse(
            id=response.id,
            role=response.role,
            content=response.content,
            content_type=response.content_type,
            audio_url=response.audio_url,
            transcription=response.transcription,
            grammar_errors=response.grammar_errors,
            vocabulary_suggestions=response.vocabulary_suggestions,
            difficulty_score=response.difficulty_score,
            feedback_type=response.feedback_type,
            created_at=response.created_at
        )
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao enviar mensagem: {str(e)}"
        )


@router.post("/sessions/{session_id}/audio", response_model=ChatMessageResponse)
async def send_audio_message(
    session_id: str,
    audio_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Envia mensagem de áudio na sessão de chat"""
    from uuid import UUID
    
    # Verifica se sessão pertence ao usuário
    session = db.query(ChatSession).filter(
        ChatSession.id == UUID(session_id),
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sessão não encontrada"
        )
    
    if not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sessão não está ativa"
        )
    
    try:
        # Lê arquivo de áudio
        audio_data = await audio_file.read()
        
        # TODO: Implementar transcrição de áudio
        # Por enquanto, retorna erro informando que precisa de transcrição
        # Em produção, usar serviço de transcrição (Whisper, Google Speech, etc.)
        
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Transcrição de áudio ainda não implementada. Por favor, envie o texto transcrito."
        )
        
        # Quando implementado:
        # transcription = await transcribe_audio(audio_data)
        # chat_service = get_chat_service(db, current_user)
        # response = chat_service.send_message(
        #     session_id=session_id,
        #     content=transcription,
        #     content_type="audio",
        #     transcription=transcription
        # )
        # return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao processar áudio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar áudio: {str(e)}"
        )


@router.delete("/sessions/{session_id}")
async def close_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fecha sessão de chat"""
    from uuid import UUID
    
    session = db.query(ChatSession).filter(
        ChatSession.id == UUID(session_id),
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sessão não encontrada"
        )
    
    chat_service = get_chat_service(db, current_user)
    chat_service.close_session(str(session.id))
    
    return {"message": "Sessão fechada com sucesso"}


@router.get("/available-models")
async def get_available_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna lista de modelos disponíveis de todas as APIs do usuário"""
    try:
        chat_service = get_chat_service(db, current_user)
        chat_router = chat_service.chat_router
        
        # Obtém modelos disponíveis (versão síncrona com cache)
        all_models = chat_router.get_all_available_models()
        
        # Para serviços não-Gemini, tenta obter modelos via API async se cache vazio
        from app.services.api_status_checker import ApiStatusChecker
        
        # OpenRouter
        if 'openrouter' in chat_router.available_services and not all_models.get('openrouter'):
            try:
                if chat_router.openrouter_api_key:
                    models = await chat_router.get_available_models('openrouter')
                    all_models['openrouter'] = models
            except Exception as e:
                logger.warning(f"Erro ao obter modelos OpenRouter: {e}")
        
        # Groq
        if 'groq' in chat_router.available_services and not all_models.get('groq'):
            try:
                if chat_router.groq_api_key:
                    models = await chat_router.get_available_models('groq')
                    all_models['groq'] = models
            except Exception as e:
                logger.warning(f"Erro ao obter modelos Groq: {e}")
        
        # Together
        if 'together' in chat_router.available_services and not all_models.get('together'):
            try:
                if chat_router.together_api_key:
                    models = await chat_router.get_available_models('together')
                    all_models['together'] = models
            except Exception as e:
                logger.warning(f"Erro ao obter modelos Together: {e}")
        
        return all_models
    except Exception as e:
        logger.error(f"Erro ao obter modelos disponíveis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter modelos: {str(e)}"
        )


@router.patch("/sessions/{session_id}/model", response_model=ChatSessionResponse)
async def change_session_model(
    session_id: str,
    model_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Troca modelo da sessão de chat"""
    from uuid import UUID
    
    # Valida dados
    service = model_data.get('service')
    model = model_data.get('model')
    
    if not service or not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="service e model são obrigatórios"
        )
    
    # Verifica se sessão pertence ao usuário
    session = db.query(ChatSession).filter(
        ChatSession.id == UUID(session_id),
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sessão não encontrada"
        )
    
    try:
        chat_service = get_chat_service(db, current_user)
        
        # Troca modelo
        updated_session = chat_service.change_session_model(
            session_id=str(session.id),
            service=service,
            model=model
        )
        
        return ChatSessionResponse(
            id=updated_session.id,
            mode=updated_session.mode,
            language=updated_session.language,
            model_service=updated_session.model_service,
            model_name=updated_session.model_name,
            is_active=updated_session.is_active,
            message_count=updated_session.message_count,
            session_context=updated_session.session_context,
            created_at=updated_session.created_at,
            updated_at=updated_session.updated_at
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erro ao trocar modelo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao trocar modelo: {str(e)}"
        )
