// 门店配置任务页的独立录制组合函数。
//
// 设计说明：
// - Web 测试管理页的 useRecordingManager 承载了录制/回放/存为用例/凭证落库等完整能力，
//   强耦合用例管理状态（40+ 依赖项）；门店配置只需要"录一段操作、转成版本草稿"，
//   因此这里只实现 开始录制 → 轮询进度 → 停止 的最小闭环，复用同一套后端接口，
//   录制记录仍然落在 hrm_web_recording_session，与 Web 测试管理共用一条数据链路。
// - 不关联 Web 用例（webCaseId 留空）：后端 hrm_web_recording_session.web_case_id
//   本来就是 nullable，录制转模板只依赖录制步骤重建，与来源用例无关。
import { ref } from "vue";
import { ElMessage } from "element-plus";
import {
    startWebRecording,
    stopWebRecording,
    getWebRecording
} from "@/api/hrm/web_case.js";

// 录制状态枚举，与 Web 用例录制页保持一致。
export const RECORDING_STATUS = {
    1: "草稿",
    2: "录制中",
    3: "已完成",
    4: "失败",
    5: "已停止"
};

export function useStandaloneRecording() {
    // 弹窗与表单状态
    const showRecordingDialog = ref(false);
    const submitting = ref(false);
    const recordingId = ref(undefined);
    const liveStatusText = ref("");
    const liveStatusType = ref("info");
    const recordedSteps = ref([]);

    const recordingForm = ref({
        sessionName: "",
        agentId: undefined,
        browserName: "chromium",
        headless: false,
        startUrl: "",
        credentialBindingId: undefined,
        manualLoginEnabled: false,
        manualLoginWaitSec: 120,
        closeBrowserOnStop: true,
        captureAssertions: true,
        recordingId: undefined
    });

    let pollTimer = null;

    function stopPoll() {
        if (pollTimer) {
            window.clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    // 重置弹窗到新建状态。
    function openRecordingDialog() {
        recordingForm.value = {
            sessionName: "",
            agentId: undefined,
            browserName: "chromium",
            headless: false,
            startUrl: "",
            credentialBindingId: undefined,
            manualLoginEnabled: false,
            manualLoginWaitSec: 120,
            closeBrowserOnStop: true,
            captureAssertions: true,
            recordingId: undefined
        };
        recordingId.value = undefined;
        recordedSteps.value = [];
        liveStatusText.value = "";
        liveStatusType.value = "info";
        showRecordingDialog.value = true;
    }

    // 轮询录制会话状态：录制中每 3 秒刷新一次，收敛到终态后停止并汇总步骤。
    function startPoll() {
        stopPoll();
        pollTimer = window.setInterval(async () => {
            if (!recordingId.value) return;
            try {
                const res = await getWebRecording(recordingId.value);
                const detail = res.data || {};
                const status = detail.status;
                if (status === 2) {
                    liveStatusText.value = `录制中，已捕获 ${detail.resultSummary?.stepCount ?? recordedSteps.value.length ?? 0} 个步骤`;
                    liveStatusType.value = "warning";
                } else {
                    stopPoll();
                    liveStatusText.value =
                        status === 3
                            ? "录制已完成，可关闭弹窗后使用「录制转模板」生成版本草稿"
                            : status === 5
                              ? "录制已停止（未正常完成），仍可尝试转模板"
                              : `录制失败：${detail.errorMessage || "未知错误"}`;
                    liveStatusType.value = status === 3 ? "success" : "danger";
                }
            } catch {
                // 轮询失败不中断录制，下一轮重试。
            }
        }, 3000);
    }

    // 开始录制：校验必填项后调用与 Web 测试管理相同的开始录制接口。
    async function startRecording() {
        const form = recordingForm.value;
        if (!form.agentId) {
            ElMessage.error("请选择执行 Agent");
            return;
        }
        if (!form.startUrl?.trim()) {
            ElMessage.error("请填写录制起始地址");
            return;
        }
        if (form.manualLoginEnabled && (!form.manualLoginWaitSec || form.manualLoginWaitSec < 1)) {
            ElMessage.error("登录等待时间必须大于 0 秒");
            return;
        }
        submitting.value = true;
        try {
            const response = await startWebRecording({
                // 不关联 Web 用例：门店配置的录制只用于转版本草稿。
                webCaseId: undefined,
                agentId: form.agentId,
                sessionName: form.sessionName || undefined,
                browserName: form.browserName,
                headless: form.headless,
                startUrl: form.startUrl.trim(),
                credentialBindingId: form.credentialBindingId || undefined,
                manualLoginEnabled: Boolean(form.manualLoginEnabled),
                manualLoginWaitSec: form.manualLoginWaitSec,
                recordingOptions: {
                    closeBrowserOnStop: form.closeBrowserOnStop,
                    captureAssertions: form.captureAssertions,
                    assertionAttachMode: form.captureAssertions ? "inside_step" : "parallel_step",
                    autoAssertTextOnClick: false
                }
            });
            recordingId.value = response.data?.recordingId;
            recordingForm.value.recordingId = recordingId.value;
            liveStatusText.value = "浏览器已拉起，请在 Agent 机器上操作目标页面";
            liveStatusType.value = "warning";
            ElMessage.success("录制已启动");
            startPoll();
        } catch (e) {
            ElMessage.error(e.message || "启动录制失败");
        } finally {
            submitting.value = false;
        }
    }

    // 停止录制：与 Web 测试管理相同的停止接口，状态由轮询收敛。
    async function stopRecording() {
        if (!recordingId.value) return;
        submitting.value = true;
        try {
            await stopWebRecording({
                recordingId: recordingId.value,
                agentId: recordingForm.value.agentId,
                closeBrowserOnStop: recordingForm.value.closeBrowserOnStop
            });
            ElMessage.success("停止指令已发送");
        } catch (e) {
            ElMessage.error(e.message || "停止录制失败");
        } finally {
            submitting.value = false;
        }
    }

    // 关闭弹窗时停止轮询；录制会话本身继续由 Agent 侧执行，不随弹窗关闭中断。
    function handleDialogClose() {
        stopPoll();
    }

    return {
        showRecordingDialog,
        submitting,
        recordingId,
        recordingForm,
        liveStatusText,
        liveStatusType,
        recordedSteps,
        openRecordingDialog,
        startRecording,
        stopRecording,
        handleDialogClose
    };
}
