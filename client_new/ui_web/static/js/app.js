/**
 * 应用外壳：导航路由、主题、全局状态栏、全局事件（弹窗桥/Toast/主题）。
 * 各页面模块只负责自己的容器内容与页面级事件。
 */
import { agentPage } from "./pages/agent.js";
import { posPage } from "./pages/pos.js";
import { sqlitePage } from "./pages/sqlite.js";
import { mitmPage } from "./pages/mitm.js";
import { logsPage } from "./pages/logs.js";
import { aboutPage } from "./pages/about.js";
import { openPluginManager } from "./plugins.js";

const { Bus, call, el, $, $$, clear, toast, openModal, backendDialog, waitForApi } = window.QTR;

const PAGE_DEFS = [
  { key: "agent", label: "Agent", render: agentPage },
  { key: "pos", label: "POS", render: posPage },
  { key: "sqlite", label: "SQLite", render: sqlitePage },
  { key: "mitm", label: "mitmproxy", render: mitmPage },
  { key: "logs", label: "日志", render: logsPage },
  { key: "about", label: "关于", render: aboutPage },
];

// mitmproxy 菜单项依赖 proxy 插件，插件缺失时隐藏（与原主窗口逻辑一致）
const PLUGIN_GATED_PAGES = { proxy: ["mitm"] };

let activePage = null;
let activeKey = "";
const pageState = {}; // key -> {inited, container}

function applyTheme(mode) {
  const root = document.documentElement;
  if (mode === "auto") delete root.dataset.theme;
  else root.dataset.theme = mode;
  $("#theme-select").value = mode;
}

async function onThemeChange(e) {
  applyTheme(e.target.value);
  await call("app", "set_theme", e.target.value);
}

function buildNav(navKeys) {
  const list = $("#nav-list");
  clear(list);
  const visible = PAGE_DEFS.filter((p) => navKeys.includes(p.key));
  for (const page of visible) {
    const li = el("li", { text: page.label, dataset: { key: page.key } });
    li.addEventListener("click", () => switchPage(page.key));
    list.append(li);
  }
  return visible;
}

function switchPage(key) {
  if (activeKey === key) return;
  const li = $$("#nav-list li").find((n) => n.dataset.key === key);
  if (!li) return;
  $$("#nav-list li").forEach((n) => n.classList.toggle("active", n.dataset.key === key));

  const container = $("#page-container");
  if (activePage && activePage.destroy) activePage.destroy();
  clear(container);
  activeKey = key;
  if (!pageState[key]) {
    const mount = el("div", { class: "page", style: "height:100%" });
    container.append(mount);
    pageState[key] = { inited: true, container: mount };
    activePage = PAGE_DEFS.find((p) => p.key === key).render(mount);
  } else {
    // 已初始化过的页面恢复 DOM（简单起见重新渲染一次）
    const mount = el("div", { class: "page", style: "height:100%" });
    container.append(mount);
    activePage = PAGE_DEFS.find((p) => p.key === key).render(mount, pageState[key]);
  }
}

async function refreshGlobalStatus() {
  try {
    const res = await call("app", "get_global_status");
    $("#status-bar").textContent = res.text || "";
  } catch (e) {
    /* 静默：状态轮询失败不打扰用户 */
  }
}

async function boot() {
  await waitForApi();
  const bootstrap = await call("app", "get_bootstrap");
  if (!bootstrap.ok) {
    toast("应用初始化失败: " + bootstrap.message, "error");
    return;
  }

  applyTheme(bootstrap.theme);
  $("#header-version").textContent = "v" + bootstrap.version;

  // 按插件安装状态过滤导航（proxy 插件缺失时隐藏 mitmproxy）
  const hidden = new Set();
  for (const plugin of bootstrap.plugins || []) {
    if (plugin.status === "missing" && PLUGIN_GATED_PAGES[plugin.name]) {
      PLUGIN_GATED_PAGES[plugin.name].forEach((k) => hidden.add(k));
    }
  }
  const navKeys = PAGE_DEFS.map((p) => p.key).filter((k) => !hidden.has(k));
  buildNav(navKeys);
  window.__qtrNavKeys = navKeys;

  $("#theme-select").addEventListener("change", onThemeChange);
  $("#btn-plugins").addEventListener("click", openPluginManager);

  // 全局事件：后端弹窗桥、Toast、主题变化、插件安装结果
  Bus.on("ui_dialog", (payload) => backendDialog(payload));
  Bus.on("ui_toast", (payload) => toast(payload.message || "", payload.level || "info"));
  Bus.on("theme_changed", (payload) => applyTheme(payload.mode));
  Bus.on("plugin_install_done", (payload) => {
    toast(payload.message || (payload.ok ? "插件任务完成" : "插件任务失败"), payload.ok ? "success" : "error");
  });

  // 全局状态轮询（2 秒，与原主窗口一致）
  await refreshGlobalStatus();
  setInterval(refreshGlobalStatus, 2000);

  // 默认进入 POS 页
  switchPage(navKeys.includes("pos") ? "pos" : navKeys[0]);
  console.log("QTRClient 前端就绪");
}

boot().catch((e) => {
  console.error(e);
  document.body.innerHTML = `<div style="padding:40px;color:#dc2626;">前端启动失败: ${e.message}</div>`;
});
