import { useState, useEffect } from 'react';
import { storage } from '../../services/storage';
import { apiKeysApi, ApiKeyStatus } from '../../services/api';
import './ApiKeyManager.css';

interface ApiKey {
  id: string;
  service: string;
  key: string;
  isActive: boolean;
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
  const [newKey, setNewKey] = useState({ service: 'gemini', key: '' });

  useEffect(() => {
    loadApiKeys();
  }, []);

    const loadApiKeys = () => {
    const keys: ApiKey[] = [];
    
    // Carrega chave Gemini do storage
    const geminiKey = storage.getGeminiApiKey();
    if (geminiKey) {
      keys.push({
        id: 'gemini-1',
        service: 'gemini',
        key: geminiKey,
        isActive: true,
        status: null,
        checkingStatus: false,
      });
    }

    // Carrega outras chaves do localStorage
    const openRouterKey = localStorage.getItem('openrouter_api_key');
    if (openRouterKey) {
      keys.push({
        id: 'openrouter-1',
        service: 'openrouter',
        key: openRouterKey,
        isActive: false,
        status: null,
        checkingStatus: false,
      });
    }

    const groqKey = localStorage.getItem('groq_api_key');
    if (groqKey) {
      keys.push({
        id: 'groq-1',
        service: 'groq',
        key: groqKey,
        isActive: false,
        status: null,
        checkingStatus: false,
      });
    }

    const togetherKey = localStorage.getItem('together_api_key');
    if (togetherKey) {
      keys.push({
        id: 'together-1',
        service: 'together',
        key: togetherKey,
        isActive: false,
        status: null,
        checkingStatus: false,
      });
    }

    setApiKeys(keys);
  };

  const handleSave = async (service: string, key: string) => {
    if (service === 'gemini') {
      storage.setGeminiApiKey(key);
    } else {
      localStorage.setItem(`${service}_api_key`, key);
    }
    
    const trimmedKey = key.trim();
    setNewKey({ service: 'gemini', key: '' });
    setEditingId(null);
    
    // Atualiza a lista de chaves
    loadApiKeys();
    
    // Verifica status automaticamente após salvar (para todas as APIs)
    if (trimmedKey && ['gemini', 'openrouter', 'groq', 'together'].includes(service)) {
      // Aguarda um pouco para garantir que o estado foi atualizado
      setTimeout(() => {
        checkApiKeyStatus({
          id: `${service}-1`,
          service: service,
          key: trimmedKey,
          isActive: service === 'gemini',
          status: null,
          checkingStatus: false,
        });
      }, 500);
    }
  };

  const handleDelete = (id: string, service: string) => {
    if (service === 'gemini') {
      localStorage.removeItem('gemini_api_key');
    } else {
      localStorage.removeItem(`${service}_api_key`);
    }
    loadApiKeys();
  };

  const handleAdd = () => {
    if (newKey.key.trim()) {
      handleSave(newKey.service, newKey.key.trim());
    }
  };

  const getServiceInfo = (serviceId: string) => {
    return SERVICES.find(s => s.id === serviceId) || SERVICES[0];
  };

  const checkApiKeyStatus = async (apiKey: ApiKey) => {
    // Suporta todos os serviços agora

    // Marca como verificando usando função de callback para garantir estado atualizado
    setApiKeys(prevKeys => prevKeys.map(k => 
      k.id === apiKey.id || (k.service === apiKey.service && k.key === apiKey.key)
        ? { ...k, checkingStatus: true }
        : k
    ));

    try {
      const status = await apiKeysApi.checkStatus(apiKey.key, apiKey.service);
      
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
                      
                      {apiKey.status.models_status.length > 0 && (
                        <div className="models-list">
                          <div className="models-header">Status dos Modelos:</div>
                          {apiKey.status.models_status.map((model) => (
                            <div key={model.name} className={`model-item ${model.status}`}>
                              <span className="model-name">{model.name}</span>
                              <span className="model-badge">
                                {model.available ? '✅ Disponível' : 
                                 model.blocked ? '❌ Bloqueado' : '⚠️ Desconhecido'}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      
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
