/**
 * mitm.js 详情刷新条件收紧 + 滚动保持 的 stub 环境真实执行验证。
 * 模拟 window.QTR / DOM / pywebview，真实 import mitmPage 并跑完整事件链路。
 */
import assert from "node:assert";

// 全局环境（必须在任何 window 引用之前）
globalThis.window = globalThis;
globalThis.localStorage = { getItem: () => null, setItem() {} };
globalThis.MutationObserver = class { observe() {} disconnect() {} };
globalThis.requestAnimationFrame = (fn) => setTimeout(fn, 0);

// ===== 最小 DOM stub =====
class FakeNode {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    // 模拟 CSSStyleDeclaration：style.display = "none" 等赋值可正常写入
    this.style = { _map: {}, setProperty(k, v) { this._map[k] = v; } };
    this._listeners = new Map();
    this.parentNode = null;
    this.textContent = "";
    this.scrollTop = 0;
    this.nodeType = 1;
  }
  get classList() {
    const self = this;
    return {
      add: (...c) => c.forEach((x) => (self.attributes.class = ((self.attributes.class || "") + " " + x).trim())),
      remove: (...c) => {
        const cur = (self.attributes.class || "").split(/\s+/).filter(Boolean);
        self.attributes.class = cur.filter((x) => !c.includes(x)).join(" ");
      },
      toggle: (c, force) => {
        const cur = (self.attributes.class || "").split(/\s+/).filter(Boolean);
        const has = cur.includes(c);
        const want = force === undefined ? !has : force;
        self.attributes.class = (want ? cur.includes(c) ? cur : [...cur, c] : cur.filter((x) => x !== c)).join(" ");
      },
      contains: (c) => (self.attributes.class || "").split(/\s+/).includes(c),
    };
  }
  get className() { return this.attributes.class || ""; }
  set className(v) { this.attributes.class = v; }
  append(...nodes) {
    for (const n of nodes.flat()) {
      if (n == null) continue;
      let node;
      if (n.nodeType) node = n;
      else { const t = new FakeNode("#text"); t.textContent = String(n); node = t; }
      node.parentNode = this;
      this.children.push(node);
    }
  }
  appendChild(n) { this.append(n); return n; }
  removeChild(n) { const i = this.children.indexOf(n); if (i >= 0) this.children.splice(i, 1); n.parentNode = null; return n; }
  get firstChild() { return this.children[0] || null; }
  get tHead() { return this.children.find((c) => c.tagName === "THEAD") || null; }
  get rows() { return this.children.filter((c) => c.tagName === "TR"); }
  get cells() { return this.children.filter((c) => c.tagName === "TD" || c.tagName === "TH"); }
  addEventListener(type, fn) { (this._listeners.get(type) || this._listeners.set(type, []).get(type)).push(fn); }
  removeEventListener(type, fn) { const a = this._listeners.get(type); if (a) { const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1); } }
  dispatch(type, ev = {}) { (this._listeners.get(type) || []).forEach((fn) => fn({ preventDefault() {}, target: this, ...ev })); }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  contains(n) { return n === this || this.children.includes(n); }
  getBoundingClientRect() { return { width: 100, height: 100, top: 0, left: 0 }; }
}

const documentStub = {
  createElement: (tag) => new FakeNode(tag),
  createTextNode: (t) => Object.assign(new FakeNode("#text"), { textContent: t, nodeType: 3 }),
  body: new FakeNode("body"),
  addEventListener() {}, removeEventListener() {},
};

// ===== window.QTR stub（记录 Bus 事件与 call 调用）=====
const busListeners = new Map();
const Bus = {
  on(e, h) { if (!busListeners.has(e)) busListeners.set(e, []); busListeners.get(e).push(h); },
  off(e, h) { const a = busListeners.get(e); if (a) { const i = a.indexOf(h); if (i >= 0) a.splice(i, 1); } },
  emit(e, p) { (busListeners.get(e) || []).forEach((fn) => fn(p)); },
};
let detailRenderCount = 0; // renderDetail 执行次数（经 detailBody children 清空计数：用 clear 钩子不行，改用 detailBody 引用比较）
// 简化：直接在 detailBody 的 clear 前后计数 —— 用 MutationObserver 不可用，改为记录 detailBody scrollTop setter 与子元素变化次数
const state = { renderDetailCalls: 0, scrollTopAfterRender: [] };

function textInput(value, attrs = {}) {
  const node = new FakeNode("input");
  node.value = value;
  Object.assign(node, attrs);
  return node;
}
function checkbox(label, checked) {
  const input = new FakeNode("input"); input.checked = !!checked;
  const labelNode = new FakeNode("label"); labelNode.textContent = label;
  const box = new FakeNode("label"); box.append(input, labelNode);
  return box;
}
function select(options, value) {
  const node = new FakeNode("select"); node.value = value;
  for (const opt of options) { const o = new FakeNode("option"); o.value = typeof opt === "object" ? opt.value : opt; o.textContent = typeof opt === "object" ? opt.label : opt; node.append(o); }
  return node;
}

window.QTR = {
  Bus,
  call: async (name, cmd, ...args) => {
    if (name === "mitm" && cmd === "get_state") {
      return { ok: true, state: "stopped", web_url: "", config: { flow_record_limit: 500 }, cert: { cert_path: "C:/fake.cer" } };
    }
    if (name === "mitm" && cmd === "refresh_cert_status") return { ok: true, trusted: true };
    if (name === "mitm" && cmd === "list_processes") return { ok: true, processes: [] };
    return { ok: true };
  },
  el: null, // 下面填充（依赖 document stub）
  $: (sel, root = documentStub) => null,
  clear(node) { while (node.firstChild) node.removeChild(node.firstChild); },
  toast() {},
  openModal() {},
  textInput,
  checkbox,
  select,
  copyText() {},
  kvTable() { return new FakeNode("div"); },
  helpTip() { return new FakeNode("span"); },
};

// 用 document stub 填充 el
const elFactory = (tag, attrs = {}, ...children) => {
  const node = documentStub.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "style") { for (const decl of String(v).split(";")) { const [pk, pv] = decl.split(":"); if (pk && pk.trim() && pv) node.style[pk.trim()] = pv.trim(); } }
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2).toLowerCase(), v);
    else node.attributes[k] = v;
  }
  for (const c of children.flat()) { if (c == null) continue; node.append(c); }
  return node;
};
window.QTR.el = elFactory;

// 全局环境补充
globalThis.document = documentStub;
window.document = documentStub;

// 渲染计数钩子：renderDetail 每次执行都会 clear(detailBody)；以 flowTableWrap 结构不可行，
// 改为包装 detailBody 的 scrollTop setter 记录重绘后的滚动位置，
// 并以「详情区子元素被重建」计数 —— 通过监听 clear 调用次数最直接：包装 window.QTR.clear？
// clear 是解构引用，包装无效。改为：每次 renderDetail 后 detailBody 中第一个卡片 title 变化次数不可靠。
// 最终方案：通过 renderFlows/renderDetail 引用是否存在于模块内无法拿到 —— 用 DOM 断言：
// 非选中流量 update 后，detailBody 的「最后重建时间戳」卡片不该变化。
// 简化且可靠的断言：detailBody.scrollTop 在每次 renderDetail 后被还原为 prevScrollTop，
// 以及 detailBody.children 被重建的次数 = renderDetail 调用次数。这里用子元素重建次数计数：
// 给 detailBody 挂一个标记 —— 在选中后记录 children.length 与内容指纹，每次事件后比较。

// ===== 导入页面模块并挂载 =====
const mod = await import("../ui_web/static/js/pages/mitm.js");
const mount = new FakeNode("div");
mod.mitmPage(mount);
await new Promise((r) => setTimeout(r, 10)); // 等 init 的 get_state

// 从 Bus 常驻订阅驱动事件；选中态经点击行设置（模拟用户点击第一行）
function rowClick(rowIndex) {
  // renderFlows 后 flowTbody.children[rowIndex] 即对应行
  const tbody = mount.querySelector ? null : null;
  // 遍历 mount 树找 tbody（FakeNode 无 querySelector，手工递归）
  let found = null;
  (function walk(n) { if (found) return; if (n.tagName === "TBODY") { found = n; return; } for (const c of n.children) walk(c); })(mount);
  assert.ok(found, "flowTbody 存在");
  const tr = found.children[rowIndex];
  assert.ok(tr, `第 ${rowIndex} 行存在`);
  tr.dispatch("click");
}

let flowCounter = 0;
function pushFlow(extra = {}) {
  flowCounter += 1;
  return {
    id: `flow-${flowCounter}`, time: "10:00:0" + flowCounter, time_full: `2026-09-23 10:00:0${flowCounter}`,
    method: "GET", url: `https://example.com/api/${flowCounter}`, path: `/api/${flowCounter}`,
    request_host: "example.com", status_code: 200, response_reason: "OK", duration_ms: 10, size: 100,
    request_headers: "A: b", request_body: "req-body-" + flowCounter, response_headers: "B: c", response_body: "resp-body-" + flowCounter,
    breakpoint_paused: false, breakpoint_matched: false, ...extra,
  };
}

// 内容指纹：递归收集 textContent
function fingerprint(n) { return n.children.length ? n.children.map(fingerprint).join("|") : n.textContent; }

// ---- 场景 1：选中 flow-1（response tab），其他流量 update 不应重绘详情 ----
Bus.emit("mitm_flow_new", { item: pushFlow() });
Bus.emit("mitm_flow_new", { item: pushFlow() });
Bus.emit("mitm_flow_new", { item: pushFlow({ status_code: null }) });
await new Promise((r) => setTimeout(r, 5));
rowClick(0); // 选中 flow-1
await new Promise((r) => setTimeout(r, 5));

// 找到 detailBody（.detail-body class 的 div：详情列内）
let detailBody = null;
(function walk(n) { if (detailBody) return; if (n.className && String(n.className).split(/\s+/).includes("detail-body") && n.tagName === "DIV") { detailBody = n; return; } for (const c of n.children) walk(c); })(mount);
assert.ok(detailBody, "detailBody 存在");
const fpBefore = fingerprint(detailBody);

// 其他流量（flow-2）收到 update：详情不应重建
Bus.emit("mitm_flow_update", { item: pushFlow.call ? { id: "flow-2", time: "10:00:02", method: "GET", path: "/api/2", request_host: "example.com", status_code: 200, duration_ms: 11, size: 101, request_body: "req-body-2", response_body: "resp-body-2-updated" } : null });
await new Promise((r) => setTimeout(r, 5));
const fpAfterOther = fingerprint(detailBody);
assert.strictEqual(fpAfterOther, fpBefore, "场景1: 非选中流量 update 后详情内容不应变化（滚动位置自然保持）");

// ---- 场景 2：在「响应」tab 阅读响应体时，选中流量自身 update（响应到达）：重绘 + 滚动位置保持 ----
// 切到响应 tab（先找到 tab 按钮）
let tabBtns = [];
(function walk(n) { for (const c of n.children) { if (c.tagName === "BUTTON" && ["总览", "请求", "响应"].includes(c.textContent)) tabBtns.push(c); walk(c); } })(mount);
assert.ok(tabBtns.length >= 3, "找到详情 tab 按钮");
const respBtn = tabBtns.find((b) => b.textContent === "响应");
respBtn.dispatch("click"); // 切 tab → detailKey 变化 → 回到顶部（预期行为）
await new Promise((r) => setTimeout(r, 5));
assert.strictEqual(detailBody.scrollTop, 0, "场景2a: 切换标签页后应回到顶部");
detailBody.scrollTop = 1234; // 模拟用户已滚动到响应体中部
Bus.emit("mitm_flow_update", { item: { id: "flow-1", time: "10:00:01", time_full: "2026-09-23 10:00:01", method: "GET", url: "https://example.com/api/1", path: "/api/1", request_host: "example.com", status_code: 200, response_reason: "OK", duration_ms: 12, size: 102, request_headers: "A: b", request_body: "req-body-1", response_headers: "B: c", response_body: "resp-body-1-final", breakpoint_paused: false, breakpoint_matched: false } });
await new Promise((r) => setTimeout(r, 5));
assert.strictEqual(detailBody.scrollTop, 1234, "场景2b: 选中流量自身 update 重绘后滚动位置应还原");
assert.ok(fingerprint(detailBody).includes("resp-body-1-final"), "场景2b: 重绘后应展示更新后的响应内容");

// ---- 场景 3：切换选中行：内容全新，回顶部，展示新流量信息 ----
rowClick(1); // 选中 flow-2
await new Promise((r) => setTimeout(r, 5));
assert.strictEqual(detailBody.scrollTop, 0, "场景3: 切换选中行后应回到顶部");
assert.ok(fingerprint(detailBody).includes("resp-body-2-updated"), "场景3: 切换后应展示新选中流量内容");

console.log("ALL PASS");
console.log(" - 场景1 非选中流量 update：详情内容未变化 ✔");
console.log(" - 场景2a 切换响应 tab：滚动回到顶部 ✔");
console.log(" - 场景2b 选中流量自身 update：内容更新 + 滚动位置还原(1234) ✔");
console.log(" - 场景3 切换选中行：回顶部且展示新流量 ✔");
