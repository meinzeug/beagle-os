/*
 * Sci-Fi HUD + Command Palette
 * - Injects the holographic HUD overlay into the document body.
 * - Provides a Ctrl/Cmd+K command palette with curated actions.
 * No external dependencies. CSP-safe (no inline styles or scripts).
 */

import { setActivePanel } from './panels.js';

// Curated commands: lazy-imported to avoid circular dependencies.
const COMMAND_DEFINITIONS = [
  { id: 'nav.overview', kind: 'Navigate', label: 'Dashboard', hint: 'Live Status & Telemetrie', keywords: 'dashboard overview start home', run: () => setActivePanel('overview') },
  { id: 'nav.inventory', kind: 'Navigate', label: 'VMs & Endpoints', hint: 'Aktive Beagle-VMs', keywords: 'vm endpoints inventory', run: () => setActivePanel('inventory') },
  { id: 'nav.virtualization', kind: 'Navigate', label: 'Nodes', hint: 'Compute, Persistenz, Bridges', keywords: 'nodes hypervisor', run: () => setActivePanel('virtualization') },
  { id: 'nav.cluster', kind: 'Navigate', label: 'Cluster', hint: 'Health & Kapazitaet', keywords: 'cluster nodes', run: () => setActivePanel('cluster') },
  { id: 'nav.provisioning', kind: 'Navigate', label: 'VM erstellen', hint: 'Provisioning Workspace', keywords: 'provision new vm create', run: () => setActivePanel('provisioning') },
  { id: 'nav.policies', kind: 'Navigate', label: 'Pools & Policies', hint: 'Desktop-Pools & Profile', keywords: 'policies pools profiles', run: () => setActivePanel('policies') },
  { id: 'nav.iam', kind: 'Navigate', label: 'Users & Roles', hint: 'IAM, RBAC, Sessions', keywords: 'iam users roles auth', run: () => setActivePanel('iam') },
  { id: 'nav.audit', kind: 'Navigate', label: 'Audit', hint: 'Compliance Reports', keywords: 'audit log compliance', run: () => setActivePanel('audit') },
  { id: 'nav.sessions', kind: 'Navigate', label: 'Sessions', hint: 'Live Sessions', keywords: 'sessions stream', run: () => setActivePanel('sessions') },
  { id: 'nav.settings', kind: 'Navigate', label: 'Einstellungen', hint: 'Allgemein', keywords: 'settings general', run: () => setActivePanel('settings_general') },

  { id: 'act.thinclient', kind: 'Action', label: 'Thinclient VM mieten (One-Click)', hint: 'Quick-Intent Provisioning', keywords: 'thinclient mieten oneclick rent', run: async () => {
      const mod = await import('./provisioning.js');
      if (typeof mod.runProvisionQuickIntent === 'function') {
        await mod.runProvisionQuickIntent('thinclient', 'prov-modal-', true);
      }
    } },
  { id: 'act.dedicated', kind: 'Action', label: 'Dedicated Server mieten (One-Click)', hint: 'Quick-Intent Provisioning', keywords: 'dedicated server mieten rent oneclick', run: async () => {
      const mod = await import('./provisioning.js');
      if (typeof mod.runProvisionQuickIntent === 'function') {
        await mod.runProvisionQuickIntent('dedicated', 'prov-modal-', true);
      }
    } },
  { id: 'act.theme', kind: 'Action', label: 'Theme umschalten', hint: 'Dark/Light Mode', keywords: 'theme dark light mode', run: async () => {
      const btn = document.getElementById('toggle-dark-mode') || document.getElementById('dark-mode-toggle');
      if (btn) btn.click();
    } },
  { id: 'act.refresh', kind: 'Action', label: 'Dashboard neu laden', hint: 'Live-Daten aktualisieren', keywords: 'refresh reload dashboard', run: async () => {
      try {
        const mod = await import('./dashboard.js');
        if (typeof mod.loadDashboard === 'function') await mod.loadDashboard();
      } catch (_) { /* dashboard module shape may differ */ }
    } },
  { id: 'act.logout', kind: 'Action', label: 'Abmelden', hint: 'Aktuelle Session beenden', keywords: 'logout signout abmelden', run: async () => {
      const btn = document.getElementById('logout-btn') || document.getElementById('btn-logout');
      if (btn) btn.click();
    } }
];

function ensureHudChrome() {
  if (document.querySelector('.scifi-hud')) return;
  const hud = document.createElement('div');
  hud.className = 'scifi-hud';
  hud.setAttribute('aria-hidden', 'true');
  hud.innerHTML = [
    '<span class="scifi-corner tl"></span>',
    '<span class="scifi-corner tr"></span>',
    '<span class="scifi-corner bl"></span>',
    '<span class="scifi-corner br"></span>',
    '<span class="scifi-scan"></span>',
    '<div class="scifi-statusbar" role="status">',
    '  <span class="scifi-dot"></span>',
    '  <span class="scifi-statusbar-text">BEAGLE.OS // CONSOLE ONLINE</span>',
    '  <span class="scifi-statusbar-clock" data-scifi-clock></span>',
    '  <span>·</span>',
    '  <span><kbd>Ctrl</kbd>+<kbd>K</kbd> · Befehle</span>',
    '</div>'
  ].join('');
  document.body.appendChild(hud);

  const clock = hud.querySelector('[data-scifi-clock]');
  const tick = () => {
    if (!clock) return;
    const d = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    clock.textContent = `T+${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  };
  tick();
  setInterval(tick, 1000);
}

function ensurePalette() {
  if (document.querySelector('[data-scifi-command-palette]')) return;
  const wrap = document.createElement('div');
  wrap.className = 'scifi-cmdk';
  wrap.hidden = true;
  wrap.setAttribute('role', 'dialog');
  wrap.setAttribute('aria-modal', 'true');
  wrap.setAttribute('aria-label', 'Beagle Command Palette');
  wrap.dataset.scifiCommandPalette = 'true';
  wrap.innerHTML = [
    '<div class="scifi-cmdk-dialog">',
    '  <div class="scifi-cmdk-head">',
    '    <span class="scifi-cmdk-prefix">&gt;_</span>',
    '    <input class="scifi-cmdk-input" type="text" autocomplete="off" spellcheck="false" placeholder="Befehl, Panel oder Aktion suchen…" data-scifi-cmdk-input>',
    '    <span class="scifi-cmdk-hint">ESC schliesst</span>',
    '  </div>',
    '  <ul class="scifi-cmdk-results" role="listbox" data-scifi-cmdk-results></ul>',
    '</div>'
  ].join('');
  document.body.appendChild(wrap);

  const input = wrap.querySelector('[data-scifi-cmdk-input]');
  const list = wrap.querySelector('[data-scifi-cmdk-results]');
  let activeIndex = 0;
  let filtered = COMMAND_DEFINITIONS.slice();

  const render = () => {
    if (!list) return;
    list.innerHTML = '';
    if (!filtered.length) {
      const empty = document.createElement('li');
      empty.className = 'scifi-cmdk-empty';
      empty.textContent = '// keine Treffer';
      list.appendChild(empty);
      return;
    }
    filtered.forEach((cmd, idx) => {
      const li = document.createElement('li');
      li.setAttribute('role', 'option');
      li.dataset.cmdId = cmd.id;
      if (idx === activeIndex) li.classList.add('is-active');
      const main = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = cmd.label;
      main.appendChild(title);
      if (cmd.hint) {
        const hint = document.createElement('small');
        hint.textContent = cmd.hint;
        main.appendChild(hint);
      }
      const kind = document.createElement('span');
      kind.className = 'scifi-cmdk-kind';
      kind.textContent = cmd.kind;
      li.appendChild(main);
      li.appendChild(kind);
      li.addEventListener('click', () => execute(cmd));
      list.appendChild(li);
    });
  };

  const filter = (q) => {
    const needle = (q || '').trim().toLowerCase();
    if (!needle) {
      filtered = COMMAND_DEFINITIONS.slice();
    } else {
      filtered = COMMAND_DEFINITIONS.filter((cmd) => {
        const hay = (cmd.label + ' ' + (cmd.hint || '') + ' ' + (cmd.keywords || '') + ' ' + cmd.kind).toLowerCase();
        return needle.split(/\s+/).every((tok) => hay.indexOf(tok) !== -1);
      });
    }
    activeIndex = 0;
    render();
  };

  const close = () => {
    wrap.hidden = true;
    document.body.classList.remove('scifi-cmdk-open');
  };
  const open = () => {
    wrap.hidden = false;
    document.body.classList.add('scifi-cmdk-open');
    if (input) {
      input.value = '';
      filter('');
      try { input.focus(); } catch (_) { /* ignore */ }
    }
  };

  const execute = async (cmd) => {
    close();
    try {
      if (cmd && typeof cmd.run === 'function') {
        await cmd.run();
      }
    } catch (err) {
      console.warn('Command palette execution failed:', err);
    }
  };

  if (input) {
    input.addEventListener('input', (event) => filter(event.target.value));
    input.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        activeIndex = Math.min(filtered.length - 1, activeIndex + 1);
        render();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        activeIndex = Math.max(0, activeIndex - 1);
        render();
      } else if (event.key === 'Enter') {
        event.preventDefault();
        const cmd = filtered[activeIndex];
        if (cmd) execute(cmd);
      } else if (event.key === 'Escape') {
        event.preventDefault();
        close();
      }
    });
  }

  wrap.addEventListener('click', (event) => {
    if (event.target === wrap) close();
  });

  document.addEventListener('keydown', (event) => {
    const isToggle = (event.key === 'k' || event.key === 'K') && (event.ctrlKey || event.metaKey);
    if (isToggle) {
      event.preventDefault();
      if (wrap.hidden) open(); else close();
    }
  });

  render();
}

export function initScifiHud() {
  if (typeof document === 'undefined' || !document.body) return;
  if (document.body.dataset.scifiHud === 'ready') return;
  document.body.dataset.scifiHud = 'ready';
  ensureHudChrome();
  ensurePalette();
}

export const __SCIFI_COMMANDS__ = COMMAND_DEFINITIONS;
