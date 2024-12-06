<script setup>

import {Close, FullScreen} from "@element-plus/icons-vue";
import {ref} from 'vue';
import {ElMessage} from 'element-plus';

const isFullscreen = defineModel({default: false});
const props = defineProps({
  showFullScreenButton: {type: Boolean, default: false}
});
const emits = defineEmits(["changeFullScreen"]);


// const isFullscreen = ref(false);
const fullscreenElement = ref(null);
const oldHeight = ref(null);

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value;
  emits("changeFullScreen", !isFullscreen.value);
}

function enterFullscreen() {
  const element = fullscreenElement.value;
  if (element.requestFullscreen) {
    element.requestFullscreen();
  } else if (element.mozRequestFullScreen) {
    element.mozRequestFullScreen(); // Firefox
  } else if (element.webkitRequestFullscreen) {
    element.webkitRequestFullscreen(); // Chrome, Safari, Opera
  } else if (element.msRequestFullscreen) {
    element.msRequestFullscreen(); // IE/Edge
  }
  isFullscreen.value = true;
  ElMessage.success('已进入全屏模式');
}

function exitFullscreenHandle() {
  if (document.exitFullscreen) {
    document.exitFullscreen();
  } else if (document.mozCancelFullScreen) {
    document.mozCancelFullScreen(); // Firefox
  } else if (document.webkitExitFullscreen) {
    document.webkitExitFullscreen(); // Chrome, Safari, Opera
  } else if (document.msExitFullscreen) {
    document.msExitFullscreen(); // IE/Edge
  }
  isFullscreen.value = false;
  ElMessage.info('已退出全屏模式');
};
</script>

<template>

  <!-- 需要全屏显示的内容 -->
  <div ref="fullscreenElement" class="content" :class="{ fullscreen: isFullscreen }">
    <el-button @click="toggleFullscreen"
               style="position: absolute;top: 22px;right: 40px; z-index: 9997; opacity: 0.6"
               :class="{'fullscreen-button': isFullscreen}"
               type="info"
               circle
               v-if="showFullScreenButton"
    >
      <el-icon v-if="!isFullscreen">
        <full-screen/>
      </el-icon>
      <el-icon v-else>
        <close/>
      </el-icon>
    </el-button>
    <div style="flex-grow: 1;">
      <slot></slot>
    </div>

  </div>

</template>


<style scoped lang="scss">
.content {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  /**
  width: 300px;
  height: auto;
  background-color: #f0f0f0;
  text-align: center;
  line-height: 200px;
  border: 1px solid #ccc;
  margin: 20px 0;
  **/
}

/* 全屏时的样式 */
.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100% !important;
  height: 100% !important;
  z-index: 9998;
  background-color: #f4f4f4;
  //margin: 10px;
  padding: 10px;
}


.fullscreen-button {
  z-index: 9998;
}
</style>
