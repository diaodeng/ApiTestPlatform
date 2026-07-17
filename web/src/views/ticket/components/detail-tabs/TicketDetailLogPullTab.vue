<script>
  import LogPullConfigFields from '@/components/ticket/LogPullConfigFields.vue';
  import LogPullNotifyConfigFields from '@/components/ticket/LogPullNotifyConfigFields.vue';

  export default {
    name: 'TicketDetailLogPullTab',
    components: {
      LogPullConfigFields,
      LogPullNotifyConfigFields,
    },
    props: {
      ctx: {
        type: Object,
        required: true,
      },
    },
    /**
     * 暴露详情组件内部上下文，保持当前 tab 只负责自身模板展示和交互触发。
     * @param {object} props 组件属性，包含详情内部上下文。
     * @returns {object} 当前 tab 模板所需的响应式上下文。
     */
    setup(props) {
      return props.ctx;
    },
  };
</script>
<template>
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
      <el-button type="primary" @click="openLogPullSubmitDialog" v-hasPermi="['ticket:logpull:add']"
        >拉取日志</el-button
      >
      <el-button link type="primary" @click="loadLogPullList">刷新</el-button>
    </div>
  </div>
  <el-table
    v-loading="logPullLoading"
    :data="logPullList"
    row-key="id"
    class="mb16 log-pull-record-table"
    scrollbar-always-on
  >
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
    <el-table-column label="摘要/异常" prop="contentSummary" min-width="220" show-overflow-tooltip>
      <template #default="scope">
        <span>{{ scope.row.errorMessage || scope.row.contentSummary || '-' }}</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="340">
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
            :disabled="logPullActionLoading || activeLogPullStatuses.includes(scope.row.status)"
            v-hasPermi="['ticket:logpull:add']"
          >
            重新拉取
          </el-button>
          <el-button
            link
            type="success"
            @click="redownloadLogPull(scope.row)"
            :disabled="
              logPullActionLoading || (!scope.row.commandResultUrl && !scope.row.storagePath)
            "
            v-hasPermi="['ticket:logpull:add']"
          >
            重新下载
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
        :parameter-examples="parameterExamples"
        :agent-options="agentOptions"
        :provider-options="providerOptions"
        :data-type-options="logPullDataTypeOptions"
        :storage-mode-options="logPullStorageModeOptions"
      />
      <LogPullNotifyConfigFields v-model="logPullForm.notifyConfig" :push-options="pushOptions" />
      <el-form-item>
        <el-button type="primary" @click="submitLogPull" :loading="logPullSubmitting"
          >提交任务</el-button
        >
        <el-button @click="logPullSubmitOpen = false">取消</el-button>
      </el-form-item>
    </el-form>
  </el-dialog>
</template>
