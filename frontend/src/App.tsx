import { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar/Sidebar';
import { URLInput } from './components/URLInput/URLInput';
import { LanguageSelector } from './components/LanguageSelector/LanguageSelector';
import { JobStatus } from './components/JobStatus/JobStatus';
import { VideoPlayer } from './components/VideoPlayer/VideoPlayer';
import { VideoList } from './components/VideoList/VideoList';
import { ApiKeyManager } from './components/ApiKeyManager/ApiKeyManager';
import { ApiUsage } from './components/ApiUsage/ApiUsage';
import { KnowledgePractice } from './components/KnowledgePractice/KnowledgePractice';
import { useJobPolling } from './hooks/useJobPolling';
import { useVideoTranslation } from './hooks/useVideoTranslation';
import { videoApi } from './services/api';
import { storage } from './services/storage';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('translate');
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [videoId, setVideoId] = useState<string | null>(null);
  const [sourceLanguage, setSourceLanguage] = useState(storage.getSourceLanguage());
  const [targetLanguage, setTargetLanguage] = useState(storage.getTargetLanguage());
  const [geminiApiKey, setGeminiApiKey] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);

  const { jobStatus, isPolling } = useJobPolling(jobId, !!jobId);
  const { subtitles, loading: subtitlesLoading, loadSubtitles } = useVideoTranslation();

  useEffect(() => {
    const saved = storage.getGeminiApiKey();
    if (saved) {
      setGeminiApiKey(saved);
    }
  }, []);

  useEffect(() => {
    storage.setSourceLanguage(sourceLanguage);
  }, [sourceLanguage]);

  useEffect(() => {
    storage.setTargetLanguage(targetLanguage);
  }, [targetLanguage]);

  // Quando job completa, carrega legendas
  useEffect(() => {
    if (jobStatus?.status === 'completed' && jobStatus.video_id) {
      loadSubtitles(jobStatus.video_id, sourceLanguage, targetLanguage);
    }
  }, [jobStatus, sourceLanguage, targetLanguage, loadSubtitles]);

  const extractVideoId = (url: string): string | null => {
    const patterns = [
      /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
      /youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})/,
    ];

    for (const pattern of patterns) {
      const match = url.match(pattern);
      if (match) {
        return match[1];
      }
    }
    return null;
  };

  const handleUrlSubmit = async (url: string) => {
    if (!geminiApiKey) {
      alert('Por favor, configure sua chave de API do Gemini primeiro.');
      return;
    }

    setYoutubeUrl(url);
    const extractedId = extractVideoId(url);
    
    if (!extractedId) {
      alert('URL do YouTube inválida.');
      return;
    }

    setVideoId(extractedId);
    setProcessing(true);

    try {
      // Verifica se já existe tradução
      const check = await videoApi.check(url, sourceLanguage, targetLanguage);
      
      if (check.exists && check.video_id) {
        // Pergunta ao usuário se deseja retraduzir
        const shouldRetranslate = window.confirm(
          'Este vídeo já foi traduzido. Deseja retraduzir com as correções aplicadas?\n\n' +
          'Clique em "OK" para retraduzir ou "Cancelar" para usar a tradução existente.'
        );
        
        if (shouldRetranslate) {
          // Retraduz com as correções
          const response = await videoApi.process({
            youtube_url: url,
            source_language: sourceLanguage,
            target_language: targetLanguage,
            gemini_api_key: geminiApiKey,
            force_retranslate: true,
          });
          setJobId(response.job_id);
          return;
        } else {
          // Carrega tradução existente
          await loadSubtitles(check.video_id, sourceLanguage, targetLanguage);
          setProcessing(false);
          return;
        }
      }

      // Inicia novo processamento
      const response = await videoApi.process({
        youtube_url: url,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        gemini_api_key: geminiApiKey,
      });

      setJobId(response.job_id);
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Erro ao processar vídeo';
      alert(errorMessage);
      setProcessing(false);
    }
  };

  const handleVideoSelect = async (selectedVideoId: string, selectedYoutubeId: string, sourceLang: string, targetLang: string) => {
    setVideoId(selectedYoutubeId);
    setYoutubeUrl(`https://www.youtube.com/watch?v=${selectedYoutubeId}`);
    setSourceLanguage(sourceLang);
    setTargetLanguage(targetLang);
    setActiveTab('translate');
    // Carrega as legendas imediatamente
    await loadSubtitles(selectedVideoId, sourceLang, targetLang);
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'translate':
        return (
          <div className="tab-content">
            <div className="tab-header">
              <h2>Traduzir Novo Vídeo</h2>
              <p>Cole a URL do YouTube e traduza as legendas</p>
            </div>

            <LanguageSelector
              sourceLanguage={sourceLanguage}
              targetLanguage={targetLanguage}
              onSourceChange={setSourceLanguage}
              onTargetChange={setTargetLanguage}
            />

            <URLInput onSubmit={handleUrlSubmit} loading={processing} />

            {jobId && <JobStatus jobStatus={jobStatus} isPolling={isPolling} jobId={jobId} />}

            {jobStatus?.status === 'error' && (
              <div className="error-message">
                Erro no processamento. Verifique sua chave de API e tente novamente.
              </div>
            )}

            {subtitlesLoading && (
              <div className="loading-message">Carregando legendas...</div>
            )}

            {subtitles && videoId && !subtitlesLoading && youtubeUrl && (
              <div style={{ marginTop: '24px' }}>
                <VideoPlayer
                  videoId={videoId}
                  segments={subtitles.segments}
                  sourceLanguage={subtitles.source_language}
                  targetLanguage={subtitles.target_language}
                />
              </div>
            )}
          </div>
        );
      
      case 'videos':
        return (
          <div className="tab-content">
            <div className="tab-header">
              <h2>Meus Vídeos Traduzidos</h2>
              <p>Selecione um vídeo para assistir com legendas traduzidas</p>
            </div>
            <VideoList onVideoSelect={handleVideoSelect} />
            {subtitlesLoading && (
              <div className="loading-message" style={{ marginTop: '24px' }}>Carregando vídeo...</div>
            )}
            {subtitles && videoId && !subtitlesLoading && (
              <div style={{ marginTop: '24px' }}>
                <VideoPlayer
                  videoId={videoId}
                  segments={subtitles.segments}
                  sourceLanguage={subtitles.source_language}
                  targetLanguage={subtitles.target_language}
                />
              </div>
            )}
          </div>
        );
      
      case 'practice':
        return (
          <div className="tab-content">
            <KnowledgePractice />
          </div>
        );
      
      case 'api-keys':
        return (
          <div className="tab-content">
            <div className="tab-header">
              <h2>Gerenciar Chaves de API</h2>
              <p>Configure suas chaves de API para diferentes serviços</p>
            </div>
            <ApiKeyManager />
          </div>
        );
      
      case 'usage':
        return (
          <div className="tab-content">
            <div className="tab-header">
              <h2>Uso e Cota da API</h2>
              <p>Monitore seu uso e custos</p>
            </div>
            <ApiUsage />
          </div>
        );
      
      default:
        return null;
    }
  };

  return (
    <div className="app">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="app-main">
        <div className="app-content">
          {renderTabContent()}
        </div>
      </main>
    </div>
  );
}

export default App;
