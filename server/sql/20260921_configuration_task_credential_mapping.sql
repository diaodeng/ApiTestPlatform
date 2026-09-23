-- 2026-09-21 配置任务系统凭证映射表
-- 任务级"系统标识 → 凭证绑定"映射：阶段/阶段模板通过 system_key 声明目标系统，
-- 凭证绑定在任务级统一配置；该映射独立于版本快照，发布后仍可修改（环境配置不冻结）。

CREATE TABLE IF NOT EXISTS configuration_task_credential_mapping (
  mapping_id BIGINT NOT NULL COMMENT '映射ID，Snowflake BIGINT',
  task_id BIGINT NOT NULL COMMENT '任务ID',
  system_key VARCHAR(64) NOT NULL COMMENT '系统标识，任务内唯一，阶段通过它引用',
  credential_binding_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '统一凭证绑定ID，空表示未绑定',
  remark VARCHAR(255) NOT NULL DEFAULT '' COMMENT '说明，如目标系统名称/地址',
  create_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '创建者',
  create_time DATETIME NOT NULL COMMENT '创建时间',
  update_by VARCHAR(64) NOT NULL DEFAULT '' COMMENT '更新者',
  update_time DATETIME NOT NULL COMMENT '更新时间',
  PRIMARY KEY (mapping_id),
  UNIQUE KEY uk_ct_cred_map_task_key (task_id, system_key),
  KEY idx_ct_cred_map_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配置任务系统凭证映射';
