/** 日志页面：三个页签（SSH日志 / 本地日志 / 程序日志），与原 PySide6 版结构一致。 */
const { Bus, call, el, $, clear, toast, textInput, copyText } = window.QTR;

export function logsPage(mount) {
  let maxLines = 3000;
  let rawLines = [];
  let tailing = "";

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
    const btn = el("button", { class: "btn small", text: t.label, dataset: { tab: t.key } });
    btn.addEventListener("click", () => switchTab(t.key));
    tabBar.append(btn);
  }
  tabBody.append(...TAB_DEFS.map((t) => panels[t.key]));

  function switchTab(key) {
    for (const t of TAB_DEFS) {
      panels[t.key].style.display = t.key === key ? "flex" : "none";
      const btn = tabBar.children.find ? [...tabBar.children].find((b) => b.dataset.tab === t.key) : null;
      if (btn) btn.classList.toggle("primary", t.key === key);
    }
  }

  mount.append(tabBar, tabBody);

  // ===== 公共：日志渲染与过滤 =====
  const filterInput = textInput("", { placeholder: "过滤关键字（留空显示全部）", style: "width:200px" });
  const maxLinesInput = textInput(String(maxLines), { type: "number", style: "width:80px" });
  const autoScrollCheck = mkCheckbox("自动滚动", true);

  function mkCheckbox(label, checked) {
    const box = el("input", { type: "checkbox", checked });
    return el("label", { class: "checkbox" }, box, el("span", { text: label }));
  }

  function makeLogPre() {
    return el("pre", { class: "panel", style: "flex:1;min-height:0" });
  }

  function renderLog(pre) {
    const keyword = filterInput.value.trim().toLowerCase();
    rawLines = rawLines.slice(-maxLines);
    const shown = keyword ? rawLines.filter((l) => l.toLowerCase().includes(keyword)) : rawLines;
    pre.textContent = shown.join("\n") || "（暂无日志）";
    if (autoScrollCheck.querySelector("input").checked) pre.scrollTop = pre.scrollHeight;
  }

  async function startTail(path) {
    const head = await call("log", "read_head", path, 500);
    rawLines = head.ok ? head.lines : [];
    await call("log", "stop_tail");
    const res = await call("log", "start_tail", path);
    if (!res.ok) return toast(res.message, "error");
    tailing = path;
  }

  // ===== Tab 1：SSH日志（原版即为占位，保留交互与提示） =====
  const sshLogPre = makeLogPre();
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
          appendSsh("当前版本未启用 SSH 实时日志功能");
        },
      }),
      sshStatus),
    sshLogPre
  );
  function appendSsh(text) {
    sshLogPre.textContent += (sshLogPre.textContent ? "\n" : "") + text;
    sshLogPre.scrollTop = sshLogPre.scrollHeight;
  }

  // ===== Tab 2：本地日志（选择外部文件 + tail） =====
  const localPre = makeLogPre();
  const localPathLabel = el("span", { class: "muted small", text: "未选择文件" });
  const localStatus = el("span", { class: "muted", text: "未在跟踪" });
  panels.local.append(
    el("div", { class: "toolbar", style: "margin:0" },
      el("button", {
        class: "btn", text: "选择文件",
        onclick: async () => {
          const res = await call("choose_file", "选择日志文件", "日志文件 (*.log;*.txt)|所有文件 (*.*)");
          if (!res.ok) return;
          localPathLabel.textContent = res.path;
          await startTail(res.path);
          renderLog(localPre);
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

  // ===== Tab 3：程序日志（监控 logs 目录下最新日志文件） =====
  const appPre = makeLogPre();
  const watchAppCheck = mkCheckbox("监控日志", false);
  const appStatus = el("span", { class: "muted", text: "就绪" });
  panels.app.append(
    el("div", { class: "toolbar", style: "margin:0" },
      watchAppCheck,
      el("div", { style: "flex:1" }),
      el("button", { class: "btn small", text: "复制", onclick: () => copyText(appPre.textContent) }),
      appStatus),
    appPre
  );
  watchAppCheck.addEventListener("change", async () => {
    const on = watchAppCheck.querySelector("input").checked;
    if (!on) {
      await call("log", "stop_tail");
      tailing = "";
      appStatus.textContent = "已停止监控";
      return;
    }
    const res = await call("log", "list_log_files");
    if (!res.ok || !res.files.length) {
      appStatus.textContent = "未找到应用日志文件";
      return toast(res.message || "未找到应用日志文件", "error");
    }
    // 监控最新的应用日志（列表已按修改时间倒序）
    const target = res.files.find((f) => f.name.endsWith(".log"));
    if (!target) return toast("未找到 .log 应用日志文件", "error");
    await startTail(target.path);
    appStatus.textContent = "正在监控: " + target.name;
  });

  // ===== 公共过滤控件联动 =====
  filterInput.addEventListener("input", () => renderLog(localPre));
  filterInput.addEventListener("input", () => renderLog(appPre));
  maxLinesInput.addEventListener("change", () => {
    maxLines = Math.max(100, Number(maxLinesInput.value || 3000));
    renderLog(localPre);
    renderLog(appPre);
  });

  // ===== 后端 tail 事件分发到当前跟踪的页面 =====
  const offTail = (() => {
    const handler = (p) => {
      if (tailing && p.path !== tailing) return;
      rawLines.push(...p.lines);
      if (panels.local.style.display !== "none") renderLog(localPre);
      else renderLog(appPre);
    };
    Bus.on("log_tail", handler);
    return () => Bus.off("log_tail", handler);
  })();

  switchTab("local");

  const observer = new MutationObserver(() => {
    if (!document.body.contains(mount)) {
      offTail();
      call("log", "stop_tail");
      observer.disconnect();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  return { destroy: () => { offTail(); call("log", "stop_tail"); } };
}
