# 2026-07-16 工单日志下载完成后处理配置

## 结论

日志拉取下载完成后新增三项可配置后处理能力：

1. 下载完成后自动解压。
2. 自动解压后从日志文件提取版本号。
3. 自动解压后为日志文件生成行索引。

版本提取和索引生成都依赖自动解压；关闭自动解压时，这两个开关在前端禁用，后端也不会执行。

## 配置位置

前端位置：工单同步自动化 -> 公共配置 -> 日志拉取后处理。

底层参数仍保存到 `ticket.logPull.storage`，新增字段：

| 字段 | 默认值 | 作用 |
|---|---:|---|
| `postDownloadExtractEnabled` | `false` | 日志压缩包下载完成后复制到日志查看目录并自动解压 |
| `postDownloadVersionExtractEnabled` | `false` | 自动解压后从日志文件中提取版本号并写入 `ticket.extra_data.version_key` |
| `postDownloadIndexEnabled` | `false` | 自动解压后为日志文件生成 `.lineidx` 行索引 |

公共配置页通过 `/ticket/log-pull/post-process-config` 读取和保存这三个开关，权限沿用 `ticket:sync:config:list/edit`；接口只覆盖后处理字段，不修改本地目录、FTP、轮询和资源保护参数。

## 后端行为

1. 日志拉取主流程下载并归档压缩包后，调用下载完成后处理服务。
2. 未开启 `postDownloadExtractEnabled` 时不执行解压、版本提取和索引。
3. 开启自动解压后，压缩包会复制到 `server/data/logs/ticket_{ticketId}/record_{recordId}/source`，并递归解压到 `extract`。
4. 开启版本提取后，系统按行流式扫描已解压日志文件，命中版本号后立即停止。
5. 开启索引后，系统为已解压日志文件生成 `.lineidx`，后续查看上下文可直接复用。
6. 后处理失败不会把已经成功的日志拉取改成失败，只记录链路步骤和服务日志。

## 注意

自动解压和索引会增加下载完成后的 CPU、磁盘和耗时；大日志包建议先只开启自动解压和版本提取，确认稳定后再按需开启索引生成。
