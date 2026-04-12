# 提示词模板

## 1) 通用任务模板
```md
Goal:
- <一句话目标>

Context:
- Module/Path: <如 server/module_hrm/...>
- Current behavior or error: <现象、报错、日志>

Constraints:
- Must keep: <兼容性、接口、性能边界>
- Must not change: <禁止改动的目录/文件/契约>

Done When:
- [ ] <验收标准 1>
- [ ] <验收标准 2>
```

## 2) Bug 修复模板
```md
Goal:
- Fix bug: <问题名称>

Context:
- Repro steps:
1. <步骤 1>
2. <步骤 2>
- Actual result: <实际结果>
- Expected result: <预期结果>
- Related files: <相关文件路径>

Constraints:
- No breaking change to existing API response fields.
- DB schema 不改，除非明确授权。

Done When:
- [ ] 复现步骤已不再失败。
- [ ] 关键链路回归通过。
- [ ] 相关检查/测试通过。
```

## 3) 功能开发模板
```md
Goal:
- Add feature: <功能名>

Context:
- User story: <谁在什么场景需要什么能力>
- Scope: <模块/页面/API 范围>
- Out of scope: <明确不做什么>

Constraints:
- Follow existing code style and directory boundaries.
- Preserve backward compatibility for old clients.

Done When:
- [ ] 行为满足用户故事。
- [ ] 错误处理与空态处理完整。
- [ ] 验证记录完整可复现。
```

## 4) 重构模板
```md
Goal:
- Refactor <模块> to improve <可读性/性能/可维护性>

Context:
- Current pain points:
1. <痛点 1>
2. <痛点 2>
- Candidate files: <候选文件>

Constraints:
- No behavior change.
- No public interface change.
- Keep patch size reviewable.

Done When:
- [ ] 对外行为不变。
- [ ] 结构更清晰、复杂度下降。
- [ ] 相关检查通过。
```
