import { useState, useEffect } from 'react';
import LeftSidebar from './components/LeftSidebar';
import CenterPanel, { EditorTab } from './components/CenterPanel';
import RightSidebar from './components/RightSidebar';
import SettingsModal from './components/SettingsModal';
import AnimatedBackground from './components/AnimatedBackground';
import SemanticModelView from './components/SemanticModelView';
import SplashScreen from './components/SplashScreen';
import { Settings as SettingsIcon, Palette, Network, TerminalSquare, Sparkles } from 'lucide-react';

// Custom Resize Handle Component
function ResizeHandle({ onResize }: { onResize: (delta: number) => void }) {
  const [isDragging, setIsDragging] = useState(false);
  
  useEffect(() => {
    if (!isDragging) return;
    
    const handleMouseMove = (e: MouseEvent) => {
      onResize(e.movementX);
    };
    
    const handleMouseUp = () => {
      setIsDragging(false);
    };
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, onResize]);
  
  return (
    <div 
      onMouseDown={() => setIsDragging(true)}
      style={{ 
        width: '16px', 
        cursor: 'col-resize', 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center',
        zIndex: 10,
        backgroundColor: isDragging ? 'rgba(255,255,255,0.05)' : 'transparent',
      }}
    >
      <div style={{ width: '2px', height: '30px', backgroundColor: 'var(--border-color)', borderRadius: '2px' }} />
    </div>
  );
}

function App() {
  const [theme, setTheme] = useState('light');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isLeftSidebarOpen] = useState(true);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(true);
  
  // Custom widths
  const [leftWidth, setLeftWidth] = useState(300);
  const [rightWidth, setRightWidth] = useState(500);
  
  // Activity bar tab: 'data', 'model'
  const [activeTab, setActiveTab] = useState<'data' | 'model'>('data');
  const [refreshSchemaTrigger, setRefreshSchemaTrigger] = useState(0);
  const [isAppLoading, setIsAppLoading] = useState(true);

  // ── Tab-based editor state ──
  const [editorTabs, setEditorTabs] = useState<EditorTab[]>([]);
  const [activeEditorTabId, setActiveEditorTabId] = useState<string | null>(null);

  // Derived: is any editor tab open?
  const isCenterPanelOpen = editorTabs.length > 0;

  useEffect(() => {
    if (isCenterPanelOpen) {
      setRightWidth(500);
    }
  }, [isCenterPanelOpen]);

  // Derived: pending proposal info (for left sidebar highlight)
  const pendingProposal = editorTabs.find(t => t.activeProposal?.status === 'pending')?.activeProposal ?? null;
  const isRelationshipProposal = pendingProposal && ['relationship_operations', 'create_relationship', 'relationship_create'].includes(pendingProposal.tool);

  
  const pendingItemName = pendingProposal && !isRelationshipProposal
    ? (pendingProposal.args?.definitions?.[0]?.name ||
       pendingProposal.args?.request?.definitions?.[0]?.name ||
       pendingProposal.args?.request?.references?.[0]?.name ||
       pendingProposal.args?.name ||
       pendingProposal.args?.Name ||
       pendingProposal.args?.measureName || null)
    : null;

  const pendingItemTable = pendingProposal && !isRelationshipProposal
    ? (pendingProposal.args?.definitions?.[0]?.tableName ||
       pendingProposal.args?.request?.definitions?.[0]?.tableName ||
       pendingProposal.args?.request?.references?.[0]?.tableName ||
       pendingProposal.args?.tableName ||
       pendingProposal.args?.TableName || null)
    : null;

  const pendingTool = pendingProposal ? pendingProposal.tool : null;
  const pendingOperation = pendingProposal ? (pendingProposal.args?.operation || pendingProposal.args?.request?.operation || pendingProposal.operation || null) : null;


  let activeItemName = null;
  let activeItemTable = null;
  if (activeEditorTabId) {
    if (activeEditorTabId.startsWith('measure:')) {
      const parts = activeEditorTabId.replace('measure:', '').split(':');
      activeItemTable = parts[0];
      activeItemName = parts.slice(1).join(':');
    } else if (activeEditorTabId.startsWith('table:')) {
      activeItemName = activeEditorTabId.replace('table:', '');
    }
  }

  const [schema, setSchema] = useState<any>(null);
  const [roles, setRoles] = useState<any[]>([]);

  // ── Generation Preview State ──
  const [previewSchema, setPreviewSchema] = useState<any>(null);
  const [generationFolderPath, setGenerationFolderPath] = useState<string>('');
  const [isPushing, setIsPushing] = useState(false);
  const [appNotification, setAppNotification] = useState<{message: string, type: 'error'|'success'} | null>(null);

  const handlePushPreview = async () => {
    if (!previewSchema || !generationFolderPath) return;
    setIsPushing(true);
    try {
      const res = await fetch('http://localhost:8000/api/generate/push', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_schema: previewSchema, folder_path: generationFolderPath })
      });
      const data = await res.json();
      if (data.status === 'success') {
        setAppNotification({ message: 'Model pushed successfully!', type: 'success' });
        setTimeout(() => setAppNotification(null), 3000);
        setPreviewSchema(null);
        setRefreshSchemaTrigger(prev => prev + 1);
        refreshSchema();
      } else {
        setAppNotification({ message: `Error: ${data.message}`, type: 'error' });
        setTimeout(() => setAppNotification(null), 4000);
      }
    } catch (err) {
      setAppNotification({ message: `Error: ${err}`, type: 'error' });
      setTimeout(() => setAppNotification(null), 4000);
    } finally {
      setIsPushing(false);
    }
  };

  const cancelPreview = () => {
    setPreviewSchema(null);
  };

  const refreshSchema = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/schema?t=${Date.now()}`);
      const result = await response.json();
      if (result.status === 'success') setSchema(result.data);
    } catch (error) {
      console.error('Failed to refresh semantic model', error);
    }
  };

  useEffect(() => {
    const initApp = async () => {
      try {
        await refreshSchema();
      } catch (err) {
        console.error('Initial load failed', err);
      } finally {
        setIsAppLoading(false);
      }
    };
    initApp();
  }, []);

  // ── Tab helpers ──
  const openOrFocusTab = (tabId: string, tabData: Omit<EditorTab, 'id'>) => {
    setEditorTabs(prev => {
      const existing = prev.find(t => t.id === tabId);
      if (existing) return prev;
      return [...prev, { id: tabId, ...tabData }];
    });
    setActiveEditorTabId(tabId);
    if (activeTab !== 'data') setActiveTab('data');
  };

  const updateTab = (tabId: string, updates: Partial<EditorTab>) => {
    setEditorTabs(prev => prev.map(t => t.id === tabId ? { ...t, ...updates } : t));
  };

  const openQueryTab = () => {
    const tabId = 'query:dax-studio';
    openOrFocusTab(tabId, {
      title: 'DAX Studio',
      code: '// Write your DAX query here',
      language: 'dax',
      icon: 'measure',
    });
  };



  const runQuery = async (tab: EditorTab) => {
    updateTab(tab.id, { code: tab.code, isRunning: true, queryResult: undefined });
    try {
      const response = await fetch('http://localhost:8000/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: tab.code }),
      });
      const result = await response.json();
      if (!response.ok || result.status !== 'success') {
        updateTab(tab.id, { isRunning: false, queryResult: { columns: [], rows: [], rowCount: 0, error: result.message || 'Query execution failed' } });
        return;
      }
      updateTab(tab.id, { isRunning: false, queryResult: result.data });
    } catch (error) {
      updateTab(tab.id, { isRunning: false, queryResult: { columns: [], rows: [], rowCount: 0, error: error instanceof Error ? error.message : 'Query execution failed' } });
    }
  };

  const closeTab = (tabId: string) => {
    setEditorTabs(prev => {
      const remaining = prev.filter(t => t.id !== tabId);
      if (activeEditorTabId === tabId) {
        setActiveEditorTabId(remaining.length > 0 ? remaining[remaining.length - 1].id : null);
      }
      return remaining;
    });
  };

  // ── Measure click: open/focus tab ──
  const handleMeasureClick = async (tableName: string, measureName: string) => {
    const tabId = `measure:${tableName}:${measureName}`;
    openOrFocusTab(tabId, {
      title: measureName,
      code: `// Fetching ${measureName}...`,
      language: 'dax',
      icon: 'measure',
    });
    try {
      const res = await fetch(`http://localhost:8000/api/measure/${encodeURIComponent(tableName)}/${encodeURIComponent(measureName)}`);
      const data = await res.json();
      updateTab(tabId, { code: data.status === 'success' ? (data.data.expression || '// No expression found') : `// Error: ${data.message}` });
    } catch (err) {
      updateTab(tabId, { code: `// Error fetching measure: ${err}` });
    }
  };

  // ── Role click: open/focus tab ──
  const handleRoleClick = (roleName: string, tableName: string, dax: string) => {
    const tabId = `role:${roleName}:${tableName}`;
    openOrFocusTab(tabId, { title: `${roleName} – ${tableName}`, code: dax, language: 'dax', icon: 'role' });
  };

  // ── Table click: open/focus tab ──
  const handleTableClick = async (tableName: string) => {
    const tabId = `table:${tableName}`;
    openOrFocusTab(tabId, {
      title: tableName,
      code: `// Fetching definition for ${tableName}...`,
      language: 'tmdl',
      icon: 'table',
      altLanguage: 'powerquery',
      altLabel: 'M-Code',
      primaryLabel: 'TMDL',
    });
    try {
      const [tmdlRes, mcodeRes] = await Promise.all([
        fetch(`http://localhost:8000/api/table/${encodeURIComponent(tableName)}/tmdl`),
        fetch(`http://localhost:8000/api/table/${encodeURIComponent(tableName)}/mcode`),
      ]);
      const tmdlData = await tmdlRes.json();
      const mcodeData = await mcodeRes.json();
      updateTab(tabId, {
        code: tmdlData.status === 'success' ? (tmdlData.data || '// No TMDL found') : `// Error: ${tmdlData.message}`,
        altCode: mcodeData.status === 'success' ? mcodeData.data : undefined,
        altLabel: mcodeData.status === 'success' ? 'M-Code' : undefined,
        primaryLabel: mcodeData.status === 'success' ? 'TMDL' : undefined,
      });
    } catch (err) {
      updateTab(tabId, { code: `// Error fetching table: ${err}` });
    }
  };

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // ── Open a proposal tab automatically ──
  const handleProposalReceived = async (prop: any) => {
    const isMeasure = prop.tool === 'measure_operations';
    const isRelationship = prop.tool === 'relationship_operations' || prop.tool === 'relationship_create' || prop.tool === 'create_relationship';
    const operation = prop.args?.request?.operation || prop.args?.operation || '';
    const firstDef = (prop.args?.request?.definitions || [])[0] || (prop.args?.request?.permissionDefinitions || [])[0] || {};
    const firstRef = (prop.args?.request?.references || [])[0] || (prop.args?.request?.permissionReferences || [])[0] || {};
    const req = prop.args?.request || {};
    
    // Look for name/tableName in definitions, then references, then root args
    const relTitle = isRelationship && firstDef.fromTable
      ? (firstDef.fromColumn || firstDef.toColumn
        ? `${firstDef.fromTable}.${firstDef.fromColumn || '?'} ↔ ${firstDef.toTable}.${firstDef.toColumn || '?'}`
        : `${firstDef.fromTable} ↔ ${firstDef.toTable}`)
      : null;
    const name = relTitle ||
                 (firstDef.name || firstDef.Name || firstDef.roleName ||
                  firstRef.name || firstRef.Name || firstRef.roleName ||
                  req.name || req.Name || req.roleName ||
                  prop.args?.name || prop.args?.Name || prop.args?.roleName ||
                  prop.args?.measureName || 'Unknown');
                 
    const tableName = firstDef.tableName || firstDef.TableName || 
                      firstRef.tableName || firstRef.TableName || 
                      req.tableName || req.TableName ||
                      prop.args?.tableName || prop.args?.TableName || '';

    const tabId = `proposal:${prop.id}`;
    let originalCode = '';
    // The new DAX/M expression being proposed
    let proposedExpression = firstDef.mExpression || firstDef.MExpression || firstDef.expression || firstDef.Expression || firstDef.filterExpression || req.expression || prop.args?.expression || '';
    if (!isMeasure && firstDef.partitions && firstDef.partitions.length > 0) {
      const source = firstDef.partitions[0].source;
      if (source && source.expression) {
        proposedExpression = source.expression;
      }
    }

    if (isMeasure && operation === 'Update' && tableName && name) {
      try {
        const res = await fetch(`http://localhost:8000/api/measure/${encodeURIComponent(tableName)}/${encodeURIComponent(name)}`);
        const data = await res.json();
        if (data.status === 'success') originalCode = data.data.expression || '';
      } catch (_) {}
    } else if (isRelationship) {
      setActiveTab('model');
      return;
    }

    // For Create, show the proposed expression. For Update, show proposed (new) expression.
    const editorCode = proposedExpression || originalCode;

    const tab: EditorTab = {
      id: tabId,
      title: name,
      code: editorCode,
      language: isMeasure ? 'dax' : 'tmdl',
      icon: isMeasure ? 'measure' : 'table',
      activeProposal: { ...prop, original_state: originalCode || undefined },
    };

    setEditorTabs(prev => {
      const existing = prev.find(t => t.id === tabId);
      if (existing) return prev;
      return [...prev, tab];
    });
    setActiveEditorTabId(tabId);
    if (activeTab !== 'data') setActiveTab('data');
    setRefreshSchemaTrigger(prev => prev + 1);
  };

  const handleGenerationPreview = (data: any) => {
    setPreviewSchema(data.schema);
    setGenerationFolderPath(data.folder_path);
    setActiveTab('model');
  };

  const isCenterVisible = activeTab !== 'data' || isCenterPanelOpen;

  const themes = ['light', 'dark', 'ocean', 'midnight', 'purple'];
  const [showThemeSelector, setShowThemeSelector] = useState(false);

  return (
    <div className="app-container" style={{ padding: '16px' }}>
      <SplashScreen isLoading={isAppLoading} />
      <AnimatedBackground theme={theme} />
      {appNotification && (
        <div style={{ position: 'fixed', top: 20, left: '50%', transform: 'translateX(-50%)', zIndex: 9999, background: appNotification.type === 'error' ? '#ef4444' : '#10b981', color: '#fff', padding: '12px 24px', borderRadius: 30, fontSize: 13, fontWeight: 600, boxShadow: '0 8px 30px rgba(0,0,0,0.2)', animation: 'fadeIn 0.2s ease-out', maxWidth: '80%', textAlign: 'center' }}>
          {appNotification.message}
        </div>
      )}
      
      {/* Activity Bar (Far Left) */}
      <div className="glass-panel" style={{ 
        width: '64px', 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        paddingTop: '16px', 
        paddingBottom: '16px', 
        gap: '8px', 
        zIndex: 10, 
        flexShrink: 0,
        border: '1px solid rgba(242, 200, 17, 0.15)',
        boxShadow: '0 0 20px rgba(218, 165, 32, 0.8)' // Darker goldenrod glow
      }}>
        <button 
          onClick={() => {
            if (activeTab === 'model') {
              setActiveTab('data');
              if (!isCenterPanelOpen && !isRightSidebarOpen) {
                setIsRightSidebarOpen(true);
              }
            } else {
              setActiveTab('model');
            }
          }} 
          title="Semantic Model View" 
          style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: activeTab === 'model' ? 'var(--accent-color)' : 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '8px', marginBottom: '8px' }}
        >
          <Network size={24} />
        </button>

        <div style={{ width: '20px', height: '1px', backgroundColor: 'rgba(255, 255, 255, 0.1)', marginBottom: '8px' }} />

        <button 
          onClick={() => {
            if (activeTab !== 'data') setActiveTab('data');
            // Toggle: if tabs are open, close them all; otherwise open explorer
            if (isCenterPanelOpen) {
              setEditorTabs([]);
              setActiveEditorTabId(null);
              if (!isRightSidebarOpen) {
                setIsRightSidebarOpen(true);
              }
            } else {
              openQueryTab();
            }
          }} 
          title="Toggle Code Editor" 
          style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: (activeTab === 'data' && isCenterPanelOpen) ? 'var(--accent-color)' : 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '8px', marginBottom: '8px' }}
        >
          <TerminalSquare size={24} />
        </button>

        <div style={{ width: '20px', height: '1px', backgroundColor: 'rgba(255, 255, 255, 0.1)', marginBottom: '8px' }} />

        <button 
          onClick={() => {
            const isCenterVisible = activeTab === 'model' || isCenterPanelOpen;
            if (isRightSidebarOpen && !isCenterVisible) {
              // Prevent closing assistant if no center panel is open
              return;
            }
            setIsRightSidebarOpen(!isRightSidebarOpen);
          }} 
          title={(!isCenterPanelOpen && activeTab !== 'model') ? "Assistant cannot be closed while center panel is empty" : "Toggle Assistant"} 
          style={{ background: 'transparent', border: 'none', cursor: (!isCenterPanelOpen && activeTab !== 'model' && isRightSidebarOpen) ? 'not-allowed' : 'pointer', color: isRightSidebarOpen ? 'var(--accent-color)' : 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '8px', opacity: (!isCenterPanelOpen && activeTab !== 'model' && isRightSidebarOpen) ? 0.5 : 1 }}
        >
          <Sparkles size={24} />
        </button>
        
        <div style={{ flexGrow: 1 }} />
        
        <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%' }}>
          {showThemeSelector && (
            <div className="glass-panel" style={{ position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: '8px', padding: '8px', display: 'flex', flexDirection: 'column', gap: '8px', animation: 'fadeIn 0.2s', zIndex: 60 }}>
              {themes.map(t => (
                <button 
                  key={t}
                  onClick={() => { setTheme(t); setShowThemeSelector(false); }}
                  title={t.charAt(0).toUpperCase() + t.slice(1)}
                  style={{
                    width: '24px', height: '24px', borderRadius: '50%', cursor: 'pointer',
                    border: theme === t ? '2px solid var(--accent-color)' : '2px solid transparent',
                    background: t === 'light' ? '#e0f2fe' : t === 'dark' ? '#1e293b' : t === 'ocean' ? '#14b8a6' : t === 'midnight' ? '#3730a3' : '#ec4899',
                    boxShadow: theme === t ? '0 0 10px var(--accent-color)' : 'none',
                    transition: 'all 0.2s'
                  }}
                />
              ))}
            </div>
          )}
          <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', marginBottom: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '8px' }} onClick={() => setShowThemeSelector(!showThemeSelector)}>
            <Palette size={24} />
          </button>
        </div>
        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '8px' }} onClick={() => setIsSettingsOpen(true)}>
          <SettingsIcon size={24} />
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'row', flexGrow: 1, width: '100%', height: '100%', overflow: 'hidden' }}>
        {isLeftSidebarOpen ? (
          <div style={{ width: leftWidth, minWidth: 150, maxWidth: 800, flexShrink: 0, display: 'block' }}>
              <LeftSidebar 
                roles={roles}
                onMeasureClick={handleMeasureClick} 
                onTableClick={handleTableClick}
                onRoleClick={handleRoleClick}
                onSchemaLoaded={setSchema}
                onRolesLoaded={setRoles}
                pendingItemName={pendingItemName}
                pendingItemTable={pendingItemTable}
                pendingTool={pendingTool}
                pendingOperation={pendingOperation}
                activeItemName={activeItemName}
                activeItemTable={activeItemTable}
                refreshSchemaTrigger={refreshSchemaTrigger}
              />
          </div>
        ) : null}
        
        {isLeftSidebarOpen ? (
          <ResizeHandle onResize={(delta) => setLeftWidth(w => Math.max(150, Math.min(800, w + delta)))} />
        ) : null}

        {isCenterVisible && (
          <div style={{ flexGrow: 1, minWidth: 300, display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
            {activeTab === 'data' && (
              <CenterPanel
                theme={theme}
                tabs={editorTabs}
                activeTabId={activeEditorTabId}
                onTabChange={setActiveEditorTabId}
                onTabClose={closeTab}
                onCodeChange={(id, code) => updateTab(id, { code, isDirty: true })}
                onNewQuery={openQueryTab}
                onRunQuery={runQuery}
                onSave={async (tab) => {
                  const isMeasureTab = tab.id.startsWith('measure:');
                  const isTableTab = tab.id.startsWith('table:');
                  const isRoleTab = tab.id.startsWith('role:');
                  if (isMeasureTab) {
                    const parts = tab.id.replace('measure:', '').split(':');
                    const tName = parts[0];
                    const mName = parts.slice(1).join(':');
                    const res = await fetch(`http://localhost:8000/api/measure/${encodeURIComponent(tName)}/${encodeURIComponent(mName)}`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ expression: tab.code }),
                    });
                    const data = await res.json();
                    if (data.status !== 'success') alert('Failed to save: ' + (data.message || 'Unknown error'));
                    else updateTab(tab.id, { isDirty: false });
                  } else if (isTableTab) {
                    const name = tab.id.replace('table:', '');
                    const res = await fetch(`http://localhost:8000/api/table/${encodeURIComponent(name)}`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ content: tab.code, type: 'tmdl' }),
                    });
                    const data = await res.json();
                    if (data.status !== 'success') alert('Failed to save: ' + (data.message || 'Unknown error'));
                    else updateTab(tab.id, { isDirty: false });
                  } else if (isRoleTab) {
                    const parts = tab.id.replace('role:', '').split(':');
                    const rName = parts[0];
                    const tName = parts.slice(1).join(':');
                    const res = await fetch(`http://localhost:8000/api/role/${encodeURIComponent(rName)}/${encodeURIComponent(tName)}`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ dax: tab.code }),
                    });
                    const data = await res.json();
                    if (data.status !== 'success') alert('Failed to save role: ' + (data.message || 'Unknown error'));
                    else {
                      updateTab(tab.id, { isDirty: false });
                      setRefreshSchemaTrigger(prev => prev + 1);
                    }
                  }
                }}
              />
            )}
            {activeTab === 'model' && (
              <div style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}>
                <SemanticModelView 
                  schema={previewSchema || schema} 
                  isPreview={!!previewSchema}
                  isPushing={isPushing}
                  onPush={handlePushPreview}
                  onCancelPreview={cancelPreview}
                  onRelationshipCreated={() => {
                    setRefreshSchemaTrigger(prev => prev + 1);
                    refreshSchema();
                  }} 
                />
              </div>
            )}
          </div>
        )}

        {(isRightSidebarOpen && isCenterVisible) ? (
          <ResizeHandle onResize={(delta) => setRightWidth(w => Math.max(200, Math.min(800, w - delta)))} />
        ) : null}

        <div style={{ 
          width: isCenterVisible ? rightWidth : 0, 
          minWidth: isCenterVisible ? 200 : 0, 
          maxWidth: isCenterVisible ? 800 : 'none', 
          flexShrink: 0, 
          flexGrow: isCenterVisible ? 0 : 1,
          display: isRightSidebarOpen ? 'block' : 'none'
        }}>
            <div style={{ position: 'relative', width: '100%', height: '100%' }}>
              <RightSidebar 
                onProposalReceived={handleProposalReceived}
                onProposalAction={(action, id, proposal) => {
                  if (action === 'accept' || action === 'reject') {
                    setRefreshSchemaTrigger(prev => prev + 1);
                    if (action === 'accept' && proposal) {
                      const isMeasure = proposal.tool === 'measure_operations';
                      const firstDef = (proposal.args?.request?.definitions || [])[0] || {};
                      const firstRef = (proposal.args?.request?.references || [])[0] || {};
                      const req = proposal.args?.request || {};
                      const name = firstDef.name || firstDef.Name || firstRef.name || firstRef.Name || req.name || req.Name || proposal.args?.name || proposal.args?.Name || proposal.args?.measureName || '';
                      const tableName = firstDef.tableName || firstDef.TableName || firstRef.tableName || firstRef.TableName || req.tableName || req.TableName || proposal.args?.tableName || proposal.args?.TableName || '';
                      
                      if (name && tableName && isMeasure) {
                        setTimeout(() => handleMeasureClick(tableName, name), 100);
                      } else if (name && !isMeasure) {
                        setTimeout(() => handleTableClick(name), 100);
                      }
                    }
                    closeTab(`proposal:${id}`);
                  }
                }}
                onGenerationPreviewReceived={handleGenerationPreview}
              />
            </div>
          </div>
        </div>

      {isSettingsOpen && <SettingsModal onClose={() => setIsSettingsOpen(false)} />}
    </div>
  );
}

export default App;
