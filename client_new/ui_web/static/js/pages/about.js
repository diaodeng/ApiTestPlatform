/** 关于页面：版本信息、检查更新、执行更新。 */
const { Bus, call, el, toast, textInput, checkbox } = window.QTR;

export function aboutPage(mount) {
  const versionTip = el("span", { class: "muted", text: "当前版本: -" });
  const checkBtn = el("button", { class: "btn", text: "检查更新" });
  const updateBtn = el("button", { class: "btn primary", text: "更新" });
  const forceCheck = checkbox("强制更新", false);
  const progressLabel = el("span", { class: "muted", text: "-" });
  const infoPre = el("pre", { class: "panel flex-fill", text: "点击“检查更新”查看版本说明" });
  const tips = el("div", {
    class: "hint", style: "color:var(--danger);font-weight:600",
    text: "更新过程中不要离开当前页面。支持单文件 exe、portable zip 和连续分片文件更新，分片建议使用 .001、.002 这类命名。",
  });

  mount.append(
    el("div", { class: "toolbar" },
      el("span", { text: "QTRClient 客户端", style: "font-weight:600;font-size:15px" }),
      versionTip, checkBtn, updateBtn, forceCheck,
      el("label", { text: "下载进度" }), progressLabel),
    tips,
    infoPre
  );

  checkBtn.addEventListener("click", async () => {
    checkBtn.disabled = true;
    versionTip.textContent = "正在检查更新...";
    const res = await call("about", "check_update");
    checkBtn.disabled = false;
    versionTip.textContent = res.message || "检查失败";
    if (res.info) infoPre.textContent = res.info;
  });

  updateBtn.addEventListener("click", async () => {
    updateBtn.disabled = true;
    checkBtn.disabled = true;
    progressLabel.textContent = "准备更新...";
    const res = await call("about", "perform_update", forceCheck.querySelector("input").checked);
    if (!res.ok) {
      toast(res.message, "error");
      updateBtn.disabled = false;
      checkBtn.disabled = false;
      progressLabel.textContent = res.message;
    }
  });

  const offProgress = (() => {
    const onProgress = (p) => (progressLabel.textContent = p.text || "");
    const onDone = (p) => {
      progressLabel.textContent = p.message || "";
      toast(p.message || (p.ok ? "更新完成" : "更新失败"), p.ok ? "success" : "error");
      updateBtn.disabled = false;
      checkBtn.disabled = false;
      if (p.ok) call("quit_app");
    };
    Bus.on("update_progress", onProgress);
    Bus.on("update_done", onDone);
    return () => {
      Bus.off("update_progress", onProgress);
      Bus.off("update_done", onDone);
    };
  })();

  (async function init() {
    const res = await call("about", "get_info");
    if (res.ok) {
      versionTip.textContent = `当前版本: ${res.version}`;
      if (res.build_label) versionTip.textContent += `（${res.build_label}）`;
      tips.textContent += ` 当前运行形态：${res.package_mode_label}，升级资源策略：${res.preferred_asset_label}。`;
    }
  })();

  const observer = new MutationObserver(() => {
    if (!document.body.contains(mount)) {
      offProgress();
      observer.disconnect();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  return { destroy: offProgress };
}
