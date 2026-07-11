<template>
  <div class="app-container ticket-detail-page">
    <TicketDetailView :ticket-id="ticketId" />
  </div>
</template>

<script setup name="TicketDetail">
  import { computed } from 'vue';
  import { useRoute } from 'vue-router';
  import TicketDetailView from '../components/TicketDetailView.vue';

  const route = useRoute();
  const ticketId = computed(() => Number(route.params.ticketId || 0));
</script>

<style scoped>
  .ticket-detail-page {
    min-height: calc(100vh - 84px);
    background: #fff;
  }
</style>
