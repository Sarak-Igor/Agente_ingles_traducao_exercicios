import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authApi, TokenResponse, UserProfile } from '../services/api';
import { storage } from '../services/storage';

interface User {
  id: string;
  username: string;
  email: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  loading: boolean;
  login: (email: string, rememberMe: boolean) => Promise<void>;
  register: (email: string, username: string, nativeLanguage?: string, learningLanguage?: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Verifica autenticação ao inicializar
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      setLoading(true);
      // Busca token de ambos storages
      const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
      
      if (!token) {
        setIsAuthenticated(false);
        setUser(null);
        setLoading(false);
        return;
      }

      // Verifica se o token é válido tentando buscar o perfil
      try {
        const profile = await authApi.getProfile();
        setIsAuthenticated(true);
        setUser({
          id: profile.id,
          username: profile.username,
          email: profile.email,
        });
      } catch (error) {
        // Token inválido ou expirado
        storage.clearAuthToken();
        setIsAuthenticated(false);
        setUser(null);
      }
    } catch (error) {
      console.error('Erro ao verificar autenticação:', error);
      setIsAuthenticated(false);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, rememberMe: boolean) => {
    try {
      const response: TokenResponse = await authApi.login({ email });
      
      // Salva token e informações do usuário
      if (rememberMe) {
        localStorage.setItem('auth_token', response.access_token);
        localStorage.setItem('user_id', response.user_id);
        localStorage.setItem('username', response.username);
      } else {
        sessionStorage.setItem('auth_token', response.access_token);
        sessionStorage.setItem('user_id', response.user_id);
        sessionStorage.setItem('username', response.username);
      }
      
      // Atualiza estado
      setIsAuthenticated(true);
      setUser({
        id: response.user_id,
        username: response.username,
        email: email,
      });
    } catch (error: any) {
      console.error('Erro ao fazer login:', error);
      throw error;
    }
  };

  const register = async (
    email: string,
    username: string,
    nativeLanguage: string = 'pt',
    learningLanguage: string = 'en'
  ) => {
    try {
      const response: TokenResponse = await authApi.register({
        email,
        username,
        native_language: nativeLanguage,
        learning_language: learningLanguage,
      });
      
      // Salva token e informações do usuário (sempre usa localStorage para registro)
      localStorage.setItem('auth_token', response.access_token);
      localStorage.setItem('user_id', response.user_id);
      localStorage.setItem('username', response.username);
      
      // Atualiza estado
      setIsAuthenticated(true);
      setUser({
        id: response.user_id,
        username: response.username,
        email: email,
      });
    } catch (error: any) {
      console.error('Erro ao registrar:', error);
      throw error;
    }
  };

  const logout = () => {
    // Limpa ambos localStorage e sessionStorage
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('username');
    sessionStorage.removeItem('auth_token');
    sessionStorage.removeItem('user_id');
    sessionStorage.removeItem('username');
    
    // Limpa chaves de API do localStorage (agora são salvas no backend por usuário)
    localStorage.removeItem('gemini_api_key');
    localStorage.removeItem('openrouter_api_key');
    localStorage.removeItem('groq_api_key');
    localStorage.removeItem('together_api_key');
    
    setIsAuthenticated(false);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        user,
        loading,
        login,
        register,
        logout,
        checkAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
