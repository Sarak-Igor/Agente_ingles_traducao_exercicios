from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import os
from app.config import settings


class EncryptionService:
    def __init__(self):
        # Usa a chave diretamente do settings (deve ser uma chave Fernet válida)
        # Se não for uma chave Fernet válida, deriva uma chave
        try:
            # Tenta usar a chave diretamente
            key = settings.encryption_key.encode()
            self.cipher = Fernet(key)
        except Exception:
            # Se falhar, deriva uma chave a partir da string
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'video_translation_salt',  # Em produção, use um salt único por instalação
                iterations=100000,
                backend=default_backend()
            )
            key = base64.urlsafe_b64encode(kdf.derive(settings.encryption_key.encode()))
            self.cipher = Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        """Criptografa uma string"""
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Descriptografa uma string"""
        return self.cipher.decrypt(ciphertext.encode()).decode()


encryption_service = EncryptionService()
