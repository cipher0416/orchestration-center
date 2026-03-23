import dagre from 'dagre';

/**
 * 后端标准状态枚举
 */
export const BACKEND_STATUS = {
    PENDING: 'pending',
    RUNNING: 'running',
    SUCCESS: 'success',
    FAILED: 'failed'
};

export const normalizeStatus = (status) => {
    const s = String(status || '').toLowerCase();
    if (s.includes('run') || s === 'executing') return BACKEND_STATUS.RUNNING;
    if (s.includes('success') || s === 'completed' || s === 'executed') return BACKEND_STATUS.SUCCESS;
    if (s.includes('fail') || s === 'error') return BACKEND_STATUS.FAILED;
    return BACKEND_STATUS.PENDING;
};

/**
 * 2. Dagre 自动排版逻辑
 */
export const getLayoutedElements = (nodes, edges, direction = 'TB') => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({ rankdir: direction, ranksep: 100, nodesep: 80 });

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: node.width, height: node.height });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        return {
            ...node,
            position: {
                x: nodeWithPosition.x - node.width / 2,
                y: nodeWithPosition.y - node.height / 2,
            },
        };
    });

    return { nodes: layoutedNodes, edges };
};

/**
 * 3. 动态计算最佳 Handle 连线点
 */
export const getBestHandles = (sourceNode, targetNode) => {
    const sPos = sourceNode.position;
    const tPos = targetNode.position;

    const sCenter = { x: sPos.x + (sourceNode.width || 200) / 2, y: sPos.y + (sourceNode.height || 100) / 2 };
    const tCenter = { x: tPos.x + (targetNode.width || 200) / 2, y: tPos.y + (targetNode.height || 100) / 2 };

    const dx = tCenter.x - sCenter.x;
    const dy = tCenter.y - sCenter.y;

    if (Math.abs(dy) > Math.abs(dx)) {
        return dy > 0
            ? { sourceHandle: 's-bottom', targetHandle: 't-top' }
            : { sourceHandle: 's-top', targetHandle: 't-bottom' };
    } else {
        return dx > 0
            ? { sourceHandle: 's-right', targetHandle: 't-left' }
            : { sourceHandle: 's-left', targetHandle: 't-right' };
    }
};

/**
 * 4. 导入转换：PSOP JSON -> React Flow Nodes/Edges
 */
export const transformWorkflowToReactFlow = (rawInput) => {
    // 兼容 API 返回的 { data: { steps: [] } } 结构
    const data = rawInput?.data ? rawInput.data : rawInput;

    if (!data || (!data.steps && !Array.isArray(data))) {
        console.warn("无效的工作流数据格式");
        return { nodes: [], edges: [] };
    }

    const steps = Array.isArray(data) ? data : (data.steps || []);
    const nodes = [];
    const edges = [];
    const targetStepNames = new Set();

    steps.forEach((step, index) => {
        let nextSteps = [];
        if (step.next && Array.isArray(step.next) && step.next.length > 0) {
            nextSteps = step.next;
        } else if (index < steps.length - 1) {
            nextSteps = [{ step: steps[index + 1].name, condition: '' }];
        }
        nextSteps.forEach(link => {
            const targetId = link.step || link.target || 'END';
            if (!['END', 'end', 'END_OF_WORKFLOW'].includes(targetId)) targetStepNames.add(targetId);
        });
        step._normalizedNext = nextSteps;
    });

    // 生成节点
    steps.forEach((step) => {
        const nodeId = step.name;
        const agents = step.subtasks?.map(t => t.agent).join(', ') || 'System';
        const skills = step.subtasks?.map(t => t.skill).join(', ') || 'None';
        const nodeStatus = step.subtasks?.some(t => t.status === 'running')
            ? 'running'
            : (step.subtasks?.every(t => t.status === 'success') ? 'success' : 'pending');

        nodes.push({
            id: nodeId,
            type: 'agentNode',
            position: { x: 0, y: 0 },
            width: 250,
            height: 110,
            data: {
                ...step,
                label: step.name,
                description: step.subtasks?.[0]?.description || '',
                agent: agents,
                skill: skills,
                status: nodeStatus
            }
        });

        step._normalizedNext?.forEach((link, idx) => {
            const rawTarget = link.step || link.target;
            const targetId = ['end', 'END'].includes(rawTarget) ? 'END_OF_WORKFLOW' : rawTarget;
            edges.push({
                id: `e-${nodeId}-${targetId}-${idx}`,
                source: nodeId,
                target: targetId,
                label: link.condition || '',
                animated: nodeStatus === 'running',
                style: { stroke: '#94a3b8', strokeWidth: 2 }
            });
        });
    });

    const startNodes = steps.filter(s => !targetStepNames.has(s.name));
    if (startNodes.length > 0) {
        nodes.unshift({ id: 'START_NODE', type: 'startNode', position: { x: 0, y: 0 }, width: 120, height: 50, data: { label: 'START', status: 'completed' } });
        startNodes.forEach(sn => edges.unshift({ id: `e-start-${sn.name}`, source: 'START_NODE', target: sn.name, style: { stroke: '#94a3b8', strokeDasharray: '5,5' } }));
    }

    const terminalNodes = steps.filter(s => !s._normalizedNext || s._normalizedNext.length === 0);
    if (edges.some(e => e.target === 'END_OF_WORKFLOW') || terminalNodes.length > 0) {
        if (!nodes.find(n => n.id === 'END_OF_WORKFLOW')) {
            nodes.push({ id: 'END_OF_WORKFLOW', type: 'endNode', position: { x: 0, y: 0 }, width: 120, height: 50, data: { label: 'END', status: 'pending' } });
        }
        terminalNodes.forEach(tn => edges.push({ id: `e-${tn.name}-implicit-end`, source: tn.name, target: 'END_OF_WORKFLOW', style: { stroke: '#94a3b8', strokeWidth: 2 } }));
    }

    steps.forEach(s => delete s._normalizedNext);
    const layouted = getLayoutedElements(nodes, edges, 'TB');
    const finalEdges = layouted.edges.map(edge => {
        const sourceNode = layouted.nodes.find(n => n.id === edge.source);
        const targetNode = layouted.nodes.find(n => n.id === edge.target);
        if (sourceNode && targetNode) {
            const { sourceHandle, targetHandle } = getBestHandles(sourceNode, targetNode);
            return { ...edge, sourceHandle, targetHandle };
        }
        return edge;
    });

    return { nodes: layouted.nodes, edges: finalEdges };
};

/**
 * 5. 导出转换：React Flow Nodes/Edges -> PSOP JSON
 */
export const transformReactFlowToPSOP = (nodes, edges, metadata = {}) => {
    const psopData = {
        name: metadata.name || "New Workflow",
        description: metadata.description || "",
        steps: [],
        tags: metadata.tags || []
    };

    const stepsMap = {};

    nodes.forEach((node) => {
        const { id, type, data } = node;
        if (['START_NODE', 'END_OF_WORKFLOW', 'startNode', 'endNode'].includes(type) ||
            ['START_NODE', 'END_OF_WORKFLOW'].includes(id)) return;

        if (type === 'agentNode') {
            let subtasks = [];
            if (data.subtasks && Array.isArray(data.subtasks)) {
                subtasks = data.subtasks.map(t => ({
                    description: t.description || data.description || id,
                    agent: t.agent || data.agent,
                    skill: t.skill || data.skill,
                    status: normalizeStatus(t.status)
                }));
            } else {
                subtasks = [{
                    description: data.description || data.label || id,
                    agent: data.agent || 'System',
                    skill: data.skill || 'None',
                    status: normalizeStatus(data.status)
                }];
            }

            stepsMap[id] = {
                name: id,
                type: data.type || "AllSuccess",
                subtasks: subtasks,
                next: []
            };
        }
    });

    edges.forEach((edge) => {
        const { source, target, label, data: edgeData } = edge;
        if (source === 'START_NODE' || !stepsMap[source]) return;

        const targetId = (target === 'END_OF_WORKFLOW') ? 'end' : target;
        stepsMap[source].next.push({
            step: targetId,
            condition: label || edgeData?.condition || ""
        });
    });

    psopData.steps = Object.values(stepsMap).map(step => {
        if (step.next.length === 0) {
            const { next, ...rest } = step;
            return rest;
        }
        return step;
    });

    return psopData;
};