<template>
  <div class="app-container ticket-similarity-config-page" v-loading="loading">
    <section class="page-intro">
      <div class="page-intro__eyebrow">相似工单检索</div>
      <h2 class="page-intro__title">配置向量检索、Embedding 和自动刷新场景</h2>
      <p class="page-intro__desc">
        配置保存后立即影响相似工单查询；历史数据需要执行向量重建后才会进入 Qdrant 或刷新本地向量。
      </p>
    </section>

    <el-card shadow="never" class="config-card">
      <template #header>
        <div class="card-header">
          <span>检索基础配置</span>
          <el-tag :type="form.enabled ? 'success' : 'info'" effect="plain">{{
            form.enabled ? '启用' : '停用'
          }}</el-tag>
        </div>
      </template>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="启用检索">
              <el-switch v-model="form.enabled" inline-prompt active-text="开" inactive-text="关" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="检索 Provider" prop="provider">
              <el-select v-model="form.provider" style="width: 100%">
                <el-option label="本地哈希 local_hash" value="local_hash" />
                <el-option label="Qdrant" value="qdrant" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="降级 Provider" prop="fallbackProvider">
              <el-select v-model="form.fallbackProvider" style="width: 100%">
                <el-option label="本地哈希 local_hash" value="local_hash" />
                <el-option label="Qdrant" value="qdrant" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="默认召回数">
              <el-input-number v-model="form.topK" :min="1" :max="100" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="相似度阈值">
              <el-input-number
                v-model="form.threshold"
                :min="-1"
                :max="1"
                :step="0.01"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="关键词权重">
              <el-input-number
                v-model="form.keywordWeight"
                :min="0"
                :max="1"
                :step="0.05"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="向量权重">
              <el-input-number
                v-model="form.vectorWeight"
                :min="0"
                :max="1"
                :step="0.05"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="16">
            <el-form-item label="向量化字段">
              <el-select
                v-model="form.fields"
                multiple
                filterable
                collapse-tags
                style="width: 100%"
              >
                <el-option
                  v-for="item in fieldOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>Embedding 服务</span>
          <el-tag effect="plain">文本转向量</el-tag>
        </div>
      </template>
      <el-form :model="form.embedding" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="Provider">
              <el-select v-model="form.embedding.provider" style="width: 100%">
                <el-option label="本地哈希 local_hash" value="local_hash" />
                <el-option label="OpenAI兼容接口" value="openai_compatible" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="模型名称">
              <el-input v-model="form.embedding.model" placeholder="如 text-embedding-3-large" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="版本">
              <el-input v-model="form.embedding.version" placeholder="如 v1" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="向量维度">
              <el-input-number
                v-model="form.embedding.dimension"
                :min="1"
                :max="16384"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="16">
            <el-form-item label="接口地址">
              <el-input
                v-model="form.embedding.endpoint"
                placeholder="http://host:port/v1/embeddings"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="16">
            <el-form-item label="API Key">
              <el-input
                v-model="form.embedding.apiKey"
                type="password"
                show-password
                placeholder="可空"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="超时秒数">
              <el-input-number
                v-model="form.embedding.timeoutSeconds"
                :min="1"
                :max="120"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>Qdrant 向量库</span>
          <el-tag effect="plain">存储与检索向量</el-tag>
        </div>
      </template>
      <el-form :model="form.qdrant" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="服务地址">
              <el-input v-model="form.qdrant.url" placeholder="http://127.0.0.1:6333" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="Collection">
              <el-input v-model="form.qdrant.collection" placeholder="ticket_similarity" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="API Key">
              <el-input
                v-model="form.qdrant.apiKey"
                type="password"
                show-password
                placeholder="可空"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="6">
            <el-form-item label="距离算法">
              <el-select v-model="form.qdrant.distance" style="width: 100%">
                <el-option label="Cosine" value="Cosine" />
                <el-option label="Dot" value="Dot" />
                <el-option label="Euclid" value="Euclid" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="6">
            <el-form-item label="自动建库">
              <el-switch
                v-model="form.qdrant.createCollection"
                inline-prompt
                active-text="开"
                inactive-text="关"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="6">
            <el-form-item label="超时秒数">
              <el-input-number
                v-model="form.qdrant.timeoutSeconds"
                :min="1"
                :max="120"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>自动刷新场景</span>
          <el-tag type="warning" effect="plain">按业务入口控制</el-tag>
        </div>
      </template>
      <div class="trigger-grid">
        <div v-for="item in sceneOptions" :key="item.key" class="trigger-item">
          <div>
            <div class="trigger-title">{{ item.label }}</div>
            <div class="trigger-desc">{{ item.desc }}</div>
          </div>
          <el-switch
            v-model="form.sceneTriggers[item.key]"
            inline-prompt
            active-text="开"
            inactive-text="关"
          />
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="config-card mt16">
      <template #header>
        <div class="card-header">
          <span>手动重建</span>
          <el-tag type="danger" effect="plain">会请求 Embedding 与 Qdrant</el-tag>
        </div>
      </template>
      <el-form :model="rebuildForm" label-width="150px">
        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="重建范围">
              <el-select v-model="rebuildForm.scope" style="width: 100%">
                <el-option label="全部有效工单" value="all" />
                <el-option label="指定工单ID" value="ids" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="每批数量">
              <el-input-number
                v-model="rebuildForm.pageSize"
                :min="1"
                :max="500"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="后台执行">
              <el-switch
                v-model="rebuildForm.runInBackground"
                inline-prompt
                active-text="开"
                inactive-text="关"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="指定 Provider">
              <el-select v-model="rebuildForm.provider" clearable style="width: 100%">
                <el-option label="跟随配置" value="" />
                <el-option label="local_hash" value="local_hash" />
                <el-option label="qdrant" value="qdrant" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="同步 Qdrant">
              <el-select v-model="rebuildForm.includeQdrantMode" style="width: 100%">
                <el-option label="跟随配置" value="auto" />
                <el-option label="强制同步" value="true" />
                <el-option label="不同步" value="false" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="rebuildForm.scope === 'ids'" :xs="24" :md="24">
            <el-form-item label="工单ID">
              <el-input
                v-model="rebuildForm.ticketIdsText"
                type="textarea"
                :rows="3"
                placeholder="多个ID用逗号、空格或换行分隔"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <el-alert v-if="rebuildResult" class="mb16" type="success" show-icon :closable="false">
        <template #title>
          重建结果：总数 {{ rebuildResult.total || 0 }}，成功
          {{ rebuildResult.processed || 0 }}，失败 {{ rebuildResult.failed || 0 }}
        </template>
      </el-alert>
      <el-space wrap>
        <el-button
          type="primary"
          :loading="saving"
          @click="handleSave"
          v-hasPermi="['ticket:similarity:config:edit']"
          >保存配置</el-button
        >
        <el-button @click="loadConfig">刷新配置</el-button>
        <el-button
          type="success"
          :loading="rebuilding"
          @click="handleRebuild"
          v-hasPermi="['ticket:similarity:rebuild']"
        >
          开始重建
        </el-button>
      </el-space>
    </el-card>
  </div>
</template>

<script setup name="TicketSimilarityConfig">
  import {
    getTicketSimilarityConfig,
    rebuildTicketSimilarity,
    saveTicketSimilarityConfig,
  } from '@/api/ticket/ticket';

  const { proxy } = getCurrentInstance();

  const loading = ref(false);
  const saving = ref(false);
  const rebuilding = ref(false);
  const rebuildResult = ref(null);
  const formRef = ref(null);

  const fieldOptions = [
    { value: 'ticketNo', label: '工单号' },
    { value: 'title', label: '标题' },
    { value: 'description', label: '描述' },
    { value: 'originDescription', label: '原始描述' },
    { value: 'aiSummary', label: 'AI摘要' },
    { value: 'rootCause', label: '最终根因' },
    { value: 'solution', label: '解决方案' },
    { value: 'rca', label: 'RCA结构化内容' },
    { value: 'moduleName', label: '模块' },
    { value: 'categoryName', label: '分类' },
    { value: 'issueTypeName', label: '工单类型' },
    { value: 'status', label: '状态' },
    { value: 'assignee', label: '当前处理人' },
    { value: 'tags', label: '标签' },
  ];

  const sceneOptions = [
    {
      key: 'externalSync',
      label: '外部同步入库',
      desc: '外部系统 POST /ticket/sync/external 后刷新向量',
    },
    { key: 'remotePull', label: '远端拉取入库', desc: '内网从公网拉取并落库后刷新向量' },
    { key: 'manualCreate', label: '手动新增', desc: '工单列表手动新增成功后刷新向量' },
    { key: 'manualUpdate', label: '手动编辑', desc: '工单列表手动编辑保存后刷新向量' },
    { key: 'import', label: 'Excel导入', desc: '导入工单成功后批量刷新向量' },
    { key: 'closeKnowledge', label: '知识沉淀', desc: '关闭工单生成知识库案例后刷新向量' },
  ];

  const rules = {
    provider: [{ required: true, message: '请选择检索 Provider', trigger: 'change' }],
    fallbackProvider: [{ required: true, message: '请选择降级 Provider', trigger: 'change' }],
  };

  function createDefaultForm() {
    return {
      enabled: true,
      provider: 'local_hash',
      fallbackProvider: 'local_hash',
      topK: 20,
      threshold: 0.05,
      keywordWeight: 0.15,
      vectorWeight: 0.85,
      fields: [
        'ticketNo',
        'title',
        'description',
        'aiSummary',
        'rootCause',
        'solution',
        'rca',
        'moduleName',
        'categoryName',
        'tags',
      ],
      embedding: {
        provider: 'local_hash',
        model: 'local-hash',
        version: 'v1',
        dimension: 128,
        endpoint: '',
        apiKey: '',
        timeoutSeconds: 15,
      },
      qdrant: {
        url: 'http://127.0.0.1:6333',
        apiKey: '',
        collection: 'ticket_similarity',
        distance: 'Cosine',
        timeoutSeconds: 15,
        createCollection: true,
      },
      sceneTriggers: {
        externalSync: true,
        remotePull: true,
        manualCreate: true,
        manualUpdate: true,
        import: true,
        closeKnowledge: true,
      },
    };
  }

  const form = reactive(createDefaultForm());
  const rebuildForm = reactive({
    scope: 'all',
    pageSize: 100,
    provider: '',
    includeQdrantMode: 'auto',
    runInBackground: true,
    ticketIdsText: '',
  });

  function assignConfig(config = {}) {
    const defaults = createDefaultForm();
    Object.assign(form, {
      ...defaults,
      ...config,
      fields:
        Array.isArray(config.fields) && config.fields.length ? config.fields : defaults.fields,
      embedding: { ...defaults.embedding, ...(config.embedding || {}) },
      qdrant: { ...defaults.qdrant, ...(config.qdrant || {}) },
      sceneTriggers: { ...defaults.sceneTriggers, ...(config.sceneTriggers || {}) },
    });
  }

  function buildPayload() {
    return {
      enabled: Boolean(form.enabled),
      provider: String(form.provider || 'local_hash').trim(),
      fallbackProvider: String(form.fallbackProvider || 'local_hash').trim(),
      topK: Number(form.topK || 20),
      threshold: Number(form.threshold || 0.05),
      keywordWeight: Number(form.keywordWeight || 0),
      vectorWeight: Number(form.vectorWeight || 0),
      fields: Array.isArray(form.fields) ? form.fields : [],
      embedding: {
        provider: String(form.embedding.provider || 'local_hash').trim(),
        model: String(form.embedding.model || '').trim(),
        version: String(form.embedding.version || 'v1').trim(),
        dimension: Number(form.embedding.dimension || 128),
        endpoint: String(form.embedding.endpoint || '').trim(),
        apiKey: String(form.embedding.apiKey || '').trim(),
        timeoutSeconds: Number(form.embedding.timeoutSeconds || 15),
      },
      qdrant: {
        url: String(form.qdrant.url || '').trim(),
        apiKey: String(form.qdrant.apiKey || '').trim(),
        collection: String(form.qdrant.collection || '').trim(),
        distance: String(form.qdrant.distance || 'Cosine').trim(),
        timeoutSeconds: Number(form.qdrant.timeoutSeconds || 15),
        createCollection: Boolean(form.qdrant.createCollection),
      },
      sceneTriggers: { ...form.sceneTriggers },
    };
  }

  function loadConfig() {
    loading.value = true;
    getTicketSimilarityConfig()
      .then((response) => {
        assignConfig(response.data || {});
      })
      .finally(() => {
        loading.value = false;
      });
  }

  function handleSave() {
    formRef.value?.validate((valid) => {
      if (!valid) {
        return;
      }
      saving.value = true;
      saveTicketSimilarityConfig(buildPayload())
        .then((response) => {
          assignConfig(response.data || {});
          proxy.$modal.msgSuccess('保存成功');
        })
        .finally(() => {
          saving.value = false;
        });
    });
  }

  function parseTicketIds() {
    return String(rebuildForm.ticketIdsText || '')
      .split(/[\s,，;；]+/)
      .map((item) => Number(item))
      .filter((item) => Number.isInteger(item) && item > 0);
  }

  function handleRebuild() {
    const ticketIds = rebuildForm.scope === 'ids' ? parseTicketIds() : [];
    if (rebuildForm.scope === 'ids' && !ticketIds.length) {
      proxy.$modal.msgWarning('请输入有效的工单ID');
      return;
    }
    const payload = {
      allTickets: rebuildForm.scope === 'all',
      ticketIds: ticketIds.length ? ticketIds : null,
      pageSize: Number(rebuildForm.pageSize || 100),
      provider: rebuildForm.provider || null,
      includeQdrant:
        rebuildForm.includeQdrantMode === 'auto' ? null : rebuildForm.includeQdrantMode === 'true',
      runInBackground: Boolean(rebuildForm.runInBackground),
    };
    rebuilding.value = true;
    rebuildTicketSimilarity(payload)
      .then((response) => {
        rebuildResult.value = response.data || null;
        proxy.$modal.msgSuccess(payload.runInBackground ? '重建任务已提交后台执行' : '重建完成');
      })
      .finally(() => {
        rebuilding.value = false;
      });
  }

  onMounted(() => {
    loadConfig();
  });
</script>

<style scoped>
  .ticket-similarity-config-page {
    padding-bottom: 72px;
  }

  .page-intro {
    margin-bottom: 16px;
  }

  .page-intro__eyebrow {
    color: #409eff;
    font-size: 13px;
    font-weight: 600;
  }

  .page-intro__title {
    margin: 4px 0;
    font-size: 22px;
    font-weight: 700;
  }

  .page-intro__desc {
    margin: 0;
    color: #606266;
    line-height: 1.6;
  }

  .config-card {
    display: inline-table;
    border-radius: 6px;
  }

  .mt16 {
    margin-top: 16px;
  }

  .mb16 {
    margin-bottom: 16px;
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .trigger-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 12px;
  }

  .trigger-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 72px;
    padding: 12px;
    border: 1px solid #ebeef5;
    border-radius: 6px;
    background: #fff;
  }

  .trigger-title {
    font-weight: 600;
    color: #303133;
  }

  .trigger-desc {
    margin-top: 4px;
    color: #909399;
    font-size: 12px;
    line-height: 1.4;
  }
</style>
