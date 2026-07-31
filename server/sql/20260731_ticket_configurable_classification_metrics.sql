-- 2026-07-31 工单外部分类映射与可配置趋势指标
-- 执行前备份 ticket、ticket_statistics_daily、ticket_statistics_period_snapshot。

ALTER TABLE ticket
  ADD COLUMN classification_source VARCHAR(32) NOT NULL DEFAULT '' COMMENT '工单类型分类来源：manual/external_mapping/ai' AFTER issue_type_name,
  ADD COLUMN classification_rule_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '外部字段分类规则ID' AFTER classification_source,
  ADD COLUMN classification_updated_at DATETIME NULL COMMENT '工单类型分类更新时间' AFTER classification_rule_id;

CREATE TABLE IF NOT EXISTS ticket_statistics_metric_snapshot (
  id BIGINT NOT NULL COMMENT '指标快照ID',
  snapshot_type VARCHAR(32) NOT NULL COMMENT '快照类型：daily/business_week',
  snapshot_key VARCHAR(64) NOT NULL COMMENT '快照日期或业务周开始日期',
  snapshot_scope VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT '快照范围：all/leaf',
  project_id BIGINT NOT NULL DEFAULT 0 COMMENT '项目ID',
  module_id BIGINT NOT NULL DEFAULT 0 COMMENT '模块ID',
  issue_type_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '工单类型编码',
  metric_code VARCHAR(64) NOT NULL COMMENT '指标编码',
  metric_label VARCHAR(128) NOT NULL DEFAULT '' COMMENT '指标名称',
  group_code VARCHAR(64) NOT NULL COMMENT '指标分组编码',
  group_label VARCHAR(128) NOT NULL DEFAULT '' COMMENT '指标分组名称',
  count INT NOT NULL DEFAULT 0 COMMENT '命中数量',
  definition_revision VARCHAR(64) NOT NULL DEFAULT '' COMMENT '指标定义版本',
  create_time DATETIME NOT NULL COMMENT '创建时间',
  update_time DATETIME NOT NULL COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_ticket_metric_snapshot_scope (snapshot_type, snapshot_key, snapshot_scope, project_id, module_id, issue_type_id, metric_code, group_code),
  KEY idx_ticket_metric_snapshot_time (snapshot_type, snapshot_key),
  KEY idx_ticket_metric_snapshot_metric (metric_code, snapshot_type, snapshot_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单可配置趋势指标快照';

-- 配置外部映射和自定义指标后，执行已有维护任务补算历史日和业务周。
-- 例如在应用任务入口补跑 2026-01-01 至当前日期；新表按快照键覆盖，重复执行不会累加。
-- 旧 ticket_statistics_daily / ticket_statistics_period_snapshot 中没有、也不再读取 Bug/非Bug/支持类固定计数字段，不需要删历史列或回填。
