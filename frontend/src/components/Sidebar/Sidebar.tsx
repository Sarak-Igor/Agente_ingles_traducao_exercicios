import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import './Sidebar.css';

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export const Sidebar = ({ activeTab, onTabChange }: SidebarProps) => {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  
  const tabs = [
    { id: 'translate', label: 'Traduzir', icon: '🎵' },
    { id: 'videos', label: 'Meus Vídeos', icon: '📹' },
    { id: 'practice', label: 'Treinar Inglês', icon: '📚' },
    { id: 'chat', label: 'Chat', icon: '💬' },
    { id: 'api-keys', label: 'Modelos LLM', icon: '🔑' },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>🎵 Tradução de Vídeos</h2>
      </div>
      <nav className="sidebar-nav">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`sidebar-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => onTabChange(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-footer">
        {user && (
          <div className="sidebar-user">
            <div className="user-info">
              <span className="user-icon">👤</span>
              <span className="user-name" title={user.email}>
                {user.username}
              </span>
            </div>
            <button
              className="logout-button"
              onClick={handleLogout}
              title="Sair / Trocar Usuário"
            >
              🚪 Sair
            </button>
          </div>
        )}
        <button className="theme-toggle" onClick={toggleTheme} title={theme === 'light' ? 'Ativar tema escuro' : 'Ativar tema claro'}>
          {theme === 'light' ? '🌙' : '☀️'}
          <span className="tab-label">Tema {theme === 'light' ? 'Escuro' : 'Claro'}</span>
        </button>
      </div>
    </aside>
  );
};
