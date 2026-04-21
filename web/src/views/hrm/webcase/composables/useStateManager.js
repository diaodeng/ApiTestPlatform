import { computed, ref, watch } from "vue";

/**
 * 状态配置域组合式逻辑。
 * @param {Object} options 依赖项
 * @returns {Object} 状态配置相关状态与方法
 */
export function useStateManager(options) {
    const {
        ElMessage,
        ElMessageBox,
        loading,
        projectOptions,
        moduleOptions,
        isPlainObject,
        isSameId,
        normalizeIdValue,
        parseOptionalJsonArray,
        parseOptionalJsonObject,
        safeJsonStringify,
        createEmptyRuntimeProfile,
        normalizeRuntimeProfile,
        normalizePersistScopeHostPatterns,
        normalizePersistContextScope,
        createEmptyBrowserSession,
        normalizeBrowserSession,
        normalizeStorageStatePayload,
        listWebRuntimeProfile,
        listWebBrowserSession,
        addWebBrowserSession,
        updateWebBrowserSession,
        delWebBrowserSession,
        addWebRuntimeProfile,
        updateWebRuntimeProfile,
        delWebRuntimeProfile,
    } = options;

    const runtimeProfiles = ref([]);
    const runtimeProfileKeyword = ref("");
    const runtimeProfileImportText = ref("");
    const runtimeProfileImportHost = ref("");
    const browserSessions = ref([]);
    const browserSessionKeyword = ref("");
    const browserSessionImportText = ref("");

    const showRuntimeProfileDialog = ref(false);
    const showBrowserSessionDialog = ref(false);
    const runtimeProfileForm = ref(createEmptyRuntimeProfile());
    const browserSessionForm = ref(createEmptyBrowserSession());

    const projectNameMap = computed(() =>
        projectOptions.value.reduce((accumulator, item) => {
            const targetId = normalizeIdValue(item.projectId);
            if (targetId) {
                accumulator[targetId] = item.projectName || `${item.projectId}`;
            }
            return accumulator;
        }, {}),
    );

    const moduleNameMap = computed(() =>
        moduleOptions.value.reduce((accumulator, item) => {
            const targetId = normalizeIdValue(item.moduleId);
            if (targetId) {
                accumulator[targetId] = item.moduleName || `${item.moduleId}`;
            }
            return accumulator;
        }, {}),
    );

    const filteredRuntimeProfileModules = computed(() => {
        if (!runtimeProfileForm.value.projectId) return moduleOptions.value;
        return moduleOptions.value.filter((item) =>
            isSameId(item.projectId, runtimeProfileForm.value.projectId),
        );
    });

    const filteredBrowserSessionModules = computed(() => {
        if (!browserSessionForm.value.projectId) return moduleOptions.value;
        return moduleOptions.value.filter((item) =>
            isSameId(item.projectId, browserSessionForm.value.projectId),
        );
    });

    const filteredRuntimeProfiles = computed(() => {
        const keyword = `${runtimeProfileKeyword.value || ""}`
            .trim()
            .toLowerCase();
        if (!keyword) return runtimeProfiles.value;
        return runtimeProfiles.value.filter((item) => {
            const scopeText = formatRuntimeProfileScope(item).toLowerCase();
            return (
                `${item.profileName || ""}`.toLowerCase().includes(keyword) ||
                scopeText.includes(keyword)
            );
        });
    });

    const filteredBrowserSessions = computed(() => {
        const keyword = `${browserSessionKeyword.value || ""}`
            .trim()
            .toLowerCase();
        if (!keyword) return browserSessions.value;
        return browserSessions.value.filter((item) => {
            const scopeText = formatRuntimeProfileScope(item).toLowerCase();
            return (
                `${item.sessionName || ""}`.toLowerCase().includes(keyword) ||
                `${item.scopeKey || ""}`.toLowerCase().includes(keyword) ||
                scopeText.includes(keyword)
            );
        });
    });

    /**
     * 标准化目标链路列表。
     * @param {Array<string>|string|undefined|null} targets 目标链路
     * @returns {Array<string>} 标准化后的目标链路列表
     */
    function normalizeRuntimeTargets(targets) {
        if (!Array.isArray(targets)) return ["web"];
        const normalized = targets
            .map((item) => `${item || ""}`.trim().toLowerCase())
            .filter(Boolean);
        return normalized.length ? normalized : ["web"];
    }

    /**
     * 判断配置是否支持 Web 链路。
     * @param {Record<string, any>} profile 配置对象
     * @returns {boolean} 是否支持 Web
     */
    function profileSupportsWeb(profile) {
        const targets = normalizeRuntimeTargets(profile?.targets);
        return targets.includes("web");
    }

    /**
     * 判断配置作用域是否匹配项目与模块。
     * @param {Record<string, any>} profile 配置对象
     * @param {any} projectId 项目ID
     * @param {any} moduleId 模块ID
     * @returns {boolean} 是否匹配
     */
    function isRuntimeProfileScopeMatch(profile, projectId, moduleId) {
        if (!profile) return false;
        const profileProjectId = normalizeIdValue(profile.projectId);
        const profileModuleId = normalizeIdValue(profile.moduleId);
        const targetProjectId = normalizeIdValue(projectId);
        const targetModuleId = normalizeIdValue(moduleId);
        if (profileProjectId && profileProjectId !== targetProjectId) {
            return false;
        }
        if (profileModuleId && profileModuleId !== targetModuleId) {
            return false;
        }
        return true;
    }

    /**
     * 判断 Session 是否匹配浏览器。
     * @param {Record<string, any>} session Session 对象
     * @param {string} browserName 浏览器名称
     * @returns {boolean} 是否匹配
     */
    function isBrowserSessionBrowserMatch(session, browserName) {
        const sessionBrowser = `${session?.browserName || ""}`
            .trim()
            .toLowerCase();
        const currentBrowser = `${browserName || ""}`.trim().toLowerCase();
        return !sessionBrowser || !currentBrowser || sessionBrowser === currentBrowser;
    }

    /**
     * 获取项目名称。
     * @param {any} projectId 项目ID
     * @returns {string} 项目名称
     */
    function getProjectName(projectId) {
        const targetId = normalizeIdValue(projectId);
        if (!targetId) return "";
        return (
            projectNameMap.value[targetId] ||
            projectOptions.value.find((item) => isSameId(item.projectId, targetId))
                ?.projectName ||
            ""
        );
    }

    /**
     * 获取模块名称。
     * @param {any} moduleId 模块ID
     * @returns {string} 模块名称
     */
    function getModuleName(moduleId) {
        const targetId = normalizeIdValue(moduleId);
        if (!targetId) return "";
        return (
            moduleNameMap.value[targetId] ||
            moduleOptions.value.find((item) => isSameId(item.moduleId, targetId))
                ?.moduleName ||
            ""
        );
    }

    /**
     * 格式化配置适用范围。
     * @param {Record<string, any>} profile 配置对象
     * @returns {string} 适用范围文本
     */
    function formatRuntimeProfileScope(profile) {
        const projectText = profile?.projectId
            ? getProjectName(profile.projectId) || profile.projectId
            : "全部项目";
        const moduleText = profile?.moduleId
            ? getModuleName(profile.moduleId) || profile.moduleId
            : "全部模块";
        return `${projectText} / ${moduleText}`;
    }

    /**
     * 格式化配置标签。
     * @param {Record<string, any>} profile 配置对象
     * @returns {string} 标签文本
     */
    function formatRuntimeProfileLabel(profile) {
        const name = profile?.profileName || profile?.profileId || "未命名配置";
        return `${name}（${formatRuntimeProfileScope(profile)}）`;
    }

    /**
     * 格式化 Session 标签。
     * @param {Record<string, any>} session Session 对象
     * @returns {string} 标签文本
     */
    function formatBrowserSessionLabel(session) {
        const name = session?.sessionName || session?.sessionId || "未命名Session";
        const browserLabel = `${session?.browserName || ""}`.trim();
        return `${name}（${formatRuntimeProfileScope(session)}${browserLabel ? ` / ${browserLabel}` : ""}）`;
    }

    /**
     * 清理已失效的当前表单绑定。
     * @returns {void}
     */
    function clearInvalidSelections() {
        const runtimeIds = new Set(
            runtimeProfiles.value
                .map((item) => normalizeIdValue(item.profileId))
                .filter(Boolean),
        );
        if (
            runtimeProfileForm.value.profileId &&
            !runtimeIds.has(normalizeIdValue(runtimeProfileForm.value.profileId))
        ) {
            runtimeProfileForm.value = createEmptyRuntimeProfile();
        }

        const sessionIds = new Set(
            browserSessions.value
                .map((item) => normalizeIdValue(item.sessionId))
                .filter(Boolean),
        );
        if (
            browserSessionForm.value.sessionId &&
            !sessionIds.has(normalizeIdValue(browserSessionForm.value.sessionId))
        ) {
            browserSessionForm.value = createEmptyBrowserSession();
        }
    }

    /**
     * 新建运行配置草稿。
     * @returns {void}
     */
    function createRuntimeProfileDraft() {
        runtimeProfileForm.value = createEmptyRuntimeProfile();
        runtimeProfileImportText.value = "";
        runtimeProfileImportHost.value = "";
    }

    /**
     * 处理运行配置行切换。
     * @param {Record<string, any>} row 当前行
     * @returns {void}
     */
    function handleRuntimeProfileRowChange(row) {
        if (!row) return;
        runtimeProfileForm.value = normalizeRuntimeProfile(row);
    }

    /**
     * 加载运行配置列表。
     * @returns {Promise<void>} 加载完成
     */
    function loadRuntimeProfiles() {
        loading.value.runtimeProfile = true;
        return listWebRuntimeProfile({ isPage: false })
            .then((response) => {
                const rows = Array.isArray(response?.data) ? response.data : [];
                runtimeProfiles.value = rows.map((item) =>
                    normalizeRuntimeProfile(item),
                );
                clearInvalidSelections();
            })
            .finally(() => {
                loading.value.runtimeProfile = false;
            });
    }

    /**
     * 新建浏览器 Session 草稿。
     * @returns {void}
     */
    function createBrowserSessionDraft() {
        browserSessionForm.value = createEmptyBrowserSession();
        browserSessionImportText.value = "";
    }

    /**
     * 处理浏览器 Session 行切换。
     * @param {Record<string, any>} row 当前行
     * @returns {void}
     */
    function handleBrowserSessionRowChange(row) {
        if (!row) return;
        browserSessionForm.value = normalizeBrowserSession(row);
    }

    /**
     * 加载浏览器 Session 列表。
     * @returns {Promise<void>} 加载完成
     */
    function loadBrowserSessions() {
        loading.value.browserSession = true;
        return listWebBrowserSession({ isPage: false })
            .then((response) => {
                const rows = Array.isArray(response?.data) ? response.data : [];
                browserSessions.value = rows.map((item) =>
                    normalizeBrowserSession(item),
                );
                clearInvalidSelections();
            })
            .finally(() => {
                loading.value.browserSession = false;
            });
    }

    /**
     * 打开浏览器 Session 管理弹窗。
     * @returns {void}
     */
    function openBrowserSessionDialog() {
        showBrowserSessionDialog.value = true;
        if (!browserSessions.value.length) {
            loadBrowserSessions();
        }
        if (!browserSessionForm.value.sessionId) {
            createBrowserSessionDraft();
        }
    }

    /**
     * 打开运行配置弹窗。
     * @returns {void}
     */
    function openRuntimeProfileDialog() {
        showRuntimeProfileDialog.value = true;
        if (!runtimeProfiles.value.length) {
            loadRuntimeProfiles();
        }
        if (!runtimeProfileForm.value.profileId) {
            createRuntimeProfileDraft();
        }
    }

    /**
     * 构造浏览器 Session 提交数据。
     * @returns {Record<string, any>} 提交数据
     */
    function buildBrowserSessionPayload() {
        const sessionName = `${browserSessionForm.value.sessionName || ""}`.trim();
        if (!sessionName) {
            throw new Error("Session名称不能为空");
        }
        const scopeKey = `${browserSessionForm.value.scopeKey || ""}`.trim();
        if (!scopeKey) {
            throw new Error("作用域Key不能为空");
        }
        const storageState =
            parseOptionalJsonObject(
                browserSessionForm.value.storageStateText,
                "StorageState",
            ) || {};
        return {
            sessionId: browserSessionForm.value.sessionId || undefined,
            sessionName,
            scopeKey,
            enabled: browserSessionForm.value.enabled !== false,
            projectId: browserSessionForm.value.projectId || undefined,
            moduleId: browserSessionForm.value.moduleId || undefined,
            browserName:
                `${browserSessionForm.value.browserName || ""}`
                    .trim()
                    .toLowerCase() || undefined,
            sort: Math.max(
                Math.round(Number(browserSessionForm.value.sort) || 0),
                0,
            ),
            hostPatterns: normalizePersistScopeHostPatterns(
                browserSessionForm.value.hostPatternsText,
            ),
            storageState: normalizeStorageStatePayload(storageState),
            remark: browserSessionForm.value.remark || undefined,
        };
    }

    /**
     * 保存浏览器 Session。
     * @returns {void}
     */
    function saveBrowserSession() {
        let payload;
        try {
            payload = buildBrowserSessionPayload();
        } catch (error) {
            ElMessage.error(error.message);
            return;
        }
        loading.value.browserSessionSave = true;
        const request = payload.sessionId
            ? updateWebBrowserSession(payload)
            : addWebBrowserSession(payload);
        request
            .then((response) => {
                const saved = normalizeBrowserSession(response?.data || payload);
                ElMessage.success(response?.msg || "保存成功");
                return loadBrowserSessions().then(() => {
                    const hit = browserSessions.value.find((item) =>
                        isSameId(item.sessionId, saved.sessionId),
                    );
                    browserSessionForm.value = normalizeBrowserSession(
                        hit || saved,
                    );
                });
            })
            .finally(() => {
                loading.value.browserSessionSave = false;
            });
    }

    /**
     * 删除浏览器 Session。
     * @returns {void}
     */
    function deleteBrowserSession() {
        const sessionId = browserSessionForm.value.sessionId;
        if (!sessionId) {
            ElMessage.warning("请先选择要删除的Session");
            return;
        }
        ElMessageBox.confirm(
            `确认删除Session【${browserSessionForm.value.sessionName || sessionId}】吗？`,
            "提示",
            { type: "warning" },
        )
            .then(() => delWebBrowserSession(sessionId))
            .then(async () => {
                ElMessage.success("删除成功");
                createBrowserSessionDraft();
                await loadBrowserSessions();
            })
            .catch(() => {});
    }

    /**
     * 从导入文本中提取 Cookie Header 内容。
     * @param {string} rawText 原始文本
     * @returns {string} Cookie 文本
     */
    function extractCookieContentFromImport(rawText) {
        const raw = `${rawText ?? ""}`.trim();
        if (!raw) return "";
        if (raw.startsWith("{") && raw.endsWith("}")) {
            try {
                const parsed = JSON.parse(raw);
                if (isPlainObject(parsed)) {
                    const cookieValue = parsed.Cookie || parsed.cookie;
                    if (typeof cookieValue === "string" && cookieValue.trim()) {
                        return cookieValue.trim();
                    }
                }
            } catch {
                // ignore
            }
        }
        const lines = raw
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter(Boolean);
        for (const line of lines) {
            const matched = line.match(/^cookie\s*:\s*(.+)$/i);
            if (matched && matched[1]) {
                return matched[1].trim();
            }
        }
        if (/^cookie\s*=/i.test(raw)) {
            return raw.replace(/^cookie\s*=/i, "").trim();
        }
        if (/^cookie\s*:/i.test(raw)) {
            return raw.replace(/^cookie\s*:/i, "").trim();
        }
        return raw;
    }

    /**
     * 从导入文本中提取 Set-Cookie 行。
     * @param {string} rawText 原始文本
     * @returns {Array<string>} Set-Cookie 行列表
     */
    function extractSetCookieLinesFromImport(rawText) {
        const raw = `${rawText ?? ""}`.trim();
        if (!raw) return [];
        const lines = [];
        if (raw.startsWith("{") && raw.endsWith("}")) {
            try {
                const parsed = JSON.parse(raw);
                if (isPlainObject(parsed)) {
                    const setCookieValue =
                        parsed["Set-Cookie"] ||
                        parsed["set-cookie"] ||
                        parsed.setCookie ||
                        parsed.set_cookie;
                    if (Array.isArray(setCookieValue)) {
                        setCookieValue.forEach((item) => {
                            const text = `${item ?? ""}`.trim();
                            if (text) lines.push(text);
                        });
                    } else if (
                        typeof setCookieValue === "string" &&
                        setCookieValue.trim()
                    ) {
                        lines.push(setCookieValue.trim());
                    }
                }
            } catch {
                // ignore
            }
        }
        if (lines.length) return lines;
        raw.split(/\r?\n/).forEach((line) => {
            const matched = `${line || ""}`
                .trim()
                .match(/^set-cookie\s*:\s*(.+)$/i);
            if (matched && matched[1]) {
                lines.push(matched[1].trim());
            }
        });
        if (lines.length) return lines;
        if (/^set-cookie\s*[:=]/i.test(raw)) {
            const text = raw.replace(/^set-cookie\s*[:=]/i, "").trim();
            if (text) return [text];
        }
        return [];
    }

    /**
     * 解析 Cookie Header 键值对。
     * @param {string} cookieText Cookie 文本
     * @returns {Array<Record<string, any>>} Cookie 列表
     */
    function parseCookiePairs(cookieText) {
        const raw = `${cookieText ?? ""}`.trim();
        if (!raw) return [];
        const entries = raw
            .split(";")
            .map((item) => item.trim())
            .filter(Boolean);
        const cookieMap = new Map();
        entries.forEach((entry) => {
            const index = entry.indexOf("=");
            if (index <= 0) return;
            const name = entry.slice(0, index).trim();
            const value = entry.slice(index + 1).trim();
            if (!name || !value) return;
            cookieMap.set(name, { name, value });
        });
        return Array.from(cookieMap.values());
    }

    /**
     * 标准化 SameSite 字段。
     * @param {string} value 原始值
     * @returns {string|undefined} 标准值
     */
    function normalizeSameSiteValue(value) {
        const normalized = `${value || ""}`.trim().toLowerCase();
        if (normalized === "lax") return "Lax";
        if (normalized === "strict") return "Strict";
        if (normalized === "none") return "None";
        return undefined;
    }

    /**
     * 解析 expires 时间戳。
     * @param {string} rawValue 原始值
     * @returns {number|undefined} Unix 时间戳
     */
    function parseExpiresTimestamp(rawValue) {
        const text = `${rawValue || ""}`.trim();
        if (!text) return undefined;
        const parsed = Date.parse(text);
        if (!Number.isFinite(parsed)) {
            return undefined;
        }
        return Math.floor(parsed / 1000);
    }

    /**
     * 解析单条 Set-Cookie。
     * @param {string} line Set-Cookie 文本
     * @returns {Record<string, any>|null} 解析结果
     */
    function parseSetCookieLine(line) {
        const text = `${line || ""}`.trim();
        if (!text) return null;
        const parts = text
            .split(";")
            .map((item) => item.trim())
            .filter(Boolean);
        if (!parts.length) return null;
        const first = parts[0];
        const eqIndex = first.indexOf("=");
        if (eqIndex <= 0) return null;
        const name = first.slice(0, eqIndex).trim();
        const value = first.slice(eqIndex + 1).trim();
        if (!name || !value) return null;
        const cookie = { name, value };
        parts.slice(1).forEach((part) => {
            const idx = part.indexOf("=");
            const rawKey = (idx >= 0 ? part.slice(0, idx) : part)
                .trim()
                .toLowerCase();
            const rawValue = idx >= 0 ? part.slice(idx + 1).trim() : "";
            if (!rawKey) return;
            if (rawKey === "domain" && rawValue) {
                cookie.domain = rawValue;
                return;
            }
            if (rawKey === "path" && rawValue) {
                cookie.path = rawValue;
                return;
            }
            if (rawKey === "secure") {
                cookie.secure = true;
                return;
            }
            if (rawKey === "httponly") {
                cookie.httpOnly = true;
                return;
            }
            if (rawKey === "samesite") {
                const sameSite = normalizeSameSiteValue(rawValue);
                if (sameSite) {
                    cookie.sameSite = sameSite;
                }
                return;
            }
            if (rawKey === "expires") {
                const expires = parseExpiresTimestamp(rawValue);
                if (expires !== undefined) {
                    cookie.expires = expires;
                }
                return;
            }
            if (rawKey === "max-age") {
                const age = Number(rawValue);
                if (Number.isFinite(age)) {
                    cookie.expires =
                        Math.floor(Date.now() / 1000) +
                        Math.max(Math.round(age), 0);
                }
            }
        });
        return cookie;
    }

    /**
     * 快速导入运行配置 Cookie 规则。
     * @returns {void}
     */
    function applyRuntimeProfileQuickImport() {
        const setCookieLines = extractSetCookieLinesFromImport(
            runtimeProfileImportText.value,
        );
        const cookiesFromSetCookie = setCookieLines
            .map((line) => parseSetCookieLine(line))
            .filter(Boolean);
        const cookieText = extractCookieContentFromImport(
            runtimeProfileImportText.value,
        );
        const cookiesFromCookieHeader = parseCookiePairs(cookieText);
        const useSetCookie = cookiesFromSetCookie.length > 0;
        const cookies = useSetCookie
            ? cookiesFromSetCookie
            : cookiesFromCookieHeader;
        if (!cookies.length) {
            ElMessage.error("未识别到可用 Cookie，请粘贴 Cookie 或 Set-Cookie 内容");
            return;
        }

        let currentRules = [];
        try {
            currentRules =
                parseOptionalJsonArray(
                    runtimeProfileForm.value.cookieRulesText,
                    "Cookie规则",
                ) || [];
        } catch (error) {
            ElMessage.error(error.message);
            return;
        }

        const matchHost = `${runtimeProfileImportHost.value || ""}`.trim();
        const ruleName =
            runtimeProfileForm.value.profileName?.trim() ||
            `导入Cookie-${new Date().toISOString().slice(0, 19)}`;
        currentRules.push({
            name: ruleName,
            match: matchHost ? { host: matchHost } : {},
            applyOn: ["before_start", "before_step", "before_goto"],
            cookies,
        });
        runtimeProfileForm.value.cookieRulesText = safeJsonStringify(currentRules);
        ElMessage.success(
            `已导入 ${cookies.length} 个 Cookie${useSetCookie ? "（Set-Cookie）" : ""}`,
        );
    }

    /**
     * 快速导入浏览器 Session 的 StorageState。
     * @returns {void}
     */
    function applyBrowserSessionQuickImport() {
        const rawText = `${browserSessionImportText.value || ""}`.trim();
        if (!rawText) {
            ElMessage.warning("请先粘贴 Cookie/Set-Cookie/StorageState 内容");
            return;
        }
        try {
            const parsed = JSON.parse(rawText);
            if (
                isPlainObject(parsed) &&
                (Array.isArray(parsed.cookies) || Array.isArray(parsed.origins))
            ) {
                const normalized = normalizeStorageStatePayload(parsed);
                browserSessionForm.value.storageStateText =
                    safeJsonStringify(normalized);
                ElMessage.success(
                    `已导入 StorageState：cookies ${normalized.cookies.length} 条，origins ${normalized.origins.length} 条`,
                );
                return;
            }
        } catch {
            // ignore
        }

        const setCookieLines = extractSetCookieLinesFromImport(rawText);
        const cookiesFromSetCookie = setCookieLines
            .map((line) => parseSetCookieLine(line))
            .filter(Boolean);
        const cookieText = extractCookieContentFromImport(rawText);
        const cookiesFromCookieHeader = parseCookiePairs(cookieText);
        const useSetCookie = cookiesFromSetCookie.length > 0;
        const cookies = useSetCookie
            ? cookiesFromSetCookie
            : cookiesFromCookieHeader;
        if (!cookies.length) {
            ElMessage.error(
                "未识别到可用数据，请粘贴 Cookie/Set-Cookie 或 storage_state JSON",
            );
            return;
        }
        browserSessionForm.value.storageStateText = safeJsonStringify({
            cookies,
            origins: [],
        });
        ElMessage.success(
            `已导入 ${cookies.length} 个 Cookie${useSetCookie ? "（Set-Cookie）" : ""}`,
        );
    }

    /**
     * 新增保留上下文作用域行。
     * @returns {void}
     */
    function addPersistContextScopeRow() {
        if (!Array.isArray(runtimeProfileForm.value.persistContextScopes)) {
            runtimeProfileForm.value.persistContextScopes = [];
        }
        runtimeProfileForm.value.persistContextScopes.push({
            key: "",
            label: "",
            hostPatterns: [],
            hostPatternsText: "",
            enabled: true,
            remark: "",
        });
    }

    /**
     * 删除保留上下文作用域行。
     * @param {number} index 行索引
     * @returns {void}
     */
    function removePersistContextScopeRow(index) {
        if (!Array.isArray(runtimeProfileForm.value.persistContextScopes)) return;
        runtimeProfileForm.value.persistContextScopes.splice(index, 1);
    }

    /**
     * 构造保留上下文作用域提交数据。
     * @param {Array<Record<string, any>>} scopes 作用域列表
     * @returns {Array<Record<string, any>>} 提交数据
     */
    function buildPersistContextScopesPayload(scopes) {
        const source = Array.isArray(scopes) ? scopes : [];
        const result = [];
        const seen = new Set();
        source.forEach((item) => {
            const scope = normalizePersistContextScope({
                ...item,
                hostPatterns: normalizePersistScopeHostPatterns(
                    item?.hostPatternsText || item?.hostPatterns,
                ),
            });
            if (!scope) return;
            const keyLower = `${scope.key}`.toLowerCase();
            if (seen.has(keyLower)) return;
            seen.add(keyLower);
            result.push({
                key: scope.key,
                label: scope.label || scope.key,
                hostPatterns: normalizePersistScopeHostPatterns(scope.hostPatterns),
                enabled: scope.enabled !== false,
                remark: scope.remark || undefined,
            });
        });
        return result;
    }

    /**
     * 构造运行配置提交数据。
     * @returns {Record<string, any>} 提交数据
     */
    function buildRuntimeProfilePayload() {
        const profileName = `${runtimeProfileForm.value.profileName || ""}`.trim();
        if (!profileName) {
            throw new Error("配置名称不能为空");
        }
        const runtimeOverrides =
            parseOptionalJsonObject(
                runtimeProfileForm.value.runtimeOverridesText,
                "运行覆盖",
            ) || {};
        const variables =
            parseOptionalJsonObject(runtimeProfileForm.value.variablesText, "变量") ||
            {};
        const cookieRules =
            parseOptionalJsonArray(
                runtimeProfileForm.value.cookieRulesText,
                "Cookie规则",
            ) || [];
        const persistContextScopes = buildPersistContextScopesPayload(
            runtimeProfileForm.value.persistContextScopes,
        );
        const targets = normalizeRuntimeTargets(runtimeProfileForm.value.targets);
        return {
            profileId: runtimeProfileForm.value.profileId || undefined,
            profileName,
            profileType: "runtime",
            targets,
            enabled: runtimeProfileForm.value.enabled !== false,
            projectId: runtimeProfileForm.value.projectId || undefined,
            moduleId: runtimeProfileForm.value.moduleId || undefined,
            sort: Math.max(
                Math.round(Number(runtimeProfileForm.value.sort) || 0),
                0,
            ),
            runtimeOverrides,
            variables,
            cookieRules,
            persistContextScopes,
            remark: runtimeProfileForm.value.remark || undefined,
        };
    }

    /**
     * 保存运行配置。
     * @returns {void}
     */
    function saveRuntimeProfile() {
        let payload;
        try {
            payload = buildRuntimeProfilePayload();
        } catch (error) {
            ElMessage.error(error.message);
            return;
        }
        loading.value.runtimeProfileSave = true;
        const request = payload.profileId
            ? updateWebRuntimeProfile(payload)
            : addWebRuntimeProfile(payload);
        request
            .then((response) => {
                const saved = normalizeRuntimeProfile(response?.data || payload);
                ElMessage.success(response?.msg || "保存成功");
                return loadRuntimeProfiles().then(() => {
                    const hit = runtimeProfiles.value.find((item) =>
                        isSameId(item.profileId, saved.profileId),
                    );
                    runtimeProfileForm.value = normalizeRuntimeProfile(hit || saved);
                });
            })
            .finally(() => {
                loading.value.runtimeProfileSave = false;
            });
    }

    /**
     * 删除运行配置。
     * @returns {void}
     */
    function deleteRuntimeProfile() {
        const profileId = runtimeProfileForm.value.profileId;
        if (!profileId) {
            ElMessage.warning("请先选择要删除的配置");
            return;
        }
        ElMessageBox.confirm(
            `确认删除配置【${runtimeProfileForm.value.profileName || profileId}】吗？`,
            "提示",
            { type: "warning" },
        )
            .then(() => delWebRuntimeProfile(profileId))
            .then(async () => {
                ElMessage.success("删除成功");
                createRuntimeProfileDraft();
                await loadRuntimeProfiles();
            })
            .catch(() => {});
    }

    watch(
        () => runtimeProfileForm.value.projectId,
        (projectId) => {
            if (!projectId) {
                runtimeProfileForm.value.moduleId = undefined;
                return;
            }
            if (
                !filteredRuntimeProfileModules.value.some((item) =>
                    isSameId(item.moduleId, runtimeProfileForm.value.moduleId),
                )
            ) {
                runtimeProfileForm.value.moduleId = undefined;
            }
        },
    );

    watch(
        () => browserSessionForm.value.projectId,
        (projectId) => {
            if (!projectId) {
                browserSessionForm.value.moduleId = undefined;
                return;
            }
            if (
                !filteredBrowserSessionModules.value.some((item) =>
                    isSameId(item.moduleId, browserSessionForm.value.moduleId),
                )
            ) {
                browserSessionForm.value.moduleId = undefined;
            }
        },
    );

    return {
        runtimeProfiles,
        runtimeProfileKeyword,
        runtimeProfileImportText,
        runtimeProfileImportHost,
        browserSessions,
        browserSessionKeyword,
        browserSessionImportText,
        showRuntimeProfileDialog,
        showBrowserSessionDialog,
        runtimeProfileForm,
        browserSessionForm,
        filteredRuntimeProfileModules,
        filteredBrowserSessionModules,
        filteredRuntimeProfiles,
        filteredBrowserSessions,
        profileSupportsWeb,
        isRuntimeProfileScopeMatch,
        isBrowserSessionBrowserMatch,
        formatRuntimeProfileScope,
        formatRuntimeProfileLabel,
        formatBrowserSessionLabel,
        createRuntimeProfileDraft,
        handleRuntimeProfileRowChange,
        loadRuntimeProfiles,
        createBrowserSessionDraft,
        handleBrowserSessionRowChange,
        loadBrowserSessions,
        openBrowserSessionDialog,
        openRuntimeProfileDialog,
        applyRuntimeProfileQuickImport,
        applyBrowserSessionQuickImport,
        addPersistContextScopeRow,
        removePersistContextScopeRow,
        deleteRuntimeProfile,
        saveRuntimeProfile,
        deleteBrowserSession,
        saveBrowserSession,
    };
}
