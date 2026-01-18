"""
Configuração de logging para o sistema
"""
import logging
import sys
from pathlib import Path
from datetime import datetime

# Cria diretório de logs se não existir
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Arquivo de log com data
LOG_FILE = LOG_DIR / f"translation_{datetime.now().strftime('%Y%m%d')}.log"


def setup_logging(log_level: str = "INFO"):
    """
    Configura sistema de logging otimizado
    
    Console: Apenas WARNING, ERROR, CRITICAL (terminal limpo)
    Arquivo: Todos os logs (INFO, DEBUG, etc) para auditoria completa
    
    Args:
        log_level: Nível de log para arquivo (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Formato de log
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Handler para console - apenas mensagens críticas (ERROR e CRITICAL)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.ERROR)  # Apenas ERROR e CRITICAL
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Handler para arquivo - todos os logs
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Configura root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Nível mais baixo para capturar tudo
    root_logger.handlers = []  # Remove handlers padrão
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Suprime completamente logs de acesso HTTP do uvicorn
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.setLevel(logging.CRITICAL)  # Suprime completamente
    uvicorn_access.propagate = False
    uvicorn_access.handlers = []  # Remove todos os handlers
    
    # Configura loggers específicos da aplicação
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.DEBUG)
    
    # Loggers de serviços - DEBUG apenas no arquivo (console já filtra por nível)
    logging.getLogger("app.services").setLevel(logging.DEBUG)
    logging.getLogger("app.services.gemini_service").setLevel(logging.DEBUG)
    logging.getLogger("app.services.libretranslate_service").setLevel(logging.DEBUG)
    logging.getLogger("app.services.translation_factory").setLevel(logging.DEBUG)
    
    # Reduz verbosidade de bibliotecas externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("youtube_transcript_api").setLevel(logging.WARNING)
    logging.getLogger("argostranslate").setLevel(logging.WARNING)
    logging.getLogger("deep_translator").setLevel(logging.WARNING)
    
    # Suprime logs do uvicorn server (startup, etc) no console
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    # Log de configuração vai para arquivo apenas (não aparece no console)
    logger.debug(f"Logging configurado. Console: ERROR+, Arquivo: {log_level}+ -> {LOG_FILE}")


def get_logger(name: str) -> logging.Logger:
    """
    Retorna um logger configurado
    
    Args:
        name: Nome do logger (geralmente __name__)
    
    Returns:
        Logger configurado
    """
    return logging.getLogger(name)
