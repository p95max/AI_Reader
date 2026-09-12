const pages = {
  "/library": {
    title: "Библиотека",
  },
  "/upload": {
    title: "Add Book",
  },
  "/settings": {
    title: "Настройки",
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
      title: "Книга и плеер",
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
        <nav class="navigation" aria-label="Основная навигация">${navigation()}</nav>
        <div class="sidebar-links"><a href="/library">▥ Stats</a><a href="/library">? Help</a><a href="/library">◉ GitHub</a></div>
        <p class="sidebar-quote">“READ.<br>LISTEN.<br>LEARN ANYWHERE.”</p>
        <small class="version">v0.1.0</small>
      </aside>
      <main class="app-shell">${content}</main>
      <nav class="mobile-navigation" aria-label="Мобильная навигация">${navigation()}</nav>
    </div>
`;
}

function statusLabel(status) {
  return {
    uploaded: "Загружена",
    queued: "В очереди",
    processing: "Обрабатывается",
    ready: "Готова",
    failed: "Ошибка",
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
        <span class="progress" aria-label="Готово ${progress}%"><span style="width: ${progress}%"></span></span>
        <span class="book-card__meta">◖ ${progress}% готово <b>•••</b></span>
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
    <div class="filters" role="group" aria-label="Фильтр книг">
      <button type="button" data-filter="all" class="is-active">All</button>
      <button type="button" data-filter="processing">Processing</button>
      <button type="button" data-filter="ready">Ready</button>
      <button type="button" disabled>Favorites</button>
    </div>
    <section id="book-list" class="book-list"><p class="placeholder">Загружаем библиотеку…</p></section>
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
      : '<a class="empty-library" href="/upload"><b>＋</b><span>Добавьте первую книгу</span><small>PDF → аудиокнига</small></a>';
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
    if (!response.ok) throw new Error("Не удалось загрузить книги");
    books = await response.json();
    draw();
  } catch (error) {
    list.innerHTML = '<p class="placeholder">Не удалось загрузить библиотеку. Попробуйте позже.</p>';
  }
}

function renderUpload() {
  document.querySelector("#app").innerHTML = shell(`
    <header class="topbar"><span>Web / Desktop (Add Book)</span><span>◉ USER⌄</span></header>
    <section class="feature-page add-book-page">
      <a class="back-link" href="/library">← Library</a><h1>ADD BOOK</h1><p>Turn your technical PDF into an audiobook.</p>
      <label class="drop-zone"><b>⇧</b><strong>Drag & drop your PDF here</strong><span>or tap to select a file</span><small>Max 200 MB · PDF only</small><input type="file" accept="application/pdf" hidden></label>
      <div class="mode-panel"><span>Processing mode</span><div class="mode-buttons"><button class="is-active">Balanced</button><button>Explain</button><button>Skip code</button></div></div>
      <div class="estimate"><span>Est. tokens<br><b>~ 184,000</b></span><span>Est. AI cost<br><b>~ $0.14</b></span><span>Est. audio<br><b>~ 10h 20m</b></span></div>
      <button class="button button--wide" disabled>START PROCESSING</button>
    </section>
  `);
}

function renderBookPage() {
  document.querySelector("#app").innerHTML = shell(`
    <header class="topbar"><span>Web / Desktop (Player)</span><span>◉ USER⌄</span></header>
    <section class="feature-page player-page"><a class="back-link" href="/library">← Library</a><div class="player-heading"><span class="book-cover book-cover--2"><b>A</b><i></i></span><div><h1>YOUR BOOK</h1><p>Техническая аудиокнига</p><span class="book-card__meta">◖ готовится · главы и плеер появятся здесь</span></div></div>
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
