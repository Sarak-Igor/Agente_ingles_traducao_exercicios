"""
Serviço para rastrear uso de tokens por modelo e serviço
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from app.models.database import TokenUsage
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TokenUsageService:
    """Serviço para gerenciar rastreamento de uso de tokens"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def record_usage(
        self,
        service: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: Optional[int] = None,
        requests: int = 1
    ):
        """
        Registra uso de tokens para um modelo específico
        
        Args:
            service: Nome do serviço ('gemini', 'openrouter', 'groq', 'together')
            model: Nome do modelo usado
            input_tokens: Tokens de entrada
            output_tokens: Tokens de saída
            total_tokens: Total de tokens (se None, calcula como input + output)
            requests: Número de requisições (padrão 1)
        """
        try:
            if total_tokens is None:
                total_tokens = input_tokens + output_tokens
            
            usage = TokenUsage(
                service=service,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                requests=requests
            )
            
            self.db.add(usage)
            self.db.commit()
            
            logger.debug(f"Registrado uso: {service}/{model} - {total_tokens} tokens ({input_tokens} in, {output_tokens} out)")
            
        except Exception as e:
            logger.error(f"Erro ao registrar uso de tokens: {e}")
            self.db.rollback()
            # Não propaga erro para não interromper o fluxo principal
    
    def get_usage_stats(
        self,
        service: Optional[str] = None,
        model: Optional[str] = None,
        days: int = 30
    ) -> Dict:
        """
        Obtém estatísticas de uso
        
        Args:
            service: Filtrar por serviço (opcional)
            model: Filtrar por modelo (opcional)
            days: Número de dias para buscar (padrão 30)
            
        Returns:
            Dict com estatísticas agregadas
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = self.db.query(
                func.sum(TokenUsage.input_tokens).label('total_input'),
                func.sum(TokenUsage.output_tokens).label('total_output'),
                func.sum(TokenUsage.total_tokens).label('total_tokens'),
                func.sum(TokenUsage.requests).label('total_requests')
            ).filter(TokenUsage.created_at >= cutoff_date)
            
            if service:
                query = query.filter(TokenUsage.service == service)
            if model:
                query = query.filter(TokenUsage.model == model)
            
            result = query.first()
            
            return {
                'input_tokens': result.total_input or 0,
                'output_tokens': result.total_output or 0,
                'total_tokens': result.total_tokens or 0,
                'requests': result.total_requests or 0,
                'days': days
            }
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas de uso: {e}")
            return {
                'input_tokens': 0,
                'output_tokens': 0,
                'total_tokens': 0,
                'requests': 0,
                'days': days
            }
    
    def get_usage_by_model(
        self,
        service: Optional[str] = None,
        days: int = 30
    ) -> List[Dict]:
        """
        Obtém uso agrupado por modelo
        
        Args:
            service: Filtrar por serviço (opcional)
            days: Número de dias para buscar (padrão 30)
            
        Returns:
            Lista de dicts com estatísticas por modelo
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = self.db.query(
                TokenUsage.service,
                TokenUsage.model,
                func.sum(TokenUsage.input_tokens).label('total_input'),
                func.sum(TokenUsage.output_tokens).label('total_output'),
                func.sum(TokenUsage.total_tokens).label('total_tokens'),
                func.sum(TokenUsage.requests).label('total_requests')
            ).filter(
                TokenUsage.created_at >= cutoff_date
            ).group_by(
                TokenUsage.service,
                TokenUsage.model
            )
            
            if service:
                query = query.filter(TokenUsage.service == service)
            
            results = query.all()
            
            return [
                {
                    'service': r.service,
                    'model': r.model,
                    'input_tokens': r.total_input or 0,
                    'output_tokens': r.total_output or 0,
                    'total_tokens': r.total_tokens or 0,
                    'requests': r.total_requests or 0
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Erro ao obter uso por modelo: {e}")
            return []
    
    def get_daily_usage(
        self,
        service: Optional[str] = None,
        days: int = 30
    ) -> List[Dict]:
        """
        Obtém uso diário agregado
        
        Args:
            service: Filtrar por serviço (opcional)
            days: Número de dias para buscar (padrão 30)
            
        Returns:
            Lista de dicts com uso por dia
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = self.db.query(
                func.date(TokenUsage.created_at).label('date'),
                func.sum(TokenUsage.total_tokens).label('total_tokens'),
                func.sum(TokenUsage.requests).label('total_requests')
            ).filter(
                TokenUsage.created_at >= cutoff_date
            ).group_by(
                func.date(TokenUsage.created_at)
            )
            
            if service:
                query = query.filter(TokenUsage.service == service)
            
            results = query.order_by(func.date(TokenUsage.created_at).desc()).all()
            
            return [
                {
                    'date': r.date.isoformat() if r.date else None,
                    'total_tokens': r.total_tokens or 0,
                    'requests': r.total_requests or 0
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Erro ao obter uso diário: {e}")
            return []
