<template>
  <el-card class="condition-editor" shadow="never">
    <template #header>
      <span>{{ title }}</span>
      <slot name="header-extra"></slot>
      <el-button
        v-if="editable"
        class="add-btn"
        type="primary"
        icon="Plus"
        @click="addCondition"
      >{{ addButtonText }}</el-button>
    </template>

    <div v-if="conditionList.length === 0" class="empty-text">{{ emptyText }}</div>

    <div v-for="(cond, idx) in conditionList" :key="idx" class="condition-item">
      <el-row :gutter="10">
        <el-col :span="5">
          <el-select v-model="cond.source" :disabled="!editable" placeholder="参数来源">
            <el-option label="Query参数" value="query" />
            <el-option label="请求头" value="header" />
            <el-option label="请求体" value="body" />
            <el-option label="路径参数" value="path" />
          </el-select>
        </el-col>

        <el-col :span="5">
          <el-input v-model="cond.key" :disabled="!editable" placeholder="参数名" />
        </el-col>

        <el-col :span="4">
          <el-select v-model="cond.operator" :disabled="!editable" placeholder="操作符">
            <el-option label="等于 =" value="=" />
            <el-option label="不等于 !=" value="!=" />
            <el-option label="大于 >" value=">" />
            <el-option label="小于 <" value="<" />
            <el-option label="包含 contains" value="contains" />
            <el-option label="正则 regex" value="regex" />
            <el-option label="正则 regex_search" value="regex_search" />
            <el-option label="存在 exists" value="exists" />
          </el-select>
        </el-col>

        <el-col :span="5">
          <el-input
            v-model="cond.value"
            :disabled="!editable || cond.operator === 'exists'"
            placeholder="匹配值"
          />
        </el-col>

        <el-col :span="3">
          <el-select v-model="cond.data_type" :disabled="!editable" placeholder="类型">
            <el-option label="字符串" value="str" />
            <el-option label="数字" value="number" />
            <el-option label="布尔值" value="bool" />
          </el-select>
        </el-col>

        <el-col :span="2">
          <el-button
            v-if="editable"
            type="danger"
            icon="Delete"
            @click="removeCondition(idx)"
          />
        </el-col>
      </el-row>
    </div>
  </el-card>
</template>

<script setup>
  import { computed, watchEffect } from 'vue';

  const conditionList = defineModel({ type: Array, default: () => [] });

  const props = defineProps({
    title: { type: String, default: '条件配置' },
    addButtonText: { type: String, default: '添加条件' },
    editable: { type: Boolean, default: true },
    emptyText: { type: String, default: '暂无条件' },
  });

  const editable = computed(() => props.editable);

  function createCondition() {
    return {
      source: 'query',
      key: '',
      operator: '=',
      value: '',
      data_type: 'str',
    };
  }

  function addCondition() {
    if (!Array.isArray(conditionList.value)) {
      conditionList.value = [];
    }
    conditionList.value.push(createCondition());
  }

  function removeCondition(index) {
    if (!Array.isArray(conditionList.value)) {
      conditionList.value = [];
      return;
    }
    conditionList.value.splice(index, 1);
  }

  watchEffect(() => {
    if (!Array.isArray(conditionList.value)) {
      conditionList.value = [];
    }
  });
</script>

<style scoped>
  .condition-editor :deep(.el-card__header) {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .add-btn {
    margin-left: auto;
  }

  .empty-text {
    color: #909399;
    padding: 6px 2px;
  }

  .condition-item {
    margin-bottom: 12px;
    padding: 10px;
    border: 1px solid #ebeef5;
    border-radius: 4px;
  }
</style>
