<script setup>
import {ElMessage} from "element-plus";
import {Setting, Search} from "@element-plus/icons-vue";
import {Json} from "@/utils/tools.js";
import {VAceEditor} from 'vue3-ace-editor';
import "./aceConfig.js"
import {search as jmespath} from '@metrichor/jmespath';

onErrorCaptured((error) => {
  console.log(error);
})

const props = defineProps({
  canSet: {
    type: [Boolean, String],
    default: false
  },
  canSearch: {
    type: [Boolean, String],
    default: false
  },
  lang: {
    type: String,
    default: "json"
  },
  themes: {
    type: String,
    default: "github"
  },
  height: {
    type: [String, Number],
    default: "calc(100vh - 160px)"
  },
  width: {
    type: [String, Number],
    default: "100%"
  },
  isFullscreen: {
    type: [Boolean],
    default: false
  }
});
const modelContent = defineModel("content");
const languageValue = ref("json");
const themesValue = ref("github");
const jmespathRex = ref("");

const language = ref([{
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
}])

languageValue.value = props.lang;
themesValue.value = props.themes;

onMounted(() => {
  console.log("挂载了编辑器")
})

onBeforeUnmount(() => {
  console.log("卸载了编辑器")
})

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

})

function updateValue(newVal) {
  modelContent.value = newVal;
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

</script>

<template>
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


    <v-ace-editor
        :class="{fullscreen:isFullscreen}"
        :value="editorContent"
        @update:value="updateValue"
        :lang="languageValue"
        :theme="themesValue"
        :style="{height: height, width: width}"
        :options="{
    useWorker: true,
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
  }"
    ></v-ace-editor>
  </div>


</template>

<style scoped lang="scss">
.flex-grow {
  flex-grow: 1;
}

.fullscreen {
  height: calc(100vh - 100px) !important;
}
</style>