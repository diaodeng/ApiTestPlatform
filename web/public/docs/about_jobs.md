# 关于定时任务

## TID / trace_id 查询

系统任务日志现在会保存每次执行的 `TID / trace_id`。当你已经从某一步自动任务里拿到 TID 时，可以进入 **系统监控 → 定时任务 → 调度日志**（或 QTR 对应的任务日志页），直接按 **TID** 搜索，串起同一次执行链路的全部任务日志。

- 日志列表新增 **TID** 列；
- 搜索区域新增 **TID** 输入框；
- 日志详情会展示完整 `trace_id`；
- 导出任务日志时也会带出 TID，方便线下排查。

## 通用任务

## 任务执行测试

调用方法：`module_task.scheduler_qtr.job_run_test

 配置关键字参数示例
 ```json
 {
  "userName": "panda", # 用户名
  "userId": 4, # 用户ID
  "ids": [], # 数据id
  "runType": 1, # RunTypeEnum
  "reportName": "定时执行", # 报告名称，可选
  "repeatNum": 1, # 重复执行次数， 默认1
  "env": 20, # 环境ID。必填
  "concurrent": 1, # 并发数，默认1,
  "runBySort"： false,  # 是否按顺序执行用例，默认false，设置为true时concurrent应该为1
  "push": false,  # 推送总开开关，默认false
  "feishuRobot": {
        "url": "51946e38-bf5d-40ee-9142-c97b55b67b1d",  # 飞书机器人token（url的最后一节）
        "keywords": [], # 关键字
        "secret": "openwrt-312209",
        "atUserId": [],
        "push": true # 是否推送，默认false
    },
  "forwardConfig": {  # 可选，默认不转发
    "forward": false, # 是否转发， 默认false
    "agentId": null, # agent管理列表中的记录，默认为空，则不转发到agent
    "forwardRuleIds": [], # 转发规则管理列表中对应的id列表，默认为空列表【不转发】
  }
}

# 简化
{
  "userName": "panda",
  "userId": 4,
  "ids": [1791140478180352],
  "runType": 1,
  "env": 20,
  "feishuRobot": {
        "push": true
    }
}
 ```

##### RunTypeEnum

##### class RunTypeEnum(Enum):
- case = 1
- model = 2
- suite = 4
- project = 8
- api = 16
- case_debug = 32