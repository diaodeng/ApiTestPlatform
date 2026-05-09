<template>
  <el-dialog
    fullscreen
    :title="ruleForm.name"
    v-model="openDialog"
    :before-close="beforeCloseDialog"
    append-to-body
  >
    <div class="rule-editor">
      <el-form :model="ruleForm" label-width="120px">
        <!-- 基础信息 -->
        <el-card style="margin-bottom: 10px" header="基础配置">
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="规则名称" required>
                <el-input v-model="ruleForm.name" />
              </el-form-item>
            </el-col>
            <el-col :span="8" v-if="false">
              <el-form-item label="所属项目">
                <el-select v-model="ruleForm.project_id">
                  <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="优先级">
                <el-input-number v-model="ruleForm.priority" :min="1" :max="100" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="mock数据">
                <el-select v-model="ruleForm.mockType">
                  <el-option :value="1" label="仅响应" />
                  <el-option :value="2" label="仅请求" />
                  <el-option :value="3" label="请求及响应" />
                  <el-option :value="4" label="原始请求" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="请求路径" required>
                <el-input v-model="ruleForm.path" placeholder="/api/users" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="HTTP方法">
                <el-select v-model="ruleForm.method">
                  <el-option value="GET" />
                  <el-option value="POST" />
                  <el-option value="PUT" />
                  <el-option value="DELETE" />
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

        <MockConditionEditor
          style="margin-bottom: 20px"
          v-model="ruleForm.ruleCondition"
          title="匹配条件"
          add-button-text="添加条件"
        ></MockConditionEditor>

        <MockResponseEditor v-model="ruleForm.response">
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
            <el-input v-model="ruleForm.response.name" style="width: 120px" />
            <el-text style="margin-left: 10px">标签</el-text>
            <el-input v-model="ruleForm.response.responseTag" style="width: 120px" />
            <el-button
              style="margin-left: 5px"
              @click="openCopyResponseDialog = !openCopyResponseDialog"
              type="primary"
              :disabled="!ruleForm.ruleId || doing.saving"
              title="另存为"
              >另存为
            </el-button>

            <el-button
              style="margin-left: 5px"
              @click="addResponse"
              type="success"
              :disabled="!ruleForm.ruleId || doing.saving"
              title="保存"
              >保存
            </el-button>
            <el-button
              style="margin-left: 5px"
              @click="setRuleDefaultResponse(ruleForm.response.ruleResponseId)"
              type="success"
              :disabled="!ruleForm.ruleId || doing.saving"
              title="设置为默认响应"
              >设置为默认响应
            </el-button>
            <el-button
              style="margin-left: 5px"
              @click="getConditionResponse"
              type="success"
              :disabled="!ruleForm.ruleId || doing.saving || doing.loadingResponseList"
              title="查看当前规则的响应"
              >匹配
            </el-button>
            <el-button
              style="margin-left: 5px"
              @click="showResponseListDialog"
              type="primary"
              :disabled="!ruleForm.ruleId || doing.saving"
              title="打开响应列表弹窗"
              >响应列表
            </el-button>
          </template>
        </MockResponseEditor>

        <div class="form-actions">
          <el-button type="primary" @click="saveRule" :loading="doing.saving">保存规则</el-button>
          <el-button @click="resetForm" v-if="!ruleForm.ruleId && !doing.saving">重置</el-button>
        </div>
      </el-form>
    </div>
  </el-dialog>

  <el-dialog
    title="复制mock规则响应"
    v-model="openCopyResponseDialog"
    append-to-body
    destroy-on-close
  >
    <el-input v-model="copyResponseName" placeholder="请输入响应名称"></el-input>
    <template #footer>
      <el-button @click="saveAsResponse" type="primary">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="isShow.dialogConditionMatchVisible"
    title="当前条件匹配到的响应"
    width="800"
    append-to-body
    destroy-on-close
  >
    <template #header>
      {{ ruleForm.ruleId }}--{{ ruleForm.name }}
      <el-button @click="getConditionResponse" type="primary" :disabled="doing.loadingResponseList"
        >刷新列表</el-button
      >
    </template>
    <el-table :data="matchedData">
      <el-table-column property="name" label="名称" />
      <el-table-column property="responseTag" label="标签" width="200" />
      <el-table-column property="priority" label="优先级" width="80">
        <template #default="scope">
          <el-input
            v-model="scope.row.priority"
            type="number"
            @blur="setResponsePriority(scope.row)"
            min="1"
            max="999"
            step="1"
          />
        </template>
      </el-table-column>
      <el-table-column property="isDefault" label="默认值" width="80" />
      <el-table-column label="操作" width="120">
        <template #default="scope">
          <el-button
            type="primary"
            :disabled="!!scope.row.isDefault || doing.saving"
            @click="setRuleDefaultResponse(scope.row.ruleResponseId)"
            >设为默认值</el-button
          >
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>

  <MockResponseListDialog
    v-model:open-dialog="openResponseListDialog"
    :rule-id="ruleForm.ruleId"
    :rule-name="ruleForm.name"
  ></MockResponseListDialog>
</template>

<script setup>
  import { reactive } from 'vue';
  import {
    addMockRule,
    getMockRule,
    updateMockRule,
    listMockRuleResponse,
    getRuleResponseDetail,
    addResponseDetail,
    editResponseDetail,
    listMockRuleResponseByCondition,
    setDefaultResponse,
    editResponsePriority,
  } from '@/api/hrm/mock.js';
  import MockConditionEditor from '@/components/hrm/mock/condition_editor.vue';
  import MockResponseEditor from '@/components/hrm/mock/response_editor.vue';
  import MockResponseListDialog from '@/components/hrm/mock/response_list_dialog.vue';
  import { ElMessage, ElMessageBox } from 'element-plus';
  import { initMockRuleFormData } from '@/components/hrm/data-template.js';

  // 初始表单结构
  const initialForm = () => JSON.parse(JSON.stringify(initMockRuleFormData));

  const openDialog = defineModel('openDialog');
  const props = defineProps(['ruleId', 'isAdd']);
  const doing = reactive({
    saving: false,
    loadingDetail: false,
    loadingResponseList: false,
  });
  const isShow = reactive({
    dialogConditionMatchVisible: false,
  });

  const ruleForm = reactive(initialForm());
  const projects = reactive([{ id: 111, name: 'test' }]); // 从API获取项目列表
  const ruleResponseData = ref([]);
  const openCopyResponseDialog = ref(false);
  const copyResponseName = ref('');
  const matchedData = ref([]); // 按条件匹配到的响应数据
  const openResponseListDialog = ref(false);

  function beforeCloseDialog(done) {
    // if (props.dataType === HrmDataTypeEnum.run_detail || !dataChange.value) {
    //   done();
    //   return;
    // }

    ElMessageBox.confirm('退出前请保存数据', '确认退出', {
      type: 'warning',
      cancelButtonText: '返回保存',
      confirmButtonText: '继续退出',
    })
      .then(() => {
        // resetForm();
        done();
      })
      .catch(() => {});
  }

  // 保存规则
  const saveRule = async () => {
    // 调用API保存规则
    doing.saving = true;
    if (ruleForm.ruleId) {
      await updateMockRule(ruleForm)
        .then((res) => {
          ElMessage.success('更新成功');
        })
        .finally(() => {
          doing.saving = false;
        });
    } else {
      await addMockRule(ruleForm)
        .then((response) => {
          Object.assign(ruleForm, response.data);
          ElMessage.success('保存成功');
        })
        .catch((error) => {})
        .finally(() => {
          doing.saving = false;
        });
    }
  };

  const setRuleDefaultResponse = async (responseId) => {
    ElMessageBox.confirm('确认将当前响应设置为默认响应吗？', '确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
      .then(() => {
        doing.saving = true;
        if (!ruleForm.response.ruleId) {
          doing.saving = false;
          return;
        }
        let data = {
          ruleResponseId: responseId,
          ruleId: ruleForm.ruleId,
          responseCondition: ruleForm.response.responseCondition,
        };
        setDefaultResponse(data)
          .then((res) => {
            if (
              ruleForm.response &&
              ruleForm.response.ruleResponseId &&
              ruleForm.response.ruleResponseId === responseId
            ) {
              ruleForm.response.isDefault = 1;
            }
            ElMessage.success('更新成功');
          })
          .finally(() => {
            doing.saving = false;
          })
          .catch((error) => {
            ElMessage.error(error.message);
          });
      })
      .catch(() => {});
  };

  const setResponsePriority = async (row) => {
    doing.saving = true;
    if (!row.ruleResponseId) {
      doing.saving = false;
      return;
    }
    let data = { ruleResponseId: row.ruleResponseId, priority: row.priority };
    editResponsePriority(data)
      .then((res) => {
        if (
          ruleForm.response &&
          ruleForm.response.ruleResponseId &&
          ruleForm.response.ruleResponseId === row.ruleResponseId
        ) {
          ruleForm.response.priority = row.priority;
        }
        ElMessage.success('更新成功');
      })
      .finally(() => {
        doing.saving = false;
      })
      .catch((error) => {
        ElMessage.error(error.message);
      });
  };

  const getConditionResponse = async () => {
    doing.loadingResponseList = true;
    if (!ruleForm.response.ruleId) {
      doing.loadingResponseList = false;
      return;
    }
    await listMockRuleResponseByCondition(ruleForm.response)
      .then((res) => {
        matchedData.value = res.data;
        isShow.dialogConditionMatchVisible = true;
      })
      .finally(() => {
        doing.loadingResponseList = false;
      });
  };

  const showResponseListDialog = () => {
    if (!ruleForm.ruleId) {
      ElMessage.warning('请先保存规则，再查看响应列表');
      return;
    }
    openResponseListDialog.value = true;
  };

  const getResponseList = async (name) => {
    if (!ruleForm.ruleId) {
      return;
    }
    doing.loadingResponseList = true;
    await listMockRuleResponse({
      ruleId: ruleForm.ruleId,
      name: name,
    })
      .then((response) => {
        ruleResponseData.value = response.data;
      })
      .catch((error) => {})
      .finally(() => {
        doing.loadingResponseList = false;
      });
  };

  const getResponseDetail = async (ruleId) => {
    if (!ruleId) {
      return;
    }
    doing.loadingDetail = true;
    await getRuleResponseDetail({
      ruleResponseId: ruleId,
    })
      .then((response) => {
        ruleForm.response = response.data;
      })
      .catch((error) => {})
      .finally(() => {
        doing.loadingDetail = false;
      });
  };

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

      await addResponseDetail(copyData)
        .then((response) => {
          ruleForm.response = response.data;
          ElMessage.success('mock规则响应保存成功');
        })
        .catch((error) => {})
        .finally(() => {
          doing.loadingDetail = false;
          copyResponseName.value = '';
        });
    } else {
      await editResponseDetail(copyData)
        .then((response) => {
          // ruleForm.response = response.data;
          ElMessage.success('mock规则响应更新成功');
        })
        .catch((error) => {})
        .finally(() => {
          doing.loadingDetail = false;
          copyResponseName.value = '';
        });
    }
  };

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
    await addResponseDetail(copyData)
      .then((response) => {
        ruleForm.response = response.data;
        openCopyResponseDialog.value = false;
        ElMessage.success('更新成功');
      })
      .catch((error) => {})
      .finally(() => {
        doing.loadingDetail = false;
        copyResponseName.value = '';
      });
  };

  const resetForm = () => {
    Object.assign(ruleForm, JSON.parse(JSON.stringify(initMockRuleFormData)));
    ruleForm.id = null;
    ruleForm.ruleId = null;
  };

  onBeforeMount(() => {});

  watch(openDialog, (value, oldValue, onCleanup) => {
    if (props.ruleId && !props.isAdd) {
      doing.loadingDetail = true;
      getMockRule(props.ruleId)
        .then((response) => {
          Object.assign(ruleForm, response.data);
        })
        .finally(() => {
          doing.loadingDetail = false;
        });
    } else {
      resetForm();
    }
  });

  onMounted(() => {});
</script>

<style scoped>
  .rule-editor {
    padding: 20px;
    background: #fff;
    border-radius: 4px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  }

  .condition-item,
  .header-item {
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
