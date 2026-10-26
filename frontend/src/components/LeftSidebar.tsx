import { useState, useEffect } from 'react';
import { Table, Calculator, Columns, ChevronDown, ChevronRight, BarChart2 } from 'lucide-react';

export default function LeftSidebar({ 
  roles = [],
  onMeasureClick,
  onTableClick,
  onRoleClick,
  onSchemaLoaded,
  onRolesLoaded,
  pendingItemName,
  pendingItemTable,
  pendingTool,
  pendingOperation,
  activeItemName,
  activeItemTable,
  refreshSchemaTrigger
}: { 
  roles?: any[],
  onMeasureClick?: (tableName: string, measureName: string) => void,
  onTableClick?: (tableName: string) => void,
  onRoleClick?: (roleName: string, tableName: string, dax: string) => void,
  onSchemaLoaded?: (schema: any) => void,
  onRolesLoaded?: (roles: any[]) => void,
  pendingItemName?: string | null,
  pendingItemTable?: string | null,
  pendingTool?: string | null,
  pendingOperation?: string | null,
  activeItemName?: string | null,
  activeItemTable?: string | null,
  refreshSchemaTrigger?: number
}) {
  const [instances, setInstances] = useState<string[]>([]);
  const [model, setModel] = useState<any>(null);

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isRefreshingModel, setIsRefreshingModel] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isLoadingSchema, setIsLoadingSchema] = useState(false);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [schema, setSchema] = useState<any[]>([]);
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});
  const [expandedRoles, setExpandedRoles] = useState<Record<string, boolean>>({});
  const [isSemanticModelExpanded, setIsSemanticModelExpanded] = useState(false);
  const [isRolesExpanded, setIsRolesExpanded] = useState(false);

  const toggleTable = (tableName: string) => {
    setExpandedTables(prev => ({
      ...prev,
      [tableName]: !prev[tableName]
    }));
  };

  const toggleRole = (roleName: string) => {
    setExpandedRoles(prev => ({
      ...prev,
      [roleName]: !prev[roleName]
    }));
  };

  const fetchInstances = () => {
    setIsRefreshing(true);
    fetch('http://localhost:8000/api/instances')
      .then(res => res.json())
      .then(data => {
        if(data.status === 'success' && data.data) {
          const lines = data.data.split('\\n');
          const parsed = lines
            .filter((line: string) => line.startsWith('- '))
            .map((line: string) => line.substring(2).trim());
          setInstances(parsed.length > 0 ? parsed : []);
        }
      })
      .finally(() => setIsRefreshing(false));
  };

  const refreshModel = () => {
    if (!model) return;
    setIsRefreshingModel(true);
    fetch('http://localhost:8000/api/model/refresh', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          // Re-fetch schema after refresh
          connectToInstance(model);
        } else {
          alert('Failed to refresh model: ' + (data.message || 'Unknown error'));
        }
      })
      .finally(() => setIsRefreshingModel(false));
  };

  const connectToInstance = (inst: string) => {
    // Extract localhost:PORT from "Dashboard Name (localhost:PORT)"
    const match = inst.match(/\((localhost:\d+)\)/);
    const instanceName = match ? match[1] : inst;
    
    setIsConnecting(true);
    fetch('http://localhost:8000/api/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instance_name: instanceName })
    })
      .then(res => res.json())
      .then(data => {
        let isMcpSuccess = true;
        if (data.status === 'success' && typeof data.data === 'string') {
          try {
            const parsed = JSON.parse(data.data);
            isMcpSuccess = parsed.success !== false;
          } catch(e) {}
        }
        
        if(data.status === 'success' && isMcpSuccess) {
          setModel(inst);
          setIsLoadingSchema(true);
          setSchemaError(null);
          // Fetch schema immediately after connecting
          fetch(`http://localhost:8000/api/schema?t=${Date.now()}`)
            .then(sres => sres.json())
            .then(sdata => {
              if (sdata.status === 'success') {
                const tables = Array.isArray(sdata.data) ? sdata.data : (sdata.data.tables || []);
                setSchema(tables);
                if (onSchemaLoaded) onSchemaLoaded(sdata.data);
              } else {
                setSchemaError(sdata.message || 'Unknown error');
              }
            })
            .catch(e => setSchemaError(e.message))
            .finally(() => setIsLoadingSchema(false));
            
          // Fetch roles
          fetch(`http://localhost:8000/api/roles?t=${Date.now()}`)
            .then(rres => rres.json())
            .then(rdata => {
              if (rdata.status === 'success' && onRolesLoaded) {
                onRolesLoaded(rdata.data);
              }
            });
        } else {
          alert('Failed to connect via MCP: ' + (data.message || 'Unknown error'));
        }
      })
      .finally(() => setIsConnecting(false));
  };

  useEffect(() => {
    fetchInstances();
  }, []);

  useEffect(() => {
    if (refreshSchemaTrigger && refreshSchemaTrigger > 0 && model) {
      setIsLoadingSchema(true);
      fetch(`http://localhost:8000/api/schema?t=${Date.now()}`)
        .then(sres => sres.json())
        .then(sdata => {
          if (sdata.status === 'success') {
            const tables = Array.isArray(sdata.data) ? sdata.data : (sdata.data.tables || []);
            setSchema(tables);
            if (onSchemaLoaded) onSchemaLoaded(sdata.data);
            
            if (pendingItemName) {
              const targetTableName = pendingItemTable || 
                tables.find((t: any) => t.measures && t.measures.length > 0)?.name || 
                tables[0]?.name || 'Pending Item';
                
              const tableWithPending = tables.find((t: any) => t.name === targetTableName);
              if (tableWithPending) {
                setExpandedTables(prev => ({ ...prev, [tableWithPending.name]: true }));
              }
            }
          }
        })
        .finally(() => {
          setIsLoadingSchema(false);
          // Also fetch roles
          fetch(`http://localhost:8000/api/roles?t=${Date.now()}`)
            .then(rres => rres.json())
            .then(rdata => {
              if (rdata.status === 'success' && onRolesLoaded) {
                onRolesLoaded(rdata.data);
              }
            });
        });
    }
  }, [refreshSchemaTrigger]);

  return (
    <div className="glass-panel left-sidebar">
      <div className="panel-header">
        <span>Explorer</span>
      </div>
      <div className="panel-content">
        <div style={{ marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h4 style={{ color: 'var(--text-muted)', fontSize: '0.85em', textTransform: 'uppercase', margin: 0 }}>Running Instances</h4>
            <button 
              onClick={fetchInstances}
              title="Find opened dashboards"
              style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
            >
              {isRefreshing ? (
                <div style={{ width: 14, height: 14, border: '2px solid var(--text-muted)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>
              )}
            </button>
          </div>
          {instances.length === 0 ? (
            <div style={{ fontSize: '0.9em', color: 'var(--text-muted)' }}>No instances found</div>
          ) : (
            instances.map((inst, i) => {
              return (
                <div 
                  key={i} 
                  onClick={() => connectToInstance(inst)}
                  style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px', 
                    fontSize: '0.9em', 
                    padding: '6px 8px',
                    margin: '2px 0',
                    cursor: 'pointer',
                    borderRadius: '4px',
                    background: model === inst ? 'rgba(74, 158, 255, 0.1)' : 'transparent',
                    border: model === inst ? '1px solid var(--accent-color)' : '1px solid transparent'
                  }}
                  onMouseEnter={(e) => {
                    if (model !== inst) e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                  }}
                  onMouseLeave={(e) => {
                    if (model !== inst) e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <BarChart2 size={16} color="#F2C811" />
                  <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: model === inst ? 'var(--text-main)' : 'var(--text-muted)' }}>{inst.split(' (localhost:')[0]}</span>
                </div>
              );
            })
          )}
        </div>
        
        {model && (
          <div style={{ marginBottom: '20px' }}>
            <h4 style={{ color: 'var(--text-muted)', fontSize: '0.85em', textTransform: 'uppercase', margin: '0 0 8px 0' }}>Connected Report</h4>
            <div style={{ fontSize: '0.9em', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 8px', background: 'rgba(74, 158, 255, 0.1)', border: '1px solid var(--accent-color)', borderRadius: '4px' }}>
              <BarChart2 size={16} color="#F2C811" />
              {model.split(' (localhost:')[0]}
            </div>
          </div>
        )}

        <div>
          <div 
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', cursor: 'pointer' }}
            onClick={() => setIsSemanticModelExpanded(!isSemanticModelExpanded)}
          >
            <h4 style={{ color: 'var(--text-muted)', fontSize: '0.85em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
              {isSemanticModelExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              Semantic Model
              {isConnecting && <div style={{ width: 12, height: 12, border: '2px solid var(--accent-color)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />}
            </h4>
            {model && (
              <button 
                onClick={(e) => { e.stopPropagation(); refreshModel(); }}
                title="Refresh Semantic Model"
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                {isRefreshingModel ? (
                  <div style={{ width: 14, height: 14, border: '2px solid var(--text-muted)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>
                )}
              </button>
            )}
          </div>
          {model && isSemanticModelExpanded ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              
              {isLoadingSchema && (
                <div style={{ fontSize: '0.85em', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ width: 12, height: 12, border: '2px solid var(--text-muted)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                  Fetching model schema...
                </div>
              )}

              {schemaError && (
                <div style={{ fontSize: '0.85em', color: '#ff6b6b', padding: '8px', background: 'rgba(255, 107, 107, 0.1)', borderRadius: '4px' }}>
                  Error loading schema: {schemaError}
                </div>
              )}

              {schema.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '8px' }}>
                  {(() => {
                    const cloned = JSON.parse(JSON.stringify(schema));
                    if (pendingItemName) {
                      if (pendingTool === 'table_operations' && pendingOperation === 'Create') {
                        // It's a table creation
                        if (!cloned.find((t: any) => t.name === pendingItemName)) {
                          cloned.push({ name: pendingItemName, measures: [], columns: [] });
                        }
                      } else {
                        // It's a measure or column creation (assume measure for now)
                        const targetTableName = pendingItemTable || 
                          cloned.find((t: any) => t.measures && t.measures.length > 0)?.name || 
                          cloned[0]?.name || 'Pending Item';
                          
                        let table = cloned.find((t: any) => t.name === targetTableName);
                        if (!table) {
                          table = { name: targetTableName, measures: [], columns: [] };
                          cloned.push(table);
                        }
                        table.measures = table.measures || [];
                        if (!table.measures.find((m: any) => m.name === pendingItemName)) {
                          table.measures.push({ name: pendingItemName });
                        }
                      }
                    }
                    return cloned;
                  })().map((table: any, i: number) => {
                    const isExpanded = expandedTables[table.name];
                    const isMeasureTable = (!table.columns || table.columns.length === 0) && table.measures && table.measures.length > 0;
                    
                    return (
                      <div key={i} style={{ display: 'flex', flexDirection: 'column' }}>
                        <div 
                          style={{ 
                            display: 'flex', alignItems: 'center', gap: '6px', 
                            padding: '4px', borderRadius: '4px',
                            color: 'var(--text-main)', fontSize: '0.9em'
                          }}
                          onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
                          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                        >
                          <div onClick={() => toggleTable(table.name)} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </div>
                          
                          <div 
                            onClick={() => onTableClick && onTableClick(table.name)} 
                            style={{ 
                              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', flexGrow: 1, minWidth: 0,
                              background: table.name === pendingItemName ? 'rgba(242, 200, 17, 0.15)' : (table.name === activeItemName && !activeItemTable) ? 'rgba(74, 158, 255, 0.15)' : 'transparent',
                              borderRadius: '4px',
                              padding: '2px 4px',
                              border: table.name === pendingItemName ? '1px solid rgba(242, 200, 17, 0.5)' : (table.name === activeItemName && !activeItemTable) ? '1px solid rgba(74, 158, 255, 0.5)' : '1px solid transparent'
                            }}
                          >
                            {isMeasureTable ? (
                               <div style={{ position: 'relative', width: '14px', height: '14px', display: 'flex', justifyContent: 'center', alignItems: 'center', flexShrink: 0 }}>
                                 <Table size={14} color="var(--text-muted)" opacity={0.5} />
                                 <Calculator size={10} color="var(--accent-color)" style={{ position: 'absolute', bottom: -2, right: -2 }} />
                               </div>
                            ) : (
                               <Table size={14} color="var(--text-muted)" style={{ flexShrink: 0 }} />
                            )}
                            <span title={table.name} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{table.name}</span>
                          </div>
                        </div>
                        
                        {isExpanded && (
                          <div style={{ display: 'flex', flexDirection: 'column', paddingLeft: '24px', gap: '2px', marginTop: '2px' }}>
                            {table.measures && table.measures.map((m: any, mi: number) => {
                              const isPending = m.name === pendingItemName;
                              const isActive = m.name === activeItemName && table.name === activeItemTable;
                              return (
                              <div 
                                key={`m-${mi}`} 
                                onClick={() => onMeasureClick && onMeasureClick(table.name, m.name)}
                                style={{ 
                                  display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85em', color: 'var(--text-main)', 
                                  padding: '2px 4px', cursor: 'pointer', borderRadius: '3px', minWidth: 0,
                                  background: isPending ? 'rgba(242, 200, 17, 0.15)' : isActive ? 'rgba(74, 158, 255, 0.15)' : 'transparent',
                                  border: isPending ? '1px solid rgba(242, 200, 17, 0.5)' : isActive ? '1px solid rgba(74, 158, 255, 0.5)' : '1px solid transparent'
                                }}
                                onMouseEnter={e => { if (!isPending && !isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.05)' }}
                                onMouseLeave={e => { if (!isPending && !isActive) e.currentTarget.style.background = 'transparent' }}
                                title={m.name}
                              >
                                <Calculator size={12} color="var(--accent-color)" style={{ flexShrink: 0 }} />
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.name}</span>
                              </div>
                            )})}
                            {table.columns && table.columns.map((c: any, ci: number) => (
                              <div key={`c-${ci}`} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85em', color: 'var(--text-main)', padding: '2px 4px', minWidth: 0 }} title={c.name}>
                                <Columns size={12} color="rgba(255,255,255,0.4)" style={{ flexShrink: 0 }} />
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', opacity: 0.8 }}>{c.name}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : !model ? (
            <div style={{ fontSize: '0.9em', color: 'var(--text-muted)' }}>Select an active report from Running Instances</div>
          ) : null}
        </div>
        
        {/* Security Roles Section */}
        {model && (
          <div style={{ marginTop: '20px' }}>
            <div 
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', cursor: 'pointer' }} 
              onClick={() => setIsRolesExpanded(!isRolesExpanded)}
            >
              <h4 style={{ color: 'var(--text-muted)', fontSize: '0.85em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                {isRolesExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                Security Roles
              </h4>
              <button 
                onClick={(e) => {
                  e.stopPropagation();
                  if (onRolesLoaded) {
                    fetch(`http://localhost:8000/api/roles?t=${Date.now()}`)
                      .then(rres => rres.json())
                      .then(rdata => {
                        if (rdata.status === 'success') onRolesLoaded(rdata.data);
                      });
                  }
                }}
                title="Refresh Security Roles"
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>
              </button>
            </div>
            
            {isRolesExpanded && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {roles && roles.length > 0 ? roles.map((role: any, i: number) => {
                  const roleName = role.name;
                  const isExpanded = expandedRoles[roleName];
                  const perms = role.tablePermissions || [];
                  return (
                    <div key={i} style={{ display: 'flex', flexDirection: 'column' }}>
                      <div 
                        style={{ 
                          display: 'flex', alignItems: 'center', gap: '6px', 
                          padding: '4px', borderRadius: '4px',
                          color: 'var(--text-main)', fontSize: '0.9em'
                        }}
                        onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      >
                        <div onClick={() => toggleRole(roleName)} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        </div>
                        
                        <div 
                          onClick={() => toggleRole(roleName)}
                          style={{ 
                            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', flexGrow: 1, minWidth: 0,
                            borderRadius: '4px',
                            padding: '2px 4px',
                          }}
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                          <span title={roleName} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{roleName}</span>
                        </div>
                      </div>
                      
                      {isExpanded && perms.length > 0 && (
                        <div style={{ display: 'flex', flexDirection: 'column', paddingLeft: '24px', gap: '2px', marginTop: '2px' }}>
                          {perms.map((rawPerm: any, pi: number) => {
                            const p = rawPerm.data || rawPerm;
                            const tName = p.name || p.TableName;
                            const dax = p.filterExpression || p.FilterExpression || '';
                            const isActive = activeItemName === roleName && activeItemTable === tName;
                            return (
                              <div 
                                key={`rp-${pi}`}
                                onClick={() => onRoleClick && onRoleClick(roleName, tName, dax)}
                                style={{ 
                                  display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85em', color: 'var(--text-main)', 
                                  padding: '2px 4px', cursor: 'pointer', borderRadius: '3px', minWidth: 0,
                                  background: isActive ? 'rgba(74, 158, 255, 0.15)' : 'transparent',
                                  border: isActive ? '1px solid rgba(74, 158, 255, 0.5)' : '1px solid transparent'
                                }}
                                onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.05)' }}
                                onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
                                title={tName}
                              >
                                <Table size={12} color="var(--text-muted)" style={{ flexShrink: 0 }} />
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tName}</span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                      {isExpanded && perms.length === 0 && (
                        <div style={{ paddingLeft: '24px', fontSize: '0.85em', color: 'var(--text-muted)' }}>
                          No table filters
                        </div>
                      )}
                    </div>
                  );
                }) : (
                  <div style={{ fontSize: '0.85em', color: 'var(--text-muted)', fontStyle: 'italic', padding: '4px' }}>
                    No security roles found
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
