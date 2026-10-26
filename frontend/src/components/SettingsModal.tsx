import { useState, useEffect } from 'react';

export default function SettingsModal({ onClose }: { onClose: () => void }) {
  const [settings, setSettings] = useState({
    active_provider: 'databricks',
    databricks_host: '',
    databricks_model: 'databricks-meta-llama-3-3-70b-instruct',
    databricks_token: '',
    openai_api_key: '',
    anthropic_api_key: '',
    groq_api_key: ''
  });

  useEffect(() => {
    fetch('http://localhost:8000/api/settings')
      .then(res => res.json())
      .then(data => {
        if (data && Object.keys(data).length > 0) {
          setSettings(prev => ({ ...prev, ...data }));
        }
      })
      .catch(err => console.error(err));
  }, []);

  const handleSave = async () => {
    try {
      await fetch('http://localhost:8000/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      onClose();
    } catch (err) {
      console.error("Failed to save settings", err);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="glass-panel modal-content" onClick={e => e.stopPropagation()}>
        <h2 style={{ marginBottom: '20px' }}>Settings</h2>
        
        <div className="input-group">
          <label>Active Provider</label>
          <select 
            value={settings.active_provider} 
            onChange={e => setSettings({...settings, active_provider: e.target.value})}
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="groq">Groq</option>
            <option value="databricks">Databricks</option>
          </select>
        </div>

        {settings.active_provider === 'databricks' && (
          <>
            <div className="input-group">
              <label>Databricks Host</label>
              <input type="text" value={settings.databricks_host} onChange={e => setSettings({...settings, databricks_host: e.target.value})} placeholder="https://adb-..." />
            </div>
            <div className="input-group">
              <label>Databricks Model / Endpoint</label>
              <input type="text" value={settings.databricks_model} onChange={e => setSettings({...settings, databricks_model: e.target.value})} placeholder="e.g. databricks-meta-llama-3-3-70b-instruct" />
            </div>
            <div className="input-group">
              <label>Databricks Token</label>
              <input type="password" value={settings.databricks_token} onChange={e => setSettings({...settings, databricks_token: e.target.value})} />
            </div>
          </>
        )}

        {settings.active_provider === 'openai' && (
          <div className="input-group">
            <label>OpenAI API Key</label>
            <input type="password" value={settings.openai_api_key} onChange={e => setSettings({...settings, openai_api_key: e.target.value})} />
          </div>
        )}

        {settings.active_provider === 'anthropic' && (
          <div className="input-group">
            <label>Anthropic API Key</label>
            <input type="password" value={settings.anthropic_api_key} onChange={e => setSettings({...settings, anthropic_api_key: e.target.value})} />
          </div>
        )}
        
        {settings.active_provider === 'groq' && (
          <div className="input-group">
            <label>Groq API Key</label>
            <input type="password" value={settings.groq_api_key} onChange={e => setSettings({...settings, groq_api_key: e.target.value})} />
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={handleSave}>Save</button>
        </div>
      </div>
    </div>
  );
}
