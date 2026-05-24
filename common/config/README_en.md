# LLM Configuration File (llm_config.json) Description

The LLM module uses a **configuration-driven** architecture. To add new models, simply edit `common/config/llm_config.json` — no Python code needed.

## File Structure Overview

```json
{
  "chat":   { ... },    // Chat/LLM model (text generation)
  "embed":  { ... },    // Embedding model (text vectorization)
  "rerank": { ... }     // Reranker model (result reordering)
}
```

Each capability key (`chat`, `embed`, `rerank`) configures one model instance. Unconfigured capabilities will raise an error when called.

## Common Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string | No | Model description for logging. |
| `model` | string | No | Model name, injected via `$MODEL` placeholder. |
| `url` | string | **Yes** | API endpoint URL. |
| `api_key` | string | No | API key; auto-added as `Authorization: Bearer` when `auth` is null. |
| `enable_thinking` | boolean | No | Chain-of-thought mode, injected via `$ENABLE_THINKING`. |
| `auth` | object/string/null | No | Authentication strategy (see below). |
| `headers` | object | No | Extra static HTTP headers. |
| `body` | object | **Yes** | Request body template with `$` placeholders. |
| `response` | object | **Yes** | Response extraction paths (dot notation). |

## Authentication (`auth`)

| Value | Description |
|-------|-------------|
| `null` | No special auth. If `api_key` is set, adds `Bearer` header automatically. |
| `{"type": "aoc_signed", ...}` | AOC platform signed headers (`x-sg-*` series). |

`aoc_signed` required params: `app_key`, `app_secret`, `authorization`, `api_code`.  
Optional with defaults: `scenario_code` ("B99999999999"), `scenario_version` ("V1"), `ability_code` ("A999999999"), `api_version` ("1.0"), `test_flag` ("1").

## Body Template Placeholders

| Placeholder | Expands to | Capability |
|-------------|-----------|------------|
| `$MODEL` | `model` field value | chat, embed, rerank |
| `$PROMPT` | `ask_llm()` / `embed()` prompt | chat, embed |
| `$QUERY` | `rerank()` query | rerank |
| `$DOCUMENTS` | `rerank()` documents (JSON array) | rerank |
| `$ENABLE_THINKING` | `enable_thinking` field value | chat, embed, rerank |

## Response Extraction Paths (`response`)

| Capability | Key | Description |
|-----------|-----|-------------|
| chat | `answer` | Answer text path, e.g. `"choices.0.message.content"` |
| chat | `reasoning` | Reasoning/thinking path (optional) |
| embed | `embedding` | Vector array path, e.g. `"data.0.embedding"` |
| rerank | `results` | Rerank results path, e.g. `"results"` |

## Configuration Examples

### OpenAI-compatible API

```json
{
  "chat": {
    "model": "deepseek-chat",
    "url": "https://api.deepseek.com/v1/chat/completions",
    "api_key": "sk-xxxxxxxx",
    "enable_thinking": true,
    "auth": null,
    "body": {
      "model": "$MODEL",
      "messages": [{"role": "user", "content": "$PROMPT"}]
    },
    "response": {
      "answer": "choices.0.message.content",
      "reasoning": "choices.0.message.reasoning_content"
    }
  }
}
```

### AOC Platform (Chat + Embed + Rerank)

```json
{
  "chat": {
    "model": "Qwen3_32B",
    "url": "http://HOST:PORT/aoc/openapi/ENDPOINT_ID",
    "auth": {
      "type": "aoc_signed",
      "app_key": "YOUR_APP_KEY",
      "app_secret": "YOUR_APP_SECRET",
      "authorization": "Bearer YOUR_TOKEN",
      "api_code": "YOUR_API_CODE"
    },
    "body": {
      "model": "$MODEL",
      "messages": [{"role": "user", "content": "$PROMPT"}],
      "chat_template_kwargs": {"enable_thinking": "$ENABLE_THINKING"}
    },
    "response": {
      "answer": "choices.0.message.content",
      "reasoning": "choices.0.message.reasoning_content"
    }
  },
  "embed": {
    "model": "bge-m3",
    "url": "http://HOST:PORT/aoc/openapi/ENDPOINT_ID",
    "auth": { "type": "aoc_signed", "app_key": "...", "app_secret": "...", "authorization": "Bearer ...", "api_code": "..." },
    "body": { "model": "$MODEL", "input": "$PROMPT" },
    "response": { "embedding": "data.0.embedding" }
  },
  "rerank": {
    "model": "bge-reranker-v2-m3",
    "url": "http://HOST:PORT/aoc/openapi/interface/bge-reranker-v2-m3",
    "auth": { "type": "aoc_signed", "app_key": "...", "app_secret": "...", "authorization": "Bearer ...", "api_code": "..." },
    "body": { "model": "$MODEL", "query": "$QUERY", "documents": "$DOCUMENTS" },
    "response": { "results": "results" }
  }
}
```

## Usage Example (Python)

```python
from common.llm import get_llm_instance, get_embed_instance, get_rerank_instance

# Chat
llm = get_llm_instance()  # defaults to "chat"
reasoning, answer = llm.ask_llm("who are you?")

# Embedding
emb = get_embed_instance()
vector = emb.embed("text to embed")

# Rerank
rerank = get_rerank_instance()
results = rerank.rerank("query", ["candidate1", "candidate2"])
```

> For detailed configuration guide, see `docs/zh/开发指南.md` Appendix D.
