<template>
  <div class="app-container desktopcase-page">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="用例管理" name="case">
        <el-form :inline="true" :model="queryParams" class="mb8">
          <el-form-item label="用例名称">
            <el-input v-model="queryParams.caseName" placeholder="请输入桌面用例名称" clearable @keyup.enter="getList" />
          </el-form-item>
          <el-form-item label="项目">
            <el-select v-model="queryParams.projectId" clearable filterable placeholder="全部项目" style="width: 180px">
              <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
            </el-select>
          </el-form-item>
          <el-form-item label="模块">
            <el-select v-model="queryParams.moduleId" clearable filterable placeholder="全部模块" style="width: 180px">
              <el-option v-for="item in filteredModules" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" icon="Search" @click="getList">搜索</el-button>
            <el-button icon="Refresh" @click="resetQuery">重置</el-button>
          </el-form-item>
        </el-form>

        <el-row :gutter="10" class="mb8">
          <el-col :span="1.5">
            <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['hrm:desktopCase:add']">新增</el-button>
          </el-col>
          <el-col :span="1.5">
            <el-button type="warning" plain icon="VideoPlay" @click="openRecordingDialog()" v-hasPermi="['hrm:desktopCase:record']">独立录制</el-button>
          </el-col>
          <el-col :span="1.5">
            <el-button type="info" plain icon="Picture" @click="openStorageConfigDialog" v-hasPermi="['hrm:desktopCase:edit']">截图存储</el-button>
          </el-col>
          <el-col :span="1.5">
            <el-button type="default" plain icon="Refresh" @click="getList">刷新</el-button>
          </el-col>
        </el-row>

        <el-table v-loading="loading.page" :data="pageDataList" border table-layout="fixed" max-height="calc(100vh - 340px)">
          <el-table-column label="桌面用例ID" prop="desktopCaseId" width="180" />
          <el-table-column label="用例名称" prop="caseName" min-width="200" />
          <el-table-column label="项目" min-width="140">
            <template #default="scope">{{ getProjectName(scope.row.projectId) || scope.row.projectId || "-" }}</template>
          </el-table-column>
          <el-table-column label="模块" min-width="140">
            <template #default="scope">{{ getModuleName(scope.row.moduleId) || scope.row.moduleId || "-" }}</template>
          </el-table-column>
          <el-table-column label="应用路径" prop="appPath" min-width="220" show-overflow-tooltip />
          <el-table-column label="步骤数" width="90">
            <template #default="scope">{{ (scope.row.steps || []).length || scope.row.stepCount || 0 }}</template>
          </el-table-column>
          <el-table-column label="更新时间" min-width="170">
            <template #default="scope">{{ formatTime(scope.row.updateTime || scope.row.createTime) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="370" fixed="right">
            <template #default="scope">
              <el-button link type="primary" icon="Edit" @click="handleEdit(scope.row)" v-hasPermi="['hrm:desktopCase:edit']">编辑</el-button>
              <el-button link type="success" icon="CaretRight" @click="openRunDialog(scope.row)" v-hasPermi="['hrm:desktopCase:run']">执行</el-button>
              <el-button link type="warning" icon="VideoPlay" @click="openRecordingDialog(scope.row)" v-hasPermi="['hrm:desktopCase:record']">录制</el-button>
              <el-button link type="info" icon="Histogram" @click="openRunHistory(scope.row)" v-hasPermi="['hrm:desktopCase:history']">记录</el-button>
              <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['hrm:desktopCase:remove']">删除</el-button>
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
            <el-select v-model="runQueryParams.desktopCaseId" clearable filterable placeholder="全部用例" style="width: 260px">
              <el-option v-for="item in caseOptions" :key="item.desktopCaseId" :label="item.caseName" :value="item.desktopCaseId" />
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
          <el-table-column label="执行记录ID" prop="desktopCaseRunId" width="180" />
          <el-table-column label="用例名称" min-width="220">
            <template #default="scope">{{ getCaseName(scope.row.desktopCaseId) || scope.row.desktopCaseId || "-" }}</template>
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
            <el-select v-model="recordingQueryParams.desktopCaseId" clearable filterable placeholder="全部用例" style="width: 260px">
              <el-option v-for="item in caseOptions" :key="item.desktopCaseId" :label="item.caseName" :value="item.desktopCaseId" />
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
            <el-button type="warning" plain icon="VideoPlay" @click="openRecordingDialog()" v-hasPermi="['hrm:desktopCase:record']">新建录制</el-button>
          </el-col>
          <el-col :span="1.5">
            <el-button type="default" plain icon="Refresh" @click="getRecordingList">刷新</el-button>
          </el-col>
        </el-row>

        <el-table v-loading="loading.recordingPage" :data="recordingList" border table-layout="fixed" max-height="calc(100vh - 360px)">
          <el-table-column label="录制ID" prop="recordingId" width="180" />
          <el-table-column label="录制名称" prop="sessionName" min-width="220" />
          <el-table-column label="所属用例" min-width="220">
            <template #default="scope">{{ getCaseName(scope.row.desktopCaseId) || scope.row.desktopCaseId || "独立录制" }}</template>
          </el-table-column>
          <el-table-column label="Agent" prop="agentCode" min-width="160" show-overflow-tooltip />
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
              <el-button link type="success" icon="VideoPlay" :disabled="!canUseRecordingResult(scope.row.status)" @click="openReplayDialog(scope.row)" v-hasPermi="['hrm:desktopCase:run']">回放</el-button>
              <el-button link type="warning" icon="Plus" :disabled="!canUseRecordingResult(scope.row.status)" @click="openRecordingActionDialog('create', scope.row)" v-hasPermi="['hrm:desktopCase:add']">保存新用例</el-button>
              <el-button link type="info" icon="DocumentAdd" :disabled="!canUseRecordingResult(scope.row.status)" @click="openRecordingActionDialog('append', scope.row)" v-hasPermi="['hrm:desktopCase:edit']">追加</el-button>
              <el-button link type="danger" icon="EditPen" :disabled="!canUseRecordingResult(scope.row.status)" @click="openRecordingActionDialog('replace', scope.row)" v-hasPermi="['hrm:desktopCase:edit']">覆盖</el-button>
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

    <el-dialog v-model="showCaseDialog" :title="form.desktopCaseId ? '编辑桌面用例' : '新增桌面用例'" width="1320px" destroy-on-close>
      <el-form :model="form" label-width="100px" class="mb16">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="用例名称">
              <el-input v-model="form.caseName" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="项目">
              <el-select v-model="form.projectId" clearable filterable style="width: 100%">
                <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="模块">
              <el-select v-model="form.moduleId" clearable filterable style="width: 100%">
                <el-option v-for="item in formModules" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="应用路径">
              <el-input v-model="form.appPath" placeholder="例如 C:\\Program Files\\Demo\\demo.exe" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="状态">
              <el-radio-group v-model="form.status">
                <el-radio :value="2">启用</el-radio>
                <el-radio :value="1">停用</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启动参数">
              <el-input v-model="form.appArgsText" type="textarea" :rows="3" placeholder="每行一个参数" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="说明">
              <el-input v-model="form.notes" type="textarea" :rows="3" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-divider content-position="left">逻辑视口</el-divider>
          </el-col>
          <el-col :span="8">
            <el-form-item label="视口模式">
              <el-select v-model="form.viewportMode" style="width: 100%">
                <el-option v-for="item in viewportModeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="逻辑宽度">
              <el-input-number v-model="form.logicalWidth" :min="1" controls-position="right" style="width: 100%" placeholder="默认跟随实际截图宽度" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="逻辑高度">
              <el-input-number v-model="form.logicalHeight" :min="1" controls-position="right" style="width: 100%" placeholder="默认跟随实际截图高度" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.viewportMode !== 'screen'" :span="8">
            <el-form-item label="区域宽度">
              <el-input-number v-model="form.viewportWidth" :min="1" controls-position="right" style="width: 100%" placeholder="活动窗口模式下可用于自动调整窗口尺寸" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.viewportMode !== 'screen'" :span="8">
            <el-form-item label="区域高度">
              <el-input-number v-model="form.viewportHeight" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.viewportMode === 'manual_region'" :span="8">
            <el-form-item label="区域起点 X">
              <el-input-number v-model="form.viewportX" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.viewportMode === 'manual_region'" :span="8">
            <el-form-item label="区域起点 Y">
              <el-input-number v-model="form.viewportY" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="form.viewportMode === 'active_window'" :span="8">
            <el-form-item label="自动调整窗口">
              <el-switch v-model="form.resizeActiveWindow" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <div class="form-tip">
              录制和执行时，坐标、模板匹配、截图、视觉比对都会基于这个逻辑视口；活动窗口模式会尽量只看当前应用窗口，手工区域模式则只看指定区域。
            </div>
          </el-col>
        </el-row>
      </el-form>

      <div class="case-steps-toolbar">
        <div class="case-steps-title">步骤列表</div>
        <div class="case-steps-actions">
          <el-button size="small" type="primary" plain icon="Plus" @click="addStep()">新增步骤</el-button>
          <el-button size="small" plain @click="toggleCaseEditorMode">{{ caseEditorMode === 'visual' ? '切换高级 JSON' : '切换可视化' }}</el-button>
          <el-button v-if="caseEditorMode === 'json'" size="small" type="success" plain @click="applyStepsJsonText">应用 JSON</el-button>
        </div>
      </div>

      <div v-if="caseEditorMode === 'visual'">
        <el-table :data="form.steps" border table-layout="fixed" max-height="420px" @row-dblclick="openStepDialogByRow">
          <el-table-column label="#" width="60">
            <template #default="scope">{{ scope.$index + 1 }}</template>
          </el-table-column>
          <el-table-column label="步骤名称" prop="stepName" min-width="180" />
          <el-table-column label="级别" prop="stepLevel" width="90" />
          <el-table-column label="动作" min-width="140">
            <template #default="scope">{{ getActionLabel(scope.row.actionType) }}</template>
          </el-table-column>
          <el-table-column label="摘要" min-width="280" show-overflow-tooltip>
            <template #default="scope">{{ summarizeStep(scope.row) }}</template>
          </el-table-column>
          <el-table-column label="超时(ms)" prop="timeoutMs" width="110" />
          <el-table-column label="基准图" width="90">
            <template #default="scope">{{ scope.row.baselineImages?.length || 0 }}</template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="scope">
              <el-button link type="primary" @click="openStepDialog(scope.$index)">编辑</el-button>
              <el-button link type="primary" :disabled="scope.$index === 0" @click="moveStep(scope.$index, -1)">上移</el-button>
              <el-button link type="primary" :disabled="scope.$index === form.steps.length - 1" @click="moveStep(scope.$index, 1)">下移</el-button>
              <el-button link type="danger" @click="removeStep(scope.$index)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div v-else>
        <el-input v-model="stepsJsonText" type="textarea" :rows="18" placeholder="请输入步骤 JSON 数组" />
      </div>

      <template #footer>
        <el-button @click="showCaseDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.save" @click="saveCase">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showStepDialog" :title="stepEditorContext.mode === 'recording' ? '编辑录制步骤' : '编辑步骤'" width="1180px" destroy-on-close>
      <el-form :model="stepDraft" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="步骤名称">
              <el-input v-model="stepDraft.stepName" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="步骤级别">
              <el-select v-model="stepDraft.stepLevel" style="width: 100%">
                <el-option label="NAV" value="NAV" />
                <el-option label="MID" value="MID" />
                <el-option label="RES" value="RES" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="动作类型">
              <el-select v-model="stepDraft.actionType" style="width: 100%" @change="handleStepActionTypeChange">
                <el-option v-for="item in actionOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="超时毫秒">
              <el-input-number v-model="stepDraft.timeoutMs" :min="0" :step="500" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="失败继续">
              <el-switch v-model="stepDraft.continueOnFailure" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="启用">
              <el-switch v-model="stepDraft.enabled" />
            </el-form-item>
          </el-col>

          <template v-if="['click', 'double_click', 'right_click', 'move', 'find_image', 'wait_image'].includes(stepDraft.actionType)">
            <el-col :span="6">
              <el-form-item label="坐标X">
                <el-input-number v-model="stepDraft.params.position.x" :min="0" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="坐标Y">
                <el-input-number v-model="stepDraft.params.position.y" :min="0" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="按钮">
                <el-select v-model="stepDraft.params.button" style="width: 100%" :disabled="stepDraft.actionType === 'right_click'">
                  <el-option label="left" value="left" />
                  <el-option label="right" value="right" />
                  <el-option label="middle" value="middle" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col v-if="stepDraft.actionType === 'move'" :span="6">
              <el-form-item label="移动耗时">
                <el-input-number v-model="stepDraft.params.duration" :min="0" :step="0.1" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
          </template>

          <template v-if="stepDraft.actionType === 'drag'">
            <el-col :span="6">
              <el-form-item label="起点X">
                <el-input-number v-model="stepDraft.params.position.x" :min="0" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="起点Y">
                <el-input-number v-model="stepDraft.params.position.y" :min="0" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="终点X">
                <el-input-number v-model="stepDraft.params.endPosition.x" :min="0" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="终点Y">
                <el-input-number v-model="stepDraft.params.endPosition.y" :min="0" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="鼠标按钮">
                <el-select v-model="stepDraft.params.button" style="width: 100%">
                  <el-option label="left" value="left" />
                  <el-option label="right" value="right" />
                  <el-option label="middle" value="middle" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="拖拽耗时">
                <el-input-number v-model="stepDraft.params.duration" :min="0" :step="0.1" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="预移动耗时">
                <el-input-number v-model="stepDraft.params.moveDuration" :min="0" :step="0.1" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
          </template>

          <template v-if="stepDraft.actionType === 'scroll'">
            <el-col :span="6">
              <el-form-item label="定位X">
                <el-input-number v-model="stepDraft.params.position.x" :min="0" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="定位Y">
                <el-input-number v-model="stepDraft.params.position.y" :min="0" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="纵向滚动">
                <el-input-number v-model="stepDraft.params.scrollAmount" :step="1" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="横向滚动">
                <el-input-number v-model="stepDraft.params.horizontalScroll" :step="1" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
          </template>

          <template v-if="stepDraft.actionType === 'typewrite'">
            <el-col :span="18">
              <el-form-item label="输入文本">
                <el-input v-model="stepDraft.params.text" type="textarea" :rows="3" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="输入间隔">
                <el-input-number v-model="stepDraft.params.interval" :min="0" :step="0.01" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
          </template>

          <template v-if="stepDraft.actionType === 'press'">
            <el-col :span="12">
              <el-form-item label="按键">
                <el-select v-model="stepDraft.params.key" filterable allow-create default-first-option style="width: 100%">
                  <el-option v-for="item in pressKeyOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
            </el-col>
          </template>

          <template v-if="stepDraft.actionType === 'hotkey'">
            <el-col :span="24">
              <el-form-item label="常用组合">
                <el-select v-model="stepUi.hotkeyPreset" clearable placeholder="可直接套用常用快捷键" style="width: 100%" @change="applyHotkeyPreset">
                  <el-option v-for="item in commonHotkeyOptions" :key="item.label" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="组合按键">
                <el-select v-model="stepDraft.params.keys" multiple filterable allow-create default-first-option style="width: 100%">
                  <el-option v-for="item in pressKeyOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
            </el-col>
          </template>

          <template v-if="['wait', 'sleep'].includes(stepDraft.actionType)">
            <el-col :span="8">
              <el-form-item label="等待毫秒">
                <el-input-number v-model="stepDraft.params.waitMs" :min="0" :step="500" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
          </template>

          <template v-if="stepDraft.actionType === 'launch_app'">
            <el-col :span="24">
              <el-form-item label="应用路径">
                <el-input v-model="stepDraft.params.appPath" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="应用参数">
                <el-input v-model="stepUi.appArgsText" type="textarea" :rows="2" placeholder="每行一个参数" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="启动等待">
                <el-input-number v-model="stepDraft.params.waitMs" :min="0" :step="500" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
          </template>
        </el-row>

        <el-divider content-position="left">图像与标注</el-divider>
        <div class="step-asset-toolbar">
          <el-button size="small" plain @click="openTargetAnnotation">裁剪目标图</el-button>
          <el-button size="small" plain @click="openMaskAnnotation(stepUi.baselineIndex)">图形标注忽略区域</el-button>
          <el-button size="small" plain @click="stepUi.showAdvanced = !stepUi.showAdvanced">{{ stepUi.showAdvanced ? '收起高级 JSON' : '展开高级 JSON' }}</el-button>
        </div>
        <el-row :gutter="16" class="mb12">
          <el-col :span="8">
            <div class="asset-card">
              <div class="asset-card-header">
                <span>目标图</span>
                <el-tag size="small" :type="stepDraft.targetImage ? 'success' : 'info'">{{ stepDraft.targetImage ? '已配置' : '未配置' }}</el-tag>
              </div>
              <el-image v-if="getAssetPreviewSrc(stepDraft.targetImage)" :src="getAssetPreviewSrc(stepDraft.targetImage)" fit="contain" class="asset-preview" :preview-src-list="[getAssetPreviewSrc(stepDraft.targetImage)]" />
              <el-empty v-else description="暂无目标图" :image-size="60" />
            </div>
          </el-col>
          <el-col :span="16">
            <div class="asset-card">
              <div class="asset-card-header">
                <span>基准图</span>
                <el-tag size="small">{{ stepDraft.baselineImages?.length || 0 }} 张</el-tag>
              </div>
              <div v-if="stepDraft.baselineImages?.length" class="baseline-grid">
                <div v-for="(item, index) in stepDraft.baselineImages" :key="item.assetId || item.filePath || index" class="baseline-item">
                  <div class="baseline-item-header">
                    <span>{{ item.resolutionKey || `基准图${index + 1}` }}</span>
                    <div class="baseline-item-actions">
                      <el-button link type="primary" @click="openBaselineAnnotation(index)">裁剪</el-button>
                      <el-button link type="danger" @click="removeBaselineImage(index)">删除</el-button>
                    </div>
                  </div>
                  <el-image :src="getAssetPreviewSrc(item)" fit="cover" class="thumb-image" :preview-src-list="[getAssetPreviewSrc(item)]" />
                </div>
              </div>
              <el-empty v-else description="暂无基准图" :image-size="60" />
            </div>
          </el-col>
        </el-row>

        <div class="asset-card mb12">
          <div class="asset-card-header">
            <span>忽略区域</span>
            <el-tag size="small">{{ stepDraft.maskRegions?.length || 0 }} 个</el-tag>
          </div>
          <el-table v-if="stepDraft.maskRegions?.length" :data="stepDraft.maskRegions" size="small" border max-height="220px">
            <el-table-column label="#" width="54">
              <template #default="scope">{{ scope.$index + 1 }}</template>
            </el-table-column>
            <el-table-column label="名称" prop="name" min-width="120" />
            <el-table-column label="X" prop="x" width="80" />
            <el-table-column label="Y" prop="y" width="80" />
            <el-table-column label="宽" prop="width" width="90" />
            <el-table-column label="高" prop="height" width="90" />
            <el-table-column label="类型" width="90">
              <template #default="scope">
                <el-tag :type="scope.row.exclude !== false ? 'danger' : 'success'">{{ scope.row.exclude !== false ? '忽略' : '保留' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="scope">
                <el-button link type="danger" @click="removeMaskRegion(scope.$index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无忽略区域" :image-size="60" />
        </div>

        <div v-if="stepUi.showAdvanced">
          <el-divider content-position="left">高级 JSON</el-divider>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="目标图片 JSON">
                <el-input v-model="stepJson.targetImage" type="textarea" :rows="5" placeholder="可为空" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="基准图 JSON">
                <el-input v-model="stepJson.baselineImages" type="textarea" :rows="5" placeholder="图片数组" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="忽略区域 JSON">
                <el-input v-model="stepJson.maskRegions" type="textarea" :rows="5" placeholder="maskRegions 数组" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="比对配置 JSON">
                <el-input v-model="stepJson.compareConfig" type="textarea" :rows="5" placeholder="留空或 {} 使用系统默认；高级模式可写 compareConfig 对象" />
              </el-form-item>
            </el-col>
          </el-row>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="showStepDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.stepSave" @click="saveStepDraft">保存步骤</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRunDialog" title="执行桌面用例" width="640px">
      <el-form :model="runForm" label-width="110px">
        <el-form-item label="执行 Agent">
          <el-select v-model="runForm.agentId" filterable placeholder="请选择 Agent" style="width: 100%">
            <el-option v-for="item in agentOptions" :key="item.agentId" :label="item.agentName || item.agentCode" :value="item.agentId" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行结束关闭应用">
          <el-switch v-model="runForm.closeAppOnFinish" />
        </el-form-item>
        <el-divider content-position="left">逻辑视口覆盖</el-divider>
        <el-form-item label="视口模式">
          <el-select v-model="runForm.viewportMode" style="width: 100%">
            <el-option v-for="item in viewportModeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="逻辑宽度">
              <el-input-number v-model="runForm.logicalWidth" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="逻辑高度">
              <el-input-number v-model="runForm.logicalHeight" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="runForm.viewportMode !== 'screen'" :span="12">
            <el-form-item label="区域宽度">
              <el-input-number v-model="runForm.viewportWidth" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="runForm.viewportMode !== 'screen'" :span="12">
            <el-form-item label="区域高度">
              <el-input-number v-model="runForm.viewportHeight" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="runForm.viewportMode === 'manual_region'" :span="12">
            <el-form-item label="区域起点 X">
              <el-input-number v-model="runForm.viewportX" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="runForm.viewportMode === 'manual_region'" :span="12">
            <el-form-item label="区域起点 Y">
              <el-input-number v-model="runForm.viewportY" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="runForm.viewportMode === 'active_window'" :span="24">
            <el-form-item label="自动调整窗口">
              <el-switch v-model="runForm.resizeActiveWindow" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="比对配置覆盖">
          <el-input
            v-model="runForm.compareConfigText"
            type="textarea"
            :rows="6"
            placeholder="可选，输入 JSON 对象；为空时按步骤配置和系统默认执行"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRunDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.run" @click="submitRun">开始执行</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRunDetailDialog" title="执行详情" width="1200px" destroy-on-close>
      <div v-if="runDetail">
        <el-descriptions :column="3" border class="mb16">
          <el-descriptions-item label="执行记录ID">{{ runDetail.desktopCaseRunId }}</el-descriptions-item>
          <el-descriptions-item label="所属用例">{{ runDetail.caseName || getCaseName(runDetail.desktopCaseId) || runDetail.desktopCaseId }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getRunStatusMeta(runDetail.status).type">{{ getRunStatusMeta(runDetail.status).label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Agent">{{ runDetail.agentCode || "-" }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatTime(runDetail.startedAt) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ formatTime(runDetail.endedAt) }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ formatDuration(runDetail.durationMs) }}</el-descriptions-item>
          <el-descriptions-item label="失败原因" :span="2">{{ runDetail.errorMessage || "-" }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="getAssetPreviewSrc(runDetail.result?.finalScreenshot)" class="image-panel mb16">
          <div class="image-panel-title">最终截图</div>
          <el-image :src="getAssetPreviewSrc(runDetail.result.finalScreenshot)" fit="contain" class="preview-image" :preview-src-list="[getAssetPreviewSrc(runDetail.result.finalScreenshot)]" />
        </div>

        <el-table :data="runDetail.result?.steps || []" border table-layout="fixed" max-height="460px">
          <el-table-column label="#" width="60">
            <template #default="scope">{{ scope.$index + 1 }}</template>
          </el-table-column>
          <el-table-column label="步骤名称" prop="stepName" min-width="180" />
          <el-table-column label="动作" prop="actionType" min-width="120" />
          <el-table-column label="状态" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.status === 'passed' ? 'success' : 'danger'">{{ scope.row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="100">
            <template #default="scope">{{ formatDuration(scope.row.durationMs) }}</template>
          </el-table-column>
          <el-table-column label="错误信息" min-width="220" show-overflow-tooltip>
            <template #default="scope">{{ scope.row.error || "-" }}</template>
          </el-table-column>
          <el-table-column label="图片" min-width="280">
            <template #default="scope">
              <div class="run-step-images">
                <el-image v-if="getAssetPreviewSrc(scope.row.currentImage)" :src="getAssetPreviewSrc(scope.row.currentImage)" fit="cover" class="thumb-image" :preview-src-list="[getAssetPreviewSrc(scope.row.currentImage)]" />
                <el-image v-if="getAssetPreviewSrc(scope.row.diffImage)" :src="getAssetPreviewSrc(scope.row.diffImage)" fit="cover" class="thumb-image" :preview-src-list="[getAssetPreviewSrc(scope.row.diffImage)]" />
                <el-image v-if="getAssetPreviewSrc(scope.row.matchedTargetImage)" :src="getAssetPreviewSrc(scope.row.matchedTargetImage)" fit="cover" class="thumb-image" :preview-src-list="[getAssetPreviewSrc(scope.row.matchedTargetImage)]" />
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="scope">
              <el-button
                v-if="scope.row.currentImage?.assetId && scope.row.stepId"
                link
                type="warning"
                @click="replaceBaseline(scope.row)"
                v-hasPermi="['hrm:desktopCase:edit']"
              >
                替换基准
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>

    <el-dialog v-model="showRecordingDialog" title="桌面录制" width="980px" destroy-on-close>
      <el-form :model="recordingForm" label-width="120px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="关联用例">
              <el-select v-model="recordingForm.desktopCaseId" clearable filterable style="width: 100%">
                <el-option v-for="item in caseOptions" :key="item.desktopCaseId" :label="item.caseName" :value="item.desktopCaseId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="录制名称">
              <el-input v-model="recordingForm.sessionName" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="执行 Agent">
              <el-select v-model="recordingForm.agentId" filterable style="width: 100%">
                <el-option v-for="item in agentOptions" :key="item.agentId" :label="item.agentName || item.agentCode" :value="item.agentId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="录制结束关闭应用">
              <el-switch v-model="recordingForm.closeAppOnStop" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="采集基准图">
              <el-switch v-model="recordingForm.captureBaselineAfterAction" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="采集目标图">
              <el-switch v-model="recordingForm.captureTargetImage" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="记录键盘文本">
              <el-switch v-model="recordingForm.includeKeyboardText" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="目标图尺寸">
              <el-input-number v-model="recordingForm.targetImageSize" :min="32" :step="16" controls-position="right" style="width: 100%" :disabled="!recordingForm.captureTargetImage" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="截图延迟(ms)">
              <el-input-number v-model="recordingForm.captureDelayMs" :min="0" :step="100" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="双击判定(ms)">
              <el-input-number v-model="recordingForm.doubleClickIntervalMs" :min="120" :step="20" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="拖拽阈值(px)">
              <el-input-number v-model="recordingForm.dragThresholdPx" :min="2" :step="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="录制中标注">
              <el-select v-model="recordingForm.annotationWaitMode" style="width: 100%">
                <el-option v-for="item in annotationWaitModeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <div class="form-tip">
              开启后，Agent 会在每步截图前或截图后暂停，并显示桌面悬浮工具栏，等待你标记验证区域、忽略区域或新增断言；这段标注操作本身不会被录制成步骤。
            </div>
          </el-col>
          <el-col :span="24">
            <el-divider content-position="left">逻辑视口</el-divider>
          </el-col>
          <el-col :span="8">
            <el-form-item label="视口模式">
              <el-select v-model="recordingForm.viewportMode" style="width: 100%">
                <el-option v-for="item in viewportModeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="逻辑宽度">
              <el-input-number v-model="recordingForm.logicalWidth" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="逻辑高度">
              <el-input-number v-model="recordingForm.logicalHeight" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="recordingForm.viewportMode !== 'screen'" :span="8">
            <el-form-item label="区域宽度">
              <el-input-number v-model="recordingForm.viewportWidth" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="recordingForm.viewportMode !== 'screen'" :span="8">
            <el-form-item label="区域高度">
              <el-input-number v-model="recordingForm.viewportHeight" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="recordingForm.viewportMode === 'manual_region'" :span="8">
            <el-form-item label="区域起点 X">
              <el-input-number v-model="recordingForm.viewportX" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="recordingForm.viewportMode === 'manual_region'" :span="8">
            <el-form-item label="区域起点 Y">
              <el-input-number v-model="recordingForm.viewportY" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="recordingForm.viewportMode === 'active_window'" :span="8">
            <el-form-item label="自动调整窗口">
              <el-switch v-model="recordingForm.resizeActiveWindow" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <div class="form-tip">
              使用整屏模式时，如果只填写逻辑宽高，客户端会默认取屏幕左上角对应大小的逻辑区域；如果希望跟随实际应用窗口，请使用“当前活动窗口”或“手工区域”。
            </div>
          </el-col>
          <el-col :span="24">
            <el-form-item label="启动应用路径">
              <el-input v-model="recordingForm.appPath" placeholder="Agent 本机可执行文件路径，可为空" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <div class="form-tip">
              这里填写的是执行 Agent 所在机器上的本地应用路径。点击“开始录制”后，Agent 会先尝试启动这个应用，再进入录制；留空则只录制当前桌面，不会主动拉起程序。
            </div>
          </el-col>
          <el-col :span="24">
            <el-form-item label="启动参数">
              <el-input v-model="recordingForm.appArgsText" type="textarea" :rows="2" placeholder="每行一个参数" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div class="recording-toolbar mb12">
        <el-button type="primary" :loading="loading.recording" @click="startRecording">开始录制</el-button>
        <el-button type="warning" :loading="loading.recordingStop" :disabled="!recordingForm.recordingId || loading.recordingStop" @click="stopRecording">停止录制</el-button>
        <el-button :disabled="!recordingForm.recordingId" @click="refreshRecording">刷新</el-button>
      </div>

      <div class="recording-live-header mb12">
        <div class="recording-live-title">
          <span>实时步骤</span>
          <el-tag size="small">{{ recordingLiveSteps.length }} 步</el-tag>
          <el-tag size="small" :type="liveRecordingStatusMeta.type">{{ liveRecordingStatusMeta.label }}</el-tag>
        </div>
        <span class="recording-live-tip">录制进行中就可以点击“编辑/标注”，直接裁剪目标图、裁剪基准图并配置忽略区域。</span>
      </div>

      <el-table :data="recordingLiveSteps" border table-layout="fixed" max-height="320px">
        <el-table-column label="#" width="60">
          <template #default="scope">{{ scope.$index + 1 }}</template>
        </el-table-column>
        <el-table-column label="步骤名称" prop="stepName" min-width="200" />
        <el-table-column label="动作" prop="actionType" min-width="140" />
        <el-table-column label="摘要" min-width="260" show-overflow-tooltip>
          <template #default="scope">{{ summarizeStep(scope.row) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="openRecordingStepDialog(scope.row)">编辑/标注</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="showRecordingDetailDialog" title="录制详情" width="1200px" destroy-on-close>
      <div v-if="recordingDetail">
        <el-descriptions :column="3" border class="mb16">
          <el-descriptions-item label="录制ID">{{ recordingDetail.recordingId }}</el-descriptions-item>
          <el-descriptions-item label="录制名称">{{ recordingDetail.sessionName }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getRecordingStatusMeta(recordingDetail.status).type">{{ getRecordingStatusMeta(recordingDetail.status).label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="关联用例">{{ getCaseName(recordingDetail.desktopCaseId) || recordingDetail.desktopCaseId || "独立录制" }}</el-descriptions-item>
          <el-descriptions-item label="Agent">{{ recordingDetail.agentCode || "-" }}</el-descriptions-item>
          <el-descriptions-item label="应用路径">{{ recordingDetail.appPath || "-" }}</el-descriptions-item>
        </el-descriptions>
        <div class="mb12">
          <el-button type="success" icon="VideoPlay" :disabled="!canUseRecordingResult(recordingDetail.status)" @click="openReplayDialog(recordingDetail)" v-hasPermi="['hrm:desktopCase:run']">回放录制</el-button>
          <el-button type="success" plain icon="Plus" :disabled="!canUseRecordingResult(recordingDetail.status)" @click="openRecordingActionDialog('create', recordingDetail)" v-hasPermi="['hrm:desktopCase:add']">保存为新用例</el-button>
          <el-button type="info" plain icon="DocumentAdd" :disabled="!canUseRecordingResult(recordingDetail.status)" @click="openRecordingActionDialog('append', recordingDetail)" v-hasPermi="['hrm:desktopCase:edit']">追加到用例</el-button>
          <el-button type="danger" plain icon="EditPen" :disabled="!canUseRecordingResult(recordingDetail.status)" @click="openRecordingActionDialog('replace', recordingDetail)" v-hasPermi="['hrm:desktopCase:edit']">覆盖到用例</el-button>
        </div>
        <el-table :data="recordingDetail.steps || []" border table-layout="fixed" max-height="460px">
          <el-table-column label="#" width="60">
            <template #default="scope">{{ scope.$index + 1 }}</template>
          </el-table-column>
          <el-table-column label="步骤名称" prop="stepName" min-width="200" />
          <el-table-column label="动作" prop="actionType" min-width="120" />
          <el-table-column label="摘要" min-width="260" show-overflow-tooltip>
            <template #default="scope">{{ summarizeStep(scope.row) }}</template>
          </el-table-column>
          <el-table-column label="截图" min-width="220">
            <template #default="scope">
              <div class="run-step-images">
                <el-image v-if="getAssetPreviewSrc(scope.row.targetImage)" :src="getAssetPreviewSrc(scope.row.targetImage)" fit="cover" class="thumb-image" :preview-src-list="[getAssetPreviewSrc(scope.row.targetImage)]" />
                <el-image v-for="item in scope.row.baselineImages || []" :key="item.assetId || item.filePath" :src="getAssetPreviewSrc(item)" fit="cover" class="thumb-image" :preview-src-list="[getAssetPreviewSrc(item)]" />
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="scope">
              <el-button link type="primary" @click="openRecordingStepDialog(scope.row)">编辑/标注</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>

    <el-dialog v-model="showRecordingActionDialog" :title="recordingActionMode === 'create' ? '录制保存为新用例' : '录制应用到现有用例'" width="700px" destroy-on-close>
      <el-form :model="recordingActionForm" label-width="120px">
        <el-form-item v-if="recordingActionMode === 'create'" label="新用例名称">
          <el-input v-model="recordingActionForm.caseName" />
        </el-form-item>
        <template v-else>
          <el-form-item label="目标用例">
            <el-select v-model="recordingActionForm.desktopCaseId" filterable style="width: 100%">
              <el-option v-for="item in caseOptions" :key="item.desktopCaseId" :label="item.caseName" :value="item.desktopCaseId" />
            </el-select>
          </el-form-item>
        </template>
        <el-form-item v-if="recordingActionMode === 'create'" label="项目">
          <el-select v-model="recordingActionForm.projectId" clearable filterable style="width: 100%">
            <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="recordingActionMode === 'create'" label="模块">
          <el-select v-model="recordingActionForm.moduleId" clearable filterable style="width: 100%">
            <el-option v-for="item in actionFormModules" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRecordingActionDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.recordingAction" @click="submitRecordingAction">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showReplayDialog" title="录制回放" width="640px" destroy-on-close>
      <el-form :model="replayForm" label-width="110px">
        <el-form-item label="执行 Agent">
          <el-select v-model="replayForm.agentId" filterable style="width: 100%">
            <el-option v-for="item in agentOptions" :key="item.agentId" :label="item.agentName || item.agentCode" :value="item.agentId" />
          </el-select>
        </el-form-item>
        <el-form-item label="回放结束关闭应用">
          <el-switch v-model="replayForm.closeAppOnFinish" />
        </el-form-item>
        <el-divider content-position="left">逻辑视口覆盖</el-divider>
        <el-row :gutter="12">
          <el-col :span="24">
            <el-form-item label="视口模式">
              <el-select v-model="replayForm.viewportMode" style="width: 100%">
                <el-option v-for="item in viewportModeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="逻辑宽度">
              <el-input-number v-model="replayForm.logicalWidth" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="逻辑高度">
              <el-input-number v-model="replayForm.logicalHeight" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="replayForm.viewportMode !== 'screen'" :span="12">
            <el-form-item label="区域宽度">
              <el-input-number v-model="replayForm.viewportWidth" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="replayForm.viewportMode !== 'screen'" :span="12">
            <el-form-item label="区域高度">
              <el-input-number v-model="replayForm.viewportHeight" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="replayForm.viewportMode === 'manual_region'" :span="12">
            <el-form-item label="区域起点 X">
              <el-input-number v-model="replayForm.viewportX" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="replayForm.viewportMode === 'manual_region'" :span="12">
            <el-form-item label="区域起点 Y">
              <el-input-number v-model="replayForm.viewportY" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="replayForm.viewportMode === 'active_window'" :span="24">
            <el-form-item label="自动调整窗口">
              <el-switch v-model="replayForm.resizeActiveWindow" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="比对配置覆盖">
          <el-input
            v-model="replayForm.compareConfigText"
            type="textarea"
            :rows="6"
            placeholder="可选，输入 JSON 对象；为空时按录制步骤配置和系统默认执行"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReplayDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.replay" @click="submitReplay">开始回放</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showStorageConfigDialog" title="桌面截图存储配置" width="760px" destroy-on-close>
      <el-form :model="storageConfigForm" label-width="120px">
        <el-form-item label="存储方式">
          <el-radio-group v-model="storageConfigForm.mode">
            <el-radio :value="'local'">本地目录</el-radio>
            <el-radio :value="'ftp'">FTP</el-radio>
            <el-radio :value="'sftp'">SFTP</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="本地存储目录">
          <el-input v-model="storageConfigForm.localDirectory" placeholder="留空则使用项目根目录下 case_data/image" />
          <div class="form-tip">当前默认目录：{{ storageConfigForm.effectiveLocalDirectory || '-' }}</div>
        </el-form-item>

        <template v-if="storageConfigForm.mode === 'ftp'">
          <el-divider content-position="left">FTP 配置</el-divider>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="Host">
                <el-input v-model="storageConfigForm.ftp.host" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Port">
                <el-input-number v-model="storageConfigForm.ftp.port" :min="1" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="用户名">
                <el-input v-model="storageConfigForm.ftp.username" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="密码">
                <el-input v-model="storageConfigForm.ftp.password" type="password" show-password />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="远端目录">
                <el-input v-model="storageConfigForm.ftp.baseDir" placeholder="例如 /data/api-test-platform/images" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="被动模式">
                <el-switch v-model="storageConfigForm.ftp.passive" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="超时(秒)">
                <el-input-number v-model="storageConfigForm.ftp.timeoutSec" :min="1" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="编码">
                <el-input v-model="storageConfigForm.ftp.encoding" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>

        <template v-if="storageConfigForm.mode === 'sftp'">
          <el-divider content-position="left">SFTP 配置</el-divider>
          <div v-if="!storageConfigForm.sftpAvailable" class="form-tip form-tip-warning">
            当前后端环境尚未安装 `paramiko`，保存配置后需在后端环境补齐该依赖才能真正使用 SFTP。
          </div>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="Host">
                <el-input v-model="storageConfigForm.sftp.host" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Port">
                <el-input-number v-model="storageConfigForm.sftp.port" :min="1" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="用户名">
                <el-input v-model="storageConfigForm.sftp.username" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="密码">
                <el-input v-model="storageConfigForm.sftp.password" type="password" show-password />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="远端目录">
                <el-input v-model="storageConfigForm.sftp.baseDir" placeholder="例如 /data/api-test-platform/images" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="超时(秒)">
                <el-input-number v-model="storageConfigForm.sftp.timeoutSec" :min="1" controls-position="right" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showStorageConfigDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading.storageConfig" @click="saveStorageConfig">保存</el-button>
      </template>
    </el-dialog>

    <DesktopAnnotationDialog
      v-model="showAnnotationDialog"
      :title="annotationDialog.title"
      :mode="annotationDialog.mode"
      :source-asset="annotationDialog.sourceAsset"
      :source-src="annotationDialog.sourceSrc"
      :initial-crop-rect="annotationDialog.initialCropRect"
      :initial-regions="annotationDialog.initialRegions"
      @confirm="handleAnnotationConfirm"
    />
  </div>
</template>

<script setup name="desktopcase">
import { computed, getCurrentInstance, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import DesktopAnnotationDialog from './components/DesktopAnnotationDialog.vue'

import { all as getAllAgent } from '@/api/hrm/agent'
import {
  addDesktopCase,
  applyDesktopRecording,
  delDesktopCase,
  getDesktopCase,
  getDesktopStorageConfig,
  getDesktopRecording,
  getDesktopRun,
  listDesktopCase,
  listDesktopRecording,
  listDesktopRun,
  replaceDesktopBaseline,
  replayDesktopRecording,
  runDesktopCase,
  saveDesktopRecordingAsCase,
  saveDesktopStorageConfig,
  startDesktopRecording,
  stopDesktopRecording,
  updateDesktopCase,
  updateDesktopRecordingEvent
} from '@/api/hrm/desktop_case'
import { showModulList } from '@/api/hrm/module'
import { listProject } from '@/api/hrm/project'

const { proxy } = getCurrentInstance()

const actionOptions = [
  { label: '点击', value: 'click' },
  { label: '双击', value: 'double_click' },
  { label: '右键', value: 'right_click' },
  { label: '移动', value: 'move' },
  { label: '拖拽', value: 'drag' },
  { label: '滚轮', value: 'scroll' },
  { label: '输入文本', value: 'typewrite' },
  { label: '按键', value: 'press' },
  { label: '快捷键', value: 'hotkey' },
  { label: '等待', value: 'wait' },
  { label: '查找图片', value: 'find_image' },
  { label: '等待图片', value: 'wait_image' },
  { label: '视觉断言', value: 'assert_visual' },
  { label: '启动应用', value: 'launch_app' },
  { label: '关闭应用', value: 'close_app' }
]

const alphabetKeyOptions = 'abcdefghijklmnopqrstuvwxyz'.split('').map((value) => ({ label: value.toUpperCase(), value }))
const numberKeyOptions = Array.from({ length: 10 }, (_, index) => ({ label: `${index}`, value: `${index}` }))
const functionKeyOptions = Array.from({ length: 24 }, (_, index) => ({ label: `F${index + 1}`, value: `f${index + 1}` }))
const symbolKeyOptions = [
  { label: '`', value: '`' },
  { label: '-', value: '-' },
  { label: '=', value: '=' },
  { label: '[', value: '[' },
  { label: ']', value: ']' },
  { label: '\\', value: '\\' },
  { label: ';', value: ';' },
  { label: '\'', value: '\'' },
  { label: ',', value: ',' },
  { label: '.', value: '.' },
  { label: '/', value: '/' }
]
const numpadKeyOptions = [
  ...Array.from({ length: 10 }, (_, index) => ({ label: `Num ${index}`, value: `num${index}` })),
  { label: 'Num .', value: 'decimal' },
  { label: 'Num /', value: 'divide' },
  { label: 'Num *', value: 'multiply' },
  { label: 'Num -', value: 'subtract' },
  { label: 'Num +', value: 'add' },
  { label: 'Num Separator', value: 'separator' }
]
const advancedKeyOptions = [
  { label: 'Caps Lock', value: 'capslock' },
  { label: 'Num Lock', value: 'numlock' },
  { label: 'Scroll Lock', value: 'scrolllock' },
  { label: 'Pause', value: 'pause' },
  { label: 'Print Screen', value: 'printscreen' },
  { label: 'Apps/Menu', value: 'apps' },
  { label: 'Ctrl Left', value: 'ctrlleft' },
  { label: 'Ctrl Right', value: 'ctrlright' },
  { label: 'Shift Left', value: 'shiftleft' },
  { label: 'Shift Right', value: 'shiftright' },
  { label: 'Alt Left', value: 'altleft' },
  { label: 'Alt Right', value: 'altright' },
  { label: 'Win Left', value: 'winleft' },
  { label: 'Win Right', value: 'winright' },
  { label: 'Browser Back', value: 'browserback' },
  { label: 'Browser Forward', value: 'browserforward' },
  { label: 'Browser Refresh', value: 'browserrefresh' },
  { label: 'Browser Search', value: 'browsersearch' },
  { label: 'Browser Home', value: 'browserhome' },
  { label: 'Browser Stop', value: 'browserstop' },
  { label: 'Volume Mute', value: 'volumemute' },
  { label: 'Volume Down', value: 'volumedown' },
  { label: 'Volume Up', value: 'volumeup' },
  { label: 'Media Play/Pause', value: 'playpause' },
  { label: 'Media Next', value: 'nexttrack' },
  { label: 'Media Previous', value: 'prevtrack' },
  { label: 'Media Stop', value: 'stop' },
  { label: 'Launch Mail', value: 'launchmail' },
  { label: 'Launch App1', value: 'launchapp1' },
  { label: 'Launch App2', value: 'launchapp2' }
]

const pressKeyOptions = [
  { label: 'Enter', value: 'enter' },
  { label: 'Tab', value: 'tab' },
  { label: 'Esc', value: 'esc' },
  { label: 'Space', value: 'space' },
  { label: 'Backspace', value: 'backspace' },
  { label: 'Delete', value: 'delete' },
  { label: 'Insert', value: 'insert' },
  { label: 'Home', value: 'home' },
  { label: 'End', value: 'end' },
  { label: 'Page Up', value: 'pageup' },
  { label: 'Page Down', value: 'pagedown' },
  { label: 'Up', value: 'up' },
  { label: 'Down', value: 'down' },
  { label: 'Left', value: 'left' },
  { label: 'Right', value: 'right' },
  { label: 'Ctrl', value: 'ctrl' },
  { label: 'Shift', value: 'shift' },
  { label: 'Alt', value: 'alt' },
  { label: 'Win', value: 'win' },
  ...functionKeyOptions,
  ...numberKeyOptions,
  ...alphabetKeyOptions,
  ...symbolKeyOptions,
  ...numpadKeyOptions,
  ...advancedKeyOptions
]

const commonHotkeyOptions = [
  { label: '复制 Ctrl+C', value: ['ctrl', 'c'] },
  { label: '粘贴 Ctrl+V', value: ['ctrl', 'v'] },
  { label: '剪切 Ctrl+X', value: ['ctrl', 'x'] },
  { label: '全选 Ctrl+A', value: ['ctrl', 'a'] },
  { label: '查找 Ctrl+F', value: ['ctrl', 'f'] },
  { label: '打印 Ctrl+P', value: ['ctrl', 'p'] },
  { label: '保存 Ctrl+S', value: ['ctrl', 's'] },
  { label: '另存为 Ctrl+Shift+S', value: ['ctrl', 'shift', 's'] },
  { label: '撤销 Ctrl+Z', value: ['ctrl', 'z'] },
  { label: '重做 Ctrl+Y', value: ['ctrl', 'y'] },
  { label: '复制 Ctrl+Insert', value: ['ctrl', 'insert'] },
  { label: '粘贴 Shift+Insert', value: ['shift', 'insert'] },
  { label: '剪切 Shift+Delete', value: ['shift', 'delete'] },
  { label: '关闭窗口 Alt+F4', value: ['alt', 'f4'] },
  { label: '切换窗口 Alt+Tab', value: ['alt', 'tab'] },
  { label: '任务管理器 Ctrl+Shift+Esc', value: ['ctrl', 'shift', 'esc'] },
  { label: '运行 Win+R', value: ['win', 'r'] },
  { label: '资源管理器 Win+E', value: ['win', 'e'] },
  { label: '显示桌面 Win+D', value: ['win', 'd'] }
]

const runStatusOptions = [
  { value: 1, label: '成功', type: 'success' },
  { value: 2, label: '失败', type: 'danger' },
  { value: 9, label: '运行中', type: 'warning' }
]

const recordingStatusOptions = [
  { value: 1, label: '草稿', type: 'info' },
  { value: 2, label: '录制中', type: 'warning' },
  { value: 3, label: '已完成', type: 'success' },
  { value: 4, label: '失败', type: 'danger' },
  { value: 5, label: '已停止', type: 'info' }
]

const viewportModeOptions = [
  { label: '使用整屏', value: 'screen' },
  { label: '当前活动窗口', value: 'active_window' },
  { label: '手工区域', value: 'manual_region' }
]

const annotationWaitModeOptions = [
  { label: '不暂停标注', value: 'disabled' },
  { label: '截图后暂停标注', value: 'after_capture' },
  { label: '截图前暂停标注', value: 'before_capture' }
]

const activeTab = ref('case')
const projectOptions = ref([])
const moduleOptions = ref([])
const agentOptions = ref([])
const caseSourceOptions = ref([])
const pageDataList = ref([])
const runRecordList = ref([])
const recordingList = ref([])
const total = ref(0)
const runTotal = ref(0)
const recordingTotal = ref(0)

const loading = reactive({
  page: false,
  save: false,
  storageConfig: false,
  stepSave: false,
  run: false,
  runPage: false,
  runDetail: false,
  recording: false,
  recordingStop: false,
  recordingPage: false,
  recordingDetail: false,
  recordingAction: false,
  replay: false
})

const queryParams = reactive({
  pageNum: 1,
  pageSize: 10,
  caseName: undefined,
  projectId: undefined,
  moduleId: undefined
})

const runQueryParams = reactive({
  pageNum: 1,
  pageSize: 10,
  desktopCaseId: undefined,
  status: undefined,
  agentCode: undefined
})

const recordingQueryParams = reactive({
  pageNum: 1,
  pageSize: 10,
  sessionName: undefined,
  desktopCaseId: undefined,
  status: undefined
})

const showCaseDialog = ref(false)
const showStepDialog = ref(false)
const showRunDialog = ref(false)
const showRunDetailDialog = ref(false)
const showRecordingDialog = ref(false)
const showRecordingDetailDialog = ref(false)
const showRecordingActionDialog = ref(false)
const showReplayDialog = ref(false)
const showStorageConfigDialog = ref(false)
const showAnnotationDialog = ref(false)

function createViewportFields(source = {}) {
  return {
    viewportMode: source?.viewportMode || source?.viewport_mode || 'screen',
    viewportX: source?.viewportX ?? source?.viewport_x,
    viewportY: source?.viewportY ?? source?.viewport_y,
    viewportWidth: source?.viewportWidth ?? source?.viewport_width,
    viewportHeight: source?.viewportHeight ?? source?.viewport_height,
    logicalWidth: source?.logicalWidth ?? source?.logical_width,
    logicalHeight: source?.logicalHeight ?? source?.logical_height,
    resizeActiveWindow: Boolean(source?.resizeActiveWindow ?? source?.resize_active_window ?? false)
  }
}

function buildViewportPayload(source = {}) {
  const payload = createViewportFields(source)
  const isDefaultScreen = payload.viewportMode === 'screen'
    && payload.viewportX === undefined
    && payload.viewportY === undefined
    && payload.viewportWidth === undefined
    && payload.viewportHeight === undefined
    && payload.logicalWidth === undefined
    && payload.logicalHeight === undefined
    && !payload.resizeActiveWindow
  if (isDefaultScreen) {
    return {}
  }
  const result = { viewportMode: payload.viewportMode }
  ;['viewportX', 'viewportY', 'viewportWidth', 'viewportHeight', 'logicalWidth', 'logicalHeight'].forEach((key) => {
    if (payload[key] !== undefined && payload[key] !== null && payload[key] !== '') {
      result[key] = Number(payload[key])
    }
  })
  if (payload.resizeActiveWindow) {
    result.resizeActiveWindow = true
  }
  return result
}

function mergeRuntimeSettingsWithViewport(runtimeSettings = {}, source = {}) {
  const merged = { ...(runtimeSettings || {}) }
  ;['viewportMode', 'viewportX', 'viewportY', 'viewportWidth', 'viewportHeight', 'logicalWidth', 'logicalHeight', 'resizeActiveWindow'].forEach((key) => {
    delete merged[key]
  })
  return {
    ...merged,
    ...buildViewportPayload(source)
  }
}

function createStorageConfigForm() {
  return {
    mode: 'local',
    localDirectory: '',
    ftp: {
      host: '',
      port: 21,
      username: '',
      password: '',
      baseDir: '',
      passive: true,
      timeoutSec: 15,
      encoding: 'utf-8'
    },
    sftp: {
      host: '',
      port: 22,
      username: '',
      password: '',
      baseDir: '',
      timeoutSec: 15
    },
    effectiveLocalDirectory: '',
    sftpAvailable: false
  }
}

function createDefaultStep(actionType = 'click') {
  return {
    stepId: undefined,
    stepName: '新步骤',
    stepLevel: 'MID',
    actionType,
    enabled: true,
    timeoutMs: undefined,
    continueOnFailure: false,
    recordOrigin: 'manual',
    params: {
      position: { x: 0, y: 0 },
      endPosition: { x: 0, y: 0 },
      offset: { dx: 0, dy: 0 },
      button: 'left',
      clicks: 1,
      duration: 0.2,
      moveDuration: 0,
      scrollAmount: -1,
      horizontalScroll: 0,
      text: '',
      interval: 0.02,
      key: 'enter',
      keys: [],
      waitMs: 1000,
      appPath: '',
      appArgs: []
    },
    targetImage: null,
    baselineImages: [],
    maskRegions: [],
    compareConfig: {},
    rawEvent: {}
  }
}

function createEmptyCase() {
  return {
    desktopCaseId: undefined,
    caseName: '',
    projectId: undefined,
    moduleId: undefined,
    appPath: '',
    appArgsText: '',
    runtimeSettings: {},
    notes: '',
    status: 2,
    steps: [],
    ...createViewportFields()
  }
}

function createRunForm() {
  return {
    agentId: undefined,
    closeAppOnFinish: true,
    compareConfigText: '',
    ...createViewportFields()
  }
}

function createRecordingForm() {
  return {
    recordingId: undefined,
    desktopCaseId: undefined,
    sessionName: '',
    agentId: undefined,
    appPath: '',
    appArgsText: '',
    closeAppOnStop: true,
    captureBaselineAfterAction: true,
    captureTargetImage: true,
    targetImageSize: 96,
    captureDelayMs: 400,
    includeKeyboardText: true,
    doubleClickIntervalMs: 320,
    dragThresholdPx: 12,
    annotationWaitMode: 'disabled',
    ...createViewportFields()
  }
}

function createRecordingActionForm() {
  return {
    recordingId: undefined,
    desktopCaseId: undefined,
    caseName: '',
    projectId: undefined,
    moduleId: undefined
  }
}

function createReplayForm() {
  return {
    recordingId: undefined,
    agentId: undefined,
    closeAppOnFinish: true,
    compareConfigText: '',
    ...createViewportFields()
  }
}

const form = ref(createEmptyCase())
const caseEditorMode = ref('visual')
const stepsJsonText = ref('[]')
const stepEditIndex = ref(-1)
const stepDraft = ref(createDefaultStep())
const stepUi = reactive({
  appArgsText: '',
  baselineIndex: 0,
  showAdvanced: false,
  hotkeyPreset: undefined
})
const stepJson = reactive({ targetImage: '', baselineImages: '[]', maskRegions: '[]', compareConfig: '{}' })
const stepEditorContext = reactive({
  mode: 'case',
  caseIndex: -1,
  recordingId: undefined,
  eventId: undefined,
  eventIndex: undefined
})
const annotationDialog = reactive({
  mode: 'mask',
  title: '图像标注',
  sourceAsset: null,
  sourceSrc: '',
  initialCropRect: null,
  initialRegions: []
})

const selectedCase = ref(null)
const runForm = ref(createRunForm())
const runDetail = ref(null)
const recordingForm = ref(createRecordingForm())
const recordingDetail = ref(null)
const recordingLiveSteps = ref([])
const recordingActionMode = ref('create')
const recordingActionForm = ref(createRecordingActionForm())
const replayForm = ref(createReplayForm())
const storageConfigForm = ref(createStorageConfigForm())

let recordingTimer = null
let annotationApplyHandler = null

function cloneData(value) {
  return JSON.parse(JSON.stringify(value))
}

function safeJsonStringify(value) {
  return JSON.stringify(value === undefined ? null : value, null, 2)
}

function parseJsonText(text, fallback, label) {
  if (!text || !`${text}`.trim()) {
    return cloneData(fallback)
  }
  try {
    return JSON.parse(text)
  } catch (error) {
    throw new Error(`${label} 解析失败: ${error.message}`)
  }
}

function parseOptionalJsonObject(text, label) {
  const raw = `${text || ''}`.trim()
  if (!raw) return undefined
  const parsed = parseJsonText(raw, {}, label)
  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error(`${label} 必须是 JSON 对象`)
  }
  return parsed
}

function parseArgsText(text) {
  return `${text || ''}`
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function buildDataImageSrc(imageBase64) {
  if (!imageBase64) return ''
  return `${imageBase64}`.startsWith('data:') ? `${imageBase64}` : `data:image/png;base64,${imageBase64}`
}

function buildApiUrl(url) {
  const raw = `${url || ''}`.trim()
  if (!raw) return ''
  if (/^(?:https?:)?\/\//i.test(raw) || raw.startsWith('data:')) {
    return raw
  }
  const baseApi = `${window.BASE_API || ''}`.replace(/\/$/, '')
  const normalizedPath = raw.startsWith('/') ? raw : `/${raw}`
  return baseApi ? `${baseApi}${normalizedPath}` : normalizedPath
}

function getAssetPreviewSrc(asset) {
  if (!asset) return ''
  if (asset.imageBase64 || asset.image_base64) {
    return buildDataImageSrc(asset.imageBase64 || asset.image_base64)
  }
  return buildApiUrl(asset.previewUrl || asset.preview_url || asset.filePath || asset.file_path || '')
}

function sanitizeAssetForPersist(asset) {
  if (!asset || typeof asset !== 'object') return asset
  const normalized = cloneData(asset)
  delete normalized.previewUrl
  delete normalized.preview_url
  if ((normalized.assetId || normalized.asset_id) && (normalized.imageBase64 || normalized.image_base64)) {
    delete normalized.imageBase64
    delete normalized.image_base64
  }
  return normalized
}

function sanitizeStepForPersist(step, index = 0) {
  const normalized = normalizeStep(step, index)
  normalized.targetImage = sanitizeAssetForPersist(normalized.targetImage)
  normalized.baselineImages = (normalized.baselineImages || []).map((item) => sanitizeAssetForPersist(item)).filter(Boolean)
  return normalized
}

function normalizeStep(step, index = 0) {
  const base = createDefaultStep(step?.actionType || 'click')
  const normalized = {
    ...base,
    ...cloneData(step || {}),
    stepName: step?.stepName || step?.step_name || `步骤${index + 1}`,
    stepLevel: step?.stepLevel || step?.step_level || 'MID',
    actionType: step?.actionType || step?.action_type || 'click',
    params: {
      ...base.params,
      ...(step?.params || {})
    },
    targetImage: step?.targetImage || step?.target_image || null,
    baselineImages: step?.baselineImages || step?.baseline_images || [],
    maskRegions: step?.maskRegions || step?.mask_regions || [],
    compareConfig: {
      ...base.compareConfig,
      ...(step?.compareConfig || step?.compare_config || {})
    },
    rawEvent: step?.rawEvent || step?.raw_event || {}
  }
  if (!normalized.params.position) {
    normalized.params.position = { x: 0, y: 0 }
  }
  if (!normalized.params.endPosition) {
    normalized.params.endPosition = {
      x: normalized.params.position.x ?? 0,
      y: normalized.params.position.y ?? 0
    }
  }
  if (!normalized.params.offset) {
    normalized.params.offset = {
      dx: (normalized.params.endPosition?.x ?? 0) - (normalized.params.position?.x ?? 0),
      dy: (normalized.params.endPosition?.y ?? 0) - (normalized.params.position?.y ?? 0)
    }
  }
  if (!Array.isArray(normalized.params.keys)) {
    normalized.params.keys = []
  }
  normalized.params.appArgs = Array.isArray(normalized.params.appArgs) ? normalized.params.appArgs : []
  normalized.params.button = normalized.params.button || 'left'
  return normalized
}

function normalizeCase(data) {
  const base = createEmptyCase()
  const runtimeSettings = cloneData(data?.runtimeSettings || data?.runtime_settings || {})
  return {
    ...base,
    ...cloneData(data || {}),
    runtimeSettings,
    ...createViewportFields(runtimeSettings),
    appArgsText: (data?.appArgs || data?.app_args || []).join('\n'),
    steps: (data?.steps || []).map((item, index) => normalizeStep(item, index))
  }
}

function buildRecordingSteps(detail) {
  const events = detail?.events || []
  return events.map((item, index) => ({
    ...normalizeStep(item?.payload || {}, index),
    eventId: item?.eventId || item?.event_id,
    eventIndex: item?.eventIndex || item?.event_index || index + 1,
    recordingId: item?.recordingId || item?.recording_id || detail?.recordingId
  }))
}

function normalizeRecordingDetail(detail) {
  const normalized = cloneData(detail || {})
  normalized.steps = buildRecordingSteps(normalized)
  return normalized
}

function extractRows(response) {
  return response?.rows || response?.data?.rows || response?.data || []
}

function padTimeValue(value) {
  return `${value}`.padStart(2, '0')
}

function normalizeDateValue(value) {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value
  }
  if (Array.isArray(value) && value.length >= 3) {
    const [year, month, day, hour = 0, minute = 0, second = 0] = value.map((item) => Number(item))
    if ([year, month, day].every((item) => Number.isFinite(item) && item > 0)) {
      const date = new Date(
        year,
        Math.max(month - 1, 0),
        day,
        Number.isFinite(hour) ? hour : 0,
        Number.isFinite(minute) ? minute : 0,
        Number.isFinite(second) ? second : 0
      )
      return Number.isNaN(date.getTime()) ? null : date
    }
  }
  if (value && typeof value === 'object') {
    if (typeof value.toDate === 'function') {
      const date = value.toDate()
      if (date instanceof Date && !Number.isNaN(date.getTime())) {
        return date
      }
    }
    const year = Number(value.year ?? value.y)
    const month = Number(value.month ?? value.m)
    const day = Number(value.day ?? value.d)
    if ([year, month, day].every((item) => Number.isFinite(item) && item > 0)) {
      const hour = Number(value.hour ?? value.h ?? value.hours ?? 0)
      const minute = Number(value.minute ?? value.i ?? value.minutes ?? 0)
      const second = Number(value.second ?? value.s ?? value.seconds ?? 0)
      const date = new Date(year, month - 1, day, hour || 0, minute || 0, second || 0)
      return Number.isNaN(date.getTime()) ? null : date
    }
    return null
  }
  const raw = `${value ?? ''}`.trim()
  if (!raw) return null
  if (/^[0-9]+$/.test(raw)) {
    let numeric = Number(raw)
    if (raw.length === 10) {
      numeric *= 1000
    }
    const date = new Date(numeric)
    return Number.isNaN(date.getTime()) ? null : date
  }
  const normalized = raw.includes('T') || /(?:Z|[+-]\d{2}:?\d{2})$/.test(raw)
    ? raw
    : raw.replace(/-/g, '/').replace(/\.\d{3,6}/, '')
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatTime(value) {
  if (value === undefined || value === null || value === '') return '-'
  const pattern = '{y}-{m}-{d} {h}:{i}:{s}'
  if (proxy?.parseTime) {
    const formatted = proxy.parseTime(value, pattern)
    if (formatted && !formatted.includes('NaN') && formatted !== '0-0-0 0:0:0') {
      return formatted
    }
  }
  const date = normalizeDateValue(value)
  if (!date) return `${value}`
  if (proxy?.parseTime) {
    const fallbackFormatted = proxy.parseTime(date, pattern)
    if (fallbackFormatted && !fallbackFormatted.includes('NaN')) {
      return fallbackFormatted
    }
  }
  return `${date.getFullYear()}-${padTimeValue(date.getMonth() + 1)}-${padTimeValue(date.getDate())} ${padTimeValue(date.getHours())}:${padTimeValue(date.getMinutes())}:${padTimeValue(date.getSeconds())}`
}

function formatDuration(value) {
  if (value === undefined || value === null || value === '') return '-'
  const ms = Number(value)
  if (!Number.isFinite(ms)) return `${value}`
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)}s`
  const minutes = Math.floor(ms / 60000)
  const seconds = ((ms % 60000) / 1000).toFixed(1)
  return `${minutes}m ${seconds}s`
}

function getActionLabel(actionType) {
  return actionOptions.find((item) => item.value === actionType)?.label || actionType || '-'
}

function summarizeStep(step) {
  const params = step?.params || {}
  if (['click', 'double_click', 'right_click', 'move', 'find_image', 'wait_image'].includes(step?.actionType)) {
    const point = params.position || {}
    return `坐标(${point.x ?? '-'}, ${point.y ?? '-'}) / 目标图 ${step?.targetImage ? '已配置' : '未配置'}`
  }
  if (step?.actionType === 'drag') {
    const point = params.position || {}
    const endPoint = params.endPosition || {}
    return `起点(${point.x ?? '-'}, ${point.y ?? '-'}) -> 终点(${endPoint.x ?? '-'}, ${endPoint.y ?? '-'})`
  }
  if (step?.actionType === 'scroll') {
    return `纵向 ${params.scrollAmount ?? 0} / 横向 ${params.horizontalScroll ?? 0}`
  }
  if (step?.actionType === 'typewrite') return params.text || '-'
  if (step?.actionType === 'press') return params.key || '-'
  if (step?.actionType === 'hotkey') return params.semantic || (Array.isArray(params.keys) ? params.keys.join(' + ') : '-')
  if (['wait', 'sleep'].includes(step?.actionType)) return `${params.waitMs || 0}ms`
  if (step?.actionType === 'launch_app') return params.appPath || '-'
  if (step?.actionType === 'assert_visual') return `基准图 ${step?.baselineImages?.length || 0} 张`
  return '-'
}

function getRunStatusMeta(status) {
  return runStatusOptions.find((item) => `${item.value}` === `${status}`) || { label: `${status ?? '-'}`, type: 'info' }
}

function getRecordingStatusMeta(status) {
  return recordingStatusOptions.find((item) => `${item.value}` === `${status}`) || { label: `${status ?? '-'}`, type: 'info' }
}

const liveRecordingStatusMeta = computed(() => {
  const currentStatus = recordingDetail.value?.status ?? (recordingForm.value.recordingId ? 2 : 1)
  return getRecordingStatusMeta(currentStatus)
})

const filteredModules = computed(() => {
  if (!queryParams.projectId) return moduleOptions.value
  return moduleOptions.value.filter((item) => `${item.projectId}` === `${queryParams.projectId}`)
})

const formModules = computed(() => {
  if (!form.value.projectId) return moduleOptions.value
  return moduleOptions.value.filter((item) => `${item.projectId}` === `${form.value.projectId}`)
})

const actionFormModules = computed(() => {
  if (!recordingActionForm.value.projectId) return moduleOptions.value
  return moduleOptions.value.filter((item) => `${item.projectId}` === `${recordingActionForm.value.projectId}`)
})

const caseOptions = computed(() => {
  const merged = [...caseSourceOptions.value]
  pageDataList.value.forEach((item) => {
    if (!merged.some((caseItem) => `${caseItem.desktopCaseId}` === `${item.desktopCaseId}`)) {
      merged.push({ desktopCaseId: item.desktopCaseId, caseName: item.caseName, projectId: item.projectId, moduleId: item.moduleId, appPath: item.appPath, appArgs: item.appArgs })
    }
  })
  return merged
})

function getProjectName(projectId) {
  return projectOptions.value.find((item) => `${item.projectId}` === `${projectId}`)?.projectName || ''
}

function getModuleName(moduleId) {
  return moduleOptions.value.find((item) => `${item.moduleId}` === `${moduleId}`)?.moduleName || ''
}

function getCaseName(desktopCaseId) {
  return caseOptions.value.find((item) => `${item.desktopCaseId}` === `${desktopCaseId}`)?.caseName || ''
}

function syncStepsJsonText() {
  stepsJsonText.value = safeJsonStringify(form.value.steps)
}

function toggleCaseEditorMode() {
  if (caseEditorMode.value === 'visual') {
    syncStepsJsonText()
    caseEditorMode.value = 'json'
    return
  }
  caseEditorMode.value = 'visual'
}

function applyStepsJsonText() {
  try {
    const parsed = parseJsonText(stepsJsonText.value, [], '步骤 JSON')
    if (!Array.isArray(parsed)) {
      throw new Error('步骤 JSON 必须是数组')
    }
    form.value.steps = parsed.map((item, index) => normalizeStep(item, index))
    caseEditorMode.value = 'visual'
    ElMessage.success('步骤 JSON 已应用')
  } catch (error) {
    ElMessage.error(error.message)
  }
}

function resetQuery() {
  Object.assign(queryParams, { pageNum: 1, pageSize: 10, caseName: undefined, projectId: undefined, moduleId: undefined })
  getList()
}

function resetRunQuery() {
  Object.assign(runQueryParams, { pageNum: 1, pageSize: 10, desktopCaseId: undefined, status: undefined, agentCode: undefined })
  getRunList()
}

function resetRecordingQuery() {
  Object.assign(recordingQueryParams, { pageNum: 1, pageSize: 10, sessionName: undefined, desktopCaseId: undefined, status: undefined })
  getRecordingList()
}

function normalizeStorageConfig(data) {
  return {
    ...createStorageConfigForm(),
    ...cloneData(data || {}),
    ftp: {
      ...createStorageConfigForm().ftp,
      ...(cloneData(data?.ftp || {}))
    },
    sftp: {
      ...createStorageConfigForm().sftp,
      ...(cloneData(data?.sftp || {}))
    }
  }
}

function openStorageConfigDialog() {
  loading.storageConfig = true
  getDesktopStorageConfig().then((response) => {
    storageConfigForm.value = normalizeStorageConfig(response.data || {})
    showStorageConfigDialog.value = true
  }).finally(() => {
    loading.storageConfig = false
  })
}

function saveStorageConfig() {
  loading.storageConfig = true
  const payload = cloneData(storageConfigForm.value)
  delete payload.effectiveLocalDirectory
  delete payload.sftpAvailable
  saveDesktopStorageConfig(payload).then((response) => {
    ElMessage.success(response.msg || '存储配置已保存')
    showStorageConfigDialog.value = false
  }).finally(() => {
    loading.storageConfig = false
  })
}

async function loadBaseData() {
  const [projectRes, moduleRes, agentRes, caseRes] = await Promise.all([
    listProject({ isPage: false }),
    showModulList({ isPage: false }),
    getAllAgent(),
    listDesktopCase({ isPage: true, pageNum: 1, pageSize: 300 })
  ])
  projectOptions.value = extractRows(projectRes)
  moduleOptions.value = extractRows(moduleRes)
  agentOptions.value = extractRows(agentRes)
  caseSourceOptions.value = extractRows(caseRes).map((item) => normalizeCase(item))
}

function getList() {
  loading.page = true
  listDesktopCase(queryParams).then((response) => {
    pageDataList.value = (response.rows || []).map((item) => normalizeCase(item))
    total.value = response.total || 0
  }).finally(() => {
    loading.page = false
  })
}

function getRunList() {
  loading.runPage = true
  listDesktopRun(runQueryParams).then((response) => {
    runRecordList.value = response.rows || []
    runTotal.value = response.total || 0
  }).finally(() => {
    loading.runPage = false
  })
}

function getRecordingList() {
  loading.recordingPage = true
  listDesktopRecording(recordingQueryParams).then((response) => {
    recordingList.value = response.rows || []
    recordingTotal.value = response.total || 0
  }).finally(() => {
    loading.recordingPage = false
  })
}

function handleAdd() {
  form.value = createEmptyCase()
  caseEditorMode.value = 'visual'
  syncStepsJsonText()
  showCaseDialog.value = true
}

function handleEdit(row) {
  getDesktopCase(row.desktopCaseId).then((response) => {
    form.value = normalizeCase(response.data || {})
    caseEditorMode.value = 'visual'
    syncStepsJsonText()
    showCaseDialog.value = true
  })
}

function handleDelete(row) {
  ElMessageBox.confirm(`是否确认删除桌面用例【${row.caseName}】？`, '提示', { type: 'warning' }).then(() => delDesktopCase(row.desktopCaseId)).then(() => {
    ElMessage.success('删除成功')
    loadBaseData()
    getList()
  }).catch(() => {})
}

function addStep(actionType = 'click') {
  form.value.steps.push(createDefaultStep(actionType))
}

function moveStep(index, delta) {
  const target = index + delta
  if (target < 0 || target >= form.value.steps.length) return
  const steps = [...form.value.steps]
  ;[steps[index], steps[target]] = [steps[target], steps[index]]
  form.value.steps = steps
}

function removeStep(index) {
  form.value.steps.splice(index, 1)
}

function ensureStepParamStructures() {
  if (!stepDraft.value.params.position) {
    stepDraft.value.params.position = { x: 0, y: 0 }
  }
  if (!stepDraft.value.params.endPosition) {
    stepDraft.value.params.endPosition = { x: 0, y: 0 }
  }
  if (!stepDraft.value.params.offset) {
    stepDraft.value.params.offset = { dx: 0, dy: 0 }
  }
  if (!Array.isArray(stepDraft.value.params.keys)) {
    stepDraft.value.params.keys = []
  }
}

function prepareStepDialog(current, context = {}) {
  stepDraft.value = cloneData(current)
  ensureStepParamStructures()
  stepUi.appArgsText = Array.isArray(current.params.appArgs) ? current.params.appArgs.join('\n') : ''
  stepUi.baselineIndex = 0
  stepUi.showAdvanced = false
  stepUi.hotkeyPreset = undefined
  stepJson.targetImage = safeJsonStringify(current.targetImage)
  stepJson.baselineImages = safeJsonStringify(current.baselineImages)
  stepJson.maskRegions = safeJsonStringify(current.maskRegions)
  stepJson.compareConfig = safeJsonStringify(current.compareConfig)
  Object.assign(stepEditorContext, {
    mode: context.mode || 'case',
    caseIndex: context.caseIndex ?? -1,
    recordingId: context.recordingId,
    eventId: context.eventId,
    eventIndex: context.eventIndex
  })
  showStepDialog.value = true
}

function openStepDialog(index) {
  const current = normalizeStep(form.value.steps[index], index)
  stepEditIndex.value = index
  prepareStepDialog(current, { mode: 'case', caseIndex: index })
}

function openStepDialogByRow(row) {
  const index = form.value.steps.indexOf(row)
  if (index >= 0) openStepDialog(index)
}

function openRecordingStepDialog(row) {
  const eventIndex = row?.eventIndex || row?.event_index || 1
  prepareStepDialog(
    normalizeStep(row, eventIndex - 1),
    {
      mode: 'recording',
      recordingId: row?.recordingId || row?.recording_id || recordingForm.value.recordingId || recordingDetail.value?.recordingId,
      eventId: row?.eventId || row?.event_id,
      eventIndex
    }
  )
}

function handleStepActionTypeChange() {
  ensureStepParamStructures()
  if (stepDraft.value.actionType === 'right_click') {
    stepDraft.value.params.button = 'right'
  }
}

function applyHotkeyPreset(presetKeys) {
  if (!Array.isArray(presetKeys)) return
  stepDraft.value.params.keys = [...presetKeys]
  stepUi.hotkeyPreset = undefined
}

function resolveAnnotationSource(preferredIndex = stepUi.baselineIndex) {
  const baselines = stepDraft.value.baselineImages || []
  return baselines[preferredIndex] || baselines[0] || stepDraft.value.targetImage || null
}

function openAnnotationDialog(config, applyHandler) {
  const sourceAsset = config.sourceAsset
  const sourceSrc = getAssetPreviewSrc(sourceAsset)
  if (!sourceAsset || !sourceSrc) {
    ElMessage.error('当前步骤缺少可标注图片，请先使用录制生成基准图，或在高级模式中补充图片数据')
    return
  }
  annotationApplyHandler = applyHandler
  Object.assign(annotationDialog, {
    mode: config.mode,
    title: config.title,
    sourceAsset,
    sourceSrc,
    initialCropRect: config.initialCropRect || null,
    initialRegions: cloneData(config.initialRegions || [])
  })
  showAnnotationDialog.value = true
}

function openTargetAnnotation() {
  const sourceAsset = resolveAnnotationSource()
  openAnnotationDialog(
    {
      mode: 'target',
      title: '裁剪目标图',
      sourceAsset,
      initialCropRect: stepDraft.value.targetImage?.region || null
    },
    ({ asset }) => {
      stepDraft.value.targetImage = asset
      stepJson.targetImage = safeJsonStringify(asset)
    }
  )
}

function openBaselineAnnotation(index = stepUi.baselineIndex) {
  stepUi.baselineIndex = index
  const sourceAsset = stepDraft.value.baselineImages?.[index] || resolveAnnotationSource(index)
  openAnnotationDialog(
    {
      mode: 'baseline',
      title: `裁剪基准图 ${stepDraft.value.baselineImages?.[index]?.resolutionKey || index + 1}`,
      sourceAsset,
      initialCropRect: stepDraft.value.baselineImages?.[index]?.region || sourceAsset?.region || null
    },
    ({ asset }) => {
      const baselineImages = [...(stepDraft.value.baselineImages || [])]
      baselineImages[index] = asset
      stepDraft.value.baselineImages = baselineImages
      stepJson.baselineImages = safeJsonStringify(baselineImages)
    }
  )
}

function openMaskAnnotation(index = stepUi.baselineIndex) {
  stepUi.baselineIndex = index
  const sourceAsset = resolveAnnotationSource(index)
  openAnnotationDialog(
    {
      mode: 'mask',
      title: '标注忽略区域',
      sourceAsset,
      initialRegions: stepDraft.value.maskRegions || []
    },
    ({ regions }) => {
      stepDraft.value.maskRegions = regions
      stepJson.maskRegions = safeJsonStringify(regions)
    }
  )
}

function removeBaselineImage(index) {
  stepDraft.value.baselineImages.splice(index, 1)
  if (stepUi.baselineIndex >= stepDraft.value.baselineImages.length) {
    stepUi.baselineIndex = Math.max(stepDraft.value.baselineImages.length - 1, 0)
  }
  stepJson.baselineImages = safeJsonStringify(stepDraft.value.baselineImages)
}

function removeMaskRegion(index) {
  stepDraft.value.maskRegions.splice(index, 1)
  stepJson.maskRegions = safeJsonStringify(stepDraft.value.maskRegions)
}

function handleAnnotationConfirm(payload) {
  if (typeof annotationApplyHandler === 'function') {
    annotationApplyHandler(payload)
  }
  annotationApplyHandler = null
}

async function saveStepDraft() {
  try {
    ensureStepParamStructures()
    if (stepDraft.value.actionType === 'drag') {
      stepDraft.value.params.offset = {
        dx: Number(stepDraft.value.params.endPosition?.x || 0) - Number(stepDraft.value.params.position?.x || 0),
        dy: Number(stepDraft.value.params.endPosition?.y || 0) - Number(stepDraft.value.params.position?.y || 0)
      }
    }
    if (stepDraft.value.actionType === 'right_click') {
      stepDraft.value.params.button = 'right'
    }
    if (stepDraft.value.actionType === 'launch_app') {
      stepDraft.value.params.appArgs = parseArgsText(stepUi.appArgsText)
    }
    stepDraft.value.targetImage = parseJsonText(stepJson.targetImage, null, '目标图片 JSON')
    stepDraft.value.baselineImages = parseJsonText(stepJson.baselineImages, [], '基准图 JSON')
    stepDraft.value.maskRegions = parseJsonText(stepJson.maskRegions, [], '忽略区域 JSON')
    stepDraft.value.compareConfig = parseJsonText(stepJson.compareConfig, {}, '比对配置 JSON')
    const normalizedStep = sanitizeStepForPersist(
      stepDraft.value,
      stepEditorContext.mode === 'case' ? stepEditIndex.value : (stepEditorContext.eventIndex || 1) - 1
    )
    if (stepEditorContext.mode === 'recording') {
      if (!stepEditorContext.recordingId) {
        throw new Error('缺少录制会话ID，无法保存录制步骤')
      }
      loading.stepSave = true
      await updateDesktopRecordingEvent({
        recordingId: stepEditorContext.recordingId,
        eventId: stepEditorContext.eventId,
        eventIndex: stepEditorContext.eventIndex,
        payload: normalizedStep
      })
      ElMessage.success('录制步骤已更新')
      showStepDialog.value = false
      await loadRecordingDetailById(stepEditorContext.recordingId, {
        syncLive: `${recordingForm.value.recordingId}` === `${stepEditorContext.recordingId}`,
        syncDetail: !!recordingDetail.value && `${recordingDetail.value.recordingId}` === `${stepEditorContext.recordingId}`,
        openDialog: false
      })
      getRecordingList()
      return
    }
    form.value.steps.splice(stepEditIndex.value, 1, normalizedStep)
    showStepDialog.value = false
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.stepSave = false
  }
}

function saveCase() {
  if (caseEditorMode.value === 'json') {
    try {
      const parsed = parseJsonText(stepsJsonText.value, [], '步骤 JSON')
      form.value.steps = parsed.map((item, index) => normalizeStep(item, index))
    } catch (error) {
      ElMessage.error(error.message)
      return
    }
  }
  if (!form.value.caseName?.trim()) {
    ElMessage.error('用例名称不能为空')
    return
  }
  if (!form.value.steps.length) {
    ElMessage.error('至少需要一个步骤')
    return
  }
  loading.save = true
  const payload = {
    ...cloneData(form.value),
    appArgs: parseArgsText(form.value.appArgsText),
    runtimeSettings: mergeRuntimeSettingsWithViewport(form.value.runtimeSettings, form.value),
    steps: form.value.steps.map((item, index) => ({
      ...sanitizeStepForPersist(item, index),
      stepIndex: index + 1
    }))
  }
  const request = payload.desktopCaseId ? updateDesktopCase(payload) : addDesktopCase(payload)
  request.then(() => {
    ElMessage.success('保存成功')
    showCaseDialog.value = false
    loadBaseData()
    getList()
  }).finally(() => {
    loading.save = false
  })
}

function openRunDialog(row) {
  selectedCase.value = row
  runForm.value = createRunForm()
  showRunDialog.value = true
}

function openRunHistory(row) {
  activeTab.value = 'run'
  runQueryParams.desktopCaseId = row.desktopCaseId
  runQueryParams.pageNum = 1
  getRunList()
}

function submitRun() {
  if (!selectedCase.value?.desktopCaseId) {
    ElMessage.error('请选择要执行的用例')
    return
  }
  if (!runForm.value.agentId) {
    ElMessage.error('请选择执行 Agent')
    return
  }
  let compareConfig
  try {
    compareConfig = parseOptionalJsonObject(runForm.value.compareConfigText, '执行比对配置')
  } catch (error) {
    ElMessage.error(error.message)
    return
  }
  loading.run = true
  const payload = {
    desktopCaseId: selectedCase.value.desktopCaseId,
    agentId: runForm.value.agentId,
    closeAppOnFinish: runForm.value.closeAppOnFinish
  }
  const runtimeOverrides = {
    ...buildViewportPayload(runForm.value)
  }
  if (compareConfig) {
    runtimeOverrides.compareConfig = compareConfig
  }
  if (Object.keys(runtimeOverrides).length) {
    payload.runtimeOverrides = runtimeOverrides
  }
  runDesktopCase(payload).then((response) => {
    ElMessage.success(response.msg || '执行完成')
    showRunDialog.value = false
    activeTab.value = 'run'
    runQueryParams.desktopCaseId = selectedCase.value.desktopCaseId
    getRunList()
    if (response.data?.desktopCaseRunId) {
      openRunDetail(response.data)
    }
  }).finally(() => {
    loading.run = false
  })
}

function openRunDetail(row) {
  loading.runDetail = true
  getDesktopRun(row.desktopCaseRunId).then((response) => {
    runDetail.value = response.data || null
    showRunDetailDialog.value = true
  }).finally(() => {
    loading.runDetail = false
  })
}

function replaceBaseline(stepRow) {
  if (!runDetail.value?.desktopCaseRunId || !stepRow?.stepId || !stepRow?.currentImage?.assetId) return
  ElMessageBox.confirm('确认使用当前截图替换该步骤基准图吗？', '提示', { type: 'warning' }).then(() => replaceDesktopBaseline({
    desktopCaseRunId: runDetail.value.desktopCaseRunId,
    stepId: stepRow.stepId,
    assetId: stepRow.currentImage.assetId,
    resolutionKey: stepRow.currentImage.resolutionKey
  })).then(() => {
    ElMessage.success('基准图已替换')
    return openRunDetail(runDetail.value)
  }).catch(() => {})
}

function stopRecordingPoll() {
  if (recordingTimer) {
    window.clearInterval(recordingTimer)
    recordingTimer = null
  }
}

function applyRecordingDetail(detail, { syncLive = true, syncDetail = true } = {}) {
  const normalized = normalizeRecordingDetail(detail)
  if (syncDetail) {
    recordingDetail.value = normalized
  }
  if (syncLive) {
    recordingLiveSteps.value = normalized.steps || []
  }
  if ([3, 4, 5].includes(Number(normalized.status))) {
    loading.recordingStop = false
    stopRecordingPoll()
  }
  return normalized
}

function loadRecordingDetailById(recordingId, { syncLive = false, syncDetail = true, openDialog = false } = {}) {
  if (!recordingId) return Promise.resolve(null)
  return getDesktopRecording(recordingId).then((response) => {
    const detail = applyRecordingDetail(response.data || {}, { syncLive, syncDetail })
    if (openDialog) {
      showRecordingDetailDialog.value = true
    }
    return detail
  })
}

function refreshRecording(recordingId = recordingForm.value.recordingId, options = {}) {
  if (!recordingId) return Promise.resolve(null)
  return loadRecordingDetailById(recordingId, {
    syncLive: options.syncLive ?? true,
    syncDetail: options.syncDetail ?? true,
    openDialog: false
  })
}

function openRecordingDialog(row = null) {
  const baseCase = row ? normalizeCase(row) : null
  recordingForm.value = {
    ...createRecordingForm(),
    desktopCaseId: baseCase?.desktopCaseId,
    sessionName: baseCase ? `${baseCase.caseName}-录制` : '',
    appPath: baseCase?.appPath || '',
    appArgsText: baseCase?.appArgsText || '',
    ...createViewportFields(baseCase?.runtimeSettings || {})
  }
  recordingDetail.value = null
  recordingLiveSteps.value = []
  loading.recordingStop = false
  stopRecordingPoll()
  showRecordingDialog.value = true
}

function startRecording() {
  if (!recordingForm.value.agentId) {
    ElMessage.error('请选择执行 Agent')
    return
  }
  loading.recording = true
  startDesktopRecording({
    desktopCaseId: recordingForm.value.desktopCaseId,
    agentId: recordingForm.value.agentId,
    sessionName: recordingForm.value.sessionName || undefined,
    appPath: recordingForm.value.appPath || undefined,
    appArgs: parseArgsText(recordingForm.value.appArgsText),
    recordingOptions: {
      closeAppOnStop: recordingForm.value.closeAppOnStop,
      captureBaselineAfterAction: recordingForm.value.captureBaselineAfterAction,
      captureTargetImage: recordingForm.value.captureTargetImage,
      targetImageSize: recordingForm.value.targetImageSize,
      captureDelayMs: recordingForm.value.captureDelayMs,
      includeKeyboardText: recordingForm.value.includeKeyboardText,
      doubleClickIntervalMs: recordingForm.value.doubleClickIntervalMs,
      dragThresholdPx: recordingForm.value.dragThresholdPx,
      annotationWaitMode: recordingForm.value.annotationWaitMode,
      ...buildViewportPayload(recordingForm.value)
    }
  }).then((response) => {
    recordingForm.value.recordingId = response.data?.recordingId
    loading.recordingStop = false
    ElMessage.success(response.msg || '录制已启动')
    refreshRecording()
    stopRecordingPoll()
    recordingTimer = window.setInterval(() => refreshRecording(), 3000)
    getRecordingList()
  }).finally(() => {
    loading.recording = false
  })
}

function stopRecording() {
  if (!recordingForm.value.recordingId || loading.recordingStop) return
  loading.recordingStop = true
  stopDesktopRecording({
    recordingId: recordingForm.value.recordingId,
    agentId: recordingForm.value.agentId,
    closeAppOnStop: recordingForm.value.closeAppOnStop
  }).then((response) => {
    ElMessage.success(response.msg || '已发送停止录制指令')
    refreshRecording()
    getRecordingList()
  }).catch(() => {
    loading.recordingStop = false
  })
}

function canUseRecordingResult(status) {
  return [3, 4, 5].includes(Number(status))
}

function openRecordingDetail(row) {
  loading.recordingDetail = true
  loadRecordingDetailById(row.recordingId, {
    syncLive: false,
    syncDetail: true,
    openDialog: true
  }).finally(() => {
    loading.recordingDetail = false
  })
}

function openRecordingActionDialog(mode, record) {
  const detailPromise = record?.recordingId && record?.events
    ? Promise.resolve(normalizeRecordingDetail(record))
    : loadRecordingDetailById(record.recordingId, { syncLive: false, syncDetail: false, openDialog: false })
  detailPromise.then((detail) => {
    if (!detail?.recordingId) return
    const sourceCase = caseOptions.value.find((item) => `${item.desktopCaseId}` === `${detail.desktopCaseId}`)
    recordingActionMode.value = mode
    recordingActionForm.value = {
      ...createRecordingActionForm(),
      recordingId: detail.recordingId,
      desktopCaseId: detail.desktopCaseId,
      caseName: `${detail.sessionName || '录制结果'}-${detail.recordingId}`,
      projectId: sourceCase?.projectId,
      moduleId: sourceCase?.moduleId
    }
    showRecordingActionDialog.value = true
  })
}

function submitRecordingAction() {
  if (!recordingActionForm.value.recordingId) return
  loading.recordingAction = true
  const request = recordingActionMode.value === 'create'
    ? saveDesktopRecordingAsCase({
      recordingId: recordingActionForm.value.recordingId,
      caseName: recordingActionForm.value.caseName,
      projectId: recordingActionForm.value.projectId,
      moduleId: recordingActionForm.value.moduleId
    })
    : applyDesktopRecording({
      recordingId: recordingActionForm.value.recordingId,
      desktopCaseId: recordingActionForm.value.desktopCaseId,
      replaceSteps: recordingActionMode.value === 'replace'
    })
  request.then(() => {
    ElMessage.success('操作成功')
    showRecordingActionDialog.value = false
    loadBaseData()
    getList()
    getRecordingList()
  }).finally(() => {
    loading.recordingAction = false
  })
}

function openReplayDialog(record) {
  replayForm.value = {
    ...createReplayForm(),
    recordingId: record.recordingId,
    agentId: record.agentId || record.agent_id || recordingForm.value.agentId,
    ...createViewportFields(record.options || {})
  }
  showReplayDialog.value = true
}

function submitReplay() {
  if (!replayForm.value.recordingId || !replayForm.value.agentId) {
    ElMessage.error('请选择回放 Agent')
    return
  }
  let compareConfig
  try {
    compareConfig = parseOptionalJsonObject(replayForm.value.compareConfigText, '回放比对配置')
  } catch (error) {
    ElMessage.error(error.message)
    return
  }
  loading.replay = true
  const payload = {
    recordingId: replayForm.value.recordingId,
    agentId: replayForm.value.agentId,
    closeAppOnFinish: replayForm.value.closeAppOnFinish
  }
  const runtimeOverrides = {
    ...buildViewportPayload(replayForm.value)
  }
  if (compareConfig) {
    runtimeOverrides.compareConfig = compareConfig
  }
  if (Object.keys(runtimeOverrides).length) {
    payload.runtimeOverrides = runtimeOverrides
  }
  replayDesktopRecording(payload).then((response) => {
    ElMessage.success(response.msg || '回放完成')
    showReplayDialog.value = false
    activeTab.value = 'run'
    getRunList()
  }).finally(() => {
    loading.replay = false
  })
}

watch(() => form.value.projectId, () => {
  if (!formModules.value.some((item) => `${item.moduleId}` === `${form.value.moduleId}`)) {
    form.value.moduleId = undefined
  }
})

watch(() => recordingActionForm.value.projectId, () => {
  if (!actionFormModules.value.some((item) => `${item.moduleId}` === `${recordingActionForm.value.moduleId}`)) {
    recordingActionForm.value.moduleId = undefined
  }
})

watch(showAnnotationDialog, (visible) => {
  if (!visible) {
    annotationApplyHandler = null
  }
})

onMounted(async () => {
  await loadBaseData()
  getList()
  getRunList()
  getRecordingList()
})

onBeforeUnmount(() => {
  stopRecordingPoll()
})
</script>

<style scoped>
.desktopcase-page {
  min-height: calc(100vh - 120px);
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.case-steps-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.case-steps-title {
  font-size: 14px;
  font-weight: 600;
}

.case-steps-actions {
  display: flex;
  gap: 8px;
}

.step-asset-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.recording-live-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.recording-live-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}

.recording-live-tip {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.asset-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 12px;
  background: var(--el-bg-color-page);
}

.asset-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  font-weight: 600;
}

.asset-preview {
  width: 100%;
  max-height: 220px;
  border-radius: 6px;
  border: 1px solid var(--el-border-color);
}

.baseline-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.baseline-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 8px;
  background: var(--el-bg-color);
}

.baseline-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 12px;
}

.baseline-item-actions {
  display: flex;
  gap: 4px;
}

.run-step-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.thumb-image {
  width: 72px;
  height: 72px;
  border-radius: 6px;
  border: 1px solid var(--el-border-color);
}

.preview-image {
  width: 100%;
  max-height: 260px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
}

.image-panel-title {
  margin-bottom: 8px;
  font-weight: 600;
}

.recording-toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.form-tip {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.form-tip-warning {
  margin-bottom: 12px;
  color: var(--el-color-warning-dark-2);
}
</style>
