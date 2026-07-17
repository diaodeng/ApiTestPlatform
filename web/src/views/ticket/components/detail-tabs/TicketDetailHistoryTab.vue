<script setup name="TicketDetailHistoryTab">
  import { computed, ref, watch } from 'vue';
  import { getCurrentInstance } from 'vue';
  import { addTicketEvent, getTicketTimeline, saveTicketRca } from '@/api/ticket/ticket';
  import { eventTypeOptions, getOptionLabel } from '../../constants';
  import { useOptions } from '../../hooks/useOptions';
  import { useWorkflow } from '../../hooks/useWorkflow';

  const props = defineProps({
    ticketId: {
      type: [Number, String],
      required: true,
    },
    active: {
      type: Boolean,
      default: false,
    },
  });

  const emit = defineEmits(['changed']);
  const { proxy } = getCurrentInstance();
  const currentTicketStatus = ref('');
  const { rootCauseTypeOptions, loadStatClassificationOptions } = useOptions();
  const { ticketStatusOptions, loadWorkflowConfig } = useWorkflow(currentTicketStatus);

  const historyActiveTab = ref('timeline');
  const timeline = ref({});
  const eventDataText = ref('');
  const eventForm = ref({
    eventType: 'ANALYSIS',
    content: '',
  });
  const rcaForm = ref({});

  const timelineItems = computed(() => {
    const items = [];
    (timeline.value.statusHistory || []).forEach((item) => {
      items.push({
        key: `status-${item.id}`,
        time: item.startedAt,
        title: `状态流转：${getOptionLabel(ticketStatusOptions.value, item.fromStatus)} -> ${getOptionLabel(ticketStatusOptions.value, item.toStatus)}`,
        content: item.comment,
      });
    });
    (timeline.value.assignHistory || []).forEach((item) => {
      items.push({
        key: `assign-${item.id}`,
        time: item.assignedAt,
        title: `指派：${item.fromUserName || '未指派'} -> ${item.toUserName || '-'}`,
        content: item.reason,
      });
    });
    (timeline.value.events || []).forEach((item) => {
      items.push({
        key: `event-${item.id}`,
        time: item.createTime,
        title: `事件：${item.eventType}`,
        content: item.content,
      });
    });
    return items.sort((a, b) => new Date(a.time || 0) - new Date(b.time || 0));
  });

  /**
   * 格式化 JSON 展示内容。
   * @param {unknown} value 待格式化对象。
   * @returns {string} 缩进后的 JSON 字符串。
   */
  function formatJson(value) {
    return JSON.stringify(value, null, 2);
  }

  /**
   * 拉取当前工单时间线、排查事件和 RCA。
   * @returns {Promise<void>} 时间线加载完成 Promise。
   */
  function refreshTimeline() {
    if (!props.ticketId) return Promise.resolve();
    return getTicketTimeline(props.ticketId).then((response) => {
      timeline.value = response.data || {};
      rcaForm.value = timeline.value.rca || rcaForm.value || {};
    });
  }

  /**
   * 切换历史子页时按需加载时间线数据。
   * @param {object} tab Element Plus tab 对象。
   * @returns {void}
   */
  function handleHistoryTabClick(tab) {
    const tabName = tab?.props?.name || tab?.paneName || tab?.name;
    if (tabName === 'timeline' || tabName === 'events' || tabName === 'rca') {
      if (!timeline.value?.statusHistory && !timeline.value?.events) {
        refreshTimeline();
      }
    }
  }

  /**
   * 提交排查事件并刷新时间线。
   * @returns {void}
   */
  function submitEvent() {
    let eventData;
    if (eventDataText.value) {
      try {
        eventData = JSON.parse(eventDataText.value);
      } catch (error) {
        proxy.$modal.msgError('结构化数据必须是合法 JSON');
        return;
      }
    }
    addTicketEvent(props.ticketId, { ...eventForm.value, eventData }).then(() => {
      proxy.$modal.msgSuccess('事件记录成功');
      eventForm.value = { eventType: 'ANALYSIS', content: '' };
      eventDataText.value = '';
      refreshTimeline();
      emit('changed');
    });
  }

  /**
   * 保存 RCA 并刷新时间线。
   * @returns {void}
   */
  function submitRca() {
    saveTicketRca(props.ticketId, rcaForm.value).then(() => {
      proxy.$modal.msgSuccess('RCA保存成功');
      refreshTimeline();
      emit('changed');
    });
  }

  watch(
    () => props.ticketId,
    () => {
      historyActiveTab.value = 'timeline';
      timeline.value = {};
      eventDataText.value = '';
      eventForm.value = { eventType: 'ANALYSIS', content: '' };
      rcaForm.value = {};
      if (props.active) {
        refreshTimeline();
      }
    }
  );

  watch(
    () => props.active,
    (active) => {
      if (active && !timeline.value?.statusHistory && !timeline.value?.events) {
        refreshTimeline();
      }
    },
    { immediate: true }
  );

  loadStatClassificationOptions();
  loadWorkflowConfig();
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

<style scoped>
  .record-head {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 8px;
    color: #606266;
    font-size: 13px;
  }

  .timeline-title {
    margin-bottom: 6px;
    font-weight: 600;
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
</style>
