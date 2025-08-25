<script setup>

import vClickOutside from "@/components/hrm/common/click-outside.js";

const props = defineProps({
  x: {type: Number, default: 0},
  y: {type: Number, default: 0},
  menus: {type: Array, default: [{"title": "右键菜单"}]},
  evt: {type: Object, default: null},
});

const visible = defineModel("visible", {type: Boolean, default: false});

const emits = defineEmits(["select"]);

const menuPosition = ref({x: 0, y: 0});
const menuRef = ref(null);

function hide() {
  visible.value = false;
}

// function show(evt) {
//   visible.value = true;
//   x.value = evt.clientX;
//   y.value = evt.clientY;
// }

function calculateContextMenuPosition(x, y) {
  const {clientWidth, clientHeight} = document.body;
  const {clientWidth: menuWidth, clientHeight: menuHeight} = menuRef.value;
  const xPosition = x + menuWidth > clientWidth ? x - menuWidth : x;
  const yPosition = y + menuHeight > clientHeight ? y - menuHeight : y;
  menuPosition.value.x = xPosition;
  menuPosition.value.y = yPosition;
}

watch([() => props.x, () => props.y], ([newX, newY], oldProps) => {
  nextTick(() => {
    calculateContextMenuPosition(newX, newY);
  });
  // calculateContextMenuPosition(newProps.x, newProps.y);
});

</script>

<template>
    <div v-show="visible"
         :style="{left: menuPosition.x + 'px',top: menuPosition.y + 'px',display: visible ? 'block' : 'none'}"
         class="context-menu"
         v-click-outside="hide"
         ref="menuRef"
    >
      <div
          v-for="(item, i) in menus"
          :key="i"
          class="menu-item"
          @click="visible = false;$emit('select', item)"
          style="display: flex;flex-direction: column;"
      >
        {{ item.title }}
        <!--      <el-button type="success">{{ item.title }}</el-button>-->

      </div>

    </div>

</template>

<style scoped lang="scss">

.context-menu {
  margin: 0;
  background: #fff;
  z-index: 9999;
  position: fixed;
  list-style-type: none;
  padding: 4px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 400;
  color: #333;
  box-shadow: 2px 2px 2px 2px rgba(0, 0, 0, 0.3);

  .menu-item {
    padding: 0 15px;
    height: 32px;
    line-height: 32px;
    color: rgb(29, 33, 41);
    cursor: pointer;
  }

  .menu-item:hover {
    background: var(--el-color-primary-light-9);
    border-radius: 4px;
  }
}
</style>