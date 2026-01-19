import { useState, FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import './Register.css';

const LANGUAGES = [
  { code: 'pt', name: 'Português' },
  { code: 'en', name: 'Inglês' },
  { code: 'es', name: 'Espanhol' },
  { code: 'fr', name: 'Francês' },
  { code: 'de', name: 'Alemão' },
  { code: 'it', name: 'Italiano' },
  { code: 'ja', name: 'Japonês' },
  { code: 'ko', name: 'Coreano' },
  { code: 'zh', name: 'Chinês' },
  { code: 'ru', name: 'Russo' },
];

export const Register = () => {
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [nativeLanguage, setNativeLanguage] = useState('pt');
  const [learningLanguage, setLearningLanguage] = useState('en');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validações
    if (!email.trim()) {
      setError('Por favor, informe seu email.');
      return;
    }

    if (!validateEmail(email)) {
      setError('Por favor, informe um email válido.');
      return;
    }

    if (!username.trim()) {
      setError('Por favor, informe um nome de usuário.');
      return;
    }

    if (username.length < 3) {
      setError('O nome de usuário deve ter no mínimo 3 caracteres.');
      return;
    }

    if (nativeLanguage === learningLanguage) {
      setError('O idioma nativo e o idioma de aprendizado devem ser diferentes.');
      return;
    }

    try {
      setLoading(true);
      await register(email, username, nativeLanguage, learningLanguage);
      navigate('/app');
    } catch (error: any) {
      console.error('Erro ao registrar:', error);
      const errorMessage = error.response?.data?.detail || 'Erro ao criar conta. Tente novamente.';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="register-container">
      <div className="register-card">
        <div className="register-header">
          <h1>🎵 Tradução de Vídeos</h1>
          <h2>Criar Conta</h2>
          <p>Preencha os dados para começar</p>
        </div>

        <form onSubmit={handleSubmit} className="register-form">
          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="seu@email.com"
              disabled={loading}
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="username">Nome de Usuário</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="seu_usuario"
              disabled={loading}
              autoComplete="username"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="nativeLanguage">Idioma Nativo</label>
              <select
                id="nativeLanguage"
                value={nativeLanguage}
                onChange={(e) => setNativeLanguage(e.target.value)}
                disabled={loading}
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="learningLanguage">Idioma de Aprendizado</label>
              <select
                id="learningLanguage"
                value={learningLanguage}
                onChange={(e) => setLearningLanguage(e.target.value)}
                disabled={loading}
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            type="submit"
            className="register-button"
            disabled={loading}
          >
            {loading ? 'Criando conta...' : 'Criar Conta'}
          </button>
        </form>

        <div className="register-footer">
          <p>
            Já tem uma conta?{' '}
            <Link to="/login" className="link">
              Faça login
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};
