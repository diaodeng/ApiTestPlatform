<template>
  <div class="app-container ticket-version-page">
    <el-form :model="queryParams" :inline="true" class="mb16">
      <el-form-item label="项目">
        <el-select v-model="queryParams.projectId" clearable filterable placeholder="全部项目" style="width: 220px">
          <el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" />
        </el-select>
      </el-form-item>
      <el-form-item label="版本状态">
        <el-select v-model="queryParams.lifecycleStatus" clearable placeholder="全部状态" style="width: 140px">
          <el-option label="待确认" value="discovered" />
          <el-option label="已确认" value="confirmed" />
          <el-option label="已废弃" value="deprecated" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键字">
        <el-input v-model="queryParams.keyword" clearable placeholder="版本号或名称" style="width: 220px" @keyup.enter="handleQuery" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">查询</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
        <el-button type="primary" plain icon="Plus" v-hasPermi="['ticket:version:add']" @click="openVersionForm()">新增版本</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="versionList" border row-key="versionId">
      <el-table-column label="项目" prop="projectName" min-width="150" show-overflow-tooltip />
      <el-table-column label="版本号" prop="versionKey" min-width="140" show-overflow-tooltip />
      <el-table-column label="展示名称" prop="versionName" min-width="160" show-overflow-tooltip />
      <el-table-column label="状态" width="100" align="center">
        <template #default="scope"><el-tag :type="versionStatusType(scope.row.lifecycleStatus)">{{ versionStatusLabel(scope.row.lifecycleStatus) }}</el-tag></template>
      </el-table-column>
      <el-table-column label="来源" prop="source" width="120" />
      <el-table-column label="计划发布" prop="plannedReleaseAt" width="170" />
      <el-table-column label="默认分支" prop="defaultBranch" min-width="150" show-overflow-tooltip />
      <el-table-column label="发布记录" width="100" align="center"><template #default="scope">{{ scope.row.releaseCount || 0 }}</template></el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" v-hasPermi="['ticket:version:edit']" @click="openVersionForm(scope.row)">维护</el-button>
          <el-button link type="primary" icon="Tickets" v-hasPermi="['ticket:version:list']" @click="openReleases(scope.row)">发布记录</el-button>
        </template>
      </el-table-column>
    </el-table>
    <pagination v-show="total > 0" :total="total" v-model:page="queryParams.pageNum" v-model:limit="queryParams.pageSize" @pagination="getList" />

    <el-dialog v-model="versionOpen" :title="versionForm.versionId ? '维护项目版本' : '新增项目版本'" width="680px" append-to-body destroy-on-close>
      <el-form ref="versionFormRef" :model="versionForm" :rules="versionRules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="项目" prop="projectId"><el-select v-model="versionForm.projectId" filterable style="width: 100%" :disabled="Boolean(versionForm.versionId)" @change="syncVersionProject"><el-option v-for="item in projectOptions" :key="item.projectId" :label="item.projectName" :value="item.projectId" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="版本号" prop="versionKey"><el-input v-model="versionForm.versionKey" maxlength="100" :disabled="Boolean(versionForm.versionId)" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="展示名称"><el-input v-model="versionForm.versionName" maxlength="200" placeholder="默认使用版本号" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="版本状态"><el-select v-model="versionForm.lifecycleStatus" style="width: 100%"><el-option label="待确认" value="discovered" /><el-option label="已确认" value="confirmed" /><el-option label="已废弃" value="deprecated" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="计划发布"><el-date-picker v-model="versionForm.plannedReleaseAt" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="默认分支"><el-input v-model="versionForm.defaultBranch" maxlength="200" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="可选"><el-switch v-model="versionForm.enabled" /></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="备注"><el-input v-model="versionForm.remark" type="textarea" :rows="3" maxlength="1000" show-word-limit /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer><el-button @click="versionOpen = false">取消</el-button><el-button type="primary" :loading="savingVersion" @click="saveVersion">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="releaseOpen" :title="`${selectedVersion?.versionKey || ''} 发布记录`" width="920px" append-to-body>
      <div class="release-toolbar"><el-button type="primary" plain icon="Plus" v-hasPermi="['ticket:version:release']" @click="openReleaseForm()">登记发布</el-button></div>
      <el-table v-loading="releaseLoading" :data="releaseList" border max-height="420">
        <el-table-column label="环境" prop="environment" width="120" />
        <el-table-column label="批次" prop="batchNo" width="120" />
        <el-table-column label="状态" width="100"><template #default="scope"><el-tag :type="releaseStatusType(scope.row.releaseStatus)">{{ releaseStatusLabel(scope.row.releaseStatus) }}</el-tag></template></el-table-column>
        <el-table-column label="计划时间" prop="plannedReleaseAt" width="170" />
        <el-table-column label="发布时间" prop="releasedAt" width="170" />
        <el-table-column label="发布人" prop="releaseBy" width="110" />
        <el-table-column label="说明" prop="remark" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="80"><template #default="scope"><el-button link type="primary" v-hasPermi="['ticket:version:release']" @click="openReleaseForm(scope.row)">编辑</el-button></template></el-table-column>
      </el-table>
      <el-alert class="release-tip" type="info" :closable="false" show-icon title="登记发布仅更新版本发布事实；关联工单将在验证通过后按工单工作流关闭。" />
    </el-dialog>

    <el-dialog v-model="releaseFormOpen" :title="releaseForm.releaseId ? '编辑发布记录' : '登记发布'" width="620px" append-to-body destroy-on-close>
      <el-form ref="releaseFormRef" :model="releaseForm" :rules="releaseRules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="环境" prop="environment"><el-input v-model="releaseForm.environment" maxlength="64" placeholder="production" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="批次"><el-input v-model="releaseForm.batchNo" maxlength="64" placeholder="default" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="发布状态"><el-select v-model="releaseForm.releaseStatus" style="width: 100%"><el-option label="计划中" value="planned" /><el-option label="已发布" value="released" /><el-option label="已回滚" value="rolled_back" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="计划时间"><el-date-picker v-model="releaseForm.plannedReleaseAt" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="发布时间"><el-date-picker v-model="releaseForm.releasedAt" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="回滚时间"><el-date-picker v-model="releaseForm.rollbackAt" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" /></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="CI/CD 链接"><el-input v-model="releaseForm.ciUrl" maxlength="1000" /></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="发布说明"><el-input v-model="releaseForm.remark" type="textarea" :rows="3" maxlength="1000" show-word-limit /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer><el-button @click="releaseFormOpen = false">取消</el-button><el-button type="primary" :loading="savingRelease" @click="saveRelease">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup name="TicketVersion">
import { listTicketProjectOptions } from '@/api/ticket/ticket'
import { addTicketVersion, addTicketVersionRelease, listTicketVersionReleases, listTicketVersions, updateTicketVersion, updateTicketVersionRelease } from '@/api/ticket/version'

const { proxy } = getCurrentInstance()
const loading = ref(false)
const savingVersion = ref(false)
const savingRelease = ref(false)
const releaseLoading = ref(false)
const versionOpen = ref(false)
const releaseOpen = ref(false)
const releaseFormOpen = ref(false)
const versionList = ref([])
const releaseList = ref([])
const projectOptions = ref([])
const total = ref(0)
const selectedVersion = ref(null)
const queryParams = ref({ pageNum: 1, pageSize: 10, projectId: undefined, lifecycleStatus: undefined, keyword: '' })
const versionForm = ref(createVersionForm())
const releaseForm = ref(createReleaseForm())
const versionRules = { projectId: [{ required: true, message: '请选择项目', trigger: 'change' }], versionKey: [{ required: true, message: '请输入版本号', trigger: 'blur' }] }
const releaseRules = { environment: [{ required: true, message: '请输入环境', trigger: 'blur' }] }

function createVersionForm() { return { versionId: undefined, projectId: undefined, projectName: '', versionKey: '', versionName: '', lifecycleStatus: 'confirmed', plannedReleaseAt: undefined, defaultBranch: '', enabled: true, remark: '' } }
function createReleaseForm() { return { releaseId: undefined, versionId: selectedVersion.value?.versionId, environment: 'production', batchNo: 'default', releaseStatus: 'planned', plannedReleaseAt: undefined, releasedAt: undefined, rollbackAt: undefined, ciUrl: '', remark: '' } }
function versionStatusLabel(value) { return { discovered: '待确认', confirmed: '已确认', deprecated: '已废弃' }[value] || value || '-' }
function versionStatusType(value) { return value === 'confirmed' ? 'success' : value === 'deprecated' ? 'info' : 'warning' }
function releaseStatusLabel(value) { return { planned: '计划中', released: '已发布', rolled_back: '已回滚' }[value] || value || '-' }
function releaseStatusType(value) { return value === 'released' ? 'success' : value === 'rolled_back' ? 'danger' : 'warning' }
function loadProjects() { return listTicketProjectOptions().then(response => { projectOptions.value = response.data || [] }) }
function getList() { loading.value = true; listTicketVersions(queryParams.value).then(response => { versionList.value = response.rows || []; total.value = response.total || 0 }).finally(() => { loading.value = false }) }
function handleQuery() { queryParams.value.pageNum = 1; getList() }
function resetQuery() { queryParams.value = { pageNum: 1, pageSize: 10, projectId: undefined, lifecycleStatus: undefined, keyword: '' }; handleQuery() }
function syncVersionProject(projectId) { const project = projectOptions.value.find(item => item.projectId === projectId); versionForm.value.projectName = project?.projectName || '' }
function openVersionForm(row) { versionForm.value = row ? { ...createVersionForm(), ...row } : createVersionForm(); versionOpen.value = true }
function saveVersion() { proxy.$refs.versionFormRef.validate(valid => { if (!valid) return; savingVersion.value = true; const request = versionForm.value.versionId ? updateTicketVersion(versionForm.value) : addTicketVersion(versionForm.value); request.then(() => { proxy.$modal.msgSuccess('版本已保存'); versionOpen.value = false; getList() }).finally(() => { savingVersion.value = false }) }) }
function openReleases(row) { selectedVersion.value = row; releaseOpen.value = true; loadReleases() }
function loadReleases() { if (!selectedVersion.value?.versionId) return; releaseLoading.value = true; listTicketVersionReleases(selectedVersion.value.versionId).then(response => { releaseList.value = response.data || [] }).finally(() => { releaseLoading.value = false }) }
function openReleaseForm(row) { releaseForm.value = row ? { ...createReleaseForm(), ...row, versionId: selectedVersion.value.versionId } : createReleaseForm(); releaseFormOpen.value = true }
function saveRelease() { proxy.$refs.releaseFormRef.validate(valid => { if (!valid) return; savingRelease.value = true; const request = releaseForm.value.releaseId ? updateTicketVersionRelease(releaseForm.value) : addTicketVersionRelease(releaseForm.value); request.then(() => { proxy.$modal.msgSuccess('发布记录已保存'); releaseFormOpen.value = false; loadReleases(); getList() }).finally(() => { savingRelease.value = false }) }) }

loadProjects()
getList()
</script>

<style scoped>
.mb16 { margin-bottom: 16px; }
.release-toolbar { margin-bottom: 12px; }
.release-tip { margin-top: 12px; }
</style>
