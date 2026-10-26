import { useEffect, useCallback } from 'react';
import { ReactFlow, useNodesState, useEdgesState, Node, Position } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { BaseEdge, EdgeProps, getSmoothStepPath } from '@xyflow/react';

function AnimatedParticleEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data
}: EdgeProps) {
  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <BaseEdge path={edgePath} markerEnd={markerEnd} style={style} />
      {data?.isActive && (
        <circle r="4" fill="var(--accent-color)" style={{ filter: 'drop-shadow(0 0 6px var(--accent-color))' }}>
          <animateMotion dur="1.5s" repeatCount="indefinite" path={edgePath} />
        </circle>
      )}
    </>
  );
}

const edgeTypes = {
  particle: AnimatedParticleEdge,
};

const initialNodes: Node[] = [
  { id: 'manager', sourcePosition: Position.Bottom, data: { label: 'Manager' }, position: { x: 10, y: 10 }, style: { background: 'var(--bg-main)', color: 'var(--text-main)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '6px 10px', fontSize: '11px', width: '120px', textAlign: 'center' as const } },
  { id: 'semantic_agent', targetPosition: Position.Left, data: { label: 'Semantic Agent' }, position: { x: 30, y: 80 }, style: { background: 'var(--bg-main)', color: 'var(--text-main)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '6px 10px', fontSize: '11px', width: '110px', textAlign: 'center' as const } },
  { id: 'dax_agent', targetPosition: Position.Left, data: { label: 'DAX Agent' }, position: { x: 30, y: 140 }, style: { background: 'var(--bg-main)', color: 'var(--text-main)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '6px 10px', fontSize: '11px', width: '110px', textAlign: 'center' as const } },
  { id: 'rls_agent', targetPosition: Position.Left, data: { label: 'RLS Agent' }, position: { x: 30, y: 200 }, style: { background: 'var(--bg-main)', color: 'var(--text-main)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '6px 10px', fontSize: '11px', width: '110px', textAlign: 'center' as const } }
];

const initialEdges = [
  { id: 'e1-2', type: 'particle', source: 'manager', target: 'semantic_agent', data: { isActive: false } },
  { id: 'e1-3', type: 'particle', source: 'manager', target: 'dax_agent', data: { isActive: false } },
  { id: 'e1-4', type: 'particle', source: 'manager', target: 'rls_agent', data: { isActive: false } },
];

export default function AgentGraph() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Highlight an active node
  const setActiveNode = useCallback((activeId: string) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === activeId || (activeId && activeId !== 'manager' && node.id === 'manager')) {
          return { ...node, style: { ...node.style, background: 'var(--accent-color)', borderColor: 'var(--accent-color)', color: 'var(--accent-text)' } };
        }
        return { ...node, style: { ...node.style, background: 'var(--bg-main)', borderColor: 'var(--border-color)', color: 'var(--text-main)' } };
      })
    );

    setEdges((eds) =>
      eds.map((edge) => {
        // If the edge connects to/from the active node (except when only manager is active)
        if (activeId !== 'manager' && (edge.target === activeId || edge.source === activeId)) {
          return {
            ...edge,
            animated: false,
            data: { isActive: true },
            style: {
              stroke: 'var(--accent-color)',
              strokeWidth: 2,
              filter: 'none',
              transition: 'all 0.3s ease'
            }
          };
        }
        return {
          ...edge,
          animated: false,
          data: { isActive: false },
          style: {
            stroke: 'var(--border-color)',
            strokeWidth: 1,
            filter: 'none',
            transition: 'all 0.3s ease'
          }
        };
      })
    );
  }, [setNodes, setEdges]);

  useEffect(() => {
    const handleHandoff = (event: Event) => {
      const customEvent = event as CustomEvent;
      const { to, status } = customEvent.detail;
      if (status === 'complete') {
        setActiveNode('manager');
        setTimeout(() => setActiveNode(''), 2000); // clear after 2 seconds
      } else {
        setActiveNode(to);
      }
    };
    window.addEventListener('agent_handoff', handleHandoff);
    return () => window.removeEventListener('agent_handoff', handleHandoff);
  }, [setActiveNode]);

  return (
    <div style={{ width: '100%', height: '100%', background: 'transparent' }}>
      <ReactFlow
        style={{ background: 'transparent' }}
        nodes={nodes}
        edges={edges}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        fitViewOptions={{ padding: 0.1, minZoom: 0.1 }}
        colorMode="system"
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        nodesFocusable={false}
        edgesFocusable={false}
        zoomOnScroll={false}
        panOnDrag={false}
        panOnScroll={false}
        zoomOnDoubleClick={false}
        attributionPosition="bottom-right"
        proOptions={{ hideAttribution: true }}
      />
    </div>
  );
}
