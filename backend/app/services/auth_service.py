"""
Serviço de autenticação com JWT e hash de senha
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.models.database import User, UserProfile
from app.config import settings
import secrets
import logging
import hashlib

logger = logging.getLogger(__name__)

# Configuração de hash de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuração JWT - usar chave secreta do .env ou gerar uma
SECRET_KEY = getattr(settings, 'jwt_secret_key', None) or secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 dias


def _pre_hash_password(password: str) -> str:
    """
    Faz pré-hash da senha usando SHA-256 antes de passar para bcrypt.
    Isso resolve o problema de senhas maiores que 72 bytes, pois:
    - SHA-256 sempre produz 32 bytes (256 bits)
    - Bcrypt aceita até 72 bytes, então 32 bytes está dentro do limite
    - Isso permite senhas de qualquer tamanho sem truncamento
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a senha está correta.
    Usa pré-hash SHA-256 para evitar problemas com senhas > 72 bytes.
    """
    # Faz pré-hash da senha antes de verificar
    pre_hashed = _pre_hash_password(plain_password)
    return pwd_context.verify(pre_hashed, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Gera hash da senha usando bcrypt.
    Usa pré-hash SHA-256 para evitar problemas com senhas > 72 bytes.
    
    Fluxo:
    1. Senha original (qualquer tamanho) -> SHA-256 -> 64 caracteres hex (32 bytes)
    2. Hash SHA-256 (32 bytes) -> bcrypt -> hash final
    
    Isso permite senhas de qualquer tamanho sem truncamento ou erros.
    """
    try:
        # Faz pré-hash da senha antes de passar para bcrypt
        pre_hashed = _pre_hash_password(password)
        logger.debug(f"Fazendo hash de senha (pré-hash SHA-256: {len(pre_hashed)} caracteres)")
        return pwd_context.hash(pre_hashed)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao fazer hash da senha: {error_msg}")
        # Se ainda houver erro de 72 bytes, significa que algo está errado
        if "72 bytes" in error_msg.lower() or "truncate" in error_msg.lower():
            logger.error("Erro de 72 bytes mesmo após pré-hash SHA-256 - isso não deveria acontecer!")
            # Tenta uma abordagem alternativa: usar apenas os primeiros 72 bytes do pré-hash
            # (embora isso não deveria ser necessário, pois SHA-256 sempre produz 64 caracteres)
            pre_hashed = _pre_hash_password(password)
            if len(pre_hashed.encode('utf-8')) > 72:
                pre_hashed = pre_hashed[:72]
            return pwd_context.hash(pre_hashed)
        raise


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Cria token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verifica e decodifica token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Busca usuário por email"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Busca usuário por username"""
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Busca usuário por ID"""
    from uuid import UUID
    try:
        return db.query(User).filter(User.id == UUID(user_id)).first()
    except (ValueError, TypeError):
        return None


def create_user(
    db: Session,
    email: str,
    username: str,
    native_language: str = "pt",
    learning_language: str = "en"
) -> User:
    """Cria novo usuário com perfil"""
    # Verifica se email ou username já existem
    if get_user_by_email(db, email):
        raise ValueError("Email já está em uso")
    if get_user_by_username(db, username):
        raise ValueError("Username já está em uso")
    
    # Cria usuário (sem senha)
    user = User(
        email=email,
        username=username
    )
    db.add(user)
    db.flush()  # Para obter o ID do usuário
    
    # Cria perfil
    profile = UserProfile(
        user_id=user.id,
        native_language=native_language,
        learning_language=learning_language,
        proficiency_level="beginner"
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    
    logger.info(f"Usuário criado: {username} ({email})")
    return user


def authenticate_user(db: Session, email: str) -> Optional[User]:
    """Autentica usuário apenas por email (sem senha)"""
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not user.is_active:
        return None
    return user
