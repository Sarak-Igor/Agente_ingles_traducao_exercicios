from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.token_usage_service import TokenUsageService
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api/usage", tags=["usage"])


class UsageStatsResponse(BaseModel):
    service: str
    total_tokens: int
    input_tokens: int
    output_tokens: int
    requests: int
    models: list
    daily_usage: list


@router.get("/stats")
async def get_usage_stats(
    service: Optional[str] = None,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Obtém estatísticas de uso de tokens
    
    Args:
        service: Filtrar por serviço (opcional)
        days: Número de dias para buscar (padrão 30, máximo 365 para evitar consultas muito lentas)
    
    Nota: Os dados são persistidos permanentemente no banco de dados.
    Você pode consultar períodos maiores alterando o parâmetro 'days'.
    """
    # Limita a 365 dias para evitar consultas muito lentas
    days = min(days, 365)
    usage_service = TokenUsageService(db)
    
    # Estatísticas gerais
    stats = usage_service.get_usage_stats(service=service, days=days)
    
    # Uso por modelo
    models_usage = usage_service.get_usage_by_model(service=service, days=days)
    
    # Uso diário
    daily_usage = usage_service.get_daily_usage(service=service, days=days)
    
    # Agrupa por serviço se não foi especificado
    if not service:
        # Agrupa todos os serviços
        services = {}
        for model_data in models_usage:
            svc = model_data['service']
            if svc not in services:
                services[svc] = {
                    'service': svc,
                    'total_tokens': 0,
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'requests': 0,
                    'models': []
                }
            
            services[svc]['total_tokens'] += model_data['total_tokens']
            services[svc]['input_tokens'] += model_data['input_tokens']
            services[svc]['output_tokens'] += model_data['output_tokens']
            services[svc]['requests'] += model_data['requests']
            services[svc]['models'].append({
                'model': model_data['model'],
                'tokens': model_data['total_tokens'],
                'input_tokens': model_data['input_tokens'],
                'output_tokens': model_data['output_tokens'],
                'requests': model_data['requests']
            })
        
        return {
            'services': list(services.values()),
            'daily_usage': daily_usage,
            'period_days': days
        }
    else:
        # Retorna para um serviço específico
        return {
            'service': service,
            'total_tokens': stats['total_tokens'],
            'input_tokens': stats['input_tokens'],
            'output_tokens': stats['output_tokens'],
            'requests': stats['requests'],
            'models': [
                {
                    'model': m['model'],
                    'tokens': m['total_tokens'],
                    'input_tokens': m['input_tokens'],
                    'output_tokens': m['output_tokens'],
                    'requests': m['requests']
                }
                for m in models_usage
            ],
            'daily_usage': daily_usage,
            'period_days': days
        }
