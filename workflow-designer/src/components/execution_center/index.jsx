import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Play,
    StopCircle,
    Activity,
    Terminal,
    CheckCircle,
    AlertCircle,
    Clock,
    Search,
    Hash,
    ChevronRight,
    MessageSquare,
    Zap,
    History,
    Plus,
    Bot,
    PlayCircle
} from 'lucide-react';
import { getWorkflow, getWorkflowById, getStartProcessStreamUrl, matchWorkflows, generateWorkflowFromIntent } from '@/service/api.js';
import { transformWorkflowToReactFlow } from '@/components/orchestration_center/workflow/utils/index.jsx';
import UnifiedWorkflow from '../orchestration_center/workflow/index.jsx';

const ExecutionCenter = ({ isDark }) => {
    const { t } = useTranslation();
    const [selectedId, setSelectedId] = useState(null);
    const [isRunning, setIsRunning] = useState(false);
    const [events, setEvents] = useState([]);
    const [psopStatus, setPsopStatus] = useState(null);
    const [error, setError] = useState(null);
    const [nodes, setNodes] = useState([]);
    const [edges, setEdges] = useState([]);
    const [eventSource, setEventSource] = useState(null);

    const [userIntent, setUserIntent] = useState('');
    const [workflowSource, setWorkflowSource] = useState(null); // 'retrieved' | 'generated'
    const [isMatching, setIsMatching] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);

    const logScrollRef = useRef(null);
    const [autoScroll, setAutoScroll] = useState(true);

    const handleMatchIntent = async () => {
        if (!userIntent.trim()) return;

        setIsMatching(true);
        setNodes([]);
        setEdges([]);
        setSelectedId(null);
        setWorkflowSource(null);
        setError(null);

        try {
            const results = await matchWorkflows(userIntent);

            if (results && results.length > 0) {
                const match = results[0];
                setSelectedId(match.workflow_id);
                setWorkflowSource('retrieved');
                setIsMatching(false);
            } else {
                setIsMatching(false);
                setIsGenerating(true);

                try {
                    const generated = await generateWorkflowFromIntent(userIntent);
                    if (generated) {
                        const wfId = generated.workflow_id || generated.id;
                        if (wfId) {
                            setSelectedId(wfId);
                            setWorkflowSource('generated');
                        } else {
                            const { nodes: n, edges: e } = transformWorkflowToReactFlow(generated);
                            setNodes(n);
                            setEdges(e);
                            setWorkflowSource('generated');
                        }
                    } else {
                        throw new Error("Generation failed.");
                    }
                } catch (genErr) {
                    console.error("Auto generation failed:", genErr);
                    setError("No matching workflow found and auto-generation failed.");
                } finally {
                    setIsGenerating(false);
                }
            }
        } catch (err) {
            console.error("Failed to match workflows:", err);
            setError("Match request failed.");
            setIsMatching(false);
        }
    };

    useEffect(() => {
        if (autoScroll && logScrollRef.current) {
            const container = logScrollRef.current;
            container.scrollTo({
                top: container.scrollHeight,
                behavior: 'smooth'
            });
        }
    }, [events, autoScroll]);

    const handleScroll = (e) => {
        const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
        const isAtBottom = scrollHeight - scrollTop - clientHeight < 30;
        if (autoScroll !== isAtBottom) {
            setAutoScroll(isAtBottom);
        }
    };

    useEffect(() => {
        if (psopStatus) {
            const { nodes: n, edges: e } = transformWorkflowToReactFlow(psopStatus);
            setNodes(n);
            setEdges(e);
        } else if (selectedId) {
            (async () => {
                try {
                    const res = await getWorkflowById(selectedId);
                    if (res.status === 'success') {
                        const { nodes: n, edges: e } = transformWorkflowToReactFlow(res.data);
                        setNodes(n);
                        setEdges(e);
                    }
                } catch (err) {
                    console.error("Failed to fetch workflow detail:", err);
                }
            })();
        }
    }, [psopStatus, selectedId]);

    // 停止执行
    const stopExecution = useCallback(() => {
        if (eventSource) {
            eventSource.close();
            setEventSource(null);
        }
        setIsRunning(false);
    }, [eventSource]);

    // 开始执行
    const startExecution = useCallback(() => {
        if (!selectedId) return;

        setError(null);
        setEvents([]);
        setPsopStatus(null);
        setIsRunning(true);
        setAutoScroll(true);

        const url = getStartProcessStreamUrl(selectedId);
        const es = new EventSource(url);

        es.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'agent_request' || data.type === 'agent_response') {
                    setEvents(prev => [...prev, data]);
                }

                switch (data.type) {
                    case 'psop_update':
                        try {
                            const status = typeof data.data.psop === 'string'
                                ? JSON.parse(data.data.psop)
                                : data.data.psop;
                            setPsopStatus(status);
                        } catch (e) {
                            console.error("Failed to parse psop_update data:", e);
                        }
                        break;
                    case 'complete':
                    case 'close':
                        setIsRunning(false);
                        es.close();
                        break;
                    case 'error':
                        setError(data.data.error);
                        setIsRunning(false);
                        es.close();
                        break;
                }
            } catch (err) {
                console.error("Failed to parse event data:", err);
            }
        };

        es.onerror = (err) => {
            setError("SSE Connection Error");
            setIsRunning(false);
            es.close();
        };

        setEventSource(es);
    }, [selectedId]);

    useEffect(() => {
        return () => {
            if (eventSource) eventSource.close();
        };
    }, [eventSource]);

    const theme = useMemo(() => ({
        sidebarCard: isDark
            ? 'bg-zinc-900 border-zinc-800 shadow-xl border-t-4 border-t-zinc-700'
            : 'bg-white border-zinc-200 shadow-xl border-t-4 border-t-zinc-300',
        mainCard: isDark
            ? 'bg-zinc-900 border-zinc-800 shadow-2xl'
            : 'bg-white border-slate-200 shadow-2xl',
        logCard: isDark
            ? 'bg-zinc-900/90 border-zinc-800 shadow-2xl backdrop-blur-xl'
            : 'bg-white/90 border-slate-200 shadow-2xl backdrop-blur-xl',
        intentInput: isDark
            ? 'bg-zinc-800 border-zinc-700 text-white placeholder-zinc-500'
            : 'bg-slate-100 border-slate-200 text-slate-900 placeholder-slate-400',
    }), [isDark]);

    const parseLogData = (data, type) => {
        const raw = type === 'agent_request' ? data.request : data.response;
        try {
            const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
            console.log(JSON.stringify(parsed, null, 2));

            return JSON.stringify(parsed, null, 2);
        } catch (e) {
            return String(raw);
        }
    };

    return (
        <div className="h-full p-8 flex flex-col gap-8 max-w-[1750px] mx-auto w-full transition-all animate-in fade-in duration-500 overflow-hidden font-sans">
            <div className={`shrink-0 rounded-[3rem] border flex items-center justify-between px-10 py-6 bg-zinc-50/10 dark:bg-zinc-900/40 ${theme.mainCard} shadow-xl`}>

                <div className="flex-1 relative group mr-12 min-w-0">
                    <Search size={22} className="absolute left-6 top-1/2 -translate-y-1/2 text-zinc-400 group-focus-within:text-blue-500 transition-colors" />
                    <input
                        type="text"
                        value={userIntent}
                        onChange={(e) => setUserIntent(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleMatchIntent()}
                        placeholder="Talk to sequence engine (e.g., 'Deploy instance to prod env')..."
                        className={`w-full h-16 pl-16 pr-8 rounded-[1.5rem] border-2 text-lg font-bold outline-none transition-all duration-300 focus:shadow-[0_0_0_8px_rgba(59,130,246,0.1)] focus:border-blue-500 ${theme.intentInput}`}
                    />
                </div>

                <div className="shrink-0 flex items-center gap-8">
                    <div className="flex items-center gap-4 pr-8 border-r border-zinc-100 dark:border-zinc-800">
                        <button
                            onClick={handleMatchIntent}
                            disabled={isMatching || isGenerating || !userIntent.trim()}
                            className="flex items-center gap-3 px-8 h-16 bg-blue-600 hover:bg-blue-500 text-white rounded-[1.5rem] text-sm font-black uppercase tracking-wider transition-all active:scale-95 disabled:opacity-50 shadow-lg shadow-blue-500/20"
                        >
                            <Search size={18} strokeWidth={3} />
                            {isMatching ? 'Matching...' : 'Match'}
                        </button>

                        {isRunning ? (
                            <button
                                onClick={stopExecution}
                                className="flex items-center gap-3 px-8 h-16 bg-rose-600 hover:bg-rose-500 text-white rounded-[1.5rem] text-sm font-black transition-all shadow-xl active:scale-95 shadow-rose-600/20"
                            >
                                <StopCircle size={18} />
                                TERMINATE
                            </button>
                        ) : (
                            <button
                                onClick={startExecution}
                                disabled={!selectedId}
                                className="group flex items-center gap-3 px-8 h-16 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:grayscale text-white rounded-[1.5rem] text-sm font-black transition-all shadow-xl active:scale-95 relative overflow-hidden"
                            >
                                <Zap size={18} className="fill-white" />
                                EXECUTE
                            </button>
                        )}
                    </div>

                    <div className="flex flex-col items-end">
                        <span className="text-[9px] font-black uppercase tracking-widest text-zinc-400">Engine Status</span>
                        <div className="flex items-center gap-2">
                            <div className={`w-2 h-2 rounded-full ${isRunning ? 'bg-emerald-500 animate-ping' : (psopStatus ? 'bg-emerald-500' : 'bg-zinc-300 dark:bg-zinc-700')}`} />
                            <span className={`text-[11px] font-black uppercase tracking-wider ${isRunning ? 'text-emerald-500' : 'dark:text-white'}`}>
                                {isRunning ? t('execution.running') : (psopStatus ? t('execution.completed') : 'Ready')}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <div className="flex-1 flex gap-8 min-h-0 overflow-hidden">
                <div className={`flex-1 flex flex-col rounded-[3.5rem] border overflow-hidden relative shadow-2xl ${theme.mainCard}`}>
                    <div className="px-10 py-8 border-b border-zinc-100 dark:border-zinc-800 flex justify-between items-center bg-zinc-50/5 dark:bg-zinc-900/20">
                        <div className="flex items-center gap-4">
                            <h2 className="text-xl font-black uppercase dark:text-white tracking-tight italic">
                                {(isMatching || isGenerating) ? 'Processing Input...' : (nodes.length > 0 ? (workflowSource === 'generated' ? 'AI Planned sequence' : 'Workflow') : 'Workflow Interface')}
                            </h2>
                            {workflowSource && (
                                <span className={`px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider ${workflowSource === 'generated' ? 'bg-purple-100 dark:bg-purple-900/40 text-purple-600' : 'bg-blue-100 dark:bg-blue-900/40 text-blue-600'}`}>
                                    {workflowSource === 'generated' ? 'AI Gen' : 'Native'}
                                </span>
                            )}
                        </div>
                    </div>

                    <div className="flex-1 relative bg-white dark:bg-zinc-950">
                        {isGenerating && (
                            <div className="absolute inset-0 z-[60] flex flex-col items-center justify-center bg-white/60 dark:bg-zinc-950/60 backdrop-blur-md">
                                <Zap size={48} className="text-blue-600 animate-bounce mb-6" />
                                <h3 className="text-lg font-black uppercase tracking-widest text-blue-600">Generating workflow...</h3>
                            </div>
                        )}

                        {selectedId || nodes.length > 0 ? (
                            <UnifiedWorkflow
                                mode="view"
                                isDark={isDark}
                                nodes={nodes}
                                edges={edges}
                                isLoading={(isRunning && nodes.length === 0) || isMatching}
                                loadingMessage={isMatching ? 'Matching...' : t('execution.init')}
                            />
                        ) : (
                            !isGenerating && (
                                <div className="h-full flex flex-col items-center justify-center opacity-10">
                                    <Bot size={100} />
                                    <p className="text-xl font-black uppercase tracking-[0.3em] mt-8">Standby</p>
                                </div>
                            )
                        )}

                        {error && (
                            <div className="absolute top-6 left-1/2 -translate-x-1/2 px-8 py-4 bg-white dark:bg-rose-500/10 border border-rose-500/50 backdrop-blur-xl rounded-2xl flex items-center gap-4 text-rose-500 shadow-2xl z-[50]">
                                <AlertCircle size={20} />
                                <p className="text-sm font-bold uppercase font-mono tracking-tighter">{error}</p>
                                <button onClick={() => setError(null)} className="ml-4 opacity-50 hover:opacity-100">
                                    <Plus size={18} className="rotate-45" />
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                <div className={`w-[500px] rounded-[3.5rem] border flex flex-col overflow-hidden shadow-2xl ${theme.logCard} shrink-0`}>
                    <div className="px-10 py-8 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between shrink-0">
                        <div className="flex items-center gap-4">
                            <div className="p-3 bg-blue-500/10 rounded-xl">
                                <Terminal size={20} className="text-blue-500" />
                            </div>
                            <h3 className="text-lg font-black uppercase tracking-widest dark:text-white">Interaction</h3>
                        </div>
                        {!autoScroll && (
                            <button onClick={() => setAutoScroll(true)} className="text-[10px] font-black text-blue-600 hover:text-blue-500 uppercase">
                                Sync
                            </button>
                        )}
                    </div>

                    <div ref={logScrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-10 space-y-8 custom-scrollbar scroll-smooth">
                        {events.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center opacity-20 italic text-sm gap-4">
                                <History size={48} className="mb-2" />
                                <p className="font-black uppercase tracking-[0.2em]">Idle</p>
                            </div>
                        ) : (
                            events.map((event, index) => (
                                <div key={index} className="relative pl-8 border-l-2 border-zinc-100 dark:border-zinc-800/50 animate-in-basic">
                                    <div className={`absolute -left-[9px] top-0 w-4 h-4 rounded-full border-4 ${isDark ? 'border-zinc-900' : 'border-white'} 
                                        ${event.type === 'agent_request' ? 'bg-blue-500' : 'bg-purple-500'}`}
                                    />
                                    <div className="flex items-center justify-between mb-3">
                                        <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded ${event.type === 'agent_request' ? 'bg-blue-100 dark:bg-blue-500/10 text-blue-600' : 'bg-purple-100 dark:bg-purple-500/10 text-purple-600'}`}>
                                            {event.type.replace('agent_', '')}
                                        </span>
                                        <span className="text-[10px] font-mono opacity-30">{new Date(event.timestamp * 1000).toLocaleTimeString()}</span>
                                    </div>
                                    <div className="p-6 rounded-[2rem] border border-zinc-100 dark:border-zinc-800 bg-white/50 dark:bg-zinc-800/30 text-[13px] leading-relaxed dark:text-zinc-300">
                                        <div className="flex items-center gap-2 mb-2 pb-2 border-b border-dashed border-zinc-100 dark:border-zinc-800/50">
                                            <Bot size={12} className="text-zinc-400" />
                                            <span className="text-[10px] font-black uppercase text-zinc-500 tracking-wider font-mono">{event.data.agent}</span>
                                        </div>
                                        <div className="opacity-80 break-words font-mono whitespace-pre-wrap text-[11px] bg-zinc-50/50 dark:bg-black/20 p-4 rounded-xl border border-zinc-100 dark:border-zinc-800/50 overflow-x-auto max-h-[400px]">
                                            {parseLogData(event.data, event.type)}
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};


export default ExecutionCenter;
