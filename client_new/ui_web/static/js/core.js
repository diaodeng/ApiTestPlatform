/**
 * 前端公共工具层（非模块脚本，挂 window.QTR）。
 * - call(name, ...args)：包装 pywebview.api 调用为 Promise，统一错误提示；
 * - Bus：前端事件订阅（配合 index.html 里的 __qtrDispatch 入口）；
 * - Modal/Toast/表单小工具：供各页面复用。
 */
(function () {
  const listeners = new Map();

  /** 前端事件总线：订阅后端推送的事件（与后端事件名一致）。 */
  const Bus = {
    on(event, handler) {
      if (!listeners.has(event)) listeners.set(event, []);
      listeners.get(event).push(handler);
    },
    off(event, handler) {
      const arr = listeners.get(event);
      if (arr) {
        const i = arr.indexOf(handler);
        if (i >= 0) arr.splice(i, 1);
      }
    },
    emit(event, payload) {
      (listeners.get(event) || []).forEach((fn) => {
        try {
          fn(payload);
        } catch (e) {
          console.error("事件处理异常", event, e);
        }
      });
    },
  };

  // 消费早于模块加载到达的事件队列
  window.__qtrHandler = (name, payload) => Bus.emit(name, payload);

  /**
   * 调用后端 Bridge 方法。
   * 支持两种形式（自动识别）：
   * - call("app", "get_global_status")     → pywebview.api.app.get_global_status()
   * - call("resolve_dialog", req, value)   → pywebview.api.resolve_dialog()（顶层透传方法）
   */
  function rawCall(...pathAndArgs) {
    const api = window.pywebview.api;
    let path = [pathAndArgs[0]];
    let args = pathAndArgs.slice(1);
    if (typeof api[pathAndArgs[0]] !== "function" && pathAndArgs.length >= 2) {
      path = [pathAndArgs[0], pathAndArgs[1]];
      args = pathAndArgs.slice(2);
    }
    let target = api;
    for (const seg of path) target = target && target[seg];
    if (typeof target !== "function") {
      return Promise.reject(new Error("后端接口不存在: " + path.join(".")));
    }
    return target(...args);
  }

  function call(name, ...args) {
    return rawCall(name, ...args).then((res) => {
      if (res && res.ok === false) {
        console.warn(`[api] ${name} 失败:`, res.message || res);
      }
      return res;
    });
  }

  function waitForApi(timeout = 15000) {
    const started = Date.now();
    return new Promise((resolve, reject) => {
      (function check() {
        if (window.pywebview && window.pywebview.api) return resolve();
        if (Date.now() - started > timeout) return reject(new Error("pywebview api 加载超时"));
        setTimeout(check, 80);
      })();
    });
  }

  // ===== DOM 小工具 =====
  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === undefined || value === null) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key === "html") node.innerHTML = value;
      else if (key === "dataset") Object.assign(node.dataset, value);
      else if (key.startsWith("on") && typeof value === "function") {
        node.addEventListener(key.slice(2).toLowerCase(), value);
      } else if (key === "value") node.value = value;
      else if (key === "checked") node.checked = !!value;
      else if (key === "disabled") node.disabled = !!value;
      else node.setAttribute(key, value);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined) continue;
      node.append(child.nodeType ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  // ===== Toast =====
  function toast(message, level = "info", duration = 3200) {
    const root = $("#toast-root");
    const item = el("div", { class: `toast ${level}`, text: message });
    root.append(item);
    setTimeout(() => item.remove(), duration);
  }

  // ===== 模态框 =====
  /**
   * 打开模态框。
   * @param {object} opts {title, body(HTMLElement), footer(HTMLElement|btn[]), wide, onClose}
   * @returns {{close:Function, body:HTMLElement}}
   */
  function openModal({ title, body, footer, wide = false, onClose }) {
    const root = $("#modal-root");
    const closeBtn = el("button", { class: "btn small modal-close", text: "关闭", onclick: () => close() });
    const bodyNode = el("div", { class: "modal-body" }, body);
    const footNode = footer ? el("div", { class: "modal-foot" }, footer) : null;
    const modal = el(
      "div",
      { class: `modal${wide ? " wide" : ""}` },
      el("div", { class: "modal-head" }, el("span", { text: title }), closeBtn),
      bodyNode,
      footNode
    );
    const overlay = el("div", { class: "modal-overlay" }, modal);
    function close() {
      overlay.remove();
      if (onClose) onClose();
    }
    overlay.addEventListener("mousedown", (e) => {
      if (e.target === overlay) close();
    });
    root.append(overlay);
    return { close, body: bodyNode };
  }

  /** 后端发起的确认框（ui_dialog 事件）使用，返回 Promise。 */
  function backendDialog(payload) {
    return new Promise((resolve) => {
      const finish = (value) => {
        call("resolve_dialog", payload.req_id, value);
        resolve(value);
        modal.close();
      };
      let foot;
      if (payload.kind === "choice") {
        // 三选项：取消=0 / 确定=1 / 切换后启动=2（语义与原 Qt DialogUtil 一致）
        foot = [
          el("button", { class: "btn", text: "取消", onclick: () => finish(0) }),
          el("button", { class: "btn", text: "确定", onclick: () => finish(1) }),
          el("button", { class: "btn primary", text: "切换后启动", onclick: () => finish(2) }),
        ];
      } else {
        foot = [
          el("button", { class: "btn", text: "取消", onclick: () => finish(false) }),
          el("button", { class: "btn primary", text: "确定", onclick: () => finish(true) }),
        ];
      }
      const modal = openModal({
        title: payload.title || "提示",
        body: el("div", { text: payload.message || "" }),
        footer: foot,
        onClose: () => {
          call("resolve_dialog", payload.req_id, payload.kind === "choice" ? 0 : false);
          resolve(payload.kind === "choice" ? 0 : false);
        },
      });
    });
  }

  // ===== 表单字段构造 =====
  function fieldRow(labelText, control, labelText2) {
    return el("div", { class: "form-row" }, el("label", { text: labelText }), control,
      labelText2 ? el("label", { text: labelText2 }) : null);
  }

  function textInput(value = "", attrs = {}) {
    return el("input", { class: "input", value, ...attrs });
  }

  function checkbox(labelText, checked, onChange) {
    const box = el("input", { type: "checkbox", checked, onchange: onChange });
    return el("label", { class: "checkbox" }, box, el("span", { text: labelText }), box);
  }

  function select(options, value, onChange, attrs = {}) {
    const sel = el("select", { class: "select", onchange: onChange, ...attrs });
    for (const opt of options) {
      const item = el("option", { value: opt.value, text: opt.label });
      sel.append(item);
    }
    if (value !== undefined && value !== null) sel.value = value;
    return sel;
  }

  /** 简单列表编辑器：每行一个输入框 + 删除按钮，返回 {node, getValue} */
  function listEditor(values, placeholder = "") {
    const container = el("div", {});
    function addRow(value = "") {
      const input = textInput(value, { placeholder, style: "flex:1" });
      const row = el(
        "div",
        { class: "form-row", style: "margin-bottom:4px" },
        input,
        el("button", {
          class: "btn small danger",
          text: "删除",
          onclick: () => row.remove(),
        })
      );
      container.append(row);
    }
    (values || []).forEach(addRow);
    return {
      node: container,
      add: addRow,
      getValue: () => $$(".input", container).map((i) => i.value.trim()).filter(Boolean),
    };
  }

  /** 通用键值表渲染 */
  function kvTable(entries) {
    const table = el("table", { class: "data kv-table" });
    const tbody = el("tbody", {});
    for (const [k, v] of entries) {
      tbody.append(el("tr", {}, el("td", { text: k }), el("td", { text: v === null || v === undefined ? "-" : String(v) })));
    }
    table.append(tbody);
    return table;
  }

  function copyText(text) {
    navigator.clipboard.writeText(text || "").then(
      () => toast("已复制", "success", 1200),
      () => toast("复制失败", "error")
    );
  }

  window.QTR = {
    Bus, call, rawCall, waitForApi, el, $, $$, clear, toast, openModal,
    backendDialog, fieldRow, textInput, checkbox, select, listEditor,
    kvTable, copyText,
  };
})();
