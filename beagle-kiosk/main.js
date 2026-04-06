// Beagle OS Gaming Kiosk - (c) Dennis Wicht / meinzeug - MIT Licensed
'use strict';

const { app, BrowserWindow, ipcMain, shell } = require('electron');
const fs = require('fs');
const fsp = require('fs/promises');
const os = require('os');
const path = require('path');
const { execFile, spawn } = require('child_process');
const { pathToFileURL } = require('url');

const APP_VERSION = app.getVersion();
const INSTALL_ROOT = process.env.BEAGLE_KIOSK_ROOT || '/opt/beagle-kiosk';
const CONFIG_PATH = path.join(INSTALL_ROOT, 'kiosk.conf');
const GAMES_PATH = path.join(INSTALL_ROOT, 'games.json');
const USER_LIBRARY_PATH = path.join(INSTALL_ROOT, 'user_library.json');
const COVER_CACHE_DIR = path.join(INSTALL_ROOT, 'assets', 'covers');
const BRAND_IMAGE_PATH = path.join(__dirname, 'assets', 'backgrounds', 'beagleos-gaming.png');
const DEFAULT_ALLOWED_STORE_DOMAINS = [
  'greenmangaming.com',
  'fanatical.com',
  'humblebundle.com',
  'store.epicgames.com',
];
const DEFAULT_GFN_STATE_ROOT =
  '/run/live/medium/pve-thin-client/state/gfn/home/.var/app/com.nvidia.geforcenow/.local/state/NVIDIA/GeForceNOW';

let mainWindow = null;
let purchaseWindow = null;
let gfnProcess = null;
let gfnWindowProbeToken = null;
let catalogRefreshPromise = null;
let sessionState = {
  gfnLoggedIn: false,
  lastKnownLibrarySync: null,
};

const defaultConfig = {
  GFN_BINARY: '/usr/local/lib/pve-thin-client/runtime/launch-geforcenow.sh',
  GFN_BINARY_FALLBACK: '/opt/nvidia/GeForceNOW.AppImage',
  GFN_LOGIN_ARGS: '',
  GFN_GAME_ARGS_TEMPLATE: '',
  GFN_GAME_URI_TEMPLATE: '',
  GFN_GAME_ID_FIELD: 'gfn_id',
  GFN_STATE_ROOT: DEFAULT_GFN_STATE_ROOT,
  KIOSK_FULLSCREEN: '1',
  KIOSK_WINDOW_WIDTH: '1600',
  KIOSK_WINDOW_HEIGHT: '900',
  LIBRARY_CACHE_TTL_SECONDS: '900',
  SESSION_STATE_CACHE: '1',
  STORE_WINDOW_FULLSCREEN: '1',
  STORE_WINDOW_BACKGROUND_COLOR: '#111315',
  DEFAULT_FILTER_GFN_ONLY: '1',
  STORE_ALLOWED_DOMAINS: DEFAULT_ALLOWED_STORE_DOMAINS.join(' '),
};

function sessionStatePath() {
  return path.join(app.getPath('userData'), 'session_state.json');
}

function parseShellConfig(contents) {
  const parsed = {};
  for (const rawLine of contents.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) {
      continue;
    }
    const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) {
      continue;
    }
    const [, key, rawValue] = match;
    let value = rawValue.trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    parsed[key] = value;
  }
  return parsed;
}

async function loadConfig() {
  try {
    const contents = await fsp.readFile(CONFIG_PATH, 'utf8');
    return { ...defaultConfig, ...parseShellConfig(contents) };
  } catch {
    return { ...defaultConfig };
  }
}

async function readJsonFile(filePath, fallbackValue) {
  try {
    const raw = await fsp.readFile(filePath, 'utf8');
    return JSON.parse(raw);
  } catch {
    return fallbackValue;
  }
}

async function writeJsonFile(filePath, value) {
  await fsp.mkdir(path.dirname(filePath), { recursive: true });
  await fsp.writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

function firstReadable(paths) {
  for (const candidate of paths) {
    if (!candidate) {
      continue;
    }
    try {
      fs.accessSync(candidate, fs.constants.X_OK);
      return candidate;
    } catch {
      continue;
    }
  }
  return '';
}

function parseArgString(argumentString) {
  if (!argumentString || !argumentString.trim()) {
    return [];
  }
  const tokens = [];
  let current = '';
  let quote = '';
  for (const char of argumentString.trim()) {
    if (quote) {
      if (char === quote) {
        quote = '';
      } else {
        current += char;
      }
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }
    if (/\s/.test(char)) {
      if (current) {
        tokens.push(current);
        current = '';
      }
      continue;
    }
    current += char;
  }
  if (current) {
    tokens.push(current);
  }
  return tokens;
}

function substituteTemplate(template, game) {
  return template.replace(/\{([^}]+)\}/g, (_, key) => {
    const value = game?.[key];
    return value == null ? '' : String(value);
  });
}

function resolveGfnBinary(config) {
  return (
    firstReadable([config.GFN_BINARY, config.GFN_BINARY_FALLBACK]) ||
    config.GFN_BINARY ||
    config.GFN_BINARY_FALLBACK
  );
}

function buildGfnLaunchPlan(config, game = null) {
  const binary = resolveGfnBinary(config);
  const args = [];

  if (!game) {
    args.push(...parseArgString(config.GFN_LOGIN_ARGS));
    return { binary, args };
  }

  if (config.GFN_GAME_ARGS_TEMPLATE) {
    args.push(...parseArgString(substituteTemplate(config.GFN_GAME_ARGS_TEMPLATE, game)));
  } else if (config.GFN_GAME_URI_TEMPLATE) {
    args.push(substituteTemplate(config.GFN_GAME_URI_TEMPLATE, game));
  } else if (game[config.GFN_GAME_ID_FIELD]) {
    args.push(String(game[config.GFN_GAME_ID_FIELD]));
  }

  return { binary, args };
}

function normalizeAllowedDomains(config) {
  const rawDomains = String(config.STORE_ALLOWED_DOMAINS || '')
    .split(/\s+/)
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  return rawDomains.length > 0 ? rawDomains : [...DEFAULT_ALLOWED_STORE_DOMAINS];
}

function isAllowedStoreHost(hostname, allowedDomains) {
  const normalized = String(hostname || '').trim().toLowerCase();
  return allowedDomains.some((domain) => normalized === domain || normalized.endsWith(`.${domain}`));
}

function ensureAllowedStoreUrl(urlString, config) {
  const url = new URL(urlString);
  if (url.protocol !== 'https:') {
    throw new Error('Only HTTPS store links are allowed.');
  }
  if (!isAllowedStoreHost(url.hostname, normalizeAllowedDomains(config))) {
    throw new Error(`Store host not allowed: ${url.hostname}`);
  }
  return url;
}

function buildStoreUrl(store, config) {
  const url = ensureAllowedStoreUrl(store.url || '', config);
  return url.toString();
}

async function loadGames() {
  const games = await readJsonFile(GAMES_PATH, []);
  return Array.isArray(games) ? games : [];
}

async function loadLibrary() {
  const payload = await readJsonFile(USER_LIBRARY_PATH, { games: [], logged_in: false });
  if (!payload || typeof payload !== 'object') {
    return { games: [], logged_in: false };
  }
  return {
    games: Array.isArray(payload.games) ? payload.games : [],
    logged_in: Boolean(payload.logged_in),
    updated_at: payload.updated_at || null,
  };
}

async function loadSessionState() {
  const config = await loadConfig();
  if (config.SESSION_STATE_CACHE !== '1') {
    return;
  }
  const payload = await readJsonFile(sessionStatePath(), {});
  if (payload && typeof payload === 'object') {
    sessionState = { ...sessionState, ...payload };
  }
}

async function persistSessionState() {
  await writeJsonFile(sessionStatePath(), sessionState);
}

function uniqueValues(values) {
  return [...new Set(values.filter(Boolean).map((value) => String(value).trim()).filter(Boolean))];
}

function normalizeGameTitle(value) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[®™©]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, ' ')
    .trim()
    .toLowerCase();
}

function slugifyGameTitle(value) {
  return normalizeGameTitle(value).replace(/\s+/g, '-');
}

function gameLookupKeys(game) {
  return uniqueValues([
    game?.id,
    game?.gfn_id,
    game?.slug,
    game?.short_name,
    game?.cms_id,
    normalizeGameTitle(game?.title),
  ]).map((value) => value.toLowerCase());
}

async function pathExists(candidate) {
  try {
    await fsp.access(candidate, fs.constants.R_OK);
    return true;
  } catch {
    return false;
  }
}

function gfnStateRootCandidates(config) {
  const runtimeUser = process.env.PVE_THIN_CLIENT_RUNTIME_USER || process.env.USER || 'thinclient';
  return uniqueValues([
    config.GFN_STATE_ROOT,
    process.env.BEAGLE_KIOSK_GFN_STATE_ROOT,
    DEFAULT_GFN_STATE_ROOT,
    path.join(os.homedir(), '.var', 'app', 'com.nvidia.geforcenow', '.local', 'state', 'NVIDIA', 'GeForceNOW'),
    path.join('/home', runtimeUser, '.var', 'app', 'com.nvidia.geforcenow', '.local', 'state', 'NVIDIA', 'GeForceNOW'),
  ]);
}

async function resolveGfnStateRoot(config) {
  for (const candidate of gfnStateRootCandidates(config)) {
    if (await pathExists(path.join(candidate, 'sharedstorage.json'))) {
      return candidate;
    }
  }
  return '';
}

async function walkFiles(rootPath, maxDepth = 8, depth = 0) {
  if (depth > maxDepth) {
    return [];
  }

  const entries = await fsp.readdir(rootPath, { withFileTypes: true }).catch(() => []);
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(rootPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await walkFiles(fullPath, maxDepth, depth + 1)));
      continue;
    }
    if (entry.isFile()) {
      files.push(fullPath);
    }
  }
  return files;
}

function extractBalancedJson(text, startIndex) {
  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let index = startIndex; index < text.length; index += 1) {
    const char = text[index];

    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === '\\') {
      escaped = true;
      continue;
    }
    if (char === '"') {
      inString = !inString;
      continue;
    }
    if (inString) {
      continue;
    }
    if (char === '{') {
      depth += 1;
      continue;
    }
    if (char === '}') {
      depth -= 1;
      if (depth === 0) {
        return text.slice(startIndex, index + 1);
      }
    }
  }

  return '';
}

function parseEmbeddedPanelPayloads(buffer) {
  const payloads = [];
  const text = buffer.toString('utf8');
  const marker = '{"data":{"panels":';
  let searchIndex = 0;

  while (searchIndex < text.length) {
    const startIndex = text.indexOf(marker, searchIndex);
    if (startIndex === -1) {
      break;
    }
    const jsonString = extractBalancedJson(text, startIndex);
    searchIndex = startIndex + marker.length;
    if (!jsonString) {
      continue;
    }
    try {
      payloads.push(JSON.parse(jsonString));
    } catch {
      continue;
    }
  }

  return payloads;
}

function decodeStarfleetSession(payload) {
  const encoded = payload?.starfleetSession?.data;
  if (!encoded) {
    return null;
  }

  let decoded = String(encoded);
  for (let attempt = 0; attempt < 4; attempt += 1) {
    try {
      const next = decodeURIComponent(decoded);
      if (next === decoded) {
        break;
      }
      decoded = next;
    } catch {
      break;
    }
  }

  try {
    const parsed = JSON.parse(decoded);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

async function readGfnSessionSnapshot(gfnStateRoot) {
  const sharedStorage = await readJsonFile(path.join(gfnStateRoot, 'sharedstorage.json'), null);
  const starfleetSession = decodeStarfleetSession(sharedStorage);

  return {
    present: Boolean(sharedStorage),
    loggedIn: Boolean(starfleetSession?.user?.isAuthenticated || starfleetSession?.accessToken),
    user: starfleetSession?.user
      ? {
          id: starfleetSession.user.sub || null,
          username: starfleetSession.user.preferred_username || null,
        }
      : null,
  };
}

function selectOwnedVariant(app) {
  const variants = Array.isArray(app?.variants) ? app.variants : [];
  return (
    variants.find((variant) => variant?.gfn?.library?.selected) ||
    variants.find((variant) => String(variant?.gfn?.library?.status || '').toUpperCase() !== 'NOT_OWNED') ||
    variants.find((variant) => String(variant?.gfn?.status || '').toUpperCase() === 'AVAILABLE') ||
    variants[0] ||
    null
  );
}

function storeLabel(value) {
  const normalized = String(value || '').trim().toUpperCase();
  if (normalized === 'EPIC') {
    return 'Epic Games Store';
  }
  if (normalized === 'STEAM') {
    return 'Steam';
  }
  if (normalized === 'UPLAY') {
    return 'Ubisoft Connect';
  }
  if (normalized === 'XBOX') {
    return 'Xbox';
  }
  return normalized || 'GeForce NOW';
}

function buildLibraryGameRecord(app, sectionTitle = '') {
  const variant = selectOwnedVariant(app);
  const title = String(app?.title || '').trim();
  const shortName = String(variant?.shortName || '').trim();
  const cmsId = variant?.id != null ? String(variant.id) : '';
  const imageUrl = app?.images?.TV_BANNER || app?.images?.HERO_IMAGE || '';

  return {
    id: String(app?.id || shortName || cmsId || slugifyGameTitle(title) || title),
    gfn_id: shortName || cmsId || String(app?.id || ''),
    cms_id: cmsId || null,
    short_name: shortName || null,
    slug: shortName || slugifyGameTitle(title),
    title,
    genre: sectionTitle || 'Meine Bibliothek',
    description: `${storeLabel(variant?.appStore)} Variante in deiner GeForce NOW Bibliothek erkannt.`,
    cover_url: imageUrl,
    geforce_now_supported: true,
    popularity: 1000,
    system_requirements: [
      'GeForce NOW Konto',
      'Stabile Internetverbindung',
      'Controller oder Maus und Tastatur',
    ],
    stores: [],
    app_store: storeLabel(variant?.appStore),
    playability_state: app?.gfn?.playabilityState || 'UNKNOWN',
    library_status: String(variant?.gfn?.library?.status || '').trim() || 'OWNED',
    owned: true,
    library_only: true,
  };
}

function dedupeLibraryGames(games) {
  const deduped = new Map();
  for (const game of games) {
    const key = gameLookupKeys(game)[0] || normalizeGameTitle(game.title) || String(game.id || game.gfn_id);
    const existing = deduped.get(key);
    if (!existing) {
      deduped.set(key, game);
      continue;
    }
    deduped.set(key, {
      ...existing,
      ...game,
      cover_url: existing.cover_url || game.cover_url,
      gfn_id: existing.gfn_id || game.gfn_id,
      cms_id: existing.cms_id || game.cms_id,
      short_name: existing.short_name || game.short_name,
    });
  }
  return [...deduped.values()];
}

function extractLibraryGamesFromPanelPayload(payload) {
  const panels = Array.isArray(payload?.data?.panels) ? payload.data.panels : [];
  const games = [];

  for (const panel of panels) {
    if (String(panel?.name || '').toUpperCase() !== 'LIBRARY') {
      continue;
    }
    for (const section of panel.sections || []) {
      for (const item of section.items || []) {
        if (item?.__typename !== 'GameItem' || !item.app?.title) {
          continue;
        }
        games.push(buildLibraryGameRecord(item.app, section.title || 'Meine Bibliothek'));
      }
    }
  }

  return dedupeLibraryGames(games);
}

async function extractLibraryGamesFromCache(gfnStateRoot) {
  const cacheRoot = path.join(gfnStateRoot, 'CefCache', 'Default', 'Service Worker', 'CacheStorage');
  if (!(await pathExists(cacheRoot))) {
    return [];
  }

  const files = await walkFiles(cacheRoot, 8);
  const extractedGames = [];

  for (const filePath of files) {
    if (!/_\d+$/.test(path.basename(filePath))) {
      continue;
    }
    const buffer = await fsp.readFile(filePath).catch(() => null);
    if (!buffer) {
      continue;
    }
    if (!buffer.includes(Buffer.from('requestType=panels/Library'))) {
      continue;
    }

    for (const payload of parseEmbeddedPanelPayloads(buffer)) {
      extractedGames.push(...extractLibraryGamesFromPanelPayload(payload));
    }
  }

  return dedupeLibraryGames(extractedGames);
}

async function extractLibraryGamesFromConsoleLog(gfnStateRoot) {
  const consoleLog = await fsp.readFile(path.join(gfnStateRoot, 'console.log'), 'utf8').catch(() => '');
  const fallbackGames = [];
  for (const match of consoleLog.matchAll(/Found game (.+?) in LIBRARY/g)) {
    const title = String(match[1] || '').trim();
    if (!title) {
      continue;
    }
    fallbackGames.push({
      id: `library-${slugifyGameTitle(title)}`,
      gfn_id: '',
      cms_id: null,
      short_name: null,
      slug: slugifyGameTitle(title),
      title,
      genre: 'Meine Bibliothek',
      description: 'Aus deiner GeForce NOW Bibliothek importiert.',
      cover_url: '',
      geforce_now_supported: true,
      popularity: 1000,
      system_requirements: [
        'GeForce NOW Konto',
        'Stabile Internetverbindung',
        'Controller oder Maus und Tastatur',
      ],
      stores: [],
      app_store: 'GeForce NOW',
      playability_state: 'UNKNOWN',
      library_status: 'OWNED',
      owned: true,
      library_only: true,
    });
  }
  return dedupeLibraryGames(fallbackGames);
}

async function synchronizeLibraryFromGfn(config, existingLibrary) {
  const gfnStateRoot = await resolveGfnStateRoot(config);
  if (!gfnStateRoot) {
    return { library: existingLibrary, changed: false };
  }

  const sessionSnapshot = await readGfnSessionSnapshot(gfnStateRoot);
  let libraryGames = await extractLibraryGamesFromCache(gfnStateRoot);
  if (libraryGames.length === 0) {
    libraryGames = await extractLibraryGamesFromConsoleLog(gfnStateRoot);
  }
  const inferredLoggedIn = sessionSnapshot.loggedIn || libraryGames.length > 0;

  const fallbackLibrary =
    existingLibrary && typeof existingLibrary === 'object'
      ? existingLibrary
      : { games: [], logged_in: false, updated_at: null };

  let nextLibrary = fallbackLibrary;
  if (inferredLoggedIn) {
    nextLibrary = {
      ...fallbackLibrary,
      logged_in: true,
      updated_at: new Date().toISOString(),
      games:
        libraryGames.length > 0
          ? libraryGames
          : Array.isArray(fallbackLibrary.games)
            ? fallbackLibrary.games
            : [],
      source: 'gfn-local-cache',
      gfn_state_root: gfnStateRoot,
    };
    if (sessionSnapshot.user) {
      nextLibrary.user = sessionSnapshot.user;
    }
  } else if (sessionSnapshot.present) {
    nextLibrary = {
      games: [],
      logged_in: false,
      updated_at: new Date().toISOString(),
      source: 'gfn-local-cache',
      gfn_state_root: gfnStateRoot,
    };
  }

  const changed = JSON.stringify(nextLibrary) !== JSON.stringify(fallbackLibrary);
  if (changed) {
    await writeJsonFile(USER_LIBRARY_PATH, nextLibrary);
  }

  sessionState.gfnLoggedIn = Boolean(nextLibrary.logged_in);
  sessionState.lastKnownLibrarySync = nextLibrary.updated_at || null;
  await persistSessionState();

  return { library: nextLibrary, changed };
}

function mergeLibraryIntoCatalog(games, library) {
  const catalogGames = Array.isArray(games) ? games.map((game) => ({ ...game })) : [];
  const libraryGames = Array.isArray(library?.games) ? library.games.map((game) => ({ ...game })) : [];
  const catalogKeyIndex = new Map();

  catalogGames.forEach((game, index) => {
    for (const key of gameLookupKeys(game)) {
      if (!catalogKeyIndex.has(key)) {
        catalogKeyIndex.set(key, index);
      }
    }
  });

  const syntheticLibraryGames = [];
  for (const libraryGame of libraryGames) {
    const matchingIndex = gameLookupKeys(libraryGame)
      .map((key) => catalogKeyIndex.get(key))
      .find((value) => value != null);

    if (matchingIndex != null) {
      catalogGames[matchingIndex] = {
        ...libraryGame,
        ...catalogGames[matchingIndex],
        cover_url: catalogGames[matchingIndex].cover_url || libraryGame.cover_url,
        gfn_id: catalogGames[matchingIndex].gfn_id || libraryGame.gfn_id,
        cms_id: catalogGames[matchingIndex].cms_id || libraryGame.cms_id,
        short_name: catalogGames[matchingIndex].short_name || libraryGame.short_name,
        app_store: catalogGames[matchingIndex].app_store || libraryGame.app_store,
        owned: true,
      };
      continue;
    }

    syntheticLibraryGames.push({
      ...libraryGame,
      owned: true,
      library_only: true,
      geforce_now_supported: true,
      stores: [],
    });
  }

  return [
    ...catalogGames.map((game) => ({ ...game, owned: Boolean(game.owned) })),
    ...syntheticLibraryGames,
  ];
}

function ownedGameIds(library) {
  const ids = new Set();
  for (const item of library.games || []) {
    for (const key of ['id', 'gfn_id', 'slug', 'short_name', 'cms_id', 'title']) {
      if (item[key]) {
        ids.add(String(item[key]).toLowerCase());
      }
    }
    if (item.title) {
      ids.add(normalizeGameTitle(item.title));
    }
  }
  return ids;
}

function configureMainWindowSecurity(window) {
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', (event, url) => {
    if (url !== window.webContents.getURL()) {
      event.preventDefault();
    }
  });
}

function configurePurchaseWindowSecurity(window, config) {
  window.webContents.setWindowOpenHandler(({ url }) => {
    try {
      ensureAllowedStoreUrl(url, config);
      return { action: 'allow' };
    } catch {
      void shell.openExternal(url);
      return { action: 'deny' };
    }
  });
  window.webContents.on('will-navigate', (event, url) => {
    try {
      ensureAllowedStoreUrl(url, config);
    } catch {
      event.preventDefault();
    }
  });
}

function emitRendererEvent(channel, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, payload);
  }
}

function createMainWindow(config) {
  const fullscreen = config.KIOSK_FULLSCREEN === '1';
  const width = Number.parseInt(config.KIOSK_WINDOW_WIDTH, 10) || 1600;
  const height = Number.parseInt(config.KIOSK_WINDOW_HEIGHT, 10) || 900;

  mainWindow = new BrowserWindow({
    width,
    height,
    show: false,
    fullscreen,
    frame: false,
    autoHideMenuBar: true,
    backgroundColor: '#111315',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  configureMainWindowSecurity(mainWindow);
  mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    console.log(
      'renderer-console',
      JSON.stringify({
        level,
        message,
        sourceId,
        line,
      })
    );
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  mainWindow.setMenuBarVisibility(false);
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.focus();
  });
}

function createPurchaseWindow(url, config) {
  if (purchaseWindow && !purchaseWindow.isDestroyed()) {
    purchaseWindow.close();
  }

  purchaseWindow = new BrowserWindow({
    parent: mainWindow,
    modal: true,
    frame: false,
    fullscreen: config.STORE_WINDOW_FULLSCREEN === '1',
    autoHideMenuBar: true,
    backgroundColor: config.STORE_WINDOW_BACKGROUND_COLOR || '#111315',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  configurePurchaseWindowSecurity(purchaseWindow, config);
  purchaseWindow.setMenuBarVisibility(false);
  purchaseWindow.loadURL(url);
  purchaseWindow.on('closed', () => {
    purchaseWindow = null;
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.focus();
    }
  });
}

function hideKioskWhileGfnRuns() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.hide();
  }
}

function restoreKioskAfterGfnExit() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.show();
    mainWindow.focus();
  }
}

function execFileCapture(command, args = [], timeoutMs = 1200) {
  return new Promise((resolve) => {
    execFile(command, args, { timeout: timeoutMs }, (error, stdout, stderr) => {
      resolve({
        ok: !error,
        stdout: stdout || '',
        stderr: stderr || '',
      });
    });
  });
}

function parseWindowList(output) {
  return String(output || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^(\S+)\s+\S+\s+\S+\s+\S+\s+(.*)$/);
      if (!match) {
        return null;
      }
      const [, windowId, remainder] = match;
      const tokens = remainder.split(/\s+/);
      const wmClass = tokens.shift() || '';
      const title = tokens.join(' ').trim();
      return { windowId, wmClass, title };
    })
    .filter(Boolean);
}

async function listX11Windows() {
  const result = await execFileCapture('wmctrl', ['-lpx']);
  if (!result.ok) {
    return [];
  }
  return parseWindowList(result.stdout);
}

function isGfnWindow(windowEntry) {
  const haystack = `${windowEntry.wmClass} ${windowEntry.title}`.toLowerCase();
  return (
    haystack.includes('geforcenow') ||
    haystack.includes('geforce now') ||
    haystack.includes('sdlgraphicscontext')
  );
}

async function focusExternalWindow(windowId) {
  const attempts = [
    () => execFileCapture('wmctrl', ['-ia', windowId]),
    () => execFileCapture('xdotool', ['windowactivate', windowId]),
  ];
  for (const attempt of attempts) {
    const result = await attempt();
    if (result.ok) {
      return true;
    }
  }
  return false;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function execFileStrict(command, args = [], timeoutMs = 600000) {
  return new Promise((resolve, reject) => {
    execFile(command, args, { timeout: timeoutMs }, (error, stdout, stderr) => {
      if (error) {
        const message = stderr || stdout || error.message || `${command} failed`;
        reject(new Error(String(message).trim()));
        return;
      }
      resolve({ stdout: stdout || '', stderr: stderr || '' });
    });
  });
}

async function waitForGfnWindow(timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const windows = await listX11Windows();
    const match = windows.find(isGfnWindow);
    if (match) {
      return match;
    }
    await delay(500);
  }
  return null;
}

async function handOverToGfnWindow(expectedPid) {
  const probeToken = Symbol('gfn-window-probe');
  gfnWindowProbeToken = probeToken;
  emitRendererEvent('kiosk:gfn-status', { state: 'launching' });

  const windowEntry = await waitForGfnWindow();
  if (gfnWindowProbeToken !== probeToken) {
    return;
  }
  if (!gfnProcess || gfnProcess.pid !== expectedPid) {
    return;
  }

  if (windowEntry) {
    hideKioskWhileGfnRuns();
    await focusExternalWindow(windowEntry.windowId);
    emitRendererEvent('kiosk:gfn-status', {
      state: 'handoff',
      windowTitle: windowEntry.title || 'GeForce NOW',
    });
    return;
  }

  emitRendererEvent('kiosk:gfn-status', { state: 'still-starting' });
}

function launchChildProcess(binary, args) {
  return spawn(binary, args, {
    detached: false,
    stdio: 'ignore',
  });
}

async function launchGfn(game = null) {
  const config = await loadConfig();
  const { binary, args } = buildGfnLaunchPlan(config, game);
  if (!binary) {
    throw new Error('No GeForce NOW binary configured.');
  }
  try {
    fs.accessSync(binary, fs.constants.X_OK);
  } catch {
    throw new Error(`GeForce NOW client is not installed or not executable: ${binary}`);
  }
  if (gfnProcess && !gfnProcess.killed) {
    throw new Error('GeForce NOW is already running.');
  }

  gfnProcess = launchChildProcess(binary, args);
  void handOverToGfnWindow(gfnProcess.pid);
  gfnProcess.on('error', () => {
    gfnWindowProbeToken = null;
    gfnProcess = null;
    emitRendererEvent('kiosk:gfn-status', { state: 'idle' });
    restoreKioskAfterGfnExit();
    void pushBootstrapStateToRenderer();
  });
  gfnProcess.on('exit', () => {
    gfnWindowProbeToken = null;
    gfnProcess = null;
    emitRendererEvent('kiosk:gfn-status', { state: 'idle' });
    restoreKioskAfterGfnExit();
    void pushBootstrapStateToRenderer();
  });
  gfnProcess.unref();

  return { binary, args };
}

async function bootstrapPayload() {
  const config = await loadConfig();
  const games = await loadGames();
  let library = await loadLibrary();
  try {
    const syncResult = await synchronizeLibraryFromGfn(config, library);
    library = syncResult.library;
  } catch (error) {
    console.warn('gfn-library-sync-failed', error);
  }
  const ownedIds = ownedGameIds(library);
  const decoratedGames = mergeLibraryIntoCatalog(
    games.map((game) => ({
      ...game,
      owned:
        ownedIds.has(String(game.id || '').toLowerCase()) ||
        ownedIds.has(String(game.gfn_id || '').toLowerCase()) ||
        ownedIds.has(String(game.slug || '').toLowerCase()) ||
        ownedIds.has(String(game.short_name || '').toLowerCase()) ||
        ownedIds.has(String(game.cms_id || '').toLowerCase()) ||
        ownedIds.has(String(game.title || '').toLowerCase()) ||
        ownedIds.has(normalizeGameTitle(game.title)),
    })),
    library
  );

  console.log(
    'bootstrap-payload',
    JSON.stringify({
      catalogCount: Array.isArray(games) ? games.length : 0,
      decoratedCount: Array.isArray(decoratedGames) ? decoratedGames.length : 0,
      libraryCount: Array.isArray(library?.games) ? library.games.length : 0,
      loggedIn: Boolean(library?.logged_in || sessionState.gfnLoggedIn),
    })
  );

  return {
    version: APP_VERSION,
    config: {
      defaultFilterGfnOnly: config.DEFAULT_FILTER_GFN_ONLY === '1',
    },
    sessionState,
    library,
    games: decoratedGames,
    coverCacheDir: COVER_CACHE_DIR,
    brandImageUrl: pathToFileURL(BRAND_IMAGE_PATH).toString(),
  };
}

async function pushBootstrapStateToRenderer() {
  try {
    emitRendererEvent('kiosk:state-update', await bootstrapPayload());
  } catch (error) {
    console.warn('kiosk-state-update-failed', error);
  }
}

async function refreshCatalogNow() {
  if (catalogRefreshPromise) {
    return catalogRefreshPromise;
  }

  const scriptPath = path.join(INSTALL_ROOT, 'update_catalog.py');
  catalogRefreshPromise = (async () => {
    await execFileStrict('/usr/bin/python3', [scriptPath]);
    await pushBootstrapStateToRenderer();
    return { ok: true };
  })().finally(() => {
    catalogRefreshPromise = null;
  });

  return catalogRefreshPromise;
}

function registerIpcHandlers() {
  ipcMain.handle('kiosk:bootstrap', async () => bootstrapPayload());

  ipcMain.handle('kiosk:start-login', async () => {
    sessionState.gfnLoggedIn = false;
    await persistSessionState();
    const launchInfo = await launchGfn(null);
    return { ok: true, launchInfo };
  });

  ipcMain.handle('kiosk:launch-game', async (_event, game) => {
    const launchInfo = await launchGfn(game);
    return { ok: true, launchInfo };
  });

  ipcMain.handle('kiosk:refresh-catalog', async () => refreshCatalogNow());

  ipcMain.handle('kiosk:open-store', async (_event, payload) => {
    const config = await loadConfig();
    const storeUrl = buildStoreUrl(payload.store, config);
    createPurchaseWindow(storeUrl, config);
    return { ok: true, storeUrl };
  });

  ipcMain.handle('kiosk:close-store', async () => {
    if (purchaseWindow && !purchaseWindow.isDestroyed()) {
      purchaseWindow.close();
    }
    return { ok: true };
  });

  ipcMain.handle('kiosk:open-external', async (_event, url) => {
    await shell.openExternal(url);
    return { ok: true };
  });
}

app.whenReady().then(async () => {
  await fsp.mkdir(COVER_CACHE_DIR, { recursive: true });
  await loadSessionState();
  registerIpcHandlers();
  const config = await loadConfig();
  createMainWindow(config);
  setInterval(() => {
    void pushBootstrapStateToRenderer();
  }, 5000).unref();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
