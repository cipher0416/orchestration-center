# A2A-T 多智能体编排中心

## 项目简介

编排中心是一个用于编排多个 Agent（智能体）协作的 Web 平台。用户在可视化工作流设计器中编排 Agent 之间的调用关系和流程图，后端 Python 框架负责解析流程、执行编排逻辑并驱动 Agent 协同工作。

## 技术栈

- **前端**: React 18 + Vite + React Flow + Tailwind CSS + i18next
- **后端**: Python 3 + FastAPI + Pydantic + a2a-sdk + Loguru

## 功能模块

- **工作流设计器** (`workflow-designer/`): 基于 React Flow 的可视化画布，支持拖拽编排 Agent 节点与执行流程图
- **SolutionPackage解析** (`framework/parser/`): 解析AN SolutionPackage中的流程描述
- **编排引擎** (`framework/orchestration/`): 核心编排逻辑，包含 LLM 调用、任务分发、流程调度、持久化等
- **执行引擎** (`framework/runtime/`): 运行时执行器，负责驱动编排流程运转
- **服务端** (`framework/server/`): 提供 API 支持与前端静态文件服务
- **配置管理** (`config/`): 集中管理 Agent Card、LLM 等配置文件
- **示例代码** (`samples/`): 包含 Agent 示例定义与示例运行入口

## 启动方式

**前端**
```bash
cd workflow-designer
yarn dev
```

**后端**
```bash
python samples/run.py
```
