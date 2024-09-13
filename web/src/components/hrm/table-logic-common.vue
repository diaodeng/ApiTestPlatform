<script setup>

const tableDataList = ref([]);
const loading = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);

const queryParams = ref({
    pageNum: 1,
    pageSize: 10,
    id: undefined,
    status: undefined
  })
</script>

<template>
  <el-table v-loading="loading" :data="tableDataList"
            @selection-change="handleSelectionChange"
            border
  >
    <el-table-column type="selection" width="55" align="center"/>
    <el-table-column label="用例ID" align="center" prop="caseId"/>
    <el-table-column label="用例名称" align="center" prop="caseName"/>
    <el-table-column label="所属项目" align="center" prop="projectName"/>
    <el-table-column label="所属模块" align="center" prop="moduleName"/>
    <!--         <el-table-column label="用例排序" align="center" prop="sort" />-->
    <el-table-column label="状态" align="center" prop="status">
      <template #default="scope">
        <dict-tag :options="sys_normal_disable" :value="scope.row.status"/>
      </template>
    </el-table-column>
    <el-table-column label="创建时间" align="center" prop="createTime" class-name="small-padding fixed-width">
      <template #default="scope">
        <span>{{ parseTime(scope.row.createTime) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="更新时间" align="center" prop="createTime" class-name="small-padding fixed-width">
      <template #default="scope">
        <span>{{ parseTime(scope.row.updateTime) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="200" align="center" class-name="small-padding fixed-width">
      <template #default="scope">
        <el-button link type="primary" icon="Histogram" @click="showHistory(scope.row)"
                   v-hasPermi="['hrm:case:history']"
                   title="执行历史">

        </el-button>
        <!--          <el-button link type="primary" icon="View" @click="handleUpdate(scope.row)" v-hasPermi="['hrm:case:detail']"-->
        <!--                     title="查看">-->

        <!--          </el-button>-->
        <el-button link type="warning" icon="Edit" v-loading="loading" @click="handleUpdate(scope.row)"
                   v-hasPermi="['hrm:case:edit']" title="编辑">
        </el-button>
        <el-button link type="warning" icon="CaretRight" v-loading="loading" @click="runTest(scope.row)"
                   v-hasPermi="['hrm:case:edit']" title="运行">
        </el-button>
        <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)"
                   v-hasPermi="['hrm:case:remove']" title="删除">
        </el-button>
      </template>
    </el-table-column>
  </el-table>

  <pagination
      v-show="total > 0"
      :total="total"
      v-model:page="queryParams.pageNum"
      v-model:limit="queryParams.pageSize"
      @pagination="getList"
  />
</template>

<style scoped lang="scss">

</style>