# 性能测试使用说明

## 1. 功能定位

性能测试模块用于在平台中管理压测场景、参数化数据、执行节点、运行记录和报告摘要。

当前实现以 Locust 作为首个压测执行引擎，后端负责：

- 保存压测场景 DSL；
- 保存 CSV 参数化数据；
- 每次运行动态生成 `locustfile.py` 和 `cases.csv`；
- 启动任务级 Locust master 子进程；
- 支持本机单进程执行；
- 支持 master + worker 分布式执行；
- 支持 Worker 注册、心跳、占用和释放；
- 支持手动选择 Worker 或自动选择 Worker；
- 支持停止、强制停止压测；
- 采集 Locust CSV/HTML 产物并生成报告摘要；
- 支持多次历史运行结果对比。

> 说明：Locust 不直接运行在 FastAPI 主进程内，而是以子进程方式启动，避免 gevent/monkey patch 影响 FastAPI。

## 2. 基本概念

### 2.1 场景 Scenario

场景是压测的静态配置，包含：

- 被测服务地址；
- 执行引擎；
- 请求 DSL；
- CSV 参数化数据；
- 备注说明。

场景可以被多次运行。修改场景后，下一次运行会重新生成 Locust 脚本，不需要手工重启 worker 或同步脚本。

### 2.2 运行 Run

运行是一次实际压测任务，包含：

- 并发用户数；
- 启动速率；
- 执行时长；
- Worker 选择方式；
- 运行状态；
- Locust master 端口；
- 运行产物目录；
- 报告摘要。

### 2.3 Worker

Worker 是压测执行节点。平台通过注册和心跳知道 Worker 是否可用。

Worker 状态：

- `idle`：空闲，可以被选择；
- `busy`：正在执行任务，不能被其他任务选择；
- `unhealthy`：不可用或心跳过期。

### 2.4 报告 Summary

报告摘要从 Locust CSV 产物中生成，主要字段包括：

- 请求总数；
- 失败数；
- 平均响应时间；
- P50；
- P95；
- P99；
- RPS；
- 失败率；
- 失败详情。

## 3. 推荐使用流程

### 3.1 单机模式

适合本地调试或没有 Worker 节点时使用。

1. 创建压测场景；
2. 创建运行记录；
3. 启动运行；
4. 查询状态；
5. 停止或等待运行结束；
6. 查看报告摘要；
7. 多次运行后做历史对比。

如果没有注册可用 Worker，自动模式会回退为本机单进程 Locust 执行。

### 3.2 分布式模式

适合正式压测。

1. 启动平台后端；
2. Worker 节点向平台注册；
3. Worker 节点持续上报心跳；
4. 创建压测场景；
5. 创建运行记录，选择 `auto` 或 `manual` Worker 模式；
6. 启动运行；
7. Worker 拉取 assignment 并启动 locust worker；
8. master 等待 worker 连接后开始压测；
9. 停止压测或等待运行结束；
10. 平台释放 Worker；
11. 查看报告和历史对比。

> 分布式模式要求 Worker 能访问运行目录中的动态脚本，例如通过共享目录、挂载盘、NFS、PVC，或后续由 Worker agent 下载脚本。

## 4. 接口说明

接口统一前缀：

```text
/pressure
```

### 4.1 创建场景

```http
POST /pressure/scenarios
```

请求体：

```json
{
  "project_id": 1,
  "name": "订单查询压测",
  "engine": "locust",
  "base_url": "http://127.0.0.1:8000",
  "dsl": {
    "wait_time": {
      "min": 0.1,
      "max": 0.5
    },
    "tasks": [
      {
        "name": "query_order",
        "weight": 1,
        "request": {
          "method": "GET",
          "url": "/api/orders/${order_id}",
          "headers": {
            "Authorization": "Bearer ${token}"
          }
        },
        "assertions": [
          {
            "source": "status_code",
            "op": "==",
            "expected": 200
          },
          {
            "source": "code",
            "op": "==",
            "expected": 0
          }
        ]
      }
    ]
  },
  "csv_text": "case\n{\"name\":\"case_1\",\"order_id\":1001,\"token\":\"token-1\",\"assert\":{\"status_code\":200,\"code\":0}}\n",
  "remark": "订单查询接口基准压测"
}
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | integer | 否 | 项目 ID，不传默认为 `0` |
| `name` | string | 是 | 场景名称 |
| `engine` | string | 否 | 执行引擎，当前生产可用值为 `locust` |
| `base_url` | string | 否 | 被测服务基础地址 |
| `dsl` | object | 是 | 压测请求 DSL |
| `csv_text` | string | 否 | CSV 参数化文本 |
| `remark` | string | 否 | 备注 |

### 4.2 查询场景列表

```http
GET /pressure/scenarios
GET /pressure/scenarios?project_id=1
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | integer | 否 | 按项目过滤场景 |

### 4.3 查询场景详情

```http
GET /pressure/scenarios/{scenario_id}
```

路径参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `scenario_id` | integer | 场景 ID |

### 4.4 更新场景

```http
PUT /pressure/scenarios/{scenario_id}
```

请求体支持局部更新：

```json
{
  "name": "订单查询压测-v2",
  "base_url": "http://127.0.0.1:9000",
  "csv_text": "case\n{\"name\":\"case_1\",\"order_id\":2001,\"token\":\"token-2\"}\n"
}
```

说明：

- 更新场景不会影响已经完成的运行记录；
- 下一次启动运行时会基于最新场景重新生成脚本和 CSV；
- 修改 CSV 或 DSL 后不需要手工重启 Worker。

### 4.5 创建运行记录

```http
POST /pressure/runs
```

请求体：

```json
{
  "scenario_id": 1,
  "users": 30,
  "spawn_rate": 5,
  "run_time": "5m",
  "target_qps": 10,
  "worker_mode": "auto",
  "worker_ids": []
}
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `scenario_id` | integer | 是 | 场景 ID |
| `users` | integer | 否 | 并发用户数，默认 `1`，最小 `1` |
| `spawn_rate` | number | 否 | 每秒启动用户数，默认 `1`，必须大于 `0` |
| `run_time` | string | 否 | 执行时长，例如 `30s`、`5m`、`1h` |
| `target_qps` | number | 否 | 目标 QPS，用于自动估算所需容量 |
| `worker_mode` | string | 否 | Worker 选择方式，`auto` 或 `manual` |
| `worker_ids` | array | 否 | 手动模式下指定 Worker ID 列表 |

### 4.6 启动运行

```http
POST /pressure/runs/{run_id}/start
```

启动过程：

1. 校验运行记录和场景；
2. 生成运行目录；
3. 生成 `locustfile.py`；
4. 生成 `data/cases.csv`；
5. 自动或手动分配 Worker；
6. 启动 Locust master 子进程；
7. 调用 Locust `/swarm` 开始压测；
8. 运行状态变为 `running`。

运行产物默认生成在：

```text
server/storage/pressure/runs/run_{run_id}
```

目录结构：

```text
run_{run_id}/
  locustfile.py
  scenario.json
  report.html
  stats_stats.csv
  stats_failures.csv
  locust-master.log
  data/
    cases.csv
```

### 4.7 停止运行

```http
POST /pressure/runs/{run_id}/stop
```

停止过程：

1. 调用 Locust `/stop`；
2. 采集 CSV 报告；
3. 生成 summary；
4. 终止 master 子进程；
5. 释放被占用 Worker；
6. 运行状态变为 `finished`。

### 4.8 强制停止运行

```http
POST /pressure/runs/{run_id}/force-stop
```

适用场景：

- Locust Web API 无响应；
- master 进程卡住；
- 需要直接释放 Worker。

强制停止后状态为：

```text
canceled
```

### 4.9 查询运行状态

```http
GET /pressure/runs/{run_id}/status
```

返回内容包含：

- 平台运行记录；
- Locust 实时统计；
- master 端口；
- Worker 分配结果；
- 报告路径；
- 错误信息。

### 4.10 查询运行历史

```http
GET /pressure/runs
GET /pressure/runs?scenario_id=1&limit=20
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `scenario_id` | integer | 否 | 按场景过滤 |
| `limit` | integer | 否 | 返回条数，默认 `20`，范围 `1-200` |

### 4.11 历史结果对比

```http
POST /pressure/runs/compare
```

请求体：

```json
{
  "run_ids": [1, 2, 3]
}
```

对比字段：

- 并发用户数；
- 启动速率；
- 请求总数；
- 失败数；
- RPS；
- 平均响应时间；
- P95；
- 失败率；
- 开始时间；
- 结束时间。

### 4.12 手动刷新报告摘要

```http
POST /pressure/runs/{run_id}/summary
```

适用场景：

- 运行进程已结束，但 summary 未及时回填；
- 手动替换或补齐 Locust CSV 后需要重新生成摘要。

## 5. Worker 接入说明

### 5.1 注册 Worker

```http
POST /pressure/workers/register
```

请求体：

```json
{
  "worker_id": "worker-01",
  "host": "10.0.0.11",
  "hostname": "load-node-01",
  "cpu_cores": 8,
  "memory_mb": 16384,
  "max_users": 1000,
  "engine_types": ["locust"],
  "labels": ["dev", "api"]
}
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `worker_id` | string | 是 | Worker 唯一标识 |
| `host` | string | 是 | Worker 主机地址 |
| `hostname` | string | 否 | 主机名 |
| `cpu_cores` | integer | 否 | CPU 核数，默认 `1` |
| `memory_mb` | integer | 否 | 内存 MB，默认 `1024` |
| `max_users` | integer | 否 | Worker 理论最大用户数，默认 `100` |
| `engine_types` | array | 否 | 支持的压测引擎，默认 `["locust"]` |
| `labels` | array | 否 | 标签，例如环境、机房、用途 |

### 5.2 Worker 心跳

```http
POST /pressure/workers/heartbeat
```

请求体：

```json
{
  "worker_id": "worker-01",
  "run_id": 1,
  "current_users": 200,
  "cpu_usage": 0.55,
  "memory_usage": 0.62,
  "rps": 120.5,
  "fail_rate": 0.01,
  "latency_ms": 80,
  "status": "busy"
}
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `worker_id` | string | 是 | Worker 唯一标识 |
| `run_id` | integer | 否 | 当前运行 ID |
| `current_users` | integer | 否 | 当前承载用户数 |
| `cpu_usage` | number | 否 | CPU 使用率，范围建议 `0-1` |
| `memory_usage` | number | 否 | 内存使用率，范围建议 `0-1` |
| `rps` | number | 否 | 当前 RPS |
| `fail_rate` | number | 否 | 失败率，范围建议 `0-1` |
| `latency_ms` | number | 否 | 平均响应时间，单位毫秒 |
| `status` | string | 否 | 当前状态：`idle`、`busy`、`unhealthy` |

### 5.3 查询 Worker 列表

```http
GET /pressure/workers
GET /pressure/workers?include_unhealthy=true
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `include_unhealthy` | boolean | 否 | 是否包含不健康 Worker，默认 `false` |

### 5.4 Worker 拉取任务

```http
GET /pressure/workers/{worker_id}/assignment
```

无任务时：

```json
{
  "assigned": false
}
```

有任务时：

```json
{
  "assigned": true,
  "run_id": 1,
  "status": "starting",
  "engine": "locust",
  "artifact_dir": "C:/myself/api-test-platform/server/storage/pressure/runs/run_1",
  "script_path": "C:/myself/api-test-platform/server/storage/pressure/runs/run_1/locustfile.py",
  "master_host": "10.0.0.10",
  "master_port": 5557,
  "command": [
    "python",
    "-m",
    "locust",
    "-f",
    "C:/myself/api-test-platform/server/storage/pressure/runs/run_1/locustfile.py",
    "--worker",
    "--master-host",
    "10.0.0.10",
    "--master-port",
    "5557"
  ]
}
```

Worker agent 可以根据 `command` 启动 locust worker。

## 6. DSL 使用说明

### 6.1 DSL 总体结构

```json
{
  "target": {
    "base_url": "http://127.0.0.1:8000"
  },
  "wait_time": {
    "min": 0.1,
    "max": 0.5
  },
  "tasks": [
    {
      "name": "task_name",
      "weight": 1,
      "request": {},
      "assertions": []
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `target.base_url` | string | 否 | 被测服务地址；也可以使用场景的 `base_url` |
| `wait_time.min` | number | 否 | 用户两次任务之间最小等待秒数，默认 `0.1` |
| `wait_time.max` | number | 否 | 用户两次任务之间最大等待秒数，默认 `0.5` |
| `tasks` | array | 是 | Locust 用户循环执行的任务列表 |

### 6.2 task 参数

```json
{
  "name": "create_order",
  "weight": 2,
  "request": {
    "method": "POST",
    "url": "/api/orders",
    "headers": {
      "Authorization": "Bearer ${token}",
      "Content-Type": "application/json"
    },
    "params": {
      "source": "pressure"
    },
    "json": {
      "sku_id": "${sku_id}",
      "count": 1
    },
    "name": "创建订单"
  },
  "assertions": [
    {
      "source": "status_code",
      "op": "==",
      "expected": 200
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 否 | 任务名，也会作为默认请求名 |
| `weight` | integer | 否 | 权重，默认 `1`；权重越高执行概率越高 |
| `request.method` | string | 否 | HTTP 方法，默认 `GET` |
| `request.url` | string | 是 | 请求路径，支持 `${变量}` |
| `request.path` | string | 否 | `url` 的兼容字段 |
| `request.headers` | object | 否 | 请求头，支持 `${变量}` |
| `request.params` | object | 否 | Query 参数，支持 `${变量}` |
| `request.json` | object | 否 | JSON 请求体，支持 `${变量}` |
| `request.body` | object | 否 | `json` 的兼容字段 |
| `request.data` | object/string | 否 | 表单或原始请求体 |
| `request.name` | string | 否 | Locust 统计中显示的请求名 |
| `assertions` | array/object | 否 | 断言规则 |

### 6.3 变量替换

请求中的字符串支持 `${变量名}` 占位符。

示例：

```json
{
  "headers": {
    "Authorization": "Bearer ${token}"
  },
  "json": {
    "username": "${username}",
    "password": "${password}"
  }
}
```

变量来自当前 CSV 行。

## 7. CSV 参数化说明

### 7.1 推荐格式：单列 case JSON

CSV：

```csv
case
{"name":"case_1","token":"token-1","order_id":1001,"assert":{"status_code":200,"code":0}}
{"name":"case_2","token":"token-2","order_id":1002,"assert":{"status_code":200,"code":0}}
```

说明：

- 表头必须包含 `case`；
- 每一行 `case` 是一个 JSON 字符串；
- JSON 中既可以放请求变量，也可以放请求覆盖配置和断言；
- Locust 并发用户会从 CSV 中循环取数据，不会因为数据耗尽而停止。

### 7.2 普通多列 CSV

CSV：

```csv
name,token,order_id
case_1,token-1,1001
case_2,token-2,1002
```

DSL 中引用：

```json
{
  "request": {
    "url": "/api/orders/${order_id}",
    "headers": {
      "Authorization": "Bearer ${token}"
    }
  }
}
```

### 7.3 CSV 行覆盖请求配置

CSV 的 JSON 行可以覆盖 DSL 中的请求配置。

```csv
case
{"name":"case_1","request":{"method":"GET","url":"/api/orders/1001"},"assert":{"status_code":200}}
{"name":"case_2","request":{"method":"POST","url":"/api/orders","json":{"sku_id":1,"count":2}},"assert":{"status_code":200}}
```

覆盖规则：

- CSV 行中的 `request` 会和 DSL 默认 `request` 深度合并；
- CSV 中字段优先级高于 DSL；
- 未覆盖字段继续使用 DSL 默认值。

### 7.4 每次请求是否换一行

当前实现是每次执行任务时调用一次 CSV 数据源：

```text
每个请求 = 从 CSV 循环取一行
```

示例：

```text
CSV: case_1, case_2, case_3

请求1 -> case_1
请求2 -> case_2
请求3 -> case_3
请求4 -> case_1
```

## 8. 断言 DSL

### 8.1 完整断言格式

```json
{
  "source": "status_code",
  "op": "==",
  "expected": 200
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `source` | string | 是 | 取值来源 |
| `op` | string | 否 | 比较操作符，默认 `==` |
| `expected` | any | 是 | 期望值 |

### 8.2 source 取值

| source | 说明 |
| --- | --- |
| `status_code` | HTTP 状态码 |
| `status` | HTTP 状态码 |
| `text` | 响应文本 |
| `headers.xxx` | 响应头，例如 `headers.Content-Type` |
| `code` | JMESPath，从响应 JSON 中取 `code` |
| `data.id` | JMESPath，从响应 JSON 中取 `data.id` |
| `data.users[0].id` | JMESPath，数组取值 |
| `data.users[?role=='admin'].id | [0]` | JMESPath，数组过滤 |

### 8.3 支持的操作符

| op | 说明 | 示例 |
| --- | --- | --- |
| `==` | 等于 | `actual == expected` |
| `!=` | 不等于 | `actual != expected` |
| `in` | 实际值在期望集合中 | `actual in expected` |
| `contains` | 实际值包含期望值 | `expected in actual` |
| `regex` | 正则匹配 | `re.search(expected, actual)` |
| `range` | 数值范围 | `low <= actual <= high` |

### 8.4 断言示例

状态码：

```json
{
  "source": "status_code",
  "op": "==",
  "expected": 200
}
```

业务 code：

```json
{
  "source": "code",
  "op": "==",
  "expected": 0
}
```

数组过滤：

```json
{
  "source": "data.users[?role=='admin'].id | [0]",
  "op": "==",
  "expected": 1
}
```

字段属于枚举值：

```json
{
  "source": "data.status",
  "op": "in",
  "expected": ["SUCCESS", "PROCESSING"]
}
```

文本包含：

```json
{
  "source": "text",
  "op": "contains",
  "expected": "success"
}
```

正则：

```json
{
  "source": "data.order_no",
  "op": "regex",
  "expected": "^ORD[0-9]{10}$"
}
```

范围：

```json
{
  "source": "data.amount",
  "op": "range",
  "expected": [1, 100]
}
```

### 8.5 简写断言格式

也支持对象简写：

```json
{
  "assert": {
    "status_code": 200,
    "code": 0,
    "data.success": true
  }
}
```

等价于：

```json
[
  {
    "source": "status_code",
    "op": "==",
    "expected": 200
  },
  {
    "source": "code",
    "op": "==",
    "expected": 0
  },
  {
    "source": "data.success",
    "op": "==",
    "expected": true
  }
]
```

## 9. Worker 调度规则

### 9.1 自动模式 auto

创建运行时：

```json
{
  "worker_mode": "auto",
  "worker_ids": []
}
```

自动模式选择逻辑：

1. 查询状态为 `idle` 的 Worker；
2. 过滤心跳过期 Worker；
3. 过滤不支持当前引擎的 Worker；
4. 结合 `max_users`、当前用户数、CPU、内存、失败率和历史能力画像计算可用容量；
5. 按评分排序；
6. 选择足够承载本次运行的 Worker；
7. 将选中 Worker 标记为 `busy`。

### 9.2 手动模式 manual

创建运行时：

```json
{
  "worker_mode": "manual",
  "worker_ids": ["worker-01", "worker-02"]
}
```

手动模式规则：

- 必须传入至少一个 Worker；
- 传入的 Worker 必须存在；
- 传入的 Worker 必须是 `idle`；
- 任何一个 Worker 不可用都会启动失败；
- 被选中的 Worker 会被标记为 `busy`。

### 9.3 本机回退

自动模式下，如果没有可用 Worker，则会回退为本机单进程 Locust。

这适合：

- 本地调试；
- 小并发验证；
- Worker 池尚未部署时的功能检查。

正式压测建议使用 Worker 池。

## 10. 并发参数建议

### 10.1 users

`users` 是 Locust 模拟的并发用户数，不等于 QPS。

粗略计算：

```text
并发用户数 = 目标 QPS × 平均响应时间秒数 × 安全系数
```

示例：

```text
目标 QPS = 10
P95 RT = 1.3s
安全系数 = 2

建议 users = 10 × 1.3 × 2 = 26，向上取整为 30
```

### 10.2 spawn_rate

`spawn_rate` 是每秒启动多少用户。

建议：

- 小流量调试：`1-5`；
- 中等压测：`5-20`；
- 大流量压测：按 Worker 能力逐步增加；
- 不建议一开始设置过大，避免启动阶段瞬时冲击掩盖真实稳定性能。

### 10.3 run_time

`run_time` 是压测持续时间。

常用值：

| 值 | 说明 |
| --- | --- |
| `30s` | 快速验证 |
| `5m` | 小规模基准 |
| `15m` | 稳定性观察 |
| `1h` | 长稳压测 |

### 10.4 target_qps

`target_qps` 当前主要用于平台估算 Worker 容量需求。

注意：

- Locust 本身主要通过 `users` 和 `spawn_rate` 控制负载；
- `target_qps` 不是硬限速；
- 如果要严格限速，需要后续在脚本层增加限流策略。

## 11. 完整示例

### 11.1 创建场景

```json
{
  "project_id": 1,
  "name": "登录并查询用户",
  "engine": "locust",
  "base_url": "http://127.0.0.1:8000",
  "dsl": {
    "wait_time": {
      "min": 0.1,
      "max": 0.3
    },
    "tasks": [
      {
        "name": "login",
        "weight": 1,
        "request": {
          "method": "POST",
          "url": "/api/login",
          "json": {
            "username": "${username}",
            "password": "${password}"
          },
          "name": "登录"
        },
        "assertions": [
          {
            "source": "status_code",
            "op": "==",
            "expected": 200
          },
          {
            "source": "code",
            "op": "==",
            "expected": 0
          }
        ]
      },
      {
        "name": "query_profile",
        "weight": 3,
        "request": {
          "method": "GET",
          "url": "/api/users/${user_id}",
          "headers": {
            "Authorization": "Bearer ${token}"
          },
          "name": "查询用户"
        },
        "assertions": [
          {
            "source": "status_code",
            "op": "==",
            "expected": 200
          },
          {
            "source": "data.id",
            "op": "==",
            "expected": 1001
          }
        ]
      }
    ]
  },
  "csv_text": "case\n{\"name\":\"u1\",\"username\":\"test1\",\"password\":\"123456\",\"token\":\"token1\",\"user_id\":1001}\n{\"name\":\"u2\",\"username\":\"test2\",\"password\":\"123456\",\"token\":\"token2\",\"user_id\":1002,\"assert\":{\"status_code\":200}}\n"
}
```

### 11.2 创建运行

```json
{
  "scenario_id": 1,
  "users": 30,
  "spawn_rate": 5,
  "run_time": "5m",
  "target_qps": 10,
  "worker_mode": "auto",
  "worker_ids": []
}
```

### 11.3 启动运行

```http
POST /pressure/runs/1/start
```

### 11.4 查询状态

```http
GET /pressure/runs/1/status
```

### 11.5 停止运行

```http
POST /pressure/runs/1/stop
```

### 11.6 对比历史

```json
{
  "run_ids": [1, 2, 3]
}
```

## 12. 常见问题

### 12.1 修改场景后是否要重启 Worker？

不需要。

每次启动运行都会重新生成脚本和 CSV。Worker 通过 assignment 获取本次运行的脚本路径。

### 12.2 为什么正在执行的 Worker 不能再被选择？

为了避免多个 Locust master 同时控制同一 Worker，平台会把被分配的 Worker 标记为 `busy`。任务停止、完成或强制停止后才释放。

### 12.3 Master 是否常驻？

不是。

当前设计是任务级 master：

```text
一次运行 = 一个 Locust master 子进程
```

运行结束后 master 会被停止。

### 12.4 Worker 是否常驻？

建议 Worker agent 常驻。

Worker agent 负责：

- 注册；
- 心跳；
- 拉取 assignment；
- 启动或停止 locust worker 进程。

### 12.5 CSV 数据会不会被用完？

不会。

CSV 数据会被循环使用，适合压测中的重复请求和容量验证。

### 12.6 `target_qps` 能不能严格限制 QPS？

当前不能。

当前 `target_qps` 用于容量估算和报告对比，不是强制限速。严格限速需要后续在 Locust 脚本中增加限流器。

### 12.7 没有 Worker 能不能跑？

可以。

自动模式下没有可用 Worker 会回退为本机单进程 Locust，适合调试和小规模验证。

### 12.8 分布式执行为什么需要共享脚本？

Locust worker 启动时也需要加载同一份 `locustfile.py`。平台动态生成脚本后，Worker 必须能访问该脚本。

可选方案：

- 共享目录；
- NFS；
- Docker Volume；
- Kubernetes PVC；
- Worker agent 下载脚本到本地后启动。

## 13. 状态流转

运行状态：

```text
pending -> starting -> running -> stopping -> finished
                     -> failed
                     -> canceled
```

Worker 状态：

```text
idle -> busy -> idle
idle -> unhealthy
busy -> unhealthy
```

## 14. 使用建议

- 正式压测前先用小并发验证 DSL、CSV 和断言；
- CSV 中的 `case` JSON 保持一行一个完整请求数据；
- 断言尽量使用业务 code 和关键字段，不只检查 HTTP 状态码；
- 首次压测先用 `users=5`、`spawn_rate=1`、`run_time=30s`；
- 稳定后再逐步提高 `users` 和 `spawn_rate`；
- Worker 心跳建议 3-5 秒一次；
- Worker `max_users` 初始值保守设置，后续通过历史能力画像逐步修正；
- 历史对比重点看 P95、失败率、RPS 和错误详情；
- 大压测前确认 master 端口和 worker 端口网络可达。
