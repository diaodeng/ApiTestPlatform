<template>
  <el-card>
    <template #header>
      <span>订阅管理</span>
      <el-button type="primary" size="small" @click="dialog = true">
        新增订阅
      </el-button>
    </template>

    <el-table :data="list" style="width:100%">
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="url" label="订阅地址" />
      <el-table-column prop="type" label="类型" width="100" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button
            type="danger"
            size="small"
            @click="remove(row.id)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <!-- 新增订阅 -->
  <el-dialog v-model="dialog" title="新增订阅">
    <el-form :model="form">
      <el-form-item label="名称">
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item label="订阅地址">
        <el-input v-model="form.url" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialog=false">取消</el-button>
      <el-button type="primary" @click="create">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  listSubscriptions,
  createSubscription,
  deleteSubscription
} from '@/api/clash/subscriptions'

const list = ref<any[]>([])
const dialog = ref(false)

const form = ref({
  name: '',
  url: '',
  type: 'clash'
})

async function load() {
  list.value = (await listSubscriptions()).data
}

async function create() {
  await createSubscription(form.value)
  dialog.value = false
  load()
}

async function remove(id: string) {
  await deleteSubscription(id)
  load()
}

onMounted(load)
</script>
