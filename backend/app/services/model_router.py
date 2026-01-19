from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
import logging
import re

logger = logging.getLogger(__name__)

# Categorias de modelos
MODEL_CATEGORIES = {
    'text': 'Escrita',
    'reasoning': 'Raciocínio',
    'audio': 'Áudio',
    'image': 'Imagem',
    'video': 'Vídeo',
    'code': 'Código',
    'multimodal': 'Multimodal'
}


class ModelRouter:
    """
    Roteador inteligente de modelos que gerencia cotas e evita modelos bloqueados
    Valida modelos disponíveis na inicialização
    Categoriza modelos por capacidade (text, reasoning, audio, video, code)
    """
    
    # Modelos padrão em ordem de prioridade (free tier primeiro)
    # Estes são usados como fallback se não conseguir listar dinamicamente
    DEFAULT_MODELS = [
        'gemini-1.5-flash',  # Melhor suporte free tier
        'gemini-1.5-pro',
        'gemini-2.0-flash',
        'gemini-2.5-flash',
        'gemini-2.5-pro'
    ]
    
    @staticmethod
    def categorize_model(model_name: str) -> str:
        """
        Categoriza um modelo Gemini baseado no nome
        
        Args:
            model_name: Nome do modelo (ex: 'gemini-1.5-flash')
            
        Returns:
            Categoria do modelo: 'text', 'reasoning', 'audio', 'image', 'video', 'code', 'multimodal'
        """
        name_lower = model_name.lower()
        
        # Code generation
        if 'code' in name_lower:
            return 'code'
        
        # Video generation models (Veo) - geração de vídeo
        if 'veo' in name_lower:
            return 'video'
        
        # Image processing - processamento de imagens (vision, image)
        if 'vision' in name_lower or 'image' in name_lower:
            return 'image'
        
        # Audio processing
        if 'audio' in name_lower or 'speech' in name_lower or 'tts' in name_lower:
            return 'audio'
        
        # Multimodal geral (se não for específico de imagem ou vídeo)
        if 'multimodal' in name_lower:
            return 'multimodal'
        
        # Pro models - geralmente melhor para raciocínio
        if 'pro' in name_lower:
            # Flash thinking é raciocínio
            if 'thinking' in name_lower or 'flash-thinking' in name_lower:
                return 'reasoning'
            # Pro com vision é imagem
            if 'vision' in name_lower:
                return 'image'
            return 'reasoning'
        
        # Flash models - geralmente para escrita rápida
        if 'flash' in name_lower:
            # Flash com vision é imagem
            if 'vision' in name_lower:
                return 'image'
            return 'text'
        
        # Experimental - tenta inferir pela descrição
        if 'exp' in name_lower:
            # Se tem thinking, é reasoning
            if 'thinking' in name_lower:
                return 'reasoning'
            # Se tem vision, é image
            if 'vision' in name_lower:
                return 'image'
            # Se tem veo, é video
            if 'veo' in name_lower:
                return 'video'
            # Padrão para experimental é text
            return 'text'
        
        # Ultra models - geralmente reasoning
        if 'ultra' in name_lower:
            return 'reasoning'
        
        # Padrão: text (escrita)
        return 'text'
    
    def __init__(self, blocked_models: List[str] = None, validate_on_init: bool = True, gemini_client=None):
        """
        Inicializa o roteador
        
        Args:
            blocked_models: Lista de modelos bloqueados (sem cota disponível)
            validate_on_init: Se True, valida modelos disponíveis na inicialização
            gemini_client: Cliente Gemini para validação (opcional)
        """
        # Inicializa lista de modelos (será expandida dinamicamente se possível)
        self.AVAILABLE_MODELS = self.DEFAULT_MODELS.copy()
        
        # Inicializa blocked_models - apenas modelos realmente bloqueados
        self.blocked_models = set(blocked_models or [])
        self.model_usage_history: Dict[str, List[datetime]] = {}
        self.model_errors: Dict[str, int] = {}  # Contador de erros por modelo
        self.validated_models: Dict[str, bool] = {}  # Cache de modelos validados
        self.last_validation: Optional[datetime] = None
        
        # IMPORTANTE: Limpa TODOS os bloqueios ao inicializar
        # Bloqueios devem ocorrer apenas durante uso real, não durante validação
        # Se blocked_models foi passado explicitamente (ex: de um job), mantém
        # Caso contrário, limpa para evitar bloqueios incorretos de validações anteriores
        if not blocked_models:
            # Limpa bloqueios - validação não deve manter bloqueios
            self.blocked_models = set()
            logger.debug("Bloqueios limpos na inicialização - validação não mantém bloqueios")
        
        # Tenta listar modelos dinamicamente se cliente fornecido
        if gemini_client:
            try:
                self._load_available_models(gemini_client)
            except Exception as e:
                logger.debug(f"Não foi possível listar modelos dinamicamente: {e}. Usando lista padrão.")
                self.AVAILABLE_MODELS = self.DEFAULT_MODELS.copy()
        
        # Valida modelos na inicialização se solicitado
        if validate_on_init and gemini_client:
            self.validate_available_models(gemini_client)
    
    def _load_available_models(self, gemini_client) -> List[str]:
        """
        Carrega lista de modelos disponíveis dinamicamente da API do Gemini
        
        Args:
            gemini_client: Cliente Gemini
            
        Returns:
            Lista de nomes de modelos disponíveis
        """
        available = []
        
        # Método 1: Tenta usar models.list() se disponível
        try:
            if hasattr(gemini_client, 'models'):
                if hasattr(gemini_client.models, 'list'):
                    models_list = gemini_client.models.list()
                    for model in models_list:
                        model_name = getattr(model, 'name', None) or str(model)
                        # Inclui modelos Gemini e Veo (vídeo)
                        if 'gemini' in model_name.lower() or 'veo' in model_name.lower():
                            clean_name = model_name.replace('models/', '').strip()
                            if clean_name and clean_name not in available:
                                available.append(clean_name)
                elif hasattr(gemini_client.models, 'list_models'):
                    models_list = gemini_client.models.list_models()
                    for model in models_list:
                        model_name = getattr(model, 'name', None) or str(model)
                        # Inclui modelos Gemini e Veo (vídeo)
                        if 'gemini' in model_name.lower() or 'veo' in model_name.lower():
                            clean_name = model_name.replace('models/', '').strip()
                            if clean_name and clean_name not in available:
                                available.append(clean_name)
        except Exception as e:
            logger.debug(f"Método 1 de listagem falhou: {e}")
        
        # Método 2: Tenta testar modelos conhecidos para ver quais funcionam
        if not available:
            logger.debug("Tentando método alternativo: testando modelos conhecidos...")
            # Usa lista expandida como base
            available = self._get_expanded_models_list()
        else:
            # Se conseguiu listar, adiciona modelos conhecidos que podem não ter aparecido
            expanded = self._get_expanded_models_list()
            for model in expanded:
                if model not in available:
                    available.append(model)
        
        if available:
            # Ordena: free tier primeiro, depois por versão
            def sort_key(name):
                # Prioriza flash (free tier)
                if 'flash' in name.lower():
                    priority = 0
                elif 'pro' in name.lower():
                    priority = 1
                else:
                    priority = 2
                
                # Extrai número da versão (1.5, 2.0, 2.5, etc)
                import re
                version_match = re.search(r'(\d+)\.(\d+)', name)
                if version_match:
                    version = float(f"{version_match.group(1)}.{version_match.group(2)}")
                else:
                    version = 0.0
                
                return (priority, -version)  # Negativo para ordenar maior primeiro
            
            available.sort(key=sort_key)
            self.AVAILABLE_MODELS = available
            logger.info(f"✅ Carregados {len(available)} modelos do Gemini")
            return available
        
        # Fallback final
        return self._get_expanded_models_list()
    
    def _get_expanded_models_list(self) -> List[str]:
        """Retorna lista expandida de modelos conhecidos - apenas modelos principais e estáveis"""
        # Lista reduzida para modelos principais que são mais prováveis de existir
        # Evita incluir modelos experimentais ou que podem não estar disponíveis
        expanded_models = [
            # Flash models (free tier) - prioridade alta - modelos principais
            'gemini-1.5-flash',
            'gemini-1.5-flash-8b',
            'gemini-2.0-flash',
            'gemini-2.5-flash',
            'gemini-2.5-flash-8b',
            # Pro models - modelos principais
            'gemini-1.5-pro',
            'gemini-1.5-pro-latest',
            'gemini-2.5-pro',
            'gemini-2.5-pro-latest',
            # Vision models (processamento de imagens/vídeo)
            'gemini-1.5-pro-vision',
            'gemini-2.0-flash-vision',
            # Video generation models (Veo)
            'veo-2',
            'veo-3',
            'veo-3.1',
            # Modelos experimentais mais comuns (se disponíveis)
            'gemini-2.0-flash-thinking-exp',
        ]
        
        # Remove duplicatas mantendo ordem
        seen = set()
        unique_models = []
        for model in expanded_models:
            if model not in seen:
                seen.add(model)
                unique_models.append(model)
        
        return unique_models
    
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
        Se a validação falhar, não bloqueia os modelos - permite que sejam usados mesmo assim
        
        Args:
            gemini_client: Cliente Gemini para fazer requisições de teste
            test_text: Texto simples para teste (padrão: "test")
        
        Returns:
            Dicionário com status de cada modelo {model_name: is_available}
        """
        validation_results = {}
        validation_errors = []
        
        logger.info("Iniciando validação de modelos disponíveis...")
        
        for model_name in self.AVAILABLE_MODELS:
            # Se já está bloqueado, marca como indisponível mas continua validando
            # (pode ter sido desbloqueado desde a última validação)
            if model_name in self.blocked_models:
                logger.debug(f"Modelo {model_name} está bloqueado, mas tentando validar novamente")
                # Não pula - tenta validar para ver se ainda está bloqueado
            
            try:
                # Testa com uma requisição muito simples e rápida
                test_prompt = "Hello"
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=test_prompt
                )
                
                # Verifica se obteve resposta válida
                if response:
                    # Tenta extrair texto de diferentes formas
                    has_text = False
                    if hasattr(response, 'text') and response.text:
                        has_text = True
                    elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'content'):
                            if hasattr(candidate.content, 'parts') and len(candidate.content.parts) > 0:
                                if hasattr(candidate.content.parts[0], 'text'):
                                    has_text = True
                            elif hasattr(candidate.content, 'text'):
                                has_text = True
                    
                    if has_text:
                        validation_results[model_name] = True
                        self.validated_models[model_name] = True
                        logger.info(f"✅ Modelo {model_name} está disponível")
                    else:
                        # Resposta vazia - não bloqueia, apenas marca como não validado
                        validation_results[model_name] = False
                        logger.debug(f"⚠️ Modelo {model_name} retornou resposta vazia (não bloqueado)")
                else:
                    # Sem resposta - não bloqueia
                    validation_results[model_name] = False
                    logger.debug(f"⚠️ Modelo {model_name} não retornou resposta (não bloqueado)")
                    
            except Exception as e:
                error_str = str(e)
                error_type = type(e).__name__
                validation_errors.append(f"{model_name}: {error_type}")
                
                logger.debug(f"Erro ao validar {model_name}: {error_type} - {error_str[:150]}")
                
                # IMPORTANTE: Durante validação inicial, NÃO bloqueia modelos
                # Erro 429 pode significar:
                # 1. Quota excedida (uso real) - mas não sabemos se foi usado
                # 2. Restrição de tier (modelo pago para free tier) - não é bloqueio real
                # 3. Modelo não disponível para esta conta/região
                # 
                # Bloqueio deve ocorrer APENAS durante uso real, não durante validação
                # 
                # Se estava bloqueado anteriormente, desbloqueia (validação não deve manter bloqueios)
                if model_name in self.blocked_models:
                    self.unblock_model(model_name)
                    logger.info(f"✅ Modelo {model_name} desbloqueado (validação não mantém bloqueios)")
                
                # Marca como não validado, mas NÃO bloqueia
                validation_results[model_name] = False
                # NÃO marca como False no validated_models - deixa como "não validado"
                # NÃO bloqueia - permite que seja usado mesmo assim
                logger.debug(f"⚠️ Modelo {model_name} erro na validação (não bloqueado, será tentado mesmo assim): {error_str[:150]}")
        
        self.last_validation = datetime.now()
        
        available_count = sum(1 for v in validation_results.values() if v)
        logger.info(f"Validação concluída: {available_count}/{len(self.AVAILABLE_MODELS)} modelos validados como disponíveis")
        
        # Se nenhum modelo foi validado, mas também nenhum foi bloqueado, loga aviso
        if available_count == 0 and len(self.blocked_models) == 0:
            logger.warning(f"⚠️ Nenhum modelo validado como disponível. Erros: {', '.join(validation_errors[:3])}")
            logger.info("ℹ️ Modelos não validados ainda podem ser usados - validação é apenas informativa")
        
        return validation_results
    
    def get_validated_models(self) -> List[str]:
        """
        Retorna lista de modelos que foram validados como disponíveis
        Se um modelo não foi validado ainda (não está no dict), assume que está disponível
        Apenas modelos explicitamente marcados como False são excluídos
        """
        return [
            model for model in self.AVAILABLE_MODELS
            if model not in self.blocked_models 
            and (model not in self.validated_models or self.validated_models[model] is True)
        ]
    
    def get_models_by_category(self, category: str) -> List[str]:
        """
        Retorna lista de modelos de uma categoria específica
        
        Args:
            category: Categoria ('text', 'reasoning', 'audio', 'video', 'code', 'multimodal')
            
        Returns:
            Lista de nomes de modelos da categoria
        """
        return [
            model for model in self.AVAILABLE_MODELS
            if self.categorize_model(model) == category
            and model not in self.blocked_models
            and (model not in self.validated_models or self.validated_models[model] is True)
        ]
    
    def get_all_categories(self) -> Dict[str, List[str]]:
        """
        Retorna todos os modelos agrupados por categoria
        
        Returns:
            Dicionário {categoria: [lista de modelos]}
        """
        categories = {}
        for model in self.AVAILABLE_MODELS:
            if model not in self.blocked_models:
                category = self.categorize_model(model)
                if category not in categories:
                    categories[category] = []
                categories[category].append(model)
        return categories
    
    def get_model_category(self, model_name: str) -> str:
        """
        Retorna a categoria de um modelo específico
        
        Args:
            model_name: Nome do modelo
            
        Returns:
            Categoria do modelo
        """
        return self.categorize_model(model_name)
    
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
