import { useEffect, useState, useRef } from 'react';
import { TranslationSegment } from '../../services/api';
import './SubtitleOverlay.css';

interface SubtitleOverlayProps {
  segments: TranslationSegment[];
  sourceLanguage: string;
  targetLanguage: string;
  isFullscreen?: boolean;
}

export const SubtitleOverlay = ({
  segments,
  sourceLanguage,
  targetLanguage,
  isFullscreen: externalFullscreen,
}: SubtitleOverlayProps) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Detecta fullscreen customizado (do container, não do YouTube)
    const checkFullscreen = () => {
      // Verifica fullscreen do documento (fullscreen customizado do container)
      const fullscreenEl = document.fullscreenElement || 
                          (document as any).webkitFullscreenElement ||
                          (document as any).mozFullScreenElement ||
                          (document as any).msFullscreenElement;
      
      const detectedFullscreen = !!fullscreenEl;
      
      // Se recebeu prop externa, usa ela como prioridade, mas também considera detecção local
      if (externalFullscreen !== undefined) {
        setIsFullscreen(externalFullscreen || detectedFullscreen);
      } else {
        setIsFullscreen(detectedFullscreen);
      }
    };

    const handleFullscreenChange = () => {
      // Pequeno delay para garantir que o DOM foi atualizado
      setTimeout(checkFullscreen, 100);
    };

    // Verifica periodicamente
    const interval = setInterval(checkFullscreen, 200);
    checkFullscreen(); // Verifica imediatamente

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);

    return () => {
      clearInterval(interval);
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    };
  }, [externalFullscreen]); // Re-executa quando externalFullscreen muda

  if (segments.length === 0) {
    return null;
  }

  // Combina múltiplos segmentos ativos preservando notas musicais (♪) como marcadores
  // As notas musicais são usadas para alinhar a tradução com o original
  const originalText = segments.map((seg) => seg.original).join(' ');
  const translatedText = segments.map((seg) => seg.translated).join(' ');

  // Conteúdo das legendas
  const subtitleContent = (
    <div 
      ref={overlayRef}
      className={`subtitle-overlay ${isFullscreen ? 'subtitle-fullscreen' : ''}`}
      data-fullscreen={isFullscreen ? 'true' : 'false'}
    >
      <div className="subtitle-container">
        <div className="subtitle-line subtitle-original">
          {originalText}
        </div>
        <div className="subtitle-line subtitle-translated">
          {translatedText}
        </div>
      </div>
    </div>
  );

  // Com fullscreen customizado, as legendas são renderizadas normalmente no container
  // O CSS garante que apareçam corretamente em fullscreen
  // Não precisa usar Portal porque o fullscreen é do container, não do YouTube
  return subtitleContent;
};
