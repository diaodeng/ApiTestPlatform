<template>
  <div class="app-container ticket-sync-automation-page" v-loading="loading">
    <section class="page-intro">
      <div class="page-intro__eyebrow">工单同步自动化</div>
      <h2 class="page-intro__title">按基础、拉取、推送、手动能力统一管理同步配置</h2>
      <p class="page-intro__desc">
        Provider 和提示词正文统一在系统管理的 AI Provider 与 AI
        提示词中维护，这里只选择编码并配置同步场景开关。
      </p>
    </section>

    <el-container>
      <el-tabs>
        <el-tab-pane label="公共配置">
          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>飞书统一凭证</span>
                <el-tag type="info" effect="plain">基础配置</el-tag>
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
                    <el-input
                      v-model="form.feishuAuth.appSecret"
                      show-password
                      placeholder="开放平台应用 app_secret"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>日志拉取后处理</span>
                <el-tag type="warning" effect="plain">下载完成后</el-tag>
              </div>
            </template>
            <el-form :model="form.logPullPostProcess" label-width="170px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="8">
                  <el-form-item label="下载完成后解压">
                    <el-switch
                      v-model="form.logPullPostProcess.postDownloadExtractEnabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="8">
                  <el-form-item label="下载完成后提取版本">
                    <el-switch
                      v-model="form.logPullPostProcess.postDownloadVersionExtractEnabled"
                      :disabled="!form.logPullPostProcess.postDownloadExtractEnabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="8">
                  <el-form-item label="下载完成后生成索引">
                    <el-switch
                      v-model="form.logPullPostProcess.postDownloadIndexEnabled"
                      :disabled="!form.logPullPostProcess.postDownloadExtractEnabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>多维表格公共配置</span>
                <el-tag type="info" effect="plain">公共覆盖基座</el-tag>
              </div>
            </template>
            <el-form :model="form.bitableCommon" label-width="150px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="默认 appToken">
                    <el-input
                      v-model="form.bitableCommon.appToken"
                      placeholder="供汇总、催办、邮箱补全、主动拉取默认继承"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="默认 tableId">
                    <el-input
                      v-model="form.bitableCommon.tableId"
                      placeholder="默认多维表格 tableId"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="默认 viewId">
                    <el-input v-model="form.bitableCommon.viewId" placeholder="可选，默认表视图" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="默认分页大小">
                    <el-input-number
                      v-model="form.bitableCommon.pageSize"
                      :min="1"
                      :max="500"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="默认过滤条件JSON">
                    <el-input
                      v-model="form.bitableCommon.filterFormula"
                      type="textarea"
                      :rows="3"
                      placeholder='可选；各模块未单独配置时继承，例如 {"conjunction":"and","conditions":[{"field_name":"状态","operator":"contains","value":["处理中"]}]}'
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <div class="mapping-desc">
                    工单汇总统计、按人催办、群消息补全、外部推送邮箱补全、主动拉取默认继承这里的多维配置；
                    各自模块填了同名字段时，以模块自身配置为准。
                  </div>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>工单汇总统计通知</span>
                <el-tag type="success" effect="plain">推送配置</el-tag>
              </div>
            </template>

            <el-form :model="form.summaryReport" label-width="150px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="启用汇总通知">
                    <el-switch
                      v-model="form.summaryReport.enabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="发送模式">
                    <el-select v-model="form.summaryReport.sendMode" style="width: 100%">
                      <el-option
                        v-for="item in notifySendModes"
                        :key="`summary-mode-${item.value}`"
                        :label="item.label"
                        :value="item.value"
                      />
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
                    <el-input
                      v-model="form.summaryReport.appToken"
                      placeholder="飞书多维表格应用 Token"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="12">
                  <el-form-item label="多维表格 tableId">
                    <el-input v-model="form.summaryReport.tableId" placeholder="飞书多维表格表ID" />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="12">
                  <el-form-item label="视图 viewId">
                    <el-input
                      v-model="form.summaryReport.viewId"
                      placeholder="可选，不填默认表视图"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="12">
                  <el-form-item label="多维时间字段">
                    <el-input
                      v-model="form.summaryReport.bitableTimeField"
                      placeholder="可选，不填回退记录创建时间"
                    />
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
                    <el-input
                      v-model="form.summaryReport.priorityField"
                      placeholder="默认：优先级"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="12">
                  <el-form-item label="分页大小">
                    <el-input-number
                      v-model="form.summaryReport.pageSize"
                      :min="1"
                      :max="500"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.summaryReport.dataSource === 'bitable'" :span="24">
                  <el-form-item label="过滤条件JSON">
                    <el-input
                      v-model="form.summaryReport.filterFormula"
                      type="textarea"
                      :rows="3"
                      placeholder="可选，飞书 records/search filter JSON"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="窗口分钟数">
                    <el-input-number
                      v-model="form.summaryReport.windowMinutes"
                      :min="1"
                      :max="10080"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="结束延迟(分钟)">
                    <el-input-number
                      v-model="form.summaryReport.endDelayMinutes"
                      :min="0"
                      :max="1440"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="包含已关闭">
                    <el-switch
                      v-model="form.summaryReport.includeClosed"
                      inline-prompt
                      active-text="是"
                      inactive-text="否"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="飞书 appId">
                    <el-input
                      v-model="form.summaryReport.appId"
                      placeholder="覆盖统一凭证（可选）"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="飞书 appSecret">
                    <el-input
                      v-model="form.summaryReport.appSecret"
                      show-password
                      placeholder="覆盖统一凭证（可选）"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="启用AI解读">
                    <el-switch
                      v-model="form.summaryReport.aiEnabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="AI Provider编码">
                    <el-input
                      v-model="form.summaryReport.aiProviderCode"
                      placeholder="示例：openai_default"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="AI提示词编码">
                    <el-input
                      v-model="form.summaryReport.aiPromptCode"
                      placeholder="示例：ticket_summary_report_default"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="固定开始时间">
                    <el-input
                      v-model="form.summaryReport.startTime"
                      placeholder="可选，格式如 2026-06-10 09:00:00"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="固定结束时间">
                    <el-input
                      v-model="form.summaryReport.endTime"
                      placeholder="可选，格式如 2026-06-10 18:00:00"
                    />
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
                <span>按人催办通知</span>
                <el-tag type="warning" effect="plain">按人和时间阈值聚合后通知</el-tag>
              </div>
            </template>

            <el-form :model="form.personReminder" label-width="150px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="启用按人催办">
                    <el-switch
                      v-model="form.personReminder.enabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="发送模式">
                    <el-select v-model="form.personReminder.sendMode" style="width: 100%">
                      <el-option
                        v-for="item in notifySendModes"
                        :key="`person-mode-${item.value}`"
                        :label="item.label"
                        :value="item.value"
                      />
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
                    <el-input
                      v-model="form.personReminder.appId"
                      placeholder="覆盖统一凭证（可选）"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="飞书 appSecret">
                    <el-input
                      v-model="form.personReminder.appSecret"
                      show-password
                      placeholder="覆盖统一凭证（可选）"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.personReminder.dataSource === 'bitable'" :xs="24" :md="12">
                  <el-form-item label="多维表格 appToken">
                    <el-input
                      v-model="form.personReminder.appToken"
                      placeholder="飞书多维表格应用 Token"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.personReminder.dataSource === 'bitable'" :xs="24" :md="12">
                  <el-form-item label="多维表格 tableId">
                    <el-input
                      v-model="form.personReminder.tableId"
                      placeholder="飞书多维表格表ID"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.personReminder.dataSource === 'bitable'" :xs="24" :md="12">
                  <el-form-item label="视图 viewId">
                    <el-input
                      v-model="form.personReminder.viewId"
                      placeholder="可选，不填默认表视图"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="阈值(分钟)">
                    <el-input-number
                      v-model="form.personReminder.thresholdMinutes"
                      :min="1"
                      :max="10080"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.personReminder.dataSource === 'bitable'" :xs="24" :md="12">
                  <el-form-item label="人员字段名">
                    <el-input
                      v-model="form.personReminder.personField"
                      placeholder="多维表格中的人员字段名"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.personReminder.dataSource === 'bitable'" :xs="24" :md="12">
                  <el-form-item label="时间字段名">
                    <el-input
                      v-model="form.personReminder.timeField"
                      placeholder="多维表格中的时间字段名"
                    />
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
                    <el-input-number
                      v-model="form.personReminder.maxRowsPerPerson"
                      :min="1"
                      :max="200"
                      style="width: 100%"
                    />
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
                    <el-input-number
                      v-model="form.personReminder.pageSize"
                      :min="1"
                      :max="500"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.personReminder.dataSource === 'bitable'" :span="24">
                  <el-form-item label="过滤条件JSON">
                    <el-input
                      v-model="form.personReminder.filterFormula"
                      type="textarea"
                      :rows="3"
                      placeholder="可选，飞书 records/search filter JSON"
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
                <span>拉日志默认值</span>
                <el-tag type="info" effect="plain">拉取配置</el-tag>
              </div>
            </template>

            <el-form ref="pullFormRef" :model="form.logPullDefaults" label-width="150px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="命令类型">
                    <el-input-number
                      v-model="form.logPullDefaults.commandDataType"
                      :min="1"
                      :max="10"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="文件上限(MB)">
                    <el-input-number
                      v-model="form.logPullDefaults.fileMaxSize"
                      :min="1"
                      :max="2000"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="压缩包上限(MB)">
                    <el-input-number
                      v-model="form.logPullDefaults.zipMaxSize"
                      :min="1"
                      :max="2000"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="存储方式">
                    <el-select
                      v-model="form.logPullDefaults.storageMode"
                      placeholder="请选择"
                      style="width: 100%"
                    >
                      <el-option label="本地" value="local" />
                      <el-option label="FTP" value="ftp" />
                      <el-option label="对象存储" value="oss" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="前置分钟数">
                    <el-input-number
                      v-model="form.logPullDefaults.rangeBeforeMinutes"
                      :min="0"
                      :max="120"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="后置分钟数">
                    <el-input-number
                      v-model="form.logPullDefaults.rangeAfterMinutes"
                      :min="0"
                      :max="120"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="自动 AI 分析">
                    <el-switch
                      v-model="form.logPullDefaults.autoAiEnabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="Agent 编码">
                    <el-input
                      v-model="form.logPullDefaults.aiAgentCode"
                      placeholder="留空则走默认 Agent"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="Provider 编码">
                    <el-input
                      v-model="form.logPullDefaults.aiProviderCode"
                      placeholder="留空则走默认 Provider"
                    />
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
        </el-tab-pane>
        <el-tab-pane label=”同步”>
          <!-- 1. 工单同步 AI 提取（代码第一步） -->
          <el-card shadow=”never” class=”config-card mt16”>
            <template #header>
              <div class=”card-header”>
                <span>工单同步 AI 提取</span>
                <el-tag type=”info” effect=”plain”>按场景独立控制AI提取开关</el-tag>
              </div>
            </template>

            <el-form :model=”form.aiSyncExtract” label-width=”150px”>
              <el-row :gutter=”16”>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”外部推送提取”>
                    <el-switch
                      v-model=”form.aiSyncExtract.externalPushEnabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                    <div class=”mapping-desc” style=”margin-top: 4px; font-size: 12px;”>
                      外部系统推送工单时，启用AI提取下方勾选的字段
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”远端拉取提取”>
                    <el-switch
                      v-model=”form.aiSyncExtract.remotePullEnabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                    <div class=”mapping-desc” style=”margin-top: 4px; font-size: 12px;”>
                      从远端系统拉取工单时，启用AI提取下方勾选的字段
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”多维表格提取”>
                    <el-switch
                      v-model=”form.aiSyncExtract.bitablePullEnabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                    <div class=”mapping-desc” style=”margin-top: 4px; font-size: 12px;”>
                      从飞书多维表格拉取工单时，启用AI提取下方勾选的字段
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”手动创建提取”>
                    <el-switch
                      v-model=”form.aiSyncExtract.manualCreateEnabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                    <div class=”mapping-desc” style=”margin-top: 4px; font-size: 12px;”>
                      手动创建工单时，启用AI提取下方勾选的字段
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”Provider 编码”>
                    <el-select
                      v-model=”form.aiSyncExtract.providerCode”
                      placeholder=”请选择 Provider；留空则使用 AI 配置中心”
                      filterable
                      clearable
                      style=”width: 100%”
                    >
                      <el-option
                        v-for=”item in providerOptions”
                        :key=”item.providerCode”
                        :label=”formatProviderOptionLabel(item)”
                        :value=”item.providerCode”
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”提示词编码”>
                    <el-select
                      v-model=”form.aiSyncExtract.promptCode”
                      placeholder=”请选择提示词模板；留空使用默认模板”
                      filterable
                      clearable
                      style=”width: 100%”
                    >
                      <el-option
                        v-for=”item in promptOptions”
                        :key=”item.templateCode || item.value”
                        :label=”formatPromptOptionLabel(item)”
                        :value=”item.templateCode || item.value”
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>

              <el-divider content-position=”left”>提取字段配置</el-divider>
              <el-row :gutter=”16”>
                <el-col :span=”24”>
                  <el-form-item label=”AI提取字段”>
                    <el-checkbox-group v-model=”form.aiSyncExtract.extractFields”>
                      <el-checkbox label=”storeName”>门店名称</el-checkbox>
                      <el-checkbox label=”posNo”>POS编号</el-checkbox>
                      <el-checkbox label=”scoNo”>SCO编号</el-checkbox>
                      <el-checkbox label=”logDate”>日志日期</el-checkbox>
                      <el-checkbox label=”versionKey”>版本号</el-checkbox>
                    </el-checkbox-group>
                    <div class=”mapping-desc” style=”margin-top: 4px; font-size: 12px;”>
                      勾选需要从工单描述中AI提取的字段，未勾选的字段将不会被提取
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <!-- 2. 工单翻译（代码第二步） -->
          <el-card shadow=”never” class=”config-card mt16”>
            <template #header>
              <div class=”card-header”>
                <span>工单翻译</span>
                <el-tag type=”warning” effect=”plain”>按场景独立控制翻译开关</el-tag>
              </div>
            </template>

            <el-form :model=”form.translateConfig” label-width=”150px”>
              <el-row :gutter=”16”>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”启用新翻译配置”>
                    <el-switch
                      v-model=”form.translateConfig.enabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                    <div class=”mapping-desc” style=”margin-top: 4px; font-size: 12px;”>
                      开启后以下场景开关生效；关闭时兜底走旧逻辑（autoTranslateOnSync / autoTranslateOnPull）
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”外部推送翻译”>
                    <el-switch
                      v-model=”form.translateConfig.translateOnExternalSync”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”远端拉取翻译”>
                    <el-switch
                      v-model=”form.translateConfig.translateOnRemotePull”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”多维表格拉取翻译”>
                    <el-switch
                      v-model=”form.translateConfig.translateOnBitablePull”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”手动创建翻译”>
                    <el-switch
                      v-model=”form.translateConfig.translateOnManualCreate”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <!-- 3. AI 分类统计（代码第三步，已有，结构不变） -->
          <el-card shadow=”never” class=”config-card mt16”>
            <template #header>
              <div class=”card-header”>
                <span>AI 分类统计配置</span>
                <el-tag type=”warning” effect=”plain”>手动配置与场景开关</el-tag>
              </div>
            </template>

            <el-form :model=”form.aiClassification” label-width=”150px”>
              <el-row :gutter=”16”>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”启用AI分类”>
                    <el-switch
                      v-model=”form.aiClassification.enabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”外部同步执行”>
                    <el-switch
                      v-model=”form.aiClassification.runOnExternalSync”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”远端拉取执行”>
                    <el-switch
                      v-model=”form.aiClassification.runOnRemotePull”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”手动创建执行”>
                    <el-switch
                      v-model=”form.aiClassification.runOnManualCreate”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”多维表格拉取执行”>
                    <el-switch
                      v-model=”form.aiClassification.runOnBitablePull”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”状态变更执行”>
                    <el-switch
                      v-model=”form.aiClassification.runOnStatusChange”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”状态变更强制覆盖”>
                    <el-switch
                      v-model=”form.aiClassification.statusChangeForceReclassify”
                      inline-prompt
                      active-text=”是”
                      inactive-text=”否”
                    />
                  </el-form-item>
                </el-col>
                <el-col :span=”24”>
                  <el-form-item label=”状态触发条件”>
                    <el-select
                      v-model=”form.aiClassification.statusChangeTriggerStatuses”
                      placeholder=”选择变更到哪些状态后重新归类，可多选”
                      multiple
                      filterable
                      clearable
                      style=”width: 100%”
                    >
                      <el-option
                        v-for=”item in workflowStatusOptions”
                        :key=”item.value”
                        :label=”item.label”
                        :value=”item.value”
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”Provider 编码”>
                    <el-select
                      v-model=”form.aiClassification.providerCode”
                      placeholder=”请选择 Provider；留空则使用 AI 配置中心”
                      filterable
                      clearable
                      style=”width: 100%”
                    >
                      <el-option
                        v-for=”item in providerOptions”
                        :key=”item.providerCode”
                        :label=”formatProviderOptionLabel(item)”
                        :value=”item.providerCode”
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”提示词编码”>
                    <el-select
                      v-model=”form.aiClassification.promptCode”
                      placeholder=”请选择提示词模板；留空使用默认模板”
                      filterable
                      clearable
                      style=”width: 100%”
                    >
                      <el-option
                        v-for=”item in promptOptions”
                        :key=”item.templateCode || item.value”
                        :label=”formatPromptOptionLabel(item)”
                        :value=”item.templateCode || item.value”
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
            <el-alert
              v-if=”form.aiClassification.promptContent”
              class=”mt8”
              type=”warning”
              show-icon
              :closable=”false”
              title=”检测到历史内联提示词”
              description=”系统会保留它作为旧配置兜底；新配置请到 AI 提示词管理中维护模板正文。保存本页不会继续写入新的提示词正文。”
            />
          </el-card>

          <!-- 4. 自动识别与自动化（代码第四步，拆分原 autoRunOnSync） -->
          <el-card shadow=”never” class=”config-card mt16”>
            <template #header>
              <div class=”card-header”>
                <span>同步后自动化</span>
                <el-tag type=”danger” effect=”plain”>按场景独立控制识别、拉日志、AI分析</el-tag>
              </div>
            </template>

            <el-form :model=”form.automationConfig” label-width=”180px”>
              <el-row :gutter=”16”>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”启用新自动化配置”>
                    <el-switch
                      v-model=”form.automationConfig.enabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                    <div class=”mapping-desc” style=”margin-top: 4px; font-size: 12px;”>
                      开启后以下场景开关生效；关闭时兜底走旧 autoRunOnSync 逻辑
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>

              <el-divider content-position=”left”>自动识别（项目/模块/人员/门店）</el-divider>
              <el-row :gutter=”16”>
                <el-col :xs=”24” :md=”8”>
                  <el-form-item label=”外部推送识别” label-width=”150px”>
                    <el-switch v-model=”form.automationConfig.autoIdentifyOnExternalSync” inline-prompt active-text=”开” inactive-text=”关” />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”8”>
                  <el-form-item label=”远端拉取识别” label-width=”150px”>
                    <el-switch v-model=”form.automationConfig.autoIdentifyOnRemotePull” inline-prompt active-text=”开” inactive-text=”关” />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”8”>
                  <el-form-item label=”多维表格拉取识别” label-width=”150px”>
                    <el-switch v-model=”form.automationConfig.autoIdentifyOnBitablePull” inline-prompt active-text=”开” inactive-text=”关” />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-divider content-position=”left”>自动拉取日志</el-divider>
              <el-row :gutter=”16”>
                <el-col :xs=”24” :md=”8”>
                  <el-form-item label=”外部推送拉日志” label-width=”150px”>
                    <el-switch v-model=”form.automationConfig.autoLogPullOnExternalSync” inline-prompt active-text=”开” inactive-text=”关” />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”8”>
                  <el-form-item label=”远端拉取拉日志” label-width=”150px”>
                    <el-switch v-model=”form.automationConfig.autoLogPullOnRemotePull” inline-prompt active-text=”开” inactive-text=”关” />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”8”>
                  <el-form-item label=”多维表格拉取拉日志” label-width=”150px”>
                    <el-switch v-model=”form.automationConfig.autoLogPullOnBitablePull” inline-prompt active-text=”开” inactive-text=”关” />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-divider content-position=”left”>日志拉取后自动 AI 分析</el-divider>
              <el-row :gutter=”16”>
                <el-col :xs=”24” :md=”8”>
                  <el-form-item label=”外部推送 AI 分析” label-width=”150px”>
                    <el-switch v-model=”form.automationConfig.autoAiAnalysisOnExternalSync” inline-prompt active-text=”开” inactive-text=”关” />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”8”>
                  <el-form-item label=”远端拉取 AI 分析” label-width=”150px”>
                    <el-switch v-model=”form.automationConfig.autoAiAnalysisOnRemotePull” inline-prompt active-text=”开” inactive-text=”关” />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”8”>
                  <el-form-item label=”多维表格拉取 AI 分析” label-width=”150px”>
                    <el-switch v-model=”form.automationConfig.autoAiAnalysisOnBitablePull” inline-prompt active-text=”开” inactive-text=”关” />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-alert class=”mt8” type=”info” show-icon :closable=”false” title=”定时任务优先” description=”定时任务参数中指定的 automation 配置优先级最高，此处配置仅在没有任务级参数时作为默认值。” />
            </el-form>
          </el-card>

          <!-- 5. 工单群消息推送（代码第五步） -->
          <el-card shadow=”never” class=”config-card mt16”>
            <template #header>
              <div class=”card-header”>
                <span>工单群消息推送</span>
                <el-tag type=”success” effect=”plain”>推送配置</el-tag>
              </div>
            </template>

            <el-form :model=”form.groupPush” label-width=”150px”>
              <el-row :gutter=”16”>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”启用群推送”>
                    <el-switch
                      v-model=”form.groupPush.enabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”发送模式”>
                    <el-select v-model=”form.groupPush.sendMode” style=”width: 100%”>
                      <el-option
                        v-for=”item in notifySendModes”
                        :key=”`group-mode-${item.value}`”
                        :label=”item.label”
                        :value=”item.value”
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”推送渠道”>
                    <el-select
                      v-model=”form.groupPush.pushIds”
                      multiple
                      filterable
                      collapse-tags
                      :loading=”pushOptionsLoading”
                      placeholder=”请选择推送配置”
                      style=”width: 100%”
                    >
                      <el-option
                        v-for=”item in pushOptions”
                        :key=”item.pushId”
                        :label=”item.label”
                        :value=”item.pushId”
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”应用群 chat_id”>
                    <el-select
                      v-model=”form.groupPush.appChatIds”
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      placeholder=”feishu_app/hybrid 模式必填”
                      style=”width: 100%”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”外部推送后发送”>
                    <el-switch
                      v-model=”form.groupPush.sendAfterExternalSync”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”远端拉取后发送”>
                    <el-switch
                      v-model=”form.groupPush.sendAfterRemotePull”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :span=”24”>
                  <el-form-item label=”自动推送状态条件”>
                    <el-select
                      v-model=”form.groupPush.autoPushStatuses”
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      collapse-tags
                      placeholder=”留空表示不按状态限制；默认保留原有三种状态”
                      style=”width: 100%”
                    >
                      <el-option
                        v-for=”item in groupPushAutoStatusOptions”
                        :key=”`group-auto-status-${item}`”
                        :label=”item”
                        :value=”item”
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”自动推送起始时间”>
                    <el-date-picker
                      v-model=”form.groupPush.autoSendAfterTime”
                      type=”datetime”
                      value-format=”YYYY-MM-DD HH:mm:ss”
                      format=”YYYY-MM-DD HH:mm:ss”
                      placeholder=”不填表示不限制提交时间”
                    />
                  </el-form-item>
                </el-col>
                <el-col :span=”24”>
                  <el-form-item label=”优先级路由”>
                    <div class=”priority-route-list”>
                      <div
                        v-for=”(route, idx) in form.groupPush.priorityRoutes”
                        :key=”`route-${idx}`”
                        class=”priority-route-item”
                      >
                        <el-row :gutter=”12”>
                          <el-col :xs=”24” :md=”6”>
                            <el-select
                              v-model=”route.priorities”
                              multiple
                              placeholder=”优先级”
                              style=”width: 100%”
                            >
                              <el-option label=”P1” value=”P1” />
                              <el-option label=”P2” value=”P2” />
                              <el-option label=”P3” value=”P3” />
                              <el-option label=”P4” value=”P4” />
                            </el-select>
                          </el-col>
                          <el-col :xs=”24” :md=”9”>
                            <el-select
                              v-model=”route.pushIds”
                              multiple
                              filterable
                              collapse-tags
                              :loading=”pushOptionsLoading”
                              placeholder=”路由推送渠道（机器人）”
                              style=”width: 100%”
                            >
                              <el-option
                                v-for=”item in pushOptions”
                                :key=”`route-push-${idx}-${item.pushId}`”
                                :label=”item.label”
                                :value=”item.pushId”
                              />
                            </el-select>
                          </el-col>
                          <el-col :xs=”24” :md=”9”>
                            <el-select
                              v-model=”route.chatIds”
                              multiple
                              filterable
                              allow-create
                              default-first-option
                              placeholder=”路由群 chat_id（应用身份）”
                              style=”width: 100%”
                            />
                          </el-col>
                        </el-row>
                      </div>
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :span=”24”>
                  <el-form-item label=”自动推送模板”>
                    <el-input
                      v-model=”form.groupPush.template”
                      type=”textarea”
                      :rows=”5”
                      placeholder=”可用变量：${ticket_no} ${ticket_title} ${project_name} ${module_name} ${ticket_status} ${assignee_name} ${ticket_url} ${sync_source_record_url} ${description} ${report_at} ${reporter_at} ${assignee_at} ${mention_at}”
                    />
                  </el-form-item>
                </el-col>
                <el-col :span=”24”>
                  <el-form-item label=”手动发送模板”>
                    <el-input
                      v-model=”form.groupPush.manualTemplate”
                      type=”textarea”
                      :rows=”4”
                      placeholder=”留空时复用自动推送模板”
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <!-- 6. 飞书多维表格主动拉取（仅数据连接） -->
          <el-card shadow=”never” class=”config-card mt16”>
            <template #header>
              <div class=”card-header”>
                <span>飞书多维表格主动拉取</span>
                <el-tag type=”warning” effect=”plain”>拉取配置（仅数据连接，功能开关见上方各模块）</el-tag>
              </div>
            </template>

            <el-form :model=”form.bitablePull” label-width=”150px”>
              <el-row :gutter=”16”>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”启用主动拉取”>
                    <el-switch
                      v-model=”form.bitablePull.enabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”来源系统标识”>
                    <el-input
                      v-model=”form.bitablePull.sourceSystem”
                      placeholder=”如 feishu_bitable_pull”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”多维 appToken”>
                    <el-input v-model=”form.bitablePull.appToken” placeholder=”为空继承公共配置” />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”多维 tableId”>
                    <el-input v-model=”form.bitablePull.tableId” placeholder=”为空继承公共配置” />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”多维 viewId”>
                    <el-input v-model=”form.bitablePull.viewId” placeholder=”为空继承公共配置” />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”分页大小”>
                    <el-input-number
                      v-model=”form.bitablePull.pageSize”
                      :min=”1”
                      :max=”500”
                      style=”width: 100%”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”工单号字段”>
                    <el-input
                      v-model=”form.bitablePull.ticketNoField”
                      placeholder=”用于说明，多数情况由字段映射给 ticketNo”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”更新时间字段”>
                    <el-input
                      v-model=”form.bitablePull.updatedAtField”
                      placeholder=”如 更新时间；默认时间窗口过滤字段之一”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”排序字段”>
                    <el-input
                      v-model=”form.bitablePull.sortField”
                      placeholder=”预留；当前仅保存说明”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”写入记录链接”>
                    <el-switch
                      v-model=”form.bitablePull.includeRecordUrl”
                      inline-prompt
                      active-text=”是”
                      inactive-text=”否”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”强制同步”>
                    <el-switch
                      v-model=”form.bitablePull.forceSync”
                      inline-prompt
                      active-text=”是”
                      inactive-text=”否”
                    />
                    <div class=”switch-inline-desc__text”>
                      开启后忽略本地快照去重，重新拉取远端数据入库并触发后处理
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :span=”24”>
                  <el-form-item label=”过滤条件JSON”>
                    <el-input
                      v-model=”form.bitablePull.filterFormula”
                      type=”textarea”
                      :rows=”3”
                      placeholder='可选；任务参数未覆盖时按此条件主动查询，如 {“conjunction”:”and”,”conditions”:[{“field_name”:”(RD)工單狀態”,”operator”:”contains”,”value”:[“3. 待产研处理”]}]}'
                    />
                  </el-form-item>
                </el-col>
                <el-col :span=”24”>
                  <el-form-item label=”字段映射”>
                    <div class=”mapping-desc mb8”>
                      “多维字段”支持下拉选择或手动输入。点击”读取表格字段”会按当前多维配置读取字段元数据，不受主动拉取过滤条件和时间窗口影响。
                    </div>
                    <div class=”mb8”>
                      <el-button
                        size=”small”
                        :loading=”bitablePullFieldsLoading”
                        @click=”handlePreviewBitablePullFields”
                      >
                        读取表格字段
                      </el-button>
                      <span
                        v-if=”bitablePullFieldOptions.length”
                        class=”mapping-desc”
                        style=”margin-left: 12px”
                      >
                        已读取 {{ bitablePullFieldOptions.length }} 个字段
                      </span>
                    </div>
                    <el-table :data=”form.bitablePull.fieldMappings” border size=”small”>
                      <el-table-column label=”多维字段” min-width=”220”>
                        <template #default=”scope”>
                          <el-select
                            v-model=”scope.row.sourceField”
                            filterable
                            allow-create
                            default-first-option
                            style=”width: 100%”
                            placeholder=”选择表格字段或手动输入”
                            @visible-change=”handleBitablePullFieldSelectVisibleChange”
                          >
                            <el-option
                              v-for=”item in bitablePullFieldOptions”
                              :key=”`bitable-source-field-${item}`”
                              :label=”item”
                              :value=”item”
                            />
                          </el-select>
                        </template>
                      </el-table-column>
                      <el-table-column label=”接口字段” min-width=”220”>
                        <template #default=”scope”>
                          <el-select
                            v-model=”scope.row.targetField”
                            filterable
                            allow-create
                            default-first-option
                            style=”width: 100%”
                            placeholder=”选择外部字段模型中的字段”
                          >
                            <el-option
                              v-for=”item in externalFieldModelOptions”
                              :key=”`bitable-pull-field-${item.value}`”
                              :label=”item.label”
                              :value=”item.value”
                            />
                          </el-select>
                        </template>
                      </el-table-column>
                      <el-table-column label=”默认值” min-width=”180”>
                        <template #default=”scope”>
                          <el-input
                            v-model=”scope.row.defaultValue”
                            placeholder=”为空时可回填默认值”
                          />
                        </template>
                      </el-table-column>
                      <el-table-column label=”多值分隔符” width=”120”>
                        <template #default=”scope”>
                          <el-input v-model=”scope.row.joinSeparator” placeholder=”,” />
                        </template>
                      </el-table-column>
                      <el-table-column label=”操作” width=”80” align=”center”>
                        <template #default=”scope”>
                          <el-button
                            link
                            type=”danger”
                            icon=”Delete”
                            @click=”removeBitablePullFieldMapping(scope.$index)”
                          />
                        </template>
                      </el-table-column>
                    </el-table>
                    <div class=”mt8”>
                      <el-button type=”primary” link icon=”Plus” @click=”addBitablePullFieldMapping”
                        >新增映射</el-button
                      >
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <!-- 7. 远端同步链接（仅数据连接） -->
          <el-card shadow=”never” class=”config-card mt16”>
            <template #header>
              <div class=”card-header”>
                <span>远端同步链接</span>
                <el-tag type=”warning” effect=”plain”>拉取配置（仅数据连接，功能开关见上方各模块）</el-tag>
              </div>
            </template>

            <el-form
              ref=”remoteFormRef”
              :model=”form.remoteSync”
              :rules=”remoteRules”
              label-width=”150px”
            >
              <el-row :gutter=”16”>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”启用远端同步” prop=”enabled”>
                    <el-switch
                      v-model=”form.remoteSync.enabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”抓取超时(秒)” prop=”timeoutSec”>
                    <el-input-number
                      v-model=”form.remoteSync.timeoutSec”
                      :min=”10”
                      :max=”300”
                      :step=”5”
                      style=”width: 100%”
                    />
                  </el-form-item>
                </el-col>
                <el-col :span=”24”>
                  <el-form-item label=”拉取地址” prop=”pullUrl”>
                    <el-input
                      v-model=”form.remoteSync.pullUrl”
                      placeholder=”https://example.com/api/tickets/pending”
                    />
                  </el-form-item>
                </el-col>
                <el-col :span=”24”>
                  <el-form-item label=”回写地址” prop=”ackUrl”>
                    <el-input
                      v-model=”form.remoteSync.ackUrl”
                      placeholder=”https://example.com/api/tickets/ack”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”消费者标识” prop=”consumer”>
                    <el-input
                      v-model=”form.remoteSync.consumer”
                      placeholder=”例如 public-ticket-sync”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”每次拉取数量” prop=”limit”>
                    <el-input-number
                      v-model=”form.remoteSync.limit”
                      :min=”1”
                      :max=”200”
                      :step=”1”
                      style=”width: 100%”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”包含已关闭” prop=”includeClosed”>
                    <el-switch
                      v-model=”form.remoteSync.includeClosed”
                      inline-prompt
                      active-text=”是”
                      inactive-text=”否”
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <!-- 8. 外部推送多维表格邮箱补全 -->
          <el-card shadow=”never” class=”config-card mt16”>
            <template #header>
              <div class=”card-header”>
                <span>外部推送多维表格邮箱补全</span>
                <el-tag type=”warning” effect=”plain”>推送配置</el-tag>
              </div>
            </template>

            <el-form :model=”form.externalSyncBitable” label-width=”150px”>
              <el-row :gutter=”16”>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”启用邮箱补全”>
                    <el-switch
                      v-model=”form.externalSyncBitable.enabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”多维 appToken”>
                    <el-input
                      v-model=”form.externalSyncBitable.appToken”
                      placeholder=”飞书多维表格应用 Token”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”多维 tableId”>
                    <el-input
                      v-model=”form.externalSyncBitable.tableId”
                      placeholder=”飞书多维表格表ID”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”多维 viewId”>
                    <el-input
                      v-model=”form.externalSyncBitable.viewId”
                      placeholder=”可选，不填默认表视图”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”飞书 appId”>
                    <el-input
                      v-model=”form.externalSyncBitable.appId”
                      placeholder=”覆盖统一凭证（可选）”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”飞书 appSecret”>
                    <el-input
                      v-model=”form.externalSyncBitable.appSecret”
                      show-password
                      placeholder=”覆盖统一凭证（可选）”
                    />
                  </el-form-item>
                </el-col>
                <el-col :span=”24”>
                  <div class=”mapping-desc”>
                    外部推送传入的 <code>recordId</code> 会作为飞书多维表格记录ID查询固定字段：
                    <code>(IT) L1 PIC</code>、<code>1.5 当前负责人</code>、<code>当前负责人</code>。
                    当前块未填写的多维凭证会继承”多维表格公共配置”。
                  </div>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <!-- 外部工单字段模型 -->
          <el-card shadow=”never” class=”config-card mt16”>
            <template #header>
              <div class=”card-header”>
                <span>外部工单字段模型</span>
                <el-tag type=”info” effect=”plain”>必填枚举来源</el-tag>
              </div>
            </template>
            <el-form :model=”form.externalFieldModel” label-width=”150px”>
              <el-form-item label=”字段模型说明”>
                <div class=”mapping-desc”>
                  外部推送字段全集、主动拉取字段映射目标字段都来自这里；这里的”默认必填”就是外部同步必填规则的唯一编辑入口，不需要再单独维护另一份必填列表。
                </div>
              </el-form-item>
              <el-form-item label=”字段列表”>
                <el-table :data=”form.externalFieldModel.fields” border size=”small”>
                  <el-table-column label=”字段名” min-width=”180”>
                    <template #default=”scope”>
                      <el-input v-model=”scope.row.fieldName” placeholder=”如 ticketNo” />
                    </template>
                  </el-table-column>
                  <el-table-column label=”显示名” min-width=”180”>
                    <template #default=”scope”>
                      <el-input v-model=”scope.row.label” placeholder=”如 工单号” />
                    </template>
                  </el-table-column>
                  <el-table-column label=”分类” min-width=”120”>
                    <template #default=”scope”>
                      <el-input v-model=”scope.row.category” placeholder=”basic/person/mapping” />
                    </template>
                  </el-table-column>
                  <el-table-column label=”默认必填” width=”120”>
                    <template #default=”scope”>
                      <el-switch v-model=”scope.row.required” />
                    </template>
                  </el-table-column>
                  <el-table-column label=”说明” min-width=”200”>
                    <template #default=”scope”>
                      <el-input v-model=”scope.row.description” placeholder=”可选说明” />
                    </template>
                  </el-table-column>
                  <el-table-column label=”操作” width=”80” align=”center”>
                    <template #default=”scope”>
                      <el-button
                        link
                        type=”danger”
                        icon=”Delete”
                        @click=”removeExternalFieldModel(scope.$index)”
                      />
                    </template>
                  </el-table-column>
                </el-table>
                <div class=”mt8”>
                  <el-button type=”primary” link icon=”Plus” @click=”addExternalFieldModel”
                    >新增字段</el-button
                  >
                </div>
              </el-form-item>
            </el-form>
          </el-card>

          <!-- 工单评论同步 -->
          <el-card shadow=”never” class=”config-card mt16”>
            <template #header>
              <div class=”card-header”>
                <span>工单评论同步</span>
                <el-tag type=”warning” effect=”plain”>默认关闭</el-tag>
              </div>
            </template>

            <el-form :model=”form.messageSync” label-width=”170px”>
              <el-row :gutter=”16”>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”启用评论同步”>
                    <el-switch
                      v-model=”form.messageSync.enabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”Webhook 入站”>
                    <el-switch
                      v-model=”form.messageSync.feishuEventEnabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”长连接入站”>
                    <el-switch
                      v-model=”form.messageSync.feishuWsEnabled”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”长连接 Token”>
                    <el-input
                      v-model=”form.messageSync.feishuWsVerificationToken”
                      placeholder=”飞书事件订阅 Verification Token，可空”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”长连接 Encrypt Key”>
                    <el-input
                      v-model=”form.messageSync.feishuWsEncryptKey”
                      placeholder=”飞书事件订阅 Encrypt Key，可空”
                      show-password
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”允许群 chat_id”>
                    <el-select
                      v-model=”form.messageSync.allowedChatIds”
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      placeholder=”留空表示不限制群”
                      style=”width: 100%”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”忽略机器人 open_id”>
                    <el-select
                      v-model=”form.messageSync.ignoreBotOpenIds”
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      placeholder=”用于避免机器人自发消息回流”
                      style=”width: 100%”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”飞书评论写入工单”>
                    <el-switch
                      v-model=”form.messageSync.syncFeishuCommentToTicket”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”飞书评论写入多维”>
                    <el-switch
                      v-model=”form.messageSync.syncFeishuCommentToBitable”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”系统评论写入多维”>
                    <el-switch
                      v-model=”form.messageSync.syncTicketCommentToBitable”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”系统评论发到话题”>
                    <el-switch
                      v-model=”form.messageSync.syncTicketCommentToFeishuThread”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”多维新增同步话题”>
                    <el-switch
                      v-model=”form.messageSync.syncBitableNewStepToFeishuThread”
                      inline-prompt
                      active-text=”开”
                      inactive-text=”关”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”排查过程字段”>
                    <el-input
                      v-model=”form.messageSync.bitableStepReasonField”
                      placeholder=”默认 stepReason”
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs=”24” :md=”12”>
                  <el-form-item label=”工单号字段”>
                    <el-input
                      v-model=”form.messageSync.bitableTicketNoField”
                      placeholder=”默认 ticketNo”
                    />
                  </el-form-item>
                </el-col>
                <el-col :span=”24”>
                  <el-form-item label=”追加格式”>
                    <el-input
                      v-model=”form.messageSync.appendStepReasonFormat”
                      placeholder=”{date} {user}：{content}”
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>
        </el-tab-pane>
        <el-tab-pane label="映射/规则">
          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>识别规则</span>
                <el-tag effect="plain">按文本匹配，找不到则保留原值</el-tag>
              </div>
            </template>

            <el-form ref="patternFormRef" :model="form" label-width="150px">
              <el-form-item label="POS 正则规则">
                <el-input
                  v-model="posPatternsText"
                  type="textarea"
                  :rows="6"
                  placeholder='请输入 JSON 数组，例如 ["A", "B"]'
                />
              </el-form-item>
              <el-form-item label="SCO 正则规则">
                <el-input
                  v-model="scoPatternsText"
                  type="textarea"
                  :rows="6"
                  placeholder='请输入 JSON 数组，例如 ["A", "B"]'
                />
              </el-form-item>
              <el-form-item label="版本号正则规则">
                <el-input
                  v-model="versionPatternsText"
                  type="textarea"
                  :rows="6"
                  placeholder='请输入 JSON 数组，例如 ["A", "B"]'
                />
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
        </el-tab-pane>
        <el-tab-pane label="系统字段">
          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>统计枚举配置</span>
                <el-tag effect="plain">基础配置</el-tag>
              </div>
            </template>

            <div class="stat-config-grid">
              <section class="stat-config-section">
                <div class="stat-config-section__head">
                  <span>工单类型</span>
                  <el-button link type="primary" icon="Plus" @click="addStatOption('issueTypes')"
                    >新增</el-button
                  >
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
                      <el-select
                        v-model="scope.row.isProblem"
                        placeholder="可选"
                        clearable
                        style="width: 100%"
                      >
                        <el-option label="真实问题" :value="true" />
                        <el-option label="非问题" :value="false" />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="80" align="center">
                    <template #default="scope">
                      <el-button
                        link
                        type="danger"
                        icon="Delete"
                        @click="removeStatOption('issueTypes', scope.$index)"
                      />
                    </template>
                  </el-table-column>
                </el-table>
              </section>

              <section class="stat-config-section">
                <div class="stat-config-section__head">
                  <span>根因分类</span>
                  <el-button
                    link
                    type="primary"
                    icon="Plus"
                    @click="addStatOption('rootCauseTypes')"
                    >新增</el-button
                  >
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
                      <el-button
                        link
                        type="danger"
                        icon="Delete"
                        @click="removeStatOption('rootCauseTypes', scope.$index)"
                      />
                    </template>
                  </el-table-column>
                </el-table>
              </section>

              <section class="stat-config-section">
                <div class="stat-config-section__head">
                  <span>解决方式</span>
                  <el-button link type="primary" icon="Plus" @click="addStatOption('solutionTypes')"
                    >新增</el-button
                  >
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
                      <el-button
                        link
                        type="danger"
                        icon="Delete"
                        @click="removeStatOption('solutionTypes', scope.$index)"
                      />
                    </template>
                  </el-table-column>
                </el-table>
              </section>

              <section class="stat-config-section">
                <div class="stat-config-section__head">
                  <span>关闭结果</span>
                  <el-button link type="primary" icon="Plus" @click="addStatOption('resolutions')"
                    >新增</el-button
                  >
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
                      <el-select
                        v-model="scope.row.isProblem"
                        placeholder="可选"
                        clearable
                        style="width: 100%"
                      >
                        <el-option label="真实问题" :value="true" />
                        <el-option label="非问题" :value="false" />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="80" align="center">
                    <template #default="scope">
                      <el-button
                        link
                        type="danger"
                        icon="Delete"
                        @click="removeStatOption('resolutions', scope.$index)"
                      />
                    </template>
                  </el-table-column>
                </el-table>
              </section>

              <section class="stat-config-section stat-config-section--wide">
                <div class="stat-config-section__head">
                  <span>细分问题类型</span>
                  <el-button
                    link
                    type="primary"
                    icon="Plus"
                    @click="addStatOption('problemPatterns')"
                    >新增</el-button
                  >
                </div>
                <el-table :data="form.statClassification.problemPatterns" border size="small">
                  <el-table-column label="编码" min-width="170">
                    <template #default="scope">
                      <el-input v-model="scope.row.value" placeholder="如 memory_leak" />
                    </template>
                  </el-table-column>
                  <el-table-column label="名称" min-width="190">
                    <template #default="scope">
                      <el-input v-model="scope.row.label" placeholder="如 内存泄露" />
                    </template>
                  </el-table-column>
                  <el-table-column label="模块Code" min-width="130">
                    <template #default="scope">
                      <el-input v-model="scope.row.moduleCode" placeholder="可选，如 coupon" />
                    </template>
                  </el-table-column>
                  <el-table-column label="工单类型" min-width="150">
                    <template #default="scope">
                      <el-input v-model="scope.row.issueTypeId" placeholder="如 system_bug" />
                    </template>
                  </el-table-column>
                  <el-table-column label="根因" min-width="150">
                    <template #default="scope">
                      <el-input v-model="scope.row.rootCauseType" placeholder="如 code_defect" />
                    </template>
                  </el-table-column>
                  <el-table-column label="关闭结果" min-width="150">
                    <template #default="scope">
                      <el-input v-model="scope.row.resolutionCode" placeholder="如 fixed" />
                    </template>
                  </el-table-column>
                  <el-table-column label="说明" min-width="240">
                    <template #default="scope">
                      <el-input
                        v-model="scope.row.description"
                        placeholder="用于AI判定的业务定义"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column label="启用" width="90" align="center">
                    <template #default="scope">
                      <el-switch v-model="scope.row.enabled" />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="80" align="center">
                    <template #default="scope">
                      <el-button
                        link
                        type="danger"
                        icon="Delete"
                        @click="removeStatOption('problemPatterns', scope.$index)"
                      />
                    </template>
                  </el-table-column>
                </el-table>
              </section>
            </div>
          </el-card>
        </el-tab-pane>
        <el-tab-pane label="操作">
          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>手动触发入口</span>
                <el-tag effect="plain">输入工单号或用户信息后直接执行</el-tag>
              </div>
            </template>

            <el-row :gutter="24">
              <el-col :xs="24" :lg="12">
                <el-form :model="groupSendForm" label-width="110px">
                  <el-form-item label="工单号">
                    <el-input
                      v-model="groupSendForm.ticketNo"
                      placeholder="输入工单号后发送群消息"
                    />
                  </el-form-item>
                  <el-form-item label="强制推送">
                    <el-switch
                      v-model="groupSendForm.forcePush"
                      active-text="是（忽略已推送状态）"
                      inactive-text="否（遵循已推送状态）"
                    />
                  </el-form-item>
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="groupSendLoading"
                      @click="handleSendGroupPushByTicket"
                    >
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
                    <el-button :loading="personPreviewLoading" @click="handlePreviewPersonReminder"
                      >统计该用户</el-button
                    >
                    <el-button
                      type="primary"
                      :loading="personRunLoading"
                      @click="handleRunPersonReminder"
                    >
                      发送该用户催办
                    </el-button>
                  </el-form-item>
                  <el-divider content-position="left">汇总统计手动触发</el-divider>
                  <el-form-item label="开始时间">
                    <el-input
                      v-model="summaryRunForm.startTime"
                      placeholder="可选，格式如 2026-06-10 09:00:00"
                    />
                  </el-form-item>
                  <el-form-item label="结束时间">
                    <el-input
                      v-model="summaryRunForm.endTime"
                      placeholder="可选，格式如 2026-06-10 18:00:00"
                    />
                  </el-form-item>
                  <el-form-item>
                    <el-button
                      type="success"
                      :loading="summaryRunLoading"
                      @click="handleRunSummaryReport"
                    >
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
                    <el-select
                      v-model="autoCategoryForm.aiPromptCode"
                      placeholder="可选，留空走当前分类配置"
                      filterable
                      clearable
                      style="width: 100%"
                    >
                      <el-option
                        v-for="item in promptOptions"
                        :key="`auto-category-${item.templateCode || item.value}`"
                        :label="formatPromptOptionLabel(item)"
                        :value="item.templateCode || item.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="8">
                  <el-form-item label="仅未归类">
                    <el-switch
                      v-model="autoCategoryForm.onlyUncategorized"
                      inline-prompt
                      active-text="是"
                      inactive-text="否"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="8">
                  <el-form-item label="全量扫描">
                    <el-switch
                      v-model="autoCategoryForm.allTickets"
                      inline-prompt
                      active-text="是"
                      inactive-text="否"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="8">
                  <el-form-item label="强制覆盖已有分类">
                    <el-switch
                      v-model="autoCategoryForm.forceReclassify"
                      inline-prompt
                      active-text="是"
                      inactive-text="否"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="指定工单号">
                    <el-input
                      v-model="autoCategoryForm.ticketIdsText"
                      placeholder="可选，多个 ticketNo 用逗号、空格或换行分隔；填写后优先按指定工单执行"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="!autoCategoryForm.allTickets" :xs="24" :md="12">
                  <el-form-item label="分页页码">
                    <el-input-number
                      v-model="autoCategoryForm.pageNum"
                      :min="1"
                      :max="999999"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="!autoCategoryForm.allTickets" :xs="24" :md="12">
                  <el-form-item label="分页大小">
                    <el-input-number
                      v-model="autoCategoryForm.pageSize"
                      :min="1"
                      :max="500"
                      style="width: 100%"
                    />
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
              <el-button :loading="autoCategoryStatsLoading" @click="handleLoadAutoCategoryStats"
                >统计未归类工单</el-button
              >
              <el-button
                type="primary"
                :loading="autoCategoryRunLoading"
                @click="handleBatchReclassifyByConfig"
                >按当前配置重归类</el-button
              >
              <el-button
                type="danger"
                plain
                :loading="autoCategoryRunLoading"
                @click="handleForceReclassifyAll"
                >强制重归类全部</el-button
              >
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
        </el-tab-pane>
      </el-tabs>
    </el-container>

    <div class="action-bar">
      <el-button
        type="primary"
        :loading="saving"
        @click="handleSave"
        v-hasPermi="['ticket:sync:config:edit']"
        >保存配置</el-button
      >
      <el-button @click="loadConfig">刷新数据</el-button>
    </div>
  </div>
</template>

<script setup name="TicketSyncAutomation">
  import {
    batchReclassifyTicketSync,
    getTicketSyncAutoCategoryStats,
    listTicketSyncNotifyPushOptions,
    previewTicketSyncBitablePullFields,
    previewTicketSyncPersonReminder,
    runTicketSyncPersonReminder,
    runTicketSyncSummaryReport,
    sendTicketSyncGroupPushByTicket,
  } from '@/api/ticket/ticket';
  import { listAiProviderOptions } from '@/api/system/aiprovider';
  import { listAiPromptTemplateOptions } from '@/api/system/aiprompt';
  import { useSyncConfig } from './hooks/useSyncConfig';

  const { proxy } = getCurrentInstance();

  // 配置管理已提取到 hooks/useSyncConfig.js
  const {
    loading,
    saving,
    workflowStatusOptions,
    form,
    mappingTexts,
    posPatternsText,
    scoPatternsText,
    versionPatternsText,
    mappingSections,
    notifySendModes,
    groupPushAutoStatusOptions,
    personDataSourceOptions,
    summaryDataSourceOptions,
    personLocalTimeFieldOptions,
    summaryTimeFieldOptions,
    externalFieldModelOptions,
    rules,
    remoteRules,
    loadConfig,
    loadWorkflowStatuses,
    handleSave,
    addStatOption,
    removeStatOption,
    addExternalFieldModel,
    removeExternalFieldModel,
    addBitablePullFieldMapping,
    removeBitablePullFieldMapping,
  } = useSyncConfig(proxy);
  const pushOptionsLoading = ref(false);
  const pushOptions = ref([]);
  const providerOptions = ref([]);
  const promptOptions = ref([]);
  const groupSendLoading = ref(false);
  const personPreviewLoading = ref(false);
  const personRunLoading = ref(false);
  const summaryRunLoading = ref(false);
  const autoCategoryStatsLoading = ref(false);
  const autoCategoryRunLoading = ref(false);
  const bitablePullFieldsLoading = ref(false);
  const bitablePullFieldsLoaded = ref(false);
  const personPreviewResult = ref(null);
  const autoCategoryStats = ref(null);
  const autoCategoryRegexText = ref('[]');
  const bitablePullFieldOptions = ref([]);
  const groupSendForm = reactive({
    ticketNo: '',
    forcePush: false,
  });
  const personQueryForm = reactive({
    userId: '',
    email: '',
  });
  const summaryRunForm = reactive({
    startTime: '',
    endTime: '',
  });
  const autoCategoryForm = reactive({
    strategy: 'ai',
    aiPromptCode: '',
    onlyUncategorized: true,
    allTickets: true,
    forceReclassify: true,
    pageNum: 1,
    pageSize: 100,
    ticketIdsText: '',
  });
  // mappingTexts + groupPushAutoStatusOptions 已通过 useSyncConfig() 提供

  /**
   * 创建远端同步字段的条件必填校验器。
   * 仅在启用远端同步时校验字段是否为空。
   * @param {string} message 校验失败提示文案。
   * @returns {(rule: any, value: any, callback: (error?: Error) => void) => void} Element Plus 表单校验回调。
   */

  /**
   * 归一化日期时间字符串，统一为 `YYYY-MM-DD HH:mm:ss`，不做时区换算。
   * @param {any} value 原始值。
   * @returns {string} 归一化后的时间文本。
   */

  watch(
    () => form.remoteSync.enabled,
    (enabled) => {
      if (enabled) {
        return;
      }
      const remoteFormRef = proxy.$refs.remoteFormRef;
      if (!remoteFormRef || typeof remoteFormRef.clearValidate !== 'function') {
        return;
      }
      remoteFormRef.clearValidate(['pullUrl', 'ackUrl', 'consumer']);
    }
  );

  watch(
    () => [
      form.bitablePull.appId,
      form.bitablePull.appSecret,
      form.bitablePull.appToken,
      form.bitablePull.tableId,
      form.bitablePull.viewId,
      form.bitablePull.filterFormula,
      form.bitableCommon.appId,
      form.bitableCommon.appSecret,
      form.bitableCommon.appToken,
      form.bitableCommon.tableId,
      form.bitableCommon.viewId,
      form.bitableCommon.filterFormula,
      form.feishuAuth.appId,
      form.feishuAuth.appSecret,
    ],
    () => {
      bitablePullFieldsLoaded.value = false;
      bitablePullFieldOptions.value = [];
    }
  );

  /**
   * 加载 AI Provider 和提示词模板选项。
   * 页面仍允许手工输入编码，选项加载失败时不阻塞配置保存。
   */
  function formatProviderOptionLabel(item = {}) {
    const code = item.providerCode || '';
    const name = item.providerName || code || '-';
    const modelName = item.modelName || '';
    return `${name}${code && name !== code ? ` [${code}]` : ''}${modelName ? ` - ${modelName}` : ''}`;
  }

  function formatPromptOptionLabel(item = {}) {
    const code = item.promptCode || item.templateCode || item.value || '';
    const name = item.promptName || item.templateName || item.label || code || '-';
    return `${name}${code && name !== code ? ` [${code}]` : ''}`;
  }

  function loadAiOptions() {
    listAiProviderOptions()
      .then((response) => {
        providerOptions.value = Array.isArray(response.data) ? response.data : [];
      })
      .catch(() => {
        providerOptions.value = [];
      });
    listAiPromptTemplateOptions({
      template_category: 'classification,analysis,common',
      enabled_only: true,
    })
      .then((response) => {
        promptOptions.value = Array.isArray(response.data) ? response.data : [];
      })
      .catch(() => {
        promptOptions.value = [];
      });
  }

  function normalizeOptionalInt(value) {
    if (value === null || value === undefined || value === '') {
      return null;
    }
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      return null;
    }
    return Math.trunc(parsed);
  }

  function normalizeOptionalEmail(value) {
    const text = String(value || '').trim();
    return text || null;
  }

  function validatePersonQuery() {
    const hasUserId = normalizeOptionalInt(personQueryForm.userId);
    const hasEmail = normalizeOptionalEmail(personQueryForm.email);
    if (!hasUserId && !hasEmail) {
      proxy.$modal.msgWarning('请输入用户ID或邮箱');
      return null;
    }
    return {
      userId: hasUserId,
      email: hasEmail,
    };
  }

  function handlePreviewPersonReminder() {
    const payload = validatePersonQuery();
    if (!payload) {
      return;
    }
    personPreviewLoading.value = true;
    previewTicketSyncPersonReminder(payload)
      .then((response) => {
        personPreviewResult.value = response.data || null;
        if (response.data?.skipped) {
          proxy.$modal.msgWarning(response.data?.skipReason || '统计已跳过');
        } else {
          proxy.$modal.msgSuccess('统计完成');
        }
      })
      .catch((error) => {
        personPreviewResult.value = null;
        proxy.$modal.msgError(error?.message || '统计失败');
      })
      .finally(() => {
        personPreviewLoading.value = false;
      });
  }

  function handleRunPersonReminder() {
    personRunLoading.value = true;
    const payload = {
      userId: normalizeOptionalInt(personQueryForm.userId),
      email: normalizeOptionalEmail(personQueryForm.email),
    };
    runTicketSyncPersonReminder(payload)
      .then((response) => {
        if (response.data?.skipped) {
          proxy.$modal.msgWarning(response.data?.skipReason || '催办已跳过');
        } else {
          proxy.$modal.msgSuccess(`催办执行完成，已发送 ${response.data?.sentPeople || 0} 人`);
        }
      })
      .catch((error) => {
        proxy.$modal.msgError(error?.message || '催办执行失败');
      })
      .finally(() => {
        personRunLoading.value = false;
      });
  }

  function handleRunSummaryReport() {
    const payload = {
      startTime: summaryRunForm.startTime || null,
      endTime: summaryRunForm.endTime || null,
    };
    summaryRunLoading.value = true;
    runTicketSyncSummaryReport(payload)
      .then((response) => {
        const totalCount = response.data?.statSummary?.totalCount || 0;
        proxy.$modal.msgSuccess(`汇总通知已执行，统计工单 ${totalCount} 条`);
      })
      .catch((error) => {
        proxy.$modal.msgError(error?.message || '汇总通知执行失败');
      })
      .finally(() => {
        summaryRunLoading.value = false;
      });
  }

  function buildBitablePullPreviewPayload() {
    return {
      bitablePull: {
        enabled: Boolean(form.bitablePull.enabled),
        appId: String(form.bitablePull.appId || '').trim(),
        appSecret: String(form.bitablePull.appSecret || '').trim(),
        appToken: String(form.bitablePull.appToken || '').trim(),
        tableId: String(form.bitablePull.tableId || '').trim(),
        viewId: String(form.bitablePull.viewId || '').trim(),
        pageSize: Math.min(Math.max(Number(form.bitablePull.pageSize || 1), 1), 500),
        filterFormula: String(form.bitablePull.filterFormula || '').trim(),
        sourceSystem: String(form.bitablePull.sourceSystem || '').trim(),
      },
      bitableCommon: {
        appId: String(form.bitableCommon.appId || '').trim(),
        appSecret: String(form.bitableCommon.appSecret || '').trim(),
        appToken: String(form.bitableCommon.appToken || '').trim(),
        tableId: String(form.bitableCommon.tableId || '').trim(),
        viewId: String(form.bitableCommon.viewId || '').trim(),
        pageSize: Math.min(Math.max(Number(form.bitableCommon.pageSize || 1), 1), 500),
        filterFormula: String(form.bitableCommon.filterFormula || '').trim(),
      },
      feishuAuth: {
        appId: String(form.feishuAuth.appId || '').trim(),
        appSecret: String(form.feishuAuth.appSecret || '').trim(),
      },
    };
  }

  function handlePreviewBitablePullFields() {
    bitablePullFieldsLoading.value = true;
    previewTicketSyncBitablePullFields(buildBitablePullPreviewPayload())
      .then((response) => {
        bitablePullFieldOptions.value = Array.isArray(response.data?.fieldNames)
          ? response.data.fieldNames
          : [];
        bitablePullFieldsLoaded.value = true;
        proxy.$modal.msgSuccess(
          bitablePullFieldOptions.value.length
            ? `已读取 ${bitablePullFieldOptions.value.length} 个字段`
            : '未读取到字段，请检查过滤条件或表格是否有数据'
        );
      })
      .catch((error) => {
        bitablePullFieldOptions.value = [];
        bitablePullFieldsLoaded.value = false;
        proxy.$modal.msgError(error?.message || '读取表格字段失败');
      })
      .finally(() => {
        bitablePullFieldsLoading.value = false;
      });
  }

  function handleBitablePullFieldSelectVisibleChange(visible) {
    if (!visible) {
      return;
    }
    if (bitablePullFieldsLoading.value || bitablePullFieldsLoaded.value) {
      return;
    }
    handlePreviewBitablePullFields();
  }

  function parseAutoCategoryRegexRules() {
    if (autoCategoryForm.strategy !== 'regex') {
      return null;
    }
    const text = String(autoCategoryRegexText.value || '').trim();
    if (!text) {
      return null;
    }
    try {
      const parsed = JSON.parse(text);
      if (!Array.isArray(parsed)) {
        throw new Error('正则规则必须是 JSON 数组');
      }
      return parsed;
    } catch (error) {
      throw new Error(error?.message || '正则规则JSON格式错误');
    }
  }

  function parseAutoCategoryTicketNos() {
    const text = String(autoCategoryForm.ticketIdsText || '').trim();
    if (!text) {
      return null;
    }
    const nos = Array.from(
      new Set(
        text
          .split(/[\s,，;；]+/)
          .map((item) => String(item).trim())
          .filter((item) => item.length > 0)
      )
    );
    if (!nos.length) {
      throw new Error('指定工单号格式错误');
    }
    return nos;
  }

  function buildAutoCategoryPayload(overrides = {}) {
    const ticketNos = parseAutoCategoryTicketNos();
    const payload = {
      ticketNos,
      strategy: autoCategoryForm.strategy,
      aiPromptCode:
        String(autoCategoryForm.aiPromptCode || form.aiClassification.promptCode || '').trim() ||
        null,
      onlyUncategorized: Boolean(autoCategoryForm.onlyUncategorized),
      allTickets: Boolean(autoCategoryForm.allTickets),
      forceReclassify: Boolean(autoCategoryForm.forceReclassify),
      pageNum: Math.max(Number(autoCategoryForm.pageNum || 1), 1),
      pageSize: Math.min(Math.max(Number(autoCategoryForm.pageSize || 100), 1), 500),
      regexRules: parseAutoCategoryRegexRules(),
    };
    return { ...payload, ...overrides };
  }

  function executeBatchReclassify(payload, successPrefix = '重归类执行完成') {
    autoCategoryRunLoading.value = true;
    batchReclassifyTicketSync(payload)
      .then((response) => {
        const data = response.data || {};
        const successCount = Number(data.successCount || 0);
        const skippedCount = Number(data.skippedCount || 0);
        const failedCount = Number(data.failedCount || 0);
        proxy.$modal.msgSuccess(
          `${successPrefix}：成功 ${successCount}，跳过 ${skippedCount}，失败 ${failedCount}`
        );
        handleLoadAutoCategoryStats();
      })
      .catch((error) => {
        proxy.$modal.msgError(error?.message || '批量重归类失败');
      })
      .finally(() => {
        autoCategoryRunLoading.value = false;
      });
  }

  function handleLoadAutoCategoryStats() {
    autoCategoryStatsLoading.value = true;
    getTicketSyncAutoCategoryStats()
      .then((response) => {
        autoCategoryStats.value = response.data || null;
        proxy.$modal.msgSuccess('未归类统计完成，不会触发自动归类');
      })
      .catch((error) => {
        autoCategoryStats.value = null;
        proxy.$modal.msgError(error?.message || '未归类统计失败');
      })
      .finally(() => {
        autoCategoryStatsLoading.value = false;
      });
  }

  function handleBatchReclassifyByConfig() {
    try {
      const payload = buildAutoCategoryPayload();
      executeBatchReclassify(payload);
    } catch (error) {
      proxy.$modal.msgError(error?.message || '批量重归类参数错误');
    }
  }

  function handleForceReclassifyAll() {
    try {
      const payload = buildAutoCategoryPayload({
        allTickets: true,
        onlyUncategorized: false,
        forceReclassify: true,
      });
      executeBatchReclassify(payload, '强制全量重归类完成');
    } catch (error) {
      proxy.$modal.msgError(error?.message || '强制全量重归类参数错误');
    }
  }

  function handleSendGroupPushByTicket() {
    const ticketNo = String(groupSendForm.ticketNo || '').trim();
    if (!ticketNo) {
      proxy.$modal.msgWarning('请输入工单号');
      return;
    }
    groupSendLoading.value = true;
    sendTicketSyncGroupPushByTicket({
      ticketNo,
      forcePush: Boolean(groupSendForm.forcePush),
    })
      .then((response) => {
        if (response.data?.skipped) {
          proxy.$modal.msgWarning(response.data?.skipReason || '发送已跳过');
          return;
        }
        const successCount = response.data?.pushSuccessCount || 0;
        const stateUpdated = response.data?.groupPushSentOnceUpdated ? '，已更新去重状态' : '';
        proxy.$modal.msgSuccess(`发送完成，成功渠道数：${successCount}${stateUpdated}`);
      })
      .catch((error) => {
        proxy.$modal.msgError(error?.message || '发送失败');
      })
      .finally(() => {
        groupSendLoading.value = false;
      });
  }

  function loadPushOptions() {
    pushOptionsLoading.value = true;
    listTicketSyncNotifyPushOptions()
      .then((response) => {
        pushOptions.value = Array.isArray(response.data) ? response.data : [];
      })
      .finally(() => {
        pushOptionsLoading.value = false;
      });
  }

  onMounted(() => {
    loadConfig();
    loadPushOptions();
    loadAiOptions();
    loadWorkflowStatuses();
    handleLoadAutoCategoryStats();
  });
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

  .switch-inline-desc {
    margin-bottom: 0;
  }

  .switch-inline-desc__text {
    margin-top: 8px;
    font-size: 12px;
    line-height: 1.5;
    color: var(--el-text-color-secondary);
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
