/** mitmproxy 页面：启停控制、流量表、详情、断点放行、证书、设置。 */
const { Bus, call, el, $, clear, toast, openModal, textInput, checkbox, select, copyText, kvTable } = window.QTR;

export function mitmPage(mount) {
  let config = null;
  let state = "stopped";
  let webUrl = "";
  let flows = []; // FlowItem 字典数组
  let selectedFlow = null;
  let showDetail = true;
  // 后端解析出的默认证书路径（证书路径留空时的实际生效值，用于设置弹窗占位提示）
  let defaultCertPath = "";
  const FLOW_LIMIT_DEFAULT = 500;

  // ===== 工具栏 =====
  const stateChip = el("span", { class: "chip", text: "已停止" });
  const modeChip = el("span", { class: "chip", text: "模式: -" });
  const countChip = el("span", { class: "chip badge-flow-count", text: "记录 0 条" });
  const certLabel = el("span", { class: "muted small", text: "证书状态：-" });
  const webUrlLabel = el("a", { class: "muted small mono", text: "", href: "#", style: "display:none" });

  const btnStart = el("button", { class: "btn primary", text: "启动" });
  const btnStop = el("button", { class: "btn", text: "停止", disabled: true });
  const btnClear = el("button", { class: "btn", text: "清空", disabled: true });
  const btnToggleDetail = el("button", { class: "btn", text: "隐藏详情", disabled: true });
  const btnOpenWeb = el("button", { class: "btn", text: "打开 Web 页面" });
  const btnSettings = el("button", { class: "btn", text: "设置" });
  const btnInstallCert = el("button", { class: "btn small", text: "安装当前用户证书" });
  const filterInput = textInput("", { placeholder: "按 URL 过滤", style: "width:200px" });

  // ===== 流量表 =====
  const flowTbody = el("tbody", {});
  const flowTable = el(
    "table", { class: "data" },
    el("thead", {}, el("tr", {},
      el("th", { text: "时间" }), el("th", { text: "方法" }), el("th", { text: "Host" }),
      el("th", { text: "Path" }), el("th", { text: "状态" }), el("th", { text: "大小" }),
      el("th", { text: "耗时" }), el("th", { text: "断点" }))));

  // ===== 详情区 =====
  const detailTabs = el("div", { class: "toolbar", style: "margin:0" });
  const detailPre = el("pre", { class: "panel flex-fill" });
  const btnPass = el("button", { class: "btn small primary", text: "继续放行", style: "display:none" });
  const btnEditPass = el("button", { class: "btn small", text: "编辑并放行", style: "display:none" });

  mount.append(
    el("div", { class: "toolbar" },
      el("span", { text: "mitmproxy", style: "font-weight:600;font-size:15px" }),
      stateChip, modeChip, countChip,
      el("div", { style: "flex:1" }),
      filterInput,
      btnStart, btnStop, btnClear, btnToggleDetail, btnOpenWeb, btnSettings),
    el("div", { class: "toolbar" },
      certLabel, btnInstallCert, webUrlLabel),
    el("div", { class: "split-v flex-fill" },
      el("div", { class: "col", style: "flex:3" },
        el("div", { class: "table-wrap flex-fill" }, flowTable)),
      el("div", { class: "col", style: "flex:2" },
        el("div", { class: "toolbar", style: "margin:0" }, detailTabs, btnPass, btnEditPass),
        detailPre))
  );
  flowTable.append(flowTbody);

  let detailTab = "request";
  ["request", "response"].forEach((tab) => {
    const btn = el("button", { class: "btn small", text: tab === "request" ? "请求" : "响应" });
    btn.addEventListener("click", () => { detailTab = tab; renderDetail(); markTab(tab); });
    btn.dataset.tab = tab;
    detailTabs.append(btn);
  });
  function markTab(tab) {
    for (const b of detailTabs.children) b.classList.toggle("primary", b.dataset.tab === tab);
  }

  // ===== 渲染 =====
  function renderFlows() {
    const keyword = filterInput.value.trim().toLowerCase();
    clear(flowTbody);
    const list = flows.filter((f) => !keyword || (f.url || "").toLowerCase().includes(keyword) || (f.host || "").toLowerCase().includes(keyword));
    for (const f of list) {
      const tr = el("tr", {
        class: selectedFlow && selectedFlow.id === f.id ? "selected" : "",
        onclick: () => { selectedFlow = f; renderFlows(); renderDetail(); },
      },
        el("td", { class: "mono small", text: f.time || "" }),
        el("td", { text: f.method || "" }),
        el("td", { class: "small", text: f.request_host || "" }),
        el("td", { class: "mono small", text: f.path || "" }),
        el("td", { class: "small", text: f.status_code ? String(f.status_code) : "..." }),
        el("td", { class: "small", text: formatBytes(f.size) }),
        el("td", { class: "small", text: f.duration_ms != null ? f.duration_ms + "ms" : "-" }),
        el("td", {}, f.breakpoint_paused ? el("span", { class: "chip warn", text: "已暂停" }) : (f.breakpoint_matched ? el("span", { class: "chip ok", text: "匹配" }) : ""))
      );
      flowTbody.append(tr);
    }
    countChip.textContent = `记录 ${flows.length} 条`;
  }

  function formatBytes(size) {
    if (size == null) return "-";
    if (size < 1024) return size + "B";
    if (size < 1024 * 1024) return (size / 1024).toFixed(1) + "KB";
    return (size / 1024 / 1024).toFixed(2) + "MB";
  }

  function renderDetail() {
    btnPass.style.display = "none";
    btnEditPass.style.display = "none";
    if (!selectedFlow) {
      detailPre.textContent = "点击左侧流量查看详情";
      markTab(detailTab);
      return;
    }
    markTab(detailTab);
    if (detailTab === "response" && !selectedFlow.response_headers && !selectedFlow.response_body) {
      detailPre.textContent = "（暂无响应数据）";
    } else {
      const lines = [];
      const src = detailTab === "request" ? selectedFlow : selectedFlow;
      const prefix = detailTab === "request" ? "request" : "response";
      lines.push(`${(src[`${prefix}_http_version`] || "").toUpperCase()} ${detailTab === "request" ? src.method + " " + (src.url || "") : (src.status_code || "") + " " + (src.response_reason || "")}`);
      lines.push("");
      lines.push(src[`${prefix}_headers`] || "（无 headers）");
      if (detailTab === "request" && src.request_cookies) { lines.push("", "[Cookies]", src.request_cookies); }
      if (detailTab === "request" && src.request_form) { lines.push("", "[Form]", src.request_form); }
      if (src[`${prefix}_body`]) { lines.push("", "[Body]", String(src[`${prefix}_body`]).slice(0, 20000)); }
      detailPre.textContent = lines.join("\n") || "（空）";
    }
    // 断点操作
    if (selectedFlow.breakpoint_paused) {
      btnPass.style.display = "";
      btnEditPass.style.display = "";
    }
  }

  function applyState() {
    const running = ["starting", "running", "stopping"].includes(state);
    btnStart.disabled = running;
    btnStop.disabled = !running;
    btnClear.disabled = false;
    btnToggleDetail.disabled = false;
    stateChip.className = "chip " + (state === "running" ? "ok" : running ? "warn" : "");
    stateChip.textContent = { stopped: "已停止", starting: "启动中", running: "运行中", stopping: "停止中" }[state] || state;
    modeChip.textContent = "模式: " + (config?.startup_mode === "web" ? "Web" : "dump") +
      (config?.startup_mode === "web" && config?.web_open_browser ? "(开浏览器)" : "");
    if (state === "running" && webUrl) {
      webUrlLabel.style.display = "";
      webUrlLabel.textContent = webUrl;
      webUrlLabel.href = webUrl;
    } else {
      webUrlLabel.style.display = "none";
    }
  }

  // ===== 事件 =====
  btnStart.addEventListener("click", () => call("mitm", "start"));
  btnStop.addEventListener("click", () => call("mitm", "stop"));
  btnClear.addEventListener("click", () => { flows = []; selectedFlow = null; renderFlows(); renderDetail(); });
  btnToggleDetail.addEventListener("click", () => {
    showDetail = !showDetail;
    btnToggleDetail.textContent = showDetail ? "隐藏详情" : "显示详情";
    detailPre.style.display = showDetail ? "" : "none";
    detailTabs.style.display = showDetail ? "" : "none";
  });
  btnOpenWeb.addEventListener("click", async () => {
    const res = await call("mitm", "open_web");
    if (!res.ok) return toast(res.message, "error");
    window.open(res.web_url, "_blank");
  });
  btnInstallCert.addEventListener("click", async () => {
    const res = await call("mitm", "install_cert");
    toast(res.message || (res.ok ? "安装成功" : "安装失败"), res.ok ? "success" : "error");
  });
  filterInput.addEventListener("input", renderFlows);

  btnPass.addEventListener("click", () => passFlow({}));
  btnEditPass.addEventListener("click", () => openBreakpointEditor(selectedFlow));
  async function passFlow(payload) {
    if (!selectedFlow) return;
    const stage = detailTab === "response" ? "response" : "request";
    const res = await call("mitm", "continue_flow", selectedFlow.id, stage, payload);
    if (!res.ok) toast(res.message, "error");
    else toast("断点已放行", "success", 1500);
  }

  /** 断点编辑弹窗：可编辑请求/响应体后放行。 */
  function openBreakpointEditor(flow) {
    const stage = detailTab === "response" ? "response" : "request";
    const headersArea = el("textarea", { class: "input mono", rows: 8, style: "width:100%" });
    headersArea.value = flow[`${stage}_headers`] || "";
    const bodyArea = el("textarea", { class: "input mono", rows: 8, style: "width:100%" });
    bodyArea.value = flow[`${stage}_body`] || "";
    const statusInput = textInput(String(flow.status_code || ""), { type: "number", style: "width:100px" });
    const body = el(
      "div", {},
      el("div", { class: "form-section", text: `编辑${stage === "request" ? "请求" : "响应"}（放行时生效）` }),
      el("div", { class: "hint", text: "headers / body 为文本编辑，空则保持原值" }),
      el("div", { class: "sub-label", text: "Headers" }), headersArea,
      stage === "response" ? el("div", { class: "form-row" }, el("label", { text: "状态码" }), statusInput) : null,
      el("div", { class: "sub-label", text: "Body" }), bodyArea
    );
    openModal({
      title: "断点编辑", body, wide: true,
      footer: el("button", {
        class: "btn primary", text: "继续放行",
        onclick: async () => {
          const payload = { headers: headersArea.value, body: bodyArea.value };
          if (stage === "response") payload.status_code = Number(statusInput.value || 0);
          const res = await call("mitm", "continue_flow", flow.id, stage, payload);
          toast(res.message || (res.ok ? "断点已放行" : "放行失败"), res.ok ? "success" : "error");
        },
      }),
    });
  }

  // ===== 设置弹窗 =====
  btnSettings.addEventListener("click", () => {
    const c = config || {};
    const { helpTip } = window.QTR;

    // 带问号提示的表单标签：点击“?”显示字段说明
    const labelWith = (label, tip) => {
      const node = el("label", { class: "sub", style: "display:inline-flex;align-items:center;gap:4px;flex:none" }, label);
      if (tip) node.append(helpTip(tip));
      return node;
    };
    const textArea = (value, rows, placeholder) => {
      const area = el("textarea", { class: "input mono", rows, placeholder, style: "flex:1;box-sizing:border-box" });
      area.value = value || "";
      return area;
    };
    // 读取 checkbox 组件（外层 label 包裹 input）的勾选状态
    const isChecked = (box) => box.querySelector("input").checked;

    // ---- 基础配置 ----
    const portInput = textInput(String(c.port ?? 9080), { type: "number", style: "width:120px" });
    const webPortInput = textInput(String(c.web_port ?? 9081), { type: "number", style: "width:120px" });
    const recordLimitInput = textInput(String(c.flow_record_limit ?? FLOW_LIMIT_DEFAULT), { type: "number", style: "width:120px" });
    const startupModeSelect = select(
      [{ value: "dump", label: "dump（应用内展示）" }, { value: "web", label: "web（mitmweb 页面）" }],
      c.startup_mode || "dump");
    const webOpenBrowserBox = checkbox("启动后打开浏览器", !!c.web_open_browser);
    const webShowInAppBox = checkbox("Web 模式下同步显示到应用界面", c.web_show_in_app !== false);
    // 代理模式即 mitmproxy 的 mode：local 表示只拦截指定应用进程，其他为 mitmproxy 原生模式
    const proxyModelSelect = select(
      ["local", "regular", "wireguard", "socks5", "dns"].map((m) => ({ value: m, label: m })),
      c.proxy_model || "local");
    const proxyModelValueInput = textInput(String(c.proxy_model_value || ""), {
      placeholder: "输入或选择要拦截的应用进程名，如 CPOS-DF.exe",
      style: "flex:1",
      list: "qtr-mitm-process-options",
    });
    // 进程下拉数据源：datalist 保证仍可手动输入，选项供下拉选择（与旧版可编辑下拉一致）
    const processOptions = el("datalist", { id: "qtr-mitm-process-options" });
    let processListLoaded = false;
    const loadProcessOptions = async () => {
      const res = await call("mitm", "list_processes");
      if (!res.ok) return toast(res.message, "error");
      clear(processOptions);
      for (const name of res.processes || []) {
        processOptions.append(el("option", { value: name }));
      }
      processListLoaded = true;
      toast(`已加载 ${processOptions.children.length} 个进程`, "success", 1500);
    };
    // 首次点击输入框自动加载进程列表，之后可用「加载」按钮手动刷新
    proxyModelValueInput.addEventListener("mousedown", () => {
      if (!processListLoaded) loadProcessOptions();
    });
    const configDirInput = textInput(String(c.mitmproxy_config_dir || ""), {
      placeholder: "留空使用 C:\\Users\\<用户名>\\.mitmproxy",
      style: "flex:1",
    });
    // 证书路径留空时后端按 默认目录 下的 mitmproxy-ca-cert.cer 解析，占位符展示实际生效路径
    const certPathInput = textInput(String(c.cert_path || ""), {
      placeholder: defaultCertPath ? `留空使用默认证书：${defaultCertPath}` : "留空使用默认证书路径",
      style: "flex:1",
    });
    const scriptPathInput = textInput(String(c.script_path || ""), {
      placeholder: "留空使用客户端内置脚本",
      style: "flex:1",
    });
    const sslInsecureBox = checkbox("忽略 SSL 校验（目标服务证书无效时仍抓包）", !!c.ssl_insecure);

    // 启动方式联动：仅 web 模式下可配置浏览器/应用内展示
    const syncStartupMode = () => {
      const isWeb = startupModeSelect.value === "web";
      webOpenBrowserBox.querySelector("input").disabled = !isWeb;
      webShowInAppBox.querySelector("input").disabled = !isWeb;
    };
    startupModeSelect.addEventListener("change", syncStartupMode);
    // 代理模式联动：仅 local 模式需要指定拦截的应用进程
    const proxyValueRow = el("div", { class: "form-row" },
      labelWith("拦截应用", "仅代理模式为 local 时生效：输入或从下拉中选择要拦截的本机应用进程名（不区分大小写），如 CPOS-DF.exe。点击输入框自动加载进程列表，「加载」按钮可手动刷新。"),
      proxyModelValueInput,
      processOptions,
      el("button", { class: "btn small", text: "加载", title: "刷新系统进程列表", onclick: () => loadProcessOptions() }));
    const syncProxyModel = () => { proxyValueRow.style.display = proxyModelSelect.value === "local" ? "" : "none"; };
    proxyModelSelect.addEventListener("change", syncProxyModel);

    // ---- Mock 与请求改写 ----
    const mockEnabledBox = checkbox("启用 Mock", !!c.is_mock);
    const mockServerInput = textInput(String(c.mock_server || ""), {
      placeholder: "Mock 服务地址，如 https://example.com/hrm/mock",
      style: "flex:1",
    });
    const addHeadersArea = textArea(c.add_headers, 3, "每行一个，格式：Content-Type=application/json");
    const addBodyArea = textArea(c.add_body, 3, "Mock 请求附加的 Body 文本，通常为 JSON");

    // ---- 过滤与拦截（开关与配置内容同行展示）----
    const breakpointEnabledBox = checkbox("启用断点拦截", !!c.breakpoint_enabled);
    const breakpointPatternInput = textInput(String(c.breakpoint_pattern || ""), {
      placeholder: "要断点的接口关键字，如 /pos/token",
      style: "flex:1",
    });
    const openIncludeBox = checkbox("启用包含规则", !!c.open_include);
    const includeArea = textArea(c.include, 3, "逗号或换行分隔的路径，命中才参与 Mock，如 /hrm/token,/hrm/user");
    const openExcludeBox = checkbox("启用排除规则", !!c.open_exclude);
    const excludeArea = textArea(c.exclude, 3, "逗号或换行分隔的路径，命中则跳过 Mock，如 /hrm/heartbeat");
    const flowFilterEnabledBox = checkbox("启用流量过滤", !!c.flow_filter_enabled);
    const flowFilterArea = textArea(c.flow_filter_pattern, 3,
      "逗号或换行分隔；以 . 开头按路径后缀匹配（如 .png），否则按路径子串匹配；命中后不记录到列表、不参与 Mock 与延迟");

    // ---- 延迟设置 ----
    const delayBoxes = {};
    const delayRows = el("div", {});
    for (const key of ["request_delay", "response_delay"]) {
      const name = key === "request_delay" ? "请求" : "响应";
      const d = c[key] || { enabled: false, delay: 0, delay_path: [] };
      const enabledBox = checkbox(`启用${name}延迟`, !!d.enabled);
      const delayInput = textInput(String(d.delay ?? 0), { type: "number", step: "0.1", style: "width:100px" });
      const pathText = textArea((d.delay_path || []).join("\n"), 2, `每行一个路径关键字，留空对全部${name}生效`);
      delayBoxes[key] = { enabledBox, delayInput, pathText };
      delayRows.append(
        el("div", { class: "form-row" }, enabledBox, el("label", { text: "延迟(秒)" }), delayInput),
        el("div", { class: "form-row" }, pathText));
    }

    const body = el(
      "div", {},
      el("div", { class: "form-section", text: "基础配置" }),
      el("div", { class: "form-row" }, labelWith("代理端口", "mitmproxy 代理监听端口，客户端需将代理指向 127.0.0.1:该端口，默认 9080。运行中修改会自动重启生效。"), portInput),
      el("div", { class: "form-row" }, labelWith("Web端口", "启动方式为 web 时 mitmweb 页面的监听端口，默认 9081。"), webPortInput),
      el("div", { class: "form-row" }, labelWith("流量记录上限", "列表最多保留的流量条数，超出后从最早的开始丢弃，默认 500。"), recordLimitInput),
      el("div", { class: "form-row" },
        labelWith("启动方式", "dump：流量直接显示在应用界面；web：通过浏览器 mitmweb 页面查看流量。"),
        startupModeSelect, webOpenBrowserBox, webShowInAppBox),
      el("div", { class: "form-row" },
        labelWith("代理模式", "mitmproxy 的抓包模式：local 只拦截指定应用进程；regular 为普通代理；其余为 mitmproxy 原生模式。"),
        proxyModelSelect),
      proxyValueRow,
      el("div", { class: "form-row" }, labelWith("配置目录", "mitmproxy 配置与证书所在目录，留空使用当前用户目录下的 .mitmproxy。"), configDirInput),
      el("div", { class: "form-row" }, labelWith("证书路径", "自定义 mitmproxy CA 证书路径，留空时使用默认目录下的 mitmproxy-ca-cert.cer（见输入框占位提示）。"), certPathInput),
      el("div", { class: "form-row" }, labelWith("脚本路径", "自定义 mitmproxy 附加脚本（.py）路径，留空使用客户端内置脚本。"), scriptPathInput),
      el("div", { class: "form-row" }, sslInsecureBox),
      el("div", { class: "form-section", text: "Mock 与请求改写" }),
      el("div", { class: "form-row" }, mockEnabledBox, mockServerInput),
      el("div", { class: "form-row" }, labelWith("附加请求头", "启用 Mock 后，转发到 Mock 服务的请求会附加这些请求头，每行一条 k=v。"), addHeadersArea),
      el("div", { class: "form-row" }, labelWith("附加 Body", "启用 Mock 后，转发到 Mock 服务的请求会附加此 Body 文本。"), addBodyArea),
      el("div", { class: "form-section", text: "过滤与拦截" }),
      el("div", { class: "form-row" }, breakpointEnabledBox, breakpointPatternInput),
      el("div", { class: "form-row" }, openIncludeBox, includeArea),
      el("div", { class: "form-row" }, openExcludeBox, excludeArea),
      el("div", { class: "form-row" }, flowFilterEnabledBox, flowFilterArea),
      el("div", { class: "form-section", text: "延迟设置" }),
      delayRows
    );

    openModal({
      title: "mitmproxy 设置", body, wide: true,
      footer: el("button", {
        class: "btn primary", text: "保存配置",
        onclick: async () => {
          config.port = Number(portInput.value || 0);
          config.web_port = Number(webPortInput.value || 0);
          config.flow_record_limit = Number(recordLimitInput.value || FLOW_LIMIT_DEFAULT);
          config.startup_mode = startupModeSelect.value;
          config.web_open_browser = isChecked(webOpenBrowserBox);
          config.web_show_in_app = isChecked(webShowInAppBox);
          config.proxy_model = proxyModelSelect.value;
          config.proxy_model_value = proxyModelValueInput.value.trim();
          config.mitmproxy_config_dir = configDirInput.value.trim();
          config.cert_path = certPathInput.value.trim();
          config.script_path = scriptPathInput.value.trim();
          config.ssl_insecure = isChecked(sslInsecureBox);
          config.is_mock = isChecked(mockEnabledBox);
          config.add_headers = addHeadersArea.value;
          config.add_body = addBodyArea.value;
          config.breakpoint_enabled = isChecked(breakpointEnabledBox);
          config.breakpoint_pattern = breakpointPatternInput.value.trim();
          config.open_include = isChecked(openIncludeBox);
          config.include = includeArea.value;
          config.open_exclude = isChecked(openExcludeBox);
          config.exclude = excludeArea.value;
          config.flow_filter_enabled = isChecked(flowFilterEnabledBox);
          config.flow_filter_pattern = flowFilterArea.value;
          for (const key of ["request_delay", "response_delay"]) {
            const d = delayBoxes[key];
            config[key] = {
              enabled: isChecked(d.enabledBox),
              delay: Number(d.delayInput.value || 0),
              delay_path: d.pathText.value.split("\n").map((s) => s.trim()).filter(Boolean),
            };
          }
          const res = await call("mitm", "save_config", config);
          if (res.ok) {
            config = res.config;
            applyState();
            toast("配置已保存" + (res.state === "stopped" ? "" : "（运行中的关键变更将自动重启生效）"), "success");
          } else toast(res.message, "error");
        },
      }),
    });
    syncStartupMode();
    syncProxyModel();
  });

  // ===== 事件订阅 =====
  const on = (event, handler) => { Bus.on(event, handler); return () => Bus.off(event, handler); };
  const unsubs = [
    on("mitm_state", (p) => {
      state = p.state;
      webUrl = p.web_url || "";
      applyState();
    }),
    on("mitm_flow_new", (p) => {
      flows.push(p.item);
      const limit = config?.flow_record_limit || FLOW_LIMIT_DEFAULT;
      if (flows.length > limit) flows.splice(0, flows.length - limit);
      renderFlows();
    }),
    on("mitm_flow_update", (p) => {
      const idx = flows.findIndex((f) => f.id === p.item.id);
      if (idx >= 0) flows[idx] = p.item;
      else flows.push(p.item);
      if (selectedFlow && selectedFlow.id === p.item.id) selectedFlow = p.item;
      renderFlows();
      renderDetail();
    }),
    on("mitm_cert_status", (p) => {
      certLabel.textContent = "证书状态：" + (p.message || (p.trusted ? "已信任" : "未信任"));
      certLabel.classList.toggle("err", p.message && p.message.includes("失败"));
    }),
  ];

  (async function init() {
    const res = await call("mitm", "get_state");
    if (!res.ok) return;
    config = res.config;
    state = res.state;
    webUrl = res.web_url || "";
    defaultCertPath = (res.cert && res.cert.cert_path) || "";
    applyState();
    call("mitm", "refresh_cert_status");
  })();

  const observer = new MutationObserver(() => {
    if (!document.body.contains(mount)) {
      unsubs.forEach((u) => u());
      observer.disconnect();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  return { destroy: () => unsubs.forEach((u) => u()) };
}
