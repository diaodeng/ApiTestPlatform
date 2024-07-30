<script setup>
import {
  CirclePlus,
  Plus,
  Edit,
  Message,
  Star,
  Delete,
  Check,
  Search,
  Setting,
  SuccessFilled
} from "@element-plus/icons-vue";
import {Json} from "@/utils/tools.js";

onErrorCaptured((error) => {
  console.log(error);
})
import {VAceEditor} from 'vue3-ace-editor';
import "./aceConfig.js"
import ace from "ace-builds/src-noconflict/ace"
// import "ace-builds/src-noconflict/mode-json"
// import "ace-builds/src-noconflict/theme-github"
// import workerJsonUrl from 'ace-builds/src-noconflict/worker-json?url'

// ace.config.set("basePath", "/node_modules/ace-builds/src-noconflict")
// ace.config.setModuleUrl("ace/mode/json_worker", workerJsonUrl)

const props = defineProps(["canSet", "lang", "theme", "height", "width"]);
const modelContent = defineModel("content");
const languageValue = ref("json");
const themesValue = ref("github");
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

onMounted(() => {
  console.log("挂载了编辑器")
})

onBeforeUnmount(() => {
  console.log("卸载了编辑器")
})

const editorContent = computed(() => {
  if (typeof modelContent.value === "string") {
    return modelContent.value
  } else {
    try {
      return JSON.stringify(modelContent.value, null, 4);
    } catch (e) {
      // return modelContent.value.toString();
      return toRaw(modelContent.value);
    }
  }

})

function updataValue(newVal) {
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

</script>

<template>
  <div>

    <el-row>
      <el-tooltip content="格式化JSON" placement="bottom-start" effect="light">
        <el-button type="primary" size="small" circle @click="jsonFormat">B</el-button>
      </el-tooltip>
      <el-tooltip content="压缩JSON" placement="bottom-start" effect="light">
        <el-button type="success" size="small" circle @click="jsonCompress">C</el-button>
      </el-tooltip>
      <el-tooltip content="移除转义符并格式化JSON" placement="bottom-start" effect="light">
        <el-button type="info" size="small" circle @click="jsonRemoveEscapeAndBeautiful">RB</el-button>
      </el-tooltip>
      <el-tooltip content="压缩并转义JSON" placement="bottom-start" effect="light">
        <el-button type="warning" size="small" circle @click="jsonCompressAndEscape">CE</el-button>
      </el-tooltip>
      <div class="flex-grow"></div>

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
        :value="editorContent"
        @update:value="updataValue"
        :lang="languageValue"
        :theme="themesValue"
        style="height: 600px; width: 100%"
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
</style>