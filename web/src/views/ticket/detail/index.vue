<template>
  <div class="ticket-detail-page">
    <TicketDetailView :ticket-id="ticketId" />
  </div>
</template>

<script setup name="TicketDetail">
  import { computed } from 'vue';
  import { useRoute } from 'vue-router';
  import TicketDetailView from '../components/TicketDetailView.vue';

  const route = useRoute();
  // 从纯净详情页路由读取工单 ID，避免详情组件依赖父页面状态。
  const ticketId = computed(() => Number(route.params.ticketId || 0));
</script>

<style scoped>
  .ticket-detail-page {
    min-height: 100vh;
    background: #fff;
  }
</style>
