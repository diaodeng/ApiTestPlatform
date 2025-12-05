<template>
<div class="vt-header">
<div
class="vt-header-cell"
v-for="col in columns"
:key="col.key"
:style="{ width: col.width + 'px' }"
>
{{ col.label }}
</div>
</div>
</template>


<script setup>
const props = defineProps({ columns: Array });
</script>


<style scoped>
.vt-header {
display: flex;
background: #fafafa;
border-bottom: 1px solid #ddd;
}
.vt-header-cell {
height: 36px;
line-height: 36px;
padding: 0 8px;
border-right: 1px solid #eee;
box-sizing: border-box;
}
</style>