/** POS 页面：扫描、启停、维护操作、设置/切换/进程/账号/本地环境弹窗。 */
const { Bus, call, el, $, clear, toast, openModal, textInput, checkbox, select, listEditor, copyText, icon } = window.QTR;

export function posPage(mount) {
  let boot = null; // get_bootstrap 结果
  let posConfig = null;
  // 每个 POS 路径的环境信息状态：path -> {loading, text}，供左侧列动态展示
  const envState = new Map();
  // 当前渲染的行内环境信息节点：path -> DOM 节点（重渲染时重建）
  const envNodes = new Map();

  // ===== 工具栏：扫描区（工作目录/模式配置收纳进「工作目录」弹窗） =====
  const btnWorkDir = el("button", { class: "btn", text: "工作目录" });
  const btnScan = el("button", { class: "btn primary", text: "扫描" });
  const btnStopPos = el("button", { class: "btn danger", text: "停止POS" });
  const btnStopOffline = el("button", { class: "btn", text: "停止离线" });
  const btnSyncCfg = el("button", { class: "btn", text: "同步配置" });
  const btnSetting = el("button", { class: "btn", text: "设置" });
  const btnChangePos = el("button", { class: "btn", text: "切换POS" });
  const btnProcess = el("button", { class: "btn", text: "进程管理" });
  const btnAccount = el("button", { class: "btn", text: "POS账号处理" });

  // ===== 启动配置勾选（与原版一致的替换证书/清缓存/覆盖驱动等） =====
  const START_FIELDS = [
    ["backup", "备份支付配置"],
    ["replace_mitm_cert", "替换证书"],
    ["change_env", "切换本地环境"],
    ["change_pos", "切换云端POS"],
    ["remove_cache", "清缓存"],
    ["cover_payment_driver", "覆盖驱动"],
    ["account_logout", "退出登录"],
  ];
  const startChecks = {};
  for (const [key, label] of START_FIELDS) startChecks[key] = checkbox(label, false, saveStartConfig);

  // ===== 列表 =====
  const filterInput = textInput("", { placeholder: "过滤关键字", style: "width:200px" });
  const resultTbody = el("tbody", {});
  const resultTable = el(
    "table", { class: "data pos-table" },
    el("thead", {}, el("tr", {},
      el("th", { text: "POS 路径" }), el("th", { text: "操作" }))));

  const statusLabel = el("span", { class: "muted selectable", text: "就绪" });
  const logPre = el("pre", { class: "panel", style: "height:120px;flex:none" });
  // 状态区收起/展开：收起时隐藏状态文本与日志面板，按钮本身保持可见
  const btnToggleStatus = el("button", { class: "btn small", text: "收起" });
  let statusExpanded = true;
  btnToggleStatus.addEventListener("click", () => {
    statusExpanded = !statusExpanded;
    statusLabel.style.display = statusExpanded ? "" : "none";
    logPre.style.display = statusExpanded ? "" : "none";
    btnToggleStatus.textContent = statusExpanded ? "收起" : "展开";
  });

  mount.append(
    el("div", { class: "toolbar" },
      btnWorkDir, btnScan,
      el("div", { style: "flex:1" }),
      btnStopPos, btnStopOffline, btnChangePos, btnProcess, btnAccount, btnSyncCfg, btnSetting
    ),
    el("div", { class: "toolbar" },
      el("label", { text: "启动前:" }),
      Object.values(startChecks),
      el("label", { text: "过滤:" }),
      filterInput
    ),
    el("div", { class: "table-wrap flex-fill" },
      resultTable),
    // 底部状态区：收起/展开按钮 + 运行状态 + 日志面板
    el("div", { class: "toolbar", style: "margin-bottom:0" }, btnToggleStatus, statusLabel),
    logPre
  );

  resultTable.append(resultTbody);

  // ===== 渲染 =====
  function renderRows() {
    clear(resultTbody);
    const keyword = filterInput.value.trim().toLowerCase();
    const history = (boot?.history || []).filter((p) => !keyword || p.toLowerCase().includes(keyword));
    for (const path of history) resultTbody.append(buildRow(path));
  }

  function buildRow(path) {
    // 左侧列两行：第一行完整路径，第二行环境信息（查看环境/本地环境切换后动态更新，行为对齐旧版 PySide）
    const envLine = el("div", { class: "pos-env-line" });
    envNodes.set(path, envLine);
    renderEnvLine(envLine, path);
    // 双击路径单元格复制完整路径（对齐旧版双击复制交互）
    const pathCell = el("td", { ondblclick: () => copyText(path) },
      el("div", { class: "mono small", text: path }),
      envLine);
    const actions = el("div", { style: "display:flex;gap:5px" });
    // 图标按钮：语义通过 title 提示，避免操作列占用过宽
    const mk = (name, title, cls, fn) =>
      el("button", { class: `btn small icon-btn ${cls || ""}`, title, onclick: () => fn(path) }, icon(name));
    actions.append(
      mk("play", "启动", "primary", startPos),
      mk("folder", "打开目录", "", (p) => call("pos", "open_location", p)),
      mk("refresh", "在线切换", "", switchOnline),
      mk("info", "查看环境", "", viewEnv),
      mk("home", "本地环境", "", openLocalEnv),
      mk("more", "更多操作", "", (p) => openMoreMenu(p, actions))
    );
    return el("tr", {}, pathCell, el("td", {}, actions));
  }

  // ===== 左侧列环境信息 =====
  // 按状态渲染环境信息行：未获取 / 获取中（高亮）/ 结果摘要
  function renderEnvLine(node, path) {
    const st = envState.get(path);
    node.classList.toggle("loading", !!(st && st.loading));
    node.textContent = !st ? "环境: 未获取"
      : st.loading ? "环境: 获取中..."
      : (st.text || "环境: 获取失败");
  }

  // 刷新指定路径当前渲染行的环境信息
  function refreshEnvLine(path) {
    const node = envNodes.get(path);
    if (node) renderEnvLine(node, path);
  }

  // 由 get_env 返回的 payload 拼一行环境摘要（格式对齐旧版 _format_env_message，含商家/门店）
  function formatEnvSummary(d) {
    if (!d) return "";
    const source = d.is_local ? "本地" : "远端";
    const envShow = d.remote_env || d.local_env || "-";
    return `${source} 商家:${d.vender_no || "-"} | 门店ID(sap/org): ${d.sap_org_no || "-"}/${d.org_no || "-"} | 环境:${envShow} 版本:${d.version || "-"} POS:${d.pos_id || "-"}`;
  }

  // 获取环境信息并更新左侧列（查看环境点击、本地环境切换成功后共用）
  async function fetchEnvToLine(path) {
    envState.set(path, { loading: true, text: "" });
    refreshEnvLine(path);
    const res = await call("pos", "get_env", path);
    envState.set(path, res.ok
      ? { loading: false, text: formatEnvSummary(res.data) }
      : { loading: false, text: "" });
    refreshEnvLine(path);
    return res;
  }

  async function startPos(path) {
    statusLabel.textContent = "启动中: " + path;
    const res = await call("pos", "start_pos", path);
    if (!res.ok && res.message) toast(res.message, res.message.includes("取消") ? "info" : "error");
  }

  async function switchOnline(path) {
    const res = await call("pos", "switch_pos_online", path);
    toast(res.message || (res.ok ? "在线切换成功" : "在线切换失败"), res.ok ? "success" : "error");
  }

  async function viewEnv(path) {
    // 环境信息直接更新到左侧列（信息行已展示完整摘要，不再弹窗）；日志区同步留档
    const res = await fetchEnvToLine(path);
    if (!res.ok) return toast(res.message, "error");
    appendLog(res.message);
  }

  // 更多操作菜单
  function openMoreMenu(path, anchor) {
    const items = [
      ["清缓存", "clean_cache"],
      ["备份驱动", "backup_payment_driver"],
      ["恢复驱动", "restore_payment_driver"],
      ["覆盖驱动", "cover_payment_driver"],
      ["清理环境文件", "clear_env"],
      ["替换证书", "replace_mitm_cert"],
      ["退出账号", "logout_pos"],
    ];
    const menu = el(
      "div", { style: "display:flex;flex-direction:column;gap:6px" },
      items.map(([label, method]) =>
        el("button", {
          class: "btn", text: label,
          onclick: async () => {
            overlay.remove();
            const res = await call("pos", method, path);
            if (res.message) toast(res.message, res.ok ? "success" : "error");
          },
        })),
      // 复制路径：纯前端行为，不走后端接口（对齐旧版更多菜单）
      el("hr", { style: "border:none;border-top:1px solid var(--border);width:100%;margin:2px 0" }),
      el("button", {
        class: "btn", text: "复制路径",
        onclick: () => { overlay.remove(); copyText(path); },
      })
    );
    const overlay = el("div", { class: "modal-overlay" }, el("div", { class: "modal", style: "width:260px" },
      el("div", { class: "modal-head" }, el("span", { text: "更多操作" }),
        el("button", { class: "btn small", text: "关闭", onclick: () => overlay.remove() })),
      el("div", { class: "modal-body" }, menu)));
    overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) overlay.remove(); });
    document.getElementById("modal-root").append(overlay);
  }

  // ===== 弹窗：工作目录（目录管理与扫描模式配置） =====
  btnWorkDir.addEventListener("click", () => {
    const sc = boot?.search_config || {};
    const editor = listEditor(sc.dir || [], "目录路径");
    const filePatternInput = textInput(sc.file_pattern || "", { style: "flex:1" });
    const dirPatternInput = textInput(sc.dir_pattern || "*", { style: "flex:1" });
    const depthInput = textInput(sc.max_depth || "1", { type: "number", min: 1, style: "width:80px" });
    const body = el(
      "div", {},
      el("div", { class: "form-section", text: "工作目录" }),
      editor.node,
      el("div", { class: "form-row" },
        el("button", {
          class: "btn small", text: "添加目录",
          onclick: async () => {
            const res = await call("choose_dir", "选择工作目录");
            if (res.ok) editor.add(res.path);
          },
        })),
      el("div", { class: "form-section", text: "扫描模式" }),
      el("div", { class: "form-row" }, el("label", { text: "文件名模式" }), filePatternInput),
      el("div", { class: "form-row" }, el("label", { text: "目录名模式" }), dirPatternInput),
      el("div", { class: "form-row" }, el("label", { text: "递归深度" }), depthInput)
    );
    openModal({
      title: "工作目录",
      body,
      footer: el("button", {
        class: "btn primary", text: "保存",
        onclick: async () => {
          await call("pos", "save_search_config", {
            ...sc,
            dir: editor.getValue(),
            file_pattern: filePatternInput.value.trim(),
            dir_pattern: dirPatternInput.value.trim() || "*",
            max_depth: depthInput.value || "1",
          });
          await reload();
          toast("已保存", "success", 1200);
        },
      }),
    });
  });

  // ===== 弹窗：POS 设置 =====
  btnSetting.addEventListener("click", () => {
    const c = posConfig || {};
    const hostFields = [
      ["pos_tool_test_host", "POS工具Test"],
      ["pos_tool_uat_host", "POS工具UAT"],
      ["pos_test_host", "POS Test"],
      ["pos_uat_host", "POS UAT"],
      ["pos_pro_host", "POS 生产"],
    ];
    // 目录类配置：mock 驱动源目录 + 支付驱动备份目录（对齐旧版 Flet 设置项）
    const dirFields = [
      ["payment_mock_driver_path", "支付MOCK驱动目录", "覆盖驱动/备份驱动时取 mock 驱动的源目录，留空用应用根目录 drive"],
      ["payment_driver_back_up_path", "支付驱动备份目录", "备份支付驱动的存放目录，留空用 POS 目录下 drive_backup"],
    ];
    const envFiles = listEditor(c.env_files || []);
    const cacheFiles = listEditor(c.cache_files || []);
    const envGroupText = el("textarea", { class: "input", rows: 6, style: "width:100%;font-family:var(--mono-font)" });
    envGroupText.value = JSON.stringify(c.env_group_vendor || {}, null, 2);
    const vendorText = el("textarea", { class: "input", rows: 6, style: "width:100%;font-family:var(--mono-font)" });
    vendorText.value = JSON.stringify(c.vendor_config || [], null, 2);
    const syncUrl = textInput(c.config_sync_url || "", { style: "flex:1" });

    const body = el(
      "div", {},
      el("div", { class: "form-section", text: "服务地址" }),
      hostFields.map(([key, label]) =>
        el("div", { class: "form-row" },
          el("label", { text: label }),
          textInput(c[key] || "", { style: "flex:1", onchange: (e) => (c[key] = e.target.value.trim()) }))
      ),
      el("div", { class: "form-section", text: "驱动目录" }),
      dirFields.map(([key, label, tip]) =>
        el("div", { class: "form-row" },
          el("label", { text: label, title: tip }),
          textInput(c[key] || "", { style: "flex:1", placeholder: tip, onchange: (e) => (c[key] = e.target.value.trim()) }))
      ),
      el("div", { class: "form-section", text: "环境文件清单（启动前按此备份/切换）" }),
      el("div", { style: "display:flex;flex-direction:column;gap:4px" }, envFiles.node),
      el("div", { class: "form-row" },
        el("button", { class: "btn small", text: "添加环境文件", onclick: () => envFiles.add() })),
      el("div", { class: "form-section", text: "缓存文件清单（清理缓存按此处理）" }),
      el("div", { style: "display:flex;flex-direction:column;gap:4px" }, cacheFiles.node),
      el("div", { class: "form-row" },
        el("button", { class: "btn small", text: "添加缓存文件", onclick: () => cacheFiles.add() })),
      el("div", { class: "form-section", text: "环境分组（env_group_vendor：环境key -> 账号列表，JSON）" }),
      envGroupText,
      el("div", { class: "form-section", text: "商家配置（vendor_config：商家/账号/分辨率，JSON）" }),
      vendorText,
      el("div", { class: "form-section", text: "配置拉取" }),
      el("div", { class: "form-row" }, el("label", { text: "拉取地址" }), syncUrl)
    );

    openModal({
      title: "POS 设置", body, wide: true,
      footer: el("button", {
        class: "btn primary", text: "保存配置",
        onclick: async () => {
          try {
            c.env_group_vendor = JSON.parse(envGroupText.value || "{}");
            c.vendor_config = JSON.parse(vendorText.value || "[]");
          } catch (e) {
            return toast("JSON 格式错误: " + e.message, "error");
          }
          c.env_files = envFiles.getValue();
          c.cache_files = cacheFiles.getValue();
          c.config_sync_url = syncUrl.value.trim();
          const res = await call("pos", "save_pos_config", c);
          if (res.ok) {
            posConfig = res.pos_config;
            toast("配置已保存", "success");
          } else toast(res.message, "error");
        },
      }),
    });
  });

  // ===== 弹窗：切换 POS =====
  btnChangePos.addEventListener("click", async () => {
    const res = await call("pos", "get_change_pos_bootstrap", "");
    if (!res.ok) return toast(res.message, "error");
    const { env_list, store_list, state } = res;
    const s = { ...state };

    const envSel = select((env_list || []).map((e) => ({ value: e.env_code, label: e.env_name })), s.env);
    const vendorSel = select([], s.vendor_id);
    const storeSel = select([], s.store_id);
    const modeSel = select([{ value: "1", label: "指定MAC" }, { value: "2", label: "指定POS_ID" }], s.switch_mode || "1");
    const macInput = textInput(res.pos_mac || "", { style: "flex:1" });
    const posNoInput = textInput(s.pos_no || "", { style: "width:100%" });
    const posNoLabel = el("label", { class: "sub", text: "POS_ID" });
    const ipInput = textInput(res.pos_ip || "");
    const typeSel = select([{ value: "1", label: "人工收银" }, { value: "2", label: "SCO" }, { value: "4", label: "Combined" }], s.pos_type || "1");
    const groupInput = textInput(s.pos_group || "", { placeholder: "POS机台组(可选)" });

    function refreshVendors() {
      s.env = envSel.value;
      clear(vendorSel); clear(storeSel);
      const vendors = {};
      for (const item of store_list || []) if (item.env === envSel.value) vendors[item.vender_id] = item.vender_name;
      for (const [k, v] of Object.entries(vendors)) vendorSel.append(el("option", { value: k, text: v }));
      if (s.vendor_id && vendorSel.querySelector(`option[value="${s.vendor_id}"]`)) vendorSel.value = s.vendor_id;
      refreshStores();
    }
    function refreshStores() {
      s.vendor_id = vendorSel.value;
      clear(storeSel);
      for (const item of store_list || []) {
        if (item.env === envSel.value && item.vender_id === vendorSel.value) {
          storeSel.append(el("option", { value: item.store_id, text: item.store_name }));
        }
      }
      if (s.store_id && storeSel.querySelector(`option[value="${s.store_id}"]`)) storeSel.value = s.store_id;
      s.store_id = storeSel.value;
    }
    envSel.addEventListener("change", refreshVendors);
    vendorSel.addEventListener("change", refreshStores);
    const persist = () => {
      s.switch_mode = modeSel.value;
      s.pos_mac = macInput.value.trim();
      s.pos_no = posNoInput.value.trim();
      s.pos_ip = ipInput.value.trim();
      s.pos_type = typeSel.value;
      s.pos_group = groupInput.value.trim();
      call("pos", "save_change_pos_state", s);
    };
    modeSel.addEventListener("change", () => {
      applyModeVisibility();
      persist();
    });
    [macInput, posNoInput, ipInput, groupInput].forEach((i) => i.addEventListener("change", persist));

    const body = el(
      "div", { class: "form-grid" },
      el("label", { class: "sub", text: "环境/商家/门店" }),
      el("div", { style: "display:flex;flex-direction:column;gap:6px" }, envSel, vendorSel, storeSel),
      el("label", { class: "sub", text: "模式" }), modeSel,
      posNoLabel, posNoInput,
      el("label", { class: "sub", text: "MAC" }), macInput,
      el("label", { class: "sub", text: "IP" }), ipInput,
      el("label", { class: "sub", text: "POS类型" }), typeSel,
      el("label", { class: "sub", text: "POS机台组" }), groupInput
    );
    const applyModeVisibility = () => {
      const show = modeSel.value === "2";
      posNoLabel.style.display = show ? "" : "none";
      posNoInput.style.display = show ? "" : "none";
    };
    applyModeVisibility();

    let modal;
    modal = openModal({
      title: "在线切换POS", body,
      footer: [
        el("button", { class: "btn", text: "取消", onclick: () => modal.close() }),
        el("button", {
          class: "btn primary", text: "确定切换",
          onclick: async () => {
            persist();
            const data = {
              env: s.env || "", venderId: s.vendor_id || "", orgNo: s.store_id || "",
              switchMode: s.switch_mode || "1", pos_mac: s.pos_mac || "", pos_no: s.pos_no || "",
              pos_ip: s.pos_ip || "", pos_type: s.pos_type || "1", pos_group: s.pos_group || "",
            };
            if (!data.env || !data.venderId || !data.orgNo) return toast("请先选择环境/商家/门店", "error");
            const r = await call("pos", "change_pos", data);
            toast(r.message || (r.ok ? "POS切换成功" : "切换失败"), r.ok ? "success" : "error");
            if (r.ok) modal.close();
          },
        }),
      ],
    });
    refreshVendors();
  });

  // ===== 弹窗：本地环境 =====
  async function openLocalEnv(path) {
    const res = await call("pos", "get_local_env", path);
    if (!res.ok) return toast(res.message, "error");
    const envSel = select(
      Object.entries(res.backed_envs).map(([k, v]) => ({ value: k, label: v })), "");
    const body = el(
      "div", { class: "form-grid" },
      el("label", { class: "sub", text: "当前环境" }), el("pre", { class: "panel", text: res.current_info }),
      el("label", { class: "sub", text: "已备份环境" }), envSel
    );
    let modal;
    modal = openModal({
      title: "切换本地环境", body,
      footer: el("button", {
        class: "btn primary", text: "确定切换",
        onclick: async () => {
          if (!envSel.value) return toast("请先选择目标环境", "error");
          const r = await call("pos", "change_local_env", path, envSel.value);
          toast(r.message || (r.ok ? "切换成功" : "切换失败"), r.ok ? "success" : "error");
          if (r.ok) {
            modal.close();
            // 切换成功后重新获取环境信息，动态更新左侧列
            fetchEnvToLine(path);
          }
        },
      }),
    });
  }

  // ===== 弹窗：进程管理 =====
  btnProcess.addEventListener("click", async () => {
    const res = await call("pos", "list_processes", "");
    if (!res.ok) return toast(res.message, "error");
    const tbody = el("tbody", {});
    const filterBox = textInput("", { placeholder: "输入进程名过滤", style: "flex:1" });
    const table = el("table", { class: "data" },
      el("thead", {}, el("tr", {}, el("th", { text: "PID" }), el("th", { text: "进程名" }), el("th", { text: "操作" }))), tbody);

    function render(list) {
      clear(tbody);
      for (const p of list) {
        tbody.append(el("tr", {},
          el("td", { text: String(p.pid) }),
          el("td", { text: p.name }),
          el("td", {}, el("button", {
            class: "btn small danger", text: "结束",
            onclick: async () => {
              const r = await call("pos", "kill_process", p.pid);
              toast(r.message || (r.ok ? "已结束" : "结束失败"), r.ok ? "success" : "error");
              await refreshList();
            },
          }))));
      }
    }
    async function refreshList() {
      const r = await call("pos", "list_processes", filterBox.value.trim());
      if (r.ok) render(r.processes);
    }
    filterBox.addEventListener("input", debounce(refreshList, 300));
    openModal({ title: "进程管理", body: el("div", {}, el("div", { class: "form-row" }, filterBox), el("div", { class: "table-wrap", style: "max-height:50vh" }, table)) });
    render(res.processes);
  });

  // ===== 弹窗：POS 账号处理 =====
  btnAccount.addEventListener("click", async () => {
    const posPath = (boot?.history || [])[0] || "";
    if (!posPath) return toast("请先扫描出 POS", "error");
    const defaults = await call("pos", "get_account_defaults", posPath);
    const envOptions = Object.keys((posConfig?.env_group_vendor) || {}).map((k) => ({ value: k, label: k }));
    const envSel = select(envOptions, defaults.env_group || (envOptions[0] && envOptions[0].value));
    const cashierInput = textInput(defaults.account || "");
    const body = el(
      "div", { class: "form-grid" },
      el("label", { class: "sub", text: "环境" }), envSel,
      el("label", { class: "sub", text: "收银员账号" }), cashierInput
    );
    openModal({
      title: "POS账号处理", body,
      footer: [
        el("button", {
          class: "btn", text: "退出账号",
          onclick: async () => {
            const r = await call("pos", "logout_account", envSel.value, cashierInput.value.trim());
            toast(r.message || (r.ok ? "退出账号成功" : "退出账号失败"), r.ok ? "success" : "error");
          },
        }),
        el("button", {
          class: "btn", text: "重置密码",
          onclick: async () => {
            const r = await call("pos", "reset_account_password", envSel.value, cashierInput.value.trim());
            toast(r.message || (r.ok ? "重置密码成功" : "重置密码失败"), r.ok ? "success" : "error");
          },
        }),
      ],
    });
  });

  // ===== 工具 =====
  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  function appendLog(text) {
    logPre.textContent += (logPre.textContent ? "\n" : "") + text;
    logPre.scrollTop = logPre.scrollHeight;
  }

  async function saveStartConfig() {
    const data = {};
    for (const [key] of START_FIELDS) data[key] = startChecks[key].querySelector("input").checked;
    await call("pos", "save_start_config", data);
  }

  async function reload() {
    const res = await call("pos", "get_bootstrap");
    // 引导数据读取失败（如配置文件损坏）：提示真实原因，页面保留可用骨架
    if (!res.ok) {
      toast(res.message || "POS 页面初始化失败", "error");
      return;
    }
    boot = res;
    posConfig = res.pos_config;
    for (const [key] of START_FIELDS) startChecks[key].querySelector("input").checked = !!res.start_config[key];
    renderRows();
  }

  // ===== 弹窗：扫描（按已保存配置执行） =====
  btnScan.addEventListener("click", async () => {
    const res = await call("pos", "scan");
    if (!res.ok) return toast(res.message, "error");
    boot.history = res.result;
    renderRows();
  });
  btnStopPos.addEventListener("click", async () => {
    const res = await call("pos", "stop_pos");
    // 停止后不再保留之前 POS 的运行信息，状态区直接以停止结果为准
    if (res && res.message) statusLabel.textContent = res.message;
  });
  btnStopOffline.addEventListener("click", () => call("pos", "stop_offline"));
  btnSyncCfg.addEventListener("click", async () => {
    const url = (posConfig?.config_sync_url || "").trim();
    if (!url) return toast("请先在设置中填写配置拉取地址", "error");
    await call("pos", "sync_remote_config", url);
  });
  filterInput.addEventListener("input", debounce(renderRows, 200));

  // ===== 事件订阅 =====
  const on = (event, handler) => { Bus.on(event, handler); return () => Bus.off(event, handler); };
  const unsubs = [
    on("pos_status", (p) => (statusLabel.textContent = p.message || "")),
    on("pos_log", (p) => appendLog(p.message || "")),
  ];

  reload();

  const observer = new MutationObserver(() => {
    if (!document.body.contains(mount)) {
      unsubs.forEach((u) => u());
      observer.disconnect();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  return { destroy: () => unsubs.forEach((u) => u()) };
}
