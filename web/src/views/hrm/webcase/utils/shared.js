import { toRaw } from "vue";

/**
 * 浏览器选项。
 * @type {Array<{label: string, value: string}>}
 */
export const browserOptions = [
    { label: "Chromium", value: "chromium" },
    { label: "Chrome", value: "chrome" },
    { label: "Microsoft Edge", value: "msedge" },
    { label: "Firefox", value: "firefox" },
    { label: "WebKit", value: "webkit" },
];

/**
 * 运行目标选项。
 * @type {Array<{label: string, value: string}>}
 */
export const runtimeTargetOptions = [
    { label: "Web", value: "web" },
    { label: "API", value: "api" },
    { label: "Desktop", value: "desktop" },
];

/**
 * Web 动作选项。
 * @type {Array<{label: string, value: string}>}
 */
export const actionOptions = [
    { label: "打开页面", value: "goto" },
    { label: "窗口最大化", value: "window_maximize" },
    { label: "设置窗口尺寸", value: "set_window_size" },
    { label: "点击元素", value: "click" },
    { label: "双击元素", value: "double_click" },
    { label: "悬停元素", value: "hover" },
    { label: "填写内容", value: "fill" },
    { label: "清空输入", value: "clear" },
    { label: "键盘按键", value: "press" },
    { label: "勾选元素", value: "check" },
    { label: "取消勾选", value: "uncheck" },
    { label: "选择下拉项", value: "select_option" },
    { label: "等待元素可见", value: "wait_visible" },
    { label: "等待元素隐藏", value: "wait_hidden" },
    { label: "固定等待", value: "sleep" },
    { label: "断言页面包含文本", value: "assert_page_contains" },
    { label: "断言页面不包含文本", value: "assert_page_not_contains" },
    { label: "断言元素文本等于", value: "assert_text_equals" },
    { label: "断言元素文本包含", value: "assert_text_contains" },
    { label: "断言页面标题包含", value: "assert_title_contains" },
    { label: "断言URL包含", value: "assert_url_contains" },
];

/**
 * 定位器类型选项。
 * @type {Array<{label: string, value: string}>}
 */
export const locatorTypeOptions = [
    { label: "Test ID", value: "test_id" },
    { label: "ID", value: "id" },
    { label: "Name", value: "name" },
    { label: "Role", value: "role" },
    { label: "Label", value: "label" },
    { label: "Placeholder", value: "placeholder" },
    { label: "Text", value: "text" },
    { label: "CSS", value: "css" },
    { label: "XPath", value: "xpath" },
];

/**
 * 断言类型选项。
 * @type {Array<{label: string, value: string}>}
 */
export const assertionTypeOptions = [
    { label: "文本包含", value: "text_contains" },
    { label: "文本相等", value: "text_equals" },
    { label: "元素可见", value: "visible" },
    { label: "页面包含", value: "page_contains" },
    { label: "标题包含", value: "title_contains" },
    { label: "URL包含", value: "url_contains" },
    { label: "URL相等", value: "url_equals" },
];

/**
 * 键盘按键选项。
 * @type {Array<{label: string, value: string}>}
 */
export const keyboardKeyOptions = [
    ...[
        "Enter",
        "Tab",
        "Escape",
        "Space",
        "Backspace",
        "Delete",
        "Insert",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "Shift",
        "Control",
        "Alt",
        "Meta",
        "CapsLock",
        "NumLock",
        "ScrollLock",
        "PrintScreen",
        "Pause",
        "ContextMenu",
    ].map((value) => ({ label: value, value })),
    ...Array.from({ length: 12 }, (_, index) => {
        const value = `F${index + 1}`;
        return { label: value, value };
    }),
    ...Array.from({ length: 26 }, (_, index) => {
        const value = String.fromCharCode(65 + index);
        return { label: value, value };
    }),
    ...Array.from({ length: 10 }, (_, index) => {
        const value = `${index}`;
        return { label: value, value };
    }),
];

/**
 * 执行状态选项。
 * @type {Array<{label: string, value: number, type: string}>}
 */
export const runStatusOptions = [
    { label: "成功", value: 1, type: "success" },
    { label: "失败", value: 2, type: "danger" },
    { label: "已跳过", value: 3, type: "info" },
    { label: "异常", value: 8, type: "danger" },
    { label: "执行中", value: 9, type: "warning" },
];

/**
 * 录制状态选项。
 * @type {Array<{label: string, value: number, type: string}>}
 */
export const recordingStatusOptions = [
    { label: "草稿", value: 1, type: "info" },
    { label: "录制中", value: 2, type: "warning" },
    { label: "已完成", value: 3, type: "success" },
    { label: "失败", value: 4, type: "danger" },
    { label: "已停止", value: 5, type: "info" },
];

/**
 * 判断值是否为普通对象。
 * @param {any} value 待判断值
 * @returns {boolean} 是否为普通对象
 */
export function isPlainObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
}

/**
 * 标准化主键值。
 * @param {any} value 原始值
 * @returns {string|undefined} 标准化后的主键
 */
export function normalizeIdValue(value) {
    if (value === undefined || value === null || value === "") {
        return undefined;
    }
    return `${value}`;
}

/**
 * 判断两个主键是否相同。
 * @param {any} left 左值
 * @param {any} right 右值
 * @returns {boolean} 是否相同
 */
export function isSameId(left, right) {
    const leftId = normalizeIdValue(left);
    const rightId = normalizeIdValue(right);
    return Boolean(leftId) && leftId === rightId;
}

/**
 * 深拷贝数据，优先使用 structuredClone。
 * @param {any} value 原始值
 * @returns {any} 深拷贝结果
 */
export function cloneData(value) {
    const rawValue = toRaw(value);
    if (typeof structuredClone === "function") {
        return structuredClone(rawValue);
    }
    return JSON.parse(JSON.stringify(rawValue ?? null));
}

/**
 * 从接口响应中提取列表数据。
 * @param {Record<string, any>} response 接口响应
 * @returns {Array} 列表数据
 */
export function extractRows(response) {
    if (Array.isArray(response?.rows)) {
        return response.rows;
    }
    if (Array.isArray(response?.data)) {
        return response.data;
    }
    return [];
}

/**
 * 标准化项目选项。
 * @param {Record<string, any>} item 原始项目数据
 * @returns {Record<string, any>} 标准化后的项目数据
 */
export function normalizeProjectOption(item = {}) {
    return {
        ...item,
        projectId: normalizeIdValue(item.projectId ?? item.project_id),
        projectName: item.projectName || item.project_name || "-",
    };
}

/**
 * 标准化模块选项。
 * @param {Record<string, any>} item 原始模块数据
 * @returns {Record<string, any>} 标准化后的模块数据
 */
export function normalizeModuleOption(item = {}) {
    return {
        ...item,
        moduleId: normalizeIdValue(item.moduleId ?? item.module_id),
        projectId: normalizeIdValue(item.projectId ?? item.project_id),
        moduleName: item.moduleName || item.module_name || "-",
    };
}

/**
 * 标准化 Agent 选项。
 * @param {Record<string, any>} item 原始 Agent 数据
 * @returns {Record<string, any>} 标准化后的 Agent 数据
 */
export function normalizeAgentOption(item = {}) {
    return {
        ...item,
        agentId: normalizeIdValue(item.agentId ?? item.agent_id),
        agentCode: item.agentCode || item.agent_code || "",
        agentName: item.agentName || item.agent_name || "",
    };
}

/**
 * 标准化用例选项。
 * @param {Record<string, any>} item 原始用例数据
 * @returns {Record<string, any>|null} 标准化后的用例
 */
export function normalizeCaseOption(item = {}) {
    const webCaseId = normalizeIdValue(item.webCaseId ?? item.web_case_id);
    if (!webCaseId) {
        return null;
    }
    return {
        ...item,
        webCaseId,
        projectId: normalizeIdValue(item.projectId ?? item.project_id),
        moduleId: normalizeIdValue(item.moduleId ?? item.module_id),
        caseName: item.caseName || item.case_name || "",
        startUrl: item.startUrl || item.start_url || "",
        browserName: item.browserName || item.browser_name || "chromium",
        headless: item.headless ?? false,
        notes: item.notes || "",
    };
}

/**
 * 合并多个来源的用例选项并去重。
 * @param {...Array} collections 多个数据集合
 * @returns {Array} 合并后的用例列表
 */
export function mergeCaseOptions(...collections) {
    const optionMap = new Map();
    collections.flat().forEach((item) => {
        const normalized = normalizeCaseOption(item);
        if (!normalized?.webCaseId) {
            return;
        }
        const existing = optionMap.get(normalized.webCaseId) || {};
        optionMap.set(normalized.webCaseId, {
            ...existing,
            ...normalized,
            caseName:
                normalized.caseName ||
                existing.caseName ||
                normalized.webCaseId,
            projectId: normalized.projectId || existing.projectId,
            moduleId: normalized.moduleId || existing.moduleId,
        });
    });
    return Array.from(optionMap.values());
}

/**
 * 安全序列化 JSON。
 * @param {any} value 待序列化值
 * @returns {string} JSON 文本
 */
export function safeJsonStringify(value) {
    try {
        return JSON.stringify(value ?? {}, null, 2);
    } catch (error) {
        return "{}";
    }
}

/**
 * 解析可选 JSON 对象。
 * @param {string} text JSON 文本
 * @param {string} label 字段名称
 * @returns {Record<string, any>|undefined} 解析结果
 */
export function parseOptionalJsonObject(text, label) {
    const raw = `${text ?? ""}`.trim();
    if (!raw) return undefined;
    let parsed;
    try {
        parsed = JSON.parse(raw);
    } catch (error) {
        throw new Error(`${label} 解析失败：${error.message}`);
    }
    if (!isPlainObject(parsed)) {
        throw new Error(`${label} 必须是 JSON 对象`);
    }
    return parsed;
}

/**
 * 解析可选 JSON 数组。
 * @param {string} text JSON 文本
 * @param {string} label 字段名称
 * @returns {Array|undefined} 解析结果
 */
export function parseOptionalJsonArray(text, label) {
    const raw = `${text ?? ""}`.trim();
    if (!raw) return undefined;
    let parsed;
    try {
        parsed = JSON.parse(raw);
    } catch (error) {
        throw new Error(`${label} 解析失败：${error.message}`);
    }
    if (!Array.isArray(parsed)) {
        throw new Error(`${label} 必须是 JSON 数组`);
    }
    return parsed;
}
