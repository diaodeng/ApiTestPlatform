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
      <el-form-item label="项目" prop="projectId">
        <el-select v-model="queryParams.projectId" placeholder="所属项目" clearable filterable style="width: 180px">
          <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
        </el-select>
      </el-form-item>
      <el-form-item label="模块" prop="moduleId">
        <el-select v-model="queryParams.moduleId" placeholder="所属模块" clearable filterable :disabled="!queryParams.projectId" style="width: 180px">
          <el-option v-for="item in queryModuleOptions" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
        </el-select>
      </el-form-item>
      <el-form-item label="内部优先级" prop="internalPriority">
        <el-select v-model="queryParams.internalPriority" placeholder="内部优先级" clearable style="width: 140px">
          <el-option v-for="item in priorityOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
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
      <el-table-column label="日志拉取" min-width="150" align="center">
        <template #default="scope">
          <el-tag
            v-if="scope.row.latestLogPull?.status"
            :type="getLogPullStatusTagType(scope.row.latestLogPull.status)"
          >
            {{ scope.row.latestLogPull.statusDesc || getOptionLabel(logPullStatusOptions, scope.row.latestLogPull.status) }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="项目" width="160" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.projectName || scope.row.merchantName || '-' }}</template>
      </el-table-column>
      <el-table-column label="模块" prop="moduleName" width="140" show-overflow-tooltip />
      <el-table-column label="对方优先级" prop="customerPriority" width="110" align="center" />
      <el-table-column label="内部优先级" prop="internalPriority" width="110" align="center" />
      <el-table-column label="来源" prop="source" width="110">
        <template #default="scope">{{ getOptionLabel(sourceOptions, scope.row.source) }}</template>
      </el-table-column>
      <el-table-column label="当前处理人" prop="currentAssigneeName" width="130" show-overflow-tooltip />
      <el-table-column label="创建时间" prop="createTime" width="170">
        <template #default="scope">{{ parseTime(scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="330" fixed="right">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="openDetail(scope.row)" v-hasPermi="['ticket:ticket:query']">
            详情
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

    <el-dialog :title="title" v-model="open" width="980px" append-to-body>
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
              <el-select v-model="form.moduleId" placeholder="请选择模块" filterable clearable :disabled="!form.projectId">
                <el-option v-for="item in formModuleOptions" :key="item.moduleId" :label="item.moduleName" :value="item.moduleId" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="版本号" prop="versionKey">
              <el-input v-model="form.versionKey" placeholder="请输入版本号，供AI分析和追溯" />
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
            <el-form-item label="分类" prop="categoryName">
              <el-input v-model="form.categoryName" placeholder="如接口异常/数据问题" />
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
            <el-form-item label="日志后AI">
              <el-switch
                v-model="form.logPullConfig.autoAiEnabled"
                inline-prompt
                active-text="是"
                inactive-text="否"
                :disabled="!form.needLogPull"
              />
            </el-form-item>
          </el-col>
          <template v-if="form.needLogPull">
            <el-col :span="8">
              <el-form-item label="vendorId" prop="vendorId">
                <el-input-number v-model="form.logPullConfig.vendorId" :min="1" controls-position="right" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="storeId" prop="storeId">
                <el-input-number v-model="form.logPullConfig.storeId" :min="1" controls-position="right" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="posNo" prop="posNo">
                <el-input-number v-model="form.logPullConfig.posNo" :min="1" controls-position="right" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="数据类型">
                <el-select v-model="form.logPullConfig.commandDataType" placeholder="请选择">
                  <el-option
                    v-for="item in logPullDataTypeOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="modifyTime">
                <el-date-picker
                  v-model="form.logPullConfig.modifyTime"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="按日期拉取"
                  clearable
                />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="path">
                <el-input v-model="form.logPullConfig.path" placeholder="可选，按路径拉取" clearable />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="时间方式">
                <el-radio-group v-model="form.logPullConfig.timeRangeMode">
                  <el-radio value="between">开始 + 结束</el-radio>
                  <el-radio value="point">时间点 + 前后范围</el-radio>
                </el-radio-group>
              </el-form-item>
            </el-col>
            <template v-if="form.logPullConfig.timeRangeMode === 'between'">
              <el-col :span="12">
                <el-form-item label="开始时间">
                  <el-date-picker
                    v-model="form.logPullConfig.logBeginTime"
                    type="datetime"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    placeholder="必填，筛选日志开始时间"
                    clearable
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="结束时间">
                  <el-date-picker
                    v-model="form.logPullConfig.logEndTime"
                    type="datetime"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    placeholder="必填，筛选日志结束时间"
                    clearable
                  />
                </el-form-item>
              </el-col>
            </template>
            <template v-else>
              <el-col :span="12">
                <el-form-item label="时间点">
                  <el-date-picker
                    v-model="form.logPullConfig.logPointTime"
                    type="datetime"
                    value-format="YYYY-MM-DD HH:mm:ss"
                    placeholder="必填，基准时间点"
                    clearable
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="前后范围">
                  <div class="time-range-inline">
                    <span>前</span>
                    <el-input-number v-model="form.logPullConfig.rangeBeforeMinutes" :min="0" controls-position="right" />
                    <span>分钟，后</span>
                    <el-input-number v-model="form.logPullConfig.rangeAfterMinutes" :min="0" controls-position="right" />
                    <span>分钟</span>
                  </div>
                </el-form-item>
              </el-col>
            </template>
            <el-col :span="12">
              <el-form-item label="单文件上限">
                <el-input-number v-model="form.logPullConfig.fileMaxSize" :min="1" controls-position="right" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="压缩包上限">
                <el-input-number v-model="form.logPullConfig.zipMaxSize" :min="1" controls-position="right" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="保存方式">
                <el-select v-model="form.logPullConfig.storageMode" placeholder="请选择">
                  <el-option
                    v-for="item in logPullStorageModeOptions"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="自动AI Agent">
                <el-select
                  v-model="form.logPullConfig.aiAgentCode"
                  placeholder="请选择Agent"
                  filterable
                  clearable
                  :disabled="!form.logPullConfig.autoAiEnabled"
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
          </template>
        </el-row>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="submitForm">确 定</el-button>
          <el-button @click="cancel">取 消</el-button>
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
            <el-option v-for="item in ticketStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="是否问题">
          <el-select v-model="statusForm.isProblem" placeholder="请选择" clearable>
            <el-option label="真实问题" :value="true" />
            <el-option label="非问题" :value="false" />
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
        <el-descriptions :column="3" border>
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

    <el-drawer v-model="detailOpen" :title="detailTitle" size="70%" append-to-body>
      <template v-if="detail.ticketId">
        <el-descriptions :column="3" border>
          <el-descriptions-item label="编号">{{ detail.ticketNo }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusTagType(detail.status)">
              {{ getOptionLabel(ticketStatusOptions, detail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="当前处理人">{{ detail.currentAssigneeName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="所属项目">{{ detail.projectName || detail.merchantName || '-' }}</el-descriptions-item>
          <el-descriptions-item label="所属模块">{{ detail.moduleName || '-' }}</el-descriptions-item>
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
          <el-descriptions-item label="对方优先级">{{ detail.customerPriority || '-' }}</el-descriptions-item>
          <el-descriptions-item label="内部优先级">{{ detail.internalPriority || '-' }}</el-descriptions-item>
          <el-descriptions-item label="总耗时">{{ formatSeconds(detail.totalProcessSeconds) }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="3">{{ detail.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="根因" :span="3">{{ detail.rootCause || '-' }}</el-descriptions-item>
          <el-descriptions-item label="解决方案" :span="3">{{ detail.solution || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="panel-header mt16 mb16">
          <div class="panel-inline">
            <el-button-group>
              <el-button :type="detailActiveTab === 'timeline' ? 'primary' : 'default'" @click="switchDetailSection('timeline')">时间线</el-button>
              <el-button :type="detailActiveTab === 'comments' ? 'primary' : 'default'" @click="switchDetailSection('comments')">评论</el-button>
              <el-button :type="detailActiveTab === 'events' ? 'primary' : 'default'" @click="switchDetailSection('events')">排查事件</el-button>
              <el-button :type="detailActiveTab === 'logPull' ? 'primary' : 'default'" @click="switchDetailSection('logPull')">日志拉取</el-button>
              <el-button :type="detailActiveTab === 'rca' ? 'primary' : 'default'" @click="switchDetailSection('rca')">RCA</el-button>
              <el-button :type="detailActiveTab === 'ai' ? 'primary' : 'default'" @click="switchDetailSection('ai')">AI分析</el-button>
            </el-button-group>
          </div>
        </div>

        <el-tabs v-model="detailActiveTab" class="detail-entry-tabs" @tab-click="handleDetailTabClick">
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
            <el-empty v-if="!timeline.comments?.length" description="暂无评论" />
            <el-card v-for="item in timeline.comments" :key="item.id" shadow="never" class="mb8">
              <div class="record-head">
                <span>{{ item.userName || '-' }}</span>
                <el-tag v-if="item.isInternal" size="small" type="warning">内部</el-tag>
                <span>{{ parseTime(item.createTime) }}</span>
              </div>
              <div>{{ item.content }}</div>
            </el-card>
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
              <el-table-column label="归档地址" prop="storagePath" min-width="220" show-overflow-tooltip />
              <el-table-column label="原始压缩包" min-width="180" show-overflow-tooltip>
                <template #default="scope">
                  <el-link v-if="scope.row.commandResultUrl" :href="scope.row.commandResultUrl" target="_blank" type="primary">
                    查看地址
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
                  <el-input-number v-model="logPullForm.vendorId" :min="1" controls-position="right" />
                </el-form-item>
                <el-form-item label="storeId" prop="storeId">
                  <el-input-number v-model="logPullForm.storeId" :min="1" controls-position="right" />
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
                <el-input v-model="rcaForm.rootCauseCategory" />
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
          <el-tab-pane label="AI分析" name="ai" lazy>
            <div class="panel-header mb16">
              <div class="panel-inline">
                <span>AI分析任务</span>
                <el-tag v-if="latestAiAnalysisTask?.status" :type="getAiStatusTagType(latestAiAnalysisTask.status)">
                  {{ getAiStatusLabel(latestAiAnalysisTask.status) }}
                </el-tag>
              </div>
              <div class="panel-inline">
                <el-button type="primary" @click="openAiAnalysisDialog" v-hasPermi="['ticket:ai:analysis:run']">
                  发起AI分析
                </el-button>
                <el-button @click="loadAiAnalysisTasks" :loading="aiTaskLoading" v-hasPermi="['ticket:ai:analysis:list']">
                  刷新任务
                </el-button>
                <el-button type="warning" plain @click="openAiRepoMappingDialog()" v-hasPermi="['ticket:ai:mapping:add']">
                  新增映射
                </el-button>
              </div>
            </div>
            <el-descriptions :column="3" border class="mb16">
              <el-descriptions-item label="最新执行状态">
                <el-tag v-if="latestAiAnalysisTask?.status" :type="getAiStatusTagType(latestAiAnalysisTask.status)">
                  {{ getAiStatusLabel(latestAiAnalysisTask.status) }}
                </el-tag>
                <span v-else>-</span>
              </el-descriptions-item>
              <el-descriptions-item label="最新提交时间">
                {{ parseTime(latestAiAnalysisTask?.createTime) || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="最新完成时间">
                {{ parseTime(latestAiAnalysisTask?.finishedAt || latestAiAnalysisTask?.updateTime) || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="版本标识">{{ latestAiAnalysisTask?.versionKey || '-' }}</el-descriptions-item>
              <el-descriptions-item label="仓库地址" :span="2">{{ latestAiAnalysisTask?.repoUrl || '-' }}</el-descriptions-item>
              <el-descriptions-item label="分支名称">{{ latestAiAnalysisTask?.branchName || '-' }}</el-descriptions-item>
              <el-descriptions-item label="置信度">{{ formatAiConfidence(aiAnalysisResult?.confidence) }}</el-descriptions-item>
              <el-descriptions-item label="根因" :span="3">{{ aiAnalysisResult?.rootCause || '-' }}</el-descriptions-item>
              <el-descriptions-item label="分析摘要" :span="3">{{ aiAnalysisResult?.analysisSummary || '-' }}</el-descriptions-item>
              <el-descriptions-item label="修复建议" :span="3">{{ aiAnalysisResult?.fixSuggestion || '-' }}</el-descriptions-item>
            </el-descriptions>
            <el-alert
              v-if="latestAiAnalysisTask?.errorMessage"
              type="error"
              show-icon
              :title="latestAiAnalysisTask.errorMessage"
              class="mb16"
            />
            <el-card shadow="never" class="mb16">
              <template #header>
                <div class="panel-header">
                  <div class="panel-inline">
                    <span>任务历史</span>
                    <el-tag v-if="aiTaskTotal">{{ aiTaskTotal }} 条</el-tag>
                  </div>
                  <el-button link type="primary" @click="loadAiAnalysisTasks" :loading="aiTaskLoading">刷新</el-button>
                </div>
              </template>
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
                <el-table-column label="仓库地址" prop="repoUrl" min-width="220" show-overflow-tooltip />
                <el-table-column label="分支" prop="branchName" width="160" show-overflow-tooltip />
                <el-table-column label="提交人" prop="submittedByName" width="120" show-overflow-tooltip />
                <el-table-column label="完成时间" prop="finishedAt" width="170">
                  <template #default="scope">{{ parseTime(scope.row.finishedAt) }}</template>
                </el-table-column>
              </el-table>
              <pagination
                v-show="aiTaskTotal > 0"
                :total="aiTaskTotal"
                v-model:page="aiTaskQuery.pageNum"
                v-model:limit="aiTaskQuery.pageSize"
                @pagination="loadAiAnalysisTasks"
              />
            </el-card>
            <el-card shadow="never">
              <template #header>
                <div class="panel-header">
                  <div class="panel-inline">
                    <span>仓库映射</span>
                    <el-tag v-if="aiRepoMappingTotal">{{ aiRepoMappingTotal }} 条</el-tag>
                  </div>
                  <el-button link type="primary" @click="loadAiRepoMappings" :loading="aiRepoMappingLoading">刷新</el-button>
                </div>
              </template>
              <el-table v-loading="aiRepoMappingLoading" :data="aiRepoMappingList" row-key="mappingId">
                <el-table-column label="版本" prop="versionKey" width="150" show-overflow-tooltip />
                <el-table-column label="仓库地址" prop="repoUrl" min-width="220" show-overflow-tooltip />
                <el-table-column label="分支" prop="branchName" width="160" show-overflow-tooltip />
                <el-table-column label="默认" width="80" align="center">
                  <template #default="scope">
                    <el-tag v-if="scope.row.isDefault" type="success" size="small">默认</el-tag>
                    <span v-else>-</span>
                  </template>
                </el-table-column>
                <el-table-column label="启用" width="80" align="center">
                  <template #default="scope">
                    <el-tag :type="scope.row.enabled ? 'success' : 'info'" size="small">
                      {{ scope.row.enabled ? '启用' : '停用' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="工作区" prop="workspaceRoot" min-width="180" show-overflow-tooltip />
                <el-table-column label="操作" width="180" fixed="right">
                  <template #default="scope">
                    <el-button link type="primary" @click="openAiRepoMappingDialog(scope.row)" v-hasPermi="['ticket:ai:mapping:edit']">
                      编辑
                    </el-button>
                    <el-button link type="danger" @click="deleteAiRepoMapping(scope.row)" v-hasPermi="['ticket:ai:mapping:remove']">
                      删除
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
            <el-card shadow="never" class="mt16">
              <template #header>AI结果原文</template>
              <pre class="json-block">{{ aiAnalysisResult ? formatJson(aiAnalysisResult) : '暂无AI分析结果' }}</pre>
            </el-card>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>

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
          <el-input
            v-model="aiAnalysisTaskForm.versionKey"
            placeholder="请输入版本号，系统将按工单所属项目 + 版本号自动匹配仓库映射"
          />
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
        <el-form-item label="强制刷新">
          <el-switch v-model="aiAnalysisTaskForm.forceRefresh" />
        </el-form-item>
        <el-alert
          title="分析任务会自动读取当前工单的日志和时间线，并通过 Codex Worker 写回结果。"
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
              <el-input v-model="aiRepoMappingForm.localRepoPath" placeholder="Worker节点仓库缓存路径" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作区根目录">
              <el-input v-model="aiRepoMappingForm.workspaceRoot" placeholder="留空则使用系统默认" />
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
import { all as listAllAgents } from '@/api/hrm/agent'
import {
  addTicket,
  addTicketComment,
  addTicketEvent,
  addTicketLogPull,
  addTicketAiAnalysis,
  addTicketAiRepoMapping,
  assignTicket,
  changeTicketStatus,
  delTicket,
  delTicketAiRepoMapping,
  downloadTicketImportTemplate,
  getTicket,
  getTicketLogPullContent,
  getTicketTimeline,
  importTicketExcel,
  listTicket,
  listTicketAiAnalysisTasks,
  listTicketAiRepoMappings,
  listTicketLogPulls,
  listTicketModuleOptions,
  listTicketProjectOptions,
  reextractTicketLogPull,
  redownloadTicketLogPull,
  retryTicketLogPull,
  saveTicketRca,
  searchTicketNaturalLanguage,
  updateTicketAiRepoMapping,
  updateTicket
} from '@/api/ticket/ticket'
import {
  eventTypeOptions,
  getLogPullStatusTagType,
  getOptionLabel,
  getStatusTagType,
  logPullDataTypeOptions,
  logPullStatusOptions,
  logPullStorageModeOptions,
  priorityOptions,
  severityOptions,
  sourceOptions,
  ticketStatusOptions
} from './constants'
import UserSelect from './components/UserSelect.vue'

const { proxy } = getCurrentInstance()

const loading = ref(false)
const showSearch = ref(true)
const ticketList = ref([])
const total = ref(0)
const projectOptions = ref([])
const formModuleOptions = ref([])
const queryModuleOptions = ref([])
const agentOptions = ref([])
const open = ref(false)
const assignOpen = ref(false)
const statusOpen = ref(false)
const importOpen = ref(false)
const importing = ref(false)
const detailOpen = ref(false)
const detailActiveTab = ref('timeline')
const title = ref('')
const currentTicketId = ref()
const currentAssigneeOption = ref(null)
const detail = ref({})
const timeline = ref({})
const tagText = ref('')
const eventDataText = ref('')
const naturalKeyword = ref('')
const importResult = ref(null)
const logPullLoading = ref(false)
const logPullSubmitting = ref(false)
const logPullActionLoading = ref(false)
const logPullSubmitOpen = ref(false)
const logPullContentLoading = ref(false)
const logPullContentOpen = ref(false)
const logPullList = ref([])
const logPullTotal = ref(0)
const aiAnalysisLoading = ref(false)
const aiAnalysisSubmitting = ref(false)
const aiAnalysisOpen = ref(false)
const aiRepoMappingOpen = ref(false)
const aiRepoMappingLoading = ref(false)
const aiRepoMappingSubmitting = ref(false)
const aiTaskLoading = ref(false)
const aiTaskList = ref([])
const aiTaskTotal = ref(0)
const aiRepoMappingList = ref([])
const aiRepoMappingTotal = ref(0)
const aiAnalysisTaskForm = ref({
  versionKey: '',
  agentCode: '',
  forceRefresh: false
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

const activeLogPullStatuses = ['created', 'submitting', 'polling', 'downloading', 'processing']

function createDefaultLogPullForm() {
  return {
    vendorId: undefined,
    storeId: undefined,
    posNo: undefined,
    commandDataType: 1,
    modifyTime: undefined,
    path: '',
    timeRangeMode: 'between',
    fileMaxSize: 500,
    zipMaxSize: 500,
    logBeginTime: undefined,
    logEndTime: undefined,
    logPointTime: undefined,
    rangeBeforeMinutes: 30,
    rangeAfterMinutes: 30,
    storageMode: undefined,
    autoAiEnabled: false,
    aiAgentCode: ''
  }
}

function createDefaultTicketForm() {
  return {
    ticketId: undefined,
    ticketNo: undefined,
    title: undefined,
    description: undefined,
    projectId: undefined,
    moduleId: undefined,
    versionKey: undefined,
    customerPriority: 'P3',
    internalPriority: 'P3',
    severity: undefined,
    source: undefined,
    categoryName: undefined,
    rootCause: undefined,
    solution: undefined,
    needLogPull: false,
    logPullConfig: createDefaultLogPullForm()
  }
}

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    status: undefined,
    projectId: undefined,
    moduleId: undefined,
    internalPriority: undefined
  },
  form: createDefaultTicketForm(),
  assignForm: {},
  statusForm: {},
  commentForm: {
    content: '',
    isInternal: false
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
  }
})

const {
  queryParams,
  form,
  assignForm,
  statusForm,
  commentForm,
  eventForm,
  rcaForm,
  logPullForm,
  logPullQuery,
  rules,
  assignRules,
  statusRules,
  logPullRules,
  aiAnalysisRules,
  aiRepoMappingRules
} = toRefs(data)

const detailTitle = computed(() => `工单详情：${detail.value.title || ''}`)
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

const latestAiAnalysisTask = computed(() => detail.value.latestAiAnalysis || null)
const aiAnalysisResult = computed(() => detail.value.aiAnalysis || latestAiAnalysisTask.value?.analysisResult || null)
const currentAiMapping = computed(() => {
  return aiRepoMappingList.value.find(
    item => item.projectId === detail.value.projectId && item.versionKey === aiAnalysisTaskForm.value.versionKey
  ) || null
})

const timelineItems = computed(() => {
  const items = []
  ;(timeline.value.statusHistory || []).forEach(item => {
    items.push({
      key: `status-${item.id}`,
      time: item.startedAt,
      title: `状态流转：${getOptionLabel(ticketStatusOptions, item.fromStatus)} -> ${getOptionLabel(ticketStatusOptions, item.toStatus)}`,
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

function getList() {
  loading.value = true
  listTicket(queryParams.value).then(response => {
    ticketList.value = response.rows || []
    total.value = response.total || 0
  }).finally(() => {
    loading.value = false
  })
}

function reset() {
  form.value = createDefaultTicketForm()
  tagText.value = ''
  proxy.resetForm('ticketRef')
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
    autoAiEnabled: Boolean(logPullConfig.autoAiEnabled ?? logPullConfig.auto_ai_enabled ?? false),
    aiAgentCode: logPullConfig.aiAgentCode || logPullConfig.ai_agent_code || ''
  }
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
  open.value = true
  title.value = '新增工单'
}

function handleUpdate(row) {
  reset()
  getTicket(row.ticketId).then(response => {
    const ticketData = response.data || {}
    form.value = {
      ...createDefaultTicketForm(),
      ...ticketData,
      logPullConfig: {
        ...createDefaultLogPullForm(),
        ...(ticketData.logPullConfig || ticketData.log_pull_config || ticketData.extraData?.ticketAutomation?.logPullConfig || ticketData.extraData?.ticket_automation?.log_pull_config || {})
      }
    }
    tagText.value = Array.isArray(form.value.tags) ? form.value.tags.join(',') : ''
    applyTicketAutomationConfig(form.value)
    loadFormModuleOptions(form.value.projectId)
    open.value = true
    title.value = '编辑工单'
  })
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
  if (config.timeRangeMode === 'between') {
    const hasAnyDirectValue = Boolean(config.logBeginTime || config.logEndTime)
    if (!hasAnyDirectValue) {
      return true
    }
    if (!config.logBeginTime || !config.logEndTime) {
      proxy.$modal.msgWarning('启用日志拉取时，开始时间和结束时间需要同时填写')
      return false
    }
    const begin = new Date(config.logBeginTime)
    const end = new Date(config.logEndTime)
    if (begin > end) {
      proxy.$modal.msgWarning('启用日志拉取时，开始时间不能晚于结束时间')
      return false
    }
  } else if (config.timeRangeMode === 'point') {
    if (!config.logPointTime) {
      proxy.$modal.msgWarning('启用日志拉取时，时间点不能为空')
      return false
    }
    const beforeMinutes = Number(config.rangeBeforeMinutes ?? 0)
    const afterMinutes = Number(config.rangeAfterMinutes ?? 0)
    if (beforeMinutes < 0 || afterMinutes < 0 || (beforeMinutes === 0 && afterMinutes === 0)) {
      proxy.$modal.msgWarning('启用日志拉取时，时间点前后范围至少需要一侧大于 0')
      return false
    }
  }
  if (config.autoAiEnabled && !String(config.aiAgentCode || '').trim()) {
    proxy.$modal.msgWarning('启用自动AI分析时，请先选择Agent')
    return false
  }
  return true
}

function submitForm() {
  proxy.$refs.ticketRef.validate(valid => {
    if (!valid) return
    if (!validateTicketAutomationConfig()) {
      return
    }
    const logPullConfig = form.value.needLogPull ? { ...form.value.logPullConfig } : undefined
    if (logPullConfig) {
      if (logPullConfig.timeRangeMode === 'between') {
        if (logPullConfig.logBeginTime || logPullConfig.logEndTime) {
          delete logPullConfig.logPointTime
          delete logPullConfig.rangeBeforeMinutes
          delete logPullConfig.rangeAfterMinutes
        } else {
          delete logPullConfig.logBeginTime
          delete logPullConfig.logEndTime
          delete logPullConfig.logPointTime
          delete logPullConfig.rangeBeforeMinutes
          delete logPullConfig.rangeAfterMinutes
        }
      } else if (logPullConfig.timeRangeMode === 'point') {
        delete logPullConfig.logBeginTime
        delete logPullConfig.logEndTime
      } else {
        delete logPullConfig.logBeginTime
        delete logPullConfig.logEndTime
        delete logPullConfig.logPointTime
        delete logPullConfig.rangeBeforeMinutes
        delete logPullConfig.rangeAfterMinutes
      }
      delete logPullConfig.timeRangeMode
    }
    const payload = {
      ...form.value,
      tags: tagText.value ? tagText.value.split(',').map(item => item.trim()).filter(Boolean) : undefined,
      needLogPull: Boolean(form.value.needLogPull),
      logPullConfig
    }
    if (payload.logPullConfig && !payload.logPullConfig.autoAiEnabled) {
      payload.logPullConfig.aiAgentCode = ''
    }
    const request = payload.ticketId ? updateTicket(payload) : addTicket(payload)
    request.then(() => {
      proxy.$modal.msgSuccess(payload.ticketId ? '修改成功' : '新增成功')
      open.value = false
      getList()
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

function openStatus(row) {
  currentTicketId.value = row.ticketId
  statusForm.value = {
    toStatus: undefined,
    comment: '',
    rootCause: row.rootCause,
    solution: row.solution,
    isProblem: row.isProblem
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
  logPullSubmitOpen.value = true
  nextTick(() => {
    resetLogPullForm()
  })
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
    detail.value = response.data || {}
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

function resetAiAnalysisDialog() {
  aiAnalysisTaskForm.value.versionKey = detail.value.versionKey || detail.value.extraData?.versionKey || ''
  aiAnalysisTaskForm.value.agentCode = detail.value.extraData?.ticketAutomation?.logPullConfig?.aiAgentCode
    || detail.value.extraData?.ticket_automation?.log_pull_config?.aiAgentCode
    || ''
  aiAnalysisTaskForm.value.forceRefresh = false
}

function openAiAnalysisDialog() {
  if (!detail.value.projectId) {
    proxy.$modal.msgWarning('当前工单缺少项目，无法发起AI分析')
    return
  }
  if (!detail.value.versionKey && !detail.value.extraData?.versionKey) {
    proxy.$modal.msgWarning('当前工单缺少版本号，请先完善版本号信息')
  }
  aiAnalysisTaskForm.value.versionKey = detail.value.versionKey || detail.value.extraData?.versionKey || aiAnalysisTaskForm.value.versionKey || ''
  aiAnalysisOpen.value = true
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
      forceRefresh: aiAnalysisTaskForm.value.forceRefresh
    }).then(() => {
      proxy.$modal.msgSuccess('AI分析任务已提交')
      aiAnalysisOpen.value = false
      Promise.all([refreshDetail(), loadAiAnalysisTasks(true), getList()])
    }).finally(() => {
      aiAnalysisSubmitting.value = false
    })
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
  detailActiveTab.value = 'timeline'
  logPullContentOpen.value = false
  logPullSubmitOpen.value = false
  timeline.value = {}
  rcaForm.value = {}
  logPullList.value = []
  aiTaskList.value = []
  aiRepoMappingList.value = []
  aiRepoMappingTotal.value = 0
  selectedLogPullRecord.value = null
  selectedLogPullContent.value = null
  logPullKeyword.value = ''
  logPullQuery.value.pageNum = 1
  resetLogPullForm()
  Promise.all([
    getTicket(row.ticketId),
    getTicketTimeline(row.ticketId)
  ]).then(([detailResponse, timelineResponse]) => {
    detail.value = detailResponse.data || {}
    timeline.value = timelineResponse.data || {}
    rcaForm.value = timeline.value.rca || {}
    aiAnalysisTaskForm.value.mappingId = detail.value.latestAiAnalysis?.mappingId || aiAnalysisTaskForm.value.mappingId
  })
}

function switchDetailSection(section) {
  detailActiveTab.value = section
  handleDetailTabClick({ props: { name: section } })
}

function handleDetailTabClick(tab) {
  const tabName = tab?.props?.name || tab?.paneName || tab?.name
  if (tabName === 'timeline' || tabName === 'comments' || tabName === 'events' || tabName === 'rca') {
    if (!timeline.value?.statusHistory && !timeline.value?.comments && !timeline.value?.events) {
      refreshTimeline()
    }
    return
  }
  if (tabName === 'logPull') {
    loadLogPullList()
    return
  }
  if (tabName === 'ai') {
    Promise.all([loadAiRepoMappings(true), loadAiAnalysisTasks()]).catch(() => {})
  }
}

function refreshTimeline() {
  return getTicketTimeline(currentTicketId.value).then(response => {
    timeline.value = response.data || {}
    rcaForm.value = timeline.value.rca || rcaForm.value
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
    refreshTimeline()
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
    refreshTimeline()
  })
}

function submitRca() {
  saveTicketRca(currentTicketId.value, rcaForm.value).then(() => {
    proxy.$modal.msgSuccess('RCA保存成功')
    refreshTimeline()
    refreshDetail()
  })
}

function submitLogPull() {
  proxy.$refs.logPullRef.validate(valid => {
    if (!valid) return
    if (!logPullForm.value.modifyTime && !logPullForm.value.path) {
      proxy.$modal.msgWarning('modifyTime 和 path 至少需要填写一个')
      return
    }
    if (logPullForm.value.timeRangeMode === 'between') {
      const hasAnyDirectValue = Boolean(logPullForm.value.logBeginTime || logPullForm.value.logEndTime)
      if (hasAnyDirectValue) {
        if (!logPullForm.value.logBeginTime || !logPullForm.value.logEndTime) {
          proxy.$modal.msgWarning('开始时间和结束时间需要同时填写')
          return
        }
        const begin = new Date(logPullForm.value.logBeginTime)
        const end = new Date(logPullForm.value.logEndTime)
        if (begin > end) {
          proxy.$modal.msgWarning('日志开始时间不能晚于结束时间')
          return
        }
      }
    } else if (logPullForm.value.timeRangeMode === 'point') {
      if (!logPullForm.value.logPointTime) {
        proxy.$modal.msgWarning('时间点必填')
        return
      }
      const beforeMinutes = Number(logPullForm.value.rangeBeforeMinutes ?? 0)
      const afterMinutes = Number(logPullForm.value.rangeAfterMinutes ?? 0)
      if (beforeMinutes < 0 || afterMinutes < 0) {
        proxy.$modal.msgWarning('时间点前后范围不能为负数')
        return
      }
      if (!beforeMinutes && !afterMinutes) {
        proxy.$modal.msgWarning('时间点前后范围至少填写一侧大于 0 的时长')
        return
      }
    }
    if (logPullForm.value.autoAiEnabled && !String(logPullForm.value.aiAgentCode || '').trim()) {
      proxy.$modal.msgWarning('启用自动AI分析时，请先选择Agent')
      return
    }
    const payload = {
      vendorId: logPullForm.value.vendorId,
      storeId: logPullForm.value.storeId,
      posNo: logPullForm.value.posNo,
      commandDataType: logPullForm.value.commandDataType,
      modifyTime: logPullForm.value.modifyTime,
      path: logPullForm.value.path,
      fileMaxSize: logPullForm.value.fileMaxSize,
      zipMaxSize: logPullForm.value.zipMaxSize,
      storageMode: logPullForm.value.storageMode
    }
    if (logPullForm.value.timeRangeMode === 'between') {
      payload.logBeginTime = logPullForm.value.logBeginTime
      payload.logEndTime = logPullForm.value.logEndTime
    } else {
      payload.logPointTime = logPullForm.value.logPointTime
      payload.rangeBeforeMinutes = Number(logPullForm.value.rangeBeforeMinutes ?? 0)
      payload.rangeAfterMinutes = Number(logPullForm.value.rangeAfterMinutes ?? 0)
    }
    payload.autoAiEnabled = Boolean(logPullForm.value.autoAiEnabled)
    payload.aiAgentCode = logPullForm.value.autoAiEnabled ? String(logPullForm.value.aiAgentCode || '').trim() : ''
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

function handleLogPullDialogClosed() {
  logPullKeyword.value = ''
  logPullWrapEnabled.value = false
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
    stopLogPullAutoRefresh()
    detailActiveTab.value = 'timeline'
    detail.value = {}
    timeline.value = {}
    logPullContentOpen.value = false
    logPullSubmitOpen.value = false
    aiAnalysisOpen.value = false
    aiRepoMappingOpen.value = false
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
    form.value.moduleId = undefined
    if (!open.value) {
      return
    }
    loadFormModuleOptions(value)
  }
)

onBeforeUnmount(() => {
  stopLogPullAutoRefresh()
})

loadProjectOptions()
loadAgentOptions()
loadQueryModuleOptions()
getList()
</script>

<style scoped>
.ticket-page :deep(.el-drawer__body) {
  padding-top: 8px;
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

.detail-entry-tabs :deep(.el-tabs__header) {
  display: none;
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
