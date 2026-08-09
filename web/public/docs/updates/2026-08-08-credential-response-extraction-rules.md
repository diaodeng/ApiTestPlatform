# 2026-08-08 凭证响应提取规则调整

- 刷新响应中的 `Set-Cookie` 不再在未配置提取规则时自动写入凭证，避免刷新成功但实际业务使用的 Header 或 Token 未更新。
- 新增明确的响应提取目标：
  - `header.cookie`：覆盖整个 Cookie Header。
  - `header.cookie.名称`：更新 Cookie Header 中指定名称的 Cookie；缺失时追加。
  - `cookies`：用响应 Cookie 对象覆盖结构化 Cookie 对象；响应未返回标准 `Set-Cookie` 时不执行空覆盖。
  - `cookies.名称`：只更新结构化 Cookie 对象中的指定项。
- `header:set-cookie` 读取唯一一条原始 `Set-Cookie` 响应头，可用于接口返回裸值的情况；多条响应头需使用 `header:set-cookie[n]` 按 1-based 序号明确选择，避免错误拼接。
