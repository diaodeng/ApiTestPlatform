# 关于定时任务

## 通用任务

## 任务执行测试
 配置参数示例
 ```json
 {
  "userName": "panda", # 用户名
  "userId": 4, # 用户ID
  "ids": [], # 数据id
  "runType": 1, # RunTypeEnum
  "reportName": "定时执行", # 报告名称，可选
  "repeatNum": 1, # 重复执行次数， 默认1
  "env": 20, # 环境ID。必填
  "concurrent": 1, # 并发数，默认1
  "feishuRobot": {
        "url": "51946e38-bf5d-40ee-9142-c97b55b67b1d",  # 飞书机器人token（url的最后一节）
        "keywords": [], # 关键字
        "secret": "openwrt-312209",
        "atUserId": [],
        "push": true # 是否推送，默认false
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