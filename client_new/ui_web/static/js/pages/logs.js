/**
 * 日志页面：三个页签（SSH日志 / 本地日志 / 程序日志），与原 PySide6 版结构一致。
 *
 * 监控会话（tail 状态、已读内容、页签、过滤配置）保存在模块级 session 中：
 * 切换到其它页面不会中断监控，回到日志页时恢复当前页签与内容继续显示。
 */
const { Bus, call, el, $, clear, toast, textInput, copyText } = window.QTR;

// ===== 模块级监控会话（跨页面切换保持） =====
const session = {
  tab: "local",        // 当前页签
  tailing: "",         // 正在跟踪的文件路径
  source: "",          // 跟踪来源：local（本地文件）/ app（程序日志）
  rawLines: [],        // 已累计的日志行
  maxLines: 3000,
  filter: "",
  autoScroll: true,
};
let busBound = false;
// 当前页面实例的视图引用（页面挂载期间有效，供事件处理器刷新显示）
let views = null;

function bindBusOnce() {
  if (busBound) return;
  busBound = true;
  Bus.on("log_tail", (p) => {
    if (session.tailing && p.path !== session.tailing) return;
    session.rawLines.push(...p.lines);
    if (session.rawLines.length > session.maxLines * 2) {
      session.rawLines = session.rawLines.slice(-session.maxLines);
    }
    renderViews();
  });
}

function renderViews() {
  if (!views) return;
  const keyword = session.filter.trim().toLowerCase();
  const shown = keyword
    ? session.rawLines.filter((l) => l.toLowerCase().includes(keyword))
    : session.rawLines;
  for (const pre of [views.localPre, views.appPre]) {
    pre.textContent = shown.join("\n") || "（暂无日志）";
    if (session.autoScroll) pre.scrollTop = pre.scrollHeight;
  }
}

async function startTail(path, source) {
  const head = await call("log", "read_head", path, 500);
  session.rawLines = head.ok ? head.lines : [];
  await call("log", "stop_tail");
  const res = await call("log", "start_tail", path);
  if (!res.ok) return toast(res.message, "error");
  session.tailing = path;
  session.source = source;
  renderViews();
}

async function stopTail() {
  await call("log", "stop_tail");
  session.tailing = "";
  session.source = "";
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

  // ===== Tab 2：本地日志（选择外部文件 + tail） =====
  const localPre = el("pre", { class: "panel", style: "flex:1;min-height:0" });
  const localPathLabel = el("span", { class: "muted small", text: session.tailing || "未选择文件" });
  const localStatus = el("span", { class: "muted", text: session.source === "local" ? "正在跟踪" : "未在跟踪" });
  panels.local.append(
    el("div", { class: "toolbar", style: "margin:0" },
      el("button", {
        class: "btn", text: "选择文件",
        onclick: async () => {
          const res = await call("choose_file", "选择日志文件", "日志文件 (*.log;*.txt)|所有文件 (*.*)");
          if (!res.ok) return;
          localPathLabel.textContent = res.path;
          await startTail(res.path, "local");
          localStatus.textContent = "正在跟踪: " + res.path.split(/[\\/]/).pop();
        },
      }),
      localPathLabel,
      el("div", { style: "flex:1" }), localStatus),
    el("div", { class: "toolbar", style: "margin:0" },
      el("label", { text: "过滤" }), filterInput,
      el("label", { text: "最大行数" }), maxLinesInput,
      autoScrollCheck,
      el("button", {
        class: "btn small", text: "复制",
        onclick: () => copyText(localPre.textContent),
      })),
    localPre
  );

  // ===== Tab 3：程序日志（监控当天应用日志） =====
  const appPre = el("pre", { class: "panel", style: "flex:1;min-height:0" });
  const watchAppCheck = mkCheckbox("监控日志", session.source === "app" && !!session.tailing);
  const appStatus = el("span", { class: "muted", text: "就绪" });
  watchAppCheck.addEventListener("change", async () => {
    const on = watchAppCheck.querySelector("input").checked;
    if (!on) {
      await stopTail();
      appStatus.textContent = "已停止监控";
      return;
    }
    const res = await call("log", "get_app_log_file");
    if (!res.ok) {
      watchAppCheck.querySelector("input").checked = false;
      appStatus.textContent = "未找到应用日志文件";
      return toast(res.message || "未找到应用日志文件", "error");
    }
    await startTail(res.path, "app");
    appStatus.textContent = "正在监控: " + res.path.split(/[\\/]/).pop();
  });
  panels.app.append(
    el("div", { class: "toolbar", style: "margin:0" },
      watchAppCheck,
      el("div", { style: "flex:1" }),
      el("button", { class: "btn small", text: "复制", onclick: () => copyText(appPre.textContent) }),
      appStatus),
    appPre
  );

  mount.append(tabBar, tabBody);

  // ===== 挂载视图并恢复现场 =====
  views = { localPre, appPre };
  switchTab(session.tab || "local");
  if (session.source === "app" && session.tailing) {
    appStatus.textContent = "正在监控: " + session.tailing.split(/[\\/]/).pop();
  } else if (session.source === "local" && session.tailing) {
    localStatus.textContent = "正在跟踪: " + session.tailing.split(/[\\/]/).pop();
  }
  renderViews();

  // ===== 页面销毁：保存现场，不中断监控 =====
  return {
    destroy() {
      session.filter = filterInput.value;
      views = null;
      // 注意：不调用 stop_tail —— 监控在后台持续，回到页面后恢复显示
    },
  };
}
