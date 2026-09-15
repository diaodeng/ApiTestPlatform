# Jenkins 拉取超时：改造说明

仓库清理（`ops/repo-cleanup.sh`）完成后，Jenkins 的拉取日志里：

- 仓库从 **2.0 GB → ~10 MB**，普通 clone 也不再超时
- master 将**不再包含 dist/**（源码 + 配置，约 10 MB）
- 可部署的 dist 内容发布在 **`dist-release` 分支**（单提交，~15 MB，已排除 sourcemap）

## 一、立即止血（清理前就能做）：浅克隆

在 Jenkins 任务（`TKE.cpos-test-tools-qtrfront-rta-test-volc`）加浅克隆配置，
把拉取量从 1.9 GB 降到 ~20 MB，5 分钟配置完当天即可恢复部署。

**自由风格任务**：Source Code Management → Git → Additional Behaviours：

| 行为 | 配置 |
|---|---|
| Advanced clone behaviours | Shallow clone depth = `1`，noTags ✅，timeout = `20` |
| （可选）Ref Spec | `+refs/heads/master:refs/remotes/origin/master`（只拉 master，不拉 4 个分支） |

**Pipeline 任务**：

```groovy
checkout([
  $class           : 'GitSCM',
  branches         : [[name: 'origin/master']],
  extensions       : [
    [$class: 'CloneOption', depth: 1, shallow: true, noTags: true, timeout: 20],
    [$class: 'CheckoutOption', timeout: 20]
  ],
  userRemoteConfigs: [[
    url           : 'http://gitlab.rta-os.com/jie.xiong/qtr-webui.git',
    credentialsId : '<现有凭据ID>'
  ]]
])
```

## 二、清理完成后按新流程二选一

### 方式 A：继续从源码构建（推荐，零改造成本）

**仓库当前 Dockerfile 本来就是多阶段构建**——Stage 1 自己执行
`npm run build:prod` 生成 dist，**根本不消费 git 里的 dist**。所以
Jenkins 任务大概率什么都不用改：拉 master → Docker 构建 → 容器内出产物。

需要同步改的一处：`vite.config.js:18` 的 `sourcemap: true` 改为按环境开关
（Dockerfile 已设 `GENERATE_SOURCEMAP=false` 但 vite 不读它，见下）。
关掉 sourcemap 后构建产物从 ~41MB 降到 ~15MB，镜像更小、构建更快：

```js
// vite.config.js
sourcemap: process.env.GENERATE_SOURCEMAP === 'true'
```

### 方式 B：直接部署 dist-release 分支（跳过源码构建）

若某些任务只是要"拿到最新产物直接部署"，改成拉 `dist-release`：

```groovy
checkout([
  $class           : 'GitSCM',
  branches         : [[name: 'origin/dist-release']],
  extensions       : [[$class: 'CloneOption', depth: 1, shallow: true, noTags: true, timeout: 20]],
  userRemoteConfigs: [[url: '...', credentialsId: '...']]
])
```

工作区根目录即 dist 内容，可直接 COPY 到 nginx 镜像或 rsync 到服务器。

## 三、开发机的日常发布动作

日常入口不变，仍然只跑 `sync-subrepos.ps1`（内部构建后自动调用
`ops/publish-dist.sh` 发布 dist-release，源码提交正常走 master，已不含 dist）。

手动发布时才需要：

```bash
npm run build:prod          # 生成 dist/
bash ops/publish-dist.sh    # 发布到 dist-release 分支（单提交强推）
git push origin master      # 源码提交正常走 master（已不再含 dist）
```
