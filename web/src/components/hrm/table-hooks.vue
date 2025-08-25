<script setup>
// variables、data、param使用
import {useI18n} from "vue-i18n";
import CommonTable from './table-config-common.vue';
import {CodeTypeEnum} from "@/components/hrm/enum.js";
import TagSelector from "@/components/hrm/common/tag-selector.vue";
import AceEditor from "@/components/hrm/common/ace-editor.vue";
import FullscreenComponents from "@/components/hrm/common/fullscreen-component.vue";
import {Close, FullScreen} from "@element-plus/icons-vue";
import {Edit} from "@element-plus/icons-vue";

const {t} = useI18n();
const selfData = defineModel();
const props = defineProps({
  tableTitle: {type: String, default: ""},
  toolFixTarget: {type: String, default: ""}
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
const fullScreen = ref(false);


</script>

<template>
  <div style="margin-bottom: 10px;margin-top: 10px">
    <el-text style="font-weight: bold">{{ tableTitle }}</el-text>
    <CommonTable :cols="tableCols" v-model="selfData.functions" table-title="回调方法"></CommonTable>
    <div style="margin-top: 5px">
      <AceEditor v-model:content="selfData.codeInfo.codeContent"
                 :can-set="false"
                 :lang="selfData.codeInfo.codeType === CodeTypeEnum.js.value ? 'javascript' : 'python'"
                 height="200px"
                 :can-resize="true"
                 :show-full-screen-button="true"
      >
        <template #edit-tools>
          <div style="margin-top: 5px">
            <el-text>自定义回调脚本</el-text>
            <el-select v-model="selfData.codeInfo.codeType"
                       style="width: 95px">
              <el-option
                  v-for="option in Object.values(CodeTypeEnum)"
                  :key="option.value * 1"
                  :label="option.label"
                  :value="option.value * 1"
              />

            </el-select>
          </div>
        </template>
      </AceEditor>
    </div>

    <!--    <el-input type="textarea" v-model="selfData.codeInfo.codeContent"/>-->
  </div>

</template>

<style scoped lang="scss">
</style>