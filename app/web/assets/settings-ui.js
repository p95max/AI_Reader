function enhanceSettingsPage() {
  if (window.location.pathname !== "/settings") return;

  const form = document.querySelector("#preferences-form");
  if (!form || form.dataset.enhanced === "true") return;

  const topbarTitle = document.querySelector(".topbar > span:first-child");
  if (topbarTitle) topbarTitle.textContent = "Settings";

  const selects = [...form.querySelectorAll("label.voice-setting > select")];
  if (!selects.length) return;

  const syncButtons = (select, group) => {
    group.querySelectorAll("button[data-value]").forEach((button) => {
      const active = button.dataset.value === select.value;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  };

  selects.forEach((select) => {
    const originalLabel = select.closest("label.voice-setting");
    if (!originalLabel) return;

    const labelText = [...originalLabel.childNodes]
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent.trim())
      .filter(Boolean)
      .join(" ");

    const control = document.createElement("div");
    control.className = "settings-control";

    const label = document.createElement("span");
    label.className = "settings-control__label";
    label.textContent = labelText;

    const group = document.createElement("div");
    group.className = "settings-segmented";
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", labelText);
    group.style.setProperty("--settings-options", String(select.options.length));

    [...select.options].forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.value = option.value;
      button.textContent = option.textContent;
      button.addEventListener("click", () => {
        select.value = option.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        syncButtons(select, group);
      });
      group.appendChild(button);
    });

    select.classList.add("settings-native-select");
    control.append(label, group, select);
    originalLabel.replaceWith(control);

    select.addEventListener("change", () => syncButtons(select, group));
    syncButtons(select, group);
  });

  form.dataset.enhanced = "true";

  const syncAll = () => {
    form.querySelectorAll(".settings-control").forEach((control) => {
      const select = control.querySelector("select");
      const group = control.querySelector(".settings-segmented");
      if (select && group) syncButtons(select, group);
    });
  };

  const status = form.querySelector("#preferences-status");
  if (status) {
    const observer = new MutationObserver(() => syncAll());
    observer.observe(status, { childList: true, subtree: true, characterData: true });
  }

  window.setTimeout(syncAll, 250);
  window.setTimeout(syncAll, 1000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => requestAnimationFrame(enhanceSettingsPage), { once: true });
} else {
  requestAnimationFrame(enhanceSettingsPage);
}

const appRoot = document.querySelector("#app");
if (appRoot) {
  const observer = new MutationObserver(() => enhanceSettingsPage());
  observer.observe(appRoot, { childList: true, subtree: true });
}
