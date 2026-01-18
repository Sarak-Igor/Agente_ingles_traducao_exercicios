import { useState, useEffect } from 'react';
import { storage } from '../../services/storage';
import { usageApi, UsageStatsResponse } from '../../services/api';
import './ApiUsage.css';

interface UsageStats {
  service: string;
  requests: number;
  tokens: number;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  models: Array<{
    model: string;
    tokens: number;
    input_tokens: number;
    output_tokens: number;
    requests: number;
  }>;
  quota: {
    limit: number;
    used: number;
    resetDate: string;
  };
}

export const ApiUsage = () => {
  const [stats, setStats] = useState<UsageStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [periodDays, setPeriodDays] = useState(30);

  useEffect(() => {
    loadUsageStats(periodDays);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadUsageStats = async (days?: number) => {
    const period = days !== undefined ? days : periodDays;
    setLoading(true);
    setError(null);
    
    try {
      const response = await usageApi.getStats(undefined, period);
      
      const statsData: UsageStats[] = [];
      
      if (response.services && response.services.length > 0) {
        // Múltiplos serviços
        for (const serviceData of response.services) {
          const serviceName = getServiceDisplayName(serviceData.service);
          
          statsData.push({
            service: serviceName,
            requests: serviceData.requests || 0,
            tokens: serviceData.total_tokens || 0,
            input_tokens: serviceData.input_tokens || 0,
            output_tokens: serviceData.output_tokens || 0,
            cost: 0, // Estimativa de custo pode ser adicionada depois
            models: serviceData.models || [],
            quota: {
              limit: getQuotaLimit(serviceData.service),
              used: serviceData.total_tokens || 0,
              resetDate: new Date(Date.now() + 24 * 60 * 60 * 1000).toLocaleDateString('pt-BR'),
            },
          });
        }
      } else if (response.service) {
        // Um serviço específico
        const serviceName = getServiceDisplayName(response.service);
        statsData.push({
          service: serviceName,
          requests: response.requests || 0,
          tokens: response.total_tokens || 0,
          input_tokens: response.input_tokens || 0,
          output_tokens: response.output_tokens || 0,
          cost: 0,
          models: response.models || [],
          quota: {
            limit: getQuotaLimit(response.service),
            used: response.total_tokens || 0,
            resetDate: new Date(Date.now() + 24 * 60 * 60 * 1000).toLocaleDateString('pt-BR'),
          },
        });
      }
      
      setStats(statsData);
    } catch (err: any) {
      console.error('Erro ao carregar estatísticas:', err);
      setError(err.response?.data?.detail || 'Erro ao carregar estatísticas de uso');
    } finally {
      setLoading(false);
    }
  };

  const getServiceDisplayName = (service: string): string => {
    const names: { [key: string]: string } = {
      'gemini': 'Google Gemini',
      'openrouter': 'OpenRouter',
      'groq': 'Groq',
      'together': 'Together AI'
    };
    return names[service] || service;
  };

  const getQuotaLimit = (service: string): number => {
    // Limites aproximados (podem ser ajustados)
    const limits: { [key: string]: number } = {
      'gemini': 1000000, // 1M tokens/dia (free tier)
      'openrouter': 50000, // Varia por tier
      'groq': 40000, // Varia por modelo
      'together': 180000 // Varia por tier
    };
    return limits[service] || 100000;
  };

  const getUsagePercentage = (used: number, limit: number) => {
    return Math.min((used / limit) * 100, 100);
  };

  const getUsageColor = (percentage: number) => {
    if (percentage < 50) return '#10b981';
    if (percentage < 80) return '#f59e0b';
    return '#ef4444';
  };

  if (loading) {
    return (
      <div className="api-usage-empty">
        <p>Carregando estatísticas...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="api-usage-empty">
        <p style={{ color: '#ef4444' }}>Erro: {error}</p>
        <button onClick={loadUsageStats} className="refresh-btn">🔄 Tentar Novamente</button>
      </div>
    );
  }

  if (stats.length === 0) {
    return (
      <div className="api-usage-empty">
        <p>Nenhum uso registrado ainda.</p>
        <p className="hint">As estatísticas de uso serão exibidas aqui após traduzir vídeos.</p>
        <button onClick={loadUsageStats} className="refresh-btn">🔄 Atualizar</button>
      </div>
    );
  }

  return (
    <div className="api-usage">
      <div className="usage-header">
        <h3>Estatísticas de Uso</h3>
        <div className="header-controls">
          <select 
            value={periodDays} 
            onChange={(e) => {
              const days = parseInt(e.target.value);
              setPeriodDays(days);
              loadUsageStats(days);
            }}
            className="period-select"
          >
            <option value="7">Últimos 7 dias</option>
            <option value="30">Últimos 30 dias</option>
            <option value="90">Últimos 90 dias</option>
            <option value="180">Últimos 180 dias</option>
            <option value="365">Últimos 365 dias</option>
          </select>
          <button onClick={() => loadUsageStats(periodDays)} className="refresh-btn">🔄 Atualizar</button>
        </div>
        <button onClick={loadUsageStats} className="refresh-btn">🔄 Atualizar</button>
      </div>

      <div className="usage-stats">
        {stats.map((stat) => {
          const percentage = getUsagePercentage(stat.quota.used, stat.quota.limit);
          const color = getUsageColor(percentage);

          return (
            <div key={stat.service} className="usage-card">
              <div className="usage-card-header">
                <h4>{stat.service}</h4>
                <span className={`usage-badge ${stat.cost === 0 ? 'free' : 'paid'}`}>
                  {stat.cost === 0 ? 'Gratuito' : `$${stat.cost.toFixed(4)}`}
                </span>
              </div>

              <div className="usage-metrics">
                <div className="metric">
                  <span className="metric-label">Requisições</span>
                  <span className="metric-value">{stat.requests.toLocaleString()}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Tokens Totais</span>
                  <span className="metric-value">{stat.tokens.toLocaleString()}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Tokens Entrada</span>
                  <span className="metric-value">{stat.input_tokens.toLocaleString()}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Tokens Saída</span>
                  <span className="metric-value">{stat.output_tokens.toLocaleString()}</span>
                </div>
              </div>

              {/* Lista de modelos utilizados */}
              {stat.models && stat.models.length > 0 && (
                <div className="models-usage">
                  <h5>Uso por Modelo:</h5>
                  <div className="models-list">
                    {stat.models.map((model) => (
                      <div key={model.model} className="model-usage-item">
                        <span className="model-name">{model.model}</span>
                        <div className="model-stats">
                          <span className="model-tokens">{model.tokens.toLocaleString()} tokens</span>
                          <span className="model-requests">{model.requests} req</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="usage-quota">
                <div className="quota-header">
                  <span>Quota Diária</span>
                  <span className="quota-numbers">
                    {stat.quota.used.toLocaleString()} / {stat.quota.limit.toLocaleString()}
                  </span>
                </div>
                <div className="quota-bar">
                  <div
                    className="quota-fill"
                    style={{
                      width: `${percentage}%`,
                      backgroundColor: color,
                    }}
                  />
                </div>
                <div className="quota-footer">
                  <span className="quota-percentage">{percentage.toFixed(1)}% usado</span>
                  <span className="quota-reset">Reset: {stat.quota.resetDate}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="usage-info">
        <h4>ℹ️ Sobre as Cotas</h4>
        <ul>
          <li><strong>Free Tier:</strong> Limites diários e por minuto aplicados automaticamente</li>
          <li><strong>Rate Limits:</strong> O sistema aguarda automaticamente quando os limites são atingidos</li>
          <li><strong>Reset:</strong> As cotas são resetadas diariamente</li>
        </ul>
      </div>
    </div>
  );
};
