<template>
  <div class="rule-editor">
    <el-form :model="ruleForm" label-width="120px">
      <!-- 基础信息 -->
      <el-card header="基础配置">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="规则名称" required>
              <el-input v-model="ruleForm.name" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="所属项目">
              <el-select v-model="ruleForm.project_id">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优先级">
              <el-input-number v-model="ruleForm.priority" :min="1" :max="100" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="请求路径" required>
              <el-input v-model="ruleForm.path" placeholder="/api/users" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="HTTP方法">
              <el-select v-model="ruleForm.method">
                <el-option value="GET" />
                <el-option value="POST" />
                <el-option value="PUT" />
                <el-option value="DELETE" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="启用规则">
              <el-switch v-model="ruleForm.is_active" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-card>

      <!-- 匹配条件 -->
      <el-card header="匹配条件">
        <div v-for="(cond, idx) in ruleForm.conditions" :key="idx" class="condition-item">
          <el-row :gutter="10">
            <el-col :span="5">
              <el-select v-model="cond.source" placeholder="参数来源">
                <el-option label="Query参数" value="query" />
                <el-option label="请求头" value="header" />
                <el-option label="请求体" value="body" />
                <el-option label="路径参数" value="path" />
              </el-select>
            </el-col>

            <el-col :span="5">
              <el-input v-model="cond.key" placeholder="参数名" />
            </el-col>

            <el-col :span="4">
              <el-select v-model="cond.operator" placeholder="操作符">
                <el-option label="等于 =" value="=" />
                <el-option label="不等于 !=" value="!=" />
                <el-option label="大于 >" value=">" />
                <el-option label="小于 <" value="<" />
                <el-option label="包含 contains" value="contains" />
                <el-option label="正则 regex" value="regex" />
                <el-option label="存在 exists" value="exists" />
              </el-select>
            </el-col>

            <el-col :span="5">
              <el-input
                v-model="cond.value"
                :disabled="cond.operator === 'exists'"
                placeholder="匹配值"
              />
            </el-col>

            <el-col :span="3">
              <el-select v-model="cond.data_type" placeholder="类型">
                <el-option label="字符串" value="str" />
                <el-option label="数字" value="number" />
                <el-option label="布尔值" value="bool" />
              </el-select>
            </el-col>

            <el-col :span="2">
              <el-button @click="removeCondition(idx)" type="danger" icon="Delete" />
            </el-col>
          </el-row>
        </div>

        <el-button @click="addCondition" type="primary" icon="Plus">添加条件</el-button>
      </el-card>

      <!-- 响应配置 -->
      <el-card header="响应配置">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="状态码">
              <el-input-number v-model="ruleForm.response.status_code" :min="100" :max="599" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="延迟(ms)">
              <el-input-number v-model="ruleForm.response.delay" :min="0" :max="10000" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="响应头">
          <div v-for="(header, idx) in ruleForm.response.headers" :key="idx" class="header-item">
            <el-input v-model="header.key" placeholder="Header名" style="width: 200px;" />
            <span style="margin: 0 10px;">:</span>
            <el-input v-model="header.value" placeholder="Header值" style="width: 300px;" />
            <el-button @click="removeHeader(idx)" type="danger" icon="Delete" />
          </div>
          <el-button @click="addHeader" type="primary" icon="Plus">添加响应头</el-button>
        </el-form-item>

        <el-form-item label="响应体模板">
          <el-alert type="info" show-icon style="margin-bottom: 10px;">
<!--            支持模板语法：{{ "{{ request.args.id }}" }} | {{ "{{ random.int(1,100) }}" }} | {{ "{{ time.iso }}" }}-->
            支持模板语法：
          </el-alert>
          <el-input
            v-model="ruleForm.response.body_template"
            type="textarea"
            :rows="10"
            placeholder="响应内容（支持JSON/XML/Text）"
          />
        </el-form-item>
      </el-card>

      <div class="form-actions">
        <el-button type="primary" @click="saveRule">保存规则</el-button>
        <el-button @click="resetForm">重置</el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup>
import { reactive } from 'vue'

// 初始表单结构
const initialForm = () => ({
  name: '',
  project_id: null,
  path: '',
  method: 'GET',
  priority: 1,
  is_active: true,
  conditions: [{
    source: 'query',
    key: '',
    operator: '=',
    value: '',
    data_type: 'str'
  }],
  response: {
    status_code: 200,
    headers: [{ key: 'Content-Type', value: 'application/json' }],
    body_template: '{\n  "id": "{{uuid}}",\n  "name": "{{request.args.name}}",\n  "status": "active"\n}',
    delay: 0
  }
})

const ruleForm = reactive(initialForm())
const projects = reactive([{id:111, name: 'test'}]) // 从API获取项目列表

// 条件操作
const addCondition = () => {
  ruleForm.conditions.push({
    source: 'query',
    key: '',
    operator: '=',
    value: '',
    data_type: 'str'
  })
}

const removeCondition = (index) => {
  ruleForm.conditions.splice(index, 1)
}

// 响应头操作
const addHeader = () => {
  ruleForm.response.headers.push({ key: '', value: '' })
}

const removeHeader = (index) => {
  ruleForm.response.headers.splice(index, 1)
}

// 保存规则
const saveRule = async () => {
  // 调用API保存规则
  console.log('保存规则:', ruleForm)
}

const resetForm = () => {
  Object.assign(ruleForm, initialForm())
}
</script>

<style scoped>
.rule-editor {
  padding: 20px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
}

.condition-item, .header-item {
  margin-bottom: 15px;
  padding: 10px;
  border: 1px solid #eee;
  border-radius: 4px;
}

.form-actions {
  margin-top: 20px;
  text-align: center;
}
</style>