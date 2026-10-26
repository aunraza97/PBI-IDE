import { useState, useRef, useEffect } from 'react';
import { Send, Check, X, FileCode2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import AgentGraph from './AgentGraph';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  proposal?: any;
  hidden?: boolean;
  thoughtProcess?: { tool: string; isError: boolean }[];
  thoughtProcessText?: string;
  thoughtItems?: { type: 'text' | 'tool'; content: string; isError?: boolean }[];
  thoughtStartTime?: number;
  thoughtEndTime?: number;
}

const TOOL_LABELS: Record<string, string> = {
  'dax_query_operations': 'Evaluating DAX query...',
  'table_operations': 'Searching schema for tables and columns...',
  'measure_operations': 'Managing DAX measures...',
  'partition_operations': 'Accessing partition and M-Code details...',
  'database_operations': 'Managing database operations...'
};

const stripTags = (text: string) => {
  if (!text) return text;
  return text
    .replace(/<function=[a-zA-Z0-9_]+>.*?<\/function>/gs, '')
    .replace(/<function=[a-zA-Z0-9_]+>.*/s, '')
    .replace(/\[[a-zA-Z0-9_]+\s*\(.*?\]/gs, '')
    .trim();
};

const TypingText = ({ text, speed = 5, onDone }: { text: string; speed?: number; onDone?: (text: string) => void }) => {
  const [visibleText, setVisibleText] = useState('');
  const doneFor = useRef('');

  useEffect(() => {
    if (!text.startsWith(visibleText)) {
      setVisibleText('');
      return;
    }
    if (visibleText.length >= text.length) {
      // Fully rendered (for this exact text) — notify once so the parent
      // knows the step finished typing.
      if (doneFor.current !== text) {
        doneFor.current = text;
        onDone?.(text);
      }
      return;
    }

    const timer = window.setTimeout(() => {
      setVisibleText(text.slice(0, visibleText.length + 50));
    }, 1);
    return () => window.clearTimeout(timer);
  }, [text, visibleText, speed]);

  return <>{visibleText}</>;
};

const TypingMarkdown = ({ text, speed = 5 }: { text: string; speed?: number }) => {
  const [visibleText, setVisibleText] = useState('');

  useEffect(() => {
    if (!text.startsWith(visibleText)) {
      setVisibleText('');
      return;
    }
    if (visibleText.length >= text.length) return;

    const timer = window.setTimeout(() => {
      setVisibleText(text.slice(0, visibleText.length + 50));
    }, 1);
    return () => window.clearTimeout(timer);
  }, [text, visibleText, speed]);

  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{visibleText}</ReactMarkdown>;
};

const ThoughtProcessView = ({ msg, isThinking }: { msg: Message, isThinking: boolean }) => {
  const [expanded, setExpanded] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [dots, setDots] = useState('');
  const [, setTick] = useState(0);
  // Indices of thought items whose typewriter has not yet finished rendering
  // the current content. "Working" stays true until the stream is done AND
  // every step is fully rendered — the header must never claim "Worked for"
  // while content is still typing out.
  const pendingRef = useRef<Set<number>>(new Set<number>());
  const seenRef = useRef<Map<number, string>>(new Map<number, string>());

  const bump = () => setTick(t => t + 1);

  // The exact string each step renders (after labels/stripping). Tracking uses
  // this — not the raw item content — so completion reports always match.
  const renderedItemText = (item: { type: 'text' | 'tool'; content: string; isError?: boolean }) =>
    item.type === 'text'
      ? stripTags(item.content)
      : (item.isError ? item.content : (TOOL_LABELS[item.content] || `Running ${item.content}...`));

  useEffect(() => {
    let changed = false;
    (msg.thoughtItems || []).forEach((item, idx) => {
      const shown = renderedItemText(item);
      if (!shown) return;
      if (seenRef.current.get(idx) !== shown) {
        seenRef.current.set(idx, shown);
        pendingRef.current.add(idx);
        changed = true;
      }
    });
    if (changed) bump();
  });

  const markTyped = (idx: number, content: string) => {
    if (seenRef.current.get(idx) === content && pendingRef.current.delete(idx)) {
      bump();
    }
  };

  const stillTyping = pendingRef.current.size > 0;
  const working = isThinking || stillTyping;

  useEffect(() => {
    setExpanded(working);
  }, [working]);

  useEffect(() => {
    if (working) {
      const timer = window.setInterval(() => {
        setElapsedSeconds(prev => prev + 1);
        setDots(d => d.length >= 3 ? '' : d + '.');
      }, 1000);
      return () => window.clearInterval(timer);
    }
  }, [working]);

  if ((!msg.thoughtProcess || msg.thoughtProcess.length === 0) && !msg.thoughtProcessText && !working) return null;

  let timeStr = '';
  if (msg.thoughtEndTime && msg.thoughtStartTime) {
      const secs = Math.max(1, Math.round((msg.thoughtEndTime - msg.thoughtStartTime) / 1000));
      if (secs >= 60) {
          timeStr = Math.floor(secs/60) + 'm ' + (secs%60) + 's';
      } else {
          timeStr = secs + 's';
      }
  }

  return (
    <div style={{ marginBottom: '8px' }}>
      <div 
        onClick={() => setExpanded(!expanded)}
        style={{ 
          fontSize: '0.85em', 
          color: 'var(--text-muted)', 
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          userSelect: 'none',
          paddingBottom: '4px'
        }}
      >
        <span>
          {working ? `Working${dots.padEnd(3, '\u00A0')} (${elapsedSeconds}s)` : `Worked for ${timeStr || elapsedSeconds + 's'}`}
        </span>
        <span style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>
          ›
        </span>
      </div>
      {expanded && (
        <div style={{ 
          paddingLeft: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
          borderLeft: '2px solid rgba(255,255,255,0.1)',
          marginTop: '4px',
          marginLeft: '4px'
        }}>
          {msg.thoughtItems?.map((item, idx) => {
            const renderedText = renderedItemText(item);
            if (item.type === 'text') {
              if (!renderedText) return null;
              return (
                <div key={idx} style={{ 
                   fontSize: '0.85em', 
                   color: 'var(--text-muted)',
                   fontFamily: 'monospace',
                   whiteSpace: 'pre-wrap',
                   marginBottom: '4px',
                   lineHeight: '1.4'
                }}>
                  <TypingText text={renderedText} speed={12} onDone={() => markTyped(idx, renderedText)} />
                  {working && idx === msg.thoughtItems!.length - 1 ? '...' : ''}
                </div>
              );
            } else {
               return (
                 <div key={idx} style={{ 
                   fontSize: '0.85em', 
                   color: item.isError ? 'var(--diff-remove-text)' : 'var(--text-muted)',
                   fontFamily: 'monospace',
                   marginBottom: '4px'
                 }}>
                   <TypingText
                     text={renderedText}
                     speed={12}
                     onDone={() => markTyped(idx, renderedText)}
                   />
                 </div>
               );
            }
          })}
        </div>
      )}
    </div>
  );
};

interface RightSidebarProps {
  onProposalReceived?: (proposal: any) => void;
  onProposalAction?: (action: 'accept' | 'reject', id: string, proposal: any) => void;
  onGenerationPreviewReceived?: (data: any) => void;
}

export default function RightSidebar({ onProposalReceived, onProposalAction, onGenerationPreviewReceived }: RightSidebarProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: 'Hello! I am your Power BI Modeling Assistant. What would you like to build today?' }
  ]);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  // Single-engine architecture: manager + dax/semantic/rls profiles. Always advanced.
  const intelligenceMode = 'advanced' as const;
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef(crypto.randomUUID());

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isThinking]);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const userMsg = { role: 'user', content: input } as Message;
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput('');
    setIsThinking(true);

    window.dispatchEvent(new CustomEvent('agent_handoff', { detail: { to: 'manager', status: 'analyzing' } }));

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: newHistory, session_id: sessionIdRef.current, intelligence_mode: intelligenceMode })
      });

      if (!response.body) throw new Error('No body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';
      
      setMessages(prev => [...prev, { role: 'assistant', content: '', thoughtStartTime: Date.now() }]);

      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.trim() === '') continue;
          if (line.startsWith('data: ') && line !== 'data: [DONE]') {
            try {
              const data = JSON.parse(line.substring(6));
              if (data.type === 'message') {
                assistantContent += data.content;
                setMessages(prev => {
                  const newArr = [...prev];
                  const lastMsg = newArr[newArr.length - 1];
                  lastMsg.content = assistantContent;
                  // NOTE: thought text stays in the working steps permanently —
                  // it is never moved or trimmed into the answer.
                  return newArr;
                });
              } else if (data.type === 'proposal') {
                const proposalObj = {
                  id: data.id,
                  tool: data.tool,
                  args: data.args,
                  status: 'pending'
                };
                setMessages(prev => {
                  const newArr = [...prev];
                  if (newArr[newArr.length - 1].proposal) {
                    newArr.push({ role: 'assistant', content: '', proposal: proposalObj });
                  } else {
                    newArr[newArr.length - 1].proposal = proposalObj;
                  }
                  return newArr;
                });
                if (onProposalReceived) onProposalReceived({ ...proposalObj, openEditor: false });
              } else if (data.type === 'generation_preview') {
                if (onGenerationPreviewReceived) onGenerationPreviewReceived(data);
              } else if (data.type === 'agent_handoff') {
                window.dispatchEvent(new CustomEvent('agent_handoff', { detail: data }));
              } else if (data.type === 'thought_chunk') {
                setMessages(prev => {
                  const newArr = [...prev];
                  const lastMsg = newArr[newArr.length - 1];
                  if (!lastMsg.thoughtStartTime) {
                    lastMsg.thoughtStartTime = Date.now();
                  }
                  if (!lastMsg.thoughtProcessText) {
                    lastMsg.thoughtProcessText = '';
                  }
                  if (!lastMsg.thoughtItems) {
                    lastMsg.thoughtItems = [];
                  }
                  const items = lastMsg.thoughtItems;
                  if (items.length > 0 && items[items.length - 1].type === 'text') {
                    items[items.length - 1].content += data.content;
                  } else {
                    items.push({ type: 'text', content: data.content });
                  }
                  lastMsg.thoughtProcessText += data.content;
                  return newArr;
                });
              } else if (data.type === 'tool_start') {
                setMessages(prev => {
                  const newArr = [...prev];
                  const lastMsg = newArr[newArr.length - 1];
                  if (!lastMsg.thoughtProcess) {
                    lastMsg.thoughtProcess = [];
                    lastMsg.thoughtStartTime = Date.now();
                  }
                  if (!lastMsg.thoughtItems) lastMsg.thoughtItems = [];

                  const alreadyShown = lastMsg.thoughtItems.some(
                    item => item.type === 'tool' && item.content === data.tool
                  );
                  if (!alreadyShown) {
                    lastMsg.thoughtProcess.push({ tool: data.tool, isError: false });
                    lastMsg.thoughtItems.push({ type: 'tool', content: data.tool, isError: false });
                  }
                  return newArr;
                });
              } else if (data.type === 'tool_error') {
                setMessages(prev => {
                  const newArr = [...prev];
                  const lastMsg = newArr[newArr.length - 1];
                  if (!lastMsg.thoughtProcess) {
                    lastMsg.thoughtProcess = [];
                    lastMsg.thoughtStartTime = Date.now();
                  }
                  if (!lastMsg.thoughtItems) lastMsg.thoughtItems = [];
                  
                  lastMsg.thoughtProcess.push({ tool: `Error: ${data.error}`, isError: true });
                  lastMsg.thoughtItems.push({ type: 'tool', content: `Error: ${data.error}`, isError: true });
                  return newArr;
                });
              } else if (data.type === 'error') {
                assistantContent += `\n\n**Error:** ${data.message}`;
                setMessages(prev => {
                  const newArr = [...prev];
                  newArr[newArr.length - 1].content = assistantContent;
                  return newArr;
                });
              }
            } catch (e) {
              console.warn("Failed to parse SSE line", line);
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : 'The proposal could not be applied.');
    } finally {
      setIsThinking(false);
      setMessages(prev => {
         const newArr = [...prev];
         const lastMsg = newArr[newArr.length - 1];
         if (lastMsg && lastMsg.thoughtProcess && !lastMsg.thoughtEndTime) {
             lastMsg.thoughtEndTime = Date.now();
         }
         return newArr;
      });
    }
  };

  const handleAccept = async (id: string, index: number) => {
    try {
      const response = await fetch(`http://localhost:8000/api/proposals/${id}/accept`, { method: 'POST' });
      const result = await response.json();
      if (!response.ok || result.status !== 'success') {
        throw new Error(result.message || 'The proposal could not be applied.');
      }
      const currentProposal = messages[index]?.proposal;
      
      setMessages(prev => {
        const newArr = [...prev];
        if (newArr[index].proposal) {
           newArr[index].proposal!.status = 'accepted';
           const propName = newArr[index].proposal!.args?.request?.definitions?.[0]?.name || 'the proposal';
           newArr.push({ role: 'user', content: `[System Status]: I accepted ${propName}. It is now in the model.`, hidden: true });
        }
        return newArr;
      });
      if (onProposalAction) onProposalAction('accept', id, currentProposal);
      
      // Also close any proposal tab if it exists
      window.dispatchEvent(new CustomEvent('close_tab', { detail: { id: `proposal:${id}` } }));
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : 'The proposal could not be applied.');
    }
  };

  const handleReject = async (id: string, index: number) => {
    try {
      const response = await fetch(`http://localhost:8000/api/proposals/${id}/reject`, { method: 'POST' });
      const result = await response.json();
      if (!response.ok || result.status !== 'success') {
        throw new Error(result.message || 'The proposal could not be rejected.');
      }
      const currentProposal = messages[index]?.proposal;
      
      setMessages(prev => {
        const newArr = [...prev];
        if (newArr[index].proposal) {
           newArr[index].proposal!.status = 'rejected';
           const propName = newArr[index].proposal!.args?.request?.definitions?.[0]?.name || 'the proposal';
           newArr.push({ role: 'user', content: `[System Status]: I rejected ${propName}. It has been deleted and reverted from the model.`, hidden: true });
        }
        return newArr;
      });
      if (onProposalAction) onProposalAction('reject', id, currentProposal);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    const handleAction = (e: Event) => {
      const customEvent = e as CustomEvent;
      const { id, action } = customEvent.detail;
      let index = messages.findIndex(m => m.proposal && m.proposal.id === id);
      // Fallback: if not found in messages, search more broadly
      if (index === -1) {
        index = messages.findIndex(m => m.proposal);
      }
      if (action === 'accept') handleAccept(id, index !== -1 ? index : 0);
      if (action === 'reject') handleReject(id, index !== -1 ? index : 0);
    };
    window.addEventListener('proposal-action', handleAction);
    return () => window.removeEventListener('proposal-action', handleAction);
  }, [messages]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isThinking]);

  return (
    <div className={`glass-panel right-sidebar ${isThinking ? 'thinking-glow' : ''}`}>
      <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Assistant</span>
      </div>
      <div className="panel-content" style={{ display: 'flex', flexDirection: 'row', gap: '16px', flexGrow: 1, overflow: 'hidden' }}>
        
        {/* Chat Messages Area */}
        <div style={{ flexGrow: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', paddingBottom: '16px' }}>
          {messages.filter(m => !m.hidden).map((m, i, filteredArr) => (
            <div key={i} style={{ 
              display: 'flex', 
              flexDirection: 'column',
              gap: '4px',
              width: '100%'
            }}>
              <div style={{ 
                background: m.role === 'user' ? 'var(--bg-hover, rgba(128,128,128,0.1))' : 'transparent',
                padding: m.role === 'user' ? '12px' : '4px 0',
                borderRadius: '8px',
                fontSize: '0.9em',
                lineHeight: '1.5',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                overflowX: 'hidden',
                width: '100%'
              }}>
                {m.role === 'assistant' && <ThoughtProcessView msg={m} isThinking={isThinking && i === filteredArr.length - 1} />}
                <div className="markdown-body">
                  {m.role === 'assistant' ? (
                    <TypingMarkdown text={stripTags(m.content)} speed={24} />
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{stripTags(m.content)}</ReactMarkdown>
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Vertical Agent Execution Graph (always visible) */}
          <div style={{ width: '160px', borderLeft: '1px solid var(--border-color)', paddingLeft: '16px', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
              <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px', textAlign: 'center' }}>Agent Graph</div>
              <div style={{ flexGrow: 1 }}>
                <AgentGraph />
              </div>
           </div>
      </div>
      
      <div style={{ padding: '10px 16px 16px', borderTop: '1px solid var(--border-color)', position: 'relative', display: 'flex', flexDirection: 'column', gap: 0 }}>
        {messages.filter(m => m.proposal && m.proposal.status === 'pending').map(m => (
          <div key={m.proposal!.id} style={{
            background: 'var(--bg-main)',
            borderRadius: '6px 6px 0 0',
            border: '1px solid var(--border-color)',
            borderBottom: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '8px',
            padding: '5px 8px',
            minHeight: '30px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)', fontSize: '11px', minWidth: 0 }}>
              <FileCode2 size={12} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {m.proposal?.args?.definitions?.[0]?.name || 
                 m.proposal?.args?.request?.definitions?.[0]?.name || 
                 m.proposal?.args?.request?.references?.[0]?.name || 
                 m.proposal?.args?.request?.permissionDefinitions?.[0]?.roleName ||
                 m.proposal?.args?.request?.permissionReferences?.[0]?.roleName ||
                 (m.proposal?.args?.request?.definitions?.[0]?.fromTable ? `${m.proposal.args.request.definitions[0].fromTable} ↔ ${m.proposal.args.request.definitions[0].toTable}` : null) ||
                 "Unknown object"}
              </span>
            </div>
            <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
              <button 
                className="btn-secondary" 
                style={{ padding: '3px 8px', fontSize: '10px', display: 'flex', alignItems: 'center', gap: '4px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)' }}
                onClick={() => {
                   if (onProposalReceived) onProposalReceived({ ...m.proposal, openEditor: true });
                }}
              >
                Review
              </button>
              <button 
                className="btn-secondary" 
                style={{ padding: '3px 6px', fontSize: '10px', display: 'flex', alignItems: 'center', gap: '4px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--diff-remove-text)', color: 'var(--diff-remove-text)' }}
                onClick={() => handleReject(m.proposal!.id, messages.indexOf(m))}
                title="Reject"
              >
                <X size={12}/>
              </button>
              <button 
                className="btn-primary" 
                style={{ padding: '3px 6px', fontSize: '10px', display: 'flex', alignItems: 'center', gap: '4px' }}
                onClick={() => handleAccept(m.proposal!.id, messages.indexOf(m))}
                title="Accept"
              >
                <Check size={12}/>
              </button>
            </div>
          </div>
        ))}
        <div style={{ 
          display: 'flex', 
          gap: '8px', 
          background: 'rgba(0,0,0,0.2)', 
          padding: '6px 6px 6px 16px', 
          borderRadius: messages.some(m => m.proposal?.status === 'pending') ? '0 0 24px 24px' : '24px', 
          border: '1px solid var(--border-color)',
          alignItems: 'flex-end'
        }}>
          <textarea 
            value={input}
            onChange={e => {
              setInput(e.target.value);
              e.target.style.height = 'auto';
              e.target.style.height = e.target.scrollHeight + 'px';
            }}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
                e.currentTarget.style.height = 'auto';
              }
            }}
            placeholder="Ask a question..."
            rows={1}
            style={{ 
              flexGrow: 1, 
              background: 'transparent', 
              border: 'none', 
              outline: 'none',
              padding: '6px 0',
              color: 'var(--text-main)',
              resize: 'none',
              fontFamily: 'inherit',
              fontSize: 'inherit',
              overflowY: 'auto',
              maxHeight: '150px',
              lineHeight: '20px'
            }}
          />
          <button 
            onClick={handleSend}
            style={{
              background: 'var(--accent-color)',
              border: 'none',
              borderRadius: '50%',
              width: '32px',
              height: '32px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              color: 'var(--accent-text)',
              flexShrink: 0
            }}
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
