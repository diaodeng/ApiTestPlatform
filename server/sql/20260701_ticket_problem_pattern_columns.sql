ALTER TABLE ticket
  ADD COLUMN problem_pattern_code VARCHAR(128) NULL COMMENT '细分问题类型编码' AFTER resolution_name,
  ADD COLUMN problem_pattern_name VARCHAR(256) NULL COMMENT '细分问题类型名称' AFTER problem_pattern_code,
  ADD COLUMN problem_pattern_confidence INT NULL COMMENT '细分问题类型置信度，0-100' AFTER problem_pattern_name,
  ADD COLUMN problem_pattern_source VARCHAR(32) NULL COMMENT '细分问题类型来源' AFTER problem_pattern_confidence,
  ADD COLUMN problem_pattern_verified TINYINT(1) NULL COMMENT '细分问题类型是否人工确认' AFTER problem_pattern_source,
  ADD COLUMN problem_pattern_verified_by VARCHAR(100) NULL COMMENT '细分问题类型确认人' AFTER problem_pattern_verified,
  ADD COLUMN problem_pattern_verified_at DATETIME NULL COMMENT '细分问题类型确认时间' AFTER problem_pattern_verified_by;
