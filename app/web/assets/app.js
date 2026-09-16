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
    ["/settings", "settings", "Settings"],
  ]
    .map((path) => {
      const [href, iconName, label] = path;
      const active = href === window.location.pathname ? ' aria-current="page"' : "";
      return `<a href="${href}"${active}>${navigationIcon(iconName)}${label}</a>`;
    })
    .join("");
}

function navigationIcon(name) {
  const paths = {
    library: '<path d="M4 5h16v15H4zM8 5v15M11 9h5M11 13h5"/>',
    upload: '<path d="M12 15V3m0 0L7 8m5-5 5 5M5 16v4h14v-4"/>',
    settings: '<path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Zm0-12.2v2m0 14v2m9-9h-2M5 12H3m15.4-6.4-1.4 1.4M7 17l-1.4 1.4m12.8 0L17 17M7 7 5.6 5.6"/>',
  };
  return `<svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[name]}</svg>`;
}

function shell(content) {
  queueMicrotask(() => { void initializeMiniPlayer(); });
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
      <footer id="mini-player" class="mini-player" aria-label="Mini player" hidden>
        <div class="mini-player__details">
          <span class="mini-player__copy"><small>NOW PLAYING</small><strong id="mini-player-title">Loading your latest book…</strong><span id="mini-player-segment">Preparing audio</span></span>
          <label class="mini-player__timeline" for="mini-player-seek"><output id="mini-player-current-time">0:00</output><input id="mini-player-seek" type="range" min="0" max="0" value="0" step="0.1" aria-label="Playback position"><output id="mini-player-total-time">0:00</output></label>
        </div>
        <audio id="mini-player-audio" preload="metadata"></audio>
        <div class="mini-player__controls" aria-label="Playback controls"><button id="mini-player-previous" type="button" aria-label="Previous segment" title="Previous segment">◀◀</button><button id="mini-player-play" type="button" aria-label="Play" title="Play">▶</button><button id="mini-player-next" type="button" aria-label="Next segment" title="Next segment">▶▶</button></div>
        <label class="mini-player__volume" for="mini-player-volume">VOL<input id="mini-player-volume" type="range" min="0" max="1" value="1" step="0.01" aria-label="Volume"></label>
        <a id="mini-player-open" class="mini-player__full" href="/player">Open full player ↗</a>
      </footer>
      <nav class="mobile-navigation" aria-label="Mobile navigation">${navigation()}</nav>
    </div>
`;
}

async function initializeMiniPlayer() {
  if (window.location.pathname.startsWith("/books/")) return;

  const player = document.querySelector("#mini-player");
  const audio = document.querySelector("#mini-player-audio");
  const playButton = document.querySelector("#mini-player-play");
  const previousButton = document.querySelector("#mini-player-previous");
  const nextButton = document.querySelector("#mini-player-next");
  const seek = document.querySelector("#mini-player-seek");
  const currentTime = document.querySelector("#mini-player-current-time");
  const totalTime = document.querySelector("#mini-player-total-time");
  const volume = document.querySelector("#mini-player-volume");
  const title = document.querySelector("#mini-player-title");
  const segment = document.querySelector("#mini-player-segment");
  const openLink = document.querySelector("#mini-player-open");
  if (!player || !audio || !playButton || !previousButton || !nextButton || !seek || !currentTime || !totalTime || !volume || !title || !segment || !openLink) return;

  try {
    const libraryResponse = await fetch("/api/v1/books", { signal: AbortSignal.timeout(10_000) });
    if (!libraryResponse.ok) throw new Error("Unable to load the library");
    const books = await libraryResponse.json();
    const lastBookId = window.localStorage.getItem("ai-reader:last-book-id");
    const preferred = books.find((book) => book.id === lastBookId);
    const candidates = [preferred, ...books.filter((book) => book !== preferred && book.status === "ready"), ...books.filter((book) => book !== preferred && book.status !== "ready")].filter(Boolean);

    for (const book of candidates) {
      const [audioResponse, playbackResponse] = await Promise.all([
        fetch(`/api/v1/books/${encodeURIComponent(book.id)}/audio`, { signal: AbortSignal.timeout(10_000) }),
        fetch(`/api/v1/books/${encodeURIComponent(book.id)}/playback`, { signal: AbortSignal.timeout(10_000) }),
      ]);
      if (!audioResponse.ok) continue;
      const chunks = await audioResponse.json();
      if (!chunks.length) continue;
      const playback = playbackResponse.ok ? await playbackResponse.json() : null;
      let currentChunk = chunks.findIndex((chunk) => chunk.id === playback?.audio_chunk_id);
      if (currentChunk < 0) currentChunk = 0;
      let lastPersistedAt = 0;
      const savedVolume = Number(window.localStorage.getItem("ai-reader:volume"));
      audio.volume = Number.isFinite(savedVolume) && savedVolume >= 0 && savedVolume <= 1 ? savedVolume : 1;
      volume.value = String(audio.volume);

      const setButton = () => {
        const playing = !audio.paused;
        playButton.textContent = playing ? "Ⅱ" : "▶";
        playButton.setAttribute("aria-label", playing ? "Pause" : "Play");
        playButton.title = playing ? "Pause" : "Play";
      };
      const getDuration = () => Number.isFinite(audio.duration) ? audio.duration : (chunks[currentChunk]?.duration_milliseconds ?? 0) / 1_000;
      const updateTimeline = () => {
        const duration = getDuration();
        seek.max = String(duration || 0);
        seek.value = String(Math.min(audio.currentTime || 0, duration || 0));
        currentTime.textContent = formatPlaybackTime(audio.currentTime || 0);
        totalTime.textContent = formatPlaybackTime(duration);
      };
      const updateSegmentControls = () => {
        previousButton.disabled = currentChunk === 0;
        nextButton.disabled = currentChunk >= chunks.length - 1;
      };
      const persistPlayback = async ({ force = false, keepalive = false } = {}) => {
        const chunk = chunks[currentChunk];
        const now = Date.now();
        if (!chunk || (!force && now - lastPersistedAt < 5_000)) return;
        lastPersistedAt = now;
        try {
          await fetch(`/api/v1/books/${encodeURIComponent(book.id)}/playback`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ audio_chunk_id: chunk.id, position_milliseconds: Math.round((audio.currentTime || 0) * 1_000) }),
            keepalive,
          });
        } catch (error) {
          // Playback continues even if saving the resume point is temporarily unavailable.
        }
      };
      const loadChunk = async (index, positionMilliseconds = 0, shouldPlay = false) => {
        if (index < 0 || index >= chunks.length) return;
        if (audio.src && index !== currentChunk) await persistPlayback({ force: true });
        currentChunk = index;
        const chunk = chunks[currentChunk];
        audio.src = chunk.stream_url;
        segment.textContent = `Segment ${currentChunk + 1} of ${chunks.length}`;
        updateSegmentControls();
        updateTimeline();
        audio.load();
        audio.addEventListener("loadedmetadata", () => {
          if (positionMilliseconds) audio.currentTime = Math.min(positionMilliseconds / 1_000, audio.duration || 0);
          updateTimeline();
          if (shouldPlay) audio.play().catch(() => { setButton(); });
        }, { once: true });
      };

      title.textContent = book.title;
      openLink.href = `/books/${encodeURIComponent(book.id)}`;
      loadChunk(currentChunk, playback?.position_milliseconds ?? 0);
      player.hidden = false;
      playButton.addEventListener("click", async () => {
        if (audio.paused) {
          try { await audio.play(); } catch (error) { segment.textContent = "Press play again to start audio"; }
        } else audio.pause();
      });
      previousButton.addEventListener("click", () => { void loadChunk(currentChunk - 1, 0, !audio.paused); });
      nextButton.addEventListener("click", () => { void loadChunk(currentChunk + 1, 0, !audio.paused); });
      seek.addEventListener("input", () => { audio.currentTime = Number(seek.value); updateTimeline(); });
      seek.addEventListener("change", () => { void persistPlayback({ force: true }); });
      volume.addEventListener("input", () => {
        audio.volume = Number(volume.value);
        window.localStorage.setItem("ai-reader:volume", String(audio.volume));
      });
      audio.addEventListener("loadedmetadata", updateTimeline);
      audio.addEventListener("timeupdate", () => { updateTimeline(); void persistPlayback(); });
      audio.addEventListener("play", setButton);
      audio.addEventListener("pause", () => { setButton(); void persistPlayback({ force: true }); });
      audio.addEventListener("ended", async () => {
        await persistPlayback({ force: true });
        if (currentChunk < chunks.length - 1) {
          await loadChunk(currentChunk + 1, 0, true);
        } else {
          segment.textContent = "Book playback complete";
          setButton();
        }
      });
      window.addEventListener("pagehide", () => { void persistPlayback({ force: true, keepalive: true }); }, { once: true });
      return;
    }
  } catch (error) {
    // The mini player is supplementary; the page remains usable if its request fails.
  }
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
  const publicationYear = Number.isInteger(book.publication_year) ? ` · ${book.publication_year}` : "";
  const initial = title.slice(0, 1).toUpperCase() || "A";
  const progress = Math.max(0, Math.min(100, Number(book.progress_percent) || 0));
  return `
    <article class="book-card">
    <a class="book-card__link" href="/books/${encodeURIComponent(book.id)}">
      <span class="book-cover book-cover--${coverVariant(book.title)}" aria-hidden="true"><b>${initial}</b><i></i></span>
      <span class="book-card__body">
        <span class="book-card__status status--${escapeHtml(book.status)}">${statusLabel(book.status)}</span>
        <strong>${title}</strong><span class="book-card__author">${author}${publicationYear}</span>
        <span class="progress" aria-label="${progress}% complete"><span style="width: ${progress}%"></span></span>
        <span class="book-card__meta">◖ ${progress}% complete <b>•••</b></span>
      </span>
    </a>
    <button type="button" class="delete-book" data-delete-book="${encodeURIComponent(book.id)}" aria-label="Delete ${title}" title="Delete book">×</button>
    </article>
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
    list.querySelectorAll("[data-delete-book]").forEach((button) => button.addEventListener("click", async () => {
      const bookId = decodeURIComponent(button.dataset.deleteBook);
      const book = books.find((item) => item.id === bookId);
      if (!book || !window.confirm(`Delete “${book.title}” and all of its audio? This cannot be undone.`)) return;
      button.disabled = true;
      try {
        const response = await fetch(`/api/v1/books/${encodeURIComponent(bookId)}`, { method: "DELETE" });
        if (!response.ok) throw new Error("Unable to delete book");
        books = books.filter((item) => item.id !== bookId);
        if (window.localStorage.getItem("ai-reader:last-book-id") === bookId) {
          window.localStorage.removeItem("ai-reader:last-book-id");
        }
        draw();
      } catch (error) {
        button.disabled = false;
        window.alert("Unable to delete this book. Please try again.");
      }
    }));
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
      <label class="drop-zone" id="drop-zone"><b>⇧</b><strong>Drag & drop your PDF here</strong><span>or tap to select a file</span><small>PDF only · up to 100 MB and 500 pages</small><input id="pdf-file" type="file" accept="application/pdf" hidden></label>
      <p id="selected-file" class="selected-file" aria-live="polite">No file selected</p>
      <section class="upload-language-control" aria-label="Reading language"><label class="voice-setting upload-language-setting">Reading language<select id="reading-language-setting" aria-label="Reading language"><option value="auto">Auto-detect</option><option value="en">English</option><option value="ru">Russian</option><option value="de">German</option></select></label></section>
      <section id="processing-scope" class="processing-scope" hidden aria-label="Pages to process"><b>PROCESSING SCOPE</b><p id="page-count-note">Upload the PDF to choose pages.</p><div class="page-range-sliders"><label>From page <output id="start-page-value" for="start-page">1</output><input id="start-page" type="range" min="1" max="1" value="1"></label><label>To page <output id="end-page-value" for="end-page">1</output><input id="end-page" type="range" min="1" max="1" value="1"></label></div><small>Start with a chapter or a sample. You can return later and process more pages from the same uploaded PDF.</small></section>
      <section class="upload-guidance" aria-label="How processing works"><b>WHAT HAPPENS NEXT</b><ol><li>We verify the PDF, its size, and its page count.</li><li>AI Reader extracts sections and prepares an estimate.</li><li>Audio is generated in the background. The first ready segments appear in the player, and you can safely leave this page.</li></ol></section>
      <details class="upload-settings"><summary>PROCESSING SETTINGS <span>Use saved defaults or customise this book</span></summary><div class="mode-panel"><span>Code mode</span><div class="mode-buttons mode-buttons--four" id="mode-buttons"><button type="button" data-mode="explain">Explain</button><button type="button" data-mode="read">Read</button><button type="button" data-mode="skip">Skip</button><button type="button" class="is-active" data-mode="hybrid">Hybrid</button></div><span class="reading-style-label">Table mode</span><div class="mode-buttons" id="table-mode-buttons"><button type="button" class="is-active" data-mode="summarize">Summarize</button><button type="button" data-mode="read_all">Read all</button><button type="button" data-mode="skip">Skip</button></div><span class="reading-style-label">Diagram mode</span><div class="mode-buttons mode-buttons--two" id="diagram-mode-buttons"><button type="button" class="is-active" data-mode="describe">Describe</button><button type="button" data-mode="skip">Skip</button></div><span class="reading-style-label">Formula mode</span><div class="mode-buttons" id="formula-mode-buttons"><button type="button" class="is-active" data-mode="explain">Explain</button><button type="button" data-mode="read">Read</button><button type="button" data-mode="skip">Skip</button></div><label class="voice-setting">Voice<select id="voice-setting" aria-label="Voice"><option value="alloy">Alloy</option><option value="ash">Ash</option><option value="ballad">Ballad</option><option value="cedar">Cedar</option><option value="coral">Coral</option><option value="echo">Echo</option><option value="fable">Fable</option><option value="marin">Marin</option><option value="nova">Nova</option><option value="onyx">Onyx</option><option value="sage">Sage</option><option value="shimmer">Shimmer</option><option value="verse">Verse</option></select></label><label class="voice-setting">Speech speed<select id="speed-setting" aria-label="Speech speed"><option value="normal">Normal</option><option value="slow">Slow</option></select></label><span class="reading-style-label">Reading style</span><div class="mode-buttons" id="style-buttons"><button type="button" data-style="calm">Calm</button><button type="button" class="is-active" data-style="neutral">Neutral</button><button type="button" data-style="expressive">Expressive</button></div></div></details>
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
  const processingScope = document.querySelector("#processing-scope");
  const pageCountNote = document.querySelector("#page-count-note");
  const startPage = document.querySelector("#start-page");
  const endPage = document.querySelector("#end-page");
  const startPageValue = document.querySelector("#start-page-value");
  const endPageValue = document.querySelector("#end-page-value");
  const readingLanguageSetting = document.querySelector("#reading-language-setting");
  const voiceSetting = document.querySelector("#voice-setting");
  const speedSetting = document.querySelector("#speed-setting");
  let file = null;
  let readingStyle = "neutral";
  let codeMode = "hybrid";
  let tableMode = "summarize";
  let diagramMode = "describe";
  let formulaMode = "explain";
  let uploadedBook = null;
  const maxPdfSizeBytes = 100 * 1024 * 1024;
  const appendParameterHelp = (element, text) => {
    const hint = document.createElement("small");
    hint.className = "parameter-help";
    hint.textContent = text;
    element.insertAdjacentElement("afterend", hint);
  };
  appendParameterHelp(document.querySelector("#mode-buttons"), "How code blocks are narrated: explain concepts, read literal code, skip it, or use a balanced hybrid.");
  appendParameterHelp(document.querySelector("#table-mode-buttons"), "Summarise table insights, read every cell, or skip tables.");
  appendParameterHelp(document.querySelector("#diagram-mode-buttons"), "Describe visual content in words, or omit it from narration.");
  appendParameterHelp(document.querySelector("#formula-mode-buttons"), "Explain notation, read symbols aloud, or skip formulas.");
  appendParameterHelp(readingLanguageSetting.closest("label"), "Auto-detect keeps the PDF's main language. Choose another language to translate the narration.");
  appendParameterHelp(voiceSetting.closest("label"), "Sets the narrator voice for this book's newly generated audio.");
  appendParameterHelp(speedSetting.closest("label"), "Normal is natural pacing; Slow improves clarity for dense material.");
  appendParameterHelp(document.querySelector("#style-buttons"), "Calm is measured, Neutral is balanced, and Expressive adds more variation.");

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
  const loadUploadedEstimate = async () => {
    if (!uploadedBook) return;
    const start = Number(startPage.value);
    const end = Number(endPage.value);
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start || end > uploadedBook.page_count) return;
    const response = await fetch(`/api/v1/books/${encodeURIComponent(uploadedBook.id)}/estimate?start_page=${start}&end_page=${end}`);
    if (!response.ok) throw new Error("Unable to estimate this page range");
    const estimate = await response.json();
    document.querySelector("#estimate-tokens").textContent = `~ ${estimate.estimated_total_tokens.toLocaleString("en-US")}`;
    document.querySelector("#estimate-cost").textContent = `~ $${estimate.estimated_ai_cost_usd.toFixed(2)}`;
    document.querySelector("#estimate-audio").textContent = formatAudioDuration(estimate.estimated_audio_seconds);
  };
  const responseError = async (response, fallback) => {
    if (response.status === 429) return "Too many requests. Please wait a minute before trying again.";
    const payload = await response.json().catch(() => null);
    return payload?.detail || fallback;
  };
  const selectFile = async (selected) => {
    if (!selected) return;
    if (selected.type !== "application/pdf" && !selected.name.toLowerCase().endsWith(".pdf")) {
      statusMessage.textContent = "Please choose a PDF file.";
      return;
    }
    if (selected.size > maxPdfSizeBytes) {
      file = null;
      selectedFile.textContent = `${selected.name} · ${formatBytes(selected.size)}`;
      statusMessage.textContent = "This PDF is larger than the 100 MB upload limit.";
      startButton.disabled = true;
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
  const syncPageRange = ({ estimate = false } = {}) => {
    if (!uploadedBook) return;
    startPage.value = String(Math.max(1, Math.min(uploadedBook.page_count, Number(startPage.value) || 1)));
    endPage.value = String(Math.max(Number(startPage.value), Math.min(uploadedBook.page_count, Number(endPage.value) || uploadedBook.page_count)));
    startPageValue.textContent = startPage.value;
    endPageValue.textContent = endPage.value;
    if (estimate) void loadUploadedEstimate().catch(() => { statusMessage.textContent = "Range estimate is unavailable. Please adjust the pages and try again."; });
  };
  [startPage, endPage].forEach((input) => input.addEventListener("input", () => syncPageRange()));
  [startPage, endPage].forEach((input) => input.addEventListener("change", () => syncPageRange({ estimate: true })));
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
    readingLanguageSetting.value = preferences.reading_language;
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
    statusMessage.textContent = uploadedBook ? "Starting selected pages…" : "Uploading PDF…";
    try {
      if (!uploadedBook) {
        const data = new FormData();
        data.append("file", file);
        const upload = await fetch("/api/v1/books", { method: "POST", body: data });
        if (!upload.ok) throw new Error(await responseError(upload, "Upload failed. Please try again."));
        uploadedBook = await upload.json();
        processingScope.hidden = false;
        startPage.max = String(uploadedBook.page_count);
        endPage.max = String(uploadedBook.page_count);
        endPage.value = String(uploadedBook.page_count);
        syncPageRange();
        pageCountNote.textContent = `${uploadedBook.page_count} pages detected. Review the estimate, then confirm processing.`;
        await loadUploadedEstimate();
        startButton.textContent = "CONFIRM & START PROCESSING";
        startButton.disabled = false;
        statusMessage.textContent = "PDF stored. Choose the page range and review the estimate before processing.";
        return;
      }
      const processing = await fetch(`/api/v1/books/${uploadedBook.id}/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reading_language: readingLanguageSetting.value, voice: voiceSetting.value, speed: speedSetting.value, style: readingStyle, code_mode: codeMode, table_mode: tableMode, diagram_mode: diagramMode, formula_mode: formulaMode, start_page: Number(startPage.value), end_page: Number(endPage.value) }),
      });
      if (!processing.ok) throw new Error(await responseError(processing, "Processing could not be started."));
      window.location.assign(`/books/${uploadedBook.id}`);
    } catch (error) {
      startButton.disabled = false;
      statusMessage.textContent = error.message || "Upload failed. Please try again.";
    }
  });
}

async function renderSettings() {
  document.querySelector("#app").innerHTML = shell(`
    <header class="topbar"><span>Web / Desktop (Settings)</span><span>◉ USER⌄</span></header>
    <form id="preferences-form" class="feature-page settings-page"><a class="back-link" href="/library">← Library</a><h1>SETTINGS</h1><p>Choose defaults for books you process next.</p>
      <div class="settings-tabs" role="tablist" aria-label="Settings sections"><button type="button" id="settings-tab-narration" role="tab" aria-controls="settings-panel-narration" aria-selected="true" data-settings-tab="narration">Narration</button><button type="button" id="settings-tab-processing" role="tab" aria-controls="settings-panel-processing" aria-selected="false" data-settings-tab="processing">Processing</button><button type="button" id="settings-tab-usage" role="tab" aria-controls="settings-panel-usage" aria-selected="false" data-settings-tab="usage">Usage &amp; cost</button></div>
      <section id="settings-panel-narration" class="settings-tab-panel" role="tabpanel" aria-labelledby="settings-tab-narration" data-settings-panel="narration"><label class="voice-setting">Reading language<select name="reading_language"><option value="auto">Auto-detect</option><option value="en">English</option><option value="ru">Russian</option><option value="de">German</option></select></label><label class="voice-setting">Voice<select name="voice"><option value="alloy">Alloy</option><option value="ash">Ash</option><option value="ballad">Ballad</option><option value="cedar">Cedar</option><option value="coral">Coral</option><option value="echo">Echo</option><option value="fable">Fable</option><option value="marin">Marin</option><option value="nova">Nova</option><option value="onyx">Onyx</option><option value="sage">Sage</option><option value="shimmer">Shimmer</option><option value="verse">Verse</option></select></label><p class="settings-warning">Changing the voice or language affects new books only. Existing books require audio reprocessing.</p><label class="voice-setting">Speech speed<select name="speed"><option value="normal">Normal</option><option value="slow">Slow</option></select></label><label class="voice-setting">Reading style<select name="style"><option value="calm">Calm</option><option value="neutral">Neutral</option><option value="expressive">Expressive</option></select></label></section>
      <section id="settings-panel-processing" class="settings-tab-panel" role="tabpanel" aria-labelledby="settings-tab-processing" data-settings-panel="processing" hidden><label class="voice-setting">Code mode<select name="code_mode"><option value="explain">Explain</option><option value="read">Read</option><option value="skip">Skip</option><option value="hybrid">Hybrid</option></select></label><label class="voice-setting">Table mode<select name="table_mode"><option value="summarize">Summarize</option><option value="read_all">Read all</option><option value="skip">Skip</option></select></label><label class="voice-setting">Diagram mode<select name="diagram_mode"><option value="describe">Describe</option><option value="skip">Skip</option></select></label><label class="voice-setting">Formula mode<select name="formula_mode"><option value="explain">Explain</option><option value="read">Read</option><option value="skip">Skip</option></select></label></section>
      <section id="settings-panel-usage" class="settings-tab-panel settings-usage" role="tabpanel" aria-labelledby="settings-tab-usage" data-settings-panel="usage" hidden><p id="settings-usage-status" class="upload-status" aria-live="polite">Open this tab to load recorded usage.</p><div id="settings-usage-content"></div></section>
      <div id="settings-save-actions" class="settings-save-actions"><p id="preferences-status" class="upload-status" aria-live="polite">Loading saved preferences…</p><button class="button button--wide" type="submit">SAVE SETTINGS</button></div>
    </form>
  `);

  const form = document.querySelector("#preferences-form");
  const statusMessage = document.querySelector("#preferences-status");
  const saveActions = document.querySelector("#settings-save-actions");
  const usageStatus = document.querySelector("#settings-usage-status");
  const usageContent = document.querySelector("#settings-usage-content");
  let usageLoaded = false;
  const appendParameterHelp = (element, text) => {
    const hint = document.createElement("small");
    hint.className = "parameter-help";
    hint.textContent = text;
    element.insertAdjacentElement("afterend", hint);
  };
  appendParameterHelp(form.querySelector('[name="reading_language"]').closest("label"), "Auto-detect retains the PDF's main language; another choice translates new narration into that language.");
  appendParameterHelp(form.querySelector('[name="voice"]').closest("label"), "Sets the narrator voice for newly generated audio.");
  appendParameterHelp(form.querySelector('[name="speed"]').closest("label"), "Normal is natural pacing; Slow improves clarity for dense material.");
  appendParameterHelp(form.querySelector('[name="style"]').closest("label"), "Calm is measured, Neutral is balanced, and Expressive adds more variation.");
  appendParameterHelp(form.querySelector('[name="code_mode"]').closest("label"), "Explain concepts, read literal code, skip it, or use a balanced hybrid.");
  appendParameterHelp(form.querySelector('[name="table_mode"]').closest("label"), "Summarise table insights, read every cell, or skip tables.");
  appendParameterHelp(form.querySelector('[name="diagram_mode"]').closest("label"), "Describe visual content in words, or omit it from narration.");
  appendParameterHelp(form.querySelector('[name="formula_mode"]').closest("label"), "Explain notation, read symbols aloud, or skip formulas.");
  const formatCost = (value) => `$${Number(value || 0).toFixed(4)}`;
  const formatAddedDate = (value) => new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
  const renderUsageSummary = (summary) => {
    usageContent.innerHTML = `<div class="settings-usage-totals"><article><span>Total cost</span><strong>${formatCost(summary.total_cost_usd)}</strong><small>AI ${formatCost(summary.ai_cost_usd)} · TTS ${formatCost(summary.tts_cost_usd)}</small></article><article><span>AI tokens</span><strong>${Number(summary.input_tokens + summary.cached_input_tokens + summary.output_tokens).toLocaleString("en-US")}</strong><small>${Number(summary.input_tokens).toLocaleString("en-US")} input · ${Number(summary.output_tokens).toLocaleString("en-US")} output</small></article><article><span>Audio generated</span><strong>${formatPlaybackTime(summary.generated_audio_seconds)}</strong><small>${Number(summary.request_count).toLocaleString("en-US")} LLM requests · ${summary.total_books} books</small></article></div><section class="settings-usage-books"><div class="settings-usage-books__header"><span>Book</span><span>Added</span><span>Tokens</span><span>AI</span><span>TTS</span><span>Total</span></div>${summary.books.length ? summary.books.map((book) => `<a href="/books/${encodeURIComponent(book.id)}"><span><strong>${escapeHtml(book.title)}</strong><small>${escapeHtml(statusLabel(book.status))} · ${formatPlaybackTime(book.generated_audio_seconds)} audio</small></span><span>${formatAddedDate(book.created_at)}</span><span>${Number(book.input_tokens + book.cached_input_tokens + book.output_tokens).toLocaleString("en-US")}</span><span>${formatCost(book.ai_cost_usd)}</span><span>${formatCost(book.tts_cost_usd)}</span><strong>${formatCost(book.total_cost_usd)}</strong></a>`).join("") : '<p class="settings-usage-empty">No book usage has been recorded yet.</p>'}</section>`;
  };
  const loadUsageSummary = async () => {
    if (usageLoaded) return;
    usageStatus.textContent = "Loading recorded usage…";
    try {
      const response = await fetch("/api/v1/books/usage-summary");
      if (!response.ok) throw new Error("Unable to load usage summary");
      renderUsageSummary(await response.json());
      usageStatus.hidden = true;
      usageLoaded = true;
    } catch (error) {
      usageStatus.textContent = "Usage data is unavailable. Please try again later.";
    }
  };
  const activateTab = (name) => {
    document.querySelectorAll("[data-settings-tab]").forEach((tab) => {
      const active = tab.dataset.settingsTab === name;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    document.querySelectorAll("[data-settings-panel]").forEach((panel) => { panel.hidden = panel.dataset.settingsPanel !== name; });
    saveActions.hidden = name === "usage";
    if (name === "usage") void loadUsageSummary();
  };
  document.querySelectorAll("[data-settings-tab]").forEach((tab) => tab.addEventListener("click", () => activateTab(tab.dataset.settingsTab)));
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
    <section class="feature-page player-page"><a class="back-link" href="/library">← Library</a><div class="player-heading"><span id="player-cover" class="book-cover book-cover--2"><b>A</b><i></i></span><div class="player-heading__details"><h1 id="player-title">LOADING BOOK</h1><p id="player-author">Technical audiobook</p><span id="player-status" class="book-card__meta">Loading audio segments…</span><div id="book-processing-progress" class="book-processing-progress" role="progressbar" aria-label="Book processing progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i></i><span id="book-processing-percent">0%</span></div><section id="processing-controls" class="processing-controls" hidden><span id="processing-control-note"></span><div><button type="button" id="pause-processing">Pause</button><button type="button" id="resume-processing" hidden>Resume</button><button type="button" id="cancel-processing">Cancel</button><label>Process through page <input id="extend-end-page" type="number" min="1"></label><button type="button" id="extend-processing">Process more</button></div><div class="append-part"><label>Add continuation PDF <input id="append-part-file" type="file" accept="application/pdf"></label><button type="button" id="append-part">ADD PART</button></div></section></div><button type="button" id="open-chapters" class="open-chapters" aria-controls="chapter-navigation" aria-expanded="false">☰ Chapters</button></div>
    <div class="player-workspace"><div class="player-main"><section class="player-panel" aria-label="Audiobook player"><p id="chunk-label" class="chunk-label">No audio segment selected</p><audio id="book-audio" preload="metadata"></audio><label class="seek-label" for="player-seek"><span id="current-time">0:00</span><input id="player-seek" type="range" min="0" max="0" value="0" step="0.1" disabled><span id="total-time">0:00</span></label><div class="player-controls"><button type="button" data-skip="-15" aria-label="Rewind 15 seconds" disabled>↺15</button><button type="button" id="previous-chunk" aria-label="Previous audio segment" disabled>◀◀</button><button type="button" id="play-pause" class="play" aria-label="Play" disabled>▶</button><button type="button" id="next-chunk" aria-label="Next audio segment" disabled>▶▶</button><button type="button" data-skip="15" aria-label="Skip 15 seconds" disabled>15↻</button></div><div class="player-settings"><label class="volume-setting" for="player-volume">Volume <input id="player-volume" type="range" min="0" max="1" value="1" step="0.01" aria-describedby="volume-value"><output id="volume-value" for="player-volume">100%</output></label><label class="speed-setting" for="playback-speed">Playback speed<select id="playback-speed" disabled><option value="0.75">0.75×</option><option value="1" selected>1×</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option><option value="2">2×</option></select></label></div></section></div>
    <div id="chapters-backdrop" class="chapters-backdrop" hidden></div><aside id="chapter-navigation" class="chapter-navigation" aria-labelledby="chapters-heading"><div class="chapter-navigation__title"><div><h2 id="chapters-heading">CHAPTERS</h2><p id="chapter-summary">Loading book structure…</p></div><div class="chapter-navigation__controls"><button type="button" id="previous-chapter" aria-label="Previous chapter" disabled>←</button><button type="button" id="next-chapter" aria-label="Next chapter" disabled>→</button><button type="button" id="close-chapters" class="close-chapters" aria-label="Close chapters">×</button></div></div><ol id="chapter-list" class="chapter-list" aria-live="polite"></ol><p id="next-available-chunk" class="next-available-chunk">Checking the next available chunk…</p></aside></div>
    <details class="usage-panel" id="usage-panel" open><summary><span><h2>USAGE &amp; COST</h2><small>Live processing totals</small></span><b aria-hidden="true">⌄</b></summary><div class="usage-grid"><article class="usage-card"><span>AI TOKENS</span><b id="usage-tokens">—</b><small id="usage-token-detail">Input / output</small></article><article class="usage-card"><span>AI COST</span><b id="usage-ai-cost">—</b><small id="usage-ai-requests">LLM requests</small></article><article class="usage-card"><span>GENERATED AUDIO</span><b id="usage-audio-duration">—</b><small id="usage-generation-time">Generation time</small></article><article class="usage-card"><span>TTS COST</span><b id="usage-tts-cost">—</b><small>Generated audio and GPU</small></article><article class="usage-card usage-card--total"><span>TOTAL COST</span><b id="usage-total-cost">—</b><small>AI adaptation + TTS</small></article></div><p id="usage-note">Loading usage data…</p></details>
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
  const volume = document.querySelector("#player-volume");
  const volumeValue = document.querySelector("#volume-value");
  const skipButtons = [...document.querySelectorAll("[data-skip]")];
  const chapterSummary = document.querySelector("#chapter-summary");
  const chapterList = document.querySelector("#chapter-list");
  const chapterNavigation = document.querySelector("#chapter-navigation");
  const openChapters = document.querySelector("#open-chapters");
  const closeChapters = document.querySelector("#close-chapters");
  const chaptersBackdrop = document.querySelector("#chapters-backdrop");
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
  const bookProcessingProgress = document.querySelector("#book-processing-progress");
  const bookProcessingPercent = document.querySelector("#book-processing-percent");
  const processingControls = document.querySelector("#processing-controls");
  const processingControlNote = document.querySelector("#processing-control-note");
  const pauseProcessing = document.querySelector("#pause-processing");
  const resumeProcessing = document.querySelector("#resume-processing");
  const cancelProcessing = document.querySelector("#cancel-processing");
  const extendEndPage = document.querySelector("#extend-end-page");
  extendEndPage.type = "range";
  const extendEndPageValue = document.createElement("output");
  extendEndPageValue.className = "extend-page-slider__value";
  extendEndPage.insertAdjacentElement("beforebegin", extendEndPageValue);
  const extendProcessing = document.querySelector("#extend-processing");
  const appendPartFile = document.querySelector("#append-part-file");
  const appendPart = document.querySelector("#append-part");
  let chunks = [];
  let currentChunk = 0;
  let chapters = [];
  let selectedChapter = Math.max(0, Number(new URLSearchParams(window.location.search).get("chapter")) || 0);
  let pendingSeekSeconds = null;
  let lastPersistedAt = 0;
  let audioRetryAttempts = 0;
  let backgroundRefreshTimer = null;

  const setBookProcessingProgress = (progress) => {
    const percent = Math.max(0, Math.min(100, Number(progress?.progress_percent) || 0));
    bookProcessingProgress.querySelector("i").style.width = `${percent}%`;
    bookProcessingProgress.setAttribute("aria-valuenow", String(Math.round(percent)));
    bookProcessingPercent.textContent = `${Math.round(percent)}%`;
  };

  const savedVolume = Number(window.localStorage.getItem("ai-reader:volume"));
  const initialVolume = Number.isFinite(savedVolume) && savedVolume >= 0 && savedVolume <= 1
    ? savedVolume
    : 1;
  const setVolume = (value) => {
    const normalized = Math.max(0, Math.min(1, Number(value) || 0));
    audio.volume = normalized;
    volume.value = String(normalized);
    volumeValue.textContent = `${Math.round(normalized * 100)}%`;
    window.localStorage.setItem("ai-reader:volume", String(normalized));
  };
  setVolume(initialVolume);

  const setChapterSheetOpen = (open) => {
    chapterNavigation.classList.toggle("is-open", open);
    chaptersBackdrop.hidden = !open;
    openChapters.setAttribute("aria-expanded", String(open));
  };

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
      chapters = makeNavigableSections(progress.chapters);
      setBookProcessingProgress(progress);
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
  const makeNavigableSections = (sourceChapters) => {
    if (sourceChapters.length !== 1) return sourceChapters;
    const [chapter] = sourceChapters;
    const pageCount = chapter.end_page - chapter.start_page + 1;
    if (pageCount < 4 || chapter.chunks.length < 2) return sourceChapters;

    const sections = [];
    const pagesPerSection = 2;
    for (let startPage = chapter.start_page; startPage <= chapter.end_page; startPage += pagesPerSection) {
      const endPage = Math.min(startPage + pagesPerSection - 1, chapter.end_page);
      const sectionChunks = chapter.chunks.filter((chunk) => chunk.page_number >= startPage && chunk.page_number <= endPage);
      if (!sectionChunks.length) continue;
      const readyChunks = sectionChunks.filter((chunk) => chunk.status === "ready").length;
      const status = sectionChunks.some((chunk) => chunk.status === "failed") ? "failed"
        : sectionChunks.some((chunk) => chunk.status === "processing") ? "processing"
        : readyChunks === sectionChunks.length ? "ready" : "queued";
      sections.push({
        ...chapter,
        chapter_index: sections.length,
        title: `Section ${sections.length + 1}`,
        start_page: startPage,
        end_page: endPage,
        chunks: sectionChunks,
        total_chunks: sectionChunks.length,
        ready_chunks: readyChunks,
        status,
      });
    }
    return sections.length > 1 ? sections : sourceChapters;
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
    chapterSummary.textContent = `Viewing section ${selected.chapter_index + 1} · pages ${selected.start_page}–${selected.end_page} · ${selected.ready_chunks}/${selected.total_chunks} chunks ready`;
    chapterList.innerHTML = chapters.map((chapter, index) => `
      <li><button type="button" class="chapter-item${index === selectedChapter ? " is-selected" : ""}" data-chapter-index="${index}" aria-current="${index === selectedChapter ? "true" : "false"}"${chapter.ready_chunks ? "" : " disabled"} title="${chapter.ready_chunks ? "Play this section" : `This section is ${statusLabel(chapter.status).toLowerCase()}`} "><span><b>SEC ${String(chapter.chapter_index + 1).padStart(2, "0")}</b><strong>${escapeHtml(chapter.title)}</strong></span><small class="status--${escapeHtml(chapter.status)}">${statusLabel(chapter.status)} · ${chapter.ready_chunks}/${chapter.total_chunks}</small></button></li>
    `).join("");
    const nextReady = chapters.flatMap((chapter) => chapter.chunks.map((chunk) => ({ chapter, chunk }))).find(({ chunk }) => chunk.status === "ready");
    nextAvailableChunk.textContent = nextReady
      ? `Next available chunk: Section ${nextReady.chapter.chapter_index + 1}, segment ${nextReady.chunk.chunk_index + 1}.`
      : "The next available chunk is still being generated.";
    previousChapter.disabled = selectedChapter === 0;
    nextChapter.disabled = selectedChapter === chapters.length - 1;
    chapterList.querySelectorAll("[data-chapter-index]").forEach((button) => button.addEventListener("click", () => {
      selectedChapter = Number(button.dataset.chapterIndex);
      window.history.replaceState({}, "", `${window.location.pathname}?chapter=${selectedChapter}`);
      drawChapterNavigation();
      playSelectedChapter();
      setChapterSheetOpen(false);
    }));
  };
  const chapterIndexForAudioChunk = (chunk) => {
    if (!chunk) return -1;
    let sourceOffset = 0;
    return chapters.findIndex((chapter) => {
      const start = sourceOffset * 1000;
      sourceOffset += chapter.chunks.length;
      const end = sourceOffset * 1000;
      const found = chunk.chunk_index >= start && chunk.chunk_index < end;
      return found;
    });
  };
  const playSelectedChapter = () => {
    const offset = chapters.slice(0, selectedChapter).reduce((total, chapter) => total + chapter.chunks.length, 0);
    const end = offset + chapters[selectedChapter].chunks.length;
    const index = chunks.findIndex((chunk) => chunk.chunk_index >= offset * 1000 && chunk.chunk_index < end * 1000);
    if (index >= 0) selectChunk(index, !audio.paused);
    else statusMessage.textContent = "Audio for this section is still being prepared.";
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
    const chapterIndex = chapterIndexForAudioChunk(chunk);
    if (chapterIndex >= 0 && chapterIndex !== selectedChapter) {
      selectedChapter = chapterIndex;
      window.history.replaceState({}, "", `${window.location.pathname}?chapter=${selectedChapter}`);
      drawChapterNavigation();
    }
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
  openChapters.addEventListener("click", () => setChapterSheetOpen(true));
  closeChapters.addEventListener("click", () => setChapterSheetOpen(false));
  chaptersBackdrop.addEventListener("click", () => setChapterSheetOpen(false));
  previous.addEventListener("click", () => selectChunk(currentChunk - 1, !audio.paused));
  next.addEventListener("click", () => selectChunk(currentChunk + 1, !audio.paused));
  previousChapter.addEventListener("click", () => {
    selectedChapter -= 1;
    window.history.replaceState({}, "", `${window.location.pathname}?chapter=${selectedChapter}`);
    drawChapterNavigation();
    if (chapters[selectedChapter]?.ready_chunks) playSelectedChapter();
  });
  nextChapter.addEventListener("click", () => {
    selectedChapter += 1;
    window.history.replaceState({}, "", `${window.location.pathname}?chapter=${selectedChapter}`);
    drawChapterNavigation();
    if (chapters[selectedChapter]?.ready_chunks) playSelectedChapter();
  });
  skipButtons.forEach((button) => button.addEventListener("click", () => {
    audio.currentTime = Math.max(0, Math.min(duration(), audio.currentTime + Number(button.dataset.skip)));
  }));
  speed.addEventListener("change", () => { audio.playbackRate = Number(speed.value); });
  volume.addEventListener("input", () => setVolume(volume.value));
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
    chapters = makeNavigableSections(progress.chapters);
    setBookProcessingProgress(progress);
    title.textContent = book.title;
    author.textContent = book.author;
    cover.className = `book-cover book-cover--${coverVariant(book.title)}`;
    cover.querySelector("b").textContent = book.title.slice(0, 1).toUpperCase() || "A";
    processingControls.hidden = false;
    extendEndPage.max = String(book.page_count);
    extendEndPage.value = String(book.processing_end_page);
    const processPayload = (endPage = book.processing_end_page) => ({ reading_language: book.reading_language, voice: book.tts_voice, speed: book.tts_speed, style: book.tts_style, code_mode: book.code_mode, table_mode: book.table_mode, diagram_mode: book.diagram_mode, formula_mode: book.formula_mode, start_page: book.processing_start_page, end_page: Number(endPage) });
    const updateProcessingControls = (current) => {
      const paused = current.processing_paused;
      processingControlNote.textContent = paused ? "Processing is paused. Ready audio remains available." : `Pages ${current.processing_start_page}–${current.processing_end_page} of ${current.page_count} are selected.`;
      pauseProcessing.hidden = paused;
      resumeProcessing.hidden = !paused;
      extendEndPage.max = String(current.page_count);
      extendEndPage.value = String(current.processing_end_page);
      extendEndPageValue.textContent = extendEndPage.value;
    };
    updateProcessingControls(book);
    extendEndPage.addEventListener("input", () => { extendEndPageValue.textContent = extendEndPage.value; });
    pauseProcessing.addEventListener("click", async () => {
      const response = await fetch(`/api/v1/books/${encodeURIComponent(bookId)}/pause`, { method: "POST" });
      if (!response.ok) return;
      updateProcessingControls(await response.json());
    });
    resumeProcessing.addEventListener("click", async () => {
      const response = await fetch(`/api/v1/books/${encodeURIComponent(bookId)}/process`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(processPayload()) });
      if (!response.ok) return;
      updateProcessingControls(await response.json());
    });
    cancelProcessing.addEventListener("click", async () => {
      if (!window.confirm("Stop pending processing? Existing audio will be kept.")) return;
      const response = await fetch(`/api/v1/books/${encodeURIComponent(bookId)}/cancel`, { method: "POST" });
      if (!response.ok) return;
      const updated = await response.json();
      processingControlNote.textContent = "Pending processing was cancelled. You can choose a range and start again.";
      pauseProcessing.hidden = true;
      resumeProcessing.hidden = true;
      extendEndPage.value = String(updated.processing_end_page);
    });
    extendProcessing.addEventListener("click", async () => {
      const response = await fetch(`/api/v1/books/${encodeURIComponent(bookId)}/process`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(processPayload(extendEndPage.value)) });
      if (!response.ok) return;
      updateProcessingControls(await response.json());
    });
    appendPart.addEventListener("click", async () => {
      const file = appendPartFile.files[0];
      if (!file) { processingControlNote.textContent = "Choose the next PDF before adding a part."; return; }
      appendPart.disabled = true;
      processingControlNote.textContent = "Uploading continuation PDF…";
      try {
        const data = new FormData();
        data.append("file", file);
        const upload = await fetch(`/api/v1/books/${encodeURIComponent(bookId)}/parts`, { method: "POST", body: data });
        if (!upload.ok) throw new Error("Unable to add continuation PDF");
        const part = await upload.json();
        const partEndPage = part.global_start_page + part.page_count - 1;
        const estimateResponse = await fetch(`/api/v1/books/${encodeURIComponent(bookId)}/estimate?start_page=${part.global_start_page}&end_page=${partEndPage}`);
        const estimate = estimateResponse.ok ? await estimateResponse.json() : null;
        const estimateText = estimate
          ? ` Estimated AI cost: $${Number(estimate.estimated_ai_cost_usd).toFixed(4)}; audio: ${formatDuration(Number(estimate.estimated_audio_seconds))}.`
          : "";
        if (!window.confirm(`Part ${part.sequence} has ${part.page_count} pages.${estimateText} Start processing it now?`)) {
          processingControlNote.textContent = `Part ${part.sequence} is stored and can be processed later.`;
          return;
        }
        const process = await fetch(`/api/v1/books/${encodeURIComponent(bookId)}/parts/${encodeURIComponent(part.id)}/process`, { method: "POST" });
        if (!process.ok) throw new Error("Unable to start the continuation");
        const updated = await process.json();
        updateProcessingControls(updated);
        processingControlNote.textContent = `Part ${part.sequence} is being processed after the existing audio.`;
      } catch (error) {
        processingControlNote.textContent = error.message || "Unable to add continuation PDF.";
      } finally { appendPart.disabled = false; }
    });
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
    const active = books.filter((book) => book.status === "processing" && Number(book.progress_percent) < 100);
    panel.hidden = active.length === 0;
    panel.innerHTML = active.map((book) => {
      const percent = Math.max(0, Math.min(100, Number(book.progress_percent) || 0));
      return `<a href="/books/${encodeURIComponent(book.id)}">Processing in background · ${escapeHtml(book.title)} · ${Math.round(percent)}%<span class="background-progress" aria-hidden="true"><i style="width:${percent}%"></i></span></a>`;
    }).join("");
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
