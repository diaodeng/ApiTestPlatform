<template>
  <div class="app-container ticket-page">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="关键字" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="标题/描述/根因/方案"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="自然语言">
        <el-input
          v-model="naturalKeyword"
          placeholder="如：支付超时且根因是下游接口"
          clearable
          style="width: 260px"
          @keyup.enter="handleNaturalSearch"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="工单状态" clearable style="width: 160px">
          <el-option v-for="item in ticketStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="外部工单号" prop="ticketNo">
        <el-input
          v-model="queryParams.ticketNo"
          placeholder="请输入外部工单号"
          clearable
          style="width: 180px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="处理状态" prop="processStatus">
        <el-select v-model="queryParams.processStatus" placeholder="处理状态" clearable style="width: 180px">
          <el-option v-for="item in ticketProcessStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="提交时间">
        <el-date-picker
          v-model="submitTimeRange"
          type="datetimerange"
          value-format="YYYY-MM-DD HH:mm:ss"
          format="YYYY-MM-DD HH:mm:ss"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          style="width: 360px"
        />
      </el-form-item>
      <el-form-item label="项目" prop="projectId">
        <el-select v-model="queryParams.projectId" placeholder="所属项目" clearable filterable style="width: 180px">
          <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
        </el-select>
      </el-form-item>
      <el-form-item label="模块" prop="moduleId">
        <el-select v-model="queryParams.moduleId" placeholder="所属模块" clearable filterable style="width: 180px">
          <el-option v-for="item in queryModuleOptions" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
        </el-select>
      </el-form-item>
      <el-form-item label="工单类型" prop="issueTypeId">
        <el-select v-model="queryParams.issueTypeId" placeholder="工单类型" clearable filterable style="width: 160px">
          <el-option v-for="item in issueTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="是否问题" prop="isProblem">
        <el-select v-model="queryParams.isProblem" placeholder="是否问题" clearable style="width: 140px">
          <el-option label="真实问题" :value="true" />
          <el-option label="非问题" :value="false" />
        </el-select>
      </el-form-item>
      <el-form-item label="内部优先级" prop="internalPriority">
        <el-select v-model="queryParams.internalPriority" placeholder="内部优先级" clearable style="width: 140px">
          <el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="当前处理人" prop="currentAssigneeId">
        <UserSelect
          v-model="queryParams.currentAssigneeId"
          :initial-option="currentAssigneeOption"
          @change="handleQueryCurrentAssigneeChange"
        />
      </el-form-item>
      <el-form-item label="1线人员" prop="firstLineAssigneeId">
        <UserSelect
          v-model="queryParams.firstLineAssigneeId"
          :initial-option="firstLineQueryAssigneeOption"
          @change="handleQueryFirstLineAssigneeChange"
        />
      </el-form-item>
      <el-form-item label="内部负责人" prop="internalOwnerId">
        <UserSelect
          v-model="queryParams.internalOwnerId"
          :initial-option="internalOwnerQueryOption"
          @change="handleQueryInternalOwnerChange"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleSearch">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['ticket:ticket:add']">
          新增
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="success" plain icon="Upload" @click="importOpen = true" v-hasPermi="['ticket:ticket:import']">
          导入
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="warning" plain icon="Download" @click="downloadTemplate" v-hasPermi="['ticket:ticket:import']">
          下载模板
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <el-table v-loading="loading" :data="ticketList" row-key="ticketId">
      <el-table-column label="工单编号" prop="ticketNo" width="190" show-overflow-tooltip />
      <el-table-column label="标题" prop="title" min-width="240" show-overflow-tooltip />
      <el-table-column label="状态" prop="status" width="120" align="center">
        <template #default="scope">
          <el-tag :type="getStatusTagType(scope.row.status)">
            {{ getOptionLabel(ticketStatusOptions, scope.row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="处理状态" min-width="160" align="center">
        <template #default="scope">
          <el-tag
            v-if="resolveTicketProcessStatus(scope.row).label"
            :type="resolveTicketProcessStatus(scope.row).type"
          >
            {{ resolveTicketProcessStatus(scope.row).label }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="项目" width="160" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.projectName || scope.row.merchantName || '-' }}</template>
      </el-table-column>
      <el-table-column label="模块" prop="moduleName" width="140" show-overflow-tooltip />
      <el-table-column label="工单类型" width="130" show-overflow-tooltip>
        <template #default="scope">{{ formatIssueType(scope.row) }}</template>
      </el-table-column>
      <el-table-column label="问题性质" width="100" align="center">
        <template #default="scope">
          <el-tag v-if="scope.row.isProblem === true" type="danger">真实问题</el-tag>
          <el-tag v-else-if="scope.row.isProblem === false" type="info">非问题</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="对方优先级" prop="customerPriority" width="110" align="center" />
      <el-table-column label="内部优先级" prop="internalPriority" width="110" align="center" />
      <el-table-column label="来源" prop="source" width="110">
        <template #default="scope">{{ getOptionLabel(sourceOptions, scope.row.source) }}</template>
      </el-table-column>
      <el-table-column label="1线人员" prop="firstLineAssigneeName" width="130" show-overflow-tooltip />
      <el-table-column label="内部负责人" prop="internalOwnerName" width="130" show-overflow-tooltip />
      <el-table-column label="当前处理人" prop="currentAssigneeName" width="130" show-overflow-tooltip />
      <el-table-column label="工单提交时间" prop="submitTime" width="170">
        <template #default="scope">{{ parseTime(scope.row.submitTime || scope.row.externalCreateTime || scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="创建时间" prop="createTime" width="170">
        <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="450" fixed="right">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="openDetail(scope.row)" v-hasPermi="['ticket:ticket:query']">
            详情
          </el-button>
          <el-button link type="primary" icon="Search" @click="openTicketLogViewer(scope.row)" v-hasPermi="['ticket:logpull:query']">
            日志
          </el-button>
          <el-button
            v-if="resolveTicketDetailUrl(scope.row)"
            link
            type="info"
            icon="Link"
            @click="openTicketLink(scope.row)"
          >
            跳转
          </el-button>
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['ticket:ticket:edit']">
            编辑
          </el-button>
          <el-button
            link
            type="warning"
            icon="User"
            @click="openAssign(scope.row)"
            v-hasPermi="['ticket:ticket:assign']"
          >
            指派
          </el-button>
          <el-button
            link
            type="success"
            icon="Switch"
            @click="openStatus(scope.row)"
            v-hasPermi="['ticket:ticket:status']"
          >
            流转
          </el-button>
          <el-button
            link
            type="danger"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-hasPermi="['ticket:ticket:remove']"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination
      v-show="total > 0"
      :total="total"
      v-model:page="queryParams.pageNum"
      v-model:limit="queryParams.pageSize"
      @pagination="getList"
    />

    <el-dialog :title="title" v-model="open" width="980px" append-to-body @closed="reset">
      <el-form ref="ticketRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="标题" prop="title">
              <el-input v-model="form.title" placeholder="请输入工单标题" maxlength="500" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工单号" prop="ticketNo">
              <el-input v-model="form.ticketNo" placeholder="请输入外部系统工单号" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属项目" prop="projectId">
              <el-select v-model="form.projectId" placeholder="请选择项目" filterable clearable>
                <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属模块" prop="moduleId">
              <el-select
                v-model="formModuleValue"
                placeholder="请选择或输入模块"
                filterable
                clearable
                allow-create
                default-first-option
                :disabled="!form.projectId"
                @change="handleModuleChange"
              >
                <el-option v-for="item in formModuleOptions" :key="item.moduleId" :label="item.moduleName" :value="String(item.moduleId)" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="版本号" prop="versionKey">
              <el-select
                v-model="form.versionKey"
                placeholder="请选择或输入版本号"
                filterable
                clearable
                allow-create
                default-first-option
                :disabled="!form.projectId"
                style="width: 100%"
              >
                <el-option
                  v-for="item in formVersionOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-divider content-position="left">角色分工</el-divider>
          </el-col>
          <el-col :span="12">
            <el-form-item label="1线人员" prop="firstLineAssigneeId">
              <UserSelect
                v-model="form.firstLineAssigneeId"
                :initial-option="firstLineAssigneeOption"
                :raw-label="form.firstLineAssigneeName"
                @change="handleFirstLineAssigneeChange"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="内部负责人" prop="internalOwnerId">
              <UserSelect
                v-model="form.internalOwnerId"
                :initial-option="internalOwnerOption"
                :raw-label="form.internalOwnerName"
                @change="handleInternalOwnerChange"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="对方优先级" prop="customerPriority">
              <el-select v-model="form.customerPriority" placeholder="请选择">
                <el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="内部优先级" prop="internalPriority">
              <el-select v-model="form.internalPriority" placeholder="请选择">
                <el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="来源" prop="source">
              <el-select v-model="form.source" placeholder="请选择" clearable>
                <el-option v-for="item in sourceOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="严重等级" prop="severity">
              <el-select v-model="form.severity" placeholder="请选择" clearable>
                <el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="工单类型" prop="issueTypeId">
              <el-select v-model="form.issueTypeId" placeholder="请选择工单类型" clearable filterable @change="handleIssueTypeChange">
                <el-option v-for="item in issueTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="是否问题" prop="isProblem">
              <el-select v-model="form.isProblem" placeholder="请选择" clearable>
                <el-option label="真实问题" :value="true" />
                <el-option label="非问题" :value="false" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="标签" prop="tagText">
              <el-input v-model="tagText" placeholder="逗号分隔，如支付,超时" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="描述" prop="description">
              <el-input v-model="form.description" type="textarea" :rows="5" placeholder="请输入问题现象和上下文" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="根因分类">
              <el-select v-model="form.rootCauseType" placeholder="请选择根因分类" clearable filterable>
                <el-option v-for="item in rootCauseTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="解决方式">
              <el-select v-model="form.solutionType" placeholder="请选择解决方式" clearable filterable>
                <el-option v-for="item in solutionTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="根因">
              <el-input v-model="form.rootCause" type="textarea" :rows="3" placeholder="最终根因，可后续RCA同步" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="解决方案">
              <el-input v-model="form.solution" type="textarea" :rows="3" placeholder="最终解决方案，可后续RCA同步" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-divider content-position="left">自动化</el-divider>
          </el-col>
          <el-col :span="12">
            <el-form-item label="创建后拉日志">
              <el-switch v-model="form.needLogPull" inline-prompt active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手动自动翻译">
              <el-switch v-model="form.autoTranslate" inline-prompt active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
          <template v-if="form.needLogPull">
            <LogPullConfigFields
              v-model="form.logPullConfig"
              :field-prefix="'logPullConfig'"
              :vendor-options="vendorOptions"
              :agent-options="agentOptions"
              :provider-options="providerOptions"
              :data-type-options="logPullDataTypeOptions"
              :storage-mode-options="logPullStorageModeOptions"
            />
            <LogPullNotifyConfigFields
              v-model="form.logPullConfig.notifyConfig"
              :field-prefix="'logPullConfig.notifyConfig'"
              :push-options="pushOptions"
            />
          </template>
        </el-row>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" :loading="formSubmitting" :disabled="formSubmitting" @click="submitForm">确 定</el-button>
          <el-button :disabled="formSubmitting" @click="cancel">取 消</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog title="指派工单" v-model="assignOpen" width="520px" append-to-body>
      <el-form ref="assignRef" :model="assignForm" :rules="assignRules" label-width="100px">
        <el-form-item label="处理人ID" prop="toUserId">
          <UserSelect
            v-model="assignForm.toUserId"
            :initial-option="currentAssigneeOption"
            @change="handleAssigneeChange"
          />
        </el-form-item>
        <el-form-item label="处理人名称" prop="toUserName">
          <el-input v-model="assignForm.toUserName" placeholder="选择用户后自动填充，也可手动调整" />
        </el-form-item>
        <el-form-item label="指派原因">
          <el-input v-model="assignForm.reason" type="textarea" :rows="3" placeholder="请输入指派原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="submitAssign">确 定</el-button>
        <el-button @click="assignOpen = false">取 消</el-button>
      </template>
    </el-dialog>

    <el-dialog title="状态流转" v-model="statusOpen" width="640px" append-to-body>
      <el-form ref="statusRef" :model="statusForm" :rules="statusRules" label-width="100px">
        <el-form-item label="目标状态" prop="toStatus">
          <el-select v-model="statusForm.toStatus" placeholder="请选择目标状态">
            <el-option
              v-for="item in statusTransitionOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="是否问题">
          <el-select v-model="statusForm.isProblem" placeholder="请选择" clearable>
            <el-option label="真实问题" :value="true" />
            <el-option label="非问题" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="根因分类">
          <el-select v-model="statusForm.rootCauseType" placeholder="请选择根因分类" clearable filterable>
            <el-option v-for="item in rootCauseTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="解决方式">
          <el-select v-model="statusForm.solutionType" placeholder="请选择解决方式" clearable filterable>
            <el-option v-for="item in solutionTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="关闭结果">
          <el-select v-model="statusForm.resolutionCode" placeholder="关闭时请选择结果" clearable filterable @change="handleResolutionChange">
            <el-option v-for="item in resolutionOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="statusForm.comment" type="textarea" :rows="3" placeholder="请输入状态流转说明" />
        </el-form-item>
        <el-form-item label="根因">
          <el-input v-model="statusForm.rootCause" type="textarea" :rows="2" placeholder="关闭/解决时建议填写" />
        </el-form-item>
        <el-form-item label="解决方案">
          <el-input v-model="statusForm.solution" type="textarea" :rows="2" placeholder="关闭/解决时建议填写" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="submitStatus">确 定</el-button>
        <el-button @click="statusOpen = false">取 消</el-button>
      </template>
    </el-dialog>

    <el-dialog title="导入工单数据" v-model="importOpen" width="720px" append-to-body>
      <el-alert
        title="支持飞书多维表格导出的 xlsx。工单号重复时会跳过，并在导入结果中列出未导入的重复工单号。"
        type="info"
        show-icon
        class="mb16"
      />
      <el-upload
        ref="uploadRef"
        drag
        action="#"
        accept=".xlsx"
        :limit="1"
        :auto-upload="false"
        :http-request="handleImportRequest"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将 Excel 拖到此处，或 <em>点击选择</em></div>
      </el-upload>
      <div v-if="importResult" class="import-result">
        <el-descriptions :column="3" border class="ticket-summary-descriptions">
          <el-descriptions-item label="读取行数">{{ importResult.totalRows }}</el-descriptions-item>
          <el-descriptions-item label="导入成功">{{ importResult.importedCount }}</el-descriptions-item>
          <el-descriptions-item label="已向量化">{{ importResult.embeddingCount }}</el-descriptions-item>
          <el-descriptions-item label="重复跳过">{{ importResult.duplicateCount }}</el-descriptions-item>
          <el-descriptions-item label="失败行">{{ importResult.failedCount }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="importResult.duplicateTicketNos?.length" class="mt12">
          <div class="result-title">重复未导入工单号</div>
          <el-tag v-for="item in importResult.duplicateTicketNos" :key="item" class="mr8 mb8" type="warning">
            {{ item }}
          </el-tag>
        </div>
        <el-table v-if="importResult.failedRows?.length" :data="importResult.failedRows" class="mt12">
          <el-table-column label="行号" prop="row" width="90" />
          <el-table-column label="失败原因" prop="reason" />
        </el-table>
      </div>
      <template #footer>
        <el-button type="primary" :loading="importing" @click="submitImport">开始导入</el-button>
        <el-button @click="importOpen = false">关 闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="detailOpen"
      :title="detailTitle"
      fullscreen
      class="ticket-detail-dialog"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetDetailDialog"
    >
      <template v-if="detail.ticketId">
        <div class="ticket-detail-scroll">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="编号">{{ detail.ticketNo }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTagType(detail.status)">
              {{ getOptionLabel(ticketStatusOptions, detail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="当前处理人">{{ detail.currentAssigneeName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="1线人员">{{ detail.firstLineAssigneeName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="内部负责人">{{ detail.internalOwnerName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="所属项目">{{ detail.projectName || detail.merchantName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="所属模块">{{ detail.moduleName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="工单类型">{{ formatIssueType(detail) }}</el-descriptions-item>
          <el-descriptions-item label="问题性质">{{ formatProblemFlag(detail.isProblem) }}</el-descriptions-item>
          <el-descriptions-item label="根因分类">{{ formatStatOption(rootCauseTypeOptions, detail.rootCauseType) }}</el-descriptions-item>
          <el-descriptions-item label="解决方式">{{ formatStatOption(solutionTypeOptions, detail.solutionType) }}</el-descriptions-item>
          <el-descriptions-item label="关闭结果">{{ formatResolution(detail) }}</el-descriptions-item>
          <el-descriptions-item label="版本号">{{ detail.versionKey || detail.extraData?.versionKey || '-' }}</el-descriptions-item>
          <el-descriptions-item label="日志拉取状态">
            <el-tag
              v-if="detail.latestLogPull?.status"
              :type="getLogPullStatusTagType(detail.latestLogPull.status)"
            >
              {{ detail.latestLogPull.statusDesc || getOptionLabel(logPullStatusOptions, detail.latestLogPull.status) }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="来源">{{ getOptionLabel(sourceOptions, detail.source) }}</el-descriptions-item>
          <el-descriptions-item label="外部链接">
            <el-link
              v-if="resolveTicketDetailUrl(detail)"
              :href="resolveTicketDetailUrl(detail)"
              target="_blank"
              type="primary"
            >
              打开详情
            </el-link>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="对方优先级">{{ detail.customerPriority || '-' }}</el-descriptions-item>
          <el-descriptions-item label="内部优先级">{{ detail.internalPriority || '-' }}</el-descriptions-item>
          <el-descriptions-item label="总耗时">{{ formatSeconds(detail.totalProcessSeconds) }}</el-descriptions-item>
          <el-descriptions-item label="根因" :span="3">{{ detail.rootCause || '-' }}</el-descriptions-item>
          <el-descriptions-item label="解决方案" :span="3">{{ detail.solution || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div class="ticket-detail-description">
          <div class="ticket-detail-description__label">
            <span>描述</span>
            <div class="ticket-detail-description__actions">
              <el-button
                link
                type="primary"
                :loading="descriptionTranslateLoading"
                @click="handleTranslateDescription"
                v-hasPermi="['ticket:ticket:edit']"
              >
                翻译
              </el-button>
              <el-button link type="primary" @click="descriptionExpanded = !descriptionExpanded">
                {{ descriptionExpanded ? '收起' : '展开' }}
              </el-button>
            </div>
          </div>
          <div
            :class="['ticket-detail-description__content', { 'ticket-detail-description__content--collapsed': !descriptionExpanded }]"
          >
            {{ detailOriginalDescription || '-' }}
          </div>
        </div>
        <div v-if="detailAiTranslation" class="ticket-detail-description ticket-detail-translation">
          <div class="ticket-detail-description__label">
            <span>翻译</span>
            <el-button link type="primary" @click="translationExpanded = !translationExpanded">
              {{ translationExpanded ? '收起' : '展开' }}
            </el-button>
          </div>
          <div
            :class="['ticket-detail-description__content', { 'ticket-detail-description__content--collapsed': !translationExpanded }]"
          >
            {{ detailAiTranslation }}
          </div>
        </div>

        <el-tabs v-model="detailMainTab" class="detail-main-tabs" @tab-click="handleDetailTabClick">
          <el-tab-pane label="概览" name="overview" lazy>
            <el-row :gutter="16">
              <el-col :span="16">
                <el-card shadow="never" class="mb16">
                  <template #header>
                    <div class="panel-header">
                      <span>最新AI结论</span>
                      <el-button-group>
                        <el-button type="primary" @click="openAiAnalysisDialog" v-hasPermi="['ticket:ai:analysis:run']">
                          发起AI分析
                        </el-button>
                        <el-button
                          type="info"
                          plain
                          @click="refreshAiAnalysisData"
                          :loading="aiAnalysisRefreshLoading"
                          v-hasPermi="['ticket:ai:analysis:list']"
                        >
                          刷新AI数据
                        </el-button>
                        <el-button @click="openAiTaskHistory" v-hasPermi="['ticket:ai:analysis:list']">
                          查看任务历史
                        </el-button>
                        <el-button type="warning" plain @click="openAiRepoMappingDialog()" v-hasPermi="['ticket:ai:mapping:add']">
                          管理映射
                        </el-button>
                        <el-button type="success" plain @click="openProjectVendorMapDialog()" v-hasPermi="['ticket:logpull:config']">
                          商家映射
                        </el-button>
                      </el-button-group>
                    </div>
                  </template>
                  <el-descriptions :column="2" border>
                    <el-descriptions-item label="最新执行状态">
                      <el-tag v-if="latestAiAnalysisTask?.status" :type="getAiStatusTagType(latestAiAnalysisTask.status)">
                        {{ getAiStatusLabel(latestAiAnalysisTask.status) }}
                      </el-tag>
                      <span v-else>-</span>
                    </el-descriptions-item>
                    <el-descriptions-item label="快照版本">
                      {{ latestSnapshot?.version || '-' }}
                    </el-descriptions-item>
                    <el-descriptions-item label="快照时间">
                      {{ parseTime(latestSnapshot?.createTime) || '-' }}
                    </el-descriptions-item>
                    <el-descriptions-item label="创建人">
                      {{ latestSnapshot?.createdByName || '-' }}
                    </el-descriptions-item>
                    <el-descriptions-item label="摘要" :span="2">{{ latestSnapshot?.summary || '-' }}</el-descriptions-item>
                    <el-descriptions-item label="根因" :span="2">{{ latestSnapshot?.rootCause || '-' }}</el-descriptions-item>
                    <el-descriptions-item label="解决方案" :span="2">{{ latestSnapshot?.solution || '-' }}</el-descriptions-item>
                    <el-descriptions-item label="预防建议" :span="2">{{ latestSnapshot?.prevention || '-' }}</el-descriptions-item>
                    <el-descriptions-item label="风险说明" :span="2">{{ latestSnapshot?.risk || '-' }}</el-descriptions-item>
                    <el-descriptions-item label="负责人" :span="2">{{ latestSnapshot?.owner || '-' }}</el-descriptions-item>
                  </el-descriptions>
                  <el-alert
                    v-if="latestAiAnalysisTask?.errorMessage"
                    type="error"
                    show-icon
                    :title="latestAiAnalysisTask.errorMessage"
                    class="mt16"
                  />
                </el-card>
              </el-col>
              <el-col :span="8">
                <el-card shadow="never">
                  <template #header>相似工单</template>
                  <el-empty v-if="!latestSimilarTickets.length" description="暂无相似工单" />
                  <div v-for="item in latestSimilarTickets" :key="item.ticketId" class="similar-item">
                    <div class="similar-title">{{ item.ticketNo }} {{ item.title }}</div>
                    <div class="similar-meta">
                      <span>相似度 {{ Math.round((item.score || 0) * 100) }}%</span>
                      <span>{{ item.rootCause || '-' }}</span>
                    </div>
                  </div>
                </el-card>
              </el-col>
            </el-row>
          </el-tab-pane>

          <el-tab-pane label="日志拉取" name="logPull" lazy>
            <div class="panel-header mb16">
              <div class="panel-inline">
                <span>拉取记录</span>
                <el-tag v-if="logPullAutoRefreshing" size="small" type="warning">自动刷新中</el-tag>
              </div>
              <div class="panel-inline">
                <PromptButton button-text="参数提示" title="参数配置入口" width="420">
                  <div>
                    日志拉取地址、Cookie、FTP/本地归档配置已统一移到系统参数配置。
                    <br />
                    <code>ticket.logPull.external</code> 管理外部地址与 Cookie。
                    <br />
                    <code>ticket.logPull.storage</code> 管理本地/FTP 与轮询参数。
                  </div>
                </PromptButton>
                <el-button type="primary" @click="openLogPullSubmitDialog" v-hasPermi="['ticket:logpull:add']">拉取日志</el-button>
                <el-button link type="primary" @click="loadLogPullList">刷新</el-button>
              </div>
            </div>
            <el-table v-loading="logPullLoading" :data="logPullList" row-key="id" class="mb16">
              <el-table-column label="创建时间" prop="createTime" width="170">
                <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
              </el-table-column>
              <el-table-column label="数据类型" width="90" align="center">
                <template #default="scope">
                  {{ getOptionLabel(logPullDataTypeOptions, scope.row.commandDataType) }}
                </template>
              </el-table-column>
              <el-table-column label="商家" prop="vendorId" width="110" show-overflow-tooltip />
              <el-table-column label="门店" prop="storeId" min-width="150" show-overflow-tooltip />
              <el-table-column label="POSID" prop="posNo" width="110" show-overflow-tooltip />
              <el-table-column label="状态" min-width="170">
                <template #default="scope">
                  <el-tag :type="getLogPullStatusTagType(scope.row.status)">
                    {{ scope.row.statusDesc || getOptionLabel(logPullStatusOptions, scope.row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="保存方式" width="90" align="center">
                <template #default="scope">{{ getOptionLabel(logPullStorageModeOptions, scope.row.storageMode) }}</template>
              </el-table-column>
              <el-table-column label="归档地址" min-width="220" show-overflow-tooltip>
                <template #default="scope">
                  <el-link v-if="scope.row.storagePath" type="primary" @click="downloadLogPullArchive(scope.row)">
                    {{ scope.row.storagePath }}
                  </el-link>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="原始压缩包" min-width="180" show-overflow-tooltip>
                <template #default="scope">
                  <el-link v-if="scope.row.commandResultUrl" type="primary" @click="downloadLogPullOriginal(scope.row)">
                    下载原始包
                  </el-link>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="摘要/异常" prop="contentSummary" min-width="220" show-overflow-tooltip>
                <template #default="scope">
                  <span>{{ scope.row.errorMessage || scope.row.contentSummary || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="340" fixed="right">
                <template #default="scope">
                  <el-button-group>
                    <el-button
                      link
                      type="primary"
                      @click="viewLogPullContent(scope.row)"
                      :disabled="!scope.row.hasContent || logPullActionLoading"
                    >
                      查看日志
                    </el-button>
                    <el-button
                      link
                      type="warning"
                      @click="retryLogPull(scope.row)"
                      :disabled="logPullActionLoading || activeLogPullStatuses.includes(scope.row.status)"
                      v-hasPermi="['ticket:logpull:add']"
                    >
                      重新拉取
                    </el-button>
                    <el-button
                      link
                      type="success"
                      @click="redownloadLogPull(scope.row)"
                      :disabled="logPullActionLoading || (!scope.row.commandResultUrl && !scope.row.storagePath)"
                      v-hasPermi="['ticket:logpull:add']"
                    >
                      重新下载
                    </el-button>
                    <el-button
                      link
                      type="danger"
                      @click="reextractLogPull(scope.row)"
                      :disabled="logPullActionLoading || (!scope.row.commandResultUrl && !scope.row.storagePath)"
                      v-hasPermi="['ticket:logpull:add']"
                    >
                      重新截取
                    </el-button>
                    <el-button
                      link
                      type="danger"
                      @click="deleteLogPull(scope.row)"
                      :disabled="logPullActionLoading || activeLogPullStatuses.includes(scope.row.status)"
                      v-hasPermi="['ticket:logpull:remove']"
                    >
                      删除
                    </el-button>
                  </el-button-group>
                </template>
              </el-table-column>
            </el-table>
            <pagination
              v-show="logPullTotal > 0"
              :total="logPullTotal"
              v-model:page="logPullQuery.pageNum"
              v-model:limit="logPullQuery.pageSize"
              @pagination="loadLogPullList"
            />
            <el-dialog
              v-model="logPullSubmitOpen"
              title="提交拉取任务"
              width="760px"
              append-to-body
              destroy-on-close
              :close-on-click-modal="false"
              @closed="resetLogPullForm"
            >
              <el-form ref="logPullRef" :model="logPullForm" :rules="logPullRules" label-width="110px">
                <LogPullConfigFields
                  v-model="logPullForm"
                  :vendor-options="vendorOptions"
                  :agent-options="agentOptions"
                  :provider-options="providerOptions"
                  :data-type-options="logPullDataTypeOptions"
                  :storage-mode-options="logPullStorageModeOptions"
                />
                <LogPullNotifyConfigFields
                  v-model="logPullForm.notifyConfig"
                  :push-options="pushOptions"
                />
                <el-form-item>
                  <el-button type="primary" @click="submitLogPull" :loading="logPullSubmitting">提交任务</el-button>
                  <el-button @click="logPullSubmitOpen = false">取消</el-button>
                </el-form-item>
              </el-form>
            </el-dialog>
          </el-tab-pane>

          <el-tab-pane label="协同/AI" name="collab" lazy>
            <div class="collab-toolbar mb16">
              <el-button type="primary" @click="openAiAnalysisDialog" v-hasPermi="['ticket:ai:analysis:run']">
                发起AI分析
              </el-button>
              <el-button @click="openAiTaskHistory" v-hasPermi="['ticket:ai:analysis:list']">
                任务历史
              </el-button>
            </div>
            <el-row :gutter="16">
              <el-col :span="16">
                <el-form :model="messageForm" label-width="90px" class="mb16">
                  <el-row :gutter="12">
                    <el-col :span="8">
                      <el-form-item label="角色">
                        <el-select v-model="messageForm.role">
                          <el-option label="提问人" value="user" />
                          <el-option label="AI" value="ai" />
                          <el-option label="开发" value="developer" />
                          <el-option label="测试" value="tester" />
                          <el-option label="系统" value="system" />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="类型">
                        <el-select v-model="messageForm.messageType">
                          <el-option label="追问" value="question" />
                          <el-option label="分析" value="analysis" />
                          <el-option label="日志" value="log" />
                          <el-option label="结论" value="conclusion" />
                          <el-option label="动作" value="action" />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="发起AI">
                        <el-switch v-model="messageForm.runAi" inline-prompt active-text="是" inactive-text="否" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="24">
                      <el-alert
                        :title="`协同消息默认沿用工单版本号：${detail.versionKey || detail.extraData?.versionKey || '-'}。`"
                        type="info"
                        show-icon
                        :closable="false"
                        class="mb12"
                      />
                    </el-col>
                    <el-col :span="24">
                      <el-form-item label="版本号">
                        <el-select
                          v-model="messageForm.versionKey"
                          placeholder="请选择或输入版本号"
                          filterable
                          clearable
                          allow-create
                          default-first-option
                          style="width: 100%"
                        >
                          <el-option
                            v-for="item in detailVersionOptions"
                            :key="item.value"
                            :label="item.label"
                            :value="item.value"
                          />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="24">
                      <el-form-item label="Agent">
                        <el-select v-model="messageForm.agentCode" placeholder="可选" filterable clearable>
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
                      <el-form-item label="Provider">
                        <el-select v-model="messageForm.aiProviderCode" placeholder="可选" filterable clearable style="width: 100%">
                          <el-option
                            v-for="item in providerOptions"
                            :key="item.providerCode"
                            :label="`${item.providerName || item.providerCode} [${item.providerCode}] ${item.modelName ? `- ${item.modelName}` : ''}`"
                            :value="item.providerCode"
                          />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="24">
                      <el-form-item label="内容">
                        <el-input v-model="messageForm.content" type="textarea" :rows="4" placeholder="补充追问、开发反馈、排查动作或AI结论" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="24">
                      <el-form-item label="附件JSON">
                        <el-input v-model="messageDataText" type="textarea" :rows="3" placeholder='可选，如 {"traceIds":["..."],"evidence":"..."}' />
                      </el-form-item>
                    </el-col>
                    <el-col :span="24">
                      <el-form-item>
                        <el-button type="primary" @click="submitMessage" v-hasPermi="['ticket:message:add']">提交消息</el-button>
                        <el-button @click="resetMessageForm">重置</el-button>
                        <el-button type="success" plain @click="saveSnapshotFromCurrentState" v-hasPermi="['ticket:snapshot:add']">
                          生成快照
                        </el-button>
                        <el-button type="warning" plain @click="generateKnowledgeFromTicket" v-hasPermi="['ticket:knowledge:add']">
                          生成知识库
                        </el-button>
                      </el-form-item>
                    </el-col>
                  </el-row>
                </el-form>

                <el-card shadow="never">
                  <template #header>消息流</template>
                  <el-empty v-if="!messageItems.length" description="暂无消息" />
                  <div v-for="item in messageItems" :key="item.id" class="mb12">
                    <div class="record-head">
                      <span>{{ item.roleLabel }}</span>
                      <el-tag size="small">{{ item.typeLabel }}</el-tag>
                      <span>{{ parseTime(item.createTime) }}</span>
                    </div>
                    <div>{{ item.content || '-' }}</div>
                    <pre v-if="item.attachments" class="json-block">{{ formatJson(item.attachments) }}</pre>
                  </div>
                </el-card>
              </el-col>
              <el-col :span="8">
                <el-card shadow="never">
                  <template #header>相似工单</template>
                  <el-empty v-if="!similarTickets.length" description="暂无相似工单" />
                  <div v-for="item in similarTickets" :key="item.ticketId" class="similar-item">
                    <div class="similar-title">{{ item.ticketNo }} {{ item.title }}</div>
                    <div class="similar-meta">
                      <span>相似度 {{ Math.round((item.score || 0) * 100) }}%</span>
                      <span>{{ item.rootCause || '-' }}</span>
                    </div>
                  </div>
                </el-card>
              </el-col>
            </el-row>
          </el-tab-pane>

          <el-tab-pane label="评论" name="comments" lazy>
            <el-form :model="commentForm" label-width="80px" class="mb16">
              <el-form-item label="评论">
                <el-input v-model="commentForm.content" type="textarea" :rows="3" placeholder="请输入沟通评论" />
              </el-form-item>
              <el-form-item>
                <el-checkbox v-model="commentForm.isInternal">内部评论</el-checkbox>
                <el-button type="primary" class="ml12" @click="submitComment" v-hasPermi="['ticket:comment:add']">
                  提交评论
                </el-button>
              </el-form-item>
            </el-form>
            <div v-loading="commentLoading">
              <el-empty v-if="!commentList.length" description="暂无评论" />
              <el-card v-for="item in commentList" :key="item.id" shadow="never" class="mb8">
                <div class="record-head">
                  <span>{{ item.userName || '-' }}</span>
                  <el-tag v-if="item.isInternal" size="small" type="warning">内部</el-tag>
                  <span>{{ parseTime(item.createTime) }}</span>
                </div>
                <div>{{ item.content }}</div>
              </el-card>
            </div>
          </el-tab-pane>

          <el-tab-pane label="历史" name="history" lazy>
            <el-tabs v-model="historyActiveTab" class="history-entry-tabs" @tab-click="handleHistoryTabClick">
              <el-tab-pane label="时间线" name="timeline" lazy>
                <el-timeline>
                  <el-timeline-item
                    v-for="item in timelineItems"
                    :key="item.key"
                    :timestamp="parseTime(item.time)"
                    placement="top"
                  >
                    <el-card shadow="never">
                      <div class="timeline-title">{{ item.title }}</div>
                      <div class="timeline-content">{{ item.content || '-' }}</div>
                    </el-card>
                  </el-timeline-item>
                </el-timeline>
              </el-tab-pane>
              <el-tab-pane label="排查事件" name="events" lazy>
                <el-form :model="eventForm" label-width="90px" class="mb16">
                  <el-form-item label="事件类型">
                    <el-select v-model="eventForm.eventType" placeholder="请选择">
                      <el-option v-for="item in eventTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="事件说明">
                    <el-input v-model="eventForm.content" type="textarea" :rows="3" placeholder="记录查了什么、结论是什么" />
                  </el-form-item>
                  <el-form-item label="结构化数据">
                    <el-input
                      v-model="eventDataText"
                      type="textarea"
                      :rows="4"
                      placeholder='JSON，如 {"traceIds":["abc"],"checkedServices":["order-api"]}'
                    />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" @click="submitEvent" v-hasPermi="['ticket:event:add']">提交事件</el-button>
                  </el-form-item>
                </el-form>
                <el-empty v-if="!timeline.events?.length" description="暂无事件" />
                <el-card v-for="item in timeline.events" :key="item.id" shadow="never" class="mb8">
                  <div class="record-head">
                    <span>{{ item.eventType }}</span>
                    <span>{{ item.operatorName || '-' }}</span>
                    <span>{{ parseTime(item.createTime) }}</span>
                  </div>
                  <div>{{ item.content || '-' }}</div>
                  <pre v-if="item.eventData" class="json-block">{{ formatJson(item.eventData) }}</pre>
                </el-card>
              </el-tab-pane>
              <el-tab-pane label="RCA" name="rca" lazy>
                <el-form ref="rcaRef" :model="rcaForm" label-width="100px">
                  <el-form-item label="问题现象">
                    <el-input v-model="rcaForm.symptom" type="textarea" :rows="2" />
                  </el-form-item>
                  <el-form-item label="影响范围">
                    <el-input v-model="rcaForm.impactScope" type="textarea" :rows="2" />
                  </el-form-item>
                  <el-form-item label="复现步骤">
                    <el-input v-model="rcaForm.reproduceSteps" type="textarea" :rows="3" />
                  </el-form-item>
                  <el-form-item label="排查过程">
                    <el-input v-model="rcaForm.investigationProcess" type="textarea" :rows="4" />
                  </el-form-item>
                  <el-form-item label="根因分类">
                    <el-select v-model="rcaForm.rootCauseCategory" placeholder="请选择根因分类" clearable filterable>
                      <el-option v-for="item in rootCauseTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="根因详情">
                    <el-input v-model="rcaForm.rootCauseDetail" type="textarea" :rows="3" />
                  </el-form-item>
                  <el-form-item label="修复方案">
                    <el-input v-model="rcaForm.fixSolution" type="textarea" :rows="3" />
                  </el-form-item>
                  <el-form-item label="验证方式">
                    <el-input v-model="rcaForm.verifyMethod" type="textarea" :rows="2" />
                  </el-form-item>
                  <el-form-item label="长期预防">
                    <el-input v-model="rcaForm.preventionSolution" type="textarea" :rows="3" />
                  </el-form-item>
                  <el-form-item>
                    <el-button type="primary" @click="submitRca" v-hasPermi="['ticket:rca:edit']">保存RCA</el-button>
                  </el-form-item>
                </el-form>
              </el-tab-pane>
              <el-tab-pane v-if="false" label="日志拉取" name="logPull" lazy>
                <div class="panel-header mb16">
                  <div class="panel-inline">
                    <span>拉取记录</span>
                    <el-tag v-if="logPullAutoRefreshing" size="small" type="warning">自动刷新中</el-tag>
                  </div>
                  <div class="panel-inline">
                    <PromptButton button-text="参数提示" title="参数配置入口" width="420">
                      <div>
                        日志拉取地址、Cookie、FTP/本地归档配置已统一移到系统参数配置。
                        <br />
                        <code>ticket.logPull.external</code> 管理外部地址与 Cookie。
                        <br />
                        <code>ticket.logPull.storage</code> 管理本地/FTP 与轮询参数。
                      </div>
                    </PromptButton>
                    <el-button type="primary" @click="openLogPullSubmitDialog" v-hasPermi="['ticket:logpull:add']">拉取日志</el-button>
                    <el-button link type="primary" @click="loadLogPullList">刷新</el-button>
                  </div>
                </div>
                <el-table v-loading="logPullLoading" :data="logPullList" row-key="id" class="mb16">
                  <el-table-column label="创建时间" prop="createTime" width="170">
                    <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
                  </el-table-column>
                  <el-table-column label="数据类型" width="90" align="center">
                    <template #default="scope">
                      {{ getOptionLabel(logPullDataTypeOptions, scope.row.commandDataType) }}
                    </template>
                  </el-table-column>
                  <el-table-column label="商家" prop="vendorId" width="110" show-overflow-tooltip />
                  <el-table-column label="门店" prop="storeId" min-width="150" show-overflow-tooltip />
                  <el-table-column label="POSID" prop="posNo" width="110" show-overflow-tooltip />
                  <el-table-column label="状态" min-width="170">
                    <template #default="scope">
                      <el-tag :type="getLogPullStatusTagType(scope.row.status)">
                        {{ scope.row.statusDesc || getOptionLabel(logPullStatusOptions, scope.row.status) }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="保存方式" width="90" align="center">
                    <template #default="scope">{{ getOptionLabel(logPullStorageModeOptions, scope.row.storageMode) }}</template>
                  </el-table-column>
                  <el-table-column label="归档地址" min-width="220" show-overflow-tooltip>
                    <template #default="scope">
                      <el-link v-if="scope.row.storagePath" type="primary" @click="downloadLogPullArchive(scope.row)">
                        {{ scope.row.storagePath }}
                      </el-link>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="原始压缩包" min-width="180" show-overflow-tooltip>
                    <template #default="scope">
                      <el-link v-if="scope.row.commandResultUrl" type="primary" @click="downloadLogPullOriginal(scope.row)">
                        下载原始包
                      </el-link>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="摘要/异常" prop="contentSummary" min-width="220" show-overflow-tooltip>
                    <template #default="scope">
                      <span>{{ scope.row.errorMessage || scope.row.contentSummary || '-' }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="280" fixed="right">
                    <template #default="scope">
                      <el-button-group>
                        <el-button
                          link
                          type="primary"
                          @click="viewLogPullContent(scope.row)"
                          :disabled="!scope.row.hasContent || logPullActionLoading"
                        >
                          查看日志
                        </el-button>
                        <el-button
                          link
                          type="warning"
                          @click="retryLogPull(scope.row)"
                          :disabled="logPullActionLoading || activeLogPullStatuses.includes(scope.row.status)"
                          v-hasPermi="['ticket:logpull:add']"
                        >
                          重新拉取
                        </el-button>
                        <el-button
                          link
                          type="success"
                          @click="redownloadLogPull(scope.row)"
                          :disabled="logPullActionLoading || (!scope.row.commandResultUrl && !scope.row.storagePath)"
                          v-hasPermi="['ticket:logpull:add']"
                        >
                          重新下载
                        </el-button>
                        <el-button
                          link
                          type="danger"
                          @click="reextractLogPull(scope.row)"
                          :disabled="logPullActionLoading || (!scope.row.commandResultUrl && !scope.row.storagePath)"
                          v-hasPermi="['ticket:logpull:add']"
                        >
                          重新截取
                        </el-button>
                      </el-button-group>
                    </template>
                  </el-table-column>
                </el-table>
                <pagination
                  v-show="logPullTotal > 0"
                  :total="logPullTotal"
                  v-model:page="logPullQuery.pageNum"
                  v-model:limit="logPullQuery.pageSize"
                  @pagination="loadLogPullList"
                />
                <el-dialog
                  v-model="logPullSubmitOpen"
                  title="提交拉取任务"
                  width="760px"
                  append-to-body
                  destroy-on-close
                  :close-on-click-modal="false"
                  @closed="resetLogPullForm"
                >
                  <el-form ref="logPullRef" :model="logPullForm" :rules="logPullRules" label-width="110px">
                    <el-form-item label="vendorId" prop="vendorId">
                      <el-select
                        v-model="logPullForm.vendorId"
                        placeholder="选择或输入商家"
                        clearable
                        filterable
                        allow-create
                        default-first-option
                        @change="handleLogPullVendorChange"
                      >
                        <el-option
                          v-for="item in vendorOptions"
                          :key="item.vendorId"
                          :label="item.label"
                          :value="item.vendorId"
                        />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="storeId" prop="storeId">
                      <el-select
                        v-model="logPullForm.storeId"
                        placeholder="选择或输入门店"
                        clearable
                        filterable
                        allow-create
                        default-first-option
                      >
                        <el-option
                          v-for="item in logPullStoreOptions"
                          :key="item.storeId"
                          :label="item.label"
                          :value="item.storeId"
                        />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="posNo" prop="posNo">
                      <el-input-number v-model="logPullForm.posNo" :min="1" controls-position="right" />
                    </el-form-item>
                    <el-form-item label="数据类型" prop="commandDataType">
                      <el-select v-model="logPullForm.commandDataType" placeholder="请选择">
                        <el-option
                          v-for="item in logPullDataTypeOptions"
                          :key="item.value"
                          :label="item.label"
                          :value="item.value"
                        />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="modifyTime">
                      <el-date-picker
                        v-model="logPullForm.modifyTime"
                        type="date"
                        value-format="YYYY-MM-DD"
                        placeholder="按日期拉取"
                        clearable
                      />
                    </el-form-item>
                    <el-form-item label="path">
                      <el-input v-model="logPullForm.path" placeholder="可选，按路径拉取" clearable />
                    </el-form-item>
                    <el-form-item label="时间方式">
                      <el-radio-group v-model="logPullForm.timeRangeMode">
                        <el-radio value="between">开始 + 结束</el-radio>
                        <el-radio value="point">时间点 + 前后范围</el-radio>
                      </el-radio-group>
                    </el-form-item>
                    <template v-if="logPullForm.timeRangeMode === 'between'">
                      <el-form-item label="开始时间">
                        <el-date-picker
                          v-model="logPullForm.logBeginTime"
                          type="datetime"
                          value-format="YYYY-MM-DD HH:mm:ss"
                          placeholder="必填，筛选日志开始时间"
                          clearable
                        />
                      </el-form-item>
                      <el-form-item label="结束时间">
                        <el-date-picker
                          v-model="logPullForm.logEndTime"
                          type="datetime"
                          value-format="YYYY-MM-DD HH:mm:ss"
                          placeholder="必填，筛选日志结束时间"
                          clearable
                        />
                      </el-form-item>
                    </template>
                    <template v-else>
                      <el-form-item label="时间点">
                        <el-date-picker
                          v-model="logPullForm.logPointTime"
                          type="datetime"
                          value-format="YYYY-MM-DD HH:mm:ss"
                          placeholder="必填，基准时间点"
                          clearable
                        />
                      </el-form-item>
                      <el-form-item label="前后范围">
                        <div class="time-range-inline">
                          <span>前</span>
                          <el-input-number v-model="logPullForm.rangeBeforeMinutes" :min="0" controls-position="right" />
                          <span>分钟，后</span>
                          <el-input-number v-model="logPullForm.rangeAfterMinutes" :min="0" controls-position="right" />
                          <span>分钟</span>
                        </div>
                      </el-form-item>
                    </template>
                    <el-form-item label="单文件上限">
                      <el-input-number v-model="logPullForm.fileMaxSize" :min="1" controls-position="right" />
                    </el-form-item>
                    <el-form-item label="压缩包上限">
                      <el-input-number v-model="logPullForm.zipMaxSize" :min="1" controls-position="right" />
                    </el-form-item>
                    <el-form-item label="保存方式">
                      <el-select v-model="logPullForm.storageMode" placeholder="请选择">
                        <el-option
                          v-for="item in logPullStorageModeOptions"
                          :key="item.value"
                          :label="item.label"
                          :value="item.value"
                        />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="自动AI">
                      <el-switch v-model="logPullForm.autoAiEnabled" inline-prompt active-text="是" inactive-text="否" />
                    </el-form-item>
                    <el-form-item label="AI Agent">
                      <el-select
                        v-model="logPullForm.aiAgentCode"
                        placeholder="请选择Agent"
                        filterable
                        clearable
                        :disabled="!logPullForm.autoAiEnabled"
                      >
                        <el-option
                          v-for="item in agentOptions"
                          :key="item.agentCode"
                          :label="`${item.agentName || item.agentCode} [${item.agentCode}]`"
                          :value="item.agentCode"
                        />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="通知配置">
                      <el-select
                        v-model="logPullForm.notifyConfig.pushIds"
                        multiple
                        filterable
                        clearable
                        placeholder="选择已有推送配置"
                      >
                        <el-option
                          v-for="item in pushOptions"
                          :key="item.pushId"
                          :label="`${item.name || item.pushId} [${item.pushId}]`"
                          :value="item.pushId"
                        />
                      </el-select>
                    </el-form-item>
                  </el-form>
                  <template #footer>
                    <el-button @click="logPullSubmitOpen = false">取消</el-button>
                    <el-button
                      type="primary"
                      :loading="logPullSubmitting"
                      @click="submitLogPull"
                      v-hasPermi="['ticket:logpull:add']"
                    >
                      提交拉取
                    </el-button>
                  </template>
                </el-dialog>
              </el-tab-pane>
            </el-tabs>
          </el-tab-pane>
        </el-tabs>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="aiAnalysisOpen"
      title="发起AI分析"
      width="620px"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetAiAnalysisDialog"
    >
        <el-form ref="aiAnalysisRef" :model="aiAnalysisTaskForm" :rules="aiAnalysisRules" label-width="110px">
        <el-form-item label="版本号" prop="versionKey">
          <el-select
            v-model="aiAnalysisTaskForm.versionKey"
            placeholder="请选择或输入版本号，系统将按工单所属项目 + 版本号自动匹配仓库映射"
            filterable
            clearable
            allow-create
            default-first-option
            style="width: 100%"
          >
            <el-option
              v-for="item in detailVersionOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Agent">
          <el-select v-model="aiAnalysisTaskForm.agentCode" placeholder="可选，优先使用指定Agent" filterable clearable>
            <el-option
              v-for="item in agentOptions"
              :key="item.agentCode"
              :label="`${item.agentName || item.agentCode} [${item.agentCode}]`"
              :value="item.agentCode"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Provider">
          <el-select v-model="aiAnalysisTaskForm.aiProviderCode" placeholder="可选，优先使用指定Provider" filterable clearable style="width: 100%">
            <el-option
              v-for="item in providerOptions"
              :key="item.providerCode"
              :label="`${item.providerName || item.providerCode} [${item.providerCode}] ${item.modelName ? `- ${item.modelName}` : ''}`"
              :value="item.providerCode"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="强制刷新">
          <el-switch v-model="aiAnalysisTaskForm.forceRefresh" />
        </el-form-item>
        <el-form-item label="额外说明">
          <el-input
            v-model="aiAnalysisTaskForm.extraInstruction"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
            placeholder="可填写本次分析的额外重点，例如优先排查的链路、已知异常现象、需要忽略的噪声等"
          />
        </el-form-item>
        <el-form-item label="追加提示词">
          <el-select
            v-model="aiAnalysisTaskForm.promptTemplateCodes"
            placeholder="可选，选择后会追加到当前分析提示词中"
            multiple
            filterable
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="item in analysisPromptOptions"
              :key="item.templateCode"
              :label="`${item.templateName || item.templateCode} [${item.templateCode}]`"
              :value="item.templateCode"
            />
          </el-select>
        </el-form-item>
        <el-alert
          :title="aiPromptHintTitle"
          :description="aiPromptHintDesc"
          type="info"
          show-icon
        />
      </el-form>
      <template #footer>
        <el-button @click="aiAnalysisOpen = false">取消</el-button>
        <el-button type="primary" :loading="aiAnalysisSubmitting" @click="submitAiAnalysis" v-hasPermi="['ticket:ai:analysis:run']">
          提交分析
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="aiTaskHistoryOpen"
      title="AI任务历史"
      width="1100px"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div class="panel-header mb16">
        <div class="panel-inline">
          <span>任务列表</span>
          <el-tag v-if="aiTaskTotal">{{ aiTaskTotal }} 条</el-tag>
        </div>
        <el-button link type="primary" @click="loadAiAnalysisTasks" :loading="aiTaskLoading">刷新</el-button>
      </div>
      <el-table v-loading="aiTaskLoading" :data="aiTaskList" row-key="taskId">
        <el-table-column label="提交时间" prop="createTime" width="170">
          <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="scope">
            <el-tag :type="getAiStatusTagType(scope.row.status)">{{ getAiStatusLabel(scope.row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="版本" prop="versionKey" width="120" show-overflow-tooltip />
        <el-table-column label="提交人" prop="submittedByName" width="120" show-overflow-tooltip />
        <el-table-column label="完成时间" prop="finishedAt" width="170">
          <template #default="scope">{{ parseTime(scope.row.finishedAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="openAiTaskDetail(scope.row)">查看原文</el-button>
            <el-button
              v-if="canRetryAiTask(scope.row)"
              link
              type="warning"
              :loading="aiAnalysisRetryLoading"
              @click="retryAiAnalysisTask(scope.row)"
              v-hasPermi="['ticket:ai:analysis:run']"
            >
              重试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <pagination
        v-show="aiTaskTotal > 0"
        :total="aiTaskTotal"
        v-model:page="aiTaskQuery.pageNum"
        v-model:limit="aiTaskQuery.pageSize"
        @pagination="loadAiAnalysisTasks"
      />
      <template #footer>
        <el-button @click="aiTaskHistoryOpen = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="aiTaskDetailOpen"
      title="AI任务原文"
      width="980px"
      top="4vh"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-descriptions :column="2" border class="mb16">
        <el-descriptions-item label="任务ID">{{ aiTaskDetailPayload.taskId || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag v-if="aiTaskDetailPayload.status" :type="getAiStatusTagType(aiTaskDetailPayload.status)">
            {{ getAiStatusLabel(aiTaskDetailPayload.status) }}
          </el-tag>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="版本">{{ aiTaskDetailPayload.versionKey || '-' }}</el-descriptions-item>
        <el-descriptions-item label="Agent">{{ aiTaskDetailPayload.agentCode || '-' }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ parseTime(aiTaskDetailPayload.createTime) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ parseTime(aiTaskDetailPayload.finishedAt || aiTaskDetailPayload.updateTime) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="仓库地址" :span="2">{{ aiTaskDetailPayload.repoUrl || '-' }}</el-descriptions-item>
        <el-descriptions-item label="分支名称" :span="2">{{ aiTaskDetailPayload.branchName || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-alert
        v-if="aiTaskDetailPayload.errorMessage"
        type="error"
        show-icon
        :title="aiTaskDetailPayload.errorMessage"
        class="mb16"
      />
      <el-tabs class="task-detail-tabs">
        <el-tab-pane label="提示词">
          <pre class="json-block task-detail-block">{{ aiTaskDetailPayload.promptText || '-' }}</pre>
        </el-tab-pane>
        <el-tab-pane label="原始输出">
          <pre class="json-block task-detail-block">{{ aiTaskDetailPayload.rawOutput || '-' }}</pre>
        </el-tab-pane>
        <el-tab-pane label="分析结果">
          <pre class="json-block task-detail-block">{{ aiTaskDetailPayload.analysisResult ? formatJson(aiTaskDetailPayload.analysisResult) : '-' }}</pre>
        </el-tab-pane>
        <el-tab-pane label="上下文">
          <pre class="json-block task-detail-block">{{ aiTaskDetailPayload.analysisContext ? formatJson(aiTaskDetailPayload.analysisContext) : '-' }}</pre>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="aiTaskDetailOpen = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="aiRepoMappingOpen"
      title="仓库映射"
      width="760px"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetAiRepoMappingForm"
    >
      <el-form ref="aiRepoMappingRef" :model="aiRepoMappingForm" :rules="aiRepoMappingRules" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="项目" prop="projectId">
              <el-select v-model="aiRepoMappingForm.projectId" placeholder="请选择项目" filterable style="width: 100%">
                <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="版本标识" prop="versionKey">
              <el-input v-model="aiRepoMappingForm.versionKey" placeholder="例如 release/2.1.3" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="仓库地址" prop="repoUrl">
              <el-input v-model="aiRepoMappingForm.repoUrl" placeholder="git@gitlab.xxx/project.git" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分支名称" prop="branchName">
              <el-input v-model="aiRepoMappingForm.branchName" placeholder="release/2.1.3" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="本地仓库" prop="localRepoPath">
              <el-input v-model="aiRepoMappingForm.localRepoPath" placeholder="留空则使用 Agent 本地配置" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作区根目录">
              <el-input v-model="aiRepoMappingForm.workspaceRoot" placeholder="留空则使用 Agent 本地配置" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Worker命令">
              <el-input v-model="aiRepoMappingForm.workerCommand" placeholder="留空则使用系统默认 codex exec" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="默认映射">
              <el-switch v-model="aiRepoMappingForm.isDefault" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用状态">
              <el-switch v-model="aiRepoMappingForm.enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="aiRepoMappingForm.remark" type="textarea" :rows="3" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="aiRepoMappingOpen = false">取消</el-button>
        <el-button type="primary" :loading="aiRepoMappingSubmitting" @click="submitAiRepoMapping">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="projectVendorMapOpen"
      title="商家映射"
      width="520px"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="resetProjectVendorMapForm"
    >
      <div v-loading="projectVendorMapLoading">
        <el-form ref="projectVendorMapRef" :model="projectVendorMapForm" :rules="projectVendorMapRules" label-width="110px">
          <el-form-item label="项目">
            <el-select v-model="projectVendorMapForm.projectId" placeholder="项目" filterable style="width: 100%" disabled>
              <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
            </el-select>
          </el-form-item>
          <el-form-item label="项目名称">
            <el-input v-model="projectVendorMapForm.projectName" disabled />
          </el-form-item>
          <el-form-item label="商户编号" prop="venderNo">
            <el-input v-model="projectVendorMapForm.venderNo" placeholder="请输入 vender_no" maxlength="30" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="projectVendorMapOpen = false">取消</el-button>
        <el-button type="primary" :loading="projectVendorMapSubmitting" @click="submitProjectVendorMap">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="logPullContentOpen"
      title="日志内容"
      width="80%"
      top="5vh"
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      @closed="handleLogPullDialogClosed"
    >
      <div v-loading="logPullContentLoading">
        <el-descriptions :column="3" border class="mb16">
          <el-descriptions-item label="记录ID">{{ selectedLogPullRecord?.id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="查看模式">{{ formatLogViewSource(selectedLogPullContent?.viewSource) }}</el-descriptions-item>
          <el-descriptions-item label="本次截取范围">
            {{ formatLogViewRange(selectedLogPullContent?.viewBeginTime, selectedLogPullContent?.viewEndTime) }}
          </el-descriptions-item>
          <el-descriptions-item label="命中条目">{{ selectedLogPullContent?.matchedEntryCount || 0 }}</el-descriptions-item>
          <el-descriptions-item label="压缩包文件数">{{ selectedLogPullContent?.archiveEntryCount || 0 }}</el-descriptions-item>
          <el-descriptions-item label="日志字符数">{{ selectedLogPullContent?.contentCharCount || 0 }}</el-descriptions-item>
          <el-descriptions-item label="归档地址" :span="2">
            {{ selectedLogPullContent?.storagePath || '-' }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="panel-header mb16 log-view-controls">
          <el-radio-group v-model="logPullViewForm.viewMode">
            <el-radio value="stored">入库内容</el-radio>
            <el-radio value="archive">原始文档</el-radio>
          </el-radio-group>
          <el-date-picker
            v-model="logPullViewForm.logBeginTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="开始时间"
            clearable
            :disabled="logPullViewForm.viewMode !== 'archive'"
            class="log-view-time-picker"
          />
          <span>至</span>
          <el-date-picker
            v-model="logPullViewForm.logEndTime"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="结束时间"
            clearable
            :disabled="logPullViewForm.viewMode !== 'archive'"
            class="log-view-time-picker"
          />
          <el-input v-model="logPullKeyword" placeholder="本地过滤关键字，按日志块筛选" clearable class="log-filter-input" />
          <el-switch
            v-model="logPullWrapEnabled"
            inline-prompt
            active-text="换行"
            inactive-text="不换行"
          />
          <el-button type="primary" @click="refreshLogPullContent">
            {{ logPullViewForm.viewMode === 'archive' ? '按当前范围查看' : '查看入库内容' }}
          </el-button>
          <el-button type="warning" @click="retryLogPull(selectedLogPullRecord)" :disabled="logPullActionLoading" v-hasPermi="['ticket:logpull:add']">
            重新拉取
          </el-button>
          <el-button
            type="success"
            @click="redownloadLogPull(selectedLogPullRecord)"
            :disabled="logPullActionLoading || (!selectedLogPullRecord?.commandResultUrl && !selectedLogPullRecord?.storagePath)"
            v-hasPermi="['ticket:logpull:add']"
          >
            重新下载
          </el-button>
          <el-button
            type="danger"
            @click="reextractLogPull(selectedLogPullRecord)"
            :disabled="logPullActionLoading || logPullViewForm.viewMode !== 'archive'"
            v-hasPermi="['ticket:logpull:add']"
          >
            重新截取
          </el-button>
          <el-button link type="primary" @click="resetLogPullViewRange">恢复记录范围</el-button>
        </div>
        <el-divider content-position="left">日志搜索</el-divider>
        <div class="panel-header mb16 log-view-controls">
          <el-input v-model="logViewerForm.keyword" placeholder="关键词搜索" clearable class="log-search-input" @keyup.enter="searchLogViewerKeyword" />
          <el-input v-model="logViewerForm.time" placeholder="时间搜索，如 14:32" clearable class="log-time-input" @keyup.enter="searchLogViewerTime" />
          <span>上下文</span>
          <el-input-number v-model="logViewerForm.contextLines" :min="0" :max="500" controls-position="right" />
          <el-button type="primary" :loading="logViewerSearching" @click="searchLogViewerKeyword">搜索</el-button>
          <el-button type="success" :loading="logViewerSearching" @click="searchLogViewerTime">按时间</el-button>
          <el-button type="warning" :loading="logViewerSearching" @click="loadLogViewerErrors">异常提取</el-button>
        </div>
        <el-alert
          v-if="logViewerErrorSummary"
          type="warning"
          show-icon
          :closable="false"
          class="mb16"
        >
          <template #title>
            异常命中 {{ logViewerErrorSummary.total || 0 }} 条：
            <span v-for="(count, text) in logViewerErrorTopItems" :key="text" class="log-error-chip">
              {{ text }} ({{ count }})
            </span>
          </template>
        </el-alert>
        <el-table
          v-if="logViewerHits.length"
          :data="logViewerHits"
          row-key="hitKey"
          size="small"
          class="mb16"
          max-height="220"
          @row-click="selectLogViewerHit"
        >
          <el-table-column label="文件" prop="file" min-width="220" show-overflow-tooltip />
          <el-table-column label="行号" prop="line" width="90" />
          <el-table-column label="内容" prop="content" min-width="360" show-overflow-tooltip />
        </el-table>
        <div v-if="logViewerContext" class="log-context-panel mb16">
          <div class="panel-header mb8">
            <span>{{ logViewerContext.file }}:{{ logViewerContext.line }}（{{ logViewerContext.start }}-{{ logViewerContext.end }}/{{ logViewerContext.totalLines }}）</span>
            <div class="panel-inline">
              <el-button link type="primary" :disabled="!logViewerContext.hasPrev || logViewerSearching" @click="pageLogViewerContext(-1)">上一段</el-button>
              <el-button link type="primary" :disabled="!logViewerContext.hasNext || logViewerSearching" @click="pageLogViewerContext(1)">下一段</el-button>
            </div>
          </div>
          <pre :class="['log-content-block', 'log-context-block', { 'log-content-wrap': logPullWrapEnabled }]">{{ logViewerContextText }}</pre>
        </div>
        <el-alert
          v-if="selectedLogPullContent?.contentTruncated"
          type="warning"
          show-icon
          title="当前日志文本已按配置截断入库，如需更多内容请调整字符上限后重新拉取。"
          class="mb16"
        />
        <pre :class="['log-content-block', 'log-content-dialog', { 'log-content-wrap': logPullWrapEnabled }]">
{{ logPullContentDisplayText }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup name="TicketIndex">
import { saveAs } from 'file-saver'
import { decompressText } from '@/utils/tools'
import { listAiProviderOptions } from '@/api/system/aiprovider'
import { listAiPromptTemplateOptions } from '@/api/system/aiprompt'
import { all as listAllAgents } from '@/api/hrm/agent'
import { allPushConfig as listAllPushConfig } from '@/api/hrm/push'
import LogPullConfigFields from '@/components/ticket/LogPullConfigFields.vue'
import LogPullNotifyConfigFields from '@/components/ticket/LogPullNotifyConfigFields.vue'
import {
  addTicket,
  addTicketMessage,
  addTicketComment,
  addTicketEvent,
  addTicketLogPull,
  addTicketAiAnalysis,
  addTicketAiRepoMapping,
  assignTicket,
  changeTicketStatus,
  delTicket,
  delTicketLogPull,
  delTicketAiRepoMapping,
  downloadTicketLogPull,
  downloadTicketImportTemplate,
  extractTicketKnowledge,
  getTicket,
  getTicketComments,
  getTicketStatClassificationOptions,
  getTicketWorkflow,
  listTicketLogPullProjectVendorMapOptions,
  getTicketLogPullContent,
  getTicketLogPullVendorStoreOptions,
  getTicketTimeline,
  importTicketExcel,
  listTicket,
  listTicketAiAnalysisTasks,
  listTicketAiRepoMappings,
  listTicketLogPulls,
  listTicketModuleOptions,
  listTicketProjectOptions,
  prepareTicketLogs,
  reextractTicketLogPull,
  redownloadTicketLogPull,
  retryTicketLogPull,
  retryTicketAiAnalysis,
  addTicketSnapshot,
  saveTicketRca,
  searchTicketLogs,
  searchTicketLogsByTime,
  searchTicketNaturalLanguage,
  getTicketLogPullProjectVendorMap,
  getTicketLogContext,
  getTicketLogErrors,
  saveTicketLogPullProjectVendorMap,
  translateTicketDescription,
  updateTicketAiRepoMapping,
  updateTicket
} from '@/api/ticket/ticket'
import {
  eventTypeOptions,
  getLogPullStatusTagType,
  getOptionLabel,
  getStatusTagType as getDefaultStatusTagType,
  logPullDataTypeOptions,
  logPullStatusOptions,
  logPullStorageModeOptions,
  priorityOptions,
  ticketProcessStatusOptions,
  severityOptions,
  sourceOptions,
  ticketStatusOptions as defaultTicketStatusOptions
} from './constants'
import {
  buildOptionalLogPullTimeRangePayload,
  createDefaultLogPullNotifyConfig,
  getOptionalLogPullTimeRangeError,
  hasLogPullTimeRange,
  normalizeLogPullNotifyConfig
} from './logPull.shared'
import UserSelect from './components/UserSelect.vue'
import { blobValidate } from '@/utils/ruoyi'

const { proxy } = getCurrentInstance()

const loading = ref(false)
const showSearch = ref(true)
const ticketList = ref([])
const total = ref(0)
const projectOptions = ref([])
const projectVendorMapOptions = ref([])
const formModuleOptions = ref([])
const formVersionOptions = ref([])
const queryModuleOptions = ref([])
const issueTypeOptions = ref([])
const rootCauseTypeOptions = ref([])
const solutionTypeOptions = ref([])
const resolutionOptions = ref([])
const agentOptions = ref([])
const providerOptions = ref([])
const analysisPromptOptions = ref([])
const vendorOptions = ref([])
const pushOptions = ref([])
const workflowConfig = ref({
  statuses: [],
  transitions: []
})
const currentTicketStatus = ref('')
const open = ref(false)
const formSubmitting = ref(false)
const assignOpen = ref(false)
const statusOpen = ref(false)
const importOpen = ref(false)
const importing = ref(false)
const detailOpen = ref(false)
const detailMainTab = ref('overview')
const descriptionExpanded = ref(true)
const translationExpanded = ref(false)
const descriptionTranslateLoading = ref(false)
const historyActiveTab = ref('timeline')
const title = ref('')
const currentTicketId = ref()
const currentAssigneeOption = ref(null)
const queryCurrentAssigneeOption = ref(null)
const queryFirstLineAssigneeOption = ref(null)
const queryInternalOwnerOption = ref(null)
const firstLineAssigneeOption = ref(null)
const internalOwnerOption = ref(null)
const formModuleValue = ref('')
const detail = ref({})
const timeline = ref({})
const commentList = ref([])
const commentLoading = ref(false)
const commentLoaded = ref(false)
const ticketMessages = ref([])
const ticketSnapshots = ref([])
const similarTickets = ref([])
const tagText = ref('')
const eventDataText = ref('')
const messageDataText = ref('')
const naturalKeyword = ref('')
const submitTimeRange = ref([])
const importResult = ref(null)
const logPullLoading = ref(false)
const logPullSubmitting = ref(false)
const logPullActionLoading = ref(false)
const logPullSubmitOpen = ref(false)
const logPullContentLoading = ref(false)
const logPullContentOpen = ref(false)
const logPullList = ref([])
const logPullTotal = ref(0)
const logViewerSearching = ref(false)
const logViewerHits = ref([])
const logViewerContext = ref(null)
const logViewerErrorSummary = ref(null)
const logViewerForm = ref({
  ticketId: undefined,
  keyword: '',
  time: '',
  contextLines: 20
})
const aiAnalysisLoading = ref(false)
const aiAnalysisSubmitting = ref(false)
const aiAnalysisRetryLoading = ref(false)
const aiAnalysisRefreshLoading = ref(false)
const aiAnalysisOpen = ref(false)
const aiTaskHistoryOpen = ref(false)
const aiTaskDetailOpen = ref(false)
const selectedAiTask = ref(null)
const aiRepoMappingOpen = ref(false)
const aiRepoMappingLoading = ref(false)
const aiRepoMappingSubmitting = ref(false)
const projectVendorMapOpen = ref(false)
const projectVendorMapLoading = ref(false)
const projectVendorMapSubmitting = ref(false)
const aiTaskLoading = ref(false)
const aiTaskList = ref([])
const aiTaskTotal = ref(0)
const aiRepoMappingList = ref([])
const aiRepoMappingTotal = ref(0)
const detailVersionOptions = ref([])
const aiAnalysisTaskForm = ref({
  versionKey: '',
  agentCode: '',
  aiProviderCode: '',
  forceRefresh: false,
  extraInstruction: '',
  promptTemplateCodes: []
})
const aiRepoMappingForm = ref({
  mappingId: undefined,
  projectId: undefined,
  projectName: '',
  versionKey: '',
  repoUrl: '',
  branchName: '',
  localRepoPath: '',
  workspaceRoot: '',
  workerCommand: '',
  isDefault: false,
  enabled: true,
  remark: ''
})
const projectVendorMapForm = ref({
  projectId: undefined,
  projectName: '',
  venderNo: ''
})
const aiTaskQuery = ref({
  pageNum: 1,
  pageSize: 10,
  status: undefined
})
const selectedLogPullRecord = ref(null)
const selectedLogPullContent = ref(null)
const logPullViewForm = ref({
  viewMode: 'stored',
  logBeginTime: undefined,
  logEndTime: undefined
})
const logPullKeyword = ref('')
const logPullWrapEnabled = ref(false)
const logPullAutoRefreshing = ref(false)

let logPullRefreshTimer = null
let suppressProjectWatcher = false

const activeLogPullStatuses = ['created', 'submitting', 'polling', 'downloading', 'processing']

function createDefaultLogPullForm() {
  return {
    vendorId: undefined,
    storeId: undefined,
    posNo: undefined,
    commandDataType: 1,
    modifyTime: undefined,
    path: '',
    cutLogEnabled: false,
    timeRangeMode: 'between',
    fileMaxSize: 500,
    zipMaxSize: 500,
    logBeginTime: undefined,
    logEndTime: undefined,
    logPointTime: undefined,
    rangeBeforeMinutes: 30,
    rangeAfterMinutes: 30,
    storageMode: 'local',
    autoAiEnabled: false,
    aiAgentCode: '',
    aiProviderCode: '',
    notifyConfig: createDefaultLogPullNotifyConfig()
  }
}

function normalizeVendorOptions(rows = []) {
  return rows.map(item => ({
    vendorId: Number(item.vendorId),
    vendorCode: String(item.vendorCode || '').trim(),
    vendorName: String(item.vendorName || item.vendorId || '').trim(),
    label: buildVendorOptionLabel(item),
    stores: Array.isArray(item.stores)
      ? item.stores.map(store => ({
        storeId: String(store.storeId || '').trim(),
        storeCode: String(store.storeCode || '').trim(),
        sapOrgNo: String(store.sapOrgNo || '').trim(),
        storeName: String(store.storeName || store.storeId || '').trim(),
        label: buildStoreOptionLabel(store)
      }))
      : []
  }))
}

function buildVendorOptionLabel(vendor) {
  const name = String(vendor.vendorName || vendor.vendorId || '').trim()
  const code = String(vendor.vendorCode || '').trim()
  const id = String(vendor.vendorId || '').trim()
  return [name, code, id ? `[${id}]` : ''].filter(Boolean).join(' ')
}

function buildStoreOptionLabel(store) {
  const name = String(store.storeName || store.storeId || '').trim()
  const orgNo = String(store.storeCode || store.storeId || '').trim()
  const sapOrgNo = String(store.sapOrgNo || '').trim()
  return [name, orgNo ? `[${orgNo}]` : '', sapOrgNo ? `(${sapOrgNo})` : ''].filter(Boolean).join(' ')
}

function loadVendorOptions() {
  return getTicketLogPullVendorStoreOptions().then(response => {
    vendorOptions.value = normalizeVendorOptions(response.data?.vendors || [])
  })
}

function loadProjectVendorMapOptions() {
  return listTicketLogPullProjectVendorMapOptions().then(response => {
    projectVendorMapOptions.value = Array.isArray(response.data) ? response.data : []
  })
}

function getProjectVendorNo(projectId) {
  const resolvedProjectId = Number(projectId)
  if (!resolvedProjectId) {
    return ''
  }
  const mapping = projectVendorMapOptions.value.find(item => Number(item.projectId) === resolvedProjectId)
  return String(mapping?.venderNo || '').trim()
}

function applyProjectVendorMapping(projectId) {
  const vendorNo = getProjectVendorNo(projectId)
  if (!vendorNo) {
    return
  }
  const resolvedVendorId = Number(vendorNo)
  logPullForm.value.vendorId = Number.isNaN(resolvedVendorId) ? vendorNo : resolvedVendorId
  resetStoreSelection(logPullForm.value, logPullForm.value.vendorId)
}

function loadProviderOptions() {
  return listAiProviderOptions().then(response => {
    providerOptions.value = response.data || []
  })
}

function loadAnalysisPromptOptions() {
  return listAiPromptTemplateOptions({
    template_category: 'analysis,common',
    enabled_only: true
  }).then(response => {
    analysisPromptOptions.value = response.data || []
  })
}

function loadDetailVersionOptions(projectId) {
  if (!projectId) {
    detailVersionOptions.value = []
    return Promise.resolve()
  }
  return listTicketAiRepoMappings({
    pageNum: 1,
    pageSize: 200,
    projectId,
    enabled: true
  }).then(response => {
    const rows = response.rows || []
    const optionMap = new Map()
    rows.forEach(item => {
      const value = String(item.versionKey || '').trim()
      if (!value || optionMap.has(value)) {
        return
      }
      const branchName = String(item.branchName || '').trim()
      const repoUrl = String(item.repoUrl || '').trim()
      const labelParts = [value]
      if (branchName) {
        labelParts.push(`- ${branchName}`)
      }
      if (repoUrl) {
        labelParts.push(`(${repoUrl})`)
      }
      optionMap.set(value, {
        value,
        label: labelParts.join(' ')
      })
    })
    detailVersionOptions.value = Array.from(optionMap.values())
  })
}

function loadPushOptions() {
  return listAllPushConfig({ pageNum: 1, pageSize: 500 }).then(response => {
    const rows = response.data || []
    pushOptions.value = Array.isArray(rows) ? rows : []
  })
}

function getVendorStoreOptions(vendorId) {
  const resolvedVendorId = Number(vendorId)
  if (!resolvedVendorId) {
    return []
  }
  const vendor = vendorOptions.value.find(item => item.vendorId === resolvedVendorId)
  return vendor?.stores || []
}

function resetStoreSelection(target, vendorId) {
  const storeId = String(target.storeId || '').trim()
  if (!storeId) {
    target.storeId = undefined
    return
  }
  const storeOptions = getVendorStoreOptions(vendorId)
  if (storeOptions.length && !storeOptions.some(item => String(item.storeId || '').trim() === storeId)) {
    target.storeId = storeId
  }
}

function handleLogPullVendorChange(vendorId) {
  resetStoreSelection(logPullForm.value, vendorId)
}

function pickFirstFilledValue(candidates = []) {
  for (const candidate of candidates) {
    if (candidate === null || candidate === undefined) {
      continue
    }
    if (typeof candidate === 'string' && !candidate.trim()) {
      continue
    }
    return candidate
  }
  return undefined
}

function resolveTicketLogPullHintsFromDetail(ticketDetail) {
  const detailPayload = ticketDetail || {}
  const extraData = detailPayload.extraData || detailPayload.extra_data || {}
  const externalSync = extraData.externalSync || extraData.external_sync || {}
  const source = externalSync.source || {}
  const logPullHints = extraData.logPullHints || extraData.log_pull_hints || {}
  const ticketAutomation = extraData.ticketAutomation || extraData.ticket_automation || {}
  const automationLogPullConfig = ticketAutomation.logPullConfig || ticketAutomation.log_pull_config || {}
  const latestLogPull = detailPayload.latestLogPull || detailPayload.latest_log_pull || {}
  const directLogPullConfig = detailPayload.logPullConfig || detailPayload.log_pull_config || {}
  return {
    vendorId: pickFirstFilledValue([
      source.vendorId,
      source.vendor_id,
      logPullHints.vendorId,
      logPullHints.vendor_id,
      latestLogPull.vendorId,
      latestLogPull.vendor_id,
      automationLogPullConfig.vendorId,
      automationLogPullConfig.vendor_id,
      directLogPullConfig.vendorId,
      directLogPullConfig.vendor_id
    ]),
    storeId: pickFirstFilledValue([
      source.storeId,
      source.store_id,
      logPullHints.storeId,
      logPullHints.store_id,
      latestLogPull.storeId,
      latestLogPull.store_id,
      automationLogPullConfig.storeId,
      automationLogPullConfig.store_id,
      directLogPullConfig.storeId,
      directLogPullConfig.store_id
    ]),
    posNo: pickFirstFilledValue([
      source.posNo,
      source.pos_no,
      source.posId,
      source.pos_id,
      source.scoNo,
      source.sco_no,
      logPullHints.posNo,
      logPullHints.pos_no,
      latestLogPull.posNo,
      latestLogPull.pos_no,
      automationLogPullConfig.posNo,
      automationLogPullConfig.pos_no,
      automationLogPullConfig.posId,
      automationLogPullConfig.pos_id,
      automationLogPullConfig.scoNo,
      automationLogPullConfig.sco_no,
      directLogPullConfig.posNo,
      directLogPullConfig.pos_no,
      directLogPullConfig.posId,
      directLogPullConfig.pos_id,
      directLogPullConfig.scoNo,
      directLogPullConfig.sco_no
    ])
  }
}

function applyTicketDetailLogPullPrefill(ticketDetail) {
  const hints = resolveTicketLogPullHintsFromDetail(ticketDetail)
  let vendorApplied = false
  const vendorId = Number(hints.vendorId)
  if (Number.isFinite(vendorId) && vendorId > 0) {
    logPullForm.value.vendorId = vendorId
    vendorApplied = true
  }
  const storeId = String(hints.storeId || '').trim()
  if (storeId) {
    logPullForm.value.storeId = storeId
  }
  const posNo = Number(hints.posNo)
  if (Number.isFinite(posNo) && posNo > 0) {
    logPullForm.value.posNo = posNo
  }
  return { vendorApplied }
}

function createDefaultTicketForm() {
  return {
    ticketId: undefined,
    ticketNo: undefined,
    ticketUrl: '',
    title: undefined,
    description: undefined,
    projectId: undefined,
    moduleId: undefined,
    moduleName: '',
    versionKey: '',
    firstLineAssigneeId: undefined,
    firstLineAssigneeName: '',
    internalOwnerId: undefined,
    internalOwnerName: '',
    customerPriority: 'P3',
    internalPriority: 'P3',
    severity: undefined,
    source: undefined,
    categoryName: undefined,
    issueTypeId: '',
    issueTypeName: '',
    isProblem: undefined,
    rootCauseType: '',
    solutionType: '',
    resolutionCode: '',
    resolutionName: '',
    rootCause: undefined,
    solution: undefined,
    needLogPull: false,
    autoTranslate: true,
    logPullConfig: createDefaultLogPullForm()
  }
}

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    status: undefined,
    ticketNo: undefined,
    processStatus: undefined,
    projectId: undefined,
    moduleId: undefined,
    issueTypeId: undefined,
    isProblem: undefined,
    rootCauseType: undefined,
    solutionType: undefined,
    resolutionCode: undefined,
    internalPriority: undefined,
    currentAssigneeId: undefined,
    firstLineAssigneeId: undefined,
    internalOwnerId: undefined,
    submitBeginTime: undefined,
    submitEndTime: undefined
  },
  form: createDefaultTicketForm(),
  assignForm: {},
  statusForm: {},
  commentForm: {
    content: '',
    isInternal: false
  },
  messageForm: {
    role: 'user',
    messageType: 'question',
    content: '',
    runAi: true,
    versionKey: '',
    agentCode: '',
    aiProviderCode: ''
  },
  eventForm: {
    eventType: 'ANALYSIS',
    content: ''
  },
  rcaForm: {},
  logPullForm: createDefaultLogPullForm(),
  logPullQuery: {
    pageNum: 1,
    pageSize: 10,
    status: undefined
  },
  rules: {
    title: [{ required: true, message: '工单标题不能为空', trigger: 'blur' }],
    ticketNo: [{ required: true, message: '工单号不能为空', trigger: 'blur' }],
    projectId: [{ required: true, message: '所属项目不能为空', trigger: 'change' }],
    customerPriority: [{ required: true, message: '对方优先级不能为空', trigger: 'change' }],
    internalPriority: [{ required: true, message: '内部优先级不能为空', trigger: 'change' }]
  },
  assignRules: {
    toUserId: [{ required: true, message: '请选择处理人', trigger: 'change' }],
    toUserName: [{ required: true, message: '处理人名称不能为空', trigger: 'blur' }]
  },
  statusRules: {
    toStatus: [{ required: true, message: '目标状态不能为空', trigger: 'change' }]
  },
  logPullRules: {
    vendorId: [{ required: true, message: 'vendorId不能为空', trigger: 'blur' }],
    storeId: [{ required: true, message: 'storeId不能为空', trigger: 'blur' }],
    posNo: [{ required: true, message: 'posNo不能为空', trigger: 'blur' }]
  },
  aiAnalysisRules: {
    versionKey: [{ required: true, message: '版本号不能为空', trigger: 'blur' }]
  },
  aiRepoMappingRules: {
    projectId: [{ required: true, message: '请选择项目', trigger: 'change' }],
    versionKey: [{ required: true, message: '版本标识不能为空', trigger: 'blur' }],
    repoUrl: [{ required: true, message: '仓库地址不能为空', trigger: 'blur' }],
    branchName: [{ required: true, message: '分支名称不能为空', trigger: 'blur' }]
  },
  projectVendorMapRules: {
    venderNo: [{ required: true, message: '商户编号不能为空', trigger: 'blur' }]
  }
})

const {
  queryParams,
  form,
  assignForm,
  statusForm,
  commentForm,
  messageForm,
  eventForm,
  rcaForm,
  logPullForm,
  logPullQuery,
  rules,
  assignRules,
  statusRules,
  logPullRules,
  aiAnalysisRules,
  aiRepoMappingRules,
  projectVendorMapRules
} = toRefs(data)

const detailTitle = computed(() => `工单详情：${detail.value.title || ''}`)
const detailOriginalDescription = computed(() => {
  const originalText = String(
    detail.value.originalDescription
    || detail.value.extraData?.originDescription
    || detail.value.extraData?.origin_description
    || ''
  ).trim()
  if (originalText) {
    return originalText
  }
  const description = String(detail.value.description || '').trim()
  return description.includes('【AI翻译】') ? description.split('【AI翻译】')[0].trim() : description
})
const detailAiTranslation = computed(() => String(
  detail.value.aiTranslation
  || detail.value.extraData?.aiTranslation
  || detail.value.extraData?.ai_translation
  || ''
).trim())
const latestSnapshotSummary = computed(() => latestSnapshot.value?.summary || detail.value.rootCause || detail.value.description || '')
const filteredLogPullContent = computed(() => {
  const text = selectedLogPullContent.value?.text || ''
  const keyword = (logPullKeyword.value || '').trim().toLowerCase()
  if (!keyword || !text) {
    return text
  }
  return text
    .split(/\n{2,}/)
    .filter(block => block.toLowerCase().includes(keyword))
    .join('\n\n')
})
const logPullContentDisplayText = computed(() => {
  const rawText = selectedLogPullContent.value?.text || ''
  if (!rawText) {
    return logPullContentLoading.value ? '日志内容加载中...' : '暂无可展示日志内容'
  }
  if ((logPullKeyword.value || '').trim() && !filteredLogPullContent.value) {
    return '当前关键字过滤后无匹配日志，请清空过滤关键字后重试'
  }
  return filteredLogPullContent.value
})
const logViewerContextText = computed(() => {
  const lines = logViewerContext.value?.lines || []
  return lines.map(item => `${String(item.line).padStart(6, ' ')}  ${item.content || ''}`).join('\n')
})
const logViewerErrorTopItems = computed(() => {
  const items = logViewerErrorSummary.value?.items || {}
  return Object.fromEntries(Object.entries(items).slice(0, 5))
})

function decodeLogText(text) {
  if (text === null || text === undefined || text === '') {
    return ''
  }
  const rawText = String(text)
  try {
    return decompressText(rawText)
  } catch (error) {
    return rawText
  }
}

function formatLogViewRange(beginTime, endTime) {
  if (!beginTime && !endTime) {
    return '-'
  }
  return `${beginTime || '-'} 至 ${endTime || '-'}`
}
function formatLogViewSource(source) {
  const value = String(source || 'stored')
  if (value === 'realtime') return '实时重截'
  if (value === 'fallback') return '实时回退'
  return '入库内容'
}

function getStatOptionLabel(options, value) {
  const text = String(value || '').trim()
  if (!text) {
    return '-'
  }
  const option = (options || []).find(item => item.value === text)
  return option?.label || text
}

function formatStatOption(options, value) {
  return getStatOptionLabel(options.value || options, value)
}

function formatProblemFlag(value) {
  if (value === true) return '真实问题'
  if (value === false) return '非问题'
  return '-'
}

function formatIssueType(row) {
  const issueTypeName = row?.issueTypeName || row?.issue_type_name || ''
  if (issueTypeName) {
    return issueTypeName
  }
  const issueTypeId = row?.issueTypeId || row?.issue_type_id || ''
  if (!issueTypeId) {
    return '-'
  }
  const option = issueTypeOptions.value.find(item => item.value === String(issueTypeId).trim())
  return option?.label || '-'
}

function formatResolution(row) {
  const resolutionName = row?.resolutionName || row?.resolution_name || ''
  if (resolutionName) {
    return resolutionName
  }
  const resolutionCode = row?.resolutionCode || row?.resolution_code || ''
  return resolutionCode ? getStatOptionLabel(resolutionOptions.value, resolutionCode) : '-'
}

function resolveTicketProcessStatus(row) {
  const latestAi = row?.latestAiAnalysis || row?.latest_ai_analysis || null
  const latestLog = row?.latestLogPull || row?.latest_log_pull || null
  const aiStatus = String(latestAi?.status || '').trim()
  if (aiStatus) {
    if (['created', 'running'].includes(aiStatus)) {
      return { label: getOptionLabel(ticketProcessStatusOptions, 'ai_running'), type: 'warning' }
    }
    if (aiStatus === 'success') {
      return { label: getOptionLabel(ticketProcessStatusOptions, 'ai_success'), type: 'success' }
    }
    if (['failed', 'canceled'].includes(aiStatus)) {
      return { label: getOptionLabel(ticketProcessStatusOptions, 'ai_failed'), type: 'danger' }
    }
  }
  const logStatus = String(latestLog?.status || '').trim()
  if (!logStatus) {
    return { label: getOptionLabel(ticketProcessStatusOptions, 'no_log_pull'), type: 'info' }
  }
  if (logStatus === 'success') {
    return { label: getOptionLabel(ticketProcessStatusOptions, 'ai_not_analyzed'), type: 'primary' }
  }
  if (['failed', 'exception'].includes(logStatus)) {
    return { label: getOptionLabel(ticketProcessStatusOptions, 'log_pull_failed'), type: 'danger' }
  }
  return {
    label: latestLog?.statusDesc || getOptionLabel(logPullStatusOptions, logStatus),
    type: getLogPullStatusTagType(logStatus)
  }
}

function normalizeWorkflowStatusOptions(statuses = []) {
  return (statuses || [])
    .map(item => {
      const value = String(item.code || '').trim()
      if (!value) {
        return null
      }
      const fallback = defaultTicketStatusOptions.find(option => option.value === value)
      return {
        label: String(item.name || fallback?.label || value).trim(),
        value,
        type: fallback?.type || 'info',
        orderNum: Number(item.orderNum ?? item.order_num ?? 0)
      }
    })
    .filter(Boolean)
    .sort((a, b) => a.orderNum - b.orderNum)
}

function getStatusTagType(value) {
  return ticketStatusOptions.value.find(item => item.value === value)?.type || getDefaultStatusTagType(value)
}

function loadWorkflowConfig() {
  return getTicketWorkflow().then(response => {
    workflowConfig.value = response.data || { statuses: [], transitions: [] }
  }).catch(() => {
    workflowConfig.value = { statuses: [], transitions: [] }
  })
}

function normalizeStatOptions(items = []) {
  return (Array.isArray(items) ? items : [])
    .map(item => ({
      value: String(item.value || item.code || '').trim(),
      label: String(item.label || item.name || item.value || item.code || '').trim(),
      isProblem: typeof item.isProblem === 'boolean' ? item.isProblem : undefined
    }))
    .filter(item => item.value)
}

function loadStatClassificationOptions() {
  return getTicketStatClassificationOptions().then(response => {
    const config = response.data || {}
    issueTypeOptions.value = normalizeStatOptions(config.issueTypes)
    rootCauseTypeOptions.value = normalizeStatOptions(config.rootCauseTypes)
    solutionTypeOptions.value = normalizeStatOptions(config.solutionTypes)
    resolutionOptions.value = normalizeStatOptions(config.resolutions)
  }).catch(() => {
    issueTypeOptions.value = []
    rootCauseTypeOptions.value = []
    solutionTypeOptions.value = []
    resolutionOptions.value = []
  })
}

const latestAiAnalysisTask = computed(() => detail.value.latestAiAnalysis || null)

const latestSnapshot = computed(() => detail.value.latestSnapshot || ticketSnapshots.value[0] || null)
const latestSimilarTickets = computed(() => (similarTickets.value || []).slice(0, 3))
const aiTaskDetailPayload = computed(() => selectedAiTask.value || {})
const aiPromptLayers = computed(() => detail.value.aiPromptLayers || {})
const logPullStoreOptions = computed(() => getVendorStoreOptions(logPullForm.value.vendorId))
const aiPromptHintTitle = computed(() => {
  const projectName = aiPromptLayers.value?.project?.projectName || detail.value.projectName || ''
  const moduleName = aiPromptLayers.value?.module?.moduleName || detail.value.moduleName || ''
  const parts = ['AI 分析会自动叠加默认提示词']
  if (projectName) {
    parts.push(`项目：${projectName}`)
  }
  if (moduleName) {
    parts.push(`模块：${moduleName}`)
  }
  return parts.join('，')
})
const aiPromptHintDesc = computed(() => {
  const hasDefaultPrompt = Boolean(aiPromptLayers.value?.hasDefaultPrompt)
  if (!hasDefaultPrompt) {
    return '当前工单未读取到项目/模块默认提示词，仍可填写额外说明来补充本次分析重点。'
  }
  return '项目和模块的默认提示词会自动参与本次分析，额外说明仅用于补充临时背景，不会覆盖系统约束和输出结构。'
})

const ticketStatusOptions = computed(() => {
  const dynamicOptions = normalizeWorkflowStatusOptions(workflowConfig.value.statuses)
  return dynamicOptions.length ? dynamicOptions : defaultTicketStatusOptions
})

const statusTransitionOptions = computed(() => {
  const fromStatus = String(currentTicketStatus.value || '').trim()
  if (!fromStatus) {
    return []
  }
  const toStatusSet = new Set(
    (workflowConfig.value.transitions || [])
      .filter(item => String(item.fromStatus || '').trim() === fromStatus)
      .map(item => String(item.toStatus || '').trim())
      .filter(Boolean)
  )
  return ticketStatusOptions.value.filter(item => toStatusSet.has(item.value))
})

const timelineItems = computed(() => {
  const items = []
  ;(timeline.value.statusHistory || []).forEach(item => {
    items.push({
      key: `status-${item.id}`,
      time: item.startedAt,
      title: `状态流转：${getOptionLabel(ticketStatusOptions.value, item.fromStatus)} -> ${getOptionLabel(ticketStatusOptions.value, item.toStatus)}`,
      content: item.comment
    })
  })
  ;(timeline.value.assignHistory || []).forEach(item => {
    items.push({
      key: `assign-${item.id}`,
      time: item.assignedAt,
      title: `指派：${item.fromUserName || '未指派'} -> ${item.toUserName || '-'}`,
      content: item.reason
    })
  })
  ;(timeline.value.events || []).forEach(item => {
    items.push({
      key: `event-${item.id}`,
      time: item.createTime,
      title: `事件：${item.eventType}`,
      content: item.content
    })
  })
  return items.sort((a, b) => new Date(a.time || 0) - new Date(b.time || 0))
})

const messageItems = computed(() => {
  return (ticketMessages.value || []).map(item => ({
    ...item,
    roleLabel: item.role || 'user',
    typeLabel: item.messageType || 'question'
  }))
})

function getList() {
  const rangeValues = Array.isArray(submitTimeRange.value) ? submitTimeRange.value : []
  const [submitBeginTime, submitEndTime] = rangeValues
  queryParams.value.submitBeginTime = submitBeginTime || undefined
  queryParams.value.submitEndTime = submitEndTime || undefined
  loading.value = true
  listTicket(queryParams.value).then(response => {
    ticketList.value = response.rows || []
    total.value = response.total || 0
  }).finally(() => {
    loading.value = false
  })
}

function resolveTicketDetailUrl(ticketRow) {
  const row = ticketRow || {}
  const syncSummary = row.syncSummary || row.sync_summary || {}
  const extraData = row.extraData || row.extra_data || {}
  const externalSync = extraData.externalSync || extraData.external_sync || {}
  const source = externalSync.source || {}
  const value = String(
    row.ticketUrl
      || row.ticket_url
      || row.url
      || syncSummary.ticketUrl
      || syncSummary.ticket_url
      || syncSummary.sourceRecordUrl
      || syncSummary.source_record_url
      || source.ticketUrl
      || source.ticket_url
      || source.recordUrl
      || source.record_url
      || ''
  ).trim()
  return value || ''
}

function openTicketLink(ticketRow) {
  const ticketUrl = resolveTicketDetailUrl(ticketRow)
  if (!ticketUrl) {
    proxy.$modal.msgWarning('当前工单未配置详情链接')
    return
  }
  window.open(ticketUrl, '_blank', 'noopener')
}

function reset() {
  formSubmitting.value = false
  form.value = createDefaultTicketForm()
  formModuleValue.value = ''
  tagText.value = ''
  firstLineAssigneeOption.value = null
  internalOwnerOption.value = null
  proxy.resetForm('ticketRef')
}

function handleIssueTypeChange(value) {
  const option = issueTypeOptions.value.find(item => item.value === value)
  form.value.issueTypeName = option?.label || ''
  if (typeof option?.isProblem === 'boolean') {
    form.value.isProblem = option.isProblem
  }
}

function syncFormModuleValueFromForm() {
  if (form.value.moduleId) {
    formModuleValue.value = String(form.value.moduleId)
    return
  }
  formModuleValue.value = form.value.moduleName || ''
}

function resolveFormModuleOption(value = formModuleValue.value) {
  const text = String(value || '').trim()
  if (!text) {
    return null
  }
  return formModuleOptions.value.find(item => String(item.moduleId) === text || item.moduleName === text) || null
}

function handleModuleChange(value) {
  const option = resolveFormModuleOption(value)
  if (option) {
    form.value.moduleId = option.moduleId
    form.value.moduleName = option.moduleName || ''
    formModuleValue.value = String(option.moduleId)
    return
  }
  form.value.moduleId = undefined
  form.value.moduleName = String(value || '').trim()
  formModuleValue.value = form.value.moduleName
}

function handleResolutionChange(value) {
  const option = resolutionOptions.value.find(item => item.value === value)
  statusForm.value.resolutionName = option?.label || ''
  if (typeof option?.isProblem === 'boolean') {
    statusForm.value.isProblem = option.isProblem
  }
}

function applyTicketAutomationConfig(ticketData) {
  const automation = ticketData?.extraData?.ticketAutomation || ticketData?.extraData?.ticket_automation || {}
  const logPullConfig = automation?.logPullConfig || automation?.log_pull_config || null
  if (!logPullConfig) {
    return
  }
  form.value.needLogPull = Boolean(automation.needLogPull ?? automation.need_log_pull ?? true)
  form.value.logPullConfig = {
    ...createDefaultLogPullForm(),
    ...logPullConfig,
    cutLogEnabled: Boolean(logPullConfig.cutLogEnabled ?? logPullConfig.cut_log_enabled ?? hasLogPullTimeRange(logPullConfig)),
    autoAiEnabled: Boolean(logPullConfig.autoAiEnabled ?? logPullConfig.auto_ai_enabled ?? false),
    aiAgentCode: logPullConfig.aiAgentCode || logPullConfig.ai_agent_code || '',
    aiProviderCode: logPullConfig.aiProviderCode || logPullConfig.ai_provider_code || '',
    notifyConfig: normalizeLogPullNotifyConfig(logPullConfig.notifyConfig || logPullConfig.notify_config)
  }
}

function syncDetailBundle(payload) {
  detail.value = payload || {}
  ticketMessages.value = detail.value.messages || []
  ticketSnapshots.value = detail.value.snapshots || []
  similarTickets.value = detail.value.similarTickets || []
}

function handleQuery() {
  queryParams.value.pageNum = 1
  getList()
}

function handleSearch() {
  if (naturalKeyword.value) {
    handleNaturalSearch()
    return
  }
  handleQuery()
}

function resetQuery() {
  proxy.resetForm('queryRef')
  naturalKeyword.value = ''
  submitTimeRange.value = []
  queryParams.value.submitBeginTime = undefined
  queryParams.value.submitEndTime = undefined
  queryCurrentAssigneeOption.value = null
  queryFirstLineAssigneeOption.value = null
  queryInternalOwnerOption.value = null
  handleQuery()
}

function handleNaturalSearch() {
  if (!naturalKeyword.value) {
    handleQuery()
    return
  }
  loading.value = true
  searchTicketNaturalLanguage({ keyword: naturalKeyword.value, limit: queryParams.value.pageSize }).then(response => {
    ticketList.value = response.data || []
    total.value = ticketList.value.length
  }).finally(() => {
    loading.value = false
  })
}

function downloadTemplate() {
  downloadTicketImportTemplate().then(data => {
    saveAs(new Blob([data]), '工单导入模板.xlsx')
  })
}

function submitImport() {
  importResult.value = null
  proxy.$refs.uploadRef.submit()
}

function handleImportRequest(option) {
  const formData = new FormData()
  formData.append('file', option.file)
  importing.value = true
  importTicketExcel(formData).then(response => {
    importResult.value = response.data
    proxy.$modal.msgSuccess('导入完成')
    proxy.$refs.uploadRef.clearFiles()
    getList()
  }).finally(() => {
    importing.value = false
  })
}

function handleAdd() {
  reset()
  formModuleOptions.value = []
  formVersionOptions.value = []
  open.value = true
  title.value = '新增工单'
}

function handleUpdate(row) {
  reset()
  getTicket(row.ticketId).then(response => {
    const ticketData = response.data || {}
    suppressProjectWatcher = true
    form.value = {
      ...createDefaultTicketForm(),
      ...ticketData,
      logPullConfig: {
        ...createDefaultLogPullForm(),
        ...(ticketData.logPullConfig || ticketData.log_pull_config || ticketData.extraData?.ticketAutomation?.logPullConfig || ticketData.extraData?.ticket_automation?.log_pull_config || {})
      }
    }
    form.value.logPullConfig.cutLogEnabled = Boolean(
      form.value.logPullConfig.cutLogEnabled
      ?? form.value.logPullConfig.cut_log_enabled
      ?? hasLogPullTimeRange(form.value.logPullConfig)
    )
    form.value.logPullConfig.notifyConfig = normalizeLogPullNotifyConfig(
      form.value.logPullConfig.notifyConfig || form.value.logPullConfig.notify_config
    )
    form.value.description = ticketData.originalDescription || ticketData.extraData?.originDescription || ticketData.description || ''
    form.value.autoTranslate = ticketData.extraData?.manualAutomation?.autoTranslate
      ?? ticketData.extraData?.manual_automation?.auto_translate
      ?? ticketData.autoTranslate
      ?? ticketData.auto_translate
      ?? true
    form.value.issueTypeId = ticketData.issueTypeId || ticketData.issue_type_id || ''
    form.value.issueTypeName = ticketData.issueTypeName || ticketData.issue_type_name || ''
    form.value.isProblem = ticketData.isProblem ?? ticketData.is_problem ?? undefined
    form.value.rootCauseType = ticketData.rootCauseType || ticketData.root_cause_type || ''
    form.value.solutionType = ticketData.solutionType || ticketData.solution_type || ''
    form.value.resolutionCode = ticketData.resolutionCode || ticketData.resolution_code || ''
    form.value.resolutionName = ticketData.resolutionName || ticketData.resolution_name || ''
    syncFormModuleValueFromForm()
    tagText.value = Array.isArray(form.value.tags) ? form.value.tags.join(',') : ''
    applyTicketAutomationConfig(form.value)
    firstLineAssigneeOption.value = buildTicketUserOption(form.value.firstLineAssigneeId, form.value.firstLineAssigneeName)
    internalOwnerOption.value = buildTicketUserOption(form.value.internalOwnerId, form.value.internalOwnerName)
    loadFormModuleOptions(form.value.projectId).finally(() => {
      suppressProjectWatcher = false
    })
    loadFormVersionOptions(form.value.projectId)
    open.value = true
    title.value = '编辑工单'
  }).catch(() => {
    suppressProjectWatcher = false
  })
}

function cancel() {
  open.value = false
}

function validateTicketAutomationConfig() {
  if (!form.value.needLogPull) {
    return true
  }
  const config = form.value.logPullConfig || {}
  if (!config.vendorId || !config.storeId || !config.posNo) {
    proxy.$modal.msgWarning('启用日志拉取时，vendorId、storeId、posNo 不能为空')
    return false
  }
  if (Number(config.commandDataType) === 2 && !String(config.path || '').trim()) {
    proxy.$modal.msgWarning('启用日志拉取且数据类型为数据库时，path 不能为空')
    return false
  }
  if (Number(config.commandDataType) !== 2 && !config.modifyTime) {
    proxy.$modal.msgWarning('启用日志拉取且数据类型为日志时，modifyTime 不能为空')
    return false
  }
  const timeRangeError = getOptionalLogPullTimeRangeError(config)
  if (timeRangeError) {
    proxy.$modal.msgWarning(`启用日志拉取时，${timeRangeError}`)
    return false
  }
  if (
    config.autoAiEnabled
    && !String(config.aiAgentCode || '').trim()
    && !String(config.aiProviderCode || '').trim()
  ) {
    proxy.$modal.msgWarning('启用自动AI分析时，请先选择Provider或Agent')
    return false
  }
  return true
}

function buildCleanLogPullConfig(source) {
  const config = { ...(source || {}) }
  config.notifyConfig = normalizeLogPullNotifyConfig(config.notifyConfig)
  if (Number(config.commandDataType) === 2) {
    delete config.modifyTime
  } else {
    delete config.path
  }
  if (!config.cutLogEnabled) {
    delete config.timeRangeMode
    delete config.logBeginTime
    delete config.logEndTime
    delete config.logPointTime
    delete config.rangeBeforeMinutes
    delete config.rangeAfterMinutes
  } else if (config.timeRangeMode === 'between') {
    delete config.logPointTime
    delete config.rangeBeforeMinutes
    delete config.rangeAfterMinutes
  } else if (config.timeRangeMode === 'point') {
    delete config.logBeginTime
    delete config.logEndTime
  }
  delete config.cutLogEnabled
  if (!config.autoAiEnabled) {
    config.aiAgentCode = ''
    config.aiProviderCode = ''
  }
  return config
}

function submitForm() {
  if (formSubmitting.value) {
    return
  }
  proxy.$refs.ticketRef.validate(valid => {
    if (!valid) return
    if (!validateTicketAutomationConfig()) {
      return
    }
    formSubmitting.value = true
    const logPullConfig = form.value.needLogPull ? buildCleanLogPullConfig(form.value.logPullConfig) : undefined
    const payload = {
      ...form.value,
      tags: tagText.value ? tagText.value.split(',').map(item => item.trim()).filter(Boolean) : undefined,
      needLogPull: Boolean(form.value.needLogPull),
      autoTranslate: Boolean(form.value.autoTranslate),
      logPullConfig
    }
    handleModuleChange(formModuleValue.value)
    payload.moduleId = form.value.moduleId
    payload.moduleName = form.value.moduleName || ''
    if (payload.issueTypeId) {
      payload.issueTypeName = payload.issueTypeName || getStatOptionLabel(issueTypeOptions.value, payload.issueTypeId)
    }
    if (payload.resolutionCode) {
      payload.resolutionName = payload.resolutionName || getStatOptionLabel(resolutionOptions.value, payload.resolutionCode)
    }
    const request = payload.ticketId ? updateTicket(payload) : addTicket(payload)
    request.then(() => {
      proxy.$modal.msgSuccess(payload.ticketId ? '修改成功' : '新增成功')
      open.value = false
      getList()
    }).finally(() => {
      formSubmitting.value = false
    })
  })
}

function handleDelete(row) {
  proxy.$modal.confirm(`是否确认删除工单 "${row.title}"？`).then(() => delTicket(row.ticketId)).then(() => {
    proxy.$modal.msgSuccess('删除成功')
    getList()
  }).catch(() => {})
}

function openAssign(row) {
  currentTicketId.value = row.ticketId
  currentAssigneeOption.value = row.currentAssigneeId
    ? {
        userId: row.currentAssigneeId,
        userName: row.currentAssigneeName,
        nickName: row.currentAssigneeName,
        label: row.currentAssigneeName
      }
    : null
  assignForm.value = {
    toUserId: row.currentAssigneeId,
    toUserName: row.currentAssigneeName,
    reason: ''
  }
  assignOpen.value = true
}

function submitAssign() {
  proxy.$refs.assignRef.validate(valid => {
    if (!valid) return
    assignTicket(currentTicketId.value, assignForm.value).then(() => {
      proxy.$modal.msgSuccess('指派成功')
      assignOpen.value = false
      getList()
    })
  })
}

function handleAssigneeChange(user) {
  assignForm.value.toUserName = user?.nickName || user?.userName || ''
  currentAssigneeOption.value = user
}

function handleQueryCurrentAssigneeChange(user) {
  queryCurrentAssigneeOption.value = user || null
}

function handleQueryFirstLineAssigneeChange(user) {
  queryFirstLineAssigneeOption.value = user || null
}

function handleQueryInternalOwnerChange(user) {
  queryInternalOwnerOption.value = user || null
}

function buildTicketUserOption(userId, userName) {
  if (!userId) {
    return null
  }
  const resolvedName = String(userName || '').trim()
  return {
    userId,
    userName: resolvedName,
    nickName: resolvedName,
    label: resolvedName
  }
}

function handleFirstLineAssigneeChange(user) {
  if (user?.isRawLabel) {
    form.value.firstLineAssigneeId = undefined
    firstLineAssigneeOption.value = null
    return
  }
  form.value.firstLineAssigneeName = user?.nickName || user?.userName || ''
  firstLineAssigneeOption.value = user
}

function handleInternalOwnerChange(user) {
  if (user?.isRawLabel) {
    form.value.internalOwnerId = undefined
    internalOwnerOption.value = null
    return
  }
  form.value.internalOwnerName = user?.nickName || user?.userName || ''
  internalOwnerOption.value = user
}

function openStatus(row) {
  currentTicketId.value = row.ticketId
  currentTicketStatus.value = row.status || ''
  statusForm.value = {
    toStatus: undefined,
    comment: '',
    rootCause: row.rootCause,
    solution: row.solution,
    isProblem: row.isProblem,
    rootCauseType: row.rootCauseType || row.root_cause_type || '',
    solutionType: row.solutionType || row.solution_type || '',
    resolutionCode: row.resolutionCode || row.resolution_code || '',
    resolutionName: row.resolutionName || row.resolution_name || ''
  }
  if (!statusTransitionOptions.value.length) {
    proxy.$modal.msgWarning('当前状态未配置可用流转规则，请先在工单工作流中配置流转规则')
  }
  statusOpen.value = true
}

function submitStatus() {
  proxy.$refs.statusRef.validate(valid => {
    if (!valid) return
    changeTicketStatus(currentTicketId.value, statusForm.value).then(() => {
      proxy.$modal.msgSuccess('状态流转成功')
      statusOpen.value = false
      getList()
    })
  })
}

function resetLogPullForm() {
  logPullForm.value = createDefaultLogPullForm()
  if (proxy.$refs.logPullRef) {
    proxy.resetForm('logPullRef')
  }
}

function openLogPullSubmitDialog() {
  resetLogPullForm()
  if (currentTicketId.value) {
    logPullForm.value.ticketId = currentTicketId.value
  }
  const prefillResult = applyTicketDetailLogPullPrefill(detail.value)
  if (!prefillResult.vendorApplied) {
    applyProjectVendorMapping(detail.value.projectId)
  }
  logPullSubmitOpen.value = true
}

function stopLogPullAutoRefresh() {
  if (logPullRefreshTimer) {
    window.clearTimeout(logPullRefreshTimer)
    logPullRefreshTimer = null
  }
  logPullAutoRefreshing.value = false
}

function scheduleLogPullAutoRefresh() {
  stopLogPullAutoRefresh()
  const hasRunningTask = detailOpen.value && logPullList.value.some(item => activeLogPullStatuses.includes(item.status))
  logPullAutoRefreshing.value = hasRunningTask
  if (!hasRunningTask) {
    return
  }
  logPullRefreshTimer = window.setTimeout(() => {
    Promise.all([loadLogPullList(true), refreshDetail()]).finally(() => {
      scheduleLogPullAutoRefresh()
    })
  }, 10000)
}

function loadLogPullList(silent = false) {
  if (!currentTicketId.value) {
    return Promise.resolve()
  }
  if (!silent) {
    logPullLoading.value = true
  }
  return listTicketLogPulls(currentTicketId.value, logPullQuery.value).then(response => {
    logPullList.value = response.rows || []
    logPullTotal.value = response.total || 0
    if (selectedLogPullRecord.value) {
      selectedLogPullRecord.value = logPullList.value.find(item => item.id === selectedLogPullRecord.value.id) || selectedLogPullRecord.value
    }
    scheduleLogPullAutoRefresh()
  }).finally(() => {
    if (!silent) {
      logPullLoading.value = false
    }
  })
}

function refreshDetail() {
  if (!currentTicketId.value) {
    return Promise.resolve()
  }
  return getTicket(currentTicketId.value).then(response => {
    syncDetailBundle(response.data || {})
    loadDetailVersionOptions(detail.value.projectId)
  })
}

function createDefaultAiRepoMappingForm(projectId, projectName) {
  return {
    mappingId: undefined,
    projectId,
    projectName: projectName || '',
    versionKey: '',
    repoUrl: '',
    branchName: '',
    localRepoPath: '',
    workspaceRoot: '',
    workerCommand: '',
    isDefault: false,
    enabled: true,
    remark: ''
  }
}

function resetAiRepoMappingForm() {
  aiRepoMappingForm.value = createDefaultAiRepoMappingForm(detail.value.projectId, detail.value.projectName || detail.value.merchantName || '')
  if (proxy.$refs.aiRepoMappingRef) {
    proxy.resetForm('aiRepoMappingRef')
  }
}

function createDefaultProjectVendorMapForm(projectId, projectName) {
  return {
    projectId,
    projectName: projectName || '',
    venderNo: ''
  }
}

function resetProjectVendorMapForm() {
  projectVendorMapForm.value = createDefaultProjectVendorMapForm(
    detail.value.projectId,
    detail.value.projectName || detail.value.merchantName || ''
  )
  if (proxy.$refs.projectVendorMapRef) {
    proxy.resetForm('projectVendorMapRef')
  }
}

function openProjectVendorMapDialog() {
  if (!detail.value.projectId) {
    proxy.$modal.msgWarning('当前工单缺少项目，无法维护商家映射')
    return
  }
  projectVendorMapLoading.value = true
  getTicketLogPullProjectVendorMap(detail.value.projectId).then(response => {
    const row = response.data || {}
    projectVendorMapForm.value = {
      projectId: row.projectId || detail.value.projectId,
      projectName: row.projectName || detail.value.projectName || detail.value.merchantName || '',
      venderNo: row.venderNo || ''
    }
  }).catch(() => {
    resetProjectVendorMapForm()
  }).finally(() => {
    projectVendorMapLoading.value = false
    projectVendorMapOpen.value = true
  })
}

function submitProjectVendorMap() {
  proxy.$refs.projectVendorMapRef.validate(valid => {
    if (!valid) return
    projectVendorMapSubmitting.value = true
    const payload = {
      projectId: projectVendorMapForm.value.projectId,
      projectName: projectVendorMapForm.value.projectName,
      venderNo: projectVendorMapForm.value.venderNo
    }
    saveTicketLogPullProjectVendorMap(payload).then(() => {
      proxy.$modal.msgSuccess('商家映射保存成功')
      projectVendorMapOpen.value = false
      loadProjectVendorMapOptions()
    }).finally(() => {
      projectVendorMapSubmitting.value = false
    })
  })
}

function loadAiRepoMappings(silent = false) {
  if (!detail.value.projectId) {
    aiRepoMappingList.value = []
    aiRepoMappingTotal.value = 0
    return Promise.resolve()
  }
  if (!silent) {
    aiRepoMappingLoading.value = true
  }
  const query = {
    pageNum: 1,
    pageSize: 50,
    projectId: detail.value.projectId
  }
  return listTicketAiRepoMappings(query).then(response => {
    aiRepoMappingList.value = response.rows || []
    aiRepoMappingTotal.value = response.total || 0
  }).finally(() => {
    if (!silent) {
      aiRepoMappingLoading.value = false
    }
  })
}

function loadAiAnalysisTasks(silent = false) {
  if (!currentTicketId.value) {
    return Promise.resolve()
  }
  if (!silent) {
    aiTaskLoading.value = true
  }
  return listTicketAiAnalysisTasks(currentTicketId.value, aiTaskQuery.value).then(response => {
    aiTaskList.value = response.rows || []
    aiTaskTotal.value = response.total || 0
  }).finally(() => {
    if (!silent) {
      aiTaskLoading.value = false
    }
  })
}

function refreshAiAnalysisData(refreshTicketList = false) {
  if (!currentTicketId.value) {
    return Promise.resolve()
  }
  aiAnalysisRefreshLoading.value = true
  const tasks = [refreshDetail(), loadAiAnalysisTasks(true)]
  if (refreshTicketList) {
    tasks.push(getList())
  }
  return Promise.all(tasks).finally(() => {
    aiAnalysisRefreshLoading.value = false
  })
}

function canRetryAiTask(row) {
  return Boolean(row?.taskId) && ['failed', 'canceled'].includes(String(row.status || '').toLowerCase())
}

function resetAiAnalysisDialog() {
  aiAnalysisTaskForm.value.versionKey = detail.value.versionKey || detail.value.extraData?.versionKey || ''
  aiAnalysisTaskForm.value.agentCode = detail.value.extraData?.ticketAutomation?.logPullConfig?.aiAgentCode
    || detail.value.extraData?.ticket_automation?.log_pull_config?.aiAgentCode
    || detail.value.latestAiAnalysis?.analysisContext?.selectedAgentCode
    || ''
  aiAnalysisTaskForm.value.aiProviderCode = detail.value.extraData?.ticketAutomation?.logPullConfig?.aiProviderCode
    || detail.value.extraData?.ticket_automation?.log_pull_config?.aiProviderCode
    || detail.value.latestAiAnalysis?.analysisContext?.selectedAiProviderCode
    || ''
  aiAnalysisTaskForm.value.forceRefresh = false
  aiAnalysisTaskForm.value.extraInstruction = ''
  aiAnalysisTaskForm.value.promptTemplateCodes = detail.value.latestAiAnalysis?.analysisContext?.selectedPromptTemplateCodes || []
}

function openAiAnalysisDialog() {
  if (!detail.value.projectId) {
    proxy.$modal.msgWarning('当前工单缺少项目，无法发起AI分析')
    return
  }
  if (!detail.value.versionKey && !detail.value.extraData?.versionKey) {
    proxy.$modal.msgWarning('当前工单缺少版本号，请先完善版本号信息')
    return
  }
  resetAiAnalysisDialog()
  aiAnalysisTaskForm.value.versionKey = detail.value.versionKey || detail.value.extraData?.versionKey || aiAnalysisTaskForm.value.versionKey || ''
  aiAnalysisOpen.value = true
}

function openAiTaskHistory() {
  aiTaskHistoryOpen.value = true
  loadAiAnalysisTasks()
}

function openAiTaskDetail(row) {
  if (!row) {
    return
  }
  selectedAiTask.value = row
  aiTaskDetailOpen.value = true
}

function submitAiAnalysis() {
  proxy.$refs.aiAnalysisRef.validate(valid => {
    if (!valid) return
    if (!aiAnalysisTaskForm.value.versionKey) {
      proxy.$modal.msgWarning('请先完善版本号信息')
      return
    }
    aiAnalysisSubmitting.value = true
    addTicketAiAnalysis(currentTicketId.value, {
      versionKey: aiAnalysisTaskForm.value.versionKey,
      agentCode: aiAnalysisTaskForm.value.agentCode || undefined,
      aiProviderCode: aiAnalysisTaskForm.value.aiProviderCode || undefined,
      forceRefresh: aiAnalysisTaskForm.value.forceRefresh,
      extraInstruction: aiAnalysisTaskForm.value.extraInstruction || undefined,
      promptTemplateCodes: aiAnalysisTaskForm.value.promptTemplateCodes?.length
        ? aiAnalysisTaskForm.value.promptTemplateCodes
        : undefined
    }).then(() => {
      proxy.$modal.msgSuccess('AI分析任务已提交')
      aiAnalysisOpen.value = false
      refreshAiAnalysisData(true)
    }).finally(() => {
      aiAnalysisSubmitting.value = false
    })
  })
}

function retryAiAnalysisTask(row) {
  if (!row?.taskId) {
    return
  }
  proxy.$modal.confirm(`是否确认重试 AI 分析任务 #${row.taskId}？`).then(() => {
    aiAnalysisRetryLoading.value = true
    return retryTicketAiAnalysis(currentTicketId.value, row.taskId)
  }).then(() => {
    proxy.$modal.msgSuccess('AI分析任务已重新提交')
    return Promise.all([loadAiAnalysisTasks(true), refreshDetail(), getList()])
  }).catch(() => {}).finally(() => {
    aiAnalysisRetryLoading.value = false
  })
}

function openAiRepoMappingDialog(row) {
  if (!detail.value.projectId) {
    proxy.$modal.msgWarning('当前工单缺少项目，无法维护映射')
    return
  }
  if (row) {
    aiRepoMappingForm.value = {
      mappingId: row.mappingId,
      projectId: row.projectId,
      projectName: row.projectName || detail.value.projectName || '',
      versionKey: row.versionKey || '',
      repoUrl: row.repoUrl || '',
      branchName: row.branchName || '',
      localRepoPath: row.localRepoPath || '',
      workspaceRoot: row.workspaceRoot || '',
      workerCommand: row.workerCommand || '',
      isDefault: Boolean(row.isDefault),
      enabled: row.enabled !== false,
      remark: row.remark || ''
    }
  } else {
    resetAiRepoMappingForm()
  }
  aiRepoMappingOpen.value = true
  loadAiRepoMappings(true)
}

function submitAiRepoMapping() {
  proxy.$refs.aiRepoMappingRef.validate(valid => {
    if (!valid) return
    aiRepoMappingSubmitting.value = true
    const payload = { ...aiRepoMappingForm.value }
    const request = payload.mappingId ? updateTicketAiRepoMapping(payload) : addTicketAiRepoMapping(payload)
    request.then(() => {
      proxy.$modal.msgSuccess(payload.mappingId ? '映射更新成功' : '映射新增成功')
      aiRepoMappingOpen.value = false
      loadAiRepoMappings(true)
    }).finally(() => {
      aiRepoMappingSubmitting.value = false
    })
  })
}

function deleteAiRepoMapping(row) {
  if (!row?.mappingId) {
    return
  }
  proxy.$modal.confirm(`是否确认删除版本映射 "${row.versionKey}"？`).then(() => {
    aiRepoMappingLoading.value = true
    return delTicketAiRepoMapping(row.mappingId)
  }).then(() => {
    proxy.$modal.msgSuccess('删除成功')
    loadAiRepoMappings(true)
  }).catch(() => {}).finally(() => {
    aiRepoMappingLoading.value = false
  })
}

function openDetail(row) {
  currentTicketId.value = row.ticketId
  detailOpen.value = true
  detailMainTab.value = 'overview'
  historyActiveTab.value = 'timeline'
  descriptionExpanded.value = true
  translationExpanded.value = false
  logPullContentOpen.value = false
  logPullSubmitOpen.value = false
  aiTaskHistoryOpen.value = false
  aiTaskDetailOpen.value = false
  timeline.value = {}
  commentList.value = []
  commentLoaded.value = false
  ticketMessages.value = []
  ticketSnapshots.value = []
  similarTickets.value = []
  rcaForm.value = {}
  logPullList.value = []
  aiTaskList.value = []
  aiTaskTotal.value = 0
  selectedAiTask.value = null
  aiRepoMappingList.value = []
  aiRepoMappingTotal.value = 0
  selectedLogPullRecord.value = null
  selectedLogPullContent.value = null
  logPullKeyword.value = ''
  logPullQuery.value.pageNum = 1
  resetLogPullForm()
  resetMessageForm()
  getTicket(row.ticketId).then(response => {
    syncDetailBundle(response.data || {})
    loadDetailVersionOptions(detail.value.projectId)
    aiAnalysisTaskForm.value.mappingId = detail.value.latestAiAnalysis?.mappingId || aiAnalysisTaskForm.value.mappingId
  })
}

function handleTranslateDescription() {
  if (!detail.value.ticketId || descriptionTranslateLoading.value) {
    return
  }
  if (!detailOriginalDescription.value) {
    proxy.$modal.msgWarning('当前工单描述为空，无法翻译')
    return
  }
  descriptionTranslateLoading.value = true
  translateTicketDescription(detail.value.ticketId).then(response => {
    syncDetailBundle(response.data || detail.value)
    proxy.$modal.msgSuccess(response.msg || '翻译成功')
    getList()
  }).finally(() => {
    descriptionTranslateLoading.value = false
  })
}

function resetDetailDialog() {
  detailMainTab.value = 'overview'
  historyActiveTab.value = 'timeline'
  descriptionExpanded.value = true
  translationExpanded.value = false
  detail.value = {}
  detailVersionOptions.value = []
  timeline.value = {}
  commentList.value = []
  commentLoaded.value = false
  commentLoading.value = false
  logPullContentOpen.value = false
  logPullSubmitOpen.value = false
  aiTaskHistoryOpen.value = false
  aiTaskDetailOpen.value = false
  selectedAiTask.value = null
  aiAnalysisOpen.value = false
  aiRepoMappingOpen.value = false
  projectVendorMapOpen.value = false
  stopLogPullAutoRefresh()
}

function switchDetailSection(section) {
  detailMainTab.value = section
  handleDetailTabClick({ props: { name: section } })
}

function handleDetailTabClick(tab) {
  const tabName = tab?.props?.name || tab?.paneName || tab?.name
  if (tabName === 'history') {
    if (!timeline.value?.statusHistory && !timeline.value?.events) {
      refreshTimeline()
    }
    return
  }
  if (tabName === 'comments') {
    loadComments()
    return
  }
  if (tabName === 'logPull') {
    loadLogPullList()
    return
  }
  if (tabName === 'collab') {
    aiAnalysisTaskForm.value.mappingId = detail.value.latestAiAnalysis?.mappingId || aiAnalysisTaskForm.value.mappingId
  }
}

function handleHistoryTabClick(tab) {
  const tabName = tab?.props?.name || tab?.paneName || tab?.name
  if (tabName === 'timeline' || tabName === 'events' || tabName === 'rca') {
    if (!timeline.value?.statusHistory && !timeline.value?.events) {
      refreshTimeline()
    }
    return
  }
}

function refreshTimeline() {
  return getTicketTimeline(currentTicketId.value).then(response => {
    timeline.value = response.data || {}
    rcaForm.value = timeline.value.rca || rcaForm.value
  })
}

function loadComments(force = false) {
  if (!currentTicketId.value || commentLoading.value || (commentLoaded.value && !force)) {
    return Promise.resolve()
  }
  commentLoading.value = true
  return getTicketComments(currentTicketId.value).then(response => {
    commentList.value = response.data || []
    commentLoaded.value = true
  }).finally(() => {
    commentLoading.value = false
  })
}

function submitComment() {
  if (!commentForm.value.content) {
    proxy.$modal.msgWarning('请填写评论内容')
    return
  }
  addTicketComment(currentTicketId.value, commentForm.value).then(() => {
    proxy.$modal.msgSuccess('评论成功')
    commentForm.value = { content: '', isInternal: false }
    Promise.all([loadComments(true), refreshDetail()])
  })
}

function resetMessageForm() {
  messageForm.value = {
    role: 'user',
    messageType: 'question',
    content: '',
    runAi: true,
    versionKey: detail.value.versionKey || detail.value.extraData?.versionKey || '',
    agentCode: detail.value.latestAiAnalysis?.agentCode
      || detail.value.latestAiAnalysis?.analysisContext?.selectedAgentCode
      || '',
    aiProviderCode: detail.value.latestAiAnalysis?.aiProviderCode
      || detail.value.latestAiAnalysis?.analysisContext?.selectedAiProviderCode
      || detail.value.extraData?.ticketAutomation?.logPullConfig?.aiProviderCode
      || detail.value.extraData?.ticket_automation?.log_pull_config?.aiProviderCode
      || ''
  }
  messageDataText.value = ''
}

function parseMessageAttachments() {
  if (!messageDataText.value) {
    return undefined
  }
  try {
    return JSON.parse(messageDataText.value)
  } catch (error) {
    proxy.$modal.msgError('消息附件必须是合法 JSON')
    return null
  }
}

function submitMessage() {
  const content = String(messageForm.value.content || '').trim()
  if (!content) {
    proxy.$modal.msgWarning('请填写消息内容')
    return
  }
  messageForm.value.versionKey = detail.value.versionKey || detail.value.extraData?.versionKey || messageForm.value.versionKey || ''
  const attachments = parseMessageAttachments()
  if (attachments === null) {
    return
  }
  addTicketMessage(currentTicketId.value, {
    ...messageForm.value,
    content,
    attachments
  }).then(response => {
    const payload = response.data || response || {}
    const aiResult = payload.result || {}
    if (messageForm.value.runAi && !aiResult.aiSuccess) {
      proxy.$modal.msgWarning(aiResult.aiMessage || payload.message || '消息已保存，但AI追问未发起')
    } else {
      proxy.$modal.msgSuccess(payload.message || (aiResult.aiSuccess ? 'AI追问任务已提交' : '消息提交成功'))
    }
    resetMessageForm()
    const refreshTasks = [refreshDetail(), getList()]
    if (aiResult.aiSuccess) {
      refreshTasks.push(loadAiAnalysisTasks(true))
    }
    Promise.all(refreshTasks)
  })
}

function saveSnapshotFromCurrentState() {
  return addTicketSnapshot(currentTicketId.value, {
    summary: latestSnapshotSummary.value || detail.value.description || '',
    rootCause: detail.value.rootCause || '',
    solution: detail.value.solution || '',
    prevention: latestSnapshot.value?.prevention || '',
    risk: latestSnapshot.value?.risk || '',
    owner: detail.value.currentAssigneeName || '',
    sourceType: 'manual',
    structuredData: {
      ticketId: detail.value.ticketId,
      rootCause: detail.value.rootCause,
      solution: detail.value.solution
    }
  }).then(() => {
    proxy.$modal.msgSuccess('快照已保存')
    return Promise.all([refreshDetail()])
  })
}

function generateKnowledgeFromTicket() {
  extractTicketKnowledge(currentTicketId.value).then(() => {
    proxy.$modal.msgSuccess('知识库案例已生成')
    Promise.all([refreshDetail(), getList()])
  })
}

function submitEvent() {
  let eventData
  if (eventDataText.value) {
    try {
      eventData = JSON.parse(eventDataText.value)
    } catch (error) {
      proxy.$modal.msgError('结构化数据必须是合法 JSON')
      return
    }
  }
  addTicketEvent(currentTicketId.value, { ...eventForm.value, eventData }).then(() => {
    proxy.$modal.msgSuccess('事件记录成功')
    eventForm.value = { eventType: 'ANALYSIS', content: '' }
    eventDataText.value = ''
    Promise.all([refreshTimeline(), refreshDetail()])
  })
}

function submitRca() {
  saveTicketRca(currentTicketId.value, rcaForm.value).then(() => {
    proxy.$modal.msgSuccess('RCA保存成功')
    Promise.all([refreshTimeline(), refreshDetail()])
  })
}

function submitLogPull() {
  proxy.$refs.logPullRef.validate(valid => {
    if (!valid) return
    if (Number(logPullForm.value.commandDataType) === 2 && !String(logPullForm.value.path || '').trim()) {
      proxy.$modal.msgWarning('数据类型为数据库时，path 不能为空')
      return
    }
    if (Number(logPullForm.value.commandDataType) !== 2 && !logPullForm.value.modifyTime) {
      proxy.$modal.msgWarning('数据类型为日志时，modifyTime 不能为空')
      return
    }
    const timeRangeError = getOptionalLogPullTimeRangeError(logPullForm.value)
    if (timeRangeError) {
      proxy.$modal.msgWarning(timeRangeError)
      return
    }
    if (
      logPullForm.value.autoAiEnabled
      && !String(logPullForm.value.aiAgentCode || '').trim()
      && !String(logPullForm.value.aiProviderCode || '').trim()
    ) {
      proxy.$modal.msgWarning('启用自动AI分析时，请先选择Provider或Agent')
      return
    }
    const payload = {
      vendorId: logPullForm.value.vendorId,
      storeId: logPullForm.value.storeId,
      posNo: logPullForm.value.posNo,
      commandDataType: logPullForm.value.commandDataType,
      fileMaxSize: logPullForm.value.fileMaxSize,
      zipMaxSize: logPullForm.value.zipMaxSize,
      storageMode: logPullForm.value.storageMode,
      notifyConfig: normalizeLogPullNotifyConfig(logPullForm.value.notifyConfig)
    }
    if (Number(logPullForm.value.commandDataType) === 2) {
      payload.path = logPullForm.value.path
    } else {
      payload.modifyTime = logPullForm.value.modifyTime
    }
    Object.assign(payload, buildOptionalLogPullTimeRangePayload(logPullForm.value))
    payload.autoAiEnabled = Boolean(logPullForm.value.autoAiEnabled)
    payload.aiAgentCode = logPullForm.value.autoAiEnabled ? String(logPullForm.value.aiAgentCode || '').trim() : ''
    payload.aiProviderCode = logPullForm.value.autoAiEnabled ? String(logPullForm.value.aiProviderCode || '').trim() : ''
    logPullSubmitting.value = true
    addTicketLogPull(currentTicketId.value, payload).then(() => {
      proxy.$modal.msgSuccess('日志拉取任务已提交')
      logPullSubmitOpen.value = false
      resetLogPullForm()
      Promise.all([loadLogPullList(true), refreshDetail(), getList()])
    }).finally(() => {
      logPullSubmitting.value = false
    })
  })
}

function runLogPullAction(actionPromise, successMessage, refreshContent = false) {
  logPullActionLoading.value = true
  return actionPromise
    .then(() => {
      proxy.$modal.msgSuccess(successMessage)
      return Promise.all([loadLogPullList(true), refreshDetail(), getList()])
    })
    .then(() => {
      if (refreshContent && selectedLogPullRecord.value?.id) {
        return refreshLogPullContent()
      }
      return undefined
    })
    .finally(() => {
      logPullActionLoading.value = false
    })
}

function deleteLogPull(row) {
  if (!row?.id) {
    return
  }
  if (activeLogPullStatuses.includes(row.status)) {
    proxy.$modal.msgWarning('当前日志拉取任务仍在执行中，不能删除')
    return
  }
  proxy.$modal.confirm(`是否确认删除日志拉取记录 #${row.id}？删除后会同步清理关联文件数据。`).then(() => {
    logPullActionLoading.value = true
    return delTicketLogPull(row.id)
  }).then(() => {
    proxy.$modal.msgSuccess('日志拉取记录已删除')
    if (selectedLogPullRecord.value?.id === row.id) {
      logPullContentOpen.value = false
      selectedLogPullRecord.value = null
      selectedLogPullContent.value = null
      logPullKeyword.value = ''
    }
    return Promise.all([loadLogPullList(true), refreshDetail(), getList()])
  }).catch(() => {}).finally(() => {
    logPullActionLoading.value = false
  })
}

function retryLogPull(row) {
  if (!row?.id) {
    return
  }
  if (activeLogPullStatuses.includes(row.status)) {
    proxy.$modal.msgWarning('当前日志拉取任务仍在执行中，不能重新拉取')
    return
  }
  runLogPullAction(retryTicketLogPull(row.id), '已重新提交拉取任务')
}

function redownloadLogPull(row) {
  if (!row?.id) {
    return
  }
  if (!row.commandResultUrl && !row.storagePath) {
    proxy.$modal.msgWarning('当前记录缺少可用于重新下载的归档地址')
    return
  }
  runLogPullAction(redownloadTicketLogPull(row.id), '日志压缩包已重新下载', true)
}

function openBrowserDownload(url) {
  const targetUrl = String(url || '').trim()
  if (!targetUrl) {
    return false
  }
  window.open(targetUrl, '_blank', 'noopener')
  return true
}

function resolveLogPullDownloadFileName(row, source = 'auto') {
  let remoteName = ''
  if (row?.commandResultUrl) {
    try {
      remoteName = new URL(String(row.commandResultUrl)).pathname.split('/').pop() || ''
    } catch (error) {
      remoteName = String(row.commandResultUrl).split('/').pop() || ''
    }
  }
  const candidates = [
    row?.downloadFileName,
    source !== 'original' && row?.storagePath ? String(row.storagePath).split(/[\\/]/).pop() : '',
    remoteName,
    `ticket_log_pull_${row?.id || Date.now()}.zip`
  ]
  for (const candidate of candidates) {
    const text = String(candidate || '').trim()
    if (text) {
      return text
    }
  }
  return `ticket_log_pull_${row?.id || Date.now()}.zip`
}

async function downloadLogPullFile(row, source, emptyMessage) {
  if (!row?.id) {
    return
  }
  try {
    logPullActionLoading.value = true
    const blob = await downloadTicketLogPull(row.id, source)
    if (!blobValidate(blob)) {
      try {
        const text = await blob.text()
        const payload = JSON.parse(text)
        proxy.$modal.msgError(payload.msg || emptyMessage || '下载失败')
      } catch (error) {
        proxy.$modal.msgError(emptyMessage || '下载失败')
      }
      return
    }
    saveAs(blob, resolveLogPullDownloadFileName(row, source))
  } catch (error) {
    console.error(error)
    proxy.$modal.msgError(emptyMessage || '下载失败')
  } finally {
    logPullActionLoading.value = false
  }
}

function downloadLogPullArchive(row) {
  if (!row?.storagePath) {
    proxy.$modal.msgWarning('当前记录缺少本服务归档地址')
    return
  }
  if (/^https?:\/\//i.test(String(row.storagePath))) {
    openBrowserDownload(row.storagePath)
    return
  }
  downloadLogPullFile(row, 'service', '本服务归档文件不存在或不可下载')
}

function downloadLogPullOriginal(row) {
  if (!row?.commandResultUrl) {
    proxy.$modal.msgWarning('当前记录缺少原始压缩包地址')
    return
  }
  openBrowserDownload(row.commandResultUrl)
}

function reextractLogPull(row = selectedLogPullRecord.value) {
  if (!row?.id) {
    return
  }
  const useCurrentView = detailOpen.value && selectedLogPullRecord.value?.id === row.id
  const query = useCurrentView
    ? buildLogPullViewQuery()
    : {
        viewMode: 'archive',
        logBeginTime: row.logBeginTime,
        logEndTime: row.logEndTime
      }
  if (useCurrentView && logPullViewForm.value.viewMode !== 'archive') {
    proxy.$modal.msgWarning('请先切换到原始文档并指定查询时间范围')
    return
  }
  if (!query.logBeginTime || !query.logEndTime) {
    proxy.$modal.msgWarning('重新截取时开始时间和结束时间必填')
    return
  }
  logPullActionLoading.value = true
  reextractTicketLogPull(row.id, query)
    .then(() => {
      proxy.$modal.msgSuccess('日志已按当前时间范围重新截取')
      return Promise.all([loadLogPullList(true), refreshDetail(), getList()])
    })
    .then(() => {
      logPullViewForm.value.viewMode = 'stored'
      if (selectedLogPullRecord.value?.id === row.id) {
        return refreshLogPullContent()
      }
      return undefined
    })
    .finally(() => {
      logPullActionLoading.value = false
    })
}

function loadProjectOptions() {
  return listTicketProjectOptions().then(response => {
    projectOptions.value = response.data || []
  })
}

function loadAgentOptions() {
  return listAllAgents().then(response => {
    const rows = response.data || []
    agentOptions.value = Array.isArray(rows) ? rows : []
  })
}

function loadQueryModuleOptions(projectId) {
  return listTicketModuleOptions(projectId ? { projectId } : {}).then(response => {
    queryModuleOptions.value = response.data || []
  })
}

function loadFormModuleOptions(projectId) {
  if (!projectId) {
    formModuleOptions.value = []
    return Promise.resolve()
  }
  return listTicketModuleOptions(projectId ? { projectId } : {}).then(response => {
    formModuleOptions.value = response.data || []
    const option = resolveFormModuleOption(form.value.moduleId)
    if (option) {
      form.value.moduleId = option.moduleId
      form.value.moduleName = option.moduleName || ''
    }
    syncFormModuleValueFromForm()
  })
}

function loadFormVersionOptions(projectId) {
  if (!projectId) {
    formVersionOptions.value = []
    return Promise.resolve()
  }
  return listTicketAiRepoMappings({
    pageNum: 1,
    pageSize: 200,
    projectId,
    enabled: true
  }).then(response => {
    const rows = response.rows || []
    const optionMap = new Map()
    rows.forEach(item => {
      const value = String(item.versionKey || '').trim()
      if (!value || optionMap.has(value)) {
        return
      }
      const branchName = String(item.branchName || '').trim()
      const repoUrl = String(item.repoUrl || '').trim()
      const labelParts = [value]
      if (branchName) {
        labelParts.push(`- ${branchName}`)
      }
      if (repoUrl) {
        labelParts.push(`(${repoUrl})`)
      }
      optionMap.set(value, {
        value,
        label: labelParts.join(' ')
      })
    })
    formVersionOptions.value = Array.from(optionMap.values())
  })
}

function viewLogPullContent(row) {
  if (!row?.id) {
    return
  }
  const previousRecordId = selectedLogPullRecord.value?.id
  selectedLogPullRecord.value = row
  logPullViewForm.value = {
    viewMode: 'stored',
    logBeginTime: row?.logBeginTime || undefined,
    logEndTime: row?.logEndTime || undefined
  }
  logPullWrapEnabled.value = false
  logPullContentOpen.value = true
  if (previousRecordId !== row.id) {
    logPullKeyword.value = ''
  }
  logPullContentLoading.value = true
  selectedLogPullContent.value = null
  getTicketLogPullContent(row.id, buildLogPullViewQuery()).then(response => {
    const payload = response?.data || {}
    selectedLogPullContent.value = {
      ...payload,
      text: decodeLogText(payload?.text || payload?.content || payload?.compressedContent || '')
    }
  }).finally(() => {
    logPullContentLoading.value = false
  })
}

function openTicketLogViewer(row) {
  if (!row?.ticketId) {
    return
  }
  logViewerSearching.value = true
  prepareTicketLogs(row.ticketId).then(() => {
    detail.value = row
    currentTicketId.value = row.ticketId
    selectedLogPullRecord.value = {
      id: undefined,
      ticketId: row.ticketId,
      storagePath: row.latestLogPull?.storagePath || '',
      commandResultUrl: row.latestLogPull?.commandResultUrl || ''
    }
    selectedLogPullContent.value = null
    logPullViewForm.value = {
      viewMode: 'stored',
      logBeginTime: undefined,
      logEndTime: undefined
    }
    resetLogViewerState(row.ticketId)
    logPullContentOpen.value = true
  }).finally(() => {
    logViewerSearching.value = false
  })
}

function handleLogPullDialogClosed() {
  logPullKeyword.value = ''
  logPullWrapEnabled.value = false
  logViewerHits.value = []
  logViewerContext.value = null
  logViewerErrorSummary.value = null
}

function resetLogPullViewRange(row = selectedLogPullRecord.value) {
  logPullViewForm.value.logBeginTime = row?.logBeginTime || undefined
  logPullViewForm.value.logEndTime = row?.logEndTime || undefined
}

function buildLogPullViewQuery() {
  return {
    viewMode: logPullViewForm.value.viewMode,
    logBeginTime: logPullViewForm.value.logBeginTime,
    logEndTime: logPullViewForm.value.logEndTime
  }
}

function refreshLogPullContent() {
  if (!selectedLogPullRecord.value?.id) {
    return
  }
  logPullContentLoading.value = true
  getTicketLogPullContent(selectedLogPullRecord.value.id, buildLogPullViewQuery()).then(response => {
    const payload = response?.data || {}
    selectedLogPullContent.value = {
      ...payload,
      text: decodeLogText(payload?.text || payload?.content || payload?.compressedContent || '')
    }
  }).finally(() => {
    logPullContentLoading.value = false
  })
}

function resetLogViewerState(ticketId = currentTicketId.value) {
  logViewerForm.value = {
    ticketId,
    keyword: '',
    time: '',
    contextLines: 20
  }
  logViewerHits.value = []
  logViewerContext.value = null
  logViewerErrorSummary.value = null
}

function buildLogViewerPayload(keywordField = 'keyword') {
  const contextLines = Number(logViewerForm.value.contextLines || 0)
  const payload = {
    ticketId: currentTicketId.value || selectedLogPullRecord.value?.ticketId || logViewerForm.value.ticketId,
    contextBefore: contextLines,
    contextAfter: contextLines,
    limit: 100,
    withContext: true
  }
  payload[keywordField] = logViewerForm.value[keywordField]
  return payload
}

function searchLogViewerKeyword() {
  const keyword = String(logViewerForm.value.keyword || '').trim()
  if (!keyword) {
    proxy.$modal.msgWarning('请输入搜索关键字')
    return
  }
  const payload = buildLogViewerPayload('keyword')
  logViewerSearching.value = true
  searchTicketLogs(payload).then(response => {
    setLogViewerHits(response?.data || [])
  }).finally(() => {
    logViewerSearching.value = false
  })
}

function searchLogViewerTime() {
  const time = String(logViewerForm.value.time || '').trim()
  if (!time) {
    proxy.$modal.msgWarning('请输入时间关键字')
    return
  }
  const payload = buildLogViewerPayload('time')
  logViewerSearching.value = true
  searchTicketLogsByTime(payload).then(response => {
    setLogViewerHits(response?.data || [])
  }).finally(() => {
    logViewerSearching.value = false
  })
}

function loadLogViewerErrors() {
  const ticketId = currentTicketId.value || selectedLogPullRecord.value?.ticketId || logViewerForm.value.ticketId
  if (!ticketId) {
    return
  }
  logViewerSearching.value = true
  getTicketLogErrors({ ticketId, limit: 100 }).then(response => {
    logViewerErrorSummary.value = response?.data || null
    setLogViewerHits(logViewerErrorSummary.value?.samples || [])
  }).finally(() => {
    logViewerSearching.value = false
  })
}

function setLogViewerHits(rows = []) {
  logViewerHits.value = rows.map((item, index) => ({
    ...item,
    hitKey: `${item.file || ''}:${item.line || 0}:${index}`
  }))
  logViewerContext.value = logViewerHits.value[0]?.context || null
}

function selectLogViewerHit(row) {
  if (!row) {
    return
  }
  if (row.context) {
    logViewerContext.value = row.context
    return
  }
  loadLogViewerContext(row.file, row.line)
}

function pageLogViewerContext(direction) {
  const context = logViewerContext.value
  if (!context) {
    return
  }
  if (direction > 0) {
    loadLogViewerContext(context.nextFile || context.file, context.nextLine || context.end + 1)
    return
  }
  loadLogViewerContext(context.prevFile || context.file, context.prevLine || Math.max(context.start - 1, 1))
}

function loadLogViewerContext(file, line) {
  const ticketId = currentTicketId.value || selectedLogPullRecord.value?.ticketId || logViewerForm.value.ticketId
  if (!ticketId || !file || !line) {
    return
  }
  const contextLines = Number(logViewerForm.value.contextLines || 0)
  logViewerSearching.value = true
  getTicketLogContext({
    ticketId,
    file,
    line,
    before: contextLines,
    after: contextLines
  }).then(response => {
    logViewerContext.value = response?.data || null
  }).finally(() => {
    logViewerSearching.value = false
  })
}

function formatJson(value) {
  return JSON.stringify(value, null, 2)
}

function getAiStatusTagType(value) {
  const status = String(value || '')
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'warning'
  if (status === 'created') return 'info'
  return 'info'
}

function getAiStatusLabel(value) {
  const status = String(value || '')
  if (status === 'success') return '成功'
  if (status === 'failed') return '失败'
  if (status === 'running') return '执行中'
  if (status === 'created') return '待执行'
  return status || '-'
}

function formatAiConfidence(value) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  const numeric = Number(value)
  if (Number.isNaN(numeric)) {
    return String(value)
  }
  if (numeric > 0 && numeric <= 1) {
    return `${Math.round(numeric * 100)}%`
  }
  return numeric.toFixed ? numeric.toFixed(2) : String(numeric)
}

function formatSeconds(seconds) {
  if (!seconds) return '-'
  const hour = Math.floor(seconds / 3600)
  const minute = Math.floor((seconds % 3600) / 60)
  const second = seconds % 60
  return `${hour}小时${minute}分${second}秒`
}

watch(detailOpen, value => {
  if (!value) {
    resetDetailDialog()
  }
})

watch(
  () => queryParams.value.projectId,
  value => {
    queryParams.value.moduleId = undefined
    loadQueryModuleOptions(value)
  }
)

watch(
  () => form.value.projectId,
  value => {
    if (suppressProjectWatcher) {
      return
    }
    form.value.moduleId = undefined
    form.value.moduleName = ''
    formModuleValue.value = ''
    if (!open.value) {
      return
    }
    loadFormModuleOptions(value)
    loadFormVersionOptions(value)
  }
)

onBeforeUnmount(() => {
  stopLogPullAutoRefresh()
})

loadProjectOptions()
loadStatClassificationOptions()
loadProjectVendorMapOptions()
loadAgentOptions()
loadProviderOptions()
loadVendorOptions()
loadAnalysisPromptOptions()
loadPushOptions()
loadQueryModuleOptions()
loadWorkflowConfig().finally(() => {
  getList()
})
</script>

<style scoped>
.ticket-page :deep(.ticket-detail-dialog .el-dialog) {
  display: flex;
  flex-direction: column;
  height: 100vh;
  margin: 0;
}

.ticket-page :deep(.ticket-detail-dialog .el-dialog__header) {
  flex: 0 0 auto;
}

.ticket-page :deep(.ticket-detail-dialog .el-dialog__body) {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  padding-top: 8px;
  padding-bottom: 12px;
}

.ticket-detail-scroll {
  height: 100%;
  overflow: auto;
  padding-right: 4px;
}

.ticket-summary-descriptions :deep(.el-descriptions__label) {
  white-space: nowrap;
}

.ticket-detail-description {
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr);
  border: 1px solid var(--el-border-color-lighter);
  border-top: 0;
  font-size: 14px;
  line-height: 1.5;
}

.ticket-detail-description__label {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  justify-content: space-between;
  padding: 8px 11px;
  color: var(--el-text-color-regular);
  background: var(--el-fill-color-light);
  border-right: 1px solid var(--el-border-color-lighter);
  font-weight: 700;
  white-space: nowrap;
}

.ticket-detail-description__actions {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-end;
  line-height: 1.2;
}

.ticket-detail-description__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.ticket-detail-description__content {
  min-width: 0;
  padding: 8px 11px;
  color: var(--el-text-color-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.ticket-detail-description__content--collapsed {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.collab-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.ticket-page :deep(.ticket-detail-dialog .detail-main-tabs) {
  height: auto;
}

.mt16 {
  margin-top: 16px;
}

.mb16 {
  margin-bottom: 16px;
}

.mb8 {
  margin-bottom: 8px;
}

.ml12 {
  margin-left: 12px;
}

.mt12 {
  margin-top: 12px;
}

.mr8 {
  margin-right: 8px;
}

.import-result {
  margin-top: 16px;
}

.result-title {
  margin-bottom: 8px;
  color: #606266;
  font-weight: 600;
}

.record-head {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
  color: #606266;
  font-size: 13px;
}

.timeline-title {
  font-weight: 600;
  margin-bottom: 6px;
}

.timeline-content {
  color: #606266;
}

.json-block {
  padding: 10px;
  margin: 10px 0 0;
  overflow: auto;
  background: #f6f8fa;
  border-radius: 4px;
}

.similar-item {
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
}

.similar-item:last-child {
  border-bottom: 0;
}

.similar-title {
  margin-bottom: 4px;
  font-weight: 600;
}

.similar-meta {
  display: flex;
  gap: 10px;
  color: #606266;
  font-size: 12px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.log-view-controls {
  flex-wrap: wrap;
  justify-content: flex-start;
}

.log-view-time-picker {
  width: 220px;
}

.panel-inline {
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-main-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.history-entry-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.task-detail-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.task-detail-block {
  max-height: 46vh;
}

.time-range-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.log-filter-input {
  max-width: 360px;
}

.log-content-block {
  max-height: 420px;
  padding: 12px;
  margin: 0;
  overflow: auto;
  white-space: pre;
  word-break: normal;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.55;
}

.log-content-wrap {
  white-space: pre-wrap;
  word-break: break-word;
}

.log-content-dialog {
  max-height: 60vh;
}
</style>
