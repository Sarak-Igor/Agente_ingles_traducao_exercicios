from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.database import ApiKey, Video
from app.services.encryption import encryption_service
from app.services.gemini_service import GeminiService
from app.services.model_router import ModelRouter
from app.services.api_status_checker import ApiStatusChecker
from app.services.token_usage_service import TokenUsageService
from app.services.model_quotas import get_model_quota_limit, get_model_pricing
from typing import List, Optional
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/api/keys", tags=["api-keys"])
logger = logging.getLogger(__name__)


class ModelStatus(BaseModel):
    name: str
    available: bool
    blocked: bool
    status: str
    reason: Optional[str] = None  # Razão do bloqueio: 'quota_exceeded', 'not_available', 'not_found', etc.
    quota_used: Optional[int] = None  # Tokens usados hoje (para modelos gratuitos)
    quota_limit: Optional[int] = None  # Limite diário de tokens (para modelos gratuitos)
    quota_percentage: Optional[float] = None  # Porcentagem de cota usada (para modelos gratuitos)
    daily_cost: Optional[float] = None  # Custo do dia em USD (para modelos pagos)


class ApiKeyStatus(BaseModel):
    service: str
    is_valid: bool
    models_status: List[ModelStatus]
    available_models: List[str]
    blocked_models: List[str]
    error: Optional[str] = None


class ApiKeyCheckRequest(BaseModel):
    api_key: str
    service: str = "gemini"
    is_free_tier: str = "free"  # 'free' ou 'paid'


@router.post("/check-status", response_model=ApiKeyStatus)
async def check_api_key_status(
    request: ApiKeyCheckRequest,
    db: Session = Depends(get_db)
):
    """
    Verifica status e cotas de uma chave de API
    Suporta: gemini, openrouter, groq, together
    """
    try:
        # Verifica Gemini (implementação específica)
        if request.service == "gemini":
            try:
                # Primeiro, valida se a chave é válida listando modelos disponíveis
                from google import genai
                test_client = genai.Client(api_key=request.api_key)
                
                # Lista modelos disponíveis primeiro (como sugerido pela API)
                available_models_list = []
                try:
                    # Tenta listar modelos disponíveis usando ListModels (como sugerido pela API)
                    try:
                        models_response = test_client.models.list()
                        
                        # Processa a resposta dependendo do formato
                        if hasattr(models_response, 'models'):
                            available_models_list = [m.name for m in models_response.models if hasattr(m, 'name')]
                        elif hasattr(models_response, '__iter__'):
                            # Se for iterável, converte para lista
                            available_models_list = []
                            for m in models_response:
                                model_name = None
                                if hasattr(m, 'name'):
                                    model_name = m.name
                                elif hasattr(m, 'display_name'):
                                    model_name = m.display_name
                                elif isinstance(m, str):
                                    model_name = m
                                else:
                                    # Tenta acessar como dict
                                    if isinstance(m, dict):
                                        model_name = m.get('name') or m.get('display_name')
                                    else:
                                        model_name = str(m)
                                
                                if model_name:
                                    available_models_list.append(model_name)
                        
                        if available_models_list:
                            logger.info(f"✅ Chave Gemini válida - {len(available_models_list)} modelo(s) listado(s): {available_models_list}")
                        else:
                            logger.warning("⚠️ ListModels retornou lista vazia")
                    except Exception as list_error:
                        logger.warning(f"⚠️ Não foi possível listar modelos via ListModels: {list_error}")
                        # Se não conseguir listar, tenta validar diretamente com diferentes formatos
                        pass
                    
                    # Se não conseguiu listar, tenta validar com modelos conhecidos
                    if not available_models_list:
                        # Tenta diferentes formatos de nome de modelo
                        test_models = [
                            'gemini-1.5-flash',
                            'models/gemini-1.5-flash',
                            'gemini-1.5-pro',
                            'models/gemini-1.5-pro',
                            'gemini-2.0-flash',
                            'models/gemini-2.0-flash',
                            'gemini-2.5-flash',
                            'models/gemini-2.5-flash'
                        ]
                        
                        for test_model in test_models:
                            try:
                                test_response = test_client.models.generate_content(
                                    model=test_model,
                                    contents="test"
                                )
                                # Se chegou aqui, encontrou um modelo válido
                                available_models_list = [test_model]
                                logger.info(f"✅ Chave Gemini válida - Modelo testado com sucesso: {test_model}")
                                break
                            except Exception as test_err:
                                error_str = str(test_err)
                                # Se for 404, continua tentando outros modelos
                                if '404' not in error_str and 'NOT_FOUND' not in error_str:
                                    # Se for outro erro (como autenticação), propaga
                                    if any(kw in error_str.lower() for kw in ['401', '403', 'invalid', 'unauthorized']):
                                        raise
                                continue
                        
                        if not available_models_list:
                            raise Exception("Nenhum modelo testado funcionou. Verifique se a chave tem acesso aos modelos Gemini.")
                    
                except Exception as test_error:
                    error_str = str(test_error)
                    logger.error(f"❌ Erro ao testar chave Gemini: {error_str}", exc_info=True)
                    
                    # Retorna erro específico
                    if any(keyword in error_str.lower() for keyword in ['401', '403', 'invalid', 'unauthorized', 'permission', 'forbidden', 'api key']):
                        return ApiKeyStatus(
                            service=request.service,
                            is_valid=False,
                            models_status=[],
                            available_models=[],
                            blocked_models=[],
                            error=f"Chave de API inválida ou não autorizada. Verifique se a chave está correta. Erro: {error_str}"
                        )
                    else:
                        return ApiKeyStatus(
                            service=request.service,
                            is_valid=False,
                            models_status=[],
                            available_models=[],
                            blocked_models=[],
                            error=f"Erro ao validar chave: {error_str}. Verifique se a chave está correta e se tem acesso à API do Google AI Studio."
                        )
                
                # Se passou no teste, cria ModelRouter e valida todos os modelos
                try:
                    model_router = ModelRouter(validate_on_init=False)
                    
                    # Normaliza nomes dos modelos da API (remove prefixo models/ se houver)
                    normalized_api_models = []
                    if available_models_list:
                        for m in available_models_list:
                            clean_name = m.replace('models/', '') if m.startswith('models/') else m
                            normalized_api_models.append(clean_name)
                        logger.info(f"Modelos normalizados da API: {normalized_api_models}")
                    
                    gemini_service = GeminiService(
                        request.api_key,
                        model_router,
                        validate_models=True
                    )
                    
                    # Obtém status dos modelos
                    models_status = []
                    available_models = model_router.get_validated_models()
                    blocked_models = model_router.get_blocked_models_list()
                except Exception as router_error:
                    # Se houver erro ao criar router/service, usa apenas a lista da API
                    logger.warning(f"Erro ao criar ModelRouter/Service: {router_error}. Usando apenas lista da API.")
                    model_router = None
                    normalized_api_models = []
                    if available_models_list:
                        for m in available_models_list:
                            clean_name = m.replace('models/', '') if m.startswith('models/') else m
                            normalized_api_models.append(clean_name)
                    available_models = normalized_api_models
                    blocked_models = []
                    models_status = []  # Inicializa models_status aqui também
                
                # Garante que models_status está inicializado
                if 'models_status' not in locals():
                    models_status = []
                
                # Se não encontrou modelos validados mas temos modelos da API, usa eles
                if not available_models and normalized_api_models:
                    available_models = normalized_api_models
                    logger.info(f"Usando modelos listados pela API: {available_models}")
                
                # Cria status detalhado para cada modelo
                # Se temos lista da API, usa ela como referência principal
                all_models_to_check = []
                
                # Se temos modelos da API, prioriza eles
                if normalized_api_models:
                    # Adiciona modelos da API primeiro
                    all_models_to_check.extend(normalized_api_models)
                    # Depois adiciona modelos conhecidos que não estão na API (para mostrar como não disponíveis)
                    for known_model in ModelRouter.AVAILABLE_MODELS:
                        if known_model not in all_models_to_check:
                            all_models_to_check.append(known_model)
                else:
                    # Se não temos lista da API, usa apenas modelos conhecidos
                    all_models_to_check = list(ModelRouter.AVAILABLE_MODELS)
                
                for model_name in all_models_to_check:
                    try:
                        # Verifica se está disponível
                        is_available = model_name in available_models if available_models else False
                        
                        # Se temos lista da API e o modelo não está nela, marca como bloqueado
                        if normalized_api_models and not is_available:
                            # Verifica se o modelo está na lista da API (com diferentes formatos)
                            try:
                                model_in_api = (
                                    model_name in normalized_api_models or
                                    f"models/{model_name}" in available_models_list or
                                    any(model_name in api_model or api_model.endswith(model_name) for api_model in available_models_list)
                                )
                                
                                if not model_in_api:
                                    try:
                                        if model_name in ModelRouter.AVAILABLE_MODELS:
                                            # Modelo conhecido mas não está na API - marca como bloqueado
                                            is_blocked = True
                                            block_reason = "not_available"  # Modelo não disponível na sua conta/região
                                        else:
                                            is_blocked = False
                                            block_reason = None
                                    except Exception:
                                        # Se não conseguir verificar, assume não bloqueado
                                        is_blocked = False
                                        block_reason = None
                                else:
                                    is_blocked = model_name in blocked_models if blocked_models else False
                                    block_reason = "quota_exceeded" if is_blocked else None
                            except Exception:
                                # Se houver erro ao verificar, assume não bloqueado
                                is_blocked = model_name in blocked_models if blocked_models else False
                                block_reason = "quota_exceeded" if is_blocked else None
                        else:
                            is_blocked = model_name in blocked_models if blocked_models else False
                            block_reason = "quota_exceeded" if is_blocked else None
                        
                        # Determina status e razão
                        if is_available:
                            status = "available"
                            block_reason = None
                        elif is_blocked:
                            status = "blocked"
                            # Se não tem razão específica, tenta determinar
                            if not block_reason:
                                # Verifica se foi bloqueado por validação
                                if blocked_models and model_name in blocked_models:
                                    block_reason = "quota_or_validation_failed"
                                else:
                                    block_reason = "not_available"
                        else:
                            # Desconhecido: modelo não foi testado ou não está na lista da API
                            status = "unknown"
                            block_reason = None
                        
                        # Calcula informações de cota/custo para o modelo
                        quota_used = None
                        quota_limit = None
                        quota_percentage = None
                        daily_cost = None
                        
                        # Busca uso de hoje para este modelo (com tratamento de erro robusto)
                        try:
                            usage_service = TokenUsageService(db)
                            today_usage = usage_service.get_today_usage_by_model(
                                service=request.service,
                                models=[model_name]
                            )
                            
                            if model_name in today_usage:
                                usage_data = today_usage[model_name]
                                
                                if request.is_free_tier == "free":
                                    # Modelo gratuito: calcula cota
                                    try:
                                        quota_limit = get_model_quota_limit(model_name)
                                        if quota_limit:
                                            quota_used = usage_data['total_tokens']
                                            quota_percentage = (quota_used / quota_limit) * 100 if quota_limit > 0 else 0
                                    except Exception as quota_error:
                                        logger.debug(f"Erro ao calcular quota para {model_name}: {quota_error}")
                                else:
                                    # Modelo pago: calcula custo
                                    try:
                                        pricing = get_model_pricing(model_name)
                                        if pricing:
                                            input_cost = usage_data['input_tokens'] * pricing['input']
                                            output_cost = usage_data['output_tokens'] * pricing['output']
                                            daily_cost = input_cost + output_cost
                                    except Exception as cost_error:
                                        logger.debug(f"Erro ao calcular custo para {model_name}: {cost_error}")
                        except Exception as usage_error:
                            # Se houver qualquer erro ao buscar uso, apenas loga e continua (não bloqueia a verificação)
                            logger.debug(f"Erro ao buscar uso para modelo {model_name}: {usage_error}")
                            # Mantém valores None (sem informação de cota/custo)
                        
                        # Adiciona modelo ao status (fora do try/except de uso)
                        try:
                            models_status.append(ModelStatus(
                                name=model_name,
                                available=is_available,
                                blocked=is_blocked,
                                status=status,
                                reason=block_reason,
                                quota_used=quota_used,
                                quota_limit=quota_limit,
                                quota_percentage=quota_percentage,
                                daily_cost=daily_cost
                            ))
                        except Exception as append_error:
                            # Se houver erro ao adicionar modelo, apenas loga e continua
                            logger.debug(f"Erro ao adicionar modelo {model_name} ao status: {append_error}")
                            # Adiciona modelo com status básico
                            try:
                                models_status.append(ModelStatus(
                                    name=model_name,
                                    available=False,
                                    blocked=False,
                                    status="unknown",
                                    reason=None,
                                    quota_used=None,
                                    quota_limit=None,
                                    quota_percentage=None,
                                    daily_cost=None
                                ))
                            except Exception:
                                # Se ainda assim falhar, apenas loga e continua para próximo modelo
                                logger.warning(f"Não foi possível adicionar modelo {model_name} ao status")
                    except Exception as model_error:
                        # Se houver erro ao processar um modelo específico, marca como desconhecido e continua
                        logger.debug(f"Erro ao processar modelo {model_name}: {model_error}")
                        try:
                            models_status.append(ModelStatus(
                                name=model_name,
                                available=False,
                                blocked=False,
                                status="unknown",
                                reason=None,
                                quota_used=None,
                                quota_limit=None,
                                quota_percentage=None,
                                daily_cost=None
                            ))
                        except Exception:
                            # Se ainda assim falhar, apenas loga e continua
                            logger.warning(f"Não foi possível adicionar modelo {model_name} ao status após erro")
                
                # Retorna status mesmo se houver alguns erros
                try:
                    return ApiKeyStatus(
                        service=request.service,
                        is_valid=len(available_models) > 0,
                        models_status=models_status,
                        available_models=available_models if available_models else [],
                        blocked_models=blocked_models if blocked_models else [],
                        error=None if len(available_models) > 0 else "Nenhum modelo disponível. Verifique suas cotas de API no console do Google AI Studio."
                    )
                except Exception as return_error:
                    # Se houver erro ao criar ApiKeyStatus, retorna versão mínima
                    logger.error(f"Erro ao criar ApiKeyStatus: {return_error}")
                    return ApiKeyStatus(
                        service=request.service,
                        is_valid=False,
                        models_status=[],
                        available_models=[],
                        blocked_models=[],
                        error=f"Erro ao processar status dos modelos: {str(return_error)}"
                    )
            except ImportError:
                return ApiKeyStatus(
                    service=request.service,
                    is_valid=False,
                    models_status=[],
                    available_models=[],
                    blocked_models=[],
                    error="Biblioteca 'google-genai' não instalada. Execute: pip install google-genai"
                )
        
        # Outras APIs (OpenRouter, Groq, Together)
        elif request.service in ["openrouter", "groq", "together"]:
            status_result = await ApiStatusChecker.check_status(request.service, request.api_key)
            
            # Busca uso de hoje para todos os modelos (com tratamento de erro)
            model_names = [model.get("name", "unknown") for model in status_result.get("models_status", [])]
            today_usage = {}
            
            try:
                usage_service = TokenUsageService(db)
                today_usage = usage_service.get_today_usage_by_model(
                    service=request.service,
                    models=model_names if model_names else None
                )
            except Exception as usage_error:
                # Se houver erro ao buscar uso, apenas loga e continua (não bloqueia a verificação)
                logger.debug(f"Erro ao buscar uso para serviço {request.service}: {usage_error}")
                # Mantém today_usage vazio (sem informação de cota/custo)
            
            # Converte para o formato esperado e adiciona informações de cota/custo
            models_status = []
            for model in status_result.get("models_status", []):
                model_name = model.get("name", "unknown")
                
                # Calcula informações de cota/custo
                quota_used = None
                quota_limit = None
                quota_percentage = None
                daily_cost = None
                
                try:
                    if model_name in today_usage:
                        usage_data = today_usage[model_name]
                        
                        if request.is_free_tier == "free":
                            # Modelo gratuito: calcula cota
                            quota_limit = get_model_quota_limit(model_name)
                            if quota_limit:
                                quota_used = usage_data['total_tokens']
                                quota_percentage = (quota_used / quota_limit) * 100 if quota_limit > 0 else 0
                        else:
                            # Modelo pago: calcula custo
                            pricing = get_model_pricing(model_name)
                            if pricing:
                                input_cost = usage_data['input_tokens'] * pricing['input']
                                output_cost = usage_data['output_tokens'] * pricing['output']
                                daily_cost = input_cost + output_cost
                except Exception as calc_error:
                    # Se houver erro ao calcular cota/custo, apenas loga e continua
                    logger.debug(f"Erro ao calcular cota/custo para modelo {model_name}: {calc_error}")
                    # Mantém valores None (sem informação de cota/custo)
                
                models_status.append(ModelStatus(
                    name=model_name,
                    available=model.get("available", False),
                    blocked=model.get("blocked", False),
                    status=model.get("status", "unknown"),
                    reason=model.get("reason"),
                    quota_used=quota_used,
                    quota_limit=quota_limit,
                    quota_percentage=quota_percentage,
                    daily_cost=daily_cost
                ))
            
            return ApiKeyStatus(
                service=request.service,
                is_valid=status_result.get("is_valid", False),
                models_status=models_status,
                available_models=status_result.get("available_models", []),
                blocked_models=status_result.get("blocked_models", []),
                error=status_result.get("error")
            )
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Serviço '{request.service}' não suportado. Serviços disponíveis: gemini, openrouter, groq, together"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        error_type = type(e).__name__
        logger.error(f"Erro ao verificar status da chave API ({error_type}): {e}", exc_info=True)
        
        # Captura detalhes do erro para diagnóstico
        error_details = []
        if hasattr(e, 'status_code'):
            error_details.append(f"Status: {e.status_code}")
        if hasattr(e, 'message'):
            error_details.append(f"Mensagem: {e.message}")
        if hasattr(e, 'details'):
            error_details.append(f"Detalhes: {e.details}")
        
        full_error = error_str
        if error_details:
            full_error = f"{error_str} ({', '.join(error_details)})"
        
        # Log detalhado para debug
        logger.error(f"Erro completo: {full_error}")
        logger.error(f"Tipo do erro: {error_type}")
        logger.error(f"Traceback completo:", exc_info=True)
        
        # Se for erro de autenticação/chave inválida
        if any(keyword in error_str.lower() for keyword in ['401', '403', 'invalid', 'unauthorized', 'permission', 'forbidden', 'api key', 'authentication']):
            return ApiKeyStatus(
                service=request.service,
                is_valid=False,
                models_status=[],
                available_models=[],
                blocked_models=[],
                error=f"Chave de API inválida ou não autorizada. Verifique se a chave está correta e se tem permissões adequadas."
            )
        
        # Se for erro de API não encontrada ou modelo não disponível
        if any(keyword in error_str.lower() for keyword in ['404', 'not found', 'not_found', 'model']):
            return ApiKeyStatus(
                service=request.service,
                is_valid=False,
                models_status=[],
                available_models=[],
                blocked_models=[],
                error=f"Modelo ou endpoint não encontrado. Verifique se a API está acessível."
            )
        
        # Erro genérico - retorna mensagem mais amigável
        return ApiKeyStatus(
            service=request.service,
            is_valid=False,
            models_status=[],
            available_models=[],
            blocked_models=[],
            error=f"Erro ao verificar status da chave. Tipo: {error_type}. Verifique os logs do servidor para mais detalhes."
        )


@router.get("/list")
async def list_api_keys(
    db: Session = Depends(get_db)
):
    """
    Lista todas as chaves de API cadastradas (sem expor as chaves)
    """
    try:
        api_keys = db.query(ApiKey).all()
        
        result = []
        for key in api_keys:
            video = db.query(Video).filter(Video.id == key.video_id).first()
            result.append({
                "id": str(key.id),
                "service": key.service,
                "video_id": str(key.video_id),
                "video_title": video.title if video else None,
                "created_at": key.created_at.isoformat() if key.created_at else None
            })
        
        return {"api_keys": result, "total": len(result)}
    except Exception as e:
        logger.error(f"Erro ao listar chaves API: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao listar chaves: {str(e)}")
