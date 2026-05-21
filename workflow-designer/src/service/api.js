import axios from "axios";

const STORAGE_KEY = 'server_config';
export const defaultIp = '127.0.0.1';
export const defaultPort = '60000';
export const defaultGateway = 'http://127.0.0.1/orchestration';

const trimTrailingSlash = (url) => url.replace(/\/$/, '');

export const getBaseUrl = () => {
    try {
        const saved = localStorage.getItem(STORAGE_KEY);
        const config = saved ? JSON.parse(saved) : {};
        if (config.mode === 'nginx') {
            return trimTrailingSlash(config.nginxUrl || config.gatewayUrl || defaultGateway);
        }
        const ip = config.ip || defaultIp;
        const port = config.port || defaultPort;
        return `http://${ip}:${port}`;
    } catch (e) {
        return `http://${defaultIp}:${defaultPort}`;
    }
}

const ORCHESTRATE_BASE = () => `${getBaseUrl()}/rest/v1/orchestrate`;

const api = axios.create({ timeout: 10000 });

api.interceptors.response.use(
    (response) => response.data,
    (error) => Promise.reject(error)
);

// ──── Agent Cards ────

export async function getAgentCards() {
    return api.get(`${ORCHESTRATE_BASE()}/agent-cards`);
}

// ──── Workflow CRUD ────

export async function getWorkflow() {
    return api.get(`${ORCHESTRATE_BASE()}/workflows`);
}

export async function getWorkflowById(id) {
    return api.get(`${ORCHESTRATE_BASE()}/workflows/${id}`);
}

export async function delWorkflowById(id) {
    return api.delete(`${ORCHESTRATE_BASE()}/workflows/${id}`);
}

export async function createWorkflow(data) {
    return api.post(`${ORCHESTRATE_BASE()}/workflows`, { psop: data });
}

// ──── Workflow Templates ────

export async function getTemplates() {
    return api.get(`${ORCHESTRATE_BASE()}/templates`);
}

export async function importTemplate(templateId) {
    return api.post(`${ORCHESTRATE_BASE()}/templates/${templateId}/import`);
}

// ──── PDF Parsing ────

export async function parsePdf(file) {
    const formData = new FormData();
    formData.append('file', file);
    try {
        const response = await axios.post(`${ORCHESTRATE_BASE()}/parse-pdf`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        const body = response.data;
        if (body.code === 200 || body.status === "success") {
            return body.data;
        }
        throw new Error(body?.message || "PDF parsing failed");
    } catch (error) {
        const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || "PDF parsing request failed";
        throw new Error(errorMsg);
    }
}

// ──── Workflow Generation ────

export async function handlePlan(preflow, agentCards) {
    try {
        const response = await axios.post(`${ORCHESTRATE_BASE()}/generate-from-preflow`, {
            preflow: preflow,
            agent_cards: agentCards
        });
        const body = response.data;
        if (body.code === 200 || body.status === "success") {
            return body.data;
        }
        throw new Error(body?.message || "Planning generation failed");
    } catch (error) {
        const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || "Planning request failed";
        throw new Error(errorMsg);
    }
}

export async function generateWorkflowFromIntent(intent, name = "Generated Workflow") {
    try {
        const response = await axios.post(`${ORCHESTRATE_BASE()}/generate-from-intent`, {
            user_intent: intent,
            workflow_name: name
        });
        const body = response.data;
        if (body.code === 200 || body.status === "success") {
            return body.data || body;
        }
        throw new Error(body?.message || "Generation failed");
    } catch (error) {
        const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || "Intent generation request failed";
        throw new Error(errorMsg);
    }
}

export async function matchWorkflows(intent) {
    try {
        const response = await axios.post(`${ORCHESTRATE_BASE()}/retrieve-by-intent`, {
            user_intent: intent,
        });
        const body = response.data;
        if (body.code === 200 || body.status === "success") {
            const data = body.data;
            if (!data) return [];
            const list = Array.isArray(data) ? data : [data];
            return list.map(item => ({
                workflow_id: item.id || item.workflow_id,
                name: item.name || item.workflow_name,
                description: item.description,
                tags: item.tags || []
            }));
        }
        throw new Error(body?.message || "Retrieval failed");
    } catch (error) {
        const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || "Retrieval request failed";
        throw new Error(errorMsg);
    }
}

// ──── Workflow Execution ────

export function getStartProcessStreamUrl(psopId, userIntent = '') {
    const base = `${ORCHESTRATE_BASE()}/execute?psop_id=${psopId}`;
    if (userIntent) {
        return `${base}&user_intent=${encodeURIComponent(userIntent)}`;
    }
    return base;
}

// ──── Execution Records ────

export async function getExecutionRecords() {
    return api.get(`${ORCHESTRATE_BASE()}/execution-records`);
}

export async function getExecutionRecord(executionId) {
    return api.get(`${ORCHESTRATE_BASE()}/execution-records/${executionId}`);
}

export async function deleteExecutionRecord(executionId) {
    return api.delete(`${ORCHESTRATE_BASE()}/execution-records/${executionId}`);
}


