/**
 * AI 仓库映射管理 composable。
 *
 * 从 index.vue 提取：
 * - aiRepoMappingOpen/List/Form/等状态
 * - 映射 CRUD 操作（新增/编辑/删除/查询）
 */
import { ref } from 'vue'
import {
  addTicketAiRepoMapping,
  delTicketAiRepoMapping,
  listTicketAiRepoMappings,
  updateTicketAiRepoMapping
} from '@/api/ticket/ticket'

export function useAiRepoMapping(detail, proxy) {
  const aiRepoMappingOpen = ref(false)
  const aiRepoMappingLoading = ref(false)
  const aiRepoMappingSubmitting = ref(false)
  const aiRepoMappingList = ref([])
  const aiRepoMappingTotal = ref(0)

  const aiRepoMappingForm = ref({
    mappingId: undefined,
    projectId: undefined,
    projectName: '',
    versionId: undefined,
    repoUrl: '',
    branchName: '',
    localRepoPath: '',
    workspaceRoot: '',
    workerCommand: '',
    isDefault: false,
    enabled: true,
    remark: ''
  })

  const aiRepoMappingRules = {
    projectId: [{ required: true, message: '请选择项目', trigger: 'change' }],
    versionId: [{ required: true, message: '请选择版本', trigger: 'change' }],
    repoUrl: [{ required: true, message: '仓库地址不能为空', trigger: 'blur' }],
    branchName: [{ required: true, message: '分支名称不能为空', trigger: 'blur' }]
  }

  /** 创建默认仓库映射表单 */
  function createDefaultAiRepoMappingForm(projectId, projectName) {
    return {
      mappingId: undefined,
      projectId,
      projectName: projectName || '',
      versionId: undefined,
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

  /** 重置仓库映射表单 */
  function resetAiRepoMappingForm() {
    aiRepoMappingForm.value = createDefaultAiRepoMappingForm(
      detail.value.projectId,
      detail.value.projectName || detail.value.merchantName || ''
    )
    if (proxy.$refs.aiRepoMappingRef) {
      proxy.resetForm('aiRepoMappingRef')
    }
  }

  /** 加载当前工单的 AI 仓库映射列表 */
  function loadAiRepoMappings(silent = false) {
    if (!detail.value.projectId) {
      aiRepoMappingList.value = []
      aiRepoMappingTotal.value = 0
      return Promise.resolve()
    }
    if (!silent) {
      aiRepoMappingLoading.value = true
    }
    const query = { pageNum: 1, pageSize: 50, projectId: detail.value.projectId }
    return listTicketAiRepoMappings(query).then(response => {
      aiRepoMappingList.value = response.rows || []
      aiRepoMappingTotal.value = response.total || 0
    }).finally(() => {
      if (!silent) {
        aiRepoMappingLoading.value = false
      }
    })
  }

  /** 打开仓库映射对话框 */
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
        versionId: row.versionId,
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

  /** 提交仓库映射（新增/编辑） */
  function submitAiRepoMapping() {
    proxy.$refs.aiRepoMappingRef.validate(valid => {
      if (!valid) return
      aiRepoMappingSubmitting.value = true
      const payload = { ...aiRepoMappingForm.value }
      const request = payload.mappingId
        ? updateTicketAiRepoMapping(payload)
        : addTicketAiRepoMapping(payload)
      request.then(() => {
        proxy.$modal.msgSuccess(payload.mappingId ? '映射更新成功' : '映射新增成功')
        aiRepoMappingOpen.value = false
        loadAiRepoMappings(true)
      }).finally(() => {
        aiRepoMappingSubmitting.value = false
      })
    })
  }

  /** 删除仓库映射 */
  function deleteAiRepoMapping(row) {
    if (!row?.mappingId) return
    proxy.$modal.confirm(`是否确认删除版本映射 "${row.versionName || row.versionKey || row.versionId}"？`).then(() => {
      aiRepoMappingLoading.value = true
      return delTicketAiRepoMapping(row.mappingId)
    }).then(() => {
      proxy.$modal.msgSuccess('删除成功')
      loadAiRepoMappings(true)
    }).catch(() => {}).finally(() => {
      aiRepoMappingLoading.value = false
    })
  }

  return {
    aiRepoMappingOpen,
    aiRepoMappingLoading,
    aiRepoMappingSubmitting,
    aiRepoMappingList,
    aiRepoMappingTotal,
    aiRepoMappingForm,
    aiRepoMappingRules,
    createDefaultAiRepoMappingForm,
    resetAiRepoMappingForm,
    loadAiRepoMappings,
    openAiRepoMappingDialog,
    submitAiRepoMapping,
    deleteAiRepoMapping
  }
}
