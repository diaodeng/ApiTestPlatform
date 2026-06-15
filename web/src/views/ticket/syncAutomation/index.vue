<template>
  <div class="app-container ticket-sync-automation-page" v-loading="loading">
    <section class="page-intro">
      <div class="page-intro__eyebrow">工单同步自动化</div>
      <h2 class="page-intro__title">这里配置外部同步入库后的自动化行为</h2>
      <p class="page-intro__desc">
        这里只管三方直推和内网定时拉取两条外部同步链路。手动新增、编辑后的自动翻译，以及创建后拉日志，走工单页本身的开关，不在这里配置。
      </p>
    </section>

    <el-card shadow="never" class="config-card">
      <template #header>
        <div class="card-header">
          <span>外部同步基础开关</span>
          <el-tag type="success" effect="plain">保存后立即生效</el-tag>
        </div>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="同步后自动执行" prop="autoRunOnSync">
              <el-switch v-model="form.autoRunOnSync" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="同步后自动翻译" prop="autoTranslateOnSync">
              <el-switch v-model="form.autoTranslateOnSync" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="默认拉取数量" prop="defaultPullLimit">
              <el-input-number v-model="form.defaultPullLimit" :min="1" :max="200" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="远端来源系统" prop="remoteSync.sourceSystem">
              <el-input v-model="form.remoteSync.sourceSystem" placeholder="例如 public / hrm / partner" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>统计枚举配置</span>
          <el-tag effect="plain">用于工单页与统计页的可视化配置</el-tag>
        </div>
      </template>

      <div class="stat-config-grid">
        <section class="stat-config-section">
          <div class="stat-config-section__head">
            <span>工单类型</span>
            <el-button link type="primary" icon="Plus" @click="addStatOption('issueTypes')">新增</el-button>
          </div>
          <el-table :data="form.statClassification.issueTypes" border size="small">
            <el-table-column label="编码" min-width="160">
              <template #default="scope">
                <el-input v-model="scope.row.value" placeholder="如 system_bug" />
              </template>
            </el-table-column>
            <el-table-column label="名称" min-width="180">
              <template #default="scope">
                <el-input v-model="scope.row.label" placeholder="如 系统Bug" />
              </template>
            </el-table-column>
            <el-table-column label="是否问题" width="140">
              <template #default="scope">
                <el-select v-model="scope.row.isProblem" placeholder="可选" clearable style="width: 100%">
                  <el-option label="真实问题" :value="true" />
                  <el-option label="非问题" :value="false" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="scope">
                <el-button link type="danger" icon="Delete" @click="removeStatOption('issueTypes', scope.$index)" />
              </template>
            </el-table-column>
          </el-table>
        </section>

        <section class="stat-config-section">
          <div class="stat-config-section__head">
            <span>根因分类</span>
            <el-button link type="primary" icon="Plus" @click="addStatOption('rootCauseTypes')">新增</el-button>
          </div>
          <el-table :data="form.statClassification.rootCauseTypes" border size="small">
            <el-table-column label="编码" min-width="160">
              <template #default="scope">
                <el-input v-model="scope.row.value" placeholder="如 code_defect" />
              </template>
            </el-table-column>
            <el-table-column label="名称" min-width="180">
              <template #default="scope">
                <el-input v-model="scope.row.label" placeholder="如 代码缺陷" />
              </template>
            </el-table-column>
            <el-table-column label="备注" min-width="180">
              <template #default="scope">
                <el-input v-model="scope.row.remark" placeholder="可选备注" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="scope">
                <el-button link type="danger" icon="Delete" @click="removeStatOption('rootCauseTypes', scope.$index)" />
              </template>
            </el-table-column>
          </el-table>
        </section>

        <section class="stat-config-section">
          <div class="stat-config-section__head">
            <span>解决方式</span>
            <el-button link type="primary" icon="Plus" @click="addStatOption('solutionTypes')">新增</el-button>
          </div>
          <el-table :data="form.statClassification.solutionTypes" border size="small">
            <el-table-column label="编码" min-width="160">
              <template #default="scope">
                <el-input v-model="scope.row.value" placeholder="如 code_fix" />
              </template>
            </el-table-column>
            <el-table-column label="名称" min-width="180">
              <template #default="scope">
                <el-input v-model="scope.row.label" placeholder="如 代码修复" />
              </template>
            </el-table-column>
            <el-table-column label="备注" min-width="180">
              <template #default="scope">
                <el-input v-model="scope.row.remark" placeholder="可选备注" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="scope">
                <el-button link type="danger" icon="Delete" @click="removeStatOption('solutionTypes', scope.$index)" />
              </template>
            </el-table-column>
          </el-table>
        </section>

        <section class="stat-config-section">
          <div class="stat-config-section__head">
            <span>关闭结果</span>
            <el-button link type="primary" icon="Plus" @click="addStatOption('resolutions')">新增</el-button>
          </div>
          <el-table :data="form.statClassification.resolutions" border size="small">
            <el-table-column label="编码" min-width="160">
              <template #default="scope">
                <el-input v-model="scope.row.value" placeholder="如 fixed" />
              </template>
            </el-table-column>
            <el-table-column label="名称" min-width="180">
              <template #default="scope">
                <el-input v-model="scope.row.label" placeholder="如 已修复" />
              </template>
            </el-table-column>
            <el-table-column label="是否问题" width="140">
              <template #default="scope">
                <el-select v-model="scope.row.isProblem" placeholder="可选" clearable style="width: 100%">
                  <el-option label="真实问题" :value="true" />
                  <el-option label="非问题" :value="false" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="scope">
                <el-button link type="danger" icon="Delete" @click="removeStatOption('resolutions', scope.$index)" />
              </template>
            </el-table-column>
          </el-table>
        </section>
      </div>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>外部推送多维表格邮箱补全</span>
          <el-tag type="warning" effect="plain">按 recordId 查询人员邮箱</el-tag>
        </div>
      </template>

      <el-form :model="form.externalSyncBitable" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="启用邮箱补全">
              <el-switch v-model="form.externalSyncBitable.enabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="多维 appToken">
              <el-input v-model="form.externalSyncBitable.appToken" placeholder="飞书多维表格应用 Token" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="多维 tableId">
              <el-input v-model="form.externalSyncBitable.tableId" placeholder="飞书多维表格表ID" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="多维 viewId">
              <el-input v-model="form.externalSyncBitable.viewId" placeholder="可选，不填默认表视图" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="飞书 appId">
              <el-input v-model="form.externalSyncBitable.appId" placeholder="覆盖统一凭证（可选）" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="飞书 appSecret">
              <el-input v-model="form.externalSyncBitable.appSecret" show-password placeholder="覆盖统一凭证（可选）" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <div class="mapping-desc">
              外部推送传入的 <code>recordId</code> 会作为飞书多维表格记录ID查询固定字段：
              <code>(IT) L1 PIC</code>、<code>1.5 当前负责人</code>、<code>当前负责人</code>。
            </div>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>远端同步链接</span>
          <el-tag type="warning" effect="plain">这里只配置拉取地址，不会自动启动任务</el-tag>
        </div>
      </template>

      <el-form ref="remoteFormRef" :model="form.remoteSync" :rules="remoteRules" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="启用远端同步" prop="enabled">
              <el-switch v-model="form.remoteSync.enabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="抓取超时(秒)" prop="timeoutSec">
              <el-input-number v-model="form.remoteSync.timeoutSec" :min="10" :max="300" :step="5" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="拉取地址" prop="pullUrl">
              <el-input v-model="form.remoteSync.pullUrl" placeholder="https://example.com/api/tickets/pending" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="回写地址" prop="ackUrl">
              <el-input v-model="form.remoteSync.ackUrl" placeholder="https://example.com/api/tickets/ack" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="消费者标识" prop="consumer">
              <el-input v-model="form.remoteSync.consumer" placeholder="例如 public-ticket-sync" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="每次拉取数量" prop="limit">
              <el-input-number v-model="form.remoteSync.limit" :min="1" :max="200" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="包含已关闭" prop="includeClosed">
              <el-switch v-model="form.remoteSync.includeClosed" inline-prompt active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="拉取后自动翻译" prop="autoTranslateOnPull">
              <el-switch v-model="form.remoteSync.autoTranslateOnPull" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>外部同步必填字段</span>
          <el-tag type="info" effect="plain">支持选择已有字段，也支持直接输入自定义字段名</el-tag>
        </div>
      </template>

      <el-form :model="form" label-width="150px">
        <el-form-item label="支持字段说明">
          <div class="mapping-desc">
            目前支持的字段：{{ externalSyncRequiredFieldOptions.map(item => item.value).join('、') }}。可直接下拉选择，也可手动输入新增字段名。
          </div>
        </el-form-item>
        <el-form-item label="必填字段列表">
          <el-select
            v-model="form.externalSyncRequiredFields"
            multiple
            filterable
            allow-create
            default-first-option
            collapse-tags
            placeholder="ticketNo, description, internalPriority, ticketVender, ticketModle, createTime, reporterName"
            style="width: 100%"
          >
            <el-option
              v-for="item in externalSyncRequiredFieldOptions"
              :key="`external-required-${item.value}`"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>工单汇总统计通知</span>
          <el-tag type="success" effect="plain">可定时统计状态/分类/优先级并推送</el-tag>
        </div>
      </template>

      <el-form :model="form.summaryReport" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="启用汇总通知">
              <el-switch v-model="form.summaryReport.enabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="发送模式">
              <el-select v-model="form.summaryReport.sendMode" style="width: 100%">
                <el-option v-for="item in notifySendModes" :key="`summary-mode-${item.value}`" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="统计数据源">
              <el-select v-model="form.summaryReport.dataSource" style="width: 100%">
                <el-option
                  v-for="item in summaryDataSourceOptions"
                  :key="`summary-source-${item.value}`"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="推送渠道">
              <el-select
                v-model="form.summaryReport.pushIds"
                multiple
                filterable
                collapse-tags
                :loading="pushOptionsLoading"
                placeholder="push_config/hybrid 模式使用"
                style="width: 100%"
              >
                <el-option
                  v-for="item in pushOptions"
                  :key="`summary-push-${item.pushId}`"
                  :label="item.label"
                  :value="item.pushId"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="应用群 chat_id">
              <el-select
                v-model="form.summaryReport.appChatIds"
                multiple
                filterable
                allow-create
                default-first-option
                placeholder="feishu_app/hybrid 模式使用"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col v-if="form.summaryReport.dataSource === 'local'" :xs="24" :md="12">
            <el-form-item label="本地时间字段">
              <el-select v-model="form.summaryReport.timeField" style="width: 100%">
                <el-option
                  v-for="item in summaryTimeFieldOptions"
                  :key="`summary-time-${item.value}`"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="12">
            <el-form-item label="多维表格 appToken">
              <el-input v-model="form.summaryReport.appToken" placeholder="飞书多维表格应用 Token" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="12">
            <el-form-item label="多维表格 tableId">
              <el-input v-model="form.summaryReport.tableId" placeholder="飞书多维表格表ID" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="12">
            <el-form-item label="视图 viewId">
              <el-input v-model="form.summaryReport.viewId" placeholder="可选，不填默认表视图" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="12">
            <el-form-item label="多维时间字段">
              <el-input v-model="form.summaryReport.bitableTimeField" placeholder="可选，不填回退记录创建时间" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="8">
            <el-form-item label="状态字段">
              <el-input v-model="form.summaryReport.statusField" placeholder="默认：状态" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="8">
            <el-form-item label="分类字段">
              <el-input v-model="form.summaryReport.categoryField" placeholder="默认：分类" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="8">
            <el-form-item label="优先级字段">
              <el-input v-model="form.summaryReport.priorityField" placeholder="默认：优先级" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="12">
            <el-form-item label="分页大小">
              <el-input-number v-model="form.summaryReport.pageSize" :min="1" :max="500" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.summaryReport.dataSource === 'bitable'" :span="24">
            <el-form-item label="过滤公式">
              <el-input
                v-model="form.summaryReport.filterFormula"
                type="textarea"
                :rows="3"
                placeholder='可选，飞书 filter 公式，例如 CurrentValue.[状态] != "已关闭"'
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="窗口分钟数">
              <el-input-number v-model="form.summaryReport.windowMinutes" :min="1" :max="10080" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="结束延迟(分钟)">
              <el-input-number v-model="form.summaryReport.endDelayMinutes" :min="0" :max="1440" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="包含已关闭">
              <el-switch v-model="form.summaryReport.includeClosed" inline-prompt active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="飞书 appId">
              <el-input v-model="form.summaryReport.appId" placeholder="覆盖统一凭证（可选）" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="飞书 appSecret">
              <el-input v-model="form.summaryReport.appSecret" show-password placeholder="覆盖统一凭证（可选）" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="启用AI解读">
              <el-switch v-model="form.summaryReport.aiEnabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="AI Provider编码">
              <el-input v-model="form.summaryReport.aiProviderCode" placeholder="示例：openai_default" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="AI提示词编码">
              <el-input v-model="form.summaryReport.aiPromptCode" placeholder="示例：ticket_summary_report_default" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="固定开始时间">
              <el-input v-model="form.summaryReport.startTime" placeholder="可选，格式如 2026-06-10 09:00:00" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="固定结束时间">
              <el-input v-model="form.summaryReport.endTime" placeholder="可选，格式如 2026-06-10 18:00:00" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="汇总模板">
              <el-input
                v-model="form.summaryReport.messageTemplate"
                type="textarea"
                :rows="6"
                placeholder="可用变量：${data_source} ${start_time} ${end_time} ${time_field} ${total_count} ${status_summary} ${category_summary} ${priority_summary} ${ai_summary} ${now_time}"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>飞书统一凭证</span>
          <el-tag type="info" effect="plain">群推送/按人催办/汇总通知共用，子配置可覆盖</el-tag>
        </div>
      </template>
      <el-form :model="form.feishuAuth" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="飞书 appId">
              <el-input v-model="form.feishuAuth.appId" placeholder="开放平台应用 app_id" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="飞书 appSecret">
              <el-input v-model="form.feishuAuth.appSecret" show-password placeholder="开放平台应用 app_secret" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>工单群消息推送</span>
          <el-tag type="success" effect="plain">推送项来自推送配置管理</el-tag>
        </div>
      </template>

      <el-form :model="form.groupPush" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="启用群推送">
              <el-switch v-model="form.groupPush.enabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="发送模式">
              <el-select v-model="form.groupPush.sendMode" style="width: 100%">
                <el-option v-for="item in notifySendModes" :key="`group-mode-${item.value}`" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="推送渠道">
              <el-select
                v-model="form.groupPush.pushIds"
                multiple
                filterable
                collapse-tags
                :loading="pushOptionsLoading"
                placeholder="请选择推送配置"
                style="width: 100%"
              >
                <el-option
                  v-for="item in pushOptions"
                  :key="item.pushId"
                  :label="item.label"
                  :value="item.pushId"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="应用群 chat_id">
              <el-select
                v-model="form.groupPush.appChatIds"
                multiple
                filterable
                allow-create
                default-first-option
                placeholder="feishu_app/hybrid 模式必填"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="外部推送后发送">
              <el-switch v-model="form.groupPush.sendAfterExternalSync" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="远端拉取后发送">
              <el-switch v-model="form.groupPush.sendAfterRemotePull" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="自动推送状态条件">
              <el-select
                v-model="form.groupPush.autoPushStatuses"
                multiple
                filterable
                allow-create
                default-first-option
                collapse-tags
                placeholder="留空表示不按状态限制；默认保留原有三种状态"
                style="width: 100%"
              >
                <el-option
                  v-for="item in groupPushAutoStatusOptions"
                  :key="`group-auto-status-${item}`"
                  :label="item"
                  :value="item"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="自动推送起始时间">
              <el-date-picker
                v-model="form.groupPush.autoSendAfterTime"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                format="YYYY-MM-DD HH:mm:ss"
                placeholder="不填表示不限制提交时间"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="优先级路由">
              <div class="priority-route-list">
                <div v-for="(route, idx) in form.groupPush.priorityRoutes" :key="`route-${idx}`" class="priority-route-item">
                  <el-row :gutter="12">
                    <el-col :xs="24" :md="6">
                      <el-select v-model="route.priorities" multiple placeholder="优先级" style="width: 100%">
                        <el-option label="P1" value="P1" />
                        <el-option label="P2" value="P2" />
                        <el-option label="P3" value="P3" />
                        <el-option label="P4" value="P4" />
                      </el-select>
                    </el-col>
                    <el-col :xs="24" :md="9">
                      <el-select
                        v-model="route.pushIds"
                        multiple
                        filterable
                        collapse-tags
                        :loading="pushOptionsLoading"
                        placeholder="路由推送渠道（机器人）"
                        style="width: 100%"
                      >
                        <el-option
                          v-for="item in pushOptions"
                          :key="`route-push-${idx}-${item.pushId}`"
                          :label="item.label"
                          :value="item.pushId"
                        />
                      </el-select>
                    </el-col>
                    <el-col :xs="24" :md="9">
                      <el-select
                        v-model="route.chatIds"
                        multiple
                        filterable
                        allow-create
                        default-first-option
                        placeholder="路由群 chat_id（应用身份）"
                        style="width: 100%"
                      />
                    </el-col>
                  </el-row>
                </div>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="自动推送模板">
              <el-input
                v-model="form.groupPush.template"
                type="textarea"
                :rows="5"
                placeholder="可用变量：${ticket_no} ${ticket_title} ${project_name} ${module_name} ${ticket_status} ${assignee_name} ${ticket_url} ${sync_source_record_url} ${description} ${report_at} ${reporter_at} ${assignee_at} ${mention_at}"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="手动发送模板">
              <el-input
                v-model="form.groupPush.manualTemplate"
                type="textarea"
                :rows="4"
                placeholder="留空时复用自动推送模板"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>按人催办通知</span>
          <el-tag type="warning" effect="plain">按人和时间阈值聚合后通知</el-tag>
        </div>
      </template>

      <el-form :model="form.personReminder" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="启用按人催办">
              <el-switch v-model="form.personReminder.enabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="发送模式">
              <el-select v-model="form.personReminder.sendMode" style="width: 100%">
                <el-option v-for="item in notifySendModes" :key="`person-mode-${item.value}`" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="统计数据源">
              <el-select v-model="form.personReminder.dataSource" style="width: 100%">
                <el-option
                  v-for="item in personDataSourceOptions"
                  :key="`person-source-${item.value}`"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="催办推送渠道">
              <el-select
                v-model="form.personReminder.pushIds"
                multiple
                filterable
                collapse-tags
                :loading="pushOptionsLoading"
                placeholder="请选择推送配置"
                style="width: 100%"
              >
                <el-option
                  v-for="item in pushOptions"
                  :key="`person-${item.pushId}`"
                  :label="item.label"
                  :value="item.pushId"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="飞书 appId">
              <el-input v-model="form.personReminder.appId" placeholder="覆盖统一凭证（可选）" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="飞书 appSecret">
              <el-input v-model="form.personReminder.appSecret" show-password placeholder="覆盖统一凭证（可选）" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.personReminder.dataSource === 'bitable'" :xs="24" :md="12">
            <el-form-item label="多维表格 appToken">
              <el-input v-model="form.personReminder.appToken" placeholder="飞书多维表格应用 Token" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.personReminder.dataSource === 'bitable'" :xs="24" :md="12">
            <el-form-item label="多维表格 tableId">
              <el-input v-model="form.personReminder.tableId" placeholder="飞书多维表格表ID" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.personReminder.dataSource === 'bitable'" :xs="24" :md="12">
            <el-form-item label="视图 viewId">
              <el-input v-model="form.personReminder.viewId" placeholder="可选，不填默认表视图" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="阈值(分钟)">
              <el-input-number v-model="form.personReminder.thresholdMinutes" :min="1" :max="10080" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.personReminder.dataSource === 'bitable'" :xs="24" :md="12">
            <el-form-item label="人员字段名">
              <el-input v-model="form.personReminder.personField" placeholder="多维表格中的人员字段名" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.personReminder.dataSource === 'bitable'" :xs="24" :md="12">
            <el-form-item label="时间字段名">
              <el-input v-model="form.personReminder.timeField" placeholder="多维表格中的时间字段名" />
            </el-form-item>
          </el-col>
          <el-col v-else :xs="24" :md="12">
            <el-form-item label="本地时间字段">
              <el-select v-model="form.personReminder.timeField" style="width: 100%">
                <el-option
                  v-for="item in personLocalTimeFieldOptions"
                  :key="`person-local-time-${item.value}`"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="明细条数上限">
              <el-input-number v-model="form.personReminder.maxRowsPerPerson" :min="1" :max="200" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="明细行模板">
              <el-input
                v-model="form.personReminder.rowsMarkdownTemplate"
                type="textarea"
                :rows="5"
                placeholder="可用变量：${index} ${created_at} ${ticket_no} ${detail_url} ${detail_link}"
              />
            </el-form-item>
          </el-col>
          <el-col v-if="form.personReminder.dataSource === 'bitable'" :xs="24" :md="12">
            <el-form-item label="分页大小">
              <el-input-number v-model="form.personReminder.pageSize" :min="1" :max="500" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.personReminder.dataSource === 'bitable'" :span="24">
            <el-form-item label="过滤公式">
              <el-input
                v-model="form.personReminder.filterFormula"
                type="textarea"
                :rows="3"
                placeholder='可选，飞书 filter 公式，例如 CurrentValue.[状态] != "已关闭"'
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="催办消息模板">
              <el-input
                v-model="form.personReminder.messageTemplate"
                type="textarea"
                :rows="6"
                placeholder="可用变量：${person_name} ${overdue_count} ${threshold_minutes} ${rows_markdown} ${now_time} ${email}"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>手动触发入口</span>
          <el-tag effect="plain">输入工单号或用户信息后直接执行</el-tag>
        </div>
      </template>

      <el-row :gutter="16">
        <el-col :xs="24" :lg="12">
          <el-form :model="groupSendForm" label-width="110px">
            <el-form-item label="工单号">
              <el-input v-model="groupSendForm.ticketNo" placeholder="输入工单号后发送群消息" />
            </el-form-item>
            <el-form-item label="强制推送">
              <el-switch
                v-model="groupSendForm.forcePush"
                active-text="是（忽略已推送状态）"
                inactive-text="否（遵循已推送状态）"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="groupSendLoading" @click="handleSendGroupPushByTicket">
                发送工单群消息
              </el-button>
            </el-form-item>
          </el-form>
        </el-col>
        <el-col :xs="24" :lg="12">
          <el-form :model="personQueryForm" label-width="110px">
            <el-form-item label="用户ID">
              <el-input v-model="personQueryForm.userId" placeholder="可选，支持数字ID" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="personQueryForm.email" placeholder="可选，支持邮箱" />
            </el-form-item>
            <el-form-item>
              <el-button :loading="personPreviewLoading" @click="handlePreviewPersonReminder">统计该用户</el-button>
              <el-button type="primary" :loading="personRunLoading" @click="handleRunPersonReminder">
                发送该用户催办
              </el-button>
            </el-form-item>
            <el-divider content-position="left">汇总统计手动触发</el-divider>
            <el-form-item label="开始时间">
              <el-input v-model="summaryRunForm.startTime" placeholder="可选，格式如 2026-06-10 09:00:00" />
            </el-form-item>
            <el-form-item label="结束时间">
              <el-input v-model="summaryRunForm.endTime" placeholder="可选，格式如 2026-06-10 18:00:00" />
            </el-form-item>
            <el-form-item>
              <el-button type="success" :loading="summaryRunLoading" @click="handleRunSummaryReport">
                发送汇总统计
              </el-button>
            </el-form-item>
          </el-form>
        </el-col>
      </el-row>

      <el-alert
        v-if="personPreviewResult"
        type="info"
        show-icon
        :closable="false"
        :title="`统计结果：命中 ${personPreviewResult.personCount || 0} 人，超时记录 ${personPreviewResult.overdueRecordCount || 0} 条`"
      />
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>自动分类管理</span>
          <el-tag effect="plain">支持未归类统计与批量重归类</el-tag>
        </div>
      </template>
      <el-form :model="autoCategoryForm" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="归类策略">
              <el-select v-model="autoCategoryForm.strategy" style="width: 100%">
                <el-option label="AI归类" value="ai" />
                <el-option label="正则归类" value="regex" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="autoCategoryForm.strategy === 'ai'" :xs="24" :md="12">
            <el-form-item label="AI提示词编码">
              <el-input v-model="autoCategoryForm.aiPromptCode" placeholder="可选，留空走系统默认提示词" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="仅未归类">
              <el-switch v-model="autoCategoryForm.onlyUncategorized" inline-prompt active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="全量扫描">
              <el-switch v-model="autoCategoryForm.allTickets" inline-prompt active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="强制覆盖已有分类">
              <el-switch v-model="autoCategoryForm.forceReclassify" inline-prompt active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
          <el-col v-if="!autoCategoryForm.allTickets" :xs="24" :md="12">
            <el-form-item label="分页页码">
              <el-input-number v-model="autoCategoryForm.pageNum" :min="1" :max="999999" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="!autoCategoryForm.allTickets" :xs="24" :md="12">
            <el-form-item label="分页大小">
              <el-input-number v-model="autoCategoryForm.pageSize" :min="1" :max="500" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="autoCategoryForm.strategy === 'regex'" :span="24">
            <el-form-item label="正则规则(JSON数组)">
              <el-input
                v-model="autoCategoryRegexText"
                type="textarea"
                :rows="6"
                placeholder='示例：[{"pattern":"支付|扣款","category":"支付问题","flags":"i"}]'
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <el-space wrap>
        <el-button :loading="autoCategoryStatsLoading" @click="handleLoadAutoCategoryStats">一键统计未归类工单</el-button>
        <el-button type="primary" :loading="autoCategoryRunLoading" @click="handleBatchReclassifyByConfig">按当前配置重归类</el-button>
        <el-button type="danger" plain :loading="autoCategoryRunLoading" @click="handleForceReclassifyAll">强制重归类全部</el-button>
      </el-space>
      <el-alert
        v-if="autoCategoryStats"
        class="mt16"
        type="info"
        show-icon
        :closable="false"
        :title="`工单总数 ${autoCategoryStats.totalCount || 0}，已归类 ${autoCategoryStats.categorizedCount || 0}，未归类 ${autoCategoryStats.uncategorizedCount || 0}（${autoCategoryStats.uncategorizedRatio || 0}%）`"
      />
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>识别规则</span>
          <el-tag effect="plain">按文本匹配，找不到则保留原值</el-tag>
        </div>
      </template>

      <el-form ref="patternFormRef" :model="form" label-width="150px">
        <el-form-item label="POS 正则规则">
          <el-input v-model="posPatternsText" type="textarea" :rows="6" placeholder='请输入 JSON 数组，例如 ["A", "B"]' />
        </el-form-item>
        <el-form-item label="SCO 正则规则">
          <el-input v-model="scoPatternsText" type="textarea" :rows="6" placeholder='请输入 JSON 数组，例如 ["A", "B"]' />
        </el-form-item>
        <el-form-item label="版本号正则规则">
          <el-input v-model="versionPatternsText" type="textarea" :rows="6" placeholder='请输入 JSON 数组，例如 ["A", "B"]' />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>映射配置</span>
          <el-tag effect="plain">给三方直推和内网拉取共用</el-tag>
        </div>
      </template>

      <div class="mapping-blocks">
        <div v-for="item in mappingSections" :key="item.key" class="mapping-section">
          <div class="mapping-title">{{ item.label }}</div>
          <div class="mapping-desc">{{ item.description }}</div>
          <el-input
            v-model="mappingTexts[item.key]"
            type="textarea"
            :rows="item.rows"
            placeholder='请输入 JSON 数组，例如 [{"source":"A","target":"B"}]'
          />
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>拉日志默认值</span>
          <el-tag type="info" effect="plain">同步后自动拉日志可复用</el-tag>
        </div>
      </template>

      <el-form ref="pullFormRef" :model="form.logPullDefaults" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="命令类型">
              <el-input-number v-model="form.logPullDefaults.commandDataType" :min="1" :max="10" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="文件上限(MB)">
              <el-input-number v-model="form.logPullDefaults.fileMaxSize" :min="1" :max="2000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="压缩包上限(MB)">
              <el-input-number v-model="form.logPullDefaults.zipMaxSize" :min="1" :max="2000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="存储方式">
              <el-select v-model="form.logPullDefaults.storageMode" placeholder="请选择" style="width: 100%">
                <el-option label="本地" value="local" />
                <el-option label="FTP" value="ftp" />
                <el-option label="对象存储" value="oss" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="前置分钟数">
              <el-input-number v-model="form.logPullDefaults.rangeBeforeMinutes" :min="0" :max="120" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="后置分钟数">
              <el-input-number v-model="form.logPullDefaults.rangeAfterMinutes" :min="0" :max="120" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="自动 AI 分析">
              <el-switch v-model="form.logPullDefaults.autoAiEnabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="Agent 编码">
              <el-input v-model="form.logPullDefaults.aiAgentCode" placeholder="留空则走默认 Agent" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="Provider 编码">
              <el-input v-model="form.logPullDefaults.aiProviderCode" placeholder="留空则走默认 Provider" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>提示词模板</span>
          <el-tag effect="plain">后续扩展 AI 识别时复用</el-tag>
        </div>
      </template>

      <el-form label-width="150px">
        <el-form-item label="分类提示词">
          <el-input
            v-model="form.promptTemplates.classificationHint"
            type="textarea"
            :rows="10"
            placeholder="用于项目、模块、状态、处理人等识别场景"
          />
        </el-form-item>
      </el-form>
    </el-card>

    <div class="action-bar">
      <el-button type="primary" :loading="saving" @click="handleSave" v-hasPermi="['ticket:sync:config:edit']">保存配置</el-button>
      <el-button @click="loadConfig">刷新数据</el-button>
    </div>
  </div>
</template>

<script setup name="TicketSyncAutomation">
import {
  batchReclassifyTicketSync,
  getTicketSyncAutoCategoryStats,
  getTicketSyncAutomationConfig,
  listTicketSyncNotifyPushOptions,
  previewTicketSyncPersonReminder,
  runTicketSyncPersonReminder,
  runTicketSyncSummaryReport,
  saveTicketSyncAutomationConfig,
  sendTicketSyncGroupPushByTicket
} from '@/api/ticket/ticket'

const { proxy } = getCurrentInstance()

const loading = ref(false)
const saving = ref(false)
const pushOptionsLoading = ref(false)
const pushOptions = ref([])
const groupSendLoading = ref(false)
const personPreviewLoading = ref(false)
const personRunLoading = ref(false)
const summaryRunLoading = ref(false)
const autoCategoryStatsLoading = ref(false)
const autoCategoryRunLoading = ref(false)
const personPreviewResult = ref(null)
const autoCategoryStats = ref(null)
const autoCategoryRegexText = ref('[]')
const groupSendForm = reactive({
  ticketNo: '',
  forcePush: false
})
const personQueryForm = reactive({
  userId: '',
  email: ''
})
const summaryRunForm = reactive({
  startTime: '',
  endTime: ''
})
const autoCategoryForm = reactive({
  strategy: 'ai',
  aiPromptCode: '',
  onlyUncategorized: true,
  allTickets: true,
  forceReclassify: true,
  pageNum: 1,
  pageSize: 100
})

const mappingTexts = reactive({
  projectMappings: '[]',
  moduleMappings: '[]',
  vendorMappings: '[]',
  storeMappings: '[]',
  statusMappings: '[]',
  assigneeMappings: '[]'
})
const posPatternsText = ref('[]')
const scoPatternsText = ref('[]')
const versionPatternsText = ref('[]')

const mappingSections = [
  { key: 'projectMappings', label: '项目映射', description: '示例：[{"keywords":["支付中心","pay-center"],"projectId":1001,"projectName":"支付平台"}]', rows: 6 },
  { key: 'moduleMappings', label: '模块映射', description: '示例：[{"keywords":["订单服务","order-service"],"moduleId":2001,"moduleName":"订单模块"}]', rows: 6 },
  { key: 'vendorMappings', label: '商家映射', description: '示例：[{"keywords":["京东","jd"],"vendorId":3001,"vendorName":"京东商户"}]', rows: 6 },
  { key: 'storeMappings', label: '门店映射', description: '示例：[{"keywords":["北京一店","bj-01"],"storeId":4001,"storeName":"北京一店"}]', rows: 6 },
  { key: 'statusMappings', label: '状态映射', description: '示例：[{"keywords":["处理中","processing"],"status":"PROCESSING"}]', rows: 6 },
  { key: 'assigneeMappings', label: '处理人映射', description: '示例：[{"keywords":["张三"],"userId":5001,"userName":"张三","email":"zhangsan@example.com"}]', rows: 6 }
]

const notifySendModes = [
  { label: '推送配置(机器人)', value: 'push_config' },
  { label: '飞书应用身份', value: 'feishu_app' },
  { label: '两种都发', value: 'hybrid' }
]

const groupPushAutoStatusOptions = [
  '2. 1.5线处理',
  '3. 待产研处理',
  '4. 产研处理中'
]

const externalSyncRequiredFieldOptions = [
  { label: 'ticketNo - 工单号', value: 'ticketNo' },
  { label: 'description - 问题描述', value: 'description' },
  { label: 'internalPriority - 内部优先级', value: 'internalPriority' },
  { label: 'ticketVender - 商家/供应商', value: 'ticketVender' },
  { label: 'ticketModle - 模块', value: 'ticketModle' },
  { label: 'createTime - 创建时间', value: 'createTime' },
  { label: 'reporterName - 1线处理人/报告人', value: 'reporterName' },
  { label: 'currentAssigneeName - 当前处理人', value: 'currentAssigneeName' },
  { label: 'internalOwner - 内部负责人', value: 'internalOwner' },
  { label: 'recordId - 飞书多维记录ID', value: 'recordId' }
]

const personDataSourceOptions = [
  { label: '飞书多维表格统计', value: 'bitable' },
  { label: '本地工单数据统计', value: 'local' }
]

const summaryDataSourceOptions = [
  { label: '本地工单数据统计', value: 'local' },
  { label: '飞书多维表格统计', value: 'bitable' }
]

const personLocalTimeFieldOptions = [
  { label: '更新时间(update_time)', value: 'update_time' },
  { label: '创建时间(create_time)', value: 'create_time' },
  { label: '开始时间(started_at)', value: 'started_at' },
  { label: '解决时间(resolved_at)', value: 'resolved_at' },
  { label: '关闭时间(closed_at)', value: 'closed_at' }
]

const summaryTimeFieldOptions = [
  { label: '创建时间', value: 'create_time' },
  { label: '更新时间', value: 'update_time' },
  { label: '关闭时间', value: 'closed_at' },
  { label: '解决时间', value: 'resolved_at' }
]

const rules = {
  defaultPullLimit: [{ required: true, message: '默认拉取数量不能为空', trigger: 'change' }]
}

/**
 * 创建远端同步字段的条件必填校验器。
 * 仅在启用远端同步时校验字段是否为空。
 * @param {string} message 校验失败提示文案。
 * @returns {(rule: any, value: any, callback: (error?: Error) => void) => void} Element Plus 表单校验回调。
 */
function createRemoteRequiredValidator(message) {
  return (_rule, value, callback) => {
    if (!form.remoteSync.enabled) {
      callback()
      return
    }
    if (String(value ?? '').trim()) {
      callback()
      return
    }
    callback(new Error(message))
  }
}

const remoteRules = {
  pullUrl: [{ validator: createRemoteRequiredValidator('拉取地址不能为空'), trigger: 'blur' }],
  ackUrl: [{ validator: createRemoteRequiredValidator('回写地址不能为空'), trigger: 'blur' }],
  consumer: [{ validator: createRemoteRequiredValidator('消费者标识不能为空'), trigger: 'blur' }],
  limit: [{ required: true, message: '每次拉取数量不能为空', trigger: 'change' }],
  timeoutSec: [{ required: true, message: '抓取超时不能为空', trigger: 'change' }]
}

const defaultStatClassification = {
  issueTypes: [
    { value: 'system_bug', label: '系统Bug', isProblem: true },
    { value: 'data_error', label: '数据错误', isProblem: true },
    { value: 'config_issue', label: '配置问题', isProblem: true },
    { value: 'performance_issue', label: '性能问题', isProblem: true },
    { value: 'support_consulting', label: '支持咨询', isProblem: false },
    { value: 'requirement_consulting', label: '需求咨询', isProblem: false },
    { value: 'user_operation', label: '用户操作问题', isProblem: false },
    { value: 'api_exception', label: '接口异常', isProblem: true }
  ],
  rootCauseTypes: [
    { value: 'code_defect', label: '代码缺陷' },
    { value: 'config_error', label: '配置错误' },
    { value: 'data_exception', label: '数据异常' },
    { value: 'third_party', label: '第三方问题' },
    { value: 'network_issue', label: '网络问题' },
    { value: 'environment_issue', label: '环境问题' },
    { value: 'operation_mistake', label: '操作失误' },
    { value: 'requirement_design', label: '需求设计问题' },
    { value: 'unknown', label: '未知' }
  ],
  solutionTypes: [
    { value: 'code_fix', label: '代码修复' },
    { value: 'config_fix', label: '配置修复' },
    { value: 'data_fix', label: '数据修复' },
    { value: 'temporary_workaround', label: '临时处理' },
    { value: 'manual_process', label: '人工处理' },
    { value: 'no_action', label: '无需处理' }
  ],
  resolutions: [
    { value: 'fixed', label: '已修复', isProblem: true },
    { value: 'non_problem', label: '非问题', isProblem: false },
    { value: 'data_processed', label: '数据已处理', isProblem: true },
    { value: 'config_fixed', label: '配置已修复', isProblem: true },
    { value: 'user_canceled', label: '用户撤销', isProblem: false },
    { value: 'duplicated', label: '重复工单', isProblem: false },
    { value: 'cannot_reproduce', label: '无法复现', isProblem: null },
    { value: 'as_designed', label: '需求如此', isProblem: false },
    { value: 'transferred', label: '已转其他团队', isProblem: null }
  ]
}

function createDefaultForm() {
  return {
    autoRunOnSync: false,
    autoTranslateOnSync: true,
    defaultPullLimit: 50,
    feishuAuth: {
      appId: '',
      appSecret: ''
    },
    remoteSync: {
      enabled: false,
      pullUrl: '',
      ackUrl: '',
      consumer: '',
      sourceSystem: 'public',
      limit: 50,
      includeClosed: true,
      autoTranslateOnPull: true,
      timeoutSec: 30,
      headers: {
        cookie: '',
        authorization: '',
        origin: ''
      }
    },
    groupPush: {
      enabled: false,
      sendMode: 'push_config',
      pushIds: [],
      appChatIds: [],
      autoPushStatuses: ['2. 1.5线处理', '3. 待产研处理', '4. 产研处理中'],
      priorityRoutes: [
        { priorities: ['P1'], pushIds: [], chatIds: [] },
        { priorities: ['P2'], pushIds: [], chatIds: [] },
        { priorities: ['P3', 'P4'], pushIds: [], chatIds: [] }
      ],
      sendAfterExternalSync: false,
      sendAfterRemotePull: false,
      autoSendAfterTime: '',
      template: '',
      manualTemplate: ''
    },
    externalSyncBitable: {
      enabled: false,
      appId: '',
      appSecret: '',
      appToken: '',
      tableId: '',
      viewId: ''
    },
    personReminder: {
      enabled: false,
      sendMode: 'push_config',
      dataSource: 'bitable',
      pushIds: [],
      appId: '',
      appSecret: '',
      feishuAppId: '',
      feishuAppSecret: '',
      appToken: '',
      tableId: '',
      viewId: '',
      filterFormula: '',
      personField: '',
      timeField: '',
      thresholdMinutes: 30,
      messageTemplate: '',
      maxRowsPerPerson: 20,
      rowsMarkdownTemplate: '',
      pageSize: 500
    },
    summaryReport: {
      enabled: false,
      sendMode: 'push_config',
      dataSource: 'local',
      pushIds: [],
      appChatIds: [],
      appId: '',
      appSecret: '',
      timeField: 'create_time',
      appToken: '',
      tableId: '',
      viewId: '',
      filterFormula: '',
      statusField: '状态',
      categoryField: '分类',
      priorityField: '优先级',
      bitableTimeField: '',
      pageSize: 500,
      aiEnabled: false,
      aiProviderCode: '',
      aiPromptCode: '',
      windowMinutes: 60,
      endDelayMinutes: 0,
      startTime: '',
      endTime: '',
      includeClosed: true,
      messageTemplate: ''
    },
    projectMappings: [],
    moduleMappings: [],
    vendorMappings: [],
    storeMappings: [],
    statusMappings: [],
    assigneeMappings: [],
    posPatterns: [],
    scoPatterns: [],
    versionPatterns: [],
    logPullDefaults: {
      commandDataType: 1,
      fileMaxSize: 500,
      zipMaxSize: 500,
      storageMode: 'local',
      rangeBeforeMinutes: 10,
      rangeAfterMinutes: 10,
      autoAiEnabled: false,
      aiAgentCode: '',
      aiProviderCode: ''
    },
    promptTemplates: {
      classificationHint: ''
    },
    statClassification: normalizeStatClassificationConfig(),
    externalSyncRequiredFields: [
      'ticketNo',
      'description',
      'internalPriority',
      'ticketVender',
      'ticketModle',
      'createTime',
      'reporterName'
    ]
  }
}

const form = reactive(createDefaultForm())

function normalizeArray(value, fallback = []) {
  if (Array.isArray(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim()) {
    try {
      const parsed = JSON.parse(value)
      return Array.isArray(parsed) ? parsed : fallback
    } catch (error) {
      return fallback
    }
  }
  return fallback
}

function normalizeStatOptionRows(value, fallback = [], allowProblemFlag = false) {
  const sourceRows = Array.isArray(value) ? value : fallback
  const seenValues = new Set()
  const rows = []
  sourceRows.forEach(item => {
    const optionValue = String(item?.value || item?.code || item?.id || '').trim()
    const optionLabel = String(item?.label || item?.name || optionValue).trim()
    if (!optionValue || seenValues.has(optionValue)) {
      return
    }
    const row = {
      value: optionValue,
      label: optionLabel || optionValue
    }
    if (allowProblemFlag) {
      row.isProblem = typeof item?.isProblem === 'boolean' ? item.isProblem : null
    }
    const remark = String(item?.remark || '').trim()
    if (remark) {
      row.remark = remark
    }
    rows.push(row)
    seenValues.add(optionValue)
  })
  return rows.length ? rows : fallback.map(item => ({ ...item }))
}

function normalizeStatClassificationConfig(value = {}) {
  const source = value && typeof value === 'object' ? value : {}
  return {
    issueTypes: normalizeStatOptionRows(source.issueTypes, defaultStatClassification.issueTypes, true),
    rootCauseTypes: normalizeStatOptionRows(source.rootCauseTypes, defaultStatClassification.rootCauseTypes),
    solutionTypes: normalizeStatOptionRows(source.solutionTypes, defaultStatClassification.solutionTypes),
    resolutions: normalizeStatOptionRows(source.resolutions, defaultStatClassification.resolutions, true)
  }
}

function addStatOption(groupKey) {
  if (!Array.isArray(form.statClassification[groupKey])) {
    form.statClassification[groupKey] = []
  }
  form.statClassification[groupKey].push({
    value: '',
    label: '',
    ...(groupKey === 'issueTypes' || groupKey === 'resolutions' ? { isProblem: null } : {})
  })
}

function removeStatOption(groupKey, index) {
  if (!Array.isArray(form.statClassification[groupKey])) {
    return
  }
  form.statClassification[groupKey].splice(index, 1)
}

/**
 * 归一化日期时间字符串，统一为 `YYYY-MM-DD HH:mm:ss`，不做时区换算。
 * @param {any} value 原始值。
 * @returns {string} 归一化后的时间文本。
 */
function normalizeDateTimeText(value) {
  const text = String(value || '').trim()
  if (!text) {
    return ''
  }
  const normalized = text.replace('T', ' ')
  const fullMatch = normalized.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)
  if (fullMatch?.[0]) {
    return fullMatch[0]
  }
  const minuteMatch = normalized.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/)
  if (minuteMatch?.[0]) {
    return `${minuteMatch[0]}:00`
  }
  return text
}

function applyConfig(payload) {
  form.autoRunOnSync = Boolean(payload.autoRunOnSync)
  form.autoTranslateOnSync = payload.autoTranslateOnSync !== false
  form.defaultPullLimit = Number(payload.defaultPullLimit || 50)
  form.statClassification = normalizeStatClassificationConfig(payload.statClassification)
  const feishuAuth = payload.feishuAuth || {}
  form.feishuAuth = {
    appId: feishuAuth.appId || '',
    appSecret: feishuAuth.appSecret || ''
  }

  const remoteSync = payload.remoteSync || {}
  form.remoteSync = {
    enabled: Boolean(remoteSync.enabled),
    pullUrl: remoteSync.pullUrl || '',
    ackUrl: remoteSync.ackUrl || '',
    consumer: remoteSync.consumer || '',
    sourceSystem: remoteSync.sourceSystem || 'public',
    limit: Number(remoteSync.limit || 50),
    includeClosed: remoteSync.includeClosed !== false,
    autoTranslateOnPull: remoteSync.autoTranslateOnPull !== false,
    timeoutSec: Number(remoteSync.timeoutSec || 30),
    headers: {
      cookie: remoteSync.headers && remoteSync.headers.cookie ? remoteSync.headers.cookie : '',
      authorization: remoteSync.headers && remoteSync.headers.authorization ? remoteSync.headers.authorization : '',
      origin: remoteSync.headers && remoteSync.headers.origin ? remoteSync.headers.origin : ''
    }
  }

  const externalSyncBitable = payload.externalSyncBitable || {}
  form.externalSyncBitable = {
    enabled: Boolean(externalSyncBitable.enabled),
    appId: externalSyncBitable.appId || '',
    appSecret: externalSyncBitable.appSecret || '',
    appToken: externalSyncBitable.appToken || '',
    tableId: externalSyncBitable.tableId || '',
    viewId: externalSyncBitable.viewId || ''
  }

  const groupPush = payload.groupPush || {}
  form.groupPush = {
    enabled: Boolean(groupPush.enabled),
    sendMode: groupPush.sendMode || 'push_config',
    pushIds: Array.isArray(groupPush.pushIds) ? groupPush.pushIds.map(item => Number(item)).filter(item => Number.isFinite(item)) : [],
    appChatIds: Array.isArray(groupPush.appChatIds) ? groupPush.appChatIds.map(item => String(item).trim()).filter(Boolean) : [],
    autoPushStatuses: Array.isArray(groupPush.autoPushStatuses)
      ? groupPush.autoPushStatuses.map(item => String(item || '').trim()).filter(Boolean)
      : ['2. 1.5线处理', '3. 待产研处理', '4. 产研处理中'],
    priorityRoutes: Array.isArray(groupPush.priorityRoutes)
      ? groupPush.priorityRoutes.map(route => ({
          priorities: Array.isArray(route?.priorities) ? route.priorities.map(item => String(item).trim()).filter(Boolean) : [],
          pushIds: Array.isArray(route?.pushIds) ? route.pushIds.map(item => Number(item)).filter(item => Number.isFinite(item)) : [],
          chatIds: Array.isArray(route?.chatIds) ? route.chatIds.map(item => String(item).trim()).filter(Boolean) : []
        }))
      : [],
    sendAfterExternalSync: Boolean(groupPush.sendAfterExternalSync),
    sendAfterRemotePull: Boolean(groupPush.sendAfterRemotePull),
    autoSendAfterTime: normalizeDateTimeText(groupPush.autoSendAfterTime || groupPush.auto_send_after_time),
    template: groupPush.template || '',
    manualTemplate: groupPush.manualTemplate || ''
  }
  if (!form.groupPush.priorityRoutes.length) {
    form.groupPush.priorityRoutes = [
      { priorities: ['P1'], pushIds: [], chatIds: [] },
      { priorities: ['P2'], pushIds: [], chatIds: [] },
      { priorities: ['P3', 'P4'], pushIds: [], chatIds: [] }
    ]
  }

  const personReminder = payload.personReminder || {}
  form.personReminder = {
    enabled: Boolean(personReminder.enabled),
    sendMode: personReminder.sendMode || 'push_config',
    dataSource: ['bitable', 'local'].includes(String(personReminder.dataSource || '').trim().toLowerCase())
      ? String(personReminder.dataSource || '').trim().toLowerCase()
      : 'bitable',
    pushIds: Array.isArray(personReminder.pushIds) ? personReminder.pushIds.map(item => Number(item)).filter(item => Number.isFinite(item)) : [],
    appId: personReminder.appId || '',
    appSecret: personReminder.appSecret || '',
    feishuAppId: personReminder.feishuAppId || '',
    feishuAppSecret: personReminder.feishuAppSecret || '',
    appToken: personReminder.appToken || '',
    tableId: personReminder.tableId || '',
    viewId: personReminder.viewId || '',
    filterFormula: personReminder.filterFormula || '',
    personField: personReminder.personField || '',
    timeField: personReminder.timeField || '',
    thresholdMinutes: Number(personReminder.thresholdMinutes || 30),
    messageTemplate: personReminder.messageTemplate || '',
    rowsMarkdownTemplate: personReminder.rowsMarkdownTemplate || '',
    maxRowsPerPerson: Number(personReminder.maxRowsPerPerson || 20),
    pageSize: Number(personReminder.pageSize || 500)
  }
  const summaryReport = payload.summaryReport || {}
  form.summaryReport = {
    enabled: Boolean(summaryReport.enabled),
    sendMode: summaryReport.sendMode || 'push_config',
    dataSource: ['bitable', 'local'].includes(String(summaryReport.dataSource || '').trim().toLowerCase())
      ? String(summaryReport.dataSource || '').trim().toLowerCase()
      : 'local',
    pushIds: Array.isArray(summaryReport.pushIds) ? summaryReport.pushIds.map(item => Number(item)).filter(item => Number.isFinite(item)) : [],
    appChatIds: Array.isArray(summaryReport.appChatIds) ? summaryReport.appChatIds.map(item => String(item).trim()).filter(Boolean) : [],
    appId: summaryReport.appId || '',
    appSecret: summaryReport.appSecret || '',
    timeField: summaryReport.timeField || 'create_time',
    appToken: summaryReport.appToken || '',
    tableId: summaryReport.tableId || '',
    viewId: summaryReport.viewId || '',
    filterFormula: summaryReport.filterFormula || '',
    statusField: summaryReport.statusField || '状态',
    categoryField: summaryReport.categoryField || '分类',
    priorityField: summaryReport.priorityField || '优先级',
    bitableTimeField: summaryReport.bitableTimeField || '',
    pageSize: Number(summaryReport.pageSize || 500),
    aiEnabled: Boolean(summaryReport.aiEnabled),
    aiProviderCode: summaryReport.aiProviderCode || '',
    aiPromptCode: summaryReport.aiPromptCode || '',
    windowMinutes: Number(summaryReport.windowMinutes || 60),
    endDelayMinutes: Number(summaryReport.endDelayMinutes || 0),
    startTime: summaryReport.startTime || '',
    endTime: summaryReport.endTime || '',
    includeClosed: summaryReport.includeClosed !== false,
    messageTemplate: summaryReport.messageTemplate || ''
  }

  form.projectMappings = normalizeArray(payload.projectMappings)
  form.moduleMappings = normalizeArray(payload.moduleMappings)
  form.vendorMappings = normalizeArray(payload.vendorMappings)
  form.storeMappings = normalizeArray(payload.storeMappings)
  form.statusMappings = normalizeArray(payload.statusMappings)
  form.assigneeMappings = normalizeArray(payload.assigneeMappings)
  form.posPatterns = normalizeArray(payload.posPatterns)
  form.scoPatterns = normalizeArray(payload.scoPatterns)
  form.versionPatterns = normalizeArray(payload.versionPatterns)

  mappingSections.forEach(item => {
    mappingTexts[item.key] = JSON.stringify(form[item.key], null, 2)
  })
  posPatternsText.value = JSON.stringify(form.posPatterns, null, 2)
  scoPatternsText.value = JSON.stringify(form.scoPatterns, null, 2)
  versionPatternsText.value = JSON.stringify(form.versionPatterns, null, 2)

  const logPullDefaults = payload.logPullDefaults || {}
  form.logPullDefaults = {
    commandDataType: Number(logPullDefaults.commandDataType || 1),
    fileMaxSize: Number(logPullDefaults.fileMaxSize || 500),
    zipMaxSize: Number(logPullDefaults.zipMaxSize || 500),
    storageMode: logPullDefaults.storageMode || 'local',
    rangeBeforeMinutes: Number(logPullDefaults.rangeBeforeMinutes || 10),
    rangeAfterMinutes: Number(logPullDefaults.rangeAfterMinutes || 10),
    autoAiEnabled: Boolean(logPullDefaults.autoAiEnabled),
    aiAgentCode: logPullDefaults.aiAgentCode || '',
    aiProviderCode: logPullDefaults.aiProviderCode || ''
  }

  form.promptTemplates = {
    classificationHint: payload.promptTemplates?.classificationHint || ''
  }
  form.externalSyncRequiredFields = Array.isArray(payload.externalSyncRequiredFields)
    ? payload.externalSyncRequiredFields.map(item => String(item || '').trim()).filter(Boolean)
    : [
        'ticketNo',
        'description',
        'internalPriority',
        'ticketVender',
        'ticketModle',
        'createTime',
        'reporterName'
      ]
}

function parseJsonArray(text, fallback = []) {
  if (!String(text || '').trim()) {
    return fallback
  }
  try {
    const parsed = JSON.parse(text)
    return Array.isArray(parsed) ? parsed : fallback
  } catch (error) {
    throw new Error('请检查 JSON 数组格式是否正确')
  }
}

function loadConfig() {
  loading.value = true
  getTicketSyncAutomationConfig()
    .then(response => {
      applyConfig(response.data?.configValue || response.data || {})
    })
    .finally(() => {
      loading.value = false
    })
}

function loadPushOptions() {
  pushOptionsLoading.value = true
  listTicketSyncNotifyPushOptions()
    .then(response => {
      pushOptions.value = Array.isArray(response.data) ? response.data : []
    })
    .finally(() => {
      pushOptionsLoading.value = false
    })
}

function validateElForm(refName) {
  return new Promise(resolve => {
    const formRef = proxy.$refs[refName]
    if (!formRef || typeof formRef.validate !== 'function') {
      resolve(true)
      return
    }
    formRef.validate(valid => resolve(valid))
  })
}

watch(
  () => form.remoteSync.enabled,
  enabled => {
    if (enabled) {
      return
    }
    const remoteFormRef = proxy.$refs.remoteFormRef
    if (!remoteFormRef || typeof remoteFormRef.clearValidate !== 'function') {
      return
    }
    remoteFormRef.clearValidate(['pullUrl', 'ackUrl', 'consumer'])
  }
)

async function handleSave() {
  const [basicValid, remoteValid] = await Promise.all([
    validateElForm('formRef'),
    validateElForm('remoteFormRef')
  ])
  if (!basicValid || !remoteValid) {
    return
  }

  saving.value = true
  try {
    const payload = JSON.parse(JSON.stringify(form))
    mappingSections.forEach(item => {
      payload[item.key] = parseJsonArray(mappingTexts[item.key])
    })
    payload.posPatterns = parseJsonArray(posPatternsText.value)
    payload.scoPatterns = parseJsonArray(scoPatternsText.value)
    payload.versionPatterns = parseJsonArray(versionPatternsText.value)
    payload.feishuAuth = {
      appId: String(payload.feishuAuth?.appId || '').trim(),
      appSecret: String(payload.feishuAuth?.appSecret || '').trim()
    }
    payload.groupPush.appChatIds = Array.isArray(payload.groupPush?.appChatIds)
      ? payload.groupPush.appChatIds.map(item => String(item || '').trim()).filter(Boolean)
      : []
    payload.groupPush.autoPushStatuses = Array.isArray(payload.groupPush?.autoPushStatuses)
      ? Array.from(new Set(payload.groupPush.autoPushStatuses.map(item => String(item || '').trim()).filter(Boolean)))
      : []
    payload.groupPush.autoSendAfterTime = normalizeDateTimeText(payload.groupPush?.autoSendAfterTime)
    payload.groupPush.priorityRoutes = Array.isArray(payload.groupPush?.priorityRoutes)
      ? payload.groupPush.priorityRoutes
          .map(route => ({
            priorities: Array.isArray(route?.priorities) ? route.priorities.map(item => String(item || '').trim().toUpperCase()).filter(Boolean) : [],
            pushIds: Array.isArray(route?.pushIds) ? route.pushIds.map(item => Number(item)).filter(item => Number.isFinite(item)) : [],
            chatIds: Array.isArray(route?.chatIds) ? route.chatIds.map(item => String(item || '').trim()).filter(Boolean) : []
          }))
          .filter(route => route.priorities.length > 0)
      : []
    payload.externalSyncBitable = {
      enabled: Boolean(payload.externalSyncBitable?.enabled),
      appId: String(payload.externalSyncBitable?.appId || '').trim(),
      appSecret: String(payload.externalSyncBitable?.appSecret || '').trim(),
      appToken: String(payload.externalSyncBitable?.appToken || '').trim(),
      tableId: String(payload.externalSyncBitable?.tableId || '').trim(),
      viewId: String(payload.externalSyncBitable?.viewId || '').trim()
    }
    payload.personReminder.appId = String(payload.personReminder?.appId || '').trim()
    payload.personReminder.appSecret = String(payload.personReminder?.appSecret || '').trim()
    payload.personReminder.rowsMarkdownTemplate = String(payload.personReminder?.rowsMarkdownTemplate || '').trim()
    payload.personReminder.dataSource = ['bitable', 'local'].includes(String(payload.personReminder?.dataSource || '').trim().toLowerCase())
      ? String(payload.personReminder?.dataSource || '').trim().toLowerCase()
      : 'bitable'
    payload.personReminder.feishuAppId = payload.personReminder.appId
    payload.personReminder.feishuAppSecret = payload.personReminder.appSecret
    payload.summaryReport.appChatIds = Array.isArray(payload.summaryReport?.appChatIds)
      ? payload.summaryReport.appChatIds.map(item => String(item || '').trim()).filter(Boolean)
      : []
    payload.summaryReport.dataSource = ['bitable', 'local'].includes(String(payload.summaryReport?.dataSource || '').trim().toLowerCase())
      ? String(payload.summaryReport?.dataSource || '').trim().toLowerCase()
      : 'local'
    payload.summaryReport.appId = String(payload.summaryReport?.appId || '').trim()
    payload.summaryReport.appSecret = String(payload.summaryReport?.appSecret || '').trim()
    payload.summaryReport.appToken = String(payload.summaryReport?.appToken || '').trim()
    payload.summaryReport.tableId = String(payload.summaryReport?.tableId || '').trim()
    payload.summaryReport.viewId = String(payload.summaryReport?.viewId || '').trim()
    payload.summaryReport.filterFormula = String(payload.summaryReport?.filterFormula || '').trim()
    payload.summaryReport.statusField = String(payload.summaryReport?.statusField || '状态').trim() || '状态'
    payload.summaryReport.categoryField = String(payload.summaryReport?.categoryField || '分类').trim() || '分类'
    payload.summaryReport.priorityField = String(payload.summaryReport?.priorityField || '优先级').trim() || '优先级'
    payload.summaryReport.bitableTimeField = String(payload.summaryReport?.bitableTimeField || '').trim()
    payload.summaryReport.pageSize = Math.min(Math.max(Number(payload.summaryReport?.pageSize || 500), 1), 500)
    payload.summaryReport.aiEnabled = Boolean(payload.summaryReport?.aiEnabled)
    payload.summaryReport.aiProviderCode = String(payload.summaryReport?.aiProviderCode || '').trim()
    payload.summaryReport.aiPromptCode = String(payload.summaryReport?.aiPromptCode || '').trim()
    payload.externalSyncRequiredFields = Array.isArray(payload.externalSyncRequiredFields)
      ? Array.from(new Set(payload.externalSyncRequiredFields.map(item => String(item || '').trim()).filter(Boolean)))
      : []
    payload.statClassification = normalizeStatClassificationConfig(payload.statClassification)
    await saveTicketSyncAutomationConfig(payload)
    proxy.$modal.msgSuccess('保存成功')
    loadConfig()
  } catch (error) {
    proxy.$modal.msgError(error?.message || '保存失败，请检查配置内容')
  } finally {
    saving.value = false
  }
}

function normalizeOptionalInt(value) {
  if (value === null || value === undefined || value === '') {
    return null
  }
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return null
  }
  return Math.trunc(parsed)
}

function normalizeOptionalEmail(value) {
  const text = String(value || '').trim()
  return text || null
}

function validatePersonQuery() {
  const hasUserId = normalizeOptionalInt(personQueryForm.userId)
  const hasEmail = normalizeOptionalEmail(personQueryForm.email)
  if (!hasUserId && !hasEmail) {
    proxy.$modal.msgWarning('请输入用户ID或邮箱')
    return null
  }
  return {
    userId: hasUserId,
    email: hasEmail
  }
}

function handlePreviewPersonReminder() {
  const payload = validatePersonQuery()
  if (!payload) {
    return
  }
  personPreviewLoading.value = true
  previewTicketSyncPersonReminder(payload)
    .then(response => {
      personPreviewResult.value = response.data || null
      if (response.data?.skipped) {
        proxy.$modal.msgWarning(response.data?.skipReason || '统计已跳过')
      } else {
        proxy.$modal.msgSuccess('统计完成')
      }
    })
    .catch(error => {
      personPreviewResult.value = null
      proxy.$modal.msgError(error?.message || '统计失败')
    })
    .finally(() => {
      personPreviewLoading.value = false
    })
}

function handleRunPersonReminder() {
  personRunLoading.value = true
  const payload = {
    userId: normalizeOptionalInt(personQueryForm.userId),
    email: normalizeOptionalEmail(personQueryForm.email)
  }
  runTicketSyncPersonReminder(payload)
    .then(response => {
      if (response.data?.skipped) {
        proxy.$modal.msgWarning(response.data?.skipReason || '催办已跳过')
      } else {
        proxy.$modal.msgSuccess(`催办执行完成，已发送 ${response.data?.sentPeople || 0} 人`)
      }
    })
    .catch(error => {
      proxy.$modal.msgError(error?.message || '催办执行失败')
    })
    .finally(() => {
      personRunLoading.value = false
    })
}

function handleRunSummaryReport() {
  const payload = {
    startTime: summaryRunForm.startTime || null,
    endTime: summaryRunForm.endTime || null
  }
  summaryRunLoading.value = true
  runTicketSyncSummaryReport(payload)
    .then(response => {
      const totalCount = response.data?.statSummary?.totalCount || 0
      proxy.$modal.msgSuccess(`汇总通知已执行，统计工单 ${totalCount} 条`)
    })
    .catch(error => {
      proxy.$modal.msgError(error?.message || '汇总通知执行失败')
    })
    .finally(() => {
      summaryRunLoading.value = false
    })
}

function parseAutoCategoryRegexRules() {
  if (autoCategoryForm.strategy !== 'regex') {
    return null
  }
  const text = String(autoCategoryRegexText.value || '').trim()
  if (!text) {
    return null
  }
  try {
    const parsed = JSON.parse(text)
    if (!Array.isArray(parsed)) {
      throw new Error('正则规则必须是 JSON 数组')
    }
    return parsed
  } catch (error) {
    throw new Error(error?.message || '正则规则JSON格式错误')
  }
}

function buildAutoCategoryPayload(overrides = {}) {
  const payload = {
    strategy: autoCategoryForm.strategy,
    aiPromptCode: String(autoCategoryForm.aiPromptCode || '').trim() || null,
    onlyUncategorized: Boolean(autoCategoryForm.onlyUncategorized),
    allTickets: Boolean(autoCategoryForm.allTickets),
    forceReclassify: Boolean(autoCategoryForm.forceReclassify),
    pageNum: Math.max(Number(autoCategoryForm.pageNum || 1), 1),
    pageSize: Math.min(Math.max(Number(autoCategoryForm.pageSize || 100), 1), 500),
    regexRules: parseAutoCategoryRegexRules()
  }
  return { ...payload, ...overrides }
}

function executeBatchReclassify(payload, successPrefix = '重归类执行完成') {
  autoCategoryRunLoading.value = true
  batchReclassifyTicketSync(payload)
    .then(response => {
      const data = response.data || {}
      const successCount = Number(data.successCount || 0)
      const skippedCount = Number(data.skippedCount || 0)
      const failedCount = Number(data.failedCount || 0)
      proxy.$modal.msgSuccess(`${successPrefix}：成功 ${successCount}，跳过 ${skippedCount}，失败 ${failedCount}`)
      handleLoadAutoCategoryStats()
    })
    .catch(error => {
      proxy.$modal.msgError(error?.message || '批量重归类失败')
    })
    .finally(() => {
      autoCategoryRunLoading.value = false
    })
}

function handleLoadAutoCategoryStats() {
  autoCategoryStatsLoading.value = true
  getTicketSyncAutoCategoryStats()
    .then(response => {
      autoCategoryStats.value = response.data || null
      proxy.$modal.msgSuccess('未归类统计完成')
    })
    .catch(error => {
      autoCategoryStats.value = null
      proxy.$modal.msgError(error?.message || '未归类统计失败')
    })
    .finally(() => {
      autoCategoryStatsLoading.value = false
    })
}

function handleBatchReclassifyByConfig() {
  try {
    const payload = buildAutoCategoryPayload()
    executeBatchReclassify(payload)
  } catch (error) {
    proxy.$modal.msgError(error?.message || '批量重归类参数错误')
  }
}

function handleForceReclassifyAll() {
  try {
    const payload = buildAutoCategoryPayload({
      allTickets: true,
      onlyUncategorized: false,
      forceReclassify: true
    })
    executeBatchReclassify(payload, '强制全量重归类完成')
  } catch (error) {
    proxy.$modal.msgError(error?.message || '强制全量重归类参数错误')
  }
}

function handleSendGroupPushByTicket() {
  const ticketNo = String(groupSendForm.ticketNo || '').trim()
  if (!ticketNo) {
    proxy.$modal.msgWarning('请输入工单号')
    return
  }
  groupSendLoading.value = true
  sendTicketSyncGroupPushByTicket({
    ticketNo,
    forcePush: Boolean(groupSendForm.forcePush)
  })
    .then(response => {
      if (response.data?.skipped) {
        proxy.$modal.msgWarning(response.data?.skipReason || '发送已跳过')
        return
      }
      const successCount = response.data?.pushSuccessCount || 0
      const stateUpdated = response.data?.groupPushSentOnceUpdated ? '，已更新去重状态' : ''
      proxy.$modal.msgSuccess(`发送完成，成功渠道数：${successCount}${stateUpdated}`)
    })
    .catch(error => {
      proxy.$modal.msgError(error?.message || '发送失败')
    })
    .finally(() => {
      groupSendLoading.value = false
    })
}

onMounted(() => {
  loadConfig()
  loadPushOptions()
  handleLoadAutoCategoryStats()
})
</script>

<style scoped>
.ticket-sync-automation-page {
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.96), rgba(255, 255, 255, 1));
  padding-bottom: 96px;
  display: block;
  width: 100%;
  align-self: stretch;
  box-sizing: border-box;
}

.ticket-sync-automation-page :deep(.el-form),
.ticket-sync-automation-page :deep(.el-row),
.ticket-sync-automation-page :deep(.el-col),
.ticket-sync-automation-page :deep(.el-card),
.ticket-sync-automation-page :deep(.el-card__body) {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.ticket-sync-automation-page :deep(.el-form-item) {
  width: 100%;
  margin-bottom: 18px;
}

.ticket-sync-automation-page :deep(.el-form-item__content) {
  min-width: 0;
  width: 100%;
}

.ticket-sync-automation-page :deep(.el-input),
.ticket-sync-automation-page :deep(.el-select),
.ticket-sync-automation-page :deep(.el-input-number),
.ticket-sync-automation-page :deep(.el-date-editor),
.ticket-sync-automation-page :deep(.el-textarea) {
  width: 100%;
}

.page-intro {
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(241, 245, 249, 0.92));
  padding: 18px 20px;
  margin-bottom: 16px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
}

.page-intro__eyebrow {
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--el-color-primary);
  margin-bottom: 8px;
  font-weight: 700;
}

.page-intro__title {
  margin: 0;
  font-size: 22px;
  line-height: 1.35;
  color: var(--el-text-color-primary);
}

.page-intro__desc {
  margin: 10px 0 0;
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-secondary);
  max-width: 100%;
}

.config-card {
  border-radius: 12px;
  width: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-weight: 600;
}

.mapping-blocks {
  display: grid;
  gap: 12px;
}

.stat-config-grid {
  display: grid;
  gap: 16px;
}

.stat-config-section {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}

.stat-config-section__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  font-weight: 600;
}

.priority-route-list {
  display: grid;
  gap: 10px;
  width: 100%;
}

.priority-route-item {
  border: 1px dashed var(--el-border-color);
  border-radius: 10px;
  padding: 10px;
  background: var(--el-fill-color-blank);
}

.mapping-section {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 14px;
  background: #fff;
}

.mapping-title {
  font-weight: 600;
  margin-bottom: 6px;
}

.mapping-desc {
  color: var(--el-text-color-secondary);
  margin-bottom: 10px;
  line-height: 1.5;
}

.action-bar {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 16px;
  position: sticky;
  bottom: 0;
  z-index: 20;
  padding: 14px 0 4px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.96));
  backdrop-filter: blur(8px);
}

.mt16 {
  margin-top: 16px;
}
</style>
