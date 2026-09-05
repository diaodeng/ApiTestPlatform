# 2026-09-06 资源指标 role 标签分层修复

## 问题现象

检查 VictoriaMetrics 上报数据发现两类分组混乱：

1. 机器/容器级指标（`cpu_usage_percent`、`memory_used_mb`、`memory_limit_mb`、`memory_pressure`、`memory_actual_available_mb`、`cpu_limit_cores` 及全部 `qtr_cgroup_*`）被拆成 `api` / `celery_beat` / `celery_worker` 三条序列。三个进程采集到的本来就是同一份机器数据，拆分后按机器聚合（sum/avg）会三倍虚高。
2. 扩展指标上线初期（约 2026-08-27 之前）的 `qtr_process_*` 进程序列缺失 `role` 标签，API/Worker/Beat 三个进程互相覆盖同一条序列，进程内存曲线呈无规律锯齿跳变，无法用于归因。

## 根因

采集线程对所有指标统一附加同一组标签，未区分指标归属层级：机器级数据不应带 `role`，进程级数据必须带 `role`。

## 修复内容

`server/utils/metrics/collect.py` 的样本格式化逻辑按指标分层处理标签：

- 机器级（machine 采集结果）与容器级（cgroup）指标：强制剥离 `role` 标签，每台机器每个指标只有一条序列；
- 进程级（`qtr_process_*`）与任务级（`qtr_task_*`）指标：强制携带 `role` 标签，三个进程序列互不覆盖。

## 对查询的影响

- 看整机 CPU/内存/cgroup：这些指标已无 `role` 标签，按 `machine` 分组即可；
- 看进程内存与任务归因：按 `role` 分组；
- 2026-08-27 之前的历史数据标签形态与现在不同，长期趋势对比时需注意剔除该时间段。

## 附带发现

VM 中存在 `machine=home`（instance=TEST）的旧环境数据，已停止推送；`machine=dev` 仅存在于一个月前，均为历史遗留，不属于当前链路。

## 验证

新增两个回归测试用例（机器级无 role、兼容模式只发机器级样本），`tests/test_memory_metrics.py` 7 个用例全部通过；ruff 检查无新增问题。
