import { useEffect, useState } from 'react';
import { videoApi } from '../../services/api';
import { useVideoTranslation } from '../../hooks/useVideoTranslation';
import './VideoList.css';

interface VideoItem {
  video_id: string;
  youtube_id: string;
  title: string;
  source_language: string;
  target_language: string;
  translation_id: string;
  created_at: string | null;
}

interface VideoListProps {
  onVideoSelect: (videoId: string, youtubeId: string, sourceLang: string, targetLang: string) => void;
}

export const VideoList = ({ onVideoSelect }: VideoListProps) => {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const { loadSubtitles } = useVideoTranslation();

  useEffect(() => {
    loadVideos();
  }, []);

  const loadVideos = async () => {
    try {
      setLoading(true);
      const response = await videoApi.listVideos();
      setVideos(response.videos || []);
    } catch (error) {
      console.error('Erro ao carregar vídeos:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleVideoClick = async (video: VideoItem) => {
    try {
      // Carrega as legendas primeiro
      await loadSubtitles(video.video_id, video.source_language, video.target_language);
      // Depois chama o callback para atualizar o estado no App
      onVideoSelect(video.video_id, video.youtube_id, video.source_language, video.target_language);
    } catch (error) {
      console.error('Erro ao carregar vídeo:', error);
      alert('Erro ao carregar vídeo. Tente novamente.');
    }
  };

  const handleDeleteVideo = async (e: React.MouseEvent, video: VideoItem) => {
    // Previne que o clique no botão dispare o clique no card
    e.stopPropagation();
    
    // Confirmação antes de deletar
    const confirmMessage = `Tem certeza que deseja deletar este vídeo?\n\n` +
      `Vídeo: ${video.title}\n` +
      `Idioma: ${getLanguageName(video.source_language)} → ${getLanguageName(video.target_language)}\n\n` +
      `Esta ação não pode ser desfeita e removerá todas as traduções relacionadas.`;
    
    if (!window.confirm(confirmMessage)) {
      return;
    }
    
    try {
      await videoApi.deleteVideo(video.video_id);
      alert('Vídeo deletado com sucesso!');
      // Recarrega a lista de vídeos
      loadVideos();
    } catch (error: any) {
      console.error('Erro ao deletar vídeo:', error);
      alert(error.response?.data?.detail || 'Erro ao deletar vídeo. Tente novamente.');
    }
  };

  const handleDeleteAllVideos = async () => {
    if (videos.length === 0) {
      alert('Não há vídeos para deletar.');
      return;
    }

    const confirmMessage = `⚠️ ATENÇÃO: Esta ação irá deletar TODOS os ${videos.length} vídeo(s) e todas as traduções relacionadas!\n\n` +
      `Esta ação NÃO pode ser desfeita.\n\n` +
      `Tem certeza que deseja continuar?`;
    
    if (!window.confirm(confirmMessage)) {
      return;
    }

    // Confirmação dupla para ação destrutiva
    const secondConfirm = window.confirm(
      `⚠️ CONFIRMAÇÃO FINAL ⚠️\n\n` +
      `Você realmente deseja deletar TODOS os ${videos.length} vídeo(s)?\n\n` +
      `Esta ação é IRREVERSÍVEL e removerá:\n` +
      `- Todos os vídeos\n` +
      `- Todas as traduções\n` +
      `- Todas as chaves API relacionadas\n` +
      `- Todos os jobs relacionados\n\n` +
      `Clique em "OK" para confirmar ou "Cancelar" para abortar.`
    );

    if (!secondConfirm) {
      return;
    }

    try {
      const response = await videoApi.deleteAllVideos();
      if (response && response.message) {
        alert(response.message);
      } else {
        alert(`Todos os vídeos deletados com sucesso! ${response.deleted_videos || 0} vídeo(s) e ${response.deleted_translations || 0} tradução(ões) removida(s).`);
      }
      // Recarrega a lista de vídeos (que agora estará vazia)
      loadVideos();
    } catch (error: any) {
      console.error('Erro ao deletar todos os vídeos:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Erro ao deletar todos os vídeos. Tente novamente.';
      alert(errorMessage);
    }
  };

  const getLanguageName = (code: string) => {
    const languages: Record<string, string> = {
      'en': 'Inglês',
      'pt': 'Português',
      'es': 'Espanhol',
      'fr': 'Francês',
      'de': 'Alemão',
    };
    return languages[code] || code;
  };

  if (loading) {
    return <div className="video-list-loading">Carregando vídeos...</div>;
  }

  if (videos.length === 0) {
    return (
      <div className="video-list-empty">
        <p>Nenhum vídeo traduzido ainda.</p>
        <p className="hint">Traduza seu primeiro vídeo na aba "Traduzir"!</p>
      </div>
    );
  }

  return (
    <div className="video-list">
      <div className="video-list-header">
        <h3>Vídeos Traduzidos ({videos.length})</h3>
        <div className="header-actions">
          <button onClick={loadVideos} className="refresh-btn">🔄 Atualizar</button>
          <button 
            onClick={handleDeleteAllVideos} 
            className="delete-all-btn"
            title="Deletar todos os vídeos"
          >
            🗑️ Limpar Todos
          </button>
        </div>
      </div>
      <div className="video-list-grid">
        {videos.map((video) => (
          <div
            key={`${video.video_id}-${video.translation_id}`}
            className="video-item"
            onClick={() => handleVideoClick(video)}
          >
            <div className="video-item-thumbnail">
              <img
                src={`https://img.youtube.com/vi/${video.youtube_id}/mqdefault.jpg`}
                alt={video.title}
                onError={(e) => {
                  (e.target as HTMLImageElement).src = 'https://via.placeholder.com/320x180?text=Video';
                }}
              />
              <button
                className="video-item-delete-btn"
                onClick={(e) => handleDeleteVideo(e, video)}
                title="Deletar vídeo"
              >
                🗑️
              </button>
            </div>
            <div className="video-item-info">
              <h4 className="video-item-title">{video.title}</h4>
              <div className="video-item-meta">
                <span className="video-item-lang">
                  {getLanguageName(video.source_language)} → {getLanguageName(video.target_language)}
                </span>
                {video.created_at && (
                  <span className="video-item-date">
                    {new Date(video.created_at).toLocaleDateString('pt-BR')}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
