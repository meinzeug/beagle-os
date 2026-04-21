// Beagle OS Gaming Kiosk - MIT Licensed
'use strict';

const state = {
  mode: 'library',
  search: '',
  genre: '',
  sort: 'popular',
  catalogCategory: '',
  page: 1,
  pageSize: 24,
  gfnOnly: true,
  games: [],
  library: { games: [], logged_in: false },
  sessionState: { gfnLoggedIn: false },
  gfnLaunchState: 'idle',
  catalogRefreshState: 'idle',
  enrollment: {
    status: 'idle',
    required: false,
    enrolled: false,
    endpointId: '',
    managerUrl: '',
    lastError: '',
    lastAttemptAt: '',
  },
  activeGame: null,
  currentEntries: [],
  focusIndex: 0,
  lastGamepadActionAt: 0,
};

const elements = {
  tabs: Array.from(document.querySelectorAll('.nav-tab')),
  modeTitle: document.getElementById('mode-title'),
  modeDescription: document.getElementById('mode-description'),
  resultCount: document.getElementById('result-count'),
  catalogHomeButton: document.getElementById('catalog-home-button'),
  catalogRefreshButton: document.getElementById('catalog-refresh-button'),
  catalogRefreshStatus: document.getElementById('catalog-refresh-status'),
  catalogHome: document.getElementById('catalog-home'),
  grid: document.getElementById('game-grid'),
  pagination: document.getElementById('catalog-pagination'),
  emptyState: document.getElementById('empty-state'),
  emptyStateText: document.getElementById('empty-state-text'),
  search: document.getElementById('search-input'),
  genre: document.getElementById('genre-filter'),
  sort: document.getElementById('sort-filter'),
  gfnOnly: document.getElementById('gfn-only-toggle'),
  loginState: document.getElementById('login-state'),
  loginButton: document.getElementById('login-button'),
  enrollmentState: document.getElementById('enrollment-state'),
  enrollmentEndpoint: document.getElementById('enrollment-endpoint'),
  enrollmentButton: document.getElementById('enrollment-button'),
  modal: document.getElementById('game-modal'),
  modalCover: document.getElementById('modal-cover'),
  modalGenre: document.getElementById('modal-genre'),
  modalTitle: document.getElementById('modal-title'),
  modalDescription: document.getElementById('modal-description'),
  modalPlayButton: document.getElementById('modal-play-button'),
  modalLoginButton: document.getElementById('modal-login-button'),
  purchasePlayButton: document.getElementById('purchase-play-button'),
  purchaseHint: document.getElementById('purchase-hint'),
  storeList: document.getElementById('store-list'),
  systemRequirements: document.getElementById('system-requirements'),
  heroArt: document.getElementById('hero-art'),
};

function normalizeGenreToken(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function gameGenreTokens(game) {
  return String(game?.genre || '')
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function isCatalogHomeView() {
  return state.mode === 'catalog' && !state.catalogCategory && !state.search && !state.genre && state.sort === 'popular';
}

function formatOwnedText(game) {
  return game.owned ? 'Bereits in deiner Bibliothek' : 'Noch nicht in deiner Bibliothek';
}

function currentModeMeta() {
  if (state.mode === 'catalog') {
    if (isCatalogHomeView()) {
      return {
        title: 'Spielekatalog',
        description: 'Kategorie waehlen und danach Seite fuer Seite durch GFN-kompatible Spiele stoebern.',
      };
    }
    return {
      title: 'Spielekatalog',
      description: 'GFN-kompatible Spiele entdecken, vergleichen und direkt im passenden Store kaufen.',
    };
  }
  return {
    title: 'Meine Bibliothek',
    description: 'Bereits gekaufte Spiele direkt ueber GeForce NOW starten.',
  };
}

function activeSort() {
  if (state.mode === 'catalog' && state.catalogCategory === 'new' && state.sort === 'popular') {
    return 'new';
  }
  return state.sort;
}

function compareBySort(left, right) {
  switch (activeSort()) {
    case 'title':
      return String(left.title).localeCompare(String(right.title), 'de');
    case 'new':
      return Number(right.release_year || 0) - Number(left.release_year || 0);
    case 'price': {
      const priceOf = (game) => {
        const first = Array.isArray(game.stores) ? game.stores[0] : null;
        return Number(String(first?.price || '').replace(/[^\d.,]/g, '').replace(',', '.')) || Number.MAX_SAFE_INTEGER;
      };
      return priceOf(left) - priceOf(right);
    }
    case 'popular':
    default:
      return Number(right.popularity || 0) - Number(left.popularity || 0);
  }
}

function modeGames() {
  if (state.mode === 'library') {
    return Array.isArray(state.library.games) ? state.library.games : [];
  }
  return Array.isArray(state.games) ? state.games : [];
}

function catalogCategoryDefinitions() {
  const games = Array.isArray(state.games) ? state.games : [];
  const currentYear = new Date().getFullYear();
  const recentCount = games.filter((game) => Number(game.release_year || 0) >= currentYear - 1).length;
  const counts = new Map();

  games.forEach((game) => {
    gameGenreTokens(game).forEach((genre) => {
      if (genre === 'GFN Compatible') {
        return;
      }
      counts.set(genre, (counts.get(genre) || 0) + 1);
    });
  });

  const genres = [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || String(left[0]).localeCompare(String(right[0]), 'de'))
    .slice(0, 8)
    .map(([label, count]) => ({
      id: `genre:${normalizeGenreToken(label)}`,
      label,
      description: `${count} Spiele`,
      count,
    }));

  return [
    {
      id: 'all',
      label: 'Alle Spiele',
      description: `${games.length} GFN-kompatible Titel`,
      count: games.length,
    },
    {
      id: 'popular',
      label: 'Beliebt',
      description: 'Schneller Einstieg mit den gefragtesten Titeln',
      count: games.length,
    },
    {
      id: 'new',
      label: 'Neu',
      description: recentCount > 0 ? `${recentCount} neuere Titel` : 'Neu sortiert anzeigen',
      count: recentCount || games.length,
    },
    ...genres,
  ];
}

function categoryMatchesGame(game) {
  if (state.mode !== 'catalog') {
    return true;
  }
  if (!state.catalogCategory || state.catalogCategory === 'all' || state.catalogCategory === 'popular') {
    return true;
  }
  if (state.catalogCategory === 'new') {
    return true;
  }
  if (!state.catalogCategory.startsWith('genre:')) {
    return true;
  }
  const wanted = state.catalogCategory.slice('genre:'.length);
  return gameGenreTokens(game).some((genre) => normalizeGenreToken(genre) === wanted);
}

function filteredGames() {
  return modeGames()
    .filter((game) => (state.mode === 'catalog' ? !game.library_only : true))
    .filter((game) => categoryMatchesGame(game))
    .filter((game) => (state.gfnOnly ? game.geforce_now_supported !== false : true))
    .filter((game) => (!state.genre ? true : String(game.genre || '') === state.genre))
    .filter((game) => {
      const haystack = [game.title, game.description, game.genre].join(' ').toLowerCase();
      return haystack.includes(state.search.toLowerCase());
    })
    .sort(compareBySort);
}

function paginatedGames(items) {
  const totalPages = Math.max(1, Math.ceil(items.length / state.pageSize));
  const page = Math.min(state.page, totalPages);
  const start = (page - 1) * state.pageSize;
  return {
    items: items.slice(start, start + state.pageSize),
    page,
    totalPages,
  };
}

function renderGenreOptions() {
  const genres = [...new Set(modeGames().map((game) => game.genre).filter(Boolean))].sort((a, b) =>
    String(a).localeCompare(String(b), 'de')
  );
  const existingValue = elements.genre.value;
  elements.genre.innerHTML = '<option value="">Alle Genres</option>';
  for (const genre of genres) {
    const option = document.createElement('option');
    option.value = genre;
    option.textContent = genre;
    elements.genre.append(option);
  }
  elements.genre.value = existingValue;
}

function updateModeMeta() {
  const meta = currentModeMeta();
  elements.modeTitle.textContent = meta.title;
  elements.modeDescription.textContent = meta.description;
  elements.tabs.forEach((tab) => tab.classList.toggle('is-active', tab.dataset.mode === state.mode));
  elements.catalogHomeButton.classList.toggle('hidden', state.mode !== 'catalog' || isCatalogHomeView());
}

function updateLoginState() {
  if (state.gfnLaunchState === 'launching') {
    elements.loginState.textContent = 'GeForce NOW wird gestartet...';
    elements.loginButton.textContent = 'GFN startet...';
    elements.loginButton.disabled = true;
    return;
  }
  if (state.gfnLaunchState === 'handoff') {
    elements.loginState.textContent = 'GeForce NOW wird in den Vordergrund gebracht...';
    elements.loginButton.textContent = 'GFN laeuft';
    elements.loginButton.disabled = true;
    return;
  }
  if (state.gfnLaunchState === 'still-starting') {
    elements.loginState.textContent = 'GeForce NOW braucht noch einen Moment. Bitte warten.';
    elements.loginButton.textContent = 'GFN startet...';
    elements.loginButton.disabled = true;
    return;
  }

  elements.loginButton.disabled = false;
  const loggedIn = Boolean(state.library.logged_in || state.sessionState.gfnLoggedIn);
  if (loggedIn) {
    elements.loginState.textContent = 'GeForce NOW Login erkannt.';
    elements.loginButton.textContent = 'GFN erneut oeffnen';
  } else {
    elements.loginState.textContent = 'Bitte zuerst mit GeForce NOW einloggen.';
    elements.loginButton.textContent = 'Mit GeForce NOW einloggen';
  }
}

function updateCatalogRefreshState(message) {
  if (state.catalogRefreshState === 'refreshing') {
    elements.catalogRefreshButton.disabled = true;
    elements.catalogRefreshStatus.textContent = 'Katalog wird aktualisiert...';
    return;
  }

  elements.catalogRefreshButton.disabled = false;
  elements.catalogRefreshStatus.textContent = message || 'Katalog manuell neu laden';
}

function updateEnrollmentState() {
  const enrollment = state.enrollment || {};
  const endpointLabel = enrollment.endpointId ? `Endpoint-ID: ${enrollment.endpointId}` : '';
  elements.enrollmentEndpoint.textContent = endpointLabel;

  if (enrollment.enrolled) {
    elements.enrollmentState.textContent = 'Kiosk ist mit Beagle gekoppelt.';
    elements.enrollmentButton.disabled = true;
    elements.enrollmentButton.textContent = 'Enrollment abgeschlossen';
    return;
  }

  if (enrollment.status === 'in-progress') {
    elements.enrollmentState.textContent = 'Enrollment läuft…';
    elements.enrollmentButton.disabled = true;
    elements.enrollmentButton.textContent = 'Bitte warten…';
    return;
  }

  if (enrollment.status === 'error') {
    elements.enrollmentState.textContent = enrollment.lastError
      ? `Enrollment fehlgeschlagen: ${enrollment.lastError}`
      : 'Enrollment fehlgeschlagen.';
    elements.enrollmentButton.disabled = false;
    elements.enrollmentButton.textContent = 'Erneut versuchen';
    return;
  }

  if (enrollment.required) {
    elements.enrollmentState.textContent = 'Enrollment steht aus. Koppeln vor dem ersten Einsatz empfohlen.';
    elements.enrollmentButton.disabled = false;
    elements.enrollmentButton.textContent = 'Enrollment starten';
    return;
  }

  elements.enrollmentState.textContent = 'Kein Enrollment-Token hinterlegt.';
  elements.enrollmentButton.disabled = true;
  elements.enrollmentButton.textContent = 'Kein Token vorhanden';
}

async function startEnrollment() {
  try {
    elements.enrollmentButton.disabled = true;
    await window.beagleKiosk.enrollNow();
  } catch (error) {
    console.error(error);
    alert(`Enrollment konnte nicht gestartet werden: ${error.message}`);
  }
}

function createStoreButtons(game) {
  const stores = Array.isArray(game.stores) ? game.stores : [];
  elements.storeList.innerHTML = '';

  if (stores.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'inline-note';
    empty.textContent = 'Keine Store-Links vorhanden.';
    elements.storeList.append(empty);
    return;
  }

  for (const store of stores) {
    const wrapper = document.createElement('button');
    wrapper.type = 'button';
    wrapper.className = 'store-button';
    wrapper.innerHTML = `
      <strong>${store.name}</strong>
      <span>${store.price || 'Preis folgt'}</span>
    `;
    wrapper.addEventListener('click', async () => {
      try {
        await window.beagleKiosk.openStore({ game, store });
        elements.purchaseHint.classList.remove('hidden');
      } catch (error) {
        console.error(error);
        alert(`Store konnte nicht geoeffnet werden: ${error.message}`);
      }
    });
    elements.storeList.append(wrapper);
  }
}

function createSystemRequirements(game) {
  const lines = Array.isArray(game.system_requirements)
    ? game.system_requirements
    : ['Streaming ueber GeForce NOW', 'Controller- und Maussteuerung'];
  elements.systemRequirements.innerHTML = '';
  for (const line of lines) {
    const item = document.createElement('li');
    item.textContent = line;
    elements.systemRequirements.append(item);
  }
}

function openModal(game) {
  state.activeGame = game;
  elements.modalCover.src = game.cover_url || elements.heroArt.src || '';
  elements.modalCover.alt = game.title || 'Spielcover';
  elements.modalGenre.textContent = game.genre || 'Unbekannt';
  elements.modalTitle.textContent = game.title || 'Unbenanntes Spiel';
  elements.modalDescription.textContent = game.description || 'Keine Beschreibung vorhanden.';
  elements.modalPlayButton.textContent = game.owned ? 'Jetzt spielen' : 'Spiel in GeForce NOW starten';
  elements.modalLoginButton.classList.toggle('hidden', Boolean(state.library.logged_in || state.sessionState.gfnLoggedIn));
  elements.purchaseHint.classList.toggle('hidden', game.owned);
  createStoreButtons(game);
  createSystemRequirements(game);
  elements.modal.showModal();
}

function renderCard(game, index) {
  const article = document.createElement('article');
  article.className = 'game-card focus-card';
  article.tabIndex = 0;
  article.dataset.index = String(index);
  article.innerHTML = `
    <img class="game-card-cover" src="${game.cover_url || elements.heroArt.src || ''}" alt="${game.title || ''}" />
    <div class="game-card-body">
      <div class="game-card-meta">
        <span class="chip">${game.genre || 'Unbekannt'}</span>
        <span class="chip chip-green">${game.geforce_now_supported === false ? 'Kein GFN' : 'GFN'}</span>
      </div>
      <h3>${game.title || 'Unbenanntes Spiel'}</h3>
      <p>${game.description || ''}</p>
      <div class="game-card-footer">
        <span class="owned-label">${formatOwnedText(game)}</span>
        <div class="card-actions">
          ${game.owned ? '<button class="button button-primary play-now">Jetzt spielen</button>' : '<button class="button details-button">Details</button>'}
        </div>
      </div>
    </div>
  `;

  article.addEventListener('focus', () => {
    state.focusIndex = index;
    updateFocusedCard();
  });

  article.addEventListener('click', (event) => {
    if (event.target.closest('.play-now')) {
      void launchGame(game);
      return;
    }
    openModal(game);
  });

  article.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (game.owned) {
        void launchGame(game);
      } else {
        openModal(game);
      }
    }
  });

  return article;
}

function renderCategoryCard(category, index) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'catalog-category-card focus-card';
  button.tabIndex = 0;
  button.dataset.index = String(index);
  button.innerHTML = `
    <span class="catalog-category-label">${category.label}</span>
    <strong>${category.count}</strong>
    <p>${category.description}</p>
  `;
  button.addEventListener('focus', () => {
    state.focusIndex = index;
    updateFocusedCard();
  });
  button.addEventListener('click', () => {
    selectCatalogCategory(category.id);
  });
  button.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      selectCatalogCategory(category.id);
    }
  });
  return button;
}

function currentCards() {
  if (!elements.catalogHome.classList.contains('hidden')) {
    return Array.from(elements.catalogHome.querySelectorAll('.focus-card'));
  }
  return Array.from(elements.grid.querySelectorAll('.focus-card'));
}

function updateFocusedCard() {
  const cards = currentCards();
  cards.forEach((card, index) => card.classList.toggle('is-focused', index === state.focusIndex));
  if (cards[state.focusIndex]) {
    cards[state.focusIndex].focus({ preventScroll: true });
  }
}

function selectCatalogCategory(categoryId) {
  state.catalogCategory = categoryId;
  state.page = 1;
  state.focusIndex = 0;
  renderGrid();
}

function goToCatalogHome() {
  state.catalogCategory = '';
  state.search = '';
  state.genre = '';
  state.sort = 'popular';
  state.page = 1;
  state.focusIndex = 0;
  elements.search.value = '';
  elements.genre.value = '';
  elements.sort.value = 'popular';
  renderGrid();
}

function renderCatalogHome() {
  const categories = catalogCategoryDefinitions();
  state.currentEntries = categories.map((category) => ({ type: 'category', category }));
  elements.catalogHome.innerHTML = '';
  elements.catalogHome.classList.remove('hidden');
  elements.grid.classList.add('hidden');
  elements.pagination.classList.add('hidden');
  elements.emptyState.classList.add('hidden');
  elements.resultCount.textContent = `${state.games.length} Spiele im Katalog`;

  categories.forEach((category, index) => {
    elements.catalogHome.append(renderCategoryCard(category, index));
  });
}

function changePage(nextPage) {
  const allItems = filteredGames();
  const { totalPages } = paginatedGames(allItems);
  const clamped = Math.max(1, Math.min(totalPages, nextPage));
  if (clamped === state.page) {
    return;
  }
  state.page = clamped;
  state.focusIndex = 0;
  renderGrid();
}

function renderPagination(totalPages, page) {
  elements.pagination.innerHTML = '';
  if (state.mode !== 'catalog' || isCatalogHomeView() || totalPages <= 1) {
    elements.pagination.classList.add('hidden');
    return;
  }

  const summary = document.createElement('span');
  summary.className = 'pagination-summary';
  summary.textContent = `Seite ${page} von ${totalPages}`;
  elements.pagination.append(summary);

  const prev = document.createElement('button');
  prev.type = 'button';
  prev.className = 'pagination-button';
  prev.textContent = 'Zurueck';
  prev.disabled = page <= 1;
  prev.addEventListener('click', () => changePage(page - 1));
  elements.pagination.append(prev);

  const maxButtons = 5;
  const startPage = Math.max(1, Math.min(page - 2, totalPages - maxButtons + 1));
  const endPage = Math.min(totalPages, startPage + maxButtons - 1);

  for (let currentPage = startPage; currentPage <= endPage; currentPage += 1) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `pagination-button${currentPage === page ? ' is-active' : ''}`;
    button.textContent = String(currentPage);
    button.addEventListener('click', () => changePage(currentPage));
    elements.pagination.append(button);
  }

  const next = document.createElement('button');
  next.type = 'button';
  next.className = 'pagination-button';
  next.textContent = 'Weiter';
  next.disabled = page >= totalPages;
  next.addEventListener('click', () => changePage(page + 1));
  elements.pagination.append(next);
  elements.pagination.classList.remove('hidden');
}

function renderGrid() {
  updateModeMeta();
  updateLoginState();
  if (isCatalogHomeView()) {
    console.log(
      'render-grid',
      JSON.stringify({
        mode: state.mode,
        sourceCount: modeGames().length,
        itemCount: 0,
        filteredCount: 0,
        libraryCount: Array.isArray(state.library.games) ? state.library.games.length : 0,
        catalogCount: Array.isArray(state.games) ? state.games.length : 0,
        loggedIn: Boolean(state.library.logged_in || state.sessionState.gfnLoggedIn),
        genre: state.genre,
        search: state.search,
        gfnOnly: state.gfnOnly,
        catalogCategory: state.catalogCategory,
        page: state.page,
        totalPages: 0,
        home: true,
      })
    );
    renderCatalogHome();
    if (state.focusIndex >= state.currentEntries.length) {
      state.focusIndex = Math.max(0, state.currentEntries.length - 1);
    }
    updateFocusedCard();
    return;
  }

  const items = filteredGames();
  const pagination = paginatedGames(items);
  state.page = pagination.page;
  state.currentEntries = pagination.items.map((game) => ({ type: 'game', game }));
  console.log(
    'render-grid',
    JSON.stringify({
      mode: state.mode,
      sourceCount: modeGames().length,
      itemCount: pagination.items.length,
      filteredCount: items.length,
      libraryCount: Array.isArray(state.library.games) ? state.library.games.length : 0,
      catalogCount: Array.isArray(state.games) ? state.games.length : 0,
      loggedIn: Boolean(state.library.logged_in || state.sessionState.gfnLoggedIn),
      genre: state.genre,
      search: state.search,
      gfnOnly: state.gfnOnly,
      catalogCategory: state.catalogCategory,
      page: pagination.page,
      totalPages: pagination.totalPages,
      home: false,
    })
  );

  elements.catalogHome.classList.add('hidden');
  elements.grid.classList.remove('hidden');
  elements.grid.innerHTML = '';
  elements.resultCount.textContent =
    state.mode === 'catalog'
      ? `${items.length} Spiele • Seite ${pagination.page}/${pagination.totalPages}`
      : `${items.length} Spiele`;
  elements.emptyState.classList.toggle('hidden', items.length > 0);

  if (items.length === 0) {
    if (state.mode === 'library' && !(state.library.logged_in || state.sessionState.gfnLoggedIn)) {
      elements.emptyStateText.textContent = 'Noch keine Bibliothek geladen. Bitte zuerst mit GeForce NOW einloggen.';
    } else {
      elements.emptyStateText.textContent = 'Aendere Suche oder Filter, oder melde dich zuerst bei GeForce NOW an.';
    }
  }

  pagination.items.forEach((game, index) => elements.grid.append(renderCard(game, index)));
  renderPagination(pagination.totalPages, pagination.page);

  if (state.focusIndex >= pagination.items.length) {
    state.focusIndex = Math.max(0, pagination.items.length - 1);
  }
  updateFocusedCard();
}

async function launchGame(game) {
  try {
    await window.beagleKiosk.launchGame(game);
  } catch (error) {
    console.error(error);
    alert(`GeForce NOW konnte nicht gestartet werden: ${error.message}`);
  }
}

async function startLogin() {
  try {
    state.gfnLaunchState = 'launching';
    updateLoginState();
    await window.beagleKiosk.startLogin();
  } catch (error) {
    state.gfnLaunchState = 'idle';
    updateLoginState();
    console.error(error);
    alert(`GFN Login konnte nicht gestartet werden: ${error.message}`);
  }
}

async function refreshCatalog() {
  try {
    state.catalogRefreshState = 'refreshing';
    updateCatalogRefreshState();
    await window.beagleKiosk.refreshCatalog();
    state.catalogRefreshState = 'idle';
    updateCatalogRefreshState('Katalog aktualisiert.');
  } catch (error) {
    state.catalogRefreshState = 'idle';
    updateCatalogRefreshState('Aktualisierung fehlgeschlagen.');
    console.error(error);
    alert(`Katalog konnte nicht aktualisiert werden: ${error.message}`);
  }
}

function switchMode(nextMode) {
  state.mode = nextMode;
  state.page = 1;
  state.focusIndex = 0;
  renderGenreOptions();
  if (state.genre && !Array.from(elements.genre.options).some((option) => option.value === state.genre)) {
    state.genre = '';
    elements.genre.value = '';
  }
  renderGrid();
}

function handleGridKeyboard(event) {
  if (elements.modal.open) {
    if (event.key === 'Escape') {
      elements.modal.close();
    }
    return;
  }

  const cards = currentCards();
  if (cards.length === 0) {
    if (event.key.toLowerCase() === 'l') {
      void startLogin();
      return;
    }
    if (event.key === 'PageDown') {
      changePage(state.page + 1);
      return;
    }
    if (event.key === 'PageUp') {
      changePage(state.page - 1);
    }
    return;
  }

  const columns = Math.max(1, Math.round((elements.catalogHome.classList.contains('hidden') ? elements.grid : elements.catalogHome).clientWidth / 320));

  switch (event.key) {
    case 'ArrowRight':
      state.focusIndex = Math.min(cards.length - 1, state.focusIndex + 1);
      updateFocusedCard();
      break;
    case 'ArrowLeft':
      state.focusIndex = Math.max(0, state.focusIndex - 1);
      updateFocusedCard();
      break;
    case 'ArrowDown':
      state.focusIndex = Math.min(cards.length - 1, state.focusIndex + columns);
      updateFocusedCard();
      break;
    case 'ArrowUp':
      state.focusIndex = Math.max(0, state.focusIndex - columns);
      updateFocusedCard();
      break;
    case 'PageDown':
      changePage(state.page + 1);
      break;
    case 'PageUp':
      changePage(state.page - 1);
      break;
    case 'Tab':
      break;
    default:
      return;
  }
  event.preventDefault();
}

function handleGamepadAction(buttonPressed, callback) {
  const now = Date.now();
  if (!buttonPressed || now - state.lastGamepadActionAt < 180) {
    return;
  }
  state.lastGamepadActionAt = now;
  callback();
}

function pollGamepad() {
  const pads = navigator.getGamepads ? navigator.getGamepads() : [];
  const pad = Array.from(pads || []).find(Boolean);
  if (!pad) {
    requestAnimationFrame(pollGamepad);
    return;
  }

  const cards = currentCards();
  const activeContainer = elements.catalogHome.classList.contains('hidden') ? elements.grid : elements.catalogHome;
  const columns = Math.max(1, Math.round(activeContainer.clientWidth / 320));

  handleGamepadAction(pad.buttons[4]?.pressed, () => switchMode('library'));
  handleGamepadAction(pad.buttons[5]?.pressed, () => switchMode('catalog'));
  handleGamepadAction(pad.buttons[14]?.pressed, () => {
    state.focusIndex = Math.max(0, state.focusIndex - 1);
    updateFocusedCard();
  });
  handleGamepadAction(pad.buttons[15]?.pressed, () => {
    state.focusIndex = Math.min(cards.length - 1, state.focusIndex + 1);
    updateFocusedCard();
  });
  handleGamepadAction(pad.buttons[12]?.pressed, () => {
    state.focusIndex = Math.max(0, state.focusIndex - columns);
    updateFocusedCard();
  });
  handleGamepadAction(pad.buttons[13]?.pressed, () => {
    state.focusIndex = Math.min(cards.length - 1, state.focusIndex + columns);
    updateFocusedCard();
  });
  handleGamepadAction(pad.buttons[0]?.pressed, () => {
    const entry = state.currentEntries[state.focusIndex];
    if (!entry) {
      return;
    }
    if (entry.type === 'category') {
      selectCatalogCategory(entry.category.id);
      return;
    }
    if (entry.game.owned) {
      void launchGame(entry.game);
    } else {
      openModal(entry.game);
    }
  });
  handleGamepadAction(pad.buttons[1]?.pressed, () => {
    if (elements.modal.open) {
      elements.modal.close();
    }
  });

  requestAnimationFrame(pollGamepad);
}

function bindEvents() {
  elements.tabs.forEach((tab) => {
    tab.addEventListener('click', () => switchMode(tab.dataset.mode));
  });

  elements.search.addEventListener('input', () => {
    state.search = elements.search.value;
    state.page = 1;
    state.focusIndex = 0;
    renderGrid();
  });

  elements.genre.addEventListener('change', () => {
    state.genre = elements.genre.value;
    state.page = 1;
    state.focusIndex = 0;
    renderGrid();
  });

  elements.sort.addEventListener('change', () => {
    state.sort = elements.sort.value;
    state.page = 1;
    state.focusIndex = 0;
    renderGrid();
  });

  elements.gfnOnly.addEventListener('change', () => {
    state.gfnOnly = elements.gfnOnly.checked;
    state.page = 1;
    state.focusIndex = 0;
    renderGrid();
  });

  elements.catalogHomeButton.addEventListener('click', () => {
    goToCatalogHome();
  });

  elements.catalogRefreshButton.addEventListener('click', () => {
    void refreshCatalog();
  });

  elements.loginButton.addEventListener('click', () => {
    void startLogin();
  });

  elements.enrollmentButton.addEventListener('click', () => {
    void startEnrollment();
  });

  elements.modalPlayButton.addEventListener('click', () => {
    if (state.activeGame) {
      void launchGame(state.activeGame);
    }
  });

  elements.modalLoginButton.addEventListener('click', () => {
    void startLogin();
  });

  elements.purchasePlayButton.addEventListener('click', () => {
    if (state.activeGame) {
      void launchGame(state.activeGame);
    }
  });

  elements.modal.addEventListener('close', () => {
    state.activeGame = null;
    updateFocusedCard();
  });

  window.addEventListener('keydown', handleGridKeyboard);
}

function applyBootstrap(bootstrap) {
  state.games = bootstrap.games || [];
  state.library = bootstrap.library || { games: [], logged_in: false };
  state.sessionState = bootstrap.sessionState || state.sessionState;
  state.enrollment = bootstrap.enrollment || state.enrollment;
  if (state.library.logged_in || state.sessionState.gfnLoggedIn) {
    state.gfnLaunchState = 'idle';
  }
  state.gfnOnly = Boolean(bootstrap.config?.defaultFilterGfnOnly);
  console.log(
    'apply-bootstrap',
    JSON.stringify({
      catalogCount: Array.isArray(state.games) ? state.games.length : 0,
      libraryCount: Array.isArray(state.library.games) ? state.library.games.length : 0,
      loggedIn: Boolean(state.library.logged_in || state.sessionState.gfnLoggedIn),
      mode: state.mode,
    })
  );
  elements.gfnOnly.checked = state.gfnOnly;
  elements.heroArt.src = bootstrap.brandImageUrl || '';
  if (state.catalogRefreshState !== 'refreshing') {
    updateCatalogRefreshState();
  }
  updateEnrollmentState();
  renderGenreOptions();
  renderGrid();
}

async function init() {
  const bootstrap = await window.beagleKiosk.bootstrap();
  bindEvents();
  applyBootstrap(bootstrap);
  if (typeof window.beagleKiosk.onGfnStatus === 'function') {
    window.beagleKiosk.onGfnStatus((payload) => {
      state.gfnLaunchState = payload?.state || 'idle';
      updateLoginState();
    });
  }
  if (typeof window.beagleKiosk.onStateUpdate === 'function') {
    window.beagleKiosk.onStateUpdate((payload) => {
      applyBootstrap(payload || {});
    });
  }
  requestAnimationFrame(pollGamepad);
}

void init();
