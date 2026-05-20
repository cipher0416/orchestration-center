<!--
!/usr/bin/env python3
Copyright (c) 2026 Huawei Technologies Co., Ltd.
All Rights Reserved.

   Licensed under the Apache License, Version 2.0 (the "License"); you may
   not use this file except in compliance with the License. You may obtain
   a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
   License for the specific language governing permissions and limitations
   under the License.
-->

# A2A-T 多智能体编排中心

## Overview

### 项目定位

编排中心是一个面向多智能体（Agent）协作的可视化编排平台，支持通过图形化工作流设计器定义Agent之间的调用关系与执行流程。后端基于Python框架解析流程并驱动Agent协同工作，帮助用户高效构建、管理和运行复杂的Agent协作流程。

### 核心能力

| 能力 | 说明                                                              |
|------|-----------------------------------------------------------------|
| **可视化编排** | 提供图形化工作流设计器，通过拖拽和连线即可完成Agent协作流程设计，无需编写代码                       |
| **多模式生成** | 支持PDF导入、手动编排、自然语言生成三种工作流创建方式，适配不同用户习惯                           |
| **A2A-T协商集成** | 集成a2a-t-sdk的fulfillment协商能力，支持Agent间协商交互，协商上下文通过Task.metadata携带 |
| **智能检索** | 基于自然语言意图检索历史工作流，快速复用已有流程                                        |
| **实时流式执行** | 通过SSE技术实时推送执行进度，便于前端展示和问题定位                                     |

### 技术架构

| 层级 | 技术 |
|------|------|
| 后端框架 | Python + FastAPI + uvicorn |
| 前端框架 | Node.js + React |
| SDK集成 | a2a-t-sdk（协商能力）、a2a-sdk（协议实现） |
| 数据存储 | PostgreSQL / File |
| 消息推送 | SSE (Server-Sent Events) |

### 目录结构

```
orchestration-center/
├── orchestrate/              # 核心编排模块
│   ├── core/                 # 核心模型（PSOP、PreFlow）
│   ├── runtime/              # 执行引擎（DynamicWorkflowEngine）
│   ├── server/               # REST API服务
│   ├── registry_client/      # 注册中心客户端
│   └── solution_package/     # SolutionPackage解析
├── samples/                  # 示例Agent
│   ├── agents/               # Agent实现（集成A2A-T协商）
│   ├── a2at_config/          # A2A-T SDK配置
│   ├── negotiation_utils.py  # 协商工具函数
│   └── agentcard/            # AgentCard定义
├── workflow-designer/        # 前端可视化设计器
├── common/                   # 公共模块（LLM、配置、日志等）
├── config/                   # 配置文件（llm_config.json等）
├── etc/                      # SSL证书、服务配置
├── data/                     # 本地数据存储
└── docs/                     # 文档
```

### 核心依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| a2a-t-sdk | &gt;=0.1.1 | Agent协商能力（fulfillment协商） |
| a2a-sdk | latest | A2A协议实现 |
| fastapi | &gt;=0.135.1 | REST API框架 |
| pydantic | &gt;=2.12.5 | 数据模型验证 |
| openai | &gt;=2.26.0 | LLM调用 |
| uvicorn | &gt;=0.42 | ASGI服务器 |

---

## Quick Start

### 环境要求

| 环境 | 版本要求         |
|------|--------------|
| Node.js | &gt;= 20.19 |
| Python | &gt;= 3.14  |

### 安装步骤

#### Windows

```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活虚拟环境
.\.venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动后端服务
python -m orchestrate.start

# 5. 启动前端服务
cd workflow-designer
npm install --force
npm run dev

# 6. （可选）启动示例Agent
cd ..
python -m samples.start_agents_server
```

#### Linux

```bash
# 1. 创建虚拟环境
python3 -m venv .venv

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动后端服务（后台运行）
nohup python -m orchestrate.start > orchestrate.log 2>&1 &

# 5. 启动前端服务
cd workflow-designer
npm install --force
npm run dev

# 6. （可选）启动示例Agent
cd ..
python -m samples.start_agents_server
```

### 验证启动成功

| 服务 | 验证方式 |
|------|----------|
| 后端服务 | 看到日志输出 `Uvicorn running on http://127.0.0.1:60000` |
| 前端服务 | 浏览器访问 `http://localhost:3003` |
| 示例Agent | 看到日志输出各Agent启动信息 |

---

## A2A-T SDK集成

本项目集成了a2a-t-sdk的协商能力，支持Agent间fulfillment协商交互。

### 协商流程

```
编排端 → 发送任务 → Agent端
                    ↓
              A2ATServer.start_negotiation()
                    ↓
              发起fulfillment协商
                    ↓
              协商上下文通过Task.metadata携带
                    ↓
编排端 → 解析metadata中的negotiationContext
                    ↓
              支持多轮协商交互
```

### 协商能力说明

| 组件 | 功能 |
|------|------|
| `A2ATServer` | Agent端协商服务，发起/接收/继续协商 |
| `A2ATClient` | 编排端协商客户端，生成任务提示词 |
| `NegotiationType.FULFILLMENT` | 当前支持的协商类型（任务执行协商） |

### 配置说明

协商配置位于 `samples/a2at_config/.env`，配置项从 `config/llm_config.json` 自动生成：

```env
A2AT_LLM_PROVIDER=deepseek
A2AT_LLM_MODEL=deepseek-chat
A2AT_LLM_API_KEY=<your-api-key>
A2AT_LLM_BASE_URL=https://api.deepseek.com
A2AT_NEGOTIATION_STATE_STORE_TYPE=in_memory
```

### 协商相关代码

| 文件路径 | 说明 |
|----------|------|
| `samples/agents/negotiation_base_agent.py` | 协商Agent基类 |
| `samples/negotiation_utils.py` | 协商工具函数 |
| `orchestrate/runtime/exec_engine.py` | 执行引擎（协商上下文解析） |

---

## 启动前配置（可选）

### IP端口配置

本项目默认在 `127.0.0.1:60000` 上开放端口侦听，可按需修改。

配置文件：`{安装目录}/etc/conf/server.conf`

```properties
ip=127.0.0.1
port=60000
```

### 证书配置

如需启用HTTPS，配置SSL证书：

```properties
ssl_certfile=etc/ssl/server.cer
ssl_keyfile=etc/ssl/server_key.pem
ssl_keyfile_password=etc/ssl/cert_pwd
ssl_ca_certs=etc/ssl/trust.cer
verify_client=true
enable_https=true
```

如不需要证书校验，设置 `enable_https=false`。

### 数据持久化配置

```properties
persistence_mode=postgresql  # 或 file
```

- `postgresql`：需配置 `{安装目录}/etc/conf/db_config.json`
- `file`：数据保存在 `{安装目录}/data` 目录