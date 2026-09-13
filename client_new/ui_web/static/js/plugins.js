/** 插件管理弹窗（对应原 PluginManagerDialog）。 */
const { call, el, $, $$, toast, openModal, textInput, checkbox } = window.QTR;
const { Bus } = window.QTR;

export function openPluginManager() {
  let currentPlugins = [];

  const pluginsTable = el("tbody", {});
  const table = el(
    "table",
    { class: "data" },
    el("thead", {},
      el("tr", {},
        el("th", { text: "插件" }),
        el("th", { text: "状态" }),
        el("th", { text: "说明" }),
        el("th", { text: "操作" })
      )
    ),
    pluginsTable
  );

  const downloadUrlInput = textInput("", { placeholder: "插件包下载源根地址，留空走 Gitee 按版本回退下载", style: "flex:1" });
  const pipUrlInput = textInput("", { placeholder: "留空使用默认国内镜像", style: "flex:1" });
  const installDirInput = textInput("", { style: "flex:1", readonly: true });

  const body = el(
    "div", {},
    el("div", { class: "form-row" }, el("label", { text: "下载源" }), downloadUrlInput,
      el("button", { class: "btn small", text: "保存下载源", onclick: saveDownloadUrl })),
    el("div", { class: "form-row" }, el("label", { text: "Pip 源" }), pipUrlInput,
      el("button", { class: "btn small", text: "保存 Pip 源", onclick: savePipUrl })),
    el("div", { class: "form-row" }, el("label", { text: "安装目录" }), installDirInput,
      el("button", {
        class: "btn small", text: "选择目录",
        onclick: async () => {
          const res = await call("choose_dir", "选择插件安装目录");
          if (res.ok) installDirInput.value = res.path;
        },
      }),
      checkbox("迁移已有插件", true),
      el("button", { class: "btn small", text: "保存安装目录", onclick: saveInstallDir })),
    el("div", { class: "table-wrap", style: "max-height: 46vh; margin-top: 8px" }, table),
    el("div", { class: "hint", style: "margin-top:6px", text: "安装完成后部分插件需重启客户端生效（状态为“已安装”时请重启）。" })
  );

  const modal = openModal({ title: "插件管理", body, wide: true });

  async function saveDownloadUrl() {
    const res = await call("app", "save_plugin_download_url", downloadUrlInput.value.trim());
    toast(res.message || (res.ok ? "已保存" : "保存失败"), res.ok ? "success" : "error");
  }
  async function savePipUrl() {
    const res = await call("app", "save_plugin_pip_url", pipUrlInput.value.trim());
    toast(res.message || (res.ok ? "已保存" : "保存失败"), res.ok ? "success" : "error");
  }
  async function saveInstallDir() {
    const migrateBox = $$('input[type="checkbox"]', modal.body).find((i) => i.parentElement.textContent.includes("迁移"));
    const res = await call("app", "save_plugin_install_dir", installDirInput.value.trim(), migrateBox ? migrateBox.checked : true);
    toast(res.message || (res.ok ? "已保存" : "保存失败"), res.ok ? "success" : "error");
  }

  function renderPlugins(plugins) {
    currentPlugins = plugins || [];
    const tbody = pluginsTable;
    window.QTR.clear(tbody);
    for (const p of currentPlugins) {
      const statusChip = el("span", { class: "chip" + (p.status === "active" ? " ok" : p.status === "missing" ? " err" : " warn"), text: p.status_text });
      const actions = el("div", { style: "display:flex;gap:6px;flex-wrap:wrap" });
      const disabled = p.busy;
      const btnOnline = el("button", {
        class: "btn small", text: disabled ? "处理中..." : "在线下载", disabled,
        onclick: async () => {
          const res = await call("app", "install_plugin_online", p.name);
          if (!res.ok) toast(res.message, "error");
        },
      });
      const btnZip = el("button", {
        class: "btn small", text: "本地安装", disabled,
        onclick: async () => {
          const file = await call("choose_file", "选择插件压缩包", "插件包 (*.zip)|所有文件 (*.*)");
          if (!file.ok) return;
          const res = await call("app", "install_plugin_zip", p.name, file.path);
          if (!res.ok) toast(res.message, "error");
        },
      });
      const btnPip = el("button", {
        class: "btn small", text: "Pip安装", disabled,
        onclick: async () => {
          const res = await call("app", "install_plugin_pip", p.name);
          if (!res.ok) toast(res.message, "error");
        },
      });
      actions.append(btnOnline, btnZip, btnPip);
      tbody.append(el("tr", {},
        el("td", { text: p.title }),
        el("td", {}, statusChip),
        el("td", { class: "muted", text: p.description }),
        el("td", {}, actions)
      ));
    }
  }

  async function loadSettings() {
    const res = await call("app", "get_plugin_settings");
    if (res.ok) {
      downloadUrlInput.value = res.download_base_url || "";
      pipUrlInput.value = res.pip_index_url || "";
      installDirInput.value = res.install_dir || "";
    }
  }

  async function refresh() {
    const res = await call("app", "list_plugins");
    if (res.ok) renderPlugins(res.plugins);
  }

  Bus.on("plugin_status_changed", (payload) => renderPlugins(payload.plugins));
  Bus.on("plugin_install_done", (payload) => {
    if (payload.plugins) renderPlugins(payload.plugins);
  });

  // 弹窗关闭时取消订阅
  const observer = new MutationObserver(() => {
    if (!document.body.contains(body)) {
      Bus.off("plugin_status_changed", handlerStatus);
      Bus.off("plugin_install_done", handlerDone);
      observer.disconnect();
    }
  });
  const handlerStatus = (payload) => renderPlugins(payload.plugins);
  const handlerDone = (payload) => {
    if (payload.plugins) renderPlugins(payload.plugins);
  };
  Bus.on("plugin_status_changed", handlerStatus);
  Bus.on("plugin_install_done", handlerDone);
  observer.observe(document.body, { childList: true, subtree: true });

  refresh();
  loadSettings();
}
