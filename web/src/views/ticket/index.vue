<template>
  <div class="app-container ticket-page">
    <template v-if="!standaloneDetailMode">
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
        <el-form-item label="状态" prop="statuses">
          <el-select
            v-model="queryParams.statuses"
            placeholder="工单状态"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            style="width: 180px"
          >
            <el-option
              v-for="item in ticketStatusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
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
        <el-form-item label="日志/AI进度" prop="processStatuses">
          <el-select
            v-model="queryParams.processStatuses"
            placeholder="日志/AI进度"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            style="width: 200px"
          >
            <el-option
              v-for="item in ticketProcessStatusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="处理结论" prop="processingConclusionStatus">
          <el-select
            v-model="queryParams.processingConclusionStatus"
            placeholder="处理结论"
            clearable
            style="width: 140px"
          >
            <el-option label="已处理" value="processed" />
            <el-option label="未处理" value="unprocessed" />
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
        <el-form-item label="处理时间">
          <el-date-picker
            v-model="processedTimeRange"
            type="datetimerange"
            value-format="YYYY-MM-DD HH:mm:ss"
            format="YYYY-MM-DD HH:mm:ss"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            style="width: 360px"
          />
        </el-form-item>
        <el-form-item label="项目" prop="projectIds">
          <el-select
            v-model="queryParams.projectIds"
            placeholder="所属项目"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            filterable
            style="width: 220px"
          >
            <el-option
              v-for="item in projectOptions"
              :key="item.projectId"
              :label="item.projectName"
              :value="item.projectId"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模块" prop="moduleIds">
          <el-select
            v-model="queryParams.moduleIds"
            placeholder="所属模块"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            filterable
            style="width: 220px"
          >
            <el-option
              v-for="item in queryModuleOptions"
              :key="item.moduleId"
              :label="item.moduleName"
              :value="item.moduleId"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模块Code" prop="moduleCodes">
          <el-select
            v-model="queryParams.moduleCodes"
            placeholder="模块Code"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            filterable
            style="width: 200px"
          >
            <el-option
              v-for="item in queryModuleCodeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="工单类型" prop="issueTypeIds">
          <el-select
            v-model="queryParams.issueTypeIds"
            placeholder="工单类型"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            filterable
            style="width: 180px"
          >
            <el-option
              v-for="item in issueTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="根因分类" prop="rootCauseTypes">
          <el-select
            v-model="queryParams.rootCauseTypes"
            placeholder="根因分类"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            filterable
            style="width: 180px"
          >
            <el-option
              v-for="item in rootCauseTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="解决方式" prop="solutionTypes">
          <el-select
            v-model="queryParams.solutionTypes"
            placeholder="解决方式"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            filterable
            style="width: 180px"
          >
            <el-option
              v-for="item in solutionTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关闭结果" prop="resolutionCodes">
          <el-select
            v-model="queryParams.resolutionCodes"
            placeholder="关闭结果"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            filterable
            style="width: 180px"
          >
            <el-option
              v-for="item in resolutionOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="细分问题" prop="problemPatternCodes">
          <el-select
            v-model="queryParams.problemPatternCodes"
            placeholder="细分问题"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            filterable
            style="width: 220px"
          >
            <el-option
              v-for="item in problemPatternOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="是否问题" prop="isProblems">
          <el-select
            v-model="queryParams.isProblems"
            placeholder="是否问题"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            style="width: 160px"
          >
            <el-option label="真实问题" :value="true" />
            <el-option label="非问题" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="内部优先级" prop="internalPriorities">
          <el-select
            v-model="queryParams.internalPriorities"
            placeholder="内部优先级"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            style="width: 160px"
          >
            <el-option
              v-for="item in priorityOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="当前处理人" prop="currentAssigneeIds">
          <UserSelect
            v-model="queryParams.currentAssigneeIds"
            multiple
            :initial-option="queryCurrentAssigneeOption"
            @change="handleQueryCurrentAssigneeChange"
          />
        </el-form-item>
        <el-form-item label="1线人员" prop="firstLineAssigneeIds">
          <UserSelect
            v-model="queryParams.firstLineAssigneeIds"
            multiple
            :initial-option="queryFirstLineAssigneeOption"
            @change="handleQueryFirstLineAssigneeChange"
          />
        </el-form-item>
        <el-form-item label="内部负责人" prop="internalOwnerIds">
          <UserSelect
            v-model="queryParams.internalOwnerIds"
            multiple
            :initial-option="queryInternalOwnerOption"
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
          <el-button
            type="primary"
            plain
            icon="Plus"
            @click="handleAdd"
            v-hasPermi="['ticket:ticket:add']"
          >
            新增
          </el-button>
        </el-col>
        <el-col :span="1.5">
          <el-button
            type="success"
            plain
            icon="Upload"
            @click="importOpen = true"
            v-hasPermi="['ticket:ticket:import']"
          >
            导入
          </el-button>
        </el-col>
        <el-col :span="1.5">
          <el-button
            type="warning"
            plain
            icon="Download"
            @click="downloadTemplate"
            v-hasPermi="['ticket:ticket:import']"
          >
            下载模板
          </el-button>
        </el-col>
        <el-col :span="1.5">
          <el-button plain icon="Setting" @click="columnConfigOpen = true">列设置</el-button>
        </el-col>
        <el-col :span="1.5">
          <el-button
            plain
            icon="Tickets"
            @click="openIssueManagement"
            v-hasPermi="['ticket:issue:list']"
          >
            问题实例管理
          </el-button>
        </el-col>
        <el-col :span="1.5">
          <el-button
            plain
            icon="EditPen"
            :disabled="selectedTicketRows.length === 0"
            @click="openReleaseBatchDialog"
            v-hasPermi="['ticket:ticket:edit']"
          >
            版本批量维护
          </el-button>
        </el-col>
        <el-col :span="1.5">
          <el-button
            plain
            icon="TrendCharts"
            @click="openVersionStatisticsDialog"
            v-hasPermi="['ticket:statistics:list']"
          >
            版本统计
          </el-button>
        </el-col>
        <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
      </el-row>

      <el-table
        v-loading="loading"
        border
        :data="ticketList"
        row-key="ticketId"
        :default-sort="{
          prop: queryParams.sortField,
          order: toElementSortOrder(queryParams.sortOrder),
        }"
        @sort-change="handleTicketSortChange"
        @selection-change="handleTicketSelectionChange"
      >
        <el-table-column type="selection" width="48" align="center" fixed="left" />
        <el-table-column
          v-if="isTicketColumnVisible('index')"
          label="序号"
          type="index"
          width="60"
          align="center"
        />
        <el-table-column
          v-if="isTicketColumnVisible('ticketNo')"
          label="工单编号"
          prop="ticketNo"
          width="190"
          sortable="custom"
          show-overflow-tooltip
        />
        <el-table-column
          v-if="isTicketColumnVisible('title')"
          label="标题"
          prop="title"
          min-width="240"
          sortable="custom"
          show-overflow-tooltip
        />
        <el-table-column
          v-if="isTicketColumnVisible('similarityScore')"
          label="相似度"
          prop="similarityScore"
          width="100"
          align="center"
        >
          <template #default="scope">
            <span v-if="scope.row.similarityScore != null">
              {{ (scope.row.similarityScore * 100).toFixed(1) }}%
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('issueNo')"
          label="问题编号"
          prop="issueNo"
          width="150"
          sortable="custom"
          show-overflow-tooltip
        >
          <template #default="scope">{{ scope.row.issueNo || '-' }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('issueConfirmed')"
          label="归因确认"
          prop="issueConfirmed"
          width="110"
          align="center"
          sortable="custom"
        >
          <template #default="scope">
            <el-tag v-if="scope.row.issueId && scope.row.issueConfirmed" type="success"
              >已确认</el-tag
            >
            <el-tag v-else-if="scope.row.issueId" type="warning">待确认</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('issueTitle')"
          label="问题标题"
          prop="issueTitle"
          min-width="180"
          show-overflow-tooltip
        >
          <template #default="scope">{{ scope.row.issueTitle || '-' }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('issueRelationType')"
          label="归因类型"
          prop="issueRelationType"
          width="110"
          sortable="custom"
          show-overflow-tooltip
        >
          <template #default="scope">{{
            formatIssueRelationType(scope.row.issueRelationType)
          }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('status')"
          label="状态"
          prop="status"
          width="120"
          align="center"
          sortable="custom"
        >
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope.row.status)">
              {{ getOptionLabel(ticketStatusOptions, scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('processStatus')"
          label="日志/AI进度"
          prop="processStatus"
          min-width="160"
          align="center"
          sortable="custom"
        >
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
        <el-table-column
          v-if="isTicketColumnVisible('processingConclusionStatus')"
          label="处理结论"
          prop="processingConclusionStatus"
          width="110"
          align="center"
          sortable="custom"
        >
          <template #default="scope">
            <el-tag v-if="scope.row.processedAt" type="success">已处理</el-tag>
            <el-tag v-else type="info">未处理</el-tag>
          </template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('project')"
          label="项目"
          prop="project"
          width="160"
          sortable="custom"
          show-overflow-tooltip
        >
          <template #default="scope">{{
            scope.row.projectName || scope.row.merchantName || '-'
          }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('moduleName')"
          label="模块"
          prop="moduleName"
          width="140"
          sortable="custom"
          show-overflow-tooltip
        />
        <el-table-column
          v-if="isTicketColumnVisible('issueType')"
          label="工单类型"
          prop="issueType"
          width="130"
          sortable="custom"
          show-overflow-tooltip
        >
          <template #default="scope">{{ formatIssueType(scope.row) }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('isProblem')"
          label="问题性质"
          prop="isProblem"
          width="100"
          align="center"
          sortable="custom"
        >
          <template #default="scope">
            <el-tag v-if="scope.row.isProblem === true" type="danger">真实问题</el-tag>
            <el-tag v-else-if="scope.row.isProblem === false" type="info">非问题</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('rootCauseType')"
          label="根因分类"
          prop="rootCauseType"
          width="130"
          sortable="custom"
          show-overflow-tooltip
        >
          <template #default="scope">{{
            formatStatOption(rootCauseTypeOptions, scope.row.rootCauseType)
          }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('solutionType')"
          label="解决方式"
          prop="solutionType"
          width="130"
          sortable="custom"
          show-overflow-tooltip
        >
          <template #default="scope">{{
            formatStatOption(solutionTypeOptions, scope.row.solutionType)
          }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('resolution')"
          label="关闭结果"
          prop="resolution"
          width="130"
          sortable="custom"
          show-overflow-tooltip
        >
          <template #default="scope">{{ formatResolution(scope.row) }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('problemPattern')"
          label="细分问题"
          prop="problemPattern"
          width="160"
          sortable="custom"
          show-overflow-tooltip
        >
          <template #default="scope">{{ formatProblemPattern(scope.row) }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('customerPriority')"
          label="对方优先级"
          prop="customerPriority"
          width="110"
          align="center"
          sortable="custom"
        />
        <el-table-column
          v-if="isTicketColumnVisible('internalPriority')"
          label="内部优先级"
          prop="internalPriority"
          width="110"
          align="center"
          sortable="custom"
        />
        <el-table-column
          v-if="isTicketColumnVisible('source')"
          label="来源"
          prop="source"
          width="110"
          sortable="custom"
        >
          <template #default="scope">{{
            getOptionLabel(sourceOptions, scope.row.source)
          }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('firstLineAssigneeName')"
          label="1线人员"
          prop="firstLineAssigneeName"
          width="130"
          sortable="custom"
          show-overflow-tooltip
        />
        <el-table-column
          v-if="isTicketColumnVisible('internalOwnerName')"
          label="内部负责人"
          prop="internalOwnerName"
          width="130"
          sortable="custom"
          show-overflow-tooltip
        />
        <el-table-column
          v-if="isTicketColumnVisible('currentAssigneeName')"
          label="当前处理人"
          prop="currentAssigneeName"
          width="130"
          sortable="custom"
          show-overflow-tooltip
        />
        <el-table-column
          v-if="isTicketColumnVisible('submitTime')"
          label="工单提交时间"
          prop="submitTime"
          width="170"
          sortable="custom"
        >
          <template #default="scope">{{
            parseTime(scope.row.submitTime || scope.row.externalCreateTime || scope.row.createTime)
          }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('firstResponseAt')"
          label="首次响应时间"
          prop="firstResponseAt"
          width="170"
          sortable="custom"
        >
          <template #default="scope">{{ parseTime(scope.row.firstResponseAt) }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('processedAt')"
          label="处理完成时间"
          prop="processedAt"
          width="170"
          sortable="custom"
        >
          <template #default="scope">{{ parseTime(scope.row.processedAt) }}</template>
        </el-table-column>
        <el-table-column
          v-if="isTicketColumnVisible('plannedFixVersion')"
          label="计划修复版本"
          prop="plannedFixVersion"
          width="140"
          sortable="custom"
          show-overflow-tooltip
        />
        <el-table-column
          v-if="isTicketColumnVisible('fixedVersion')"
          label="实际修复版本"
          prop="fixedVersion"
          width="140"
          sortable="custom"
          show-overflow-tooltip
        />
        <el-table-column
          v-if="isTicketColumnVisible('releasedVersion')"
          label="实际发版版本"
          prop="releasedVersion"
          width="140"
          sortable="custom"
          show-overflow-tooltip
        />
        <el-table-column
          v-if="isTicketColumnVisible('createTime')"
          label="创建时间"
          prop="createTime"
          width="170"
          sortable="custom"
        >
          <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
        </el-table-column>
        <el-table-column label="操作" align="center" width="450" fixed="right">
          <template #default="scope">
            <el-button
              link
              type="primary"
              icon="View"
              @click="openDetail(scope.row)"
              v-hasPermi="['ticket:ticket:query']"
            >
              详情
            </el-button>
            <el-button
              link
              type="primary"
              icon="Search"
              @click="openTicketLogViewer(scope.row)"
              v-hasPermi="['ticket:logpull:query']"
            >
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
            <el-button
              link
              type="primary"
              icon="Edit"
              @click="handleUpdate(scope.row)"
              v-hasPermi="['ticket:ticket:edit']"
            >
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

      <el-dialog title="工单列表列设置" v-model="columnConfigOpen" width="560px" append-to-body>
        <el-checkbox-group v-model="visibleTicketColumnKeys" class="ticket-column-config">
          <el-checkbox
            v-for="item in ticketColumnOptions"
            :key="item.key"
            :label="item.key"
            :disabled="item.required"
          >
            {{ item.label }}
          </el-checkbox>
        </el-checkbox-group>
        <template #footer>
          <el-button @click="resetTicketColumnConfig">恢复默认</el-button>
          <el-button type="primary" @click="saveTicketColumnConfig">保存</el-button>
        </template>
      </el-dialog>

      <el-dialog
        title="版本批量维护"
        v-model="releaseBatchOpen"
        width="720px"
        append-to-body
        @closed="resetReleaseBatchForm"
      >
        <el-alert
          type="info"
          :closable="false"
          show-icon
          :title="`已选择 ${selectedTicketRows.length} 张工单，空字段不会覆盖原值`"
          class="mb12"
        />
        <el-form ref="releaseBatchRef" :model="releaseBatchForm" label-width="120px">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="计划修复版本">
                <el-input v-model="releaseBatchForm.plannedFixVersion" maxlength="100" clearable />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="实际修复版本">
                <el-input v-model="releaseBatchForm.fixedVersion" maxlength="100" clearable />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="实际发版版本">
                <el-input v-model="releaseBatchForm.releasedVersion" maxlength="100" clearable />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="发版完成">
                <el-checkbox v-model="releaseBatchForm.markReleased">标记为已发版</el-checkbox>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="发版时间">
                <el-date-picker
                  v-model="releaseBatchForm.releasedAt"
                  type="datetime"
                  value-format="YYYY-MM-DD HH:mm:ss"
                  format="YYYY-MM-DD HH:mm:ss"
                  placeholder="留空则使用当前时间"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="验证完成">
                <el-checkbox v-model="releaseBatchForm.markVerified">标记为已验证</el-checkbox>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="验证时间">
                <el-date-picker
                  v-model="releaseBatchForm.verifiedAt"
                  type="datetime"
                  value-format="YYYY-MM-DD HH:mm:ss"
                  format="YYYY-MM-DD HH:mm:ss"
                  placeholder="留空则使用当前时间"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="维护说明">
                <el-input
                  v-model="releaseBatchForm.comment"
                  type="textarea"
                  :rows="3"
                  maxlength="500"
                  show-word-limit
                  placeholder="可选，写入发版/验证事件"
                />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
        <template #footer>
          <el-button :disabled="releaseBatchSubmitting" @click="releaseBatchOpen = false"
            >取 消</el-button
          >
          <el-button
            type="primary"
            :loading="releaseBatchSubmitting"
            :disabled="releaseBatchSubmitting"
            @click="submitReleaseBatch"
          >
            确 定
          </el-button>
        </template>
      </el-dialog>

      <el-dialog title="版本统计" v-model="versionStatisticsOpen" width="1180px" append-to-body>
        <div class="version-statistics-toolbar">
          <el-input
            v-model="versionStatisticsQuery.versionKeyword"
            placeholder="版本关键字"
            clearable
            style="width: 220px"
            @keyup.enter="loadVersionStatistics"
          />
          <el-button
            type="primary"
            icon="Search"
            :loading="versionStatisticsLoading"
            @click="loadVersionStatistics"
          >
            查询
          </el-button>
        </div>
        <el-tabs v-model="versionStatisticsTab">
          <el-tab-pane label="发生版本" name="affected">
            <el-table
              v-loading="versionStatisticsLoading"
              :data="versionStatistics.affectedVersionRows || []"
              max-height="520"
            >
              <el-table-column label="版本" prop="version" min-width="140" show-overflow-tooltip />
              <el-table-column label="工单数" prop="ticketCount" width="90" align="right" />
              <el-table-column label="真实问题" prop="problemCount" width="90" align="right" />
              <el-table-column label="Issue数" prop="issueCount" width="90" align="right" />
              <el-table-column label="未处理" prop="unprocessedCount" width="90" align="right" />
              <el-table-column label="未关闭" prop="openBacklog" width="90" align="right" />
              <el-table-column label="Top模块" min-width="180" show-overflow-tooltip>
                <template #default="scope">{{ formatTopRows(scope.row.topModules) }}</template>
              </el-table-column>
              <el-table-column label="Top类型" min-width="180" show-overflow-tooltip>
                <template #default="scope">{{ formatTopRows(scope.row.topIssueTypes) }}</template>
              </el-table-column>
              <el-table-column label="Top根因" min-width="180" show-overflow-tooltip>
                <template #default="scope">{{ formatTopRows(scope.row.topRootCauses) }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="修复/发版版本" name="fix">
            <el-table
              v-loading="versionStatisticsLoading"
              :data="versionStatistics.fixVersionRows || []"
              max-height="520"
            >
              <el-table-column label="版本" prop="version" min-width="140" show-overflow-tooltip />
              <el-table-column label="工单数" prop="ticketCount" width="90" align="right" />
              <el-table-column label="Issue数" prop="issueCount" width="90" align="right" />
              <el-table-column label="已发版" prop="releasedCount" width="90" align="right" />
              <el-table-column label="已验证" prop="verifiedCount" width="90" align="right" />
              <el-table-column label="未验证" prop="unverifiedCount" width="90" align="right" />
              <el-table-column label="关闭结果" min-width="190" show-overflow-tooltip>
                <template #default="scope">{{
                  formatTopRows(scope.row.resolutionCounts)
                }}</template>
              </el-table-column>
              <el-table-column label="解决方式" min-width="190" show-overflow-tooltip>
                <template #default="scope">{{
                  formatTopRows(scope.row.solutionTypeCounts)
                }}</template>
              </el-table-column>
              <el-table-column label="细分问题" min-width="190" show-overflow-tooltip>
                <template #default="scope">{{
                  formatTopRows(scope.row.topProblemPatterns)
                }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </el-dialog>

      <pagination
        v-show="total > 0"
        :total="total"
        v-model:page="queryParams.pageNum"
        v-model:limit="queryParams.pageSize"
        @pagination="getList"
      />
    </template>

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
                <el-option
                  v-for="item in projectOptions"
                  :key="item.projectId"
                  :label="item.projectName"
                  :value="item.projectId"
                />
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
                <el-option
                  v-for="item in formModuleOptions"
                  :key="item.moduleId"
                  :label="item.moduleName"
                  :value="String(item.moduleId)"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发生版本" prop="versionKey">
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
          <el-col :span="12">
            <el-form-item label="计划修复版本" prop="plannedFixVersion">
              <el-input
                v-model="form.plannedFixVersion"
                placeholder="请输入计划修复版本"
                maxlength="100"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="实际修复版本" prop="fixedVersion">
              <el-input
                v-model="form.fixedVersion"
                placeholder="请输入实际修复版本"
                maxlength="100"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="实际发版版本" prop="releasedVersion">
              <el-input
                v-model="form.releasedVersion"
                placeholder="请输入实际发版版本"
                maxlength="100"
              />
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
                <el-option
                  v-for="item in priorityOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="内部优先级" prop="internalPriority">
              <el-select v-model="form.internalPriority" placeholder="请选择">
                <el-option
                  v-for="item in priorityOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="来源" prop="source">
              <el-select v-model="form.source" placeholder="请选择" clearable>
                <el-option
                  v-for="item in sourceOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="严重等级" prop="severity">
              <el-select v-model="form.severity" placeholder="请选择" clearable>
                <el-option
                  v-for="item in severityOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="工单类型" prop="issueTypeId">
              <el-select
                v-model="form.issueTypeId"
                placeholder="请选择工单类型"
                clearable
                filterable
                @change="handleIssueTypeChange"
              >
                <el-option
                  v-for="item in issueTypeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
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
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="5"
                placeholder="请输入问题现象和上下文"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="根因分类">
              <el-select
                v-model="form.rootCauseType"
                placeholder="请选择根因分类"
                clearable
                filterable
              >
                <el-option
                  v-for="item in rootCauseTypeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="解决方式">
              <el-select
                v-model="form.solutionType"
                placeholder="请选择解决方式"
                clearable
                filterable
              >
                <el-option
                  v-for="item in solutionTypeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="细分问题">
              <el-select
                v-model="form.problemPatternCode"
                placeholder="请选择细分问题"
                clearable
                filterable
                @change="handleProblemPatternChange"
              >
                <el-option
                  v-for="item in problemPatternOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="细分确认">
              <el-switch
                v-model="form.problemPatternVerified"
                inline-prompt
                active-text="已确认"
                inactive-text="待确认"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="根因">
              <el-input
                v-model="form.rootCause"
                type="textarea"
                :rows="3"
                placeholder="最终根因，可后续RCA同步"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="解决方案">
              <el-input
                v-model="form.solution"
                type="textarea"
                :rows="3"
                placeholder="最终解决方案，可后续RCA同步"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-divider content-position="left">自动化</el-divider>
          </el-col>
          <el-col :span="12">
            <el-form-item label="创建后拉日志">
              <el-switch
                v-model="form.needLogPull"
                inline-prompt
                active-text="是"
                inactive-text="否"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手动自动翻译">
              <el-switch
                v-model="form.autoTranslate"
                inline-prompt
                active-text="是"
                inactive-text="否"
              />
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
          <el-button
            type="primary"
            :loading="formSubmitting"
            :disabled="formSubmitting"
            @click="submitForm"
            >确 定</el-button
          >
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
          <el-input
            v-model="assignForm.toUserName"
            placeholder="选择用户后自动填充，也可手动调整"
          />
        </el-form-item>
        <el-form-item label="指派原因">
          <el-input
            v-model="assignForm.reason"
            type="textarea"
            :rows="3"
            placeholder="请输入指派原因"
          />
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
          <el-select
            v-model="statusForm.rootCauseType"
            placeholder="请选择根因分类"
            clearable
            filterable
          >
            <el-option
              v-for="item in rootCauseTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="解决方式">
          <el-select
            v-model="statusForm.solutionType"
            placeholder="请选择解决方式"
            clearable
            filterable
          >
            <el-option
              v-for="item in solutionTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关闭结果">
          <el-select
            v-model="statusForm.resolutionCode"
            placeholder="关闭时请选择结果"
            clearable
            filterable
            @change="handleResolutionChange"
          >
            <el-option
              v-for="item in resolutionOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="细分问题">
          <el-select
            v-model="statusForm.problemPatternCode"
            placeholder="请选择细分问题"
            clearable
            filterable
            @change="handleStatusProblemPatternChange"
          >
            <el-option
              v-for="item in problemPatternOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="细分确认">
          <el-switch
            v-model="statusForm.problemPatternVerified"
            inline-prompt
            active-text="已确认"
            inactive-text="待确认"
          />
        </el-form-item>
        <el-form-item label="说明">
          <el-input
            v-model="statusForm.comment"
            type="textarea"
            :rows="3"
            placeholder="请输入状态流转说明"
          />
        </el-form-item>
        <el-form-item label="根因">
          <el-input
            v-model="statusForm.rootCause"
            type="textarea"
            :rows="2"
            placeholder="关闭/解决时建议填写"
          />
        </el-form-item>
        <el-form-item label="解决方案">
          <el-input
            v-model="statusForm.solution"
            type="textarea"
            :rows="2"
            placeholder="关闭/解决时建议填写"
          />
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
          <el-descriptions-item label="导入成功">{{
            importResult.importedCount
          }}</el-descriptions-item>
          <el-descriptions-item label="已向量化">{{
            importResult.embeddingCount
          }}</el-descriptions-item>
          <el-descriptions-item label="重复跳过">{{
            importResult.duplicateCount
          }}</el-descriptions-item>
          <el-descriptions-item label="失败行">{{ importResult.failedCount }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="importResult.duplicateTicketNos?.length" class="mt12">
          <div class="result-title">重复未导入工单号</div>
          <el-tag
            v-for="item in importResult.duplicateTicketNos"
            :key="item"
            class="mr8 mb8"
            type="warning"
          >
            {{ item }}
          </el-tag>
        </div>
        <el-table
          v-if="importResult.failedRows?.length"
          :data="importResult.failedRows"
          class="mt12"
        >
          <el-table-column label="行号" prop="row" width="90" />
          <el-table-column label="失败原因" prop="reason" />
        </el-table>
      </div>
      <template #footer>
        <el-button type="primary" :loading="importing" @click="submitImport">开始导入</el-button>
        <el-button @click="importOpen = false">关 闭</el-button>
      </template>
    </el-dialog>

    <TicketDetailWithList
      v-model:open="detailOpen"
      :ticket-id="currentTicketId"
      @changed="getList"
      @closed="handleDetailClosed"
    />
  </div>
</template>

<script setup name="TicketIndex">
  import { saveAs } from 'file-saver';
  import LogPullConfigFields from '@/components/ticket/LogPullConfigFields.vue';
  import LogPullNotifyConfigFields from '@/components/ticket/LogPullNotifyConfigFields.vue';
  import {
    addTicket,
    assignTicket,
    batchUpdateTicketRelease,
    changeTicketStatus,
    delTicket,
    downloadTicketImportTemplate,
    getTicket,
    getTicketVersionStatistics,
    importTicketExcel,
    updateTicket,
  } from '@/api/ticket/ticket';
  import {
    getLogPullStatusTagType,
    getOptionLabel,
    logPullDataTypeOptions,
    logPullStatusOptions,
    logPullStorageModeOptions,
    priorityOptions,
    ticketProcessStatusOptions,
    severityOptions,
    sourceOptions,
  } from './constants';
  import {
    buildCleanLogPullConfig,
    createDefaultLogPullForm,
    getOptionalLogPullTimeRangeError,
    hasLogPullTimeRange,
    normalizeLogPullNotifyConfig,
  } from './logPull.shared';
  import UserSelect from './components/UserSelect.vue';
  import TicketDetailWithList from './components/TicketDetailWithList.vue';
  import { useRoute, useRouter } from 'vue-router';
  import { useWorkflow } from './hooks/useWorkflow';
  import { useOptions } from './hooks/useOptions';
  import { useTicketList } from './hooks/useTicketList';

  const { proxy } = getCurrentInstance();
  const route = useRoute();
  const router = useRouter();

  // standaloneDetailMode 必须在 useTicketList 之前定义
  const standaloneDetailMode = computed(() => route.name === 'TicketDetail');

  // 列表查询 + 列配置 + 外部链接 已提取到 hooks/useTicketList.js
  const {
    loading,
    showSearch,
    ticketList,
    total,
    naturalKeyword,
    submitTimeRange,
    processedTimeRange,
    queryParams,
    queryCurrentAssigneeOption,
    queryFirstLineAssigneeOption,
    queryInternalOwnerOption,
    columnConfigOpen,
    ticketColumnOptions,
    visibleTicketColumnKeys,
    loadTicketColumnConfig,
    saveTicketColumnConfig,
    resetTicketColumnConfig,
    isTicketColumnVisible,
    getList,
    handleTicketSortChange,
    resolveTicketDetailUrl,
    openTicketLink,
    openSystemTicketDetail,
    handleQuery,
    handleSearch,
    resetQuery,
    handleNaturalSearch,
    buildTicketListQueryParams,
    handleQueryCurrentAssigneeChange,
    handleQueryFirstLineAssigneeChange,
    handleQueryInternalOwnerChange,
    toElementSortOrder,
  } = useTicketList(proxy, standaloneDetailMode, router);
  // 选项数据 + 格式化函数 已提取到 hooks/useOptions.js
  const {
    projectOptions,
    formModuleOptions,
    formVersionOptions,
    queryModuleOptions,
    queryModuleCodeOptions,
    issueTypeOptions,
    rootCauseTypeOptions,
    solutionTypeOptions,
    resolutionOptions,
    problemPatternOptions,
    agentOptions,
    providerOptions,
    vendorOptions,
    pushOptions,
    loadVendorOptions,
    loadProviderOptions,
    loadPushOptions,
    loadProjectOptions,
    loadAgentOptions,
    loadQueryModuleOptions,
    loadFormModuleOptions,
    loadFormVersionOptions,
    getStatOptionLabel,
    formatStatOption,
    formatProblemFlag,
    formatIssueType,
    formatResolution,
    formatProblemPattern,
    loadStatClassificationOptions,
  } = useOptions();
  // ticketColumnOptions / defaultTicketColumnKeys / requiredTicketColumnKeys 已通过 useTicketList() 提供
  // agentOptions / providerOptions / vendorOptions / pushOptions 已通过 useOptions() 提供
  // 已提取到 hooks/useWorkflow.js — workflowConfig / ticketStatusOptions / statusTransitionOptions / getStatusTagType / loadWorkflowConfig
  const currentTicketStatus = ref('');
  const { ticketStatusOptions, statusTransitionOptions, getStatusTagType, loadWorkflowConfig } =
    useWorkflow(currentTicketStatus);

  const open = ref(false);
  const formSubmitting = ref(false);
  const assignOpen = ref(false);
  const statusOpen = ref(false);
  const importOpen = ref(false);
  const importing = ref(false);
  const detailOpen = ref(false);
  const title = ref('');
  const currentTicketId = ref();
  const currentAssigneeOption = ref(null);
  const firstLineAssigneeOption = ref(null);
  const internalOwnerOption = ref(null);
  const formModuleValue = ref('');
  const selectedTicketRows = ref([]);
  const releaseBatchOpen = ref(false);
  const releaseBatchSubmitting = ref(false);
  const releaseBatchForm = ref(createDefaultReleaseBatchForm());
  const versionStatisticsOpen = ref(false);
  const versionStatisticsLoading = ref(false);
  const versionStatisticsTab = ref('affected');
  const versionStatistics = ref({
    total: 0,
    affectedVersionRows: [],
    fixVersionRows: [],
  });
  const versionStatisticsQuery = ref({
    versionKeyword: '',
    topLimit: 5,
    versionLimit: 50,
  });
  const importResult = ref(null);
  let suppressProjectWatcher = false;
  const standaloneRouteTicketId = computed(() => {
    const ticketId = Number(route.params.ticketId);
    return Number.isFinite(ticketId) && ticketId > 0 ? ticketId : undefined;
  });

  /**
   * 获取工单自动化日志拉取配置，兼容新旧 extraData 命名。
   * @param {object} ticketData 工单详情数据
   * @returns {object} 日志拉取配置对象
   */

  /**
   * 根据 Provider 编码获取 Provider 配置。
   * @param {string} providerCode Provider 编码
   * @returns {object | undefined} Provider 配置
   */

  /**
   * 按 Provider 绑定关系自动补齐 AI 分析表单 Agent。
   * @param {string} providerCode Provider 编码
   * @returns {void}
   */

  /**
   * 处理 AI 分析 Provider 变更，自动带入 Provider 绑定的 Agent。
   * @param {string} providerCode Provider 编码
   * @returns {void}
   */

  /**
   * 解析本次 AI 分析的默认追加提示词编码。
   * @returns {Array<string>} 追加提示词编码列表
   */

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
      affectedVersion: '',
      plannedFixVersion: '',
      fixedVersion: '',
      releasedVersion: '',
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
      problemPatternCode: '',
      problemPatternName: '',
      problemPatternVerified: false,
      rootCause: undefined,
      solution: undefined,
      needLogPull: false,
      autoTranslate: false,
      logPullConfig: createDefaultLogPullForm(),
    };
  }

  function createDefaultReleaseBatchForm() {
    return {
      plannedFixVersion: '',
      fixedVersion: '',
      releasedVersion: '',
      releasedAt: '',
      verifiedAt: '',
      markReleased: false,
      markVerified: false,
      comment: '',
    };
  }

  function handleTicketSelectionChange(rows) {
    selectedTicketRows.value = Array.isArray(rows) ? rows : [];
  }

  function openReleaseBatchDialog() {
    if (!selectedTicketRows.value.length) {
      proxy.$modal.msgWarning('请先选择需要维护的工单');
      return;
    }
    releaseBatchForm.value = createDefaultReleaseBatchForm();
    releaseBatchOpen.value = true;
  }

  function resetReleaseBatchForm() {
    releaseBatchForm.value = createDefaultReleaseBatchForm();
    releaseBatchSubmitting.value = false;
  }

  function buildReleaseBatchPayload() {
    const formData = releaseBatchForm.value || {};
    const ticketIds = selectedTicketRows.value
      .map((item) => Number(item.ticketId || item.ticket_id))
      .filter((item) => Number.isFinite(item) && item > 0);
    const payload = {
      ticketIds,
      plannedFixVersion: String(formData.plannedFixVersion || '').trim() || undefined,
      fixedVersion: String(formData.fixedVersion || '').trim() || undefined,
      releasedVersion: String(formData.releasedVersion || '').trim() || undefined,
      releasedAt: formData.releasedAt || undefined,
      verifiedAt: formData.verifiedAt || undefined,
      markReleased: Boolean(formData.markReleased),
      markVerified: Boolean(formData.markVerified),
      comment: String(formData.comment || '').trim() || undefined,
    };
    return Object.fromEntries(
      Object.entries(payload).filter(
        ([, value]) => value !== undefined && value !== null && value !== ''
      )
    );
  }

  function submitReleaseBatch() {
    const payload = buildReleaseBatchPayload();
    if (!payload.ticketIds?.length) {
      proxy.$modal.msgWarning('请先选择需要维护的工单');
      return;
    }
    const hasUpdate = [
      payload.plannedFixVersion,
      payload.fixedVersion,
      payload.releasedVersion,
      payload.releasedAt,
      payload.verifiedAt,
      payload.markReleased,
      payload.markVerified,
    ].some(Boolean);
    if (!hasUpdate) {
      proxy.$modal.msgWarning('请至少填写一个版本治理字段');
      return;
    }
    releaseBatchSubmitting.value = true;
    batchUpdateTicketRelease(payload)
      .then((response) => {
        const updatedCount = response.data?.updatedCount ?? payload.ticketIds.length;
        proxy.$modal.msgSuccess(`已维护 ${updatedCount} 张工单`);
        releaseBatchOpen.value = false;
        getList();
      })
      .finally(() => {
        releaseBatchSubmitting.value = false;
      });
  }

  function openVersionStatisticsDialog() {
    versionStatisticsOpen.value = true;
    loadVersionStatistics();
  }

  function buildVersionStatisticsQuery() {
    const params = buildTicketListQueryParams();
    return {
      beginTime: params.beginTime,
      endTime: params.endTime,
      submitBeginTime: params.submitBeginTime,
      submitEndTime: params.submitEndTime,
      processedBeginTime: params.processedBeginTime,
      processedEndTime: params.processedEndTime,
      projectIds: params.projectIds,
      moduleIds: params.moduleIds,
      issueTypeIds: params.issueTypeIds,
      rootCauseTypes: params.rootCauseTypes,
      solutionTypes: params.solutionTypes,
      resolutionCodes: params.resolutionCodes,
      problemPatternCodes: params.problemPatternCodes,
      versionKeyword: String(versionStatisticsQuery.value.versionKeyword || '').trim() || undefined,
      topLimit: versionStatisticsQuery.value.topLimit,
      versionLimit: versionStatisticsQuery.value.versionLimit,
    };
  }

  function loadVersionStatistics() {
    versionStatisticsLoading.value = true;
    getTicketVersionStatistics(buildVersionStatisticsQuery())
      .then((response) => {
        versionStatistics.value = response.data || {
          total: 0,
          affectedVersionRows: [],
          fixVersionRows: [],
        };
      })
      .finally(() => {
        versionStatisticsLoading.value = false;
      });
  }

  function formatTopRows(rows) {
    if (!Array.isArray(rows) || !rows.length) {
      return '-';
    }
    return rows.map((item) => `${item.name || '未填写'}(${item.count || 0})`).join('、');
  }

  const data = reactive({
    // queryParams 已通过 useTicketList() 提供
    form: createDefaultTicketForm(),
    assignForm: {},
    statusForm: {},
    rules: {
      title: [{ required: true, message: '工单标题不能为空', trigger: 'blur' }],
      ticketNo: [{ required: true, message: '工单号不能为空', trigger: 'blur' }],
      projectId: [{ required: true, message: '所属项目不能为空', trigger: 'change' }],
      customerPriority: [{ required: true, message: '对方优先级不能为空', trigger: 'change' }],
      internalPriority: [{ required: true, message: '内部优先级不能为空', trigger: 'change' }],
    },
    assignRules: {
      toUserId: [{ required: true, message: '请选择处理人', trigger: 'change' }],
      toUserName: [{ required: true, message: '处理人名称不能为空', trigger: 'blur' }],
    },
    statusRules: {
      toStatus: [{ required: true, message: '目标状态不能为空', trigger: 'change' }],
    },
  });

  const {
    // queryParams 已通过 useTicketList() 提供
    form,
    assignForm,
    statusForm,
    rules,
    assignRules,
    statusRules,
  } = toRefs(data);

  /**
   * 解析列表中的日志/AI处理状态，用于展示当前处理进度。
   * @param {object} row 工单列表行数据
   * @returns {{label: string, type: string}} 状态标签信息
   */
  function resolveTicketProcessStatus(row) {
    const latestLog = row?.latestLogPull || row?.latest_log_pull || null;
    const latestAi = row?.latestAiAnalysis || row?.latest_ai_analysis || null;
    const logStatus = String(latestLog?.status || '').toLowerCase();
    const aiStatus = String(latestAi?.status || '').toLowerCase();
    if (aiStatus) {
      if (aiStatus === 'running' || aiStatus === 'created') {
        return { label: getOptionLabel(ticketProcessStatusOptions, 'ai_running'), type: 'warning' };
      }
      if (aiStatus === 'success') {
        return { label: getOptionLabel(ticketProcessStatusOptions, 'ai_success'), type: 'success' };
      }
      if (aiStatus === 'failed' || aiStatus === 'canceled') {
        return { label: getOptionLabel(ticketProcessStatusOptions, 'ai_failed'), type: 'danger' };
      }
    }
    if (!latestLog) {
      return { label: getOptionLabel(ticketProcessStatusOptions, 'no_log_pull'), type: 'info' };
    }
    if (logStatus === 'success' && !latestAi) {
      return {
        label: getOptionLabel(ticketProcessStatusOptions, 'ai_not_analyzed'),
        type: 'warning',
      };
    }
    if (logStatus === 'failed') {
      return {
        label: getOptionLabel(ticketProcessStatusOptions, 'log_pull_failed'),
        type: 'danger',
      };
    }
    return {
      label: latestLog?.statusDesc || getOptionLabel(logPullStatusOptions, logStatus),
      type: getLogPullStatusTagType(logStatus),
    };
  }

  /**
   * 格式化工单归因关系类型。
   * @param {string} value 归因关系类型
   * @returns {string} 中文展示文本
   */
  function formatIssueRelationType(value) {
    if (value === 'manual') return '人工确认';
    if (value === 'similar') return '相似归因';
    if (value === 'external') return '外部关联';
    return value || '-';
  }

  function reset() {
    formSubmitting.value = false;
    form.value = createDefaultTicketForm();
    formModuleValue.value = '';
    tagText.value = '';
    firstLineAssigneeOption.value = null;
    internalOwnerOption.value = null;
    proxy.resetForm('ticketRef');
  }

  function handleIssueTypeChange(value) {
    const option = issueTypeOptions.value.find((item) => item.value === value);
    form.value.issueTypeName = option?.label || '';
    if (typeof option?.isProblem === 'boolean') {
      form.value.isProblem = option.isProblem;
    }
  }

  function handleProblemPatternChange(value) {
    const option = problemPatternOptions.value.find((item) => item.value === value);
    form.value.problemPatternName = option?.label || '';
  }

  function handleStatusProblemPatternChange(value) {
    const option = problemPatternOptions.value.find((item) => item.value === value);
    statusForm.value.problemPatternName = option?.label || '';
  }

  function syncFormModuleValueFromForm() {
    if (form.value.moduleId) {
      formModuleValue.value = String(form.value.moduleId);
      return;
    }
    formModuleValue.value = form.value.moduleName || '';
  }

  function resolveFormModuleOption(value = formModuleValue.value) {
    const text = String(value || '').trim();
    if (!text) {
      return null;
    }
    return (
      formModuleOptions.value.find(
        (item) => String(item.moduleId) === text || item.moduleName === text
      ) || null
    );
  }

  function buildModuleCodeOptions(moduleOptions = []) {
    const codeMap = new Map();
    (Array.isArray(moduleOptions) ? moduleOptions : []).forEach((item) => {
      const code = String(item?.moduleCode || '').trim();
      if (!code || codeMap.has(code)) {
        return;
      }
      codeMap.set(code, {
        value: code,
        label: code,
      });
    });
    return Array.from(codeMap.values());
  }

  function handleModuleChange(value) {
    const option = resolveFormModuleOption(value);
    if (option) {
      form.value.moduleId = option.moduleId;
      form.value.moduleName = option.moduleName || '';
      formModuleValue.value = String(option.moduleId);
      return;
    }
    form.value.moduleId = undefined;
    form.value.moduleName = String(value || '').trim();
    formModuleValue.value = form.value.moduleName;
  }

  function handleResolutionChange(value) {
    const option = resolutionOptions.value.find((item) => item.value === value);
    statusForm.value.resolutionName = option?.label || '';
    if (typeof option?.isProblem === 'boolean') {
      statusForm.value.isProblem = option.isProblem;
    }
  }

  function applyTicketAutomationConfig(ticketData) {
    const automation =
      ticketData?.extraData?.ticketAutomation || ticketData?.extraData?.ticket_automation || {};
    const logPullConfig = automation?.logPullConfig || automation?.log_pull_config || null;
    if (!logPullConfig) {
      return;
    }
    form.value.needLogPull = Boolean(automation.needLogPull ?? automation.need_log_pull ?? true);
    form.value.logPullConfig = {
      ...createDefaultLogPullForm(),
      ...logPullConfig,
      cutLogEnabled: Boolean(
        logPullConfig.cutLogEnabled ??
        logPullConfig.cut_log_enabled ??
        hasLogPullTimeRange(logPullConfig)
      ),
      autoAiEnabled: Boolean(logPullConfig.autoAiEnabled ?? logPullConfig.auto_ai_enabled ?? false),
      aiAgentCode: logPullConfig.aiAgentCode || logPullConfig.ai_agent_code || '',
      aiProviderCode: logPullConfig.aiProviderCode || logPullConfig.ai_provider_code || '',
      notifyConfig: normalizeLogPullNotifyConfig(
        logPullConfig.notifyConfig || logPullConfig.notify_config
      ),
    };
  }

  function syncDetailBundle(payload) {
    detail.value = payload || {};
    ticketMessages.value = detail.value.messages || [];
    ticketSnapshots.value = detail.value.snapshots || [];
    similarTickets.value = detail.value.similarTickets || [];
  }

  function downloadTemplate() {
    downloadTicketImportTemplate().then((data) => {
      saveAs(new Blob([data]), '工单导入模板.xlsx');
    });
  }

  function submitImport() {
    importResult.value = null;
    proxy.$refs.uploadRef.submit();
  }

  function handleImportRequest(option) {
    const formData = new FormData();
    formData.append('file', option.file);
    importing.value = true;
    importTicketExcel(formData)
      .then((response) => {
        importResult.value = response.data;
        proxy.$modal.msgSuccess('导入完成');
        proxy.$refs.uploadRef.clearFiles();
        getList();
      })
      .finally(() => {
        importing.value = false;
      });
  }

  function handleAdd() {
    reset();
    formModuleOptions.value = [];
    formVersionOptions.value = [];
    open.value = true;
    title.value = '新增工单';
  }

  function openIssueManagement() {
    const resolved = router.resolve({
      name: 'TicketIssue',
    });
    window.open(resolved.href, '_blank', 'noopener');
  }

  function handleUpdate(row) {
    reset();
    getTicket(row.ticketId)
      .then((response) => {
        const ticketData = response.data || {};
        suppressProjectWatcher = true;
        form.value = {
          ...createDefaultTicketForm(),
          ...ticketData,
          logPullConfig: {
            ...createDefaultLogPullForm(),
            ...(ticketData.logPullConfig ||
              ticketData.log_pull_config ||
              ticketData.extraData?.ticketAutomation?.logPullConfig ||
              ticketData.extraData?.ticket_automation?.log_pull_config ||
              {}),
          },
        };
        form.value.logPullConfig.cutLogEnabled = Boolean(
          form.value.logPullConfig.cutLogEnabled ??
          form.value.logPullConfig.cut_log_enabled ??
          hasLogPullTimeRange(form.value.logPullConfig)
        );
        form.value.logPullConfig.notifyConfig = normalizeLogPullNotifyConfig(
          form.value.logPullConfig.notifyConfig || form.value.logPullConfig.notify_config
        );
        form.value.description =
          ticketData.originalDescription ||
          ticketData.extraData?.originDescription ||
          ticketData.description ||
          '';
        form.value.autoTranslate =
          ticketData.extraData?.manualAutomation?.autoTranslate ??
          ticketData.extraData?.manual_automation?.auto_translate ??
          ticketData.autoTranslate ??
          ticketData.auto_translate ??
          false;
        form.value.issueTypeId = ticketData.issueTypeId || ticketData.issue_type_id || '';
        form.value.issueTypeName = ticketData.issueTypeName || ticketData.issue_type_name || '';
        form.value.versionKey =
          ticketData.versionKey ||
          ticketData.affectedVersion ||
          ticketData.extraData?.versionKey ||
          ticketData.extraData?.version_key ||
          '';
        form.value.affectedVersion = ticketData.affectedVersion || form.value.versionKey || '';
        form.value.plannedFixVersion =
          ticketData.plannedFixVersion || ticketData.planned_fix_version || '';
        form.value.fixedVersion = ticketData.fixedVersion || ticketData.fixed_version || '';
        form.value.releasedVersion =
          ticketData.releasedVersion || ticketData.released_version || '';
        form.value.isProblem = ticketData.isProblem ?? ticketData.is_problem ?? undefined;
        form.value.rootCauseType = ticketData.rootCauseType || ticketData.root_cause_type || '';
        form.value.solutionType = ticketData.solutionType || ticketData.solution_type || '';
        form.value.resolutionCode = ticketData.resolutionCode || ticketData.resolution_code || '';
        form.value.resolutionName = ticketData.resolutionName || ticketData.resolution_name || '';
        form.value.problemPatternCode =
          ticketData.problemPatternCode || ticketData.problem_pattern_code || '';
        form.value.problemPatternName =
          ticketData.problemPatternName || ticketData.problem_pattern_name || '';
        form.value.problemPatternVerified = Boolean(
          ticketData.problemPatternVerified ?? ticketData.problem_pattern_verified ?? false
        );
        syncFormModuleValueFromForm();
        tagText.value = Array.isArray(form.value.tags) ? form.value.tags.join(',') : '';
        applyTicketAutomationConfig(form.value);
        firstLineAssigneeOption.value = buildTicketUserOption(
          form.value.firstLineAssigneeId,
          form.value.firstLineAssigneeName
        );
        internalOwnerOption.value = buildTicketUserOption(
          form.value.internalOwnerId,
          form.value.internalOwnerName
        );
        loadFormModuleOptions(form.value.projectId).finally(() => {
          suppressProjectWatcher = false;
        });
        loadFormVersionOptions(form.value.projectId);
        open.value = true;
        title.value = '编辑工单';
      })
      .catch(() => {
        suppressProjectWatcher = false;
      });
  }

  function cancel() {
    open.value = false;
  }

  function validateTicketAutomationConfig() {
    if (!form.value.needLogPull) {
      return true;
    }
    const config = form.value.logPullConfig || {};
    if (!config.vendorId || !config.storeId || !config.posNo) {
      proxy.$modal.msgWarning('启用日志拉取时，vendorId、storeId、posNo 不能为空');
      return false;
    }
    if (Number(config.commandDataType) === 2 && !String(config.path || '').trim()) {
      proxy.$modal.msgWarning('启用日志拉取且数据类型为数据库时，path 不能为空');
      return false;
    }
    if (Number(config.commandDataType) !== 2 && !config.modifyTime) {
      proxy.$modal.msgWarning('启用日志拉取且数据类型为日志时，modifyTime 不能为空');
      return false;
    }
    const timeRangeError = getOptionalLogPullTimeRangeError(config);
    if (timeRangeError) {
      proxy.$modal.msgWarning(`启用日志拉取时，${timeRangeError}`);
      return false;
    }
    if (
      config.autoAiEnabled &&
      !String(config.aiAgentCode || '').trim() &&
      !String(config.aiProviderCode || '').trim()
    ) {
      proxy.$modal.msgWarning('启用自动AI分析时，请先选择Provider或Agent');
      return false;
    }
    return true;
  }

  function submitForm() {
    if (formSubmitting.value) {
      return;
    }
    proxy.$refs.ticketRef.validate((valid) => {
      if (!valid) return;
      if (!validateTicketAutomationConfig()) {
        return;
      }
      formSubmitting.value = true;
      const logPullConfig = form.value.needLogPull
        ? buildCleanLogPullConfig(form.value.logPullConfig)
        : undefined;
      const payload = {
        ...form.value,
        tags: tagText.value
          ? tagText.value
              .split(',')
              .map((item) => item.trim())
              .filter(Boolean)
          : undefined,
        needLogPull: Boolean(form.value.needLogPull),
        autoTranslate: Boolean(form.value.autoTranslate),
        logPullConfig,
      };
      handleModuleChange(formModuleValue.value);
      payload.moduleId = form.value.moduleId;
      payload.moduleName = form.value.moduleName || '';
      payload.affectedVersion = payload.versionKey || payload.affectedVersion || '';
      if (payload.issueTypeId) {
        payload.issueTypeName =
          payload.issueTypeName || getStatOptionLabel(issueTypeOptions.value, payload.issueTypeId);
      }
      if (payload.resolutionCode) {
        payload.resolutionName =
          payload.resolutionName ||
          getStatOptionLabel(resolutionOptions.value, payload.resolutionCode);
      }
      if (payload.problemPatternCode) {
        payload.problemPatternName =
          payload.problemPatternName ||
          getStatOptionLabel(problemPatternOptions.value, payload.problemPatternCode);
        payload.problemPatternSource = payload.problemPatternVerified
          ? 'manual'
          : payload.problemPatternSource;
      }
      const request = payload.ticketId ? updateTicket(payload) : addTicket(payload);
      request
        .then(() => {
          proxy.$modal.msgSuccess(payload.ticketId ? '修改成功' : '新增成功');
          open.value = false;
          getList();
        })
        .finally(() => {
          formSubmitting.value = false;
        });
    });
  }

  function handleDelete(row) {
    proxy.$modal
      .confirm(`是否确认删除工单 "${row.title}"？`)
      .then(() => delTicket(row.ticketId))
      .then(() => {
        proxy.$modal.msgSuccess('删除成功');
        getList();
      })
      .catch(() => {});
  }

  function openAssign(row) {
    currentTicketId.value = row.ticketId;
    currentAssigneeOption.value = row.currentAssigneeId
      ? {
          userId: row.currentAssigneeId,
          userName: row.currentAssigneeName,
          nickName: row.currentAssigneeName,
          label: row.currentAssigneeName,
        }
      : null;
    assignForm.value = {
      toUserId: row.currentAssigneeId,
      toUserName: row.currentAssigneeName,
      reason: '',
    };
    assignOpen.value = true;
  }

  function submitAssign() {
    proxy.$refs.assignRef.validate((valid) => {
      if (!valid) return;
      assignTicket(currentTicketId.value, assignForm.value).then(() => {
        proxy.$modal.msgSuccess('指派成功');
        assignOpen.value = false;
        getList();
      });
    });
  }

  function handleAssigneeChange(user) {
    assignForm.value.toUserName = user?.nickName || user?.userName || '';
    currentAssigneeOption.value = user;
  }

  function buildTicketUserOption(userId, userName) {
    if (!userId) {
      return null;
    }
    const resolvedName = String(userName || '').trim();
    return {
      userId,
      userName: resolvedName,
      nickName: resolvedName,
      label: resolvedName,
    };
  }

  function handleFirstLineAssigneeChange(user) {
    if (user?.isRawLabel) {
      form.value.firstLineAssigneeId = undefined;
      firstLineAssigneeOption.value = null;
      return;
    }
    form.value.firstLineAssigneeName = user?.nickName || user?.userName || '';
    firstLineAssigneeOption.value = user;
  }

  function handleInternalOwnerChange(user) {
    if (user?.isRawLabel) {
      form.value.internalOwnerId = undefined;
      internalOwnerOption.value = null;
      return;
    }
    form.value.internalOwnerName = user?.nickName || user?.userName || '';
    internalOwnerOption.value = user;
  }

  function openStatus(row) {
    currentTicketId.value = row.ticketId;
    currentTicketStatus.value = row.status || '';
    statusForm.value = {
      toStatus: undefined,
      comment: '',
      rootCause: row.rootCause,
      solution: row.solution,
      isProblem: row.isProblem,
      rootCauseType: row.rootCauseType || row.root_cause_type || '',
      solutionType: row.solutionType || row.solution_type || '',
      resolutionCode: row.resolutionCode || row.resolution_code || '',
      resolutionName: row.resolutionName || row.resolution_name || '',
      problemPatternCode: row.problemPatternCode || row.problem_pattern_code || '',
      problemPatternName: row.problemPatternName || row.problem_pattern_name || '',
      problemPatternVerified: Boolean(
        row.problemPatternVerified ?? row.problem_pattern_verified ?? false
      ),
    };
    if (!statusTransitionOptions.value.length) {
      proxy.$modal.msgWarning('当前状态未配置可用流转规则，请先在工单工作流中配置流转规则');
    }
    statusOpen.value = true;
  }

  function submitStatus() {
    proxy.$refs.statusRef.validate((valid) => {
      if (!valid) return;
      changeTicketStatus(currentTicketId.value, statusForm.value).then(() => {
        proxy.$modal.msgSuccess('状态流转成功');
        statusOpen.value = false;
        getList();
      });
    });
  }

  /**
   * 打开工单详情组件，父页只传递工单 ID，不再参与详情数据加载。
   * @param {object} row 工单列表行或包含 ticketId 的对象
   * @returns {void}
   */
  function openDetail(row) {
    const ticketId = Number(row?.ticketId || row?.ticket_id || row);
    if (!Number.isFinite(ticketId) || ticketId <= 0) {
      proxy.$modal.msgWarning('工单ID无效，无法打开详情');
      return;
    }
    currentTicketId.value = ticketId;
    detailOpen.value = true;
  }

  /**
   * 详情弹窗关闭后的父页收尾；独立详情路由关闭时回到列表路由。
   * @returns {void}
   */
  function handleDetailClosed() {
    if (standaloneDetailMode.value) {
      router.replace('/ticket/ticket');
    }
  }

  // 过滤掉项目变更后已经不在模块候选范围内的模块和模块 Code。
  function filterInvalidQueryValues(values, validValues) {
    const validSet = new Set((validValues || []).map((item) => String(item)));
    return normalizeQueryList(values).filter((item) => validSet.has(String(item)));
  }

  // 加载列表筛选用模块选项，多项目筛选时在前端按项目 ID 收敛候选。

  watch(standaloneRouteTicketId, (ticketId) => {
    if (!standaloneDetailMode.value || !ticketId || ticketId === currentTicketId.value) {
      return;
    }
    currentTicketId.value = ticketId;
    detailOpen.value = true;
  });

  watch(
    () => queryParams.value.projectIds,
    (value) => {
      queryParams.value.moduleIds = [];
      queryParams.value.moduleCodes = [];
      loadQueryModuleOptions(value);
    },
    { deep: true }
  );

  watch(
    () => form.value.projectId,
    (value) => {
      if (suppressProjectWatcher) {
        return;
      }
      form.value.moduleId = undefined;
      form.value.moduleName = '';
      formModuleValue.value = '';
      if (!open.value) {
        return;
      }
      loadFormModuleOptions(value);
      loadFormVersionOptions(value);
    }
  );

  loadProjectOptions();
  loadStatClassificationOptions();
  loadAgentOptions();
  loadProviderOptions();
  loadVendorOptions();
  loadPushOptions();
  loadTicketColumnConfig();
  loadQueryModuleOptions();
  loadWorkflowConfig().finally(() => {
    if (standaloneDetailMode.value && standaloneRouteTicketId.value) {
      currentTicketId.value = standaloneRouteTicketId.value;
      detailOpen.value = true;
      return;
    }
    getList();
  });
</script>

<style scoped>
  .ticket-column-config {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px 16px;
  }

  .ticket-summary-descriptions :deep(.el-descriptions__label) {
    white-space: nowrap;
  }

  .collab-toolbar {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  .mt16 {
    margin-top: 16px;
  }

  .mb16 {
    margin-bottom: 16px;
  }

  .mb12 {
    margin-bottom: 12px;
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

  .version-statistics-toolbar {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 12px;
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

  .similar-actions {
    display: flex;
    gap: 12px;
    margin-top: 6px;
    font-size: 12px;
    align-items: center;
    flex-wrap: wrap;
  }

  .issue-summary-inline {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .issue-summary-inline span:last-child {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .panel-header {
    display: flex;
    justify-content: start;
    gap: 12px;
  }

  .log-view-controls {
    flex-wrap: wrap;
    align-items: center;
  }

  .ticket-page :deep(.ticket-log-viewer-dialog .el-dialog__body) {
    height: calc(100vh - 56px);
    overflow: hidden;
  }

  .log-viewer-content {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }

  .log-keyword-input {
    width: min(460px, 100%);
  }

  .log-highlight-input {
    width: min(360px, 100%);
  }

  .log-context-lines-input {
    width: 120px;
  }

  .log-highlight-summary-tag {
    max-width: min(280px, 32vw);
    min-width: 0;
  }

  .log-highlight-summary {
    display: inline-block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    vertical-align: bottom;
    white-space: nowrap;
  }

  .log-view-time-picker {
    width: 220px;
  }

  .log-file-scope-select {
    width: min(360px, 100%);
  }

  .panel-inline {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: nowrap;
  }

  .inline-inputs {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
  }

  .inline-inputs :deep(.el-input-number) {
    flex: 1;
    min-width: 0;
  }

  .inline-separator {
    color: #606266;
    white-space: nowrap;
  }

  .log-view-panel {
    display: flex;
    flex: 0 0 auto;
    flex-direction: column;
    min-height: 0;
    padding: 10px;
    border: 1px solid #dcdfe6;
    border-radius: 6px;
    background: #ffffff;
  }

  .log-view-panel-header {
    align-items: center;
    flex-wrap: wrap;
    justify-content: space-between;
  }

  .log-view-panel-header > span {
    min-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .log-view-panel-fullscreen {
    position: fixed;
    inset: 16px;
    z-index: 3000;
    display: flex;
    flex-direction: column;
    padding: 14px;
    overflow: hidden;
    box-shadow: 0 8px 24px rgb(0 0 0 / 18%);
  }

  .log-view-panel-fullscreen :deep(.el-table) {
    flex: 1;
  }

  .log-view-panel-fullscreen .log-content-block {
    flex: 1;
    max-height: none;
  }

  .log-view-panel-minimized {
    flex: 0 0 auto;
    padding-bottom: 6px;
  }

  .log-view-panel-fill {
    flex: 1 1 auto;
    min-height: 0;
  }

  .log-view-panel-fill :deep(.el-table) {
    flex: 1 1 auto;
    min-height: 0;
  }

  .log-view-panel-fill .log-content-block {
    flex: 1 1 auto;
    max-height: none;
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
    max-height: 52vh;
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

  .log-context-line {
    display: block;
  }

  .log-context-line-no {
    color: #94a3b8;
    user-select: none;
  }

  .log-context-line-content {
    white-space: inherit;
  }

  :global(::highlight(ticket-log-context-highlight)) {
    color: #111827;
    background: #fde047;
  }

  .log-context-highlight {
    padding: 0 1px;
    color: #111827;
    background: #fde047;
    border-radius: 2px;
  }

  .log-context-highlight-1 {
    background: #bfdbfe;
  }

  .log-context-highlight-2 {
    background: #bbf7d0;
  }

  .log-context-highlight-3 {
    background: #fecaca;
  }

  .log-context-highlight-4 {
    background: #ddd6fe;
  }

  .log-context-highlight-5 {
    background: #fed7aa;
  }

  .log-content-dialog {
    max-height: 60vh;
  }

  .log-pull-record-table :deep(.el-scrollbar__bar.is-horizontal) {
    height: 12px;
  }

  .log-pull-record-table :deep(.el-scrollbar__bar.is-horizontal .el-scrollbar__thumb) {
    min-width: 48px;
  }
</style>
