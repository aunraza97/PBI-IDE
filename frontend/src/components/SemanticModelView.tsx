import { useState, useCallback, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  applyNodeChanges,
  applyEdgeChanges,
  Node,
  Edge,
  Handle,
  Position,
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Table as TableIcon, Columns, Calculator, ArrowRight, ArrowRightLeft, Wand2, UploadCloud } from 'lucide-react';

// Custom Edge for Power BI style relationships
const RelationshipEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  style,
  data,
  selected
}: any) => {
  const isActive = data?.isActive !== false;
  const isHovered = data?.isHovered;
  const isDimmed = data?.isDimmed;
  
  const edgeColor = selected || isHovered ? 'var(--accent-color)' : (isActive ? 'rgba(100, 116, 139, 0.72)' : 'rgba(148, 163, 184, 0.45)');
  const strokeWidth = selected || isHovered ? 2.5 : 1.5;
  const opacity = isDimmed && !selected && !isHovered ? 0.2 : 1;

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition: Position.Right,
    targetX,
    targetY,
    targetPosition: Position.Left,
  });

  return (
    <>
      <BaseEdge id={id} path={edgePath} style={{ ...style, strokeWidth, stroke: edgeColor, strokeDasharray: isActive ? 'none' : '4 4', opacity }} />
      <EdgeLabelRenderer>
        <div style={{ position: 'absolute', transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`, background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '3px', padding: '2px 4px', pointerEvents: 'none', display: 'flex', alignItems: 'center', gap: 3, fontSize: 9, color: edgeColor, opacity, zIndex: selected || isHovered ? 100 : 0 }} className="nodrag nopan">
          {data?.fromCardinality === 'Many' ? '*' : '1'}<span style={{ opacity: 0.55 }}>:</span>{data?.toCardinality === 'Many' ? '*' : '1'}
          {data?.crossFilteringBehavior === 'BothDirections' ? <ArrowRightLeft size={9} color={edgeColor} /> : <ArrowRight size={9} color={edgeColor} />}
          {(isHovered || selected) && data?.relationship && (
             <span style={{ marginLeft: 4, paddingLeft: 4, borderLeft: `1px solid ${edgeColor}`, fontWeight: 500, whiteSpace: 'nowrap' }}>
                {data.relationship.fromColumn} ↔ {data.relationship.toColumn}
             </span>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

// Custom Node for "Tall Tables"
const TableNode = ({ data }: { data: any }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    setIsCollapsed(data.showFields === false);
  }, [data.showFields]);

  return (
    <div style={{ width: '210px', maxHeight: '270px', fontSize: '12px', background: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: '6px', boxShadow: '0 3px 12px rgba(0,0,0,0.12)', overflow: 'visible' }}>
      <div 
        onClick={() => setIsCollapsed(!isCollapsed)}
        style={{ 
          background: 'var(--bg-secondary)', 
          padding: '7px 9px', 
          borderBottom: isCollapsed ? 'none' : '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          fontWeight: 'bold',
          transition: 'background 0.2s',
          fontSize: '12px',
          lineHeight: '16px'
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(0, 0, 0, 0.1)'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'var(--bg-panel)'}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <TableIcon size={13} color="var(--accent-color)" />
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{data.label}</span>
        </div>
        <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
          {isCollapsed ? '▼' : '▲'}
        </div>
      </div>
      
      {!isCollapsed && data.showFields !== false && (
        <div style={{ maxHeight: '222px', overflowY: 'auto', overflowX: 'hidden', width: '100%', padding: '7px 9px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
          {data.columns && data.columns.map((col: any, i: number) => {
            const isHoveredCol = data.hoveredRelationship && (
              (data.hoveredRelationship.fromTable === data.label && data.hoveredRelationship.fromColumn === col.name) ||
              (data.hoveredRelationship.toTable === data.label && data.hoveredRelationship.toColumn === col.name)
            );
            return (
              <div key={i} style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: '6px', minHeight: '18px', minWidth: 0, width: '100%', overflow: 'hidden', background: isHoveredCol ? 'var(--bg-secondary)' : 'transparent', borderRadius: '3px' }}>
                <Handle type="target" position={Position.Left} id={`target:${col.name}`} style={{ width: 4, height: 18, left: -4, opacity: 0, visibility: 'hidden', border: 'none' }} />
                <Columns size={10} color={isHoveredCol ? 'var(--accent-color)' : 'var(--text-muted)'} />
                <span style={{ color: isHoveredCol ? 'var(--accent-color)' : 'var(--text-main)', fontWeight: isHoveredCol ? 'bold' : 'normal', fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{col.name}</span>
                <Handle type="source" position={Position.Right} id={`source:${col.name}`} style={{ width: 9, height: 18, right: -18, borderRadius: '0 9px 9px 0', background: 'var(--accent-color)', border: '1px solid var(--bg-panel)', zIndex: 5 }} />
              </div>
            );
          })}
          {data.measures && data.measures.map((m: any, i: number) => (
            <div key={`m-${i}`} style={{ display: 'flex', alignItems: 'center', gap: '6px', minHeight: '18px', lineHeight: '16px', minWidth: 0, width: '100%', overflow: 'hidden' }}>
              <Calculator size={10} color="var(--accent-color)" />
              <span style={{ color: 'var(--text-main)', fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.name}</span>
            </div>
          ))}
          {(!data.columns || data.columns.length === 0) && (!data.measures || data.measures.length === 0) && (
            <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No columns</div>
          )}
        </div>
      )}
      <Handle type="target" position={Position.Left} id="table-target" style={{ width: 4, height: 4, opacity: 0, pointerEvents: 'none' }} />
      <Handle type="source" position={Position.Right} id="table-source" style={{ width: 4, height: 4, opacity: 0, pointerEvents: 'none' }} />
    </div>
  );
};

const nodeTypes = {
  tableNode: TableNode
};

const edgeTypes = {
  relationshipEdge: RelationshipEdge
};

export default function SemanticModelView({ schema, onRelationshipCreated, isPreview, onPush, onCancelPreview, isPushing }: { schema: any; onRelationshipCreated?: () => void; isPreview?: boolean; onPush?: () => void; onCancelPreview?: () => void; isPushing?: boolean }) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [connectionDraft, setConnectionDraft] = useState<any>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [fromTable, setFromTable] = useState('');
  const [fromColumn, setFromColumn] = useState('');
  const [toTable, setToTable] = useState('');
  const [toColumn, setToColumn] = useState('');
  const [showFields, setShowFields] = useState(true);
  const [selectedRelationship, setSelectedRelationship] = useState<any>(null);
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null);
  const [notification, setNotification] = useState<{message: string, type: 'error'|'success'} | null>(null);

  const tables = schema?.tables || [];
  const selectedFromTable = tables.find((table: any) => table.name === fromTable);
  const selectedToTable = tables.find((table: any) => table.name === toTable);

  useEffect(() => {
    if (!schema || !schema.tables) return;
    const tables = schema.tables;
    const relationships = schema.relationships || [];
    const nodeWidth = 210;
    const rowHeight = showFields ? 270 : 48;
    const xGap = 200;
    const yGap = 50;

    // 1. Determine direction based on cardinality (Many -> 1)
    const layoutEdges = relationships.map((rel: any) => {
      // If it flows One -> Many, reverse it for layout so Many is on the left
      if ((rel.toCardinality === 'Many' || rel.toCardinality === '*') && 
          (rel.fromCardinality === 'One' || rel.fromCardinality === '1')) {
        return { source: rel.toTable, target: rel.fromTable };
      }
      return { source: rel.fromTable, target: rel.toTable };
    });

    // 2. Calculate depths (longest path from source)
    const depths = new Map<string, number>();
    tables.forEach((t: any) => depths.set(t.name, 0));

    let changed = true;
    let iterations = 0;
    while (changed && iterations < tables.length) {
      changed = false;
      layoutEdges.forEach((edge: any) => {
        const sourceDepth = depths.get(edge.source) || 0;
        const targetDepth = depths.get(edge.target) || 0;
        if (sourceDepth + 1 > targetDepth) {
          depths.set(edge.target, sourceDepth + 1);
          changed = true;
        }
      });
      iterations++;
    }

    // 3. Group tables by depth
    const layers = new Map<number, string[]>();
    tables.forEach((t: any) => {
      const d = depths.get(t.name) || 0;
      if (!layers.has(d)) layers.set(d, []);
      layers.get(d)!.push(t.name);
    });

    // 4. Assign positions
    const positions = new Map<string, { x: number; y: number; row: number; column: number }>();
    layers.forEach((tableNames, depth) => {
      tableNames.forEach((name, index) => {
        // Center the rows vertically around y=300
        const totalInLayer = tableNames.length;
        const totalHeight = totalInLayer * rowHeight + (totalInLayer - 1) * yGap;
        const startY = 300 - (totalHeight / 2);
        
        const y = startY + index * (rowHeight + yGap);
        const x = depth * (nodeWidth + xGap) + 60;
        positions.set(name, { x, y, row: index, column: depth });
      });
    });

    const newNodes: Node[] = tables.map((table: any) => {
      const position = positions.get(table.name)!;
      return {
        id: table.name,
        type: 'tableNode',
        position: { x: position.x, y: position.y },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        data: { label: table.name, columns: table.columns, measures: table.measures, showFields }
      };
    });

    const newEdges: Edge[] = relationships.map((rel: any, index: number) => {
      const sourcePosition = positions.get(rel.fromTable)!;
      const targetPosition = positions.get(rel.toTable)!;
      const sameRow = sourcePosition.row === targetPosition.row;
      const corridorY = sameRow
        ? undefined
        : (Math.max(sourcePosition.y, targetPosition.y) - yGap / 2);
      return {
        id: `rel-${index}`,
        source: rel.fromTable,
        target: rel.toTable,
        sourceHandle: 'table-source',
        targetHandle: 'table-target',
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        type: 'relationshipEdge',
        zIndex: 10,
        data: { fromCardinality: rel.fromCardinality, toCardinality: rel.toCardinality, isActive: rel.isActive, crossFilteringBehavior: rel.crossFilteringBehavior, relationship: rel, laneIndex: index, sameRow, corridorY }
      };
    });
    setNodes(newNodes);
    setEdges(newEdges);
  }, [schema, showFields]);

  const onNodesChange = useCallback(
    (changes: any) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );
  const onEdgesChange = useCallback(
    (changes: any) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  const onEdgeMouseEnter = useCallback((_: any, edge: Edge) => {
    setEdges((eds) => eds.map((e) => ({
      ...e,
      data: { ...e.data, isHovered: e.id === edge.id, isDimmed: e.id !== edge.id },
      zIndex: e.id === edge.id ? 100 : 0
    })));
    setNodes((nds) => nds.map((n) => ({
      ...n,
      data: { ...n.data, hoveredRelationship: edge.data?.relationship }
    })));
  }, []);

  const onEdgeMouseLeave = useCallback(() => {
    setEdges((eds) => eds.map((e) => ({
      ...e,
      data: { ...e.data, isHovered: false, isDimmed: false },
      zIndex: 0
    })));
    setNodes((nds) => nds.map((n) => ({
      ...n,
      data: { ...n.data, hoveredRelationship: null }
    })));
  }, []);

  const onConnect = useCallback((connection: any) => {
    if (!connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) return;
    setConnectionDraft({
      fromTable: connection.source,
      fromColumn: connection.sourceHandle.replace('source:', ''),
      toTable: connection.target,
      toColumn: connection.targetHandle.replace('target:', '')
    });
  }, []);

  const createRelationship = async (draft = connectionDraft) => {
    if (!draft) return;
    setIsCreating(true);
    try {
      const response = await fetch('http://localhost:8000/api/relationship', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft)
      });
      const result = await response.json();
      if (!response.ok || result.status !== 'success') {
        throw new Error(result.message || 'Relationship creation failed');
      }
      setConnectionDraft(null);
      setFromColumn('');
      setToColumn('');
      onRelationshipCreated?.();
      setNotification({ message: 'Relationship created successfully', type: 'success' });
      setTimeout(() => setNotification(null), 3000);
    } catch (error) {
      setNotification({ message: error instanceof Error ? error.message : 'Relationship creation failed', type: 'error' });
      setTimeout(() => setNotification(null), 3000);
    } finally {
      setIsCreating(false);
    }
  };

  const formDraft = { fromTable, fromColumn, toTable, toColumn };
  const canCreate = Boolean(connectionDraft || (fromTable && fromColumn && toTable && toColumn));

  return (
    <div className="glass-panel" style={{ width: '100%', height: '100%', background: 'var(--model-surface)', position: 'relative', boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.08)' }}>
      <div style={{ position: 'absolute', top: 12, left: 12, right: 12, zIndex: 10, background: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: 12, padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap', fontSize: 11, boxShadow: '0 3px 12px rgba(0,0,0,0.12)' }}>
        <strong style={{ color: 'var(--text-main)', marginRight: 4 }}>Model</strong>
        <button className="btn-secondary" onClick={() => reactFlowInstance?.fitView({ padding: 0.2, duration: 300, maxZoom: 1 })} style={{ padding: '5px 9px', fontSize: 11 }}>Fit model</button>
        <button className="btn-secondary" onClick={() => setShowFields(value => !value)} style={{ padding: '5px 9px', fontSize: 11 }}>{showFields ? 'Hide fields' : 'Show fields'}</button>
        {!isPreview && (
          <>
            <span style={{ color: 'var(--border-color)', margin: '0 3px' }}>|</span>
        <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Create relationship</span>
        <select value={fromTable} onChange={event => { setFromTable(event.target.value); setFromColumn(''); }} style={{ maxWidth: 145, padding: '5px 6px', border: '1px solid var(--border-color)', borderRadius: 4, background: 'var(--bg-secondary)', color: 'var(--text-main)', fontSize: 11 }}>
          <option value="">From table</option>
          {tables.map((table: any) => <option key={table.name} value={table.name}>{table.name}</option>)}
        </select>
        <select value={fromColumn} onChange={event => setFromColumn(event.target.value)} disabled={!selectedFromTable} style={{ maxWidth: 145, padding: '5px 6px', border: '1px solid var(--border-color)', borderRadius: 4, background: 'var(--bg-secondary)', color: 'var(--text-main)', fontSize: 11 }}>
          <option value="">From column</option>
          {(selectedFromTable?.columns || []).map((column: any) => <option key={column.name} value={column.name}>{column.name}</option>)}
        </select>
        <span style={{ color: 'var(--text-muted)' }}>→</span>
        <select value={toTable} onChange={event => { setToTable(event.target.value); setToColumn(''); }} style={{ maxWidth: 145, padding: '5px 6px', border: '1px solid var(--border-color)', borderRadius: 4, background: 'var(--bg-secondary)', color: 'var(--text-main)', fontSize: 11 }}>
          <option value="">To table</option>
          {tables.map((table: any) => <option key={table.name} value={table.name}>{table.name}</option>)}
        </select>
        <select value={toColumn} onChange={event => setToColumn(event.target.value)} disabled={!selectedToTable} style={{ maxWidth: 145, padding: '5px 6px', border: '1px solid var(--border-color)', borderRadius: 4, background: 'var(--bg-secondary)', color: 'var(--text-main)', fontSize: 11 }}>
          <option value="">To column</option>
          {(selectedToTable?.columns || []).map((column: any) => <option key={column.name} value={column.name}>{column.name}</option>)}
        </select>
        <button className="btn-primary" onClick={() => createRelationship(connectionDraft || formDraft)} disabled={isCreating || !canCreate} style={{ padding: '5px 9px', fontSize: 11 }}>{isCreating ? 'Creating...' : 'Create'}</button>
        {connectionDraft && <>
          <span style={{ color: 'var(--text-muted)' }}>Drag selection: {connectionDraft.fromTable}[{connectionDraft.fromColumn}] → {connectionDraft.toTable}[{connectionDraft.toColumn}]</span>
          <button className="btn-secondary" onClick={() => setConnectionDraft(null)} disabled={isCreating} style={{ padding: '5px 8px', fontSize: 11 }}>Cancel</button>
        </>}
          </>
        )}
      </div>
      {isPreview && (
        <div style={{ position: 'absolute', bottom: 40, left: '50%', transform: 'translateX(-50%)', zIndex: 20, background: 'var(--accent-color)', border: 'none', borderRadius: 30, padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 12, boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)', whiteSpace: 'nowrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent-text)' }}>
            <Wand2 size={16} />
            <strong style={{ fontSize: '14px' }}>AI Generated Model Preview</strong>
          </div>
          <div style={{ width: 1, height: 16, background: 'var(--accent-text)', opacity: 0.3 }} />
          <button onClick={onPush} disabled={isPushing} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 16px', fontSize: '13px', borderRadius: 20, background: 'var(--accent-text)', color: 'var(--accent-color)', border: 'none', fontWeight: 'bold', cursor: 'pointer' }}>
            <UploadCloud size={14} />
            {isPushing ? 'Pushing...' : 'Push to Power BI'}
          </button>
          <button onClick={onCancelPreview} disabled={isPushing} style={{ padding: '6px 14px', fontSize: '13px', borderRadius: 20, border: '1px solid var(--accent-text)', background: 'transparent', color: 'var(--accent-text)', cursor: 'pointer', opacity: 0.9 }}>
            Cancel
          </button>
        </div>
      )}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onInit={setReactFlowInstance}
        onEdgeClick={(_, edge) => setSelectedRelationship(edge.data?.relationship || null)}
        onEdgeMouseEnter={onEdgeMouseEnter}
        onEdgeMouseLeave={onEdgeMouseLeave}
        onPaneClick={() => setSelectedRelationship(null)}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        minZoom={0.35}
        maxZoom={1}
        fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="rgba(100,116,139,0.18)" gap={20} />
        <Controls style={{ background: 'var(--bg-secondary)', fill: 'var(--text-main)', color: 'var(--text-main)' }} />
      </ReactFlow>
      
      <div style={{ position: 'absolute', bottom: 12, right: 12, zIndex: 10, background: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: 6, padding: '10px 12px', fontSize: 11, boxShadow: '0 3px 12px rgba(0,0,0,0.12)', color: 'var(--text-main)' }}>
        <div style={{ fontWeight: 700, marginBottom: 8, fontSize: 10, textTransform: 'uppercase', color: 'var(--text-muted)' }}>Legend</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <div style={{ width: 24, height: 2, background: 'rgba(100, 116, 139, 0.72)' }} />
          <span>Active Relationship</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 24, height: 0, borderBottom: '2px dashed rgba(148, 163, 184, 0.45)' }} />
          <span style={{ color: 'var(--text-muted)' }}>Inactive Relationship</span>
        </div>
      </div>
      {selectedRelationship && (
        <div style={{ position: 'absolute', right: 12, bottom: 100, width: 230, zIndex: 10, background: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: 6, padding: '10px 12px', fontSize: 11, boxShadow: '0 3px 12px rgba(0,0,0,0.12)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 7, fontWeight: 700, color: 'var(--text-main)' }}>
            <span>Relationship</span>
            <button onClick={() => setSelectedRelationship(null)} style={{ border: 0, background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer' }}>×</button>
          </div>
          <div style={{ color: 'var(--text-main)' }}>{selectedRelationship.fromTable}[{selectedRelationship.fromColumn}]</div>
          <div style={{ color: 'var(--text-muted)', margin: '3px 0' }}>{selectedRelationship.fromCardinality === 'Many' ? '*' : '1'} : {selectedRelationship.toCardinality === 'Many' ? '*' : '1'}</div>
          <div style={{ color: 'var(--text-main)' }}>{selectedRelationship.toTable}[{selectedRelationship.toColumn}]</div>
          <div style={{ color: 'var(--text-muted)', marginTop: 7 }}>Filter: {selectedRelationship.crossFilteringBehavior || 'SingleDirection'}</div>
        </div>
      )}

      {notification && (
        <div style={{ position: 'absolute', top: 60, left: '50%', transform: 'translateX(-50%)', zIndex: 100, background: notification.type === 'error' ? '#ef4444' : '#10b981', color: '#fff', padding: '8px 16px', borderRadius: 20, fontSize: 12, fontWeight: 600, boxShadow: '0 4px 12px rgba(0,0,0,0.15)', animation: 'fadeIn 0.2s ease-out' }}>
          {notification.message}
        </div>
      )}
    </div>
  );
}
