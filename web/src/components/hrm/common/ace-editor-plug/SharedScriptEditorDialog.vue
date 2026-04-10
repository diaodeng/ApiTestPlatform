<script setup>
import {computed, nextTick, onBeforeUnmount, ref, watch} from "vue";
import * as ace from "ace-builds";
import "@/components/hrm/common/aceConfig.js";
import {CodeTypeEnum} from "@/components/hrm/enum.js";

const visible = ref(false);
const dialogTitle = ref("脚本编辑");
const editorRef = ref(null);
const currentSessionKey = ref("");
const currentCodeInfo = ref(null);
const languageOptions = Object.values(CodeTypeEnum);
const sessionMap = new Map();
let editor = null;

function getLangByCodeType(codeType) {
  return codeType === CodeTypeEnum.js.value ? "javascript" : "python";
}

function syncSessionValue(session, value) {
  const nextValue = value || "";
  if (session.getValue() !== nextValue) {
    session.setValue(nextValue);
  }
}

function ensureSession(sessionKey, codeInfo) {
  let session = sessionMap.get(sessionKey);
  if (!session) {
    session = ace.createEditSession(codeInfo?.codeContent || "");
    session.setUseWrapMode(true);
    session.on("change", () => {
      if (currentSessionKey.value === sessionKey && currentCodeInfo.value) {
        currentCodeInfo.value.codeContent = session.getValue();
      }
    });
    sessionMap.set(sessionKey, session);
  }
  syncSessionValue(session, codeInfo?.codeContent);
  session.setMode(`ace/mode/${getLangByCodeType(codeInfo?.codeType)}`);
  return session;
}

async function ensureEditor() {
  if (editor || !editorRef.value) {
    return;
  }
  await nextTick();
  if (!editorRef.value) {
    return;
  }
  editor = ace.edit(editorRef.value);
  editor.setTheme("ace/theme/github");
  editor.setOptions({
    fontSize: 14,
    showPrintMargin: false,
    tabSize: 2,
    useSoftTabs: true,
    wrap: true,
    highlightActiveLine: true,
    enableBasicAutocompletion: true,
    enableLiveAutocompletion: true,
    enableSnippets: true,
  });
}

function applyCurrentSession() {
  if (!editor || !currentSessionKey.value || !currentCodeInfo.value) {
    return;
  }
  const session = ensureSession(currentSessionKey.value, currentCodeInfo.value);
  editor.setSession(session);
  editor.resize(true);
  editor.focus();
}

async function open(payload) {
  if (!payload?.sessionKey || !payload?.codeInfo) {
    return;
  }
  currentSessionKey.value = payload.sessionKey;
  currentCodeInfo.value = payload.codeInfo;
  dialogTitle.value = payload.title || "脚本编辑";
  visible.value = true;
  await nextTick();
  await ensureEditor();
  applyCurrentSession();
}

function closeEditor() {
  visible.value = false;
}

function destroyEditor() {
  if (!editor) {
    return;
  }
  editor.destroy();
  editor = null;
}

function reset() {
  visible.value = false;
  currentSessionKey.value = "";
  currentCodeInfo.value = null;
  destroyEditor();
  sessionMap.forEach((session) => {
    session.destroy?.();
  });
  sessionMap.clear();
}

const currentCodeType = computed({
  get() {
    return currentCodeInfo.value?.codeType ?? CodeTypeEnum.js.value;
  },
  set(value) {
    if (!currentCodeInfo.value) {
      return;
    }
    currentCodeInfo.value.codeType = value * 1;
    const session = sessionMap.get(currentSessionKey.value);
    if (session) {
      session.setMode(`ace/mode/${getLangByCodeType(currentCodeInfo.value.codeType)}`);
    }
    if (editor) {
      applyCurrentSession();
    }
  }
});

watch(visible, async (newValue) => {
  if (!newValue) {
    return;
  }
  await nextTick();
  await ensureEditor();
  applyCurrentSession();
});

onBeforeUnmount(() => {
  reset();
});

defineExpose({
  open,
  reset,
});
</script>

<template>
  <el-dialog
      v-model="visible"
      :title="dialogTitle"
      width="80%"
      top="5vh"
      append-to-body
      class="shared-script-editor-dialog"
  >
    <div class="shared-script-editor-dialog__toolbar">
      <el-text type="info">代码会实时同步到当前用例数据</el-text>
      <el-select v-model="currentCodeType" size="small" style="width: 120px">
        <el-option
            v-for="option in languageOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
        />
      </el-select>
    </div>
    <div ref="editorRef" class="shared-script-editor-dialog__editor"></div>

    <template #footer>
      <el-button type="primary" @click="closeEditor">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped lang="scss">
.shared-script-editor-dialog__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.shared-script-editor-dialog__editor {
  width: 100%;
  height: 70vh;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  overflow: hidden;
}
</style>
