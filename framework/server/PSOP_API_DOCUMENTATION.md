# PSOP API 接口文档

## 概述

PSOP (Parallel-Standard Operation Process) 是运行时工作流，用于系统执行。它定义了明确的任务及其在智能体粒度上的关系。每个任务指定了使用哪个智能体和技能。

本文档描述了 `framework/server/frontend_support_server.py` 中新增的三个PSOP管理接口。

## 服务器信息

- **服务器地址**: `http://localhost:6000`
- **启动命令**: `python -m framework.server.frontend_support_server`
- **日志输出**: 启动时会显示所有可用接口

## 接口列表

### 1. 获取PSOP列表接口
### 2. 按ID获取PSOP详情接口
### 3. 保存PSOP接口

---

## 接口详情

### 1. 获取PSOP列表接口

#### 基本信息
- **端点**: `GET /psops`
- **功能**: 获取所有PSOP的列表
- **描述**: 返回存储中的所有PSOP，支持分页和类型过滤

#### 请求参数
| 参数名 | 类型 | 必填 | 默认值 | 描述 |
|--------|------|------|--------|------|
| `limit` | integer | 否 | 10 | 返回结果数量限制 |
| `workflow_type` | string | 否 | "psop" | 工作流类型，可选值: "all", "psop", "preflow" |

#### 请求示例
```bash
# 获取前10个PSOP
curl -X GET "http://localhost:6000/psops"

# 获取前5个PSOP
curl -X GET "http://localhost:6000/psops?limit=5"

# 获取所有类型的工作流
curl -X GET "http://localhost:6000/psops?workflow_type=all"
```

#### 响应格式
**成功响应 (200 OK):**
```json
{
  "status": "success",
  "count": 2,
  "data": [
    {
      "workflow_id": "test-psop-001",
      "workflow_type": "psop",
      "name": "能源节约分析流程",
      "description": "用于分析能源使用情况的PSOP",
      "tags": ["energy", "analysis", "automation"],
      "created_at": "2026-03-18T18:18:26.264191",
      "score": 1.0
    },
    {
      "workflow_id": "test-psop-002",
      "workflow_type": "psop",
      "name": "故障诊断流程",
      "description": "用于系统故障诊断的PSOP",
      "tags": ["diagnosis", "troubleshooting", "maintenance"],
      "created_at": "2026-03-18T18:18:26.270861",
      "score": 1.0
    }
  ]
}
```

**错误响应 (500 Internal Server Error):**
```json
{
  "error": "获取PSOP列表失败: [错误详情]"
}
```

#### 状态码
- `200`: 成功获取PSOP列表
- `500`: 服务器内部错误

---

### 2. 按ID获取PSOP详情接口

#### 基本信息
- **端点**: `GET /psops/<workflow_id>`
- **功能**: 根据ID获取单个PSOP的完整详情
- **描述**: 返回指定ID的PSOP完整数据

#### 路径参数
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `workflow_id` | string | 是 | PSOP的唯一标识符 |

#### 请求示例
```bash
# 获取ID为test-psop-001的PSOP详情
curl -X GET "http://localhost:6000/psops/test-psop-001"
```

#### 响应格式
**成功响应 (200 OK):**
```json
{
  "status": "success",
  "data": {
    "id": "test-psop-001",
    "name": "能源节约分析流程",
    "description": "用于分析能源使用情况的PSOP",
    "created_at": "2026-03-18T18:18:26.264191",
    "steps": [
      {
        "name": "数据收集",
        "type": "AllSuccess",
        "subtasks": [
          {
            "description": "收集能源使用数据",
            "agent": "data-collector",
            "skill": "data-collection",
            "status": "pending"
          }
        ],
        "next": null
      },
      {
        "name": "分析处理",
        "type": "AllSuccess",
        "subtasks": [
          {
            "description": "分析能源使用模式",
            "agent": "analyst",
            "skill": "pattern-analysis",
            "status": "pending"
          }
        ],
        "next": null
      }
    ],
    "related_preflow": null,
    "user_intent": null,
    "tags": ["energy", "analysis", "automation"]
  }
}
```

**错误响应 (404 Not Found):**
```json
{
  "error": "未找到ID为 test-psop-999 的PSOP"
}
```

**错误响应 (500 Internal Server Error):**
```json
{
  "error": "获取PSOP详情失败: [错误详情]"
}
```

#### 状态码
- `200`: 成功获取PSOP详情
- `404`: 指定的PSOP不存在
- `500`: 服务器内部错误

---

### 3. 保存PSOP接口

#### 基本信息
- **端点**: `POST /psops`
- **功能**: 保存PSOP到存储系统
- **描述**: 创建新的PSOP或更新现有PSOP

#### 请求头
```
Content-Type: application/json
```

#### 请求体
PSOP的JSON数据，必须符合PSOP模型定义。

#### 请求示例
```bash
# 保存一个新的PSOP
curl -X POST "http://localhost:6000/psops" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-psop-003",
    "name": "数据备份流程",
    "description": "用于系统数据备份的PSOP",
    "tags": ["backup", "data-protection", "automation"],
    "steps": [
      {
        "name": "备份准备",
        "type": "AllSuccess",
        "subtasks": [
          {
            "description": "检查备份存储空间",
            "agent": "storage-manager",
            "skill": "storage-check",
            "status": "pending"
          }
        ]
      }
    ]
  }'
```

#### 响应格式
**成功响应 (201 Created):**
```json
{
  "status": "success",
  "message": "PSOP保存成功",
  "workflow_id": "test-psop-003"
}
```

**错误响应 (400 Bad Request):**
```json
{
  "error": "请求体为空"
}
```

**错误响应 (500 Internal Server Error):**
```json
{
  "error": "保存PSOP失败: 1 validation error for PSOP\nsteps\n  Field required [type=missing, input_value={'id': 'test-psop-003',...}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.12/v/missing"
}
```

#### 状态码
- `201`: PSOP保存成功
- `400`: 请求体为空或格式错误
- `500`: 服务器内部错误或数据验证失败

---

## PSOP数据结构

### PSOP模型定义
```python
class PSOP(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()),
                    description="Unique workflow identifier (auto-generated if not provided)")
    name: str = Field(..., description="Workflow name", examples=['energy_saving_process', 'fault_diagnosis_process'])
    description: Optional[str] = Field(None, description="Brief work description, empty by default")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    steps: List[Step] = Field(..., description="List of steps in the agent collaboration workflow")
    related_preflow: Optional[str] = Field(None,
                                           description="Associated Preflow ID that this PSOP was generated from")
    user_intent: Optional[str] = Field(None,
                                       description="Original user intent that generated this workflow")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for quick filtering")
```

### Step模型定义
```python
class Step(BaseModel):
    name: str = Field(..., description="Step identifier", examples=['step1', 'step2'])
    type: StepType = Field(StepType.ALL_SUCCESS,
                           description="Step success condition")
    subtasks: List[Task] = Field(..., description="List of subtasks within the step")
    next: Optional[List[JumpCondition]] = Field(None,
                                                description="Jump conditions to next steps")
```

### Task模型定义
```python
class Task(BaseModel):
    description: str = Field(..., description="Task description")
    agent: str = Field(..., description="Name of the agent executing the task")
    skill: str = Field(..., description="Skill required to execute the task")
    status: TaskStatus = Field(TaskStatus.PENDING, description="Task execution status")
```

### 枚举类型
```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

class StepType(str, Enum):
    ALL_SUCCESS = "AllSuccess"
    ANY_SUCCESS = "AnySuccess"
```

---

## 完整使用示例

### Python示例
```python
import requests
import json

# 服务器地址
BASE_URL = "http://localhost:6000"

# 1. 获取PSOP列表
def get_psop_list(limit=10):
    response = requests.get(f"{BASE_URL}/psops", params={"limit": limit})
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"获取列表失败: {response.text}")

# 2. 保存PSOP
def save_psop(psop_data):
    headers = {"Content-Type": "application/json"}
    response = requests.post(f"{BASE_URL}/psops", 
                           json=psop_data, 
                           headers=headers)
    if response.status_code == 201:
        return response.json()
    else:
        raise Exception(f"保存失败: {response.text}")

# 3. 获取PSOP详情
def get_psop_detail(workflow_id):
    response = requests.get(f"{BASE_URL}/psops/{workflow_id}")
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        raise Exception(f"PSOP不存在: {workflow_id}")
    else:
        raise Exception(f"获取详情失败: {response.text}")

# 使用示例
if __name__ == "__main__":
    # 创建PSOP数据
    new_psop = {
        "id": "my-custom-psop",
        "name": "自定义工作流",
        "description": "这是一个自定义的PSOP示例",
        "tags": ["custom", "example", "test"],
        "steps": [
            {
                "name": "第一步",
                "type": "AllSuccess",
                "subtasks": [
                    {
                        "description": "执行初始化任务",
                        "agent": "init-agent",
                        "skill": "initialization",
                        "status": "pending"
                    }
                ]
            }
        ]
    }
    
    try:
        # 保存PSOP
        result = save_psop(new_psop)
        print(f"保存成功: {result}")
        
        # 获取列表
        psop_list = get_psop_list()
        print(f"PSOP列表: {psop_list}")
        
        # 获取详情
        detail = get_psop_detail("my-custom-psop")
        print(f"PSOP详情: {detail}")
        
    except Exception as e:
        print(f"操作失败: {str(e)}")
```

### JavaScript示例
```javascript
// 使用fetch API
const BASE_URL = 'http://localhost:6000';

// 获取PSOP列表
async function getPsopList(limit = 10) {
    const response = await fetch(`${BASE_URL}/psops?limit=${limit}`);
    if (!response.ok) {
        throw new Error(`获取列表失败: ${response.status}`);
    }
    return await response.json();
}

// 保存PSOP
async function savePsop(psopData) {
    const response = await fetch(`${BASE_URL}/psops`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(psopData)
    });
    
    if (!response.ok) {
        throw new Error(`保存失败: ${response.status}`);
    }
    return await response.json();
}

// 获取PSOP详情
async function getPsopDetail(workflowId) {
    const response = await fetch(`${BASE_URL}/psops/${workflowId}`);
    if (response.status === 404) {
        throw new Error(`PSOP不存在: ${workflowId}`);
    }
    if (!response.ok) {
        throw new Error(`获取详情失败: ${response.status}`);
    }
    return await response.json();
}

// 使用示例
async function example() {
    const newPsop = {
        id: 'js-test-psop',
        name: 'JavaScript测试PSOP',
        description: '通过JavaScript创建的PSOP',
        tags: ['javascript', 'test', 'frontend'],
        steps: [
            {
                name: '前端处理',
                type: 'AllSuccess',
                subtasks: [
                    {
                        description: '处理用户输入',
                        agent: 'frontend-agent',
                        skill: 'input-processing',
                        status: 'pending'
                    }
                ]
            }
        ]
    };
    
    try {
        // 保存PSOP
        const saveResult = await savePsop(newPsop);
        console.log('保存成功:', saveResult);
        
        // 获取列表
        const list = await getPsopList(5);
        console.log('PSOP列表:', list);
        
        // 获取详情
        const detail = await getPsopDetail('js-test-psop');
        console.log('PSOP详情:', detail);
        
    } catch (error) {
        console.error('操作失败:', error.message);
    }
}

// 运行示例
example();
```

---

## 错误处理指南

### 常见错误及解决方法

1. **400 Bad Request**
   - **原因**: 请求体为空或格式错误
   - **解决方法**: 检查请求体是否为有效的JSON格式

2. **404 Not Found**
   - **原因**: 请求的PSOP ID不存在
   - **解决方法**: 检查PSOP ID是否正确，或先调用列表接口确认可用ID

3. **500 Internal Server Error**
   - **原因**: 服务器内部错误或数据验证失败
   - **解决方法**: 
     - 检查PSOP数据结构是否符合模型定义
     - 查看服务器日志获取详细错误信息
     - 确保所有必需字段都已提供

### 数据验证错误示例
```json
{
  "error": "保存PSOP失败: 1 validation error for PSOP\nsteps\n  Field required [type=missing, input_value={'id': 'test', 'name': 'test'}, input_type=dict]"
}
```
**解决方法**: 确保提供了`steps`字段，且其值为非空数组。

---

## 注意事项

1. **ID生成**: 如果请求中不提供`id`字段，系统会自动生成UUID作为ID
2. **时间戳**: `created_at`字段会自动设置为当前时间
3. **数据持久化**: PSOP数据保存在`workflow_storage/psop/`目录下的JSON文件中
4. **并发安全**: 接口支持并发访问，但同一ID的PSOP多次保存会覆盖之前的数据
5. **数据验证**: 所有输入数据都会进行严格的Pydantic验证

---

## 相关接口

除了PSOP接口外，服务器还提供以下接口：

1. **POST /parse-pdf** - 上传PDF文件并解析
2. **POST /plan** - 提交任务和步骤，获取规划结果

启动服务器时会显示所有可用接口的日志信息。

---