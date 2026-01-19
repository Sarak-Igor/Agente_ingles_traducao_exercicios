from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Text, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Video(Base):
    __tablename__ = "videos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    youtube_id = Column(String(20), nullable=False, index=True)
    title = Column(String(500))
    duration = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="videos")
    translations = relationship("Translation", back_populates="video", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="video")  # Removido cascade - chaves são do usuário, não do vídeo
    
    __table_args__ = (
        UniqueConstraint('user_id', 'youtube_id', name='unique_user_video'),
    )


class Translation(Base):
    __tablename__ = "translations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    segments = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="translations")
    video = relationship("Video", back_populates="translations")
    
    __table_args__ = (
        UniqueConstraint('video_id', 'source_language', 'target_language', name='unique_video_translation'),
    )


class ApiKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True)  # Opcional - mantido para compatibilidade
    service = Column(String(50), nullable=False)  # 'gemini', 'openrouter', 'groq', 'together', etc.
    encrypted_key = Column(Text, nullable=False)  # Chave criptografada
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", backref="api_keys")
    video = relationship("Video", back_populates="api_keys")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'service', name='unique_user_service_key'),
    )


class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
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
    
    user = relationship("User", backref="jobs")


class TokenUsage(Base):
    __tablename__ = "token_usage"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    service = Column(String(50), nullable=False, index=True)  # 'gemini', 'openrouter', 'groq', 'together'
    model = Column(String(100), nullable=False, index=True)  # Nome do modelo usado
    input_tokens = Column(Integer, default=0)  # Tokens de entrada
    output_tokens = Column(Integer, default=0)  # Tokens de saída
    total_tokens = Column(Integer, default=0)  # Total de tokens (input + output)
    requests = Column(Integer, default=1)  # Número de requisições
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    user = relationship("User", backref="token_usage")


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    # Relações reversas definidas nos outros modelos (videos, translations, api_keys, jobs, token_usage)


class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Idioma nativo e idioma aprendido
    native_language = Column(String(10), nullable=False, default="pt")  # pt, en, es, etc.
    learning_language = Column(String(10), nullable=False, default="en")  # Idioma que está aprendendo
    
    # Nível de conhecimento (beginner, intermediate, advanced)
    proficiency_level = Column(String(20), nullable=False, default="beginner")
    
    # Métricas de progresso
    total_chat_messages = Column(Integer, default=0)
    total_practice_sessions = Column(Integer, default=0)
    average_response_time = Column(Float, default=0.0)  # Tempo médio de resposta em segundos
    
    # Contexto de aprendizado (JSONB para flexibilidade)
    learning_context = Column(JSONB, nullable=True)  # Tópicos estudados, dificuldades, etc.
    
    # Preferências
    preferred_learning_style = Column(String(50), nullable=True)  # formal, casual, conversational
    preferred_model = Column(String(100), nullable=True)  # Modelo preferido do usuário
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="profile")


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Configuração da sessão
    mode = Column(String(20), nullable=False, default="writing")  # writing, conversation
    language = Column(String(10), nullable=False)  # Idioma sendo praticado
    
    # Modelo usado na sessão
    model_service = Column(String(50), nullable=True)  # gemini, openrouter, groq, together
    model_name = Column(String(100), nullable=True)  # Nome específico do modelo
    
    # Status e métricas
    is_active = Column(Boolean, default=True, nullable=False)
    message_count = Column(Integer, default=0)
    
    # Contexto da sessão (para continuidade)
    session_context = Column(JSONB, nullable=True)  # Tópicos discutidos, erros comuns, etc.
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Conteúdo
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    content_type = Column(String(20), nullable=False, default="text")  # text, audio
    
    # Metadados de áudio (se aplicável)
    audio_url = Column(String(500), nullable=True)  # URL do arquivo de áudio
    transcription = Column(Text, nullable=True)  # Transcrição do áudio
    
    # Análise e feedback (para mensagens do usuário)
    grammar_errors = Column(JSONB, nullable=True)  # Lista de erros gramaticais detectados
    vocabulary_suggestions = Column(JSONB, nullable=True)  # Sugestões de vocabulário
    difficulty_score = Column(Float, nullable=True)  # Dificuldade estimada da mensagem
    
    # Feedback do professor (para mensagens do assistant)
    feedback_type = Column(String(50), nullable=True)  # correction, explanation, encouragement, etc.
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    session = relationship("ChatSession", back_populates="messages")