const pages = {
  "/library": {
    title: "Library",
  },
  "/upload": {
    title: "Add Book",
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
    ["/library", "▣", "Library"],
    ["/upload", "⇧", "Add Book"],
    ["/settings", "⚙", "Settings"],
  ]
    .map((path) => {
      const [href, icon, label] = path;
      const active = href === window.location.pathname ? ' aria-current="page"' : "";
      return `<a href="${href}"${active}><span aria-hidden="true">${icon}</span>${label}</a>`;
    })
    .join("");
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
      <main class="app-shell">${content}</main>
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

function renderUpload() {
  document.querySelector("#app").innerHTML = shell(`
    <header class="topbar"><span>Web / Desktop (Add Book)</span><span>◉ USER⌄</span></header>
    <form id="upload-form" class="feature-page add-book-page">
      <a class="back-link" href="/library">← Library</a><h1>ADD BOOK</h1><p>Turn your technical PDF into an audiobook.</p>
      <label class="drop-zone" id="drop-zone"><b>⇧</b><strong>Drag & drop your PDF here</strong><span>or tap to select a file</span><small>Max 200 MB · PDF only</small><input id="pdf-file" type="file" accept="application/pdf" hidden></label>
      <p id="selected-file" class="selected-file" aria-live="polite">No file selected</p>
      <div class="mode-panel"><span>Processing mode</span><div class="mode-buttons" id="mode-buttons"><button type="button" class="is-active" data-mode="balanced">Balanced</button><button type="button" data-mode="explain">Explain code</button><button type="button" data-mode="skip">Skip code</button></div><label class="voice-setting">Voice<select aria-label="Voice"><option>Default</option><option>Neutral</option><option>Expressive</option></select></label></div>
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
  let file = null;

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
  }));
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
      const processing = await fetch(`/api/v1/books/${book.id}/process`, { method: "POST" });
      if (!processing.ok) throw new Error(await processing.text());
      window.location.assign(`/books/${book.id}`);
    } catch (error) {
      startButton.disabled = false;
      statusMessage.textContent = "Upload failed. Please try again.";
    }
  });
}

function renderBookPage() {
  document.querySelector("#app").innerHTML = shell(`
    <header class="topbar"><span>Web / Desktop (Player)</span><span>◉ USER⌄</span></header>
    <section class="feature-page player-page"><a class="back-link" href="/library">← Library</a><div class="player-heading"><span class="book-cover book-cover--2"><b>A</b><i></i></span><div><h1>YOUR BOOK</h1><p>Technical audiobook</p><span class="book-card__meta">◖ preparing · chapters and player will appear here</span></div></div>
    <div class="player-tabs"><button class="is-active">Player</button><button>Chapters</button><button>Details</button></div><div class="player-track"><span></span></div><div class="player-controls"><button>↺15</button><button>◀</button><button class="play">Ⅱ</button><button>▶</button><button>15↻</button></div></section>
  `);
}

if (window.location.pathname === "/library") {
  renderLibrary();
} else if (window.location.pathname === "/upload") {
  renderUpload();
} else if (window.location.pathname.startsWith("/books/")) {
  renderBookPage();
} else {
  const page = currentPage(window.location.pathname);
  document.querySelector("#app").innerHTML = shell(`
    <h1>${page.title}</h1>
    <section class="placeholder"><p>${page.description}</p></section>
  `);
}
