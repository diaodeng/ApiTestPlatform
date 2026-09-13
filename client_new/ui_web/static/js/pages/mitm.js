/** mitmproxy 页面：启停控制、流量表、详情、断点放行、证书、设置。 */
const { Bus, call, el, $, clear, toast, openModal, textInput, checkbox, select, copyText, kvTable } = window.QTR;

export function mitmPage(mount) {
  let config = null;
  let state = "stopped";
  let webUrl = "";
  let flows = []; // FlowItem 字典数组
  let selectedFlow = null;
  let showDetail = true;
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
    const F = (key, label, attrs = {}, transform = (v) => v) => {
      const input = textInput(String(c[key] ?? ""), attrs);
      input.dataset.key = key;
      input.dataset.transform = transform.name;
      return [label, input, transform];
    };
    const fields = [
      F("port", "代理端口", { type: "number" }, Number),
      F("web_port", "Web端口", { type: "number" }, Number),
      F("cert_path", "证书路径", {}),
      F("script_path", "脚本路径", {}),
      F("mitmproxy_config_dir", "配置目录", {}),
      F("proxy_client", "代理客户端", { placeholder: "进程名" }),
      F("proxy_model_value", "代理模式值", {}),
      F("mock_server", "Mock 服务地址", {}),
      F("flow_record_limit", "流量记录上限", { type: "number" }, Number),
      F("flow_filter_pattern", "流量过滤关键字", {}),
      F("add_headers", "附加请求头(文本)"),
      F("exclude", "排除规则"),
      F("include", "包含规则"),
    ];
    const grid = el("div", { class: "form-grid" });
    for (const [label, input] of fields) {
      grid.append(el("label", { class: "sub", text: label }), input);
    }
    const checks = {
      startup_mode: select([{ value: "dump", label: "dump" }, { value: "web", label: "web" }], c.startup_mode || "dump"),
      web_open_browser: checkbox("启动后打开浏览器", !!c.web_open_browser),
      web_show_in_app: checkbox("Web 模式下同步显示到应用界面", !!c.web_show_in_app),
      ssl_insecure: checkbox("忽略 SSL 校验", !!c.ssl_insecure),
      is_mock: checkbox("启用 mock", !!c.is_mock),
      open_include: checkbox("启用包含规则", !!c.open_include),
      open_exclude: checkbox("启用排除规则", !!c.open_exclude),
      breakpoint_enabled: checkbox("启用断点拦截", !!c.breakpoint_enabled),
      flow_filter_enabled: checkbox("启用流量过滤", !!c.flow_filter_enabled),
    };
    const bpPattern = textInput(c.breakpoint_pattern || "", { placeholder: "输入要断点的接口关键字，如 /pos/token", style: "flex:1" });
    const delayBoxes = {};
    const delayRows = el("div", {});
    for (const key of ["request_delay", "response_delay"]) {
      const d = c[key] || { enabled: false, delay: 0, delay_path: [] };
      const enabledBox = checkbox(key === "request_delay" ? "启用请求延迟" : "启用响应延迟", d.enabled);
      const delayInput = textInput(String(d.delay ?? 0), { type: "number", style: "width:100px" });
      const pathText = el("textarea", { class: "input mono", rows: 2, style: "width:100%", placeholder: "每行一个路径关键字" });
      pathText.value = (d.delay_path || []).join("\n");
      delayBoxes[key] = { enabledBox, delayInput, pathText };
      delayRows.append(
        el("div", { class: "form-row" }, enabledBox, el("label", { text: "延迟(秒)" }), delayInput),
        el("div", { class: "form-row" }, pathText));
    }

    const body = el(
      "div", {},
      grid,
      el("div", { class: "form-section", text: "开关与模式" }),
      el("div", { class: "form-row" }, el("label", { text: "启动方式" }), checks.startup_mode, checks.web_open_browser, checks.web_show_in_app),
      el("div", { class: "form-row" }, checks.ssl_insecure, checks.is_mock, checks.flow_filter_enabled),
      el("div", { class: "form-row" }, checks.open_include, checks.open_exclude, checks.breakpoint_enabled),
      el("div", { class: "form-row" }, el("label", { text: "断点关键字" }), bpPattern),
      el("div", { class: "form-section", text: "延迟设置" }),
      delayRows
    );
    openModal({
      title: "mitmproxy 设置", body, wide: true,
      footer: el("button", {
        class: "btn primary", text: "保存配置",
        onclick: async () => {
          for (const [, input, transform] of fields) {
            const key = input.dataset.key;
            config[key] = transform(input.value.trim() || input.value);
          }
          config.startup_mode = checks.startup_mode.value;
          config.web_open_browser = checks.web_open_browser.querySelector("input").checked;
          config.web_show_in_app = checks.web_show_in_app.querySelector("input").checked;
          config.ssl_insecure = checks.ssl_insecure.querySelector("input").checked;
          config.is_mock = checks.is_mock.querySelector("input").checked;
          config.open_include = checks.open_include.querySelector("input").checked;
          config.open_exclude = checks.open_exclude.querySelector("input").checked;
          config.breakpoint_enabled = checks.breakpoint_enabled.querySelector("input").checked;
          config.breakpoint_pattern = bpPattern.value.trim();
          config.flow_filter_enabled = checks.flow_filter_enabled.querySelector("input").checked;
          for (const key of ["request_delay", "response_delay"]) {
            const d = delayBoxes[key];
            config[key] = {
              enabled: d.enabledBox.querySelector("input").checked,
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
