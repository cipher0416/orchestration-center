# 编排中心API参考

## 使用前必读

### 简介

  编排中心是一个面向多智能体（Agent）协作的可视化编排平台，主要开放提供以下接口:
  - **PDF解析**：上传PDF文件并解析指定章节，提取工作流信息。
  - **工作流规划**：提交任务和步骤，获取规划后的PSOP工作流结果。
  - **查询PSOP列表**：获取已保存的PSOP工作流列表。
  - **查询指定PSOP**：根据ID获取单个PSOP工作流详情。
  - **保存PSOP**：保存新的PSOP工作流。
  - **删除PSOP**：删除指定的PSOP工作流。
  - **查询AgentCard列表**：获取全量AgentCard列表。
  - **意图生成PSOP**：根据自然语言意图生成PSOP工作流。
  - **意图检索PSOP**：根据自然语言意图检索匹配的PSOP工作流。
  - **SSE执行工作流**：启动PSOP执行并通过SSE实时推送进度。

### 约束与限制

  具体内容请参见各接口的接口约束。

## PDF解析接口

- 典型场景

    用户需要从PDF文档中提取工作流配置信息时，可通过该接口上传PDF文件并解析指定章节内容。

- 功能描述

    上传PDF文件并解析指定章节，提取工作流JSON数据。

- 接口约束

  - 上传文件格式仅支持PDF。
  - 单次上传文件大小不得超过100MB。
  - PDF文档需包含标题为"5. Interaction Flow"的章节。
  - 单实例上该接口最大并发数为50。

- 调用方法

    POST

- URI

    */parse-pdf*

- 请求参数

  <a id="表1-form-data参数列表"></a>**表1** form-data参数列表

    | 参数名称 | 是否必选 | 类型     | 值域       | 默认值 | 描述                |
    |------|------|--------|----------|-----|-------------------|
    | file | 是    | file   | PDF文件格式  | -   | 待解析的PDF文件。       |

- 请求示例

    ```json
    POST /parse-pdf HTTP/1.1
    Host: your-domain.com
    Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

    ------WebKitFormBoundary
    Content-Disposition: form-data; name="file"; filename="workflow.pdf"
    Content-Type: application/pdf

    [PDF文件二进制数据]
    ------WebKitFormBoundary--
    ```

- 响应参数

    <a id="表2-响应参数列表"></a>**表2** 响应参数列表

    | 参数名称    | 是否必选 | 类型     | 值域   | 默认值 | 描述              |
    |---------|------|--------|------|-----|-----------------|
    | status  | 是    | string | -    | -   | 响应状态，成功为"success"。 |
    | message | 是    | string | -    | -   | 响应消息描述。          |
    | content | 否    | string | -    | -   | 解析后的PreFlow JSON数据。 |

- 响应样例

    解析成功：
    ```json
    {
      "status": "success",
      "message": "PDF文件解析成功",
      "content": "{\"name\": \"工作流名称\", \"description\": \"工作流描述\", \"steps\": [...]}"
    }
    ```

    解析失败：
    ```json
    {
      "status": "error",
      "message": "PDF解析失败，未找到指定章节"
    }
    ```

- 状态码

  | 状态码 | 说明                         |
  |--------|----------------------------|
  | 200    | 解析成功。                      |
  | 400    | 未提供文件、文件名为空、非PDF文件，或未找到指定章节。 |
  | 500    | 解析失败，服务内部错误。                |

## 工作流规划接口

- 典型场景

    用户需要根据任务描述和可用Agent信息生成工作流规划时，可通过该接口获取规划后的PSOP工作流结果。

- 功能描述

    提交任务描述（PreFlow）和可用Agent信息，通过规划算法生成PSOP工作流JSON数据。

- 接口约束

  - 请求体大小不得超过1MB。
  - 单实例上该接口最大并发数为50。

- 调用方法

    POST

- URI

    */plan*

- 请求参数

  <a id="表3-body参数列表"></a>**表3** body参数列表

    | 参数名称       | 是否必选 | 类型              | 值域 | 默认值 | 描述                          |
    |------------|------|-----------------|----|-----|-----------------------------|
    | preflow    | 是    | reference       | -  | -   | PreFlow对象，详细请参见[表4](#表4-preflow对象的参数列表)。 |
    | agentCards | 是    | array_reference | -  | -   | 可用Agent列表，详细请参见[表5](#表5-agentcard对象的参数列表)。 |

  <a id="表4-preflow对象的参数列表"></a>**表4** PreFlow对象的参数列表

    | 参数名称        | 是否必选 | 类型     | 值域       | 默认值 | 描述                    |
    |-------------|------|--------|----------|-----|-----------------------|
    | name        | 是    | string | 1~100个字符 | -   | 工作流名称。                |
    | description | 否    | string | 1~500个字符 | -   | 工作流描述。                |
    | steps_md    | 是    | string | -        | -   | Markdown格式的步骤描述。      |

  <a id="表5-agentcard对象的参数列表"></a>**表5** AgentCard对象的参数列表

    | 参数名称                | 是否必选 | 类型              | 值域                   | 默认值 | 描述               |
    |---------------------|------|-----------------|----------------------|-----|------------------|
    | name                | 是    | string          | 1~100个字符              | -   | AgentCard名称。     |
    | description         | 是    | string          | 1~1000个字符             | -   | AgentCard描述。     |
    | version             | 是    | string          | 1~50个字符               | -   | AgentCard版本。     |
    | provider            | 是    | reference       | -                    | -   | 提供商信息。           |
    | skills              | 是    | array_reference | 最大数量：100个技能           | -   | 技能列表。            |
    | capabilities        | 是    | reference       | -                    | -   | AgentCard能力项。    |
    | supportedInterfaces | 是    | array_reference | 1~3个列表               | -   | 支持的协议。           |

- 请求示例

    ```json
    POST /plan HTTP/1.1
    Host: your-domain.com
    Content-Type: application/json
    {
      "preflow": {
        "name": "RAN节能工作流",
        "description": "RAN网络节能优化工作流",
        "steps_md": "1. 探索意图目标\n2. 执行节能配置\n3. 生成效果报告"
      },
      "agentCards": [
        {
          "name": "RAN Energy Saving Agent",
          "description": "负责RAN能效优化的自主闭环运行，包括意图探索、意图实现、效果评估与报告。",
          "version": "1.0.0",
          "provider": {
            "organization": "Huawei",
            "url": "https://www.huawei.com"
          },
          "skills": [
            {
              "id": "ran-es-intent-exploration",
              "name": "RAN ES Intent Exploration",
              "description": "评估并确定指定RAN ES意图目标的最佳可能性，考虑当前资源状况和系统能力。",
              "tags": [
                "wireless",
                "energy-saving",
                "intent"
              ]
            },
            {
              "id": "ran-es-intent-lifecycle-management",
              "name": "RAN ES Intent Lifecycle Management",
              "description": "管理RAN节能意图的生命周期，包括创建、修改、删除、激活、去激活意图，并执行数据采集、分析、解决方案制定与配置。",
              "tags": [
                "wireless",
                "energy-saving",
                "intent"
              ]
            },
            {
              "id": "ran-es-intent-reporting",
              "name": "RAN ES Intent Reporting",
              "description": "提供意图报告查询、订阅、通知功能，报告意图实现状态、达成值、推荐值及配置修改信息。",
              "tags": [
                "wireless",
                "energy-saving",
                "reporting"
              ]
            }
          ],
          "capabilities": {
            "streaming": true,
            "pushNotifications": false,
            "extensions": []
          },
          "defaultInputModes": [
            "text",
            "json"
          ],
          "defaultOutputModes": [
            "text",
            "json"
          ],
          "supportedInterfaces": [
            {
              "protocolBinding": "GPRC",
              "protocolVersion": "1.0.0",
              "url": "http://127.0.0.1:5000/"
            },
            {
              "protocolBinding": "HTTP+JSON",
              "protocolVersion": "1.0.0",
              "url": "http://127.0.0.1:5000/"
            }
          ]
        }
      ]
    }
    ```

- 响应参数

    <a id="表6-响应参数列表"></a>**表6** 响应参数列表

    | 参数名称   | 是否必选 | 类型     | 值域   | 默认值 | 描述                  |
    |--------|------|--------|------|-----|---------------------|
    | status | 是    | string | -    | -   | 响应状态，成功为"success"。 |
    | data   | 否    | string | -    | -   | PSOP工作流JSON数据。     |

- 响应样例

    规划成功：
    ```json
    {
      "status": "success",
      "data": "{\"id\": \"psop-001\", \"name\": \"RAN节能工作流\", \"steps\": [...]}"
    }
    ```

    规划失败：
    ```json
    {
      "status": "error",
      "message": "规划失败，无法匹配可用Agent"
    }
    ```

- 状态码

  | 状态码 | 说明               |
  |--------|------------------|
  | 200    | 规划成功。            |
  | 400    | 请求参数校验失败。        |
  | 500    | 规划失败，服务内部错误。     |

## 查询PSOP列表

- 典型场景

    用户需要查看已保存的PSOP工作流列表时，可通过该接口获取工作流列表信息。

- 功能描述

    获取已保存的PSOP工作流列表，支持按类型筛选和数量限制。

- 接口约束

  - 返回结果默认按创建时间倒序排列。
  - 单实例上该接口最大并发数为50。

- 调用方法

    GET

- URI

    */psops*

- 请求参数

  <a id="表7-query参数列表"></a>**表7** query参数列表

    | 参数名称         | 是否必选 | 类型      | 值域                        | 默认值    | 描述                                     |
    |------------|------|---------|---------------------------|--------|----------------------------------------|
    | limit      | 否    | integer | 1~100                     | 10     | 返回结果数量限制。                              |
    | workflow_type | 否    | string  | "all"、"psop"、"preflow" | "psop" | 工作流类型筛选。"all"返回全部类型，"psop"返回PSOP类型，"preflow"返回PreFlow类型。 |

- 请求示例

    - 查询默认PSOP列表

      ```json
      GET /psops HTTP/1.1
      Host: your-domain.com
      Content-Type: application/json
      ```

    - 查询全部类型工作流

      ```json
      GET /psops?limit=20&workflow_type=all HTTP/1.1
      Host: your-domain.com
      Content-Type: application/json
      ```

    - 查询PreFlow类型工作流

      ```json
      GET /psops?workflow_type=preflow HTTP/1.1
      Host: your-domain.com
      Content-Type: application/json
      ```

- 响应参数

    <a id="表8-响应参数列表"></a>**表8** 响应参数列表

    | 参数名称      | 是否必选 | 类型              | 值域 | 默认值 | 描述                                  |
    |-----------|------|-----------------|----|-----|-------------------------------------|
    | workflows | 是    | array_reference | -  | -   | 工作流列表，详细请参见[表9](#表9-psop对象的参数列表)。 |

  <a id="表9-psop对象的参数列表"></a>**表9** PSOP对象的参数列表

    | 参数名称        | 是否必选 | 类型              | 值域       | 默认值 | 描述         |
    |-------------|------|-----------------|----------|-----|------------|
    | id          | 是    | string          | -        | -   | 工作流唯一标识。   |
    | name        | 是    | string          | 1~100个字符 | -   | 工作流名称。     |
    | description | 否    | string          | 1~500个字符 | -   | 工作流描述。     |
    | steps       | 是    | array_reference | -        | -   | 步骤列表。      |
    | tags        | 否    | array of string | -        | -   | 标签列表。      |
    | created_at  | 是    | string          | ISO时间格式  | -   | 创建时间。      |
    | updated_at  | 是    | string          | ISO时间格式  | -   | 最后更新时间。    |

- 响应样例

    ```json
    {
      "workflows": [
        {
          "id": "psop-001",
          "name": "RAN节能工作流",
          "description": "RAN网络节能优化工作流",
          "steps": [
            {
              "id": "step-1",
              "name": "意图探索",
              "agent_name": "RAN Energy Saving Agent",
              "skill_id": "ran-es-intent-exploration"
            },
            {
              "id": "step-2",
              "name": "意图管理",
              "agent_name": "RAN Energy Saving Agent",
              "skill_id": "ran-es-intent-lifecycle-management"
            }
          ],
          "tags": ["wireless", "energy-saving"],
          "created_at": "2026-01-15T10:30:00Z",
          "updated_at": "2026-01-15T10:30:00Z"
        }
      ]
    }
    ```

- 状态码

  | 状态码 | 说明       |
  |--------|----------|
  | 200    | 查询成功。    |
  | 500    | 查询失败，服务内部错误。 |

## 查询指定PSOP

- 典型场景

    用户需要查看特定PSOP工作流的详细信息时，可通过该接口根据ID获取工作流详情。

- 功能描述

    根据工作流ID精确查询单个PSOP工作流的完整详细信息。

- 接口约束

  - 工作流ID必须存在。
  - 单实例上该接口最大并发数为50。

- 调用方法

    GET

- URI

    */psops/{workflow_id}*

- 请求参数

  <a id="表10-path参数列表"></a>**表10** path参数列表

    | 参数名称        | 是否必选 | 类型     | 值域 | 默认值 | 描述              |
    |-------------|------|--------|----|-----|-----------------|
    | workflow_id | 是    | string | -  | -   | PSOP工作流ID，唯一标识。 |

- 请求示例

    ```json
    GET /psops/psop-001 HTTP/1.1
    Host: your-domain.com
    Content-Type: application/json
    ```

- 响应参数

    <a id="表11-响应参数列表"></a>**表11** 响应参数列表

    | 参数名称        | 是否必选 | 类型              | 值域       | 默认值 | 描述         |
    |-------------|------|-----------------|----------|-----|------------|
    | id          | 是    | string          | -        | -   | 工作流唯一标识。   |
    | name        | 是    | string          | 1~100个字符 | -   | 工作流名称。     |
    | description | 否    | string          | 1~500个字符 | -   | 工作流描述。     |
    | steps       | 是    | array_reference | -        | -   | 步骤列表。      |
    | tags        | 否    | array of string | -        | -   | 标签列表。      |
    | created_at  | 是    | string          | ISO时间格式  | -   | 创建时间。      |
    | updated_at  | 是    | string          | ISO时间格式  | -   | 最后更新时间。    |

- 响应样例

    查询成功：
    ```json
    {
      "id": "psop-001",
      "name": "RAN节能工作流",
      "description": "RAN网络节能优化工作流",
      "steps": [
        {
          "id": "step-1",
          "name": "意图探索",
          "agent_name": "RAN Energy Saving Agent",
          "skill_id": "ran-es-intent-exploration",
          "input": {},
          "output": {}
        },
        {
          "id": "step-2",
          "name": "意图管理",
          "agent_name": "RAN Energy Saving Agent",
          "skill_id": "ran-es-intent-lifecycle-management",
          "input": {},
          "output": {}
        }
      ],
      "tags": ["wireless", "energy-saving"],
      "created_at": "2026-01-15T10:30:00Z",
      "updated_at": "2026-01-15T10:30:00Z"
    }
    ```

    查询失败：
    ```json
    {
      "status": "error",
      "message": "工作流不存在"
    }
    ```

- 状态码

  | 状态码 | 说明              |
  |--------|-----------------|
  | 200    | 查询成功。           |
  | 404    | 查询失败，工作流不存在。    |
  | 500    | 查询失败，服务内部错误。    |

## 保存PSOP

- 典型场景

    用户需要保存新生成或修改后的PSOP工作流时，可通过该接口将工作流持久化存储。

- 功能描述

    保存PSOP工作流信息到数据库。如果工作流ID已存在则更新，否则创建新工作流。

- 接口约束

  - 请求体必须符合PSOP模型定义。
  - 单实例上该接口最大并发数为50。

- 调用方法

    POST

- URI

    */psops*

- 请求参数

  <a id="表12-body参数列表"></a>**表12** body参数列表

    | 参数名称        | 是否必选 | 类型              | 值域       | 默认值 | 描述                                       |
    |-------------|------|-----------------|----------|-----|------------------------------------------|
    | id          | 否    | string          | -        | 自动生成 | 工作流唯一标识，不提供时自动生成。                       |
    | name        | 是    | string          | 1~100个字符 | -   | 工作流名称。                                   |
    | description | 否    | string          | 1~500个字符 | -   | 工作流描述。                                   |
    | steps       | 是    | array_reference | -        | -   | 步骤列表，详细请参见[表13](#表13-step对象的参数列表)。      |
    | tags        | 否    | array of string | -        | -   | 标签列表，用于分类和检索。                            |

  <a id="表13-step对象的参数列表"></a>**表13** Step对象的参数列表

    | 参数名称       | 是否必选 | 类型       | 值域       | 默认值 | 描述              |
    |------------|------|----------|----------|-----|-----------------|
    | id         | 是    | string   | -        | -   | 步骤唯一标识。         |
    | name       | 是    | string   | 1~100个字符 | -   | 步骤名称。           |
    | agent_name | 是    | string   | -        | -   | 执行该步骤的Agent名称。  |
    | skill_id   | 是    | string   | -        | -   | Agent技能ID。      |
    | input      | 否    | object   | -        | -   | 步骤输入参数。         |
    | output     | 否    | object   | -        | -   | 步骤输出参数。         |

- 请求示例

    ```json
    POST /psops HTTP/1.1
    Host: your-domain.com
    Content-Type: application/json
    {
      "name": "RAN节能工作流",
      "description": "RAN网络节能优化工作流",
      "steps": [
        {
          "id": "step-1",
          "name": "意图探索",
          "agent_name": "RAN Energy Saving Agent",
          "skill_id": "ran-es-intent-exploration",
          "input": {},
          "output": {}
        },
        {
          "id": "step-2",
          "name": "意图管理",
          "agent_name": "RAN Energy Saving Agent",
          "skill_id": "ran-es-intent-lifecycle-management",
          "input": {},
          "output": {}
        },
        {
          "id": "step-3",
          "name": "效果报告",
          "agent_name": "RAN Energy Saving Agent",
          "skill_id": "ran-es-intent-reporting",
          "input": {},
          "output": {}
        }
      ],
      "tags": ["wireless", "energy-saving"]
    }
    ```

- 响应参数

    <a id="表14-响应参数列表"></a>**表14** 响应参数列表

    | 参数名称        | 是否必选 | 类型     | 值域       | 默认值 | 描述         |
    |-------------|------|--------|----------|-----|------------|
    | id          | 是    | string | -        | -   | 工作流唯一标识。   |
    | name        | 是    | string | 1~100个字符 | -   | 工作流名称。     |
    | message     | 是    | string | -        | -   | 操作结果消息。    |

- 响应样例

    保存成功：
    ```json
    {
      "id": "psop-001",
      "name": "RAN节能工作流",
      "message": "工作流保存成功"
    }
    ```

    保存失败：
    ```json
    {
      "status": "error",
      "message": "工作流参数校验失败"
    }
    ```

- 状态码

  | 状态码 | 说明               |
  |--------|------------------|
  | 201    | 保存成功。            |
  | 400    | 保存失败，参数校验失败。     |
  | 500    | 保存失败，服务内部错误。     |

## 删除PSOP

- 典型场景

    用户需要删除不再使用的PSOP工作流时，可通过该接口删除指定工作流。

- 功能描述

    根据工作流ID删除指定的PSOP工作流。删除后该工作流将无法恢复。

- 接口约束

  - 工作流ID必须存在。
  - 删除操作不可逆，请谨慎操作。
  - 单实例上该接口最大并发数为50。

- 调用方法

    DELETE

- URI

    */psops/{workflow_id}*

- 请求参数

  <a id="表15-path参数列表"></a>**表15** path参数列表

    | 参数名称        | 是否必选 | 类型     | 值域 | 默认值 | 描述              |
    |-------------|------|--------|----|-----|-----------------|
    | workflow_id | 是    | string | -  | -   | PSOP工作流ID，唯一标识。 |

- 请求示例

    ```json
    DELETE /psops/psop-001 HTTP/1.1
    Host: your-domain.com
    Content-Type: application/json
    ```

- 响应参数

    无。

- 响应样例

    删除成功：无响应体。

- 状态码

  | 状态码 | 说明              |
  |--------|-----------------|
  | 200    | 删除成功。           |
  | 404    | 删除失败，工作流不存在。    |
  | 500    | 删除失败，服务内部错误。    |

## 查询AgentCard列表

- 典型场景

    用户需要查看系统中所有可用Agent信息时，可通过该接口获取AgentCard列表。

- 功能描述

    获取编排中心管理的全量AgentCard列表，用于工作流规划时选择合适的Agent。

- 接口约束

  - 单实例上该接口最大并发数为50。

- 调用方法

    GET

- URI

    */agent-cards*

- 请求参数

    无。

- 请求示例

    ```json
    GET /agent-cards HTTP/1.1
    Host: your-domain.com
    Content-Type: application/json
    ```

- 响应参数

    <a id="表16-响应参数列表"></a>**表16** 响应参数列表

    | 参数名称       | 是否必选 | 类型              | 值域 | 默认值 | 描述                                         |
    |------------|------|-----------------|----|-----|--------------------------------------------|
    | agentCards | 是    | array_reference | -  | -   | AgentCard列表，详细请参见[表5](#表5-agentcard对象的参数列表)。 |

- 响应样例

    ```json
    {
      "agentCards": [
        {
          "name": "RAN Energy Saving Agent",
          "description": "负责RAN能效优化的自主闭环运行，包括意图探索、意图实现、效果评估与报告。",
          "version": "1.0.0",
          "provider": {
            "organization": "Huawei",
            "url": "https://www.huawei.com"
          },
          "skills": [
            {
              "id": "ran-es-intent-exploration",
              "name": "RAN ES Intent Exploration",
              "description": "评估并确定指定RAN ES意图目标的最佳可能性，考虑当前资源状况和系统能力。",
              "tags": [
                "wireless",
                "energy-saving",
                "intent"
              ]
            }
          ],
          "capabilities": {
            "streaming": true,
            "pushNotifications": false,
            "extensions": []
          },
          "defaultInputModes": [
            "text",
            "json"
          ],
          "defaultOutputModes": [
            "text",
            "json"
          ],
          "supportedInterfaces": [
            {
              "protocolBinding": "GPRC",
              "protocolVersion": "1.0.0",
              "url": "http://127.0.0.1:5000/"
            }
          ]
        }
      ]
    }
    ```

- 状态码

  | 状态码 | 说明       |
  |--------|----------|
  | 200    | 查询成功。    |
  | 500    | 查询失败，服务内部错误。 |

## 意图生成PSOP

- 典型场景

    用户通过自然语言描述业务意图，需要系统自动生成对应的PSOP工作流时，可通过该接口实现意图到工作流的自动转换。

- 功能描述

    接收自然语言描述的业务意图，通过大模型理解用户需求，自动生成符合要求的PSOP工作流JSON数据。

- 接口约束

  - 单实例上该接口最大并发数为50。

- 调用方法

    POST

- URI

    */generate-from-intent*

- 请求参数

  <a id="表17-body参数列表"></a>**表17** body参数列表

    | 参数名称         | 是否必选 | 类型     | 值域        | 默认值 | 描述                 |
    |--------------|------|--------|-----------|-----|--------------------|
    | user_intent  | 是    | string | -        | -   | 自然语言描述的业务意图。       |
    | workflow_name | 否    | string | 1~100个字符  | -   | 工作流名称，不提供时自动生成。    |

- 请求示例

    ```json
    POST /generate-from-intent HTTP/1.1
    Host: your-domain.com
    Content-Type: application/json
    {
      "user_intent": "我希望实现一个RAN网络节能优化的工作流，能够自动探索意图目标、配置节能策略并生成效果报告",
      "workflow_name": "RAN节能工作流"
    }
    ```

- 响应参数

    <a id="表18-响应参数列表"></a>**表18** 响应参数列表

    | 参数名称   | 是否必选 | 类型     | 值域   | 默认值 | 描述                  |
    |--------|------|--------|------|-----|---------------------|
    | status | 是    | string | -    | -   | 响应状态，成功为"success"。 |
    | data   | 否    | object | -    | -   | 生成的PSOP工作流JSON对象。  |

- 响应样例

    生成成功：
    ```json
    {
      "status": "success",
      "data": {
        "id": "psop-auto-001",
        "name": "RAN节能工作流",
        "description": "基于用户意图自动生成的RAN网络节能优化工作流",
        "steps": [
          {
            "id": "step-1",
            "name": "意图探索",
            "agent_name": "RAN Energy Saving Agent",
            "skill_id": "ran-es-intent-exploration"
          },
          {
            "id": "step-2",
            "name": "策略配置",
            "agent_name": "RAN Energy Saving Agent",
            "skill_id": "ran-es-intent-lifecycle-management"
          },
          {
            "id": "step-3",
            "name": "效果报告",
            "agent_name": "RAN Energy Saving Agent",
            "skill_id": "ran-es-intent-reporting"
          }
        ],
        "tags": ["wireless", "energy-saving", "auto-generated"]
      }
    }
    ```

    生成失败：
    ```json
    {
      "status": "error",
      "message": "意图理解失败，请提供更详细的描述"
    }
    ```

- 状态码

  | 状态码 | 说明               |
  |--------|------------------|
  | 200    | 生成成功。            |
  | 400    | 生成失败，参数校验失败。     |
  | 500    | 生成失败，服务内部错误。     |

## 意图检索PSOP

- 典型场景

    用户希望通过自然语言描述查找已存在的PSOP工作流时，可通过该接口实现语义化检索。

- 功能描述

    接收自然语言描述的业务意图，通过语义理解能力匹配系统中已保存的PSOP工作流，返回最相关的工作流列表。

- 接口约束

  - 返回最匹配的单个工作流，若无匹配则返回空。
  - 单实例上该接口最大并发数为50。

- 调用方法

    POST

- URI

    */retrieve-by-intent*

- 请求参数

  <a id="表19-body参数列表"></a>**表19** body参数列表

    | 参数名称        | 是否必选 | 类型     | 值域 | 默认值 | 描述            |
    |-------------|------|--------|----|-----|---------------|
    | user_intent | 是    | string | -  | -   | 自然语言描述的业务意图。 |

- 请求示例

    ```json
    POST /retrieve-by-intent HTTP/1.1
    Host: your-domain.com
    Content-Type: application/json
    {
      "user_intent": "我需要一个关于RAN网络节能的工作流"
    }
    ```

- 响应参数

    <a id="表20-响应参数列表"></a>**表20** 响应参数列表

    | 参数名称      | 是否必选 | 类型              | 值域 | 默认值 | 描述                                  |
    |-----------|------|-----------------|----|-----|-------------------------------------|
    | status    | 是    | string          | -  | -   | 响应状态，成功为"success"。                 |
    | workflows | 否    | array_reference | -  | -   | 匹配的工作流列表，详细请参见[表9](#表9-psop对象的参数列表)。 |

- 响应样例

    检索成功：
    ```json
    {
      "status": "success",
      "workflows": [
        {
          "id": "psop-001",
          "name": "RAN节能工作流",
          "description": "RAN网络节能优化工作流",
          "steps": [
            {
              "id": "step-1",
              "name": "意图探索",
              "agent_name": "RAN Energy Saving Agent",
              "skill_id": "ran-es-intent-exploration"
            }
          ],
          "tags": ["wireless", "energy-saving"],
          "created_at": "2026-01-15T10:30:00Z",
          "updated_at": "2026-01-15T10:30:00Z"
        }
      ]
    }
    ```

    未找到匹配工作流：
    ```json
    {
      "status": "success",
      "workflows": []
    }
    ```

- 状态码

  | 状态码 | 说明            |
  |--------|---------------|
  | 200    | 检索成功。         |
  | 400    | 检索失败，参数校验失败。 |
  | 500    | 检索失败，服务内部错误。 |

## SSE执行工作流

- 典型场景

    用户需要执行已保存的PSOP工作流并实时查看执行进度时，可通过该接口启动工作流并通过SSE接收实时进度更新。

- 功能描述

    启动指定的PSOP工作流执行，通过Server-Sent Events (SSE)实时推送工作流执行进度、Agent调用状态和执行结果。

- 接口约束

  - 工作流ID必须存在。
  - 客户端需支持EventSource API或SSE协议。
  - 单实例上该接口最大并发数为50。

- 调用方法

    GET

- URI

    */rest/start_process_stream*

- 请求参数

  <a id="表21-query参数列表"></a>**表21** query参数列表

    | 参数名称    | 是否必选 | 类型     | 值域 | 默认值 | 描述            |
    |---------|------|--------|----|-----|---------------|
    | psop_id | 是    | string | -  | -   | PSOP工作流ID，唯一标识。 |

- 请求示例

    ```json
    GET /rest/start_process_stream?psop_id=psop-001 HTTP/1.1
    Host: your-domain.com
    Accept: text/event-stream
    Cache-Control: no-cache
    Connection: keep-alive
    ```

- 响应参数

  <a id="表22-sse事件类型列表"></a>**表22** SSE事件类型列表

    | 事件类型           | 描述                          |
    |----------------|-----------------------------|
    | init           | 初始化事件，返回工作流基本信息。            |
    | start          | 工作流开始执行事件。                  |
    | agent_request  | Agent请求事件，包含Agent调用参数。      |
    | agent_response | Agent响应事件，包含Agent执行结果。      |
    | psop_update    | 工作流状态更新事件，包含当前步骤执行状态。       |
    | complete       | 工作流执行完成事件，包含最终执行结果。         |
    | error          | 执行错误事件，包含错误信息。              |
    | close          | 连接关闭事件，SSE流结束。              |

  <a id="表23-sse事件数据参数列表"></a>**表23** SSE事件数据参数列表

    | 参数名称        | 是否必选 | 类型     | 值域   | 默认值 | 描述               |
    |-------------|------|--------|------|-----|------------------|
    | event       | 是    | string | -    | -   | 事件类型。            |
    | data        | 是    | object | -    | -   | 事件数据，JSON格式。     |
    | timestamp   | 是    | string | ISO时间格式 | -   | 事件发生时间戳。         |

- 响应样例

    SSE事件流示例：
    ```
    event: init
    data: {"psop_id": "psop-001", "name": "RAN节能工作流", "total_steps": 3}
    timestamp: 2026-01-15T10:30:00Z

    event: start
    data: {"message": "工作流开始执行"}
    timestamp: 2026-01-15T10:30:01Z

    event: agent_request
    data: {"step_id": "step-1", "agent_name": "RAN Energy Saving Agent", "skill_id": "ran-es-intent-exploration", "input": {}}
    timestamp: 2026-01-15T10:30:02Z

    event: agent_response
    data: {"step_id": "step-1", "output": {"result": "意图探索完成"}}
    timestamp: 2026-01-15T10:30:05Z

    event: psop_update
    data: {"step_id": "step-1", "status": "completed", "progress": 33}
    timestamp: 2026-01-15T10:30:05Z

    event: complete
    data: {"status": "success", "message": "工作流执行完成", "total_steps": 3, "completed_steps": 3}
    timestamp: 2026-01-15T10:30:15Z

    event: close
    data: {"message": "SSE连接关闭"}
    timestamp: 2026-01-15T10:30:15Z
    ```

    执行失败示例：
    ```
    event: error
    data: {"error_code": "AGENT_TIMEOUT", "message": "Agent响应超时", "step_id": "step-2"}
    timestamp: 2026-01-15T10:30:20Z
    ```

- 状态码

  | 状态码 | 说明                    |
  |--------|-----------------------|
  | 200    | SSE连接建立成功，开始推送事件流。    |
  | 400    | 参数校验失败，缺少psop_id或格式错误。 |
  | 404    | 工作流不存在。               |
  | 500    | 执行失败，服务内部错误。          |