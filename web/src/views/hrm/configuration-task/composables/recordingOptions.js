// 门店配置独立录制弹窗的选项加载。
// 录制接口按 agentId 下发执行 Agent（与 Web 用例录制一致），凭证投影复用统一凭证
// 的 Web 绑定选项（playwright_storage 类型），与 Web 测试管理页的加载逻辑保持一致。
import { listCredentialBindingOptions } from "@/api/system/credential";

// 加载 Agent 列表（保留原始字段，含 agentId/agentCode/status）。
export function listAgentsForRecording() {
    return import("@/api/hrm/agent").then(({ all }) =>
        all().then((response) => (Array.isArray(response.data) ? response.data : []))
    );
}

// 加载 Web 凭证投影绑定选项：只保留 playwright_storage 类型（浏览器登录态投影）。
export function listWebCredentialOptions() {
    return listCredentialBindingOptions("web_case").then(
        (response) =>
            (response.data || []).filter((item) => item.projectionType === "playwright_storage")
    );
}
