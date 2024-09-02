<script lang="ts" setup>
import {CirclePlusFilled, Delete, Edit, Folder, Plus, RemoveFilled, Tickets} from "@element-plus/icons-vue";
import EditLabelText from "@/components/hrm/common/edit-label-text.vue";
import {ElMessageBox, ElMessage} from "element-plus";
import {apiTree, addApi, updateApi, delApi, getApi} from "@/api/hrm/api.js";
import {randomString} from "@/utils/tools.js";


const dataSource = defineModel("dataSource");
const filterText = defineModel("filterText");
const treeRef = defineModel("treeRef");

const emit = defineEmits(["nodeDbClick", "delNode", "filter"]);

interface Tree {
  apiId: bigint,
  name: string,
  parentId: bigint,
  children?: Tree[]
}

let id = 1000;

const handleNodeClick = (data: Tree, node, treeNode, event) => {
  // console.log(data)
  // console.log(node)
  // console.log(treeNode)
  console.log(event)
  if (event && event.target) {
    console.log(event.target)
  }
}

// const dataSource = ref<Tree[]>([
//   {
//     id: 1,
//     name: 'Level one 1',
//     children: [
//       {
//         id: 2,
//         name: 'Level two 1-1',
//         children: [
//           {
//             id: 3,
//             name: 'Level three 1-1-1',
//           },
//         ],
//       },
//     ],
//   },
//   {
//     id: 4,
//     name: 'Level one 2',
//     children: [
//       {
//         id: 5,
//         name: 'Level two 2-1',
//         children: [
//           {
//             id: 6,
//             name: 'Level three 2-1-1',
//           },
//         ],
//       },
//       {
//         id: 7,
//         name: 'Level two 2-2',
//         children: [
//           {
//             id: 8,
//             name: 'Level three 2-2-1',
//           },
//         ],
//       },
//     ],
//   },
//   {
//     id: 9,
//     name: 'Level one 3',
//     children: [
//       {
//         id: 10,
//         name: 'Level two 3-1',
//         children: [
//           {
//             id: 11,
//             name: 'Level three 3-1-1',
//           },
//         ],
//       },
//       {
//         id: 12,
//         name: 'Level two 3-2',
//         children: [
//           {
//             id: 13,
//             name: 'Level three 3-2-1',
//           },
//         ],
//       },
//     ],
//   },
// ])

const defaultProps = {
  key: 'apiId',
  children: 'children',
  label: 'name',
  isLeaf: "isParent",
  parentId: "parentId"
}

const append = (data: Tree) => {
  if (!data.isParent) {
    return;
  }
  const newChild = {
    id: null,
    name: '新增API',
    children: [],
    isNew: true,
    apiId: randomString(10),
    isParent: false,
    parentId: data.apiId
  }
  if (!data.children) {
    data.children = []
  }
  data.children.push(newChild)
  // dataSource.value = [...dataSource.value]
}

const remove = (node: Node, data: Tree) => {
  ElMessageBox.confirm("确定删除吗？\n对应目录下的所有内容都将被删除", "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    console.log(data)
    delApi(data.apiId).then(res => {
      // console.log(res)
      const parent = node.parent;
      const children: Tree[] = parent.data.children || parent.data;
      const index = children.findIndex((d) => d.apiId === data.apiId);
      children.splice(index, 1);
      // dataSource.value = [...dataSource.value]
      ElMessage.success("删除成功");
    }).catch(() => {
    });

  }).catch(() => {
  });
}

const handleDbClick = (event, node: Node, data: Tree) => {
  emit('nodeDbClick', event, node, data);
}


function treeFilter(value, data, node) {
  if (!value) {
    return true
  }
  debugger
  if (data.name.indexOf(value) !== -1 || data.title.indexOf(value) !== -1) {
    return true;
  } else {
    return false;
  }
}

</script>

<template>
  <el-tree
      style="max-width: 600px"
      :data="dataSource"
      :props="defaultProps"
      node-key="apiId"
      :expand-on-click-node="false"
      ref="treeRef"
      :filter-node-method="treeFilter"

  >
    <template #default="{ node, data }">
      <span @dblclick="(event) => {handleDbClick(event, node, data)}"
            @click="(event)=>{handleNodeClick(data, node, event)}"
            @mouseenter="(event)=>{node.data.edit=true}"
            @mouseleave="(event)=>{node.data.edit=false}"
      >
          <el-icon v-if="data.isParent"><folder/></el-icon>
          <el-icon v-else><tickets/></el-icon>
          <span><edit-label-text v-model:content="data.name"
                                 v-model:show-edite="node.data.edit"></edit-label-text></span>
          <span v-if="node.data.edit">
<!--            <el-icon color="blue"><edit></edit></el-icon>-->
            <el-icon color="green" @click.stop="append(data)" v-if="data.isParent"><circle-plus-filled></circle-plus-filled></el-icon>
            <el-icon color="red" @click.stop="remove(node, data)"><remove-filled></remove-filled></el-icon>
          </span>
        </span>

    </template>

  </el-tree>
</template>

<style scoped lang="scss">

</style>