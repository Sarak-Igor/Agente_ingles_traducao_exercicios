"""
Rotas de autenticação
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.schemas.schemas import UserRegister, UserLogin, Token, UserProfileResponse
from app.services.auth_service import (
    create_user,
    authenticate_user,
    create_access_token,
    verify_token,
    get_user_by_id,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.models.database import UserProfile
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Dependency para obter usuário atual a partir do token"""
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Registra novo usuário"""
    try:
        user = create_user(
            db=db,
            email=user_data.email,
            username=user_data.username,
            native_language=user_data.native_language,
            learning_language=user_data.learning_language
        )
        
        # Cria token de acesso
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "username": user.username},
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            user_id=user.id,
            username=user.username
        )
    except ValueError as e:
        logger.warning(f"Erro de validação ao registrar: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erro ao registrar usuário: {e}", exc_info=True)
        error_detail = str(e)
        # Mensagens mais específicas para erros comuns
        if "relation" in error_detail.lower() and "does not exist" in error_detail.lower():
            error_detail = "Tabelas do banco de dados não foram criadas. Execute o script de inicialização do banco."
        elif "duplicate key" in error_detail.lower() or "unique constraint" in error_detail.lower():
            error_detail = "Email ou nome de usuário já está em uso."
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )


@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    """Login do usuário (apenas por email, sem senha)"""
    user = authenticate_user(db, user_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email não encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username},
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        username=user.username
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna perfil do usuário atual"""
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil não encontrado"
        )
    
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        native_language=profile.native_language,
        learning_language=profile.learning_language,
        proficiency_level=profile.proficiency_level,
        total_chat_messages=profile.total_chat_messages,
        total_practice_sessions=profile.total_practice_sessions,
        average_response_time=profile.average_response_time,
        learning_context=profile.learning_context,
        preferred_learning_style=profile.preferred_learning_style,
        preferred_model=profile.preferred_model,
        created_at=current_user.created_at
    )
