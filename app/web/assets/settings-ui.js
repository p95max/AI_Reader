function normalizeTopbarTitle() {
  const topbarTitle = document.querySelector(".topbar > span:first-child");
  if (!topbarTitle) return;

  const pathname = window.location.pathname;
  const title = pathname === "/library"
    ? "Library"
    : pathname === "/upload"
      ? "Add Book"
      : pathname === "/settings"
        ? "Settings"
        : pathname === "/player" || pathname.startsWith("/books/")
          ? "Player"
          : null;

  if (title && topbarTitle.textContent !== title) topbarTitle.textContent = title;
}

function enhanceSettingsPage() {
  normalizeTopbarTitle();

  if (window.location.pathname !== "/settings") return;

  const form = document.querySelector("#preferences-form");
  if (!form || form.dataset.enhanced === "true") return;

  const selects = [...form.querySelectorAll("label.voice-setting > select")];
  if (!selects.length) return;

  const voiceProfiles = {
    alloy: "Balanced · clear",
    ash: "Deep · measured",
    ballad: "Warm · expressive",
    cedar: "Grounded · steady",
    coral: "Bright · friendly",
    echo: "Smooth · neutral",
    fable: "Story-led · warm",
    marin: "Natural · polished",
    nova: "Energetic · clear",
    onyx: "Low · confident",
    sage: "Calm · precise",
    shimmer: "Light · engaging",
    verse: "Dynamic · vivid",
  };

  const syncButtons = (select, group) => {
    group.querySelectorAll("button[data-value]").forEach((button) => {
      const active = button.dataset.value === select.value;
      button.classList.toggle("is-active", active);
      button.setAttribute(select.name === "voice" ? "aria-checked" : "aria-pressed", String(active));
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
    const isVoiceControl = select.name === "voice";
    control.className = `settings-control${isVoiceControl ? " settings-control--voice" : ""}`;

    const label = document.createElement("span");
    label.className = "settings-control__label";
    label.textContent = labelText;
    if (isVoiceControl) {
      const hint = document.createElement("small");
      hint.className = "settings-control__hint";
      hint.textContent = "Choose the narration voice for books you process next.";
      label.append(hint);
    }

    const group = document.createElement("div");
    group.className = `settings-segmented${isVoiceControl ? " settings-voice-grid" : ""}`;
    group.setAttribute("role", isVoiceControl ? "radiogroup" : "group");
    group.setAttribute("aria-label", labelText);
    group.style.setProperty("--settings-options", String(select.options.length));

    [...select.options].forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.value = option.value;
      if (isVoiceControl) {
        button.className = "settings-voice-card";
        button.setAttribute("role", "radio");
        const name = document.createElement("strong");
        name.textContent = option.textContent;
        const profile = document.createElement("span");
        profile.textContent = voiceProfiles[option.value] ?? "OpenAI voice";
        button.append(name, profile);
      } else {
        button.textContent = option.textContent;
      }
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
    const observer = new MutationObserver(syncAll);
    observer.observe(status, { childList: true, subtree: true, characterData: true });
  }

  window.setTimeout(syncAll, 250);
  window.setTimeout(syncAll, 1000);
}

const runEnhancement = () => requestAnimationFrame(enhanceSettingsPage);

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", runEnhancement, { once: true });
} else {
  runEnhancement();
}
