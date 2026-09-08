<template>
  <div class="app-container ticket-sync-automation-page" v-loading="loading">
    <section class="page-intro">
      <div class="page-intro__eyebrow">工单同步自动化</div>
      <h2 class="page-intro__title">按入库执行顺序管理同步、来源、通知与统计配置</h2>
      <p class="page-intro__desc">
        Provider 和提示词正文统一在系统管理的 AI Provider 与 AI
        提示词中维护，这里只选择编码并配置同步场景开关。
      </p>
    </section>

    <div class="config-tabs-wrap">
      <el-tabs>
        <el-tab-pane label="入库流程" lazy>
          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>⓪ 自动化关注范围</span>
                <el-tag type="warning" effect="plain"
                  >范围外只同步与映射，不调用 AI 或自动群推送</el-tag
                >
              </div>
            </template>
            <el-form :model="form.automationScope" label-width="180px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="8">
                  <el-form-item label="启用关注范围">
                    <el-switch
                      v-model="form.automationScope.enabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="8">
                  <el-form-item label="统计默认仅关注范围">
                    <el-switch
                      v-model="form.automationScope.applyToStatisticsDefault"
                      :disabled="!form.automationScope.enabled"
                      inline-prompt
                      active-text="是"
                      inactive-text="否"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="精确模块 ID">
                    <el-select
                      v-model="form.automationScope.moduleIds"
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      placeholder="可选；输入系统模块 ID 后按 Enter 添加"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="精确模块 Code">
                    <el-select
                      v-model="form.automationScope.moduleCodes"
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      placeholder="可选；输入系统模块 Code 后按 Enter 添加"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="模块名称包含关键字">
                    <el-select
                      v-model="form.automationScope.moduleNameIncludes"
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      placeholder="例如 POS、收银；模块名称命中任一关键字即进入关注范围"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-alert
                    type="info"
                    show-icon
                    :closable="false"
                    title="判定顺序"
                    description="模块 ID、模块 Code、模块名称关键字任一命中即进入范围；启用后未填写任何模块条件时不限制。范围外仍会同步原始数据、字段映射、模块/状态更新和外部规则分类；翻译、AI 提取、AI 分类、自动拉日志/AI 分析、向量刷新和自动群推送都会跳过。现有群推送条件保持原样，仅对范围内工单继续判断。"
                  />
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>场景 × 步骤 开关总表</span>
                <el-tag type="danger" effect="plain"
                  >所有场景开关集中在此，下方步骤卡片只维护参数</el-tag
                >
              </div>
            </template>
            <el-alert
              type="warning"
              show-icon
              :closable="false"
              title="总闸门在上方「自动化关注范围」：范围外工单仅执行同步与映射，下表所有开关都不会生效。"
            />
            <el-table :data="sceneMatrixRows" border size="small" class="scene-matrix-table mt8">
              <el-table-column label="步骤（按执行顺序）" min-width="240">
                <template #default="{ row }">
                  <div class="scene-matrix-step">
                    <span>{{ row.label }}</span>
                    <el-switch
                      v-if="row.master"
                      v-model="form[row.section][row.master]"
                      size="small"
                      inline-prompt
                      active-text="总开关开"
                      inactive-text="总开关关"
                    />
                  </div>
                  <div class="scene-matrix-hint">{{ row.hint }}</div>
                </template>
              </el-table-column>
              <el-table-column
                v-for="(scene, sceneIndex) in sceneMatrixScenes"
                :key="`scene-col-${scene}`"
                :label="scene"
                align="center"
                width="130"
              >
                <template #default="{ row }">
                  <el-switch
                    v-model="form[row.section][row.fields[sceneIndex]]"
                    :disabled="Boolean(row.master) && !form[row.section][row.master]"
                    inline-prompt
                    active-text="开"
                    inactive-text="关"
                  />
                </template>
              </el-table-column>
            </el-table>
            <div class="mapping-desc" style="margin-top: 10px">
              场景含义：外部推送=第三方系统直推；远端拉取=内网定时拉取公网工单；多维表格拉取=飞书多维表格定时拉取；手动创建=页面手工新增工单。
              定时任务参数中指定的 automation 配置优先于本表。
            </div>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>① 字段识别与映射</span>
                <el-tag effect="plain">入库后先按规则识别归属；按文本匹配，找不到则保留原值</el-tag>
                <el-button
                  type="primary"
                  plain
                  size="small"
                  class="card-setting-btn"
                  @click="mappingDialogVisible = true"
                >
                  设置
                </el-button>
              </div>
            </template>

            <div class="card-summary-grid">
              <div class="card-summary-item">
                <div class="card-summary-item__label">正则识别规则</div>
                <div class="card-summary-item__value">
                  POS / SCO / 版本号 三组正则，从工单文本提取编号与版本
                </div>
              </div>
              <div class="card-summary-item">
                <div class="card-summary-item__label">映射配置</div>
                <div class="card-summary-item__value">
                  {{ mappingSections.length }} 组映射（项目 / 模块 / 商家 / 门店 / 状态 /
                  处理人），三方直推与内网拉取共用
                </div>
              </div>
            </div>
            <div class="mapping-desc">
              点击右上角「设置」在弹窗中维护各映射组 JSON
              与正则规则；识别失败不阻断入库，找不到时保留外部原值。
            </div>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>② 外部工单字段模型</span>
                <el-tag type="info" effect="plain">必填枚举来源</el-tag>
              </div>
            </template>
            <el-form :model="form.externalFieldModel" label-width="150px">
              <el-form-item label="字段模型说明">
                <div class="mapping-desc">
                  外部推送字段全集、主动拉取字段映射目标字段都来自这里；这里的"默认必填"就是外部同步必填规则的唯一编辑入口，不需要再单独维护另一份必填列表。
                </div>
              </el-form-item>
              <el-form-item label="字段列表">
                <el-table :data="form.externalFieldModel.fields" border size="small">
                  <el-table-column label="字段名" min-width="180">
                    <template #default="scope">
                      <el-input v-model="scope.row.fieldName" placeholder="如 ticketNo" />
                    </template>
                  </el-table-column>
                  <el-table-column label="显示名" min-width="180">
                    <template #default="scope">
                      <el-input v-model="scope.row.label" placeholder="如 工单号" />
                    </template>
                  </el-table-column>
                  <el-table-column label="分类" min-width="120">
                    <template #default="scope">
                      <el-input v-model="scope.row.category" placeholder="basic/person/mapping" />
                    </template>
                  </el-table-column>
                  <el-table-column label="默认必填" width="120">
                    <template #default="scope">
                      <el-switch v-model="scope.row.required" />
                    </template>
                  </el-table-column>
                  <el-table-column label="说明" min-width="200">
                    <template #default="scope">
                      <el-input v-model="scope.row.description" placeholder="可选说明" />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="80" align="center">
                    <template #default="scope">
                      <el-button
                        link
                        type="danger"
                        icon="Delete"
                        @click="removeExternalFieldModel(scope.$index)"
                      />
                    </template>
                  </el-table-column>
                </el-table>
                <div class="mt8">
                  <el-button type="primary" link icon="Plus" @click="addExternalFieldModel"
                    >新增字段</el-button
                  >
                </div>
              </el-form-item>
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>③ 工单同步 AI 提取</span>
                <el-tag type="info" effect="plain">参数配置；场景开关见顶部总表</el-tag>
              </div>
            </template>

            <el-form :model="form.aiSyncExtract" label-width="150px">
              <div class="mapping-desc">
                场景开关已聚合到「场景 × 步骤 开关总表」；本卡片仅维护
                Provider、模型、提示词与提取字段。
              </div>
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="Provider 编码">
                    <el-select
                      v-model="form.aiSyncExtract.providerCode"
                      placeholder="请选择参数提取 Provider"
                      filterable
                      clearable
                      style="width: 100%"
                      @change="handleProviderModelChange('aiSyncExtract', $event)"
                    >
                      <el-option
                        v-for="item in lightProviderOptions"
                        :key="item.providerCode"
                        :label="formatProviderOptionLabel(item)"
                        :value="item.providerCode"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="模型">
                    <el-select
                      v-model="form.aiSyncExtract.modelName"
                      placeholder="留空使用Provider默认模型"
                      filterable
                      clearable
                      style="width: 100%"
                      :disabled="!form.aiSyncExtract.providerCode"
                    >
                      <el-option
                        v-for="item in lightModelOptionsMap[form.aiSyncExtract.providerCode] || []"
                        :key="item.modelId"
                        :label="item.displayName || item.modelId"
                        :value="item.modelId"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="提示词编码">
                    <el-select
                      v-model="form.aiSyncExtract.promptCode"
                      placeholder="请选择提示词模板；留空使用默认模板"
                      filterable
                      clearable
                      style="width: 100%"
                    >
                      <el-option
                        v-for="item in promptOptions"
                        :key="item.templateCode || item.value"
                        :label="formatPromptOptionLabel(item)"
                        :value="item.templateCode || item.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>

              <el-divider content-position="left">提取字段配置</el-divider>
              <el-row :gutter="16">
                <el-col :span="24">
                  <el-form-item label="AI提取字段">
                    <el-checkbox-group v-model="form.aiSyncExtract.extractFields">
                      <el-checkbox label="storeName">门店名称</el-checkbox>
                      <el-checkbox label="posNo">POS编号</el-checkbox>
                      <el-checkbox label="scoNo">SCO编号</el-checkbox>
                      <el-checkbox label="logDate">日志日期</el-checkbox>
                      <el-checkbox label="versionKey">版本号</el-checkbox>
                    </el-checkbox-group>
                    <div class="mapping-desc" style="margin-top: 4px; font-size: 12px">
                      勾选需要从工单描述中AI提取的字段，未勾选的字段将不会被提取
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>④ 工单标题总结</span>
                <el-tag type="info" effect="plain">缺少标题时执行</el-tag>
              </div>
            </template>

            <el-form :model="form.titleSummaryConfig" label-width="150px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="启用标题总结">
                    <el-switch
                      v-model="form.titleSummaryConfig.enabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="Provider 编码">
                    <el-select
                      v-model="form.titleSummaryConfig.providerCode"
                      placeholder="请选择标题总结 Provider"
                      filterable
                      clearable
                      style="width: 100%"
                      @change="handleProviderModelChange('titleSummaryConfig', $event)"
                    >
                      <el-option
                        v-for="item in lightProviderOptions"
                        :key="item.providerCode"
                        :label="formatProviderOptionLabel(item)"
                        :value="item.providerCode"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="模型">
                    <el-select
                      v-model="form.titleSummaryConfig.modelName"
                      placeholder="留空使用Provider默认模型"
                      filterable
                      clearable
                      style="width: 100%"
                      :disabled="!form.titleSummaryConfig.providerCode"
                    >
                      <el-option
                        v-for="item in lightModelOptionsMap[form.titleSummaryConfig.providerCode] ||
                        []"
                        :key="item.modelId"
                        :label="item.displayName || item.modelId"
                        :value="item.modelId"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="提示词编码">
                    <el-select
                      v-model="form.titleSummaryConfig.promptCode"
                      placeholder="请选择标题总结提示词"
                      filterable
                      clearable
                      style="width: 100%"
                    >
                      <el-option
                        v-for="item in promptOptions"
                        :key="item.templateCode || item.value"
                        :label="formatPromptOptionLabel(item)"
                        :value="item.templateCode || item.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>⑤ 工单翻译</span>
                <el-tag type="warning" effect="plain">参数配置；场景开关见顶部总表</el-tag>
              </div>
            </template>

            <el-form :model="form.translateConfig" label-width="150px">
              <div class="mapping-desc">
                翻译总开关与各场景开关已聚合到「场景 × 步骤 开关总表」；本卡片仅维护
                Provider、模型与提示词。
              </div>
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="Provider 编码">
                    <el-select
                      v-model="form.translateConfig.providerCode"
                      placeholder="请选择翻译 Provider"
                      filterable
                      clearable
                      style="width: 100%"
                      @change="handleProviderModelChange('translateConfig', $event)"
                    >
                      <el-option
                        v-for="item in lightProviderOptions"
                        :key="item.providerCode"
                        :label="formatProviderOptionLabel(item)"
                        :value="item.providerCode"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="模型">
                    <el-select
                      v-model="form.translateConfig.modelName"
                      placeholder="留空使用Provider默认模型"
                      filterable
                      clearable
                      style="width: 100%"
                      :disabled="!form.translateConfig.providerCode"
                    >
                      <el-option
                        v-for="item in lightModelOptionsMap[form.translateConfig.providerCode] ||
                        []"
                        :key="item.modelId"
                        :label="item.displayName || item.modelId"
                        :value="item.modelId"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="提示词编码">
                    <el-select
                      v-model="form.translateConfig.promptCode"
                      placeholder="请选择翻译提示词"
                      filterable
                      clearable
                      style="width: 100%"
                    >
                      <el-option
                        v-for="item in promptOptions"
                        :key="item.templateCode || item.value"
                        :label="formatPromptOptionLabel(item)"
                        :value="item.templateCode || item.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>⑥ AI 分类统计配置</span>
                <el-tag type="warning" effect="plain"
                  >参数与状态变更触发；场景开关见顶部总表</el-tag
                >
              </div>
            </template>

            <el-form :model="form.aiClassification" label-width="150px">
              <div class="mapping-desc">
                AI 分类总开关与各场景开关已聚合到「场景 × 步骤
                开关总表」；状态变更触发的重归类在下方单独控制。
              </div>
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="状态变更执行">
                    <el-switch
                      v-model="form.aiClassification.runOnStatusChange"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="状态变更强制覆盖">
                    <el-switch
                      v-model="form.aiClassification.statusChangeForceReclassify"
                      inline-prompt
                      active-text="是"
                      inactive-text="否"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="状态触发条件">
                    <el-select
                      v-model="form.aiClassification.statusChangeTriggerStatuses"
                      placeholder="选择变更到哪些状态后重新归类，可多选"
                      multiple
                      filterable
                      clearable
                      style="width: 100%"
                    >
                      <el-option
                        v-for="item in workflowStatusOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="Provider 编码">
                    <el-select
                      v-model="form.aiClassification.providerCode"
                      placeholder="请选择分类 Provider"
                      filterable
                      clearable
                      style="width: 100%"
                      @change="handleProviderModelChange('aiClassification', $event)"
                    >
                      <el-option
                        v-for="item in lightProviderOptions"
                        :key="item.providerCode"
                        :label="formatProviderOptionLabel(item)"
                        :value="item.providerCode"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="模型">
                    <el-select
                      v-model="form.aiClassification.modelName"
                      placeholder="留空使用Provider默认模型"
                      filterable
                      clearable
                      style="width: 100%"
                      :disabled="!form.aiClassification.providerCode"
                    >
                      <el-option
                        v-for="item in lightModelOptionsMap[form.aiClassification.providerCode] ||
                        []"
                        :key="item.modelId"
                        :label="item.displayName || item.modelId"
                        :value="item.modelId"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="提示词编码">
                    <el-select
                      v-model="form.aiClassification.promptCode"
                      placeholder="请选择提示词模板；留空使用默认模板"
                      filterable
                      clearable
                      style="width: 100%"
                    >
                      <el-option
                        v-for="item in promptOptions"
                        :key="item.templateCode || item.value"
                        :label="formatPromptOptionLabel(item)"
                        :value="item.templateCode || item.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>⑦ 同步后自动化</span>
                <el-tag type="danger" effect="plain">识别/拉日志/AI分析；场景开关见顶部总表</el-tag>
                <el-button
                  type="primary"
                  plain
                  size="small"
                  class="card-setting-btn"
                  @click="logPullDialogVisible = true"
                >
                  日志拉取设置
                </el-button>
              </div>
            </template>

            <el-form :model="form.automationConfig" label-width="180px">
              <div class="mapping-desc">
                识别、自动拉日志、自动 AI 分析的场景开关已聚合到「场景 × 步骤
                开关总表」；自动拉日志的参数与停止条件点击右上角「日志拉取设置」在弹窗中维护。
              </div>

              <el-divider content-position="left">自动化结果通知</el-divider>
              <el-row :gutter="16">
                <el-col :xs="24" :md="6">
                  <el-form-item label="启用结果通知" label-width="150px">
                    <el-switch
                      v-model="form.automationNotification.enabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.automationNotification.enabled" :xs="24" :md="9">
                  <el-form-item label="推送配置" label-width="150px">
                    <el-select
                      v-model="form.automationNotification.pushIds"
                      multiple
                      filterable
                      collapse-tags
                      :loading="pushOptionsLoading"
                      placeholder="请选择推送配置"
                      style="width: 100%"
                    >
                      <el-option
                        v-for="item in pushOptions"
                        :key="item.pushId || item.value"
                        :label="item.pushName || item.label || item.name"
                        :value="item.pushId || item.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col v-if="form.automationNotification.enabled" :xs="12" :md="4">
                  <el-form-item label="成功时推送" label-width="110px">
                    <el-switch v-model="form.automationNotification.success.push" />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.automationNotification.enabled" :xs="12" :md="4">
                  <el-form-item label="失败时推送" label-width="110px">
                    <el-switch v-model="form.automationNotification.failed.push" />
                  </el-form-item>
                </el-col>
                <el-col v-if="form.automationNotification.enabled" :span="24">
                  <el-form-item label="消息模板" label-width="150px">
                    <el-input
                      v-model="form.automationNotification.messageTemplate"
                      type="textarea"
                      :rows="6"
                      placeholder="留空使用系统默认模板；使用 ${变量名} 引用变量"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-descriptions
                v-if="form.automationNotification.enabled"
                :column="3"
                border
                size="small"
                class="automation-notify-variables"
              >
                <el-descriptions-item label="${ticket_no}">工单号</el-descriptions-item>
                <el-descriptions-item label="${ticket_title}">工单标题</el-descriptions-item>
                <el-descriptions-item label="${merchant_name}">商家名称</el-descriptions-item>
                <el-descriptions-item label="${store_name}"
                  >门店名称或日志门店编号</el-descriptions-item
                >
                <el-descriptions-item label="${stage_label}"
                  >当前阶段，如日志拉取、AI 分析</el-descriptions-item
                >
                <el-descriptions-item label="${status_label}">成功或失败</el-descriptions-item>
                <el-descriptions-item label="${reason}">失败原因或结果说明</el-descriptions-item>
                <el-descriptions-item label="${detail}">任务、日志或异常详情</el-descriptions-item>
                <el-descriptions-item label="${ticket_url}">工单详情链接</el-descriptions-item>
              </el-descriptions>

              <el-alert
                class="mt8"
                type="info"
                show-icon
                :closable="false"
                title="定时任务优先"
                description="定时任务参数中指定的 automation 配置优先级最高，此处配置仅在没有任务级参数时作为默认值。"
              />
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>⑧ 工单群消息推送</span>
                <el-tag type="success" effect="plain">参数配置；场景开关见顶部总表</el-tag>
              </div>
            </template>

            <el-form :model="form.groupPush" label-width="150px">
              <div class="mapping-desc">
                群推送总开关与各场景开关已聚合到「场景 × 步骤
                开关总表」；本卡片维护推送渠道、推送条件与模板。
              </div>
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="发送模式">
                    <el-select v-model="form.groupPush.sendMode" style="width: 100%">
                      <el-option
                        v-for="item in notifySendModes"
                        :key="`group-mode-${item.value}`"
                        :label="item.label"
                        :value="item.value"
                      />
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
                <el-col :span="24">
                  <el-form-item prop="autoPushCondition">
                    <template #label>
                      推送条件
                      <PromptButton placement="top" width="700">
                        <div class="condition-help-popover">
                          <div class="condition-help-title">语法说明</div>
                          <table class="condition-help-table">
                            <thead>
                              <tr>
                                <th>类型</th>
                                <th>写法</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr>
                                <td>比较</td>
                                <td>
                                  <code>status_name == '3. 待产研处理'</code>（支持
                                  ==、!=、&gt;、&lt;、&gt;=、&lt;=）
                                </td>
                              </tr>
                              <tr>
                                <td>成员</td>
                                <td>
                                  <code>status_name in ['2. 1.5线处理', '3. 待产研处理']</code>
                                </td>
                              </tr>
                              <tr>
                                <td>排除</td>
                                <td><code>status_name not in ['5. 已关闭', '6. 已取消']</code></td>
                              </tr>
                              <tr>
                                <td>有值</td>
                                <td><code>has(module_id)</code> — 字段非 None 且非空字符串</td>
                              </tr>
                              <tr>
                                <td>空值</td>
                                <td><code>module_id is None</code> — 字段为 None</td>
                              </tr>
                              <tr>
                                <td>非空</td>
                                <td><code>module_id is not None</code> — 字段不为 None</td>
                              </tr>
                              <tr>
                                <td>逻辑</td>
                                <td>
                                  <code>and</code> / <code>or</code> / <code>not</code> + 括号
                                  <code>( )</code>
                                </td>
                              </tr>
                              <tr>
                                <td>时间比较</td>
                                <td>
                                  <code>submit_time &gt;= '2026-01-01'</code
                                  >（日期时间可用引号括起来比较）
                                </td>
                              </tr>
                            </tbody>
                          </table>
                          <div class="condition-help-subtitle">常用示例</div>
                          <table class="condition-help-table">
                            <thead>
                              <tr>
                                <th>场景</th>
                                <th>表达式</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr>
                                <td>特定状态+高优先级</td>
                                <td>
                                  <code
                                    >status_name in ['3. 待产研处理', '4. 产研处理中'] and
                                    internal_priority in ['P0', 'P1']</code
                                  >
                                </td>
                              </tr>
                              <tr>
                                <td>有模块归属才推送</td>
                                <td>
                                  <code
                                    >status_name in ['2. 1.5线处理', '3. 待产研处理'] and
                                    has(module_id)</code
                                  >
                                </td>
                              </tr>
                              <tr>
                                <td>指定项目+严重等级</td>
                                <td><code>has(project_id) and severity in ['S1', 'S2']</code></td>
                              </tr>
                              <tr>
                                <td>有商家的P1工单</td>
                                <td>
                                  <code>has(merchant_name) and internal_priority == 'P1'</code>
                                </td>
                              </tr>
                              <tr>
                                <td>指定时间后创建</td>
                                <td><code>submit_time &gt;= '2026-07-01 00:00:00'</code></td>
                              </tr>
                              <tr>
                                <td>排除关闭+有模块</td>
                                <td>
                                  <code
                                    >status_name not in ['5. 已关闭', '6. 已取消'] and
                                    has(module_id)</code
                                  >
                                </td>
                              </tr>
                            </tbody>
                          </table>
                          <div class="condition-help-subtitle">可用字段列表</div>
                          <table class="condition-help-table condition-help-fields">
                            <thead>
                              <tr>
                                <th style="width: 30%">分类</th>
                                <th>字段名</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr>
                                <td>基本信息</td>
                                <td>
                                  <code>ticket_id</code> <code>ticket_no</code>
                                  <code>ticket_url</code> <code>title</code>
                                  <code>status</code>（编码） <code>status_name</code>（显示名）
                                  <code>source</code> <code>del_flag</code>
                                </td>
                              </tr>
                              <tr>
                                <td>项目/模块/分类</td>
                                <td>
                                  <code>project_id</code> <code>module_id</code>
                                  <code>module_name</code> <code>category_id</code>
                                  <code>category_name</code> <code>issue_type_id</code>
                                  <code>issue_type_name</code>
                                </td>
                              </tr>
                              <tr>
                                <td>优先级/严重度</td>
                                <td>
                                  <code>customer_priority</code> <code>internal_priority</code>
                                  <code>severity</code>
                                </td>
                              </tr>
                              <tr>
                                <td>人员</td>
                                <td>
                                  <code>reporter_id</code> <code>reporter_name</code>
                                  <code>current_assignee_id</code>
                                  <code>current_assignee_name</code>
                                  <code>first_line_assignee_id</code>
                                  <code>first_line_assignee_name</code>
                                  <code>internal_owner_id</code> <code>internal_owner_name</code>
                                </td>
                              </tr>
                              <tr>
                                <td>商家/版本</td>
                                <td>
                                  <code>merchant_name</code> <code>affected_version</code>
                                  <code>planned_fix_version</code> <code>fixed_version</code>
                                  <code>released_version</code>
                                </td>
                              </tr>
                              <tr>
                                <td>分析结果</td>
                                <td>
                                  <code>is_problem</code> <code>root_cause_type</code>
                                  <code>solution_type</code> <code>resolution_code</code>
                                  <code>resolution_name</code> <code>problem_pattern_code</code>
                                  <code>problem_pattern_name</code>
                                  <code>problem_pattern_confidence</code>
                                  <code>problem_pattern_source</code>
                                  <code>problem_pattern_verified</code> <code>issue_id</code>
                                  <code>issue_relation_type</code> <code>issue_confirmed</code>
                                  <code>root_cause</code> <code>solution</code>
                                </td>
                              </tr>
                              <tr>
                                <td>时间字段</td>
                                <td>
                                  <code>submit_time</code> <code>started_at</code>
                                  <code>resolved_at</code> <code>closed_at</code>
                                  <code>first_response_at</code> <code>processed_at</code>
                                  <code>released_at</code> <code>verified_at</code>
                                  <code>total_process_seconds</code>
                                </td>
                              </tr>
                              <tr>
                                <td>其他</td>
                                <td>
                                  <code>description</code> <code>tags</code> <code>create_by</code>
                                  <code>update_by</code>
                                </td>
                              </tr>
                            </tbody>
                          </table>
                          <div class="condition-help-note">
                            留空表示不限制，所有工单均推送。填写后只有满足表达式的工单才会自动推送。
                          </div>
                        </div>
                      </PromptButton>
                    </template>
                    <el-input
                      v-model="form.groupPush.autoPushCondition"
                      type="textarea"
                      :rows="2"
                      placeholder="例: status_name in [&#39;2. 1.5线处理&#39;, &#39;3. 待产研处理&#39;] and has(module_id)"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="优先级路由">
                    <div class="priority-route-list">
                      <div
                        v-for="(route, idx) in form.groupPush.priorityRoutes"
                        :key="`route-${idx}`"
                        class="priority-route-item"
                      >
                        <el-row :gutter="12">
                          <el-col :xs="24" :md="6">
                            <el-select
                              v-model="route.priorities"
                              multiple
                              placeholder="优先级"
                              style="width: 100%"
                            >
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

              <el-divider content-position="left">AI 分析结果话题回帖</el-divider>
              <div class="mapping-desc">
                AI 分析完成后，把分析结果回帖到该工单在工单群的话题中（复用工单信息推送的群消息锚点）。
                仅在发送模式为 feishu_app / hybrid 时生效；工单未发过群消息（无锚点）时自动跳过，不新建话题。
                手动触发分析时可在提交页选择本次是否回帖。
              </div>
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="启用回帖">
                    <el-switch
                      v-model="form.groupPush.aiResultFollowUp.enabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                      :disabled="form.groupPush.sendMode === 'push_config'"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="推送时机">
                    <el-select
                      v-model="form.groupPush.aiResultFollowUp.sendOn"
                      style="width: 100%"
                      :disabled="form.groupPush.sendMode === 'push_config'"
                    >
                      <el-option label="不推送" value="none" />
                      <el-option label="仅分析成功" value="success" />
                      <el-option label="仅分析失败" value="failed" />
                      <el-option label="成功和失败都推送" value="always" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="话题内回复">
                    <el-switch
                      v-model="form.groupPush.aiResultFollowUp.replyInThread"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                      :disabled="form.groupPush.sendMode === 'push_config'"
                    />
                    <div class="mapping-desc">
                      开启后回复挂在工作单信息话题下；关闭则以普通引用回复形式发送。
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="无锚点处理">
                    <el-select
                      v-model="form.groupPush.aiResultFollowUp.noAnchorStrategy"
                      style="width: 100%"
                      :disabled="form.groupPush.sendMode === 'push_config'"
                    >
                      <el-option
                        label="跳过并记录日志（默认，防止重复发送）"
                        value="skip"
                      />
                      <el-option
                        label="先补发工单信息消息建立话题，再回帖"
                        value="send_then_reply"
                      />
                    </el-select>
                    <div class="mapping-desc">
                      工单此前未发过群消息（无话题锚点）时的处理。历史已在群里跟进过的工单建议保持"跳过"，
                      避免重复发送工单信息；补发会走完整推送判定（范围/场景开关/推送条件/去重），
                      已发送过的工单不会重复发。
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="回帖模板">
                    <el-input
                      v-model="form.groupPush.aiResultFollowUp.template"
                      type="textarea"
                      :rows="5"
                      :disabled="form.groupPush.sendMode === 'push_config'"
                      placeholder="留空使用默认模板。可用变量：${ticket_no} ${ticket_title} ${ticket_url} ${ai_status_label} ${analysis_summary} ${root_cause} ${fix_suggestion} ${confidence} ${related_files} ${evidence} ${risk_items} ${next_steps} ${ai_error_message}"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>旁路 · 工单知识提炼</span>
                <el-tag type="info" effect="plain">关闭或手动提炼时执行</el-tag>
              </div>
            </template>

            <el-form :model="form.knowledgeConfig" label-width="150px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="启用知识提炼">
                    <el-switch
                      v-model="form.knowledgeConfig.enabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="Provider 编码">
                    <el-select
                      v-model="form.knowledgeConfig.providerCode"
                      placeholder="请选择知识提炼 Provider"
                      filterable
                      clearable
                      style="width: 100%"
                      @change="handleProviderModelChange('knowledgeConfig', $event)"
                    >
                      <el-option
                        v-for="item in lightProviderOptions"
                        :key="item.providerCode"
                        :label="formatProviderOptionLabel(item)"
                        :value="item.providerCode"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="模型">
                    <el-select
                      v-model="form.knowledgeConfig.modelName"
                      placeholder="留空使用Provider默认模型"
                      filterable
                      clearable
                      style="width: 100%"
                      :disabled="!form.knowledgeConfig.providerCode"
                    >
                      <el-option
                        v-for="item in lightModelOptionsMap[form.knowledgeConfig.providerCode] ||
                        []"
                        :key="item.modelId"
                        :label="item.displayName || item.modelId"
                        :value="item.modelId"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="提示词编码">
                    <el-select
                      v-model="form.knowledgeConfig.promptCode"
                      placeholder="请选择知识提炼提示词"
                      filterable
                      clearable
                      style="width: 100%"
                    >
                      <el-option
                        v-for="item in promptOptions"
                        :key="item.templateCode || item.value"
                        :label="formatPromptOptionLabel(item)"
                        :value="item.templateCode || item.value"
                      />
                    </el-select>
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
        <el-tab-pane label="来源与拉取" lazy>
          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>飞书统一凭证</span>
                <el-tag type="info" effect="plain">统一凭证基座（appId/appSecret）</el-tag>
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
                <span>连接解析预览</span>
                <el-tag type="info" effect="plain">只读：展示各使用方实际生效的连接配置</el-tag>
              </div>
            </template>
            <el-alert
              type="info"
              show-icon
              :closable="false"
              title="解析顺序：模块自身配置 → 多维表格公共配置 → 统一凭证"
              description="下表为实时解析结果；留空的覆盖字段不会覆盖继承值。修改请在各模块卡片的「连接与凭证覆盖」中填写，公共默认值在上方「多维表格公共配置」维护。"
            />
            <el-table
              :data="connectionPreviewRows"
              border
              size="small"
              class="connection-preview-table mt8"
            >
              <el-table-column label="使用方" min-width="180">
                <template #default="{ row }">{{ row.name }}</template>
              </el-table-column>
              <el-table-column label="appId" min-width="220">
                <template #default="{ row }">
                  <div class="connection-preview-cell">{{ row.appId.value }}</div>
                  <el-tag size="small" type="info" effect="plain">{{ row.appId.source }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="appToken" min-width="220">
                <template #default="{ row }">
                  <div class="connection-preview-cell">{{ row.appToken.value }}</div>
                  <el-tag size="small" type="info" effect="plain">{{ row.appToken.source }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="tableId" min-width="220">
                <template #default="{ row }">
                  <div class="connection-preview-cell">{{ row.tableId.value }}</div>
                  <el-tag size="small" type="info" effect="plain">{{ row.tableId.source }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>远端同步链接</span>
                <el-tag type="warning" effect="plain">内网定时拉取公网工单的连接配置</el-tag>
              </div>
            </template>

            <el-form
              ref="remoteFormRef"
              :model="form.remoteSync"
              :rules="remoteRules"
              label-width="150px"
            >
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="启用远端同步" prop="enabled">
                    <el-switch
                      v-model="form.remoteSync.enabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="抓取超时(秒)" prop="timeoutSec">
                    <el-input-number
                      v-model="form.remoteSync.timeoutSec"
                      :min="10"
                      :max="300"
                      :step="5"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="拉取地址" prop="pullUrl">
                    <el-input
                      v-model="form.remoteSync.pullUrl"
                      placeholder="https://example.com/api/tickets/pending"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="回写地址" prop="ackUrl">
                    <el-input
                      v-model="form.remoteSync.ackUrl"
                      placeholder="https://example.com/api/tickets/ack"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="消费者标识" prop="consumer">
                    <el-input
                      v-model="form.remoteSync.consumer"
                      placeholder="例如 public-ticket-sync"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="每次拉取数量" prop="limit">
                    <el-input-number
                      v-model="form.remoteSync.limit"
                      :min="1"
                      :max="200"
                      :step="1"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="包含已关闭" prop="includeClosed">
                    <el-switch
                      v-model="form.remoteSync.includeClosed"
                      inline-prompt
                      active-text="是"
                      inactive-text="否"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="凭证绑定">
                    <el-select
                      v-model="form.remoteSync.credentialBindingId"
                      filterable
                      clearable
                      style="width: 100%"
                      placeholder="选择远端同步 API Key 绑定"
                    >
                      <el-option
                        v-for="item in remoteCredentialOptions"
                        :key="item.bindingId"
                        :label="`${item.bindingName} / ${item.credentialName}`"
                        :value="item.bindingId"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="24"
                  ><el-form-item label="Origin（可选）"
                    ><el-input
                      v-model="form.remoteSync.origin"
                      placeholder="仅填写非敏感 Origin 请求头" /></el-form-item
                ></el-col>
              </el-row>
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>飞书多维表格主动拉取</span>
                <el-tag type="warning" effect="plain">定时调度、过滤条件与字段映射</el-tag>
              </div>
            </template>

            <el-form :model="form.bitablePull" label-width="150px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="启用主动拉取">
                    <el-switch
                      v-model="form.bitablePull.enabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="来源系统标识">
                    <el-input
                      v-model="form.bitablePull.sourceSystem"
                      placeholder="如 feishu_bitable_pull"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="分页大小">
                    <el-input-number
                      v-model="form.bitablePull.pageSize"
                      :min="1"
                      :max="500"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-collapse class="override-collapse">
                    <el-collapse-item name="connection">
                      <template #title>
                        <span class="override-collapse__title">连接与过滤覆盖（可选）</span>
                        <span class="override-collapse__hint"
                          >appToken / tableId / viewId / 过滤条件留空时依次继承：本模块 →
                          多维表格公共配置；实际生效值见「连接解析预览」</span
                        >
                      </template>
                      <el-row :gutter="16">
                        <el-col :xs="24" :md="12">
                          <el-form-item label="多维 appToken">
                            <el-input
                              v-model="form.bitablePull.appToken"
                              placeholder="为空继承公共配置"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col :xs="24" :md="12">
                          <el-form-item label="多维 tableId">
                            <el-input
                              v-model="form.bitablePull.tableId"
                              placeholder="为空继承公共配置"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col :xs="24" :md="12">
                          <el-form-item label="多维 viewId">
                            <el-input
                              v-model="form.bitablePull.viewId"
                              placeholder="为空继承公共配置"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col :span="24">
                          <el-form-item label="过滤条件JSON">
                            <el-input
                              v-model="form.bitablePull.filterFormula"
                              type="textarea"
                              :rows="3"
                              placeholder='可选；任务参数未覆盖时按此条件主动查询，如 {"conjunction":"and","conditions":[{"field_name":"(RD)工單狀態","operator":"contains","value":["3. 待产研处理"]}]}'
                            />
                          </el-form-item>
                        </el-col>
                      </el-row>
                    </el-collapse-item>
                  </el-collapse>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="工单号字段">
                    <el-input
                      v-model="form.bitablePull.ticketNoField"
                      placeholder="用于说明，多数情况由字段映射给 ticketNo"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="更新时间字段">
                    <el-input
                      v-model="form.bitablePull.updatedAtField"
                      placeholder="如 更新时间；默认时间窗口过滤字段之一"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="排序字段">
                    <el-input
                      v-model="form.bitablePull.sortField"
                      placeholder="预留；当前仅保存说明"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="写入记录链接">
                    <el-switch
                      v-model="form.bitablePull.includeRecordUrl"
                      inline-prompt
                      active-text="是"
                      inactive-text="否"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="强制同步">
                    <el-switch
                      v-model="form.bitablePull.forceSync"
                      inline-prompt
                      active-text="是"
                      inactive-text="否"
                    />
                    <div class="switch-inline-desc__text">
                      开启后忽略本地快照去重，重新拉取远端数据入库并触发后处理
                    </div>
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="字段映射">
                    <div class="mapping-desc mb8">
                      "多维字段"支持下拉选择或手动输入。点击"读取表格字段"会按当前多维配置读取字段元数据，不受主动拉取过滤条件和时间窗口影响。
                    </div>
                    <div class="mb8">
                      <el-button
                        size="small"
                        :loading="bitablePullFieldsLoading"
                        @click="handlePreviewBitablePullFields"
                      >
                        读取表格字段
                      </el-button>
                      <span
                        v-if="bitablePullFieldOptions.length"
                        class="mapping-desc"
                        style="margin-left: 12px"
                      >
                        已读取 {{ bitablePullFieldOptions.length }} 个字段
                      </span>
                    </div>
                    <el-table :data="form.bitablePull.fieldMappings" border size="small">
                      <el-table-column label="多维字段" min-width="220">
                        <template #default="scope">
                          <el-select
                            v-model="scope.row.sourceField"
                            filterable
                            allow-create
                            default-first-option
                            style="width: 100%"
                            placeholder="选择表格字段或手动输入"
                            @visible-change="handleBitablePullFieldSelectVisibleChange"
                          >
                            <el-option
                              v-for="item in bitablePullFieldOptions"
                              :key="`bitable-source-field-${item}`"
                              :label="item"
                              :value="item"
                            />
                          </el-select>
                        </template>
                      </el-table-column>
                      <el-table-column label="接口字段" min-width="220">
                        <template #default="scope">
                          <el-select
                            v-model="scope.row.targetField"
                            filterable
                            allow-create
                            default-first-option
                            style="width: 100%"
                            placeholder="选择外部字段模型中的字段"
                          >
                            <el-option
                              v-for="item in externalFieldModelOptions"
                              :key="`bitable-pull-field-${item.value}`"
                              :label="item.label"
                              :value="item.value"
                            />
                          </el-select>
                        </template>
                      </el-table-column>
                      <el-table-column label="默认值" min-width="180">
                        <template #default="scope">
                          <el-input
                            v-model="scope.row.defaultValue"
                            placeholder="为空时可回填默认值"
                          />
                        </template>
                      </el-table-column>
                      <el-table-column label="多值分隔符" width="120">
                        <template #default="scope">
                          <el-input v-model="scope.row.joinSeparator" placeholder="," />
                        </template>
                      </el-table-column>
                      <el-table-column label="操作" width="80" align="center">
                        <template #default="scope">
                          <el-button
                            link
                            type="danger"
                            icon="Delete"
                            @click="removeBitablePullFieldMapping(scope.$index)"
                          />
                        </template>
                      </el-table-column>
                    </el-table>
                    <div class="mt8">
                      <el-button type="primary" link icon="Plus" @click="addBitablePullFieldMapping"
                        >新增映射</el-button
                      >
                    </div>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>外部推送多维表格邮箱补全</span>
                <el-tag type="warning" effect="plain">外部推送记录邮箱补全</el-tag>
              </div>
            </template>

            <el-form :model="form.externalSyncBitable" label-width="150px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="启用邮箱补全">
                    <el-switch
                      v-model="form.externalSyncBitable.enabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-collapse class="override-collapse">
                    <el-collapse-item name="connection">
                      <template #title>
                        <span class="override-collapse__title">连接与凭证覆盖（可选）</span>
                        <span class="override-collapse__hint"
                          >留空时依次继承：本模块 → 多维表格公共配置 →
                          统一凭证；实际生效值见「连接解析预览」</span
                        >
                      </template>
                      <el-row :gutter="16">
                        <el-col :xs="24" :md="12">
                          <el-form-item label="多维 appToken">
                            <el-input
                              v-model="form.externalSyncBitable.appToken"
                              placeholder="飞书多维表格应用 Token"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col :xs="24" :md="12">
                          <el-form-item label="多维 tableId">
                            <el-input
                              v-model="form.externalSyncBitable.tableId"
                              placeholder="飞书多维表格表ID"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col :xs="24" :md="12">
                          <el-form-item label="多维 viewId">
                            <el-input
                              v-model="form.externalSyncBitable.viewId"
                              placeholder="可选，不填默认表视图"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col :xs="24" :md="12">
                          <el-form-item label="飞书 appId">
                            <el-input
                              v-model="form.externalSyncBitable.appId"
                              placeholder="覆盖统一凭证（可选）"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col :xs="24" :md="12">
                          <el-form-item label="飞书 appSecret">
                            <el-input
                              v-model="form.externalSyncBitable.appSecret"
                              show-password
                              placeholder="覆盖统一凭证（可选）"
                            />
                          </el-form-item>
                        </el-col>
                      </el-row>
                    </el-collapse-item>
                  </el-collapse>
                </el-col>
                <el-col :span="24">
                  <div class="mapping-desc">
                    外部推送传入的 <code>recordId</code> 会作为飞书多维表格记录ID查询固定字段：
                    <code>(IT) L1 PIC</code>、<code>1.5 当前负责人</code>、<code>当前负责人</code>。
                    当前块未填写的多维凭证会继承"多维表格公共配置"。
                  </div>
                </el-col>
              </el-row>
            </el-form>
          </el-card>
        </el-tab-pane>
        <el-tab-pane label="评论同步" lazy>
          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>工单评论同步</span>
                <el-tag type="warning" effect="plain">默认关闭</el-tag>
              </div>
            </template>

            <el-form :model="form.messageSync" label-width="170px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="启用评论同步">
                    <el-switch
                      v-model="form.messageSync.enabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="Webhook 入站">
                    <el-switch
                      v-model="form.messageSync.feishuEventEnabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="长连接入站">
                    <el-switch
                      v-model="form.messageSync.feishuWsEnabled"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="长连接 Token">
                    <el-input
                      v-model="form.messageSync.feishuWsVerificationToken"
                      placeholder="飞书事件订阅 Verification Token，可空"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="长连接 Encrypt Key">
                    <el-input
                      v-model="form.messageSync.feishuWsEncryptKey"
                      placeholder="飞书事件订阅 Encrypt Key，可空"
                      show-password
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="允许群 chat_id">
                    <el-select
                      v-model="form.messageSync.allowedChatIds"
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      placeholder="留空表示不限制群"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="忽略机器人 open_id">
                    <el-select
                      v-model="form.messageSync.ignoreBotOpenIds"
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      placeholder="用于避免机器人自发消息回流"
                      style="width: 100%"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="飞书评论写入工单">
                    <el-switch
                      v-model="form.messageSync.syncFeishuCommentToTicket"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="飞书评论写入多维">
                    <el-switch
                      v-model="form.messageSync.syncFeishuCommentToBitable"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="系统评论写入多维">
                    <el-switch
                      v-model="form.messageSync.syncTicketCommentToBitable"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="系统评论发到话题">
                    <el-switch
                      v-model="form.messageSync.syncTicketCommentToFeishuThread"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="多维新增同步话题">
                    <el-switch
                      v-model="form.messageSync.syncBitableNewStepToFeishuThread"
                      inline-prompt
                      active-text="开"
                      inactive-text="关"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="排查过程字段">
                    <el-input
                      v-model="form.messageSync.bitableStepReasonField"
                      placeholder="默认 stepReason"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="工单号字段">
                    <el-input
                      v-model="form.messageSync.bitableTicketNoField"
                      placeholder="默认 ticketNo"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="24">
                  <el-form-item label="追加格式">
                    <el-input
                      v-model="form.messageSync.appendStepReasonFormat"
                      placeholder="{date} {user}：{content}"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </el-card>
        </el-tab-pane>
        <el-tab-pane label="通知任务" lazy>
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
                <el-col :span="24">
                  <el-collapse class="override-collapse">
                    <el-collapse-item name="connection">
                      <template #title>
                        <span class="override-collapse__title"
                          >多维表格连接与字段覆盖（数据源=多维表格时）</span
                        >
                        <span class="override-collapse__hint"
                          >连接留空时依次继承：本模块 → 多维表格公共配置 →
                          统一凭证；实际生效值见「来源与拉取」页签的连接解析预览</span
                        >
                      </template>
                      <el-row :gutter="16">
                        <el-col
                          v-if="form.summaryReport.dataSource === 'bitable'"
                          :xs="24"
                          :md="12"
                        >
                          <el-form-item label="多维表格 appToken">
                            <el-input
                              v-model="form.summaryReport.appToken"
                              placeholder="飞书多维表格应用 Token"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col
                          v-if="form.summaryReport.dataSource === 'bitable'"
                          :xs="24"
                          :md="12"
                        >
                          <el-form-item label="多维表格 tableId">
                            <el-input
                              v-model="form.summaryReport.tableId"
                              placeholder="飞书多维表格表ID"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col
                          v-if="form.summaryReport.dataSource === 'bitable'"
                          :xs="24"
                          :md="12"
                        >
                          <el-form-item label="视图 viewId">
                            <el-input
                              v-model="form.summaryReport.viewId"
                              placeholder="可选，不填默认表视图"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col
                          v-if="form.summaryReport.dataSource === 'bitable'"
                          :xs="24"
                          :md="12"
                        >
                          <el-form-item label="多维时间字段">
                            <el-input
                              v-model="form.summaryReport.bitableTimeField"
                              placeholder="可选，不填回退记录创建时间"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="8">
                          <el-form-item label="状态字段">
                            <el-input
                              v-model="form.summaryReport.statusField"
                              placeholder="默认：状态"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col v-if="form.summaryReport.dataSource === 'bitable'" :xs="24" :md="8">
                          <el-form-item label="分类字段">
                            <el-input
                              v-model="form.summaryReport.categoryField"
                              placeholder="默认：分类"
                            />
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
                        <el-col
                          v-if="form.summaryReport.dataSource === 'bitable'"
                          :xs="24"
                          :md="12"
                        >
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
                      </el-row>
                    </el-collapse-item>
                  </el-collapse>
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
                    <el-select
                      v-model="form.summaryReport.aiProviderCode"
                      placeholder="请选择汇总解读 Provider"
                      filterable
                      clearable
                      style="width: 100%"
                      @change="handleProviderModelChange('summaryReport', $event)"
                    >
                      <el-option
                        v-for="item in lightProviderOptions"
                        :key="item.providerCode"
                        :label="formatProviderOptionLabel(item)"
                        :value="item.providerCode"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="AI模型">
                    <el-select
                      v-model="form.summaryReport.aiModelName"
                      placeholder="留空使用Provider默认模型"
                      filterable
                      clearable
                      style="width: 100%"
                      :disabled="!form.summaryReport.aiProviderCode"
                    >
                      <el-option
                        v-for="item in lightModelOptionsMap[form.summaryReport.aiProviderCode] ||
                        []"
                        :key="item.modelId"
                        :label="item.displayName || item.modelId"
                        :value="item.modelId"
                      />
                    </el-select>
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
                <el-col :span="24">
                  <el-collapse class="override-collapse">
                    <el-collapse-item name="connection">
                      <template #title>
                        <span class="override-collapse__title">连接与凭证覆盖（可选）</span>
                        <span class="override-collapse__hint"
                          >连接留空时依次继承：本模块 → 多维表格公共配置 →
                          统一凭证；实际生效值见「来源与拉取」页签的连接解析预览</span
                        >
                      </template>
                      <el-row :gutter="16">
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
                        <el-col
                          v-if="form.personReminder.dataSource === 'bitable'"
                          :xs="24"
                          :md="12"
                        >
                          <el-form-item label="多维表格 appToken">
                            <el-input
                              v-model="form.personReminder.appToken"
                              placeholder="飞书多维表格应用 Token"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col
                          v-if="form.personReminder.dataSource === 'bitable'"
                          :xs="24"
                          :md="12"
                        >
                          <el-form-item label="多维表格 tableId">
                            <el-input
                              v-model="form.personReminder.tableId"
                              placeholder="飞书多维表格表ID"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col
                          v-if="form.personReminder.dataSource === 'bitable'"
                          :xs="24"
                          :md="12"
                        >
                          <el-form-item label="视图 viewId">
                            <el-input
                              v-model="form.personReminder.viewId"
                              placeholder="可选，不填默认表视图"
                            />
                          </el-form-item>
                        </el-col>
                        <el-col
                          v-if="form.personReminder.dataSource === 'bitable'"
                          :xs="24"
                          :md="12"
                        >
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
                      </el-row>
                    </el-collapse-item>
                  </el-collapse>
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
        </el-tab-pane>
        <el-tab-pane label="统计与分类" lazy>
          <el-alert
            title="统计结果不写入快照表。任务运行时按当前工单数据聚合；同一历史区间在工单后续状态变化后可能得到不同结果。"
            type="warning"
            show-icon
            :closable="false"
          />

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
            <el-divider />
            <section class="stat-config-section stat-config-section--wide">
              <div class="stat-config-section__head"><span>允许用于自定义统计的字段</span></div>
              <el-checkbox-group v-model="form.statisticFieldKeys">
                <el-checkbox
                  v-for="field in allStatisticFieldOptions"
                  :key="field.value"
                  :label="field.value"
                  >{{ field.label }}</el-checkbox
                >
              </el-checkbox-group>
            </section>
            <el-divider />
            <section class="stat-config-section stat-config-section--wide">
              <div class="stat-config-section__head">
                <span>外部字段工单类型映射</span
                ><el-button
                  link
                  type="primary"
                  icon="Plus"
                  @click="addExternalClassificationMapping"
                  >新增</el-button
                >
              </div>
              <el-table :data="form.externalClassificationMappings" border size="small">
                <el-table-column label="接口字段" min-width="160"
                  ><template #default="scope"
                    ><el-select
                      v-model="scope.row.sourceField"
                      filterable
                      allow-create
                      default-first-option
                      placeholder="如 externalCategory"
                      ><el-option
                        v-for="field in form.externalFieldModel.fields"
                        :key="field.fieldName"
                        :label="`${field.fieldName} - ${field.label}`"
                        :value="field.fieldName" /></el-select></template
                ></el-table-column>
                <el-table-column label="规则" width="120"
                  ><template #default="scope"
                    ><el-select v-model="scope.row.operator"
                      ><el-option label="等于" value="equals" /><el-option
                        label="包含"
                        value="contains" /><el-option label="属于" value="in" /><el-option
                        label="正则"
                        value="regex" /></el-select></template
                ></el-table-column>
                <el-table-column label="匹配值" min-width="200"
                  ><template #default="scope"
                    ><el-select
                      v-model="scope.row.matchValues"
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      placeholder="输入后回车"
                      style="width: 100%" /></template
                ></el-table-column>
                <el-table-column label="工单类型" min-width="170"
                  ><template #default="scope"
                    ><el-select v-model="scope.row.issueTypeId" filterable
                      ><el-option
                        v-for="item in form.statClassification.issueTypes"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value" /></el-select></template
                ></el-table-column>
                <el-table-column label="优先级" width="100"
                  ><template #default="scope"
                    ><el-input-number
                      v-model="scope.row.priority"
                      :min="0"
                      controls-position="right"
                      style="width: 100%" /></template
                ></el-table-column>
                <el-table-column label="启用" width="70"
                  ><template #default="scope"><el-switch v-model="scope.row.enabled" /></template
                ></el-table-column>
                <el-table-column label="操作" width="70"
                  ><template #default="scope"
                    ><el-button
                      link
                      type="danger"
                      icon="Delete"
                      @click="removeExternalClassificationMapping(scope.$index)" /></template
                ></el-table-column>
              </el-table>
            </section>
            <section class="stat-config-section stat-config-section--wide mt16">
              <div class="stat-config-section__head">
                <span>自定义趋势指标</span
                ><el-button link type="primary" icon="Plus" @click="addCustomTrendMetric"
                  >新增</el-button
                >
              </div>
              <el-card
                v-for="(metric, metricIndex) in form.customTrendMetrics"
                :key="metricIndex"
                shadow="never"
                class="mb16"
              >
                <el-row :gutter="12"
                  ><el-col :span="6"
                    ><el-input v-model="metric.metricCode" placeholder="指标编码" /></el-col
                  ><el-col :span="6"
                    ><el-input v-model="metric.label" placeholder="指标名称" /></el-col
                  ><el-col :span="5"
                    ><el-select v-model="metric.overlapMode"
                      ><el-option label="允许重叠" value="allow" /><el-option
                        label="互斥"
                        value="exclusive" /></el-select></el-col
                  ><el-col :span="3"><el-switch v-model="metric.enabled" /></el-col
                  ><el-col :span="4"
                    ><el-button link type="primary" @click="addCustomTrendMetricGroup(metric)"
                      >新增分组</el-button
                    ><el-button link type="danger" @click="removeCustomTrendMetric(metricIndex)"
                      >删除</el-button
                    ></el-col
                  ></el-row
                >
                <el-card
                  v-for="(group, groupIndex) in metric.groups"
                  :key="groupIndex"
                  shadow="never"
                  class="mt16"
                  ><el-row :gutter="8"
                    ><el-col :span="5"
                      ><el-input v-model="group.groupCode" placeholder="分组编码" /></el-col
                    ><el-col :span="5"
                      ><el-input v-model="group.label" placeholder="分组名称" /></el-col
                    ><el-col :span="4"
                      ><el-select v-model="group.conditionMode"
                        ><el-option label="全部满足" value="all" /><el-option
                          label="任一满足"
                          value="any" /></el-select></el-col
                    ><el-col :span="5"
                      ><el-button link type="primary" @click="addCustomTrendMetricCondition(group)"
                        >新增条件</el-button
                      ></el-col
                    ></el-row
                  ><el-row
                    v-for="(condition, conditionIndex) in group.conditions"
                    :key="conditionIndex"
                    :gutter="8"
                    class="mt16"
                    ><el-col :span="6"
                      ><el-select v-model="condition.sourceField"
                        ><el-option
                          v-for="field in statisticFieldOptions"
                          :key="field.value"
                          :label="field.label"
                          :value="field.value" /></el-select></el-col
                    ><el-col :span="5"
                      ><el-select v-model="condition.operator"
                        ><el-option label="等于" value="equals" /><el-option
                          label="包含"
                          value="contains" /><el-option label="属于" value="in" /><el-option
                          label="正则"
                          value="regex" /><el-option label="为空" value="is_empty" /><el-option
                          label="不为空"
                          value="is_not_empty" /></el-select></el-col
                    ><el-col :span="10"
                      ><el-select
                        v-if="!isCustomTrendEmptyOperator(condition.operator)"
                        v-model="condition.matchValues"
                        multiple
                        filterable
                        allow-create
                        default-first-option
                        placeholder="输入后回车"
                        style="width: 100%"
                        ><el-option
                          v-for="item in getCustomTrendConditionValueOptions(condition.sourceField)"
                          :key="item.value"
                          :label="item.label"
                          :value="item.value" /></el-select
                      ><span v-else class="text-muted">无需填写匹配值</span></el-col
                    ><el-col :span="3"
                      ><el-button
                        link
                        type="danger"
                        @click="group.conditions.splice(conditionIndex, 1)"
                        >删除</el-button
                      ></el-col
                    ></el-row
                  ></el-card
                >
              </el-card>
            </section>
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>当前系统工单统计方案</span>
                <el-button link type="primary" icon="Plus" @click="addCustomStatisticsProfile"
                  >新增方案</el-button
                >
              </div>
            </template>
            <el-card
              v-for="(profile, profileIndex) in form.customStatisticsProfiles"
              :key="profileIndex"
              shadow="never"
              class="mb16"
            >
              <template #header>
                <div class="card-header">
                  <span>{{
                    profile.label || profile.profileCode || `方案 ${profileIndex + 1}`
                  }}</span>
                  <el-space>
                    <el-switch v-model="profile.enabled" active-text="启用" inactive-text="停用" />
                    <el-button
                      link
                      type="danger"
                      @click="removeCustomStatisticsProfile(profileIndex)"
                      >删除</el-button
                    >
                  </el-space>
                </div>
              </template>
              <el-row :gutter="16">
                <el-col :xs="24" :md="8"
                  ><el-form-item label="方案编码"
                    ><el-input
                      v-model="profile.profileCode"
                      placeholder="如 daily_coupon_conclusion" /></el-form-item
                ></el-col>
                <el-col :xs="24" :md="8"
                  ><el-form-item label="方案名称"
                    ><el-input
                      v-model="profile.label"
                      placeholder="如 券模块今日结论统计" /></el-form-item
                ></el-col>
                <el-col :xs="24" :md="8"
                  ><el-form-item label="统计时间字段"
                    ><el-select v-model="profile.timeField" style="width: 100%"
                      ><el-option
                        v-for="field in customStatisticsTimeFields"
                        :key="field.value"
                        :label="field.label"
                        :value="field.value" /></el-select></el-form-item
                ></el-col>
                <el-col :xs="24" :md="8"
                  ><el-form-item label="时间范围"
                    ><el-select v-model="profile.timeRange.mode" style="width: 100%"
                      ><el-option label="今天（截至执行时刻）" value="today" /><el-option
                        label="昨天（完整自然日）"
                        value="yesterday" /><el-option
                        label="最近 N 天"
                        value="rolling_days" /><el-option
                        label="本周（周一开始）"
                        value="current_week" /><el-option
                        label="上周（完整自然周）"
                        value="previous_week" /><el-option
                        label="自定义固定范围"
                        value="custom" /></el-select></el-form-item
                ></el-col>
                <el-col v-if="profile.timeRange.mode === 'rolling_days'" :xs="24" :md="8"
                  ><el-form-item label="最近天数"
                    ><el-input-number
                      v-model="profile.timeRange.rollingDays"
                      :min="1"
                      :max="90"
                      style="width: 100%" /></el-form-item
                ></el-col>
                <el-col v-if="profile.timeRange.mode === 'custom'" :xs="24" :md="8"
                  ><el-form-item label="开始时间"
                    ><el-date-picker
                      v-model="profile.timeRange.startTime"
                      type="datetime"
                      value-format="YYYY-MM-DDTHH:mm:ss"
                      style="width: 100%" /></el-form-item
                ></el-col>
                <el-col v-if="profile.timeRange.mode === 'custom'" :xs="24" :md="8"
                  ><el-form-item label="结束时间"
                    ><el-date-picker
                      v-model="profile.timeRange.endTime"
                      type="datetime"
                      value-format="YYYY-MM-DDTHH:mm:ss"
                      style="width: 100%" /></el-form-item
                ></el-col>
              </el-row>
              <el-divider content-position="left">统计范围</el-divider>
              <el-row :gutter="16">
                <el-col :xs="24" :md="12"
                  ><el-form-item label="项目 ID"
                    ><el-select
                      v-model="profile.scope.projectIds"
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      placeholder="输入 ID 后回车"
                      style="width: 100%" /></el-form-item
                ></el-col>
                <el-col :xs="24" :md="12"
                  ><el-form-item label="模块 ID"
                    ><el-select
                      v-model="profile.scope.moduleIds"
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      placeholder="输入 ID 后回车"
                      style="width: 100%" /></el-form-item
                ></el-col>
                <el-col :xs="24" :md="12"
                  ><el-form-item label="模块编码"
                    ><el-select
                      v-model="profile.scope.moduleCodes"
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      placeholder="如 coupon，输入后回车"
                      style="width: 100%" /></el-form-item
                ></el-col>
                <el-col :xs="24" :md="12"
                  ><el-form-item label="工单类型"
                    ><el-select
                      v-model="profile.scope.issueTypeIds"
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      style="width: 100%"
                      ><el-option
                        v-for="item in form.statClassification.issueTypes"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value" /></el-select></el-form-item
                ></el-col>
              </el-row>
              <el-divider content-position="left">分组规则</el-divider>
              <el-row :gutter="16">
                <el-col :xs="24" :md="8"
                  ><el-form-item label="分组方式"
                    ><el-select v-model="profile.grouping.mode" style="width: 100%"
                      ><el-option label="按字段原值分组" value="field" /><el-option
                        label="按条件规则归类"
                        value="rules" /></el-select></el-form-item
                ></el-col>
                <el-col v-if="profile.grouping.mode === 'field'" :xs="24" :md="8"
                  ><el-form-item label="分组字段"
                    ><el-select v-model="profile.grouping.sourceField" style="width: 100%"
                      ><el-option
                        v-for="field in customStatisticsFields"
                        :key="field.value"
                        :label="field.label"
                        :value="field.value" /></el-select></el-form-item
                ></el-col>
                <el-col v-if="profile.grouping.mode === 'rules'" :xs="24" :md="8"
                  ><el-form-item label="重叠规则"
                    ><el-select v-model="profile.grouping.overlapMode" style="width: 100%"
                      ><el-option label="允许同时归入多个分组" value="allow" /><el-option
                        label="仅命中最高优先级分组"
                        value="exclusive" /></el-select></el-form-item
                ></el-col>
                <el-col v-if="profile.grouping.mode === 'rules'" :xs="24" :md="8"
                  ><el-form-item label="未命中"
                    ><el-switch
                      v-model="profile.grouping.includeUnmatched"
                      active-text="归入未归类"
                      inactive-text="不计入分组" /></el-form-item
                ></el-col>
              </el-row>
              <template v-if="profile.grouping.mode === 'rules'">
                <el-button
                  link
                  type="primary"
                  icon="Plus"
                  @click="addCustomStatisticsGroup(profile)"
                  >新增规则分组</el-button
                >
                <el-card
                  v-for="(group, groupIndex) in profile.grouping.groups"
                  :key="groupIndex"
                  shadow="never"
                  class="mt16"
                >
                  <el-row :gutter="12"
                    ><el-col :xs="24" :md="5"
                      ><el-input v-model="group.groupCode" placeholder="分组编码" /></el-col
                    ><el-col :xs="24" :md="5"
                      ><el-input v-model="group.label" placeholder="分组名称" /></el-col
                    ><el-col :xs="24" :md="4"
                      ><el-input-number
                        v-model="group.priority"
                        :min="0"
                        style="width: 100%" /></el-col
                    ><el-col :xs="24" :md="4"
                      ><el-select v-model="group.conditionMode" style="width: 100%"
                        ><el-option label="全部满足" value="all" /><el-option
                          label="任一满足"
                          value="any" /></el-select></el-col
                    ><el-col :xs="24" :md="6"
                      ><el-button link type="primary" @click="addCustomStatisticsCondition(group)"
                        >新增条件</el-button
                      ><el-button
                        link
                        type="danger"
                        @click="profile.grouping.groups.splice(groupIndex, 1)"
                        >删除分组</el-button
                      ></el-col
                    ></el-row
                  >
                  <el-row
                    v-for="(condition, conditionIndex) in group.conditions"
                    :key="conditionIndex"
                    :gutter="12"
                    class="mt16"
                    ><el-col :xs="24" :md="6"
                      ><el-select v-model="condition.sourceField" style="width: 100%"
                        ><el-option
                          v-for="field in customStatisticsFields"
                          :key="field.value"
                          :label="field.label"
                          :value="field.value" /></el-select></el-col
                    ><el-col :xs="24" :md="5"
                      ><el-select v-model="condition.operator" style="width: 100%"
                        ><el-option label="等于" value="equals" /><el-option
                          label="包含"
                          value="contains" /><el-option label="属于" value="in" /><el-option
                          label="正则"
                          value="regex" /><el-option label="为空" value="is_empty" /><el-option
                          label="不为空"
                          value="is_not_empty" /></el-select></el-col
                    ><el-col :xs="24" :md="10"
                      ><el-select
                        v-if="!isCustomTrendEmptyOperator(condition.operator)"
                        v-model="condition.matchValues"
                        multiple
                        filterable
                        allow-create
                        default-first-option
                        placeholder="输入后回车"
                        style="width: 100%"
                      /><span v-else class="text-muted">无需填写匹配值</span></el-col
                    ><el-col :xs="24" :md="3"
                      ><el-button
                        link
                        type="danger"
                        @click="group.conditions.splice(conditionIndex, 1)"
                        >删除</el-button
                      ></el-col
                    ></el-row
                  >
                </el-card>
              </template>
              <el-divider content-position="left">通知</el-divider>
              <el-row :gutter="16"
                ><el-col :xs="24" :md="8"
                  ><el-form-item label="发送通知"
                    ><el-switch v-model="profile.notification.enabled" /></el-form-item></el-col
                ><el-col v-if="profile.notification.enabled" :xs="24" :md="8"
                  ><el-form-item label="发送渠道"
                    ><el-select v-model="profile.notification.sendMode" style="width: 100%"
                      ><el-option
                        v-for="item in notifySendModes"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value" /></el-select></el-form-item></el-col
                ><el-col v-if="profile.notification.enabled" :xs="24" :md="8"
                  ><el-form-item label="通知格式"
                    ><el-select v-model="profile.notification.messageFormat" style="width: 100%"
                      ><el-option label="文本模板" value="text" /><el-option
                        label="飞书卡片（飞书渠道）"
                        value="feishu_card" /></el-select></el-form-item></el-col
              ></el-row>
              <el-row v-if="profile.notification.enabled" :gutter="16"
                ><el-col v-if="profile.notification.sendMode !== 'feishu_app'" :xs="24" :md="12"
                  ><el-form-item label="推送配置"
                    ><el-select
                      v-model="profile.notification.pushIds"
                      multiple
                      filterable
                      style="width: 100%"
                      ><el-option
                        v-for="item in pushOptions"
                        :key="item.pushId || item.value"
                        :label="item.pushName || item.label || item.name"
                        :value="item.pushId || item.value" /></el-select></el-form-item></el-col
                ><el-col v-if="profile.notification.sendMode !== 'push_config'" :xs="24" :md="12"
                  ><el-form-item label="飞书群 chat_id"
                    ><el-select
                      v-model="profile.notification.appChatIds"
                      multiple
                      filterable
                      allow-create
                      default-first-option
                      style="width: 100%" /></el-form-item></el-col
                ><el-col v-if="profile.notification.sendMode !== 'push_config'" :xs="24" :md="12"
                  ><el-form-item label="飞书 appId"
                    ><el-input v-model="profile.notification.appId" /></el-form-item></el-col
                ><el-col v-if="profile.notification.sendMode !== 'push_config'" :xs="24" :md="12"
                  ><el-form-item label="飞书 appSecret"
                    ><el-input
                      v-model="profile.notification.appSecret"
                      type="password"
                      show-password /></el-form-item></el-col
                ><el-col :span="24"
                  ><el-form-item label="消息模板"
                    ><el-input
                      v-model="profile.notification.messageTemplate"
                      type="textarea"
                      :rows="5"
                      placeholder="可用变量：${profile_label} ${start_time} ${end_time} ${time_field_label} ${total_count} ${group_summary} ${top_tickets} ${now_time}" /></el-form-item></el-col
                ><el-col :xs="24" :md="8"
                  ><el-form-item label="附带工单明细"
                    ><el-switch
                      v-model="profile.notification.includeTopTickets" /></el-form-item></el-col
                ><el-col v-if="profile.notification.includeTopTickets" :xs="24" :md="8"
                  ><el-form-item label="明细数量"
                    ><el-input-number
                      v-model="profile.notification.topTicketLimit"
                      :min="1"
                      :max="20"
                      style="width: 100%" /></el-form-item></el-col
              ></el-row>
            </el-card>
            <el-empty
              v-if="!form.customStatisticsProfiles.length"
              description="暂无统计方案，请新增后保存配置"
            />
          </el-card>
        </el-tab-pane>
        <el-tab-pane label="操作" lazy>
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
                  <el-divider content-position="left">自定义统计手动执行</el-divider>
                  <el-form-item label="统计方案">
                    <el-select
                      v-model="customStatisticsRunForm.profileCodes"
                      multiple
                      clearable
                      placeholder="留空执行全部启用方案"
                      style="width: 100%"
                    >
                      <el-option
                        v-for="profile in form.customStatisticsProfiles"
                        :key="profile.profileCode"
                        :label="profile.label || profile.profileCode"
                        :value="profile.profileCode"
                        :disabled="!profile.enabled || !profile.profileCode"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="发送通知">
                    <el-switch
                      v-model="customStatisticsRunForm.send"
                      active-text="按方案发送"
                      inactive-text="仅预览"
                    />
                  </el-form-item>
                  <el-form-item>
                    <el-button
                      type="primary"
                      :loading="customStatisticsRunLoading"
                      @click="handleRunCustomStatistics"
                      >执行自定义统计</el-button
                    >
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
            <el-alert
              v-for="item in customStatisticsRunResult"
              :key="item.profileCode"
              class="mt16"
              type="info"
              show-icon
              :closable="false"
              :title="`${item.profileLabel}：工单 ${item.totalCount || 0} 条，${(item.groups || []).map((group) => `${group.label} ${group.count}`).join('；') || '无分组数据'}`"
            />
          </el-card>

          <el-card shadow="never" class="config-card mt16">
            <template #header>
              <div class="card-header">
                <span>指定工单手动自动化</span>
                <el-tag effect="plain">按工单号补跑多维表格拉取或数据库快照自动化</el-tag>
              </div>
            </template>
            <el-alert
              title="指定工单手动自动化"
              type="info"
              :closable="false"
              show-icon
              description="可在关闭定时主动拉取时补跑指定工单。查询多维表格模式仅按工单号查询，忽略主动拉取开关、常规过滤条件和时间窗口；数据库快照模式不覆盖工单字段，只重新执行后处理自动化。"
            />
            <el-form :model="manualAutomationForm" label-width="150px" style="margin-top: 16px">
              <el-row :gutter="16">
                <el-col :xs="24" :md="10">
                  <el-form-item label="工单号" required>
                    <el-input
                      v-model="manualAutomationForm.ticketNo"
                      clearable
                      placeholder="输入要补跑的精确工单号"
                      @keyup.enter="handleRunManualAutomation"
                    />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="10">
                  <el-form-item label="数据来源">
                    <el-radio-group v-model="manualAutomationForm.source">
                      <el-radio value="bitable">查询多维表格</el-radio>
                      <el-radio value="database">使用数据库快照</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="4">
                  <el-form-item label-width="0">
                    <el-button
                      type="primary"
                      :loading="manualAutomationLoading"
                      v-hasPermi="['ticket:sync:config:edit']"
                      @click="handleRunManualAutomation"
                    >
                      执行自动化
                    </el-button>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
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
                      <el-option label="映射归类" value="external_mapping" />
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
                <el-col v-if="autoCategoryForm.strategy === 'external_mapping'" :span="24">
                  <el-alert
                    title="映射归类会根据工单已保存的原始外部字段与“系统字段”中的工单类型映射规则重新匹配；不会调用 AI。人工确认的工单类型默认不会被覆盖。"
                    type="info"
                    show-icon
                    :closable="false"
                  />
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
    </div>

    <!-- ① 字段识别与映射设置弹窗：内容较多，收进弹窗维护；映射文本与正则跟随页面底部"保存配置"一起保存 -->
    <el-dialog
      v-model="mappingDialogVisible"
      title="① 字段识别与映射设置"
      width="80%"
      top="6vh"
      destroy-on-close
      class="config-dialog"
      append-to-body
    >
      <el-divider content-position="left">正则识别规则</el-divider>

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

      <el-divider content-position="left">映射配置（三方直推与内网拉取共用）</el-divider>

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
      <template #footer>
        <span class="config-dialog__tip">此处修改跟随页面底部「保存配置」一起生效</span>
        <el-button type="primary" @click="mappingDialogVisible = false">完成</el-button>
      </template>
    </el-dialog>

    <!-- ⑦ 日志拉取设置弹窗：拉日志默认值跟随主保存；存储与外部接口配置保持各自独立保存按钮 -->
    <el-dialog
      v-model="logPullDialogVisible"
      title="⑦ 日志拉取设置"
      width="80%"
      top="4vh"
      destroy-on-close
      class="config-dialog"
      append-to-body
    >
      <el-alert
        type="info"
        show-icon
        :closable="false"
        title="保存方式说明"
        description="「拉日志默认值」跟随页面底部「保存配置」一起保存；「存储与资源限制」和「日志拉取外部接口配置」相互独立，分别使用各自弹窗底部的保存按钮立即生效。"
      />
      <el-card shadow="never" class="config-card mt16">
        <template #header>
          <div class="card-header">
            <span>拉日志默认值</span>
            <el-tag type="info" effect="plain">提交参数默认值</el-tag>
          </div>
        </template>
        <el-form :model="form.logPullDefaults" label-width="150px">
          <el-row :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item label="默认日志环境">
                <el-select
                  v-model="form.logPullDefaults.environment"
                  filterable
                  clearable
                  placeholder="选择环境分组和子环境"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in logPullExternalEnvironmentOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
                <div class="form-tip">自动拉日志未单独指定环境时使用；格式为“分组:子环境”。</div>
              </el-form-item>
            </el-col>
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
            <el-col :span="24">
              <el-divider content-position="left">日志拉取后自动 AI 分析</el-divider>
              <div class="form-help-text form-help-text--section">
                这里控制自动日志拉取成功后的 AI 分析行为，手工 AI 分析不受这里影响。
              </div>
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
                <el-select
                  v-model="form.logPullDefaults.aiAgentCode"
                  placeholder="留空则走默认 Agent"
                  filterable
                  clearable
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in agentOptions"
                    :key="item.agentCode"
                    :label="`${item.agentName || item.agentCode} [${item.agentCode}]`"
                    :value="item.agentCode"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="Provider 编码">
                <el-select
                  v-model="form.logPullDefaults.aiProviderCode"
                  placeholder="留空则走默认 Provider"
                  filterable
                  clearable
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in analysisProviderOptions"
                    :key="item.providerCode"
                    :label="`${item.providerName || item.providerCode} [${item.providerCode}] ${item.defaultModel ? '- ' + item.defaultModel : ''}`"
                    :value="item.providerCode"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col v-if="form.logPullDefaults.autoAiEnabled" :xs="24" :md="12">
              <el-form-item label="历史分析条件">
                <el-radio-group v-model="form.logPullDefaults.autoAiAnalysisCondition.analysisMode">
                  <el-radio-button label="always">允许重复分析</el-radio-button>
                  <el-radio-button label="not_successful">仅无成功记录</el-radio-button>
                </el-radio-group>
              </el-form-item>
            </el-col>
            <el-col v-if="form.logPullDefaults.autoAiEnabled" :xs="24" :md="12">
              <el-form-item label="状态过滤">
                <el-switch
                  v-model="form.logPullDefaults.autoAiAnalysisCondition.statusFilterEnabled"
                  inline-prompt
                  active-text="开"
                  inactive-text="关"
                />
                <div class="form-help-text">仅自动分析受影响；手动分析不受影响</div>
              </el-form-item>
            </el-col>
            <el-col
              v-if="
                form.logPullDefaults.autoAiEnabled &&
                form.logPullDefaults.autoAiAnalysisCondition.statusFilterEnabled
              "
              :span="24"
            >
              <el-form-item label="允许的工单状态" required>
                <el-select
                  v-model="form.logPullDefaults.autoAiAnalysisCondition.statusCodes"
                  multiple
                  filterable
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="请选择内部工作流状态（多选）"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in workflowStatusOptions"
                    :key="`auto-ai-status-${item.value}`"
                    :label="`${item.label} [${item.value}]`"
                    :value="item.value"
                  />
                </el-select>
                <div class="form-help-text">
                  工单状态需先映射为内部状态；未满足条件时不会消耗 Token
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-divider content-position="left">自动拉日志停止条件</el-divider>
              <div class="form-help-text form-help-text--section">
                这里控制哪些内部状态命中后不再自动拉日志，只影响自动任务，不影响手工拉日志。
              </div>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="自动拉日志停止条件">
                <el-switch
                  v-model="form.logPullDefaults.autoLogPullStopCondition.enabled"
                  inline-prompt
                  active-text="开"
                  inactive-text="关"
                />
                <div class="form-help-text">仅影响自动拉日志；手工拉日志不受影响</div>
              </el-form-item>
            </el-col>
            <el-col v-if="form.logPullDefaults.autoLogPullStopCondition.enabled" :xs="24" :md="12">
              <el-form-item label="停止运行中自动任务">
                <el-switch
                  v-model="form.logPullDefaults.autoLogPullStopCondition.cancelActiveRecords"
                  inline-prompt
                  active-text="开"
                  inactive-text="关"
                />
                <div class="form-help-text">命中状态后可自动停止仍在执行中的自动日志任务</div>
              </el-form-item>
            </el-col>
            <el-col v-if="form.logPullDefaults.autoLogPullStopCondition.enabled" :span="24">
              <el-form-item label="停止状态（多选）" required>
                <el-select
                  v-model="form.logPullDefaults.autoLogPullStopCondition.statusCodes"
                  multiple
                  filterable
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="请选择命中后停止自动拉日志的内部工作流状态"
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in workflowStatusOptions"
                    :key="`auto-log-stop-status-${item.value}`"
                    :label="`${item.label} [${item.value}]`"
                    :value="item.value"
                  />
                </el-select>
                <div class="form-help-text">
                  命中任一状态即停止自动拉日志，并不再发送无意义的拉取失败通知
                </div>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>
      <el-card shadow="never" class="config-card mt16">
        <template #header>
          <div class="card-header">
            <span>存储与资源限制</span>
            <el-tag type="warning" effect="plain">运行态护栏</el-tag>
          </div>
        </template>
        <el-form :model="logPullStorage" label-width="170px">
          <el-row :gutter="16">
            <el-col :xs="24" :md="12">
              <el-form-item label="最大并发数">
                <el-input-number
                  v-model="logPullStorage.maxWorkers"
                  :min="1"
                  :max="20"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="轮询间隔(秒)">
                <el-input-number
                  v-model="logPullStorage.pollIntervalSec"
                  :min="3"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="轮询超时(秒)">
                <el-input-number
                  v-model="logPullStorage.pollTimeoutSec"
                  :min="60"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="下载超时(秒)">
                <el-input-number
                  v-model="logPullStorage.downloadTimeoutSec"
                  :min="30"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="入库字符上限">
                <el-input-number
                  v-model="logPullStorage.maxContentChars"
                  :min="10000"
                  :step="10000"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="解压时限(秒)">
                <el-input-number
                  v-model="logPullStorage.maxExtractSeconds"
                  :min="30"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="解压文件数上限">
                <el-input-number
                  v-model="logPullStorage.maxExtractFileCount"
                  :min="100"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="解压总字节上限">
                <el-input-number
                  v-model="logPullStorage.maxExtractTotalBytes"
                  :min="10485760"
                  :step="10485760"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="搜索时限(秒)">
                <el-input-number
                  v-model="logPullStorage.maxSearchSeconds"
                  :min="3"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="搜索文件数上限">
                <el-input-number
                  v-model="logPullStorage.maxSearchFileCount"
                  :min="10"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="降级搜索字节上限">
                <el-input-number
                  v-model="logPullStorage.maxPythonSearchBytes"
                  :min="10485760"
                  :step="10485760"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="搜索最大并发数">
                <el-input-number
                  v-model="logPullStorage.maxConcurrentSearches"
                  :min="1"
                  :max="8"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="搜索单行最大字节数">
                <el-input-number
                  v-model="logPullStorage.maxSearchLineBytes"
                  :min="256"
                  :max="4194304"
                  :step="65536"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="存储方式">
                <el-select v-model="logPullStorage.mode" placeholder="请选择" style="width: 100%">
                  <el-option label="本地" value="local" />
                  <el-option label="FTP" value="ftp" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12" v-if="logPullStorage.mode === 'local'">
              <el-form-item label="本地保存目录">
                <el-input
                  v-model="logPullStorage.localDirectory"
                  placeholder="留空则使用默认目录"
                />
              </el-form-item>
            </el-col>
            <el-col :span="24" v-if="logPullStorage.mode === 'ftp'">
              <el-form-item label="FTP 配置">
                <div class="ftp-config-grid">
                  <el-input v-model="logPullStorage.ftp.host" placeholder="主机" class="ftp-item" />
                  <el-input-number
                    v-model="logPullStorage.ftp.port"
                    :min="1"
                    placeholder="端口"
                    class="ftp-item"
                  />
                  <el-input
                    v-model="logPullStorage.ftp.username"
                    placeholder="用户名"
                    class="ftp-item"
                  />
                  <el-input
                    v-model="logPullStorage.ftp.password"
                    type="password"
                    show-password
                    placeholder="密码"
                    class="ftp-item"
                  />
                  <el-input
                    v-model="logPullStorage.ftp.baseDir"
                    placeholder="基础目录"
                    class="ftp-item"
                  />
                  <el-input-number
                    v-model="logPullStorage.ftp.timeoutSec"
                    :min="1"
                    placeholder="超时秒数"
                    class="ftp-item"
                  />
                  <el-input
                    v-model="logPullStorage.ftp.encoding"
                    placeholder="编码"
                    class="ftp-item"
                  />
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-divider content-position="left">下载完成后处理</el-divider>
            </el-col>
            <el-col :xs="24" :md="8">
              <el-form-item label="下载完成后解压">
                <el-switch
                  v-model="logPullStorage.postDownloadExtractEnabled"
                  inline-prompt
                  active-text="开"
                  inactive-text="关"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="8">
              <el-form-item label="下载完成后提取版本">
                <el-switch
                  v-model="logPullStorage.postDownloadVersionExtractEnabled"
                  :disabled="!logPullStorage.postDownloadExtractEnabled"
                  inline-prompt
                  active-text="开"
                  inactive-text="关"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="8">
              <el-form-item label="下载完成后生成索引">
                <el-switch
                  v-model="logPullStorage.postDownloadIndexEnabled"
                  :disabled="!logPullStorage.postDownloadExtractEnabled"
                  inline-prompt
                  active-text="开"
                  inactive-text="关"
                />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="版本提取正则">
                <el-input
                  v-model="logPullVersionExtractPatternsText"
                  type="textarea"
                  :rows="4"
                  placeholder='请输入 JSON 数组，例如 ["ms_h\\s*:\\s*\\d+\\s*,\\s*ms_l\\s*:\\s*\\d+[^,\\n]*,\\s*version\\s*[:=]\\s*(\\d+(?:\\.\\d+){2,3})"]'
                />
                <div class="form-help-text">
                  用于日志拉取成功后从日志正文提取应用版本号，按顺序取第一个命中；每个正则的第一个分组作为版本号。
                  默认锚定"ms_h:...version:"特征行，避免误提取 launcher_version（启动器版本）和 OpenGL
                  解析版本。清空数组或全部非法时回退内置默认正则；非法正则会被自动忽略。
                </div>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
        <div class="mt16">
          <el-button
            type="success"
            :loading="logPullStorageSaving"
            @click="logPullStorageHandleSave"
            >保存存储与资源限制</el-button
          >
        </div>
      </el-card>
      <el-card shadow="never" class="config-card mt16">
        <template #header>
          <div class="card-header">
            <span>日志拉取外部接口配置</span>
            <el-tag type="warning" effect="plain">环境分组 + 子环境 + 商家映射</el-tag>
          </div>
        </template>
        <el-alert
          class="mb16"
          title="配置说明"
          type="info"
          :closable="false"
          show-icon
          description="每个环境分组（如 prod、uat）下可配置多个子环境，每个子环境绑定独立凭证。商家选择后根据 vendorFilter 自动匹配子环境；「*」表示覆盖所有商家。未匹配到时可指定默认子环境兜底。"
        />
        <div v-loading="logPullExternalLoading" class="env-groups-container">
          <el-empty
            v-if="!logPullExternalGroupKeys.length && !logPullExternalLoading"
            description="暂无环境分组配置，请新增"
          />
          <div v-for="groupKey in logPullExternalGroupKeys" :key="groupKey" class="env-group-card">
            <div class="env-group-header">
              <el-input
                :model-value="logPullExternalGroups[groupKey].label"
                placeholder="分组名称，如 生产环境"
                style="width: 260px"
                @update:model-value="(val) => logPullExternalUpdateGroupLabel(groupKey, val)"
              />
              <el-tag type="info" size="small" class="ml8">{{ groupKey }}</el-tag>
              <div class="env-group-actions">
                <el-button
                  type="danger"
                  link
                  icon="Delete"
                  @click="logPullExternalRemoveGroup(groupKey)"
                  >删除分组</el-button
                >
              </div>
            </div>
            <el-table
              :data="Object.entries(logPullExternalGroups[groupKey].items)"
              border
              size="small"
              class="env-items-table"
            >
              <el-table-column label="子环境 key" width="130">
                <template #default="{ row }">
                  <el-tag size="small">{{ row[0] }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="名称" width="150">
                <template #default="{ row }">
                  <el-input
                    :model-value="row[1].label"
                    placeholder="UAT1"
                    size="small"
                    @update:model-value="
                      (val) => logPullExternalUpdateItemConfig(groupKey, row[0], 'label', val)
                    "
                  />
                </template>
              </el-table-column>
              <el-table-column label="insertUrl" min-width="200">
                <template #default="{ row }">
                  <el-input
                    :model-value="row[1].insertUrl"
                    placeholder="https://..."
                    size="small"
                    @update:model-value="
                      (val) => logPullExternalUpdateItemConfig(groupKey, row[0], 'insertUrl', val)
                    "
                  />
                </template>
              </el-table-column>
              <el-table-column label="pageUrl" min-width="200">
                <template #default="{ row }">
                  <el-input
                    :model-value="row[1].pageUrl"
                    placeholder="https://..."
                    size="small"
                    @update:model-value="
                      (val) => logPullExternalUpdateItemConfig(groupKey, row[0], 'pageUrl', val)
                    "
                  />
                </template>
              </el-table-column>
              <el-table-column label="凭证绑定" width="220">
                <template #default="{ row }">
                  <el-select
                    :model-value="row[1].credentialBindingId"
                    placeholder="选择凭证绑定"
                    filterable
                    clearable
                    size="small"
                    style="width: 100%"
                    @update:model-value="
                      (val) =>
                        logPullExternalUpdateItemConfig(
                          groupKey,
                          row[0],
                          'credentialBindingId',
                          val
                        )
                    "
                  >
                    <el-option
                      v-for="opt in logPullExternalCredentialBindingOptions"
                      :key="opt.bindingId"
                      :label="opt.label"
                      :value="String(opt.bindingId)"
                    />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="origin" min-width="200">
                <template #default="{ row }">
                  <el-input
                    :model-value="row[1].origin"
                    placeholder="https://..."
                    size="small"
                    @update:model-value="
                      (val) => logPullExternalUpdateItemConfig(groupKey, row[0], 'origin', val)
                    "
                  />
                </template>
              </el-table-column>
              <el-table-column label="商家范围" width="280">
                <template #default="{ row }">
                  <el-select
                    :model-value="row[1].vendorFilter"
                    multiple
                    filterable
                    collapse-tags
                    collapse-tags-tooltip
                    placeholder="选择商家（* 表示全部）"
                    size="small"
                    style="width: 100%"
                    @update:model-value="
                      (val) =>
                        logPullExternalUpdateItemConfig(groupKey, row[0], 'vendorFilter', val)
                    "
                  >
                    <el-option label="★ 全部商家" value="*" />
                    <el-option
                      v-for="opt in logPullExternalVendorFilterOptions"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                      :disabled="row[1].vendorFilter.includes('*')"
                    />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="70" align="center">
                <template #default="{ row }">
                  <el-button
                    link
                    type="danger"
                    icon="Delete"
                    size="small"
                    @click="logPullExternalRemoveEnvItem(groupKey, row[0])"
                  />
                </template>
              </el-table-column>
            </el-table>
            <div class="env-group-footer">
              <el-button
                type="primary"
                link
                icon="Plus"
                @click="logPullExternalAddEnvItem(groupKey)"
                >新增子环境</el-button
              >
              <el-form-item label="默认子环境" label-width="100px" class="env-default-item">
                <el-select
                  :model-value="logPullExternalGroups[groupKey].defaultItem"
                  placeholder="商家未匹配时兜底"
                  clearable
                  size="small"
                  style="width: 200px"
                  @update:model-value="
                    (val) => logPullExternalUpdateGroupDefaultItem(groupKey, val)
                  "
                >
                  <el-option
                    v-for="itemKey in logPullExternalGetItemKeysForGroup(groupKey)"
                    :key="itemKey"
                    :label="`${logPullExternalGroups[groupKey].items[itemKey]?.label || itemKey} (${itemKey})`"
                    :value="itemKey"
                  />
                </el-select>
              </el-form-item>
            </div>
          </div>
        </div>
        <div class="mt16">
          <el-button type="primary" icon="Plus" @click="logPullExternalAddGroup"
            >新增环境分组</el-button
          >
          <el-button
            type="success"
            :loading="logPullExternalSaving"
            @click="logPullExternalHandleSave"
            class="ml8"
            >保存外部接口配置</el-button
          >
        </div>
      </el-card>
      <template #footer>
        <el-button @click="logPullDialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存拉日志默认值</el-button>
      </template>
    </el-dialog>

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
    runTicketManualAutomation,
    runTicketSyncPersonReminder,
    runTicketSyncSummaryReport,
    runTicketCustomStatistics,
    sendTicketSyncGroupPushByTicket,
  } from '@/api/ticket/ticket';
  import { listAiProviderOptions, listAiProviderModelOptions } from '@/api/system/aiprovider';
  import { listAiPromptTemplateOptions } from '@/api/system/aiprompt';
  import { all as listAllAgents } from '@/api/hrm/agent';
  import { useSyncConfig } from './hooks/useSyncConfig';
  import { useLogPullExternalConfig } from './hooks/useLogPullExternalConfig';
  import { useLogPullStorageConfig } from './hooks/useLogPullStorageConfig';

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
    personDataSourceOptions,
    summaryDataSourceOptions,
    personLocalTimeFieldOptions,
    summaryTimeFieldOptions,
    externalFieldModelOptions,
    rules,
    remoteRules,
    remoteCredentialOptions,
    loadConfig,
    loadRemoteCredentialOptions,
    loadWorkflowStatuses,
    handleSave,
    addStatOption,
    removeStatOption,
    addExternalFieldModel,
    removeExternalFieldModel,
    addBitablePullFieldMapping,
    removeBitablePullFieldMapping,
    addExternalClassificationMapping,
    removeExternalClassificationMapping,
    addCustomTrendMetric,
    removeCustomTrendMetric,
    addCustomTrendMetricGroup,
    addCustomTrendMetricCondition,
    addCustomStatisticsProfile,
    removeCustomStatisticsProfile,
    addCustomStatisticsGroup,
    addCustomStatisticsCondition,
  } = useSyncConfig(proxy);

  // 日志拉取外部接口（环境分组+子环境+商家映射）配置管理
  const {
    loading: logPullExternalLoading,
    saving: logPullExternalSaving,
    groups: logPullExternalGroups,
    groupKeys: logPullExternalGroupKeys,
    environmentOptions: logPullExternalEnvironmentOptions,
    vendorFilterOptions: logPullExternalVendorFilterOptions,
    credentialBindingOptions: logPullExternalCredentialBindingOptions,
    loadConfig: logPullExternalLoadConfig,
    addGroup: logPullExternalAddGroup,
    removeGroup: logPullExternalRemoveGroup,
    addEnvItem: logPullExternalAddEnvItem,
    removeEnvItem: logPullExternalRemoveEnvItem,
    updateGroupLabel: logPullExternalUpdateGroupLabel,
    updateItemConfig: logPullExternalUpdateItemConfig,
    handleSave: logPullExternalHandleSave,
    getItemKeysForGroup: logPullExternalGetItemKeysForGroup,
  } = useLogPullExternalConfig(proxy);

  // 日志拉取存储与资源限制配置管理
  const {
    loading: logPullStorageLoading,
    saving: logPullStorageSaving,
    storage: logPullStorage,
    versionExtractPatternsText: logPullVersionExtractPatternsText,
    loadConfig: logPullStorageLoadConfig,
    handleSave: logPullStorageHandleSave,
  } = useLogPullStorageConfig(proxy);

  /**
   * 更新分组的 defaultItem。
   */
  function logPullExternalUpdateGroupDefaultItem(groupKey, val) {
    if (logPullExternalGroups[groupKey]) {
      logPullExternalGroups[groupKey].defaultItem = val || null;
    }
  }
  const allStatisticFieldOptions = [
    { value: 'issueTypeId', label: '工单类型' },
    { value: 'isProblem', label: '是否问题' },
    { value: 'status', label: '工单状态' },
    { value: 'source', label: '来源' },
    { value: 'rootCauseType', label: '根因分类' },
    { value: 'solutionType', label: '解决方式' },
    { value: 'resolutionCode', label: '关闭结果' },
    { value: 'internalPriority', label: '内部优先级' },
    { value: 'projectId', label: '项目' },
    { value: 'moduleId', label: '模块' },
  ];
  const customStatisticsFields = [
    ...allStatisticFieldOptions,
    { value: 'moduleName', label: '模块名称' },
    { value: 'problemPatternCode', label: '细分问题' },
    { value: 'processedAt', label: '形成结论时间' },
    { value: 'hasConclusion', label: '是否有结论（processedAt 不为空）' },
  ];
  const customStatisticsTimeFields = [
    { value: 'submitTime', label: '提交时间' },
    { value: 'createTime', label: '创建时间' },
    { value: 'firstResponseAt', label: '首次响应时间' },
    { value: 'processedAt', label: '形成结论时间' },
    { value: 'resolvedAt', label: '处置完成时间' },
    { value: 'closedAt', label: '关闭时间' },
  ];
  const statisticFieldOptions = computed(() =>
    allStatisticFieldOptions.filter((item) => form.statisticFieldKeys.includes(item.value))
  );
  function isCustomTrendEmptyOperator(operator) {
    return ['is_empty', 'is_not_empty'].includes(operator);
  }
  function getCustomTrendConditionValueOptions(sourceField) {
    if (sourceField !== 'issueTypeId') return [];
    return (form.statClassification.issueTypes || []).map((item) => ({
      value: item.value,
      label: item.label ? `${item.label} (${item.value})` : item.value,
    }));
  }
  // ===== 场景 × 步骤 开关总表 =====
  // 仅调整展示位置：字段与后端 ticket.sync.automation 的
  // aiSyncExtract / translateConfig / aiClassification / automationConfig / groupPush 配置键一一对应，不改存储结构。
  const sceneMatrixScenes = ['外部推送', '远端拉取', '多维表格拉取', '手动创建'];
  const sceneMatrixRows = [
    {
      section: 'aiSyncExtract',
      label: '③ AI 同步提取',
      hint: '从标题/描述提取门店、POS/SCO、日期、版本等字段',
      fields: [
        'externalPushEnabled',
        'remotePullEnabled',
        'bitablePullEnabled',
        'manualCreateEnabled',
      ],
    },
    {
      section: 'translateConfig',
      label: '⑤ 翻译',
      hint: '翻译工单描述；已有成功翻译结果时跳过',
      master: 'enabled',
      fields: [
        'translateOnExternalSync',
        'translateOnRemotePull',
        'translateOnBitablePull',
        'translateOnManualCreate',
      ],
    },
    {
      section: 'aiClassification',
      label: '⑥ AI 自动分类',
      hint: '状态变更触发的重归类在「AI 分类统计配置」卡片单独控制',
      master: 'enabled',
      fields: ['runOnExternalSync', 'runOnRemotePull', 'runOnBitablePull', 'runOnManualCreate'],
    },
    {
      section: 'automationConfig',
      label: '⑦ 自动识别',
      hint: '识别结果回写项目/模块/人员/门店归属',
      fields: [
        'autoIdentifyOnExternalSync',
        'autoIdentifyOnRemotePull',
        'autoIdentifyOnBitablePull',
        'autoIdentifyOnManualCreate',
      ],
    },
    {
      section: 'automationConfig',
      label: '⑦ 自动拉日志',
      hint: '命中停止条件或参数不全时跳过；参数见「日志拉取配置」',
      fields: [
        'autoLogPullOnExternalSync',
        'autoLogPullOnRemotePull',
        'autoLogPullOnBitablePull',
        'autoLogPullOnManualCreate',
      ],
    },
    {
      section: 'automationConfig',
      label: '⑦ 自动 AI 分析',
      hint: '随自动拉日志执行；Agent/Provider 见「日志拉取配置」',
      fields: [
        'autoAiAnalysisOnExternalSync',
        'autoAiAnalysisOnRemotePull',
        'autoAiAnalysisOnBitablePull',
        'autoAiAnalysisOnManualCreate',
      ],
    },
    {
      section: 'groupPush',
      label: '⑧ 自动群推送',
      hint: '满足推送条件时发送；已自动推送过的工单不会重复推送',
      master: 'enabled',
      fields: [
        'sendAfterExternalSync',
        'sendAfterRemotePull',
        'sendAfterBitablePull',
        'sendAfterManualCreate',
      ],
    },
  ];

  // ===== 连接解析预览 =====
  // 只读模拟后端 resolve_bitable_runtime_config 的继承顺序：模块自身 → bitableCommon → feishuAuth（appId/appSecret）。
  const connectionPreviewRows = computed(() => {
    const resolveWithAuth = (moduleValue, commonValue, authValue) => {
      const moduleText = String(moduleValue || '').trim();
      if (moduleText) return { value: moduleText, source: '模块覆盖' };
      const commonText = String(commonValue || '').trim();
      if (commonText) return { value: commonText, source: '公共配置' };
      const authText = String(authValue || '').trim();
      if (authText) return { value: authText, source: '统一凭证' };
      return { value: '—', source: '未配置' };
    };
    const resolveCommon = (moduleValue, commonValue) => {
      const moduleText = String(moduleValue || '').trim();
      if (moduleText) return { value: moduleText, source: '模块覆盖' };
      const commonText = String(commonValue || '').trim();
      if (commonText) return { value: commonText, source: '公共配置' };
      return { value: '—', source: '未配置' };
    };
    const consumers = [
      { name: '外部推送邮箱补全', section: form.externalSyncBitable },
      { name: '飞书多维表格主动拉取', section: form.bitablePull },
      { name: '汇总统计通知', section: form.summaryReport },
      { name: '按人催办通知', section: form.personReminder },
    ];
    return consumers.map((consumer) => ({
      name: consumer.name,
      appId: resolveWithAuth(
        consumer.section.appId,
        form.bitableCommon.appId,
        form.feishuAuth.appId
      ),
      appToken: resolveCommon(consumer.section.appToken, form.bitableCommon.appToken),
      tableId: resolveCommon(consumer.section.tableId, form.bitableCommon.tableId),
    }));
  });

  // 弹窗可见性：字段识别与映射 / 日志拉取设置
  const mappingDialogVisible = ref(false);
  const logPullDialogVisible = ref(false);

  const pushOptionsLoading = ref(false);
  const pushOptions = ref([]);
  const analysisProviderOptions = ref([]);
  const lightProviderOptions = ref([]);
  const lightModelOptionsMap = ref({});
  const promptOptions = ref([]);
  const agentOptions = ref([]);
  const groupSendLoading = ref(false);
  const personPreviewLoading = ref(false);
  const personRunLoading = ref(false);
  const summaryRunLoading = ref(false);
  const customStatisticsRunLoading = ref(false);
  const autoCategoryStatsLoading = ref(false);
  const autoCategoryRunLoading = ref(false);
  const bitablePullFieldsLoading = ref(false);
  const manualAutomationLoading = ref(false);
  const bitablePullFieldsLoaded = ref(false);
  const personPreviewResult = ref(null);
  const autoCategoryStats = ref(null);
  const autoCategoryRegexText = ref('[]');
  const bitablePullFieldOptions = ref([]);
  const groupSendForm = reactive({
    ticketNo: '',
    forcePush: false,
  });
  const manualAutomationForm = reactive({
    ticketNo: '',
    source: 'bitable',
  });
  const personQueryForm = reactive({
    userId: '',
    email: '',
  });
  const summaryRunForm = reactive({
    startTime: '',
    endTime: '',
  });
  const customStatisticsRunForm = reactive({
    profileCodes: [],
    send: true,
  });
  const customStatisticsRunResult = ref([]);
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
  // mappingTexts 已通过 useSyncConfig() 提供

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
    const modelName = item.defaultModel || '';
    return `${name}${code && name !== code ? ` [${code}]` : ''}${modelName ? ` - ${modelName}` : ''}`;
  }

  function formatPromptOptionLabel(item = {}) {
    const code = item.promptCode || item.templateCode || item.value || '';
    const name = item.promptName || item.templateName || item.label || code || '-';
    return `${name}${code && name !== code ? ` [${code}]` : ''}`;
  }

  /**
   * Provider 变更时加载该 Provider 的可用模型列表。
   * @param {string} sectionName 配置段名称
   * @param {string} providerCode Provider 编码
   */
  function handleProviderModelChange(sectionName, providerCode) {
    if (!providerCode) {
      lightModelOptionsMap.value[providerCode] = [];
      return;
    }
    if (lightModelOptionsMap.value[providerCode]) return;
    listAiProviderModelOptions(providerCode)
      .then((response) => {
        lightModelOptionsMap.value[providerCode] = Array.isArray(response.data)
          ? response.data
          : [];
      })
      .catch(() => {
        lightModelOptionsMap.value[providerCode] = [];
      });
  }

  /**
   * 预加载所有已配置 Provider 的模型列表。
   */
  function preloadModelOptions() {
    const sections = [
      'aiSyncExtract',
      'translateConfig',
      'titleSummaryConfig',
      'knowledgeConfig',
      'aiClassification',
      'summaryReport',
    ];
    sections.forEach((section) => {
      const providerCode = form[section]?.providerCode || form[section]?.aiProviderCode;
      if (providerCode) {
        handleProviderModelChange(section, providerCode);
      }
    });
  }

  function loadAiOptions() {
    listAllAgents()
      .then((response) => {
        agentOptions.value = Array.isArray(response.data) ? response.data : [];
      })
      .catch(() => {
        agentOptions.value = [];
      });
    listAiProviderOptions({ usage: 'ticket_analysis_worker' })
      .then((response) => {
        analysisProviderOptions.value = Array.isArray(response.data) ? response.data : [];
      })
      .catch(() => {
        analysisProviderOptions.value = [];
      });
    listAiProviderOptions({ usage: 'ticket_light_text', executor: 'direct_http' })
      .then((response) => {
        lightProviderOptions.value = Array.isArray(response.data) ? response.data : [];
      })
      .catch(() => {
        lightProviderOptions.value = [];
      });
    listAiPromptTemplateOptions({
      template_category: 'translate,knowledge,classification,analysis,common',
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

  function handleRunCustomStatistics() {
    customStatisticsRunLoading.value = true;
    runTicketCustomStatistics({
      profileCodes: customStatisticsRunForm.profileCodes.length
        ? customStatisticsRunForm.profileCodes
        : null,
      send: customStatisticsRunForm.send,
    })
      .then((response) => {
        customStatisticsRunResult.value = Array.isArray(response.data) ? response.data : [];
        proxy.$modal.msgSuccess(
          `自定义统计执行完成，共 ${customStatisticsRunResult.value.length} 个方案`
        );
      })
      .catch((error) => {
        customStatisticsRunResult.value = [];
        proxy.$modal.msgError(error?.message || '自定义统计执行失败');
      })
      .finally(() => {
        customStatisticsRunLoading.value = false;
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

  /**
   * 按输入工单号手动执行多维表格拉取后的自动化流程。
   */
  function handleRunManualAutomation() {
    const ticketNo = String(manualAutomationForm.ticketNo || '').trim();
    if (!ticketNo) {
      proxy.$modal.msgWarning('请先输入工单号');
      return;
    }
    manualAutomationLoading.value = true;
    runTicketManualAutomation({
      ticketNo,
      source: manualAutomationForm.source,
    })
      .then((response) => {
        const sourceLabel = manualAutomationForm.source === 'database' ? '数据库快照' : '多维表格';
        proxy.$modal.msgSuccess(
          `${sourceLabel}工单自动化已执行完成：${response.data?.ticketNo || ticketNo}`
        );
      })
      .catch((error) => {
        proxy.$modal.msgError(error?.message || '工单自动化执行失败');
      })
      .finally(() => {
        manualAutomationLoading.value = false;
      });
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
        autoCategoryForm.strategy === 'ai'
          ? String(
              autoCategoryForm.aiPromptCode || form.aiClassification.promptCode || ''
            ).trim() || null
          : null,
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
    loadConfig().then(() => {
      preloadModelOptions();
    });
    loadRemoteCredentialOptions();
    loadPushOptions();
    loadAiOptions();
    loadWorkflowStatuses();
    handleLoadAutoCategoryStats();
    logPullExternalLoadConfig();
    logPullStorageLoadConfig();
  });
</script>

<style scoped>
  .ticket-sync-automation-page {
    background: linear-gradient(180deg, rgba(248, 250, 252, 0.96), rgba(255, 255, 255, 1));
    padding-bottom: 72px;
    display: block;
    width: 100%;
    max-width: 100%;
    align-self: stretch;
    box-sizing: border-box;
    /* 必须用 clip 而不是 hidden：hidden 会把 overflow-y 变成 auto，本元素变成滚动容器，
       导致底部 action-bar 的 position: sticky 失效（按钮悬在内容末尾而非吸附视口底部）；
       clip 只做裁剪、不产生滚动容器，横向滚动防护与 sticky 吸底两者兼得。 */
    overflow-x: clip;
  }

  /* 页签容器：块级 + 允许收缩，避免 flex 主轴撑出横向滚动 */
  .config-tabs-wrap {
    width: 100%;
    min-width: 0;
    display: block;
  }

  .config-tabs-wrap :deep(.el-tabs__content) {
    overflow: hidden;
  }

  .config-tabs-wrap :deep(.el-tab-pane) {
    min-width: 0;
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

  /* ---- 自适应与紧凑化 ---- */

  /* 表格撑宽根治：表格本体宽度受限，超宽列由 el-table 内部横向滚动，不再把页面撑宽 */
  .ticket-sync-automation-page :deep(.el-table),
  .config-dialog :deep(.el-table) {
    width: 100% !important;
    max-width: 100%;
  }

  .ticket-sync-automation-page :deep(.el-table__inner-wrapper),
  .config-dialog :deep(.el-table__inner-wrapper) {
    max-width: 100%;
  }

  /* 页签导航紧凑 */
  .config-tabs-wrap :deep(.el-tabs__nav-wrap)::after {
    height: 1px;
  }

  /* 卡片间距紧凑：mt16 → 视觉 12px */
  .ticket-sync-automation-page :deep(.config-card) {
    border-radius: 10px;
  }

  .ticket-sync-automation-page :deep(.config-card .el-card__body) {
    padding: 14px 16px;
  }

  /* 表单项间距紧凑 */
  .ticket-sync-automation-page :deep(.el-form-item) {
    margin-bottom: 12px;
  }

  .ticket-sync-automation-page :deep(.el-form-item__label) {
    padding-bottom: 2px;
  }

  /* 分隔线上下间距紧凑 */
  .ticket-sync-automation-page :deep(.el-divider--horizontal) {
    margin: 14px 0 12px;
  }

  /* 提示条紧凑 */
  .ticket-sync-automation-page :deep(.el-alert) {
    padding: 6px 12px;
  }

  .ticket-sync-automation-page :deep(.el-alert__description) {
    margin-top: 2px;
  }

  /* mt16 在本页统一收紧为 12px */
  .ticket-sync-automation-page .mt16,
  .ticket-sync-automation-page :deep(.mt16) {
    margin-top: 12px;
  }

  /* 弹窗内表单：窄屏降为单列（覆盖 Element Plus 的百分比列宽，需同时覆盖 width） */
  @media (max-width: 768px) {
    .config-dialog :deep(.el-col) {
      max-width: 100%;
      flex: 0 0 100%;
      width: 100%;
    }

    .config-dialog :deep(.el-form-item) {
      margin-bottom: 10px;
    }
  }

  /* 弹窗遮罩下页面禁止滚动 */
  .config-dialog :deep(.el-dialog) {
    margin-bottom: 4vh;
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
    flex-wrap: wrap;
    gap: 8px 12px;
    font-weight: 600;
  }

  .card-header .el-tag {
    max-width: 100%;
    white-space: normal;
    height: auto;
    padding-top: 2px;
    padding-bottom: 2px;
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

  .form-help-text--section {
    margin-top: -6px;
    margin-bottom: 8px;
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

  .condition-help-popover {
    max-width: 680px;
    max-height: 520px;
    overflow-y: auto;
    font-size: 13px;
    line-height: 1.6;
    padding-right: 4px;
  }

  .condition-help-title {
    font-weight: 600;
    font-size: 14px;
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }

  .condition-help-subtitle {
    font-weight: 600;
    font-size: 13px;
    margin-top: 12px;
    margin-bottom: 6px;
  }

  .condition-help-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  .condition-help-table th,
  .condition-help-table td {
    padding: 4px 8px;
    border: 1px solid var(--el-border-color-lighter);
    text-align: left;
    vertical-align: top;
  }

  .condition-help-table th {
    background: var(--el-fill-color-light);
    font-weight: 500;
  }

  .condition-help-table code {
    background: var(--el-fill-color);
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 11px;
    white-space: nowrap;
  }

  .condition-help-fields td code {
    margin: 0 2px;
    display: inline-block;
  }

  .condition-help-fields td {
    line-height: 2;
  }

  .condition-help-note {
    margin-top: 10px;
    padding: 6px 8px;
    background: var(--el-color-warning-light-9);
    border-radius: 4px;
    font-size: 12px;
    color: var(--el-color-warning-dark-2);
    line-height: 1.5;
  }

  /* 日志拉取外部接口配置样式 */
  .env-groups-container {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .env-group-card {
    border: 1px solid var(--el-border-color-light);
    border-radius: 8px;
    padding: 16px;
    background: var(--el-bg-color);
  }

  .env-group-header {
    display: flex;
    align-items: center;
    margin-bottom: 12px;
  }

  .env-group-actions {
    margin-left: auto;
  }

  .env-items-table {
    margin-bottom: 0;
  }

  .env-group-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px dashed var(--el-border-color-lighter);
  }

  .env-default-item {
    margin-bottom: 0;
  }

  .env-default-item :deep(.el-form-item__label) {
    font-weight: normal;
    color: var(--el-text-color-regular);
  }

  .ftp-config-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    width: 100%;
  }
  /* 场景 × 步骤 开关总表 */
  .scene-matrix-table {
    width: 100%;
  }

  .scene-matrix-step {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
  }

  .scene-matrix-hint {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    line-height: 1.4;
    margin-top: 2px;
  }

  /* 连接覆盖折叠区与解析预览 */
  .override-collapse {
    width: 100%;
    border: 1px dashed var(--el-border-color);
    border-radius: 8px;
    padding: 0 12px;
    box-sizing: border-box;
  }

  .override-collapse :deep(.el-collapse-item__header) {
    height: 40px;
  }

  .override-collapse__title {
    font-weight: 600;
    margin-right: 12px;
  }

  .override-collapse__hint {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  .connection-preview-table {
    width: 100%;
  }

  .connection-preview-cell {
    word-break: break-all;
    line-height: 1.4;
  }

  /* 卡片头部设置按钮（靠右） */
  .card-setting-btn {
    margin-left: auto;
  }

  /* 摘要卡片（设置入口卡片的内容概览） */
  .card-summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 12px;
    margin-bottom: 12px;
  }

  .card-summary-item {
    border: 1px dashed var(--el-border-color);
    border-radius: 8px;
    padding: 10px 12px;
    background: var(--el-fill-color-blank);
  }

  .card-summary-item__label {
    font-weight: 600;
    margin-bottom: 4px;
  }

  .card-summary-item__value {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    line-height: 1.5;
  }

  /* 配置弹窗：内容区限宽滚动，避免撑出横向滚动 */
  .config-dialog {
    max-width: 96vw;
  }

  .config-dialog .el-dialog__body {
    max-height: 72vh;
    overflow-y: auto;
    padding-top: 10px;
  }

  .config-dialog__tip {
    margin-right: 12px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
</style>
