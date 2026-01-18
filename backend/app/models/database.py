from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Video(Base):
    __tablename__ = "videos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    youtube_id = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(500))
    duration = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    translations = relationship("Translation", back_populates="video", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="video", cascade="all, delete-orphan")


class Translation(Base):
    __tablename__ = "translations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    segments = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    video = relationship("Video", back_populates="translations")
    
    __table_args__ = (
        UniqueConstraint('video_id', 'source_language', 'target_language', name='unique_video_translation'),
    )


class ApiKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    service = Column(String(50), nullable=False)  # 'gemini', 'openai', etc.
    encrypted_key = Column(Text, nullable=False)  # Chave criptografada
    is_free_tier = Column(String(10), nullable=False, default='free')  # 'free' ou 'paid'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    video = relationship("Video", back_populates="api_keys")


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=True)
    status = Column(String(20), nullable=False, default="queued")  # queued, processing, completed, error
    progress = Column(Integer, default=0)
    message = Column(String(500))
    error = Column(Text)
    translation_service = Column(String(50))  # Nome do serviço de tradução usado (gemini, googletrans, argos, etc)
    # Campos para checkpoint e retomada
    last_translated_group_index = Column(Integer, default=-1)  # Índice do último grupo traduzido
    partial_segments = Column(JSONB, nullable=True)  # Segmentos parcialmente traduzidos
    blocked_models = Column(JSONB, nullable=True)  # Lista de modelos bloqueados por cota
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class TokenUsage(Base):
    __tablename__ = "token_usage"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service = Column(String(50), nullable=False, index=True)  # 'gemini', 'openrouter', 'groq', 'together'
    model = Column(String(100), nullable=False, index=True)  # Nome do modelo usado
    input_tokens = Column(Integer, default=0)  # Tokens de entrada
    output_tokens = Column(Integer, default=0)  # Tokens de saída
    total_tokens = Column(Integer, default=0)  # Total de tokens (input + output)
    requests = Column(Integer, default=1)  # Número de requisições
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class Word(Base):
    __tablename__ = "words"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    word = Column(String(200), nullable=False, index=True)  # A palavra em si
    language = Column(String(10), nullable=False, index=True)  # 'en' ou 'pt'
    translation = Column(String(200), nullable=True)  # Tradução da palavra (opcional)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    __table_args__ = (
        UniqueConstraint('word', 'language', name='unique_word_language'),
    )