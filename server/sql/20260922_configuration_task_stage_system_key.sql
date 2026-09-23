-- 2026-09-22 阶段化执行阶段二：版本阶段与运行阶段快照支持"目标系统"声明
-- 阶段通过 system_key 引用任务系统凭证映射（configuration_task_credential_mapping），
-- 运行创建时服务端合并各系统凭证登录态为单一浏览器初始化 seed。

ALTER TABLE configuration_task_stage
  ADD COLUMN system_key VARCHAR(64) NOT NULL DEFAULT '' COMMENT '目标系统标识，引用任务系统凭证映射，空表示不使用独立凭证' AFTER stage_key;

ALTER TABLE configuration_task_run_stage
  ADD COLUMN system_key VARCHAR(64) NOT NULL DEFAULT '' COMMENT '目标系统标识快照，空表示不使用独立凭证' AFTER stage_key;
