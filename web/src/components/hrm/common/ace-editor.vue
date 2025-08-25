<script setup>
import "./aceConfig.js"
import {useTemplateRef, defineAsyncComponent} from "vue";
import {ElMessage} from "element-plus";
import {Setting, Search} from "@element-plus/icons-vue";
import {Json} from "@/utils/tools.js";
import {VAceEditor} from 'vue3-ace-editor';
import {search as jmespath} from '@metrichor/jmespath';
import FullscreenComponent from "@/components/hrm/common/fullscreen-component.vue";

onErrorCaptured((error) => {

  console.log("编辑器相关异常");
  console.log(error);
});


const props = defineProps({
  canSet: {type: [Boolean, String], default: false},
  canSearch: {type: [Boolean, String], default: false},
  lang: {type: String, default: "json"},
  themes: {type: String, default: "github"},
  height: {type: [String, Number], default: "calc(100vh - 160px)"},
  width: {type: [String, Number], default: "100%"},
  showFullScreenButton: {type: [Boolean, String], default: false},
  enableBasicAutocompletion: {type: Boolean, default: true},
  enableLiveAutocompletion: {type: Boolean, default: true},
  enableSnippets: {type: Boolean, default: true},
  showPrintMargin: {type: Boolean, default: false},
  highlightActiveLine: {type: Boolean, default: true},
  highlightSelectedWord: {type: Boolean, default: true},
  tabSize: {type: Number, default: 2},
  fontSize: {type: Number, default: 14},
  wrap: {type: Boolean, default: false},
  readOnly: {type: Boolean, default: false},
  useWorker: {type: Boolean, default: true},
  canResize: {type: Boolean, default: false}
});
const modelContent = defineModel("content");
const languageValue = ref("json");
const themesValue = ref("github");
const jmespathRex = ref("");
const aceEditorRef = useTemplateRef("aceEditorRef");
const isFullscreen = ref(false);

const startY = ref(0);
const startHeight = ref(0);
let isDragging = false;
let intervalId = null;

const editorHeight = ref("100px");
const editorWidth = ref("100%");
//
// const jmespath = defineAsyncComponent(() =>
//   import('@metrichor/jmespath')
// );


const language = ref([{
  "label": "text",
  "value": "text",
  "enable": true
}, {
  "label": "json",
  "value": "json",
  "enable": true
}, {
  "label": "javascript",
  "value": "javascript",
  "enable": true
}, {
  "label": "python",
  "value": "python",
  "enable": true
}, {
  "label": "yaml",
  "value": "yaml",
  "enable": true
}, {
  "label": "html",
  "value": "html",
  "enable": true
}]);
const themes = ref([{
  "label": "github",
  "value": "github",
  "enable": true
}, {
  "label": "github_dark",
  "value": "github_dark",
  "enable": true
}, {
  "label": "chrome",
  "value": "chrome",
  "enable": true
}, {
  "label": "monokai",
  "value": "monokai",
  "enable": true
}, {
  "label": "eclipse",
  "value": "eclipse",
  "enable": true
}]);

const editorConfig = ref(
    {
      enableBasicAutocompletion: true,
      enableLiveAutocompletion: true,
      enableSnippets: true,
      showPrintMargin: false,
      highlightActiveLine: true,
      highlightSelectedWord: true,
      tabSize: 2,
      fontSize: 14,
      wrap: false,
      readOnly: false,
    }
);

languageValue.value = props.lang;
themesValue.value = props.themes;

watch(() => props.lang, (newValue) => {
  languageValue.value = newValue;
});
watch(() => props.height, (newValue) => {
  editorHeight.value = newValue;
});
watch(() => props.width, (newValue) => {
  editorWidth.value = newValue;
});

onMounted(() => {
  // console.log("浏览器的新值" + modelContent.value);
  nextTick(() => {
    try {
      console.log("挂载了编辑器");
      editorHeight.value = props.height;
      document?.addEventListener('mousemove', onMoveResizeEditor);
    } catch (e) {
      console.log("编辑挂载载异常");
    }
  });

});

onBeforeUnmount(() => {
  console.log("卸载了编辑器")
  try {
    document?.removeEventListener('mousemove', resizeEditor);
    document?.removeEventListener('mouseup', stopResizing);
    document?.removeEventListener('mouseleave', onMouseLeave);
    document?.removeEventListener('mousemove', onMoveResizeEditor);
  } catch (e) {
    console.log("编辑器卸载异常");
  }
});

let originalStyles = {
  width: "",
  height: "",
  position: "",
  top: "",
  left: "",
  zIndex: "",
}

const editorContent = computed(() => {
  let data = modelContent.value;
  if (typeof data === "string") {
    return toRaw(data);
  } else {
    try {
      return JSON.stringify(data, null, 4);
    } catch (e) {
      return toRaw(data);
    }
  }
});

function updateValue(newVal) {
  nextTick(() => {
    modelContent.value = newVal;
  });
}

function jsonFormat(env) {
  modelContent.value = Json.beautifulJson(modelContent.value);
}

function jsonCompress(env) {
  modelContent.value = Json.compressJson(modelContent.value);
}

function jsonCompressAndEscape(env) {
  modelContent.value = Json.compressAndEscape(modelContent.value);
}

function jsonRemoveEscapeAndBeautiful(env) {
  const tmpData = Json.removeEscape(modelContent.value);
  modelContent.value = Json.beautifulJson(tmpData)
}

function jmespathSearch() {
  let data = modelContent.value;
  let dataObj = null;
  const rex = jmespathRex.value;
  if (!rex) {
    ElMessage.warning("请输入jmespath表达式");
    return;
  }
  if (!data) {
    ElMessage.warning("没有可查询的数据");
    return;
  } else {
    try {
      dataObj = Json.parse(data)
    } catch (e) {
      ElMessage.error("被查询数据不是合法的json数据");
      return;
    }
  }

  try {
    const result = jmespath(dataObj, jmespathRex.value);
    console.log("搜索结果：" + result);
    modelContent.value = result;
  } catch (e) {
    ElMessage.error("查询异常" + e);
  }
}

const startResizing = (e) => {
  // console.log("开始调整高度");
  isDragging = true;
  startY.value = e.clientY;
  startHeight.value = aceEditorRef.value.$el.offsetHeight;
  document.addEventListener('mousemove', resizeEditor);
  document.addEventListener('mouseup', stopResizing);
  document.addEventListener('mouseleave', onMouseLeave);
};

// 调整编辑器的高度
const resizeEditor = (e) => {
  if (isDragging) {
    const diff = e.clientY - startY.value;
    editorHeight.value = (startHeight.value + diff) + 'px';
  }
};

// 停止调整
const stopResizing = () => {
  console.log("停止高度调整");
  isDragging = false;
  document.removeEventListener('mousemove', resizeEditor);
  document.removeEventListener('mouseup', stopResizing);
  document.removeEventListener('mouseleave', onMouseLeave);
};

function onMouseLeave(e) {
  console.log("鼠标离开页面");
  if (isDragging) {
    const lastMouseMove = e; // 你可以记录鼠标离开时的位置
    isDragging = false;
    document.removeEventListener('mousemove', resizeEditor);
    document.removeEventListener('mouseup', stopResizing);
    document.removeEventListener('mouseleave', onMouseLeave);

    // 设置定时器继续调整高度
    const speed = 5; // 你可以调整这个速度
    intervalId = setInterval(() => {
      // 这里假设我们希望鼠标离开时继续向上或向下移动
      // 你可以根据实际情况决定移动方向
      if (lastMouseMove.clientY < window.innerHeight - editorHeight.value / 2) {
        // 鼠标在元素上方离开，增加高度
        editorHeight.value = `${parseInt(resizable.style.height) + speed}px`;
      } else {
        // 鼠标在元素下方离开，减少高度
        editorHeight.value = `${parseInt(resizable.style.height) - speed}px`;
      }

      // 检查边界条件，防止高度变为负数或过大
      const newHeight = parseInt(resizable.style.height);
      if (newHeight <= 20 || newHeight >= window.innerHeight) {
        clearInterval(intervalId);
      }
    }, 50); // 调整时间间隔，以毫秒为单位
  }
}

function onMoveResizeEditor(e) {
  if (intervalId !== null) {
    clearInterval(intervalId);
    intervalId = null;
    isDragging = true; // 可以重新设置为拖动状态，但需要注意逻辑处理
    document.addEventListener('mousemove', resizeEditor);
  }
}

// watch(() => props.isFullscreen, (newValue) => {
//   if (newValue) {
//     const editor = aceEditorRef.value.$el;
//     originalStyles.height = aceEditorRef.value.$el.style.height;
//     editorHeight.value = "100%";
//   } else {
//     const editor = aceEditorRef.value.$el;
//     editorHeight.value = originalStyles.height;
//     editor.style.position = "relative";
//   }
//   nextTick(()=>{
//     aceEditorRef.value.getAceInstance().resize(true);
//   });
//
// });

function changeFullScreenStatus(currentStatus) {

  nextTick(() => {
    if (currentStatus) {
      const editor = aceEditorRef.value.$el;
      originalStyles.height = editor.style.height;
      originalStyles.width = editor.style.width;
      editorHeight.value = "calc(100%)";
      editorWidth.value = "calc(100%)";
    } else {
      const editor = aceEditorRef.value.$el;
      editorHeight.value = originalStyles.height;
      editorWidth.value = originalStyles.width;
      editor.style.position = "relative";
    }
    aceEditorRef?.value?.getAceInstance()?.resize(true);
  });
}


</script>

<template>
  <FullscreenComponent v-model="isFullscreen"
                       @change-full-screen="changeFullScreenStatus"
                       :show-full-screen-button="showFullScreenButton"
  >
    <div style="display: flex; flex-direction: column; height: 100%; width: 100%">
      <div>
        <slot name="edit-tools"></slot>
      </div>
      <div>
        <el-row align="middle">
          <div v-if="languageValue === 'json'">
            <el-tooltip content="格式化JSON" placement="top-start" effect="light">
              <el-button type="primary" size="small" circle @click="jsonFormat">B</el-button>
            </el-tooltip>
            <el-tooltip content="压缩JSON" placement="top-start" effect="light">
              <el-button type="success" size="small" circle @click="jsonCompress">C</el-button>
            </el-tooltip>
            <el-tooltip content="移除转义符并格式化JSON" placement="top-start" effect="light">
              <el-button type="info" size="small" circle @click="jsonRemoveEscapeAndBeautiful">RB</el-button>
            </el-tooltip>
            <el-tooltip content="压缩并转义JSON" placement="top-start" effect="light">
              <el-button type="warning" size="small" circle @click="jsonCompressAndEscape">CE</el-button>
            </el-tooltip>
          </div>

          <div class="flex-grow">
            <el-input size="small"
                      v-if="canSearch && languageValue === 'json'"
                      v-model="jmespathRex"
                      placeholder="jmespath表达式"
                      style="padding-left: 5px;padding-right: 5px"
            >
              <template #append>
                <el-tooltip content="使用jmespath搜索" placement="top-start" effect="light">
                  <el-button :icon="Search" @click="jmespathSearch"></el-button>
                </el-tooltip>
              </template>
            </el-input>
          </div>

          <el-popover v-if="canSet"
                      placement="top-start"
                      title="设置"
                      :width="200"
                      trigger="click"
                      content="this is content, this is content, this is content"
          >
            <template #reference>
              <el-button size="small" circle :icon="Setting"/>
            </template>
            <template #default>
              <el-row v-if="canSet" class="editor-row">
                <el-text>语言：</el-text>
                <el-col>
                  <el-select v-model="languageValue">
                    <el-option v-for="item in language"
                               :key="item.value"
                               :label="item.label"
                               :value="item.value"
                               :disabled="!item.enable"

                    ></el-option>
                  </el-select>
                </el-col>
              </el-row>
              <el-row>
                <el-col>
                  <el-text>主题：</el-text>
                  <el-select v-model="themesValue">
                    <el-option v-for="item in themes"
                               :key="item.value"
                               :label="item.label"
                               :value="item.value"
                               :disabled="!item.enable"
                    ></el-option>
                  </el-select>
                </el-col>
              </el-row>
            </template>
          </el-popover>
        </el-row>
      </div>
      <div style="flex-grow: 1">
        <Suspense>
          <v-ace-editor
              ref="aceEditorRef"
              :value="editorContent"
              @update:value="updateValue"
              :lang="languageValue"
              :theme="themesValue"
              :style="{height: editorHeight, width: editorWidth}"
              :options="{
          useWorker: props.useWorker,
          enableBasicAutocompletion: props.enableBasicAutocompletion,
          enableLiveAutocompletion: props.enableLiveAutocompletion,
          enableSnippets: props.enableSnippets,
          showPrintMargin: props.showPrintMargin,
          highlightActiveLine: props.highlightActiveLine,
          highlightSelectedWord: props.highlightSelectedWord,
          tabSize: props.tabSize,
          fontSize: props.fontSize,
          wrap: props.wrap,
          readOnly: props.readOnly,
        }"
              aria-autocomplete="list"
          ></v-ace-editor>
        </Suspense>

      </div>
    </div>


    <div style="width: 100%;text-align: center" v-if="canResize">
      <div class="resize-handle" @mousedown.prevent="startResizing"></div>
    </div>

  </FullscreenComponent>


</template>

<style scoped lang="scss">
.flex-grow {
  flex-grow: 1;
}

.resize-handle {
  border-radius: 5px;
  margin-left: 43px;
  width: 60px;
  margin: 0 auto;
  height: 10px;
  background-color: rgba(147, 143, 143, 0.29);
  cursor: ns-resize;
}


</style>