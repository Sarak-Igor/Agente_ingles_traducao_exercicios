from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import video, jobs, practice, api_keys, usage
from app.database import engine, Base
from app.services.logging_config import setup_logging
# Importa modelos para garantir que sejam registrados no Base.metadata
from app.models.database import Video, Translation, ApiKey, Job, TokenUsage

# Configura logging ANTES de qualquer outra coisa
setup_logging("INFO")

# Cria tabelas automaticamente (incluindo TokenUsage)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Video Translation API",
    description="API para tradução de legendas de vídeos do YouTube",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas
app.include_router(video.router)
app.include_router(jobs.router)
app.include_router(practice.router)
app.include_router(api_keys.router)
app.include_router(usage.router)


@app.get("/")
async def root():
    return {"message": "Video Translation API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
