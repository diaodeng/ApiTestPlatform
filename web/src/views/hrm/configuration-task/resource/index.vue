<template>
  <div class="app-container">
    <el-card shadow="never" class="mb8">
      <el-form :inline="true" :model="query" @submit.prevent>
        <el-form-item label="Agent">
          <el-select v-model="query.agentCode" clearable filterable placeholder="全部 Agent" style="width: 200px">
            <el-option v-for="item in agentOptions" :key="item.agentCode" :label="agentLabel(item)" :value="item.agentCode" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="query.status" clearable placeholder="全部状态" style="width: 140px">
            <el-option v-for="item in statusOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键字">
          <el-input v-model="query.keyword" clearable placeholder="文件名 / 备注" style="width: 200px" @keyup.enter="loadResources" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" icon="Search" @click="loadResources">查询</el-button>
          <el-button icon="Refresh" @click="resetQuery">重置</el-button>
          <el-button v-hasPermi="['configuration_task:resource:add']" type="success" icon="Upload" @click="openUploadDialog">上传资源</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="resources" border stripe>
        <el-table-column label="资源ID" prop="resourceId" width="200" show-overflow-tooltip />
        <el-table-column label="Agent" prop="agentCode" width="150" show-overflow-tooltip />
        <el-table-column label="文件名" prop="originalFileName" min-width="180" show-overflow-tooltip />
        <el-table-column label="大小" width="110">
          <template #default="{ row }">{{ formatBytes(row.fileSize) }}</template>
        </el-table-column>
        <el-table-column label="SHA-256" width="140">
          <template #default="{ row }">
            <el-tooltip :content="row.sha256" placement="top">
              <span class="mono-text">{{ shortSha(row.sha256) }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="版本" prop="version" width="70" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" prop="createTime" width="170">
          <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" icon="View" @click="openDetail(row)">详情</el-button>
            <el-button
              v-hasPermi="['configuration_task:resource:delete']"
              link
              type="danger"
              icon="Delete"
              :disabled="row.status === 'DELETING' || row.status === 'DELETED'"
              @click="handleDelete(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 上传资源对话框：登记元数据后走 begin/chunk/commit 分片推送到 Agent 落盘 -->
    <el-dialog v-model="uploadVisible" title="上传资源到 Agent" width="520px" :close-on-click-modal="false">
      <el-form label-width="100px">
        <el-form-item label="目标 Agent" required>
          <el-select v-model="uploadForm.agentCode" filterable placeholder="选择在线 Agent" style="width: 100%">
            <el-option v-for="item in onlineAgents" :key="item.agentCode" :label="agentLabel(item)" :value="item.agentCode" />
          </el-select>
        </el-form-item>
        <el-form-item label="本地文件" required>
          <input ref="fileInputRef" type="file" style="display: none" @change="onFilePicked" />
          <el-button icon="FolderOpened" @click="triggerFilePick">{{ uploadForm.file ? uploadForm.file.name : '选择文件' }}</el-button>
          <span v-if="uploadForm.file" class="file-size">{{ formatBytes(uploadForm.file.size) }}</span>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="uploadForm.remark" type="textarea" :rows="2" maxlength="500" placeholder="可选，便于识别用途" />
        </el-form-item>
        <el-form-item v-if="uploadProgress.total > 0">
          <el-progress
            :percentage="uploadProgress.percentage"
            :status="uploadProgress.failed ? 'exception' : uploadProgress.percentage >= 100 ? 'success' : undefined"
            style="width: 100%"
          />
          <span class="upload-hint">{{ uploadProgress.hint }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!canUpload" @click="handleUpload">开始上传</el-button>
      </template>
    </el-dialog>

    <!-- 资源详情对话框 -->
    <el-dialog v-model="detailVisible" title="资源详情" width="620px">
      <el-descriptions v-if="detailRow" :column="1" border>
        <el-descriptions-item label="资源ID">{{ detailRow.resourceId }}</el-descriptions-item>
        <el-descriptions-item label="Agent">{{ detailRow.agentCode }}</el-descriptions-item>
        <el-descriptions-item label="文件名">{{ detailRow.originalFileName }}</el-descriptions-item>
        <el-descriptions-item label="大小">{{ formatBytes(detailRow.fileSize) }}（{{ detailRow.fileSize }} 字节）</el-descriptions-item>
        <el-descriptions-item label="SHA-256"><span class="mono-text">{{ detailRow.sha256 }}</span></el-descriptions-item>
        <el-descriptions-item label="MIME">{{ detailRow.mimeType }}</el-descriptions-item>
        <el-descriptions-item label="存储键">{{ detailRow.objectKey }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ detailRow.version }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag :type="statusTagType(detailRow.status)">{{ detailRow.status }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="创建人 / 时间">{{ detailRow.createBy }} / {{ formatTime(detailRow.createTime) }}</el-descriptions-item>
        <el-descriptions-item v-if="detailRow.errorMessage" label="最近错误">{{ detailRow.errorMessage }}</el-descriptions-item>
        <el-descriptions-item v-if="detailRow.remark" label="备注">{{ detailRow.remark }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup name="ConfigurationTaskResource">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  addResource,
  beginResourceTransfer,
  commitResourceTransfer,
  deleteResource,
  getResource,
  listResources,
  sendResourceTransferChunk
} from '@/api/hrm/configuration_task'
import { listAgentsForRecording } from '../composables/recordingOptions'
import { bytesToBase64, formatBytes, guessMimeType, sha256Hex } from '@/utils/fileDigest'

// 分片大小必须与服务端/Agent 协议限制一致（单块 512KiB，单文件 100MiB）
const CHUNK_SIZE = 512 * 1024
const MAX_FILE_SIZE = 100 * 1024 * 1024

const loading = ref(false)
const resources = ref([])
const agentOptions = ref([])
const statusOptions = ['PENDING', 'UPLOADING', 'READY', 'FAILED', 'EXPIRED', 'DELETING', 'DELETED']
const query = reactive({ agentCode: '', status: '', keyword: '' })

const uploadVisible = ref(false)
const uploading = ref(false)
const fileInputRef = ref(null)
const uploadForm = reactive({ agentCode: '', file: null, remark: '' })
const uploadProgress = reactive({ total: 0, done: 0, percentage: 0, hint: '', failed: false })

const detailVisible = ref(false)
const detailRow = ref(null)

const onlineAgents = computed(() => agentOptions.value.filter((item) => Number(item.status) === 2))
const canUpload = computed(() => Boolean(uploadForm.agentCode && uploadForm.file && !uploading.value))

function agentLabel(item) {
  const online = Number(item.status) === 2
  return `${item.agentCode}${online ? '' : '（离线）'}`
}

function shortSha(value) {
  const text = String(value || '')
  return text.length > 16 ? `${text.slice(0, 8)}…${text.slice(-8)}` : text
}

function statusTagType(status) {
  if (status === 'READY') return 'success'
  if (status === 'FAILED' || status === 'EXPIRED' || status === 'DELETED') return 'danger'
  if (status === 'UPLOADING' || status === 'DELETING') return 'warning'
  return 'info'
}

function formatTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 19)
}

async function loadAgents() {
  try {
    agentOptions.value = await listAgentsForRecording()
  } catch (error) {
    agentOptions.value = []
  }
}

async function loadResources() {
  loading.value = true
  try {
    const params = { limit: 200 }
    if (query.agentCode) params.agentCode = query.agentCode
    if (query.status) params.status = query.status
    if (query.keyword) params.keyword = query.keyword
    const response = await listResources(params)
    resources.value = Array.isArray(response.data) ? response.data : []
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.agentCode = ''
  query.status = ''
  query.keyword = ''
  loadResources()
}

function openUploadDialog() {
  uploadForm.agentCode = ''
  uploadForm.file = null
  uploadForm.remark = ''
  uploadProgress.total = 0
  uploadProgress.done = 0
  uploadProgress.percentage = 0
  uploadProgress.hint = ''
  uploadProgress.failed = false
  uploadVisible.value = true
}

function triggerFilePick() {
  if (!uploading.value && fileInputRef.value) {
    fileInputRef.value.value = ''
    fileInputRef.value.click()
  }
}

function onFilePicked(event) {
  const file = event.target.files && event.target.files[0]
  if (!file) return
  if (file.size > MAX_FILE_SIZE) {
    ElMessage.error('文件超过 100MiB 协议上限')
    return
  }
  uploadForm.file = file
}

async function handleUpload() {
  const file = uploadForm.file
  const agentCode = uploadForm.agentCode
  if (!file || !agentCode) return
  uploading.value = true
  uploadProgress.failed = false
  uploadProgress.total = file.size
  uploadProgress.done = 0
  uploadProgress.percentage = 0
  uploadProgress.hint = '正在计算 SHA-256…'
  try {
    // 1. 登记元数据（服务端生成 resourceId，objectKey 用摘要前缀保证幂等与可识别）
    const sha256 = await sha256Hex(await file.arrayBuffer())
    const objectKey = `manual/${sha256.slice(0, 16)}/${file.name}`
    const createResponse = await addResource({
      providerType: 'agent_local',
      providerExecutionSide: 'agent',
      agentCode,
      objectKey,
      originalFileName: file.name,
      mimeType: guessMimeType(file.name),
      fileSize: file.size,
      sha256,
      remark: uploadForm.remark
    })
    const resourceId = createResponse.data && createResponse.data.resourceId
    if (!resourceId) throw new Error('资源登记失败：未返回资源ID')

    // 2. 开始传输，拿到传输标识
    uploadProgress.hint = '正在通知 Agent 接收…'
    const beginResponse = await beginResourceTransfer(resourceId, {})
    const transferId = beginResponse.data && beginResponse.data.transferId
    if (!transferId) throw new Error('传输开始失败：未返回传输ID')

    // 3. 按 offset 分片推送，逐块校验 SHA-256
    let index = 0
    for (let offset = 0; offset < file.size; offset += CHUNK_SIZE) {
      const slice = file.slice(offset, offset + CHUNK_SIZE)
      const bytes = new Uint8Array(await slice.arrayBuffer())
      const chunkSha256 = await sha256Hex(bytes)
      const data = bytesToBase64(bytes)
      await sendResourceTransferChunk(resourceId, transferId, {
        index,
        offset,
        totalBytes: file.size,
        chunkBytes: bytes.length,
        chunkSha256,
        data
      })
      index += 1
      uploadProgress.done = offset + bytes.length
      uploadProgress.percentage = Math.floor((uploadProgress.done / file.size) * 100)
      uploadProgress.hint = `已传输 ${formatBytes(uploadProgress.done)} / ${formatBytes(file.size)}`
    }

    // 4. 提交传输，Agent 校验完整大小与摘要后原子落盘为 READY
    uploadProgress.hint = '正在提交校验…'
    await commitResourceTransfer(resourceId, transferId, {})
    uploadProgress.percentage = 100
    uploadProgress.hint = '上传完成，资源已就绪'
    ElMessage.success('资源上传完成')
    uploadVisible.value = false
    loadResources()
  } catch (error) {
    uploadProgress.failed = true
    uploadProgress.hint = error && error.message ? error.message : '上传失败'
    ElMessage.error(uploadProgress.hint)
  } finally {
    uploading.value = false
  }
}

function openDetail(row) {
  getResource(row.resourceId)
    .then((response) => {
      detailRow.value = response.data || row
      detailVisible.value = true
    })
    .catch(() => {
      detailRow.value = row
      detailVisible.value = true
    })
}

async function handleDelete(row) {
  const confirmed = await ElMessageBox.confirm(
    `确认删除资源 ${row.originalFileName}（${row.agentCode}）？删除会通知 Agent 清理本地文件。`,
    '删除确认',
    { type: 'warning' }
  ).catch(() => false)
  if (!confirmed) return
  await deleteResource(row.resourceId, { force: false, reason: '资源管理页面手动删除' })
  ElMessage.success('删除请求已提交')
  loadResources()
}

onMounted(() => {
  loadAgents()
  loadResources()
})
</script>

<style scoped>
.mb8 {
  margin-bottom: 8px;
}
.mono-text {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
}
.file-size {
  margin-left: 8px;
  color: #909399;
}
.upload-hint {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}
</style>
