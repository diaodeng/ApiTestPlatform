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
        <el-form-item label="处理状态" prop="processStatuses">
          <el-select
            v-model="queryParams.processStatuses"
            placeholder="处理状态"
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
        <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
      </el-row>

      <el-table
        v-loading="loading"
        :data="ticketList"
        row-key="ticketId"
        :default-sort="{
          prop: queryParams.sortField,
          order: toElementSortOrder(queryParams.sortOrder),
        }"
        @sort-change="handleTicketSortChange"
      >
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
          label="处理状态"
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
            <el-descriptions-item label="当前处理人">{{
              detail.currentAssigneeName || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="1线人员">{{
              detail.firstLineAssigneeName || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="内部负责人">{{
              detail.internalOwnerName || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="所属项目">{{
              detail.projectName || detail.merchantName || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="所属模块">{{
              detail.moduleName || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="工单类型">{{
              formatIssueType(detail)
            }}</el-descriptions-item>
            <el-descriptions-item label="问题性质">{{
              formatProblemFlag(detail.isProblem)
            }}</el-descriptions-item>
            <el-descriptions-item label="根因分类">{{
              formatStatOption(rootCauseTypeOptions, detail.rootCauseType)
            }}</el-descriptions-item>
            <el-descriptions-item label="解决方式">{{
              formatStatOption(solutionTypeOptions, detail.solutionType)
            }}</el-descriptions-item>
            <el-descriptions-item label="关闭结果">{{
              formatResolution(detail)
            }}</el-descriptions-item>
            <el-descriptions-item label="细分问题">{{
              formatProblemPattern(detail)
            }}</el-descriptions-item>
            <el-descriptions-item label="细分确认">
              <el-tag v-if="detail.problemPatternVerified === true" type="success">已确认</el-tag>
              <el-tag v-else-if="detail.problemPatternVerified === false" type="warning"
                >待确认</el-tag
              >
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="版本号">{{
              detail.versionKey || detail.extraData?.versionKey || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="日志拉取状态">
              <el-tag
                v-if="detail.latestLogPull?.status"
                :type="getLogPullStatusTagType(detail.latestLogPull.status)"
              >
                {{
                  detail.latestLogPull.statusDesc ||
                  getOptionLabel(logPullStatusOptions, detail.latestLogPull.status)
                }}
              </el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="来源">{{
              getOptionLabel(sourceOptions, detail.source)
            }}</el-descriptions-item>
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
            <el-descriptions-item label="对方优先级">{{
              detail.customerPriority || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="内部优先级">{{
              detail.internalPriority || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="总耗时">{{
              formatSeconds(detail.totalProcessSeconds)
            }}</el-descriptions-item>
            <el-descriptions-item label="根因" :span="3">{{
              detail.rootCause || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="解决方案" :span="3">{{
              detail.solution || '-'
            }}</el-descriptions-item>
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
              :class="[
                'ticket-detail-description__content',
                { 'ticket-detail-description__content--collapsed': !descriptionExpanded },
              ]"
            >
              {{ detailOriginalDescription || '-' }}
            </div>
          </div>
          <div
            v-if="detailAiTranslation"
            class="ticket-detail-description ticket-detail-translation"
          >
            <div class="ticket-detail-description__label">
              <span>翻译</span>
              <el-button link type="primary" @click="translationExpanded = !translationExpanded">
                {{ translationExpanded ? '收起' : '展开' }}
              </el-button>
            </div>
            <div
              :class="[
                'ticket-detail-description__content',
                { 'ticket-detail-description__content--collapsed': !translationExpanded },
              ]"
            >
              {{ detailAiTranslation }}
            </div>
          </div>

          <el-tabs
            v-model="detailMainTab"
            class="detail-main-tabs"
            @tab-click="handleDetailTabClick"
          >
            <el-tab-pane label="概览" name="overview" lazy>
              <el-row :gutter="16">
                <el-col :span="16">
                  <el-card shadow="never" class="mb16">
                    <template #header>
                      <div class="panel-header">
                        <span>最新AI结论</span>
                        <el-button-group>
                          <el-button
                            type="primary"
                            @click="openAiAnalysisDialog"
                            v-hasPermi="['ticket:ai:analysis:run']"
                          >
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
                          <el-button
                            @click="openAiTaskHistory"
                            v-hasPermi="['ticket:ai:analysis:list']"
                          >
                            查看任务历史
                          </el-button>
                          <el-button
                            type="warning"
                            plain
                            @click="openAiRepoMappingDialog()"
                            v-hasPermi="['ticket:ai:mapping:add']"
                          >
                            管理映射
                          </el-button>
                          <el-button
                            type="success"
                            plain
                            @click="openProjectVendorMapDialog()"
                            v-hasPermi="['ticket:logpull:config']"
                          >
                            商家映射
                          </el-button>
                        </el-button-group>
                      </div>
                    </template>
                    <el-descriptions :column="2" border>
                      <el-descriptions-item label="最新执行状态">
                        <el-tag
                          v-if="latestAiAnalysisTask?.status"
                          :type="getAiStatusTagType(latestAiAnalysisTask.status)"
                        >
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
                      <el-descriptions-item label="摘要" :span="2">{{
                        latestSnapshot?.summary || '-'
                      }}</el-descriptions-item>
                      <el-descriptions-item label="根因" :span="2">{{
                        latestSnapshot?.rootCause || '-'
                      }}</el-descriptions-item>
                      <el-descriptions-item label="解决方案" :span="2">{{
                        latestSnapshot?.solution || '-'
                      }}</el-descriptions-item>
                      <el-descriptions-item label="预防建议" :span="2">{{
                        latestSnapshot?.prevention || '-'
                      }}</el-descriptions-item>
                      <el-descriptions-item label="风险说明" :span="2">{{
                        latestSnapshot?.risk || '-'
                      }}</el-descriptions-item>
                      <el-descriptions-item label="负责人" :span="2">{{
                        latestSnapshot?.owner || '-'
                      }}</el-descriptions-item>
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
                    <div
                      v-for="item in latestSimilarTickets"
                      :key="item.ticketId"
                      class="similar-item"
                    >
                      <div class="similar-title">{{ item.ticketNo }} {{ item.title }}</div>
                      <div class="similar-meta">
                        <span>相似度 {{ Math.round((item.score || 0) * 100) }}%</span>
                        <span>{{ item.rootCause || '-' }}</span>
                      </div>
                      <div class="similar-actions">
                        <el-link
                          type="primary"
                          :underline="false"
                          @click="openSystemTicketDetail(item)"
                          >系统详情</el-link
                        >
                        <el-link
                          v-if="resolveTicketDetailUrl(item)"
                          type="info"
                          :underline="false"
                          @click="openTicketLink(item)"
                        >
                          飞书详情
                        </el-link>
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
                  <el-tag v-if="logPullAutoRefreshing" size="small" type="warning"
                    >自动刷新中</el-tag
                  >
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
                  <el-button
                    type="primary"
                    @click="openLogPullSubmitDialog"
                    v-hasPermi="['ticket:logpull:add']"
                    >拉取日志</el-button
                  >
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
                <el-table-column label="拉取参数" min-width="180" show-overflow-tooltip>
                  <template #default="scope">{{ formatLogPullParameter(scope.row) }}</template>
                </el-table-column>
                <el-table-column label="商家" prop="vendorId" width="110" show-overflow-tooltip />
                <el-table-column
                  label="门店"
                  prop="storeId"
                  min-width="150"
                  show-overflow-tooltip
                />
                <el-table-column label="POSID" prop="posNo" width="110" show-overflow-tooltip />
                <el-table-column label="状态" min-width="170">
                  <template #default="scope">
                    <el-tag :type="getLogPullStatusTagType(scope.row.status)">
                      {{
                        scope.row.statusDesc ||
                        getOptionLabel(logPullStatusOptions, scope.row.status)
                      }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="保存方式" width="90" align="center">
                  <template #default="scope">{{
                    getOptionLabel(logPullStorageModeOptions, scope.row.storageMode)
                  }}</template>
                </el-table-column>
                <el-table-column label="归档地址" min-width="220" show-overflow-tooltip>
                  <template #default="scope">
                    <el-link
                      v-if="getLogPullArchiveDownloadUrl(scope.row)"
                      type="primary"
                      :href="getLogPullArchiveDownloadUrl(scope.row)"
                      target="_blank"
                      @click.prevent="downloadLogPullArchive(scope.row)"
                      @contextmenu.prevent="copyLogPullArchiveDownloadUrl(scope.row)"
                    >
                      {{ getLogPullArchiveDisplayText(scope.row) }}
                    </el-link>
                    <span v-else>-</span>
                  </template>
                </el-table-column>
                <el-table-column label="原始压缩包" min-width="180" show-overflow-tooltip>
                  <template #default="scope">
                    <el-link
                      v-if="getLogPullOriginalDownloadUrl(scope.row)"
                      type="primary"
                      :href="getLogPullOriginalDownloadUrl(scope.row)"
                      target="_blank"
                      @click.prevent="downloadLogPullOriginal(scope.row)"
                      @contextmenu.prevent="copyLogPullOriginalDownloadUrl(scope.row)"
                    >
                      {{ getLogPullOriginalDownloadUrl(scope.row) }}
                    </el-link>
                    <span v-else>-</span>
                  </template>
                </el-table-column>
                <el-table-column
                  label="摘要/异常"
                  prop="contentSummary"
                  min-width="220"
                  show-overflow-tooltip
                >
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
                        @click="openLogViewerFromPullRecord(scope.row)"
                        :disabled="logPullActionLoading"
                      >
                        查看日志
                      </el-button>
                      <el-button
                        link
                        type="warning"
                        @click="retryLogPull(scope.row)"
                        :disabled="
                          logPullActionLoading || activeLogPullStatuses.includes(scope.row.status)
                        "
                        v-hasPermi="['ticket:logpull:add']"
                      >
                        重新拉取
                      </el-button>
                      <el-button
                        link
                        type="success"
                        @click="redownloadLogPull(scope.row)"
                        :disabled="
                          logPullActionLoading ||
                          (!scope.row.commandResultUrl && !scope.row.storagePath)
                        "
                        v-hasPermi="['ticket:logpull:add']"
                      >
                        重新下载
                      </el-button>
                      <el-button
                        link
                        type="danger"
                        @click="deleteLogPull(scope.row)"
                        :disabled="
                          logPullActionLoading || activeLogPullStatuses.includes(scope.row.status)
                        "
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
                <el-form
                  ref="logPullRef"
                  :model="logPullForm"
                  :rules="logPullRules"
                  label-width="110px"
                >
                  <LogPullConfigFields
                    v-model="logPullForm"
                    :vendor-options="vendorOptions"
                    :parameter-examples="parameterExamples"
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
                    <el-button type="primary" @click="submitLogPull" :loading="logPullSubmitting"
                      >提交任务</el-button
                    >
                    <el-button @click="logPullSubmitOpen = false">取消</el-button>
                  </el-form-item>
                </el-form>
              </el-dialog>
            </el-tab-pane>

            <el-tab-pane label="协同/AI" name="collab" lazy>
              <div class="collab-toolbar mb16">
                <el-button
                  type="primary"
                  @click="openAiAnalysisDialog"
                  v-hasPermi="['ticket:ai:analysis:run']"
                >
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
                          <el-switch
                            v-model="messageForm.runAi"
                            inline-prompt
                            active-text="是"
                            inactive-text="否"
                          />
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
                          <el-select
                            v-model="messageForm.agentCode"
                            placeholder="可选"
                            filterable
                            clearable
                            @change="handleMessageAgentChange"
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
                        <el-form-item label="Provider">
                          <el-select
                            v-model="messageForm.aiProviderCode"
                            placeholder="可选"
                            filterable
                            clearable
                            style="width: 100%"
                            @change="handleMessageProviderChange"
                          >
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
                          <el-input
                            v-model="messageForm.content"
                            type="textarea"
                            :rows="4"
                            placeholder="补充追问、开发反馈、排查动作或AI结论"
                          />
                        </el-form-item>
                      </el-col>
                      <el-col :span="24">
                        <el-form-item label="附件JSON">
                          <el-input
                            v-model="messageDataText"
                            type="textarea"
                            :rows="3"
                            placeholder='可选，如 {"traceIds":["..."],"evidence":"..."}'
                          />
                        </el-form-item>
                      </el-col>
                      <el-col :span="24">
                        <el-form-item>
                          <el-button
                            type="primary"
                            @click="submitMessage"
                            v-hasPermi="['ticket:message:add']"
                            >提交消息</el-button
                          >
                          <el-button @click="resetMessageForm">重置</el-button>
                          <el-button
                            type="success"
                            plain
                            @click="saveSnapshotFromCurrentState"
                            v-hasPermi="['ticket:snapshot:add']"
                          >
                            生成快照
                          </el-button>
                          <el-button
                            type="warning"
                            plain
                            @click="generateKnowledgeFromTicket"
                            v-hasPermi="['ticket:knowledge:add']"
                          >
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
                      <pre v-if="item.attachments" class="json-block">{{
                        formatJson(item.attachments)
                      }}</pre>
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
                      <div class="similar-actions">
                        <el-link
                          type="primary"
                          :underline="false"
                          @click="openSystemTicketDetail(item)"
                          >系统详情</el-link
                        >
                        <el-link
                          v-if="resolveTicketDetailUrl(item)"
                          type="info"
                          :underline="false"
                          @click="openTicketLink(item)"
                        >
                          飞书详情
                        </el-link>
                      </div>
                    </div>
                  </el-card>
                </el-col>
              </el-row>
            </el-tab-pane>

            <el-tab-pane label="评论" name="comments" lazy>
              <el-form :model="commentForm" label-width="80px" class="mb16">
                <el-form-item label="评论">
                  <el-input
                    v-model="commentForm.content"
                    type="textarea"
                    :rows="3"
                    placeholder="请输入沟通评论"
                  />
                </el-form-item>
                <el-form-item>
                  <el-checkbox v-model="commentForm.isInternal">内部评论</el-checkbox>
                  <el-button
                    type="primary"
                    class="ml12"
                    @click="submitComment"
                    v-hasPermi="['ticket:comment:add']"
                  >
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
              <el-tabs
                v-model="historyActiveTab"
                class="history-entry-tabs"
                @tab-click="handleHistoryTabClick"
              >
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
                        <el-option
                          v-for="item in eventTypeOptions"
                          :key="item.value"
                          :label="item.label"
                          :value="item.value"
                        />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="事件说明">
                      <el-input
                        v-model="eventForm.content"
                        type="textarea"
                        :rows="3"
                        placeholder="记录查了什么、结论是什么"
                      />
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
                      <el-button
                        type="primary"
                        @click="submitEvent"
                        v-hasPermi="['ticket:event:add']"
                        >提交事件</el-button
                      >
                    </el-form-item>
                  </el-form>
                  <el-empty v-if="!timeline.events?.length" description="暂无事件" />
                  <el-card
                    v-for="item in timeline.events"
                    :key="item.id"
                    shadow="never"
                    class="mb8"
                  >
                    <div class="record-head">
                      <span>{{ item.eventType }}</span>
                      <span>{{ item.operatorName || '-' }}</span>
                      <span>{{ parseTime(item.createTime) }}</span>
                    </div>
                    <div>{{ item.content || '-' }}</div>
                    <pre v-if="item.eventData" class="json-block">{{
                      formatJson(item.eventData)
                    }}</pre>
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
                      <el-select
                        v-model="rcaForm.rootCauseCategory"
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
                      <el-button type="primary" @click="submitRca" v-hasPermi="['ticket:rca:edit']"
                        >保存RCA</el-button
                      >
                    </el-form-item>
                  </el-form>
                </el-tab-pane>
                <el-tab-pane v-if="false" label="日志拉取" name="logPull" lazy>
                  <div class="panel-header mb16">
                    <div class="panel-inline">
                      <span>拉取记录</span>
                      <el-tag v-if="logPullAutoRefreshing" size="small" type="warning"
                        >自动刷新中</el-tag
                      >
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
                      <el-button
                        type="primary"
                        @click="openLogPullSubmitDialog"
                        v-hasPermi="['ticket:logpull:add']"
                        >拉取日志</el-button
                      >
                      <el-button link type="primary" @click="loadLogPullList">刷新</el-button>
                    </div>
                  </div>
                  <el-table
                    v-loading="logPullLoading"
                    :data="logPullList"
                    row-key="id"
                    class="mb16"
                  >
                    <el-table-column label="创建时间" prop="createTime" width="170">
                      <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
                    </el-table-column>
                    <el-table-column label="数据类型" width="90" align="center">
                      <template #default="scope">
                        {{ getOptionLabel(logPullDataTypeOptions, scope.row.commandDataType) }}
                      </template>
                    </el-table-column>
                    <el-table-column
                      label="商家"
                      prop="vendorId"
                      width="110"
                      show-overflow-tooltip
                    />
                    <el-table-column
                      label="门店"
                      prop="storeId"
                      min-width="150"
                      show-overflow-tooltip
                    />
                    <el-table-column label="POSID" prop="posNo" width="110" show-overflow-tooltip />
                    <el-table-column label="状态" min-width="170">
                      <template #default="scope">
                        <el-tag :type="getLogPullStatusTagType(scope.row.status)">
                          {{
                            scope.row.statusDesc ||
                            getOptionLabel(logPullStatusOptions, scope.row.status)
                          }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column label="保存方式" width="90" align="center">
                      <template #default="scope">{{
                        getOptionLabel(logPullStorageModeOptions, scope.row.storageMode)
                      }}</template>
                    </el-table-column>
                    <el-table-column label="归档地址" min-width="220" show-overflow-tooltip>
                      <template #default="scope">
                        <el-link
                          v-if="scope.row.storagePath"
                          type="primary"
                          @click="downloadLogPullArchive(scope.row)"
                        >
                          {{ scope.row.storagePath }}
                        </el-link>
                        <span v-else>-</span>
                      </template>
                    </el-table-column>
                    <el-table-column label="原始压缩包" min-width="180" show-overflow-tooltip>
                      <template #default="scope">
                        <el-link
                          v-if="scope.row.commandResultUrl"
                          type="primary"
                          @click="downloadLogPullOriginal(scope.row)"
                        >
                          下载原始包
                        </el-link>
                        <span v-else>-</span>
                      </template>
                    </el-table-column>
                    <el-table-column
                      label="摘要/异常"
                      prop="contentSummary"
                      min-width="220"
                      show-overflow-tooltip
                    >
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
                            @click="openLogViewerFromPullRecord(scope.row)"
                            :disabled="logPullActionLoading"
                          >
                            查看日志
                          </el-button>
                          <el-button
                            link
                            type="warning"
                            @click="retryLogPull(scope.row)"
                            :disabled="
                              logPullActionLoading ||
                              activeLogPullStatuses.includes(scope.row.status)
                            "
                            v-hasPermi="['ticket:logpull:add']"
                          >
                            重新拉取
                          </el-button>
                          <el-button
                            link
                            type="success"
                            @click="redownloadLogPull(scope.row)"
                            :disabled="
                              logPullActionLoading ||
                              (!scope.row.commandResultUrl && !scope.row.storagePath)
                            "
                            v-hasPermi="['ticket:logpull:add']"
                          >
                            重新下载
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
                    <el-form
                      ref="logPullRef"
                      :model="logPullForm"
                      :rules="logPullRules"
                      label-width="110px"
                    >
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
                        <el-input-number
                          v-model="logPullForm.posNo"
                          :min="1"
                          controls-position="right"
                        />
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
                        <el-input
                          v-model="logPullForm.path"
                          placeholder="可选，按路径拉取"
                          clearable
                        />
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
                            <el-input-number
                              v-model="logPullForm.rangeBeforeMinutes"
                              :min="0"
                              controls-position="right"
                            />
                            <span>分钟，后</span>
                            <el-input-number
                              v-model="logPullForm.rangeAfterMinutes"
                              :min="0"
                              controls-position="right"
                            />
                            <span>分钟</span>
                          </div>
                        </el-form-item>
                      </template>
                      <el-form-item label="单文件上限">
                        <el-input-number
                          v-model="logPullForm.fileMaxSize"
                          :min="1"
                          controls-position="right"
                        />
                      </el-form-item>
                      <el-form-item label="压缩包上限">
                        <el-input-number
                          v-model="logPullForm.zipMaxSize"
                          :min="1"
                          controls-position="right"
                        />
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
                        <el-switch
                          v-model="logPullForm.autoAiEnabled"
                          inline-prompt
                          active-text="是"
                          inactive-text="否"
                        />
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
      <el-form
        ref="aiAnalysisRef"
        :model="aiAnalysisTaskForm"
        :rules="aiAnalysisRules"
        label-width="110px"
      >
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
          <el-select
            v-model="aiAnalysisTaskForm.agentCode"
            placeholder="可选，优先使用指定Agent"
            filterable
            clearable
            style="width: 100%"
            @change="handleAiAnalysisAgentChange"
          >
            <el-option
              v-for="item in agentOptions"
              :key="item.agentCode"
              :label="`${item.agentName || item.agentCode} [${item.agentCode}]`"
              :value="item.agentCode"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Provider">
          <el-select
            v-model="aiAnalysisTaskForm.aiProviderCode"
            placeholder="可选，优先使用指定Provider"
            filterable
            clearable
            style="width: 100%"
            @change="handleAiAnalysisProviderChange"
          >
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
        <el-form-item label="日志模式">
          <el-select
            v-model="aiAnalysisTaskForm.logAnalysisMode"
            placeholder="请选择日志分析模式"
            style="width: 100%"
          >
            <el-option label="生成摘要" value="digest" />
            <el-option label="完整目录" value="full_directory" />
            <el-option label="摘要 + 完整目录" value="hybrid" />
          </el-select>
        </el-form-item>
        <el-form-item label="日志时间">
          <el-radio-group v-model="aiAnalysisTaskForm.logTimeMode">
            <el-radio-button label="none">不指定</el-radio-button>
            <el-radio-button label="range">开始/结束</el-radio-button>
            <el-radio-button label="point">时间点前后</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <template v-if="aiAnalysisTaskForm.logTimeMode === 'range'">
          <el-form-item label="开始时间">
            <el-date-picker
              v-model="aiAnalysisTaskForm.logBeginTime"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              placeholder="选择日志开始时间"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="结束时间">
            <el-date-picker
              v-model="aiAnalysisTaskForm.logEndTime"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              placeholder="选择日志结束时间"
              style="width: 100%"
            />
          </el-form-item>
        </template>
        <template v-if="aiAnalysisTaskForm.logTimeMode === 'point'">
          <el-form-item label="问题时间点">
            <el-date-picker
              v-model="aiAnalysisTaskForm.logPointTime"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              placeholder="选择问题发生时间"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="前后分钟">
            <div class="inline-inputs">
              <el-input-number v-model="aiAnalysisTaskForm.rangeBeforeMinutes" :min="0" :step="1" />
              <span class="inline-separator">前</span>
              <el-input-number v-model="aiAnalysisTaskForm.rangeAfterMinutes" :min="0" :step="1" />
              <span class="inline-separator">后</span>
            </div>
          </el-form-item>
        </template>
        <el-form-item v-if="aiAnalysisTaskForm.logTimeMode !== 'none'" label="缺失策略">
          <el-select
            v-model="aiAnalysisTaskForm.logWindowMissingStrategy"
            placeholder="数据库没有截取正文时怎么处理"
            style="width: 100%"
          >
            <el-option label="Agent 本地截取" value="agent_extract" />
            <el-option label="服务端实时截取" value="server_extract" />
          </el-select>
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
            @change="handleAiAnalysisPromptTemplateChange"
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
        <el-button
          type="primary"
          :loading="aiAnalysisSubmitting"
          @click="submitAiAnalysis"
          v-hasPermi="['ticket:ai:analysis:run']"
        >
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
        <el-button link type="primary" @click="loadAiAnalysisTasks" :loading="aiTaskLoading"
          >刷新</el-button
        >
      </div>
      <el-table v-loading="aiTaskLoading" :data="aiTaskList" row-key="taskId">
        <el-table-column label="提交时间" prop="createTime" width="170">
          <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="scope">
            <el-tag :type="getAiStatusTagType(scope.row.status)">{{
              getAiStatusLabel(scope.row.status)
            }}</el-tag>
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
        <el-descriptions-item label="任务ID">{{
          aiTaskDetailPayload.taskId || '-'
        }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag
            v-if="aiTaskDetailPayload.status"
            :type="getAiStatusTagType(aiTaskDetailPayload.status)"
          >
            {{ getAiStatusLabel(aiTaskDetailPayload.status) }}
          </el-tag>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="版本">{{
          aiTaskDetailPayload.versionKey || '-'
        }}</el-descriptions-item>
        <el-descriptions-item label="Agent">{{
          aiTaskDetailPayload.agentCode || '-'
        }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{
          parseTime(aiTaskDetailPayload.createTime) || '-'
        }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{
          parseTime(aiTaskDetailPayload.finishedAt || aiTaskDetailPayload.updateTime) || '-'
        }}</el-descriptions-item>
        <el-descriptions-item label="仓库地址" :span="2">{{
          aiTaskDetailPayload.repoUrl || '-'
        }}</el-descriptions-item>
        <el-descriptions-item label="分支名称" :span="2">{{
          aiTaskDetailPayload.branchName || '-'
        }}</el-descriptions-item>
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
          <pre class="json-block task-detail-block">{{
            aiTaskDetailPayload.promptText || '-'
          }}</pre>
        </el-tab-pane>
        <el-tab-pane label="原始输出">
          <pre class="json-block task-detail-block">{{ aiTaskDetailPayload.rawOutput || '-' }}</pre>
        </el-tab-pane>
        <el-tab-pane label="分析结果">
          <pre class="json-block task-detail-block">{{
            aiTaskDetailPayload.analysisResult
              ? formatJson(aiTaskDetailPayload.analysisResult)
              : '-'
          }}</pre>
        </el-tab-pane>
        <el-tab-pane label="上下文">
          <pre class="json-block task-detail-block">{{
            aiTaskDetailPayload.analysisContext
              ? formatJson(aiTaskDetailPayload.analysisContext)
              : '-'
          }}</pre>
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
      <el-form
        ref="aiRepoMappingRef"
        :model="aiRepoMappingForm"
        :rules="aiRepoMappingRules"
        label-width="110px"
      >
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="项目" prop="projectId">
              <el-select
                v-model="aiRepoMappingForm.projectId"
                placeholder="请选择项目"
                filterable
                style="width: 100%"
              >
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
            <el-form-item label="版本标识" prop="versionKey">
              <el-input v-model="aiRepoMappingForm.versionKey" placeholder="例如 release/2.1.3" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="仓库地址" prop="repoUrl">
              <el-input
                v-model="aiRepoMappingForm.repoUrl"
                placeholder="git@gitlab.xxx/project.git"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分支名称" prop="branchName">
              <el-input v-model="aiRepoMappingForm.branchName" placeholder="release/2.1.3" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="本地仓库" prop="localRepoPath">
              <el-input
                v-model="aiRepoMappingForm.localRepoPath"
                placeholder="留空则使用 Agent 本地配置"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作区根目录">
              <el-input
                v-model="aiRepoMappingForm.workspaceRoot"
                placeholder="留空则使用 Agent 本地配置"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Worker命令">
              <el-input
                v-model="aiRepoMappingForm.workerCommand"
                placeholder="留空则使用系统默认 codex exec"
              />
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
        <el-form
          ref="projectVendorMapRef"
          :model="projectVendorMapForm"
          :rules="projectVendorMapRules"
          label-width="110px"
        >
          <el-form-item label="项目">
            <el-select
              v-model="projectVendorMapForm.projectId"
              placeholder="项目"
              filterable
              style="width: 100%"
              disabled
            >
              <el-option
                v-for="item in projectOptions"
                :key="item.projectId"
                :label="item.projectName"
                :value="item.projectId"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="项目名称">
            <el-input v-model="projectVendorMapForm.projectName" disabled />
          </el-form-item>
          <el-form-item label="商户编号" prop="venderNo">
            <el-input
              v-model="projectVendorMapForm.venderNo"
              placeholder="请输入 vender_no"
              maxlength="30"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="projectVendorMapOpen = false">取消</el-button>
        <el-button
          type="primary"
          :loading="projectVendorMapSubmitting"
          @click="submitProjectVendorMap"
          >保存</el-button
        >
      </template>
    </el-dialog>

    <el-dialog
      v-model="logPullContentOpen"
      :title="logViewerDialogTitle"
      fullscreen
      append-to-body
      destroy-on-close
      :close-on-click-modal="false"
      class="ticket-log-viewer-dialog"
      @closed="handleLogPullDialogClosed"
    >
      <div v-loading="logViewerSearching">
        <div class="panel-header mb16 log-view-controls">
          <el-input
            v-model="logViewerForm.keyword"
            placeholder="关键词搜索"
            clearable
            @keyup.enter="searchLogViewerKeyword"
          />
          <el-button type="primary" :loading="logViewerSearching" @click="searchLogViewerKeyword"
            >搜索</el-button
          >
          <el-select
            v-model="logViewerForm.file"
            class="log-file-scope-select"
            clearable
            filterable
            placeholder="全局搜索"
          >
            <el-option
              v-for="file in logViewerFileOptions"
              :key="file"
              :label="file"
              :value="file"
            />
          </el-select>
          <el-button
            v-if="logViewerForm.file"
            link
            type="primary"
            @click="clearLogViewerFileScope"
            >清除文件范围</el-button
          >
          <el-text>上下文</el-text>
          <el-input-number
            v-model="logViewerForm.contextLines"
            :min="0"
            :max="500"
            controls-position="right"
          />
          <el-text>结果上限</el-text>
          <el-input-number
            v-model="logViewerForm.limit"
            :min="1"
            :max="5000"
            :step="100"
            controls-position="right"
          />
          <el-button
            type="warning"
            @click="retryLogPull(selectedLogPullRecord)"
            :disabled="logPullActionLoading"
            v-hasPermi="['ticket:logpull:add']"
          >
            重新拉取
          </el-button>
          <el-button
            type="success"
            @click="redownloadLogPull(selectedLogPullRecord)"
            :disabled="
              logPullActionLoading ||
              (!selectedLogPullRecord?.commandResultUrl && !selectedLogPullRecord?.storagePath)
            "
            v-hasPermi="['ticket:logpull:add']"
          >
            重新下载
          </el-button>
          <el-button type="warning" :loading="logViewerSearching" @click="loadLogViewerErrors"
            >异常提取</el-button
          >
        </div>
        <el-alert
          v-if="logViewerErrorSummary"
          type="warning"
          show-icon
          :closable="false"
          class="mb16"
          :title="`异常命中 ${logViewerErrorSummary.total || 0} 条`"
        />
        <div
          v-if="logViewerHits.length"
          :class="[
            'log-view-panel',
            'mb16',
            {
              'log-view-panel-fullscreen': logViewerResultViewMode === 'fullscreen',
              'log-view-panel-minimized': logViewerResultViewMode === 'minimized',
            },
          ]"
        >
          <div class="panel-header mb8 log-view-panel-header">
            <span
              >搜索结果：{{ logViewerHits.length }} 条（当前上限
              {{ logViewerForm.limit }} 条）</span
            >
            <div class="panel-inline">
              <el-button
                link
                type="primary"
                :icon="logViewerResultViewMode === 'minimized' ? 'Plus' : 'Minus'"
                @click="
                  setLogViewerPanelMode(
                    'result',
                    logViewerResultViewMode === 'minimized' ? 'normal' : 'minimized'
                  )
                "
              >
                {{ logViewerResultViewMode === 'minimized' ? '展开' : '最小化' }}
              </el-button>
              <el-button
                link
                type="primary"
                :icon="logViewerResultViewMode === 'fullscreen' ? 'FullScreen' : 'Rank'"
                @click="
                  setLogViewerPanelMode(
                    'result',
                    logViewerResultViewMode === 'fullscreen' ? 'normal' : 'fullscreen'
                  )
                "
              >
                {{ logViewerResultViewMode === 'fullscreen' ? '还原' : '放大全屏' }}
              </el-button>
            </div>
          </div>
          <el-table
            v-show="logViewerResultViewMode !== 'minimized'"
            :data="logViewerHits"
            row-key="hitKey"
            size="small"
            :max-height="logViewerResultTableHeight"
            @row-click="selectLogViewerHit"
          >
            <el-table-column label="文件" prop="file" min-width="220" show-overflow-tooltip />
            <el-table-column label="行号" prop="line" width="90" />
            <el-table-column label="内容" prop="content" min-width="360" show-overflow-tooltip />
            <el-table-column label="操作" width="130" fixed="right">
              <template #default="scope">
                <el-button
                  link
                  type="primary"
                  @click.stop="searchLogViewerInFile(scope.row.file)"
                  >在此文件搜索</el-button
                >
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div
          v-if="logViewerContext"
          :class="[
            'log-context-panel',
            'log-view-panel',
            'mb16',
            {
              'log-view-panel-fullscreen': logViewerContextViewMode === 'fullscreen',
              'log-view-panel-minimized': logViewerContextViewMode === 'minimized',
            },
          ]"
        >
          <div class="panel-header mb8 log-view-panel-header">
            <span
              >{{ logViewerContext.file }}:{{ logViewerContext.line }}（{{
                logViewerContext.start
              }}-{{ logViewerContext.end }}/{{ logViewerContext.totalLines }}）</span
            >
            <div class="panel-inline">
              <el-switch
                v-model="logPullWrapEnabled"
                inline-prompt
                active-text="换行"
                inactive-text="不换行"
              />
              <el-tag v-if="logViewerHighlightText" type="warning" effect="plain" round>
                高亮：{{ logViewerHighlightText }}
              </el-tag>
              <el-button
                v-if="logViewerHighlightText"
                link
                type="primary"
                @click="clearLogViewerHighlight"
                >清除高亮</el-button
              >
              <el-button
                link
                type="primary"
                :disabled="!logViewerContext.hasPrev || logViewerSearching"
                @click="pageLogViewerContext(-1)"
                >上一段</el-button
              >
              <el-button
                link
                type="primary"
                :disabled="!logViewerContext.hasNext || logViewerSearching"
                @click="pageLogViewerContext(1)"
                >下一段</el-button
              >
              <el-button
                link
                type="primary"
                :icon="logViewerContextViewMode === 'minimized' ? 'Plus' : 'Minus'"
                @click="
                  setLogViewerPanelMode(
                    'context',
                    logViewerContextViewMode === 'minimized' ? 'normal' : 'minimized'
                  )
                "
              >
                {{ logViewerContextViewMode === 'minimized' ? '展开' : '最小化' }}
              </el-button>
              <el-button
                link
                type="primary"
                :icon="logViewerContextViewMode === 'fullscreen' ? 'FullScreen' : 'Rank'"
                @click="
                  setLogViewerPanelMode(
                    'context',
                    logViewerContextViewMode === 'fullscreen' ? 'normal' : 'fullscreen'
                  )
                "
              >
                {{ logViewerContextViewMode === 'fullscreen' ? '还原' : '放大全屏' }}
              </el-button>
            </div>
          </div>
          <pre
            v-show="logViewerContextViewMode !== 'minimized'"
            :class="[
              'log-content-block',
              'log-context-block',
              { 'log-content-wrap': logPullWrapEnabled },
            ]"
            @mouseup="captureLogViewerHighlight"
            ><span
              v-for="item in logViewerContextDisplayLines"
              :key="`${item.file}:${item.line}`"
              class="log-context-line"
              ><span class="log-context-line-no">{{ item.paddedLine }}</span
              ><span class="log-context-line-content"
                ><template v-for="(part, partIndex) in item.parts" :key="partIndex"
                  ><mark v-if="part.highlight" class="log-context-highlight">{{
                    part.text
                  }}</mark
                  ><span v-else>{{ part.text }}</span></template
                ></span
              ></span
            ></pre
          >
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup name="TicketIndex">
  import { saveAs } from 'file-saver';
  import LogPullConfigFields from '@/components/ticket/LogPullConfigFields.vue';
  import LogPullNotifyConfigFields from '@/components/ticket/LogPullNotifyConfigFields.vue';
  import {
    addTicket,
    addTicketMessage,
    addTicketComment,
    addTicketEvent,
    addTicketAiAnalysis,
    assignTicket,
    changeTicketStatus,
    delTicket,
    downloadTicketImportTemplate,
    extractTicketKnowledge,
    getTicket,
    getTicketComments,
    getTicketTimeline,
    importTicketExcel,
    listTicketAiAnalysisTasks,
    retryTicketAiAnalysis,
    addTicketSnapshot,
    saveTicketRca,
    getTicketLogPullProjectVendorMap,
    saveTicketLogPullProjectVendorMap,
    translateTicketDescription,
    updateTicket,
  } from '@/api/ticket/ticket';
  import {
    eventTypeOptions,
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
    getOptionalLogPullTimeRangeError,
    hasLogPullTimeRange,
    normalizeLogPullNotifyConfig,
  } from './logPull.shared';
  import UserSelect from './components/UserSelect.vue';
  import { useRoute, useRouter } from 'vue-router';
  import { useWorkflow } from './hooks/useWorkflow';
  import { useAiRepoMapping } from './hooks/useAiRepoMapping';
  import { useOptions } from './hooks/useOptions';
  import { useLogViewer } from './hooks/useLogViewer';
  import { useTicketList } from './hooks/useTicketList';
  import {
    buildTicketAiPreferenceDefaults,
    saveTicketAiPreferencePatch,
  } from './hooks/useTicketAiPreference';

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
    analysisPromptOptions,
    vendorOptions,
    parameterExamples,
    pushOptions,
    detailVersionOptions,
    loadVendorOptions,
    loadProjectVendorMapOptions,
    getProjectVendorNo,
    getVendorStoreOptions,
    loadProviderOptions,
    loadAnalysisPromptOptions,
    getTicketAutomationLogPullConfig,
    resolveAiAnalysisProviderAgent,
    resolveDefaultAiPromptTemplateCodesFromDetail,
    loadDetailVersionOptions,
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
  // agentOptions / providerOptions / analysisPromptOptions / vendorOptions / parameterExamples / pushOptions 已通过 useOptions() 提供
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
  const detailMainTab = ref('overview');
  const descriptionExpanded = ref(true);
  const translationExpanded = ref(false);
  const descriptionTranslateLoading = ref(false);
  const historyActiveTab = ref('timeline');
  const title = ref('');
  const currentTicketId = ref();
  const currentAssigneeOption = ref(null);
  const firstLineAssigneeOption = ref(null);
  const internalOwnerOption = ref(null);
  const formModuleValue = ref('');
  const detail = ref({});
  const timeline = ref({});
  const commentList = ref([]);
  const commentLoading = ref(false);
  const commentLoaded = ref(false);
  const ticketMessages = ref([]);
  const ticketSnapshots = ref([]);
  const similarTickets = ref([]);
  const tagText = ref('');
  const eventDataText = ref('');
  const messageDataText = ref('');
  const importResult = ref(null);
  // 日志拉取 + 日志查看器 已提取到 hooks/useLogViewer.js
  const {
    logPullLoading,
    logPullSubmitting,
    logPullActionLoading,
    logPullSubmitOpen,
    logPullContentOpen,
    logPullList,
    logPullTotal,
    logPullForm,
    logPullQuery,
    logPullWrapEnabled,
    logPullAutoRefreshing,
    selectedLogPullRecord,
    activeLogPullStatuses,
    logViewerTicketMeta,
    logViewerSearching,
    logViewerHits,
    logViewerContext,
    logViewerErrorSummary,
    logViewerResultViewMode,
    logViewerContextViewMode,
    logViewerHighlightText,
    logViewerForm,
    createDefaultLogPullForm,
    buildCleanLogPullConfig,
    resetStoreSelection,
    resetLogPullForm,
    openLogPullSubmitDialog,
    stopLogPullAutoRefresh,
    loadLogPullList,
    handleLogPullVendorChange,
    submitLogPull,
    deleteLogPull,
    retryLogPull,
    redownloadLogPull,
    getLogPullOriginalDownloadUrl,
    getLogPullArchiveDownloadUrl,
    getLogPullArchiveDisplayText,
    formatLogPullParameter,
    copyLogPullOriginalDownloadUrl,
    copyLogPullArchiveDownloadUrl,
    downloadLogPullArchive,
    downloadLogPullOriginal,
    openTicketLogViewer,
    openLogViewerFromPullRecord,
    handleLogPullDialogClosed,
    searchLogViewerInFile,
    clearLogViewerFileScope,
    captureLogViewerHighlight,
    clearLogViewerHighlight,
    setLogViewerPanelMode,
    searchLogViewerKeyword,
    loadLogViewerErrors,
    selectLogViewerHit,
    pageLogViewerContext,
  } = useLogViewer(proxy, currentTicketId, {
    detail,
    detailOpen,
    getList,
    refreshDetail,
    applyProjectVendorMapping,
    getVendorStoreOptions,
  });

  /**
   * 根据工单项目映射预填日志拉取供应商。
   * 拆分后日志拉取表单归 useLogViewer 管理，因此保留在页面层完成跨 hook 状态回写。
   */
  function applyProjectVendorMapping(projectId) {
    const vendorNo = getProjectVendorNo(projectId)
    if (!vendorNo) {
      return
    }
    const resolvedVendorId = Number(vendorNo)
    logPullForm.value.vendorId = Number.isNaN(resolvedVendorId) ? vendorNo : resolvedVendorId
    resetStoreSelection(logPullForm.value, logPullForm.value.vendorId)
  }
  const aiAnalysisSubmitting = ref(false);
  const aiAnalysisRetryLoading = ref(false);
  const aiAnalysisRefreshLoading = ref(false);
  const aiAnalysisOpen = ref(false);
  const aiTaskHistoryOpen = ref(false);
  const aiTaskDetailOpen = ref(false);
  const selectedAiTask = ref(null);
  // aiRepoMapping* 已提取到 hooks/useAiRepoMapping.js
  const {
    aiRepoMappingOpen,
    aiRepoMappingSubmitting,
    aiRepoMappingList,
    aiRepoMappingTotal,
    aiRepoMappingForm,
    aiRepoMappingRules,
    resetAiRepoMappingForm,
    openAiRepoMappingDialog,
    submitAiRepoMapping,
  } = useAiRepoMapping(detail, proxy);
  const projectVendorMapOpen = ref(false);
  const projectVendorMapLoading = ref(false);
  const projectVendorMapSubmitting = ref(false);
  const aiTaskLoading = ref(false);
  const aiTaskList = ref([]);
  const aiTaskTotal = ref(0);
  // detailVersionOptions 已通过 useOptions() 提供
  const aiAnalysisTaskForm = ref({
    versionKey: '',
    logPullRecordId: undefined,
    agentCode: '',
    aiProviderCode: '',
    forceRefresh: false,
    logAnalysisMode: 'hybrid',
    logTimeMode: 'none',
    logWindowMissingStrategy: 'agent_extract',
    logBeginTime: '',
    logEndTime: '',
    logPointTime: '',
    rangeBeforeMinutes: 5,
    rangeAfterMinutes: 10,
    extraInstruction: '',
    promptTemplateCodes: [],
  });

  /**
   * 根据 Provider 绑定关系回填 AI 分析 Agent。
   * useOptions 只负责解析选项，页面层负责写入当前分析表单。
   */
  function applyAiAnalysisProviderAgent(providerCode) {
    const providerAgentCode = resolveAiAnalysisProviderAgent(providerCode)
    if (providerAgentCode) {
      aiAnalysisTaskForm.value.agentCode = providerAgentCode
    }
  }

  /**
   * 根据 Provider 绑定关系回填协同消息 Agent。
   */
  function applyMessageProviderAgent(providerCode) {
    const providerAgentCode = resolveAiAnalysisProviderAgent(providerCode);
    if (providerAgentCode) {
      messageForm.value.agentCode = providerAgentCode;
    }
  }

  /**
   * 记录发起 AI 分析弹窗中用户手动选择的 Agent。
   */
  function handleAiAnalysisAgentChange(agentCode) {
    saveTicketAiPreferencePatch({ agentCode });
  }

  /**
   * 处理 AI 分析 Provider 变更，保持与备份分支一致的 Agent 自动带入行为。
   */
  function handleAiAnalysisProviderChange(providerCode) {
    applyAiAnalysisProviderAgent(providerCode)
    saveTicketAiPreferencePatch({
      aiProviderCode: providerCode,
      agentCode: aiAnalysisTaskForm.value.agentCode,
    })
  }

  /**
   * 记录发起 AI 分析弹窗中用户手动选择的追加提示词。
   */
  function handleAiAnalysisPromptTemplateChange(promptTemplateCodes) {
    saveTicketAiPreferencePatch({ promptTemplateCodes });
  }

  /**
   * 记录协同/AI 表单中用户手动选择的 Agent。
   */
  function handleMessageAgentChange(agentCode) {
    saveTicketAiPreferencePatch({ agentCode });
  }

  /**
   * 处理协同/AI Provider 变更，并保存本次手动选择。
   */
  function handleMessageProviderChange(providerCode) {
    applyMessageProviderAgent(providerCode);
    saveTicketAiPreferencePatch({
      aiProviderCode: providerCode,
      agentCode: messageForm.value.agentCode,
    });
  }

  /**
   * 从当前工单详情解析默认追加提示词编码。
   */
  function resolveDefaultAiPromptTemplateCodes() {
    return resolveDefaultAiPromptTemplateCodesFromDetail(detail.value)
  }
  const projectVendorMapForm = ref({
    projectId: undefined,
    projectName: '',
    venderNo: '',
  });
  const aiTaskQuery = ref({
    pageNum: 1,
    pageSize: 10,
    status: undefined,
  });

  let suppressProjectWatcher = false;
  // activeLogPullStatuses 已通过 useLogViewer() 提供
  const aiTerminalStatuses = ['success', 'failed', 'canceled'];
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

  const data = reactive({
    // queryParams 已通过 useTicketList() 提供
    form: createDefaultTicketForm(),
    assignForm: {},
    statusForm: {},
    commentForm: {
      content: '',
      isInternal: false,
    },
    messageForm: {
      role: 'user',
      messageType: 'question',
      content: '',
      runAi: true,
      versionKey: '',
      agentCode: '',
      aiProviderCode: '',
    },
    eventForm: {
      eventType: 'ANALYSIS',
      content: '',
    },
    rcaForm: {},
    // logPullForm / logPullQuery 已通过 useLogViewer() 提供
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
    logPullRules: {
      vendorId: [{ required: true, message: 'vendorId不能为空', trigger: 'blur' }],
      storeId: [{ required: true, message: 'storeId不能为空', trigger: 'blur' }],
      posNo: [{ required: true, message: 'posNo不能为空', trigger: 'blur' }],
    },
    aiAnalysisRules: {
      versionKey: [],
    },
    // aiRepoMappingRules 已提取到 hooks/useAiRepoMapping.js
    projectVendorMapRules: {
      venderNo: [{ required: true, message: '商户编号不能为空', trigger: 'blur' }],
    },
  });

  const {
    // queryParams 已通过 useTicketList() 提供
    form,
    assignForm,
    statusForm,
    commentForm,
    messageForm,
    eventForm,
    rcaForm,
    // logPullForm / logPullQuery 已通过 useLogViewer() 提供
    rules,
    assignRules,
    statusRules,
    logPullRules,
    aiAnalysisRules,
    projectVendorMapRules,
  } = toRefs(data);

  const detailTitle = computed(() => `工单详情：${detail.value.title || ''}`);
  const detailOriginalDescription = computed(() => {
    const originalText = String(
      detail.value.originalDescription ||
        detail.value.extraData?.originDescription ||
        detail.value.extraData?.origin_description ||
        ''
    ).trim();
    if (originalText) {
      return originalText;
    }
    const description = String(detail.value.description || '').trim();
    return description.includes('【AI翻译】')
      ? description.split('【AI翻译】')[0].trim()
      : description;
  });
  const detailAiTranslation = computed(() =>
    String(
      detail.value.aiTranslation ||
        detail.value.extraData?.aiTranslation ||
        detail.value.extraData?.ai_translation ||
        ''
    ).trim()
  );
  const latestSnapshotSummary = computed(
    () => latestSnapshot.value?.summary || detail.value.rootCause || detail.value.description || ''
  );
  /** 根据当前搜索结果生成可选文件范围，支持先全局搜索再收敛到单文件。 */
  const logViewerFileOptions = computed(() => {
    const files = new Set();
    logViewerHits.value.forEach((item) => {
      const file = String(item?.file || '').trim();
      if (file) files.add(file);
    });
    const scopedFile = String(logViewerForm.value.file || '').trim();
    if (scopedFile) files.add(scopedFile);
    return Array.from(files).sort();
  });
  /** 将一行日志按当前选中文案拆成普通片段和高亮片段。 */
  function splitLogViewerHighlightParts(content) {
    const text = String(content || '');
    const keyword = String(logViewerHighlightText.value || '');
    if (!keyword) return [{ text, highlight: false }];
    const parts = [];
    let cursor = 0;
    while (cursor < text.length) {
      const index = text.indexOf(keyword, cursor);
      if (index < 0) {
        parts.push({ text: text.slice(cursor), highlight: false });
        break;
      }
      if (index > cursor) {
        parts.push({ text: text.slice(cursor, index), highlight: false });
      }
      parts.push({ text: text.slice(index, index + keyword.length), highlight: true });
      cursor = index + keyword.length;
    }
    return parts.length ? parts : [{ text, highlight: false }];
  }
  /** 生成日志详细信息块的展示行，避免在模板中拼接行号和高亮结构。 */
  const logViewerContextDisplayLines = computed(() => {
    const lines = logViewerContext.value?.lines || [];
    return lines.map((item) => ({
      file: item.file || logViewerContext.value?.file || '',
      line: item.line,
      paddedLine: `${String(item.line).padStart(6, ' ')}  `,
      parts: splitLogViewerHighlightParts(item.content || ''),
    }));
  });
  const logViewerResultTableHeight = computed(() =>
    logViewerResultViewMode.value === 'fullscreen' ? 'calc(100vh - 170px)' : 320
  );
  const logViewerDialogTitle = computed(() => {
    const ticketNo = String(logViewerTicketMeta.value?.ticketNo || '').trim();
    const ticketTitle = String(logViewerTicketMeta.value?.title || '').trim();
    if (ticketNo && ticketTitle) {
      return `日志查看 - ${ticketNo} - ${ticketTitle}`;
    }
    if (ticketNo) {
      return `日志查看 - ${ticketNo}`;
    }
    if (ticketTitle) {
      return `日志查看 - ${ticketTitle}`;
    }
    return '日志查看';
  });

  function resolveTicketProcessStatus(row) {
    const latestAi = row?.latestAiAnalysis || row?.latest_ai_analysis || null;
    const latestLog = row?.latestLogPull || row?.latest_log_pull || null;
    const aiStatus = String(latestAi?.status || '').trim();
    if (aiStatus) {
      if (['created', 'running'].includes(aiStatus)) {
        return { label: getOptionLabel(ticketProcessStatusOptions, 'ai_running'), type: 'warning' };
      }
      if (aiStatus === 'success') {
        return { label: getOptionLabel(ticketProcessStatusOptions, 'ai_success'), type: 'success' };
      }
      if (['failed', 'canceled'].includes(aiStatus)) {
        return { label: getOptionLabel(ticketProcessStatusOptions, 'ai_failed'), type: 'danger' };
      }
    }
    const logStatus = String(latestLog?.status || '').trim();
    if (!logStatus) {
      return { label: getOptionLabel(ticketProcessStatusOptions, 'no_log_pull'), type: 'info' };
    }
    if (logStatus === 'success') {
      return {
        label: getOptionLabel(ticketProcessStatusOptions, 'ai_not_analyzed'),
        type: 'primary',
      };
    }
    if (['failed', 'exception'].includes(logStatus)) {
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

  // normalizeWorkflowStatusOptions / getStatusTagType / loadWorkflowConfig 已提取到 hooks/useWorkflow.js

  const latestAiAnalysisTask = computed(() => detail.value.latestAiAnalysis || null);

  const latestSnapshot = computed(
    () => detail.value.latestSnapshot || ticketSnapshots.value[0] || null
  );
  const latestSimilarTickets = computed(() => (similarTickets.value || []).slice(0, 3));
  const aiTaskDetailPayload = computed(() => selectedAiTask.value || {});
  const aiPromptLayers = computed(() => detail.value.aiPromptLayers || {});
  const logPullStoreOptions = computed(() => getVendorStoreOptions(logPullForm.value.vendorId));
  const aiPromptHintTitle = computed(() => {
    const projectName =
      aiPromptLayers.value?.project?.projectName || detail.value.projectName || '';
    const moduleName = aiPromptLayers.value?.module?.moduleName || detail.value.moduleName || '';
    const parts = ['AI 分析会自动叠加默认提示词'];
    if (projectName) {
      parts.push(`项目：${projectName}`);
    }
    if (moduleName) {
      parts.push(`模块：${moduleName}`);
    }
    return parts.join('，');
  });
  const aiPromptHintDesc = computed(() => {
    const hasDefaultPrompt = Boolean(aiPromptLayers.value?.hasDefaultPrompt);
    if (!hasDefaultPrompt) {
      return '当前工单未读取到项目/模块默认提示词，仍可填写额外说明来补充本次分析重点。';
    }
    return '项目和模块的默认提示词会自动参与本次分析，额外说明仅用于补充临时背景，不会覆盖系统约束和输出结构。';
  });

  // ticketStatusOptions / statusTransitionOptions 已提取到 hooks/useWorkflow.js

  const timelineItems = computed(() => {
    const items = [];
    (timeline.value.statusHistory || []).forEach((item) => {
      items.push({
        key: `status-${item.id}`,
        time: item.startedAt,
        title: `状态流转：${getOptionLabel(ticketStatusOptions.value, item.fromStatus)} -> ${getOptionLabel(ticketStatusOptions.value, item.toStatus)}`,
        content: item.comment,
      });
    });
    (timeline.value.assignHistory || []).forEach((item) => {
      items.push({
        key: `assign-${item.id}`,
        time: item.assignedAt,
        title: `指派：${item.fromUserName || '未指派'} -> ${item.toUserName || '-'}`,
        content: item.reason,
      });
    });
    (timeline.value.events || []).forEach((item) => {
      items.push({
        key: `event-${item.id}`,
        time: item.createTime,
        title: `事件：${item.eventType}`,
        content: item.content,
      });
    });
    return items.sort((a, b) => new Date(a.time || 0) - new Date(b.time || 0));
  });

  const messageItems = computed(() => {
    return (ticketMessages.value || []).map((item) => ({
      ...item,
      roleLabel: item.role || 'user',
      typeLabel: item.messageType || 'question',
    }));
  });

  // 将查询栏中的单值或多选数组统一转成数组，便于后续拼接查询参数。

  // 将多选数组拼成后端约定的逗号分隔查询参数。

  // 构造工单列表查询参数，避免全局 GET 序列化把数组转成 field[0] 形式。

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

  function refreshDetail() {
    if (!currentTicketId.value) {
      return Promise.resolve();
    }
    return getTicket(currentTicketId.value).then((response) => {
      syncDetailBundle(response.data || {});
      loadDetailVersionOptions(detail.value.projectId);
    });
  }

  // createDefaultAiRepoMappingForm / resetAiRepoMappingForm 已提取到 hooks/useAiRepoMapping.js

  function createDefaultProjectVendorMapForm(projectId, projectName) {
    return {
      projectId,
      projectName: projectName || '',
      venderNo: '',
    };
  }

  function resetProjectVendorMapForm() {
    projectVendorMapForm.value = createDefaultProjectVendorMapForm(
      detail.value.projectId,
      detail.value.projectName || detail.value.merchantName || ''
    );
    if (proxy.$refs.projectVendorMapRef) {
      proxy.resetForm('projectVendorMapRef');
    }
  }

  function openProjectVendorMapDialog() {
    if (!detail.value.projectId) {
      proxy.$modal.msgWarning('当前工单缺少项目，无法维护商家映射');
      return;
    }
    projectVendorMapLoading.value = true;
    getTicketLogPullProjectVendorMap(detail.value.projectId)
      .then((response) => {
        const row = response.data || {};
        projectVendorMapForm.value = {
          projectId: row.projectId || detail.value.projectId,
          projectName:
            row.projectName || detail.value.projectName || detail.value.merchantName || '',
          venderNo: row.venderNo || '',
        };
      })
      .catch(() => {
        resetProjectVendorMapForm();
      })
      .finally(() => {
        projectVendorMapLoading.value = false;
        projectVendorMapOpen.value = true;
      });
  }

  function submitProjectVendorMap() {
    proxy.$refs.projectVendorMapRef.validate((valid) => {
      if (!valid) return;
      projectVendorMapSubmitting.value = true;
      const payload = {
        projectId: projectVendorMapForm.value.projectId,
        projectName: projectVendorMapForm.value.projectName,
        venderNo: projectVendorMapForm.value.venderNo,
      };
      saveTicketLogPullProjectVendorMap(payload)
        .then(() => {
          proxy.$modal.msgSuccess('商家映射保存成功');
          projectVendorMapOpen.value = false;
          loadProjectVendorMapOptions();
        })
        .finally(() => {
          projectVendorMapSubmitting.value = false;
        });
    });
  }

  // loadAiRepoMappings 已提取到 hooks/useAiRepoMapping.js

  function loadAiAnalysisTasks(silent = false) {
    if (!currentTicketId.value) {
      return Promise.resolve([]);
    }
    if (!silent) {
      aiTaskLoading.value = true;
    }
    return listTicketAiAnalysisTasks(currentTicketId.value, aiTaskQuery.value)
      .then((response) => {
        aiTaskList.value = response.rows || [];
        aiTaskTotal.value = response.total || 0;
        return aiTaskList.value;
      })
      .finally(() => {
        if (!silent) {
          aiTaskLoading.value = false;
        }
      });
  }

  function refreshAiAnalysisData(refreshTicketList = false) {
    if (!currentTicketId.value) {
      return Promise.resolve();
    }
    aiAnalysisRefreshLoading.value = true;
    const tasks = [refreshDetail(), loadAiAnalysisTasks(true)];
    if (refreshTicketList) {
      tasks.push(getList());
    }
    return Promise.all(tasks).finally(() => {
      aiAnalysisRefreshLoading.value = false;
    });
  }

  function canRetryAiTask(row) {
    return (
      Boolean(row?.taskId) &&
      ['failed', 'canceled'].includes(String(row.status || '').toLowerCase())
    );
  }

  /**
   * 等待指定毫秒数，供 AI 任务短轮询使用。
   * @param {number} ms 等待毫秒数
   * @returns {Promise<void>} 等待完成 Promise
   */
  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  /**
   * 从接口异常对象中提取可读错误信息，避免页面显示空对象。
   * @param {unknown} error 接口异常、字符串或响应对象
   * @param {string} fallback 无法提取时的兜底文案
   * @returns {string} 可直接提示给用户的错误文案
   */
  function extractReadableError(error, fallback = '操作失败') {
    if (!error) return fallback;
    if (typeof error === 'string') return error;
    if (error instanceof Error && error.message) return error.message;
    if (typeof error === 'object') {
      const candidates = [
        error.message,
        error.msg,
        error.errorMessage,
        error.response?.data?.msg,
        error.response?.data?.message,
        error.response?.data?.detail,
        error.data?.message,
        error.data?.msg,
      ];
      for (const candidate of candidates) {
        const text = extractReadableError(candidate, '');
        if (text) return text;
      }
      try {
        const text = JSON.stringify(error);
        return text && text !== '{}' ? text : fallback;
      } catch (_error) {
        return fallback;
      }
    }
    return String(error);
  }

  /**
   * 从 AI 分析提交接口响应中提取本次提交的任务对象。
   * @param {object} response 提交接口响应
   * @returns {object | null} AI 分析任务对象，未找到时返回 null
   */
  function extractSubmittedAiTask(response) {
    const payload = response?.data || response || {};
    const result = payload.result || payload.data?.result || {};
    return result?.taskId ? result : null;
  }

  /**
   * 短轮询指定 AI 分析任务，捕获后台快速失败或成功的终态。
   * @param {number | string} taskId AI 分析任务ID
   * @param {object} options 轮询配置，包含 maxAttempts 和 intervalMs
   * @returns {Promise<object | null>} 命中终态的任务对象，超时返回 null
   */
  async function waitForAiTaskTerminal(taskId, options = {}) {
    const maxAttempts = Number(options.maxAttempts || 6);
    const intervalMs = Number(options.intervalMs || 1500);
    for (let index = 0; index < maxAttempts; index += 1) {
      if (index > 0) {
        await sleep(intervalMs);
      }
      const tasks = await loadAiAnalysisTasks(true);
      const currentTask = (tasks || []).find((item) => String(item.taskId) === String(taskId));
      const status = String(currentTask?.status || '').toLowerCase();
      if (currentTask && aiTerminalStatuses.includes(status)) {
        return currentTask;
      }
    }
    return null;
  }

  /**
   * 提示 AI 分析任务提交结果，并在后台快速失败时展示真实失败原因。
   * @param {object} response 提交或重试接口响应
   * @param {string} successMessage 提交成功提示文案
   * @returns {Promise<void>} 提示完成 Promise
   */
  async function notifyAiTaskSubmitResult(response, successMessage) {
    const submittedTask = extractSubmittedAiTask(response);
    proxy.$modal.msgSuccess(successMessage);
    if (!submittedTask?.taskId) {
      return;
    }
    const terminalTask = await waitForAiTaskTerminal(submittedTask.taskId);
    const status = String(terminalTask?.status || '').toLowerCase();
    if (status === 'failed' || status === 'canceled') {
      const message =
        terminalTask.errorMessage ||
        terminalTask.statusDesc ||
        'AI分析任务执行失败，请查看任务历史';
      proxy.$modal.msgError(message);
      selectedAiTask.value = terminalTask;
    }
  }

  /**
   * 后台短轮询 AI 分析任务终态，不阻塞提交弹窗关闭。
   * @param {object} response 提交或重试接口响应
   * @returns {void}
   */
  function watchAiTaskSubmitResult(response) {
    const submittedTask = extractSubmittedAiTask(response);
    if (!submittedTask?.taskId) {
      return;
    }
    waitForAiTaskTerminal(submittedTask.taskId)
      .then((terminalTask) => {
        const status = String(terminalTask?.status || '').toLowerCase();
        if (status === 'failed' || status === 'canceled') {
          const message =
            terminalTask.errorMessage ||
            terminalTask.statusDesc ||
            'AI分析任务执行失败，请查看任务历史';
          proxy.$modal.msgError(message);
          selectedAiTask.value = terminalTask;
        }
        if (terminalTask) {
          refreshAiAnalysisData(true);
        }
      })
      .catch(() => {
        loadAiAnalysisTasks(true);
      });
  }

  function resetAiAnalysisDialog() {
    const logPullConfig = getTicketAutomationLogPullConfig(detail.value);
    const aiDefaults = buildTicketAiPreferenceDefaults(
      detail.value,
      resolveDefaultAiPromptTemplateCodes()
    );
    aiAnalysisTaskForm.value.versionKey =
      detail.value.versionKey || detail.value.extraData?.versionKey || '';
    aiAnalysisTaskForm.value.logPullRecordId = selectedLogPullRecord.value?.id || undefined;
    aiAnalysisTaskForm.value.agentCode = aiDefaults.agentCode;
    aiAnalysisTaskForm.value.aiProviderCode = aiDefaults.aiProviderCode;
    if (!aiDefaults.hasManualAgentCode) {
      applyAiAnalysisProviderAgent(aiAnalysisTaskForm.value.aiProviderCode);
    }
    aiAnalysisTaskForm.value.forceRefresh = false;
    aiAnalysisTaskForm.value.logAnalysisMode =
      logPullConfig.logAnalysisMode || logPullConfig.log_analysis_mode || 'hybrid';
    aiAnalysisTaskForm.value.logTimeMode = 'none';
    aiAnalysisTaskForm.value.logWindowMissingStrategy =
      detail.value.latestAiAnalysis?.analysisContext?.logWindowMissingStrategy || 'agent_extract';
    aiAnalysisTaskForm.value.logBeginTime = '';
    aiAnalysisTaskForm.value.logEndTime = '';
    aiAnalysisTaskForm.value.logPointTime = '';
    aiAnalysisTaskForm.value.rangeBeforeMinutes = 5;
    aiAnalysisTaskForm.value.rangeAfterMinutes = 10;
    aiAnalysisTaskForm.value.extraInstruction =
      logPullConfig.extraInstruction || logPullConfig.extra_instruction || '';
    aiAnalysisTaskForm.value.promptTemplateCodes = aiDefaults.promptTemplateCodes;
  }

  function openAiAnalysisDialog() {
    if (!detail.value.projectId) {
      proxy.$modal.msgWarning('当前工单缺少项目，无法发起AI分析');
      return;
    }
    resetAiAnalysisDialog();
    aiAnalysisTaskForm.value.versionKey =
      detail.value.versionKey ||
      detail.value.extraData?.versionKey ||
      aiAnalysisTaskForm.value.versionKey ||
      '';
    aiAnalysisOpen.value = true;
  }

  function openAiTaskHistory() {
    aiTaskHistoryOpen.value = true;
    loadAiAnalysisTasks();
  }

  function openAiTaskDetail(row) {
    if (!row) {
      return;
    }
    selectedAiTask.value = row;
    aiTaskDetailOpen.value = true;
  }

  function submitAiAnalysis() {
    proxy.$refs.aiAnalysisRef.validate((valid) => {
      if (!valid) return;
      if (
        aiAnalysisTaskForm.value.logTimeMode === 'range' &&
        (!aiAnalysisTaskForm.value.logBeginTime || !aiAnalysisTaskForm.value.logEndTime)
      ) {
        proxy.$modal.msgWarning('请填写日志开始和结束时间');
        return;
      }
      if (
        aiAnalysisTaskForm.value.logTimeMode === 'point' &&
        !aiAnalysisTaskForm.value.logPointTime
      ) {
        proxy.$modal.msgWarning('请选择问题发生时间点');
        return;
      }
      if (
        aiAnalysisTaskForm.value.logTimeMode === 'point' &&
        Number(aiAnalysisTaskForm.value.rangeBeforeMinutes || 0) === 0 &&
        Number(aiAnalysisTaskForm.value.rangeAfterMinutes || 0) === 0
      ) {
        proxy.$modal.msgWarning('时间点前后分钟至少需要一侧大于 0');
        return;
      }
      aiAnalysisSubmitting.value = true;
      const payload = {
        versionKey: aiAnalysisTaskForm.value.versionKey || undefined,
        logPullRecordId: aiAnalysisTaskForm.value.logPullRecordId || undefined,
        agentCode: aiAnalysisTaskForm.value.agentCode || undefined,
        aiProviderCode: aiAnalysisTaskForm.value.aiProviderCode || undefined,
        forceRefresh: aiAnalysisTaskForm.value.forceRefresh,
        logAnalysisMode: aiAnalysisTaskForm.value.logAnalysisMode || 'hybrid',
        extraInstruction: aiAnalysisTaskForm.value.extraInstruction || undefined,
        promptTemplateCodes: aiAnalysisTaskForm.value.promptTemplateCodes?.length
          ? aiAnalysisTaskForm.value.promptTemplateCodes
          : undefined,
      };
      if (aiAnalysisTaskForm.value.logTimeMode !== 'none') {
        payload.logWindowMissingStrategy =
          aiAnalysisTaskForm.value.logWindowMissingStrategy || 'agent_extract';
      }
      if (aiAnalysisTaskForm.value.logTimeMode === 'range') {
        payload.logBeginTime = aiAnalysisTaskForm.value.logBeginTime;
        payload.logEndTime = aiAnalysisTaskForm.value.logEndTime;
      }
      if (aiAnalysisTaskForm.value.logTimeMode === 'point') {
        payload.logPointTime = aiAnalysisTaskForm.value.logPointTime;
        payload.rangeBeforeMinutes = aiAnalysisTaskForm.value.rangeBeforeMinutes;
        payload.rangeAfterMinutes = aiAnalysisTaskForm.value.rangeAfterMinutes;
      }
      addTicketAiAnalysis(currentTicketId.value, payload)
        .then((response) => {
          proxy.$modal.msgSuccess('AI分析任务已提交');
          aiAnalysisOpen.value = false;
          refreshAiAnalysisData(true);
          watchAiTaskSubmitResult(response);
        })
        .catch((error) => {
          proxy.$modal.msgError(extractReadableError(error, 'AI分析任务提交失败'));
        })
        .finally(() => {
          aiAnalysisSubmitting.value = false;
        });
    });
  }

  function retryAiAnalysisTask(row) {
    if (!row?.taskId) {
      return;
    }
    proxy.$modal
      .confirm(`是否确认重试 AI 分析任务 #${row.taskId}？`)
      .then(() => {
        aiAnalysisRetryLoading.value = true;
        return retryTicketAiAnalysis(currentTicketId.value, row.taskId);
      })
      .then(async (response) => {
        await notifyAiTaskSubmitResult(response, 'AI分析任务已重新提交');
        return Promise.all([loadAiAnalysisTasks(true), refreshDetail(), getList()]);
      })
      .catch((error) => {
        if (error !== 'cancel' && error !== 'close') {
          proxy.$modal.msgError(extractReadableError(error, 'AI分析任务重试失败'));
        }
      })
      .finally(() => {
        aiAnalysisRetryLoading.value = false;
      });
  }

  // openAiRepoMappingDialog / submitAiRepoMapping / deleteAiRepoMapping 已提取到 hooks/useAiRepoMapping.js

  function openDetail(row) {
    const ticketId = Number(row?.ticketId || row?.ticket_id || row);
    if (!Number.isFinite(ticketId) || ticketId <= 0) {
      proxy.$modal.msgWarning('工单ID无效，无法打开详情');
      return Promise.resolve();
    }
    currentTicketId.value = ticketId;
    detailOpen.value = true;
    detailMainTab.value = 'overview';
    historyActiveTab.value = 'timeline';
    descriptionExpanded.value = true;
    translationExpanded.value = false;
    logPullContentOpen.value = false;
    logPullSubmitOpen.value = false;
    aiTaskHistoryOpen.value = false;
    aiTaskDetailOpen.value = false;
    timeline.value = {};
    commentList.value = [];
    commentLoaded.value = false;
    ticketMessages.value = [];
    ticketSnapshots.value = [];
    similarTickets.value = [];
    rcaForm.value = {};
    logPullList.value = [];
    aiTaskList.value = [];
    aiTaskTotal.value = 0;
    selectedAiTask.value = null;
    aiRepoMappingList.value = [];
    aiRepoMappingTotal.value = 0;
    selectedLogPullRecord.value = null;
    logPullQuery.value.pageNum = 1;
    resetLogPullForm();
    resetMessageForm();
    return getTicket(ticketId).then((response) => {
      syncDetailBundle(response.data || {});
      loadDetailVersionOptions(detail.value.projectId);
      aiAnalysisTaskForm.value.mappingId =
        detail.value.latestAiAnalysis?.mappingId || aiAnalysisTaskForm.value.mappingId;
    });
  }

  function handleTranslateDescription() {
    if (!detail.value.ticketId || descriptionTranslateLoading.value) {
      return;
    }
    if (!detailOriginalDescription.value) {
      proxy.$modal.msgWarning('当前工单描述为空，无法翻译');
      return;
    }
    descriptionTranslateLoading.value = true;
    translateTicketDescription(detail.value.ticketId)
      .then((response) => {
        syncDetailBundle(response.data || detail.value);
        proxy.$modal.msgSuccess(response.msg || '翻译成功');
        getList();
      })
      .finally(() => {
        descriptionTranslateLoading.value = false;
      });
  }

  function resetDetailDialog() {
    detailMainTab.value = 'overview';
    historyActiveTab.value = 'timeline';
    descriptionExpanded.value = true;
    translationExpanded.value = false;
    detail.value = {};
    detailVersionOptions.value = [];
    timeline.value = {};
    commentList.value = [];
    commentLoaded.value = false;
    commentLoading.value = false;
    logPullContentOpen.value = false;
    logPullSubmitOpen.value = false;
    aiTaskHistoryOpen.value = false;
    aiTaskDetailOpen.value = false;
    selectedAiTask.value = null;
    aiAnalysisOpen.value = false;
    aiRepoMappingOpen.value = false;
    projectVendorMapOpen.value = false;
    stopLogPullAutoRefresh();
  }

  function switchDetailSection(section) {
    detailMainTab.value = section;
    handleDetailTabClick({ props: { name: section } });
  }

  function handleDetailTabClick(tab) {
    const tabName = tab?.props?.name || tab?.paneName || tab?.name;
    if (tabName === 'history') {
      if (!timeline.value?.statusHistory && !timeline.value?.events) {
        refreshTimeline();
      }
      return;
    }
    if (tabName === 'comments') {
      loadComments();
      return;
    }
    if (tabName === 'logPull') {
      loadLogPullList();
      return;
    }
    if (tabName === 'collab') {
      aiAnalysisTaskForm.value.mappingId =
        detail.value.latestAiAnalysis?.mappingId || aiAnalysisTaskForm.value.mappingId;
    }
  }

  function handleHistoryTabClick(tab) {
    const tabName = tab?.props?.name || tab?.paneName || tab?.name;
    if (tabName === 'timeline' || tabName === 'events' || tabName === 'rca') {
      if (!timeline.value?.statusHistory && !timeline.value?.events) {
        refreshTimeline();
      }
      return;
    }
  }

  function refreshTimeline() {
    return getTicketTimeline(currentTicketId.value).then((response) => {
      timeline.value = response.data || {};
      rcaForm.value = timeline.value.rca || rcaForm.value;
    });
  }

  function loadComments(force = false) {
    if (!currentTicketId.value || commentLoading.value || (commentLoaded.value && !force)) {
      return Promise.resolve();
    }
    commentLoading.value = true;
    return getTicketComments(currentTicketId.value)
      .then((response) => {
        commentList.value = response.data || [];
        commentLoaded.value = true;
      })
      .finally(() => {
        commentLoading.value = false;
      });
  }

  function submitComment() {
    if (!commentForm.value.content) {
      proxy.$modal.msgWarning('请填写评论内容');
      return;
    }
    addTicketComment(currentTicketId.value, commentForm.value).then(() => {
      proxy.$modal.msgSuccess('评论成功');
      commentForm.value = { content: '', isInternal: false };
      Promise.all([loadComments(true), refreshDetail()]);
    });
  }

  function resetMessageForm() {
    const aiDefaults = buildTicketAiPreferenceDefaults(
      detail.value,
      resolveDefaultAiPromptTemplateCodes()
    );
    messageForm.value = {
      role: 'user',
      messageType: 'question',
      content: '',
      runAi: true,
      versionKey: detail.value.versionKey || detail.value.extraData?.versionKey || '',
      agentCode: aiDefaults.agentCode,
      aiProviderCode: aiDefaults.aiProviderCode,
    };
    if (!aiDefaults.hasManualAgentCode) {
      applyMessageProviderAgent(messageForm.value.aiProviderCode);
    }
    messageDataText.value = '';
  }

  function parseMessageAttachments() {
    if (!messageDataText.value) {
      return undefined;
    }
    try {
      return JSON.parse(messageDataText.value);
    } catch (error) {
      proxy.$modal.msgError('消息附件必须是合法 JSON');
      return null;
    }
  }

  function submitMessage() {
    const content = String(messageForm.value.content || '').trim();
    if (!content) {
      proxy.$modal.msgWarning('请填写消息内容');
      return;
    }
    messageForm.value.versionKey =
      detail.value.versionKey ||
      detail.value.extraData?.versionKey ||
      messageForm.value.versionKey ||
      '';
    const attachments = parseMessageAttachments();
    if (attachments === null) {
      return;
    }
    addTicketMessage(currentTicketId.value, {
      ...messageForm.value,
      content,
      attachments,
    }).then((response) => {
      const payload = response.data || response || {};
      const aiResult = payload.result || {};
      if (messageForm.value.runAi && !aiResult.aiSuccess) {
        proxy.$modal.msgWarning(
          aiResult.aiMessage || payload.message || '消息已保存，但AI追问未发起'
        );
      } else {
        proxy.$modal.msgSuccess(
          payload.message || (aiResult.aiSuccess ? 'AI追问任务已提交' : '消息提交成功')
        );
      }
      resetMessageForm();
      const refreshTasks = [refreshDetail(), getList()];
      if (aiResult.aiSuccess) {
        refreshTasks.push(loadAiAnalysisTasks(true));
      }
      Promise.all(refreshTasks);
    });
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
        solution: detail.value.solution,
      },
    }).then(() => {
      proxy.$modal.msgSuccess('快照已保存');
      return Promise.all([refreshDetail()]);
    });
  }

  function generateKnowledgeFromTicket() {
    extractTicketKnowledge(currentTicketId.value).then(() => {
      proxy.$modal.msgSuccess('知识库案例已生成');
      Promise.all([refreshDetail(), getList()]);
    });
  }

  function submitEvent() {
    let eventData;
    if (eventDataText.value) {
      try {
        eventData = JSON.parse(eventDataText.value);
      } catch (error) {
        proxy.$modal.msgError('结构化数据必须是合法 JSON');
        return;
      }
    }
    addTicketEvent(currentTicketId.value, { ...eventForm.value, eventData }).then(() => {
      proxy.$modal.msgSuccess('事件记录成功');
      eventForm.value = { eventType: 'ANALYSIS', content: '' };
      eventDataText.value = '';
      Promise.all([refreshTimeline(), refreshDetail()]);
    });
  }

  function submitRca() {
    saveTicketRca(currentTicketId.value, rcaForm.value).then(() => {
      proxy.$modal.msgSuccess('RCA保存成功');
      Promise.all([refreshTimeline(), refreshDetail()]);
    });
  }

  /**
   * 读取日志拉取记录的外部原始压缩包下载地址。
   * @param {object} row 日志拉取记录行数据
   * @returns {string} 可用于打开或复制的原始压缩包地址
   */

  /**
   * 复制文本到系统剪贴板，优先使用 Clipboard API，不支持时回退到临时输入框。
   * @param {string} text 需要复制的文本
   * @returns {Promise<boolean>} 是否复制成功
   */

  /**
   * 复制工单详情页日志拉取记录的原始压缩包地址，方便粘贴到邮件或 IM。
   * @param {object} row 日志拉取记录行数据
   * @returns {Promise<void>}
   */

  // 过滤掉项目变更后已经不在模块候选范围内的模块和模块 Code。
  function filterInvalidQueryValues(values, validValues) {
    const validSet = new Set((validValues || []).map((item) => String(item)));
    return normalizeQueryList(values).filter((item) => validSet.has(String(item)));
  }

  // 加载列表筛选用模块选项，多项目筛选时在前端按项目 ID 收敛候选。

  function formatJson(value) {
    return JSON.stringify(value, null, 2);
  }

  function getAiStatusTagType(value) {
    const status = String(value || '');
    if (status === 'success') return 'success';
    if (status === 'failed') return 'danger';
    if (status === 'running') return 'warning';
    if (status === 'created') return 'info';
    return 'info';
  }

  function getAiStatusLabel(value) {
    const status = String(value || '');
    if (status === 'success') return '成功';
    if (status === 'failed') return '失败';
    if (status === 'running') return '执行中';
    if (status === 'created') return '待执行';
    return status || '-';
  }

  function formatAiConfidence(value) {
    if (value === null || value === undefined || value === '') {
      return '-';
    }
    const numeric = Number(value);
    if (Number.isNaN(numeric)) {
      return String(value);
    }
    if (numeric > 0 && numeric <= 1) {
      return `${Math.round(numeric * 100)}%`;
    }
    return numeric.toFixed ? numeric.toFixed(2) : String(numeric);
  }

  function formatSeconds(seconds) {
    if (!seconds) return '-';
    const hour = Math.floor(seconds / 3600);
    const minute = Math.floor((seconds % 3600) / 60);
    const second = seconds % 60;
    return `${hour}小时${minute}分${second}秒`;
  }

  watch(detailOpen, (value) => {
    if (!value) {
      resetDetailDialog();
      if (standaloneDetailMode.value) {
        router.replace('/ticket/ticket');
      }
    }
  });

  watch(standaloneRouteTicketId, (ticketId) => {
    if (!standaloneDetailMode.value || !ticketId || ticketId === currentTicketId.value) {
      return;
    }
    openDetail({ ticketId });
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

  onBeforeUnmount(() => {
    stopLogPullAutoRefresh();
  });

  loadProjectOptions();
  loadStatClassificationOptions();
  loadProjectVendorMapOptions();
  loadAgentOptions();
  loadProviderOptions();
  loadVendorOptions();
  loadAnalysisPromptOptions();
  loadPushOptions();
  loadTicketColumnConfig();
  loadQueryModuleOptions();
  loadWorkflowConfig().finally(() => {
    if (standaloneDetailMode.value && standaloneRouteTicketId.value) {
      openDetail({ ticketId: standaloneRouteTicketId.value });
      return;
    }
    getList();
  });
</script>

<style scoped>
  .ticket-page :deep(.ticket-detail-dialog .el-dialog) {
    display: flex;
    flex-direction: column;
    height: 100vh;
    margin: 0;
  }

  .ticket-column-config {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px 16px;
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

  .similar-actions {
    display: flex;
    gap: 12px;
    margin-top: 6px;
    font-size: 12px;
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
    flex-wrap: wrap;
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
    padding: 10px;
    border: 1px solid #dcdfe6;
    border-radius: 6px;
    background: #ffffff;
  }

  .log-view-panel-header {
    align-items: center;
    justify-content: space-between;
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
    padding-bottom: 6px;
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

  .log-context-highlight {
    padding: 0 1px;
    color: #111827;
    background: #fde047;
    border-radius: 2px;
  }

  .log-content-dialog {
    max-height: 60vh;
  }
</style>
