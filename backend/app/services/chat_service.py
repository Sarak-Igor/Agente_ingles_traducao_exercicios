"""
Serviço de chat para aprendizado de idiomas
Gerencia conversas com LLMs configurados como professores de idioma
"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from app.models.database import ChatSession, ChatMessage, UserProfile
from app.services.chat_router import ChatRouter
from app.services.llm_service import LLMService
import json
import logging

logger = logging.getLogger(__name__)


class ChatService:
    """Serviço para gerenciar chat de aprendizado de idiomas"""
    
    def __init__(
        self,
        chat_router: ChatRouter,
        db: Session
    ):
        self.chat_router = chat_router
        self.db = db
    
    def create_session(
        self,
        user_id: str,
        mode: str,
        language: str,
        user_profile: Optional[UserProfile] = None,
        preferred_service: Optional[str] = None,
        preferred_model: Optional[str] = None
    ) -> ChatSession:
        """Cria nova sessão de chat"""
        from uuid import UUID
        
        # Se modelo preferido foi fornecido, valida e usa
        if preferred_service and preferred_model:
            # Valida que serviço está disponível
            if not self.chat_router.is_service_available(preferred_service):
                raise Exception(f"Serviço {preferred_service} não está disponível")
            
            # Valida modelo (verifica se está na lista de disponíveis)
            # Por enquanto, aceita qualquer modelo - validação será feita no uso
            model_info = {
                'service': preferred_service,
                'model': preferred_model
            }
        else:
            # Seleciona melhor modelo para a sessão
            model_info = self.chat_router.select_best_model(
                mode=mode,
                user_profile=user_profile,
                preferred_service=preferred_service
            )
        
        if not model_info:
            raise Exception("Nenhum modelo LLM disponível")
        
        session = ChatSession(
            user_id=UUID(user_id),
            mode=mode,
            language=language,
            model_service=model_info.get('service'),
            model_name=model_info.get('model'),
            is_active=True
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        # Cria mensagem inicial do sistema
        initial_message = self._create_initial_message(session, user_profile)
        self.db.add(initial_message)
        self.db.commit()
        
        logger.info(f"Sessão de chat criada: {session.id} (modo: {mode}, idioma: {language}, modelo: {model_info.get('service')}/{model_info.get('model')})")
        return session
    
    def _create_initial_message(
        self,
        session: ChatSession,
        user_profile: Optional[UserProfile]
    ) -> ChatMessage:
        """Cria mensagem inicial do professor"""
        # Constrói prompt do sistema baseado no contexto
        system_prompt = self._build_system_prompt(session, user_profile)
        
        message = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=system_prompt,
            content_type="text"
        )
        
        return message
    
    def _build_system_prompt(
        self,
        session: ChatSession,
        user_profile: Optional[UserProfile]
    ) -> str:
        """Constrói prompt do sistema para o professor"""
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
        
        learning_language = language_names.get(session.language, session.language)
        native_language = "português"
        proficiency = "iniciante"
        
        if user_profile:
            native_language = language_names.get(user_profile.native_language, user_profile.native_language)
            proficiency = {
                'beginner': 'iniciante',
                'intermediate': 'intermediário',
                'advanced': 'avançado'
            }.get(user_profile.proficiency_level, 'iniciante')
        
        if session.mode == "writing":
            prompt = f"""Você é um professor de {learning_language} experiente e paciente. Seu aluno é {proficiency} e fala {native_language} como idioma nativo.

MODO: ESCRITA
- Avalie a escrita do aluno
- Corrija erros gramaticais de forma clara e didática
- Explique as correções quando necessário
- Forneça sugestões de vocabulário mais apropriado
- Seja encorajador e positivo
- Use {native_language} para explicações quando necessário
- Mantenha o foco em melhorar a escrita do aluno

Comece a conversa de forma amigável e pergunte sobre o que o aluno gostaria de praticar hoje."""
        else:
            prompt = f"""Você é um professor de {learning_language} experiente e paciente. Seu aluno é {proficiency} e fala {native_language} como idioma nativo.

MODO: CONVERSA
- Converse naturalmente em {learning_language}
- Ajuste a complexidade do vocabulário ao nível do aluno ({proficiency})
- Faça perguntas interessantes para manter a conversa fluindo
- Corrija erros de forma sutil e natural
- Use {native_language} apenas quando necessário para explicações
- Seja encorajador e crie um ambiente descontraído

Comece a conversa de forma natural e amigável."""
        
        return prompt
    
    def send_message(
        self,
        session_id: str,
        content: str,
        content_type: str = "text",
        transcription: Optional[str] = None
    ) -> ChatMessage:
        """Envia mensagem do usuário e obtém resposta do professor"""
        from uuid import UUID
        
        session = self.db.query(ChatSession).filter(ChatSession.id == UUID(session_id)).first()
        if not session:
            raise Exception("Sessão não encontrada")
        
        if not session.is_active:
            raise Exception("Sessão não está ativa")
        
        # Cria mensagem do usuário
        user_message = ChatMessage(
            session_id=session.id,
            role="user",
            content=content,
            content_type=content_type,
            transcription=transcription
        )
        self.db.add(user_message)
        self.db.flush()
        
        # Obtém histórico de mensagens para contexto
        previous_messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.created_at).all()
        
        # Gera resposta do professor
        assistant_response = self._generate_response(
            session,
            previous_messages,
            user_message
        )
        
        # Cria mensagem do assistente
        assistant_message = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=assistant_response['content'],
            content_type="text",
            feedback_type=assistant_response.get('feedback_type')
        )
        self.db.add(assistant_message)
        
        # Atualiza contador de mensagens
        session.message_count += 1
        
        # Atualiza perfil do usuário
        user_profile = self.db.query(UserProfile).filter(
            UserProfile.user_id == session.user_id
        ).first()
        if user_profile:
            user_profile.total_chat_messages += 1
        
        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(assistant_message)
        
        return assistant_message
    
    def _generate_response(
        self,
        session: ChatSession,
        previous_messages: List[ChatMessage],
        user_message: ChatMessage
    ) -> Dict[str, str]:
        """Gera resposta do professor usando LLM"""
        # Obtém serviço LLM
        service = self.chat_router.get_service(session.model_service)
        if not service:
            raise Exception(f"Serviço {session.model_service} não disponível")
        
        # Constrói contexto da conversa
        conversation_context = self._build_conversation_context(
            previous_messages,
            user_message
        )
        
        try:
            # Obtém modelo da sessão (se especificado)
            model_name = session.model_name if session.model_name else None
            
            # Gera resposta usando modelo da sessão
            # Para serviços não-Gemini, passa model_name como parâmetro
            if session.model_service == 'gemini':
                # Gemini usa ModelRouter internamente, não precisa passar model_name
                response_text = service.generate_text(
                    prompt=conversation_context,
                    max_tokens=1000
                )
            else:
                # Outros serviços aceitam model_name como parâmetro
                response_text = service.generate_text(
                    prompt=conversation_context,
                    max_tokens=1000,
                    model_name=model_name
                )
            
            # Analisa tipo de feedback (opcional)
            feedback_type = self._analyze_feedback_type(response_text)
            
            return {
                'content': response_text,
                'feedback_type': feedback_type
            }
        except Exception as e:
            logger.error(f"Erro ao gerar resposta: {e}")
            raise Exception(f"Erro ao gerar resposta do professor: {str(e)}")
    
    def _build_conversation_context(
        self,
        previous_messages: List[ChatMessage],
        current_message: ChatMessage
    ) -> str:
        """Constrói contexto da conversa para o LLM"""
        context_parts = []
        
        # Adiciona mensagens anteriores (últimas 10 para não exceder tokens)
        recent_messages = previous_messages[-10:] if len(previous_messages) > 10 else previous_messages
        
        for msg in recent_messages:
            if msg.role == "user":
                content = msg.transcription if msg.transcription else msg.content
                context_parts.append(f"Aluno: {content}")
            elif msg.role == "assistant":
                context_parts.append(f"Professor: {msg.content}")
        
        # Adiciona mensagem atual
        current_content = current_message.transcription if current_message.transcription else current_message.content
        context_parts.append(f"Aluno: {current_content}")
        context_parts.append("Professor:")
        
        return "\n".join(context_parts)
    
    def _analyze_feedback_type(self, response: str) -> Optional[str]:
        """Analisa tipo de feedback na resposta (opcional)"""
        response_lower = response.lower()
        
        if any(word in response_lower for word in ['correto', 'correção', 'erro', 'deveria ser']):
            return "correction"
        elif any(word in response_lower for word in ['explicação', 'porque', 'razão', 'motivo']):
            return "explanation"
        elif any(word in response_lower for word in ['parabéns', 'bom trabalho', 'excelente', 'ótimo']):
            return "encouragement"
        
        return None
    
    def get_session_messages(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[ChatMessage]:
        """Retorna mensagens da sessão"""
        from uuid import UUID
        
        messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == UUID(session_id)
        ).order_by(ChatMessage.created_at).limit(limit).all()
        
        return messages
    
    def close_session(self, session_id: str):
        """Fecha sessão de chat"""
        from uuid import UUID
        
        session = self.db.query(ChatSession).filter(ChatSession.id == UUID(session_id)).first()
        if session:
            session.is_active = False
            self.db.commit()
    
    def change_session_model(
        self,
        session_id: str,
        service: str,
        model: str
    ) -> ChatSession:
        """Troca modelo da sessão de chat"""
        from uuid import UUID
        
        session = self.db.query(ChatSession).filter(ChatSession.id == UUID(session_id)).first()
        if not session:
            raise ValueError("Sessão não encontrada")
        
        if not session.is_active:
            raise ValueError("Sessão não está ativa")
        
        # Valida que serviço está disponível
        if not self.chat_router.is_service_available(service):
            raise ValueError(f"Serviço {service} não está disponível")
        
        # Valida modelo (verifica se está na lista de disponíveis do serviço)
        # Para Gemini, valida via ModelRouter
        if service == 'gemini':
            if self.chat_router.gemini_service:
                available_models = self.chat_router.gemini_service.model_router.get_available_models()
                if model not in available_models:
                    raise ValueError(f"Modelo {model} não está disponível para Gemini")
        else:
            # Para outros serviços, valida se modelo está na lista de disponíveis
            # Por enquanto, aceita qualquer modelo - validação será feita no uso
            # (pode ser melhorado no futuro com validação mais rigorosa)
            pass
        
        # Atualiza modelo na sessão
        session.model_service = service
        session.model_name = model
        
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(f"Modelo da sessão {session_id} alterado para {service}/{model}")
        return session