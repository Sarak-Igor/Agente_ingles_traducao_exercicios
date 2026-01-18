from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


class ModelRouter:
    """
    Roteador inteligente de modelos que gerencia cotas e evita modelos bloqueados
    Valida modelos disponíveis na inicialização
    """
    
    # Modelos disponíveis em ordem de prioridade (free tier primeiro)
    AVAILABLE_MODELS = [
        'gemini-1.5-flash',  # Melhor suporte free tier
        'gemini-1.5-pro',
        'gemini-2.0-flash',
        'gemini-2.5-flash',
        'gemini-2.5-pro'
    ]
    
    def __init__(self, blocked_models: List[str] = None, validate_on_init: bool = True, gemini_client=None):
        """
        Inicializa o roteador
        
        Args:
            blocked_models: Lista de modelos bloqueados (sem cota disponível)
            validate_on_init: Se True, valida modelos disponíveis na inicialização
            gemini_client: Cliente Gemini para validação (opcional)
        """
        self.blocked_models = set(blocked_models or [])
        self.model_usage_history: Dict[str, List[datetime]] = {}
        self.model_errors: Dict[str, int] = {}  # Contador de erros por modelo
        self.validated_models: Dict[str, bool] = {}  # Cache de modelos validados
        self.last_validation: Optional[datetime] = None
        
        # Valida modelos na inicialização se solicitado
        if validate_on_init and gemini_client:
            self.validate_available_models(gemini_client)
    
    def get_available_models(self) -> List[str]:
        """
        Retorna lista de modelos disponíveis (não bloqueados)
        """
        return [model for model in self.AVAILABLE_MODELS if model not in self.blocked_models]
    
    def get_next_model(self, exclude_models: List[str] = None) -> Optional[str]:
        """
        Retorna o próximo modelo disponível para uso
        
        Args:
            exclude_models: Modelos a excluir da seleção (ex: já tentados nesta sessão)
        
        Returns:
            Nome do modelo ou None se nenhum estiver disponível
        """
        exclude = set(exclude_models or [])
        exclude.update(self.blocked_models)
        
        available = [m for m in self.AVAILABLE_MODELS if m not in exclude]
        
        if not available:
            return None
        
        # Retorna o primeiro disponível (já está em ordem de prioridade)
        return available[0]
    
    def block_model(self, model_name: str, reason: str = "quota_exceeded"):
        """
        Bloqueia um modelo (ex: cota excedida)
        
        Args:
            model_name: Nome do modelo a bloquear
            reason: Razão do bloqueio
        """
        self.blocked_models.add(model_name)
        if model_name not in self.model_errors:
            self.model_errors[model_name] = 0
        self.model_errors[model_name] += 1
    
    def unblock_model(self, model_name: str):
        """
        Desbloqueia um modelo (ex: após reset de cota)
        
        Args:
            model_name: Nome do modelo a desbloquear
        """
        self.blocked_models.discard(model_name)
    
    def record_success(self, model_name: str):
        """
        Registra uso bem-sucedido de um modelo
        """
        if model_name not in self.model_usage_history:
            self.model_usage_history[model_name] = []
        self.model_usage_history[model_name].append(datetime.now())
        
        # Limpa histórico antigo (mais de 1 hora)
        cutoff = datetime.now() - timedelta(hours=1)
        self.model_usage_history[model_name] = [
            ts for ts in self.model_usage_history[model_name] if ts > cutoff
        ]
    
    def record_error(self, model_name: str, error_type: str = "unknown"):
        """
        Registra erro ao usar um modelo
        
        Args:
            model_name: Nome do modelo
            error_type: Tipo de erro ('quota', 'rate_limit', 'api_error', etc.)
        """
        if model_name not in self.model_errors:
            self.model_errors[model_name] = 0
        self.model_errors[model_name] += 1
        
        # Se for erro de cota, bloqueia o modelo
        if error_type in ['quota', 'resource_exhausted', '429']:
            self.block_model(model_name, error_type)
    
    def get_blocked_models_list(self) -> List[str]:
        """
        Retorna lista de modelos bloqueados
        """
        return list(self.blocked_models)
    
    def validate_available_models(self, gemini_client, test_text: str = "test") -> Dict[str, bool]:
        """
        Valida quais modelos estão disponíveis testando cada um
        
        Args:
            gemini_client: Cliente Gemini para fazer requisições de teste
            test_text: Texto simples para teste (padrão: "test")
        
        Returns:
            Dicionário com status de cada modelo {model_name: is_available}
        """
        validation_results = {}
        
        logger.debug("Iniciando validação de modelos disponíveis...")
        
        # Primeiro, tenta listar modelos disponíveis via API
        api_available_models = []
        try:
            models_response = gemini_client.models.list()
            if hasattr(models_response, 'models'):
                api_available_models = [m.name for m in models_response.models if hasattr(m, 'name')]
            elif hasattr(models_response, '__iter__'):
                api_available_models = [m.name if hasattr(m, 'name') else str(m) for m in models_response]
            
            if api_available_models:
                logger.debug(f"Modelos disponíveis na API: {api_available_models}")
        except Exception as list_error:
            logger.debug(f"Não foi possível listar modelos via API: {list_error}")
        
        for model_name in self.AVAILABLE_MODELS:
            # Se já está bloqueado, marca como indisponível
            if model_name in self.blocked_models:
                validation_results[model_name] = False
                logger.debug(f"Modelo {model_name} já está bloqueado, pulando validação")
                continue
            
            try:
                # Tenta diferentes formatos de nome de modelo
                model_variants = [
                    model_name,  # Nome original
                    f"models/{model_name}",  # Com prefixo models/
                ]
                
                # Se temos lista da API, verifica se o modelo está nela
                if api_available_models:
                    # Procura por modelos que contenham o nome
                    matching_models = [m for m in api_available_models if model_name in m or m.endswith(model_name)]
                    if matching_models:
                        model_variants = matching_models[:1] + model_variants  # Prioriza modelos da API
                
                response = None
                used_model_name = None
                
                for variant in model_variants:
                    try:
                        # Testa com uma requisição simples
                        test_prompt = f"Traduza: {test_text}"
                        response = gemini_client.models.generate_content(
                            model=variant,
                            contents=test_prompt
                        )
                        used_model_name = variant
                        break
                    except Exception as variant_error:
                        error_str = str(variant_error)
                        # Se for 404, tenta próximo variant
                        if '404' in error_str or 'NOT_FOUND' in error_str:
                            continue
                        # Se for outro erro, propaga
                        raise
                
                if not response:
                    raise Exception(f"Nenhuma variante do modelo {model_name} funcionou")
                
                # Verifica se obteve resposta válida
                if response:
                    validation_results[model_name] = True
                    self.validated_models[model_name] = True
                    logger.debug(f"Modelo {model_name} está disponível")
                else:
                    validation_results[model_name] = False
                    self.validated_models[model_name] = False
                    self.block_model(model_name, "validation_failed")
                    logger.debug(f"Modelo {model_name} não retornou resposta válida")
                    
            except Exception as e:
                error_str = str(e)
                error_type = type(e).__name__
                
                # Captura detalhes específicos do erro Gemini (apenas para log em arquivo)
                error_details = []
                if hasattr(e, 'status_code'):
                    error_details.append(f"Status: {e.status_code}")
                if hasattr(e, 'message'):
                    error_details.append(f"Mensagem: {e.message}")
                
                # Extrai mensagem resumida do erro
                short_error = error_str
                if hasattr(e, 'message') and e.message:
                    # Tenta extrair apenas a mensagem principal do erro Gemini
                    if isinstance(e.message, str):
                        # Pega apenas a primeira linha da mensagem
                        short_error = e.message.split('\n')[0] if '\n' in e.message else e.message
                    elif isinstance(e.message, dict) and 'message' in e.message:
                        short_error = e.message['message'].split('\n')[0] if '\n' in str(e.message['message']) else str(e.message['message'])
                
                # Log detalhado apenas em arquivo (DEBUG) - não aparece no console
                logger.debug(f"Erro ao validar modelo {model_name} ({error_type}): {error_str}", exc_info=True)
                
                # Se for erro de quota, bloqueia imediatamente (log resumido)
                if any(keyword in error_str.lower() for keyword in ['429', 'resource_exhausted', 'quota', 'rate limit']):
                    validation_results[model_name] = False
                    self.validated_models[model_name] = False
                    self.block_model(model_name, "quota_exceeded")
                    # Log resumido - apenas mensagem curta, sem traceback
                    logger.debug(f"Modelo {model_name} sem cota disponível - bloqueado: {short_error[:100]}")
                # Se for erro 404, modelo não existe
                elif any(keyword in error_str.lower() for keyword in ['404', 'not_found', 'not found']):
                    validation_results[model_name] = False
                    self.validated_models[model_name] = False
                    self.block_model(model_name, "not_found")
                    logger.debug(f"Modelo {model_name} não encontrado - bloqueado")
                # Se for erro de autenticação
                elif any(keyword in error_str.lower() for keyword in ['401', '403', 'invalid', 'unauthorized', 'permission', 'forbidden', 'api key']):
                    validation_results[model_name] = False
                    self.validated_models[model_name] = False
                    logger.debug(f"Modelo {model_name} - erro de autenticação: {short_error[:100]}")
                else:
                    # Outros erros: marca como indisponível mas não bloqueia permanentemente
                    validation_results[model_name] = False
                    self.validated_models[model_name] = False
                    logger.debug(f"Modelo {model_name} retornou erro na validação: {short_error[:100]}")
        
        self.last_validation = datetime.now()
        
        available_count = sum(1 for v in validation_results.values() if v)
        # Log resumido apenas em arquivo (DEBUG)
        logger.debug(f"Validação concluída: {available_count}/{len(self.AVAILABLE_MODELS)} modelos disponíveis")
        
        return validation_results
    
    def get_validated_models(self) -> List[str]:
        """
        Retorna lista de modelos que foram validados como disponíveis
        """
        return [
            model for model in self.AVAILABLE_MODELS
            if model not in self.blocked_models and self.validated_models.get(model, True)
        ]
    
    def should_revalidate(self, max_age_minutes: int = 60) -> bool:
        """
        Verifica se deve revalidar modelos (última validação muito antiga)
        
        Args:
            max_age_minutes: Idade máxima da validação em minutos
        
        Returns:
            True se deve revalidar
        """
        if not self.last_validation:
            return True
        
        age = datetime.now() - self.last_validation
        return age.total_seconds() > (max_age_minutes * 60)
    
    def to_dict(self) -> Dict:
        """
        Serializa estado do roteador para salvar no banco
        """
        return {
            'blocked_models': list(self.blocked_models),
            'model_errors': self.model_errors
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ModelRouter':
        """
        Restaura roteador a partir de dados salvos
        """
        if isinstance(data, str):
            data = json.loads(data)
        
        router = cls(blocked_models=data.get('blocked_models', []))
        router.model_errors = data.get('model_errors', {})
        return router
