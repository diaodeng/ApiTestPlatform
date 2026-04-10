<template>
  <div class="app-container webcase-page">
    <el-tabs v-model="activeTab" class="webcase-tabs">
      <el-tab-pane label="用例管理" name="case">
        <el-form :inline="true" :model="queryParams" class="mb8">
          <el-form-item label="用例名称">
            <el-input v-model="queryParams.caseName" placeholder="请输入 Web 用例名称" clearable @keyup.enter="getList" />
          </el-form-item>
          <el-form-item label="项目">
            <el-select v-model="queryParams.projectId" clearable filterable placeholder="全部项目" style="width: 180px">
              <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
            </el-select>
          </el-form-item>
          <el-form-item label="模块">
            <el-select v-model="queryParams.moduleId" clearable filterable placeholder="全部模块" style="width: 180px">
              <el-option v-for="item in filteredSearchModules" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" icon="Search" @click="getList">搜索</el-button>
            <el-button icon="Refresh" @click="resetQuery">重置</el-button>
          </el-form-item>
        </el-form>

        <el-row :gutter="10" class="mb8">
          <el-col :span="1.5">
            <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['hrm:webCase:add']">新增</el-button>
          </el-col>
          <el-col :span="1.5">
            <el-button type="warning" plain icon="VideoPlay" @click="openRecordingDialog()" v-hasPermi="['hrm:webCase:record']">独立录制</el-button>
          </el-col>
          <el-col :span="1.5">
            <el-button type="default" plain icon="Refresh" @click="getList">刷新</el-button>
          </el-col>
        </el-row>

        <el-table v-loading="loading.page" :data="pageDataList" border table-layout="fixed" max-height="calc(100vh - 340px)">
          <el-table-column label="Web用例ID" prop="webCaseId" width="170" />
          <el-table-column label="用例名称" prop="caseName" min-width="220" />
          <el-table-column label="项目" min-width="140">
            <template #default="scope">{{ getProjectName(scope.row.projectId) || scope.row.projectId || "-" }}</template>
          </el-table-column>
          <el-table-column label="模块" min-width="140">
            <template #default="scope">{{ getModuleName(scope.row.moduleId) || scope.row.moduleId || "-" }}</template>
          </el-table-column>
          <el-table-column label="起始地址" prop="startUrl" min-width="220" show-overflow-tooltip />
          <el-table-column label="浏览器" prop="browserName" width="120" />
          <el-table-column label="无头" width="90">
            <template #default="scope">{{ scope.row.headless ? "是" : "否" }}</template>
          </el-table-column>
          <el-table-column label="更新时间" min-width="170">
            <template #default="scope">{{ formatTime(scope.row.updateTime || scope.row.createTime) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="370" fixed="right">
            <template #default="scope">
              <el-button link type="primary" icon="Edit" @click="handleEdit(scope.row)" v-hasPermi="['hrm:webCase:edit']">编辑</el-button>
              <el-button link type="success" icon="CaretRight" @click="openRunDialog(scope.row)" v-hasPermi="['hrm:webCase:run']">执行</el-button>
              <el-button link type="warning" icon="VideoPlay" @click="openRecordingDialog(scope.row)" v-hasPermi="['hrm:webCase:record']">录制</el-button>
              <el-button link type="info" icon="Histogram" @click="openRunHistory(scope.row)" v-hasPermi="['hrm:webCase:history']">记录</el-button>
              <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['hrm:webCase:remove']">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pager">
          <el-pagination
            v-model:current-page="queryParams.pageNum"
            v-model:page-size="queryParams.pageSize"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            :total="total"
            @size-change="getList"
            @current-change="getList"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="执行记录" name="run">
        <el-form :inline="true" :model="runQueryParams" class="mb8">
          <el-form-item label="所属用例">
            <el-select
              v-model="runQueryParams.webCaseId"
              clearable
              filterable
              remote
              reserve-keyword
              placeholder="输入用例名称搜索"
              style="width: 240px"
              :remote-method="searchCaseOptions"
              :loading="caseSelectLoading"
              @visible-change="handleCaseSelectVisibleChange"
            >
              <el-option v-for="item in caseSelectOptions" :key="item.webCaseId" :label="item.caseName" :value="item.webCaseId" />
            </el-select>
          </el-form-item>
          <el-form-item label="执行状态">
            <el-select v-model="runQueryParams.status" clearable placeholder="全部状态" style="width: 160px">
              <el-option v-for="item in runStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="Agent编码">
            <el-input v-model="runQueryParams.agentCode" placeholder="支持精确筛选" clearable />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" icon="Search" @click="getRunList">搜索</el-button>
            <el-button icon="Refresh" @click="resetRunQuery">重置</el-button>
          </el-form-item>
        </el-form>

        <el-table v-loading="loading.runPage" :data="runRecordList" border table-layout="fixed" max-height="calc(100vh - 320px)">
          <el-table-column label="执行记录ID" prop="webCaseRunId" width="170" />
          <el-table-column label="用例名称" min-width="220">
            <template #default="scope">{{ getCaseName(scope.row.webCaseId) || scope.row.webCaseId || "-" }}</template>
          </el-table-column>
          <el-table-column label="Agent" prop="agentCode" min-width="160" show-overflow-tooltip />
          <el-table-column label="触发方式" prop="triggerType" width="110" />
          <el-table-column label="状态" width="100">
            <template #default="scope">
              <el-tag :type="getRunStatusMeta(scope.row.status).type">{{ getRunStatusMeta(scope.row.status).label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="开始时间" min-width="170">
            <template #default="scope">{{ formatTime(scope.row.startedAt) }}</template>
          </el-table-column>
          <el-table-column label="耗时" width="120">
            <template #default="scope">{{ formatDuration(scope.row.durationMs) }}</template>
          </el-table-column>
          <el-table-column label="失败原因" min-width="260" show-overflow-tooltip>
            <template #default="scope">{{ scope.row.errorMessage || "-" }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="scope">
              <el-button link type="primary" icon="View" @click="openRunDetail(scope.row)">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pager">
          <el-pagination
            v-model:current-page="runQueryParams.pageNum"
            v-model:page-size="runQueryParams.pageSize"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            :total="runTotal"
            @size-change="getRunList"
            @current-change="getRunList"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="录制记录" name="recording">
        <el-form :inline="true" :model="recordingQueryParams" class="mb8">
          <el-form-item label="录制名称">
            <el-input v-model="recordingQueryParams.sessionName" placeholder="请输入录制名称" clearable @keyup.enter="getRecordingList" />
          </el-form-item>
          <el-form-item label="所属用例">
            <el-select
              v-model="recordingQueryParams.webCaseId"
              clearable
              filterable
              remote
              reserve-keyword
              placeholder="输入用例名称搜索"
              style="width: 240px"
              :remote-method="searchCaseOptions"
              :loading="caseSelectLoading"
              @visible-change="handleCaseSelectVisibleChange"
            >
              <el-option v-for="item in caseSelectOptions" :key="item.webCaseId" :label="item.caseName" :value="item.webCaseId" />
            </el-select>
          </el-form-item>
          <el-form-item label="录制状态">
            <el-select v-model="recordingQueryParams.status" clearable placeholder="全部状态" style="width: 160px">
              <el-option v-for="item in recordingStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" icon="Search" @click="getRecordingList">搜索</el-button>
            <el-button icon="Refresh" @click="resetRecordingQuery">重置</el-button>
          </el-form-item>
        </el-form>

        <el-row :gutter="10" class="mb8">
          <el-col :span="1.5">
            <el-button type="warning" plain icon="VideoPlay" @click="openRecordingDialog()" v-hasPermi="['hrm:webCase:record']">新建录制</el-button>
          </el-col>
          <el-col :span="1.5">
            <el-button type="default" plain icon="Refresh" @click="getRecordingList">刷新</el-button>
          </el-col>
        </el-row>

        <el-table v-loading="loading.recordingPage" :data="recordingList" border table-layout="fixed" max-height="calc(100vh - 360px)">
          <el-table-column label="录制ID" prop="recordingId" width="170" />
          <el-table-column label="录制名称" prop="sessionName" min-width="220" />
          <el-table-column label="所属用例" min-width="220">
            <template #default="scope">{{ getCaseName(scope.row.webCaseId) || scope.row.webCaseId || "独立录制" }}</template>
          </el-table-column>
          <el-table-column label="Agent" prop="agentCode" min-width="150" show-overflow-tooltip />
          <el-table-column label="浏览器" width="120">
            <template #default="scope">{{ scope.row.browserName }}{{ scope.row.headless ? " / 无头" : "" }}</template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="scope">
              <el-tag :type="getRecordingStatusMeta(scope.row.status).type">{{ getRecordingStatusMeta(scope.row.status).label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="开始时间" min-width="170">
            <template #default="scope">{{ formatTime(scope.row.startedAt) }}</template>
          </el-table-column>
          <el-table-column label="最近事件" min-width="170">
            <template #default="scope">{{ formatTime(scope.row.lastEventAt) }}</template>
          </el-table-column>
          <el-table-column label="失败原因" min-width="220" show-overflow-tooltip>
            <template #default="scope">{{ scope.row.errorMessage || "-" }}</template>
          </el-table-column>
          <el-table-column label="操作" width="360" fixed="right">
            <template #default="scope">
              <el-button link type="primary" icon="View" @click="openRecordingDetail(scope.row)">查看</el-button>
              <el-button link type="success" icon="VideoPlay" :disabled="!canUseRecordingResult(scope.row.status)" @click="openReplayDialog(scope.row)" v-hasPermi="['hrm:webCase:run']">回放</el-button>
              <el-button link type="warning" icon="Plus" :disabled="!canUseRecordingResult(scope.row.status)" @click="openRecordingActionDialog('create', scope.row)" v-hasPermi="['hrm:webCase:add']">保存新用例</el-button>
              <el-button link type="info" icon="DocumentAdd" :disabled="!canUseRecordingResult(scope.row.status)" @click="openRecordingActionDialog('append', scope.row)" v-hasPermi="['hrm:webCase:edit']">追加</el-button>
              <el-button link type="danger" icon="EditPen" :disabled="!canUseRecordingResult(scope.row.status)" @click="openRecordingActionDialog('replace', scope.row)" v-hasPermi="['hrm:webCase:edit']">覆盖</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pager">
          <el-pagination
            v-model:current-page="recordingQueryParams.pageNum"
            v-model:page-size="recordingQueryParams.pageSize"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            :total="recordingTotal"
            @size-change="getRecordingList"
            @current-change="getRecordingList"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="showCaseDialog" :title="caseDialogTitle" width="1360px" destroy-on-close>
      <el-form :model="form" label-width="90px" class="mb16">
        <el-row :gutter="16">
          <el-col :span="10">
            <el-form-item label="用例名称">
              <el-input v-model="form.caseName" />
            </el-form-item>
          </el-col>
          <el-col :span="7">
            <el-form-item label="浏览器">
              <el-select v-model="form.browserName" style="width: 100%">
                <el-option v-for="item in browserOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="7">
            <el-form-item label="无头模式">
              <el-switch v-model="form.headless" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目">
              <el-select v-model="form.projectId" clearable filterable style="width: 100%">
                <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模块">
              <el-select v-model="form.moduleId" clearable filterable style="width: 100%">
                <el-option v-for="item in filteredCaseModules" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="起始地址">
              <el-input v-model="form.startUrl" placeholder="https://example.com" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="说明">
              <el-input v-model="form.notes" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-tabs v-model="caseEditorTab" class="case-editor-tabs">
        <el-tab-pane label="可视化步骤" name="visual">
          <div class="step-table-toolbar">
            <div class="panel-title">测试步骤</div>
            <div class="step-table-toolbar-actions">
              <el-button type="primary" icon="Plus" @click="addStep()">新增步骤</el-button>
              <el-button plain icon="EditPen" :disabled="selectedStepIndex < 0" @click="openStepDetailByIndex(selectedStepIndex)">编辑当前步骤</el-button>
            </div>
          </div>
          <el-table
            :data="form.steps"
            border
            class="step-edit-table"
            max-height="560px"
            empty-text="暂无步骤，可手动新增或通过录制生成"
            :row-class-name="getStepRowClassName"
            @row-click="handleStepRowClick"
          >
            <el-table-column label="序号" width="120" fixed="left">
              <template #default="scope">
                <div class="step-order-cell">
                  <span>#{{ scope.$index + 1 }}</span>
                  <el-tag size="small" :type="scope.row.enabled ? 'success' : 'info'">{{ scope.row.enabled ? "启用" : "停用" }}</el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="动作" width="170">
              <template #default="scope">
                <el-select
                  v-model="scope.row.actionType"
                  filterable
                  style="width: 100%"
                  @click.stop
                  @change="handleStepActionTypeChange(scope.row)"
                >
                  <el-option v-for="item in actionOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="步骤名称" min-width="220">
              <template #default="scope">
                <el-input v-model="scope.row.stepName" @click.stop placeholder="请输入步骤名称" />
              </template>
            </el-table-column>
            <el-table-column label="定位信息" min-width="320">
              <template #default="scope">
                <template v-if="stepNeedsTarget(scope.row.actionType) && getPrimaryLocator(scope.row)">
                  <div class="step-inline-target" @click.stop>
                    <el-select
                      :model-value="getPrimaryLocator(scope.row)?.locatorType"
                      style="width: 110px"
                      @update:model-value="updatePrimaryLocatorType(scope.row, $event)"
                    >
                      <el-option v-for="item in locatorTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                    <template v-if="getPrimaryLocator(scope.row)?.locatorType === 'role'">
                      <el-input
                        :model-value="getPrimaryLocator(scope.row)?.locatorValue?.role || ''"
                        placeholder="角色"
                        @update:model-value="updatePrimaryLocatorValue(scope.row, 'role', $event)"
                      />
                      <el-input
                        :model-value="getPrimaryLocator(scope.row)?.locatorValue?.name || ''"
                        placeholder="名称"
                        @update:model-value="updatePrimaryLocatorValue(scope.row, 'name', $event)"
                      />
                    </template>
                    <el-input
                      v-else-if="['label', 'placeholder', 'text'].includes(getPrimaryLocator(scope.row)?.locatorType)"
                      :model-value="getPrimaryLocator(scope.row)?.locatorValue?.text || ''"
                      placeholder="定位文本"
                      @update:model-value="updatePrimaryLocatorValue(scope.row, 'text', $event)"
                    />
                    <el-input
                      v-else-if="getPrimaryLocator(scope.row)?.locatorType === 'test_id'"
                      :model-value="getPrimaryLocator(scope.row)?.locatorValue?.testId || ''"
                      placeholder="Test ID"
                      @update:model-value="updatePrimaryLocatorValue(scope.row, 'testId', $event)"
                    />
                    <el-input
                      v-else
                      :model-value="getPrimaryLocator(scope.row)?.locatorValue?.selector || ''"
                      :placeholder="getPrimaryLocator(scope.row)?.locatorType === 'xpath' ? '//*[@id=&quot;login&quot;]' : '.login-button'"
                      @update:model-value="updatePrimaryLocatorValue(scope.row, 'selector', $event)"
                    />
                  </div>
                </template>
                <span v-else class="step-cell-placeholder">当前动作无需定位器</span>
              </template>
            </el-table-column>
            <el-table-column label="输入/参数" min-width="260">
              <template #default="scope">
                <template v-if="scope.row.actionType === 'goto'">
                  <el-input v-model="scope.row.params.url" @click.stop placeholder="https://example.com/path" />
                </template>
                <template v-else-if="scope.row.actionType === 'fill'">
                  <el-input v-model="scope.row.params.value" @click.stop placeholder="请输入内容" />
                </template>
                <template v-else-if="scope.row.actionType === 'press'">
                  <el-select
                    v-model="scope.row.params.key"
                    filterable
                    allow-create
                    default-first-option
                    style="width: 100%"
                    placeholder="选择或输入按键"
                    @click.stop
                  >
                    <el-option v-for="item in keyboardKeyOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </template>
                <template v-else-if="scope.row.actionType === 'select_option'">
                  <el-select
                    v-model="scope.row.params.values"
                    multiple
                    filterable
                    allow-create
                    default-first-option
                    collapse-tags
                    collapse-tags-tooltip
                    style="width: 100%"
                    placeholder="输入或选择选项值"
                    @click.stop
                  />
                </template>
                <span v-else class="step-cell-placeholder">当前动作无额外参数</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="scope">
                <div class="step-op-buttons">
                  <el-button link icon="Top" :disabled="scope.$index === 0" @click.stop="moveStep(scope.$index, -1)" />
                  <el-button link icon="Bottom" :disabled="scope.$index === form.steps.length - 1" @click.stop="moveStep(scope.$index, 1)" />
                  <el-button link type="primary" icon="EditPen" @click.stop="openStepDetailByIndex(scope.$index)">编辑</el-button>
                  <el-button link type="danger" icon="Delete" @click.stop="removeStep(scope.$index)" />
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="高级 JSON" name="json">
          <div class="json-toolbar">
            <el-button type="primary" icon="Check" @click="applyStepsTextToForm(true)">应用 JSON 到可视化</el-button>
            <el-button icon="RefreshRight" @click="syncStepsTextFromForm">使用当前可视化刷新 JSON</el-button>
          </div>
          <AceEditor v-model:content="stepsText" lang="json" :can-set="true" height="560px" />
        </el-tab-pane>
      </el-tabs>

      <template #footer>
        <el-button @click="showCaseDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.save" @click="saveCase">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showStepDetailDialog" :title="stepDetailTitle" width="1160px" destroy-on-close append-to-body>
      <template v-if="currentStep">
        <el-form :model="currentStep" label-width="100px" class="mb16">
          <el-row :gutter="16">
            <el-col :span="10">
              <el-form-item label="步骤名称">
                <el-input v-model="currentStep.stepName" placeholder="请输入步骤名称" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="动作类型">
                <el-select v-model="currentStep.actionType" filterable style="width: 100%" @change="handleStepActionTypeChange(currentStep)">
                  <el-option v-for="item in actionOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-form-item label="启用">
                <el-switch v-model="currentStep.enabled" />
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-form-item label="继续执行">
                <el-switch v-model="currentStep.continueOnFailure" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="超时(ms)">
                <el-input-number v-model="currentStep.timeoutMs" :min="0" :step="1000" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="记录来源">
                <el-input v-model="currentStep.recordOrigin" placeholder="manual / record" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="元素ID">
                <el-input v-model="currentStep.elementId" placeholder="可选" />
              </el-form-item>
            </el-col>
            <el-col v-if="currentStep.actionType === 'goto'" :span="24">
              <el-form-item label="跳转地址">
                <el-input v-model="currentStep.params.url" placeholder="https://example.com/path" />
              </el-form-item>
            </el-col>
            <el-col v-else-if="currentStep.actionType === 'fill'" :span="24">
              <el-form-item label="输入内容">
                <el-input v-model="currentStep.params.value" type="textarea" :rows="3" placeholder="请输入内容" />
              </el-form-item>
            </el-col>
            <el-col v-else-if="currentStep.actionType === 'press'" :span="24">
              <el-form-item label="按键值">
                <el-select
                  v-model="currentStep.params.key"
                  filterable
                  allow-create
                  default-first-option
                  style="width: 100%"
                  placeholder="选择或输入按键"
                >
                  <el-option v-for="item in keyboardKeyOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col v-else-if="currentStep.actionType === 'select_option'" :span="24">
              <el-form-item label="选项值">
                <el-select
                  v-model="currentStep.params.values"
                  multiple
                  filterable
                  allow-create
                  default-first-option
                  collapse-tags
                  collapse-tags-tooltip
                  style="width: 100%"
                  placeholder="输入或选择下拉选项值"
                />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>

        <el-card v-if="stepNeedsTarget(currentStep.actionType)" class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>定位与快照</span>
              <el-button type="primary" plain icon="Plus" @click="addLocator(currentStep)">新增定位器</el-button>
            </div>
          </template>

          <el-row :gutter="16" class="mb16">
            <el-col :span="8">
              <el-form-item label="元素文本" label-width="90px">
                <el-input v-model="currentStep.targetSnapshot.elementText" placeholder="元素文本快照" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="指纹" label-width="90px">
                <el-input v-model="currentStep.targetSnapshot.fingerprint" placeholder="元素指纹" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="稳定分" label-width="90px">
                <el-input-number v-model="currentStep.targetSnapshot.stableScore" :min="0" :step="1" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="页面URL" label-width="90px">
                <el-input v-model="currentStep.targetSnapshot.context.pageUrl" placeholder="页面 URL" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Frame URL" label-width="90px">
                <el-input v-model="currentStep.targetSnapshot.context.frameUrl" placeholder="Frame URL" />
              </el-form-item>
            </el-col>
          </el-row>

          <div v-if="currentStep.targetSnapshot?.locators?.length" class="locator-list">
            <div
              v-for="(locator, locatorIndex) in currentStep.targetSnapshot.locators"
              :key="locator.locatorSnapshotId || `${currentStep.stepIndex || selectedStepIndex}-${locatorIndex}`"
              class="locator-item"
            >
              <div class="locator-header">
                <div class="locator-title">定位器 {{ locatorIndex + 1 }}</div>
                <div class="locator-actions">
                  <el-switch v-model="locator.enabled" inline-prompt active-text="启用" inactive-text="停用" />
                  <el-button link icon="Top" :disabled="locatorIndex === 0" @click="moveLocator(currentStep, locatorIndex, -1)" />
                  <el-button
                    link
                    icon="Bottom"
                    :disabled="locatorIndex === currentStep.targetSnapshot.locators.length - 1"
                    @click="moveLocator(currentStep, locatorIndex, 1)"
                  />
                  <el-button link type="danger" icon="Delete" @click="removeLocator(currentStep, locatorIndex)" />
                </div>
              </div>

              <el-row :gutter="12">
                <el-col :span="6">
                  <el-form-item label="类型" label-width="60px">
                    <el-select v-model="locator.locatorType" style="width: 100%" @change="handleLocatorTypeChange(locator)">
                      <el-option v-for="item in locatorTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col v-if="locator.locatorType === 'role'" :span="8">
                  <el-form-item label="角色" label-width="60px">
                    <el-input v-model="locator.locatorValue.role" placeholder="button / textbox" />
                  </el-form-item>
                </el-col>
                <el-col v-if="locator.locatorType === 'role'" :span="6">
                  <el-form-item label="名称" label-width="60px">
                    <el-input v-model="locator.locatorValue.name" placeholder="按钮名称" />
                  </el-form-item>
                </el-col>
                <el-col v-if="locator.locatorType === 'role'" :span="4">
                  <el-form-item label="精确" label-width="60px">
                    <el-switch v-model="locator.locatorValue.exact" />
                  </el-form-item>
                </el-col>
                <el-col v-if="['label', 'placeholder', 'text'].includes(locator.locatorType)" :span="14">
                  <el-form-item label="文本" label-width="60px">
                    <el-input v-model="locator.locatorValue.text" placeholder="定位文本" />
                  </el-form-item>
                </el-col>
                <el-col v-if="['label', 'placeholder', 'text'].includes(locator.locatorType)" :span="4">
                  <el-form-item label="精确" label-width="60px">
                    <el-switch v-model="locator.locatorValue.exact" />
                  </el-form-item>
                </el-col>
                <el-col v-if="locator.locatorType === 'test_id'" :span="14">
                  <el-form-item label="Test ID" label-width="70px">
                    <el-input v-model="locator.locatorValue.testId" placeholder="data-testid" />
                  </el-form-item>
                </el-col>
                <el-col v-if="['css', 'xpath'].includes(locator.locatorType)" :span="18">
                  <el-form-item label="选择器" label-width="60px">
                    <el-input
                      v-model="locator.locatorValue.selector"
                      :placeholder="locator.locatorType === 'xpath' ? '//*[@id=&quot;login&quot;]' : '.login-button'"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </div>
          </div>
          <el-empty v-else description="当前步骤暂无定位器" :image-size="70" />
        </el-card>

        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>断言</span>
              <el-button type="primary" plain icon="Plus" @click="addAssertion(currentStep)">新增断言</el-button>
            </div>
          </template>

          <div v-if="currentStep.assertions?.length" class="assertion-list">
            <div v-for="(assertion, assertionIndex) in currentStep.assertions" :key="`${selectedStepIndex}-${assertionIndex}`" class="assertion-item">
              <el-row :gutter="12">
                <el-col :span="6">
                  <el-form-item label="断言类型" label-width="80px">
                    <el-select v-model="assertion.assertType" style="width: 100%">
                      <el-option v-for="item in assertionTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="期望值" label-width="80px">
                    <el-input v-model="assertion.expected" placeholder="请输入期望值" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="实际来源" label-width="80px">
                    <el-input v-model="assertion.actualSource" placeholder="如 text / url" />
                  </el-form-item>
                </el-col>
                <el-col :span="2">
                  <el-form-item label="启用" label-width="50px">
                    <el-switch v-model="assertion.enabled" />
                  </el-form-item>
                </el-col>
                <el-col :span="2" class="assertion-remove">
                  <el-button link type="danger" icon="Delete" @click="removeAssertion(currentStep, assertionIndex)">删除</el-button>
                </el-col>
              </el-row>
            </div>
          </div>
          <el-empty v-else description="当前步骤暂无断言" :image-size="70" />
        </el-card>

        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>原始事件</span>
              <span class="step-detail-tip">用于查看录制时的原始数据，默认只读</span>
            </div>
          </template>
          <AceEditor :content="safeJsonStringify(currentStep.rawEvent || {})" lang="json" :read-only="true" height="220px" />
        </el-card>
      </template>
      <template #footer>
        <el-button @click="showStepDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRunDialog" title="执行 Web 用例" width="560px" destroy-on-close>
      <el-form :model="runForm" label-width="120px">
        <el-form-item label="目标用例">
          <el-input :model-value="selectedCase ? `${selectedCase.caseName} [${selectedCase.webCaseId}]` : ''" readonly />
        </el-form-item>
        <el-form-item label="执行 Agent">
          <el-select v-model="runForm.agentId" filterable style="width: 100%">
            <el-option v-for="item in agentOptions" :key="item.agentId" :label="`${item.agentName || item.agentCode} [${item.agentCode}]`" :value="item.agentId" />
          </el-select>
        </el-form-item>
        <el-form-item label="浏览器">
          <el-select v-model="runForm.browserName" style="width: 100%">
            <el-option v-for="item in browserOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="无头模式">
          <el-switch v-model="runForm.headless" />
        </el-form-item>
        <el-form-item label="结束后关闭浏览器">
          <el-switch v-model="runForm.closeBrowserOnFinish" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRunDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.run" @click="submitRun">执行</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRunDetailDialog" :title="runDetailTitle" width="1180px" destroy-on-close>
      <template v-if="runDetail">
        <el-descriptions :column="4" border class="mb16">
          <el-descriptions-item label="执行记录ID">{{ runDetail.webCaseRunId }}</el-descriptions-item>
          <el-descriptions-item label="所属用例">{{ runDetail.caseName || getCaseName(runDetail.webCaseId) || runDetail.webCaseId }}</el-descriptions-item>
          <el-descriptions-item label="Agent">{{ runDetail.agentCode || "-" }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getRunStatusMeta(runDetail.status).type">{{ getRunStatusMeta(runDetail.status).label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatTime(runDetail.startedAt) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ formatTime(runDetail.endedAt) }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ formatDuration(runDetail.durationMs) }}</el-descriptions-item>
          <el-descriptions-item label="触发方式">{{ runDetail.triggerType || "-" }}</el-descriptions-item>
        </el-descriptions>

        <el-alert v-if="runDetail.errorMessage" :title="runDetail.errorMessage" type="error" show-icon :closable="false" class="mb16" />

        <el-table :data="runStepResults" border max-height="320px" class="mb16">
          <el-table-column label="步骤" prop="stepName" min-width="220" />
          <el-table-column label="状态" width="110">
            <template #default="scope">
                <el-tag :type="isPassedStepStatus(scope.row.status) ? 'success' : 'danger'">{{ scope.row.status || "-" }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="110">
            <template #default="scope">{{ formatDuration(scope.row.durationMs) }}</template>
          </el-table-column>
          <el-table-column label="页面" prop="pageUrl" min-width="220" show-overflow-tooltip />
          <el-table-column label="失败原因" prop="error" min-width="260" show-overflow-tooltip />
        </el-table>

        <AceEditor :content="runDetailJsonText" lang="json" :read-only="true" height="260px" />
      </template>
    </el-dialog>

    <el-dialog v-model="showRecordingDialog" :title="recordingDialogTitle" width="1240px" destroy-on-close @close="stopRecordingPoll">
      <el-form :model="recordingForm" label-width="120px" class="mb12">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="关联用例">
              <el-input :model-value="recordingLinkedCaseLabel" readonly />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="录制名称">
              <el-input v-model="recordingForm.sessionName" placeholder="为空则自动生成录制名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="执行 Agent">
              <el-select v-model="recordingForm.agentId" filterable style="width: 100%">
                <el-option v-for="item in agentOptions" :key="item.agentId" :label="`${item.agentName || item.agentCode} [${item.agentCode}]`" :value="item.agentId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="浏览器">
              <el-select v-model="recordingForm.browserName" style="width: 100%">
                <el-option v-for="item in browserOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="无头模式">
              <el-switch v-model="recordingForm.headless" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="起始地址">
              <el-input v-model="recordingForm.startUrl" placeholder="https://example.com" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="停止时关闭浏览器">
              <el-switch v-model="recordingForm.closeBrowserOnStop" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="当前录制ID">
              <el-input :model-value="recordingForm.recordingId || '-'" readonly />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div class="recording-toolbar">
        <el-button type="primary" :loading="loading.recording" @click="startRecording">开始录制</el-button>
        <el-button type="warning" :disabled="!recordingForm.recordingId" @click="stopRecording">停止录制</el-button>
        <el-button :disabled="!recordingForm.recordingId" @click="refreshRecording">刷新详情</el-button>
        <el-button type="success" :disabled="!recordingForm.recordingId" @click="openRecordingDetail(recordingForm.recordingId)">查看录制详情</el-button>
        <el-button type="success" plain :disabled="!recordingResultReady" @click="openRecordingActionDialog('create', recordingForm.recordingId)">保存为新用例</el-button>
        <el-button type="info" plain :disabled="!recordingResultReady" @click="openRecordingActionDialog('append', recordingForm.recordingId)">追加到用例</el-button>
        <el-button type="danger" plain :disabled="!recordingResultReady" @click="openRecordingActionDialog('replace', recordingForm.recordingId)">覆盖到用例</el-button>
      </div>

      <el-alert :title="recordingLiveStatusText" :type="recordingLiveStatusType" :closable="false" show-icon class="mb16" />

      <el-table :data="liveRecordingSteps" border max-height="300px" class="mb16">
        <el-table-column label="序号" prop="stepIndex" width="80" />
        <el-table-column label="动作" width="120">
          <template #default="scope">{{ getActionLabel(scope.row.actionType) }}</template>
        </el-table-column>
        <el-table-column label="步骤名称" prop="stepName" min-width="220" />
        <el-table-column label="定位信息" min-width="260">
          <template #default="scope">{{ describeStepTarget(scope.row) }}</template>
        </el-table-column>
        <el-table-column label="输入/参数" min-width="220" show-overflow-tooltip>
          <template #default="scope">{{ summarizeStepParams(scope.row) }}</template>
        </el-table-column>
      </el-table>

      <AceEditor :content="recordingDetailText" lang="json" :read-only="true" height="220px" />
    </el-dialog>

    <el-dialog v-model="showRecordingDetailDialog" :title="recordingDetailTitle" width="1240px" destroy-on-close>
      <template v-if="recordingDetail">
        <el-descriptions :column="4" border class="mb16">
          <el-descriptions-item label="录制ID">{{ recordingDetail.recordingId }}</el-descriptions-item>
          <el-descriptions-item label="录制名称">{{ recordingDetail.sessionName || "-" }}</el-descriptions-item>
          <el-descriptions-item label="所属用例">{{ getCaseName(recordingDetail.webCaseId) || recordingDetail.webCaseId || "独立录制" }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getRecordingStatusMeta(recordingDetail.status).type">{{ getRecordingStatusMeta(recordingDetail.status).label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Agent">{{ recordingDetail.agentCode || "-" }}</el-descriptions-item>
          <el-descriptions-item label="浏览器">{{ recordingDetail.browserName || "-" }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatTime(recordingDetail.startedAt) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ formatTime(recordingDetail.endedAt) }}</el-descriptions-item>
        </el-descriptions>

        <el-alert v-if="recordingDetail.errorMessage" :title="recordingDetail.errorMessage" type="error" :closable="false" show-icon class="mb16" />

        <div class="recording-toolbar mb16">
          <el-button type="success" icon="VideoPlay" :disabled="!canUseRecordingResult(recordingDetail.status)" @click="openReplayDialog(recordingDetail)" v-hasPermi="['hrm:webCase:run']">回放录制</el-button>
          <el-button type="success" plain icon="Plus" :disabled="!canUseRecordingResult(recordingDetail.status)" @click="openRecordingActionDialog('create', recordingDetail)" v-hasPermi="['hrm:webCase:add']">保存为新用例</el-button>
          <el-button type="info" plain icon="DocumentAdd" :disabled="!canUseRecordingResult(recordingDetail.status)" @click="openRecordingActionDialog('append', recordingDetail)" v-hasPermi="['hrm:webCase:edit']">追加到用例</el-button>
          <el-button type="danger" plain icon="EditPen" :disabled="!canUseRecordingResult(recordingDetail.status)" @click="openRecordingActionDialog('replace', recordingDetail)" v-hasPermi="['hrm:webCase:edit']">覆盖到用例</el-button>
        </div>

        <el-tabs v-model="recordingDetailTab">
          <el-tab-pane label="步骤预览" name="steps">
            <el-table :data="recordingPreviewSteps" border max-height="380px">
              <el-table-column label="序号" prop="stepIndex" width="80" />
              <el-table-column label="动作" width="120">
                <template #default="scope">{{ getActionLabel(scope.row.actionType) }}</template>
              </el-table-column>
              <el-table-column label="步骤名称" prop="stepName" min-width="220" />
              <el-table-column label="定位信息" min-width="280">
                <template #default="scope">{{ describeStepTarget(scope.row) }}</template>
              </el-table-column>
              <el-table-column label="输入/参数" min-width="220" show-overflow-tooltip>
                <template #default="scope">{{ summarizeStepParams(scope.row) }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="原始事件" name="events">
            <el-table :data="recordingEventRows" border max-height="380px">
              <el-table-column label="序号" prop="eventIndex" width="80" />
              <el-table-column label="事件类型" prop="eventType" width="140" />
              <el-table-column label="动作" min-width="160">
                <template #default="scope">{{ scope.row.payload?.actionType || "-" }}</template>
              </el-table-column>
              <el-table-column label="步骤名称" min-width="220">
                <template #default="scope">{{ scope.row.payload?.stepName || "-" }}</template>
              </el-table-column>
              <el-table-column label="元素文本" min-width="220">
                <template #default="scope">{{ scope.row.payload?.targetSnapshot?.elementText || "-" }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="原始 JSON" name="json">
            <AceEditor :content="recordingDetailJsonText" lang="json" :read-only="true" height="400px" />
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-dialog>

    <el-dialog v-model="showRecordingActionDialog" :title="recordingActionDialogTitle" width="760px" destroy-on-close>
      <el-alert :title="recordingActionDialogTip" :type="recordingActionMode === 'replace' ? 'warning' : 'info'" :closable="false" show-icon class="mb16" />
      <el-form :model="recordingActionForm" label-width="110px">
        <template v-if="recordingActionMode === 'create'">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="用例名称">
                <el-input v-model="recordingActionForm.caseName" placeholder="请输入新用例名称" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="浏览器">
                <el-select v-model="recordingActionForm.browserName" style="width: 100%">
                  <el-option v-for="item in browserOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="项目">
                <el-select v-model="recordingActionForm.projectId" clearable filterable style="width: 100%">
                  <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="模块">
                <el-select v-model="recordingActionForm.moduleId" clearable filterable style="width: 100%">
                  <el-option v-for="item in filteredRecordingActionModules" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="起始地址">
                <el-input v-model="recordingActionForm.startUrl" placeholder="https://example.com" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="无头模式">
                <el-switch v-model="recordingActionForm.headless" />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="说明">
                <el-input v-model="recordingActionForm.notes" type="textarea" :rows="3" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>
        <template v-else>
          <el-form-item label="目标用例">
            <el-select
              v-model="recordingActionForm.webCaseId"
              clearable
              filterable
              remote
              reserve-keyword
              style="width: 100%"
              placeholder="请输入目标用例名称"
              :remote-method="searchCaseOptions"
              :loading="caseSelectLoading"
              @visible-change="handleCaseSelectVisibleChange"
            >
              <el-option v-for="item in caseSelectOptions" :key="item.webCaseId" :label="`${item.caseName} [${item.webCaseId}]`" :value="item.webCaseId" />
            </el-select>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showRecordingActionDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.recordingAction" @click="submitRecordingAction">{{ recordingActionSubmitText }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showReplayDialog" title="录制回放" width="560px" destroy-on-close>
      <el-form :model="replayForm" label-width="120px">
        <el-form-item label="录制会话">
          <el-input :model-value="selectedReplayLabel" readonly />
        </el-form-item>
        <el-form-item label="执行 Agent">
          <el-select v-model="replayForm.agentId" filterable style="width: 100%">
            <el-option v-for="item in agentOptions" :key="item.agentId" :label="`${item.agentName || item.agentCode} [${item.agentCode}]`" :value="item.agentId" />
          </el-select>
        </el-form-item>
        <el-form-item label="浏览器">
          <el-select v-model="replayForm.browserName" style="width: 100%">
            <el-option v-for="item in browserOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="无头模式">
          <el-switch v-model="replayForm.headless" />
        </el-form-item>
        <el-form-item label="结束后关闭浏览器">
          <el-switch v-model="replayForm.closeBrowserOnFinish" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReplayDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.replay" @click="submitReplay">开始回放</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showReplayResultDialog" :title="replayResultTitle" width="1180px" destroy-on-close>
      <template v-if="replayResult">
        <el-alert
          :title="replayResult.errorMessage || (replayResult.status === 'passed' ? '回放执行成功' : '回放执行失败')"
          :type="replayResult.status === 'passed' ? 'success' : 'error'"
          :closable="false"
          show-icon
          class="mb16"
        />
        <el-table :data="replayStepResults" border max-height="320px" class="mb16">
          <el-table-column label="步骤" prop="stepName" min-width="220" />
          <el-table-column label="状态" width="110">
            <template #default="scope">
                <el-tag :type="isPassedStepStatus(scope.row.status) ? 'success' : 'danger'">{{ scope.row.status || "-" }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="110">
            <template #default="scope">{{ formatDuration(scope.row.durationMs) }}</template>
          </el-table-column>
          <el-table-column label="页面" prop="pageUrl" min-width="220" show-overflow-tooltip />
          <el-table-column label="失败原因" prop="error" min-width="260" show-overflow-tooltip />
        </el-table>
        <AceEditor :content="replayResultJsonText" lang="json" :read-only="true" height="260px" />
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="WebCase">
import { ElMessage, ElMessageBox } from "element-plus";
import AceEditor from "@/components/hrm/common/ace-editor.vue";
import { all as getAllAgent } from "@/api/hrm/agent.js";
import { listProject } from "@/api/hrm/project.js";
import { showModulList } from "@/api/hrm/module.js";
import {
  addWebCase,
  applyWebRecording,
  delWebCase,
  getWebCase,
  getWebRecording,
  getWebRun,
  listWebCase,
  listWebRecording,
  listWebRun,
  replayWebRecording,
  runWebCase,
  saveWebRecordingAsCase,
  startWebRecording,
  stopWebRecording,
  updateWebCase,
} from "@/api/hrm/web_case.js";

const { proxy } = getCurrentInstance();

const browserOptions = [
  { label: "Chromium", value: "chromium" },
  { label: "Chrome", value: "chrome" },
  { label: "Microsoft Edge", value: "msedge" },
  { label: "Firefox", value: "firefox" },
  { label: "WebKit", value: "webkit" },
];

const actionOptions = [
  { label: "打开页面", value: "goto" },
  { label: "点击元素", value: "click" },
  { label: "填写内容", value: "fill" },
  { label: "键盘按键", value: "press" },
  { label: "勾选元素", value: "check" },
  { label: "取消勾选", value: "uncheck" },
  { label: "选择下拉项", value: "select_option" },
];

const locatorTypeOptions = [
  { label: "Role", value: "role" },
  { label: "Label", value: "label" },
  { label: "Placeholder", value: "placeholder" },
  { label: "Text", value: "text" },
  { label: "Test ID", value: "test_id" },
  { label: "CSS", value: "css" },
  { label: "XPath", value: "xpath" },
];

const assertionTypeOptions = [
  { label: "文本包含", value: "text_contains" },
  { label: "文本相等", value: "text_equals" },
  { label: "元素可见", value: "visible" },
  { label: "URL包含", value: "url_contains" },
];

const keyboardKeyOptions = [
  ...[
    "Enter",
    "Tab",
    "Escape",
    "Space",
    "Backspace",
    "Delete",
    "Insert",
    "Home",
    "End",
    "PageUp",
    "PageDown",
    "ArrowUp",
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
    "Shift",
    "Control",
    "Alt",
    "Meta",
    "CapsLock",
    "NumLock",
    "ScrollLock",
    "PrintScreen",
    "Pause",
    "ContextMenu",
  ].map((value) => ({ label: value, value })),
  ...Array.from({ length: 12 }, (_, index) => {
    const value = `F${index + 1}`;
    return { label: value, value };
  }),
  ...Array.from({ length: 26 }, (_, index) => {
    const value = String.fromCharCode(65 + index);
    return { label: value, value };
  }),
  ...Array.from({ length: 10 }, (_, index) => {
    const value = `${index}`;
    return { label: value, value };
  }),
];

const runStatusOptions = [
  { label: "成功", value: 1, type: "success" },
  { label: "失败", value: 2, type: "danger" },
  { label: "已跳过", value: 3, type: "info" },
  { label: "异常", value: 8, type: "danger" },
  { label: "执行中", value: 9, type: "warning" },
];

const recordingStatusOptions = [
  { label: "草稿", value: 1, type: "info" },
  { label: "录制中", value: 2, type: "warning" },
  { label: "已完成", value: 3, type: "success" },
  { label: "失败", value: 4, type: "danger" },
  { label: "已停止", value: 5, type: "info" },
];

const activeTab = ref("case");
const pageDataList = ref([]);
const total = ref(0);
const runRecordList = ref([]);
const runTotal = ref(0);
const recordingList = ref([]);
const recordingTotal = ref(0);
const projectOptions = ref([]);
const moduleOptions = ref([]);
const agentOptions = ref([]);
const allCaseOptions = ref([]);
const caseSelectOptions = ref([]);
const caseSelectLoading = ref(false);

const selectedCase = ref(null);
const selectedRecording = ref(null);
const recordingEvents = ref([]);
const liveRecordingSteps = ref([]);
const recordingDetail = ref(null);
const runDetail = ref(null);
const replayResult = ref(null);
const recordingDetailText = ref("");

const loading = ref({
  page: false,
  save: false,
  run: false,
  runPage: false,
  runDetail: false,
  recording: false,
  recordingPage: false,
  recordingDetail: false,
  recordingAction: false,
  replay: false,
});

const queryParams = ref({
  pageNum: 1,
  pageSize: 10,
  caseName: undefined,
  projectId: undefined,
  moduleId: undefined,
});

const runQueryParams = ref({
  pageNum: 1,
  pageSize: 10,
  webCaseId: undefined,
  status: undefined,
  agentCode: undefined,
});

const recordingQueryParams = ref({
  pageNum: 1,
  pageSize: 10,
  sessionName: undefined,
  webCaseId: undefined,
  status: undefined,
});

const showCaseDialog = ref(false);
const showRunDialog = ref(false);
const showRunDetailDialog = ref(false);
const showRecordingDialog = ref(false);
const showRecordingDetailDialog = ref(false);
const showRecordingActionDialog = ref(false);
const showReplayDialog = ref(false);
const showReplayResultDialog = ref(false);
const showStepDetailDialog = ref(false);

const caseEditorTab = ref("visual");
const recordingDetailTab = ref("steps");
const selectedStepIndex = ref(-1);
const stepsText = ref("[]");
let recordingTimer = null;

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function normalizeIdValue(value) {
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  return `${value}`;
}

function isSameId(left, right) {
  const leftId = normalizeIdValue(left);
  const rightId = normalizeIdValue(right);
  return Boolean(leftId) && leftId === rightId;
}

function cloneData(value) {
  const rawValue = toRaw(value);
  if (typeof structuredClone === "function") {
    return structuredClone(rawValue);
  }
  return JSON.parse(JSON.stringify(rawValue ?? null));
}

function extractRows(response) {
  if (Array.isArray(response?.rows)) {
    return response.rows;
  }
  if (Array.isArray(response?.data)) {
    return response.data;
  }
  return [];
}

function normalizeProjectOption(item = {}) {
  return {
    ...item,
    projectId: normalizeIdValue(item.projectId ?? item.project_id),
    projectName: item.projectName || item.project_name || "-",
  };
}

function normalizeModuleOption(item = {}) {
  return {
    ...item,
    moduleId: normalizeIdValue(item.moduleId ?? item.module_id),
    projectId: normalizeIdValue(item.projectId ?? item.project_id),
    moduleName: item.moduleName || item.module_name || "-",
  };
}

function normalizeAgentOption(item = {}) {
  return {
    ...item,
    agentId: normalizeIdValue(item.agentId ?? item.agent_id),
    agentCode: item.agentCode || item.agent_code || "",
    agentName: item.agentName || item.agent_name || "",
  };
}

function normalizeCaseOption(item = {}) {
  const webCaseId = normalizeIdValue(item.webCaseId ?? item.web_case_id);
  if (!webCaseId) {
    return null;
  }
  return {
    ...item,
    webCaseId,
    projectId: normalizeIdValue(item.projectId ?? item.project_id),
    moduleId: normalizeIdValue(item.moduleId ?? item.module_id),
    caseName: item.caseName || item.case_name || "",
    startUrl: item.startUrl || item.start_url || "",
    browserName: item.browserName || item.browser_name || "chromium",
    headless: item.headless ?? false,
    notes: item.notes || "",
  };
}

function mergeCaseOptions(...collections) {
  const optionMap = new Map();
  collections.flat().forEach((item) => {
    const normalized = normalizeCaseOption(item);
    if (!normalized?.webCaseId) {
      return;
    }
    const existing = optionMap.get(normalized.webCaseId) || {};
    optionMap.set(normalized.webCaseId, {
      ...existing,
      ...normalized,
      caseName: normalized.caseName || existing.caseName || normalized.webCaseId,
      projectId: normalized.projectId || existing.projectId,
      moduleId: normalized.moduleId || existing.moduleId,
    });
  });
  return Array.from(optionMap.values());
}

function safeJsonStringify(value) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch (error) {
    return "{}";
  }
}

function createDefaultContext() {
  return {
    pageUrl: "",
    frameUrl: "",
    frameChain: [],
    shadowChain: [],
  };
}

function normalizeLocatorValue(locatorType, locatorValue) {
  if (locatorType === "role") {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      role: value.role || "",
      name: value.name || "",
      exact: Boolean(value.exact),
    };
  }
  if (["label", "placeholder", "text"].includes(locatorType)) {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      text: value.text || "",
      exact: Boolean(value.exact),
    };
  }
  if (locatorType === "test_id") {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      testId: value.testId || "",
    };
  }
  if (["css", "xpath"].includes(locatorType)) {
    if (typeof locatorValue === "string") {
      return { selector: locatorValue };
    }
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      selector: value.selector || "",
    };
  }
  return isPlainObject(locatorValue) ? cloneData(locatorValue) : {};
}

function createDefaultLocator(locatorType = "css") {
  return {
    locatorSnapshotId: undefined,
    locatorType,
    locatorValue: normalizeLocatorValue(locatorType, {}),
    priority: 0,
    enabled: true,
  };
}

function normalizeLocator(locator = {}, index = 0) {
  const locatorType = locator.locatorType || locator.locator_type || "css";
  return {
    locatorSnapshotId: locator.locatorSnapshotId || locator.locator_snapshot_id,
    locatorType,
    locatorValue: normalizeLocatorValue(locatorType, locator.locatorValue ?? locator.locator_value),
    priority: Number.isFinite(Number(locator.priority)) ? Number(locator.priority) : index,
    enabled: locator.enabled !== false,
  };
}

function createDefaultTargetSnapshot() {
  return {
    targetSnapshotId: undefined,
    fingerprint: "",
    elementText: "",
    stableScore: 0,
    context: createDefaultContext(),
    locators: [createDefaultLocator()],
  };
}

function normalizeTargetSnapshot(snapshot) {
  if (!snapshot) {
    return null;
  }
  const context = isPlainObject(snapshot.context) ? snapshot.context : {};
  return {
    targetSnapshotId: snapshot.targetSnapshotId || snapshot.target_snapshot_id,
    fingerprint: snapshot.fingerprint || "",
    elementText: snapshot.elementText || snapshot.element_text || "",
    stableScore: Number(snapshot.stableScore ?? snapshot.stable_score ?? 0),
    context: {
      pageUrl: context.pageUrl || context.page_url || "",
      frameUrl: context.frameUrl || context.frame_url || "",
      frameChain: Array.isArray(context.frameChain || context.frame_chain) ? cloneData(context.frameChain || context.frame_chain) : [],
      shadowChain: Array.isArray(context.shadowChain || context.shadow_chain) ? cloneData(context.shadowChain || context.shadow_chain) : [],
    },
    locators: Array.isArray(snapshot.locators) ? snapshot.locators.map((item, index) => normalizeLocator(item, index)) : [],
  };
}

function createDefaultAssertion(assertType = "visible") {
  return {
    assertType,
    expected: "",
    operator: "",
    actualSource: "",
    enabled: true,
  };
}

function normalizeAssertion(assertion = {}) {
  return {
    assertType: assertion.assertType || assertion.assert_type || "visible",
    expected: assertion.expected ?? "",
    operator: assertion.operator || "",
    actualSource: assertion.actualSource || assertion.actual_source || "",
    enabled: assertion.enabled !== false,
  };
}

function stepNeedsTarget(actionType) {
  return actionType !== "goto";
}

function getActionLabel(actionType) {
  return actionOptions.find((item) => item.value === actionType)?.label || actionType || "未设置";
}

function normalizeStepParams(actionType, params) {
  const data = isPlainObject(params) ? cloneData(params) : {};
  if (actionType === "goto") {
    return { url: data.url || "" };
  }
  if (actionType === "fill") {
    return { value: data.value ?? "" };
  }
  if (actionType === "press") {
    return { key: data.key || "Enter" };
  }
  if (actionType === "select_option") {
    const values = Array.isArray(data.values) ? data.values : data.values ? [data.values] : [];
    return { values: values.map((item) => `${item}`) };
  }
  return {};
}

function normalizeStep(step = {}, index = 0) {
  const actionType = step.actionType || step.action_type || "click";
  const targetSnapshot = normalizeTargetSnapshot(step.targetSnapshot || step.target_snapshot);
  return {
    stepId: step.stepId || step.step_id,
    stepIndex: Number(step.stepIndex ?? step.step_index ?? index + 1),
    stepName: step.stepName || step.step_name || `${getActionLabel(actionType)} ${index + 1}`,
    actionType,
    enabled: step.enabled !== false,
    timeoutMs: step.timeoutMs ?? step.timeout_ms,
    continueOnFailure: Boolean(step.continueOnFailure || step.continue_on_failure),
    recordOrigin: step.recordOrigin || step.record_origin || "manual",
    elementId: step.elementId || step.element_id,
    params: normalizeStepParams(actionType, step.params),
    assertions: Array.isArray(step.assertions) ? step.assertions.map(normalizeAssertion) : [],
    rawEvent: isPlainObject(step.rawEvent || step.raw_event) ? cloneData(step.rawEvent || step.raw_event) : {},
    targetSnapshot: stepNeedsTarget(actionType) ? (targetSnapshot || createDefaultTargetSnapshot()) : targetSnapshot,
  };
}

function createDefaultStep(actionType = "click") {
  return normalizeStep({ actionType, stepName: getActionLabel(actionType), targetSnapshot: stepNeedsTarget(actionType) ? createDefaultTargetSnapshot() : null });
}

function createEmptyCase() {
  return {
    webCaseId: undefined,
    caseName: "新增 Web 用例",
    projectId: undefined,
    moduleId: undefined,
    startUrl: "",
    browserName: "chromium",
    headless: false,
    runtimeSettings: {},
    notes: "",
    status: 2,
    remark: "",
    steps: [],
  };
}

function normalizeCase(data = {}) {
  const base = createEmptyCase();
  return {
    ...base,
    ...data,
    webCaseId: normalizeIdValue(data.webCaseId || data.web_case_id),
    caseName: data.caseName || data.case_name || base.caseName,
    projectId: normalizeIdValue(data.projectId || data.project_id),
    moduleId: normalizeIdValue(data.moduleId || data.module_id),
    startUrl: data.startUrl || data.start_url || "",
    browserName: data.browserName || data.browser_name || base.browserName,
    headless: data.headless ?? base.headless,
    runtimeSettings: isPlainObject(data.runtimeSettings || data.runtime_settings) ? cloneData(data.runtimeSettings || data.runtime_settings) : {},
    notes: data.notes || "",
    status: data.status ?? 2,
    remark: data.remark || "",
    steps: Array.isArray(data.steps) ? data.steps.map((step, index) => normalizeStep(step, index)) : [],
  };
}

const form = ref(createEmptyCase());
const runForm = ref({
  agentId: undefined,
  browserName: "chromium",
  headless: true,
  closeBrowserOnFinish: true,
});
const recordingForm = ref({
  webCaseId: undefined,
  sessionName: "",
  agentId: undefined,
  browserName: "chromium",
  headless: false,
  startUrl: "",
  closeBrowserOnStop: true,
  recordingId: undefined,
});
const recordingActionMode = ref("create");
const recordingActionForm = ref({
  recordingId: undefined,
  webCaseId: undefined,
  caseName: "",
  projectId: undefined,
  moduleId: undefined,
  startUrl: "",
  browserName: "chromium",
  headless: false,
  notes: "",
});
const replayForm = ref({
  recordingId: undefined,
  agentId: undefined,
  browserName: "chromium",
  headless: false,
  closeBrowserOnFinish: true,
});

const projectNameMap = computed(() => Object.fromEntries(projectOptions.value.map((item) => [item.projectId, item.projectName])));
const moduleNameMap = computed(() => Object.fromEntries(moduleOptions.value.map((item) => [item.moduleId, item.moduleName])));
const caseNameMap = computed(() => Object.fromEntries(
  mergeCaseOptions(
    allCaseOptions.value,
    caseSelectOptions.value,
    pageDataList.value,
    runRecordList.value,
    recordingList.value,
    runDetail.value ? [runDetail.value] : [],
    recordingDetail.value ? [recordingDetail.value] : []
  ).map((item) => [item.webCaseId, item.caseName])
));

const filteredSearchModules = computed(() => {
  if (!queryParams.value.projectId) return moduleOptions.value;
  return moduleOptions.value.filter((item) => isSameId(item.projectId, queryParams.value.projectId));
});

const filteredCaseModules = computed(() => {
  if (!form.value.projectId) return moduleOptions.value;
  return moduleOptions.value.filter((item) => isSameId(item.projectId, form.value.projectId));
});

const filteredRecordingActionModules = computed(() => {
  if (!recordingActionForm.value.projectId) return moduleOptions.value;
  return moduleOptions.value.filter((item) => isSameId(item.projectId, recordingActionForm.value.projectId));
});

const caseDialogTitle = computed(() => `${form.value.webCaseId ? "编辑" : "新增"} Web 用例`);
const currentStep = computed(() => form.value.steps[selectedStepIndex.value] || null);
const stepDetailTitle = computed(() => (selectedStepIndex.value >= 0 ? `步骤详情 - #${selectedStepIndex.value + 1}` : "步骤详情"));
const runDetailTitle = computed(() => {
  if (!runDetail.value) return "执行详情";
  return `执行详情 - ${runDetail.value.caseName || getCaseName(runDetail.value.webCaseId) || runDetail.value.webCaseId}`;
});
const runStepResults = computed(() => Array.isArray(runDetail.value?.result?.steps) ? runDetail.value.result.steps : []);
const runDetailJsonText = computed(() => safeJsonStringify(runDetail.value?.result || {}));

const recordingLinkedCaseLabel = computed(() => {
  if (!recordingForm.value.webCaseId) return "独立录制";
  return `${getCaseName(recordingForm.value.webCaseId) || recordingForm.value.webCaseId} [${recordingForm.value.webCaseId}]`;
});

const recordingDialogTitle = computed(() => (recordingForm.value.recordingId ? `录制 Web 步骤 [${recordingForm.value.recordingId}]` : "录制 Web 步骤"));
const recordingDetailTitle = computed(() => {
  if (!recordingDetail.value) return "录制详情";
  return `录制详情 - ${recordingDetail.value.sessionName || recordingDetail.value.recordingId}`;
});
const recordingPreviewSteps = computed(() => Array.isArray(recordingDetail.value?.steps) ? recordingDetail.value.steps : []);
const recordingEventRows = computed(() => Array.isArray(recordingDetail.value?.events) ? recordingDetail.value.events : []);
const recordingDetailJsonText = computed(() => safeJsonStringify(recordingDetail.value || {}));

const recordingLiveStatusMeta = computed(() => getRecordingStatusMeta(recordingDetail.value?.status || (recordingForm.value.recordingId ? 2 : 1)));
const recordingResultReady = computed(() => canUseRecordingResult(recordingDetail.value?.status) && liveRecordingSteps.value.length > 0);
const recordingLiveStatusText = computed(() => {
  if (!recordingForm.value.recordingId) {
    return "请先填写录制参数后启动录制。";
  }
  if (recordingDetail.value?.status === 5) {
    return "停止指令已发送，正在等待录制结果落盘。";
  }
  return `录制状态：${recordingLiveStatusMeta.value.label}`;
});
const recordingLiveStatusType = computed(() => recordingLiveStatusMeta.value.type);

const recordingActionDialogTitle = computed(() => {
  if (recordingActionMode.value === "create") return "将录制保存为新用例";
  if (recordingActionMode.value === "append") return "将录制追加到用例";
  return "使用录制覆盖用例步骤";
});

const recordingActionDialogTip = computed(() => {
  if (recordingActionMode.value === "create") return "当前录制会保存成一个独立的新 Web 用例。";
  if (recordingActionMode.value === "append") return "会把录制得到的步骤追加到目标用例尾部，不会覆盖原步骤。";
  return "会使用当前录制步骤替换目标用例原有步骤，请确认后再执行。";
});

const recordingActionSubmitText = computed(() => (recordingActionMode.value === "create" ? "保存新用例" : "确认应用"));
const selectedReplayLabel = computed(() => {
  if (!selectedRecording.value) return "";
  return `${selectedRecording.value.sessionName || "录制回放"} [${selectedRecording.value.recordingId}]`;
});
const replayResultTitle = computed(() => {
  if (!replayResult.value) return "回放结果";
  return `${replayResult.value.sessionName || "录制回放"} - ${replayResult.value.status === "passed" ? "成功" : "失败"}`;
});
const replayStepResults = computed(() => Array.isArray(replayResult.value?.result?.steps) ? replayResult.value.result.steps : []);
const replayResultJsonText = computed(() => safeJsonStringify(replayResult.value?.result || replayResult.value || {}));

function formatTime(value) {
  return value ? proxy.parseTime(value) : "-";
}

function formatDuration(value) {
  if (value === undefined || value === null || value === "") return "-";
  const ms = Number(value);
  if (!Number.isFinite(ms)) return `${value}`;
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)}s`;
  const minutes = Math.floor(ms / 60000);
  const seconds = ((ms % 60000) / 1000).toFixed(1);
  return `${minutes}m ${seconds}s`;
}

function getRunStatusMeta(status) {
  return runStatusOptions.find((item) => item.value === status) || { label: `${status ?? "-"}`, type: "info" };
}

function getRecordingStatusMeta(status) {
  return recordingStatusOptions.find((item) => item.value === status) || { label: `${status ?? "-"}`, type: "info" };
}

function isPassedStepStatus(status) {
  return ["passed", "success", "ok", 1, true].includes(status);
}

function getProjectName(projectId) {
  const targetId = normalizeIdValue(projectId);
  if (!targetId) {
    return "";
  }
  return projectNameMap.value[targetId] || projectOptions.value.find((item) => isSameId(item.projectId, targetId))?.projectName || "";
}

function getModuleName(moduleId) {
  const targetId = normalizeIdValue(moduleId);
  if (!targetId) {
    return "";
  }
  return moduleNameMap.value[targetId] || moduleOptions.value.find((item) => isSameId(item.moduleId, targetId))?.moduleName || "";
}

function getCaseName(webCaseId) {
  const targetId = normalizeIdValue(webCaseId);
  if (!targetId) {
    return "";
  }
  return caseNameMap.value[targetId] || mergeCaseOptions(pageDataList.value, allCaseOptions.value, caseSelectOptions.value).find((item) => isSameId(item.webCaseId, targetId))?.caseName || "";
}

function syncCaseOptions(...collections) {
  const mergedAll = mergeCaseOptions(allCaseOptions.value, ...collections);
  const mergedSelect = mergeCaseOptions(caseSelectOptions.value, ...collections);
  allCaseOptions.value = mergedAll;
  caseSelectOptions.value = mergedSelect.length ? mergedSelect : mergedAll;
}

function loadAllCaseOptions(force = false) {
  if (!force && allCaseOptions.value.length) {
    return Promise.resolve(allCaseOptions.value);
  }
  return searchCaseOptions("");
}

function searchCaseOptions(keyword = "") {
  const searchKeyword = keyword?.trim();
  caseSelectLoading.value = true;
  return listWebCase({
    pageNum: 1,
    pageSize: searchKeyword ? 50 : 200,
    caseName: searchKeyword || undefined,
  }).then((response) => {
    const rows = mergeCaseOptions(extractRows(response));
    caseSelectOptions.value = rows;
    allCaseOptions.value = mergeCaseOptions(allCaseOptions.value, rows);
    return rows;
  }).finally(() => {
    caseSelectLoading.value = false;
  });
}

function handleCaseSelectVisibleChange(visible) {
  if (visible && !caseSelectOptions.value.length) {
    searchCaseOptions("");
  }
}

function shouldStopRecordingPoll(status) {
  return [3, 4].includes(Number(status));
}

function canUseRecordingResult(status) {
  return [3, 4, 5].includes(Number(status));
}

function describeLocator(locator) {
  if (!locator) return "未设置定位器";
  if (locator.locatorType === "role") {
    return `role=${locator.locatorValue.role || "-"} / name=${locator.locatorValue.name || "-"}`;
  }
  if (["label", "placeholder", "text"].includes(locator.locatorType)) {
    return `${locator.locatorType}=${locator.locatorValue.text || "-"}`;
  }
  if (locator.locatorType === "test_id") {
    return `testId=${locator.locatorValue.testId || "-"}`;
  }
  return `${locator.locatorType}=${locator.locatorValue.selector || "-"}`;
}

function describeStepTarget(step) {
  if (!stepNeedsTarget(step.actionType)) {
    return step.params?.url || "页面跳转";
  }
  const firstLocator = step.targetSnapshot?.locators?.find((item) => item.enabled !== false) || step.targetSnapshot?.locators?.[0];
  const locatorText = firstLocator ? describeLocator(firstLocator) : "未设置定位器";
  const elementText = step.targetSnapshot?.elementText ? ` / 文本=${step.targetSnapshot.elementText}` : "";
  return `${locatorText}${elementText}`;
}

function summarizeStepParams(step) {
  if (!step) return "-";
  if (step.actionType === "goto") return step.params?.url || "-";
  if (step.actionType === "fill") return step.params?.value || "-";
  if (step.actionType === "press") return step.params?.key || "-";
  if (step.actionType === "select_option") return Array.isArray(step.params?.values) && step.params.values.length ? step.params.values.join(", ") : "-";
  return "-";
}

function syncStepsTextFromForm() {
  stepsText.value = safeJsonStringify(form.value.steps.map((step, index) => prepareStepForSubmit(step, index + 1)));
}

function applyStepsTextToForm(showSuccess = false) {
  let parsedSteps = [];
  try {
    parsedSteps = JSON.parse(stepsText.value || "[]");
  } catch (error) {
    ElMessage.error(`步骤 JSON 解析失败：${error.message}`);
    return false;
  }
  if (!Array.isArray(parsedSteps)) {
    ElMessage.error("步骤 JSON 必须是数组");
    return false;
  }
  form.value.steps = parsedSteps.map((step, index) => normalizeStep(step, index));
  selectedStepIndex.value = form.value.steps.length ? 0 : -1;
  if (showSuccess) {
    ElMessage.success("JSON 已同步到可视化编辑器");
  }
  return true;
}

function stripStepIdentity(step) {
  const cloned = normalizeStep(cloneData(step));
  cloned.stepId = undefined;
  if (cloned.targetSnapshot) {
    cloned.targetSnapshot.targetSnapshotId = undefined;
    cloned.targetSnapshot.locators = cloned.targetSnapshot.locators.map((locator, index) => ({
      ...locator,
      locatorSnapshotId: undefined,
      priority: index,
    }));
  }
  return cloned;
}

function selectStep(index) {
  selectedStepIndex.value = index;
}

function openStepDetailByIndex(index) {
  if (index < 0 || index >= form.value.steps.length) {
    return;
  }
  form.value.steps[index] = normalizeStep(form.value.steps[index], index);
  if (stepNeedsTarget(form.value.steps[index]?.actionType)) {
    getPrimaryLocator(form.value.steps[index]);
  }
  selectedStepIndex.value = index;
  showStepDetailDialog.value = true;
}

function handleStepRowClick(row) {
  const index = form.value.steps.indexOf(row);
  if (index === -1) {
    return;
  }
  openStepDetailByIndex(index);
}

function getStepRowClassName({ row }) {
  return form.value.steps.indexOf(row) === selectedStepIndex.value ? "selected-step-row" : "";
}

function addStep(actionType = "click") {
  form.value.steps.push(createDefaultStep(actionType));
  selectedStepIndex.value = form.value.steps.length - 1;
}

function copyStep(index) {
  const source = form.value.steps[index];
  if (!source) return;
  const copied = stripStepIdentity(source);
  copied.stepName = `${copied.stepName} - 副本`;
  form.value.steps.splice(index + 1, 0, copied);
  selectedStepIndex.value = index + 1;
}

function removeStep(index) {
  form.value.steps.splice(index, 1);
  if (!form.value.steps.length) {
    selectedStepIndex.value = -1;
    return;
  }
  selectedStepIndex.value = Math.min(index, form.value.steps.length - 1);
}

function moveStep(index, direction) {
  const targetIndex = index + direction;
  if (targetIndex < 0 || targetIndex >= form.value.steps.length) return;
  const steps = [...form.value.steps];
  [steps[index], steps[targetIndex]] = [steps[targetIndex], steps[index]];
  form.value.steps = steps;
  selectedStepIndex.value = targetIndex;
}

function addLocator(step) {
  if (!step.targetSnapshot) {
    step.targetSnapshot = createDefaultTargetSnapshot();
  }
  if (!Array.isArray(step.targetSnapshot.locators)) {
    step.targetSnapshot.locators = [];
  }
  step.targetSnapshot.locators.push(createDefaultLocator());
}

function moveLocator(step, index, direction) {
  if (!step?.targetSnapshot?.locators) return;
  const targetIndex = index + direction;
  if (targetIndex < 0 || targetIndex >= step.targetSnapshot.locators.length) return;
  const locators = [...step.targetSnapshot.locators];
  [locators[index], locators[targetIndex]] = [locators[targetIndex], locators[index]];
  step.targetSnapshot.locators = locators;
}

function removeLocator(step, index) {
  if (!step?.targetSnapshot?.locators) return;
  step.targetSnapshot.locators.splice(index, 1);
}

function addAssertion(step) {
  step.assertions.push(createDefaultAssertion());
}

function removeAssertion(step, index) {
  step.assertions.splice(index, 1);
}

function handleStepActionTypeChange(step) {
  step.params = normalizeStepParams(step.actionType, step.params);
  if (stepNeedsTarget(step.actionType) && !step.targetSnapshot) {
    step.targetSnapshot = createDefaultTargetSnapshot();
  }
}

function getPrimaryLocator(step) {
  if (!stepNeedsTarget(step?.actionType)) {
    return null;
  }
  if (!step.targetSnapshot) {
    step.targetSnapshot = createDefaultTargetSnapshot();
  }
  if (!Array.isArray(step.targetSnapshot.locators) || !step.targetSnapshot.locators.length) {
    step.targetSnapshot.locators = [createDefaultLocator()];
  }
  return step.targetSnapshot.locators.find((item) => item.enabled !== false) || step.targetSnapshot.locators[0];
}

function updatePrimaryLocatorType(step, locatorType) {
  const locator = getPrimaryLocator(step);
  if (!locator) {
    return;
  }
  locator.locatorType = locatorType;
  locator.locatorValue = normalizeLocatorValue(locatorType, {});
}

function updatePrimaryLocatorValue(step, key, value) {
  const locator = getPrimaryLocator(step);
  if (!locator) {
    return;
  }
  locator.locatorValue = normalizeLocatorValue(locator.locatorType, locator.locatorValue);
  locator.locatorValue[key] = value;
}

function handleLocatorTypeChange(locator) {
  locator.locatorValue = normalizeLocatorValue(locator.locatorType, locator.locatorValue);
}

function isLocatorFilled(locator) {
  if (!locator || locator.enabled === false) return false;
  if (locator.locatorType === "role") {
    return Boolean(locator.locatorValue.role);
  }
  if (["label", "placeholder", "text"].includes(locator.locatorType)) {
    return Boolean(locator.locatorValue.text);
  }
  if (locator.locatorType === "test_id") {
    return Boolean(locator.locatorValue.testId);
  }
  return Boolean(locator.locatorValue.selector);
}

function getCaseValidationError() {
  if (!form.value.caseName?.trim()) return "用例名称不能为空";
  if (!form.value.steps.length) return "至少需要一个测试步骤";

  for (let index = 0; index < form.value.steps.length; index += 1) {
    const step = normalizeStep(form.value.steps[index], index);
    if (!step.stepName?.trim()) return `步骤${index + 1}名称不能为空`;
    if (!step.actionType) return `步骤${index + 1}缺少动作类型`;
    if (step.actionType === "goto" && !step.params.url?.trim()) return `步骤${index + 1}缺少跳转地址`;
    if (step.actionType === "press" && !step.params.key?.trim()) return `步骤${index + 1}缺少按键值`;
    if (step.actionType === "select_option" && (!Array.isArray(step.params.values) || !step.params.values.length)) {
      return `步骤${index + 1}至少需要一个下拉项值`;
    }
    if (stepNeedsTarget(step.actionType)) {
      const locators = step.targetSnapshot?.locators || [];
      if (!locators.length) return `步骤${index + 1}至少需要一个定位器`;
      if (!locators.some(isLocatorFilled)) return `步骤${index + 1}至少需要一个可用定位器`;
    }
  }
  return "";
}

function prepareAssertionForSubmit(assertion) {
  return {
    assertType: assertion.assertType,
    expected: assertion.expected ?? "",
    operator: assertion.operator || undefined,
    actualSource: assertion.actualSource || undefined,
    enabled: assertion.enabled !== false,
  };
}

function prepareLocatorForSubmit(locator, index) {
  return {
    locatorSnapshotId: locator.locatorSnapshotId,
    locatorType: locator.locatorType,
    locatorValue: normalizeLocatorValue(locator.locatorType, locator.locatorValue),
    priority: index,
    enabled: locator.enabled !== false,
  };
}

function prepareTargetSnapshotForSubmit(snapshot) {
  const normalized = normalizeTargetSnapshot(snapshot) || createDefaultTargetSnapshot();
  return {
    targetSnapshotId: normalized.targetSnapshotId,
    fingerprint: normalized.fingerprint || undefined,
    elementText: normalized.elementText || "",
    stableScore: Number(normalized.stableScore || 0),
    context: {
      pageUrl: normalized.context.pageUrl || "",
      frameUrl: normalized.context.frameUrl || "",
      frameChain: normalized.context.frameChain || [],
      shadowChain: normalized.context.shadowChain || [],
    },
    locators: normalized.locators.map((locator, index) => prepareLocatorForSubmit(locator, index)),
  };
}

function buildStepParamsForSubmit(step) {
  if (step.actionType === "goto") {
    return { url: step.params.url || "" };
  }
  if (step.actionType === "fill") {
    return { value: step.params.value ?? "" };
  }
  if (step.actionType === "press") {
    return { key: step.params.key || "Enter" };
  }
  if (step.actionType === "select_option") {
    return { values: Array.isArray(step.params.values) ? step.params.values.filter((item) => `${item}`.trim()) : [] };
  }
  return {};
}

function prepareStepForSubmit(step, index) {
  const normalized = normalizeStep(step, index - 1);
  return {
    stepId: normalized.stepId,
    stepIndex: index,
    stepName: normalized.stepName?.trim() || `步骤${index}`,
    actionType: normalized.actionType,
    enabled: normalized.enabled !== false,
    timeoutMs: normalized.timeoutMs ?? undefined,
    continueOnFailure: Boolean(normalized.continueOnFailure),
    recordOrigin: normalized.recordOrigin || "manual",
    elementId: normalized.elementId || undefined,
    params: buildStepParamsForSubmit(normalized),
    assertions: normalized.assertions.map(prepareAssertionForSubmit),
    rawEvent: normalized.rawEvent || {},
    targetSnapshot: stepNeedsTarget(normalized.actionType) ? prepareTargetSnapshotForSubmit(normalized.targetSnapshot) : null,
  };
}

function resetForm() {
  form.value = createEmptyCase();
  selectedStepIndex.value = -1;
  caseEditorTab.value = "visual";
  syncStepsTextFromForm();
}

function resetQuery() {
  queryParams.value = { pageNum: 1, pageSize: 10, caseName: undefined, projectId: undefined, moduleId: undefined };
  getList();
}

function resetRunQuery() {
  runQueryParams.value = { pageNum: 1, pageSize: 10, webCaseId: undefined, status: undefined, agentCode: undefined };
  getRunList();
}

function resetRecordingQuery() {
  recordingQueryParams.value = { pageNum: 1, pageSize: 10, sessionName: undefined, webCaseId: undefined, status: undefined };
  getRecordingList();
}

async function loadBaseData() {
  const [projectRes, moduleRes, agentRes] = await Promise.all([
    listProject({ isPage: false }),
    showModulList({ isPage: false }),
    getAllAgent(),
  ]);
  projectOptions.value = extractRows(projectRes).map(normalizeProjectOption);
  moduleOptions.value = extractRows(moduleRes).map(normalizeModuleOption);
  agentOptions.value = extractRows(agentRes).map(normalizeAgentOption);
}

function getList() {
  loading.value.page = true;
  listWebCase(queryParams.value).then((response) => {
    pageDataList.value = (response.rows || []).map((item) => normalizeCaseOption(item) || item);
    total.value = response.total || 0;
    syncCaseOptions(pageDataList.value);
  }).finally(() => {
    loading.value.page = false;
  });
}

function getRunList() {
  loading.value.runPage = true;
  listWebRun(runQueryParams.value).then((response) => {
    runRecordList.value = response.rows || [];
    runTotal.value = response.total || 0;
    syncCaseOptions(runRecordList.value);
  }).finally(() => {
    loading.value.runPage = false;
  });
}

function getRecordingList() {
  loading.value.recordingPage = true;
  listWebRecording(recordingQueryParams.value).then((response) => {
    recordingList.value = response.rows || [];
    recordingTotal.value = response.total || 0;
    syncCaseOptions(recordingList.value);
  }).finally(() => {
    loading.value.recordingPage = false;
  });
}

function handleAdd() {
  resetForm();
  showCaseDialog.value = true;
}

function handleEdit(row) {
  return getWebCase(row.webCaseId).then((response) => {
    form.value = normalizeCase(response.data || {});
    syncCaseOptions(form.value);
    selectedStepIndex.value = form.value.steps.length ? 0 : -1;
    syncStepsTextFromForm();
    caseEditorTab.value = "visual";
    showCaseDialog.value = true;
  });
}

function handleDelete(row) {
  ElMessageBox.confirm(`是否确认删除 Web 用例【${row.caseName}】？`, "提示", { type: "warning" }).then(() => {
    return delWebCase(row.webCaseId);
  }).then(async () => {
    ElMessage.success("删除成功");
    getList();
    await loadAllCaseOptions(true);
  }).catch(() => {});
}

function saveCase() {
  if (caseEditorTab.value === "json" && !applyStepsTextToForm()) {
    return;
  }
  const errorMessage = getCaseValidationError();
  if (errorMessage) {
    ElMessage.error(errorMessage);
    return;
  }

  loading.value.save = true;
  const rawForm = toRaw(form.value) || {};
  const payload = {
    ...rawForm,
    runtimeSettings: isPlainObject(rawForm.runtimeSettings) ? cloneData(rawForm.runtimeSettings) : {},
    steps: form.value.steps.map((step, index) => prepareStepForSubmit(step, index + 1)),
  };
  const request = payload.webCaseId ? updateWebCase(payload) : addWebCase(payload);
  request.then(async () => {
    ElMessage.success("保存成功");
    showCaseDialog.value = false;
    getList();
    await loadAllCaseOptions(true);
  }).finally(() => {
    loading.value.save = false;
  });
}

function openRunDialog(row) {
  selectedCase.value = row;
  runForm.value = {
    agentId: undefined,
    browserName: row.browserName || "chromium",
    headless: row.headless ?? true,
    closeBrowserOnFinish: true,
  };
  showRunDialog.value = true;
}

function openRunHistory(row) {
  activeTab.value = "run";
  runQueryParams.value.webCaseId = row.webCaseId;
  runQueryParams.value.pageNum = 1;
  getRunList();
}

function openRunDetail(row) {
  loading.value.runDetail = true;
  getWebRun(row.webCaseRunId).then((response) => {
    runDetail.value = response.data || null;
    syncCaseOptions(runDetail.value);
    showRunDetailDialog.value = true;
  }).finally(() => {
    loading.value.runDetail = false;
  });
}

function submitRun() {
  if (!selectedCase.value?.webCaseId) {
    ElMessage.error("请选择要执行的用例");
    return;
  }
  if (!runForm.value.agentId) {
    ElMessage.error("请选择执行 Agent");
    return;
  }

  loading.value.run = true;
  runWebCase({
    webCaseId: selectedCase.value.webCaseId,
    agentId: runForm.value.agentId,
    browserName: runForm.value.browserName,
    headless: runForm.value.headless,
    closeBrowserOnFinish: runForm.value.closeBrowserOnFinish,
  }).then((response) => {
    ElMessage.success(response.msg || "执行完成");
    showRunDialog.value = false;
    activeTab.value = "run";
    runQueryParams.value.webCaseId = selectedCase.value.webCaseId;
    getRunList();
    if (response.data?.webCaseRunId) {
      openRunDetail(response.data);
    }
  }).catch(() => {
    activeTab.value = "run";
    runQueryParams.value.webCaseId = selectedCase.value.webCaseId;
    getRunList();
  }).finally(() => {
    loading.value.run = false;
  });
}

function resetRecordingDialogState(row = null) {
  stopRecordingPoll();
  selectedCase.value = row || null;
  recordingEvents.value = [];
  liveRecordingSteps.value = [];
  recordingDetail.value = null;
  recordingDetailText.value = "";
  recordingForm.value = {
    webCaseId: row?.webCaseId,
    sessionName: row ? `${row.caseName}-录制` : "",
    agentId: undefined,
    browserName: row?.browserName || "chromium",
    headless: false,
    startUrl: row?.startUrl || "",
    closeBrowserOnStop: true,
    recordingId: undefined,
  };
}

function openRecordingDialog(row = null) {
  resetRecordingDialogState(row);
  showRecordingDialog.value = true;
}

function startRecordingPoll() {
  stopRecordingPoll();
  recordingTimer = window.setInterval(() => {
    if (recordingForm.value.recordingId) {
      refreshRecording();
    }
  }, 3000);
}

function stopRecordingPoll() {
  if (recordingTimer) {
    window.clearInterval(recordingTimer);
    recordingTimer = null;
  }
}

function updateLiveRecording(detail) {
  recordingDetail.value = detail;
  recordingEvents.value = detail.events || [];
  liveRecordingSteps.value = detail.steps || [];
  recordingDetailText.value = safeJsonStringify(detail);
  if (shouldStopRecordingPoll(detail.status)) {
    stopRecordingPoll();
  }
}

function fetchRecordingDetail(recordingId) {
  return getWebRecording(recordingId).then((response) => response.data || {});
}

function startRecording() {
  if (!recordingForm.value.agentId) {
    ElMessage.error("请选择执行 Agent");
    return;
  }
  if (!recordingForm.value.startUrl?.trim()) {
    ElMessage.error("请填写录制起始地址");
    return;
  }

  loading.value.recording = true;
  startWebRecording({
    webCaseId: recordingForm.value.webCaseId,
    agentId: recordingForm.value.agentId,
    sessionName: recordingForm.value.sessionName || undefined,
    browserName: recordingForm.value.browserName,
    headless: recordingForm.value.headless,
    startUrl: recordingForm.value.startUrl,
    recordingOptions: {
      closeBrowserOnStop: recordingForm.value.closeBrowserOnStop,
    },
  }).then((response) => {
    recordingForm.value.recordingId = response.data?.recordingId;
    ElMessage.success(response.msg || "录制已启动");
    refreshRecording();
    startRecordingPoll();
    getRecordingList();
  }).finally(() => {
    loading.value.recording = false;
  });
}

function stopRecording() {
  if (!recordingForm.value.recordingId) return;
  stopWebRecording({
    recordingId: recordingForm.value.recordingId,
    agentId: recordingForm.value.agentId,
    closeBrowserOnStop: recordingForm.value.closeBrowserOnStop,
  }).then((response) => {
    ElMessage.success(response.msg || "已发送停止录制指令");
    refreshRecording();
    getRecordingList();
  });
}

function refreshRecording() {
  if (!recordingForm.value.recordingId) return;
  fetchRecordingDetail(recordingForm.value.recordingId).then((detail) => {
    updateLiveRecording(detail);
  });
}

function openRecordingDetail(recordingSource) {
  const recordingId = typeof recordingSource === "number" ? recordingSource : recordingSource?.recordingId;
  if (!recordingId) return;
  loading.value.recordingDetail = true;
  fetchRecordingDetail(recordingId).then((detail) => {
    recordingDetail.value = detail;
    syncCaseOptions(detail);
    selectedRecording.value = detail;
    showRecordingDetailDialog.value = true;
  }).finally(() => {
    loading.value.recordingDetail = false;
  });
}

function buildRecordingActionDefaults(detail) {
  const linkedCase = mergeCaseOptions(allCaseOptions.value, pageDataList.value, caseSelectOptions.value).find((item) => isSameId(item.webCaseId, detail.webCaseId));
  return {
    recordingId: detail.recordingId,
    webCaseId: normalizeIdValue(detail.webCaseId || selectedCase.value?.webCaseId),
    caseName: `${linkedCase?.caseName || detail.sessionName || "录制结果"}-${detail.recordingId}`,
    projectId: linkedCase?.projectId,
    moduleId: linkedCase?.moduleId,
    startUrl: detail.startUrl || linkedCase?.startUrl || "",
    browserName: detail.browserName || linkedCase?.browserName || "chromium",
    headless: detail.headless ?? linkedCase?.headless ?? false,
    notes: linkedCase?.notes || `由录制[${detail.sessionName || detail.recordingId}]生成`,
  };
}

function resolveRecordingSource(recordingSource) {
  if (typeof recordingSource === "number") {
    return fetchRecordingDetail(recordingSource);
  }
  if (recordingSource?.recordingId && Array.isArray(recordingSource.steps)) {
    return Promise.resolve(recordingSource);
  }
  if (recordingSource?.recordingId) {
    return fetchRecordingDetail(recordingSource.recordingId);
  }
  return Promise.resolve(null);
}

function openRecordingActionDialog(mode, recordingSource) {
  resolveRecordingSource(recordingSource).then((detail) => {
    if (!detail?.recordingId) {
      ElMessage.error("未找到可用录制记录");
      return;
    }
    if (!canUseRecordingResult(detail.status)) {
      ElMessage.warning("录制仍在进行中，请先停止录制并等待结果生成");
      return;
    }
    if (!Array.isArray(detail.steps) || !detail.steps.length) {
      ElMessage.warning("当前录制记录中没有可保存的步骤");
      return;
    }
    recordingActionMode.value = mode;
    selectedRecording.value = detail;
    recordingActionForm.value = buildRecordingActionDefaults(detail);
    showRecordingActionDialog.value = true;
  });
}

function submitRecordingAction() {
  if (!recordingActionForm.value.recordingId) {
    ElMessage.error("缺少录制会话ID");
    return;
  }

  const mode = recordingActionMode.value;
  if (mode === "create" && !recordingActionForm.value.caseName?.trim()) {
    ElMessage.error("请输入新用例名称");
    return;
  }
  if (mode !== "create" && !recordingActionForm.value.webCaseId) {
    ElMessage.error("请选择目标用例");
    return;
  }

  loading.value.recordingAction = true;
  const promise =
    mode === "create"
      ? saveWebRecordingAsCase({
          recordingId: recordingActionForm.value.recordingId,
          caseName: recordingActionForm.value.caseName,
          projectId: recordingActionForm.value.projectId,
          moduleId: recordingActionForm.value.moduleId,
          startUrl: recordingActionForm.value.startUrl,
          browserName: recordingActionForm.value.browserName,
          headless: recordingActionForm.value.headless,
          notes: recordingActionForm.value.notes,
        })
      : applyWebRecording({
          recordingId: recordingActionForm.value.recordingId,
          webCaseId: recordingActionForm.value.webCaseId,
          replaceSteps: mode === "replace",
        });

  promise.then(async (response) => {
    ElMessage.success(response.msg || "操作成功");
    showRecordingActionDialog.value = false;
    await loadAllCaseOptions(true);
    getList();
    getRecordingList();
    if (mode === "create" && response.data?.webCaseId) {
      activeTab.value = "case";
      handleEdit(response.data);
    }
  }).finally(() => {
    loading.value.recordingAction = false;
  });
}

function openReplayDialog(recordingSource) {
  resolveRecordingSource(recordingSource).then((detail) => {
    if (!detail?.recordingId) {
      ElMessage.error("未找到可用录制记录");
      return;
    }
    if (!canUseRecordingResult(detail.status)) {
      ElMessage.warning("录制仍在进行中，请先停止录制并等待结果生成");
      return;
    }
    if (!Array.isArray(detail.steps) || !detail.steps.length) {
      ElMessage.warning("当前录制记录中没有可回放的步骤");
      return;
    }
    selectedRecording.value = detail;
    replayForm.value = {
      recordingId: detail.recordingId,
      agentId: undefined,
      browserName: detail.browserName || "chromium",
      headless: detail.headless ?? false,
      closeBrowserOnFinish: true,
    };
    showReplayDialog.value = true;
  });
}

function submitReplay() {
  if (!replayForm.value.recordingId) {
    ElMessage.error("缺少录制会话ID");
    return;
  }
  if (!replayForm.value.agentId) {
    ElMessage.error("请选择执行 Agent");
    return;
  }

  loading.value.replay = true;
  replayWebRecording({
    recordingId: replayForm.value.recordingId,
    agentId: replayForm.value.agentId,
    browserName: replayForm.value.browserName,
    headless: replayForm.value.headless,
    closeBrowserOnFinish: replayForm.value.closeBrowserOnFinish,
  }).then((response) => {
    replayResult.value = response.data || null;
    showReplayDialog.value = false;
    showReplayResultDialog.value = true;
    ElMessage.success(response.msg || "回放完成");
  }).finally(() => {
    loading.value.replay = false;
  });
}

watch(() => form.value.steps, () => {
  if (caseEditorTab.value !== "json") {
    syncStepsTextFromForm();
  }
}, { deep: true });

watch(() => form.value.steps.length, (length) => {
  if (!length) {
    selectedStepIndex.value = -1;
    return;
  }
  if (selectedStepIndex.value < 0) {
    selectedStepIndex.value = 0;
    return;
  }
  if (selectedStepIndex.value >= length) {
    selectedStepIndex.value = length - 1;
  }
});

watch(activeTab, (value) => {
  if (value === "run") {
    loadAllCaseOptions();
    getRunList();
  }
  if (value === "recording") {
    loadAllCaseOptions();
    getRecordingList();
  }
});

watch(() => queryParams.value.projectId, (projectId) => {
  if (!projectId) {
    return;
  }
  if (!filteredSearchModules.value.some((item) => isSameId(item.moduleId, queryParams.value.moduleId))) {
    queryParams.value.moduleId = undefined;
  }
});

watch(() => form.value.projectId, (projectId) => {
  if (!projectId) return;
  if (!filteredCaseModules.value.some((item) => isSameId(item.moduleId, form.value.moduleId))) {
    form.value.moduleId = undefined;
  }
});

watch(() => recordingActionForm.value.projectId, (projectId) => {
  if (!projectId) return;
  if (!filteredRecordingActionModules.value.some((item) => isSameId(item.moduleId, recordingActionForm.value.moduleId))) {
    recordingActionForm.value.moduleId = undefined;
  }
});

onMounted(async () => {
  await loadBaseData();
  resetForm();
  getList();
});

onBeforeUnmount(() => {
  stopRecordingPoll();
});
</script>

<style scoped lang="scss">
.webcase-page {
  min-height: calc(100vh - 84px);
}

.webcase-tabs :deep(.el-tabs__content) {
  overflow: visible;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.case-editor-tabs {
  margin-top: 8px;
}

.step-table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.step-table-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-edit-table :deep(.el-table__row) {
  cursor: pointer;
}

.step-edit-table :deep(.selected-step-row > td) {
  background: var(--el-color-primary-light-9);
}

.step-order-cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.step-inline-target {
  display: grid;
  grid-template-columns: 110px repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.step-cell-placeholder {
  color: var(--el-text-color-placeholder);
}

.step-op-buttons {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.step-detail-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.step-editor {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
  align-items: start;
}

.step-list-panel,
.step-detail-panel {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-bg-color);
}

.panel-toolbar,
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-toolbar {
  padding: 14px 16px 10px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
}

.step-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.step-item {
  padding: 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.step-item:hover {
  transform: translateY(-1px);
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 8px 24px rgba(64, 158, 255, 0.08);
}

.step-item.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.step-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.step-index {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.step-name {
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 6px;
}

.step-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
  min-height: 36px;
}

.step-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  margin-top: 8px;
}

.step-detail-panel {
  padding: 16px;
}

.panel-card {
  margin-bottom: 16px;
}

.locator-list,
.assertion-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.locator-item,
.assertion-item {
  padding: 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-extra-light);
}

.locator-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.locator-title {
  font-weight: 600;
}

.locator-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.assertion-remove {
  display: flex;
  align-items: center;
}

.json-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.recording-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.mb12 {
  margin-bottom: 12px;
}

.mb16 {
  margin-bottom: 16px;
}

@media (max-width: 1200px) {
  .step-table-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .step-table-toolbar-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .step-inline-target {
    grid-template-columns: 1fr;
  }

  .step-editor {
    grid-template-columns: 1fr;
  }
}
</style>
