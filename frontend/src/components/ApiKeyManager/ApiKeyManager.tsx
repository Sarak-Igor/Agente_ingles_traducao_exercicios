import { useState, useEffect } from 'react';
import { apiKeysApi, ApiKeyStatus, ApiKeyResponse } from '../../services/api';
import './ApiKeyManager.css';

interface ApiKey {
  id: string;
  service: string;
  key: string;
  isActive: boolean;
  status?: ApiKeyStatus | null;
  checkingStatus?: boolean;
  backendId?: string; // ID do backend
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

  const loadApiKeys = async () => {
    try {
      // Carrega chaves do backend (do usuário atual)
      const response = await apiKeysApi.list();
      const backendKeys = response.api_keys || [];
      
      // Converte para formato local (sem expor as chaves - backend não retorna)
      // Por enquanto, vamos mostrar apenas os serviços que têm chaves salvas
      const keys: ApiKey[] = backendKeys.map((bk: ApiKeyResponse) => ({
        id: `${bk.service}-${bk.id}`,
        backendId: bk.id,
        service: bk.service,
        key: '••••••••••••••••', // Não expõe a chave real
        isActive: bk.service === 'gemini',
        status: null,
        checkingStatus: false,
      }));

      setApiKeys(keys);
    } catch (error) {
      console.error('Erro ao carregar chaves de API:', error);
      setApiKeys([]);
    }
  };

  const handleSave = async (service: string, key: string, apiKeyId?: string) => {
    try {
      const trimmedKey = key.trim();
      
      if (!trimmedKey) {
        return;
      }

      // Salva no backend
      await apiKeysApi.create({
        service,
        api_key: trimmedKey,
      });
      
      setNewKey({ service: 'gemini', key: '' });
      setEditingId(null);
      
      // Atualiza a lista de chaves
      await loadApiKeys();
      
      // Verifica status automaticamente após salvar
      if (['gemini', 'openrouter', 'groq', 'together'].includes(service)) {
        // Busca a chave recém-salva para verificar status
        setTimeout(async () => {
          const updatedKeys = await apiKeysApi.list();
          const savedKey = updatedKeys.api_keys.find((k: ApiKeyResponse) => k.service === service);
          if (savedKey) {
            // Para verificar status, precisamos da chave real (que acabamos de salvar)
            checkApiKeyStatus({
              id: `${service}-${savedKey.id}`,
              backendId: savedKey.id,
              service: service,
              key: trimmedKey, // Usa a chave que acabamos de salvar
              isActive: service === 'gemini',
              status: null,
              checkingStatus: false,
            });
          }
        }, 500);
      }
    } catch (error: any) {
      console.error('Erro ao salvar chave de API:', error);
      alert(error.response?.data?.detail || 'Erro ao salvar chave de API');
    }
  };

  const handleDelete = async (id: string, service: string, backendId?: string) => {
    try {
      if (backendId) {
        await apiKeysApi.delete(backendId);
      } else {
        // Fallback: tenta deletar por serviço
        await apiKeysApi.deleteByService(service);
      }
      await loadApiKeys();
    } catch (error: any) {
      console.error('Erro ao deletar chave de API:', error);
      alert(error.response?.data?.detail || 'Erro ao deletar chave de API');
    }
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
    // Marca como verificando usando função de callback para garantir estado atualizado
    setApiKeys(prevKeys => prevKeys.map(k => 
      k.id === apiKey.id || (k.service === apiKey.service && k.key === apiKey.key)
        ? { ...k, checkingStatus: true }
        : k
    ));

    try {
      let status: ApiKeyStatus;
      
      // Se a chave está salva no backend (não visível), usa rota especial
      if (apiKey.key === '••••••••••••••••' && apiKey.backendId) {
        status = await apiKeysApi.checkSavedStatus(apiKey.service);
      } else {
        // Se a chave está sendo editada/fornecida, usa rota normal
        status = await apiKeysApi.checkStatus(apiKey.key, apiKey.service);
      }
      
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
                        : apiKey.key === '••••••••••••••••' 
                          ? 'Chave salva (não visível)'
                          : `${apiKey.key.substring(0, 12)}...${apiKey.key.substring(apiKey.key.length - 4)}`}
                    </p>
                  </div>
                </div>
                <div className="api-key-actions">
                  {editingId === apiKey.id ? (
                    <>
                      <button
                        onClick={() => handleSave(apiKey.service, apiKey.key, apiKey.backendId)}
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
                        onClick={() => handleDelete(apiKey.id, apiKey.service, apiKey.backendId)}
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
                          {(() => {
                            // Agrupa modelos por categoria
                            const categoryLabels: { [key: string]: string } = {
                              'text': '📝 Escrita',
                              'reasoning': '🧠 Raciocínio',
                              'audio': '🎵 Áudio',
                              'image': '🖼️ Imagem',
                              'video': '🎬 Vídeo',
                              'code': '💻 Código',
                              'multimodal': '🌐 Multimodal'
                            };
                            
                            // Usa models_by_category se disponível, senão agrupa manualmente
                            const grouped = apiKey.status.models_by_category || (() => {
                              const groups: { [key: string]: typeof apiKey.status.models_status } = {};
                              apiKey.status.models_status.forEach(model => {
                                const cat = model.category || 'text';
                                if (!groups[cat]) groups[cat] = [];
                                groups[cat].push(model);
                              });
                              return groups;
                            })();
                            
                            // Ordem de exibição das categorias
                            const categoryOrder = ['text', 'reasoning', 'audio', 'image', 'video', 'code', 'multimodal'];
                            
                            return categoryOrder.map(category => {
                              const models = grouped[category];
                              if (!models || models.length === 0) return null;
                              
                              return (
                                <div key={category} className="model-category-group">
                                  <div className="model-category-header">
                                    {categoryLabels[category] || category}
                                  </div>
                                  {models.map((model) => (
                                    <div key={model.name} className={`model-item ${model.status}`}>
                                      <span className="model-name">{model.name}</span>
                                      <span className="model-badge">
                                        {model.available && !model.blocked ? '✅ Disponível' : 
                                         model.blocked ? '❌ Bloqueado' : '⚠️ Desconhecido'}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              );
                            });
                          })()}
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
