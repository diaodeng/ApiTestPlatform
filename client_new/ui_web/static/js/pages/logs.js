/** 日志页面：应用日志目录、外部文件 tail、过滤与行数上限。 */
const { Bus, call, el, $, clear, toast, openModal, textInput } = window.QTR;

export function logsPage(mount) {
  let tailing = "";
  let maxLines = 3000;
  let rawLines = [];

  const fileListBody = el("tbody", {});
  const filterInput = textInput("", { placeholder: "过滤关键字（留空显示全部）", style: "width:220px" });
  const maxLinesInput = textInput(String(maxLines), { type: "number", style: "width:80px" });
  const btnPickFile = el("button", { class: "btn", text: "选择外部日志文件" });
  const btnStopTail = el("button", { class: "btn", text: "停止跟踪", disabled: true });
  const autoScrollCheck = mkCheckbox("自动滚动", true);
  const logPre = el("pre", { class: "panel flex-fill" });
  const statusLabel = el("span", { class: "muted", text: "未在跟踪" });

  const fileTable = el(
    "table", { class: "data" },
    el("thead", {}, el("tr", {}, el("th", { text: "文件" }), el("th", { text: "大小" }), el("th", { text: "修改时间" }), el("th", { text: "操作" }))));

  mount.append(
    el("div", { class: "toolbar" },
      el("label", { text: "过滤" }), filterInput,
      el("label", { text: "最大行数" }), maxLinesInput,
      autoScrollCheck,
      btnPickFile, btnStopTail,
      el("div", { style: "flex:1" }), statusLabel),
    el("div", { class: "split-v flex-fill" },
      el("div", { class: "col", style: "flex:1" },
        el("span", { class: "sub-label", text: "应用日志文件（logs 目录）" }),
        el("div", { class: "table-wrap flex-fill" }, fileTable)),
      el("div", { class: "col", style: "flex:3" }, logPre))
  );
  fileTable.append(fileListBody);

  function mkCheckbox(label, checked) {
    const box = el("input", { type: "checkbox", checked });
    return el("label", { class: "checkbox" }, box, el("span", { text: label }));
  }

  // ===== 渲染 =====
  function renderLog() {
    const keyword = filterInput.value.trim().toLowerCase();
    rawLines = rawLines.slice(-maxLines);
    const shown = keyword ? rawLines.filter((l) => l.toLowerCase().includes(keyword)) : rawLines;
    logPre.textContent = shown.join("\n") || "（暂无日志）";
    if (autoScrollCheck.querySelector("input").checked) logPre.scrollTop = logPre.scrollHeight;
  }

  async function refreshFiles() {
    const res = await call("log", "list_log_files");
    if (!res.ok) return;
    clear(fileListBody);
    for (const f of res.files) {
      fileListBody.append(el("tr", {},
        el("td", { class: "mono small", text: f.name }),
        el("td", { class: "small", text: f.size + "B" }),
        el("td", { class: "small muted", text: f.mtime }),
        el("td", {}, el("button", {
          class: "btn small", text: "跟踪",
          onclick: () => startTail(f.path),
        }))));
    }
  }

  async function startTail(path) {
    // 打开时先读末尾 500 行
    const head = await call("log", "read_head", path, 500);
    rawLines = head.ok ? head.lines : [];
    renderLog();
    await call("log", "stop_tail");
    const res = await call("log", "start_tail", path);
    if (!res.ok) return toast(res.message, "error");
    tailing = path;
    statusLabel.textContent = "正在跟踪: " + path.split(/[\\/]/).pop();
    btnStopTail.disabled = false;
  }

  // ===== 事件 =====
  btnPickFile.addEventListener("click", async () => {
    const res = await call("choose_file", "选择日志文件", "日志文件 (*.log;*.txt)|所有文件 (*.*)");
    if (res.ok) startTail(res.path);
  });
  btnStopTail.addEventListener("click", async () => {
    await call("log", "stop_tail");
    tailing = "";
    statusLabel.textContent = "未在跟踪";
    btnStopTail.disabled = true;
  });
  filterInput.addEventListener("input", renderLog);
  maxLinesInput.addEventListener("change", () => {
    maxLines = Math.max(100, Number(maxLinesInput.value || 3000));
    renderLog();
  });

  const offTail = (() => {
    const handler = (p) => {
      if (tailing && p.path !== tailing) return;
      rawLines.push(...p.lines);
      renderLog();
    };
    Bus.on("log_tail", handler);
    return () => Bus.off("log_tail", handler);
  })();

  refreshFiles();

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
