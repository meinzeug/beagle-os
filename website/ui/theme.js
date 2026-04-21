import { qs } from './dom.js';

function isDarkModeActive() {
  return !document.body.classList.contains('light-mode');
}

export function loadDarkModePreference() {
  try {
    if (localStorage.getItem('beagle.darkMode') === '0') {
      document.body.classList.add('light-mode');
    } else {
      document.body.classList.remove('light-mode');
    }
  } catch (error) {
    void error;
  }
}

export function toggleDarkMode() {
  document.body.classList.toggle('light-mode');
  try {
    localStorage.setItem('beagle.darkMode', isDarkModeActive() ? '1' : '0');
  } catch (error) {
    void error;
  }
  updateDarkModeButton();
}

export function updateDarkModeButton() {
  const btn = qs('toggle-dark-mode');
  if (!btn) {
    return;
  }
  const isDark = isDarkModeActive();
  btn.setAttribute('aria-label', isDark ? 'Hellmodus aktivieren' : 'Dunkelmodus aktivieren');
  const useEl = btn.querySelector('use');
  if (useEl) {
    useEl.setAttribute('href', isDark ? '#i-sun' : '#i-moon');
    try {
      useEl.setAttributeNS('http://www.w3.org/1999/xlink', 'href', isDark ? '#i-sun' : '#i-moon');
    } catch (error) {
      void error;
    }
  } else if (!btn.querySelector('svg')) {
    btn.textContent = isDark ? 'Hell' : 'Dunkel';
  }
}
