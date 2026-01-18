from pydantic_settings import BaseSettings
from typing import Optional
from urllib.parse import quote_plus
from pathlib import Path
import os


def load_env_manual():
    """Carrega variáveis do .env manualmente com encoding correto"""
    # Procura o .env na raiz do projeto (2 níveis acima de app/config.py)
    env_path = Path(__file__).parent.parent.parent / ".env"
    env_vars = {}
    
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    return env_vars


class Settings(BaseSettings):
    database_url: str
    redis_url: Optional[str] = None
    encryption_key: str
    host: str = "0.0.0.0"
    port: int = 8000
    frontend_url: str = "http://localhost:5173"
    
    class Config:
        # Procura o .env na raiz do projeto
        env_file = str(Path(__file__).parent.parent.parent / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        # Carrega manualmente para garantir encoding correto
        env_vars = load_env_manual()
        # Atualiza com valores do .env se não foram passados
        for key, value in env_vars.items():
            if key.upper() not in os.environ:
                os.environ[key.upper()] = value
        
        super().__init__(**kwargs)
    
    def get_database_url(self) -> str:
        """Retorna a URL do banco com encoding correto"""
        url = self.database_url
        
        # Codifica a senha se necessário
        if "postgresql://" in url:
            try:
                # Extrai componentes
                url_part = url.replace("postgresql://", "")
                if "@" in url_part:
                    auth_part, db_part = url_part.split("@", 1)
                    if ":" in auth_part:
                        user, password = auth_part.split(":", 1)
                        # Codifica caracteres especiais na senha
                        encoded_password = quote_plus(password, safe='')
                        return f"postgresql://{user}:{encoded_password}@{db_part}"
            except Exception:
                pass
        
        return url


settings = Settings()
