import Editor, { DiffEditor } from '@monaco-editor/react';
import { useRef, useState, useEffect } from 'react';
import { Code2, Save, X, Check, FileCode2, Table2 } from 'lucide-react';

export interface EditorTab {
  id: string;
  title: string;
  code: string;
  language: string;
  altCode?: string;
  altLanguage?: string;
  altLabel?: string;
  primaryLabel?: string;
  activeProposal?: any;
  isDirty?: boolean;
  icon?: 'measure' | 'table' | 'role';
  queryResult?: { columns: string[]; rows: Record<string, unknown>[]; rowCount: number; error?: string };
  isRunning?: boolean;
}

interface CenterPanelProps {
  theme?: string;
  tabs: EditorTab[];
  activeTabId: string | null;
  onTabChange: (id: string) => void;
  onTabClose: (id: string) => void;
  onCodeChange: (id: string, code: string) => void;
  onSave?: (tab: EditorTab) => Promise<void>;
  onRunQuery?: (tab: EditorTab) => Promise<void>;
  onNewQuery?: () => void;
}

// DAX Monarch tokenizer definition
const DAX_LANGUAGE_DEF = {
  ignoreCase: true,
  keywords: [
    'CALCULATE', 'CALCULATETABLE', 'SUM', 'SUMX', 'FILTER', 'ALL', 'ALLEXCEPT',
    'ALLSELECTED', 'ALLNOBLANKROW', 'VAR', 'RETURN', 'IF', 'IFERROR', 'SWITCH',
    'BLANK', 'ISBLANK', 'AVERAGE', 'AVERAGEX', 'AVERAGEA',
    'MIN', 'MINX', 'MINA', 'MAX', 'MAXX', 'MAXA',
    'COUNT', 'COUNTA', 'COUNTX', 'COUNTROWS', 'COUNTBLANK', 'DISTINCTCOUNT',
    'DIVIDE', 'EVALUATE', 'DEFINE', 'MEASURE', 'COLUMN', 'ORDER', 'BY', 'ASC', 'DESC',
    'FORMAT', 'TEXT', 'VALUE', 'INT', 'ROUND', 'ROUNDUP', 'ROUNDDOWN',
    'YEAR', 'MONTH', 'DAY', 'DATE', 'TODAY', 'NOW', 'DATEDIFF', 'DATEADD',
    'RELATED', 'RELATEDTABLE', 'LOOKUPVALUE',
    'TRUE', 'FALSE', 'NOT', 'AND', 'OR', 'IN',
    'HASONEVALUE', 'SELECTEDVALUE', 'EARLIER', 'EARLIEST',
    'RANKX', 'TOPN', 'GENERATE', 'GENERATEALL',
    'UNION', 'INTERSECT', 'EXCEPT', 'CROSSJOIN', 'ADDCOLUMNS', 'SELECTCOLUMNS',
    'SUMMARIZE', 'SUMMARIZECOLUMNS', 'GROUPBY', 'ROLLUP',
    'USERELATIONSHIP', 'CROSSFILTER', 'TREATAS',
    'VALUES', 'DISTINCT', 'DATATABLE', 'ROW', 'CONTAINS',
    'FIRSTDATE', 'LASTDATE', 'DATESYTD', 'DATESQTD', 'DATESMTD',
    'SAMEPERIODLASTYEAR', 'PREVIOUSYEAR', 'PREVIOUSQUARTER', 'PREVIOUSMONTH', 'PREVIOUSDAY',
    'TOTALYTD', 'TOTALQTD', 'TOTALMTD',
    'ABS', 'SQRT', 'POWER', 'MOD', 'QUOTIENT', 'CEILING', 'FLOOR', 'LEN',
    'LEFT', 'RIGHT', 'MID', 'CONCATENATE', 'CONCATENATEX', 'UPPER', 'LOWER', 'TRIM',
    'SUBSTITUTE', 'REPLACE', 'SEARCH', 'FIND', 'EXACT', 'REPT',
    'ISERROR', 'ISLOGICAL', 'ISNONTEXT', 'ISNUMBER', 'ISTEXT',
  ],
  tokenizer: {
    root: [
      [/(?:'[^']*'|[a-zA-Z_]\w*)\[[^\]]*\]/, 'type.identifier'],
      [/\[[^\]]*\]/, 'type.identifier'],
      [/'[^']*'/, 'string'],
      [/"[^"]*"/, 'string'],
      [/\/\/[^\n]*/, 'comment'],
      [/\/\*/, 'comment', '@blockComment'],
      [/\b\d+(\.\d+)?([eE][+-]?\d+)?\b/, 'number'],
      [/[a-zA-Z_]\w*/, {
        cases: {
          '@keywords': 'keyword',
          '@default': 'identifier',
        }
      }],
      [/[=<>!&|+\-*\/^%]+/, 'operator'],
      [/[(),;]/, 'delimiter'],
    ],
    blockComment: [
      [/[^/*]+/, 'comment'],
      [/\*\//, 'comment', '@pop'],
      [/[/*]/, 'comment'],
    ],
  },
};

let daxRegistered = false;

export default function CenterPanel({
  theme = 'dark',
  tabs,
  activeTabId,
  onTabChange,
  onTabClose,
  onCodeChange,
  onSave,
  onRunQuery,
  onNewQuery,
}: CenterPanelProps) {
  const [showAltMap, setShowAltMap] = useState<Record<string, boolean>>({});
  const [isSaving, setIsSaving] = useState(false);
  const monacoRef = useRef<any>(null);
  const editorRef = useRef<any>(null);

  const activeTab = tabs.find(t => t.id === activeTabId) ?? null;
  const showAlt = activeTab ? (showAltMap[activeTab.id] ?? false) : false;

  // Reset alt view when switching tabs
  useEffect(() => {
    if (activeTabId) setShowAltMap(prev => ({ ...prev, [activeTabId]: false }));
  }, [activeTabId]);

  const hasToggle = Boolean(activeTab?.altCode && activeTab?.altLabel && activeTab?.primaryLabel);
  const activeCode = activeTab ? (showAlt ? (activeTab.altCode ?? '') : activeTab.code) : '';
  const activeLanguage = activeTab ? (showAlt ? (activeTab.altLanguage ?? 'powerquery') : activeTab.language) : 'dax';

  // Diff view logic
  let originalDiffCode = '';
  let modifiedCode = activeCode;
  if (activeTab?.activeProposal) {
    const prop = activeTab.activeProposal;
    originalDiffCode = (prop.original_state !== undefined && prop.original_state !== null) ? prop.original_state : '';
    const firstDef = (prop.args?.request?.definitions || [])[0] || {};
    if (firstDef.expression !== undefined) modifiedCode = firstDef.expression;
    else if (firstDef.tmdl !== undefined) modifiedCode = firstDef.tmdl;
    else if (prop.args?.measure?.expression !== undefined) modifiedCode = prop.args.measure.expression;
    else if (prop.args?.tmdl !== undefined) modifiedCode = prop.args.tmdl;
    else if (prop.args?.expression !== undefined) modifiedCode = prop.args.expression;
  }

  const handleEditorDidMount = (editor: any, monaco: any) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    if (!daxRegistered) {
      monaco.languages.register({ id: 'dax', aliases: ['DAX', 'dax'] });
      monaco.languages.setMonarchTokensProvider('dax', DAX_LANGUAGE_DEF);
      daxRegistered = true;
    }
    const model = editor.getModel();
    if (model && activeLanguage === 'dax') monaco.editor.setModelLanguage(model, 'dax');
    if (activeTab?.id.startsWith('query:') && onRunQuery) {
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
        onRunQuery({ ...activeTab, code: editor.getValue() });
      });
    }
  };

  const handleSave = async () => {
    if (onSave && activeTab) {
      setIsSaving(true);
      try { await onSave(activeTab); } finally { setIsSaving(false); }
    }
  };

  // Empty state
  if (tabs.length === 0) {
    return (
      <div className="glass-panel center-panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '12px', color: 'var(--text-muted)' }}>
        <Code2 size={36} opacity={0.25} />
        <span style={{ fontSize: '0.9em' }}>Click a measure or table in the Explorer to open it</span>
        {onNewQuery && (
          <button className="btn-primary" onClick={onNewQuery} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            Open DAX Studio
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="glass-panel center-panel" style={{ display: 'flex', flexDirection: 'column' }}>

      {/* ── Tab Bar ── */}
      <div style={{
        display: 'flex', flexDirection: 'row', alignItems: 'stretch',
        borderBottom: '1px solid var(--border-color)',
        overflowX: 'auto', flexShrink: 0, minHeight: '36px',
        background: 'var(--bg-secondary)', borderRadius: '12px 12px 0 0',
      }}>
        {tabs.filter(tab => !tab.id.startsWith('query:')).map(tab => {
          const isActive = tab.id === activeTabId;
          const isProposal = !!tab.activeProposal;
          return (
            <div
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              title={tab.title}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '0 10px', cursor: 'pointer',
                maxWidth: '200px', minWidth: 0, flexShrink: 0,
                borderRight: '1px solid var(--border-color)',
                background: isActive ? 'var(--bg-main)' : 'transparent',
                borderBottom: isActive ? '2px solid var(--accent-color)' : '2px solid transparent',
                transition: 'background 0.15s',
              }}
            >
              {tab.icon === 'table'
                ? <Table2 size={12} style={{ flexShrink: 0, opacity: 0.7 }} />
                : <FileCode2 size={12} style={{ flexShrink: 0, color: isProposal ? 'var(--accent-color)' : undefined, opacity: isProposal ? 1 : 0.7 }} />
              }
              <span style={{
                fontSize: '12px', fontWeight: isActive ? 600 : 400,
                color: isActive ? 'var(--text-main)' : 'var(--text-muted)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '130px',
              }}>
                {tab.title}
              </span>
              {isProposal && (
                <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--accent-color)', flexShrink: 0 }} />
              )}
              <button
                onClick={e => { e.stopPropagation(); onTabClose(tab.id); }}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '2px', borderRadius: '3px', display: 'flex', alignItems: 'center', flexShrink: 0 }}
                title="Close"
              >
                <X size={11} />
              </button>
            </div>
          );
        })}
        {onNewQuery && (
          <button
            onClick={onNewQuery}
            title="Open DAX Studio"
            style={{
              margin: '0 8px 0 auto',
              padding: '0 14px',
              height: '36px',
              border: 'none',
              borderLeft: '1px solid var(--border-color)',
              borderBottom: activeTabId?.startsWith('query:') ? '2px solid var(--accent-color)' : '2px solid transparent',
              background: activeTabId?.startsWith('query:') ? 'var(--bg-main)' : 'transparent',
              color: activeTabId?.startsWith('query:') ? 'var(--text-main)' : 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: activeTabId?.startsWith('query:') ? 600 : 400,
              flexShrink: 0
            }}
          >
            DAX Studio
          </button>
        )}
      </div>

      {/* ── Panel Header ── */}
      {activeTab && (
        <div className="panel-header" style={{ borderTop: 'none', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Code2 size={18} />
            <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              {activeTab.activeProposal ? 'Proposal Review' : (activeTab.id.startsWith('query:') ? 'DAX Query' : (activeTab.language === 'dax' ? 'DAX Editor' : 'TMDL Editor'))}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {hasToggle && (
              <div style={{ display: 'flex', borderRadius: '20px', overflow: 'hidden', border: '1px solid var(--border-color)', background: 'var(--bg-secondary)' }}>
                <button onClick={() => setShowAltMap(prev => ({ ...prev, [activeTab.id]: false }))}
                  style={{ padding: '4px 14px', fontSize: '12px', fontWeight: 600, border: 'none', cursor: 'pointer', borderRadius: '20px 0 0 20px', background: !showAlt ? 'var(--accent-color)' : 'transparent', color: !showAlt ? '#fff' : 'var(--text-secondary)', transition: 'all 0.2s' }}>
                  {activeTab.primaryLabel}
                </button>
                <button onClick={() => setShowAltMap(prev => ({ ...prev, [activeTab.id]: true }))}
                  style={{ padding: '4px 14px', fontSize: '12px', fontWeight: 600, border: 'none', cursor: 'pointer', borderRadius: '0 20px 20px 0', background: showAlt ? 'var(--accent-color)' : 'transparent', color: showAlt ? '#fff' : 'var(--text-secondary)', transition: 'all 0.2s' }}>
                  {activeTab.altLabel}
                </button>
              </div>
            )}
            
            {activeTab.activeProposal && (
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="btn-secondary"
                  onClick={() => window.dispatchEvent(new CustomEvent('proposal-action', { detail: { id: activeTab.activeProposal!.id, action: 'reject' } }))}
                  style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.5)', color: '#ef4444', padding: '4px 12px', fontSize: '12px', display: 'flex', gap: '4px', alignItems: 'center', borderRadius: '4px', cursor: 'pointer', fontWeight: 600 }}>
                  <X size={14} /> Reject
                </button>
                <button className="btn-primary"
                  onClick={() => window.dispatchEvent(new CustomEvent('proposal-action', { detail: { id: activeTab.activeProposal!.id, action: 'accept' } }))}
                  style={{ background: 'var(--accent-color)', color: '#ffffff', border: 'none', padding: '4px 12px', fontSize: '12px', display: 'flex', gap: '4px', alignItems: 'center', borderRadius: '4px', cursor: 'pointer', fontWeight: 600 }}>
                  <Check size={14} /> Accept
                </button>
              </div>
            )}
            
            {onSave && !activeTab.activeProposal && (
              !activeTab.id.startsWith('query:') && (
              <button onClick={handleSave} disabled={isSaving}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 12px', background: 'var(--accent-color)', color: '#fff', border: 'none', borderRadius: '4px', cursor: isSaving ? 'not-allowed' : 'pointer', opacity: isSaving ? 0.7 : 1, fontSize: '13px', fontWeight: 600 }}
                title="Save to Power BI">
                {isSaving ? <div style={{ width: 14, height: 14, border: '2px solid #fff', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} /> : <Save size={14} />}
                Save
              </button>
              )
            )}
            {activeTab.id.startsWith('query:') && onRunQuery && (
              <button onClick={() => onRunQuery(activeTab)} disabled={activeTab.isRunning}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 14px', background: 'var(--accent-color)', color: '#fff', border: 'none', borderRadius: '4px', cursor: activeTab.isRunning ? 'not-allowed' : 'pointer', opacity: activeTab.isRunning ? 0.7 : 1, fontSize: '13px', fontWeight: 600 }}>
                {activeTab.isRunning ? 'Running...' : 'Run'}
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Editor Body ── */}
      <div style={{ flexGrow: 1, overflow: 'hidden', position: 'relative', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: activeTab?.id.startsWith('query:') ? '0 0 58%' : '1 1 auto', minHeight: 0, position: 'relative' }}>
        {activeTab?.activeProposal ? (
          <DiffEditor
            height="100%"
            language={activeLanguage}
            theme={theme === 'light' ? 'light' : 'vs-dark'}
            original={originalDiffCode}
            modified={modifiedCode}
            onMount={(editor, monaco) => handleEditorDidMount(editor.getModifiedEditor(), monaco)}
            options={{ readOnly: true, minimap: { enabled: false }, fontSize: 14, padding: { top: 16 }, renderSideBySide: false }}
          />
        ) : activeTab ? (
          <Editor
            height="100%"
            language={activeLanguage}
            theme={theme === 'light' ? 'light' : 'vs-dark'}
            value={activeCode}
            onMount={handleEditorDidMount}
            onChange={(val) => { if (!showAlt && activeTab) onCodeChange(activeTab.id, val || ''); }}
            options={{ readOnly: showAlt, minimap: { enabled: false }, fontSize: 14, padding: { top: 16 }, overviewRulerBorder: false, overviewRulerLanes: 0, hideCursorInOverviewRuler: true, scrollBeyondLastLine: false, wordWrap: 'on', scrollbar: { vertical: 'auto', horizontal: 'auto' } }}
          />
        ) : null}
        </div>
        {activeTab?.id.startsWith('query:') && (
          <div style={{ flex: '1 1 42%', minHeight: 0, overflow: 'auto', borderTop: '1px solid var(--border-color)', padding: '10px', background: 'var(--bg-secondary)' }}>
            {activeTab.isRunning && <div style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Executing query...</div>}
            {!activeTab.isRunning && activeTab.queryResult?.error && <div style={{ color: 'var(--diff-remove-text)', fontSize: '12px', whiteSpace: 'pre-wrap' }}>{activeTab.queryResult.error}</div>}
            {!activeTab.isRunning && activeTab.queryResult && !activeTab.queryResult.error && (
              activeTab.queryResult.rowCount === 0 ? <div style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Query returned no rows.</div> : (
                <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '12px' }}>
                  <thead><tr>{activeTab.queryResult.columns.map(column => <th key={column} style={{ textAlign: 'left', padding: '6px 8px', borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>{column}</th>)}</tr></thead>
                  <tbody>{activeTab.queryResult.rows.map((row, index) => <tr key={index}>{activeTab.queryResult!.columns.map(column => <td key={column} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)' }}>{String(row[column] ?? '')}</td>)}</tr>)}</tbody>
                </table>
              )
            )}
          </div>
        )}
      </div>
    </div>
  );
}

