<script setup>
import * as echarts from 'echarts'
import {countInfo} from "@/api/hrm/report.js"
import {Pear} from "@element-plus/icons-vue";

const echartsRef = ref(null);
let echartInstance = null;
const loading = ref(false);

const options = ref({
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'cross',
      crossStyle: {
        color: '#999'
      }
    }
  },
  toolbox: {
    feature: {
      dataView: {show: false, readOnly: false},
      magicType: {show: true, type: ['line', 'bar']},
      restore: {show: true},
      saveAsImage: {show: true}
    }
  },
  legend: {
    data: ['失败用例', '成功用例', '通过率']
  },
  xAxis: [
    {
      type: 'category',
      data: [],
      axisPointer: {
        type: 'shadow'
      }
    }
  ],
  yAxis: [
    {
      type: 'value',
      name: '个数',
      min: 0,
      max: 100,
      interval: 10,
      axisLabel: {
        formatter: '{value} '
      }
    },
    {
      type: 'value',
      name: '成功率',
      min: 0,
      max: 100,
      interval: 10,
      axisLabel: {
        formatter: '% {value}'
      }
    }
  ],
  series: [
    {
      name: '失败用例',
      type: 'bar',
      data: [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    },
    {
      name: '通过率',
      type: 'line',
      yAxisIndex: 1,
      data: [0, 0, 90, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    },
    {
      name: '成功用例',
      type: 'bar',
      data: [0, 0, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    }
  ]
});

const responseData = ref({});

let option1 = {
  title: {
    text: 'ECharts 入门示例'
  },
  tooltip: {},
  legend: {
    data: ['销量']
  },
  xAxis: {
    data: ['衬衫', '羊毛衫', '雪纺衫', '裤子', '高跟鞋', '袜子']
  },
  yAxis: {},
  series: [{
    name: '销量',
    type: 'bar',
    data: [5, 20, 36, 10, 10, 20]
  }]
}


function get_date_xAxis() {
  let data = [];
  for (var i = 0; i < 12; i++) {
    data[i] = getDay(i)
  }
  return data.reverse();
}

function getDay(day) {
  let today = new Date();
  let targetday_milliseconds = today.getTime() + 1000 * 60 * 60 * 24 * day * -1;
  today.setTime(targetday_milliseconds); //注意，这行是关键代码
  let tYear = today.getFullYear();
  let tMonth = today.getMonth();
  let tDate = today.getDate();
  tMonth = doHandleMonth(tMonth + 1);
  tDate = doHandleMonth(tDate);
  return tYear + "-" + tMonth + "-" + tDate;
}

function doHandleMonth(month) {
  let m = month;
  if (month.toString().length === 1) {
    m = "0" + month;
  }
  return m;
}

onMounted(async () => {
  loading.value = true;
  countInfo().then((res) => {

    let data = res.data;
    responseData.value = data;
    let pass = data.total.pass;
    let fail = data.total.fail;
    // let total = data.total;
    let pass_rate = data.total.percent;
    let xAxis_data = get_date_xAxis();
    options.value.xAxis[0].data = xAxis_data;
    options.value.series[0].data = fail;
    options.value.series[1].data = pass_rate;
    options.value.series[2].data = pass;


    let max_fail = Math.max.apply(null, options.value.series[0].data);
    let max_pass = Math.max.apply(null, options.value.series[2].data);

    if (Math.max(max_fail, max_pass) > 100) {
      options.value.yAxis[0].max = Math.max(max_fail, max_pass) + 10;
      options.value.yAxis[0].interval = parseInt(Math.max(max_fail, max_pass) / 10);
    }

    // await nextTick();
    echartInstance = echarts.init(echartsRef.value);
    echartInstance.setOption(options.value, true);
  }).finally(() => {
    loading.value = false;
  });


  window.addEventListener('resize', () => {
    echartInstance.resize()
  }, false);

});

onUnmounted(() => {
  if (echartInstance != null && echartInstance.dispose) {
    echartInstance.dispose();
  }

});


</script>

<template>
  <!--  <div>{{options}}</div>-->
  <div style="width: 100%;height: 100%;display: flex;flex-direction: column;align-items: stretch;padding-top: 10px"
       v-loading="loading">
    <el-row justify="space-evenly">
      <el-card style="width: 20%" shadow="hover">
        <div style="display: flex;flex-direction: row">
          <div>
            <el-icon size="50" color="#2BE5BFFF" style="color:#efd110;">
              <UserFilled></UserFilled>
            </el-icon>
          </div>
          <div>
            <el-statistic :value="responseData.projectCount">
              <template #title>
                <div style="display: inline-flex; align-items: center">
                  项目
                  <el-tooltip
                      effect="dark"
                      content="项目总数"
                      placement="top"
                  >
                    <el-icon style="margin-left: 4px" :size="12">
                      <Warning/>
                    </el-icon>
                  </el-tooltip>
                </div>
              </template>
            </el-statistic>
          </div>
        </div>
      </el-card>
      <el-card style="width: 20%" shadow="hover">
        <div style="display: flex">
          <div>
            <el-icon size="50" color="#EA5959FF">
              <HelpFilled></HelpFilled>
            </el-icon>
          </div>
          <div>
            <el-statistic :value="responseData.moduleCount">
              <template #title>
                <div style="display: inline-flex; align-items: center">
                  模块
                  <el-tooltip
                      effect="dark"
                      content="模块总数"
                      placement="top"
                  >
                    <el-icon style="margin-left: 4px" :size="12">
                      <Warning/>
                    </el-icon>
                  </el-tooltip>
                </div>
              </template>
            </el-statistic>
          </div>
        </div>
      </el-card>
      <el-card style="width: 20%" shadow="hover">
        <div style="display:flex;">
          <div>
            <el-icon size="50" color="#19C6EFFF">
              <Histogram></Histogram>
            </el-icon>
          </div>
          <div>
            <el-statistic :value="responseData.caseCount">
              <template #title>
                <div style="display: inline-flex; align-items: center">
                  用例
                  <el-tooltip
                      effect="dark"
                      content="用例总数"
                      placement="top"
                  >
                    <el-icon style="margin-left: 4px" :size="12">
                      <Warning/>
                    </el-icon>
                  </el-tooltip>
                </div>
              </template>
            </el-statistic>
          </div>
        </div>

      </el-card>
      <el-card style="width: 20%" shadow="hover">
        <div style="display: flex">
          <div>
            <el-icon size="50" color="#EFD110FF">
              <Operation></Operation>
            </el-icon>
          </div>
          <div>
            <el-statistic :value="responseData.suiteCount">
              <template #title>
                <div style="display: inline-flex; align-items: center">
                  套件
                  <el-tooltip
                      effect="dark"
                      content="套件总数"
                      placement="top"
                  >
                    <el-icon style="margin-left: 4px" :size="12">
                      <Warning/>
                    </el-icon>
                  </el-tooltip>
                </div>
              </template>
            </el-statistic>
          </div>
        </div>
      </el-card>
    </el-row>
    <div class="echarts" ref="echartsRef" style="width: 100%;flex-grow: 1">

    </div>
  </div>

</template>

<style scoped lang="scss">
.echarts {
  width: 100%;
  height: 100%;
}
</style>