"""
Interface abstrata para serviços de tradução
Permite trocar facilmente entre diferentes provedores (Gemini, LibreTranslate, etc.)
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Callable
from app.schemas.schemas import SubtitleSegment, TranslationSegment
import logging
import time

logger = logging.getLogger(__name__)


class TranslationService(ABC):
    """
    Interface base para serviços de tradução
    Permite implementar diferentes provedores mantendo a mesma interface
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def translate_text(
        self, 
        text: str, 
        target_language: str, 
        source_language: str = "auto"
    ) -> str:
        """
        Traduz um texto
        
        Args:
            text: Texto a traduzir
            target_language: Idioma de destino (código ISO, ex: 'pt', 'en')
            source_language: Idioma de origem (código ISO ou 'auto')
        
        Returns:
            Texto traduzido
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Verifica se o serviço está disponível
        
        Returns:
            True se disponível, False caso contrário
        """
        pass
    
    def translate_segments(
        self,
        segments: List[SubtitleSegment],
        target_language: str,
        source_language: str = "auto",
        max_gap: float = 1.5,
        progress_callback: Optional[Callable] = None
    ) -> List[TranslationSegment]:
        """
        Traduz segmentos de legenda (implementação padrão)
        Pode ser sobrescrito por serviços específicos para otimização
        
        Args:
            segments: Segmentos originais
            target_language: Idioma de destino
            source_language: Idioma de origem
            max_gap: Gap máximo entre segmentos para agrupamento (segundos)
            progress_callback: Callback(progress, message) para atualizar progresso
        
        Returns:
            Lista de segmentos traduzidos
        """
        if not segments:
            return []
        
        # Agrupa segmentos
        grouped = self._group_segments(segments, max_gap)
        total_groups = len(grouped)
        
        translated_segments = []
        
        for idx, group in enumerate(grouped):
            start_time = time.time()
            
            # Combina textos do grupo
            combined_text = " ".join([seg.text for seg in group['segments']])
            
            # Log de início
            self.logger.info(
                f"Traduzindo grupo {idx + 1}/{total_groups} "
                f"({len(group['segments'])} segmentos, {len(combined_text)} caracteres)"
            )
            
            # Atualiza progresso
            if progress_callback:
                progress = int((idx / total_groups) * 100)
                message = f"Traduzindo grupo {idx + 1} de {total_groups}..."
                progress_callback(progress, message)
            
            try:
                # CRÍTICO: Se há apenas 1 segmento, traduz individualmente para sincronização perfeita
                if len(group['segments']) == 1:
                    seg = group['segments'][0]
                    # Traduz individualmente para garantir sincronização perfeita 1:1
                    try:
                        translated_text_for_seg = self.translate_text(
                            seg.text,
                            target_language,
                            source_language
                        )
                        # Preserva notas musicais do original
                        if seg.text.strip().startswith('♪') and not translated_text_for_seg.strip().startswith('♪'):
                            translated_text_for_seg = '♪ ' + translated_text_for_seg.strip()
                        if seg.text.strip().endswith('♪') and not translated_text_for_seg.strip().endswith('♪'):
                            translated_text_for_seg = translated_text_for_seg.strip() + ' ♪'
                    except Exception as e:
                        self.logger.warning(f"Erro ao traduzir segmento individualmente: {e}, usando texto original")
                        translated_text_for_seg = seg.text
                    
                    elapsed = time.time() - start_time
                    self.logger.info(
                        f"Segmento {idx + 1}/{total_groups} traduzido em {elapsed:.2f}s "
                        f"({len(translated_text_for_seg)} caracteres)"
                    )
                    
                    translated_segments.append(TranslationSegment(
                        start=seg.start,
                        duration=seg.duration,
                        original=seg.text,
                        translated=translated_text_for_seg
                    ))
                else:
                    # Múltiplos segmentos: traduz agrupado e distribui
                    translated_text = self.translate_text(
                        combined_text,
                        target_language,
                        source_language
                    )
                    
                    elapsed = time.time() - start_time
                    self.logger.info(
                        f"Grupo {idx + 1}/{total_groups} traduzido em {elapsed:.2f}s "
                        f"({len(translated_text)} caracteres)"
                    )
                    
                    # Distribui tradução
                    translated_parts = self._distribute_translation(
                        group['segments'],
                        translated_text
                    )
                    
                    # Cria segmentos traduzidos
                    for i, seg in enumerate(group['segments']):
                        if i < len(translated_parts) and translated_parts[i] and translated_parts[i].strip():
                            # Usa tradução distribuída (remove apenas notas musicais se vazio)
                            translated_text_for_seg = translated_parts[i].strip()
                            # Se resultado é apenas nota musical, traduz individualmente
                            if translated_text_for_seg == '♪' or translated_text_for_seg == '♪ ':
                                try:
                                    translated_text_for_seg = self.translate_text(
                                        seg.text,
                                        target_language,
                                        source_language
                                    )
                                    # Preserva notas musicais do original
                                    if seg.text.strip().startswith('♪') and not translated_text_for_seg.strip().startswith('♪'):
                                        translated_text_for_seg = '♪ ' + translated_text_for_seg.strip()
                                    if seg.text.strip().endswith('♪') and not translated_text_for_seg.strip().endswith('♪'):
                                        translated_text_for_seg = translated_text_for_seg.strip() + ' ♪'
                                except Exception as e:
                                    self.logger.warning(f"Erro ao traduzir segmento individualmente: {e}")
                                    translated_text_for_seg = seg.text
                        else:
                            # Fallback: se distribuição falhou, traduz individualmente para manter sincronização
                            try:
                                translated_text_for_seg = self.translate_text(
                                    seg.text,
                                    target_language,
                                    source_language
                                )
                                # Preserva notas musicais do original
                                if seg.text.strip().startswith('♪') and not translated_text_for_seg.strip().startswith('♪'):
                                    translated_text_for_seg = '♪ ' + translated_text_for_seg.strip()
                                if seg.text.strip().endswith('♪') and not translated_text_for_seg.strip().endswith('♪'):
                                    translated_text_for_seg = translated_text_for_seg.strip() + ' ♪'
                            except Exception as e:
                                self.logger.warning(f"Erro ao traduzir segmento individualmente: {e}, usando texto original")
                                translated_text_for_seg = seg.text
                        
                        translated_segments.append(TranslationSegment(
                            start=seg.start,
                            duration=seg.duration,
                            original=seg.text,
                            translated=translated_text_for_seg
                        ))
                    
            except Exception as e:
                elapsed = time.time() - start_time
                self.logger.error(
                    f"Erro ao traduzir grupo {idx + 1}/{total_groups} após {elapsed:.2f}s: {str(e)}"
                )
                raise
        
        return translated_segments
    
    def _group_segments(self, segments: List[SubtitleSegment], max_gap: float) -> List[dict]:
        """
        Agrupa segmentos próximos temporalmente
        CRÍTICO: Se max_gap=0.0, NÃO agrupa nada - cada segmento é traduzido individualmente
        Isso garante sincronização perfeita 1:1 entre original e tradução
        """
        if not segments:
            return []
        
        # Se max_gap é 0, não agrupa - cada segmento é um grupo individual
        # Isso garante sincronização perfeita timestamp a timestamp
        if max_gap == 0.0:
            return [
                {
                    'segments': [seg],
                    'start': seg.start,
                    'end': seg.start + seg.duration
                }
                for seg in segments
            ]
        
        groups = []
        current_group = {
            'segments': [segments[0]],
            'start': segments[0].start,
            'end': segments[0].start + segments[0].duration
        }
        
        for i in range(1, len(segments)):
            seg = segments[i]
            gap = seg.start - current_group['end']
            
            # Verifica se o último segmento do grupo termina com pontuação final
            last_seg = current_group['segments'][-1]
            ends_with_final_punctuation = last_seg.text.strip().endswith(('.', '!', '?'))
            
            # Não agrupa se:
            # 1. Gap é muito grande
            # 2. Último segmento termina com pontuação final (fim de frase)
            # 3. Segmento atual começa com maiúscula (provavelmente início de nova frase)
            should_not_group = (
                gap > max_gap or
                ends_with_final_punctuation or
                (seg.text.strip() and seg.text.strip()[0].isupper() and gap > 0.1)
            )
            
            if not should_not_group:
                current_group['segments'].append(seg)
                current_group['end'] = seg.start + seg.duration
            else:
                groups.append(current_group)
                current_group = {
                    'segments': [seg],
                    'start': seg.start,
                    'end': seg.start + seg.duration
                }
        
        if current_group['segments']:
            groups.append(current_group)
        
        return groups
    
    def _distribute_translation(
        self,
        segments: List[SubtitleSegment],
        translated_text: str
    ) -> List[str]:
        """
        Distribui tradução agrupada de volta para segmentos individuais
        Preserva notas musicais (♪) do YouTube como marcadores de alinhamento
        As notas musicais são usadas para manter a estrutura original na tradução
        
        CRÍTICO: Se há apenas 1 segmento, retorna a tradução diretamente
        Se há múltiplos segmentos, distribui proporcionalmente mas preserva estrutura
        """
        if len(segments) == 1:
            # Se há apenas 1 segmento, retorna a tradução completa
            # Preserva notas musicais do original se existirem
            original_text = segments[0].text
            result = translated_text.strip()
            
            # Preserva notas musicais do original
            if original_text.strip().startswith('♪') and not result.startswith('♪'):
                result = '♪ ' + result
            if original_text.strip().endswith('♪') and not result.endswith('♪'):
                result = result + ' ♪'
            
            return [result]
        
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
            # Primeiro, tenta dividir a tradução proporcionalmente
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
        - Notas musicais (♪) - usadas como marcadores de alinhamento
        - Pontuação (., ,, !, ?)
        - Limites naturais de frase
        """
        import re
        
        text = translated_text.strip()
        
        if len(weights) == 1:
            return [text]
        
        # Se há notas musicais na tradução, divide respeitando-as como marcadores
        if '♪' in text:
            segments = []
            char_idx = 0
            text_len = len(text)
            
            # Encontra todas as notas musicais e suas posições
            note_positions = []
            for match in re.finditer(r'♪+', text):
                note_positions.append(match.start())
            
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
                    
                    # Prioridade: nota musical (marcador de alinhamento) > pontuação > espaço
                    # Notas musicais são marcadores importantes que separam frases
                    for split_point in range(search_end, search_start, -1):
                        if split_point < len(text):
                            char = text[split_point]
                            if char == '♪':
                                # Nota musical: pega até depois dela (marcador de separação)
                                next_idx = split_point + 1
                                while next_idx < len(text) and text[next_idx] == '♪':
                                    next_idx += 1
                                # Pula espaço após nota se houver
                                if next_idx < len(text) and text[next_idx] == ' ':
                                    best_split = next_idx + 1
                                else:
                                    best_split = next_idx
                                break
                            elif char in ['.', ',', '!', '?', ';', ':']:
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
