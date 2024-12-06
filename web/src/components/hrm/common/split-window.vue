<script setup>
const props = defineProps({
  "leftWidth": {type: [String, Number], default: "200px"},
  "windowWidth": {type: [String, Number], default: "100%"},
  "windowHeight": {type: [String, Number], default: "100%"}
});

let boxRef = ref(null);
let leftRef = ref(null);
let resizeRef = ref(null);
let rightRef = ref(null);
let startX = ref(0);
let leftStartWidth = ref(500);
let selfLeftWidth = ref(toRaw(props.leftWidth));

const dragging = ref(false);


const onMouseMove = (event) => {
  if (dragging.value) {
    let endX = event.pageX;
    let leftW = leftStartWidth.value + (endX - startX.value); // （endx-startx）=移动的距离。resize[i].left+移动的距离=左边区域最后的宽度
    let rightW = boxRef.value.offsetWidth - resizeRef.value.offsetWidth - leftW; // 容器宽度 - 左边区域的宽度 = 右边区域的宽度
    // leftRef.value.style.width = leftW + 'px';
    selfLeftWidth.value = leftW + 'px';
    rightRef.value.style.width = rightW + 'px';
  }
};

function resizeDown(e) {
  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', resizeUp);
  dragging.value = true;
  resizeRef.value.background = '#818181';
  leftStartWidth.value = leftRef.value.offsetWidth;
  startX.value = e.pageX;
}

function resizeUp(e) {
  window.removeEventListener('mousemove', onMouseMove);
  window.removeEventListener('mouseup', resizeUp);
  dragging.value = false;
  //颜色恢复
  resizeRef.value.background = '#d6d6d6';
  // document.onmousemove = null;
  // document.onmouseup = null;
  // resizeRef.releaseCapture && resizeRef.releaseCapture(); //当你不在需要继续获得鼠标消息就要应该调用ReleaseCapture()释放掉
}

function boxResize(event) {
  let leftW = leftRef.value.offsetWidth;
  let rightW = boxRef.value.offsetWidth - resizeRef.value.offsetWidth - leftW; // 容器宽度 - 左边区域的宽度 = 右边区域的宽度

  // selfLeftWidth.value = leftW + 'px';
  if (rightW >= 20) {
    rightRef.value.style.width = rightW + 'px';
  }

}


</script>

<template>
  <el-container style="width: 100%;height: 100%">
    <div class="box" ref="boxRef" :style="{width: windowWidth, height: windowHeight}" @resize="boxResize">
      <!--    <div class="box" ref="boxRef" >-->
      <div class="left" ref="leftRef" :style="{width: selfLeftWidth}" style="height: 100%">
        <slot name="left"></slot>
      </div>
      <div
          style="align-items: center; height: auto; display: flex; justify-content: center; position: relative; background-color: #f1f3f6; border-radius: 5px;">
        <div class="resize" ref="resizeRef" @mousedown="resizeDown" style="height: auto">⋮</div>
      </div>

      <div class="right" ref="rightRef">
        <slot name="right"></slot>
      </div>
    </div>

  </el-container>

</template>

<style scoped lang="scss">

/* 拖拽相关样式 */
/*包围div样式*/
.box {
  display: inline-flex;
  width: 100%;
  height: 100%;
  /*margin: 1% 0px;*/
  overflow: hidden;
  /*box-shadow: -1px 9px 10px 3px rgba(0, 0, 0, 0.11);*/
}

/*左侧div样式*/
.left {
  width: calc(100%); /*左侧初始化宽度*/
  height: 100%;
  background: #FFFFFF;
  /*float: left;*/
  min-width: 50px;
}

.right {
  height: 100%;
  width: calc(100%);
  min-width: 50px;
}

/*拖拽区div样式*/
.resize {
  cursor: col-resize;
  /*float: left;*/
  /*position: relative;*/
  top: 45%;
  background-color: #d6d6d6;
  border-radius: 5px;
  margin-top: -10px;
  width: 10px;
  height: 50px;
  background-size: cover;
  background-position: center;
  /*z-index: 99999;*/
  font-size: 32px;
  color: white;
}

/*拖拽区鼠标悬停样式*/
.resize:hover {
  color: #444444;
}
</style>