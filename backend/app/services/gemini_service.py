from google import genai
from typing import List, Optional, Callable
from app.schemas.schemas import SubtitleSegment, TranslationSegment
from app.services.model_router import ModelRouter
from app.services.token_usage_service import TokenUsageService
from sqlalchemy.orm import Session
import time
import re
import json
import logging

logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self, api_key: str, model_router: Optional[ModelRouter] = None, validate_models: bool = True, db: Optional[Session] = None):
        self.client = genai.Client(api_key=api_key)
        # Cria ModelRouter sem validação inicial (será validado depois)
        self.model_router = model_router or ModelRouter(validate_on_init=False)
        self.model = 'gemini-1.5-flash'
        self.last_request_time = 0
        self.min_delay_between_requests = 1.0  # Aumentado para evitar rate limit
        self.progress_callback = None
        self.checkpoint_callback = None  # Callback para salvar checkpoint
        self.db = db
        self.token_usage_service = TokenUsageService(db) if db else None
        
        # Valida modelos na inicialização se solicitado
        if validate_models:
            try:
                self.model_router.validate_available_models(self.client)
                # Atualiza modelo inicial para o primeiro disponível
                available = self.model_router.get_validated_models()
                if available:
                    self.model = available[0]
                    logger.info(f"✅ Modelo inicial definido: {self.model}")
                else:
                    logger.warning("⚠️ Nenhum modelo disponível após validação. O sistema tentará usar modelos mesmo assim.")
            except Exception as e:
                logger.error(f"❌ Erro ao validar modelos na inicialização: {e}")
                # Continua mesmo se validação falhar - tentará validar durante uso
    
    def translate_segments(
        self, 
        segments: List[SubtitleSegment], 
        target_language: str,
        source_language: str = "auto",
        progress_callback: Optional[Callable] = None,
        checkpoint_callback: Optional[Callable] = None,
        start_from_index: int = 0,
        existing_translations: Optional[List[TranslationSegment]] = None,
        max_gap: float = 0.0  # Por padrão, não agrupa - traduz individualmente para sincronização perfeita
    ) -> List[TranslationSegment]:
        """
        Traduz segmentos de legenda mantendo alinhamento preciso com timestamps
        Suporta retomada de tradução parcial
        
        Args:
            segments: Segmentos originais para traduzir
            target_language: Idioma de destino
            source_language: Idioma de origem
            progress_callback: Função callback(progress, message) para atualizar progresso
            checkpoint_callback: Função callback(group_index, translated_segments, blocked_models) para salvar checkpoint
            start_from_index: Índice do grupo para começar (retomada)
            existing_translations: Segmentos já traduzidos (para retomada)
            max_gap: Gap máximo entre segmentos para agrupamento (0.0 = não agrupa, traduz individualmente)
        
        Returns:
            Lista completa de segmentos traduzidos
        """
        if not segments:
            return []
        
        self.progress_callback = progress_callback
        self.checkpoint_callback = checkpoint_callback
        
        # Agrupa segmentos próximos (max_gap=0.0 por padrão = não agrupa para sincronização perfeita)
        grouped = self._group_segments(segments, max_gap)
        total_groups = len(grouped)
        
        # Inicia com traduções existentes ou lista vazia
        translated_segments = list(existing_translations) if existing_translations else []
        
        # Se retomando, já temos alguns segmentos traduzidos
        if start_from_index > 0:
            translated_segments = translated_segments[:start_from_index] if existing_translations else []
        
        # Traduz grupos restantes
        for idx in range(start_from_index, total_groups):
            group = grouped[idx]
            
            # Combina textos do grupo
            combined_text = " ".join([seg.text for seg in group['segments']])
            
            # Atualiza progresso (50% a 90% = 40% do progresso total)
            if progress_callback:
                progress = 50 + int((idx / total_groups) * 40)
                message = f"Traduzindo grupo {idx + 1} de {total_groups}..."
                progress_callback(progress, message)
            
            # Adiciona delay entre requisições para evitar rate limit
            self._wait_before_request()
            
            # Tenta traduzir com roteamento inteligente
            try:
                translated_text = self._translate_text_with_router(
                    combined_text, 
                    target_language, 
                    source_language
                )
                
                # Se o grupo tem apenas um segmento, traduz diretamente
                if len(group['segments']) == 1:
                    translated_segments.append(TranslationSegment(
                        start=group['segments'][0].start,
                        duration=group['segments'][0].duration,
                        original=group['segments'][0].text,
                        translated=translated_text
                    ))
                else:
                    # Distribui a tradução mantendo timestamps originais
                    translated_parts = self._distribute_translation(
                        group['segments'], 
                        translated_text
                    )
                    
                    # Cria segmentos de tradução com timestamps originais
                    for i, seg in enumerate(group['segments']):
                        translated_text_for_seg = ""
                        if i < len(translated_parts) and translated_parts[i] and translated_parts[i].strip() != '♪':
                            translated_text_for_seg = translated_parts[i]
                        else:
                            # Fallback: se distribuição falhou ou retornou apenas notas, traduz individualmente
                            try:
                                translated_text_for_seg = self._translate_text_with_router(
                                    seg.text,
                                    target_language,
                                    source_language
                                )
                            except Exception as e:
                                logger.warning(f"Erro ao traduzir segmento individualmente: {e}, usando texto original")
                                translated_text_for_seg = seg.text  # Fallback para o texto original se tudo falhar
                        
                        translated_segments.append(TranslationSegment(
                            start=seg.start,
                            duration=seg.duration,
                            original=seg.text,
                            translated=translated_text_for_seg
                        ))
                
                # Salva checkpoint após cada grupo
                if checkpoint_callback:
                    checkpoint_callback(
                        idx,
                        translated_segments,
                        self.model_router.get_blocked_models_list()
                    )
                    
            except Exception as e:
                error_str = str(e)
                # Se for erro de cota, salva checkpoint e propaga
                if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'quota' in error_str.lower():
                    if checkpoint_callback:
                        checkpoint_callback(
                            idx - 1,  # Salva até o último grupo traduzido
                            translated_segments,
                            self.model_router.get_blocked_models_list()
                        )
                    raise Exception(f"Cota excedida. Progresso salvo até grupo {idx}. Detalhes: {error_str}")
                else:
                    # Outros erros: propaga imediatamente
                    raise
        
        return translated_segments
    
    def _group_segments(self, segments: List[SubtitleSegment], max_gap: float = 0.0) -> List[dict]:
        """
        Agrupa segmentos que estão próximos temporalmente
        Por padrão, max_gap=0.0 para garantir tradução individual e sincronização perfeita
        """
        if not segments:
            return []
        
        groups = []
        current_group = {
            'segments': [segments[0]],
            'start': segments[0].start,
            'end': segments[0].start + segments[0].duration
        }
        
        for i in range(1, len(segments)):
            seg = segments[i]
            gap = seg.start - current_group['end']
            
            # Se o gap é pequeno, adiciona ao grupo atual
            if gap <= max_gap:
                current_group['segments'].append(seg)
                current_group['end'] = seg.start + seg.duration
            else:
                # Fecha grupo atual e inicia novo
                groups.append(current_group)
                current_group = {
                    'segments': [seg],
                    'start': seg.start,
                    'end': seg.start + seg.duration
                }
        
        # Adiciona último grupo
        if current_group['segments']:
            groups.append(current_group)
        
        return groups
    
    def _wait_before_request(self):
        """Aguarda o tempo necessário antes de fazer uma requisição para evitar rate limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_delay_between_requests:
            sleep_time = self.min_delay_between_requests - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _extract_retry_delay(self, error_message: str) -> float:
        """Extrai o tempo de retry sugerido da mensagem de erro"""
        # Procura por padrões como "Please retry in 30.56s" ou "retryDelay: '30s'"
        patterns = [
            r"Please retry in ([\d.]+)s",
            r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s",
            r"retry in ([\d.]+)\s*seconds?",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_message, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        
        # Se não encontrar, retorna um delay padrão
        return 30.0
    
    def _translate_text_with_router(
        self, 
        text: str, 
        target_language: str, 
        source_language: str = "auto"
    ) -> str:
        """
        Traduz texto usando roteamento inteligente de modelos
        """
        language_names = {
            'pt': 'português',
            'en': 'inglês',
            'es': 'espanhol',
            'fr': 'francês',
            'de': 'alemão',
            'it': 'italiano',
            'ja': 'japonês',
            'ko': 'coreano',
            'zh': 'chinês',
            'ru': 'russo'
        }
        
        target_lang_name = language_names.get(target_language, target_language)
        
        # Verifica se há notas musicais no texto (marcadores de alinhamento do YouTube)
        has_musical_notes = '♪' in text
        note_instruction = ""
        if has_musical_notes:
            note_instruction = "\nIMPORTANTE: O texto contém notas musicais (♪) que são marcadores de alinhamento. Preserve essas notas musicais na mesma posição relativa na tradução. As notas musicais separam frases e devem ser mantidas para sincronização."
        
        prompt = f"""Traduza o seguinte texto para {target_lang_name}. 
Mantenha o mesmo tom e estilo. Se for uma música ou poesia, preserve a rima e ritmo quando possível.{note_instruction}
Retorne APENAS a tradução, sem explicações ou comentários.

Texto: {text}

Tradução:"""
        
        max_retries = 3
        last_error = None
        tried_models = []
        
        for attempt in range(max_retries):
            # Revalida modelos se necessário (a cada hora)
            if self.model_router.should_revalidate():
                try:
                    logger.info("Revalidando modelos disponíveis...")
                    self.model_router.validate_available_models(self.client)
                except Exception as e:
                    logger.warning(f"Erro ao revalidar modelos: {e}")
            
            # Obtém próximo modelo disponível (excluindo os já tentados)
            # Prioriza modelos validados como disponíveis
            validated_models = self.model_router.get_validated_models()
            exclude = set(tried_models)
            exclude.update(self.model_router.blocked_models)
            
            # Tenta primeiro modelos validados
            available_validated = [m for m in validated_models if m not in exclude]
            if available_validated:
                model_name = available_validated[0]
            else:
                # Se não há modelos validados, tenta qualquer disponível
                model_name = self.model_router.get_next_model(exclude_models=tried_models)
            
            if not model_name:
                # Nenhum modelo disponível
                blocked = self.model_router.get_blocked_models_list()
                validated = self.model_router.get_validated_models()
                raise Exception(
                    f"Todos os modelos estão indisponíveis. "
                    f"Modelos bloqueados: {blocked}. "
                    f"Modelos validados: {validated}. "
                    f"Verifique suas cotas de API."
                )
            
            tried_models.append(model_name)
            
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                
                # Acessa o texto da resposta
                translated = None
                if hasattr(response, 'text'):
                    translated = response.text.strip()
                elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content'):
                        if hasattr(candidate.content, 'parts') and len(candidate.content.parts) > 0:
                            translated = candidate.content.parts[0].text.strip()
                        elif hasattr(candidate.content, 'text'):
                            translated = candidate.content.text.strip()
                
                if translated:
                    # Sucesso: registra uso e atualiza modelo atual
                    self.model_router.record_success(model_name)
                    self.model = model_name
                    
                    # Captura informações de uso de tokens da resposta
                    input_tokens = 0
                    output_tokens = 0
                    total_tokens = 0
                    
                    try:
                        # Tenta obter informações de uso da resposta
                        if hasattr(response, 'usage_metadata'):
                            usage = response.usage_metadata
                            if hasattr(usage, 'prompt_token_count'):
                                input_tokens = usage.prompt_token_count
                            if hasattr(usage, 'candidates_token_count'):
                                output_tokens = usage.candidates_token_count
                            if hasattr(usage, 'total_token_count'):
                                total_tokens = usage.total_token_count
                        elif hasattr(response, 'usage'):
                            usage = response.usage
                            if hasattr(usage, 'prompt_token_count'):
                                input_tokens = usage.prompt_token_count
                            if hasattr(usage, 'candidates_token_count'):
                                output_tokens = usage.candidates_token_count
                            if hasattr(usage, 'total_token_count'):
                                total_tokens = usage.total_token_count
                    except Exception as e:
                        logger.debug(f"Não foi possível obter uso de tokens da resposta: {e}")
                    
                    # Registra uso de tokens se o serviço estiver disponível
                    if self.token_usage_service and (input_tokens > 0 or output_tokens > 0 or total_tokens > 0):
                        self.token_usage_service.record_usage(
                            service='gemini',
                            model=model_name,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens if total_tokens > 0 else None,
                            requests=1
                        )
                    
                    # Remove aspas se presentes
                    if translated.startswith('"') and translated.endswith('"'):
                        translated = translated[1:-1]
                    if translated.startswith("'") and translated.endswith("'"):
                        translated = translated[1:-1]
                    
                    return translated
                    
            except Exception as e:
                error_str = str(e)
                last_error = e
                
                # Se for erro 404 (modelo não encontrado), tenta próximo
                if '404' in error_str or 'NOT_FOUND' in error_str:
                    self.model_router.record_error(model_name, 'not_found')
                    continue
                
                # Se for erro 429 (rate limit/quota), bloqueia modelo imediatamente e tenta próximo
                if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'quota' in error_str.lower():
                    self.model_router.record_error(model_name, 'quota')
                    self.model_router.block_model(model_name, 'quota_exceeded')
                    self.model_router.validated_models[model_name] = False
                    logger.warning(f"Modelo {model_name} bloqueado por cota excedida. Tentando próximo modelo...")
                    
                    # Se ainda há tentativas, continua com próximo modelo
                    if attempt < max_retries - 1:
                        continue
                    else:
                        # Última tentativa: verifica se há outros modelos disponíveis
                        remaining_models = self.model_router.get_validated_models()
                        remaining_models = [m for m in remaining_models if m not in tried_models]
                        if remaining_models:
                            logger.info(f"Ainda há modelos disponíveis: {remaining_models}. Continuando...")
                            continue
                        else:
                            # Nenhum modelo disponível: propaga erro
                            raise Exception(
                                f"Cota excedida em todos os modelos tentados. "
                                f"Modelos bloqueados: {self.model_router.get_blocked_models_list()}. "
                                f"Detalhes: {error_str}"
                            )
                
                # Para outros erros, registra e propaga
                self.model_router.record_error(model_name, 'api_error')
                raise
        
        # Se chegou aqui, nenhum modelo funcionou
        raise Exception(
            f"Erro ao traduzir após {max_retries} tentativas. "
            f"Modelos bloqueados: {self.model_router.get_blocked_models_list()}. "
            f"Último erro: {str(last_error)}"
        )
    
    def _translate_text(self, text: str, target_language: str, source_language: str = "auto") -> str:
        """Traduz um texto usando Gemini com retry automático para rate limits"""
        language_names = {
            'pt': 'português',
            'en': 'inglês',
            'es': 'espanhol',
            'fr': 'francês',
            'de': 'alemão',
            'it': 'italiano',
            'ja': 'japonês',
            'ko': 'coreano',
            'zh': 'chinês',
            'ru': 'russo'
        }
        
        target_lang_name = language_names.get(target_language, target_language)
        
        # Verifica se há notas musicais no texto (marcadores de alinhamento do YouTube)
        has_musical_notes = '♪' in text
        note_instruction = ""
        if has_musical_notes:
            note_instruction = "\nIMPORTANTE: O texto contém notas musicais (♪) que são marcadores de alinhamento. Preserve essas notas musicais na mesma posição relativa na tradução. As notas musicais separam frases e devem ser mantidas para sincronização."
        
        prompt = f"""Traduza o seguinte texto para {target_lang_name}. 
Mantenha o mesmo tom e estilo. Se for uma música ou poesia, preserve a rima e ritmo quando possível.{note_instruction}
Retorne APENAS a tradução, sem explicações ou comentários.

Texto: {text}

Tradução:"""
        
        # Modelos em ordem de prioridade - gemini-1.5-flash geralmente tem melhor suporte no free tier
        models_to_try = [
            'gemini-1.5-flash',  # Prioriza free tier
            'gemini-1.5-pro',
            'gemini-2.0-flash',
            'gemini-2.5-flash', 
            'gemini-2.5-pro'
        ]
        
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            for model_name in models_to_try:
                try:
                    # Nova API do google-genai - sintaxe correta
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    
                    # Acessa o texto da resposta
                    translated = None
                    if hasattr(response, 'text'):
                        translated = response.text.strip()
                    elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'content'):
                            if hasattr(candidate.content, 'parts') and len(candidate.content.parts) > 0:
                                translated = candidate.content.parts[0].text.strip()
                            elif hasattr(candidate.content, 'text'):
                                translated = candidate.content.text.strip()
                    
                    if translated:
                        # Atualiza o modelo usado para próximas chamadas
                        self.model = model_name
                        
                        # Remove aspas se presentes
                        if translated.startswith('"') and translated.endswith('"'):
                            translated = translated[1:-1]
                        if translated.startswith("'") and translated.endswith("'"):
                            translated = translated[1:-1]
                        
                        return translated
                        
                except Exception as e:
                    error_str = str(e)
                    last_error = e
                    
                    # Se for erro 404 (modelo não encontrado), tenta próximo modelo
                    if '404' in error_str or 'NOT_FOUND' in error_str:
                        continue
                    
                    # Se for erro 429 (rate limit), aguarda e tenta novamente
                    if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'quota' in error_str.lower():
                        if attempt < max_retries - 1:
                            # Extrai o tempo de retry sugerido
                            retry_delay = self._extract_retry_delay(error_str)
                            # Adiciona um pouco mais de margem
                            retry_delay = retry_delay + 5.0
                            
                            # Aguarda antes de tentar novamente
                            time.sleep(retry_delay)
                            # Tenta próximo modelo ou próxima tentativa
                            continue
                        else:
                            # Última tentativa falhou, propaga erro
                            raise Exception(f"Cota excedida. Aguarde alguns minutos e tente novamente. Detalhes: {error_str}")
                    
                    # Para outros erros, propaga imediatamente
                    raise
        
        # Se chegou aqui, nenhum modelo funcionou
        raise Exception(f"Erro ao traduzir com Gemini após {max_retries} tentativas. Último erro: {str(last_error)}")
    
    def _distribute_translation(
        self, 
        segments: List[SubtitleSegment], 
        translated_text: str
    ) -> List[str]:
        """
        Distribui uma tradução agrupada de volta para os segmentos individuais
        Preserva notas musicais (♪) do YouTube como marcadores de alinhamento
        As notas musicais são usadas para manter a estrutura original na tradução
        """
        if len(segments) == 1:
            return [translated_text]
        
        import re
        
        # Extrai textos originais e mapeia posições das notas musicais
        original_texts = [seg.text for seg in segments]
        original_combined = " ".join(original_texts)
        
        # Mapeia posições exatas das notas musicais no original
        # Notas musicais são marcadores importantes que separam frases
        musical_note_pattern = r'♪+'
        
        # Encontra todas as notas musicais e suas posições no texto original combinado
        original_note_positions = []
        for match in re.finditer(musical_note_pattern, original_combined):
            original_note_positions.append({
                'start': match.start(),
                'end': match.end(),
                'text': match.group()
            })
        
        # Verifica se cada segmento original tem notas musicais
        segment_note_info = []
        current_pos = 0
        for i, seg_text in enumerate(original_texts):
            seg_start_in_combined = current_pos
            seg_end_in_combined = current_pos + len(seg_text)
            
            # Encontra notas musicais neste segmento
            notes_in_segment = []
            for note_pos in original_note_positions:
                if seg_start_in_combined <= note_pos['start'] < seg_end_in_combined:
                    # Nota está dentro deste segmento
                    relative_pos = note_pos['start'] - seg_start_in_combined
                    notes_in_segment.append({
                        'position': relative_pos,
                        'text': note_pos['text']
                    })
            
            # Verifica início e fim do segmento
            has_start_note = seg_text.strip().startswith('♪')
            has_end_note = seg_text.strip().endswith('♪')
            
            segment_note_info.append({
                'has_start': has_start_note,
                'has_end': has_end_note,
                'notes': notes_in_segment,
                'text': seg_text
            })
            
            current_pos = seg_end_in_combined + 1  # +1 para o espaço entre segmentos
        
        # Limpa a tradução mas preserva notas musicais que já existem
        translated_clean = translated_text.strip()
        
        # Se a tradução não tem notas musicais mas o original tem, insere nas mesmas posições
        if not re.search(musical_note_pattern, translated_clean) and original_note_positions:
            # Divide a tradução usando as notas musicais do original como guia
            result = self._smart_split_translation_with_notes(
                translated_clean,
                segment_note_info,
                original_texts
            )
        else:
            # Se a tradução já tem notas musicais, usa divisão normal mas preserva as notas
            total_chars = sum(len(seg.text) for seg in segments)
            weights = [len(seg.text) / total_chars for seg in segments]
            result = self._smart_split_translation(
                translated_clean,
                weights,
                original_texts
            )
            
            # Adiciona notas musicais baseado na estrutura original
            for i, seg_info in enumerate(segment_note_info):
                if i < len(result):
                    # Adiciona nota no início se o original tinha
                    if seg_info['has_start'] and not result[i].strip().startswith('♪'):
                        result[i] = '♪ ' + result[i].strip()
                    # Adiciona nota no fim se o original tinha
                    if seg_info['has_end'] and not result[i].strip().endswith('♪'):
                        result[i] = result[i].strip() + ' ♪'
        
        return result
    
    def _smart_split_translation_with_notes(
        self,
        translated_text: str,
        segment_note_info: List[dict],
        original_texts: List[str]
    ) -> List[str]:
        """
        Divide tradução usando notas musicais do original como marcadores de alinhamento
        Preserva a estrutura de notas musicais para manter sincronização
        """
        import re
        
        text = translated_text.strip()
        num_segments = len(segment_note_info)
        
        if num_segments == 1:
            # Se só há um segmento, adiciona notas se necessário
            result = [text]
            if segment_note_info[0]['has_start'] and not text.strip().startswith('♪'):
                result[0] = '♪ ' + text.strip()
            if segment_note_info[0]['has_end'] and not text.strip().endswith('♪'):
                result[0] = result[0].strip() + ' ♪'
            return result
        
        # Calcula pesos baseados no tamanho dos textos originais
        total_chars = sum(len(info['text']) for info in segment_note_info)
        weights = [len(info['text']) / total_chars for info in segment_note_info]
        
        # Divide a tradução respeitando as notas musicais do original
        result = []
        char_idx = 0
        text_len = len(text)
        
        for i, (weight, seg_info) in enumerate(zip(weights, segment_note_info)):
            target_chars = int(text_len * weight)
            
            if i == len(weights) - 1:
                # Último segmento: pega tudo que sobrou
                segment_text = text[char_idx:].strip()
            else:
                # Procura ponto de divisão próximo ao target
                search_start = char_idx
                search_end = min(char_idx + target_chars + int(text_len * 0.3), text_len)
                
                best_split = search_end
                
                # Prioridade: pontuação > espaço
                for split_point in range(search_end, search_start, -1):
                    if split_point < len(text):
                        char = text[split_point]
                        if char in ['.', ',', '!', '?', ';', ':']:
                            best_split = split_point + 1
                            break
                        elif char == ' ' and split_point > search_start + int(target_chars * 0.7):
                            best_split = split_point + 1
                            break
                
                segment_text = text[char_idx:best_split].strip()
                char_idx = best_split
            
            # Adiciona notas musicais baseado na estrutura original
            if seg_info['has_start'] and not segment_text.strip().startswith('♪'):
                segment_text = '♪ ' + segment_text.strip()
            if seg_info['has_end'] and not segment_text.strip().endswith('♪'):
                segment_text = segment_text.strip() + ' ♪'
            
            result.append(segment_text)
        
        return result
    
    def _smart_split_translation(
        self,
        translated_text: str,
        weights: List[float],
        original_texts: List[str]
    ) -> List[str]:
        """
        Divide tradução de forma inteligente, respeitando:
        - Notas musicais (♪)
        - Pontuação (., ,, !, ?)
        - Limites naturais de frase
        """
        import re
        
        text = translated_text.strip()
        
        if len(weights) == 1:
            return [text]
        
        # Se há notas musicais, divide respeitando-as
        if '♪' in text:
            segments = []
            char_idx = 0
            text_len = len(text)
            
            for i, weight in enumerate(weights):
                target_chars = int(text_len * weight)
                
                if i == len(weights) - 1:
                    # Último segmento: pega tudo que sobrou
                    segments.append(text[char_idx:].strip())
                else:
                    # Procura ponto de divisão natural próximo ao target
                    search_start = char_idx
                    search_end = min(char_idx + target_chars + int(text_len * 0.3), text_len)
                    
                    best_split = search_end
                    
                    # Prioridade: nota musical > ponto > vírgula > espaço
                    for split_point in range(search_end, search_start, -1):
                        if split_point < len(text):
                            char = text[split_point]
                            if char in ['♪', '.', ',', '!', '?']:
                                # Se for nota musical, pega até depois dela
                                if char == '♪':
                                    # Procura espaço ou fim após a(s) nota(s)
                                    next_idx = split_point + 1
                                    while next_idx < len(text) and text[next_idx] == '♪':
                                        next_idx += 1
                                    if next_idx < len(text) and text[next_idx] == ' ':
                                        best_split = next_idx + 1
                                    else:
                                        best_split = next_idx
                                else:
                                    best_split = split_point + 1
                                break
                            elif char == ' ' and split_point > search_start + int(target_chars * 0.7):
                                best_split = split_point + 1
                                break
                    
                    segment_text = text[char_idx:best_split].strip()
                    segments.append(segment_text)
                    char_idx = best_split
            
            # Garante que todos os segmentos tenham conteúdo
            while len(segments) < len(weights):
                segments.append("")
            if len(segments) > len(weights):
                segments = segments[:len(weights)]
            
            return segments
        
        # Se não há notas musicais, usa divisão inteligente por pontuação
        words = text.split()
        result = []
        word_idx = 0
        
        for i, weight in enumerate(weights):
            num_words = max(1, int(len(words) * weight))
            
            segment_words = []
            for j in range(word_idx, min(word_idx + num_words, len(words))):
                segment_words.append(words[j])
                # Se a palavra termina com pontuação e já temos 70% das palavras, para
                if j < len(words) - 1 and words[j][-1] in ['.', ',', '!', '?']:
                    if len(segment_words) >= int(num_words * 0.7):
                        word_idx = j + 1
                        break
            else:
                word_idx = min(word_idx + num_words, len(words))
            
            result.append(" ".join(segment_words))
        
        # Adiciona palavras restantes ao último segmento
        if word_idx < len(words):
            result[-1] += " " + " ".join(words[word_idx:])
        
        return result
