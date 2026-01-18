import { useState, useEffect, useRef } from 'react';
import { videoApi, JobStatusResponse } from '../services/api';

export const useJobPolling = (jobId: string | null, enabled: boolean = true) => {
  const [jobStatus, setJobStatus] = useState<JobStatusResponse | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!jobId || !enabled) {
      return;
    }

    setIsPolling(true);

    const poll = async () => {
      try {
        const status = await videoApi.getJobStatus(jobId);
        setJobStatus(status);

        if (status.status === 'completed' || status.status === 'error') {
          setIsPolling(false);
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }
        }
      } catch (error) {
        console.error('Erro ao verificar status do job:', error);
        setIsPolling(false);
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      }
    };

    // Primeira verificação imediata
    poll();

    // Polling a cada 2 segundos
    intervalRef.current = setInterval(poll, 2000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [jobId, enabled]);

  return { jobStatus, isPolling };
};
