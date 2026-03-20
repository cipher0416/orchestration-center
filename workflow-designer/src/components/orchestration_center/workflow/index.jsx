import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    ReactFlow,
    ReactFlowProvider,
    Controls,
    Background,
    MarkerType,
    useReactFlow,
    useNodesState,
    useEdgesState,
    addEdge
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Layers } from 'lucide-react';
import { useTranslation } from "react-i18next";

import AgentNode from './CustomNodes/AgentNode/index.jsx';
import { EndNode, StartNode } from "./CustomNodes/CircleNode/index.jsx";
import { SmartStepEdge } from '@tisoap/react-flow-smart-edge';
import FloatingEdge from "./CustomEdges/FloatingEdge/index.jsx";
import Toolbar from "./toolbar/index.jsx";
import ToolbarLite from "./toolbar_lite/index.jsx";
import WorkflowLoader from "./loading/index.tsx";
import PropertyPanel from "./property_panel/index.jsx";
import Sidebar from "./siderbar/index.jsx";

const nodeTypes = {
    agentNode: AgentNode,
    startNode: StartNode,
    endNode: EndNode,
};

const edgeTypes = {
    smart: SmartStepEdge,
    floating: FloatingEdge,
};

const initialEditNodes = [
    {
        id: 'startNode',
        type: 'startNode',
        position: { x: 400, y: 50 },
        data: { description: 'this is the start node', name: 'start_node', status: 'start-event' }
    },
    {
        id: 'endNode',
        type: 'endNode',
        position: { x: 400, y: 600 },
        data: { description: 'this is a end node.', status: 'end_node', type: 'end-event' }
    }
];

const FlowInner = ({
                       mode,
                       isDark,
                       // View 模式 Props
                       viewNodes = [],
                       viewEdges = [],
                       onSelectChange,
                       // Edit 模式 Props
                       importedNodes,
                       importedEdges,
                       onCancel
                   }) => {
    const { t } = useTranslation();
    const { screenToFlowPosition, fitView, setCenter, getNode } = useReactFlow();
    const [rfInstance, setRfInstance] = useState(null);

    const themeClasses = useMemo(() => ({
        container: isDark ? 'bg-[#0f172a] text-slate-200' : 'bg-[#f8fafc] text-slate-900',
        gridColor: isDark ? '#334155' : '#cbd5e1',
        activeEdgeColor: '#3b82f6',
        activeStrokeWidth: 2,
        inactiveEdgeColor: isDark ? '#475569' : '#94a3b8',
        inactiveStrokeWidth: 1,
        panel: isDark ? 'bg-slate-900/80 border-slate-700 shadow-[0_0_20px_rgba(0,0,0,0.4)]' : 'bg-white/80 border-white/20 shadow-2xl',
    }), [isDark]);

    const [viewSelectedNodeId, setViewSelectedNodeId] = useState(null);

    const processedNodes = useMemo(() => {
        if (mode !== 'view') return [];
        return viewNodes.map(node => ({
            ...node,
            data: { ...node.data, isDark },
            selected: node.id === viewSelectedNodeId,
        }));
    }, [viewNodes, viewSelectedNodeId, isDark, mode]);

    const processedEdges = useMemo(() => {
        if (mode !== 'view') return [];

        const nodeMap = new Map();
        viewNodes.forEach(n => {
            nodeMap.set(n.id, {
                status: n.data?.status || 'not_executed',
                type: n.type
            });
        });

        const sourceOutgoingStats = new Map();
        viewEdges.forEach(edge => {
            const targetNode = nodeMap.get(edge.target);
            if (!targetNode) return;
            if (!sourceOutgoingStats.has(edge.source)) {
                sourceOutgoingStats.set(edge.source, { hasExecutedChild: false });
            }
            const stats = sourceOutgoingStats.get(edge.source);
            if (targetNode.status === 'executed' && targetNode.type !== 'endNode') {
                stats.hasExecutedChild = true;
            }
        });

        return viewEdges.map(edge => {
            const sourceNode = nodeMap.get(edge.source);
            const targetNode = nodeMap.get(edge.target);
            const sourceStats = sourceOutgoingStats.get(edge.source);
            if (!sourceNode || !targetNode) return edge;

            const isSourcePassed = ['executed', 'current'].includes(sourceNode.status) || sourceNode.type === 'startNode';
            const isTargetActive = ['executed', 'current'].includes(targetNode.status);
            let isActive = isSourcePassed && isTargetActive;

            if (isActive && (targetNode.type === 'endNode' || targetNode.status === 'current')) {
                if (sourceStats && sourceStats.hasExecutedChild) isActive = false;
            }

            return {
                ...edge,
                label: null,
                animated: isActive,
                style: {
                    ...edge.style,
                    stroke: isActive ? themeClasses.activeEdgeColor : themeClasses.inactiveEdgeColor,
                    strokeWidth: isActive ? themeClasses.activeStrokeWidth : themeClasses.inactiveStrokeWidth,
                    opacity: isActive ? 1 : 0.5,
                },
                markerEnd: {
                    type: MarkerType.ArrowClosed,
                    color: isActive ? themeClasses.activeEdgeColor : themeClasses.inactiveEdgeColor,
                },
                zIndex: isActive ? 10 : 0,
            };
        });
    }, [viewEdges, viewNodes, themeClasses, mode]);

    useEffect(() => {
        if (mode === 'view' && viewNodes.length > 0) {
            const currentNode = viewNodes.find(n => n.data?.status === 'current')
                || viewNodes.find(n => n.type === 'startNode' && n.data?.status !== 'executed');

            if (currentNode) {
                const timer = setTimeout(() => {
                    const internalNode = getNode(currentNode.id);
                    const width = internalNode?.measured?.width || currentNode.width || 180;
                    const height = internalNode?.measured?.height || currentNode.height || 60;
                    setCenter(currentNode.position.x + width / 2, currentNode.position.y + height / 2, { zoom: 1.2, duration: 1000 });
                }, 100);
                return () => clearTimeout(timer);
            } else {
                fitView({ padding: 0.2, duration: 800 });
            }
        }
    }, [viewNodes, setCenter, getNode, fitView, mode]);

    const [editNodes, setEditNodes, onNodesChange] = useNodesState(initialEditNodes);
    const [editEdges, setEditEdges, onEdgesChange] = useEdgesState([]);
    const [selectedElement, setSelectedElement] = useState(null);
    const [phenomenon, setPhenomenon] = useState("");

    useEffect(() => {
        if (mode === 'edit' && importedNodes?.length > 0) {
            setEditNodes(importedNodes.map(node => ({ ...node, data: { ...node.data, isDark } })));
            // setTimeout(() => fitView({ padding: 0.2, duration: 800 }), 100);
        }
    }, [importedNodes, setEditNodes, isDark, fitView, mode]);

    useEffect(() => {
        if (mode === 'edit' && importedEdges) {
            setEditEdges(importedEdges.map(edge => ({
                ...edge,
                // type: edge.type || 'smart',
                animated: edge.animated !== undefined ? edge.animated : true,
            })));
            setTimeout(() => fitView({ padding: 0.2, duration: 800 }), 400);
        }
    }, [importedEdges, setEditEdges, mode,fitView]);

    const onDeleteSelected = useCallback(() => {
        if (!selectedElement) return;
        if (selectedElement.id === 'startNode' || selectedElement.id === 'endNode') return;

        if (editNodes.some(n => n.id === selectedElement.id)) {
            setEditNodes((nds) => nds.filter((node) => node.id !== selectedElement.id));
            setEditEdges((eds) => eds.filter((edge) => edge.source !== selectedElement.id && edge.target !== selectedElement.id));
        } else {
            setEditEdges((eds) => eds.filter((edge) => edge.id !== selectedElement.id));
        }
        setSelectedElement(null);
    }, [selectedElement, editNodes, setEditNodes, setEditEdges]);

    const onConnect = useCallback((params) => {
        const newEdge = {
            ...params,
            type: 'smart',
            animated: true,
            markerEnd: { type: MarkerType.ArrowClosed, color: isDark ? '#3b82f6' : '#2563eb' },
            style: { strokeWidth: 2, stroke: isDark ? '#3b82f6' : '#2563eb' }
        };
        setEditEdges((eds) => addEdge(newEdge, eds));
    }, [setEditEdges, isDark]);

    const onDrop = useCallback((event) => {
        event.preventDefault();
        const rawData = event.dataTransfer.getData('application/agent-template');
        if (!rawData) return;
        try {
            const templateData = JSON.parse(rawData);
            const nextIndex = editNodes.filter(n => n.id.startsWith('checkStep')).length + 1;
            const newId = `checkStep${nextIndex}`;
            const newNode = {
                id: newId,
                type: 'agentNode',
                position: screenToFlowPosition({ x: event.clientX, y: event.clientY }),
                data: { ...templateData, task: templateData.defaultTask, input_params: {}, status: 'not_executed', name: newId, isDark },
            };
            setEditNodes((nds) => nds.concat(newNode));
        } catch (error) {
            console.error(t('error.parse_failed'), error);
        }
    }, [editNodes, screenToFlowPosition, setEditNodes, isDark, t]);

    const displayNodes = mode === 'view' ? processedNodes : editNodes;
    const displayEdges = mode === 'view' ? processedEdges : editEdges;

    return (
        <div className={`h-full w-full relative overflow-hidden transition-colors duration-300 ${themeClasses.container}`}>
            <ReactFlow
                nodes={displayNodes}
                edges={displayEdges}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                onNodesChange={mode === 'edit' ? onNodesChange : undefined}
                onEdgesChange={mode === 'edit' ? onEdgesChange : undefined}
                onConnect={mode === 'edit' ? onConnect : undefined}
                onDrop={mode === 'edit' ? onDrop : undefined}
                onDragOver={mode === 'edit' ? (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; } : undefined}
                onSelectionChange={mode === 'edit' ? (({ nodes, edges }) => setSelectedElement(nodes[0] || edges[0] || null)) : undefined}
                onNodeClick={(e, n) => {
                    if (mode === 'view') {
                        e.stopPropagation();
                        setViewSelectedNodeId(n.id);
                        if (onSelectChange) onSelectChange(n);
                    }
                }}
                onPaneClick={() => {
                    if (mode === 'view') {
                        setViewSelectedNodeId(null);
                        if (onSelectChange) onSelectChange(null);
                    }
                }}
                nodesConnectable={mode === 'edit'}
                nodesDraggable={true}
                elementsSelectable={true}
                onInit={setRfInstance}
                colorMode={isDark ? 'dark' : 'light'}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                proOptions={{ hideAttribution: true }}
                defaultEdgeOptions={{
                    type: mode === 'edit' ? 'smoothstep' : 'straight',
                    animated: false,
                }}
            >
                <Background color={themeClasses.gridColor} gap={20} variant="dots" />
                <Controls showInteractive={mode === 'edit'} position="bottom-right" />
            </ReactFlow>

            {mode === 'view' && (
                <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-5 pointer-events-none">
                    <div className="pointer-events-auto">
                        <ToolbarLite isDark={isDark} onFitView={() => fitView({ padding: 0.2, duration: 800 })} />
                    </div>
                </div>
            )}

            {mode === 'edit' && (
                <>
                    <div className="absolute top-6 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
                        <div className="pointer-events-auto">
                            <Toolbar isDark={isDark} nodes={editNodes} edges={editEdges} onCancel={onCancel} onClear={() => { setEditNodes(initialEditNodes); setEditEdges([]); }} onFitView={() => fitView({ padding: 0.4, duration: 800 })} phenomenon={phenomenon} />
                        </div>
                    </div>
                    <div className="absolute justify-center left-8 top-12 bottom-12 w-32 z-40 pointer-events-none flex flex-col min-h-0">
                        <div className={`pointer-events-auto flex flex-col backdrop-blur-md border rounded-2xl overflow-hidden transition-all ${themeClasses.panel}`}>
                            <Sidebar isDark={isDark} />
                        </div>
                    </div>
                    <div className={`absolute justify-center right-4 top-4 bottom-4 w-80 z-40 pointer-events-none flex flex-col min-h-0 transition-all duration-300 transform ${selectedElement ? 'translate-x-0 opacity-100' : 'translate-x-10 opacity-0'}`}>
                        <div className={`pointer-events-auto flex flex-col backdrop-blur-md border rounded-2xl overflow-hidden ${themeClasses.panel}`}>
                            {selectedElement && (
                                <PropertyPanel isDark={isDark} selectedElement={selectedElement} nodes={editNodes} edges={editEdges} setNodes={setEditNodes} setEdges={setEditEdges} onDelete={onDeleteSelected} setPhenomenon={setPhenomenon} />
                            )}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};
const UnifiedWorkflow = ({
                             mode = 'view',
                             isDark = false,
                             nodes = [],
                             edges = [],
                             isLoading = false,
                             loadingMessage = "Loading workflow...",
                             onSelectChange,
                             visible = true,
                             importedNodes,
                             importedEdges,
                             onCancel
                         }) => {
    if (mode === 'view' && isLoading) {
        return <WorkflowLoader isDark={isDark} loadingMessage={loadingMessage} />;
    }

    if (mode === 'view' && !isLoading && nodes.length === 0) {
        return (
            <div className="w-full h-full min-h-[300px] flex flex-col items-center justify-center p-8 bg-zinc-50/50 dark:bg-zinc-800/20 rounded-[2rem] border-2 border-dashed border-zinc-200 dark:border-zinc-700/50 transition-all duration-300">
                <div className="w-20 h-20 mb-6 rounded-3xl bg-white dark:bg-zinc-800/80 shadow-md flex items-center justify-center border border-zinc-100 dark:border-zinc-700/50">
                    <Layers className="w-10 h-10 text-zinc-300 dark:text-zinc-600" strokeWidth={1.5} />
                </div>
                <h3 className="text-lg font-black text-zinc-600 dark:text-zinc-300 mb-2 tracking-tight">No Workflow Data</h3>
                <p className="text-sm text-zinc-400 dark:text-zinc-500 max-w-sm text-center leading-relaxed">
                    There are no nodes or edges to display for this execution record.
                </p>
            </div>
        );
    }

    const baseBg = isDark ? "bg-[#0f172a]" : "bg-[#f8fafc]";
    const editWrapperClass = visible
        ? `absolute inset-0 z-[50] translate-y-0 opacity-100 transition-all duration-300 ${baseBg}`
        : `absolute inset-0 z-[-1] translate-y-4 opacity-0 pointer-events-none transition-all duration-300 ${baseBg}`;

    return (
        <div className={mode === 'edit' ? editWrapperClass : "w-full h-full min-h-[300px]"}>
            <ReactFlowProvider>
                <FlowInner
                    mode={mode}
                    isDark={isDark}
                    viewNodes={nodes}
                    viewEdges={edges}
                    onSelectChange={onSelectChange}
                    importedNodes={importedNodes}
                    importedEdges={importedEdges}
                    onCancel={onCancel}
                />
            </ReactFlowProvider>
        </div>
    );
};

export default UnifiedWorkflow;