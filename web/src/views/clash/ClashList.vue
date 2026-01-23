<template>
  <el-row :gutter="20">
    <el-col :span="8" v-for="c in list" :key="c.id">
      <el-card>
        <h4>{{ c.name }}</h4>

        <el-tag :type="c.status === 'online' ? 'success' : 'danger'">
          {{ c.status }}
        </el-tag>

        <div style="margin-top:10px">
          <el-button
            type="primary"
            size="small"
            @click="go(c.id)"
          >
            管理
          </el-button>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listClashServices } from '@/api/clash/clash'

const list = ref<any[]>([])
const router = useRouter()

function go(id: string) {
  router.push(`/clash/${id}`)
}

onMounted(async () => {
  list.value = (await listClashServices()).data
})
</script>
