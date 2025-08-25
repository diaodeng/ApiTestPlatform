<script setup>
import EditLabel from "@/components/hrm/common/edite-label.vue";
import StepDetail from "@/components/hrm/case/step-detail.vue";
import {randomString} from "@/utils/tools.js";
import {initStepData} from "@/components/hrm/data-template.js";
import {CaseRunStatusEnum} from "@/components/hrm/enum.js";
import {useResizeObserver} from "@vueuse/core";
import Sortable from "sortablejs";
import SplitWindow from "@/components/hrm/common/split-window.vue";

const testStepsData = defineModel('testStepsData', {required: true});
const props = defineProps(["stepsHeight"]);

const loading = ref({
  switchStep: false
});
// const {proxy} = getCurrentInstance();
const activeTestStepName = ref(0);
const tabsHeight = ref(0);
const tabsScrollRef = ref();
const extendStepTabLabel = ref(true);
const tabsRef = ref();
const currentStepDataRef = ref(JSON.parse(JSON.stringify(initStepData)));

// const {sys_normal_disable} = proxy.useDict("sys_normal_disable");
// const {hrm_data_type} = proxy.useDict("hrm_data_type");
// const {sys_request_method} = proxy.useDict("sys_request_method");


function editTabs(action, paneName, tapType, initTabData) {
  if (action === "remove") {
    const oldActiveStep = activeTestStepName.value;

    const currentTabIndex = paneName !== undefined ? paneName : activeTestStepName.value;

    testStepsData.value.splice(currentTabIndex, 1);
    if (testStepsData.value.length <= 0) {
      let tmpStepData = JSON.parse(JSON.stringify(initStepData));
      tmpStepData.step_id = randomString(10);
      testStepsData.value.push(tmpStepData);
      activeTestStepName.value = 0;
      return;
    }

    if (oldActiveStep >= currentTabIndex) {
      if (oldActiveStep === 0) {
        activeTestStepName.value = 0;
        return;
      }
      activeTestStepName.value = oldActiveStep - 1;
    }

  } else if (action === "add") {

    let newTabName = paneName !== undefined ? paneName + 1 : activeTestStepName.value + 1;

    testStepsData.value.splice(newTabName, 0, initTabData)
    activeTestStepName.value = newTabName
  } else if (action === "copy") {
    const currentTabIndex = paneName !== undefined ? paneName : activeTestStepName.value;
    const currentTabData = JSON.parse(JSON.stringify(toRaw(testStepsData.value[currentTabIndex])));
    currentTabData.step_id = randomString(10);
    currentTabData.name = currentTabData.name + "-副本";

    const newTabName = currentTabIndex + 1;

    testStepsData.value.splice(newTabName, 0, currentTabData)
    activeTestStepName.value = newTabName
  } else if (action === "statuChange") {
    const currentTabIndex = paneName !== undefined ? paneName : activeTestStepName.value;
    console.log(currentTabIndex);
    console.log(testStepsData.value[currentTabIndex].enable)
    console.log(!testStepsData.value[currentTabIndex].enable)
    testStepsData.value[currentTabIndex].enable = !testStepsData.value[currentTabIndex].enable;
    console.log(testStepsData.value[currentTabIndex].enable)
  } else {
    console.log("other")
  }
}


useResizeObserver(tabsScrollRef, (entries) => {
  const entry = entries[0]
  const {width, height} = entry.contentRect;
  nextTick(() => {
    tabsHeight.value = height;
  });

});

function setpTabsSortAble() {//行拖拽
  const tabsNav = tabsRef.value;
  new Sortable(tabsNav, {
    animation: 150,
    handle: ".step-tab-label .step-type-icon",
    sort: true,
    onEnd: (evt) => {

      const stepLength = testStepsData.value.length;
      let oldIndex = evt.oldIndex;
      if (oldIndex < 0) {
        oldIndex = 0;
      } else if (oldIndex > stepLength) {
        oldIndex = stepLength;
      }
      let newIndex = evt.newIndex;

      if (newIndex < 0) {
        newIndex = 0;
      } else if (newIndex > stepLength) {
        newIndex = stepLength;
      }
      // console.log("步骤数量：" + testStepsData.value.length + " 当前位置： " + oldIndex + " 新位置：" + newIndex);
      if (oldIndex === newIndex) {
        return;
      }

      const oldItem = testStepsData.value[oldIndex];
      testStepsData.value.splice(oldIndex, 1);
      testStepsData.value.splice(newIndex, 0, oldItem);
    },
  });
}

function clickStep(stepIndex, event) {
  let currentElement = undefined;
  if (event && event.nodeType === 1) {
    currentElement = event;
  } else {
    currentElement = event.currentTarget;
  }
  if (!currentElement) {
    return
  }
  loading.value.switchStep = true;
  for (const child of currentElement.parentElement.children) {
    child.classList.remove("selected-list");
  }
  currentElement.classList.add("selected-list");

  currentStepDataRef.value = testStepsData.value[stepIndex];
  loading.value.switchStep = false;

}

onMounted(() => {
  nextTick(() => {
    setpTabsSortAble();
    clickStep(0, tabsRef?.value.children[0]);
  });
});

watch(() => testStepsData.value, (newValue) => {
  nextTick(() => {
    clickStep(0, tabsRef?.value.children[0]);
  });
});

</script>

<template>
  <el-scrollbar :height="stepsHeight" ref="tabsScrollRef">
    <div :style="{height: tabsHeight + 'px'}">
      <split-window>
        <template #left>
          <ul ref="tabsRef"
              :disabled="loading.switchStep"
              :style="{
              height: stepsHeight + 'px',
              listStyle: 'none',
              paddingLeft: 0 +'px',
              marginLeft: 0 + 'px',
              marginTop: 0+ 'px',
              marginBottom: 0+ 'px',
              overflowY: 'auto'}"
              v-loading="loading.switchStep">
            <li v-for="(step, index) in testStepsData" @click="clickStep(index, $event)"
                :key="step.step_id"
                style="white-space: nowrap">
              <el-link :underline="false">
                <el-button style="margin: 0;padding: 0;" type="primary" circle size="small">{{ index + 1 }}</el-button>
                <EditLabel v-model:name-text="testStepsData[index].name"
                           :notify="step.result && step.result.status !== CaseRunStatusEnum.passed.value"
                           v-model:enable="testStepsData[index].enable"
                           :index-key="index"
                           :type="step.step_type"
                           :is-show="extendStepTabLabel"
                           @edit-element="editTabs"
                           class="step-tab-label"></EditLabel>
              </el-link>

            </li>
          </ul>
        </template>
        <template #right>
          <div style="margin-left: 5px">
            <Suspense>
              <StepDetail v-model:step-data="currentStepDataRef"
                          :tabs-height="stepsHeight"
                          v-model:loading="loading.switchStep"
              ></StepDetail>
              <template #fallback>加载中。。。</template>
            </Suspense>
          </div>
        </template>
      </split-window>
    </div>
  </el-scrollbar>

</template>

<style scoped lang="scss">
.selected-list {
  background-color: rgba(12, 174, 141, 0.2);
  border-radius: 10px;
}
</style>