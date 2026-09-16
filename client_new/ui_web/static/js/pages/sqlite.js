/** SQLite 查询页面：库/表选择、分页浏览、快速过滤、SQL 执行、收藏、列配置。 */
const { call, el, $, clear, toast, openModal, textInput, select, copyText } = window.QTR;

export function sqlitePage(mount) {
  let cfg = null; // SqliteQueryConfigModel
  let directories = []; // 扫描结果
  let tables = [];
  let columns = [];
  let page = 1;
  let total = 0;

  // ===== 工具栏 =====
  const dirSel = select([], "", null, { style: "min-width:180px" });
  const dbSel = select([], "", null, { style: "min-width:180px" });
  const tableSel = select([], "", null, { style: "min-width:160px" });
  const btnScan = el("button", { class: "btn primary", text: "扫描" });
  const btnWorkDirs = el("button", { class: "btn", text: "工作目录" });
  const btnColumnCfg = el("button", { class: "btn", text: "列配置" });
  const filterFieldSel = select([], "", null);
  const filterOpSel = select(
    [["contains", "包含"], ["eq", "等于"], ["ne", "不等于"], ["gt", "大于"], ["lt", "小于"], ["like", "LIKE"], ["empty", "为空"]]
      .map(([v, l]) => ({ value: v, label: l })),
    "contains");
  const filterValueInput = textInput("", { style: "width:130px" });
  const btnApplyFilter = el("button", { class: "btn small", text: "应用" });
  const btnClearFilter = el("button", { class: "btn small ghost", text: "清除" });
  const pageSizeInput = textInput("100", { type: "number", style: "width:70px" });

  // ===== 分页 =====
  const pageInfo = el("span", { class: "muted", text: "- / -" });
  const btnPrev = el("button", { class: "btn small", text: "上一页", disabled: true });
  const btnNext = el("button", { class: "btn small", text: "下一页", disabled: true });
  const pageJump = textInput("", { type: "number", style: "width:64px" });
  const btnJump = el("button", { class: "btn small", text: "跳转" });

  // ===== SQL 编辑区 =====
  const sqlEditor = el("textarea", { class: "input mono", rows: 5, style: "width:100%;resize:vertical" });
  const btnRunSql = el("button", { class: "btn primary", text: "查询" });
  const btnClearSql = el("button", { class: "btn", text: "清空" });
  const btnFavManage = el("button", { class: "btn", text: "常用SQL" });
  const sqlResultPre = el("pre", { class: "panel", style: "max-height:26vh" });

  // ===== 结果表 =====
  const resultWrap = el("div", { class: "table-wrap flex-fill" });
  const statusLabel = el("span", { class: "muted", text: "就绪" });

  mount.append(
    el("div", { class: "toolbar" },
      btnWorkDirs, dirSel, btnScan,
      el("label", { text: "数据库" }), dbSel,
      el("label", { text: "表" }), tableSel,
      btnColumnCfg),
    el("div", { class: "toolbar" },
      el("label", { text: "过滤" }), filterFieldSel, filterOpSel, filterValueInput,
      btnApplyFilter, btnClearFilter,
      el("label", { text: "每页" }), pageSizeInput,
      el("div", { style: "flex:1" }),
      btnPrev, pageInfo, btnNext, pageJump, btnJump),
    resultWrap,
    el("div", { style: "display:flex;gap:8px;flex:none" },
      el("div", { style: "flex:3;display:flex;flex-direction:column;gap:6px" },
        sqlEditor,
        el("div", { class: "toolbar", style: "margin:0" }, btnRunSql, btnClearSql, btnFavManage)),
      el("div", { style: "flex:2;display:flex;flex-direction:column;gap:6px" },
        el("span", { class: "sub-label", text: "SQL 执行结果" }), sqlResultPre)),
    el("div", { class: "toolbar", style: "margin:0" }, statusLabel)
  );

  // ===== 内部逻辑 =====
  const currentTableCfg = () => {
    const key = `${cfg.last_database_path}::${cfg.last_table_name}`;
    if (!cfg.table_view_configs[key]) {
      cfg.table_view_configs[key] = { visible_columns: [], page_size: 100, filter_field: "", filter_operator: "contains", filter_value: "" };
    }
    return cfg.table_view_configs[key];
  };

  function saveCfg() { call("sqlite", "save_config", cfg); }

  function renderDirs(prefer = "") {
    clear(dirSel);
    for (const d of directories) dirSel.append(el("option", { value: d.directory_path, text: d.directory_path }));
    const target = prefer || cfg.last_directory_path;
    if (target && dirSel.querySelector(`option[value="${CSS.escape(target)}"]`)) dirSel.value = target;
    renderDatabases();
  }

  function renderDatabases(prefer = "") {
    clear(dbSel);
    const dir = directories.find((d) => d.directory_path === dirSel.value);
    for (const db of dir?.database_files || []) dbSel.append(el("option", { value: db.file_path, text: `${db.file_name} (${formatSize(db.size)})` }));
    const target = prefer || cfg.last_database_path;
    if (target && dbSel.querySelector(`option[value="${CSS.escape(target)}"]`)) dbSel.value = target;
    loadTables();
  }

  function formatSize(size) {
    if (!size && size !== 0) return "-";
    if (size < 1024) return size + "B";
    if (size < 1024 * 1024) return (size / 1024).toFixed(1) + "KB";
    return (size / 1024 / 1024).toFixed(1) + "MB";
  }

  async function loadTables(prefer = "") {
    clear(tableSel);
    columns = [];
    renderFilterFields();
    if (!dbSel.value) return renderTable({ columns: [], rows: [] });
    const res = await call("sqlite", "list_tables", dbSel.value);
    if (!res.ok) return toast(res.message, "error");
    tables = res.tables;
    for (const t of tables) tableSel.append(el("option", { value: t, text: t }));
    const target = prefer || cfg.last_table_name;
    if (target && tables.includes(target)) tableSel.value = target;
    loadTableData(1);
  }

  function renderFilterFields() {
    clear(filterFieldSel);
    filterFieldSel.append(el("option", { value: "", text: "（全部列）" }));
    for (const c of columns) filterFieldSel.append(el("option", { value: c, text: c }));
  }

  async function loadTableData(targetPage = 1) {
    cfg.last_directory_path = dirSel.value;
    cfg.last_database_path = dbSel.value;
    cfg.last_table_name = tableSel.value;
    saveCfg();

    if (!dbSel.value || !tableSel.value) return renderTable({ columns: [], rows: [] });
    const tcfg = currentTableCfg();
    const res = await call("sqlite", "fetch_table_page",
      dbSel.value, tableSel.value, targetPage, Number(pageSizeInput.value || tcfg.page_size || 100),
      tcfg.filter_field || "", tcfg.filter_operator || "contains", tcfg.filter_value || "");
    if (!res.ok) { toast(res.message, "error"); return; }
    page = res.page;
    total = res.total;
    columns = res.columns;
    renderFilterFields();
    renderTable(res);
    updatePagination();
  }

  function renderTable(data) {
    clear(resultWrap);
    const visible = currentTableCfg().visible_columns || [];
    const showCols = visible.length ? data.columns.filter((c) => visible.includes(c)) : data.columns;
    const table = el("table", { class: "data" });
    table.append(el("thead", {}, el("tr", {}, showCols.map((c) => el("th", { text: c })))));
    const tbody = el("tbody", {});
    const colIdx = showCols.map((c) => data.columns.indexOf(c));
    for (const row of data.rows || []) {
      tbody.append(el("tr", {}, colIdx.map((i) => el("td", {
        text: row[i] === null || row[i] === undefined ? "NULL" : String(row[i]),
        class: row[i] === null || row[i] === undefined ? "muted" : "",
        title: row[i] === null || row[i] === undefined ? "" : String(row[i]),
      }))));
    }
    table.append(tbody);
    resultWrap.append(table);
  }

  function updatePagination() {
    const size = Number(pageSizeInput.value || 100);
    const totalPages = Math.max(1, Math.ceil(total / size));
    pageInfo.textContent = `第 ${page} / ${totalPages} 页，共 ${total} 行`;
    btnPrev.disabled = page <= 1;
    btnNext.disabled = page >= totalPages;
  }

  // ===== 工具栏事件 =====
  btnScan.addEventListener("click", async () => {
    statusLabel.textContent = "开始扫描 SQLite 数据库...";
    const res = await call("sqlite", "scan_databases");
    if (!res.ok) return toast(res.message, "error");
    directories = res.directories;
    cfg.scanned_directories = directories;
    saveCfg();
    const totalDb = directories.reduce((n, d) => n + (d.database_files || []).length, 0);
    statusLabel.textContent = `扫描完成，找到 ${directories.length} 个目录，${totalDb} 个数据库文件`;
    renderDirs();
  });
  dirSel.addEventListener("change", () => renderDatabases());
  dbSel.addEventListener("change", () => loadTables());
  tableSel.addEventListener("change", () => loadTableData(1));
  btnPrev.addEventListener("click", () => loadTableData(page - 1));
  btnNext.addEventListener("click", () => loadTableData(page + 1));
  btnJump.addEventListener("click", () => loadTableData(Number(pageJump.value || 1)));
  pageSizeInput.addEventListener("change", () => {
    currentTableCfg().page_size = Number(pageSizeInput.value || 100);
    saveCfg();
    loadTableData(1);
  });
  btnApplyFilter.addEventListener("click", () => {
    const tcfg = currentTableCfg();
    tcfg.filter_field = filterFieldSel.value;
    tcfg.filter_operator = filterOpSel.value;
    tcfg.filter_value = filterValueInput.value;
    saveCfg();
    loadTableData(1);
  });
  btnClearFilter.addEventListener("click", () => {
    filterValueInput.value = "";
    const tcfg = currentTableCfg();
    tcfg.filter_field = "";
    tcfg.filter_value = "";
    saveCfg();
    loadTableData(1);
  });

  // ===== 弹窗：工作目录 =====
  btnWorkDirs.addEventListener("click", async () => {
    const res = await call("sqlite", "get_work_dirs");
    const dirs = res.work_dirs || [];
    const body = el("div", {},
      el("div", { class: "table-wrap", style: "max-height:40vh" },
        el("table", { class: "data" }, el("tbody", {},
          dirs.map((d) => el("tr", {},
            el("td", { text: d }),
            el("td", {}, el("button", {
              class: "btn small danger", text: "删除",
              onclick: async (e) => {
                await call("sqlite", "remove_work_dir", d);
                e.target.closest("tr").remove();
              },
            }))))))));
    openModal({
      title: "SQLite 工作目录", body,
      footer: [
        el("button", {
          class: "btn", text: "添加目录",
          onclick: async () => {
            const r = await call("choose_dir", "选择扫描目录");
            if (r.ok) await call("sqlite", "add_work_dir", r.path);
            body.querySelector("tbody").append(el("tr", {},
              el("td", { text: r.path }),
              el("td", {}, el("button", { class: "btn small danger", text: "删除", onclick: (e) => e.target.closest("tr").remove() }))));
          },
        }),
      ],
    });
  });

  // ===== 弹窗：列配置 =====
  btnColumnCfg.addEventListener("click", () => {
    const tcfg = currentTableCfg();
    const boxes = columns.map((c) => {
      const checked = !tcfg.visible_columns.length || tcfg.visible_columns.includes(c);
      return { col: c, node: window.QTR.checkbox(c, checked) };
    });
    const body = el("div", { style: "display:grid;grid-template-columns:repeat(3,1fr);gap:6px" },
      boxes.map((b) => b.node));
    openModal({
      title: "列配置", body,
      footer: [
        el("button", {
          class: "btn", text: "全选",
          onclick: () => boxes.forEach((b) => (b.node.querySelector("input").checked = true)),
        }),
        el("button", {
          class: "btn primary", text: "应用",
          onclick: () => {
            const selected = boxes.filter((b) => b.node.querySelector("input").checked).map((b) => b.col);
            tcfg.visible_columns = selected.length === columns.length ? [] : selected;
            saveCfg();
            loadTableData(page);
          },
        }),
      ],
    });
  });

  // ===== SQL 执行 =====
  btnRunSql.addEventListener("click", async () => {
    const sql = sqlEditor.value.trim();
    if (!sql) return toast("请输入 SQL", "error");
    if (!dbSel.value) return toast("请先选择数据库", "error");
    cfg.last_sql = sql;
    saveCfg();
    const res = await call("sqlite", "execute_sql", dbSel.value, sql);
    if (!res.ok) {
      sqlResultPre.textContent = "执行失败: " + res.message;
      return toast(res.message, "error");
    }
    sqlResultPre.textContent = `执行成功，${res.total ?? (res.rows || []).length} 行`;
    if (res.columns) {
      renderTable(res);
      statusLabel.textContent = `SQL 执行成功，返回 ${(res.rows || []).length} 行`;
    }
  });
  btnClearSql.addEventListener("click", () => { sqlEditor.value = ""; });
  sqlEditor.addEventListener("change", () => { cfg.last_sql = sqlEditor.value; saveCfg(); });

  // ===== 弹窗：常用 SQL =====
  btnFavManage.addEventListener("click", () => {
    const tbody = el("tbody", {});
    const nameInput = textInput("", { placeholder: "常用 SQL 名称", style: "width:150px" });
    const scopeSel = select([{ value: "global", label: "全局" }, { value: "database", label: "当前数据库" }], "global");
    const sqlInput = el("textarea", { class: "input mono", rows: 4, style: "width:100%", placeholder: "这里可以编辑要保存或载入的 SQL" });

    function renderList() {
      clear(tbody);
      for (const fav of cfg.favorite_sqls || []) {
        tbody.append(el("tr", {},
          el("td", { text: fav.name }),
          el("td", { text: fav.scope === "global" ? "全局" : "数据库" }),
          el("td", { class: "mono muted small", text: (fav.sql || "").slice(0, 60) }),
          el("td", {},
            el("button", {
              class: "btn small", text: "载入到主页面",
              onclick: () => { sqlEditor.value = fav.sql; cfg.last_sql = fav.sql; saveCfg(); toast("已载入", "success", 1200); },
            }),
            el("button", {
              class: "btn small danger", text: "删除",
              onclick: async (e) => {
                await call("sqlite", "save_config", { ...cfg, favorite_sqls: cfg.favorite_sqls.filter((f) => f !== fav) });
                cfg.favorite_sqls = cfg.favorite_sqls.filter((f) => f !== fav);
                e.target.closest("tr").remove();
              },
            }))));
      }
    }

    const body = el(
      "div", {},
      el("div", { class: "table-wrap", style: "max-height:32vh" },
        el("table", { class: "data" },
          el("thead", {}, el("tr", {}, el("th", { text: "名称" }), el("th", { text: "范围" }), el("th", { text: "SQL" }), el("th", { text: "操作" }))),
          tbody)),
      el("div", { class: "form-row", style: "margin-top:8px" }, nameInput, scopeSel,
        el("button", {
          class: "btn small primary", text: "保存当前SQL",
          onclick: () => {
            const sql = sqlInput.value.trim() || sqlEditor.value.trim();
            if (!sql) return toast("SQL 内容为空", "error");
            if (!nameInput.value.trim()) return toast("请填写名称", "error");
            const fav = {
              name: nameInput.value.trim(), sql,
              scope: scopeSel.value, database_path: dbSel.value, table_name: tableSel.value,
            };
            cfg.favorite_sqls = [...(cfg.favorite_sqls || []), fav];
            saveCfg();
            renderList();
            toast("已保存", "success", 1200);
          },
        })),
      el("div", {}, sqlInput)
    );
    openModal({ title: "常用 SQL", body });
    renderList();
  });

  // ===== 初始化 =====
  (async function init() {
    const res = await call("sqlite", "get_config");
    if (!res.ok) return;
    cfg = res.config;
    directories = cfg.scanned_directories || [];
    sqlEditor.value = cfg.last_sql || "";
    renderDirs(cfg.last_directory_path);
  })();

  return {};
}
