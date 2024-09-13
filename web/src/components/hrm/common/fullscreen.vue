<script setup>

import {Close, FullScreen} from "@element-plus/icons-vue";
import {ref} from 'vue';
import {ElMessage} from 'element-plus';


const isFullscreen = ref(false);
const fullscreenElement = ref(null);
const oldHeight = ref(null);

function toggleFullscreen() {
  // if (isFullscreen.value) {
  //   // console.log(fullscreenElement.value)
  //   fullscreenElement.value.clientHeight = oldHeight.value;
  // } else {
  //   console.log(fullscreenElement.value)
  //   // console.log(fullscreenElement.value.height)
  //   // console.log(fullscreenElement.value)
  //   oldHeight.value = fullscreenElement.value.clientHeight;
  //   // console.log(oldHeight.value)
  // }
  isFullscreen.value = !isFullscreen.value
};

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
};

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
  <div>
    <!-- 需要全屏显示的内容 -->
    <div ref="fullscreenElement" class="content" :class="{ fullscreen: isFullscreen }">
      <el-button @click="toggleFullscreen"
                 style="position: absolute;top: 22px;right: 40px;z-index: 9999;opacity: 0.6"
                 type="info"
                 circle
      >
        <el-icon v-if="!isFullscreen">
          <full-screen/>
        </el-icon>
        <el-icon v-else>
          <close/>
        </el-icon>
      </el-button>
      <slot></slot>
    </div>
  </div>
</template>


<style scoped>
.content {
  //width: 300px;
  //height: auto;
  //background-color: #f0f0f0;
  //text-align: center;
  //line-height: 200px;
  //border: 1px solid #ccc;
  //margin: 20px 0;
}

/* 全屏时的样式 */
.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9998;
  background-color: white;
  margin: 0;
}
</style>


<style scoped lang="scss">

</style>