const pages = {
  "/library": {
    title: "Library",
  },
  "/upload": {
    title: "Add Book",
  },
  "/player": {
    title: "Player",
  },
  "/settings": {
    title: "Settings",
  },
};

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  })[character]);
}

function currentPage(pathname) {
  if (pathname.startsWith("/books/")) {
    return {
      title: "Book and player",
    };
  }
  return pages[pathname] ?? pages["/library"];
}

function navigation() {
  return [
    ["/library", "library", "Library"],
    ["/upload", "upload", "Add Book"],
    ["/player", "player", "Player"],
    ["/settings", "settings", "Settings"],
  ]
    .map((path) => {
      const [href, iconName, label] = path;
      const isPlayerPage = href === "/player" && window.location.pathname.startsWith("/books/");
      const active = href === window.location.pathname || isPlayerPage ? ' aria-current="page"' : "";
      return `<a href="${href}"${active}>${navigationIcon(iconName)}${label}</a>`;
    })
    .join("");
}

function navigationIcon(name) {
  const paths = {
    library: '<path d="M4 5h16v15H4zM8 5v15M11 9h5M11 13h5"/>',
    upload: '<path d="M12 15V3m0 0L7 8m5-5 5 5M5 16v4h14v-4"/>',
    player: '<path d="M5 4h14v16H5zM10 9l5 3-5 3z"/>',
    settings: '<path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Zm0-12.2v2m0 14v2m9-9h-2M5 12H3m15.4-6.4-1.4 1.4M7 17l-1.4 1.4m12.8 0L17 17M7 7 5.6 5.6"/>',
  };
  return `<svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[name]}</svg>`;
}

function shell(content) {
  return `
    <div class="app-frame">
      <aside class="sidebar">
        <a class="brand" href="/library" aria-label="AI Reader"><span>AI</span>READER<small>TURN PDFS INTO KNOWLEDGE.</small></a>
        <nav class="navigation" aria-label="Primary navigation">${navigation()}</nav>
        <div class="sidebar-links"><a href="/library">▥ Stats</a><a href="/library">? Help</a><a href="/library">◉ GitHub</a></div>
        <p class="sidebar-quote">“READ.<br>LISTEN.<br>LEARN ANYWHERE.”</p>
        <small class="version">v0.1.0</small>
      </aside>
      <main class="app-shell"><div id="background-status" role="status" aria-live="polite" hidden></div>${content}</main>
      <nav class="mobile-navigation" aria-label="Mobile navigation">${navigation()}</nav>
    </div>
`;
}

function statusLabel(status) {
  return {
    uploaded: "Uploaded",
    queued: "Queued",
    processing: "Processing",
    ready: "Ready",
    failed: "Failed",
  }[status] ?? status;
}

function coverVariant(title) {
  return [...title].reduce((sum, letter) => sum + letter.codePointAt(0), 0) % 6;
}

function renderBookCard(book) {
  const title = escapeHtml(book.title);
  const author = escapeHtml(book.author);
  const initial = title.slice(0, 1).toUpperCase() || "A";
  const progress = Math.max(0, Math.min(100, Number(book.progress_percent) || 0));
  return `
    <a class="book-card" href="/books/${encodeURIComponent(book.id)}">
      <span class="book-cover book-cover--${coverVariant(book.title)}" aria-hidden="true"><b>${initial}</b><i></i></span>
      <span class="book-card__body">
        <span class="book-card__status status--${escapeHtml(book.status)}">${statusLabel(book.status)}</span>
        <strong>${title}</strong><span class="book-card__author">${author}</span>
        <span class="progress" aria-label="${progress}% complete"><span style="width: ${progress}%"></span></span>
        <span class="book-card__meta">◖ ${progress}% complete <b>•••</b></span>
      </span>
    </a>
  `;
}

async function renderLibrary() {
  const app = document.querySelector("#app");
  app.innerHTML = shell(`
    <header class="topbar"><span>Web / Desktop (Library)</span><span>◉ USER⌄</span></header>
    <header class="library-header">
      <div><h1>LIBRARY</h1><p>Your books, always with you.</p></div>
      <div class="library-actions"><label class="search"><span>⌕</span><input id="library-search" type="search" placeholder="Search books..." /></label><a class="button" href="/upload">＋ ADD BOOK</a></div>
    </header>
    <div class="filters" role="group" aria-label="Book filter">
      <button type="button" data-filter="all" class="is-active">All</button>
      <button type="button" data-filter="processing">Processing</button>
      <button type="button" data-filter="ready">Ready</button>
      <button type="button" disabled>Favorites</button>
    </div>
    <section id="book-list" class="book-list"><p class="placeholder">Loading library…</p></section>
  `);

  let books = [];
  let activeFilter = "all";
  const list = document.querySelector("#book-list");
  const search = document.querySelector("#library-search");
  const draw = () => {
    const term = search.value.trim().toLocaleLowerCase();
    const visible = books.filter((book) => (
      (activeFilter === "all" || book.status === activeFilter)
      && `${book.title} ${book.author}`.toLocaleLowerCase().includes(term)
    ));
    list.innerHTML = visible.length
      ? visible.map(renderBookCard).join("")
      : '<a class="empty-library" href="/upload"><b>＋</b><span>Add your first book</span><small>PDF → audiobook</small></a>';
  };
  search.addEventListener("input", draw);
  window.addEventListener("books-updated", (event) => { books = event.detail; draw(); });
  document.querySelectorAll("[data-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      activeFilter = button.dataset.filter;
      document.querySelectorAll("[data-filter]").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      draw();
    });
  });
  try {
    const response = await fetch("/api/v1/books");
    if (!response.ok) throw new Error("Unable to load books");
    books = await response.json();
    draw();
  } catch (error) {
    list.innerHTML = '<p class="placeholder">Unable to load the library. Please try again later.</p>';
  }
}

async function renderUpload() {
  document.querySelector("#app").innerHTML = shell(`
    <header class="topbar"><span>Web / Desktop (Add Book)</span><span>◉ USER⌄</span></header>
    <form id="upload-form" class="feature-page add-book-page">
      <a class="back-link" href="/library">← Library</a><h1>ADD BOOK</h1><p>Turn your technical PDF into an audiobook.</p>
      <label class="drop-zone" id="drop-zone"><b>⇧</b><strong>Drag & drop your PDF here</strong><span>or tap to select a file</span><small>Max 200 MB · PDF only</small><input id="pdf-file" type="file" accept="application/pdf" hidden></label>
      <p id="selected-file" class="selected-file" aria-live="polite">No file selected</p>
      <div class="mode-panel"><span>Code mode</span><div class="mode-buttons mode-buttons--four" id="mode-buttons"><button type="button" data-mode="explain">Explain</button><button type="button" data-mode="read">Read</button><button type="button" data-mode="skip">Skip</button><button type="button" class="is-active" data-mode="hybrid">Hybrid</button></div><span class="reading-style-label">Table mode</span><div class="mode-buttons" id="table-mode-buttons"><button type="button" class="is-active" data-mode="summarize">Summarize</button><button type="button" data-mode="read_all">Read all</button><button type="button" data-mode="skip">Skip</button></div><span class="reading-style-label">Diagram mode</span><div class="mode-buttons mode-buttons--two" id="diagram-mode-buttons"><button type="button" class="is-active" data-mode="describe">Describe</button><button type="button" data-mode="skip">Skip</button></div><span class="reading-style-label">Formula mode</span><div class="mode-buttons" id="formula-mode-buttons"><button type="button" class="is-active" data-mode="explain">Explain</button><button type="button" data-mode="read">Read</button><button type="button" data-mode="skip">Skip</button></div><label class="voice-setting">Voice<select id="voice-setting" aria-label="Voice"><option value="Ryan">Ryan</option><option value="Aiden">Aiden</option><option value="Vivian">Vivian</option></select></label><label class="voice-setting">Speech speed<select id="speed-setting" aria-label="Speech speed"><option value="normal">Normal</option><option value="slow">Slow</option></select></label><span class="reading-style-label">Reading style</span><div class="mode-buttons" id="style-buttons"><button type="button" data-style="calm">Calm</button><button type="button" class="is-active" data-style="neutral">Neutral</button><button type="button" data-style="expressive">Expressive</button></div></div>
      <div class="estimate"><span>Est. tokens<br><b id="estimate-tokens">—</b></span><span>Est. AI cost<br><b id="estimate-cost">—</b></span><span>Est. audio<br><b id="estimate-audio">—</b></span></div>
      <p class="estimate-note">Estimate is based on file size and is refined after PDF extraction.</p><p id="upload-status" class="upload-status" aria-live="polite"></p>
      <button id="start-processing" class="button button--wide" type="submit" disabled>START PROCESSING</button>
    </form>
  `);

  const form = document.querySelector("#upload-form");
  const fileInput = document.querySelector("#pdf-file");
  const dropZone = document.querySelector("#drop-zone");
  const selectedFile = document.querySelector("#selected-file");
  const startButton = document.querySelector("#start-processing");
  const statusMessage = document.querySelector("#upload-status");
  const voiceSetting = document.querySelector("#voice-setting");
  const speedSetting = document.querySelector("#speed-setting");
  let file = null;
  let readingStyle = "neutral";
  let codeMode = "hybrid";
  let tableMode = "summarize";
  let diagramMode = "describe";
  let formulaMode = "explain";

  const formatBytes = (bytes) => {
    if (bytes < 1_024) return `${bytes} B`;
    if (bytes < 1_048_576) return `${(bytes / 1_024).toFixed(1)} KB`;
    return `${(bytes / 1_048_576).toFixed(1)} MB`;
  };
  const formatAudioDuration = (seconds) => {
    const hours = Math.floor(seconds / 3_600);
    const minutes = Math.round((seconds % 3_600) / 60);
    return hours ? `~ ${hours}h ${minutes}m` : `~ ${minutes}m`;
  };
  const loadEstimate = async (selected) => {
    const response = await fetch(`/api/v1/books/estimate?file_size_bytes=${selected.size}`);
    if (!response.ok) throw new Error("Unable to calculate estimate");
    const estimate = await response.json();
    document.querySelector("#estimate-tokens").textContent = `~ ${estimate.estimated_total_tokens.toLocaleString("en-US")}`;
    document.querySelector("#estimate-cost").textContent = `~ $${estimate.estimated_ai_cost_usd.toFixed(2)}`;
    document.querySelector("#estimate-audio").textContent = formatAudioDuration(estimate.estimated_audio_seconds);
  };
  const selectFile = async (selected) => {
    if (!selected) return;
    if (selected.type !== "application/pdf" && !selected.name.toLowerCase().endsWith(".pdf")) {
      statusMessage.textContent = "Please choose a PDF file.";
      return;
    }
    file = selected;
    selectedFile.textContent = `${selected.name} · ${formatBytes(selected.size)}`;
    statusMessage.textContent = "";
    startButton.disabled = false;
    try {
      await loadEstimate(selected);
    } catch (error) {
      statusMessage.textContent = "Estimate is unavailable, but you can still start processing.";
    }
  };
  fileInput.addEventListener("change", () => selectFile(fileInput.files[0]));
  dropZone.addEventListener("dragover", (event) => { event.preventDefault(); dropZone.classList.add("is-dragging"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("is-dragging"));
  dropZone.addEventListener("drop", (event) => { event.preventDefault(); dropZone.classList.remove("is-dragging"); selectFile(event.dataTransfer.files[0]); });
  document.querySelectorAll("#mode-buttons button").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll("#mode-buttons button").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    codeMode = button.dataset.mode;
  }));
  const bindModeButtons = (selector, selectMode) => document.querySelectorAll(`${selector} button`).forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll(`${selector} button`).forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    selectMode(button.dataset.mode);
  }));
  bindModeButtons("#table-mode-buttons", (mode) => { tableMode = mode; });
  bindModeButtons("#diagram-mode-buttons", (mode) => { diagramMode = mode; });
  bindModeButtons("#formula-mode-buttons", (mode) => { formulaMode = mode; });
  document.querySelectorAll("#style-buttons button").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll("#style-buttons button").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    readingStyle = button.dataset.style;
  }));
  const selectMode = (selector, mode, applyMode) => {
    const button = [...document.querySelectorAll(`${selector} button`)].find((item) => item.dataset.mode === mode);
    if (!button) return;
    document.querySelectorAll(`${selector} button`).forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    applyMode(mode);
  };
  const selectStyle = (style) => {
    const button = [...document.querySelectorAll("#style-buttons button")].find((item) => item.dataset.style === style);
    if (!button) return;
    document.querySelectorAll("#style-buttons button").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    readingStyle = style;
  };
  try {
    const response = await fetch("/api/v1/settings/preferences");
    if (!response.ok) throw new Error("Unable to load preferences");
    const preferences = await response.json();
    voiceSetting.value = preferences.voice;
    speedSetting.value = preferences.speed;
    selectStyle(preferences.style);
    selectMode("#mode-buttons", preferences.code_mode, (mode) => { codeMode = mode; });
    selectMode("#table-mode-buttons", preferences.table_mode, (mode) => { tableMode = mode; });
    selectMode("#diagram-mode-buttons", preferences.diagram_mode, (mode) => { diagramMode = mode; });
    selectMode("#formula-mode-buttons", preferences.formula_mode, (mode) => { formulaMode = mode; });
  } catch (error) {
    statusMessage.textContent = "Saved preferences could not be loaded; using defaults.";
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!file) return;
    startButton.disabled = true;
    statusMessage.textContent = "Uploading PDF…";
    try {
      const data = new FormData();
      data.append("file", file);
      const upload = await fetch("/api/v1/books", { method: "POST", body: data });
      if (!upload.ok) throw new Error(await upload.text());
      const book = await upload.json();
      statusMessage.textContent = "Starting processing…";
      const processing = await fetch(`/api/v1/books/${book.id}/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice: voiceSetting.value, speed: speedSetting.value, style: readingStyle, code_mode: codeMode, table_mode: tableMode, diagram_mode: diagramMode, formula_mode: formulaMode }),
      });
      if (!processing.ok) throw new Error(await processing.text());
      window.location.assign(`/books/${book.id}`);
    } catch (error) {
      startButton.disabled = false;
      statusMessage.textContent = "Upload failed. Please try again.";
    }
  });
}

async function renderSettings() {
  document.querySelector("#app").innerHTML = shell(`
    <header class="topbar"><span>Web / Desktop (Settings)</span><span>◉ USER⌄</span></header>
    <form id="preferences-form" class="feature-page settings-page"><a class="back-link" href="/library">← Library</a><h1>SETTINGS</h1><p>Choose defaults for books you process next.</p>
      <label class="voice-setting">Voice<select name="voice"><option value="Ryan">Ryan</option><option value="Aiden">Aiden</option><option value="Vivian">Vivian</option></select></label>
      <label class="voice-setting">Speech speed<select name="speed"><option value="normal">Normal</option><option value="slow">Slow</option></select></label>
      <label class="voice-setting">Reading style<select name="style"><option value="calm">Calm</option><option value="neutral">Neutral</option><option value="expressive">Expressive</option></select></label>
      <label class="voice-setting">Code mode<select name="code_mode"><option value="explain">Explain</option><option value="read">Read</option><option value="skip">Skip</option><option value="hybrid">Hybrid</option></select></label>
      <label class="voice-setting">Table mode<select name="table_mode"><option value="summarize">Summarize</option><option value="read_all">Read all</option><option value="skip">Skip</option></select></label>
      <label class="voice-setting">Diagram mode<select name="diagram_mode"><option value="describe">Describe</option><option value="skip">Skip</option></select></label>
      <label class="voice-setting">Formula mode<select name="formula_mode"><option value="explain">Explain</option><option value="read">Read</option><option value="skip">Skip</option></select></label>
      <p id="preferences-status" class="upload-status" aria-live="polite">Loading saved preferences…</p><button class="button button--wide" type="submit">SAVE SETTINGS</button>
    </form>
  `);

  const form = document.querySelector("#preferences-form");
  const statusMessage = document.querySelector("#preferences-status");
  try {
    const response = await fetch("/api/v1/settings/preferences");
    if (!response.ok) throw new Error("Unable to load preferences");
    const preferences = await response.json();
    Object.entries(preferences).forEach(([name, value]) => {
      const control = form.elements.namedItem(name);
      if (control && typeof value === "string") control.value = value;
    });
    statusMessage.textContent = "Settings are applied to each book when processing starts.";
  } catch (error) {
    statusMessage.textContent = "Unable to load saved settings.";
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    statusMessage.textContent = "Saving settings…";
    const payload = Object.fromEntries(new FormData(form).entries());
    try {
      const response = await fetch("/api/v1/settings/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await response.text());
      statusMessage.textContent = "Settings saved. They will be used for your next book.";
    } catch (error) {
      statusMessage.textContent = "Unable to save settings. Please try again.";
    }
  });
}

function formatPlaybackTime(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  const hours = Math.floor(value / 3_600);
  const minutes = Math.floor((value % 3_600) / 60);
  const remainingSeconds = value % 60;
  return hours
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`
    : `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

async function renderBookPage() {
  document.querySelector("#app").innerHTML = shell(`
    <header class="topbar"><span>Web / Desktop (Player)</span><span>◉ USER⌄</span></header>
    <section class="feature-page player-page"><a class="back-link" href="/library">← Library</a><div class="player-heading"><span id="player-cover" class="book-cover book-cover--2"><b>A</b><i></i></span><div><h1 id="player-title">LOADING BOOK</h1><p id="player-author">Technical audiobook</p><span id="player-status" class="book-card__meta">Loading audio segments…</span></div></div>
    <section class="player-panel" aria-label="Audiobook player"><p id="chunk-label" class="chunk-label">No audio segment selected</p><audio id="book-audio" preload="metadata"></audio><label class="seek-label" for="player-seek"><span id="current-time">0:00</span><input id="player-seek" type="range" min="0" max="0" value="0" step="0.1" disabled><span id="total-time">0:00</span></label><div class="player-controls"><button type="button" data-skip="-15" aria-label="Rewind 15 seconds" disabled>↺15</button><button type="button" id="previous-chunk" aria-label="Previous audio segment" disabled>◀◀</button><button type="button" id="play-pause" class="play" aria-label="Play" disabled>▶</button><button type="button" id="next-chunk" aria-label="Next audio segment" disabled>▶▶</button><button type="button" data-skip="15" aria-label="Skip 15 seconds" disabled>15↻</button></div><label class="speed-setting" for="playback-speed">Playback speed<select id="playback-speed" disabled><option value="0.75">0.75×</option><option value="1" selected>1×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option><option value="2">2×</option></select></label></section>
    <details class="usage-panel" id="usage-panel" open><summary><span><h2>USAGE &amp; COST</h2><small>Live processing totals</small></span><b aria-hidden="true">⌄</b></summary><div class="usage-grid"><article class="usage-card"><span>AI TOKENS</span><b id="usage-tokens">—</b><small id="usage-token-detail">Input / output</small></article><article class="usage-card"><span>AI COST</span><b id="usage-ai-cost">—</b><small id="usage-ai-requests">LLM requests</small></article><article class="usage-card"><span>GENERATED AUDIO</span><b id="usage-audio-duration">—</b><small id="usage-generation-time">Generation time</small></article><article class="usage-card"><span>TTS COST</span><b id="usage-tts-cost">—</b><small>Generated audio and GPU</small></article><article class="usage-card usage-card--total"><span>TOTAL COST</span><b id="usage-total-cost">—</b><small>AI adaptation + TTS</small></article></div><p id="usage-note">Loading usage data…</p></details>
    <section class="chapter-navigation" aria-labelledby="chapters-heading"><div class="chapter-navigation__title"><div><h2 id="chapters-heading">CHAPTERS</h2><p id="chapter-summary">Loading book structure…</p></div><div class="chapter-navigation__controls"><button type="button" id="previous-chapter" aria-label="Previous chapter" disabled>←</button><button type="button" id="next-chapter" aria-label="Next chapter" disabled>→</button></div></div><ol id="chapter-list" class="chapter-list" aria-live="polite"></ol><p id="next-available-chunk" class="next-available-chunk">Checking the next available chunk…</p></section>
    </section>
  `);

  const bookId = window.location.pathname.split("/").at(-1);
  window.localStorage.setItem("ai-reader:last-book-id", bookId);
  const title = document.querySelector("#player-title");
  const author = document.querySelector("#player-author");
  const cover = document.querySelector("#player-cover");
  const statusMessage = document.querySelector("#player-status");
  const chunkLabel = document.querySelector("#chunk-label");
  const audio = document.querySelector("#book-audio");
  const seek = document.querySelector("#player-seek");
  const currentTime = document.querySelector("#current-time");
  const totalTime = document.querySelector("#total-time");
  const playPause = document.querySelector("#play-pause");
  const previous = document.querySelector("#previous-chunk");
  const next = document.querySelector("#next-chunk");
  const speed = document.querySelector("#playback-speed");
  const skipButtons = [...document.querySelectorAll("[data-skip]")];
  const chapterSummary = document.querySelector("#chapter-summary");
  const chapterList = document.querySelector("#chapter-list");
  const previousChapter = document.querySelector("#previous-chapter");
  const nextChapter = document.querySelector("#next-chapter");
  const nextAvailableChunk = document.querySelector("#next-available-chunk");
  const usagePanel = document.querySelector("#usage-panel");
  const usageTokens = document.querySelector("#usage-tokens");
  const usageTokenDetail = document.querySelector("#usage-token-detail");
  const usageAiCost = document.querySelector("#usage-ai-cost");
  const usageAiRequests = document.querySelector("#usage-ai-requests");
  const usageAudioDuration = document.querySelector("#usage-audio-duration");
  const usageGenerationTime = document.querySelector("#usage-generation-time");
  const usageTtsCost = document.querySelector("#usage-tts-cost");
  const usageTotalCost = document.querySelector("#usage-total-cost");
  const usageNote = document.querySelector("#usage-note");
  let chunks = [];
  let currentChunk = 0;
  let chapters = [];
  let selectedChapter = Math.max(0, Number(new URLSearchParams(window.location.search).get("chapter")) || 0);
  let pendingSeekSeconds = null;
  let lastPersistedAt = 0;
  let audioRetryAttempts = 0;
  let backgroundRefreshTimer = null;

  if (window.matchMedia("(max-width: 850px)").matches) usagePanel.open = false;

  const formatDuration = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return minutes ? `${minutes}m ${String(remainingSeconds).padStart(2, "0")}s` : `${remainingSeconds}s`;
  };
  const loadUsage = async () => {
    try {
      const response = await fetch(`/api/v1/books/${encodeURIComponent(bookId)}/usage`);
      if (!response.ok) throw new Error("Unable to load processing usage");
      const usage = await response.json();
      const formatCost = (value) => `$${Number(value).toFixed(4)}`;
      const tokenTotal = Number(usage.actual_input_tokens) + Number(usage.actual_output_tokens);
      usageTokens.textContent = tokenTotal.toLocaleString("en-US");
      usageTokenDetail.textContent = `${Number(usage.actual_input_tokens).toLocaleString("en-US")} input · ${Number(usage.actual_output_tokens).toLocaleString("en-US")} output · ${Number(usage.actual_cached_input_tokens).toLocaleString("en-US")} cached`;
      usageAiCost.textContent = formatCost(usage.actual_cost_usd);
      usageAiRequests.textContent = `${usage.request_count} LLM request${usage.request_count === 1 ? "" : "s"}`;
      usageAudioDuration.textContent = formatDuration(Number(usage.generated_audio_seconds));
      usageGenerationTime.textContent = `${formatDuration(Number(usage.tts_generation_seconds))} generation`;
      usageTtsCost.textContent = formatCost(usage.actual_tts_cost_usd);
      usageTotalCost.textContent = formatCost(usage.total_processing_cost_usd);
      const difference = Number(usage.difference_usd);
      usageNote.textContent = `AI estimate ${formatCost(usage.estimated_cost_usd)} · AI variance ${difference >= 0 ? "+" : "−"}${formatCost(Math.abs(difference))} · ${usage.estimate_model_name || "Current model"} · price list ${usage.estimate_pricing_version}`;
    } catch (error) {
      usageNote.textContent = "Usage data is not available yet.";
    }
  };

  const setControlsEnabled = (enabled) => {
    [playPause, previous, next, speed, ...skipButtons].forEach((control) => { control.disabled = !enabled; });
    seek.disabled = !enabled;
  };
  const duration = () => Number.isFinite(audio.duration) ? audio.duration : (chunks[currentChunk]?.duration_milliseconds ?? 0) / 1_000;
  const updateTimeline = () => {
    const total = duration();
    seek.max = String(total || 0);
    seek.value = String(Math.min(audio.currentTime || 0, total || 0));
    currentTime.textContent = formatPlaybackTime(audio.currentTime);
    totalTime.textContent = formatPlaybackTime(total);
  };
  const updateButtons = () => {
    const available = chunks.length > 0;
    playPause.disabled = !available;
    previous.disabled = !available || currentChunk === 0;
    next.disabled = !available || currentChunk === chunks.length - 1;
    skipButtons.forEach((button) => { button.disabled = !available; });
  };
  const setPlayButton = () => {
    const playing = !audio.paused;
    playPause.textContent = playing ? "Ⅱ" : "▶";
    playPause.setAttribute("aria-label", playing ? "Pause" : "Play");
  };
  const refreshBackgroundProgress = async () => {
    if (document.visibilityState === "hidden") return;
    try {
      const [audioResponse, progressResponse] = await Promise.all([
        fetch(`/api/v1/books/${encodeURIComponent(bookId)}/audio`),
        fetch(`/api/v1/books/${encodeURIComponent(bookId)}/progress`),
      ]);
      if (!audioResponse.ok || !progressResponse.ok) return;

      const refreshedChunks = await audioResponse.json();
      const progress = await progressResponse.json();
      const hadNoAudio = chunks.length === 0;
      const selectedId = chunks[currentChunk]?.id;
      chunks = refreshedChunks;
      const restoredIndex = chunks.findIndex((chunk) => chunk.id === selectedId);
      if (restoredIndex >= 0) currentChunk = restoredIndex;
      chapters = progress.chapters;
      drawChapterNavigation();
      setControlsEnabled(chunks.length > 0);
      updateButtons();
      if (chunks.length) chunkLabel.textContent = `Segment ${currentChunk + 1} of ${chunks.length}`;

      if (hadNoAudio && chunks.length) {
        statusMessage.classList.remove("player-processing-status");
        await selectChunk(0);
        statusMessage.textContent = "Your first audio segment is ready.";
      }
      if (progress.total_chunks > 0 && progress.ready_chunks === progress.total_chunks) {
        window.clearInterval(backgroundRefreshTimer);
        backgroundRefreshTimer = null;
      }
    } catch (error) {
      // Keep the currently rendered state; the next background check can recover.
    }
  };
  const startBackgroundRefresh = () => {
    if (backgroundRefreshTimer !== null) return;
    backgroundRefreshTimer = window.setInterval(refreshBackgroundProgress, 7_000);
  };
  const persistPlayback = async ({ force = false, keepalive = false } = {}) => {
    const chunk = chunks[currentChunk];
    if (!chunk || !audio.src) return;
    const positionMilliseconds = Math.max(0, Math.round((audio.currentTime || 0) * 1_000));
    const now = Date.now();
    if (!force && now - lastPersistedAt < 5_000) return;
    lastPersistedAt = now;
    try {
      const response = await fetch(`/api/v1/books/${encodeURIComponent(bookId)}/playback`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ audio_chunk_id: chunk.id, position_milliseconds: positionMilliseconds }),
        keepalive,
      });
      if (!response.ok && !keepalive) throw new Error("Unable to save playback position");
    } catch (error) {
      if (!keepalive) statusMessage.textContent = "Playback is active, but the position could not be saved.";
    }
  };
  const drawChapterNavigation = () => {
    if (!chapters.length) {
      chapterSummary.textContent = "Book structure is still being prepared.";
      chapterList.innerHTML = '<li class="chapter-list__empty">Chapters will appear here as soon as PDF extraction finishes.</li>';
      nextAvailableChunk.textContent = "The next available chunk is still being generated.";
      previousChapter.disabled = true;
      nextChapter.disabled = true;
      return;
    }
    selectedChapter = Math.min(selectedChapter, chapters.length - 1);
    const selected = chapters[selectedChapter];
    chapterSummary.textContent = `Viewing Chapter ${selected.chapter_index + 1} · pages ${selected.start_page}–${selected.end_page} · ${selected.ready_chunks}/${selected.total_chunks} chunks ready`;
    chapterList.innerHTML = chapters.map((chapter, index) => `
      <li><button type="button" class="chapter-item${index === selectedChapter ? " is-selected" : ""}" data-chapter-index="${index}" aria-current="${index === selectedChapter ? "true" : "false"}"><span><b>CH ${String(chapter.chapter_index + 1).padStart(2, "0")}</b><strong>${escapeHtml(chapter.title)}</strong></span><small class="status--${escapeHtml(chapter.status)}">${statusLabel(chapter.status)} · ${chapter.ready_chunks}/${chapter.total_chunks}</small></button></li>
    `).join("");
    const nextReady = chapters.flatMap((chapter) => chapter.chunks.map((chunk) => ({ chapter, chunk }))).find(({ chunk }) => chunk.status === "ready");
    nextAvailableChunk.textContent = nextReady
      ? `Next available chunk: Chapter ${nextReady.chapter.chapter_index + 1}, segment ${nextReady.chunk.chunk_index + 1}.`
      : "The next available chunk is still being generated.";
    previousChapter.disabled = selectedChapter === 0;
    nextChapter.disabled = selectedChapter === chapters.length - 1;
    chapterList.querySelectorAll("[data-chapter-index]").forEach((button) => button.addEventListener("click", () => {
      selectedChapter = Number(button.dataset.chapterIndex);
      window.history.replaceState({}, "", `${window.location.pathname}?chapter=${selectedChapter}`);
      drawChapterNavigation();
      playSelectedChapter();
    }));
  };
  const playSelectedChapter = () => {
    const offset = chapters.slice(0, selectedChapter).reduce((total, chapter) => total + chapter.chunks.length, 0);
    const end = offset + chapters[selectedChapter].chunks.length;
    const index = chunks.findIndex((chunk) => chunk.chunk_index >= offset * 1000 && chunk.chunk_index < end * 1000);
    if (index >= 0) selectChunk(index, !audio.paused);
    else statusMessage.textContent = "Audio for this chapter is still being prepared.";
  };
  const selectChunk = async (index, shouldPlay = false, startAtMilliseconds = 0) => {
    if (index < 0 || index >= chunks.length) return;
    if (audio.src && index !== currentChunk) await persistPlayback({ force: true });
    currentChunk = index;
    const chunk = chunks[currentChunk];
    audioRetryAttempts = 0;
    pendingSeekSeconds = Math.max(0, startAtMilliseconds / 1_000);
    audio.src = chunk.stream_url;
    audio.playbackRate = Number(speed.value);
    audio.load();
    chunkLabel.textContent = `Segment ${currentChunk + 1} of ${chunks.length}`;
    statusMessage.textContent = "Ready to play";
    updateTimeline();
    updateButtons();
    if (shouldPlay) {
      try { await audio.play(); } catch (error) { statusMessage.textContent = "Press Play to start audio."; }
    }
  };

  playPause.addEventListener("click", async () => {
    if (audio.paused) {
      try { await audio.play(); } catch (error) { statusMessage.textContent = "Unable to start audio. Please try again."; }
    } else {
      audio.pause();
    }
  });
  previous.addEventListener("click", () => selectChunk(currentChunk - 1, !audio.paused));
  next.addEventListener("click", () => selectChunk(currentChunk + 1, !audio.paused));
  previousChapter.addEventListener("click", () => {
    selectedChapter -= 1;
    playSelectedChapter();
    window.history.replaceState({}, "", `${window.location.pathname}?chapter=${selectedChapter}`);
    drawChapterNavigation();
    loadUsage();
  });
  nextChapter.addEventListener("click", () => {
    selectedChapter += 1;
    playSelectedChapter();
    window.history.replaceState({}, "", `${window.location.pathname}?chapter=${selectedChapter}`);
    drawChapterNavigation();
  });
  skipButtons.forEach((button) => button.addEventListener("click", () => {
    audio.currentTime = Math.max(0, Math.min(duration(), audio.currentTime + Number(button.dataset.skip)));
  }));
  speed.addEventListener("change", () => { audio.playbackRate = Number(speed.value); });
  seek.addEventListener("input", () => { audio.currentTime = Number(seek.value); updateTimeline(); });
  seek.addEventListener("change", () => { persistPlayback({ force: true }); });
  audio.addEventListener("loadedmetadata", () => {
    if (pendingSeekSeconds !== null) {
      audio.currentTime = Math.min(pendingSeekSeconds, duration());
      pendingSeekSeconds = null;
    }
    updateTimeline();
  });
  audio.addEventListener("timeupdate", () => { updateTimeline(); persistPlayback(); });
  audio.addEventListener("play", setPlayButton);
  audio.addEventListener("pause", () => { setPlayButton(); persistPlayback({ force: true }); });
  audio.addEventListener("ended", async () => {
    await persistPlayback({ force: true });
    if (currentChunk < chunks.length - 1) selectChunk(currentChunk + 1, true);
    else { statusMessage.textContent = "Book playback complete"; setPlayButton(); }
  });
  audio.addEventListener("error", () => {
    if (audioRetryAttempts < 2 && chunks[currentChunk]) {
      audioRetryAttempts += 1;
      statusMessage.textContent = `Connection interrupted. Retrying segment (${audioRetryAttempts}/2)…`;
      window.setTimeout(() => audio.load(), 800 * audioRetryAttempts);
      return;
    }
    statusMessage.textContent = "This audio segment could not be loaded. Check your connection and try again.";
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") persistPlayback({ force: true, keepalive: true });
  });
  window.addEventListener("pagehide", () => {
    persistPlayback({ force: true, keepalive: true });
    window.clearInterval(backgroundRefreshTimer);
  });

  try {
    const [bookResponse, audioResponse, progressResponse, playbackResponse] = await Promise.all([
      fetch(`/api/v1/books/${encodeURIComponent(bookId)}`),
      fetch(`/api/v1/books/${encodeURIComponent(bookId)}/audio`),
      fetch(`/api/v1/books/${encodeURIComponent(bookId)}/progress`),
      fetch(`/api/v1/books/${encodeURIComponent(bookId)}/playback`),
    ]);
    if (!bookResponse.ok || !audioResponse.ok || !progressResponse.ok || !playbackResponse.ok) throw new Error("Unable to load book player");
    const book = await bookResponse.json();
    chunks = await audioResponse.json();
    const progress = await progressResponse.json();
    const playback = await playbackResponse.json();
    chapters = progress.chapters;
    title.textContent = book.title;
    author.textContent = book.author;
    cover.className = `book-cover book-cover--${coverVariant(book.title)}`;
    cover.querySelector("b").textContent = book.title.slice(0, 1).toUpperCase() || "A";
    drawChapterNavigation();
    await loadUsage();
    window.setInterval(loadUsage, 15_000);
    setControlsEnabled(chunks.length > 0);
    startBackgroundRefresh();
    if (!chunks.length) {
      statusMessage.classList.add("player-processing-status");
      statusMessage.innerHTML = '<span>Preparing your first audio segment</span><span class="processing-line" aria-hidden="true"><i></i></span><span class="processing-bars" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span>';
      return;
    }
    statusMessage.classList.remove("player-processing-status");
    const resumeChunk = chunks.findIndex((chunk) => chunk.id === playback.audio_chunk_id);
    const resumeIndex = resumeChunk >= 0 ? resumeChunk : 0;
    const resumeAtMilliseconds = resumeChunk >= 0 ? playback.position_milliseconds : 0;
    await selectChunk(resumeIndex, false, resumeAtMilliseconds);
    if (resumeAtMilliseconds > 0) {
      statusMessage.textContent = `Resume position restored at ${formatPlaybackTime(resumeAtMilliseconds / 1_000)}.`;
    }
  } catch (error) {
    statusMessage.textContent = "Unable to load this book. Please return to your library and try again.";
  }
}

async function renderPlayerLanding() {
  document.querySelector("#app").innerHTML = shell(`
    <header class="topbar"><span>Web / Desktop (Player)</span><span>◉ USER⌄</span></header>
    <section class="feature-page"><a class="back-link" href="/library">← Library</a><h1>PLAYER</h1><p id="player-landing-status">Opening your most recent book…</p></section>
  `);

  const statusMessage = document.querySelector("#player-landing-status");
  try {
    const response = await fetch("/api/v1/books");
    if (!response.ok) throw new Error("Unable to load books");
    const books = await response.json();
    const lastBookId = window.localStorage.getItem("ai-reader:last-book-id");
    const book = books.find((item) => item.id === lastBookId)
      ?? books.find((item) => item.status === "ready")
      ?? books[0];
    if (book) {
      window.location.replace(`/books/${encodeURIComponent(book.id)}`);
      return;
    }
    statusMessage.innerHTML = 'No books are available yet. <a class="back-link" href="/upload">Add a book</a> to start listening.';
  } catch (error) {
    statusMessage.textContent = "Unable to open the player. Please try again later.";
  }
}

let monitorBusy = false;
async function refreshGlobalProcessing() {
  if (monitorBusy || document.hidden) return;
  monitorBusy = true;
  try {
    const response = await fetch("/api/v1/books", { signal: AbortSignal.timeout(10000) });
    if (!response.ok) throw new Error("Library unavailable");
    const books = await response.json();
    window.dispatchEvent(new CustomEvent("books-updated", { detail: books }));
    const panel = document.querySelector("#background-status");
    if (!panel) return;
    const active = books.filter((book) => book.status === "processing");
    panel.hidden = active.length === 0;
    panel.innerHTML = active.map((book) => `<a href="/books/${encodeURIComponent(book.id)}">Processing in background · ${escapeHtml(book.title)} · ${Number(book.progress_percent).toFixed(0)}%<span class="processing-line" aria-hidden="true"><i></i></span></a>`).join("");
  } catch (error) {
    const panel = document.querySelector("#background-status");
    if (panel) { panel.hidden = false; panel.textContent = "Processing status unavailable. Reconnecting…"; }
  } finally { monitorBusy = false; }
}
window.setInterval(refreshGlobalProcessing, 7000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshGlobalProcessing(); });
window.addEventListener("pageshow", refreshGlobalProcessing);

if (window.location.pathname === "/library") {
  renderLibrary();
} else if (window.location.pathname === "/upload") {
  renderUpload();
} else if (window.location.pathname === "/player") {
  renderPlayerLanding();
} else if (window.location.pathname === "/settings") {
  renderSettings();
} else if (window.location.pathname.startsWith("/books/")) {
  renderBookPage();
} else {
  const page = currentPage(window.location.pathname);
  document.querySelector("#app").innerHTML = shell(`
    <h1>${page.title}</h1>
    <section class="placeholder"><p>${page.description}</p></section>
  `);
}
