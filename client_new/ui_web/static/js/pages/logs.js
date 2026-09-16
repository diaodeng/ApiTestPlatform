/**
 * 日志页面：三个页签（SSH日志 / 本地日志 / 程序日志），与原 PySide6 版结构一致。
 *
 * 本地日志与程序日志为两路完全独立的监控：
 * - 各自维护独立的监听状态、已读内容与监听开关，互不影响；
 * - 本地日志：选择文件仅"选中"，勾选「监听日志」才开始 tail，取消勾选即停止；
 * - 程序日志：完全监听当前程序自身日志（logs 目录当天文件），由独立开关控制。
 *
 * 监控会话（tail 状态、已读内容、页签、过滤配置）保存在模块级 session 中：
 * 切换到其它页面不会中断监控，回到日志页时恢复当前页签与内容继续显示。
 */
const { Bus, call, el, $, clear, toast, textInput, copyText } = window.QTR;

// ===== 模块级监控会话（跨页面切换保持） =====
// 每个来源（local/app）独立持有：监控文件路径、是否在监听、已累计日志行。
const session = {
  tab: "local",        // 当前页签
  filter: "",
  maxLines: 3000,
  autoScroll: true,
  local: { path: "", tailing: false, lines: [] },  // 本地日志会话
  app: { path: "", tailing: false, lines: [] },    // 程序日志会话
};
let busBound = false;
// 当前页面实例的视图引用（页面挂载期间有效，供事件处理器刷新显示）
let views = null;

function bindBusOnce() {
  if (busBound) return;
  busBound = true;
  Bus.on("log_tail", (p) => {
    const src = p.source === "app" ? "app" : "local";
    const one = session[src];
    // 只接收该来源当前正在监听的文件内容（切换文件后旧线程的残留推送会被丢弃）
    if (!one.tailing || p.path !== one.path) return;
    one.lines.push(...p.lines);
    if (one.lines.length > session.maxLines * 2) {
      one.lines = one.lines.slice(-session.maxLines);
    }
    renderViews();
  });
}

function renderViews() {
  if (!views) return;
  const keyword = session.filter.trim().toLowerCase();
  const pick = (lines) => {
    const shown = keyword
      ? lines.filter((l) => l.toLowerCase().includes(keyword))
      : lines;
    return shown.join("\n") || "（暂无日志）";
  };
  for (const [key, pre] of [["local", views.localPre], ["app", views.appPre]]) {
    pre.textContent = pick(session[key].lines);
    if (session.autoScroll) pre.scrollTop = pre.scrollHeight;
  }
}

// ===== tail 控制（后端按 source 隔离，两路互不影响） =====

async function startTail(source, path) {
  const head = await call("log", "read_head", path, 500);
  const one = session[source];
  one.lines = head.ok ? head.lines : [];
  const res = await call("log", "start_tail", source, path);
  if (!res.ok) return toast(res.message, "error");
  one.path = path;
  one.tailing = true;
  renderViews();
}

async function stopTail(source) {
  await call("log", "stop_tail", source);
  const one = session[source];
  one.tailing = false;
}

// ===== 复制：优先复制用户选中的文本，无选区时复制全部内容 =====

function copyPanelContent(pre) {
  const selected = String(window.getSelection ? window.getSelection() : "").trim();
  copyText(selected || pre.textContent);
}

export function logsPage(mount) {
  bindBusOnce();

  // ===== 页签框架 =====
  const TAB_DEFS = [
    { key: "ssh", label: "SSH日志" },
    { key: "local", label: "本地日志" },
    { key: "app", label: "程序日志" },
  ];
  const tabBar = el("div", { class: "toolbar", style: "margin:0" });
  const tabBody = el("div", { class: "flex-fill", style: "display:flex;flex-direction:column;gap:6px;min-height:0" });
  const panels = {};
  for (const t of TAB_DEFS) {
    panels[t.key] = el("div", { style: "display:none;flex-direction:column;gap:6px;flex:1;min-height:0" });
    const btn = el("button", { class: "btn small tab-btn", text: t.label, dataset: { tab: t.key } });
    btn.addEventListener("click", () => switchTab(t.key));
    tabBar.append(btn);
  }
  tabBody.append(...TAB_DEFS.map((t) => panels[t.key]));

  function switchTab(key) {
    session.tab = key;
    for (const t of TAB_DEFS) {
      panels[t.key].style.display = t.key === key ? "flex" : "none";
      const btn = [...tabBar.children].find((b) => b.dataset.tab === t.key);
      if (btn) btn.classList.toggle("active", t.key === key);
    }
  }

  // ===== 公共：过滤控件（状态保存在 session，页面切换不丢失） =====
  const filterInput = textInput(session.filter, { placeholder: "过滤关键字（留空显示全部）", style: "width:200px" });
  const maxLinesInput = textInput(String(session.maxLines), { type: "number", style: "width:80px" });
  const autoScrollCheck = mkCheckbox("自动滚动", session.autoScroll);
  filterInput.addEventListener("input", () => {
    session.filter = filterInput.value;
    renderViews();
  });
  maxLinesInput.addEventListener("change", () => {
    session.maxLines = Math.max(100, Number(maxLinesInput.value || 3000));
    renderViews();
  });
  autoScrollCheck.addEventListener("change", () => {
    session.autoScroll = autoScrollCheck.querySelector("input").checked;
    renderViews();
  });

  function mkCheckbox(label, checked) {
    const box = el("input", { type: "checkbox", checked });
    return el("label", { class: "checkbox" }, box, el("span", { text: label }));
  }

  // ===== Tab 1：SSH日志（原版即为占位，保留交互与提示） =====
  const sshLogPre = el("pre", { class: "panel", style: "flex:1;min-height:0", text: "（SSH 实时日志未启用）" });
  const sshStatus = el("span", { class: "muted", text: "未连接" });
  const sshHost = textInput("", { placeholder: "主机地址", style: "flex:2" });
  const sshPort = textInput("22", { style: "width:70px" });
  const sshUser = textInput("", { placeholder: "用户名", style: "flex:1" });
  const sshPassword = textInput("", { placeholder: "密码", type: "password", style: "flex:1" });
  const sshPath = textInput("/var/log/syslog", { style: "flex:2" });
  panels.ssh.append(
    el("div", { class: "toolbar", style: "margin:0" },
      el("label", { text: "主机" }), sshHost,
      el("label", { text: "端口" }), sshPort,
      el("label", { text: "用户" }), sshUser,
      el("label", { text: "密码" }), sshPassword),
    el("div", { class: "toolbar", style: "margin:0" },
      el("label", { text: "日志路径" }), sshPath,
      el("button", {
        class: "btn", text: "连接SSH",
        onclick: () => {
          sshStatus.textContent = "未实现";
          sshLogPre.textContent += (sshLogPre.textContent ? "\n" : "") + "当前版本未启用 SSH 实时日志功能";
        },
      }),
      sshStatus),
    sshLogPre
  );

  // ===== Tab 2：本地日志（选择外部文件，独立监听开关） =====
  const localPre = el("pre", { class: "panel", style: "flex:1;min-height:0" });
  const localPathLabel = el("span", { class: "muted small", text: session.local.path || "未选择文件" });
  const localStatus = el("span", { class: "muted", text: "未在监听" });
  const localWatchCheck = mkCheckbox("监听日志", session.local.tailing);
  const fileName = (p) => p.split(/[\\/]/).pop();

  // 「选择文件」只负责选中文件（更新路径显示），不自动开始监听
  const chooseBtn = el("button", {
    class: "btn", text: "选择文件",
    onclick: async () => {
      const res = await call("choose_file", "选择日志文件", "日志文件 (*.log;*.txt)|所有文件 (*.*)");
      if (!res.ok) return;
      session.local.path = res.path;
      localPathLabel.textContent = res.path;
      // 若当前正在监听旧文件，切换到新文件继续监听；否则仅选中不监听
      if (localWatchCheck.querySelector("input").checked) {
        await startTail("local", res.path);
        localStatus.textContent = "正在监听: " + fileName(res.path);
      } else {
        localStatus.textContent = "已选中，未监听";
      }
    },
  });

  // 独立监听开关：勾选开始监听选中文件，取消勾选停止监听
  localWatchCheck.addEventListener("change", async () => {
    const on = localWatchCheck.querySelector("input").checked;
    if (!on) {
      await stopTail("local");
      localStatus.textContent = "已停止监听";
      return;
    }
    if (!session.local.path) {
      localWatchCheck.querySelector("input").checked = false;
      localStatus.textContent = "请先选择文件";
      return toast("请先选择要监听的日志文件", "error");
    }
    await startTail("local", session.local.path);
    localStatus.textContent = "正在监听: " + fileName(session.local.path);
  });

  panels.local.append(
    el("div", { class: "toolbar", style: "margin:0" },
      chooseBtn,
      localWatchCheck,
      localPathLabel,
      el("div", { style: "flex:1" }), localStatus),
    el("div", { class: "toolbar", style: "margin:0" },
      el("label", { text: "过滤" }), filterInput,
      el("label", { text: "最大行数" }), maxLinesInput,
      autoScrollCheck,
      el("button", {
        class: "btn small", text: "复制",
        onclick: () => copyPanelContent(localPre),
      })),
    localPre
  );

  // ===== Tab 3：程序日志（完全监听当前程序自身日志，独立监听开关） =====
  const appPre = el("pre", { class: "panel", style: "flex:1;min-height:0" });
  const watchAppCheck = mkCheckbox("监听日志", session.app.tailing);
  const appStatus = el("span", { class: "muted", text: "未在监听" });
  watchAppCheck.addEventListener("change", async () => {
    const on = watchAppCheck.querySelector("input").checked;
    if (!on) {
      await stopTail("app");
      appStatus.textContent = "已停止监听";
      return;
    }
    const res = await call("log", "get_app_log_file");
    if (!res.ok) {
      watchAppCheck.querySelector("input").checked = false;
      appStatus.textContent = "未找到应用日志文件";
      return toast(res.message || "未找到应用日志文件", "error");
    }
    await startTail("app", res.path);
    appStatus.textContent = "正在监听: " + fileName(res.path);
  });
  panels.app.append(
    el("div", { class: "toolbar", style: "margin:0" },
      watchAppCheck,
      el("div", { style: "flex:1" }),
      el("button", { class: "btn small", text: "复制", onclick: () => copyPanelContent(appPre) }),
      appStatus),
    appPre
  );

  mount.append(tabBar, tabBody);

  // ===== 挂载视图并恢复现场 =====
  views = { localPre, appPre };
  switchTab(session.tab || "local");
  if (session.local.tailing && session.local.path) {
    localStatus.textContent = "正在监听: " + fileName(session.local.path);
  } else if (session.local.path) {
    localStatus.textContent = "已选中，未监听";
  }
  if (session.app.tailing && session.app.path) {
    appStatus.textContent = "正在监听: " + fileName(session.app.path);
  }
  renderViews();

  // ===== 首次进入：本地日志默认选中当前程序日志文件，但不开始监听 =====
  if (!session.local.path) {
    call("log", "get_app_log_file").then((res) => {
      if (!res.ok || session.local.path) return;
      session.local.path = res.path;
      localPathLabel.textContent = res.path;
      if (views && !(session.local.tailing && session.local.path)) {
        localStatus.textContent = "已选中，未监听";
      }
    });
  }

  // ===== 页面销毁：保存现场，不中断监控 =====
  return {
    destroy() {
      session.filter = filterInput.value;
      views = null;
      // 注意：不调用 stop_tail —— 监控在后台持续，回到页面后恢复显示
    },
  };
}
