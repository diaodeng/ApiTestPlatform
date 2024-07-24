<script setup>
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


</script>

<template>
  <div>
    <el-row v-if="canSet" class="editor-row">
      <el-text>语言：</el-text>
      <el-col :span="5">
        <el-select v-model="languageValue">
          <el-option v-for="item in language"
                     :key="item.value"
                     :label="item.label"
                     :value="item.value"
                     :disabled="!item.enable"

          ></el-option>
        </el-select>
      </el-col>
      <el-text>主题：</el-text>
      <el-col :span="5">
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

</style>