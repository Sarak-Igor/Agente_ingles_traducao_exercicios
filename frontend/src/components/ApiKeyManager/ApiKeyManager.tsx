import { useState, useEffect } from 'react';
import { storage } from '../../services/storage';
import { apiKeysApi, ApiKeyStatus } from '../../services/api';
import './ApiKeyManager.css';

interface ApiKey {
  id: string;
  service: string;
  key: string;
  isActive: boolean;
  isFreeTier: string; // 'free' ou 'paid'
  status?: ApiKeyStatus | null;
  checkingStatus?: boolean;
}

const SERVICES = [
  { id: 'gemini', name: 'Google Gemini', icon: '🤖', url: 'https://aistudio.google.com/apikey' },
  { id: 'openrouter', name: 'OpenRouter', icon: '🌐', url: 'https://openrouter.ai/keys' },
  { id: 'groq', name: 'Groq', icon: '⚡', url: 'https://console.groq.com/keys' },
  { id: 'together', name: 'Together AI', icon: '🤝', url: 'https://api.together.xyz/settings/api-keys' },
];

export const ApiKeyManager = () => {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [newKey, setNewKey] = useState({ service: 'gemini', key: '', isFreeTier: 'free' });

  useEffect(() => {
    // Migração automática: garante que todas as chaves antigas tenham isFreeTier
    const migrateOldKeys = () => {
      const services = ['gemini', 'openrouter', 'groq', 'together'];
      services.forEach(service => {
        const keyName = service === 'gemini' ? 'gemini_api_key' : `${service}_api_key`;
        const tierName = service === 'gemini' ? 'gemini_is_free_tier' : `${service}_is_free_tier`;
        
        // Se existe a chave mas não existe o tipo, define como 'free' por padrão
        if (service === 'gemini') {
          const geminiKey = storage.getGeminiApiKey();
          if (geminiKey && !localStorage.getItem('gemini_is_free_tier')) {
            localStorage.setItem('gemini_is_free_tier', 'free');
          }
        } else {
          const apiKey = localStorage.getItem(keyName);
          if (apiKey && !localStorage.getItem(tierName)) {
            localStorage.setItem(tierName, 'free');
          }
        }
      });
    };
    
    migrateOldKeys();
    loadApiKeys();
  }, []);

    const loadApiKeys = () => {
    const keys: ApiKey[] = [];
    
    // Carrega chave Gemini do storage
    const geminiKey = storage.getGeminiApiKey();
    if (geminiKey) {
      const isFreeTier = localStorage.getItem('gemini_is_free_tier') || 'free';
      keys.push({
        id: 'gemini-1',
        service: 'gemini',
        key: geminiKey,
        isActive: true,
        isFreeTier: isFreeTier,
        status: null,
        checkingStatus: false,
      });
    }

    // Carrega outras chaves do localStorage
    const openRouterKey = localStorage.getItem('openrouter_api_key');
    if (openRouterKey) {
      const isFreeTier = localStorage.getItem('openrouter_is_free_tier') || 'free';
      keys.push({
        id: 'openrouter-1',
        service: 'openrouter',
        key: openRouterKey,
        isActive: false,
        isFreeTier: isFreeTier,
        status: null,
        checkingStatus: false,
      });
    }

    const groqKey = localStorage.getItem('groq_api_key');
    if (groqKey) {
      const isFreeTier = localStorage.getItem('groq_is_free_tier') || 'free';
      keys.push({
        id: 'groq-1',
        service: 'groq',
        key: groqKey,
        isActive: false,
        isFreeTier: isFreeTier,
        status: null,
        checkingStatus: false,
      });
    }

    const togetherKey = localStorage.getItem('together_api_key');
    if (togetherKey) {
      const isFreeTier = localStorage.getItem('together_is_free_tier') || 'free';
      keys.push({
        id: 'together-1',
        service: 'together',
        key: togetherKey,
        isActive: false,
        isFreeTier: isFreeTier,
        status: null,
        checkingStatus: false,
      });
    }

    setApiKeys(keys);
  };

  const handleSave = async (service: string, key: string, isFreeTier: string = 'free') => {
    if (service === 'gemini') {
      storage.setGeminiApiKey(key);
      localStorage.setItem('gemini_is_free_tier', isFreeTier);
    } else {
      localStorage.setItem(`${service}_api_key`, key);
      localStorage.setItem(`${service}_is_free_tier`, isFreeTier);
    }
    
    const trimmedKey = key.trim();
    setNewKey({ service: 'gemini', key: '', isFreeTier: 'free' });
    setEditingId(null);
    
    // Atualiza a lista de chaves
    loadApiKeys();
    
    // Verifica status automaticamente após salvar (para todas as APIs)
    if (trimmedKey && ['gemini', 'openrouter', 'groq', 'together'].includes(service)) {
      // Aguarda um pouco para garantir que o estado foi atualizado
      setTimeout(() => {
        const savedKey = apiKeys.find(k => k.service === service) || {
          id: `${service}-1`,
          service: service,
          key: trimmedKey,
          isActive: service === 'gemini',
          isFreeTier: isFreeTier,
          status: null,
          checkingStatus: false,
        };
        checkApiKeyStatus(savedKey);
      }, 500);
    }
  };

  const handleDelete = (id: string, service: string) => {
    if (service === 'gemini') {
      localStorage.removeItem('gemini_api_key');
      localStorage.removeItem('gemini_is_free_tier');
    } else {
      localStorage.removeItem(`${service}_api_key`);
      localStorage.removeItem(`${service}_is_free_tier`);
    }
    loadApiKeys();
  };

  const handleAdd = () => {
    if (newKey.key.trim()) {
      handleSave(newKey.service, newKey.key.trim(), newKey.isFreeTier);
    }
  };

  const getServiceInfo = (serviceId: string) => {
    return SERVICES.find(s => s.id === serviceId) || SERVICES[0];
  };

  type ModelCategory = 'audio' | 'video' | 'escrita' | 'raciocinio';

  const categorizeModel = (modelName: string): ModelCategory => {
    const name = modelName.toLowerCase();
    
    // Áudio - modelos relacionados a processamento de áudio, fala, etc.
    if (name.includes('audio') || name.includes('speech') || name.includes('tts') || 
        name.includes('whisper') || name.includes('asr') || name.includes('sound')) {
      return 'audio';
    }
    
    // Vídeo - modelos relacionados a processamento de vídeo, visão, etc.
    if (name.includes('video') || name.includes('vision') || name.includes('imagen') ||
        name.includes('dall-e') || name.includes('image') || name.includes('clip') ||
        name.includes('multimodal') || name.includes('vision')) {
      return 'video';
    }
    
    // Raciocínio - modelos avançados de raciocínio, análise, etc.
    // Modelos "pro" (exceto flash) e modelos com "reasoning", "ultra", "advanced", "thinking"
    if (name.includes('reasoning') || 
        (name.includes('pro') && !name.includes('flash')) ||
        name.includes('ultra') || 
        name.includes('advanced') || 
        name.includes('thinking') ||
        name.includes('deepmind')) {
      return 'raciocinio';
    }
    
    // Escrita - modelos de texto, geração de texto, tradução, etc. (padrão)
    // Inclui modelos "flash", "turbo", "chat", "text", etc.
    return 'escrita';
  };

  const groupModelsByCategory = (models: Array<{ name: string; available: boolean; blocked: boolean; status: string; reason?: string }>) => {
    const grouped: Record<ModelCategory, typeof models> = {
      audio: [],
      video: [],
      escrita: [],
      raciocinio: [],
    };

    models.forEach(model => {
      const category = categorizeModel(model.name);
      grouped[category].push(model);
    });

    return grouped;
  };

  const getCategoryLabel = (category: ModelCategory): string => {
    const labels: Record<ModelCategory, string> = {
      audio: '🎵 Áudio',
      video: '🎬 Vídeo',
      escrita: '✍️ Escrita',
      raciocinio: '🧠 Raciocínio',
    };
    return labels[category];
  };

  const checkApiKeyStatus = async (apiKey: ApiKey) => {
    // Suporta todos os serviços agora

    // Garante que isFreeTier sempre tenha um valor (compatibilidade com chaves antigas)
    const isFreeTier = apiKey.isFreeTier || 'free';

    // Marca como verificando usando função de callback para garantir estado atualizado
    setApiKeys(prevKeys => prevKeys.map(k => 
      k.id === apiKey.id || (k.service === apiKey.service && k.key === apiKey.key)
        ? { ...k, checkingStatus: true, isFreeTier: k.isFreeTier || 'free' }
        : k
    ));

    try {
      const status = await apiKeysApi.checkStatus(apiKey.key, apiKey.service, isFreeTier);
      
      // Atualiza status usando função de callback
      setApiKeys(prevKeys => prevKeys.map(k => 
        k.id === apiKey.id || (k.service === apiKey.service && k.key === apiKey.key)
          ? { ...k, status, checkingStatus: false }
          : k
      ));
    } catch (error: any) {
      console.error('Erro ao verificar status:', error);
      const errorStatus: ApiKeyStatus = {
        service: apiKey.service,
        is_valid: false,
        models_status: [],
        available_models: [],
        blocked_models: [],
        error: error.response?.data?.detail || 'Erro ao verificar status da chave'
      };
      
      // Atualiza com erro usando função de callback
      setApiKeys(prevKeys => prevKeys.map(k => 
        k.id === apiKey.id || (k.service === apiKey.service && k.key === apiKey.key)
          ? { ...k, status: errorStatus, checkingStatus: false }
          : k
      ));
    }
  };

  return (
    <div className="api-key-manager">
      <div className="api-key-list">
        {apiKeys.map((apiKey) => {
          const serviceInfo = getServiceInfo(apiKey.service);
          return (
            <div key={apiKey.id} className="api-key-item">
              <div className="api-key-item-header">
                <div className="api-key-service">
                  <span className="service-icon">{serviceInfo.icon}</span>
                  <div>
                    <h4>{serviceInfo.name}</h4>
                    <p className="api-key-preview">
                      {editingId === apiKey.id 
                        ? apiKey.key 
                        : `${apiKey.key.substring(0, 12)}...${apiKey.key.substring(apiKey.key.length - 4)}`}
                    </p>
                  </div>
                </div>
                <div className="api-key-actions">
                  {editingId === apiKey.id ? (
                    <>
                      <button
                        onClick={() => handleSave(apiKey.service, apiKey.key)}
                        className="btn-save"
                      >
                        Salvar
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="btn-cancel"
                      >
                        Cancelar
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => setEditingId(apiKey.id)}
                        className="btn-edit"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleDelete(apiKey.id, apiKey.service)}
                        className="btn-delete"
                      >
                        Remover
                      </button>
                    </>
                  )}
                </div>
              </div>
              {editingId === apiKey.id && (
                <>
                  <input
                    type="password"
                    value={apiKey.key}
                    onChange={(e) => {
                      setApiKeys(apiKeys.map(k => 
                        k.id === apiKey.id ? { ...k, key: e.target.value } : k
                      ));
                    }}
                    className="api-key-edit-input"
                    placeholder="Cole a chave de API"
                  />
                  <select
                    value={apiKey.isFreeTier || 'free'}
                    onChange={(e) => {
                      setApiKeys(apiKeys.map(k => 
                        k.id === apiKey.id ? { ...k, isFreeTier: e.target.value } : k
                      ));
                    }}
                    className="api-key-edit-input"
                    style={{ marginTop: '8px' }}
                  >
                    <option value="free">🆓 Gratuito (Free Tier)</option>
                    <option value="paid">💳 Pago (Pay-as-you-go)</option>
                  </select>
                </>
              )}
              
              {/* Status e Cotas */}
              {!editingId && (
                <div className="api-key-status">
                  <button
                    onClick={() => checkApiKeyStatus(apiKey)}
                    disabled={apiKey.checkingStatus}
                    className="btn-check-status"
                  >
                    {apiKey.checkingStatus ? '🔄 Verificando...' : '📊 Verificar Cotas'}
                  </button>
                  
                  {apiKey.status && (
                    <div className="quota-info">
                      <div className={`quota-status ${apiKey.status.is_valid ? 'valid' : 'invalid'}`}>
                        <span className="status-indicator">
                          {apiKey.status.is_valid ? '✅' : '❌'}
                        </span>
                        <span className="status-text">
                          {apiKey.status.is_valid 
                            ? apiKey.status.available_models.length > 0
                              ? `${apiKey.status.available_models.length} modelo(s) disponível(is)`
                              : 'Chave válida'
                            : 'Chave inválida ou sem acesso'}
                        </span>
                      </div>
                      
                      {apiKey.status.models_status.length > 0 && (() => {
                        const groupedModels = groupModelsByCategory(apiKey.status.models_status);
                        const categories: ModelCategory[] = ['audio', 'video', 'escrita', 'raciocinio'];
                        
                        return (
                          <div className="models-list">
                            <div className="models-header">Status dos Modelos:</div>
                            {categories.map((category) => {
                              const models = groupedModels[category];
                              if (models.length === 0) return null;
                              
                              return (
                                <div key={category} className="model-category">
                                  <div className="model-category-header">
                                    {getCategoryLabel(category)} ({models.length})
                                  </div>
                                  <div className="model-category-items">
                                    {models.map((model) => {
                                      let statusText = '';
                                      let statusTooltip = '';
                                      
                                      if (model.available) {
                                        statusText = '✅ Disponível';
                                        statusTooltip = 'Modelo disponível e funcionando';
                                      } else if (model.blocked) {
                                        statusText = '❌ Bloqueado';
                                        // Determina motivo do bloqueio
                                        if (model.reason === 'not_available') {
                                          statusTooltip = 'Modelo não disponível na sua conta ou região';
                                        } else if (model.reason === 'quota_exceeded') {
                                          statusTooltip = 'Cota de API atingida';
                                        } else if (model.reason === 'not_found') {
                                          statusTooltip = 'Modelo não encontrado na API';
                                        } else if (model.reason === 'not_in_api_list') {
                                          statusTooltip = 'Modelo não disponível na lista da API';
                                        } else {
                                          statusTooltip = 'Modelo bloqueado (cota atingida ou não disponível)';
                                        }
                                      } else {
                                        statusText = '⚠️ Desconhecido';
                                        statusTooltip = 'Status do modelo não foi determinado';
                                      }
                                      
                                      // Formata informações de cota/custo
                                      const formatQuota = (used: number, limit: number) => {
                                        const formatNumber = (num: number) => {
                                          if (num >= 1_000_000) {
                                            return `${(num / 1_000_000).toFixed(1)}M`;
                                          } else if (num >= 1000) {
                                            return `${(num / 1000).toFixed(0)}K`;
                                          }
                                          return num.toString();
                                        };
                                        const usedFormatted = formatNumber(used);
                                        const limitFormatted = formatNumber(limit);
                                        const percentage = limit > 0 ? ((used / limit) * 100).toFixed(0) : '0';
                                        return `${usedFormatted} / ${limitFormatted} tokens (${percentage}%)`;
                                      };
                                      
                                      const formatCost = (cost: number) => {
                                        if (cost < 0.01) {
                                          return `US$ ${cost.toFixed(4)}`;
                                        }
                                        return `US$ ${cost.toFixed(2)}`;
                                      };
                                      
                                      // Garante compatibilidade com chaves antigas
                                      const apiKeyIsFreeTier = apiKey.isFreeTier || 'free';
                                      
                                      const quotaInfo = apiKeyIsFreeTier === 'free' && model.quota_used !== null && model.quota_limit !== null
                                        ? formatQuota(model.quota_used, model.quota_limit)
                                        : apiKeyIsFreeTier === 'paid' && model.daily_cost !== null
                                        ? formatCost(model.daily_cost)
                                        : null;
                                      
                                      return (
                                        <div key={model.name} className={`model-item ${model.status}`} title={statusTooltip}>
                                          <div className="model-info">
                                            <span className="model-name">{model.name}</span>
                                            {quotaInfo && (
                                              <span className="model-quota-info">
                                                {quotaInfo}
                                              </span>
                                            )}
                                          </div>
                                          <span className="model-badge">
                                            {statusText}
                                          </span>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        );
                      })()}
                      
                      {apiKey.status.is_valid && apiKey.status.available_models.length === 0 && (
                        <div className="quota-info-text">
                          ✅ Chave de API válida e funcionando
                        </div>
                      )}
                      
                      {apiKey.status.error && (
                        <div className="quota-error">
                          ⚠️ {apiKey.status.error}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="api-key-add">
        <h3>Adicionar Nova Chave</h3>
        <div className="api-key-add-form">
          <select
            value={newKey.service}
            onChange={(e) => setNewKey({ ...newKey, service: e.target.value })}
            className="api-key-service-select"
          >
            {SERVICES.map((service) => (
              <option key={service.id} value={service.id}>
                {service.icon} {service.name}
              </option>
            ))}
          </select>
          <input
            type="password"
            value={newKey.key}
            onChange={(e) => setNewKey({ ...newKey, key: e.target.value })}
            placeholder="Cole sua chave de API aqui"
            className="api-key-add-input"
          />
          <select
            value={newKey.isFreeTier}
            onChange={(e) => setNewKey({ ...newKey, isFreeTier: e.target.value })}
            className="api-key-service-select"
          >
            <option value="free">🆓 Gratuito (Free Tier)</option>
            <option value="paid">💳 Pago (Pay-as-you-go)</option>
          </select>
          <div className="api-key-add-actions">
            <a
              href={getServiceInfo(newKey.service).url}
              target="_blank"
              rel="noopener noreferrer"
              className="api-key-link-btn"
            >
              Obter Chave
            </a>
            <button
              onClick={handleAdd}
              disabled={!newKey.key.trim()}
              className="btn-add"
            >
              Adicionar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
