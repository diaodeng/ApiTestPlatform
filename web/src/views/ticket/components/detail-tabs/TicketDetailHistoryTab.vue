<script>
  export default {
    name: 'TicketDetailHistoryTab',
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
  <el-tabs v-model="historyActiveTab" class="history-entry-tabs" @tab-click="handleHistoryTabClick">
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
          <el-button type="primary" @click="submitEvent" v-hasPermi="['ticket:event:add']"
            >提交事件</el-button
          >
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
  </el-tabs>
</template>
