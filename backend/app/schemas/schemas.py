from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class SubtitleSegment(BaseModel):
    start: float
    duration: float
    text: str


class TranslationSegment(BaseModel):
    start: float
    duration: float
    original: str
    translated: str


class VideoProcessRequest(BaseModel):
    youtube_url: HttpUrl
    source_language: str = Field(..., min_length=2, max_length=10)
    target_language: str = Field(..., min_length=2, max_length=10)
    gemini_api_key: str = Field(..., min_length=10)
    force_retranslate: bool = Field(default=False, description="Força retradução mesmo se já existir tradução")


class VideoProcessResponse(BaseModel):
    job_id: UUID
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    progress: int
    message: Optional[str] = None
    video_id: Optional[UUID] = None
    error: Optional[str] = None
    translation_service: Optional[str] = None  # Serviço de tradução sendo usado


class SubtitlesResponse(BaseModel):
    video_id: UUID
    source_language: str
    target_language: str
    segments: List[TranslationSegment]


class VideoCheckResponse(BaseModel):
    exists: bool
    translation_id: Optional[UUID] = None
    video_id: Optional[UUID] = None
