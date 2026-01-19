from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.database import Video, Translation, ApiKey, User
from app.api.routes.auth import get_current_user
from app.services.encryption import encryption_service
from app.services.gemini_service import GeminiService
from app.services.model_router import ModelRouter
from app.services.translation_factory import TranslationServiceFactory
from app.services.llm_service import (
    LLMService, 
    OpenRouterLLMService, 
    GroqLLMService, 
    TogetherAILLMService,
    GeminiLLMService
)
from typing import List, Optional
from uuid import UUID
import random
import re
import logging
import os

router = APIRouter(prefix="/api/practice", tags=["practice"])
logger = logging.getLogger(__name__)


def get_gemini_service(user_id: UUID, db: Session, validate_models: bool = True) -> Optional[GeminiService]:
    """
    Obtém serviço Gemini para um usuário específico
    Valida modelos disponíveis na inicialização
    
    Args:
        user_id: ID do usuário
        db: Sessão do banco de dados
        validate_models: Se True, valida modelos disponíveis na inicialização
    """
    try:
        api_key_record = db.query(ApiKey).filter(
            ApiKey.user_id == user_id,
            ApiKey.service == "gemini"
        ).first()
        
        if not api_key_record:
            return None
        
        decrypted_key = encryption_service.decrypt(api_key_record.encrypted_key)
        
        # Cria ModelRouter sem validação inicial (será validado no GeminiService)
        model_router = ModelRouter(validate_on_init=False)
        
        # Cria GeminiService que validará modelos na inicialização
        # Passa db para rastreamento de tokens
        return GeminiService(decrypted_key, model_router, validate_models=validate_models, db=db)
    except Exception as e:
        logger.error(f"Erro ao obter GeminiService: {e}")
        return None


def get_available_llm_services(
    db: Session, 
    user_id: UUID,
    api_keys_from_request: Optional[dict] = None
) -> List[tuple]:
    """
    Obtém todos os serviços LLM disponíveis em ordem de prioridade
    Todos os serviços recebem TokenUsageService para rastreamento de tokens
    
    Args:
        db: Sessão do banco de dados
        user_id: ID do usuário (obrigatório)
        api_keys_from_request: Dict com chaves de API do request (opcional)
    
    Returns:
        Lista de tuplas (nome_servico, LLMService)
    """
    from app.services.token_usage_service import TokenUsageService
    
    services = []
    api_keys = api_keys_from_request or {}
    
    # Cria TokenUsageService para rastreamento de tokens (compartilhado entre todos os serviços)
    token_usage_service = TokenUsageService(db)
    
    # 1. Tenta Gemini (do banco de dados vinculado ao usuário)
    gemini_service = get_gemini_service(user_id, db, validate_models=False)
    if gemini_service:
        try:
            # Gemini já tem token_usage_service integrado
            gemini_llm = GeminiLLMService(gemini_service)
            if gemini_llm.is_available():
                services.append(('gemini', gemini_llm))
                logger.info("Gemini disponível para geração de frases")
        except Exception as e:
            logger.debug(f"Gemini não disponível: {e}")
    
    # 2. Tenta OpenRouter
    try:
        openrouter_key = api_keys.get('openrouter')
        
        # Se não veio no request, tenta do banco (do usuário)
        if not openrouter_key:
            api_key_record = db.query(ApiKey).filter(
                ApiKey.user_id == user_id,
                ApiKey.service == "openrouter"
            ).first()
            if api_key_record:
                openrouter_key = encryption_service.decrypt(api_key_record.encrypted_key)
        
        # Se ainda não encontrou, tenta variável de ambiente
        if not openrouter_key:
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
        
        if openrouter_key:
            # Passa token_usage_service para rastreamento
            openrouter_service = OpenRouterLLMService(openrouter_key, token_usage_service)
            if openrouter_service.is_available():
                services.append(('openrouter', openrouter_service))
                logger.info("OpenRouter disponível para geração de frases")
    except Exception as e:
        logger.debug(f"OpenRouter não disponível: {e}")
    
    # 3. Tenta Groq
    try:
        groq_key = api_keys.get('groq')
        
        if not groq_key:
            api_key_record = db.query(ApiKey).filter(
                ApiKey.user_id == user_id,
                ApiKey.service == "groq"
            ).first()
            if api_key_record:
                groq_key = encryption_service.decrypt(api_key_record.encrypted_key)
        
        if not groq_key:
            groq_key = os.getenv("GROQ_API_KEY")
        
        if groq_key:
            # Passa token_usage_service para rastreamento
            groq_service = GroqLLMService(groq_key, token_usage_service)
            if groq_service.is_available():
                services.append(('groq', groq_service))
                logger.info("Groq disponível para geração de frases")
    except Exception as e:
        logger.debug(f"Groq não disponível: {e}")
    
    # 4. Tenta Together AI
    try:
        together_key = api_keys.get('together')
        
        if not together_key:
            api_key_record = db.query(ApiKey).filter(
                ApiKey.user_id == user_id,
                ApiKey.service == "together"
            ).first()
            if api_key_record:
                together_key = encryption_service.decrypt(api_key_record.encrypted_key)
        
        if not together_key:
            together_key = os.getenv("TOGETHER_API_KEY")
        
        if together_key:
            # Passa token_usage_service para rastreamento
            together_service = TogetherAILLMService(together_key, token_usage_service)
            if together_service.is_available():
                services.append(('together', together_service))
                logger.info("Together AI disponível para geração de frases")
    except Exception as e:
        logger.debug(f"Together AI não disponível: {e}")
    
    return services


@router.post("/available-agents")
async def get_available_agents(
    request: dict = {},
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna lista de agentes LLM disponíveis com cota
    Aceita chaves de API no request (opcional)
    
    Body (opcional):
        api_keys: Dict com chaves de API {'gemini': '...', 'openrouter': '...', 'groq': '...', 'together': '...'}
    """
    try:
        from app.services.api_status_checker import ApiStatusChecker
        
        agents = []
        api_keys_from_request = request.get('api_keys', {}) if request else {}
        logger.info(f"Chaves recebidas no request: {list(api_keys_from_request.keys())}")
        
        # Verifica Gemini
        try:
            gemini_key = api_keys_from_request.get('gemini')
            if not gemini_key:
                gemini_key = os.getenv("GEMINI_API_KEY")
            if not gemini_key:
                # Tenta buscar do banco (do usuário)
                api_key_record = db.query(ApiKey).filter(
                    ApiKey.user_id == current_user.id,
                    ApiKey.service == "gemini"
                ).first()
                if api_key_record:
                    gemini_key = encryption_service.decrypt(api_key_record.encrypted_key)
            
            if gemini_key:
                model_router = ModelRouter(validate_on_init=False)
                gemini_service = GeminiService(
                    gemini_key,
                    model_router,
                    validate_models=True
                )
                available_models = model_router.get_validated_models()
                if available_models:
                    for model in available_models:
                        category = model_router.get_model_category(model)
                        agents.append({
                            "service": "gemini",
                            "model": model,
                            "display_name": f"Gemini - {model}",
                            "available": True,
                            "category": category
                        })
        except Exception as e:
            logger.debug(f"Gemini não disponível: {e}")
        
        # Verifica OpenRouter
        try:
            openrouter_key = api_keys_from_request.get('openrouter')
            if not openrouter_key:
                openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if not openrouter_key:
                api_key_record = db.query(ApiKey).filter(
                    ApiKey.service == "openrouter"
                ).first()
                if api_key_record:
                    openrouter_key = encryption_service.decrypt(api_key_record.encrypted_key)
            
            if openrouter_key:
                status = await ApiStatusChecker.check_status("openrouter", openrouter_key)
                logger.info(f"OpenRouter status: is_valid={status.get('is_valid')}, available_models={status.get('available_models')}")
                if status.get("is_valid") and status.get("available_models"):
                    for model in status["available_models"]:
                        agents.append({
                            "service": "openrouter",
                            "model": model,
                            "display_name": f"OpenRouter - {model}",
                            "available": True
                        })
                elif status.get("is_valid"):
                    # Se a chave é válida mas não retornou modelos, tenta usar modelos padrão conhecidos
                    logger.debug("OpenRouter válido mas sem lista de modelos, usando modelos padrão")
                    default_models = ["openai/gpt-3.5-turbo", "openai/gpt-4", "anthropic/claude-3-haiku"]
                    for model in default_models:
                        agents.append({
                            "service": "openrouter",
                            "model": model,
                            "display_name": f"OpenRouter - {model}",
                            "available": True
                        })
        except Exception as e:
            logger.debug(f"OpenRouter não disponível: {e}", exc_info=True)
        
        # Verifica Groq
        try:
            groq_key = api_keys_from_request.get('groq')
            if not groq_key:
                groq_key = os.getenv("GROQ_API_KEY")
            if not groq_key:
                api_key_record = db.query(ApiKey).filter(
                    ApiKey.service == "groq"
                ).first()
                if api_key_record:
                    groq_key = encryption_service.decrypt(api_key_record.encrypted_key)
            
            if groq_key:
                status = await ApiStatusChecker.check_status("groq", groq_key)
                logger.info(f"Groq status: is_valid={status.get('is_valid')}, available_models={status.get('available_models')}")
                if status.get("is_valid") and status.get("available_models"):
                    for model in status["available_models"]:
                        agents.append({
                            "service": "groq",
                            "model": model,
                            "display_name": f"Groq - {model}",
                            "available": True
                        })
                elif status.get("is_valid"):
                    # Se a chave é válida mas não retornou modelos, tenta usar modelos padrão conhecidos
                    logger.debug("Groq válido mas sem lista de modelos, usando modelos padrão")
                    default_models = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"]
                    for model in default_models:
                        agents.append({
                            "service": "groq",
                            "model": model,
                            "display_name": f"Groq - {model}",
                            "available": True
                        })
        except Exception as e:
            logger.debug(f"Groq não disponível: {e}", exc_info=True)
        
        # Verifica Together AI
        try:
            together_key = api_keys_from_request.get('together')
            if not together_key:
                together_key = os.getenv("TOGETHER_API_KEY")
            if not together_key:
                api_key_record = db.query(ApiKey).filter(
                    ApiKey.service == "together"
                ).first()
                if api_key_record:
                    together_key = encryption_service.decrypt(api_key_record.encrypted_key)
            
            if together_key:
                status = await ApiStatusChecker.check_status("together", together_key)
                logger.info(f"Together AI status: is_valid={status.get('is_valid')}, available_models={status.get('available_models')}")
                if status.get("is_valid") and status.get("available_models"):
                    for model in status["available_models"]:
                        agents.append({
                            "service": "together",
                            "model": model,
                            "display_name": f"Together AI - {model}",
                            "available": True
                        })
                elif status.get("is_valid"):
                    # Se a chave é válida mas não retornou modelos, tenta usar modelos padrão conhecidos
                    logger.debug("Together AI válido mas sem lista de modelos, usando modelos padrão")
                    default_models = ["meta-llama/Llama-3-8b-chat-hf", "meta-llama/Llama-3-70b-chat-hf"]
                    for model in default_models:
                        agents.append({
                            "service": "together",
                            "model": model,
                            "display_name": f"Together AI - {model}",
                            "available": True
                        })
        except Exception as e:
            logger.debug(f"Together AI não disponível: {e}", exc_info=True)
        
        logger.info(f"Total de agentes encontrados: {len(agents)}")
        for agent in agents:
            logger.info(f"  - {agent['display_name']}")
        
        return {"agents": agents}
        
    except Exception as e:
        logger.error(f"Erro ao obter agentes disponíveis: {e}", exc_info=True)
        return {"agents": []}


@router.post("/phrase/music-context")
async def get_music_phrase(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna uma frase aleatória das músicas traduzidas
    
    Body:
        direction: 'en-to-pt' ou 'pt-to-en'
        difficulty: 'easy', 'medium', 'hard'
        video_ids: Lista de IDs de vídeos (opcional)
    """
    try:
        direction = request.get('direction', 'en-to-pt')
        difficulty = request.get('difficulty', 'medium')
        video_ids = request.get('video_ids')
        
        # Filtra vídeos se especificado
        video_ids_list = None
        if video_ids:
            video_ids_list = [UUID(vid) for vid in video_ids]
        
        # Busca traduções disponíveis (apenas do usuário atual)
        query = db.query(Translation).join(Video).filter(
            Translation.user_id == current_user.id,
            Video.user_id == current_user.id
        )
        
        if video_ids_list:
            query = query.filter(Video.id.in_(video_ids_list))
        
        # Filtra por direção de tradução
        if direction == "en-to-pt":
            query = query.filter(
                Translation.source_language == "en",
                Translation.target_language == "pt"
            )
        else:  # pt-to-en
            query = query.filter(
                Translation.source_language == "pt",
                Translation.target_language == "en"
            )
        
        translations = query.all()
        
        if not translations:
            raise HTTPException(
                status_code=404,
                detail="Nenhuma tradução encontrada com os critérios especificados"
            )
        
        # Seleciona tradução aleatória
        translation = random.choice(translations)
        video = db.query(Video).filter(Video.id == translation.video_id).first()
        
        # Filtra segmentos por dificuldade
        all_segments = translation.segments
        filtered_segments = filter_segments_by_difficulty(all_segments, difficulty)
        
        if not filtered_segments:
            # Se não há segmentos na dificuldade, usa todos
            filtered_segments = all_segments
        
        # Seleciona segmento aleatório
        segment = random.choice(filtered_segments)
        
        return {
            "id": f"{translation.id}-{segment.get('start', 0)}",
            "original": segment.get('original', ''),
            "translated": segment.get('translated', ''),
            "source_language": translation.source_language,
            "target_language": translation.target_language,
            "video_title": video.title if video else None,
            "video_id": str(video.id) if video else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar frase: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao buscar frase: {str(e)}")


@router.post("/phrase/new-context")
async def generate_practice_phrase(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Gera uma frase nova usando palavras das músicas traduzidas
    Tenta usar serviços LLM disponíveis com fallback automático (Gemini, OpenRouter, Groq, Together)
    
    Body:
        direction: 'en-to-pt' ou 'pt-to-en'
        difficulty: 'easy', 'medium', 'hard'
        video_ids: Lista de IDs de vídeos (opcional)
        api_keys: Dict com chaves de API opcionais {'openrouter': '...', 'groq': '...', 'together': '...'}
    """
    try:
        direction = request.get('direction', 'en-to-pt')
        difficulty = request.get('difficulty', 'medium')
        video_ids = request.get('video_ids')
        
        # Busca traduções para extrair palavras (apenas do usuário atual)
        query = db.query(Translation).join(Video).filter(
            Translation.user_id == current_user.id,
            Video.user_id == current_user.id
        )
        
        if video_ids:
            video_ids_list = [UUID(vid) for vid in video_ids]
            query = query.filter(Video.id.in_(video_ids_list))
        
        # Filtra por direção
        if direction == "en-to-pt":
            query = query.filter(
                Translation.source_language == "en",
                Translation.target_language == "pt"
            )
        else:
            query = query.filter(
                Translation.source_language == "pt",
                Translation.target_language == "en"
            )
        
        translations = query.all()
        
        if not translations:
            raise HTTPException(
                status_code=404,
                detail="Nenhuma tradução encontrada para gerar frase"
            )
        
        # Extrai palavras de todas as traduções
        source_words = extract_words_from_translations(translations, direction, difficulty)
        
        if not source_words:
            raise HTTPException(
                status_code=404,
                detail="Não foi possível extrair palavras suficientes"
            )
        
        source_lang = "en" if direction == "en-to-pt" else "pt"
        target_lang = "pt" if direction == "en-to-pt" else "en"
        
        # Obtém chaves de API do request (se fornecidas)
        api_keys_from_request = request.get('api_keys', {})
        
        # Obtém prompt customizado ou usa padrão
        custom_prompt = request.get('custom_prompt')
        preferred_agent = request.get('preferred_agent')  # {'service': '...', 'model': '...'}
        
        # Obtém todos os serviços LLM disponíveis (do usuário)
        available_services = get_available_llm_services(db, current_user.id, api_keys_from_request)
        
        if not available_services:
            raise HTTPException(
                status_code=400,
                detail="Nenhum serviço LLM configurado. Configure pelo menos uma chave de API (Gemini, OpenRouter, Groq ou Together AI) para gerar frases."
            )
        
        # Se há agente preferido, tenta usá-lo primeiro
        if preferred_agent:
            preferred_service = preferred_agent.get('service')
            preferred_model = preferred_agent.get('model')
            
            # Reordena serviços para colocar o preferido primeiro
            preferred_found = False
            reordered_services = []
            
            for service_name, llm_service in available_services:
                if service_name == preferred_service:
                    # Para Gemini, verifica se o modelo corresponde
                    if service_name == 'gemini':
                        if hasattr(llm_service, 'gemini_service') and hasattr(llm_service.gemini_service, 'model'):
                            if llm_service.gemini_service.model == preferred_model or not preferred_model:
                                reordered_services.insert(0, (service_name, llm_service))
                                preferred_found = True
                                continue
                    else:
                        # Para outros serviços, verifica se o modelo corresponde
                        if hasattr(llm_service, 'model_name'):
                            if llm_service.model_name == preferred_model or not preferred_model:
                                reordered_services.insert(0, (service_name, llm_service))
                                preferred_found = True
                                continue
                
                reordered_services.append((service_name, llm_service))
            
            if preferred_found:
                available_services = reordered_services
        
        # Tenta gerar frase com fallback automático entre serviços
        generated_phrase = None
        last_error = None
        tried_services = []
        used_service = None
        used_model = None
        
        for service_name, llm_service in available_services:
            try:
                tried_services.append(service_name)
                logger.info(f"Tentando gerar frase com {service_name}...")
                
                # Gera frase e captura modelo usado (se disponível)
                result = generate_phrase_with_llm(
                    llm_service,
                    source_words,
                    source_lang,
                    target_lang,
                    difficulty,
                    custom_prompt=custom_prompt
                )
                
                # result contém {'phrase': {...}, 'model': '...'}
                phrase_data = result['phrase']
                used_service = service_name
                used_model = result.get('model', service_name)  # Modelo específico se disponível
                
                logger.info(f"Frase gerada com sucesso usando {service_name} (modelo: {used_model})")
                
                # Cria ID único que inclui hash da resposta correta para verificação
                import hashlib
                phrase_hash = hashlib.md5(
                    (phrase_data['original'] + phrase_data['translated']).encode()
                ).hexdigest()[:8]
                
                return {
                    "id": f"generated-{phrase_hash}",
                    "original": phrase_data['original'],
                    "translated": phrase_data['translated'],
                    "source_language": source_lang,
                    "target_language": target_lang,
                    "video_title": None,
                    "video_id": None,
                    "model_used": used_model or used_service,  # Modelo usado para gerar
                    "service_used": used_service  # Serviço usado
                }
                
            except Exception as e:
                error_str = str(e)
                last_error = e
                logger.debug(f"Erro ao gerar frase com {service_name}: {error_str}")
                
                # Se for erro de cota ou indisponibilidade, continua para próximo serviço
                if any(keyword in error_str.lower() for keyword in [
                    'quota', 'indisponível', 'unavailable', 'blocked', 
                    'rate limit', '429', '402', 'sem crédito'
                ]):
                    logger.info(f"{service_name} sem cota disponível, tentando próximo serviço...")
                    continue
                # Para outros erros, também continua tentando
                continue
        
        # Se nenhum serviço funcionou
        error_detail = (
            f"Não foi possível gerar frase. Serviços tentados: {', '.join(tried_services)}. "
        )
        if last_error:
            error_detail += f"Último erro: {str(last_error)}"
        else:
            error_detail += "Nenhum serviço conseguiu gerar a frase."
        
        raise HTTPException(
            status_code=503,
            detail=error_detail
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar frase: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar frase: {str(e)}")


@router.post("/check-answer")
async def check_practice_answer(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verifica se a resposta do usuário está correta
    
    Body:
        phrase_id: ID da frase
        user_answer: Resposta do usuário
        direction: 'en-to-pt' ou 'pt-to-en'
    """
    try:
        phrase_id = request.get('phrase_id')
        user_answer = request.get('user_answer', '').strip()
        direction = request.get('direction', 'en-to-pt')
        
        if not phrase_id:
            raise HTTPException(status_code=400, detail="ID da frase não fornecido")
        
        if not user_answer:
            raise HTTPException(status_code=400, detail="Resposta não pode estar vazia")
        
        # Para palavras avulsas (word-*)
        if isinstance(phrase_id, str) and phrase_id.startswith('word-'):
            correct_answer = request.get('correct_answer')
            if not correct_answer:
                # Se não veio no request, tenta traduzir usando LLM
                word = phrase_id.replace('word-', '')
                try:
                    # Busca tradução usando serviços disponíveis
                    source_lang = "en" if direction == "en-to-pt" else "pt"
                    target_lang = "pt" if direction == "en-to-pt" else "en"
                    
                    # Tenta usar Gemini primeiro
                    gemini_key = os.getenv("GEMINI_API_KEY")
                    if gemini_key:
                        try:
                            model_router = ModelRouter(validate_on_init=False)
                            gemini_service = GeminiService(gemini_key, model_router, validate_models=False)
                            correct_answer = gemini_service._translate_text_with_router(
                                word, target_lang, source_lang
                            )
                        except:
                            pass
                    
                    # Se não conseguiu, usa tradução simples (retorna a palavra como fallback)
                    if not correct_answer:
                        correct_answer = word  # Fallback
                except:
                    correct_answer = word  # Fallback
            
            is_correct = check_answer_similarity(user_answer, correct_answer)
            similarity = calculate_similarity(user_answer, correct_answer)
            
            return {
                "is_correct": is_correct,
                "correct_answer": correct_answer,
                "similarity": similarity
            }
        
        # Para frases geradas, a resposta correta vem no request
        if isinstance(phrase_id, str) and phrase_id.startswith('generated-'):
            correct_answer = request.get('correct_answer')
            if not correct_answer:
                # Se não veio no request, retorna erro
                raise HTTPException(
                    status_code=400,
                    detail="Resposta correta não fornecida para frase gerada"
                )
            
            is_correct = check_answer_similarity(user_answer, correct_answer)
            similarity = calculate_similarity(user_answer, correct_answer)
            
            return {
                "is_correct": is_correct,
                "correct_answer": correct_answer,
                "similarity": similarity
            }
        
        # Para frases das músicas, busca a tradução correta
        if not isinstance(phrase_id, str) or '-' not in phrase_id:
            raise HTTPException(
                status_code=400,
                detail=f"Formato de ID da frase inválido: {phrase_id}"
            )
        
        try:
            translation_id, segment_start = phrase_id.rsplit('-', 1)
            
            # Valida se segment_start é um número válido
            try:
                segment_start_float = float(segment_start)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Formato de timestamp inválido no ID da frase: {segment_start}"
                )
            
            # Valida se translation_id é um UUID válido
            try:
                translation_uuid = UUID(translation_id)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Formato de UUID inválido no ID da frase: {translation_id}"
                )
            
            translation = db.query(Translation).filter(
                Translation.id == translation_uuid,
                Translation.user_id == current_user.id
            ).first()
            
        except HTTPException:
            raise
        except (ValueError, AttributeError) as e:
            logger.error(f"Erro ao processar phrase_id '{phrase_id}': {e}", exc_info=True)
            raise HTTPException(
                status_code=400,
                detail=f"Formato de ID da frase inválido: {phrase_id}"
            )
        
        if not translation:
            raise HTTPException(status_code=404, detail="Frase não encontrada")
        
        # Encontra o segmento correto
        correct_answer = None
        try:
            for seg in translation.segments:
                seg_start = seg.get('start', 0)
                if isinstance(seg_start, (int, float)):
                    if abs(seg_start - segment_start_float) < 0.1:
                        if direction == "en-to-pt":
                            correct_answer = seg.get('translated', '')
                        else:
                            correct_answer = seg.get('original', '')
                        break
        except Exception as e:
            logger.error(f"Erro ao buscar segmento: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Erro ao processar segmentos da tradução"
            )
        
        if not correct_answer:
            raise HTTPException(status_code=404, detail="Segmento não encontrado")
        
        # Verifica resposta (comparação flexível)
        is_correct = check_answer_similarity(user_answer, correct_answer)
        
        return {
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "similarity": calculate_similarity(user_answer, correct_answer)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao verificar resposta: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao verificar resposta: {str(e)}")


def filter_segments_by_difficulty(segments: List[dict], difficulty: str) -> List[dict]:
    """Filtra segmentos por dificuldade baseado no tamanho"""
    if difficulty == "easy":
        # Frases curtas (até 5 palavras)
        return [s for s in segments if len(s.get('original', '').split()) <= 5]
    elif difficulty == "medium":
        # Frases médias (6-12 palavras)
        return [s for s in segments if 6 <= len(s.get('original', '').split()) <= 12]
    else:  # hard
        # Frases longas (13+ palavras)
        return [s for s in segments if len(s.get('original', '').split()) >= 13]


def extract_words_from_translations(
    translations: List[Translation],
    direction: str,
    difficulty: str
) -> List[str]:
    """Extrai palavras únicas das traduções"""
    words = set()
    
    for translation in translations:
        for segment in translation.segments:
            text = segment.get('original', '') if direction == "en-to-pt" else segment.get('translated', '')
            
            # Remove notas musicais e caracteres especiais
            text = re.sub(r'♪+', '', text)
            text = re.sub(r'[^\w\s]', ' ', text)
            
            # Extrai palavras
            segment_words = [w.lower() for w in text.split() if len(w) > 2]
            words.update(segment_words)
    
    # Filtra por dificuldade
    if difficulty == "easy":
        # Palavras comuns e curtas
        common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'can', 'could', 'should', 'may', 'might', 'must', 'to', 'of', 'in', 'on', 'at', 'for', 'with', 'by', 'from', 'as', 'and', 'or', 'but', 'if', 'when', 'where', 'what', 'who', 'why', 'how', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their'}
        words = [w for w in words if w in common_words or len(w) <= 4]
    elif difficulty == "hard":
        # Palavras longas e menos comuns
        words = [w for w in words if len(w) >= 6]
    
    return list(words)[:100]  # Limita a 100 palavras


def generate_phrase_with_llm(
    llm_service: LLMService,
    words: List[str],
    source_lang: str,
    target_lang: str,
    difficulty: str,
    custom_prompt: Optional[str] = None
) -> dict:
    """
    Gera frase usando qualquer serviço LLM
    Retorna dict com 'phrase' e 'model' (se disponível)
    
    Args:
        llm_service: Serviço LLM a ser usado
        words: Lista de palavras disponíveis
        source_lang: Idioma de origem ('en' ou 'pt')
        target_lang: Idioma de destino ('pt' ou 'en')
        difficulty: Nível de dificuldade ('easy', 'medium', 'hard')
        custom_prompt: Prompt customizado (opcional). Se fornecido, será usado em vez do prompt padrão.
                      Pode usar {words} como placeholder para as palavras selecionadas.
    """
    import random
    
    # Seleciona 3-7 palavras aleatórias
    num_words = random.randint(3, 7) if difficulty == "medium" else (random.randint(2, 4) if difficulty == "easy" else random.randint(5, 10))
    selected_words = random.sample(words, min(num_words, len(words)))
    
    source_lang_name = "inglês" if source_lang == "en" else "português"
    target_lang_name = "português" if target_lang == "pt" else "inglês"
    
    difficulty_desc = {
        "easy": "frases curtas e simples, com vocabulário básico",
        "medium": "frases de tamanho médio, com vocabulário intermediário",
        "hard": "frases mais complexas, com vocabulário avançado"
    }
    
    # Usa prompt customizado se fornecido, caso contrário usa o padrão
    if custom_prompt:
        # Substitui placeholders no prompt customizado
        prompt = custom_prompt.replace('{words}', ', '.join(selected_words))
        prompt = prompt.replace('{source_lang}', source_lang_name)
        prompt = prompt.replace('{target_lang}', target_lang_name)
        prompt = prompt.replace('{difficulty}', difficulty)
        prompt = prompt.replace('{difficulty_desc}', difficulty_desc.get(difficulty, ''))
    else:
        prompt = f"""Você é um professor de idiomas. Crie uma frase natural e completa em {source_lang_name} usando TODAS as seguintes palavras: {', '.join(selected_words)}

INSTRUÇÕES IMPORTANTES:
1. A frase deve ser natural, completa e fazer sentido gramaticalmente
2. Use TODAS as palavras fornecidas na frase
3. A frase deve ser adequada para nível {difficulty} de dificuldade ({difficulty_desc.get(difficulty, '')})
4. A frase deve ser uma sentença completa e coerente
5. NÃO adicione explicações, comentários ou prefixos como "Frase:" ou "A frase é:"
6. Retorne APENAS a frase criada, sem aspas, sem citações, sem nada além da frase

Exemplo de formato correto:
Se as palavras forem: ["love", "heart", "beautiful"]
Você deve retornar apenas: "I love your beautiful heart"

Agora crie a frase usando as palavras: {', '.join(selected_words)}"""

    try:
        # Gera frase original usando LLM
        original_phrase = llm_service.generate_text(prompt, max_tokens=200)
        
        # Limpa a resposta
        original_phrase = original_phrase.strip()
        # Remove prefixos comuns
        for prefix in ['Frase:', 'Frase em', 'Resposta:', 'A frase:', 'A frase é:', 'Frase criada:', 'Here is the phrase:', 'The phrase is:']:
            if original_phrase.lower().startswith(prefix.lower()):
                original_phrase = original_phrase[len(prefix):].strip()
        # Remove aspas se houver
        original_phrase = original_phrase.strip('"').strip("'").strip()
        
        if not original_phrase:
            raise Exception("Frase gerada está vazia")
        
        # Traduz a frase gerada usando o mesmo LLM
        translation_prompt = f"""Traduza o seguinte texto de {source_lang_name} para {target_lang_name}. 
Mantenha o mesmo tom e estilo. Retorne APENAS a tradução, sem explicações ou comentários.

Texto: {original_phrase}

Tradução:"""
        
        translated_phrase = llm_service.generate_text(translation_prompt, max_tokens=200)
        translated_phrase = translated_phrase.strip().strip('"').strip("'").strip()
        
        if not translated_phrase:
            raise Exception("Tradução gerada está vazia")
        
        # Tenta obter nome do modelo usado (se disponível)
        model_name = None
        if isinstance(llm_service, GeminiLLMService):
            # Para Gemini, obtém o modelo atual
            if hasattr(llm_service.gemini_service, 'model'):
                model_name = llm_service.gemini_service.model
        elif isinstance(llm_service, OpenRouterLLMService):
            model_name = "openai/gpt-3.5-turbo"  # Modelo padrão do OpenRouter
        elif isinstance(llm_service, GroqLLMService):
            model_name = "llama-3.1-8b-instant"  # Modelo padrão do Groq
        elif isinstance(llm_service, TogetherAILLMService):
            model_name = "meta-llama/Llama-3-8b-chat-hf"  # Modelo padrão do Together
        
        return {
            "phrase": {
                "original": original_phrase,
                "translated": translated_phrase
            },
            "model": model_name
        }
    except Exception as e:
        logger.error(f"Erro ao gerar frase com LLM: {e}")
        raise Exception(f"Erro ao gerar frase: {str(e)}")


def generate_phrase_with_words(
    gemini_service: GeminiService,
    words: List[str],
    source_lang: str,
    target_lang: str,
    difficulty: str
) -> dict:
    """Gera frase usando GeminiService (mantido para compatibilidade)"""
    llm_service = GeminiLLMService(gemini_service)
    return generate_phrase_with_llm(llm_service, words, source_lang, target_lang, difficulty)


# Dicionário de palavras equivalentes/sinônimos
EQUIVALENT_WORDS = {
    # Demonstrativos
    'este': ['esse', 'aquele'],
    'esse': ['este', 'aquele'],
    'esta': ['essa', 'aquela'],
    'essa': ['esta', 'aquela'],
    'estes': ['esses', 'aqueles'],
    'esses': ['estes', 'aqueles'],
    'estas': ['essas', 'aquelas'],
    'essas': ['estas', 'aquelas'],
    # Pronomes pessoais
    'você': ['tu', 'voce'],
    'tu': ['você', 'voce'],
    'voce': ['você', 'tu'],
    'vocês': ['vós', 'voces'],
    'vós': ['vocês', 'voces'],
    # Artigos (em alguns contextos)
    'o': ['a'],
    'a': ['o'],
    'os': ['as'],
    'as': ['os'],
    # Contração comum
    'na': ['no'],
    'no': ['na'],
    'da': ['do'],
    'do': ['da'],
    # Inglês
    'this': ['that', 'these', 'those'],
    'that': ['this', 'these', 'those'],
    'these': ['this', 'that', 'those'],
    'those': ['this', 'that', 'these'],
}


def normalize_semantic(text: str) -> str:
    """
    Normaliza texto considerando sinônimos e palavras equivalentes
    Substitui palavras por suas formas canônicas
    """
    words = text.lower().split()
    normalized = []
    
    for word in words:
        # Remove acentos básicos para comparação
        word_clean = word.strip()
        
        # Verifica se a palavra tem equivalentes
        found_equivalent = False
        for canonical, equivalents in EQUIVALENT_WORDS.items():
            if word_clean == canonical or word_clean in equivalents:
                normalized.append(canonical)
                found_equivalent = True
                break
        
        if not found_equivalent:
            normalized.append(word_clean)
    
    return ' '.join(normalized)


def check_answer_similarity(user_answer: str, correct_answer: str) -> bool:
    """
    Verifica se a resposta do usuário está correta (comparação flexível)
    Considera sinônimos, variações e ajusta threshold baseado no tamanho da frase
    """
    if not user_answer or not correct_answer:
        return False
    
    # Normaliza respostas (remove emojis, pontuação, etc)
    user_norm = normalize_text(user_answer)
    correct_norm = normalize_text(correct_answer)
    
    # Verificação exata após normalização básica
    if user_norm == correct_norm:
        return True
    
    # Normalização semântica (considera sinônimos)
    user_semantic = normalize_semantic(user_norm)
    correct_semantic = normalize_semantic(correct_norm)
    
    # Verificação exata após normalização semântica
    if user_semantic == correct_semantic:
        return True
    
    # Calcula similaridade
    similarity = calculate_similarity(user_semantic, correct_semantic)
    
    # Conta palavras para ajustar threshold
    user_words = set(user_semantic.split())
    correct_words = set(correct_semantic.split())
    num_words = max(len(user_words), len(correct_words))
    
    # Ajusta threshold baseado no tamanho da frase
    if num_words <= 3:
        # Frases muito curtas: threshold mais baixo (60%)
        threshold = 0.60
    elif num_words <= 6:
        # Frases curtas: threshold médio (65%)
        threshold = 0.65
    elif num_words <= 10:
        # Frases médias: threshold padrão (70%)
        threshold = 0.70
    else:
        # Frases longas: threshold mais alto (75%)
        threshold = 0.75
    
    # Verifica similaridade básica
    if similarity >= threshold:
        return True
    
    # Verifica palavras importantes (ignorando palavras muito comuns)
    common_words = {
        'o', 'a', 'os', 'as', 'um', 'uma', 'de', 'do', 'da', 'dos', 'das',
        'em', 'no', 'na', 'nos', 'nas', 'para', 'por', 'com', 'sem',
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'can', 'could', 'should', 'may', 'might', 'must', 'to', 'of',
        'in', 'on', 'at', 'for', 'with', 'by', 'from', 'as', 'and', 'or',
        'but', 'if', 'when', 'where', 'what', 'who', 'why', 'how',
        'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
        'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your',
        'his', 'her', 'its', 'our', 'their'
    }
    
    user_important = user_words - common_words
    correct_important = correct_words - common_words
    
    # Se não há palavras importantes, considera todas
    if not correct_important:
        correct_important = correct_words
        user_important = user_words
    
    # Verifica se pelo menos 70% das palavras importantes estão presentes
    if correct_important:
        important_match = len(user_important.intersection(correct_important)) / len(correct_important)
        if important_match >= 0.7:
            return True
    
    # Última verificação: similaridade com threshold ajustado
    return similarity >= threshold


def normalize_text(text: str) -> str:
    """Normaliza texto para comparação"""
    # Remove acentos, pontuação, espaços extras
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def calculate_similarity(text1: str, text2: str) -> float:
    """Calcula similaridade entre dois textos (0.0 a 1.0)"""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0
