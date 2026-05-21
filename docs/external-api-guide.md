# Orchestration Center — External Integration Guide

## Overview

The Orchestration Center provides a public API (`/api/v1`) for external systems to
orchestrate and execute agent workflows. Three orchestration modes are supported:

| Mode | Endpoint | Input | Description |
|---|---|---|---|
| **SOP-based** | `POST /api/v1/orchestrate/sop` | SOP text, PDF, TXT, or MD file | Fixed-step business process → PSOP |
| **Intent-based** | `POST /api/v1/orchestrate/intent` | Natural language intent | Open-ended task → PSOP |
| **Auto-execute** | `POST /api/v1/orchestrate/execute` | Task description | Search → orchestrate → execute (SSE) |

**Base URL**: `http://<host>:<port>` (default `http://127.0.0.1:60000`)

---

## Common Response Envelope

All non-streaming responses use:

```json
{
  "code": 200,
  "message": "success",
  "status": "success",
  "data": <payload>
}
```

HTTP status codes: `200` (OK), `201` (Created), `400` (Bad Request), `404` (Not Found), `413` (Payload Too Large), `429` (Too Many Requests), `503` (Server Busy), `500` (Server Error).

### Error Response Format

All error responses follow the same envelope:

```json
{
  "detail": "Human-readable error message"
}
```

| HTTP Status | Typical Cause |
|---|---|
| `400` | Invalid request parameters, missing required fields, invalid file format |
| `404` | PSOP workflow or execution record not found, no agents available |
| `413` | File too large (max 100 MB) |
| `429` | Rate limit exceeded |
| `503` | Server is busy (concurrency limit reached) |
| `500` | Internal server error, LLM generation failure, agent communication error |

---

## Data Models

### PSOP

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | No | Unique workflow identifier (auto-generated UUID) |
| `name` | string | Yes | Workflow name |
| `description` | string | No | Brief workflow description |
| `created_at` | datetime | No | Creation timestamp (auto-generated) |
| `steps` | List[Step] | Yes | List of steps in the agent collaboration workflow |
| `related_preflow` | string | No | Associated PreFlow ID that this PSOP was generated from |
| `user_intent` | string | No | Original user intent that generated this workflow |
| `tags` | List[string] | No | Tags for quick filtering |

### Step

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Step identifier |
| `type` | StepType | No | Success condition: `AllSuccess` (all subtasks succeed) or `AnySuccess` (any subtask succeeds). Default: `AllSuccess` |
| `subtasks` | List[Task] | Yes | List of subtasks within the step. No dependencies between subtasks, can be executed in parallel |
| `next` | List[JumpCondition] | No | Jump conditions to next steps. If empty, unconditional jump |
| `layer` | int | No | Orchestration layer level. 0 = execution layer (leaf agents), 1+ = aggregation layers. Default: 0 |
| `context_from` | List[string] | No | List of step names whose outputs should be provided as context. Use `["*"]` for ALL previously executed steps. If None and layer > 0, predecessors are auto-derived from graph edges |

### Task

| Field | Type | Required | Description |
|---|---|---|---|
| `task_id` | string | No | Unique task identifier (auto-generated UUID) |
| `description` | string | Yes | Task description |
| `agent` | string | Yes | Name of the agent executing the task |
| `skill` | string | Yes | Skill required to execute the task |
| `status` | TaskStatus | No | Task execution status. Default: `pending` |

### TaskStatus (enum)

| Value | Description |
|---|---|
| `pending` | Task not yet started |
| `running` | Task currently executing |
| `success` | Task completed successfully |
| `failed` | Task execution failed |

### JumpCondition

| Field | Type | Required | Description |
|---|---|---|---|
| `step` | string | Yes | Target step name |
| `condition` | string | Yes | Condition description for jumping |

---

## 1. SOP-Based Orchestration

Generates a PSOP workflow from a structured SOP (Standard Operating Procedure).
Accepts either JSON text or a file upload (PDF, TXT, or MD).
**When both JSON body and file are provided, the file takes precedence.**

```
POST /api/v1/orchestrate/sop
```

### Request (JSON body)

```json
{
  "sop_content": "## Step 1: Dispatch diagnosis to both city OMCs\n\n- Agent: Transport Workbench Agent\n- Skill: dispatch-diagnosis\n\n## Step 2: City 1 performs leased-line fault diagnosis\n\n- Agent: SPN Fault Handling Agent City1 OMC\n- Skill: leased-line-diagnosis\n\n## Step 3: City 2 performs leased-line fault diagnosis\n\n- Agent: SPN Fault Handling Agent City2 OMC\n- Skill: leased-line-diagnosis\n\n## Step 4: Aggregate and generate summary report\n\n- Agent: Transport Workbench Agent\n- Skill: aggregate-analysis",
  "name": "SPN-Leased-Line-Diagnosis"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `sop_content` | string | Yes (if no file) | Natural language SOP steps (markdown text) |
| `name` | string | No | Workflow name (auto-generated if omitted) |

### Request (File upload)

```
Content-Type: multipart/form-data
file: <SolutionPackage.pdf|txt|md>
name: <Optional workflow name>
```

Supported file formats:
- **PDF**: Must contain chapter "5. Interaction Flow" with SOP steps. Filename validation: alphanumeric, hyphens, underscores, spaces, 1–128 chars + `.pdf` extension.
- **TXT / MD**: Plain text or Markdown SOP content. Same filename validation rules with `.txt` or `.md` extension.

The `name` field is optional; if omitted, the PDF filename is used. Maximum file size: 100 MB.

### Response (201 Created)

```json
{
  "code": 201,
  "message": "PSOP generated and saved",
  "status": "success",
  "data": {
    "id": "uuid",
    "name": "SPN-Leased-Line-Diagnosis",
    "description": null,
    "steps": [ /* Array<Step> */ ],
    "created_at": "2026-05-20T21:00:00",
    "related_preflow": "preflow-uuid",
    "user_intent": "## Step 1: Dispatch diagnosis...",
    "tags": []
  }
}
```

The `user_intent` field is automatically set to the first 200 characters of the SOP content. The `related_preflow` field links to the internally generated PreFlow.

### curl Example

```bash
# Text SOP
curl -X POST http://127.0.0.1:60000/api/v1/orchestrate/sop \
  -H "Content-Type: application/json" \
  -d '{"sop_content": "## Step 1: Dispatch diagnosis\n- Agent: Transport Workbench Agent\n- Skill: dispatch-diagnosis\n\n## Step 2: City OMC diagnosis\n- Agent: SPN Fault Handling Agent City1 OMC\n- Skill: spn-diagnosis", "name": "test"}'

# PDF upload with optional name
curl -X POST http://127.0.0.1:60000/api/v1/orchestrate/sop \
  -F "file=@SolutionPackage.pdf" \
  -F "name=SPN-Leased-Line-Diagnosis"

# TXT file upload
curl -X POST http://127.0.0.1:60000/api/v1/orchestrate/sop \
  -F "file=@sop_steps.txt"
```

---

## 2. Intent-Based Orchestration

Generates a PSOP workflow from a free-form natural language description.
No SOP steps required — the LLM plans the workflow autonomously.

```
POST /api/v1/orchestrate/intent
```

### Request

```json
{
  "intent": "Perform energy optimization across all base stations. First evaluate current energy consumption, then generate optimization strategies and deploy them.",
  "name": "Network-Wide-Energy-Optimization"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `intent` | string | Yes | Natural language task description |
| `name` | string | No | Workflow name (auto-generated if omitted) |

### Response (201 Created)

Same PSOP structure as SOP endpoint. The `user_intent` field records the original intent.

### curl Example

```bash
curl -X POST http://127.0.0.1:60000/api/v1/orchestrate/intent \
  -H "Content-Type: application/json" \
  -d '{"intent": "Optimize energy consumption across all base stations", "name": "Energy Optimization"}'
```

---

## 3. Auto-Orchestrate + Execute (SSE)

The primary external execution endpoint. Given a task description:
1. Searches existing PSOPs by semantic match
2. If found, executes the best match
3. If not found, auto-generates a new PSOP via intent orchestration, then executes

Returns a **Server-Sent Events (SSE)** stream with real-time execution progress.

**Important**: The `task` field is passed as `runtime_intent` to the execution engine. During execution, the engine injects the runtime intent into the context of **all steps** (including layer-0 leaf steps), so agents receive the user's original scenario description alongside their predefined task instructions. This ensures agents have the specific scenario data (e.g., "华为园区早上8点出现网络故障") needed to produce contextual responses.

```
POST /api/v1/orchestrate/execute
```

### Request

```json
{
  "task": "Diagnose leased-line faults in both city SPN networks and generate a summary report",
  "name": "SPN-Diagnosis"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `task` | string | Yes | Task description for search/orchestration. Also injected as runtime context into all execution steps |
| `name` | string | No | Workflow name for auto-generation |

### SSE Event Types

| Event | Direction | Description |
|---|---|---|
| `init` | → | Execution engine initialized |
| `start` | → | Workflow execution started |
| `agent_request` | → | Message sent to an agent |
| `agent_response` | ← | Agent's response received |
| `psop_update` | → | Full PSOP state updated (task status changes) |
| `complete` | → | Workflow execution completed successfully |
| `error` | → | Workflow execution failed |
| `close` | → | SSE connection closed |

### SSE Event Format

```
data: {"type":"agent_request","data":{"agent":"Transport Workbench Agent","request":"..."},"timestamp":1716230401.0}

data: {"type":"agent_response","data":{"agent":"Transport Workbench Agent","response":"..."},"timestamp":1716230403.0}

data: {"type":"complete","data":{"psop_id":"uuid","execution_history":[...]}}

event: close
data: {}
```

### Agent Request Event

```json
{
  "type": "agent_request",
  "data": {
    "agent": "Transport Workbench Agent",
    "request": "message_id: \"xxx\"\nrole: ROLE_AGENT\nparts {\n  text: \"task content\"\n}\n"
  },
  "timestamp": 1716230401.0
}
```

### Agent Response Event

```json
{
  "type": "agent_response",
  "data": {
    "agent": "Transport Workbench Agent",
    "response": "{\"id\":\"...\",\"status\":{\"state\":\"TASK_STATE_COMPLETED\"},\"artifacts\":[{\"parts\":[{\"text\":\"response content\"}]}]}"
  },
  "timestamp": 1716230403.0
}
```

### Complete Event

```json
{
  "type": "complete",
  "data": {
    "psop_id": "uuid",
    "execution_history": [
      {"step": "step1", "task": "task description", "status": "success", "output": "..."},
      {"step": "step2", "task": "task description", "status": "success", "output": "..."}
    ]
  }
}
```

Note: `execution_history` item `status` values are lowercase: `success` or `failed`.

### PSOP Update Event

Emitted after each subtask completes or fails. Contains the **full serialized PSOP object** with updated task statuses, not a summary.

```json
{
  "type": "psop_update",
  "data": {
    "psop": {
      "id": "uuid",
      "name": "SPN-Leased-Line-Diagnosis",
      "steps": [
        {
          "name": "step1",
          "type": "AllSuccess",
          "subtasks": [
            {
              "task_id": "uuid",
              "description": "Dispatch diagnosis...",
              "agent": "Transport Workbench Agent",
              "skill": "dispatch-diagnosis",
              "status": "success"
            }
          ],
          "next": null,
          "layer": 0,
          "context_from": null
        }
      ],
      "created_at": "2026-05-20T21:00:00",
      "tags": []
    }
  },
  "timestamp": 1716230402.0
}
```

The `psop` field contains a complete PSOP model (same structure as the Data Models section above). Task `status` values follow the TaskStatus enum: `pending`, `running`, `success`, `failed`.

### curl Example (SSE)

```bash
curl -N -X POST http://127.0.0.1:60000/api/v1/orchestrate/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "Diagnose leased-line faults in both city OMCs and generate a summary report"}'
```

### Client Integration Pattern (JavaScript)

```javascript
async function executeWorkflow(task) {
  const response = await fetch('http://127.0.0.1:60000/api/v1/orchestrate/execute', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const event = JSON.parse(line.slice(6));
        console.log(event.type, event.data);
      }
    }
  }
}
```

### Client Integration Pattern (Python)

```python
import requests
import json

def execute_workflow(task: str, base_url: str = "http://127.0.0.1:60000"):
    response = requests.post(
        f"{base_url}/api/v1/orchestrate/execute",
        json={"task": task},
        stream=True,
        headers={"Accept": "text/event-stream"}
    )

    for line in response.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            event = json.loads(line[6:])
            event_type = event.get("type")
            if event_type == "agent_response":
                print(f"[{event['data']['agent']}] {event['data']['response'][:100]}")
            elif event_type == "complete":
                print(f"Execution complete: {event['data']['psop_id']}")
                return event['data']
            elif event_type == "error":
                raise RuntimeError(event['data']['error'])
```

---

## 4. Execute Known PSOP

Execute a previously generated PSOP workflow by its ID. Returns an SSE stream.

```
GET /api/v1/orchestrate/execute/{psop_id}
```

### Path Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `psop_id` | string | Yes | The PSOP workflow ID (returned by SOP or intent orchestration) |

### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `user_intent` | string | No | Runtime user intent and scenario description. When provided, the engine injects this context into **all steps** (including layer-0 leaf steps), so agents receive the specific scenario alongside their predefined task instructions. This is critical when executing a retrieved PSOP — the original user intent contains scenario data that the PSOP's predefined tasks alone do not carry. |

### curl Example

```bash
# Execute without runtime context
curl -N http://127.0.0.1:60000/api/v1/orchestrate/execute/6a204d60-f2ff-471b-9892-c5beae1c3a5c

# Execute with runtime intent (recommended when PSOP was retrieved by intent matching)
curl -N "http://127.0.0.1:60000/api/v1/orchestrate/execute/6a204d60-f2ff-471b-9892-c5beae1c3a5c?user_intent=SPN%E4%B8%93%E7%BA%BF%E6%95%85%E9%9C%9C%E8%AF%81%E6%96%AD%EF%BC%8C%E5%8D%97%E9%9D%9E%E5%9B%AD%E5%8C%BA%E5%B7%A8%E8%AF%988%E7%82%B9%E5%87%BA%E7%8E%B0%E7%BD%AE%E7%BD%91%E6%95%9C%E9%9C%9C%E4%BA%86"
```

---

## 5. List Available Agents

Returns the complete agent inventory from the registry.

```
GET /api/v1/agents
```

### Response

```json
{
  "code": 200,
  "status": "success",
  "data": [
    {
      "name": "Transport Workbench Agent",
      "description": "Responsible for dispatching...",
      "version": "1.0.0",
      "provider": {"organization": "Huawei", "url": "https://www.huawei.com"},
      "skills": [
        {"id": "dispatch-diagnosis", "name": "Dispatch Diagnosis", "description": "...", "tags": ["wireless", "fault"]},
        {"id": "aggregate-analysis", "name": "Aggregate Analysis", "description": "...", "tags": ["wireless", "analysis"]}
      ],
      "capabilities": {"streaming": true, "pushNotifications": false, "extensions": []},
      "defaultInputModes": ["text", "json"],
      "defaultOutputModes": ["text", "json"],
      "supportedInterfaces": [
        {"protocolBinding": "HTTP+JSON", "protocolVersion": "1.0.0", "url": "http://127.0.0.1:8904"}
      ]
    }
  ]
}
```

The response data is a list of A2A AgentCard objects. The exact structure follows the A2A protocol specification and may include additional fields beyond what is shown above.

---

## 6. Get Execution Result

Retrieve the full execution record (all agent interactions, final PSOP state, execution history).

```
GET /api/v1/executions/{execution_id}
```

The `execution_id` is available in the `complete` SSE event or can be obtained from the execution records list.

### Path Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `execution_id` | string | Yes | The execution record ID |

### Response

```json
{
  "code": 200,
  "status": "success",
  "data": {
    "execution_id": "uuid",
    "psop_id": "uuid",
    "psop_name": "SPN-Leased-Line-Diagnosis",
    "started_at": "2026-05-20T21:00:00",
    "completed_at": "2026-05-20T21:00:45",
    "status": "success",
    "execution_history": [
      {"step": "step1", "task": "...", "status": "success", "output": "..."}
    ],
    "final_psop": { /* full PSOP with updated task statuses */ },
    "events": [ /* all agent_request/response events */ ],
    "error": null
  }
}
```

Note: `execution_history` item `status` values are lowercase: `success` or `failed`. The `final_psop` field contains a complete PSOP object with all task statuses updated to their final state.

---

## Integration Flow Summary

```
┌──────────────────┐
│ External System  │
└────────┬─────────┘
         │
         │  POST /api/v1/orchestrate/sop     ──→ PSOP (from SOP text/PDF/TXT/MD)
         │  POST /api/v1/orchestrate/intent  ──→ PSOP (from intent)
         │
         │  POST /api/v1/orchestrate/execute ──→ SSE stream (search + orchestrate + execute)
         │  GET  /api/v1/orchestrate/execute/{id}?user_intent=... ──→ SSE stream (execute known PSOP with context)
         │
         │  GET /api/v1/agents              ──→ Agent inventory
         │  GET /api/v1/executions/{id}     ──→ Execution result
         │
         ▼
┌──────────────────┐
│ Orchestration    │
│ Center           │
│  ┌─────────────┐ │
│  │ PSOP Engine │ │────→ Agent 1 (port 8899)
│  │             │ │────→ Agent 2 (port 8900)
│  │             │ │────→ ...
│  └─────────────┘ │
└──────────────────┘
```

## Typical Integration Pattern

```
1. GET /api/v1/agents                    → Discover available agents & skills
2. POST /api/v1/orchestrate/sop          → Create PSOP from SOP (or skip to step 3)
   or
   POST /api/v1/orchestrate/intent       → Create PSOP from intent
3. POST /api/v1/orchestrate/execute      → Execute (auto-search + auto-orchestrate + SSE stream)
   or
   GET /api/v1/orchestrate/execute/{id}?user_intent=... → Execute known PSOP with runtime context
4. GET /api/v1/executions/{execution_id} → Retrieve detailed execution result
```

## Notes

- The external API prefix is `/api/v1`. Internal UI endpoints use `/rest/v1/orchestrate`.
- All orchestration endpoints auto-save the generated PSOP.
- The `/orchestrate/execute` endpoint persists an `ExecutionRecord` on completion for later retrieval.
- When executing a PSOP (via auto-execute or by ID), the runtime intent is injected into every step's context, including layer-0 leaf steps. This gives agents the user's original scenario description alongside predefined task instructions.
- SSE connections use `text/event-stream` with keep-alive. Clients should handle reconnection.
- Rate limiting applies to all endpoints (default 50 req/s per endpoint, configurable in `etc/conf/server.conf`).
- Agent availability depends on the agent registry service. The orchestration center queries it on each request.
- No authentication is required in the open-source release. Authentication can be added via middleware for production deployments.
- All enum values (TaskStatus, StepType) are lowercase strings: `pending`, `running`, `success`, `failed`, `AllSuccess`, `AnySuccess`.