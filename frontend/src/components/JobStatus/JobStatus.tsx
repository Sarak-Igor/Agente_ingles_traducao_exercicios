import { useState, useEffect, useRef } from 'react';
import { JobStatusResponse } from '../../services/api';
import './JobStatus.css';

interface JobStatusProps {
  jobStatus: JobStatusResponse | null;
  isPolling: boolean;
  jobId: string;
}

export const JobStatus = ({ jobStatus, isPolling, jobId }: JobStatusProps) => {
  const [startTime] = useState<number>(Date.now());
  const [estimatedTimeRemaining, setEstimatedTimeRemaining] = useState<number | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!jobStatus || jobStatus.status === 'completed' || jobStatus.status === 'error') {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      setEstimatedTimeRemaining(null);
      return;
    }

    const calculateEstimatedTime = () => {
      if (jobStatus.progress > 0 && jobStatus.progress < 100) {
        const elapsed = (Date.now() - startTime) / 1000; // em segundos
        const progressDecimal = jobStatus.progress / 100;
        const estimatedTotal = elapsed / progressDecimal;
        const remaining = estimatedTotal - elapsed;
        setEstimatedTimeRemaining(Math.max(0, Math.round(remaining)));
      } else {
        setEstimatedTimeRemaining(null);
      }
    };

    calculateEstimatedTime();

    intervalRef.current = setInterval(calculateEstimatedTime, 1000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [jobStatus, startTime]);

  const formatTime = (seconds: number): string => {
    if (seconds < 60) {
      return `${seconds}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    if (minutes < 60) {
      return `${minutes}m ${remainingSeconds}s`;
    }
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours}h ${remainingMinutes}m`;
  };

  if (!jobStatus) {
    return null;
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return '#10b981';
      case 'error':
        return '#ef4444';
      case 'processing':
        return '#3b82f6';
      default:
        return '#6b7280';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'queued':
        return 'Na fila';
      case 'processing':
        return 'Processando';
      case 'completed':
        return 'Concluído';
      case 'error':
        return 'Erro';
      default:
        return status;
    }
  };

  const getServiceDisplayName = (service: string): string => {
    const serviceNames: { [key: string]: string } = {
      'gemini': 'Gemini (LLM)',
      'deeptranslator': 'Deep Translator',
      'deep-translator': 'Deep Translator',
      'googletrans': 'Google Translate',
      'googletranslate': 'Google Translate',
      'argos': 'Argos Translate',
      'argostranslate': 'Argos Translate',
      'libretranslate': 'LibreTranslate',
    };
    return serviceNames[service.toLowerCase()] || service;
  };

  return (
    <div className="job-status-container">
      <div className="job-status-header">
        <div
          className="job-status-badge"
          style={{ backgroundColor: getStatusColor(jobStatus.status) }}
        >
          {getStatusText(jobStatus.status)}
        </div>
        {isPolling && <div className="job-status-spinner"></div>}
      </div>
      
      {jobStatus.progress > 0 && (
        <div className="job-progress-container">
          <div className="job-progress-bar">
            <div
              className="job-progress-fill"
              style={{ width: `${jobStatus.progress}%` }}
            />
          </div>
          <span className="job-progress-text">{jobStatus.progress}%</span>
        </div>
      )}
      
      {jobStatus.message && (
        <p className="job-status-message">{jobStatus.message}</p>
      )}

      {jobStatus.translation_service && jobStatus.status === 'processing' && (
        <p className="job-status-service">
          🔧 Traduzindo com: <strong>{getServiceDisplayName(jobStatus.translation_service)}</strong>
        </p>
      )}

      {estimatedTimeRemaining !== null && jobStatus.status === 'processing' && (
        <p className="job-status-estimated-time">
          ⏱️ Tempo estimado restante: <strong>{formatTime(estimatedTimeRemaining)}</strong>
        </p>
      )}
      
      {jobStatus.error && (
        <div className="job-status-error">
          <strong>Erro:</strong> {jobStatus.error}
        </div>
      )}
    </div>
  );
};
