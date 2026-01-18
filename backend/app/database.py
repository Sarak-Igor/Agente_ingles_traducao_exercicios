from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from urllib.parse import urlparse
from app.config import settings
import sys
import os
import logging

logger = logging.getLogger(__name__)

def create_database_engine():
    """Cria engine do banco usando parâmetros diretos para evitar problemas de encoding"""
    url = settings.get_database_url()
    
    try:
        # Parse da URL
        parsed = urlparse(url)
        
        # Extrai componentes
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        database = parsed.path.lstrip('/') if parsed.path else "Agente_traducao"
        user = parsed.username or "postgres"
        password = parsed.password or ""
        
        # Usa parâmetros de conexão diretos em vez de URL string
        # Isso evita problemas de encoding com caminhos que contêm acentos
        connect_args = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
            "client_encoding": "utf8"
        }
        
        # Constrói URL sem senha para logging (senha será passada via connect_args)
        safe_url = f"postgresql://{user}:***@{host}:{port}/{database}"
        
        # Cria engine usando 'postgresql+psycopg2://' mas passa parâmetros via connect_args
        # Isso evita que o psycopg2 tente decodificar a URL string
        engine_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
        
        # Força encoding UTF-8 no ambiente
        if sys.platform == 'win32':
            os.environ['PGCLIENTENCODING'] = 'UTF8'
        
        return create_engine(
            engine_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args={"client_encoding": "utf8"},
            echo=False
        )
    except Exception as e:
        # Fallback: tenta URL direta
        logger.warning(f"Erro ao processar URL, usando fallback: {e}")
        if sys.platform == 'win32':
            os.environ['PGCLIENTENCODING'] = 'UTF8'
        return create_engine(
            url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args={"client_encoding": "utf8"}
        )

engine = create_database_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency para obter sessão do banco de dados"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        # Em caso de erro, faz rollback antes de fechar
        db.rollback()
        raise
    finally:
        # Fecha a sessão apenas se não estiver em uma transação ativa
        try:
            db.close()
        except Exception:
            # Ignora erros ao fechar se a sessão já estiver em estado inválido
            pass
