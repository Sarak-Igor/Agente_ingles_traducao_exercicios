"""
Script para inicializar o banco de dados
Execute: python init_db.py
"""
from app.database import engine, Base
from app.models.database import Video, Translation, ApiKey, Job, Word, TokenUsage

if __name__ == "__main__":
    print("Criando tabelas no banco de dados...")
    Base.metadata.create_all(bind=engine)
    print("Tabelas criadas com sucesso!")
