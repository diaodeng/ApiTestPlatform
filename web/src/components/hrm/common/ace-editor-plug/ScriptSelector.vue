<template>
  <div class="selector">
    <div
      v-for="block in blocks"
      :key="block.key"
      :class="['item', { active: block.key === active }]"
      @click="$emit('switch', block.key)"
    >
      {{ block.label }}
      <span v-if="dirtyMap[block.key]" class="dirty-dot">*</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  blocks: Array,
  active: String,
  dirtyMap: Object
})
</script>

<style scoped>
.selector {
  width: 180px;
  border-right: 1px solid #ddd;
}

.item {
  padding: 10px;
  cursor: pointer;
}

.item.active {
  background: #eee;
  font-weight: bold;
}

.dirty-dot {
  color: red;
  margin-left: 6px;
}
</style>