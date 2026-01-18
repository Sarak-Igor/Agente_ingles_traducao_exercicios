import { useState, useEffect } from 'react';
import { videoApi } from '../../services/api';
import { storage } from '../../services/storage';
import './KnowledgePractice.css';

interface PracticePhrase {
  id: string;
  original: string;
  translated: string;
  source_language: string;
  target_language: string;
  video_title?: string;
  model_used?: string;
  service_used?: string;
}

interface PracticeStats {
  total: number;
  correct: number;
  incorrect: number;
  streak: number;
  skipped: number;
}

type PracticeContext = 'music-context' | 'new-context' | 'words';
type PracticeModality = 'complete' | 'translate';
type TranslationDirection = 'en-to-pt' | 'pt-to-en';
type Difficulty = 'easy' | 'medium' | 'hard';

export const KnowledgePractice = () => {
  const [modalities, setModalities] = useState<PracticeModality[]>(['translate']);
  const [contexts, setContexts] = useState<PracticeContext[]>(['music-context']);
  const [direction, setDirection] = useState<TranslationDirection>('en-to-pt');
  const [difficulty, setDifficulty] = useState<Difficulty>('medium');
  const [currentPhrase, setCurrentPhrase] = useState<PracticePhrase | null>(null);
  const [userAnswer, setUserAnswer] = useState('');
  const [showAnswer, setShowAnswer] = useState(false);
  const [isCorrect, setIsCorrect] = useState<boolean | null>(null);
  // Carrega estatísticas do localStorage ao montar
  const loadStatsFromStorage = (): PracticeStats => {
    const saved = storage.getPracticeStats();
    if (saved) {
      return saved;
    }
    return {
      total: 0,
      correct: 0,
      incorrect: 0,
      streak: 0,
      skipped: 0,
    };
  };

  const [stats, setStats] = useState<PracticeStats>(loadStatsFromStorage());
  const [loading, setLoading] = useState(false);
  const [selectedVideos, setSelectedVideos] = useState<string[]>([]);
  const [availableVideos, setAvailableVideos] = useState<any[]>([]);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [customPrompt, setCustomPrompt] = useState('');
  const [selectedAgent, setSelectedAgent] = useState<{ service: string; model: string } | null>(null);
  const [availableAgents, setAvailableAgents] = useState<Array<{ service: string; model: string; display_name: string; available: boolean }>>([]);
  const [currentWord, setCurrentWord] = useState<PracticePhrase | null>(null);
  const [wordTranslations, setWordTranslations] = useState<{ [word: string]: string }>({});
  const [showAddWordsModal, setShowAddWordsModal] = useState(false);
  const [wordsInput, setWordsInput] = useState('');
  const [wordsList, setWordsList] = useState<Array<{ id: string; word: string; language: string; translation: string | null; created_at: string | null }>>([]);
  const [loadingWords, setLoadingWords] = useState(false);
  const [wordsFilterLanguage, setWordsFilterLanguage] = useState<string>('');

  useEffect(() => {
    loadAvailableVideos();
    loadAvailableAgents();
    // Carrega estatísticas salvas ao montar o componente
    const savedStats = storage.getPracticeStats();
    if (savedStats) {
      setStats(savedStats);
    }
    // Carrega frase não respondida se existir
    const savedPhrase = storage.getCurrentPhrase();
    if (savedPhrase && savedPhrase.phrase) {
      setCurrentPhrase(savedPhrase.phrase);
      setUserAnswer(savedPhrase.userAnswer);
    }
    // Carrega prompt padrão
    const defaultPrompt = `Você é um professor de idiomas. Crie uma frase natural e completa em {source_lang} usando TODAS as seguintes palavras: {words}

INSTRUÇÕES IMPORTANTES:
1. A frase deve ser natural, completa e fazer sentido gramaticalmente
2. Use TODAS as palavras fornecidas na frase
3. A frase deve ser adequada para nível {difficulty} de dificuldade ({difficulty_desc})
4. A frase deve ser uma sentença completa e coerente
5. NÃO adicione explicações, comentários ou prefixos como "Frase:" ou "A frase é:"
6. Retorne APENAS a frase criada, sem aspas, sem citações, sem nada além da frase

Exemplo de formato correto:
Se as palavras forem: ["love", "heart", "beautiful"]
Você deve retornar apenas: "I love your beautiful heart"

Agora crie a frase usando as palavras: {words}`;
    setCustomPrompt(defaultPrompt);
  }, []);

  // Salva frase não respondida sempre que mudar
  useEffect(() => {
    if (currentPhrase && !showAnswer && !userAnswer.trim() && !contexts.includes('words')) {
      storage.saveCurrentPhrase(currentPhrase, userAnswer);
    } else if (showAnswer || userAnswer.trim()) {
      // Limpa se foi respondida
      storage.clearCurrentPhrase();
    }
  }, [currentPhrase, showAnswer, userAnswer, contexts]);

  const loadAvailableVideos = async () => {
    try {
      const response = await videoApi.listVideos();
      setAvailableVideos(response.videos || []);
    } catch (error) {
      console.error('Erro ao carregar vídeos:', error);
    }
  };

  const loadAvailableAgents = async () => {
    try {
      // Busca chaves de API do localStorage para enviar ao backend
      const apiKeys: { gemini?: string; openrouter?: string; groq?: string; together?: string } = {};
      
      const geminiKey = storage.getGeminiApiKey();
      if (geminiKey) {
        apiKeys.gemini = geminiKey;
        console.log('Chave Gemini encontrada');
      }
      
      const openrouterKey = localStorage.getItem('openrouter_api_key');
      if (openrouterKey) {
        apiKeys.openrouter = openrouterKey;
        console.log('Chave OpenRouter encontrada');
      }
      
      const groqKey = localStorage.getItem('groq_api_key');
      if (groqKey) {
        apiKeys.groq = groqKey;
        console.log('Chave Groq encontrada');
      }
      
      const togetherKey = localStorage.getItem('together_api_key');
      if (togetherKey) {
        apiKeys.together = togetherKey;
        console.log('Chave Together encontrada');
      }
      
      console.log('Enviando chaves para backend:', Object.keys(apiKeys));
      const response = await videoApi.getAvailableAgents(apiKeys);
      console.log('Resposta completa do backend:', response);
      console.log('Agentes recebidos do backend:', response.agents);
      console.log('Número de agentes:', response.agents?.length || 0);
      
      if (response.agents && response.agents.length > 0) {
        setAvailableAgents(response.agents);
      } else {
        console.warn('Nenhum agente retornado do backend');
        setAvailableAgents([]);
      }
    } catch (error) {
      console.error('Erro ao carregar agentes disponíveis:', error);
      setAvailableAgents([]);
    }
  };

  const handleSelectAllVideos = (checked: boolean) => {
    if (checked) {
      setSelectedVideos(availableVideos.map(v => v.video_id));
    } else {
      setSelectedVideos([]);
    }
  };

  const loadNextPhrase = async () => {
    // Validação: precisa ter pelo menos uma modalidade e um contexto
    if (modalities.length === 0) {
      alert('Selecione pelo menos uma modalidade (Traduzir ou Completar Frases)');
      return;
    }
    
    if (contexts.length === 0) {
      alert('Selecione pelo menos um contexto');
      return;
    }

    setLoading(true);
    setShowAnswer(false);
    setUserAnswer('');
    setIsCorrect(null);
    // Limpa frase salva ao carregar nova
    storage.clearCurrentPhrase();

    try {
      // Seleciona contexto aleatório dos selecionados
      const selectedContext = contexts.length > 0 
        ? contexts[Math.floor(Math.random() * contexts.length)]
        : 'music-context';

      let phrase: PracticePhrase;

      if (selectedContext === 'music-context') {
        // Contexto: Frases das músicas
        phrase = await videoApi.getMusicPhrase({
          direction,
          difficulty,
          video_ids: selectedVideos.length > 0 ? selectedVideos : undefined,
        });
      } else if (selectedContext === 'new-context') {
        // Contexto: Frases novas com palavras das músicas
        // Busca chaves de API do localStorage para enviar ao backend
        const apiKeys: { openrouter?: string; groq?: string; together?: string } = {};
        
        const openrouterKey = localStorage.getItem('openrouter_api_key');
        if (openrouterKey) apiKeys.openrouter = openrouterKey;
        
        const groqKey = localStorage.getItem('groq_api_key');
        if (groqKey) apiKeys.groq = groqKey;
        
        const togetherKey = localStorage.getItem('together_api_key');
        if (togetherKey) apiKeys.together = togetherKey;
        
        phrase = await videoApi.generatePracticePhrase({
          direction,
          difficulty,
          video_ids: selectedVideos.length > 0 ? selectedVideos : undefined,
          api_keys: Object.keys(apiKeys).length > 0 ? apiKeys : undefined,
          custom_prompt: customPrompt || undefined,
          preferred_agent: selectedAgent || undefined,
        });
      } else {
        // Contexto: Palavras (não deve chegar aqui, mas mantido para segurança)
        throw new Error('Contexto de palavras deve usar loadNextWord');
      }

      setCurrentPhrase(phrase);
      // Salva frase não respondida
      storage.saveCurrentPhrase(phrase, '');
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Erro ao carregar frase. Verifique se há vídeos traduzidos.');
    } finally {
      setLoading(false);
    }
  };

  const loadNextWord = async () => {
    // Validação: precisa ter pelo menos uma modalidade
    if (modalities.length === 0) {
      alert('Selecione pelo menos uma modalidade (Traduzir ou Completar Frases)');
      return;
    }

    setLoading(true);
    setShowAnswer(false);
    setUserAnswer('');
    setIsCorrect(null);
    
    try {
      const wordData = await videoApi.getWordForPractice({
        direction,
        difficulty,
        video_ids: selectedVideos.length > 0 ? selectedVideos : undefined,
        limit: 1
      });
      
      // Converte para formato PracticePhrase
      const wordPhrase: PracticePhrase = {
        id: wordData.id,
        original: direction === 'en-to-pt' ? wordData.word : (wordData.translation || ''),
        translated: direction === 'en-to-pt' ? (wordData.translation || '') : wordData.word,
        source_language: wordData.source_language,
        target_language: wordData.target_language
      };
      
      setCurrentWord(wordPhrase);
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Erro ao carregar palavra. Traduza algumas músicas primeiro ou adicione palavras usando o botão "Adicionar Palavras".');
    } finally {
      setLoading(false);
    }
  };

  const checkWordTranslation = async () => {
    if (!currentWord || !userAnswer.trim()) {
      return;
    }

    try {
      // Determina a palavra original e a tradução esperada
      const sourceWord = direction === 'en-to-pt' ? currentWord.original : currentWord.translated;
      const expectedTranslation = direction === 'en-to-pt' ? currentWord.translated : currentWord.original;
      
      // Se não tem tradução salva, passa a palavra original para o backend traduzir
      const checkParams: any = {
        phrase_id: currentWord.id,
        user_answer: userAnswer.trim(),
        direction,
      };
      
      // Se temos uma tradução esperada, passa ela
      if (expectedTranslation) {
        checkParams.correct_answer = expectedTranslation;
      } else {
        // Se não tem tradução, passa a palavra original para o backend tentar traduzir
        checkParams.word = sourceWord;
      }
      
      const result = await videoApi.checkPracticeAnswer(checkParams);
      setIsCorrect(result.is_correct);
      setShowAnswer(true);
      updateStats(result.is_correct);
      
      // Salva tradução correta sempre (para usar depois)
      if (result.correct_answer && sourceWord) {
        setWordTranslations(prev => ({
          ...prev,
          [sourceWord]: result.correct_answer
        }));
      }
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Erro ao verificar tradução';
      console.error('Erro ao verificar tradução:', error);
      alert(errorMessage);
    }
  };

  const loadWordsList = async () => {
    setLoadingWords(true);
    try {
      const result = await videoApi.listWords(wordsFilterLanguage || undefined);
      setWordsList(result.words);
    } catch (error: any) {
      console.error('Erro ao carregar palavras:', error);
    } finally {
      setLoadingWords(false);
    }
  };

  useEffect(() => {
    if (showAddWordsModal) {
      loadWordsList();
    }
  }, [showAddWordsModal, wordsFilterLanguage]);

  const handleAddWords = async (wordsText: string) => {
    const words = wordsText
      .split(/[,\n\r]+/)
      .map(w => w.trim())
      .filter(w => w.length > 0);
    
    if (words.length === 0) {
      alert('Digite pelo menos uma palavra!');
      return;
    }
    
    try {
      // Determina idioma baseado na direção atual
      const language = direction === 'en-to-pt' ? 'en' : 'pt';
      
      const result = await videoApi.addWords({
        words,
        language
      });
      
      alert(`Palavras adicionadas com sucesso!\n\nAdicionadas: ${result.added}\nJá existiam: ${result.skipped}\nTotal processadas: ${result.total}`);
      
      setWordsInput('');
      await loadWordsList();
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Erro ao adicionar palavras';
      console.error('Erro ao adicionar palavras:', error);
      alert(errorMessage);
    }
  };

  const handleDeleteWord = async (wordId: string) => {
    if (!window.confirm('Deseja realmente deletar esta palavra?')) {
      return;
    }

    try {
      await videoApi.deleteWord(wordId);
      await loadWordsList();
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Erro ao deletar palavra';
      console.error('Erro ao deletar palavra:', error);
      alert(errorMessage);
    }
  };

  const checkAnswer = async () => {
    if (!currentPhrase || !userAnswer.trim()) {
      return;
    }

    // Validação adicional
    if (!currentPhrase.id) {
      alert('Erro: ID da frase não encontrado. Recarregue a frase.');
      return;
    }

    try {
      // Para frases geradas, precisa enviar a resposta correta também
      const checkParams: any = {
        phrase_id: currentPhrase.id,
        user_answer: userAnswer.trim(),
        direction,
      };
      
      // Se for frase gerada, adiciona resposta correta
      if (currentPhrase.id && currentPhrase.id.startsWith('generated-')) {
        const correctAnswer = direction === 'en-to-pt' 
          ? currentPhrase.translated 
          : currentPhrase.original;
        
        if (!correctAnswer) {
          alert('Erro: Resposta correta não encontrada. Recarregue a frase.');
          return;
        }
        
        checkParams.correct_answer = correctAnswer;
      }
      
      const result = await videoApi.checkPracticeAnswer(checkParams);

      setIsCorrect(result.is_correct);
      setShowAnswer(true);
      updateStats(result.is_correct);
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Erro ao verificar resposta';
      console.error('Erro ao verificar resposta:', error);
      alert(errorMessage);
    }
  };

  const updateStats = (correct: boolean) => {
    setStats((prev) => {
      const newStats = {
        total: prev.total + 1,
        correct: correct ? prev.correct + 1 : prev.correct,
        incorrect: correct ? prev.incorrect : prev.incorrect + 1,
        streak: correct ? prev.streak + 1 : 0,
        skipped: prev.skipped || 0,
      };
      // Salva no localStorage sempre que atualizar
      storage.setPracticeStats(newStats);
      // Limpa frase salva quando responde
      if (currentPhrase) {
        storage.clearCurrentPhrase();
      }
      return newStats;
    });
  };

  const skipPhrase = () => {
    setStats((prev) => {
      const newStats = {
        total: prev.total,
        correct: prev.correct,
        incorrect: prev.incorrect,
        streak: 0, // Reseta sequência ao pular
        skipped: (prev.skipped || 0) + 1,
      };
      // Salva no localStorage
      storage.setPracticeStats(newStats);
      return newStats;
    });
    
    // Limpa frase atual e carrega próxima
    setShowAnswer(false);
    setUserAnswer('');
    setIsCorrect(null);
    storage.clearCurrentPhrase();
    
    if (contexts.includes('words')) {
      loadNextWord();
    } else {
      loadNextPhrase();
    }
  };

  const saveSession = () => {
    if (stats.total === 0) {
      alert('Não há estatísticas para salvar. Pratique primeiro!');
      return;
    }

    const session = {
      ...stats,
      skipped: stats.skipped || 0,
      timestamp: new Date().toISOString(),
    };

    storage.savePracticeSession(session);
    alert(`Sessão salva com sucesso!\n\nTotal: ${stats.total}\nAcertos: ${stats.correct}\nErros: ${stats.incorrect}\nPuladas: ${stats.skipped || 0}\nSequência: ${stats.streak}`);
  };

  const resetStats = () => {
    const resetStats = {
      total: 0,
      correct: 0,
      incorrect: 0,
      streak: 0,
      skipped: 0,
    };
    setStats(resetStats);
    // Limpa do localStorage também
    storage.clearPracticeStats();
  };

  const startNewSession = () => {
    if (window.confirm('Deseja iniciar uma nova sessão? Isso irá resetar as estatísticas e limpar o progresso atual.')) {
      resetStats();
      setCurrentPhrase(null);
      setUserAnswer('');
      setShowAnswer(false);
      setIsCorrect(null);
      setCurrentWordIndex(0);
      storage.clearCurrentPhrase();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !showAnswer) {
      checkAnswer();
    } else if (e.key === 'Enter' && showAnswer) {
      loadNextPhrase();
    }
  };

  const getModelDisplayName = (model: string, service?: string): string => {
    if (!model) return 'Desconhecido';
    
    // Nomes amigáveis para os modelos
    const modelNames: { [key: string]: string } = {
      'gemini-1.5-flash': 'Gemini 1.5 Flash',
      'gemini-1.5-pro': 'Gemini 1.5 Pro',
      'gemini-2.0-flash': 'Gemini 2.0 Flash',
      'gemini-2.5-flash': 'Gemini 2.5 Flash',
      'gemini-2.5-pro': 'Gemini 2.5 Pro',
      'openai/gpt-3.5-turbo': 'GPT-3.5 Turbo (OpenRouter)',
      'llama-3.1-8b-instant': 'Llama 3.1 8B (Groq)',
      'meta-llama/Llama-3-8b-chat-hf': 'Llama 3 8B (Together AI)',
    };
    
    // Se tiver nome amigável, usa ele
    if (modelNames[model]) {
      return modelNames[model];
    }
    
    // Caso contrário, formata o nome
    if (service) {
      const serviceNames: { [key: string]: string } = {
        'gemini': 'Gemini',
        'openrouter': 'OpenRouter',
        'groq': 'Groq',
        'together': 'Together AI'
      };
      return `${model} (${serviceNames[service] || service})`;
    }
    
    return model;
  };

  return (
    <div className="knowledge-practice">
      <div className="practice-header">
        <h2>📚 Treinar Inglês com Músicas</h2>
        <p>Use as letras das músicas traduzidas para praticar inglês</p>
      </div>

      <div className="practice-config">
        <div className="config-section">
          <label>Modalidade:</label>
          <div className="checkbox-group">
            <label>
              <input
                type="checkbox"
                value="translate"
                checked={modalities.includes('translate')}
                onChange={(e) => {
                  if (e.target.checked) {
                    setModalities([...modalities, 'translate']);
                  } else {
                    setModalities(modalities.filter(m => m !== 'translate'));
                  }
                }}
              />
              <span>Traduzir</span>
            </label>
            <label>
              <input
                type="checkbox"
                value="complete"
                checked={modalities.includes('complete')}
                onChange={(e) => {
                  if (e.target.checked) {
                    setModalities([...modalities, 'complete']);
                  } else {
                    setModalities(modalities.filter(m => m !== 'complete'));
                  }
                }}
              />
              <span>Completar Frases</span>
            </label>
          </div>
          {modalities.length === 0 && (
            <p style={{ color: '#ef4444', fontSize: '0.875rem', marginTop: '8px' }}>
              Selecione pelo menos uma modalidade
            </p>
          )}
        </div>

        <div className="config-section">
          <label>Contexto:</label>
          <div className="checkbox-group">
            <label>
              <input
                type="checkbox"
                value="music-context"
                checked={contexts.includes('music-context')}
                onChange={(e) => {
                  if (e.target.checked) {
                    setContexts([...contexts, 'music-context']);
                  } else {
                    setContexts(contexts.filter(c => c !== 'music-context'));
                  }
                }}
              />
              <span>Frases das Músicas</span>
            </label>
            <label>
              <input
                type="checkbox"
                value="new-context"
                checked={contexts.includes('new-context')}
                onChange={(e) => {
                  if (e.target.checked) {
                    setContexts([...contexts, 'new-context']);
                  } else {
                    setContexts(contexts.filter(c => c !== 'new-context'));
                  }
                }}
              />
              <span>Palavras em Novos Contextos</span>
            </label>
            <label>
              <input
                type="checkbox"
                value="words"
                checked={contexts.includes('words')}
                onChange={(e) => {
                  if (e.target.checked) {
                    setContexts([...contexts, 'words']);
                  } else {
                    setContexts(contexts.filter(c => c !== 'words'));
                  }
                }}
              />
              <span>Palavras</span>
            </label>
          </div>
          {contexts.length === 0 && (
            <p style={{ color: '#ef4444', fontSize: '0.875rem', marginTop: '8px' }}>
              Selecione pelo menos um contexto
            </p>
          )}
        </div>

        <div className="config-section">
          <button 
            onClick={() => setShowAddWordsModal(true)} 
            className="add-words-btn"
            style={{ width: 'auto', marginTop: '8px' }}
          >
            ➕ Adicionar Palavras
          </button>
        </div>

        <div className="config-section">
          <label>Direção da Tradução:</label>
          <div className="radio-group">
            <label>
              <input
                type="radio"
                value="en-to-pt"
                checked={direction === 'en-to-pt'}
                onChange={(e) => setDirection(e.target.value as TranslationDirection)}
              />
              <span>Inglês → Português</span>
            </label>
            <label>
              <input
                type="radio"
                value="pt-to-en"
                checked={direction === 'pt-to-en'}
                onChange={(e) => setDirection(e.target.value as TranslationDirection)}
              />
              <span>Português → Inglês</span>
            </label>
          </div>
        </div>

        <div className="config-section">
          <label>Dificuldade:</label>
          <select
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value as Difficulty)}
          >
            <option value="easy">Fácil</option>
            <option value="medium">Médio</option>
            <option value="hard">Difícil</option>
          </select>
        </div>

        <div className="config-section">
          <div className="config-section-header">
            <label>Vídeos (opcional - deixe vazio para usar todos):</label>
            {contexts.includes('new-context') && (
              <button 
                onClick={() => {
                  setShowConfigModal(true);
                  loadAvailableAgents();
                }} 
                className="config-btn"
                title="Configurar prompt e agente"
              >
                ⚙️ Configurações
              </button>
            )}
          </div>
          <div className="video-selector">
            {availableVideos.length > 0 && (
              <label className="video-checkbox select-all">
                <input
                  type="checkbox"
                  checked={selectedVideos.length === availableVideos.length && availableVideos.length > 0}
                  onChange={(e) => handleSelectAllVideos(e.target.checked)}
                />
                <span><strong>Selecionar todos</strong></span>
              </label>
            )}
            {availableVideos.map((video) => (
              <label key={video.video_id} className="video-checkbox">
                <input
                  type="checkbox"
                  checked={selectedVideos.includes(video.video_id)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedVideos([...selectedVideos, video.video_id]);
                    } else {
                      setSelectedVideos(selectedVideos.filter((id) => id !== video.video_id));
                    }
                  }}
                />
                <span>{video.title}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      <div className="practice-stats">
        <div className="stat-item">
          <span className="stat-label">Total:</span>
          <span className="stat-value">{stats.total}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Acertos:</span>
          <span className="stat-value correct">{stats.correct}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Erros:</span>
          <span className="stat-value incorrect">{stats.incorrect}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Sequência:</span>
          <span className="stat-value streak">{stats.streak}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Puladas:</span>
          <span className="stat-value skipped">{stats.skipped || 0}</span>
        </div>
        <button onClick={startNewSession} className="new-session-btn" title="Iniciar nova sessão">
          🆕 Iniciar Nova Sessão
        </button>
        <button onClick={resetStats} className="reset-stats-btn">
          Resetar
        </button>
        <button onClick={saveSession} className="save-session-btn" title="Salvar sessão atual">
          💾 Salvar Sessão
        </button>
      </div>

      <div className="practice-exercise">
        {contexts.includes('words') && currentWord && !loading && (
          <div className="exercise-content">
            <div className="phrase-display">
              <div className="phrase-label">
                {direction === 'en-to-pt' ? 'Traduza a palavra do Inglês:' : 'Traduza a palavra do Português:'}
              </div>
              <div className="phrase-text word-text">
                {direction === 'en-to-pt' ? currentWord.original : currentWord.translated}
              </div>
            </div>

            <div className="answer-section">
              <label>Sua tradução:</label>
              <input
                type="text"
                value={userAnswer}
                onChange={(e) => setUserAnswer(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && !showAnswer) {
                    checkWordTranslation();
                  } else if (e.key === 'Enter' && showAnswer) {
                    loadNextWord();
                  }
                }}
                placeholder="Digite a tradução aqui..."
                disabled={showAnswer}
                className="word-answer-input"
              />

              {!showAnswer && (
                <div className="action-buttons">
                  <button 
                    onClick={checkWordTranslation} 
                    className="check-btn" 
                    disabled={!userAnswer.trim()}
                  >
                    Verificar
                  </button>
                  <button onClick={skipPhrase} className="skip-btn" title="Pular esta palavra">
                    ⏭️ Pular
                  </button>
                </div>
              )}

              {showAnswer && (
                <div className={`answer-feedback ${isCorrect ? 'correct' : 'incorrect'}`}>
                  <div className="feedback-header">
                    {isCorrect ? '✅ Correto!' : '❌ Incorreto'}
                  </div>
                  <div className="correct-answer">
                    <strong>Tradução correta:</strong>
                    <div className="answer-text">
                      {direction === 'en-to-pt' ? currentWord.translated : currentWord.original}
                    </div>
                  </div>
                  <button onClick={loadNextWord} className="next-btn">
                    Próxima Palavra
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {contexts.includes('words') && !currentWord && !loading && (
          <div className="exercise-placeholder">
            <p>Clique em "Iniciar" para começar a praticar com palavras do banco de dados!</p>
            <button onClick={loadNextWord} className="start-btn">
              Iniciar
            </button>
          </div>
        )}

        {contexts.includes('words') && loading && (
          <div className="exercise-loading">
            <p>Carregando palavra...</p>
          </div>
        )}

        {!currentPhrase && !loading && !contexts.includes('words') && (
          <div className="exercise-placeholder">
            <p>Clique em "Iniciar" para começar a praticar!</p>
            <button onClick={loadNextPhrase} className="start-btn" disabled={modalities.length === 0 || contexts.length === 0}>
              Iniciar
            </button>
          </div>
        )}

        {loading && !contexts.includes('words') && (
          <div className="exercise-loading">
            <p>Carregando frase...</p>
          </div>
        )}

        {currentPhrase && !loading && !contexts.includes('words') && (
          <div className="exercise-content">
            <div className="phrase-display">
              <div className="phrase-label">
                {direction === 'en-to-pt' ? 'Traduza do Inglês:' : 'Traduza do Português:'}
              </div>
              <div className="phrase-text">
                {direction === 'en-to-pt' ? currentPhrase.original : currentPhrase.translated}
              </div>
              {currentPhrase.video_title && (
                <div className="phrase-source">Música: {currentPhrase.video_title}</div>
              )}
              {currentPhrase.model_used && (
                <div className="phrase-model">
                  <span className="model-label">Modelo usado:</span>
                  <span className="model-name">{getModelDisplayName(currentPhrase.model_used, currentPhrase.service_used)}</span>
                </div>
              )}
            </div>

            <div className="answer-section">
              <label>Sua resposta:</label>
              <textarea
                value={userAnswer}
                onChange={(e) => setUserAnswer(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Digite sua tradução aqui..."
                disabled={showAnswer}
                className="answer-input"
              />

              {!showAnswer && (
                <div className="action-buttons">
                  <button onClick={checkAnswer} className="check-btn" disabled={!userAnswer.trim()}>
                    Verificar
                  </button>
                  <button onClick={skipPhrase} className="skip-btn" title="Pular esta frase">
                    ⏭️ Pular
                  </button>
                </div>
              )}

              {showAnswer && (
                <div className={`answer-feedback ${isCorrect ? 'correct' : 'incorrect'}`}>
                  <div className="feedback-header">
                    {isCorrect ? '✅ Correto!' : '❌ Incorreto'}
                  </div>
                  <div className="correct-answer">
                    <strong>Resposta correta:</strong>
                    <div className="answer-text">
                      {direction === 'en-to-pt' ? currentPhrase.translated : currentPhrase.original}
                    </div>
                  </div>
                  {!isCorrect && (
                    <div className="user-answer">
                      <strong>Sua resposta:</strong>
                      <div className="answer-text">{userAnswer}</div>
                    </div>
                  )}
                  <button onClick={loadNextPhrase} className="next-btn">
                    Próxima Frase
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Modal de Configuração */}
      {showConfigModal && (
        <div className="modal-overlay" onClick={() => setShowConfigModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>⚙️ Configurações de Geração</h3>
              <button className="modal-close" onClick={() => setShowConfigModal(false)}>×</button>
            </div>
            
            <div className="modal-body">
              <div className="config-field">
                <label>Prompt Customizado:</label>
                <textarea
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="Digite o prompt customizado aqui..."
                  className="prompt-textarea"
                  rows={12}
                />
                <div className="prompt-help">
                  <strong>Placeholders disponíveis:</strong>
                  <ul>
                    <li><code>{'{words}'}</code> - Palavras selecionadas</li>
                    <li><code>{'{source_lang}'}</code> - Idioma de origem</li>
                    <li><code>{'{target_lang}'}</code> - Idioma de destino</li>
                    <li><code>{'{difficulty}'}</code> - Nível de dificuldade</li>
                    <li><code>{'{difficulty_desc}'}</code> - Descrição da dificuldade</li>
                  </ul>
                </div>
              </div>

              <div className="config-field">
                <label>Agente Preferido (opcional):</label>
                <select
                  value={selectedAgent ? `${selectedAgent.service}:${selectedAgent.model}` : ''}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value) {
                      const [service, model] = value.split(':');
                      setSelectedAgent({ service, model });
                    } else {
                      setSelectedAgent(null);
                    }
                  }}
                  className="agent-select"
                >
                  <option value="">Usar agente automático (fallback)</option>
                  {availableAgents && availableAgents.length > 0 ? (
                    availableAgents
                      .filter(a => a.available !== false)
                      .map((agent) => (
                        <option key={`${agent.service}:${agent.model}`} value={`${agent.service}:${agent.model}`}>
                          {agent.display_name}
                        </option>
                      ))
                  ) : (
                    <option value="" disabled>Carregando agentes...</option>
                  )}
                </select>
                {(!availableAgents || availableAgents.length === 0) && (
                  <p className="no-agents">Nenhum agente disponível. Configure chaves de API na aba "Chaves API" e verifique as cotas.</p>
                )}
                {availableAgents && availableAgents.length > 0 && (
                  <p className="agents-info" style={{ marginTop: '8px', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                    {availableAgents.length} agente(s) disponível(is)
                  </p>
                )}
              </div>
            </div>

            <div className="modal-footer">
              <button onClick={() => setShowConfigModal(false)} className="modal-btn-primary">
                Salvar
              </button>
              <button 
                onClick={() => {
                  const defaultPrompt = `Você é um professor de idiomas. Crie uma frase natural e completa em {source_lang} usando TODAS as seguintes palavras: {words}

INSTRUÇÕES IMPORTANTES:
1. A frase deve ser natural, completa e fazer sentido gramaticalmente
2. Use TODAS as palavras fornecidas na frase
3. A frase deve ser adequada para nível {difficulty} de dificuldade ({difficulty_desc})
4. A frase deve ser uma sentença completa e coerente
5. NÃO adicione explicações, comentários ou prefixos como "Frase:" ou "A frase é:"
6. Retorne APENAS a frase criada, sem aspas, sem citações, sem nada além da frase

Exemplo de formato correto:
Se as palavras forem: ["love", "heart", "beautiful"]
Você deve retornar apenas: "I love your beautiful heart"

Agora crie a frase usando as palavras: {words}`;
                  setCustomPrompt(defaultPrompt);
                  setSelectedAgent(null);
                }} 
                className="modal-btn-secondary"
              >
                Restaurar Padrão
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Gerenciar Palavras */}
      {showAddWordsModal && (
        <div className="modal-overlay" onClick={() => setShowAddWordsModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '800px' }}>
            <div className="modal-header">
              <h3>📚 Gerenciar Palavras</h3>
              <button className="modal-close" onClick={() => setShowAddWordsModal(false)}>×</button>
            </div>
            
            <div className="modal-body">
              <div className="config-field">
                <label>Adicionar Novas Palavras:</label>
                <textarea
                  value={wordsInput}
                  onChange={(e) => setWordsInput(e.target.value)}
                  placeholder="Digite as palavras aqui, separadas por vírgula ou uma por linha...&#10;Exemplo: love, heart, beautiful&#10;ou&#10;love&#10;heart&#10;beautiful"
                  className="words-input"
                  rows={4}
                />
                <div className="prompt-help" style={{ marginTop: '8px' }}>
                  <strong>Dica:</strong> As palavras serão adicionadas no idioma atual da direção de tradução ({direction === 'en-to-pt' ? 'Inglês' : 'Português'})
                </div>
                <button 
                  onClick={() => handleAddWords(wordsInput)} 
                  className="modal-btn-primary"
                  disabled={!wordsInput.trim()}
                  style={{ marginTop: '12px', width: 'auto' }}
                >
                  ➕ Adicionar Palavras
                </button>
              </div>

              <div className="config-field" style={{ marginTop: '32px', borderTop: '1px solid var(--border-color)', paddingTop: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <label style={{ margin: 0 }}>Palavras Adicionadas ({wordsList.length}):</label>
                  <select
                    value={wordsFilterLanguage}
                    onChange={(e) => setWordsFilterLanguage(e.target.value)}
                    style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid var(--border-color)' }}
                  >
                    <option value="">Todos os idiomas</option>
                    <option value="en">Inglês</option>
                    <option value="pt">Português</option>
                  </select>
                </div>
                
                {loadingWords ? (
                  <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>
                    Carregando palavras...
                  </div>
                ) : wordsList.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-secondary)' }}>
                    Nenhuma palavra adicionada ainda. Adicione palavras acima para começar.
                  </div>
                ) : (
                  <div style={{ maxHeight: '300px', overflowY: 'auto', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '12px' }}>
                    {wordsList.map((word) => (
                      <div key={word.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px', borderBottom: '1px solid var(--border-color)', marginBottom: '4px' }}>
                        <div>
                          <strong>{word.word}</strong>
                          <span style={{ marginLeft: '8px', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                            ({word.language === 'en' ? 'Inglês' : 'Português'})
                          </span>
                          {word.translation && (
                            <span style={{ marginLeft: '8px', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                              → {word.translation}
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => handleDeleteWord(word.id)}
                          style={{
                            padding: '4px 8px',
                            background: '#ef4444',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '0.875rem'
                          }}
                          title="Deletar palavra"
                        >
                          🗑️
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="prompt-help" style={{ marginTop: '16px', padding: '12px', background: 'var(--bg-secondary)', borderRadius: '6px' }}>
                <strong>ℹ️ Informações:</strong>
                <ul style={{ marginTop: '8px', marginBottom: 0 }}>
                  <li>As palavras adicionadas manualmente complementam as palavras das músicas traduzidas</li>
                  <li>A modalidade "Palavras" busca palavras tanto das músicas quanto do banco de dados</li>
                  <li>Você pode filtrar palavras por idioma usando o seletor acima</li>
                </ul>
              </div>
            </div>

            <div className="modal-footer">
              <button 
                onClick={() => {
                  setShowAddWordsModal(false);
                  setWordsInput('');
                  setWordsFilterLanguage('');
                }} 
                className="modal-btn-secondary"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
