<script setup>


import {parseJson} from "@/api/hrm/tools.js";
import {ElMessage} from "element-plus";
import {Json} from "@/utils/tools.js";
import Editor from "@/components/Editor/index.vue";
import AceEditor from "@/components/hrm/common/ace-editor.vue";

const form = ref({
  content: "",
  advanced: false,
  whiteList: [],
  nestedParse: false,
})
const result = ref("")


function base64Encode(str) {
  return btoa(
      encodeURIComponent(str).replace(
          /%([0-9A-F]{2})/g,
          (_, p1) => String.fromCharCode('0x' + p1)
      )
  );
}

function comfirmParse(evt) {
  console.log(form.value.content);
  const data = {
    content: base64Encode(form.value.content),
    advanced: form.value.advanced,
    whiteList: form.value.whiteList,
    nestedParse: form.value.nestedParse,
  }
  parseJson(data).then(response => {
    result.value = Json.beautifulJson(response.data);
  }).catch(error => {
    ElMessage.error(error.message);
  });
}

</script>

<template>
  <el-container style="width:100%;height:100%;">
    <el-header>
      <el-text>JSON格式化工具</el-text>
      <el-row>
        <el-button @click="comfirmParse">提交</el-button>
<!--        <el-checkbox v-model="form.advanced">高级</el-checkbox>-->
        <el-checkbox v-model="form.nestedParse">递归</el-checkbox>

      </el-row>
    </el-header>
    <el-main style="height: 100%;">
      <el-row style="height: 100%;">
        <el-splitter style="height: 100%;">
          <el-splitter-panel size="40%" style="height: 100%;">
            <div style="height: 100%;">
              <el-input type="textarea" v-model="form.content" style="height: 100%"></el-input>
            </div>
          </el-splitter-panel>
          <el-splitter-panel :min="200">
            <div style="height: 100%;">
              <AceEditor v-model:content="result"
                         :can-set="true"
                         :can-search="true"
                         height="100%"
                         key="tools_editor"
                         :enable-basic-autocompletion="false"
                         :enable-live-autocompletion="false"
                         :enable-snippets="false"
              ></AceEditor>
              <!--              <el-input type="textarea" v-model="result" style="height: 100%;"></el-input>-->
            </div>
          </el-splitter-panel>
        </el-splitter>

      </el-row>
    </el-main>


    <!--    <el-input v-model="form.value.whiteList"></el-input>-->

  </el-container>
</template>

<style scoped lang="scss">
:deep(textarea) {
  height: 100%;
}

</style>