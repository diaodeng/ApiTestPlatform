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
          <el-col :span="2">
            <el-button
              type="success"
              plain
              icon="CaretRight"
              :disabled="!selectedCaseRows.length"
              @click="openBatchRunDialog"
              v-hasPermi="['hrm:webCase:run']"
            >
              批量执行
            </el-button>
          </el-col>
          <el-col :span="1.5">
            <el-button type="warning" plain icon="VideoPlay" @click="openRecordingDialog()" v-hasPermi="['hrm:webCase:record']">独立录制</el-button>
          </el-col>
          <el-col :span="1.5">
            <el-button type="default" plain icon="Refresh" @click="getList">刷新</el-button>
          </el-col>
          <el-col :span="2">
            <el-button type="info" plain icon="Setting" @click="openRuntimeProfileDialog" v-hasPermi="['hrm:webCase:edit']">Cookie配置</el-button>
          </el-col>
          <el-col :span="2">
            <el-button type="info" plain icon="Lock" @click="openBrowserSessionDialog" v-hasPermi="['hrm:webCase:persistContext']">浏览器Session</el-button>
          </el-col>
        </el-row>

        <el-table
          v-loading="loading.page"
          :data="pageDataList"
          border
          table-layout="fixed"
          max-height="calc(100vh - 340px)"
          row-key="webCaseId"
          @selection-change="handleCaseSelectionChange"
        >
          <el-table-column type="selection" width="52" align="center" :reserve-selection="true" />
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

        <el-row :gutter="10" class="mb8">
          <el-col :span="1.5">
            <el-button type="default" plain icon="Refresh" @click="getRunList">刷新</el-button>
          </el-col>
          <el-col :span="2">
            <el-button
              type="danger"
              plain
              icon="Delete"
              :disabled="!selectedRunRows.length"
              @click="handleDeleteRunRecords()"
              v-hasPermi="['hrm:webCase:remove']"
            >
              删除记录
            </el-button>
          </el-col>
        </el-row>

        <el-table
          v-loading="loading.runPage"
          :data="runRecordList"
          border
          table-layout="fixed"
          max-height="calc(100vh - 320px)"
          row-key="webCaseRunId"
          @selection-change="handleRunSelectionChange"
        >
          <el-table-column type="selection" width="52" align="center" :reserve-selection="true" />
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
            <template #default="scope">{{ getRunRowFailureReason(scope.row) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="320" fixed="right">
            <template #default="scope">
              <el-button link type="primary" icon="View" @click="openRunDetail(scope.row)">查看详情</el-button>
              <el-button
                v-if="canStopRun(scope.row)"
                link
                type="warning"
                icon="VideoPause"
                @click="handleStopRun(scope.row)"
                v-hasPermi="['hrm:webCase:run']"
              >
                停止
              </el-button>
              <el-button
                v-if="canCancelPreparedRun(scope.row)"
                link
                type="warning"
                icon="CircleClose"
                @click="handleCancelPreparedRun(scope.row)"
                v-hasPermi="['hrm:webCase:run']"
              >
                取消准备
              </el-button>
              <el-button link type="danger" icon="Delete" @click="handleDeleteRunRecords(scope.row)" v-hasPermi="['hrm:webCase:remove']">删除</el-button>
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

        <el-row :gutter="10" class="mb8">
          <el-col :span="2">
            <el-button
              type="danger"
              plain
              icon="Delete"
              :disabled="!selectedRecordingRows.length"
              @click="handleDeleteRecordingRecords()"
              v-hasPermi="['hrm:webCase:remove']"
            >
              删除记录
            </el-button>
          </el-col>
        </el-row>

        <el-table
          v-loading="loading.recordingPage"
          :data="recordingList"
          border
          table-layout="fixed"
          max-height="calc(100vh - 360px)"
          row-key="recordingId"
          @selection-change="handleRecordingSelectionChange"
        >
          <el-table-column type="selection" width="52" align="center" :reserve-selection="true" />
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
          <el-table-column label="操作" width="620" fixed="right">
            <template #default="scope">
              <el-button link type="primary" icon="View" @click="openRecordingDetail(scope.row)">查看</el-button>
              <el-button
                v-if="canStopRecording(scope.row)"
                link
                type="warning"
                icon="VideoPause"
                @click="handleStopRecording(scope.row)"
                v-hasPermi="['hrm:webCase:record']"
              >
                停止
              </el-button>
              <el-button
                v-if="canCancelPreparedRecording(scope.row)"
                link
                type="warning"
                icon="CircleClose"
                @click="handleCancelPreparedRecording(scope.row)"
                v-hasPermi="['hrm:webCase:record']"
              >
                取消准备
              </el-button>
              <el-button link type="danger" icon="Delete" @click="handleDeleteRecordingRecords(scope.row)" v-hasPermi="['hrm:webCase:remove']">删除</el-button>
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

    <el-dialog
      v-model="showCaseDialog"
      :title="caseDialogTitle"
      width="1360px"
      destroy-on-close
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
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
                      v-else-if="getPrimaryLocator(scope.row)?.locatorType === 'id'"
                      :model-value="getPrimaryLocator(scope.row)?.locatorValue?.id || ''"
                      placeholder="元素 id"
                      @update:model-value="updatePrimaryLocatorValue(scope.row, 'id', $event)"
                    />
                    <el-input
                      v-else-if="getPrimaryLocator(scope.row)?.locatorType === 'name'"
                      :model-value="getPrimaryLocator(scope.row)?.locatorValue?.name || ''"
                      placeholder="元素 name"
                      @update:model-value="updatePrimaryLocatorValue(scope.row, 'name', $event)"
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
                <template v-else-if="['sleep', 'wait'].includes(scope.row.actionType)">
                  <el-input-number v-model="scope.row.params.waitMs" :min="0" :step="100" controls-position="right" style="width: 100%" />
                </template>
                <template v-else-if="['assert_page_contains', 'assert_page_not_contains'].includes(scope.row.actionType)">
                  <el-input v-model="scope.row.params.text" @click.stop placeholder="请输入断言文本" />
                </template>
                <template v-else-if="scope.row.actionType === 'assert_title_contains'">
                  <el-input v-model="scope.row.params.title" @click.stop placeholder="请输入页面标题关键字" />
                </template>
                <template v-else-if="scope.row.actionType === 'assert_url_contains'">
                  <el-input v-model="scope.row.params.urlPart" @click.stop placeholder="请输入URL关键字" />
                </template>
                <template v-else-if="['assert_text_equals', 'assert_text_contains'].includes(scope.row.actionType)">
                  <el-input v-model="scope.row.params.expected" @click.stop placeholder="请输入元素文本期望值" />
                </template>
                <span v-else class="step-cell-placeholder">当前动作无额外参数</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="290" fixed="right">
              <template #default="scope">
                <div class="step-op-buttons">
                  <el-button link type="primary" icon="Plus" @click.stop="insertStep(scope.$index)">前插</el-button>
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

    <el-dialog
      v-model="showStepDetailDialog"
      :title="stepDetailTitle"
      width="1160px"
      destroy-on-close
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
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
            <el-col :span="6">
              <el-form-item label="超时(ms)">
                <el-input-number v-model="currentStep.timeoutMs" :min="0" :step="1000" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="思考(ms)">
                <el-input-number v-model="currentStep.params.thinkTimeMs" :min="0" :step="100" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="记录来源">
                <el-input v-model="currentStep.recordOrigin" placeholder="manual / record" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
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
            <el-col v-else-if="['sleep', 'wait'].includes(currentStep.actionType)" :span="24">
              <el-form-item label="等待时长(ms)">
                <el-input-number v-model="currentStep.params.waitMs" :min="0" :step="100" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col v-else-if="['assert_page_contains', 'assert_page_not_contains'].includes(currentStep.actionType)" :span="24">
              <el-form-item label="页面文本">
                <el-input v-model="currentStep.params.text" type="textarea" :rows="2" placeholder="请输入页面中应包含/不包含的文本" />
              </el-form-item>
            </el-col>
            <el-col v-else-if="currentStep.actionType === 'assert_title_contains'" :span="24">
              <el-form-item label="标题关键字">
                <el-input v-model="currentStep.params.title" placeholder="请输入页面标题关键字" />
              </el-form-item>
            </el-col>
            <el-col v-else-if="currentStep.actionType === 'assert_url_contains'" :span="24">
              <el-form-item label="URL关键字">
                <el-input v-model="currentStep.params.urlPart" placeholder="请输入 URL 中应包含的关键字" />
              </el-form-item>
            </el-col>
            <el-col v-else-if="['assert_text_equals', 'assert_text_contains'].includes(currentStep.actionType)" :span="24">
              <el-form-item label="文本期望值">
                <el-input v-model="currentStep.params.expected" type="textarea" :rows="2" placeholder="请输入元素文本期望值" />
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
          <div class="locator-tip">执行顺序按列表从上到下，仅尝试“启用”定位器；命中后继续下一步，可用“设为首选”快速置顶。</div>

          <div v-if="currentStep.targetSnapshot?.locators?.length" class="locator-list">
            <div
              v-for="(locator, locatorIndex) in currentStep.targetSnapshot.locators"
              :key="locator.locatorSnapshotId || `${currentStep.stepIndex || selectedStepIndex}-${locatorIndex}`"
              class="locator-item"
            >
              <div class="locator-header">
                <div class="locator-title">
                  <span>定位器 {{ locatorIndex + 1 }}</span>
                  <el-tag v-if="locatorIndex === 0" size="small" type="success">首选</el-tag>
                </div>
                <div class="locator-actions">
                  <el-switch v-model="locator.enabled" inline-prompt active-text="启用" inactive-text="停用" />
                  <el-button link type="primary" :disabled="locatorIndex === 0" @click="setPrimaryLocator(currentStep, locatorIndex)">设为首选</el-button>
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
                <el-col v-if="locator.locatorType === 'id'" :span="14">
                  <el-form-item label="ID" label-width="70px">
                    <el-input v-model="locator.locatorValue.id" placeholder="元素 id" />
                  </el-form-item>
                </el-col>
                <el-col v-if="locator.locatorType === 'name'" :span="14">
                  <el-form-item label="Name" label-width="70px">
                    <el-input v-model="locator.locatorValue.name" placeholder="元素 name" />
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

          <div v-if="currentStep.assertions?.length">
            <el-table :data="currentStep.assertions" border table-layout="fixed" class="assertion-edit-table">
              <el-table-column type="expand" width="56">
                <template #default="scope">
                  <template v-if="assertionNeedsTarget(scope.row.assertType)">
                    <div class="locator-tip">断言定位器会按从上到下顺序尝试，命中第一个后执行断言。</div>
                    <div v-if="getAssertionLocatorList(scope.row).length" class="locator-list">
                      <div
                        v-for="(locator, locatorIndex) in getAssertionLocatorList(scope.row)"
                        :key="locator.locatorSnapshotId || `${selectedStepIndex}-${scope.$index}-${locatorIndex}`"
                        class="locator-item"
                      >
                        <div class="locator-header">
                          <div class="locator-title">
                            <span>定位器 {{ locatorIndex + 1 }}</span>
                            <el-tag v-if="locatorIndex === 0" size="small" type="success">首选</el-tag>
                          </div>
                          <div class="locator-actions">
                            <el-switch v-model="locator.enabled" inline-prompt active-text="启用" inactive-text="停用" />
                            <el-button link type="primary" :disabled="locatorIndex === 0" @click="setAssertionPrimaryLocator(scope.row, locatorIndex)">设为首选</el-button>
                            <el-button link icon="Top" :disabled="locatorIndex === 0" @click="moveAssertionLocator(scope.row, locatorIndex, -1)" />
                            <el-button
                              link
                              icon="Bottom"
                              :disabled="locatorIndex === getAssertionLocatorList(scope.row).length - 1"
                              @click="moveAssertionLocator(scope.row, locatorIndex, 1)"
                            />
                            <el-button link type="danger" icon="Delete" @click="removeAssertionLocator(scope.row, locatorIndex)" />
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
                          <el-col v-if="locator.locatorType === 'id'" :span="14">
                            <el-form-item label="ID" label-width="70px">
                              <el-input v-model="locator.locatorValue.id" placeholder="元素 id" />
                            </el-form-item>
                          </el-col>
                          <el-col v-if="locator.locatorType === 'name'" :span="14">
                            <el-form-item label="Name" label-width="70px">
                              <el-input v-model="locator.locatorValue.name" placeholder="元素 name" />
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
                    <el-empty v-else description="当前断言暂无定位器" :image-size="60" />
                  </template>
                  <span v-else class="step-cell-placeholder">当前断言无需独立定位器</span>
                </template>
              </el-table-column>
              <el-table-column label="序号" width="76">
                <template #default="scope">#{{ scope.$index + 1 }}</template>
              </el-table-column>
              <el-table-column label="启用" width="90">
                <template #default="scope">
                  <el-switch v-model="scope.row.enabled" />
                </template>
              </el-table-column>
              <el-table-column label="断言类型" width="170">
                <template #default="scope">
                  <el-select v-model="scope.row.assertType" style="width: 100%" @change="handleAssertionTypeChange(scope.row)">
                    <el-option v-for="item in assertionTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="期望值" min-width="220">
                <template #default="scope">
                  <el-input v-model="scope.row.expected" placeholder="请输入期望值" />
                </template>
              </el-table-column>
              <el-table-column label="等待(ms)" width="130">
                <template #default="scope">
                  <el-input-number v-model="scope.row.waitMs" :min="200" :step="100" controls-position="right" style="width: 100%" />
                </template>
              </el-table-column>
              <el-table-column label="定位器(首选)" min-width="340">
                <template #default="scope">
                  <template v-if="assertionNeedsTarget(scope.row.assertType) && getAssertionPrimaryLocator(scope.row)">
                    <div class="step-inline-target" @click.stop>
                      <el-select
                        :model-value="getAssertionPrimaryLocator(scope.row)?.locatorType"
                        style="width: 110px"
                        @update:model-value="updateAssertionPrimaryLocatorType(scope.row, $event)"
                      >
                        <el-option v-for="item in locatorTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                      </el-select>
                      <template v-if="getAssertionPrimaryLocator(scope.row)?.locatorType === 'role'">
                        <el-input
                          :model-value="getAssertionPrimaryLocator(scope.row)?.locatorValue?.role || ''"
                          placeholder="角色"
                          @update:model-value="updateAssertionPrimaryLocatorValue(scope.row, 'role', $event)"
                        />
                        <el-input
                          :model-value="getAssertionPrimaryLocator(scope.row)?.locatorValue?.name || ''"
                          placeholder="名称"
                          @update:model-value="updateAssertionPrimaryLocatorValue(scope.row, 'name', $event)"
                        />
                      </template>
                      <el-input
                        v-else-if="['label', 'placeholder', 'text'].includes(getAssertionPrimaryLocator(scope.row)?.locatorType)"
                        :model-value="getAssertionPrimaryLocator(scope.row)?.locatorValue?.text || ''"
                        placeholder="定位文本"
                        @update:model-value="updateAssertionPrimaryLocatorValue(scope.row, 'text', $event)"
                      />
                      <el-input
                        v-else-if="getAssertionPrimaryLocator(scope.row)?.locatorType === 'test_id'"
                        :model-value="getAssertionPrimaryLocator(scope.row)?.locatorValue?.testId || ''"
                        placeholder="Test ID"
                        @update:model-value="updateAssertionPrimaryLocatorValue(scope.row, 'testId', $event)"
                      />
                      <el-input
                        v-else-if="getAssertionPrimaryLocator(scope.row)?.locatorType === 'id'"
                        :model-value="getAssertionPrimaryLocator(scope.row)?.locatorValue?.id || ''"
                        placeholder="元素 id"
                        @update:model-value="updateAssertionPrimaryLocatorValue(scope.row, 'id', $event)"
                      />
                      <el-input
                        v-else-if="getAssertionPrimaryLocator(scope.row)?.locatorType === 'name'"
                        :model-value="getAssertionPrimaryLocator(scope.row)?.locatorValue?.name || ''"
                        placeholder="元素 name"
                        @update:model-value="updateAssertionPrimaryLocatorValue(scope.row, 'name', $event)"
                      />
                      <el-input
                        v-else
                        :model-value="getAssertionPrimaryLocator(scope.row)?.locatorValue?.selector || ''"
                        :placeholder="getAssertionPrimaryLocator(scope.row)?.locatorType === 'xpath' ? '//*[@id=&quot;login&quot;]' : '.login-button'"
                        @update:model-value="updateAssertionPrimaryLocatorValue(scope.row, 'selector', $event)"
                      />
                    </div>
                  </template>
                  <span v-else class="step-cell-placeholder">当前断言无需定位器</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="170" fixed="right">
                <template #default="scope">
                  <el-button
                    link
                    type="primary"
                    :disabled="!assertionNeedsTarget(scope.row.assertType)"
                    @click="addAssertionLocator(scope.row)"
                  >
                    新增定位器
                  </el-button>
                  <el-button link type="danger" icon="Delete" @click="removeAssertion(currentStep, scope.$index)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="step-detail-tip mt8">展开每行可编辑该断言的完整定位器列表及优先级。</div>
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

    <el-dialog
      v-model="showRunDialog"
      title="执行 Web 用例"
      width="760px"
      destroy-on-close
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <el-form :model="runForm" label-width="120px">
        <el-form-item label="目标用例">
          <el-input :model-value="runTargetLabel" type="textarea" :rows="2" readonly />
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
        <el-form-item label="每条后重启浏览器">
          <el-switch v-model="runForm.closeBrowserOnFinish" />
        </el-form-item>
        <el-form-item label="浏览器Session" v-hasPermi="['hrm:webCase:persistContext']">
          <el-row :gutter="10" style="width: 100%">
            <el-col :span="18">
              <el-select v-model="runForm.browserSessionId" clearable filterable style="width: 100%" placeholder="可选：选择浏览器Session">
                <el-option
                  v-for="item in availableBrowserSessionsForRun"
                  :key="item.sessionId"
                  :label="formatBrowserSessionLabel(item)"
                  :value="item.sessionId"
                />
              </el-select>
            </el-col>
            <el-col :span="6">
              <el-button style="width: 100%" @click="openBrowserSessionDialog">管理Session</el-button>
            </el-col>
          </el-row>
        </el-form-item>
        <el-form-item label="保留浏览器状态" v-hasPermi="['hrm:webCase:persistContext']">
          <el-switch v-model="runForm.persistContextEnabled" />
        </el-form-item>
        <el-form-item v-if="runForm.persistContextEnabled" label="自动同步Session" v-hasPermi="['hrm:webCase:persistContext']">
          <el-switch v-model="runForm.persistContextAutoSyncSession" />
        </el-form-item>
        <el-form-item v-if="runForm.persistContextEnabled" label="状态作用域" v-hasPermi="['hrm:webCase:persistContext']">
          <el-select v-model="runForm.persistContextKey" clearable filterable style="width: 100%" placeholder="请选择状态作用域">
            <el-option
              v-for="item in availablePersistScopesForRun"
              :key="item.key"
              :label="formatPersistScopeLabel(item)"
              :value="item.key"
            />
          </el-select>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="手动登录闸门">
              <el-switch v-model="runForm.manualLoginEnabled" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="登录等待(秒)">
              <el-input-number
                v-model="runForm.manualLoginWaitSec"
                :min="0"
                :max="3600"
                :step="10"
                controls-position="right"
                style="width: 100%"
                :disabled="!runForm.manualLoginEnabled || runForm.manualLoginRequireConfirm"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="登录后确认继续">
          <el-switch
            v-model="runForm.manualLoginRequireConfirm"
            :disabled="!runForm.manualLoginEnabled"
            inline-prompt
            active-text="开启"
            inactive-text="关闭"
          />
        </el-form-item>
        <el-form-item>
          <span class="step-detail-tip">
            开启“登录后确认继续”后，会先启动浏览器等待你手动登录，确认后才继续；批量执行仅首条触发确认。关闭“每条后重启浏览器”可在批量执行中复用同一浏览器会话。
          </span>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="单步超时覆盖(ms)">
              <el-input-number v-model="runForm.stepTimeoutMs" :min="500" :step="500" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="步骤思考时间(ms)">
              <el-input-number v-model="runForm.stepThinkTimeMs" :min="0" :step="100" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showRunDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.run" @click="submitRun">执行</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showRunDetailDialog"
      :title="runDetailTitle"
      width="1180px"
      destroy-on-close
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      @close="stopRunDetailPoll"
    >
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

        <el-alert v-if="runDetailFailureMessage" :title="runDetailFailureMessage" type="error" show-icon :closable="false" class="mb16" />
        <el-alert
          v-if="runCookieApplySummary"
          :title="runCookieApplySummary"
          :type="runCookieApplySummaryType"
          show-icon
          :closable="false"
          class="mb16"
        />

        <div class="recording-toolbar">
          <el-button @click="refreshRunDetail">刷新详情</el-button>
          <el-button
            v-if="canStopRun(runDetail)"
            type="warning"
            @click="handleStopRun(runDetail)"
            v-hasPermi="['hrm:webCase:run']"
          >
            停止执行
          </el-button>
          <el-button
            v-if="canCancelPreparedRun(runDetail)"
            type="warning"
            plain
            @click="handleCancelPreparedRun(runDetail)"
            v-hasPermi="['hrm:webCase:run']"
          >
            取消准备
          </el-button>
          <el-button type="danger" plain @click="handleDeleteRunRecords(runDetail)" v-hasPermi="['hrm:webCase:remove']">删除记录</el-button>
        </div>

        <el-table :data="runStepResults" border max-height="320px" class="mb16">
          <el-table-column label="步骤" prop="stepName" min-width="220" />
          <el-table-column label="状态" width="110">
            <template #default="scope">
                <el-tag :type="getStepStatusTagType(scope.row.status)">{{ scope.row.status || "-" }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="110">
            <template #default="scope">{{ formatDuration(scope.row.durationMs) }}</template>
          </el-table-column>
          <el-table-column label="页面" prop="pageUrl" min-width="220" show-overflow-tooltip />
          <el-table-column label="失败原因" min-width="260" show-overflow-tooltip>
            <template #default="scope">{{ getStepFailureReason(scope.row) }}</template>
          </el-table-column>
        </el-table>

        <AceEditor :content="runDetailJsonText" lang="json" :read-only="true" height="260px" />
      </template>
    </el-dialog>

    <el-dialog
      v-model="showRecordingDialog"
      :title="recordingDialogTitle"
      width="1240px"
      destroy-on-close
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      @close="stopRecordingPoll"
    >
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
           <el-col :span="24" v-hasPermi="['hrm:webCase:persistContext']">
             <el-form-item label="浏览器Session">
               <el-row :gutter="10" style="width: 100%">
                 <el-col :span="18">
                   <el-select v-model="recordingForm.browserSessionId" clearable filterable style="width: 100%" placeholder="可选：选择浏览器Session">
                     <el-option
                       v-for="item in availableBrowserSessionsForRecording"
                       :key="item.sessionId"
                       :label="formatBrowserSessionLabel(item)"
                       :value="item.sessionId"
                     />
                   </el-select>
                 </el-col>
                 <el-col :span="6">
                   <el-button style="width: 100%" @click="openBrowserSessionDialog">管理Session</el-button>
                 </el-col>
               </el-row>
             </el-form-item>
           </el-col>
           <el-col :span="12">
             <el-form-item label="手动登录闸门">
               <el-switch v-model="recordingForm.manualLoginEnabled" />
             </el-form-item>
           </el-col>
           <el-col :span="12">
             <el-form-item label="登录等待(秒)">
               <el-input-number
                 v-model="recordingForm.manualLoginWaitSec"
                 :min="0"
                 :max="3600"
                  :step="10"
                  controls-position="right"
                  style="width: 100%"
                  :disabled="!recordingForm.manualLoginEnabled || recordingForm.manualLoginRequireConfirm"
                />
              </el-form-item>
            </el-col>
           <el-col :span="12">
             <el-form-item label="登录后确认继续">
               <el-switch
                 v-model="recordingForm.manualLoginRequireConfirm"
                 :disabled="!recordingForm.manualLoginEnabled"
                 inline-prompt
                 active-text="开启"
                 inactive-text="关闭"
               />
             </el-form-item>
           </el-col>
            <el-col :span="12">
              <el-form-item label="停止时关闭浏览器">
                <el-switch v-model="recordingForm.closeBrowserOnStop" />
              </el-form-item>
            </el-col>
            <el-col :span="12" v-hasPermi="['hrm:webCase:persistContext']">
              <el-form-item label="保留浏览器状态">
                <el-switch v-model="recordingForm.persistContextEnabled" />
              </el-form-item>
            </el-col>
            <el-col :span="24" v-if="recordingForm.persistContextEnabled" v-hasPermi="['hrm:webCase:persistContext']">
              <el-form-item label="自动同步Session">
                <el-switch v-model="recordingForm.persistContextAutoSyncSession" />
              </el-form-item>
            </el-col>
            <el-col :span="24" v-if="recordingForm.persistContextEnabled" v-hasPermi="['hrm:webCase:persistContext']">
              <el-form-item label="状态作用域">
                <el-select v-model="recordingForm.persistContextKey" clearable filterable style="width: 100%" placeholder="请选择状态作用域">
                  <el-option
                    v-for="item in availablePersistScopesForRecording"
                    :key="item.key"
                    :label="formatPersistScopeLabel(item)"
                    :value="item.key"
                  />
                </el-select>
              </el-form-item>
            </el-col>
           <el-col :span="12">
             <el-form-item label="启用断言录制">
               <el-switch v-model="recordingForm.captureAssertions" />
             </el-form-item>
           </el-col>
          <el-col :span="12">
            <el-form-item label="断言归属方式">
              <el-switch
                v-model="recordingForm.attachAssertionsToPreviousStep"
                :disabled="!recordingForm.captureAssertions"
                inline-prompt
                active-text="步骤内"
                inactive-text="平级"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="点击前自动断言">
              <el-switch v-model="recordingForm.autoAssertTextOnClick" :disabled="!recordingForm.captureAssertions" />
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
      <el-alert
        :title="recordingAssertionTipText"
        type="info"
        :closable="false"
        show-icon
        class="mb12"
      />

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

    <el-dialog
      v-model="showRecordingDetailDialog"
      :title="recordingDetailTitle"
      width="1240px"
      destroy-on-close
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      @close="stopRecordingDetailPoll"
    >
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
          <el-button @click="refreshRecordingDetail">刷新详情</el-button>
          <el-button
            v-if="canStopRecording(recordingDetail)"
            type="warning"
            icon="VideoPause"
            @click="handleStopRecording(recordingDetail)"
            v-hasPermi="['hrm:webCase:record']"
          >
            停止录制
          </el-button>
          <el-button
            v-if="canCancelPreparedRecording(recordingDetail)"
            type="warning"
            plain
            icon="CircleClose"
            @click="handleCancelPreparedRecording(recordingDetail)"
            v-hasPermi="['hrm:webCase:record']"
          >
            取消准备
          </el-button>
          <el-button type="danger" plain icon="Delete" @click="handleDeleteRecordingRecords(recordingDetail)" v-hasPermi="['hrm:webCase:remove']">删除记录</el-button>
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

    <el-dialog
      v-model="showRecordingActionDialog"
      :title="recordingActionDialogTitle"
      width="760px"
      destroy-on-close
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
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

    <el-dialog
      v-model="showReplayDialog"
      title="录制回放"
      width="560px"
      destroy-on-close
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
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

    <el-dialog
      v-model="showReplayResultDialog"
      :title="replayResultTitle"
      width="1180px"
      destroy-on-close
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <template v-if="replayResult">
        <el-alert
          :title="replayFailureMessage || (replayResult.status === 'passed' ? '回放执行成功' : '回放执行失败')"
          :type="replayResult.status === 'passed' ? 'success' : 'error'"
          :closable="false"
          show-icon
          class="mb16"
        />
        <el-table :data="replayStepResults" border max-height="320px" class="mb16">
          <el-table-column label="步骤" prop="stepName" min-width="220" />
          <el-table-column label="状态" width="110">
            <template #default="scope">
                <el-tag :type="getStepStatusTagType(scope.row.status)">{{ scope.row.status || "-" }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="110">
            <template #default="scope">{{ formatDuration(scope.row.durationMs) }}</template>
          </el-table-column>
          <el-table-column label="页面" prop="pageUrl" min-width="220" show-overflow-tooltip />
          <el-table-column label="失败原因" min-width="260" show-overflow-tooltip>
            <template #default="scope">{{ getStepFailureReason(scope.row) }}</template>
          </el-table-column>
        </el-table>
        <AceEditor :content="replayResultJsonText" lang="json" :read-only="true" height="260px" />
      </template>
    </el-dialog>

    <el-dialog
      v-model="showRuntimeProfileDialog"
      title="Cookie配置管理"
      width="1180px"
      destroy-on-close
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <el-row :gutter="16">
        <el-col :span="11">
          <div class="runtime-profile-toolbar mb12">
            <el-input v-model="runtimeProfileKeyword" clearable placeholder="按名称筛选配置" />
            <el-button type="primary" @click="createRuntimeProfileDraft">新建</el-button>
            <el-button @click="loadRuntimeProfiles">刷新</el-button>
          </div>
          <el-table
            v-loading="loading.runtimeProfile"
            :data="filteredRuntimeProfiles"
            border
            row-key="profileId"
            highlight-current-row
            max-height="520px"
            @current-change="handleRuntimeProfileRowChange"
          >
            <el-table-column label="名称" min-width="220" show-overflow-tooltip>
              <template #default="scope">{{ scope.row.profileName || "-" }}</template>
            </el-table-column>
            <el-table-column label="适用范围" min-width="150" show-overflow-tooltip>
              <template #default="scope">{{ formatRuntimeProfileScope(scope.row) }}</template>
            </el-table-column>
            <el-table-column label="目标链路" min-width="120" show-overflow-tooltip>
              <template #default="scope">{{ (scope.row.targets || []).join(", ") || "-" }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="scope">
                <el-tag :type="scope.row.enabled === false ? 'info' : 'success'">{{ scope.row.enabled === false ? "停用" : "启用" }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-col>
        <el-col :span="13">
          <el-form :model="runtimeProfileForm" label-width="120px">
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="配置名称">
                  <el-input v-model="runtimeProfileForm.profileName" placeholder="例如：生产登录态" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="是否启用">
                  <el-switch v-model="runtimeProfileForm.enabled" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="目标链路">
                  <el-select v-model="runtimeProfileForm.targets" multiple collapse-tags style="width: 100%">
                    <el-option v-for="item in runtimeTargetOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="排序">
                  <el-input-number v-model="runtimeProfileForm.sort" :min="0" :step="1" controls-position="right" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="项目(可选)">
                  <el-select v-model="runtimeProfileForm.projectId" clearable filterable style="width: 100%">
                    <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="模块(可选)">
                  <el-select v-model="runtimeProfileForm.moduleId" clearable filterable style="width: 100%">
                    <el-option v-for="item in filteredRuntimeProfileModules" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="运行覆盖(JSON)">
                  <el-input
                    v-model="runtimeProfileForm.runtimeOverridesText"
                    type="textarea"
                    :rows="3"
                    placeholder='可选，例如：{"stepTimeoutMs":10000}'
                  />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="变量(JSON)">
                  <el-input
                    v-model="runtimeProfileForm.variablesText"
                    type="textarea"
                    :rows="3"
                    placeholder='可选，例如：{"token":"xxx","sid":"yyy"}'
                  />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="Cookie规则(JSON)">
                  <el-input
                    v-model="runtimeProfileForm.cookieRulesText"
                    type="textarea"
                    :rows="5"
                    placeholder='可选数组，例如：[{"name":"主站登录","match":{"host":"example.com"},"cookies":[{"name":"token","value":"${token}"}]}]'
                  />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="快速导入">
                  <el-row :gutter="8" style="width: 100%">
                    <el-col :span="14">
                      <el-input v-model="runtimeProfileImportHost" placeholder="可选：匹配域名，例如 example.com" />
                    </el-col>
                    <el-col :span="10">
                      <el-button style="width: 100%" @click="applyRuntimeProfileQuickImport">解析并填充Cookie规则</el-button>
                    </el-col>
                    <el-col :span="24" class="mt8">
                      <el-input
                        v-model="runtimeProfileImportText"
                        type="textarea"
                        :rows="4"
                        placeholder="支持 Cookie: a=1; b=2、Set-Cookie 响应头，或完整请求头文本"
                      />
                    </el-col>
                  </el-row>
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="状态作用域">
                  <div style="width: 100%">
                    <div class="runtime-profile-toolbar mb8">
                      <span class="step-detail-tip">用于保留浏览器状态的作用域键，下拉可在执行/录制时直接选择。</span>
                      <el-button type="primary" plain @click="addPersistContextScopeRow">新增作用域</el-button>
                    </div>
                    <el-table :data="runtimeProfileForm.persistContextScopes" border max-height="220px">
                      <el-table-column label="作用域Key" min-width="180">
                        <template #default="scope">
                          <el-input v-model="scope.row.key" placeholder="例如 testpartner.sm-os.com" />
                        </template>
                      </el-table-column>
                      <el-table-column label="显示名称" min-width="160">
                        <template #default="scope">
                          <el-input v-model="scope.row.label" placeholder="可选：例如 SM测试环境" />
                        </template>
                      </el-table-column>
                      <el-table-column label="匹配域名(逗号分隔)" min-width="220">
                        <template #default="scope">
                          <el-input v-model="scope.row.hostPatternsText" placeholder="可选：sm-os.com,testpartner.sm-os.com" />
                        </template>
                      </el-table-column>
                      <el-table-column label="启用" width="90">
                        <template #default="scope">
                          <el-switch v-model="scope.row.enabled" />
                        </template>
                      </el-table-column>
                      <el-table-column label="备注" min-width="160">
                        <template #default="scope">
                          <el-input v-model="scope.row.remark" placeholder="可选" />
                        </template>
                      </el-table-column>
                      <el-table-column label="操作" width="80" fixed="right">
                        <template #default="scope">
                          <el-button link type="danger" @click="removePersistContextScopeRow(scope.$index)">删除</el-button>
                        </template>
                      </el-table-column>
                    </el-table>
                  </div>
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="备注">
                  <el-input v-model="runtimeProfileForm.remark" type="textarea" :rows="2" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-col>
      </el-row>
      <template #footer>
        <el-button @click="showRuntimeProfileDialog = false">关闭</el-button>
        <el-button type="danger" :disabled="!runtimeProfileForm.profileId" @click="deleteRuntimeProfile">删除</el-button>
        <el-button type="primary" :loading="loading.runtimeProfileSave" @click="saveRuntimeProfile">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showBrowserSessionDialog"
      title="浏览器Session管理"
      width="1240px"
      destroy-on-close
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <el-row :gutter="16">
        <el-col :span="10">
          <div class="runtime-profile-toolbar mb12">
            <el-input v-model="browserSessionKeyword" clearable placeholder="按名称/作用域筛选Session" />
            <el-button type="primary" @click="createBrowserSessionDraft">新建</el-button>
            <el-button @click="loadBrowserSessions">刷新</el-button>
          </div>
          <el-table
            v-loading="loading.browserSession"
            :data="filteredBrowserSessions"
            border
            row-key="sessionId"
            highlight-current-row
            max-height="520px"
            @current-change="handleBrowserSessionRowChange"
          >
            <el-table-column label="名称" min-width="180" show-overflow-tooltip>
              <template #default="scope">{{ scope.row.sessionName || "-" }}</template>
            </el-table-column>
            <el-table-column label="作用域Key" min-width="180" show-overflow-tooltip>
              <template #default="scope">{{ scope.row.scopeKey || "-" }}</template>
            </el-table-column>
            <el-table-column label="适用范围" min-width="150" show-overflow-tooltip>
              <template #default="scope">{{ formatRuntimeProfileScope(scope.row) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="scope">
                <el-tag :type="scope.row.enabled === false ? 'info' : 'success'">{{ scope.row.enabled === false ? "停用" : "启用" }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-col>
        <el-col :span="14">
          <el-form :model="browserSessionForm" label-width="120px">
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="Session名称">
                  <el-input v-model="browserSessionForm.sessionName" placeholder="例如：SM测试登录态" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="作用域Key">
                  <el-input v-model="browserSessionForm.scopeKey" placeholder="例如：testpartner.sm-os.com" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="是否启用">
                  <el-switch v-model="browserSessionForm.enabled" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="绑定浏览器">
                  <el-select v-model="browserSessionForm.browserName" clearable style="width: 100%" placeholder="可选：仅匹配指定浏览器">
                    <el-option v-for="item in browserOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="项目(可选)">
                  <el-select v-model="browserSessionForm.projectId" clearable filterable style="width: 100%">
                    <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="模块(可选)">
                  <el-select v-model="browserSessionForm.moduleId" clearable filterable style="width: 100%">
                    <el-option v-for="item in filteredBrowserSessionModules" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="排序">
                  <el-input-number v-model="browserSessionForm.sort" :min="0" :step="1" controls-position="right" style="width: 100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="匹配域名">
                  <el-input v-model="browserSessionForm.hostPatternsText" placeholder="可选：sm-os.com,*.sm-os.com" />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="快速导入">
                  <el-row :gutter="8" style="width: 100%">
                    <el-col :span="24">
                      <el-button style="width: 100%" @click="applyBrowserSessionQuickImport">解析并填充StorageState</el-button>
                    </el-col>
                    <el-col :span="24" class="mt8">
                      <el-input
                        v-model="browserSessionImportText"
                        type="textarea"
                        :rows="4"
                        placeholder="支持 storage_state JSON、Cookie: a=1; b=2、Set-Cookie 响应头，或完整请求头文本"
                      />
                    </el-col>
                  </el-row>
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="StorageState(JSON)">
                  <el-input
                    v-model="browserSessionForm.storageStateText"
                    type="textarea"
                    :rows="12"
                    placeholder='例如：{"cookies":[],"origins":[]}'
                  />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="备注">
                  <el-input v-model="browserSessionForm.remark" type="textarea" :rows="2" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-col>
      </el-row>
      <template #footer>
        <el-button @click="showBrowserSessionDialog = false">关闭</el-button>
        <el-button type="danger" :disabled="!browserSessionForm.sessionId" @click="deleteBrowserSession">删除</el-button>
        <el-button type="primary" :loading="loading.browserSessionSave" @click="saveBrowserSession">保存</el-button>
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
  addWebBrowserSession,
  applyWebRecording,
  cancelWebRecording,
  cancelWebRun,
  delWebBrowserSession,
  delWebCase,
  delWebRecording,
  delWebRun,
  delWebRuntimeProfile,
  continueWebRecording,
  continueWebRun,
  getWebCase,
  getWebRecording,
  getWebRun,
  listWebBrowserSession,
  listWebRuntimeProfile,
  listWebCase,
  listWebRecording,
  listWebRun,
  replayWebRecording,
  runWebCase,
  addWebRuntimeProfile,
  saveWebRecordingAsCase,
  startWebRecording,
  stopWebRun,
  stopWebRecording,
  updateWebBrowserSession,
  updateWebRuntimeProfile,
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

const runtimeTargetOptions = [
  { label: "Web", value: "web" },
  { label: "API", value: "api" },
  { label: "Desktop", value: "desktop" },
];

const actionOptions = [
  { label: "打开页面", value: "goto" },
  { label: "点击元素", value: "click" },
  { label: "双击元素", value: "double_click" },
  { label: "悬停元素", value: "hover" },
  { label: "填写内容", value: "fill" },
  { label: "清空输入", value: "clear" },
  { label: "键盘按键", value: "press" },
  { label: "勾选元素", value: "check" },
  { label: "取消勾选", value: "uncheck" },
  { label: "选择下拉项", value: "select_option" },
  { label: "等待元素可见", value: "wait_visible" },
  { label: "等待元素隐藏", value: "wait_hidden" },
  { label: "固定等待", value: "sleep" },
  { label: "断言页面包含文本", value: "assert_page_contains" },
  { label: "断言页面不包含文本", value: "assert_page_not_contains" },
  { label: "断言元素文本等于", value: "assert_text_equals" },
  { label: "断言元素文本包含", value: "assert_text_contains" },
  { label: "断言页面标题包含", value: "assert_title_contains" },
  { label: "断言URL包含", value: "assert_url_contains" },
];

const locatorTypeOptions = [
  { label: "Test ID", value: "test_id" },
  { label: "ID", value: "id" },
  { label: "Name", value: "name" },
  { label: "Role", value: "role" },
  { label: "Label", value: "label" },
  { label: "Placeholder", value: "placeholder" },
  { label: "Text", value: "text" },
  { label: "CSS", value: "css" },
  { label: "XPath", value: "xpath" },
];

const assertionTypeOptions = [
  { label: "文本包含", value: "text_contains" },
  { label: "文本相等", value: "text_equals" },
  { label: "元素可见", value: "visible" },
  { label: "页面包含", value: "page_contains" },
  { label: "标题包含", value: "title_contains" },
  { label: "URL包含", value: "url_contains" },
  { label: "URL相等", value: "url_equals" },
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
const runtimeProfiles = ref([]);
const runtimeProfileKeyword = ref("");
const runtimeProfileImportText = ref("");
const runtimeProfileImportHost = ref("");
const browserSessions = ref([]);
const browserSessionKeyword = ref("");
const browserSessionImportText = ref("");

const selectedCase = ref(null);
const selectedCaseRows = ref([]);
const selectedRunRows = ref([]);
const selectedRecordingRows = ref([]);
const runTargetCases = ref([]);
const selectedRecording = ref(null);
const recordingEvents = ref([]);
const liveRecordingSteps = ref([]);
const recordingDetail = ref(null);
const runDetail = ref(null);
const replayResult = ref(null);
const recordingDetailText = ref("");

let runDetailTimer = null;
let recordingDetailTimer = null;

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
  runtimeProfile: false,
  runtimeProfileSave: false,
  browserSession: false,
  browserSessionSave: false,
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
const showRuntimeProfileDialog = ref(false);
const showBrowserSessionDialog = ref(false);

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

function parseOptionalJsonObject(text, label) {
  const raw = `${text ?? ""}`.trim();
  if (!raw) return undefined;
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    throw new Error(`${label} 解析失败：${error.message}`);
  }
  if (!isPlainObject(parsed)) {
    throw new Error(`${label} 必须是 JSON 对象`);
  }
  return parsed;
}

function parseOptionalJsonArray(text, label) {
  const raw = `${text ?? ""}`.trim();
  if (!raw) return undefined;
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    throw new Error(`${label} 解析失败：${error.message}`);
  }
  if (!Array.isArray(parsed)) {
    throw new Error(`${label} 必须是 JSON 数组`);
  }
  return parsed;
}

function createDefaultContext() {
  return {
    pageUrl: "",
    frameUrl: "",
    frameChain: [],
    shadowChain: [],
  };
}

/**
 * 解析定位器索引元信息，支持 nth/index/targetIndex 等字段。
 * @param {any} locatorValue 定位器参数
 * @returns {{nth?: number, index?: number, targetIndex?: number, matchCount?: number, uniqueness?: string}}
 */
function extractLocatorMeta(locatorValue) {
  const value = isPlainObject(locatorValue) ? locatorValue : {};
  const result = {};
  for (const key of ["nth", "index", "targetIndex", "target_index"]) {
    const raw = value[key];
    if (raw === undefined || raw === null || raw === "") continue;
    const parsed = Number(raw);
    if (Number.isInteger(parsed) && parsed >= 0) {
      if (key === "target_index") result.targetIndex = parsed;
      else result[key] = parsed;
      break;
    }
  }
  const rawMatchCount = value.matchCount ?? value.match_count;
  if (rawMatchCount !== undefined && rawMatchCount !== null && rawMatchCount !== "") {
    const parsedMatchCount = Number(rawMatchCount);
    if (Number.isInteger(parsedMatchCount) && parsedMatchCount >= 0) {
      result.matchCount = parsedMatchCount;
    }
  }
  const uniqueness = `${value.uniqueness ?? ""}`.trim();
  if (uniqueness) {
    result.uniqueness = uniqueness;
  }
  return result;
}

/**
 * 获取定位器最终使用的索引值。
 * @param {any} locatorValue 定位器参数
 * @returns {number | null}
 */
function resolveLocatorIndex(locatorValue) {
  const meta = extractLocatorMeta(locatorValue);
  for (const key of ["nth", "index", "targetIndex"]) {
    if (Number.isInteger(meta[key]) && meta[key] >= 0) {
      return meta[key];
    }
  }
  return null;
}

function normalizeLocatorValue(locatorType, locatorValue) {
  const meta = extractLocatorMeta(locatorValue);
  if (locatorType === "role") {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      role: value.role || "",
      name: value.name || "",
      exact: Boolean(value.exact),
      ...meta,
    };
  }
  if (["label", "placeholder", "text"].includes(locatorType)) {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      text: value.text || "",
      exact: Boolean(value.exact),
      ...meta,
    };
  }
  if (locatorType === "test_id") {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      testId: value.testId || "",
      ...meta,
    };
  }
  if (locatorType === "id") {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      id: value.id || "",
      ...meta,
    };
  }
  if (locatorType === "name") {
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      name: value.name || "",
      ...meta,
    };
  }
  if (["css", "xpath"].includes(locatorType)) {
    if (typeof locatorValue === "string") {
      return { selector: locatorValue, ...meta };
    }
    const value = isPlainObject(locatorValue) ? locatorValue : {};
    return {
      selector: value.selector || "",
      ...meta,
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
    waitMs: undefined,
    targetSnapshot: null,
  };
}

function assertionNeedsTarget(assertType) {
  return ["text_contains", "text_equals", "visible"].includes(`${assertType || ""}`.toLowerCase());
}

function normalizeAssertion(assertion = {}) {
  return {
    assertType: assertion.assertType || assertion.assert_type || "visible",
    expected: assertion.expected ?? "",
    operator: assertion.operator || "",
    actualSource: assertion.actualSource || assertion.actual_source || "",
    enabled: assertion.enabled !== false,
    waitMs: assertion.waitMs ?? assertion.wait_ms,
    targetSnapshot: normalizeTargetSnapshot(assertion.targetSnapshot || assertion.target_snapshot),
  };
}

function stepNeedsTarget(actionType) {
  return ![
    "goto",
    "sleep",
    "wait",
    "assert_page_contains",
    "assert_page_not_contains",
    "assert_title_contains",
    "assert_url_contains",
  ].includes(actionType);
}

function getActionLabel(actionType) {
  return actionOptions.find((item) => item.value === actionType)?.label || actionType || "未设置";
}

function normalizeThinkTimeMs(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) return 0;
  return Math.round(parsed);
}

function normalizeStepParams(actionType, params) {
  const data = isPlainObject(params) ? cloneData(params) : {};
  const thinkTimeMs = normalizeThinkTimeMs(data.thinkTimeMs ?? data.think_time_ms);
  const waitMs = Number(data.waitMs ?? data.wait_ms ?? 0);
  if (actionType === "goto") {
    return { url: data.url || "", thinkTimeMs };
  }
  if (actionType === "fill") {
    return { value: data.value ?? "", thinkTimeMs };
  }
  if (actionType === "press") {
    return { key: data.key || "Enter", thinkTimeMs };
  }
  if (actionType === "select_option") {
    const values = Array.isArray(data.values) ? data.values : data.values ? [data.values] : [];
    return { values: values.map((item) => `${item}`), thinkTimeMs };
  }
  if (["sleep", "wait"].includes(actionType)) {
    return { waitMs: Number.isFinite(waitMs) && waitMs >= 0 ? Math.round(waitMs) : 0, thinkTimeMs };
  }
  if (["assert_page_contains", "assert_page_not_contains"].includes(actionType)) {
    return { text: data.text ?? data.expected ?? "", thinkTimeMs };
  }
  if (actionType === "assert_title_contains") {
    return { title: data.title ?? data.text ?? data.expected ?? "", thinkTimeMs };
  }
  if (actionType === "assert_url_contains") {
    return { urlPart: data.urlPart ?? data.url_part ?? data.text ?? data.expected ?? "", thinkTimeMs };
  }
  if (["assert_text_equals", "assert_text_contains"].includes(actionType)) {
    return { expected: data.expected ?? data.text ?? "", thinkTimeMs };
  }
  return { thinkTimeMs };
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

function normalizePersistScopeHostPatterns(rawValue) {
  let candidates = [];
  if (Array.isArray(rawValue)) {
    candidates = rawValue;
  } else if (typeof rawValue === "string") {
    candidates = rawValue.split(",");
  } else if (rawValue !== undefined && rawValue !== null && rawValue !== "") {
    candidates = [rawValue];
  }
  const seen = new Set();
  return candidates
    .map((item) => `${item ?? ""}`.trim().toLowerCase())
    .filter((item) => {
      if (!item || seen.has(item)) return false;
      seen.add(item);
      return true;
    });
}

function normalizePersistContextScope(scope = {}) {
  const key = `${scope.key ?? scope.scopeKey ?? scope.scope_key ?? scope.persistContextKey ?? scope.persist_context_key ?? ""}`.trim();
  if (!key) return null;
  const hostPatterns = normalizePersistScopeHostPatterns(
    scope.hostPatterns ?? scope.host_patterns ?? scope.host ?? scope.domain
  );
  return {
    key,
    label: `${scope.label ?? scope.name ?? key}`.trim() || key,
    hostPatterns,
    hostPatternsText: hostPatterns.join(","),
    enabled: parseBooleanFlag(scope.enabled, true),
    remark: `${scope.remark ?? ""}`.trim(),
  };
}

function normalizePersistContextScopeList(rawList) {
  if (!Array.isArray(rawList)) return [];
  const seen = new Set();
  const result = [];
  rawList.forEach((item) => {
    const normalized = normalizePersistContextScope(item);
    if (!normalized) return;
    const keyLower = normalized.key.toLowerCase();
    if (seen.has(keyLower)) return;
    seen.add(keyLower);
    result.push(normalized);
  });
  return result;
}

function createEmptyRuntimeProfile() {
  return {
    profileId: undefined,
    profileName: "",
    profileType: "runtime",
    targets: ["web"],
    enabled: true,
    projectId: undefined,
    moduleId: undefined,
    sort: 0,
    runtimeOverridesText: "",
    variablesText: "",
    cookieRulesText: "",
    persistContextScopes: [],
    remark: "",
  };
}

function normalizeRuntimeProfile(profile = {}) {
  const base = createEmptyRuntimeProfile();
  const runtimeOverrides = isPlainObject(profile.runtimeOverrides || profile.runtime_overrides)
    ? cloneData(profile.runtimeOverrides || profile.runtime_overrides)
    : {};
  const variables = isPlainObject(profile.variables)
    ? cloneData(profile.variables)
    : {};
  const cookieRules = Array.isArray(profile.cookieRules || profile.cookie_rules)
    ? cloneData(profile.cookieRules || profile.cookie_rules)
    : [];
  const persistContextScopes = normalizePersistContextScopeList(
    profile.persistContextScopes || profile.persist_context_scopes
  );
  const targets = Array.isArray(profile.targets) && profile.targets.length
    ? profile.targets.map((item) => `${item}`.trim().toLowerCase()).filter(Boolean)
    : ["web"];
  return {
    ...base,
    ...profile,
    profileId: normalizeIdValue(profile.profileId || profile.profile_id),
    profileName: profile.profileName || profile.profile_name || "",
    profileType: profile.profileType || profile.profile_type || "runtime",
    targets,
    enabled: profile.enabled !== false,
    projectId: normalizeIdValue(profile.projectId || profile.project_id),
    moduleId: normalizeIdValue(profile.moduleId || profile.module_id),
    sort: Number.isFinite(Number(profile.sort)) ? Math.max(Math.round(Number(profile.sort)), 0) : 0,
    runtimeOverridesText: Object.keys(runtimeOverrides).length ? safeJsonStringify(runtimeOverrides) : "",
    variablesText: Object.keys(variables).length ? safeJsonStringify(variables) : "",
    cookieRulesText: cookieRules.length ? safeJsonStringify(cookieRules) : "",
    persistContextScopes,
    remark: profile.remark || "",
    createTime: profile.createTime || profile.create_time,
    updateTime: profile.updateTime || profile.update_time,
  };
}

function normalizeStorageStatePayload(rawState) {
  let state = rawState;
  if (typeof rawState === "string" && rawState.trim()) {
    try {
      state = JSON.parse(rawState);
    } catch (error) {
      state = {};
    }
  }
  const value = isPlainObject(state) ? state : {};
  const cookies = Array.isArray(value.cookies) ? value.cookies.filter((item) => isPlainObject(item)).map((item) => cloneData(item)) : [];
  const origins = Array.isArray(value.origins) ? value.origins.filter((item) => isPlainObject(item)).map((item) => cloneData(item)) : [];
  return {
    cookies,
    origins,
  };
}

function createEmptyBrowserSession() {
  return {
    sessionId: undefined,
    sessionName: "",
    scopeKey: "",
    enabled: true,
    projectId: undefined,
    moduleId: undefined,
    browserName: "",
    sort: 0,
    hostPatternsText: "",
    storageStateText: safeJsonStringify({ cookies: [], origins: [] }),
    remark: "",
  };
}

function normalizeBrowserSession(session = {}) {
  const base = createEmptyBrowserSession();
  const hostPatterns = normalizePersistScopeHostPatterns(
    session.hostPatterns ?? session.host_patterns ?? session.host ?? session.domain
  );
  const storageState = normalizeStorageStatePayload(session.storageState ?? session.storage_state);
  const scopeKey = `${session.scopeKey ?? session.scope_key ?? session.persistContextKey ?? session.persist_context_key ?? ""}`.trim();
  return {
    ...base,
    ...session,
    sessionId: normalizeIdValue(session.sessionId || session.session_id),
    sessionName: `${session.sessionName || session.session_name || ""}`.trim(),
    scopeKey: scopeKey || normalizeIdValue(session.sessionId || session.session_id) || "",
    enabled: parseBooleanFlag(session.enabled, true),
    projectId: normalizeIdValue(session.projectId || session.project_id),
    moduleId: normalizeIdValue(session.moduleId || session.module_id),
    browserName: `${session.browserName || session.browser_name || ""}`.trim().toLowerCase(),
    sort: Number.isFinite(Number(session.sort)) ? Math.max(Math.round(Number(session.sort)), 0) : 0,
    hostPatternsText: hostPatterns.join(","),
    storageStateText: safeJsonStringify(storageState),
    remark: `${session.remark || ""}`.trim(),
    createTime: session.createTime || session.create_time,
    updateTime: session.updateTime || session.update_time,
  };
}

const form = ref(createEmptyCase());
const runForm = ref({
  agentId: undefined,
  browserName: "chromium",
  headless: true,
  closeBrowserOnFinish: true,
  browserSessionId: undefined,
  persistContextEnabled: false,
  persistContextAutoSyncSession: true,
  persistContextKey: "",
  manualLoginEnabled: false,
  manualLoginRequireConfirm: false,
  manualLoginWaitSec: 120,
  stepTimeoutMs: undefined,
  stepThinkTimeMs: undefined,
});
const recordingForm = ref({
  webCaseId: undefined,
  sessionName: "",
  agentId: undefined,
  browserName: "chromium",
  headless: false,
  startUrl: "",
  browserSessionId: undefined,
  persistContextEnabled: false,
  persistContextAutoSyncSession: true,
  persistContextKey: "",
  manualLoginEnabled: false,
  manualLoginRequireConfirm: false,
  manualLoginWaitSec: 120,
  closeBrowserOnStop: true,
  captureAssertions: true,
  attachAssertionsToPreviousStep: true,
  autoAssertTextOnClick: false,
  recordingId: undefined,
});
const runtimeProfileForm = ref(createEmptyRuntimeProfile());
const browserSessionForm = ref(createEmptyBrowserSession());
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

const filteredRuntimeProfileModules = computed(() => {
  if (!runtimeProfileForm.value.projectId) return moduleOptions.value;
  return moduleOptions.value.filter((item) => isSameId(item.projectId, runtimeProfileForm.value.projectId));
});

const filteredBrowserSessionModules = computed(() => {
  if (!browserSessionForm.value.projectId) return moduleOptions.value;
  return moduleOptions.value.filter((item) => isSameId(item.projectId, browserSessionForm.value.projectId));
});

const filteredRuntimeProfiles = computed(() => {
  const keyword = `${runtimeProfileKeyword.value || ""}`.trim().toLowerCase();
  if (!keyword) return runtimeProfiles.value;
  return runtimeProfiles.value.filter((item) => `${item.profileName || ""}`.toLowerCase().includes(keyword));
});

const filteredBrowserSessions = computed(() => {
  const keyword = `${browserSessionKeyword.value || ""}`.trim().toLowerCase();
  if (!keyword) return browserSessions.value;
  return browserSessions.value.filter((item) => {
    const sessionName = `${item.sessionName || ""}`.toLowerCase();
    const scopeKey = `${item.scopeKey || ""}`.toLowerCase();
    return sessionName.includes(keyword) || scopeKey.includes(keyword);
  });
});

const runScopeProjectId = computed(() => runTargetCases.value?.[0]?.projectId || selectedCase.value?.projectId);
const runScopeModuleId = computed(() => runTargetCases.value?.[0]?.moduleId || selectedCase.value?.moduleId);

const recordingScopeProjectId = computed(() => selectedCase.value?.projectId);
const recordingScopeModuleId = computed(() => selectedCase.value?.moduleId);

const availableRuntimeProfilesForRun = computed(() => runtimeProfiles.value.filter(
  (item) => item.enabled !== false && profileSupportsWeb(item) && isRuntimeProfileScopeMatch(item, runScopeProjectId.value, runScopeModuleId.value)
));

const availableRuntimeProfilesForRecording = computed(() => runtimeProfiles.value.filter(
  (item) => item.enabled !== false && profileSupportsWeb(item) && isRuntimeProfileScopeMatch(item, recordingScopeProjectId.value, recordingScopeModuleId.value)
));

const availableBrowserSessionsForRun = computed(() => browserSessions.value.filter(
  (item) => item.enabled !== false
    && isRuntimeProfileScopeMatch(item, runScopeProjectId.value, runScopeModuleId.value)
    && isBrowserSessionBrowserMatch(item, runForm.value.browserName)
));

const availableBrowserSessionsForRecording = computed(() => browserSessions.value.filter(
  (item) => item.enabled !== false
    && isRuntimeProfileScopeMatch(item, recordingScopeProjectId.value, recordingScopeModuleId.value)
    && isBrowserSessionBrowserMatch(item, recordingForm.value.browserName)
));

function collectPersistScopeOptionsFromSessions(sessions, currentKey = "") {
  const rows = [];
  const seen = new Set();
  const sessionList = Array.isArray(sessions) ? sessions : [];
  sessionList.forEach((session) => {
    const scopeKey = `${session?.scopeKey || session?.sessionId || ""}`.trim();
    if (!scopeKey) return;
    const keyLower = scopeKey.toLowerCase();
    if (seen.has(keyLower)) return;
    seen.add(keyLower);
    const hostPatterns = normalizePersistScopeHostPatterns(session?.hostPatternsText || session?.hostPatterns);
    rows.push({
      key: scopeKey,
      label: `${session?.sessionName || scopeKey}`.trim() || scopeKey,
      hostPatterns,
      hostPatternsText: hostPatterns.join(","),
      enabled: session?.enabled !== false,
      remark: `${session?.remark || ""}`.trim(),
      sourceSessionName: `${session?.sessionName || ""}`.trim(),
      sourceSessionId: `${session?.sessionId || ""}`.trim(),
    });
  });
  const current = `${currentKey || ""}`.trim();
  if (current && !rows.some((item) => `${item.key}`.toLowerCase() === current.toLowerCase())) {
    rows.unshift({
      key: current,
      label: current,
      hostPatterns: [],
      hostPatternsText: "",
      enabled: true,
      remark: "",
      sourceSessionName: "",
      sourceSessionId: "",
    });
  }
  return rows;
}

function formatPersistScopeLabel(scope) {
  const label = `${scope?.label || scope?.key || ""}`.trim() || `${scope?.key || ""}`.trim();
  const key = `${scope?.key || ""}`.trim();
  const sessionName = `${scope?.sourceSessionName || ""}`.trim();
  const hostPatterns = normalizePersistScopeHostPatterns(scope?.hostPatterns || scope?.hostPatternsText);
  const hostText = hostPatterns.length ? hostPatterns.join(",") : "";
  const extra = [sessionName, hostText].filter(Boolean).join(" | ");
  if (!extra) {
    return label === key || !key ? label : `${label} [${key}]`;
  }
  return label === key || !key ? `${label} (${extra})` : `${label} [${key}] (${extra})`;
}

function hasPersistScopeOption(options, key) {
  const normalizedKey = `${key || ""}`.trim().toLowerCase();
  if (!normalizedKey) return false;
  return (Array.isArray(options) ? options : []).some((item) => `${item?.key || ""}`.trim().toLowerCase() === normalizedKey);
}

const availablePersistScopesForRun = computed(() => {
  return collectPersistScopeOptionsFromSessions(availableBrowserSessionsForRun.value, runForm.value.persistContextKey);
});

const availablePersistScopesForRecording = computed(() => {
  return collectPersistScopeOptionsFromSessions(availableBrowserSessionsForRecording.value, recordingForm.value.persistContextKey);
});

const caseDialogTitle = computed(() => `${form.value.webCaseId ? "编辑" : "新增"} Web 用例`);
const currentStep = computed(() => form.value.steps[selectedStepIndex.value] || null);
const stepDetailTitle = computed(() => (selectedStepIndex.value >= 0 ? `步骤详情 - #${selectedStepIndex.value + 1}` : "步骤详情"));
const runDetailTitle = computed(() => {
  if (!runDetail.value) return "执行详情";
  return `执行详情 - ${runDetail.value.caseName || getCaseName(runDetail.value.webCaseId) || runDetail.value.webCaseId}`;
});
const runTargetLabel = computed(() => {
  const targets = Array.isArray(runTargetCases.value) ? runTargetCases.value : [];
  if (!targets.length) return "";
  if (targets.length === 1) {
    const target = targets[0];
    return `${target.caseName || target.webCaseId} [${target.webCaseId}]`;
  }
  const previewText = targets.slice(0, 5).map((item) => `${item.caseName || item.webCaseId} [${item.webCaseId}]`).join("，");
  return `已选择 ${targets.length} 条用例：${previewText}${targets.length > 5 ? " ..." : ""}`;
});
const runStepResults = computed(() => Array.isArray(runDetail.value?.result?.steps) ? runDetail.value.result.steps : []);
const runRuntimeDebug = computed(() => (isPlainObject(runDetail.value?.result?.runtimeDebug) ? runDetail.value.result.runtimeDebug : null));
const runDetailFailureMessage = computed(() => getRunRowFailureReason(runDetail.value));
const runCookieApplySummary = computed(() => {
  const runtimeDebug = runRuntimeDebug.value;
  if (!runtimeDebug) {
    return "";
  }
  const cookieApply = isPlainObject(runtimeDebug.beforeStartCookieApply) ? runtimeDebug.beforeStartCookieApply : null;
  if (!cookieApply) {
    return "";
  }
  const appliedCount = Number(cookieApply.appliedCount || 0);
  const rules = Array.isArray(cookieApply.rules)
    ? cookieApply.rules.map((item) => `${item || ""}`.trim()).filter(Boolean)
    : [];
  if (appliedCount > 0) {
    return `启动前已注入 ${appliedCount} 个 Cookie${rules.length ? `（规则：${rules.join("，")}）` : ""}`;
  }
  return "启动前未注入 Cookie，请检查配置规则的 host/domain/path 与目标站点是否匹配";
});
const runCookieApplySummaryType = computed(() => {
  const runtimeDebug = runRuntimeDebug.value;
  if (!runtimeDebug) {
    return "info";
  }
  const cookieApply = isPlainObject(runtimeDebug.beforeStartCookieApply) ? runtimeDebug.beforeStartCookieApply : null;
  if (!cookieApply) {
    return "info";
  }
  const appliedCount = Number(cookieApply.appliedCount || 0);
  return appliedCount > 0 ? "success" : "warning";
});
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
const recordingAssertionTipText = computed(() => {
  if (!recordingForm.value.captureAssertions) {
    return "当前已关闭断言录制，仅记录操作步骤。";
  }
  const pickTip = recordingForm.value.attachAssertionsToPreviousStep
    ? "按住 Alt 点击任意元素可把断言追加到上一步（不触发点击）。"
    : "按住 Alt 点击任意元素会新增平级断言步骤（不触发点击）。";
  if (recordingForm.value.autoAssertTextOnClick) {
    return `录制技巧：普通点击会先插入“断言文本包含”再执行点击；${pickTip}`;
  }
  return `录制技巧：${pickTip} 适合新页面批量文案验收。`;
});
const recordingLiveStatusText = computed(() => {
  if (!recordingForm.value.recordingId) {
    return "请先填写录制参数后启动录制。";
  }
  if (recordingDetail.value?.status === 5) {
    const summaryPayload = getRecordingSummaryPayload(recordingDetail.value);
    const summaryStatus = `${summaryPayload?.status || ""}`.trim().toLowerCase();
    if (["cancelled", "canceled"].includes(summaryStatus)) {
      return "录制已取消。";
    }
    if (["stopped", "finished", "failed"].includes(summaryStatus)) {
      return "录制已结束。";
    }
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
const replayFailureMessage = computed(() => getRunRowFailureReason(replayResult.value));
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

function parseBooleanFlag(value, defaultValue = false) {
  if (value === undefined || value === null || value === "") return defaultValue;
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  const normalized = `${value}`.trim().toLowerCase();
  if (["1", "true", "yes", "on", "enabled"].includes(normalized)) return true;
  if (["0", "false", "no", "off", "disabled"].includes(normalized)) return false;
  return defaultValue;
}

function normalizeManualLoginWaitSec(value, defaultValue = 120) {
  const raw = Number(value);
  if (!Number.isFinite(raw)) return defaultValue;
  return Math.min(3600, Math.max(0, Math.round(raw)));
}

async function confirmAndContinueRunManualLogin({ runId, agentId, caseName }) {
  try {
    await ElMessageBox.confirm(
      `浏览器已启动，请先手动完成登录，再点击继续。\n执行记录ID：${runId}${caseName ? `\n目标用例：${caseName}` : ""}`,
      "等待手动登录",
      {
        confirmButtonText: "我已登录，继续执行",
        cancelButtonText: "取消继续",
        type: "warning",
        closeOnClickModal: false,
        closeOnPressEscape: false,
        showClose: false,
        distinguishCancelAndClose: true,
      }
    );
  } catch {
    try {
      await cancelWebRun({
        webCaseRunId: runId,
        agentId: agentId || undefined,
        reason: "用户取消继续执行",
      });
      ElMessage.info("已取消执行准备");
    } catch (cancelError) {
      const msg = cancelError?.response?.data?.msg || cancelError?.message || "取消执行准备失败";
      ElMessage.warning(msg);
    }
    throw new Error("已取消继续执行");
  }
  return continueWebRun({
    webCaseRunId: runId,
    agentId: agentId || undefined,
  });
}

async function confirmAndContinueRecordingManualLogin({ recordingId, agentId, sessionName }) {
  try {
    await ElMessageBox.confirm(
      `浏览器已启动，请先手动完成登录，再点击继续录制。\n录制ID：${recordingId}${sessionName ? `\n录制名称：${sessionName}` : ""}`,
      "等待手动登录",
      {
        confirmButtonText: "我已登录，继续录制",
        cancelButtonText: "取消继续",
        type: "warning",
        closeOnClickModal: false,
        closeOnPressEscape: false,
        showClose: false,
        distinguishCancelAndClose: true,
      }
    );
  } catch {
    try {
      await cancelWebRecording({
        recordingId,
        agentId: agentId || undefined,
        reason: "用户取消继续录制",
      });
      ElMessage.info("已取消录制准备");
    } catch (cancelError) {
      const msg = cancelError?.response?.data?.msg || cancelError?.message || "取消录制准备失败";
      ElMessage.warning(msg);
    }
    throw new Error("已取消继续录制");
  }
  return continueWebRecording({
    recordingId,
    agentId: agentId || undefined,
  });
}

function getRunStatusMeta(status) {
  return runStatusOptions.find((item) => item.value === status) || { label: `${status ?? "-"}`, type: "info" };
}

function getRecordingStatusMeta(status) {
  return recordingStatusOptions.find((item) => item.value === status) || { label: `${status ?? "-"}`, type: "info" };
}

function normalizeStepStatus(status) {
  return `${status ?? ""}`.trim().toLowerCase();
}

function isPassedStepStatus(status) {
  const normalized = normalizeStepStatus(status);
  return ["passed", "success", "ok"].includes(normalized) || status === 1 || status === true;
}

function isSkippedStepStatus(status) {
  const normalized = normalizeStepStatus(status);
  return ["skipped", "skip", "disabled"].includes(normalized);
}

function isRunningStepStatus(status) {
  const normalized = normalizeStepStatus(status);
  return ["running", "in_progress", "processing"].includes(normalized);
}

function getStepStatusTagType(status) {
  if (isPassedStepStatus(status)) return "success";
  if (isSkippedStepStatus(status)) return "info";
  if (isRunningStepStatus(status)) return "warning";
  return "danger";
}

function getStepFailureReason(step) {
  if (!step) return "-";
  if (isPassedStepStatus(step.status) || isSkippedStepStatus(step.status) || isRunningStepStatus(step.status)) return "-";
  const candidates = [step.error, step.errorMessage, step.message, step.reason, step.errorType, step.error_type];
  for (const item of candidates) {
    const text = `${item ?? ""}`.trim();
    if (text) return text;
  }
  return "执行失败（无详细错误）";
}

function getFirstFailedStep(resultPayload) {
  const steps = Array.isArray(resultPayload?.steps) ? resultPayload.steps : [];
  return steps.find(
    (item) => item
      && !isPassedStepStatus(item.status)
      && !isSkippedStepStatus(item.status)
      && !isRunningStepStatus(item.status)
  );
}

function getRunRowFailureReason(row) {
  const direct = `${row?.errorMessage ?? ""}`.trim();
  if (direct) return direct;
  const failedStep = getFirstFailedStep(row?.result);
  if (!failedStep) return "-";
  const stepName = `${failedStep.stepName ?? failedStep.step_name ?? failedStep.stepId ?? failedStep.step_id ?? "未知步骤"}`.trim();
  const reason = getStepFailureReason(failedStep);
  if (!stepName) return reason || "执行失败";
  if (!reason || reason === "-") return `[${stepName}] 执行失败`;
  if (reason.includes(stepName)) return reason;
  return `[${stepName}] ${reason}`;
}

function getRunResultPayload(row) {
  return isPlainObject(row?.result) ? row.result : {};
}

function isRunWaitingManualConfirm(row) {
  const resultPayload = getRunResultPayload(row);
  if (resultPayload.awaitingManualConfirm === true) return true;
  const directGate = isPlainObject(resultPayload.manualLoginGate) ? resultPayload.manualLoginGate : null;
  const runtimeDebug = isPlainObject(resultPayload.runtimeDebug) ? resultPayload.runtimeDebug : null;
  const runtimeGate = isPlainObject(runtimeDebug?.manualLoginGate) ? runtimeDebug.manualLoginGate : null;
  const gate = directGate || runtimeGate;
  if (gate && gate.waitingConfirm === true) return true;
  const statusText = `${resultPayload.manualLoginStatus || ""}`.trim().toLowerCase();
  return statusText === "waiting_manual_login";
}

function canStopRun(row) {
  return Number(row?.status) === 9 && !isRunWaitingManualConfirm(row);
}

function canCancelPreparedRun(row) {
  return Number(row?.status) === 9 && isRunWaitingManualConfirm(row);
}

function getRecordingSummaryPayload(row) {
  if (isPlainObject(row?.resultSummary)) return row.resultSummary;
  if (isPlainObject(row?.result_summary)) return row.result_summary;
  if (isPlainObject(row?.resultSummaryJson)) return row.resultSummaryJson;
  if (isPlainObject(row?.result_summary_json)) return row.result_summary_json;
  return {};
}

function isRecordingWaitingManualConfirm(row) {
  const payload = getRecordingSummaryPayload(row);
  const manualGate = isPlainObject(payload.manualLoginGate) ? payload.manualLoginGate : null;
  if (manualGate && manualGate.waitingConfirm === true) return true;
  const statusText = `${payload.status || ""}`.trim().toLowerCase();
  return statusText === "waiting_manual_login";
}

function canStopRecording(row) {
  return Number(row?.status) === 2 && !isRecordingWaitingManualConfirm(row);
}

function canCancelPreparedRecording(row) {
  return Number(row?.status) === 2 && isRecordingWaitingManualConfirm(row);
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

function normalizeRuntimeTargets(targets) {
  if (!Array.isArray(targets)) return ["web"];
  const normalized = targets.map((item) => `${item || ""}`.trim().toLowerCase()).filter(Boolean);
  return normalized.length ? Array.from(new Set(normalized)) : ["web"];
}

function profileSupportsWeb(profile) {
  const targets = normalizeRuntimeTargets(profile?.targets);
  return targets.includes("web") || targets.includes("all") || targets.includes("*");
}

function isRuntimeProfileScopeMatch(profile, projectId, moduleId) {
  const profileProjectId = normalizeIdValue(profile?.projectId);
  const profileModuleId = normalizeIdValue(profile?.moduleId);
  const currentProjectId = normalizeIdValue(projectId);
  const currentModuleId = normalizeIdValue(moduleId);
  if (profileProjectId && currentProjectId && profileProjectId !== currentProjectId) return false;
  if (profileProjectId && !currentProjectId) return false;
  if (profileModuleId && currentModuleId && profileModuleId !== currentModuleId) return false;
  if (profileModuleId && !currentModuleId) return false;
  return true;
}

function isBrowserSessionBrowserMatch(session, browserName) {
  const sessionBrowser = `${session?.browserName || ""}`.trim().toLowerCase();
  if (!sessionBrowser) return true;
  const targetBrowser = `${browserName || ""}`.trim().toLowerCase();
  if (!targetBrowser) return true;
  return sessionBrowser === targetBrowser;
}

function formatRuntimeProfileScope(profile) {
  const projectName = profile?.projectId ? (getProjectName(profile.projectId) || profile.projectId) : "全局";
  const moduleName = profile?.moduleId ? (getModuleName(profile.moduleId) || profile.moduleId) : "全部模块";
  return `${projectName} / ${moduleName}`;
}

function formatRuntimeProfileLabel(profile) {
  const name = profile?.profileName || profile?.profileId || "未命名配置";
  return `${name}（${formatRuntimeProfileScope(profile)}）`;
}

function formatBrowserSessionLabel(session) {
  const name = `${session?.sessionName || session?.scopeKey || session?.sessionId || "未命名Session"}`.trim();
  const browserValue = `${session?.browserName || ""}`.trim().toLowerCase();
  const browserLabel = browserValue
    ? (browserOptions.find((item) => item.value === browserValue)?.label || browserValue)
    : "";
  return `${name}（${formatRuntimeProfileScope(session)}${browserLabel ? ` / ${browserLabel}` : ""}）`;
}

const runtimeVariableKeys = ["variables", "runtimeVariables", "runtime_variables", "cookieVariables", "cookie_variables"];
const runtimeCookieRuleKeys = ["cookieRules", "cookie_rules", "cookieScopes", "cookie_scopes", "cookieProfiles", "cookie_profiles"];
const runtimeVarPattern = /\$\{([a-zA-Z0-9_.-]+)\}|\{\{([a-zA-Z0-9_.-]+)\}\}/g;

function getRuntimeProfileById(profileId) {
  const normalizedId = normalizeIdValue(profileId);
  if (!normalizedId) return null;
  return runtimeProfiles.value.find((item) => isSameId(item.profileId, normalizedId)) || null;
}

function collectRuntimeVariables(runtimeOverrides) {
  const source = isPlainObject(runtimeOverrides) ? runtimeOverrides : {};
  const result = {};
  runtimeVariableKeys.forEach((key) => {
    const value = source[key];
    if (isPlainObject(value)) {
      Object.assign(result, value);
    }
  });
  return result;
}

function collectCookieRules(runtimeOverrides) {
  const source = isPlainObject(runtimeOverrides) ? runtimeOverrides : {};
  const result = [];
  runtimeCookieRuleKeys.forEach((key) => {
    const value = source[key];
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (isPlainObject(item)) {
          result.push(cloneData(item));
        }
      });
    }
  });
  return result;
}

function mergeRuntimeOverrides(baseRuntimeOverrides, overrideRuntimeOverrides) {
  const base = isPlainObject(baseRuntimeOverrides) ? cloneData(baseRuntimeOverrides) : {};
  const override = isPlainObject(overrideRuntimeOverrides) ? cloneData(overrideRuntimeOverrides) : {};
  const merged = { ...base };
  Object.entries(override).forEach(([key, value]) => {
    if (value !== null && value !== undefined) {
      merged[key] = value;
    }
  });

  const mergedVariables = collectRuntimeVariables(base);
  Object.assign(mergedVariables, collectRuntimeVariables(override));
  if (Object.keys(mergedVariables).length) {
    merged.variables = mergedVariables;
  }
  runtimeVariableKeys.forEach((key) => {
    if (key !== "variables") {
      delete merged[key];
    }
  });

  const mergedRules = [...collectCookieRules(base), ...collectCookieRules(override)];
  if (mergedRules.length) {
    merged.cookieRules = mergedRules;
  }
  runtimeCookieRuleKeys.forEach((key) => {
    if (key !== "cookieRules") {
      delete merged[key];
    }
  });
  return merged;
}

function composeRuntimeOverridesFromProfile(profile) {
  if (!profile) return {};
  const runtimeOverrides = isPlainObject(profile.runtimeOverrides || profile.runtime_overrides)
    ? cloneData(profile.runtimeOverrides || profile.runtime_overrides)
    : {};
  if (isPlainObject(profile.variables) && Object.keys(profile.variables).length) {
    const existingVariables = collectRuntimeVariables(runtimeOverrides);
    runtimeOverrides.variables = { ...existingVariables, ...profile.variables };
  }
  if (Array.isArray(profile.cookieRules || profile.cookie_rules) && (profile.cookieRules || profile.cookie_rules).length) {
    const existingRules = collectCookieRules(runtimeOverrides);
    runtimeOverrides.cookieRules = [...existingRules, ...cloneData(profile.cookieRules || profile.cookie_rules)];
  }
  runtimeVariableKeys.forEach((key) => {
    if (key !== "variables") {
      delete runtimeOverrides[key];
    }
  });
  runtimeCookieRuleKeys.forEach((key) => {
    if (key !== "cookieRules") {
      delete runtimeOverrides[key];
    }
  });
  return runtimeOverrides;
}

function interpolateRuntimeString(value, variables) {
  const text = `${value ?? ""}`;
  if (!text) return text;
  return text.replace(runtimeVarPattern, (match, varA, varB) => {
    const key = varA || varB || "";
    if (Object.prototype.hasOwnProperty.call(variables, key)) {
      return `${variables[key] ?? ""}`;
    }
    return match;
  });
}

function ensureArrayValue(value) {
  if (Array.isArray(value)) return value.map((item) => `${item ?? ""}`).filter((item) => item.trim());
  if (value === undefined || value === null || value === "") return [];
  return [`${value}`];
}

function hostFromUrl(url) {
  const raw = `${url ?? ""}`.trim();
  if (!raw) return "";
  try {
    return new URL(raw).hostname.toLowerCase();
  } catch (error) {
    return "";
  }
}

function normalizeCookieRuleForPreview(rule, index = 0) {
  if (!isPlainObject(rule)) return null;
  const rawCookies = Array.isArray(rule.cookies) ? rule.cookies : [];
  const cookies = rawCookies.filter((item) => isPlainObject(item)).map((item) => cloneData(item));
  if (!cookies.length) return null;
  const match = isPlainObject(rule.match) ? cloneData(rule.match) : {};
  ["host", "domain", "urlContains", "url_contains", "urlRegex", "url_regex"].forEach((key) => {
    if (!Object.prototype.hasOwnProperty.call(match, key) && rule[key] !== undefined && rule[key] !== null && rule[key] !== "") {
      match[key] = rule[key];
    }
  });
  const applyOnRaw = Array.isArray(rule.applyOn || rule.apply_on) ? (rule.applyOn || rule.apply_on) : [];
  const applyOn = new Set(
    applyOnRaw
      .map((item) => `${item ?? ""}`.trim().toLowerCase())
      .filter(Boolean)
  );
  if (!applyOn.size) {
    ["before_start", "before_step", "before_goto"].forEach((item) => applyOn.add(item));
  }
  return {
    name: `${rule.name || `rule_${index + 1}`}`,
    match,
    applyOn,
    cookies,
  };
}

function ruleMatchesUrlForPreview(rule, targetUrl, targetHost, variables) {
  const match = isPlainObject(rule?.match) ? rule.match : {};
  if (!Object.keys(match).length) return true;

  const hostValues = [
    ...ensureArrayValue(match.host),
    ...ensureArrayValue(match.domain),
  ].map((item) => interpolateRuntimeString(`${item}`.toLowerCase(), variables));
  if (hostValues.length) {
    if (!targetHost) return false;
    if (!hostValues.some((item) => item && (targetHost === item || targetHost.endsWith(`.${item}`)))) {
      return false;
    }
  }

  const containsValues = ensureArrayValue(match.urlContains ?? match.url_contains).map((item) => interpolateRuntimeString(item, variables));
  if (containsValues.length) {
    if (!containsValues.some((item) => item && targetUrl.includes(item))) {
      return false;
    }
  }

  const regexValues = ensureArrayValue(match.urlRegex ?? match.url_regex).map((item) => interpolateRuntimeString(item, variables));
  if (regexValues.length) {
    let matched = false;
    regexValues.forEach((pattern) => {
      if (matched || !pattern) return;
      try {
        if (new RegExp(pattern).test(targetUrl)) {
          matched = true;
        }
      } catch (error) {
        // ignore invalid regex
      }
    });
    if (!matched) {
      return false;
    }
  }
  return true;
}

function normalizeCookieForPreview(cookieDef, targetUrl, targetHost, variables, defaultDomain = "") {
  if (!isPlainObject(cookieDef)) return null;
  const name = interpolateRuntimeString(cookieDef.name, variables).trim();
  if (!name) return null;
  const value = interpolateRuntimeString(cookieDef.value, variables);
  if (value === "") return null;

  const cookie = {
    name,
    value,
  };
  const explicitUrl = cookieDef.url ? interpolateRuntimeString(cookieDef.url, variables) : "";
  const explicitDomain = cookieDef.domain ? interpolateRuntimeString(cookieDef.domain, variables) : "";
  const explicitPath = cookieDef.path ? interpolateRuntimeString(cookieDef.path, variables) : "";
  const fallbackDomain = interpolateRuntimeString(defaultDomain || "", variables).trim().replace(/^\./, "").toLowerCase();
  if (explicitUrl) {
    cookie.url = explicitUrl;
  } else if (explicitDomain) {
    cookie.domain = explicitDomain;
    cookie.path = explicitPath || "/";
  } else if (fallbackDomain) {
    cookie.domain = fallbackDomain;
    cookie.path = explicitPath || "/";
  } else if (targetUrl) {
    cookie.url = targetUrl;
  } else if (targetHost) {
    cookie.domain = targetHost;
    cookie.path = "/";
  } else {
    return null;
  }
  if (cookieDef.httpOnly !== undefined) {
    cookie.httpOnly = Boolean(cookieDef.httpOnly);
  }
  if (cookieDef.secure !== undefined) {
    cookie.secure = Boolean(cookieDef.secure);
  }
  if (cookieDef.sameSite !== undefined && cookieDef.sameSite !== null && cookieDef.sameSite !== "") {
    cookie.sameSite = `${cookieDef.sameSite}`;
  }
  if (cookieDef.expires !== undefined && cookieDef.expires !== null && cookieDef.expires !== "") {
    const expiresValue = Number(cookieDef.expires);
    if (Number.isFinite(expiresValue)) {
      cookie.expires = Math.round(expiresValue);
    }
  }
  return cookie;
}

function buildCookiePreviewForTarget({ targetUrl, runtimeProfileId, runtimeOverrides, stage = "before_start" }) {
  const normalizedStage = `${stage || ""}`.trim().toLowerCase() || "before_start";
  const normalizedTargetUrl = `${targetUrl || ""}`.trim();
  const targetHost = hostFromUrl(normalizedTargetUrl);

  const profile = getRuntimeProfileById(runtimeProfileId);
  const profileRuntimeOverrides = composeRuntimeOverridesFromProfile(profile);
  const mergedRuntimeOverrides = mergeRuntimeOverrides(profileRuntimeOverrides, runtimeOverrides);
  const variables = collectRuntimeVariables(mergedRuntimeOverrides);
  const rules = collectCookieRules(mergedRuntimeOverrides)
    .map((item, index) => normalizeCookieRuleForPreview(item, index))
    .filter(Boolean);

  const matchedRuleNames = [];
  const cookies = [];
  rules.forEach((rule) => {
    if (rule.applyOn.size && !rule.applyOn.has(normalizedStage)) return;
    if (!ruleMatchesUrlForPreview(rule, normalizedTargetUrl, targetHost, variables)) return;
    matchedRuleNames.push(rule.name);
    const ruleMatch = isPlainObject(rule.match) ? rule.match : {};
    const defaultDomainCandidates = [
      ...ensureArrayValue(ruleMatch.domain),
      ...ensureArrayValue(ruleMatch.host),
    ];
    const defaultDomain = defaultDomainCandidates
      .map((item) => interpolateRuntimeString(item, variables).trim().replace(/^\./, "").toLowerCase())
      .find((item) => item);
    rule.cookies.forEach((cookieDef) => {
      const normalized = normalizeCookieForPreview(cookieDef, normalizedTargetUrl, targetHost, variables, defaultDomain);
      if (normalized) {
        cookies.push(normalized);
      }
    });
  });

  const dedup = new Map();
  cookies.forEach((cookie) => {
    const key = `${cookie.name}::${cookie.domain || cookie.url || ""}::${cookie.path || "/"}`;
    dedup.set(key, cookie);
  });
  const dedupedCookies = Array.from(dedup.values());
  return {
    targetUrl: normalizedTargetUrl,
    targetHost,
    rules: matchedRuleNames,
    cookies: dedupedCookies,
    appliedCount: dedupedCookies.length,
  };
}

function escapeHtml(text) {
  return `${text ?? ""}`
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function hasCookiePreviewInput(runtimeProfileId, runtimeOverrides) {
  if (normalizeIdValue(runtimeProfileId)) return true;
  return collectCookieRules(runtimeOverrides).length > 0;
}

async function confirmCookiePreviewBeforeStart({
  mode,
  targets,
  runtimeProfileId,
  runtimeOverrides,
  stage = "before_start",
}) {
  if (!hasCookiePreviewInput(runtimeProfileId, runtimeOverrides)) {
    return true;
  }
  const normalizedTargets = Array.isArray(targets) ? targets.filter((item) => item && item.targetUrl) : [];
  if (!normalizedTargets.length) {
    return true;
  }
  const previewRows = normalizedTargets.map((target, index) => {
    const preview = buildCookiePreviewForTarget({
      targetUrl: target.targetUrl,
      runtimeProfileId,
      runtimeOverrides,
      stage,
    });
    return {
      label: target.label || `目标${index + 1}`,
      ...preview,
    };
  });
  const hasZeroApply = previewRows.some((item) => Number(item.appliedCount || 0) <= 0);
  const displayRows = previewRows.slice(0, 12);
  const omitted = previewRows.length - displayRows.length;
  const lines = displayRows.map((item, index) => {
    const cookieNames = item.cookies.slice(0, 6).map((cookie) => cookie.name).filter(Boolean);
    const cookieText = cookieNames.length ? `，Cookie: ${escapeHtml(cookieNames.join(", "))}` : "";
    const ruleText = item.rules.length ? `，规则: ${escapeHtml(item.rules.join("、"))}` : "，规则: 无命中";
    return `${index + 1}. <strong>${escapeHtml(item.label)}</strong> (${escapeHtml(item.targetHost || item.targetUrl || "-")})：注入 <strong>${item.appliedCount}</strong> 个${ruleText}${cookieText}`;
  });
  if (omitted > 0) {
    lines.push(`其余 ${omitted} 条目标已省略，规则计算逻辑一致。`);
  }
  if (hasZeroApply) {
    lines.push("存在未命中Cookie规则的目标，可能仍会跳转登录页。");
  }
  const title = mode === "recording" ? "录制前 Cookie 预览" : "执行前 Cookie 预览";
  const confirmText = mode === "recording" ? "确认开始录制" : "确认继续执行";
  const html = `<div style="line-height: 1.6;">${lines.map((line) => `<div>${line}</div>`).join("")}</div>`;
  try {
    await ElMessageBox.confirm(html, title, {
      type: hasZeroApply ? "warning" : "info",
      confirmButtonText: confirmText,
      cancelButtonText: "取消",
      closeOnClickModal: false,
      closeOnPressEscape: false,
      dangerouslyUseHTMLString: true,
    });
    return true;
  } catch (error) {
    return false;
  }
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

function shouldStopRecordingPoll(detailOrStatus) {
  if (isPlainObject(detailOrStatus)) {
    const status = Number(detailOrStatus.status);
    if ([3, 4].includes(status)) {
      return true;
    }
    if (status !== 5) {
      return false;
    }
    const summaryPayload = getRecordingSummaryPayload(detailOrStatus);
    const summaryStatus = `${summaryPayload?.status || ""}`.trim().toLowerCase();
    return ["cancelled", "canceled", "stopped", "finished", "failed"].includes(summaryStatus);
  }
  return [3, 4].includes(Number(detailOrStatus));
}

function shouldStopRunDetailPoll(status) {
  return [1, 2, 3, 8].includes(Number(status));
}

function canUseRecordingResult(status) {
  return [3, 4, 5].includes(Number(status));
}

function describeLocator(locator) {
  if (!locator) return "未设置定位器";
  const resolvedIndex = resolveLocatorIndex(locator.locatorValue);
  const indexSuffix = resolvedIndex === null ? "" : ` / nth=${resolvedIndex}`;
  if (locator.locatorType === "role") {
    return `role=${locator.locatorValue.role || "-"} / name=${locator.locatorValue.name || "-"}${indexSuffix}`;
  }
  if (["label", "placeholder", "text"].includes(locator.locatorType)) {
    return `${locator.locatorType}=${locator.locatorValue.text || "-"}${indexSuffix}`;
  }
  if (locator.locatorType === "test_id") {
    return `testId=${locator.locatorValue.testId || "-"}${indexSuffix}`;
  }
  if (locator.locatorType === "id") {
    return `id=${locator.locatorValue.id || "-"}${indexSuffix}`;
  }
  if (locator.locatorType === "name") {
    return `name=${locator.locatorValue.name || "-"}${indexSuffix}`;
  }
  return `${locator.locatorType}=${locator.locatorValue.selector || "-"}${indexSuffix}`;
}

function describeStepTarget(step) {
  if (!stepNeedsTarget(step.actionType)) {
    if (step.actionType === "goto") return step.params?.url || "页面跳转";
    if (["sleep", "wait"].includes(step.actionType)) return `等待 ${Number(step.params?.waitMs ?? 0) || 0}ms`;
    if (step.actionType === "assert_page_contains") return `页面包含 ${step.params?.text || "-"}`;
    if (step.actionType === "assert_page_not_contains") return `页面不包含 ${step.params?.text || "-"}`;
    if (step.actionType === "assert_title_contains") return `标题包含 ${step.params?.title || "-"}`;
    if (step.actionType === "assert_url_contains") return `URL包含 ${step.params?.urlPart || "-"}`;
    return "页面级动作";
  }
  const firstLocator = step.targetSnapshot?.locators?.find((item) => item.enabled !== false) || step.targetSnapshot?.locators?.[0];
  const locatorText = firstLocator ? describeLocator(firstLocator) : "未设置定位器";
  const elementText = step.targetSnapshot?.elementText ? ` / 文本=${step.targetSnapshot.elementText}` : "";
  return `${locatorText}${elementText}`;
}

function summarizeStepParams(step) {
  if (!step) return "-";
  const thinkTimeMs = normalizeThinkTimeMs(step.params?.thinkTimeMs);
  const appendThinkTime = (text) => (thinkTimeMs > 0 ? `${text || "-"} / 思考${thinkTimeMs}ms` : text || "-");
  if (step.actionType === "goto") return appendThinkTime(step.params?.url || "-");
  if (step.actionType === "fill") return appendThinkTime(step.params?.value || "-");
  if (step.actionType === "press") return appendThinkTime(step.params?.key || "-");
  if (step.actionType === "select_option") {
    const valuesText = Array.isArray(step.params?.values) && step.params.values.length ? step.params.values.join(", ") : "-";
    return appendThinkTime(valuesText);
  }
  if (["sleep", "wait"].includes(step.actionType)) return appendThinkTime(`${Number(step.params?.waitMs ?? 0) || 0}ms`);
  if (step.actionType === "assert_page_contains") return appendThinkTime(`页面包含：${step.params?.text || "-"}`);
  if (step.actionType === "assert_page_not_contains") return appendThinkTime(`页面不含：${step.params?.text || "-"}`);
  if (step.actionType === "assert_title_contains") return appendThinkTime(`标题包含：${step.params?.title || "-"}`);
  if (step.actionType === "assert_url_contains") return appendThinkTime(`URL包含：${step.params?.urlPart || "-"}`);
  if (step.actionType === "assert_text_equals") return appendThinkTime(`文本等于：${step.params?.expected || "-"}`);
  if (step.actionType === "assert_text_contains") return appendThinkTime(`文本包含：${step.params?.expected || "-"}`);
  return appendThinkTime("-");
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

function insertStep(index, actionType = "click") {
  const insertIndex = Math.max(0, Math.min(Number(index), form.value.steps.length));
  form.value.steps.splice(insertIndex, 0, createDefaultStep(actionType));
  selectedStepIndex.value = insertIndex;
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

function setPrimaryLocator(step, index) {
  if (!step?.targetSnapshot?.locators) return;
  if (index <= 0 || index >= step.targetSnapshot.locators.length) return;
  const locators = [...step.targetSnapshot.locators];
  const [preferred] = locators.splice(index, 1);
  locators.unshift(preferred);
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

function handleAssertionTypeChange(assertion) {
  if (!assertionNeedsTarget(assertion?.assertType)) {
    return;
  }
  getAssertionLocatorList(assertion);
}

function ensureAssertionTargetSnapshot(assertion) {
  if (!assertion?.targetSnapshot) {
    assertion.targetSnapshot = createDefaultTargetSnapshot();
  }
  if (!Array.isArray(assertion.targetSnapshot.locators)) {
    assertion.targetSnapshot.locators = [];
  }
  return assertion.targetSnapshot;
}

function getAssertionLocatorList(assertion) {
  if (!assertionNeedsTarget(assertion?.assertType)) {
    return [];
  }
  const snapshot = ensureAssertionTargetSnapshot(assertion);
  if (!snapshot.locators.length) {
    snapshot.locators = [createDefaultLocator()];
  }
  return snapshot.locators;
}

function getAssertionPrimaryLocator(assertion) {
  const locators = getAssertionLocatorList(assertion);
  return locators.find((item) => item.enabled !== false) || locators[0] || null;
}

function updateAssertionPrimaryLocatorType(assertion, locatorType) {
  const locator = getAssertionPrimaryLocator(assertion);
  if (!locator) {
    return;
  }
  locator.locatorType = locatorType;
  locator.locatorValue = normalizeLocatorValue(locatorType, {});
}

function updateAssertionPrimaryLocatorValue(assertion, key, value) {
  const locator = getAssertionPrimaryLocator(assertion);
  if (!locator) {
    return;
  }
  locator.locatorValue = normalizeLocatorValue(locator.locatorType, locator.locatorValue);
  locator.locatorValue[key] = value;
}

function addAssertionLocator(assertion) {
  if (!assertionNeedsTarget(assertion?.assertType)) return;
  const snapshot = ensureAssertionTargetSnapshot(assertion);
  snapshot.locators.push(createDefaultLocator());
}

function moveAssertionLocator(assertion, index, direction) {
  const locators = getAssertionLocatorList(assertion);
  const targetIndex = index + direction;
  if (targetIndex < 0 || targetIndex >= locators.length) return;
  [locators[index], locators[targetIndex]] = [locators[targetIndex], locators[index]];
}

function setAssertionPrimaryLocator(assertion, index) {
  const locators = getAssertionLocatorList(assertion);
  if (index <= 0 || index >= locators.length) return;
  const [preferred] = locators.splice(index, 1);
  locators.unshift(preferred);
}

function removeAssertionLocator(assertion, index) {
  const snapshot = ensureAssertionTargetSnapshot(assertion);
  if (!Array.isArray(snapshot.locators) || !snapshot.locators.length) return;
  snapshot.locators.splice(index, 1);
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
  if (locator.locatorType === "id") {
    return Boolean(locator.locatorValue.id);
  }
  if (locator.locatorType === "name") {
    return Boolean(locator.locatorValue.name);
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
    if (["sleep", "wait"].includes(step.actionType) && Number(step.params.waitMs ?? 0) < 0) {
      return `步骤${index + 1}等待时间不能小于0`;
    }
    if (["assert_page_contains", "assert_page_not_contains"].includes(step.actionType) && !`${step.params.text ?? ""}`.trim()) {
      return `步骤${index + 1}缺少页面断言文本`;
    }
    if (step.actionType === "assert_title_contains" && !`${step.params.title ?? ""}`.trim()) {
      return `步骤${index + 1}缺少标题断言文本`;
    }
    if (step.actionType === "assert_url_contains" && !`${step.params.urlPart ?? ""}`.trim()) {
      return `步骤${index + 1}缺少URL断言文本`;
    }
    if (["assert_text_equals", "assert_text_contains"].includes(step.actionType) && !`${step.params.expected ?? ""}`.trim()) {
      return `步骤${index + 1}缺少元素文本断言值`;
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
  const waitMs = Number(assertion.waitMs);
  return {
    assertType: assertion.assertType,
    expected: assertion.expected ?? "",
    operator: assertion.operator || undefined,
    actualSource: assertion.actualSource || undefined,
    enabled: assertion.enabled !== false,
    waitMs: Number.isFinite(waitMs) && waitMs > 0 ? Math.round(waitMs) : undefined,
    targetSnapshot: assertion.targetSnapshot ? prepareTargetSnapshotForSubmit(assertion.targetSnapshot) : undefined,
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
  const thinkTimeMs = normalizeThinkTimeMs(step.params?.thinkTimeMs);
  const withThinkTime = (payload) => (thinkTimeMs > 0 ? { ...payload, thinkTimeMs } : payload);
  if (step.actionType === "goto") {
    return withThinkTime({ url: step.params.url || "" });
  }
  if (step.actionType === "fill") {
    return withThinkTime({ value: step.params.value ?? "" });
  }
  if (step.actionType === "press") {
    return withThinkTime({ key: step.params.key || "Enter" });
  }
  if (step.actionType === "select_option") {
    return withThinkTime({ values: Array.isArray(step.params.values) ? step.params.values.filter((item) => `${item}`.trim()) : [] });
  }
  if (["sleep", "wait"].includes(step.actionType)) {
    return withThinkTime({ waitMs: Math.max(Math.round(Number(step.params?.waitMs ?? 0) || 0), 0) });
  }
  if (["assert_page_contains", "assert_page_not_contains"].includes(step.actionType)) {
    return withThinkTime({ text: step.params?.text ?? "" });
  }
  if (step.actionType === "assert_title_contains") {
    return withThinkTime({ title: step.params?.title ?? "" });
  }
  if (step.actionType === "assert_url_contains") {
    return withThinkTime({ urlPart: step.params?.urlPart ?? "" });
  }
  if (["assert_text_equals", "assert_text_contains"].includes(step.actionType)) {
    return withThinkTime({ expected: step.params?.expected ?? "" });
  }
  return withThinkTime({});
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
  return listWebRun(runQueryParams.value).then((response) => {
    runRecordList.value = response.rows || [];
    runTotal.value = response.total || 0;
    syncCaseOptions(runRecordList.value);
  }).finally(() => {
    loading.value.runPage = false;
  });
}

function getRecordingList() {
  loading.value.recordingPage = true;
  return listWebRecording(recordingQueryParams.value).then((response) => {
    recordingList.value = response.rows || [];
    recordingTotal.value = response.total || 0;
    syncCaseOptions(recordingList.value);
  }).finally(() => {
    loading.value.recordingPage = false;
  });
}

function collectRunRecordIds(row) {
  if (row?.webCaseRunId) {
    return [normalizeIdValue(row.webCaseRunId)].filter(Boolean);
  }
  const ids = selectedRunRows.value
    .map((item) => normalizeIdValue(item?.webCaseRunId))
    .filter(Boolean);
  return Array.from(new Set(ids));
}

function collectRecordingIds(row) {
  if (row?.recordingId) {
    return [normalizeIdValue(row.recordingId)].filter(Boolean);
  }
  const ids = selectedRecordingRows.value
    .map((item) => normalizeIdValue(item?.recordingId))
    .filter(Boolean);
  return Array.from(new Set(ids));
}

async function handleStopRun(row) {
  const runId = normalizeIdValue(row?.webCaseRunId);
  if (!runId) return;
  try {
    await ElMessageBox.confirm(`确认停止执行记录【${runId}】吗？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    const response = await stopWebRun({
      webCaseRunId: runId,
      agentId: row?.agentId || undefined,
    });
    ElMessage.success(response.msg || "已停止执行");
    await getRunList();
    await refreshRunDetail().catch(() => {});
  } catch (error) {
    const msg = error?.response?.data?.msg || error?.message || "停止执行失败";
    ElMessage.error(msg);
  }
}

async function handleCancelPreparedRun(row) {
  const runId = normalizeIdValue(row?.webCaseRunId);
  if (!runId) return;
  try {
    await ElMessageBox.confirm(`确认取消执行准备【${runId}】吗？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    const response = await cancelWebRun({
      webCaseRunId: runId,
      agentId: row?.agentId || undefined,
      reason: "已取消执行准备",
    });
    ElMessage.success(response.msg || "已取消执行准备");
    await getRunList();
    await refreshRunDetail().catch(() => {});
  } catch (error) {
    const msg = error?.response?.data?.msg || error?.message || "取消执行准备失败";
    ElMessage.error(msg);
  }
}

async function handleDeleteRunRecords(row = null) {
  const ids = collectRunRecordIds(row);
  if (!ids.length) {
    ElMessage.warning("请先选择要删除的执行记录");
    return;
  }
  try {
    await ElMessageBox.confirm(`确认删除 ${ids.length} 条执行记录吗？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    const response = await delWebRun(ids.join(","));
    ElMessage.success(response.msg || "删除成功");
    selectedRunRows.value = [];
    if (runDetail.value?.webCaseRunId && ids.includes(normalizeIdValue(runDetail.value.webCaseRunId))) {
      showRunDetailDialog.value = false;
      runDetail.value = null;
      stopRunDetailPoll();
    }
    await getRunList();
  } catch (error) {
    const msg = error?.response?.data?.msg || error?.message || "删除执行记录失败";
    ElMessage.error(msg);
  }
}

async function handleStopRecording(row) {
  const recordingId = normalizeIdValue(row?.recordingId);
  if (!recordingId) return;
  try {
    await ElMessageBox.confirm(`确认停止录制【${recordingId}】吗？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    const response = await stopWebRecording({
      recordingId,
      agentId: row?.agentId || undefined,
      closeBrowserOnStop: true,
    });
    ElMessage.success(response.msg || "已发送停止录制指令");
    await getRecordingList();
    await refreshRecordingDetail().catch(() => {});
  } catch (error) {
    const msg = error?.response?.data?.msg || error?.message || "停止录制失败";
    ElMessage.error(msg);
  }
}

async function handleCancelPreparedRecording(row) {
  const recordingId = normalizeIdValue(row?.recordingId);
  if (!recordingId) return;
  try {
    await ElMessageBox.confirm(`确认取消录制准备【${recordingId}】吗？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    const response = await cancelWebRecording({
      recordingId,
      agentId: row?.agentId || undefined,
      reason: "已取消录制准备",
    });
    ElMessage.success(response.msg || "已取消录制准备");
    await getRecordingList();
    await refreshRecordingDetail().catch(() => {});
  } catch (error) {
    const msg = error?.response?.data?.msg || error?.message || "取消录制准备失败";
    ElMessage.error(msg);
  }
}

async function handleDeleteRecordingRecords(row = null) {
  const ids = collectRecordingIds(row);
  if (!ids.length) {
    ElMessage.warning("请先选择要删除的录制记录");
    return;
  }
  try {
    await ElMessageBox.confirm(`确认删除 ${ids.length} 条录制记录吗？`, "提示", { type: "warning" });
  } catch {
    return;
  }
  try {
    const response = await delWebRecording(ids.join(","));
    ElMessage.success(response.msg || "删除成功");
    selectedRecordingRows.value = [];
    if (recordingDetail.value?.recordingId && ids.includes(normalizeIdValue(recordingDetail.value.recordingId))) {
      showRecordingDetailDialog.value = false;
      recordingDetail.value = null;
      stopRecordingDetailPoll();
    }
    await getRecordingList();
  } catch (error) {
    const msg = error?.response?.data?.msg || error?.message || "删除录制记录失败";
    ElMessage.error(msg);
  }
}

function clearInvalidRuntimeProfileBindings() {
  const runtimeIds = new Set(runtimeProfiles.value.map((item) => normalizeIdValue(item.profileId)).filter(Boolean));
  if (runtimeProfileForm.value.profileId && !runtimeIds.has(normalizeIdValue(runtimeProfileForm.value.profileId))) {
    runtimeProfileForm.value = createEmptyRuntimeProfile();
  }
  const sessionIds = new Set(browserSessions.value.map((item) => normalizeIdValue(item.sessionId)).filter(Boolean));
  if (runForm.value.browserSessionId && !sessionIds.has(normalizeIdValue(runForm.value.browserSessionId))) {
    runForm.value.browserSessionId = undefined;
  }
  if (recordingForm.value.browserSessionId && !sessionIds.has(normalizeIdValue(recordingForm.value.browserSessionId))) {
    recordingForm.value.browserSessionId = undefined;
  }
  if (browserSessionForm.value.sessionId && !sessionIds.has(normalizeIdValue(browserSessionForm.value.sessionId))) {
    browserSessionForm.value = createEmptyBrowserSession();
  }
}

function createRuntimeProfileDraft() {
  runtimeProfileForm.value = createEmptyRuntimeProfile();
  runtimeProfileImportText.value = "";
  runtimeProfileImportHost.value = "";
}

function handleRuntimeProfileRowChange(row) {
  if (!row) return;
  runtimeProfileForm.value = normalizeRuntimeProfile(row);
}

function loadRuntimeProfiles() {
  loading.value.runtimeProfile = true;
  return listWebRuntimeProfile({ isPage: false }).then((response) => {
    const rows = Array.isArray(response?.data) ? response.data : [];
    runtimeProfiles.value = rows.map((item) => normalizeRuntimeProfile(item));
    clearInvalidRuntimeProfileBindings();
  }).finally(() => {
    loading.value.runtimeProfile = false;
  });
}

function createBrowserSessionDraft() {
  browserSessionForm.value = createEmptyBrowserSession();
  browserSessionImportText.value = "";
}

function handleBrowserSessionRowChange(row) {
  if (!row) return;
  browserSessionForm.value = normalizeBrowserSession(row);
}

function loadBrowserSessions() {
  loading.value.browserSession = true;
  return listWebBrowserSession({ isPage: false }).then((response) => {
    const rows = Array.isArray(response?.data) ? response.data : [];
    browserSessions.value = rows.map((item) => normalizeBrowserSession(item));
    clearInvalidRuntimeProfileBindings();
  }).finally(() => {
    loading.value.browserSession = false;
  });
}

function openBrowserSessionDialog() {
  showBrowserSessionDialog.value = true;
  if (!browserSessions.value.length) {
    loadBrowserSessions();
  }
  if (!browserSessionForm.value.sessionId) {
    createBrowserSessionDraft();
  }
}

function openRuntimeProfileDialog() {
  showRuntimeProfileDialog.value = true;
  if (!runtimeProfiles.value.length) {
    loadRuntimeProfiles();
  }
  if (!runtimeProfileForm.value.profileId) {
    createRuntimeProfileDraft();
  }
}

function buildBrowserSessionPayload() {
  const sessionName = `${browserSessionForm.value.sessionName || ""}`.trim();
  if (!sessionName) {
    throw new Error("Session名称不能为空");
  }
  const scopeKey = `${browserSessionForm.value.scopeKey || ""}`.trim();
  if (!scopeKey) {
    throw new Error("作用域Key不能为空");
  }
  const storageState = parseOptionalJsonObject(browserSessionForm.value.storageStateText, "StorageState") || {};
  return {
    sessionId: browserSessionForm.value.sessionId || undefined,
    sessionName,
    scopeKey,
    enabled: browserSessionForm.value.enabled !== false,
    projectId: browserSessionForm.value.projectId || undefined,
    moduleId: browserSessionForm.value.moduleId || undefined,
    browserName: `${browserSessionForm.value.browserName || ""}`.trim().toLowerCase() || undefined,
    sort: Math.max(Math.round(Number(browserSessionForm.value.sort) || 0), 0),
    hostPatterns: normalizePersistScopeHostPatterns(browserSessionForm.value.hostPatternsText),
    storageState: normalizeStorageStatePayload(storageState),
    remark: browserSessionForm.value.remark || undefined,
  };
}

function saveBrowserSession() {
  let payload;
  try {
    payload = buildBrowserSessionPayload();
  } catch (error) {
    ElMessage.error(error.message);
    return;
  }
  loading.value.browserSessionSave = true;
  const request = payload.sessionId ? updateWebBrowserSession(payload) : addWebBrowserSession(payload);
  request.then((response) => {
    const saved = normalizeBrowserSession(response?.data || payload);
    ElMessage.success(response?.msg || "保存成功");
    return loadBrowserSessions().then(() => {
      const hit = browserSessions.value.find((item) => isSameId(item.sessionId, saved.sessionId));
      browserSessionForm.value = normalizeBrowserSession(hit || saved);
    });
  }).finally(() => {
    loading.value.browserSessionSave = false;
  });
}

function deleteBrowserSession() {
  const sessionId = browserSessionForm.value.sessionId;
  if (!sessionId) {
    ElMessage.warning("请先选择要删除的Session");
    return;
  }
  ElMessageBox.confirm(`确认删除Session【${browserSessionForm.value.sessionName || sessionId}】吗？`, "提示", { type: "warning" })
    .then(() => delWebBrowserSession(sessionId))
    .then(async () => {
      ElMessage.success("删除成功");
      createBrowserSessionDraft();
      await loadBrowserSessions();
    })
    .catch(() => {});
}

function extractCookieContentFromImport(rawText) {
  const raw = `${rawText ?? ""}`.trim();
  if (!raw) return "";
  if (raw.startsWith("{") && raw.endsWith("}")) {
    try {
      const parsed = JSON.parse(raw);
      if (isPlainObject(parsed)) {
        const cookieValue = parsed.Cookie || parsed.cookie;
        if (typeof cookieValue === "string" && cookieValue.trim()) {
          return cookieValue.trim();
        }
      }
    } catch (error) {
      // ignore
    }
  }
  const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  for (const line of lines) {
    const matched = line.match(/^cookie\s*:\s*(.+)$/i);
    if (matched && matched[1]) {
      return matched[1].trim();
    }
  }
  if (/^cookie\s*=/i.test(raw)) {
    return raw.replace(/^cookie\s*=/i, "").trim();
  }
  if (/^cookie\s*:/i.test(raw)) {
    return raw.replace(/^cookie\s*:/i, "").trim();
  }
  return raw;
}

function extractSetCookieLinesFromImport(rawText) {
  const raw = `${rawText ?? ""}`.trim();
  if (!raw) return [];
  const lines = [];
  if (raw.startsWith("{") && raw.endsWith("}")) {
    try {
      const parsed = JSON.parse(raw);
      if (isPlainObject(parsed)) {
        const setCookieValue = parsed["Set-Cookie"] || parsed["set-cookie"] || parsed.setCookie || parsed.set_cookie;
        if (Array.isArray(setCookieValue)) {
          setCookieValue.forEach((item) => {
            const text = `${item ?? ""}`.trim();
            if (text) lines.push(text);
          });
        } else if (typeof setCookieValue === "string" && setCookieValue.trim()) {
          lines.push(setCookieValue.trim());
        }
      }
    } catch (error) {
      // ignore
    }
  }
  if (lines.length) {
    return lines;
  }
  raw.split(/\r?\n/).forEach((line) => {
    const matched = `${line || ""}`.trim().match(/^set-cookie\s*:\s*(.+)$/i);
    if (matched && matched[1]) {
      lines.push(matched[1].trim());
    }
  });
  if (lines.length) {
    return lines;
  }
  if (/^set-cookie\s*[:=]/i.test(raw)) {
    const text = raw.replace(/^set-cookie\s*[:=]/i, "").trim();
    if (text) {
      return [text];
    }
  }
  return [];
}

function parseCookiePairs(cookieText) {
  const raw = `${cookieText ?? ""}`.trim();
  if (!raw) return [];
  const entries = raw
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean);
  const cookieMap = new Map();
  entries.forEach((entry) => {
    const index = entry.indexOf("=");
    if (index <= 0) return;
    const name = entry.slice(0, index).trim();
    const value = entry.slice(index + 1).trim();
    if (!name || !value) return;
    cookieMap.set(name, { name, value });
  });
  return Array.from(cookieMap.values());
}

function normalizeSameSiteValue(value) {
  const normalized = `${value || ""}`.trim().toLowerCase();
  if (normalized === "lax") return "Lax";
  if (normalized === "strict") return "Strict";
  if (normalized === "none") return "None";
  return undefined;
}

function parseExpiresTimestamp(rawValue) {
  const text = `${rawValue || ""}`.trim();
  if (!text) return undefined;
  const parsed = Date.parse(text);
  if (!Number.isFinite(parsed)) {
    return undefined;
  }
  return Math.floor(parsed / 1000);
}

function parseSetCookieLine(line) {
  const text = `${line || ""}`.trim();
  if (!text) return null;
  const parts = text.split(";").map((item) => item.trim()).filter(Boolean);
  if (!parts.length) return null;
  const first = parts[0];
  const eqIndex = first.indexOf("=");
  if (eqIndex <= 0) return null;
  const name = first.slice(0, eqIndex).trim();
  const value = first.slice(eqIndex + 1).trim();
  if (!name || !value) return null;
  const cookie = { name, value };
  parts.slice(1).forEach((part) => {
    const idx = part.indexOf("=");
    const rawKey = (idx >= 0 ? part.slice(0, idx) : part).trim().toLowerCase();
    const rawValue = idx >= 0 ? part.slice(idx + 1).trim() : "";
    if (!rawKey) return;
    if (rawKey === "domain" && rawValue) {
      cookie.domain = rawValue;
      return;
    }
    if (rawKey === "path" && rawValue) {
      cookie.path = rawValue;
      return;
    }
    if (rawKey === "secure") {
      cookie.secure = true;
      return;
    }
    if (rawKey === "httponly") {
      cookie.httpOnly = true;
      return;
    }
    if (rawKey === "samesite") {
      const sameSite = normalizeSameSiteValue(rawValue);
      if (sameSite) {
        cookie.sameSite = sameSite;
      }
      return;
    }
    if (rawKey === "expires") {
      const expires = parseExpiresTimestamp(rawValue);
      if (expires !== undefined) {
        cookie.expires = expires;
      }
      return;
    }
    if (rawKey === "max-age") {
      const age = Number(rawValue);
      if (Number.isFinite(age)) {
        cookie.expires = Math.floor(Date.now() / 1000) + Math.max(Math.round(age), 0);
      }
    }
  });
  return cookie;
}

function applyRuntimeProfileQuickImport() {
  const setCookieLines = extractSetCookieLinesFromImport(runtimeProfileImportText.value);
  const cookiesFromSetCookie = setCookieLines.map((line) => parseSetCookieLine(line)).filter(Boolean);
  const cookieText = extractCookieContentFromImport(runtimeProfileImportText.value);
  const cookiesFromCookieHeader = parseCookiePairs(cookieText);
  const useSetCookie = cookiesFromSetCookie.length > 0;
  const cookies = useSetCookie ? cookiesFromSetCookie : cookiesFromCookieHeader;
  if (!cookies.length) {
    ElMessage.error("未识别到可用 Cookie，请粘贴 Cookie 或 Set-Cookie 内容");
    return;
  }

  let currentRules = [];
  try {
    currentRules = parseOptionalJsonArray(runtimeProfileForm.value.cookieRulesText, "Cookie规则") || [];
  } catch (error) {
    ElMessage.error(error.message);
    return;
  }

  const matchHost = `${runtimeProfileImportHost.value || ""}`.trim();
  const ruleName = runtimeProfileForm.value.profileName?.trim() || `导入Cookie-${new Date().toISOString().slice(0, 19)}`;
  currentRules.push({
    name: ruleName,
    match: matchHost ? { host: matchHost } : {},
    applyOn: ["before_start", "before_step", "before_goto"],
    cookies,
  });
  runtimeProfileForm.value.cookieRulesText = safeJsonStringify(currentRules);
  ElMessage.success(`已导入 ${cookies.length} 个 Cookie${useSetCookie ? "（Set-Cookie）" : ""}`);
}

function applyBrowserSessionQuickImport() {
  const rawText = `${browserSessionImportText.value || ""}`.trim();
  if (!rawText) {
    ElMessage.warning("请先粘贴 Cookie/Set-Cookie/StorageState 内容");
    return;
  }
  try {
    const parsed = JSON.parse(rawText);
    if (isPlainObject(parsed) && (Array.isArray(parsed.cookies) || Array.isArray(parsed.origins))) {
      const normalized = normalizeStorageStatePayload(parsed);
      browserSessionForm.value.storageStateText = safeJsonStringify(normalized);
      ElMessage.success(`已导入 StorageState：cookies ${normalized.cookies.length} 条，origins ${normalized.origins.length} 条`);
      return;
    }
  } catch (error) {
    // ignore: 继续按Cookie文本解析
  }

  const setCookieLines = extractSetCookieLinesFromImport(rawText);
  const cookiesFromSetCookie = setCookieLines.map((line) => parseSetCookieLine(line)).filter(Boolean);
  const cookieText = extractCookieContentFromImport(rawText);
  const cookiesFromCookieHeader = parseCookiePairs(cookieText);
  const useSetCookie = cookiesFromSetCookie.length > 0;
  const cookies = useSetCookie ? cookiesFromSetCookie : cookiesFromCookieHeader;
  if (!cookies.length) {
    ElMessage.error("未识别到可用数据，请粘贴 Cookie/Set-Cookie 或 storage_state JSON");
    return;
  }
  browserSessionForm.value.storageStateText = safeJsonStringify({
    cookies,
    origins: [],
  });
  ElMessage.success(`已导入 ${cookies.length} 个 Cookie${useSetCookie ? "（Set-Cookie）" : ""}`);
}

function addPersistContextScopeRow() {
  if (!Array.isArray(runtimeProfileForm.value.persistContextScopes)) {
    runtimeProfileForm.value.persistContextScopes = [];
  }
  runtimeProfileForm.value.persistContextScopes.push({
    key: "",
    label: "",
    hostPatterns: [],
    hostPatternsText: "",
    enabled: true,
    remark: "",
  });
}

function removePersistContextScopeRow(index) {
  if (!Array.isArray(runtimeProfileForm.value.persistContextScopes)) return;
  runtimeProfileForm.value.persistContextScopes.splice(index, 1);
}

function buildPersistContextScopesPayload(scopes) {
  const source = Array.isArray(scopes) ? scopes : [];
  const result = [];
  const seen = new Set();
  source.forEach((item) => {
    const scope = normalizePersistContextScope({
      ...item,
      hostPatterns: normalizePersistScopeHostPatterns(item?.hostPatternsText || item?.hostPatterns),
    });
    if (!scope) return;
    const keyLower = `${scope.key}`.toLowerCase();
    if (seen.has(keyLower)) return;
    seen.add(keyLower);
    result.push({
      key: scope.key,
      label: scope.label || scope.key,
      hostPatterns: normalizePersistScopeHostPatterns(scope.hostPatterns),
      enabled: scope.enabled !== false,
      remark: scope.remark || undefined,
    });
  });
  return result;
}

function buildRuntimeProfilePayload() {
  const profileName = `${runtimeProfileForm.value.profileName || ""}`.trim();
  if (!profileName) {
    throw new Error("配置名称不能为空");
  }
  const runtimeOverrides = parseOptionalJsonObject(runtimeProfileForm.value.runtimeOverridesText, "运行覆盖") || {};
  const variables = parseOptionalJsonObject(runtimeProfileForm.value.variablesText, "变量") || {};
  const cookieRules = parseOptionalJsonArray(runtimeProfileForm.value.cookieRulesText, "Cookie规则") || [];
  const persistContextScopes = buildPersistContextScopesPayload(runtimeProfileForm.value.persistContextScopes);
  const targets = normalizeRuntimeTargets(runtimeProfileForm.value.targets);
  return {
    profileId: runtimeProfileForm.value.profileId || undefined,
    profileName,
    profileType: "runtime",
    targets,
    enabled: runtimeProfileForm.value.enabled !== false,
    projectId: runtimeProfileForm.value.projectId || undefined,
    moduleId: runtimeProfileForm.value.moduleId || undefined,
    sort: Math.max(Math.round(Number(runtimeProfileForm.value.sort) || 0), 0),
    runtimeOverrides,
    variables,
    cookieRules,
    persistContextScopes,
    remark: runtimeProfileForm.value.remark || undefined,
  };
}

function saveRuntimeProfile() {
  let payload;
  try {
    payload = buildRuntimeProfilePayload();
  } catch (error) {
    ElMessage.error(error.message);
    return;
  }
  loading.value.runtimeProfileSave = true;
  const request = payload.profileId ? updateWebRuntimeProfile(payload) : addWebRuntimeProfile(payload);
  request.then((response) => {
    const saved = normalizeRuntimeProfile(response?.data || payload);
    ElMessage.success(response?.msg || "保存成功");
    return loadRuntimeProfiles().then(() => {
      const hit = runtimeProfiles.value.find((item) => isSameId(item.profileId, saved.profileId));
      runtimeProfileForm.value = normalizeRuntimeProfile(hit || saved);
    });
  }).finally(() => {
    loading.value.runtimeProfileSave = false;
  });
}

function deleteRuntimeProfile() {
  const profileId = runtimeProfileForm.value.profileId;
  if (!profileId) {
    ElMessage.warning("请先选择要删除的配置");
    return;
  }
  ElMessageBox.confirm(`确认删除配置【${runtimeProfileForm.value.profileName || profileId}】吗？`, "提示", { type: "warning" })
    .then(() => delWebRuntimeProfile(profileId))
    .then(async () => {
      ElMessage.success("删除成功");
      createRuntimeProfileDraft();
      await loadRuntimeProfiles();
    })
    .catch(() => {});
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

function handleCaseSelectionChange(selection) {
  selectedCaseRows.value = Array.isArray(selection) ? selection.map((item) => normalizeCaseOption(item) || item) : [];
}

function handleRunSelectionChange(selection) {
  selectedRunRows.value = Array.isArray(selection) ? selection : [];
}

function handleRecordingSelectionChange(selection) {
  selectedRecordingRows.value = Array.isArray(selection) ? selection : [];
}

function initRunFormByCase(row) {
  const runtimeSettings = isPlainObject(row?.runtimeSettings || row?.runtime_settings) ? cloneData(row.runtimeSettings || row.runtime_settings) : {};
  const browserSessionId = normalizeIdValue(
    runtimeSettings.browserSessionId
      ?? runtimeSettings.browser_session_id
      ?? runtimeSettings.persistContextSessionId
      ?? runtimeSettings.persist_context_session_id
      ?? runtimeSettings.sessionProfileId
      ?? runtimeSettings.session_profile_id
  );
  const stepTimeoutCandidate = Number(
    runtimeSettings.stepTimeoutMs
      ?? runtimeSettings.step_timeout_ms
      ?? runtimeSettings.timeoutMs
      ?? runtimeSettings.timeout_ms
  );
  const stepThinkCandidate = Number(
    runtimeSettings.stepThinkTimeMs
      ?? runtimeSettings.step_think_time_ms
      ?? runtimeSettings.thinkTimeMs
      ?? runtimeSettings.think_time_ms
  );
  const manualLoginEnabled = parseBooleanFlag(
    runtimeSettings.manualLoginEnabled
      ?? runtimeSettings.manual_login_enabled
      ?? runtimeSettings.manualLoginGate
      ?? runtimeSettings.manual_login_gate,
    false
  );
  const manualLoginRequireConfirm = parseBooleanFlag(
    runtimeSettings.manualLoginRequireConfirm
      ?? runtimeSettings.manual_login_require_confirm
      ?? runtimeSettings.manualLoginNeedConfirm
      ?? runtimeSettings.manual_login_need_confirm,
    false
  );
  const manualLoginWaitSec = normalizeManualLoginWaitSec(
    runtimeSettings.manualLoginWaitSec
      ?? runtimeSettings.manual_login_wait_sec
      ?? runtimeSettings.manualLoginTimeoutSec
      ?? runtimeSettings.manual_login_timeout_sec,
    120
  );
  const closeBrowserOnFinish = parseBooleanFlag(
    runtimeSettings.closeBrowserOnFinish ?? runtimeSettings.close_browser_on_finish,
    true
  );
  const persistContextEnabled = parseBooleanFlag(
    runtimeSettings.persistContextEnabled
      ?? runtimeSettings.persist_context_enabled
      ?? runtimeSettings.preserveBrowserContext
      ?? runtimeSettings.preserve_browser_context
      ?? runtimeSettings.keepBrowserCache
      ?? runtimeSettings.keep_browser_cache,
    false
  );
  const persistContextAutoSyncSession = parseBooleanFlag(
    runtimeSettings.persistContextAutoSyncSession
      ?? runtimeSettings.persist_context_auto_sync_session
      ?? runtimeSettings.persistContextSyncToSession
      ?? runtimeSettings.persist_context_sync_to_session,
    true
  );
  const persistContextKey = `${runtimeSettings.persistContextKey
    ?? runtimeSettings.persist_context_key
    ?? runtimeSettings.preserveContextKey
    ?? runtimeSettings.preserve_context_key
    ?? ""}`.trim();
  runForm.value = {
    agentId: undefined,
    browserName: row?.browserName || "chromium",
    headless: row?.headless ?? true,
    closeBrowserOnFinish,
    browserSessionId,
    persistContextEnabled: Boolean(persistContextEnabled || browserSessionId),
    persistContextAutoSyncSession,
    persistContextKey,
    manualLoginEnabled,
    manualLoginRequireConfirm: manualLoginEnabled ? manualLoginRequireConfirm : false,
    manualLoginWaitSec,
    stepTimeoutMs: Number.isFinite(stepTimeoutCandidate) && stepTimeoutCandidate >= 500 ? Math.round(stepTimeoutCandidate) : undefined,
    stepThinkTimeMs: Number.isFinite(stepThinkCandidate) && stepThinkCandidate >= 0 ? Math.round(stepThinkCandidate) : undefined,
  };
}

function openRunDialog(row) {
  const normalized = normalizeCaseOption(row) || row;
  selectedCase.value = normalized;
  runTargetCases.value = normalized?.webCaseId ? [normalized] : [];
  initRunFormByCase(normalized);
  showRunDialog.value = true;
}

function openBatchRunDialog() {
  const candidates = (Array.isArray(selectedCaseRows.value) ? selectedCaseRows.value : [])
    .map((item) => normalizeCaseOption(item) || item)
    .filter((item) => item?.webCaseId);
  if (!candidates.length) {
    ElMessage.warning("请先勾选至少一条用例");
    return;
  }
  const uniqueTargets = Array.from(new Map(candidates.map((item) => [item.webCaseId, item])).values());
  selectedCase.value = uniqueTargets[0];
  runTargetCases.value = uniqueTargets;
  initRunFormByCase(uniqueTargets[0]);
  showRunDialog.value = true;
}

function openRunHistory(row) {
  activeTab.value = "run";
  runQueryParams.value.webCaseId = row.webCaseId;
  runQueryParams.value.pageNum = 1;
  getRunList();
}

function stopRunDetailPoll() {
  if (runDetailTimer) {
    window.clearInterval(runDetailTimer);
    runDetailTimer = null;
  }
}

function refreshRunDetail() {
  const runId = normalizeIdValue(runDetail.value?.webCaseRunId);
  if (!runId || !showRunDetailDialog.value) {
    return Promise.resolve(null);
  }
  return getWebRun(runId).then((response) => {
    runDetail.value = response.data || null;
    syncCaseOptions(runDetail.value);
    if (shouldStopRunDetailPoll(runDetail.value?.status)) {
      stopRunDetailPoll();
    }
    return runDetail.value;
  });
}

function startRunDetailPoll() {
  stopRunDetailPoll();
  if (!runDetail.value?.webCaseRunId || shouldStopRunDetailPoll(runDetail.value?.status)) {
    return;
  }
  runDetailTimer = window.setInterval(() => {
    refreshRunDetail();
  }, 3000);
}

function openRunDetail(row) {
  const runId = normalizeIdValue(row?.webCaseRunId);
  if (!runId) return;
  stopRunDetailPoll();
  loading.value.runDetail = true;
  getWebRun(runId).then((response) => {
    runDetail.value = response.data || null;
    syncCaseOptions(runDetail.value);
    showRunDetailDialog.value = true;
    startRunDetailPoll();
  }).finally(() => {
    loading.value.runDetail = false;
  });
}

async function submitRun() {
  const runTargets = Array.isArray(runTargetCases.value) && runTargetCases.value.length
    ? runTargetCases.value.filter((item) => item?.webCaseId)
    : (selectedCase.value?.webCaseId ? [selectedCase.value] : []);
  if (!runTargets.length) {
    ElMessage.error("请选择要执行的用例");
    return;
  }
  if (!runForm.value.agentId) {
    ElMessage.error("请选择执行 Agent");
    return;
  }

  const runtimeOverrides = {};
  if (runForm.value.stepTimeoutMs !== undefined && runForm.value.stepTimeoutMs !== null && runForm.value.stepTimeoutMs !== "") {
    const stepTimeoutMs = Math.round(Number(runForm.value.stepTimeoutMs));
    if (!Number.isFinite(stepTimeoutMs) || stepTimeoutMs < 500) {
      ElMessage.error("单步超时覆盖必须大于等于 500ms");
      return;
    }
    runtimeOverrides.stepTimeoutMs = stepTimeoutMs;
  }
  if (runForm.value.stepThinkTimeMs !== undefined && runForm.value.stepThinkTimeMs !== null && runForm.value.stepThinkTimeMs !== "") {
    const stepThinkTimeMs = Math.round(Number(runForm.value.stepThinkTimeMs));
    if (!Number.isFinite(stepThinkTimeMs) || stepThinkTimeMs < 0) {
      ElMessage.error("步骤思考时间必须大于等于 0ms");
      return;
    }
    runtimeOverrides.stepThinkTimeMs = stepThinkTimeMs;
  }
  const manualLoginEnabled = Boolean(runForm.value.manualLoginEnabled);
  const manualLoginRequireConfirm = manualLoginEnabled && Boolean(runForm.value.manualLoginRequireConfirm);
  const manualLoginWaitSec = normalizeManualLoginWaitSec(runForm.value.manualLoginWaitSec, 120);

  loading.value.run = true;
  try {
    if (manualLoginEnabled && !manualLoginRequireConfirm) {
      ElMessage.info(`浏览器启动后将预留 ${manualLoginWaitSec} 秒手动登录时间，再开始正式执行`);
    }
    if (manualLoginRequireConfirm) {
      ElMessage.info("已开启“登录后确认继续”：仅首条执行会暂停等待你确认，后续用例直接执行");
    }
    let successCount = 0;
    let failedCount = 0;
    let reuseRetainedSessionId = "";
    const runResponses = [];
    for (let index = 0; index < runTargets.length; index++) {
      const target = runTargets[index];
      const enableManualForCurrent = manualLoginEnabled && (!manualLoginRequireConfirm || index === 0);
      const requireConfirmForCurrent = manualLoginRequireConfirm && index === 0;
      const runtimeOverridesForCurrent = { ...runtimeOverrides };
      if (!runForm.value.closeBrowserOnFinish && reuseRetainedSessionId) {
        runtimeOverridesForCurrent.reuseRetainedSessionId = reuseRetainedSessionId;
      }
      const payload = {
        webCaseId: target.webCaseId,
        agentId: runForm.value.agentId,
        browserName: runForm.value.browserName,
        headless: runForm.value.headless,
        closeBrowserOnFinish: runForm.value.closeBrowserOnFinish,
        browserSessionId: runForm.value.browserSessionId || undefined,
        persistContextEnabled: Boolean(runForm.value.persistContextEnabled || runForm.value.browserSessionId),
        persistContextAutoSyncSession: Boolean(
          (runForm.value.persistContextEnabled || runForm.value.browserSessionId)
          && runForm.value.persistContextAutoSyncSession
        ),
        persistContextKey: runForm.value.persistContextKey?.trim() || undefined,
        manualLoginEnabled: enableManualForCurrent,
        manualLoginRequireConfirm: requireConfirmForCurrent,
        manualLoginWaitSec,
      };
      if (Object.keys(runtimeOverridesForCurrent).length) {
        payload.runtimeOverrides = runtimeOverridesForCurrent;
      }
      try {
        let response = await runWebCase(payload);
        if (requireConfirmForCurrent) {
          const runId = response?.data?.webCaseRunId;
          if (!runId) {
            throw new Error("执行准备成功但未返回执行记录ID，无法继续");
          }
          response = await confirmAndContinueRunManualLogin({
            runId,
            agentId: runForm.value.agentId,
            caseName: target.caseName || `${target.webCaseId}`,
          });
        }
        const retainedSessionId = `${response?.data?.result?.retainedSessionId || ""}`.trim();
        reuseRetainedSessionId = (!runForm.value.closeBrowserOnFinish && retainedSessionId) ? retainedSessionId : "";
        successCount += 1;
        runResponses.push({ target, response });
      } catch (error) {
        reuseRetainedSessionId = "";
        failedCount += 1;
        runResponses.push({ target, error });
        if (requireConfirmForCurrent) {
          break;
        }
      }
    }
    showRunDialog.value = false;
    activeTab.value = "run";
    runQueryParams.value.webCaseId = runTargets.length === 1 ? runTargets[0].webCaseId : undefined;
    getRunList();
    if (runTargets.length === 1) {
      const first = runResponses[0];
      if (first?.response) {
        ElMessage.success(first.response.msg || "执行完成");
        if (first.response.data?.webCaseRunId) {
          openRunDetail(first.response.data);
        }
      } else {
        const msg = first?.error?.response?.data?.msg || first?.error?.message || "执行失败";
        ElMessage.error(msg);
      }
      return;
    }
    if (failedCount === 0) {
      ElMessage.success(`批量执行完成：成功 ${successCount} 条`);
    } else if (successCount === 0) {
      ElMessage.error(`批量执行完成：失败 ${failedCount} 条`);
    } else {
      ElMessage.warning(`批量执行完成：成功 ${successCount} 条，失败 ${failedCount} 条`);
    }
  } catch (error) {
    const msg = error?.response?.data?.msg || error?.message || "执行失败";
    ElMessage.error(msg);
  } finally {
    loading.value.run = false;
  }
}

function resetRecordingDialogState(row = null) {
  stopRecordingPoll();
  selectedCase.value = row || null;
  recordingEvents.value = [];
  liveRecordingSteps.value = [];
  recordingDetail.value = null;
  recordingDetailText.value = "";
  const runtimeSettings = isPlainObject(row?.runtimeSettings || row?.runtime_settings) ? cloneData(row.runtimeSettings || row.runtime_settings) : {};
  const browserSessionId = normalizeIdValue(
    runtimeSettings.browserSessionId
      ?? runtimeSettings.browser_session_id
      ?? runtimeSettings.persistContextSessionId
      ?? runtimeSettings.persist_context_session_id
      ?? runtimeSettings.sessionProfileId
      ?? runtimeSettings.session_profile_id
  );
  const manualLoginEnabled = parseBooleanFlag(
    runtimeSettings.manualLoginEnabled
      ?? runtimeSettings.manual_login_enabled
      ?? runtimeSettings.manualLoginGate
      ?? runtimeSettings.manual_login_gate,
    false
  );
  const manualLoginRequireConfirm = parseBooleanFlag(
    runtimeSettings.manualLoginRequireConfirm
      ?? runtimeSettings.manual_login_require_confirm
      ?? runtimeSettings.manualLoginNeedConfirm
      ?? runtimeSettings.manual_login_need_confirm,
    false
  );
  const manualLoginWaitSec = normalizeManualLoginWaitSec(
    runtimeSettings.manualLoginWaitSec
      ?? runtimeSettings.manual_login_wait_sec
      ?? runtimeSettings.manualLoginTimeoutSec
      ?? runtimeSettings.manual_login_timeout_sec,
    120
  );
  const persistContextEnabled = parseBooleanFlag(
    runtimeSettings.persistContextEnabled
      ?? runtimeSettings.persist_context_enabled
      ?? runtimeSettings.preserveBrowserContext
      ?? runtimeSettings.preserve_browser_context
      ?? runtimeSettings.keepBrowserCache
      ?? runtimeSettings.keep_browser_cache,
    false
  );
  const persistContextAutoSyncSession = parseBooleanFlag(
    runtimeSettings.persistContextAutoSyncSession
      ?? runtimeSettings.persist_context_auto_sync_session
      ?? runtimeSettings.persistContextSyncToSession
      ?? runtimeSettings.persist_context_sync_to_session,
    true
  );
  const persistContextKey = `${runtimeSettings.persistContextKey
    ?? runtimeSettings.persist_context_key
    ?? runtimeSettings.preserveContextKey
    ?? runtimeSettings.preserve_context_key
    ?? ""}`.trim();
  recordingForm.value = {
    webCaseId: row?.webCaseId,
    sessionName: row ? `${row.caseName}-录制` : "",
    agentId: undefined,
    browserName: row?.browserName || "chromium",
    headless: false,
    startUrl: row?.startUrl || "",
    browserSessionId,
    persistContextEnabled: Boolean(persistContextEnabled || browserSessionId),
    persistContextAutoSyncSession,
    persistContextKey,
    manualLoginEnabled,
    manualLoginRequireConfirm: manualLoginEnabled ? manualLoginRequireConfirm : false,
    manualLoginWaitSec,
    closeBrowserOnStop: true,
    captureAssertions: true,
    attachAssertionsToPreviousStep: true,
    autoAssertTextOnClick: false,
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
  if (shouldStopRecordingPoll(detail)) {
    stopRecordingPoll();
  }
}

function fetchRecordingDetail(recordingId) {
  return getWebRecording(recordingId).then((response) => response.data || {});
}

async function startRecording() {
  if (!recordingForm.value.agentId) {
    ElMessage.error("请选择执行 Agent");
    return;
  }
  if (!recordingForm.value.startUrl?.trim()) {
    ElMessage.error("请填写录制起始地址");
    return;
  }

  const manualLoginEnabled = Boolean(recordingForm.value.manualLoginEnabled);
  const manualLoginRequireConfirm = manualLoginEnabled && Boolean(recordingForm.value.manualLoginRequireConfirm);
  const manualLoginWaitSec = normalizeManualLoginWaitSec(recordingForm.value.manualLoginWaitSec, 120);

  loading.value.recording = true;
  if (manualLoginEnabled && !manualLoginRequireConfirm) {
    ElMessage.info(`浏览器启动后将预留 ${manualLoginWaitSec} 秒手动登录时间，再开始录制`);
  }
  try {
    const response = await startWebRecording({
      webCaseId: recordingForm.value.webCaseId,
      agentId: recordingForm.value.agentId,
      sessionName: recordingForm.value.sessionName || undefined,
      browserName: recordingForm.value.browserName,
      headless: recordingForm.value.headless,
      startUrl: recordingForm.value.startUrl,
      browserSessionId: recordingForm.value.browserSessionId || undefined,
      persistContextEnabled: Boolean(recordingForm.value.persistContextEnabled || recordingForm.value.browserSessionId),
      persistContextAutoSyncSession: Boolean(
        (recordingForm.value.persistContextEnabled || recordingForm.value.browserSessionId)
        && recordingForm.value.persistContextAutoSyncSession
      ),
      persistContextKey: recordingForm.value.persistContextKey?.trim() || undefined,
      manualLoginEnabled,
      manualLoginRequireConfirm,
      manualLoginWaitSec,
      recordingOptions: {
        closeBrowserOnStop: recordingForm.value.closeBrowserOnStop,
        captureAssertions: recordingForm.value.captureAssertions,
        assertionAttachMode: recordingForm.value.captureAssertions
          ? (recordingForm.value.attachAssertionsToPreviousStep ? "inside_step" : "parallel_step")
          : "parallel_step",
        autoAssertTextOnClick: recordingForm.value.captureAssertions && recordingForm.value.autoAssertTextOnClick,
      },
    });
    recordingForm.value.recordingId = response.data?.recordingId;
    ElMessage.success(response.msg || "录制已启动");
    refreshRecording();
    startRecordingPoll();
    getRecordingList();
    if (manualLoginRequireConfirm && recordingForm.value.recordingId) {
      await confirmAndContinueRecordingManualLogin({
        recordingId: recordingForm.value.recordingId,
        agentId: recordingForm.value.agentId,
        sessionName: recordingForm.value.sessionName,
      });
      ElMessage.success("已确认继续录制");
      refreshRecording();
      getRecordingList();
    }
  } catch (error) {
    const msg = error?.response?.data?.msg || error?.message || "录制启动失败";
    ElMessage.error(msg);
  } finally {
    loading.value.recording = false;
  }
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

function stopRecordingDetailPoll() {
  if (recordingDetailTimer) {
    window.clearInterval(recordingDetailTimer);
    recordingDetailTimer = null;
  }
}

function refreshRecordingDetail() {
  const recordingId = normalizeIdValue(recordingDetail.value?.recordingId);
  if (!recordingId || !showRecordingDetailDialog.value) {
    return Promise.resolve(null);
  }
  return fetchRecordingDetail(recordingId).then((detail) => {
    recordingDetail.value = detail;
    syncCaseOptions(detail);
    selectedRecording.value = detail;
    if (shouldStopRecordingPoll(detail)) {
      stopRecordingDetailPoll();
    }
    return detail;
  });
}

function startRecordingDetailPoll() {
  stopRecordingDetailPoll();
  if (!recordingDetail.value?.recordingId || shouldStopRecordingPoll(recordingDetail.value)) {
    return;
  }
  recordingDetailTimer = window.setInterval(() => {
    refreshRecordingDetail();
  }, 3000);
}

function openRecordingDetail(recordingSource) {
  const recordingId = typeof recordingSource === "number" ? recordingSource : recordingSource?.recordingId;
  if (!recordingId) return;
  stopRecordingDetailPoll();
  loading.value.recordingDetail = true;
  fetchRecordingDetail(recordingId).then((detail) => {
    recordingDetail.value = detail;
    syncCaseOptions(detail);
    selectedRecording.value = detail;
    showRecordingDetailDialog.value = true;
    startRecordingDetailPoll();
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

watch(() => runtimeProfileForm.value.projectId, (projectId) => {
  if (!projectId) {
    runtimeProfileForm.value.moduleId = undefined;
    return;
  }
  if (!filteredRuntimeProfileModules.value.some((item) => isSameId(item.moduleId, runtimeProfileForm.value.moduleId))) {
    runtimeProfileForm.value.moduleId = undefined;
  }
});

watch(() => browserSessionForm.value.projectId, (projectId) => {
  if (!projectId) {
    browserSessionForm.value.moduleId = undefined;
    return;
  }
  if (!filteredBrowserSessionModules.value.some((item) => isSameId(item.moduleId, browserSessionForm.value.moduleId))) {
    browserSessionForm.value.moduleId = undefined;
  }
});

watch(() => runForm.value.browserSessionId, (sessionId) => {
  const normalizedSessionId = normalizeIdValue(sessionId);
  if (!normalizedSessionId) return;
  const selectedSession = browserSessions.value.find((item) => isSameId(item.sessionId, normalizedSessionId));
  runForm.value.persistContextEnabled = true;
  runForm.value.persistContextAutoSyncSession = true;
  if (selectedSession?.scopeKey) {
    runForm.value.persistContextKey = selectedSession.scopeKey;
  }
});

watch(() => recordingForm.value.browserSessionId, (sessionId) => {
  const normalizedSessionId = normalizeIdValue(sessionId);
  if (!normalizedSessionId) return;
  const selectedSession = browserSessions.value.find((item) => isSameId(item.sessionId, normalizedSessionId));
  recordingForm.value.persistContextEnabled = true;
  recordingForm.value.persistContextAutoSyncSession = true;
  if (selectedSession?.scopeKey) {
    recordingForm.value.persistContextKey = selectedSession.scopeKey;
  }
});

watch(
  () => [runForm.value.persistContextEnabled, availablePersistScopesForRun.value.length],
  () => {
    if (!runForm.value.persistContextEnabled) return;
    const key = `${runForm.value.persistContextKey || ""}`.trim();
    if (!key && availablePersistScopesForRun.value.length) {
      runForm.value.persistContextKey = availablePersistScopesForRun.value[0].key;
      return;
    }
    if (key && !hasPersistScopeOption(availablePersistScopesForRun.value, key)) {
      runForm.value.persistContextKey = "";
    }
  }
);

watch(
  () => [recordingForm.value.persistContextEnabled, availablePersistScopesForRecording.value.length],
  () => {
    if (!recordingForm.value.persistContextEnabled) return;
    const key = `${recordingForm.value.persistContextKey || ""}`.trim();
    if (!key && availablePersistScopesForRecording.value.length) {
      recordingForm.value.persistContextKey = availablePersistScopesForRecording.value[0].key;
      return;
    }
    if (key && !hasPersistScopeOption(availablePersistScopesForRecording.value, key)) {
      recordingForm.value.persistContextKey = "";
    }
  }
);

onMounted(async () => {
  await loadBaseData();
  await loadRuntimeProfiles().catch(() => {});
  await loadBrowserSessions().catch(() => {});
  createRuntimeProfileDraft();
  resetForm();
  getList();
});

onBeforeUnmount(() => {
  stopRecordingPoll();
  stopRunDetailPoll();
  stopRecordingDetailPoll();
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
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.locator-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.locator-tip {
  margin-bottom: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.assertion-remove {
  display: flex;
  align-items: center;
}

.assertion-edit-table :deep(.el-table__expanded-cell) {
  background: var(--el-fill-color-blank);
}

.mt8 {
  margin-top: 8px;
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

.runtime-profile-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
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
