# LLM 配置文件（llm_config.json）说明

LLM 模块采用**配置驱动**架构，接入新模型只需编辑 `common/config/llm_config.json`，无需编写 Python 代码。

## 文件结构

```json
{
  "chat":   { ... },    // Chat/LLM 模型（文本生成）
  "embed":  { ... },    // Embedding 模型（文本向量化）
  "rerank": { ... }     // Reranker 模型（结果重排序）
}
```

每个能力 key（`chat`、`embed`、`rerank`）配置一个模型实例，按需配置即可。

## 通用字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `description` | string | 否 | 模型描述，用于日志 |
| `model` | string | 否 | 模型名称，通过 `$MODEL` 占位符注入 |
| `url` | string | **是** | API 端点地址 |
| `api_key` | string | 否 | API 密钥，`auth` 为 null 时自动作为 `Authorization: Bearer` 头 |
| `enable_thinking` | boolean | 否 | 思考模式开关，通过 `$ENABLE_THINKING` 注入 |
| `auth` | object/string/null | 否 | 认证策略（见下文） |
| `headers` | object | 否 | 额外静态 HTTP 头 |
| `body` | object | **是** | 请求体模板，支持 `$` 占位符 |
| `response` | object | **是** | 响应提取路径（点分路径） |

## 认证策略（`auth`）

| 值 | 说明 |
|-----|------|
| `null` | 无特殊认证，`api_key` 非空时自动加 Bearer 头，适合 OpenAI 兼容 API |
| `{"type": "aoc_signed", ...}` | AOC 平台签名 Header（`x-sg-*` 系列） |

`aoc_signed` 必填参数：`app_key`、`app_secret`、`authorization`、`api_code`。  
带默认值的可选参数：`scenario_code`（"B99999999999"）、`scenario_version`（"V1"）、`ability_code`（"A999999999"）、`api_version`（"1.0"）、`test_flag`（"1"）。

## 请求体占位符

| 占位符 | 展开为 | 适用能力 |
|--------|--------|----------|
| `$MODEL` | `model` 字段值 | chat, embed, rerank |
| `$PROMPT` | `ask_llm()` / `embed()` 的 prompt 参数 | chat, embed |
| `$QUERY` | `rerank()` 的 query 参数 | rerank |
| `$DOCUMENTS` | `rerank()` 的 documents 参数（JSON 数组） | rerank |
| `$ENABLE_THINKING` | `enable_thinking` 字段值 | chat, embed, rerank |

## 响应提取路径（`response`）

| 能力 | response 键 | 说明 |
|------|-------------|------|
| chat | `answer` | 回答文本路径，如 `"choices.0.message.content"` |
| chat | `reasoning` | 推理/思考过程路径（可选） |
| embed | `embedding` | 向量数组路径，如 `"data.0.embedding"` |
| rerank | `results` | 重排结果路径，如 `"results"` |

## 配置示例

### OpenAI 兼容 API

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

### AOC 平台（Chat + Embed + Rerank）

```json
{
  "chat": {
    "model": "Qwen3_32B",
    "url": "http://宿主机:端口/aoc/openapi/端点ID",
    "auth": {
      "type": "aoc_signed",
      "app_key": "你的_APP_KEY",
      "app_secret": "你的_APP_SECRET",
      "authorization": "Bearer 你的_TOKEN",
      "api_code": "你的_API_CODE"
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
    "url": "http://宿主机:端口/aoc/openapi/端点ID",
    "auth": { "type": "aoc_signed", "app_key": "...", "app_secret": "...", "authorization": "Bearer ...", "api_code": "..." },
    "body": { "model": "$MODEL", "input": "$PROMPT" },
    "response": { "embedding": "data.0.embedding" }
  },
  "rerank": {
    "model": "bge-reranker-v2-m3",
    "url": "http://宿主机:端口/aoc/openapi/interface/bge-reranker-v2-m3",
    "auth": { "type": "aoc_signed", "app_key": "...", "app_secret": "...", "authorization": "Bearer ...", "api_code": "..." },
    "body": { "model": "$MODEL", "query": "$QUERY", "documents": "$DOCUMENTS" },
    "response": { "results": "results" }
  }
}
```

## 代码调用示例

```python
from common.llm import get_llm_instance, get_embed_instance, get_rerank_instance

# Chat
llm = get_llm_instance()  # 默认使用 "chat"
reasoning, answer = llm.ask_llm("你好")

# Embedding
emb = get_embed_instance()
vector = emb.embed("需要向量化的文本")

# Rerank
rerank = get_rerank_instance()
results = rerank.rerank("查询", ["候选1", "候选2"])
```

> 详细配置指南见 `docs/zh/开发指南.md` 附录 D。
