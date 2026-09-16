# 2026-09-10 修复启动脚本 apt 源导致 ripgrep 缺失（日志搜索保护阈值报错根因）

## 问题现象

- 工单 INC00001941655 日志搜索报错：`日志搜索扫描量超过当前保护阈值，请缩小文件范围或调整日志拉取存储配置`（接口 `/ticket/logs/search`）。
- 生产实测容器内没有 `rg`（ripgrep），但 `start.sh` 里明明有 `apt-get install ... ripgrep` 安装动作。

## 根因

1. **bullseye EOL 触发镜像站清理**：基础镜像 `python:3.11-slim-bullseye` 于 2026-08-31 结束 LTS。USTC 镜像站对 `bullseye-security` 池的 .deb 文件渐进清理（索引仍在、下载 404）。2026-09-05 清到 supervisor 依赖 `python3-pkg-resources`（已有 changelog），2026-09-10 实测清到 `libfreetype6`（`libcairo2` 的依赖，security 池 u2 版本 404）。
2. **apt 事务原子性殃及 ripgrep**：`apt-get install libcairo2 ripgrep` 中 `libcairo2` 依赖的 `libfreetype6` 候选版本来自 security 池且下载 404，整个事务失败——ripgrep 自身的 .deb 虽完好（main 池实测 200）但根本轮不到安装。且该环境不能重建镜像，系统依赖每次启动都要现场重装，故 rg 持续缺失。
3. **`set -e` 豁免坑让失败静默**：`start.sh` 把 `apt-get install` 放在 `&& rm -rf ...` 长链的非末位，bash 规则下 `set -e` 不对非最后一个命令的失败触发退出，apt 失败后脚本继续执行，应用带着"没有 rg"的状态正常启动。
4. **最终表现**：`ticket_log_service.py` 中 `shutil.which("rg")` 落空 → 日志搜索走 Python 降级路径 → 该工单日志压缩包 31.58MB（61 个文件）解压后超过 Python 降级搜索保护阈值 `maxPythonSearchBytes`（生产配置 256MB）→ 报保护阈值错误。

## 变更内容（`server/start.sh`）

1. **apt 源切换到阿里云 debian-archive 冻结归档**：
   - `deb.debian.org/debian` → `mirrors.aliyun.com/debian-archive/debian`。归档是 EOL 后的永久冻结快照，承诺不清理；Release 无 `Valid-Until` 不会过期；国内网络可达（官方 archive.debian.org 直连 200 但境外，不适合当前网络环境）。
   - 实测归档 main 池 ripgrep / libcairo2 / libfreetype6 全部 200 可下载，`bullseye` 与 `bullseye-updates` 两条 InRelease 均有效。
2. **删除 security 源**（而不是改指向）：归档源没有 `bullseye-security`，指向 404 会让 `apt-get update` 整体失败。同时兼容传统 `sources.list` 与 deb822（`sources.list.d/debian.sources`）两种源格式。
3. **拆掉 `&&` 长链**：`rm -rf /var/lib/apt/lists/*` 单独成行，今后 apt 失败会被 `set -e` 正确捕获、不再静默跳过。
4. **安装结果显式自检**：安装后检查 `rg` 与 `libcairo` 的存在性，缺失时输出 ERROR 日志（`ripgrep 安装失败，日志搜索将降级为 Python 慢速模式...`），杜绝再次静默降级难排查。

## 遗留与风险

- 归档源没有安全更新：bullseye EOL 后本就无安全更新，且仅装运行时库（libcairo2、ripgrep），supervisor 已走 uv 依赖管理，风险可接受。
- 阿里云归档为单点：归档语义下被清理的概率极低；万一失效可回退官方 archive.debian.org（境外）或推进基础镜像升级 bookworm。
- 若生产实际使用 deb822 格式源，本次兼容逻辑已在本地模拟验证（security 段整块删除、main 段改指归档），但未在生产容器实测。

## 验证

- `bash -n server/start.sh` 语法通过。
- 三种 sources.list 形态（传统格式、security 行旧写法变体、deb822）的 sed 替换逻辑本地模拟全部通过。
- 阿里云归档源的 InRelease 与目标 .deb 文件 HTTP 状态实测（2026-09-10）全部 200。
- 未执行：生产容器重启后的端到端验证（`which rg`、启动日志出现"ripgrep 安装成功"）。需在下次部署时确认。

## 关联

- 根因分析过程见 wiki：`wiki/concepts/server-startup-env.md`（修复记录 4）。
- 前置问题：`web/public/docs/changelog/2026-09-05-start-sh-supervisor-uv-install.md`（同一清理风暴的第一波，supervisor 404）。
