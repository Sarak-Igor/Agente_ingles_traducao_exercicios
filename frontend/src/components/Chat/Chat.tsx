import { useState, useEffect, useRef } from 'react';
import { chatApi, ChatSession, ChatMessage, ChatSessionCreate, AvailableModelsResponse, ChangeModelRequest } from '../../services/api';
import { storage } from '../../services/storage';
import './Chat.css';

export const Chat = () => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [mode, setMode] = useState<'writing' | 'conversation'>('writing');
  const [loading, setLoading] = useState(false);
  const [creatingSession, setCreatingSession] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const [availableModels, setAvailableModels] = useState<AvailableModelsResponse>({});
  const [showModelSelector, setShowModelSelector] = useState(false);
  const [changingModel, setChangingModel] = useState(false);

  const targetLanguage = storage.getTargetLanguage();

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    if (currentSession) {
      loadSessionMessages();
      loadAvailableModels();
    }
  }, [currentSession]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadSessions = async () => {
    try {
      const data = await chatApi.listSessions();
      setSessions(data);
    } catch (error: any) {
      console.error('Erro ao carregar sessões:', error);
      // O ProtectedRoute já gerencia autenticação
    }
  };

  const loadSessionMessages = async () => {
    if (!currentSession) return;
    
    try {
      const data = await chatApi.getSession(currentSession.id);
      setMessages(data.messages);
      // Atualiza sessão atual com dados mais recentes
      setCurrentSession(data);
    } catch (error) {
      console.error('Erro ao carregar mensagens:', error);
    }
  };

  const loadAvailableModels = async () => {
    try {
      const models = await chatApi.getAvailableModels();
      setAvailableModels(models);
    } catch (error) {
      console.error('Erro ao carregar modelos disponíveis:', error);
    }
  };

  const handleChangeModel = async (service: string, model: string) => {
    if (!currentSession || changingModel) return;

    setChangingModel(true);
    try {
      const updatedSession = await chatApi.changeModel(currentSession.id, { service, model });
      setCurrentSession(updatedSession);
      setShowModelSelector(false);
    } catch (error: any) {
      console.error('Erro ao trocar modelo:', error);
      alert(error.response?.data?.detail || 'Erro ao trocar modelo');
    } finally {
      setChangingModel(false);
    }
  };

  const getModelDisplayName = (session: ChatSession | null): string => {
    if (!session || !session.model_service || !session.model_name) {
      return 'Modelo não definido';
    }
    
    const serviceNames: { [key: string]: string } = {
      'gemini': 'Gemini',
      'openrouter': 'OpenRouter',
      'groq': 'Groq',
      'together': 'Together'
    };
    
    const serviceName = serviceNames[session.model_service] || session.model_service;
    return `${serviceName} - ${session.model_name}`;
  };

  const createNewSession = async () => {
    if (!targetLanguage) {
      alert('Por favor, selecione um idioma de destino primeiro.');
      return;
    }

    setCreatingSession(true);
    try {
      const sessionData: ChatSessionCreate = {
        mode,
        language: targetLanguage,
      };
      const session = await chatApi.createSession(sessionData);
      setCurrentSession(session);
      setSessions([session, ...sessions]);
      setMessages([]);
    } catch (error: any) {
      console.error('Erro ao criar sessão:', error);
      alert(error.response?.data?.detail || 'Erro ao criar sessão de chat');
    } finally {
      setCreatingSession(false);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || !currentSession || loading) return;

    const userMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: inputMessage,
      content_type: 'text',
      created_at: new Date().toISOString(),
    };

    setMessages([...messages, userMessage]);
    setInputMessage('');
    setLoading(true);

    try {
      const response = await chatApi.sendMessage(currentSession.id, {
        content: inputMessage,
        content_type: 'text',
      });
      setMessages((prev) => [...prev, response]);
    } catch (error: any) {
      console.error('Erro ao enviar mensagem:', error);
      alert(error.response?.data?.detail || 'Erro ao enviar mensagem');
      // Remove mensagem temporária em caso de erro
      setMessages((prev) => prev.filter((m) => m.id !== userMessage.id));
    } finally {
      setLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(chunks, { type: 'audio/webm' });
        await sendAudioMessage(audioBlob);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error('Erro ao iniciar gravação:', error);
      alert('Erro ao acessar o microfone. Verifique as permissões.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const sendAudioMessage = async (audioBlob: Blob) => {
    if (!currentSession || loading) return;

    setLoading(true);
    try {
      const audioFile = new File([audioBlob], 'audio.webm', { type: 'audio/webm' });
      const response = await chatApi.sendAudio(currentSession.id, audioFile);
      setMessages((prev) => [...prev, response]);
    } catch (error: any) {
      console.error('Erro ao enviar áudio:', error);
      if (error.response?.status !== 501) {
        alert(error.response?.data?.detail || 'Erro ao enviar áudio');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2>💬 Chat com Professor</h2>
        <div className="chat-controls">
          <div className="mode-selector">
            <label>
              <input
                type="radio"
                value="writing"
                checked={mode === 'writing'}
                onChange={(e) => setMode(e.target.value as 'writing' | 'conversation')}
                disabled={!!currentSession}
              />
              ✍️ Escrita
            </label>
            <label>
              <input
                type="radio"
                value="conversation"
                checked={mode === 'conversation'}
                onChange={(e) => setMode(e.target.value as 'conversation' | 'writing')}
                disabled={!!currentSession}
              />
              🎤 Conversa
            </label>
          </div>
          {!currentSession ? (
            <button
              onClick={createNewSession}
              disabled={creatingSession}
              className="btn-primary"
            >
              {creatingSession ? 'Criando...' : 'Nova Conversa'}
            </button>
          ) : (
            <>
              <div className="current-model-info">
                <span className="model-label">Modelo:</span>
                <span className="model-name">{getModelDisplayName(currentSession)}</span>
                <button
                  onClick={() => setShowModelSelector(true)}
                  className="btn-change-model"
                  disabled={changingModel}
                  title="Trocar modelo"
                >
                  🔄
                </button>
              </div>
              <button
                onClick={() => {
                  setCurrentSession(null);
                  setMessages([]);
                }}
                className="btn-secondary"
              >
                Nova Conversa
              </button>
            </>
          )}
        </div>
      </div>

      {!currentSession ? (
        <div className="chat-welcome">
          <p>Selecione o modo de treino e clique em "Nova Conversa" para começar!</p>
          <div className="mode-info">
            <div className="mode-card">
              <h3>✍️ Modo Escrita</h3>
              <p>Pratique sua escrita. O professor corrigirá seus erros e dará feedback.</p>
            </div>
            <div className="mode-card">
              <h3>🎤 Modo Conversa</h3>
              <p>Converse naturalmente. O professor ajustará o nível ao seu conhecimento.</p>
            </div>
          </div>
        </div>
      ) : (
        <>
          <div className="chat-messages">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`message ${message.role}`}
              >
                <div className="message-content">
                  {message.role === 'user' && message.content_type === 'audio' && (
                    <div className="audio-indicator">🎤 Áudio enviado</div>
                  )}
                  <p>{message.content}</p>
                  {message.feedback_type && (
                    <span className="feedback-badge">{message.feedback_type}</span>
                  )}
                </div>
                <div className="message-time">
                  {new Date(message.created_at).toLocaleTimeString()}
                </div>
              </div>
            ))}
            {loading && (
              <div className="message assistant">
                <div className="message-content">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-container">
            <div className="chat-input-wrapper">
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={
                  mode === 'writing'
                    ? 'Escreva sua mensagem...'
                    : 'Digite ou grave uma mensagem...'
                }
                disabled={loading}
                rows={3}
              />
              <div className="chat-input-actions">
                {mode === 'conversation' && (
                  <button
                    onClick={isRecording ? stopRecording : startRecording}
                    className={`audio-button ${isRecording ? 'recording' : ''}`}
                    disabled={loading}
                    title={isRecording ? 'Parar gravação' : 'Gravar áudio'}
                  >
                    {isRecording ? '⏹️' : '🎤'}
                  </button>
                )}
                <button
                  onClick={sendMessage}
                  disabled={!inputMessage.trim() || loading}
                  className="send-button"
                >
                  Enviar
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {showModelSelector && (
        <div className="model-selector-overlay" onClick={() => setShowModelSelector(false)}>
          <div className="model-selector-modal" onClick={(e) => e.stopPropagation()}>
            <div className="model-selector-header">
              <h3>Selecionar Modelo</h3>
              <button
                className="close-button"
                onClick={() => setShowModelSelector(false)}
              >
                ×
              </button>
            </div>
            <div className="model-selector-content">
              {Object.entries(availableModels).map(([service, models]) => {
                if (!models || models.length === 0) return null;
                
                const serviceNames: { [key: string]: string } = {
                  'gemini': 'Gemini',
                  'openrouter': 'OpenRouter',
                  'groq': 'Groq',
                  'together': 'Together'
                };
                
                const serviceIcons: { [key: string]: string } = {
                  'gemini': '🤖',
                  'openrouter': '🌐',
                  'groq': '⚡',
                  'together': '🔗'
                };
                
                return (
                  <div key={service} className="model-service-group">
                    <div className="service-header">
                      <span className="service-icon">{serviceIcons[service] || '🔧'}</span>
                      <h4 className={`service-name service-${service}`}>
                        {serviceNames[service] || service}
                      </h4>
                      <span className="service-badge">API</span>
                    </div>
                    <div className="model-list">
                      {models.map((model) => (
                        <button
                          key={model.name}
                          className={`model-item ${
                            currentSession?.model_service === service &&
                            currentSession?.model_name === model.name
                              ? 'active'
                              : ''
                          } ${!model.available ? 'unavailable' : ''}`}
                          onClick={() => handleChangeModel(service, model.name)}
                          disabled={changingModel || !model.available}
                        >
                          <div className="model-item-content">
                            <span className="model-item-name">{model.name}</span>
                            {model.category && (
                              <span className="model-category">{model.category}</span>
                            )}
                          </div>
                          <div className="model-item-badges">
                            {currentSession?.model_service === service &&
                              currentSession?.model_name === model.name && (
                              <span className="model-item-badge current">Atual</span>
                            )}
                            {!model.available && (
                              <span className="model-item-badge unavailable">Indisponível</span>
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
              {Object.keys(availableModels).length === 0 && (
                <div className="no-models">Carregando modelos disponíveis...</div>
              )}
            </div>
            {changingModel && (
              <div className="model-selector-loading">Trocando modelo...</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
