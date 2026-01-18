import './LanguageSelector.css';

interface LanguageSelectorProps {
  sourceLanguage: string;
  targetLanguage: string;
  onSourceChange: (lang: string) => void;
  onTargetChange: (lang: string) => void;
}

const LANGUAGES = [
  { code: 'en', name: 'Inglês' },
  { code: 'pt', name: 'Português' },
  { code: 'es', name: 'Espanhol' },
  { code: 'fr', name: 'Francês' },
  { code: 'de', name: 'Alemão' },
  { code: 'it', name: 'Italiano' },
  { code: 'ja', name: 'Japonês' },
  { code: 'ko', name: 'Coreano' },
  { code: 'zh', name: 'Chinês' },
  { code: 'ru', name: 'Russo' },
];

export const LanguageSelector = ({
  sourceLanguage,
  targetLanguage,
  onSourceChange,
  onTargetChange,
}: LanguageSelectorProps) => {
  return (
    <div className="language-selector">
      <div className="language-group">
        <label className="language-label">Idioma Original:</label>
        <select
          value={sourceLanguage}
          onChange={(e) => onSourceChange(e.target.value)}
          className="language-select"
        >
          {LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.name}
            </option>
          ))}
        </select>
      </div>
      
      <div className="language-arrow">→</div>
      
      <div className="language-group">
        <label className="language-label">Idioma de Tradução:</label>
        <select
          value={targetLanguage}
          onChange={(e) => onTargetChange(e.target.value)}
          className="language-select"
        >
          {LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
};
