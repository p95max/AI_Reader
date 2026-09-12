const pages = {
  "/library": {
    title: "Библиотека",
  },
  "/upload": {
    title: "Загрузить книгу",
    description: "Здесь появится загрузка PDF для обработки.",
  },
  "/settings": {
    title: "Настройки",
    description: "Здесь появятся настройки голоса и обработки технического контента.",
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
      description: "Здесь появятся детали книги, её прогресс и аудиоплеер.",
    };
  }
  return pages[pathname] ?? pages["/library"];
}

function navigation() {
  return ["/library", "/upload", "/settings"]
    .map((path) => {
      const label = pages[path].title;
      const active = path === window.location.pathname ? ' aria-current="page"' : "";
      return `<a href="${path}"${active}>${label}</a>`;
    })
    .join("");
}

function shell(content) {
  return `
  <main class="app-shell">
    <nav class="navigation" aria-label="Основная навигация">${navigation()}</nav>
    ${content}
  </main>
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

function renderBookCard(book) {
  const title = escapeHtml(book.title);
  const author = escapeHtml(book.author);
  const initial = title.slice(0, 1).toUpperCase() || "A";
  const progress = Math.max(0, Math.min(100, Number(book.progress_percent) || 0));
  return `
    <a class="book-card" href="/books/${encodeURIComponent(book.id)}">
      <span class="book-cover" aria-hidden="true">${initial}</span>
      <span class="book-card__body">
        <strong>${title}</strong>
        <span class="book-card__author">${author}</span>
        <span class="book-card__status status--${escapeHtml(book.status)}">${statusLabel(book.status)}</span>
        <span class="progress" aria-label="Готово ${progress}%"><span style="width: ${progress}%"></span></span>
        <span class="book-card__percent">${progress}%</span>
      </span>
    </a>
  `;
}

async function renderLibrary() {
  const app = document.querySelector("#app");
  app.innerHTML = shell(`
    <header class="library-header">
      <div><h1>Библиотека</h1><p>Ваши технические книги</p></div>
      <a class="button" href="/upload">Add Book</a>
    </header>
    <label class="search"><span>Поиск</span><input id="library-search" type="search" placeholder="Название книги" /></label>
    <div class="filters" role="group" aria-label="Фильтр книг">
      <button type="button" data-filter="all" class="is-active">All</button>
      <button type="button" data-filter="processing">Processing</button>
      <button type="button" data-filter="ready">Ready</button>
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
      : '<p class="placeholder">Книг по этому запросу нет.</p>';
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

if (window.location.pathname === "/library") {
  renderLibrary();
} else {
  const page = currentPage(window.location.pathname);
  document.querySelector("#app").innerHTML = shell(`
    <h1>${page.title}</h1>
    <section class="placeholder"><p>${page.description}</p></section>
  `);
}
