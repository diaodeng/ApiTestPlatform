<script lang="ts" setup>
import {CirclePlusFilled, Folder, RemoveFilled, Tickets} from "@element-plus/icons-vue";
import EditLabelText from "@/components/hrm/common/edit-label-text.vue";
import ContextMenu from "@/components/hrm/common/context-menu.vue";
import {HrmDataTypeEnum, CaseStepTypeEnum} from "@/components/hrm/enum";
import {ElMessage, ElMessageBox} from "element-plus";
import {delApi} from "@/api/hrm/api.js";
import {randomString} from "@/utils/tools.js";


const dataSource = defineModel("dataSource");
const filterText = defineModel("filterText");
const treeRef = defineModel("treeRef");
const contextMenuSelectNode = ref({e: null, data: null, node: null, nodeRef: null});
const contextMenu = reactive({
  show: false,
  x: 0,
  y: 0,
  data: [
    {
      title: '新增文件夹',
      apiType: CaseStepTypeEnum.folder,
      icon: 'Menu'
    },
    {
      title: '新增http请求',
      apiType: CaseStepTypeEnum.http,
      icon: 'Menu',
      divided: true
    },
    {
      title: '新增websocket请求',
      apiType: CaseStepTypeEnum.websocket,
      icon: 'Menu',
      divided: true
    },
    // {
    //   title: '1-3 菜单',
    //   icon: 'https://element-plus.org/images/element-plus-logo.svg',
    //   children: [
    //     {title: '1-3-1 菜单', remark: 'Ctrl+A'},
    //     {title: '1-3-2 菜单', disabled: true},
    //     {
    //       title: '1-3-3 菜单',
    //       className: 'custom-red-menu-item'
    //     }
    //   ],
    //   disabled: true
    // }
  ],
  onSelect: (item: any) => {
    append(contextMenuSelectNode.value.data, item.apiType);
    // ElMessage.success('选中了' + item.title)
  }
})

const emit = defineEmits(["nodeDbClick", "delNode", "filter", "addNode"]);

interface Tree {
  apiId: bigint,
  type: number,
  apiType: number,
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

/*
* 右键
* */
function handleNodeRightClick(event, data, node, nodeRef) {
  // console.log(event)
  // console.log(data)
  // console.log(node)
  // console.log(nodeRef.value)
  contextMenuSelectNode.value.e = event;
  contextMenuSelectNode.value.data = data;
  contextMenuSelectNode.value.node = node;
  contextMenuSelectNode.value.nodeRef = nodeRef;
  contextMenu.show = true;
  contextMenu.x = event.clientX
  contextMenu.y = event.clientY
  console.log(event.clientX, event.clientY)
  event.preventDefault();
  // emit("nodeDbClick", event, data, node, nodeRef)

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

const append = (data: Tree, type) => {
  if (!data.isParent) {
    return;
  }

  const newStepId = randomString(10);
  const newStepName = "新增API";
  const newChild = {
    id: null,
    name: newStepName,
    children: [],
    isNew: true,
    apiId: newStepId,
    isParent: type === CaseStepTypeEnum.folder,
    parentId: data.apiId,
    type: type !== CaseStepTypeEnum.folder?HrmDataTypeEnum.api: HrmDataTypeEnum.folder,
    apiType: type
  }
  if (!data.children) {
    data.children = []
  }
  data.children.push(newChild)
  emit('addNode', type, newChild);
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
      emit('delNode', data);
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
  if (data.name.indexOf(value) !== -1 || data.title.indexOf(value) !== -1) {
    return true;
  } else {
    return false;
  }
}

</script>

<template>
  <ContextMenu v-model:visible="contextMenu.show"
               :x="contextMenu.x"
               :y="contextMenu.y"
               @select="contextMenu.onSelect"
               :menus="contextMenu.data"

  ></ContextMenu>
  <el-tree
      style="max-width: 600px"
      :data="dataSource"
      :props="defaultProps"
      node-key="apiId"
      :expand-on-click-node="false"
      ref="treeRef"
      :filter-node-method="treeFilter"
      @node-contextmenu="handleNodeRightClick"

  >
    <template #default="{ node, data }">
      <span @dblclick="(event) => {handleDbClick(event, node, data)}"
            @click="(event)=>{handleNodeClick(data, node, event)}"
            @mouseenter="(event)=>{node.data.edit=true}"
            @mouseleave="(event)=>{node.data.edit=false}"
      >
          <el-icon v-if="data.apiType===CaseStepTypeEnum.folder && data.isParent"><folder/></el-icon>
          <el-button v-else-if="data.apiType===CaseStepTypeEnum.http" type="text" style="color: green">RQ</el-button>
          <el-button v-else-if="data.apiType===CaseStepTypeEnum.websocket" type="text" color="blue">WS</el-button>
          <el-button v-else-if="data.apiType===CaseStepTypeEnum.webui" type="text" style="color: yellow">WB</el-button>
          <span><edit-label-text v-model:content="data.name"
                                 v-model:show-edite="node.data.edit"></edit-label-text></span>
          <span v-if="node.data.edit">
<!--            <el-icon color="blue"><edit></edit></el-icon>-->
          <el-icon color="green" @click.stop="append(data, CaseStepTypeEnum.http)"><circle-plus-filled></circle-plus-filled></el-icon>
            <!--            <RequestTypeDropdown @type-selected="append" :index-key="data"></RequestTypeDropdown>-->
            <el-icon color="red" @click.stop="remove(node, data)"><remove-filled></remove-filled></el-icon>
          </span>
        </span>

    </template>

  </el-tree>
</template>

<style scoped lang="scss">

</style>