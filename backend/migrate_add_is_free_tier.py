"""
Script de migração para adicionar campo is_free_tier na tabela api_keys
Execute: python migrate_add_is_free_tier.py
"""
from sqlalchemy import text
from app.database import engine

def migrate():
    """Adiciona campo is_free_tier se não existir"""
    with engine.connect() as conn:
        try:
            # Verifica se a coluna já existe
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='api_keys' AND column_name='is_free_tier'
            """))
            
            if result.fetchone():
                print("✅ Campo 'is_free_tier' já existe na tabela api_keys")
                return
            
            # Adiciona a coluna
            conn.execute(text("""
                ALTER TABLE api_keys 
                ADD COLUMN is_free_tier VARCHAR(10) NOT NULL DEFAULT 'free'
            """))
            conn.commit()
            print("✅ Campo 'is_free_tier' adicionado com sucesso!")
            
        except Exception as e:
            print(f"❌ Erro ao adicionar campo: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    print("Iniciando migração...")
    migrate()
    print("Migração concluída!")
