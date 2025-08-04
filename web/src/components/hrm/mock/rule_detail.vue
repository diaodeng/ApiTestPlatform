<template>
  <el-dialog fullscreen :title='ruleForm.name'
             v-model="openDialog"
             :before-close="beforeCloseDialog"
             append-to-body>
    <div class="rule-editor">
      <el-form :model="ruleForm" label-width="120px">
        <!-- 基础信息 -->
        <el-card style="margin-bottom: 10px" header="基础配置">
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="规则名称" required>
                <el-input v-model="ruleForm.name"/>
              </el-form-item>
            </el-col>
            <el-col :span="8" v-if="false">
              <el-form-item label="所属项目">
                <el-select v-model="ruleForm.project_id">
                  <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id"/>
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="优先级">
                <el-input-number v-model="ruleForm.priority" :min="1" :max="100"/>
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="mock数据">
                <el-select v-model="ruleForm.mockType">
                  <el-option :value="1" label="仅响应"/>
                  <el-option :value="2" label="仅请求"/>
                  <el-option :value="3" label="请求及响应"/>
                  <el-option :value="4" label="原始请求"/>
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="请求路径" required>
                <el-input v-model="ruleForm.path" placeholder="/api/users"/>
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="HTTP方法">
                <el-select v-model="ruleForm.method">
                  <el-option value="GET"/>
                  <el-option value="POST"/>
                  <el-option value="PUT"/>
                  <el-option value="DELETE"/>
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="启用规则">
                <el-radio-group v-model="ruleForm.status">
                  <el-radio :value="1">禁用</el-radio>
                  <el-radio :value="2">启用</el-radio>
                </el-radio-group>
              </el-form-item>
            </el-col>
          </el-row>
        </el-card>

        <!-- 匹配条件 -->
        <el-card style="margin-bottom: 10px" header="匹配条件">
          <template #header>
            匹配条件
            <el-button @click="addCondition" type="primary" icon="Plus">添加条件</el-button>
          </template>
          <div v-for="(cond, idx) in ruleForm.ruleCondition" :key="idx" class="condition-item">
            <el-row :gutter="10">
              <el-col :span="5">
                <el-select v-model="cond.source" placeholder="参数来源">
                  <el-option label="Query参数" value="query"/>
                  <el-option label="请求头" value="header"/>
                  <el-option label="请求体" value="body"/>
                  <el-option label="路径参数" value="path"/>
                </el-select>
              </el-col>

              <el-col :span="5">
                <el-input v-model="cond.key" placeholder="参数名"/>
              </el-col>

              <el-col :span="4">
                <el-select v-model="cond.operator" placeholder="操作符">
                  <el-option label="等于 =" value="="/>
                  <el-option label="不等于 !=" value="!="/>
                  <el-option label="大于 >" value=">"/>
                  <el-option label="小于 <" value="<"/>
                  <el-option label="包含 contains" value="contains"/>
                  <el-option label="正则 regex" value="regex"/>
                  <el-option label="正则 regex_search" value="regex_search"/>
                  <el-option label="存在 exists" value="exists"/>
                </el-select>
              </el-col>

              <el-col :span="5">
                <el-input
                    v-model="cond.value"
                    :disabled="cond.operator === 'exists'"
                    placeholder="匹配值"
                />
              </el-col>

              <el-col :span="3">
                <el-select v-model="cond.data_type" placeholder="类型">
                  <el-option label="字符串" value="str"/>
                  <el-option label="数字" value="number"/>
                  <el-option label="布尔值" value="bool"/>
                </el-select>
              </el-col>

              <el-col :span="2">
                <el-button @click="removeCondition(idx)" type="danger" icon="Delete"/>
              </el-col>
            </el-row>
          </div>
        </el-card>

        <!-- 响应配置 -->
        <el-card header="响应信息配置">
          <template #header>
            响应信息配置
            <el-select
                v-model="ruleForm.response.ruleResponseId"
                filterable
                remote
                reserve-keyword
                placeholder="输入响应名称关键字"
                remote-show-suffix
                :remote-method="getResponseList"
                :loading="doing.loadingResponseList"
                style="width: 240px"
                @change="getResponseDetail"
            >
              <el-option
                  v-for="item in ruleResponseData"
                  :key="item.ruleResponseId"
                  :label="item.name"
                  :value="item.ruleResponseId"
              />
            </el-select>
            <el-text style="margin-left: 10px">名称</el-text>
            <el-input v-model="ruleForm.response.name" style="width: 120px"/>
            <el-text style="margin-left: 10px">标签</el-text>
            <el-input v-model="ruleForm.response.responseTag" style="width: 120px"/>
            <el-button style="margin-left: 5px"
                       @click="openCopyResponseDialog = !openCopyResponseDialog"
                       type="primary"
                       :disabled="!ruleForm.ruleId || doing.saving"
                       title="另存为">另存为
            </el-button>

            <el-button style="margin-left: 5px" @click="addResponse" type="success"
                       :disabled="!ruleForm.ruleId || doing.saving"
                       title="保存">保存
            </el-button>
            <el-button style="margin-left: 5px" @click="setRuleDefaultResponse" type="success"
                       :disabled="!ruleForm.ruleId || doing.saving"
                       title="设置为默认响应">设置默认响应
            </el-button>
            <el-button style="margin-left: 5px" @click="getConditionResponse" type="success"
                       :disabled="!ruleForm.ruleId || doing.saving"
                       title="查看当前规则的响应">匹配
            </el-button>
          </template>
          <el-card style="margin-bottom: 5px" header="响应匹配条件">
            <template #header>
              响应匹配条件
              <el-button @click="addResponseCondition" type="primary" icon="Plus">添加条件</el-button>
            </template>
            <div v-for="(cond, idx) in ruleForm.response?.responseCondition" :key="idx" class="condition-item">
              <el-row :gutter="10">
                <el-col :span="5">
                  <el-select v-model="cond.source" placeholder="参数来源">
                    <el-option label="Query参数" value="query"/>
                    <el-option label="请求头" value="header"/>
                    <el-option label="请求体" value="body"/>
                    <el-option label="路径参数" value="path"/>
                  </el-select>
                </el-col>

                <el-col :span="5">
                  <el-input v-model="cond.key" placeholder="参数名"/>
                </el-col>

                <el-col :span="4">
                  <el-select v-model="cond.operator" placeholder="操作符">
                    <el-option label="等于 =" value="="/>
                    <el-option label="不等于 !=" value="!="/>
                    <el-option label="大于 >" value=">"/>
                    <el-option label="小于 <" value="<"/>
                    <el-option label="包含 contains" value="contains"/>
                    <el-option label="正则 regex" value="regex"/>
                    <el-option label="存在 exists" value="exists"/>
                  </el-select>
                </el-col>

                <el-col :span="5">
                  <el-input
                      v-model="cond.value"
                      :disabled="cond.operator === 'exists'"
                      placeholder="匹配值"
                  />
                </el-col>

                <el-col :span="3">
                  <el-select v-model="cond.data_type" placeholder="类型">
                    <el-option label="字符串" value="str"/>
                    <el-option label="数字" value="number"/>
                    <el-option label="布尔值" value="bool"/>
                  </el-select>
                </el-col>

                <el-col :span="2">
                  <el-button @click="removeResponseCondition(idx)" type="danger" icon="Delete"/>
                </el-col>
              </el-row>
            </div>
          </el-card>
          <el-card header="响应配置">
            <template #header>
              响应配置
              <el-button @click="addHeader" type="primary" icon="Plus">添加响应头</el-button>
            </template>
            <el-row :gutter="20">
              <el-col :span="6">
                <el-form-item label="状态码">
                  <el-input-number v-model="ruleForm.response.statusCode" :min="100" :max="599"/>
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="延迟(ms)">
                  <el-input-number v-model="ruleForm.response.delay" :min="0" :max="10000"/>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="响应头">
              <div v-for="(header, idx) in ruleForm.response.headersTemplate" :key="idx" class="header-item">
                <el-input v-model="header.key" placeholder="Header名" style="width: 200px;"/>
                <span style="margin: 0 10px;">:</span>
                <el-input v-model="header.value" placeholder="Header值" style="width: 300px;"/>
                <el-button @click="removeHeader(idx)" type="danger" icon="Delete"/>
              </div>

            </el-form-item>

            <el-form-item label="响应体模板">
              <el-alert type="info" show-icon style="margin-bottom: 10px;">
                <div v-pre>
                  支持模板语法： "{{ request.args.id }}" | "{{ random.int(1,100) }}" | "{{ time.iso }}"
                </div>
              </el-alert>
              <el-input
                  v-model="ruleForm.response.bodyTemplate"
                  type="textarea"
                  :rows="10"
                  placeholder="响应内容（支持JSON/XML/Text）"
              />
            </el-form-item>
          </el-card>

        </el-card>

        <div class="form-actions">
          <el-button type="primary" @click="saveRule" :loading="doing.saving">保存规则</el-button>
          <el-button @click="resetForm">重置</el-button>
        </div>
      </el-form>
    </div>
  </el-dialog>

  <el-dialog title='复制mock规则响应'
             v-model="openCopyResponseDialog">
    <el-input v-model="copyResponseName" placeholder="请输入响应名称"></el-input>
    <template #footer>
      <el-button @click="saveAsResponse" type="primary">保存</el-button>
    </template>

  </el-dialog>

  <el-dialog v-model="isShow.dialogConditionMatchVisible" title="当前条件匹配到的响应" width="800">
    <el-table :data="matchedData">
      <el-table-column property="name" label="名称"/>
      <el-table-column property="responseTag" label="标签" width="200" />
      <el-table-column property="isDefault" label="默认值" width="80" />
    </el-table>
  </el-dialog>
</template>

<script setup>
import {reactive} from 'vue'
import {
  addMockRule,
  getMockRule,
  updateMockRule,
  listMockRuleResponse,
  getRuleResponseDetail,
  addResponseDetail,
  editResponseDetail, listMockRuleResponseByCondition, setDefaultResponse
} from "@/api/hrm/mock.js"
import {ElMessage, ElMessageBox} from "element-plus";
import {initMockRuleFormData} from "@/components/hrm/data-template.js";

// 初始表单结构
const initialForm = () => (JSON.parse(JSON.stringify(initMockRuleFormData)));

const openDialog = defineModel("openDialog");
const props = defineProps(["ruleId", "isAdd"]);
const doing = reactive({
  saving: false,
  loadingDetail: false,
  loadingResponseList: false,
});
const isShow = reactive({
  dialogConditionMatchVisible: false,
});

const ruleForm = reactive(initialForm())
const projects = reactive([{id: 111, name: 'test'}]) // 从API获取项目列表
const ruleResponseData = ref([]);
const openCopyResponseDialog = ref(false);
const copyResponseName = ref('');
const matchedData = ref([]);  // 按条件匹配到的响应数据

const selectResponseData = () => {
  console.log(ruleForm.response.ruleResponseId);
  return typeof ruleForm.response.ruleResponseId;
};

function beforeCloseDialog(done) {
  // if (props.dataType === HrmDataTypeEnum.run_detail || !dataChange.value) {
  //   done();
  //   return;
  // }

  ElMessageBox.confirm("退出前请保存数据", "确认退出", {
    type: "warning",
    cancelButtonText: "返回保存",
    confirmButtonText: "继续退出"
  }).then(() => {
    // resetForm();
    done();
  }).catch(() => {
  });
}

// 条件操作
const addCondition = () => {
  ruleForm.ruleCondition.push({
    source: 'query',
    key: '',
    operator: '=',
    value: '',
    data_type: 'str'
  })
}

// 响应条件操作
const addResponseCondition = () => {
  ruleForm.response?.responseCondition.push({
    source: 'query',
    key: '',
    operator: '=',
    value: '',
    data_type: 'str'
  });
}

const removeCondition = (index) => {
  ruleForm.ruleCondition.splice(index, 1);
}

const removeResponseCondition = (index) => {
  ruleForm.response.responseCondition.splice(index, 1);
}

// 响应头操作
const addHeader = () => {
  ruleForm.response.headersTemplate.push({key: '', value: ''});
}

const removeHeader = (index) => {
  ruleForm.response.headersTemplate.splice(index, 1);
}

// 保存规则
const saveRule = async () => {
  // 调用API保存规则
  doing.saving = true;
  if (ruleForm.ruleId) {
    await updateMockRule(ruleForm).then((res) => {
      ElMessage.success("更新成功");
    }).finally(() => {
      doing.saving = false;
    });
  } else {
    await addMockRule(ruleForm).then(response => {
      Object.assign(ruleForm, response.data);
      ElMessage.success("保存成功");
    }).catch((error) => {

    }).finally(() => {
      doing.saving = false;
    });
  }
}

const setRuleDefaultResponse = async () => {
  ElMessageBox.confirm("确认将当前响应设置为默认响应吗？", "确认", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    doing.saving = true;
    if (!ruleForm.response.ruleId) {
      return;
    }
    setDefaultResponse(ruleForm.response).then((res) => {
      ElMessage.success("更新成功");
    }).finally(() => {
      doing.saving = false;
    }).catch((error) => {
      ElMessage.error(error.message);
    });
  }).catch(() => {
  });


}

const getConditionResponse = async () => {
  doing.saving = true;
  if (!ruleForm.response.ruleId) {
    return;
  }
  await listMockRuleResponseByCondition(ruleForm.response).then((res) => {
    matchedData.value = res.data;
    isShow.dialogConditionMatchVisible = true;
  }).finally(() => {
    doing.saving = false;
  });
}

const getResponseList = async (name) => {

  if (!ruleForm.ruleId) {
    return;
  }
  doing.loadingResponseList = true;
  await listMockRuleResponse({
    ruleId: ruleForm.ruleId,
    name: name,
  }).then((response) => {
    ruleResponseData.value = response.data;
  }).catch((error) => {

  }).finally(() => {
    doing.loadingResponseList = false;
  });

}

const getResponseDetail = async (ruleId) => {
  console.log(ruleForm.response.ruleResponseId);
  console.log(typeof ruleForm.response.ruleResponseId);
  if (!ruleId) {
    return;
  }
  doing.loadingDetail = true;
  await getRuleResponseDetail({
    ruleResponseId: ruleId,
  }).then((response) => {
    ruleForm.response = response.data;
  }).catch((error) => {

  }).finally(() => {
    doing.loadingDetail = false;
  });
}

const addResponse = async () => {
  if (!ruleForm.ruleId) {
    return;
  }
  doing.loadingDetail = true;
  let copyData = JSON.parse(JSON.stringify(ruleForm.response));
  copyData.ruleId = ruleForm.ruleId;
  if (!copyData.ruleResponseId) {
    copyData.ruleResponseId = null;
    copyData.id = null;

    await addResponseDetail(copyData).then((response) => {
      ruleForm.response = response.data;
      ElMessage.success("mock规则响应保存成功");
    }).catch((error) => {

    }).finally(() => {
      doing.loadingDetail = false;
      copyResponseName.value = "";
    });
  } else {
    await editResponseDetail(copyData).then((response) => {
      // ruleForm.response = response.data;
      ElMessage.success("mock规则响应更新成功");
    }).catch((error) => {

    }).finally(() => {
      doing.loadingDetail = false;
      copyResponseName.value = "";
    });
  }


}

const saveAsResponse = async () => {
  if (!ruleForm.ruleId) {
    return;
  }
  doing.loadingDetail = true;
  let copyData = JSON.parse(JSON.stringify(ruleForm.response));
  copyData.ruleId = ruleForm.ruleId;
  copyData.ruleResponseId = null;
  copyData.id = null;
  copyData.name = copyResponseName.value;
  await addResponseDetail(copyData).then((response) => {
    ruleForm.response = response.data;
    openCopyResponseDialog.value = false;
    ElMessage.success("更新成功");
  }).catch((error) => {

  }).finally(() => {
    doing.loadingDetail = false;
    copyResponseName.value = "";
  });
}

const resetForm = () => {
  Object.assign(ruleForm, JSON.parse(JSON.stringify(initMockRuleFormData)));
  ruleForm.id = null;
  ruleForm.ruleId = null;
}

onBeforeMount(() => {

});

watch(openDialog, (value, oldValue, onCleanup) => {
  if (props.ruleId && !props.isAdd) {
    doing.loadingDetail = true;
    getMockRule(props.ruleId).then((response) => {
      Object.assign(ruleForm, response.data);
    }).finally(() => {
      doing.loadingDetail = false;
    });
  } else {
    resetForm();
  }
})

onMounted(() => {


})
</script>

<style scoped>
.rule-editor {
  padding: 20px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.condition-item, .header-item {
  margin-bottom: 15px;
  padding: 10px;
  border: 1px solid #eee;
  border-radius: 4px;
}

.form-actions {
  margin-top: 20px;
  text-align: center;
}
</style>