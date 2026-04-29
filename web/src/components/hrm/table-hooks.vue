<script setup>
// variables、data、param使用
import {useI18n} from "vue-i18n";
import CommonTable from './table-config-common.vue';
import {CodeTypeEnum} from "@/components/hrm/enum.js";
import CodeViewNew from "@/components/hrm/common/hightlight-component.vue";

const {t} = useI18n();
const selfData = defineModel();
const props = defineProps({
  tableTitle: {type: String, default: ""},
  toolFixTarget: {type: String, default: ""},
  editorKey: {type: String, default: ""},
  editorTitle: {type: String, default: ""}
});
const tableCols = [{
  name: t('message.configTable.header.key'),
  prop: "key",
  width: 300
}, {
  name: t('message.configTable.header.desc'),
  prop: "desc",
  width: ""
}]
const scriptEditorContext = inject("hrm_script_editor", null);

const languageOptions = Object.values(CodeTypeEnum);

const currentLang = computed(() => {
  return selfData.value?.codeInfo?.codeType === CodeTypeEnum.js.value ? "javascript" : "python";
});

const hasScriptContent = computed(() => {
  return Boolean(selfData.value?.codeInfo?.codeContent);
});

watch(() => selfData.value, (newValue) => {
  if (!newValue) {
    return;
  }
  if (!newValue.codeInfo) {
    newValue.codeInfo = {
      codeType: CodeTypeEnum.js.value,
      codeContent: "",
    };
  }
  if (!Array.isArray(newValue.functions)) {
    newValue.functions = [];
  }
}, {immediate: true});

function openScriptEditor() {
  if (!selfData.value?.codeInfo) {
    return;
  }
  scriptEditorContext?.openScriptEditor?.({
    sessionKey: props.editorKey || props.tableTitle || "table-hooks-editor",
    title: props.editorTitle || props.tableTitle || "回调脚本",
    codeInfo: selfData.value.codeInfo,
  });
}


</script>

<template>
  <div style="margin-bottom: 10px;margin-top: 10px">
    <el-text style="font-weight: bold">{{ tableTitle }}</el-text>
    <el-card>
      <CommonTable :cols="tableCols" v-model="selfData.functions" table-title="回调方法"></CommonTable>
    </el-card>

    <el-card style="margin-top: 5px">
      <el-row justify="space-between" align="middle" class="hooks-script-toolbar">
        <div class="hooks-script-toolbar__left">
          <el-text>回调脚本</el-text>
          <el-tag size="small" type="info">{{ currentLang }}</el-tag>
        </div>
        <div class="hooks-script-toolbar__right">
          <el-select v-model="selfData.codeInfo.codeType"
                     size="small"
                     style="width: 100px">
            <el-option
                v-for="option in languageOptions"
                :key="option.value * 1"
                :label="option.label"
                :value="option.value * 1"
            />
          </el-select>
          <el-button type="primary" text @click="openScriptEditor">编辑</el-button>
        </div>
      </el-row>
      <div class="hooks-script-preview">
        <CodeViewNew
            v-if="hasScriptContent"
            :code="selfData.codeInfo.codeContent"
            :lang="currentLang"
        />
        <el-empty v-else description="暂无脚本" :image-size="60"/>
      </div>
    </el-card>

    <!--    <el-input type="textarea" v-model="selfData.codeInfo.codeContent"/>-->
  </div>

</template>

<style scoped lang="scss">
.hooks-script-toolbar__left,
.hooks-script-toolbar__right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hooks-script-preview {
  margin-top: 10px;
}
</style>
