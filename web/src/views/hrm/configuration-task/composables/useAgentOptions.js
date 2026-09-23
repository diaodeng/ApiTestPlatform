// 配置任务模块共享的 Agent 下拉选项加载逻辑。
// 任务编辑、运行确认、定时配置三处弹窗都需要选择执行 Agent，
// 统一从这里取列表，避免同一页面重复请求 /qtr/agent/list。
import { ref } from "vue";
import { all as listAllAgents } from "@/api/hrm/agent";

// 模块级单例：同一页面多个组件共享同一份列表与加载状态。
const agentOptions = ref([]);
const loaded = ref(false);
const loading = ref(false);

export function useAgentOptions() {
    // 加载已登记的 Agent 列表；已加载过则直接复用，失败时静默清空由调用方提示。
    async function ensureAgentOptions() {
        if (loaded.value || loading.value) return;
        loading.value = true;
        try {
            const res = await listAllAgents();
            agentOptions.value = Array.isArray(res.data) ? res.data : [];
            loaded.value = true;
        } catch (e) {
            agentOptions.value = [];
            throw e;
        } finally {
            loading.value = false;
        }
    }

    return { agentOptions, ensureAgentOptions, agentsLoading: loading };
}
