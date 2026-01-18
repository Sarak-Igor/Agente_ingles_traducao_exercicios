import { useState, useRef, useEffect } from 'react';
import YouTube, { YouTubeProps } from 'react-youtube';
import { SubtitleOverlay } from './SubtitleOverlay';
import { TranslationSegment } from '../../services/api';
import './VideoPlayer.css';

interface VideoPlayerProps {
  videoId: string;
  segments: TranslationSegment[];
  sourceLanguage: string;
  targetLanguage: string;
}

export const VideoPlayer = ({
  videoId,
  segments,
  sourceLanguage,
  targetLanguage,
}: VideoPlayerProps) => {
  const [currentTime, setCurrentTime] = useState(0);
  const [player, setPlayer] = useState<any>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const fullscreenCheckRef = useRef<NodeJS.Timeout | null>(null);

  const opts: YouTubeProps['opts'] = {
    height: '480',
    width: '100%',
    playerVars: {
      autoplay: 0,
      controls: 1,
      rel: 0,
      modestbranding: 1,
      fs: 0, // Desabilita fullscreen nativo do YouTube - usamos fullscreen customizado
      disablekb: 0,
    },
  };

  const handleReady: YouTubeProps['onReady'] = (event) => {
    const playerInstance = event.target;
    setPlayer(playerInstance);
    startTimeTracking(playerInstance);
    startFullscreenDetection();
    
    // Intercepta tentativas de fullscreen do YouTube e redireciona para nosso fullscreen
    try {
      // Remove o botão de fullscreen nativo do YouTube se possível
      const iframe = document.querySelector('iframe[src*="youtube.com"]') as HTMLIFrameElement;
      if (iframe) {
        // Observa mudanças no iframe para detectar quando ele tenta entrar em fullscreen
        const observer = new MutationObserver(() => {
          // Se detectar que o iframe está tentando fullscreen, força nosso fullscreen
          const container = document.querySelector('.video-player-container') as HTMLElement;
          if (container && !document.fullscreenElement) {
            // Não força automaticamente, mas garante que nosso overlay apareça
          }
        });
        
        observer.observe(iframe, {
          attributes: true,
          attributeFilter: ['style', 'class'],
        });
      }
    } catch (error) {
      // Ignora erros
    }
  };

  const startFullscreenDetection = () => {
    // Verifica fullscreen periodicamente
    if (fullscreenCheckRef.current) {
      clearInterval(fullscreenCheckRef.current);
    }

    const checkFullscreen = () => {
      try {
        // Verifica fullscreen do documento (fullscreen customizado)
        const docFullscreen = !!(
          document.fullscreenElement ||
          (document as any).webkitFullscreenElement ||
          (document as any).mozFullScreenElement ||
          (document as any).msFullscreenElement
        );
        
        setIsFullscreen(docFullscreen);
      } catch (error) {
        // Ignora erros
      }
    };

    // Verifica imediatamente
    checkFullscreen();
    
    // Verifica periodicamente (a cada 200ms para melhor performance)
    fullscreenCheckRef.current = setInterval(checkFullscreen, 200);
  };

  const startTimeTracking = (playerInstance: any) => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    intervalRef.current = setInterval(() => {
      try {
        const time = playerInstance.getCurrentTime();
        setCurrentTime(time);
      } catch (error) {
        // Player pode não estar pronto
      }
    }, 100); // Atualiza a cada 100ms para sincronização precisa
  };

  useEffect(() => {
    // Detecta mudanças de fullscreen via eventos
    const handleFullscreenChange = () => {
      const isFullscreen = !!(
        document.fullscreenElement ||
        (document as any).webkitFullscreenElement ||
        (document as any).mozFullScreenElement ||
        (document as any).msFullscreenElement
      );
      setIsFullscreen(isFullscreen);
      
      // Ajusta tamanho do container quando entrar/sair de fullscreen
      const container = document.querySelector('.video-player-container') as HTMLElement;
      if (container) {
        if (isFullscreen) {
          // Em fullscreen, preenche toda a tela
          const screenWidth = window.screen.width;
          const screenHeight = window.screen.height;
          container.style.width = `${screenWidth}px`;
          container.style.height = `${screenHeight}px`;
        } else {
          // Fora de fullscreen, restaura dimensões originais
          container.style.width = '';
          container.style.height = '';
        }
      }
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (fullscreenCheckRef.current) {
        clearInterval(fullscreenCheckRef.current);
      }
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    };
  }, []);

  const getActiveSegments = (): TranslationSegment[] => {
    // Filtra segmentos ativos no momento atual
    // Usa margem de tolerância de 0.1s antes e depois para melhor sincronização
    const tolerance = 0.1;
    const activeSegments = segments.filter((seg) => {
      const startTime = seg.start - tolerance; // Começa um pouco antes
      const endTime = seg.start + seg.duration + tolerance; // Termina um pouco depois
      return currentTime >= startTime && currentTime < endTime;
    });
    
    // Se há múltiplos segmentos ativos (sobreposição), prioriza o que está mais próximo do tempo atual
    if (activeSegments.length > 1) {
      // Ordena por proximidade do tempo atual (mais próximo primeiro)
      activeSegments.sort((a, b) => {
        const aDistance = Math.abs(currentTime - (a.start + a.duration / 2));
        const bDistance = Math.abs(currentTime - (b.start + b.duration / 2));
        return aDistance - bDistance;
      });
      // Retorna apenas o mais próximo para evitar misturar frases diferentes
      return [activeSegments[0]];
    }
    
    return activeSegments;
  };

  const handleFullscreenClick = async () => {
    const container = document.querySelector('.video-player-container') as HTMLElement;
    if (!container) return;

    try {
      if (!document.fullscreenElement) {
        // Entra em fullscreen do container (inclui vídeo + legendas)
        // Detecta tamanho da tela e ajusta o container
        const screenWidth = window.screen.width;
        const screenHeight = window.screen.height;
        
        // Define dimensões do container para preencher toda a tela
        container.style.width = `${screenWidth}px`;
        container.style.height = `${screenHeight}px`;
        
        if (container.requestFullscreen) {
          await container.requestFullscreen();
        } else if ((container as any).webkitRequestFullscreen) {
          await (container as any).webkitRequestFullscreen();
        } else if ((container as any).mozRequestFullScreen) {
          await (container as any).mozRequestFullScreen();
        } else if ((container as any).msRequestFullscreen) {
          await (container as any).msRequestFullscreen();
        }
        setIsFullscreen(true);
      } else {
        // Sai de fullscreen
        if (document.exitFullscreen) {
          await document.exitFullscreen();
        } else if ((document as any).webkitExitFullscreen) {
          await (document as any).webkitExitFullscreen();
        } else if ((document as any).mozCancelFullScreen) {
          await (document as any).mozCancelFullScreen();
        } else if ((document as any).msExitFullscreen) {
          await (document as any).msExitFullscreen();
        }
        setIsFullscreen(false);
        
        // Restaura dimensões originais
        container.style.width = '';
        container.style.height = '';
      }
    } catch (error) {
      console.error('Erro ao alternar fullscreen:', error);
    }
  };

  return (
    <div className="video-player-container">
      <div className="video-wrapper">
        <YouTube
          videoId={videoId}
          opts={opts}
          onReady={handleReady}
          className="youtube-player"
        />
        <button
          className="fullscreen-toggle-btn"
          onClick={handleFullscreenClick}
          title={isFullscreen ? "Sair de tela cheia" : "Tela cheia"}
        >
          {isFullscreen ? '⤓' : '⤢'}
        </button>
        {/* Overlay de legendas - sempre renderizado */}
        <SubtitleOverlay
          segments={getActiveSegments()}
          sourceLanguage={sourceLanguage}
          targetLanguage={targetLanguage}
          isFullscreen={isFullscreen}
        />
      </div>
    </div>
  );
};
