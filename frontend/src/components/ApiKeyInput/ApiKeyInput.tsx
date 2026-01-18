import { useState, useEffect } from 'react';
import { storage } from '../../services/storage';
import './ApiKeyInput.css';

interface ApiKeyInputProps {
  onApiKeyChange: (key: string) => void;
}

export const ApiKeyInput = ({ onApiKeyChange }: ApiKeyInputProps) => {
  const [apiKey, setApiKey] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const [hasSavedKey, setHasSavedKey] = useState(false);

  useEffect(() => {
    const saved = storage.getGeminiApiKey();
    if (saved) {
      setApiKey(saved);
      setHasSavedKey(true);
      onApiKeyChange(saved);
    }
  }, [onApiKeyChange]);

  const handleSave = () => {
    if (apiKey.trim()) {
      storage.setGeminiApiKey(apiKey.trim());
      setHasSavedKey(true);
      onApiKeyChange(apiKey.trim());
      setIsExpanded(false);
    }
  };

  return (
    <div className="api-key-container">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="api-key-toggle"
      >
        {isExpanded ? '▼' : '▶'} Configurar Chave de API (Gemini)
        {hasSavedKey && !isExpanded && <span className="api-key-status">✓ Configurada</span>}
      </button>
      
      {isExpanded && (
        <div className="api-key-form">
          <p className="api-key-info">
            Obtenha sua chave gratuita em:{' '}
            <a
              href="https://aistudio.google.com/apikey"
              target="_blank"
              rel="noopener noreferrer"
              className="api-key-link"
            >
              Google AI Studio
            </a>
          </p>
          <div className="api-key-input-wrapper">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Cole sua chave de API aqui (AIza...)"
              className="api-key-input"
            />
            <button
              type="button"
              onClick={handleSave}
              className="api-key-save"
              disabled={!apiKey.trim()}
            >
              Salvar
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
