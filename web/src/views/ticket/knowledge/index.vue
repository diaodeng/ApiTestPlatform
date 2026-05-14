<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
      <el-form-item label="关键字" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="标题/内容"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="分类" prop="category">
        <el-input
          v-model="queryParams.category"
          placeholder="文章分类"
          clearable
          style="width: 180px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['ticket:knowledge:add']">
          新增
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <el-table v-loading="loading" :data="articleList" row-key="articleId">
      <el-table-column label="文章ID" prop="articleId" width="190" />
      <el-table-column label="标题" prop="title" min-width="260" show-overflow-tooltip />
      <el-table-column label="分类" prop="category" width="140" />
      <el-table-column label="向量状态" prop="embeddingStatus" width="120" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.embeddingStatus === 'done' ? 'success' : 'info'">
            {{ scope.row.embeddingStatus || 'pending' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建人" prop="createdByName" width="130" />
      <el-table-column label="更新时间" prop="updateTime" width="170">
        <template #default="scope">{{ parseTime(scope.row.updateTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="240" fixed="right">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleDetail(scope.row)" v-hasPermi="['ticket:knowledge:query']">
            详情
          </el-button>
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['ticket:knowledge:edit']">
            编辑
          </el-button>
          <el-button
            link
            type="danger"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-hasPermi="['ticket:knowledge:remove']"
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

    <el-dialog :title="title" v-model="open" width="920px" append-to-body>
      <el-form ref="articleRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="16">
            <el-form-item label="标题" prop="title">
              <el-input v-model="form.title" placeholder="请输入文章标题" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="分类" prop="category">
              <el-input v-model="form.category" placeholder="如支付/权限/性能" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="标签">
              <el-input v-model="tagText" placeholder="逗号分隔，如超时,接口异常" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联工单">
              <el-input v-model="ticketIdsText" placeholder="逗号分隔工单ID" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="内容" prop="content">
              <el-input
                v-model="form.content"
                type="textarea"
                :rows="14"
                placeholder="建议包含：现象、影响范围、排查过程、根因、修复方案、验证方式、长期预防"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="submitForm">确 定</el-button>
        <el-button @click="cancel">取 消</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailOpen" :title="detail.title || '知识库详情'" size="60%" append-to-body>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="文章ID">{{ detail.articleId }}</el-descriptions-item>
        <el-descriptions-item label="分类">{{ detail.category || '-' }}</el-descriptions-item>
        <el-descriptions-item label="标签" :span="2">{{ formatArray(detail.tags) }}</el-descriptions-item>
        <el-descriptions-item label="关联工单" :span="2">{{ formatArray(detail.relatedTicketIds) }}</el-descriptions-item>
        <el-descriptions-item label="向量状态">{{ detail.embeddingStatus || 'pending' }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ parseTime(detail.updateTime) }}</el-descriptions-item>
      </el-descriptions>
      <el-card shadow="never" class="content-card">
        <pre class="article-content">{{ detail.content || '-' }}</pre>
      </el-card>
    </el-drawer>
  </div>
</template>

<script setup name="TicketKnowledge">
import {
  addKnowledge,
  delKnowledge,
  getKnowledge,
  listKnowledge,
  updateKnowledge
} from '@/api/ticket/ticket'

const { proxy } = getCurrentInstance()

const loading = ref(false)
const showSearch = ref(true)
const articleList = ref([])
const total = ref(0)
const open = ref(false)
const detailOpen = ref(false)
const title = ref('')
const tagText = ref('')
const ticketIdsText = ref('')
const detail = ref({})

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    category: undefined
  },
  form: {},
  rules: {
    title: [{ required: true, message: '文章标题不能为空', trigger: 'blur' }],
    content: [{ required: true, message: '文章内容不能为空', trigger: 'blur' }]
  }
})

const { queryParams, form, rules } = toRefs(data)

function getList() {
  loading.value = true
  listKnowledge(queryParams.value).then(response => {
    articleList.value = response.rows || []
    total.value = response.total || 0
  }).finally(() => {
    loading.value = false
  })
}

function reset() {
  form.value = {
    articleId: undefined,
    title: undefined,
    content: undefined,
    category: undefined,
    embeddingStatus: 'pending'
  }
  tagText.value = ''
  ticketIdsText.value = ''
  proxy.resetForm('articleRef')
}

function handleQuery() {
  queryParams.value.pageNum = 1
  getList()
}

function resetQuery() {
  proxy.resetForm('queryRef')
  handleQuery()
}

function handleAdd() {
  reset()
  title.value = '新增知识库文章'
  open.value = true
}

function handleUpdate(row) {
  reset()
  getKnowledge(row.articleId).then(response => {
    form.value = response.data || {}
    tagText.value = Array.isArray(form.value.tags) ? form.value.tags.join(',') : ''
    ticketIdsText.value = Array.isArray(form.value.relatedTicketIds) ? form.value.relatedTicketIds.join(',') : ''
    title.value = '编辑知识库文章'
    open.value = true
  })
}

function handleDetail(row) {
  getKnowledge(row.articleId).then(response => {
    detail.value = response.data || {}
    detailOpen.value = true
  })
}

function submitForm() {
  proxy.$refs.articleRef.validate(valid => {
    if (!valid) return
    const payload = {
      ...form.value,
      tags: splitText(tagText.value),
      relatedTicketIds: splitText(ticketIdsText.value).map(item => Number(item)).filter(Boolean)
    }
    const request = payload.articleId ? updateKnowledge(payload) : addKnowledge(payload)
    request.then(() => {
      proxy.$modal.msgSuccess(payload.articleId ? '修改成功' : '新增成功')
      open.value = false
      getList()
    })
  })
}

function handleDelete(row) {
  proxy.$modal.confirm(`是否确认删除知识库文章 "${row.title}"？`).then(() => delKnowledge(row.articleId)).then(() => {
    proxy.$modal.msgSuccess('删除成功')
    getList()
  }).catch(() => {})
}

function cancel() {
  open.value = false
  reset()
}

function splitText(value) {
  return value ? value.split(',').map(item => item.trim()).filter(Boolean) : []
}

function formatArray(value) {
  return Array.isArray(value) ? value.join(', ') : '-'
}

getList()
</script>

<style scoped>
.mb8 {
  margin-bottom: 8px;
}

.content-card {
  margin-top: 16px;
}

.article-content {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.7;
  font-family: inherit;
}
</style>
