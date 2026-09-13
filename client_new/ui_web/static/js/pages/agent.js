/** Agent 页面：连接控制、服务器管理、连接设置、浏览器设置、请求/响应日志。 */
const { Bus, call, el, $, clear, toast, openModal, textInput, checkbox, select } = window.QTR;

export function agentPage(mount) {
  let config = null;
  let state = "stopped";
  let localMac = "";
  let configSyncing = false;

  // ===== 顶部工具栏 =====
  const stateChip = el("span", { class: "chip", text: "已停止" });
  const statusLabel = el("span", { class: "muted", text: "就绪" });
  const macLabel = el("span", { class: "muted small", text: "MAC: -" });

  const serverInput = textInput("", { list: "agent-server-list", placeholder: "例如: ws://127.0.0.1:9099/qtr/agent/ws", style: "min-width: 280px" });
  const datalist = el("datalist", { id: "agent-server-list" });
  const showLogCheck = checkbox("显示请求/响应日志", false);
  const btnStart = el("button", { class: "btn primary", text: "启动" });
  const btnStop = el("button", { class: "btn", text: "停止", disabled: true });
  const btnServers = el("button", { class: "btn", text: "服务器管理" });
  const btnConn = el("button", { class: "btn", text: "连接设置" });
  const btnBrowser = el("button", { class: "btn", text: "浏览器设置" });
  const btnSync = el("button", { class: "btn", text: "同步配置" });
  const btnClearLogs = el("button", { class: "btn ghost", text: "清空日志" });

  // ===== 日志区 =====
  const requestPre = el("pre", { class: "panel flex-fill", text: "请求日志..." });
  const responsePre = el("pre", { class: "panel flex-fill", text: "响应日志..." });

  mount.append(
    el("div", { class: "toolbar" },
      el("span", { text: "Agent", style: "font-weight:600;font-size:15px" }), stateChip,
      statusLabel, macLabel,
      el("div", { style: "flex:1" }),
      btnStart, btnStop, btnClearLogs
    ),
    el("div", { class: "toolbar" },
      el("label", { text: "服务地址" }), serverInput, datalist,
      showLogCheck,
      el("div", { style: "flex:1" }),
      btnServers, btnConn, btnBrowser, btnSync
    ),
    el("div", { class: "split-v flex-fill" },
      el("div", { class: "col", style: "flex:1" }, el("span", { class: "sub-label", text: "请求" }), requestPre),
      el("div", { class: "col", style: "flex:1" }, el("span", { class: "sub-label", text: "响应" }), responsePre)
    )
  );

  // ===== 交互 =====
  btnStart.addEventListener("click", () => call("agent", "start"));
  btnStop.addEventListener("click", () => call("agent", "stop"));
  btnClearLogs.addEventListener("click", () => {
    requestPre.textContent = "请求日志...";
    responsePre.textContent = "响应日志...";
  });
  btnSync.addEventListener("click", async () => {
    const res = await call("agent", "sync_config");
    if (!res.ok) toast(res.message, "error");
  });
  serverInput.addEventListener("change", saveQuickSettings);
  showLogCheck.addEventListener("change", saveQuickSettings);

  function collectData() {
    return {
      ...config,
      current_server: serverInput.value.trim(),
      show_logs: showLogCheck.checked,
    };
  }

  function saveQuickSettings() {
    if (!config) return;
    call("agent", "save_config", collectData());
  }

  function applyConfig() {
    if (!config) return;
    serverInput.value = config.current_server || "";
    showLogCheck.checked = !!config.show_logs;
    datalist.clear?.();
    clear(datalist);
    for (const name of Object.keys(config.server_list || {})) {
      datalist.append(el("option", { value: config.server_list[name] }));
    }
  }

  function applyState() {
    const running = ["starting", "running", "stopping"].includes(state);
    btnStart.disabled = running;
    btnStop.disabled = !running;
    stateChip.className = "chip " + (state === "running" ? "ok" : running ? "warn" : "");
    const labelMap = { stopped: "已停止", starting: "连接中", running: "运行中", stopping: "停止中" };
    stateChip.textContent = labelMap[state] || state;
  }

  // ===== 弹窗：服务器管理（新增/修改/删除，沿用原版三按钮交互） =====
  btnServers.addEventListener("click", () => {
    const tbody = el("tbody", {});
    const syncUrlInput = textInput(config.config_sync_url || "", { placeholder: "配置拉取地址", style: "flex:1" });
    let selectedName = "";

    function renderRows() {
      selectedName = "";
      clear(tbody);
      for (const [name, url] of Object.entries(config.server_list || {})) {
        const tr = el("tr", { onclick: () => {
          selectedName = name;
          for (const row of tbody.children) row.classList.toggle("selected", row === tr);
        } },
          el("td", { text: name }),
          el("td", { text: url }),
          el("td", { class: "muted small", text: name === config.current_server ? "当前使用" : "" })
        );
        tbody.append(tr);
      }
    }

    /** 新增/修改共用的小弹窗；editName 为空表示新增。 */
    function openServerEditor(editName = "") {
      const nameInput = textInput(editName, { placeholder: "名称" });
      const urlInput = textInput(editName ? config.server_list[editName] || "" : "", { placeholder: "地址 ws://...", style: "width:100%" });
      let editorModal;
      editorModal = openModal({
        title: editName ? `修改服务器：${editName}` : "新增服务器",
        body: el("div", { class: "form-grid" },
          el("label", { class: "sub", text: "名称" }), nameInput,
          el("label", { class: "sub", text: "地址" }), urlInput),
        footer: el("button", {
          class: "btn primary", text: "保存",
          onclick: async () => {
            const res = await call("agent", "save_server", nameInput.value.trim(), urlInput.value.trim(), editName);
            if (!res.ok) return toast(res.message, "error");
            await reloadConfig();
            renderRows();
            editorModal.close();
            toast("已保存", "success", 1200);
          },
        }),
      });
    }

    const body = el(
      "div", {},
      el("div", { class: "toolbar", style: "margin:0" },
        el("button", { class: "btn small primary", text: "新增", onclick: () => openServerEditor() }),
        el("button", {
          class: "btn small", text: "修改",
          onclick: () => {
            if (!selectedName) return toast("请先在列表中选择要修改的服务器", "error");
            openServerEditor(selectedName);
          },
        }),
        el("button", {
          class: "btn small danger", text: "删除",
          onclick: async () => {
            if (!selectedName) return toast("请先在列表中选择要删除的服务器", "error");
            const res = await call("agent", "delete_server", selectedName);
            if (!res.ok) return toast(res.message, "error");
            await reloadConfig();
            renderRows();
          },
        })),
      el("div", { class: "table-wrap", style: "max-height:40vh; margin-top:8px" },
        el("table", { class: "data" },
          el("thead", {}, el("tr", {}, el("th", { text: "名称" }), el("th", { text: "地址" }), el("th", { text: "" }))),
          tbody)),
      el("div", { class: "form-row", style: "margin-top:10px" },
        el("label", { text: "配置拉取" }), syncUrlInput,
        el("button", {
          class: "btn small", text: "保存拉取地址",
          onclick: async () => {
            await call("agent", "save_config", { ...config, config_sync_url: syncUrlInput.value.trim() });
            await reloadConfig();
            toast("已保存", "success", 1200);
          },
        }))
    );
    openModal({ title: "Agent 服务器管理", body });
    renderRows();
  });

  // ===== 弹窗：连接设置 =====
  btnConn.addEventListener("click", () => {
    const inputs = {
      retry_times: textInput(String(config.retry_times ?? 0), { type: "number" }),
      retry_interval: textInput(String(config.retry_interval ?? 5), { type: "number" }),
      retry_forever_interval: textInput(String(config.retry_forever_interval ?? 300), { type: "number" }),
      max_send_size: textInput(String(config.max_send_size ?? 0), { type: "number" }),
    };
    const body = el(
      "div", { class: "form-grid" },
      el("label", { class: "sub", text: "连接失败后自动重试" }), checkbox("", config.retry, (e) => (config.retry = e.target.checked)),
      el("label", { class: "sub", text: "重试次数" }), inputs.retry_times,
      el("label", { class: "sub", text: "重试间隔(秒)" }), inputs.retry_interval,
      el("label", { class: "sub", text: "高频重试用尽后低频永续重连" }), checkbox("", config.retry_forever, (e) => (config.retry_forever = e.target.checked)),
      el("label", { class: "sub", text: "永续重连间隔(秒)" }), inputs.retry_forever_interval,
      el("label", { class: "sub", text: "单条消息上限(字节)" }), inputs.max_send_size
    );
    openModal({
      title: "连接设置",
      body,
      footer: el("button", {
        class: "btn primary", text: "保存",
        onclick: async () => {
          const data = {
            ...config,
            retry_times: Number(inputs.retry_times.value || 0),
            retry_interval: Number(inputs.retry_interval.value || 5),
            retry_forever_interval: Number(inputs.retry_forever_interval.value || 300),
            max_send_size: Number(inputs.max_send_size.value || 0),
          };
          const res = await call("agent", "save_config", data);
          if (res.ok) {
            config = res.config;
            toast("已保存", "success", 1200);
          } else toast(res.message, "error");
        },
      }),
    });
  });

  // ===== 弹窗：浏览器设置 =====
  btnBrowser.addEventListener("click", () => {
    const b = config.browser || {};
    const bindInput = (key) => (e) => { config.browser[key] = e.target.value.trim(); };
    const inputs = {
      install_dir: textInput(b.install_dir || "", { style: "flex:1", onchange: bindInput("install_dir") }),
      host: textInput(b.playwright_download_host || "", { style: "flex:1", placeholder: "例如: https://npmmirror.com/mirrors/playwright", onchange: bindInput("playwright_download_host") }),
      proxy: textInput(b.playwright_download_proxy || "", { style: "flex:1", placeholder: "例如: http://127.0.0.1:7890", onchange: bindInput("playwright_download_proxy") }),
      chromium: textInput(b.chromium_executable_path || "", { style: "flex:1", placeholder: "留空则使用 Playwright 的 chromium", onchange: bindInput("chromium_executable_path") }),
      firefox: textInput(b.firefox_executable_path || "", { style: "flex:1", placeholder: "留空则使用 Playwright 的 firefox", onchange: bindInput("firefox_executable_path") }),
      webkit: textInput(b.webkit_executable_path || "", { style: "flex:1", placeholder: "留空则使用 Playwright 的 webkit", onchange: bindInput("webkit_executable_path") }),
    };
    const body = el(
      "div", {},
      el("div", { class: "form-row" }, checkbox("浏览器缺失时自动安装", b.auto_install, (e) => (config.browser.auto_install = e.target.checked))),
      el("div", { class: "form-row" }, el("label", { text: "安装目录" }), inputs.install_dir,
        el("button", {
          class: "btn small", text: "浏览",
          onclick: async () => {
            const res = await call("choose_dir", "选择浏览器安装目录");
            if (res.ok) inputs.install_dir.value = res.path;
          },
        })),
      el("div", { class: "form-row" }, el("label", { text: "下载源" }), inputs.host),
      el("div", { class: "form-row" }, el("label", { text: "下载代理" }), inputs.proxy),
      el("div", { class: "form-row" }, el("label", { text: "chromium 路径" }), inputs.chromium),
      el("div", { class: "form-row" }, el("label", { text: "firefox 路径" }), inputs.firefox),
      el("div", { class: "form-row" }, el("label", { text: "webkit 路径" }), inputs.webkit),
      el("div", { class: "form-row" },
        el("label", { text: "手动下载" }),
        el("button", { class: "btn small", text: "chromium", onclick: () => downloadBrowser("chromium") }),
        el("button", { class: "btn small", text: "firefox", onclick: () => downloadBrowser("firefox") }),
        el("button", { class: "btn small", text: "webkit", onclick: () => downloadBrowser("webkit") }),
        el("span", { class: "hint", text: "按当前配置下载对应浏览器内核" }))
    );
    openModal({ title: "浏览器设置", body });
  });

  async function downloadBrowser(name) {
    // 下载前先把浏览器配置（含本次修改）保存到后端，与原实现一致
    await call("agent", "save_config", collectData());
    const res = await call("agent", "manual_download_browser", name, config.browser);
    if (!res.ok) toast(res.message, "error");
  }

  // ===== 事件订阅 =====
  const unsubs = [
    on("agent_state", (p) => { state = p.state; applyState(); }),
    on("agent_status", (p) => (statusLabel.textContent = p.message || "")),
    on("agent_error", (p) => toast(p.message || "", "error")),
    on("agent_mac", (p) => (macLabel.textContent = "MAC: " + (p.mac || "-"))),
    on("agent_request", (p) => appendLog(requestPre, p.text)),
    on("agent_response", (p) => appendLog(responsePre, p.text)),
    on("agent_install_log", (p) => appendLog(responsePre, p.text)),
    on("agent_config_syncing", (p) => {
      configSyncing = p.syncing;
      btnSync.disabled = configSyncing;
      btnSync.textContent = configSyncing ? "同步中..." : "同步配置";
    }),
    on("agent_config_sync_result", (p) => {
      toast(p.message || "", p.ok ? "success" : "error");
      reloadConfig();
    }),
    on("agent_manual_downloading", (p) => toast(p.message || "", p.ok === false ? "error" : "info")),
  ];

  function on(event, handler) {
    Bus.on(event, handler);
    return () => Bus.off(event, handler);
  }

  function appendLog(pre, text) {
    if (!text) return;
    if (pre.textContent.startsWith("请求日志") || pre.textContent.startsWith("响应日志")) pre.textContent = "";
    pre.textContent += text + "\n";
    pre.scrollTop = pre.scrollHeight;
  }

  async function reloadConfig() {
    const res = await call("agent", "get_state");
    if (res.ok) {
      config = res.config;
      localMac = res.local_mac;
      macLabel.textContent = "MAC: " + (localMac || "-");
      applyConfig();
      applyState();
    }
  }

  // ===== 初始化 =====
  (async function init() {
    const res = await call("agent", "get_state");
    if (!res.ok) return;
    config = res.config;
    localMac = res.local_mac;
    state = res.state;
    macLabel.textContent = "MAC: " + (localMac || "-");
    applyConfig();
    applyState();
  })();

  // 页面销毁时取消订阅
  mount.dataset.bound = "agent";
  const observer = new MutationObserver(() => {
    if (!document.body.contains(mount)) {
      unsubs.forEach((u) => u());
      observer.disconnect();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  return { destroy: () => unsubs.forEach((u) => u()) };
}
