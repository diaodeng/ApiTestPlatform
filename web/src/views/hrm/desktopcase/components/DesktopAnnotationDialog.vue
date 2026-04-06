<template>
  <el-dialog v-model="visible" :title="title" width="1180px" destroy-on-close append-to-body>
    <div class="annotation-layout">
      <div class="annotation-main">
        <div class="annotation-toolbar">
          <span>{{ helpText }}</span>
          <div class="annotation-toolbar-actions">
            <el-button v-if="isSingleMode" size="small" plain @click="resetToFullImage">整图选中</el-button>
            <el-button size="small" plain @click="clearRects">清空</el-button>
          </div>
        </div>
        <div class="annotation-stage-wrap">
          <div v-if="!sourceSrc" class="annotation-empty">当前没有可用于标注的图片</div>
          <div v-else class="annotation-stage">
            <img ref="imageRef" :src="sourceSrc" class="annotation-image" @load="handleImageLoad" />
            <svg
              v-if="display.width > 0 && display.height > 0"
              class="annotation-overlay"
              :width="display.width"
              :height="display.height"
              @mousedown="handlePointerDown"
            >
              <rect
                v-for="(item, index) in displayRects"
                :key="`rect-${index}`"
                :x="item.x"
                :y="item.y"
                :width="item.width"
                :height="item.height"
                :class="['annotation-rect', index === activeIndex ? 'is-active' : '', item.exclude ? 'is-exclude' : 'is-include']"
                @mousedown.stop="selectRect(index)"
              />
              <rect
                v-if="draftDisplayRect"
                :x="draftDisplayRect.x"
                :y="draftDisplayRect.y"
                :width="draftDisplayRect.width"
                :height="draftDisplayRect.height"
                class="annotation-rect is-draft"
              />
            </svg>
          </div>
        </div>
      </div>
      <div class="annotation-sidebar">
        <el-alert :title="modeLabel" type="info" :closable="false" show-icon class="mb12" />
        <div class="annotation-meta mb12">
          <div>原图尺寸：{{ display.naturalWidth || '-' }} x {{ display.naturalHeight || '-' }}</div>
          <div>基准偏移：{{ baseOffset.x }}, {{ baseOffset.y }}</div>
          <div>当前区域数：{{ rects.length }}</div>
        </div>

        <template v-if="isSingleMode">
          <el-empty v-if="activeIndex < 0" description="在图片上拖拽框选区域" :image-size="80" />
          <el-form v-else label-width="72px" size="small">
            <el-form-item label="X">
              <el-input-number v-model="rects[activeIndex].x" :min="0" :max="display.naturalWidth" controls-position="right" style="width: 100%" />
            </el-form-item>
            <el-form-item label="Y">
              <el-input-number v-model="rects[activeIndex].y" :min="0" :max="display.naturalHeight" controls-position="right" style="width: 100%" />
            </el-form-item>
            <el-form-item label="宽度">
              <el-input-number v-model="rects[activeIndex].width" :min="1" :max="display.naturalWidth" controls-position="right" style="width: 100%" />
            </el-form-item>
            <el-form-item label="高度">
              <el-input-number v-model="rects[activeIndex].height" :min="1" :max="display.naturalHeight" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-form>
        </template>

        <template v-else>
          <div class="mask-list-toolbar">
            <span>忽略区域</span>
            <el-button size="small" plain @click="appendDefaultMask">加一条</el-button>
          </div>
          <el-table
            :data="rects"
            size="small"
            border
            highlight-current-row
            max-height="280px"
            @current-change="handleCurrentRowChange"
          >
            <el-table-column label="#" width="54">
              <template #default="scope">{{ scope.$index + 1 }}</template>
            </el-table-column>
            <el-table-column label="名称" min-width="120">
              <template #default="scope">
                <el-input v-model="scope.row.name" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="类型" width="90">
              <template #default="scope">
                <el-switch v-model="scope.row.exclude" active-text="忽略" inactive-text="保留" inline-prompt />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="scope">
                <el-button link type="danger" @click="removeRect(scope.$index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="activeIndex < 0" description="在图片上拖拽新增忽略区域，或在表格中新增后微调" :image-size="80" class="mt12" />
          <el-form v-else label-width="72px" size="small" class="mt12">
            <el-form-item label="X">
              <el-input-number v-model="rects[activeIndex].x" :min="0" :max="display.naturalWidth" controls-position="right" style="width: 100%" />
            </el-form-item>
            <el-form-item label="Y">
              <el-input-number v-model="rects[activeIndex].y" :min="0" :max="display.naturalHeight" controls-position="right" style="width: 100%" />
            </el-form-item>
            <el-form-item label="宽度">
              <el-input-number v-model="rects[activeIndex].width" :min="1" :max="display.naturalWidth" controls-position="right" style="width: 100%" />
            </el-form-item>
            <el-form-item label="高度">
              <el-input-number v-model="rects[activeIndex].height" :min="1" :max="display.naturalHeight" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-form>
        </template>
      </div>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="submit">应用</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '图像标注' },
  mode: { type: String, default: 'mask' },
  sourceAsset: { type: Object, default: null },
  sourceSrc: { type: String, default: '' },
  initialCropRect: { type: Object, default: null },
  initialRegions: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const imageRef = ref(null)
const rects = ref([])
const activeIndex = ref(-1)
const draftRect = ref(null)
const drawing = reactive({ active: false, startX: 0, startY: 0 })
const display = reactive({ width: 0, height: 0, naturalWidth: 0, naturalHeight: 0 })

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const isSingleMode = computed(() => props.mode === 'target' || props.mode === 'baseline')

const modeLabel = computed(() => {
  if (props.mode === 'target') return '目标图裁剪'
  if (props.mode === 'baseline') return '基准图裁剪'
  return '忽略区域标注'
})

const helpText = computed(() => {
  if (isSingleMode.value) return '在图片上拖拽框选区域，可在右侧微调数值后应用。'
  return '在图片上拖拽新增忽略区域，右侧可编辑名称、类型和坐标。'
})

const baseOffset = computed(() => {
  const region = props.sourceAsset?.region || {}
  return {
    x: Number(region.x) || 0,
    y: Number(region.y) || 0
  }
})

const displayRects = computed(() => rects.value.map((item) => localRectToDisplay(item)))
const draftDisplayRect = computed(() => (draftRect.value ? localRectToDisplay(draftRect.value) : null))

watch(
  () => [props.modelValue, props.sourceSrc, props.mode, props.initialCropRect, props.initialRegions, props.sourceAsset],
  async ([open]) => {
    if (!open) {
      detachPointerListeners()
      drawing.active = false
      draftRect.value = null
      return
    }
    await nextTick()
    resetState()
  },
  { deep: true }
)

function resetState() {
  const sourceImage = imageRef.value
  if (sourceImage) {
    display.naturalWidth = sourceImage.naturalWidth || sourceImage.width || 0
    display.naturalHeight = sourceImage.naturalHeight || sourceImage.height || 0
    updateDisplayBox()
  }
  if (isSingleMode.value) {
    const cropRect = toLocalRect(props.initialCropRect)
    rects.value = cropRect ? [cropRect] : []
    activeIndex.value = cropRect ? 0 : -1
    if (!cropRect && props.mode === 'baseline' && display.naturalWidth > 0 && display.naturalHeight > 0) {
      resetToFullImage()
    }
    return
  }
  rects.value = (props.initialRegions || []).map((item, index) => ({
    ...toLocalRect(item),
    name: item?.name || `忽略区域${index + 1}`,
    exclude: item?.exclude !== false
  })).filter(Boolean)
  activeIndex.value = rects.value.length ? 0 : -1
}

function handleImageLoad() {
  const sourceImage = imageRef.value
  if (!sourceImage) return
  display.naturalWidth = sourceImage.naturalWidth || sourceImage.width || 0
  display.naturalHeight = sourceImage.naturalHeight || sourceImage.height || 0
  updateDisplayBox()
  resetState()
}

function updateDisplayBox() {
  const sourceImage = imageRef.value
  if (!sourceImage) return
  const rect = sourceImage.getBoundingClientRect()
  display.width = rect.width
  display.height = rect.height
}

function detachPointerListeners() {
  window.removeEventListener('mousemove', handlePointerMove)
  window.removeEventListener('mouseup', handlePointerUp)
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

function normalizeRectFromPoints(startX, startY, endX, endY) {
  const x = clamp(Math.min(startX, endX), 0, display.naturalWidth)
  const y = clamp(Math.min(startY, endY), 0, display.naturalHeight)
  const width = clamp(Math.abs(endX - startX), 0, display.naturalWidth)
  const height = clamp(Math.abs(endY - startY), 0, display.naturalHeight)
  return {
    x: Math.round(x),
    y: Math.round(y),
    width: Math.round(width),
    height: Math.round(height)
  }
}

function toLocalRect(rect) {
  if (!rect) return null
  return {
    x: clamp(Math.round((Number(rect.x) || 0) - baseOffset.value.x), 0, display.naturalWidth),
    y: clamp(Math.round((Number(rect.y) || 0) - baseOffset.value.y), 0, display.naturalHeight),
    width: clamp(Math.round(Number(rect.width) || 0), 0, display.naturalWidth),
    height: clamp(Math.round(Number(rect.height) || 0), 0, display.naturalHeight),
    name: rect.name || '',
    exclude: rect.exclude !== false
  }
}

function toAbsoluteRect(rect) {
  return {
    x: Math.round(rect.x + baseOffset.value.x),
    y: Math.round(rect.y + baseOffset.value.y),
    width: Math.round(rect.width),
    height: Math.round(rect.height),
    exclude: rect.exclude !== false,
    name: rect.name || ''
  }
}

function localRectToDisplay(rect) {
  const scaleX = display.naturalWidth > 0 ? display.width / display.naturalWidth : 1
  const scaleY = display.naturalHeight > 0 ? display.height / display.naturalHeight : 1
  return {
    x: rect.x * scaleX,
    y: rect.y * scaleY,
    width: rect.width * scaleX,
    height: rect.height * scaleY,
    exclude: rect.exclude !== false
  }
}

function pointerToLocal(event) {
  const sourceImage = imageRef.value
  if (!sourceImage) return null
  const rect = sourceImage.getBoundingClientRect()
  if (!rect.width || !rect.height) return null
  const scaleX = display.naturalWidth / rect.width
  const scaleY = display.naturalHeight / rect.height
  return {
    x: clamp((event.clientX - rect.left) * scaleX, 0, display.naturalWidth),
    y: clamp((event.clientY - rect.top) * scaleY, 0, display.naturalHeight)
  }
}

function handlePointerDown(event) {
  if (event.button !== 0 || !display.width || !display.height) return
  const point = pointerToLocal(event)
  if (!point) return
  drawing.active = true
  drawing.startX = point.x
  drawing.startY = point.y
  draftRect.value = {
    x: point.x,
    y: point.y,
    width: 0,
    height: 0,
    name: isSingleMode.value ? '' : `忽略区域${rects.value.length + 1}`,
    exclude: true
  }
  detachPointerListeners()
  window.addEventListener('mousemove', handlePointerMove)
  window.addEventListener('mouseup', handlePointerUp)
}

function handlePointerMove(event) {
  if (!drawing.active || !draftRect.value) return
  const point = pointerToLocal(event)
  if (!point) return
  draftRect.value = {
    ...draftRect.value,
    ...normalizeRectFromPoints(drawing.startX, drawing.startY, point.x, point.y)
  }
}

function handlePointerUp() {
  detachPointerListeners()
  drawing.active = false
  if (!draftRect.value) return
  if (draftRect.value.width < 2 || draftRect.value.height < 2) {
    draftRect.value = null
    return
  }
  const finalized = {
    ...draftRect.value,
    x: Math.round(draftRect.value.x),
    y: Math.round(draftRect.value.y),
    width: Math.round(draftRect.value.width),
    height: Math.round(draftRect.value.height)
  }
  if (isSingleMode.value) {
    rects.value = [finalized]
    activeIndex.value = 0
  } else {
    rects.value.push(finalized)
    activeIndex.value = rects.value.length - 1
  }
  draftRect.value = null
}

function selectRect(index) {
  activeIndex.value = index
}

function handleCurrentRowChange(row) {
  if (!row) return
  activeIndex.value = rects.value.indexOf(row)
}

function clearRects() {
  rects.value = []
  activeIndex.value = -1
}

function appendDefaultMask() {
  rects.value.push({
    name: `忽略区域${rects.value.length + 1}`,
    x: Math.round(display.naturalWidth * 0.2),
    y: Math.round(display.naturalHeight * 0.2),
    width: Math.round(display.naturalWidth * 0.2) || 32,
    height: Math.round(display.naturalHeight * 0.12) || 32,
    exclude: true
  })
  activeIndex.value = rects.value.length - 1
}

function removeRect(index) {
  rects.value.splice(index, 1)
  if (!rects.value.length) {
    activeIndex.value = -1
    return
  }
  if (activeIndex.value >= rects.value.length) {
    activeIndex.value = rects.value.length - 1
  }
}

function resetToFullImage() {
  if (!display.naturalWidth || !display.naturalHeight) return
  rects.value = [{
    x: 0,
    y: 0,
    width: Math.round(display.naturalWidth),
    height: Math.round(display.naturalHeight),
    exclude: false,
    name: ''
  }]
  activeIndex.value = 0
}

function buildUniqueFileName(prefix) {
  const sourceName = `${props.sourceAsset?.fileName || prefix}`.replace(/\.[^.]+$/, '')
  return `${sourceName}-${Date.now()}.png`
}

function cropToAsset(rect) {
  const sourceImage = imageRef.value
  if (!sourceImage) return null
  const canvas = document.createElement('canvas')
  canvas.width = rect.width
  canvas.height = rect.height
  const context = canvas.getContext('2d')
  if (!context) return null
  context.drawImage(
    sourceImage,
    rect.x,
    rect.y,
    rect.width,
    rect.height,
    0,
    0,
    rect.width,
    rect.height
  )
  return {
    assetType: props.mode === 'target' ? 'target' : 'baseline',
    fileName: buildUniqueFileName(props.mode === 'target' ? 'target' : 'baseline'),
    resolutionKey: props.sourceAsset?.resolutionKey,
    width: rect.width,
    height: rect.height,
    region: toAbsoluteRect(rect),
    metadata: {
      ...(props.sourceAsset?.metadata || {}),
      annotationMode: props.mode,
      sourceAssetId: props.sourceAsset?.assetId
    },
    imageBase64: canvas.toDataURL('image/png')
  }
}

function submit() {
  if (isSingleMode.value) {
    if (!rects.value.length) {
      ElMessage.error('请先框选一个区域')
      return
    }
    const rect = rects.value[activeIndex.value >= 0 ? activeIndex.value : 0]
    if (!rect) {
      ElMessage.error('请先框选一个区域')
      return
    }
    const asset = cropToAsset(rect)
    if (!asset) {
      ElMessage.error('裁剪图片失败')
      return
    }
    emit('confirm', { asset, cropRect: toAbsoluteRect(rect) })
    visible.value = false
    return
  }
  emit('confirm', { regions: rects.value.map((item) => toAbsoluteRect(item)) })
  visible.value = false
}

onBeforeUnmount(() => {
  detachPointerListeners()
})
</script>

<style scoped>
.annotation-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
  min-height: 620px;
}

.annotation-main {
  min-width: 0;
}

.annotation-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
}

.annotation-toolbar-actions {
  display: flex;
  gap: 8px;
}

.annotation-stage-wrap {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  min-height: 560px;
  padding: 12px;
  background: linear-gradient(135deg, #f7f8fa 0%, #eef2f6 100%);
  overflow: auto;
}

.annotation-empty {
  min-height: 536px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary);
}

.annotation-stage {
  position: relative;
  display: inline-block;
  max-width: 100%;
}

.annotation-image {
  display: block;
  max-width: 100%;
  max-height: 536px;
  border-radius: 6px;
  user-select: none;
}

.annotation-overlay {
  position: absolute;
  inset: 0;
  cursor: crosshair;
}

.annotation-rect {
  fill: rgba(64, 158, 255, 0.18);
  stroke: #409eff;
  stroke-width: 2px;
}

.annotation-rect.is-exclude {
  fill: rgba(245, 108, 108, 0.18);
  stroke: #f56c6c;
}

.annotation-rect.is-active {
  stroke-width: 3px;
}

.annotation-rect.is-draft {
  fill: rgba(103, 194, 58, 0.16);
  stroke: #67c23a;
  stroke-dasharray: 6 4;
}

.annotation-sidebar {
  border-left: 1px solid var(--el-border-color-lighter);
  padding-left: 16px;
}

.annotation-meta {
  display: grid;
  gap: 6px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.mask-list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.mt12 {
  margin-top: 12px;
}

.mb12 {
  margin-bottom: 12px;
}
</style>
