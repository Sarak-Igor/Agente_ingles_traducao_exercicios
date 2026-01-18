import { useState } from 'react';
import './URLInput.css';

interface URLInputProps {
  onSubmit: (url: string) => void;
  loading?: boolean;
}

export const URLInput = ({ onSubmit, loading }: URLInputProps) => {
  const [url, setUrl] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim()) {
      onSubmit(url.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} className="url-input-container">
      <div className="url-input-wrapper">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Cole a URL do vídeo do YouTube aqui..."
          className="url-input"
          disabled={loading}
        />
        <button
          type="submit"
          className="url-submit-button"
          disabled={loading || !url.trim()}
        >
          {loading ? 'Processando...' : 'Traduzir'}
        </button>
      </div>
    </form>
  );
};
