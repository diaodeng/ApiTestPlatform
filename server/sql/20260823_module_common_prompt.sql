-- 2026-08-23 工单模块通用提示词
--
-- 使用顺序：
-- 1. 先执行本文件中的预检 SELECT，确认同一项目内 trim(module_code) 没有重复；
-- 2. 对空编码、重复编码进行人工处理，不自动合并 module_id 或历史工单；
-- 3. 确认预检结果为空后，再执行最后的联合唯一索引 DDL；
-- 4. 由「HRM -> 模块通用提示词」页面按业务语义录入通用说明。
--
-- 历史 AI 任务的 prompt_text/analysis_context 不在本迁移中回填。

CREATE TABLE IF NOT EXISTS hrm_module_common_prompt (
  prompt_id BIGINT NOT NULL COMMENT '模块通用提示词ID',
  module_code VARCHAR(128) NOT NULL COMMENT '模块业务编码',
  prompt_content LONGTEXT NOT NULL COMMENT '模块通用说明',
  enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  create_by VARCHAR(64) NULL DEFAULT '' COMMENT '创建者',
  create_time DATETIME NOT NULL COMMENT '创建时间',
  update_by VARCHAR(64) NULL DEFAULT '' COMMENT '更新者',
  update_time DATETIME NOT NULL COMMENT '更新时间',
  remark VARCHAR(500) NULL DEFAULT '' COMMENT '备注',
  del_flag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标志：0存在 2删除',
  PRIMARY KEY (prompt_id),
  UNIQUE KEY uk_hrm_module_common_prompt_code (module_code),
  KEY idx_hrm_module_common_prompt_enabled (enabled, del_flag),
  KEY idx_hrm_module_common_prompt_update_time (update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单模块通用提示词';

-- 预检：以下查询必须均无结果后，才执行后续 ALTER TABLE。
SELECT
  project_id,
  TRIM(module_code) AS normalized_module_code,
  COUNT(*) AS duplicate_count,
  GROUP_CONCAT(module_id ORDER BY module_id) AS module_ids
FROM hrm_module
WHERE NULLIF(TRIM(module_code), '') IS NOT NULL
GROUP BY project_id, TRIM(module_code)
HAVING COUNT(*) > 1;

SELECT module_id, project_id, module_code
FROM hrm_module
WHERE module_code IS NOT NULL
  AND module_code <> TRIM(module_code);

-- 生产确认预检为空后执行：
-- ALTER TABLE hrm_module
--   ADD UNIQUE KEY uk_hrm_module_project_code (project_id, module_code);
