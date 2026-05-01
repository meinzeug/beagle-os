(function () {
    const STORAGE_KEY = 'beagle-lang';
    const defaultLang = 'en';

    function applyLanguage(lang) {
        const nextLang = lang === 'de' ? 'de' : 'en';
        document.documentElement.lang = nextLang;
        localStorage.setItem(STORAGE_KEY, nextLang);

        document.querySelectorAll('[data-en][data-de]').forEach((element) => {
            const value = element.dataset[nextLang];
            if (value == null) {
                return;
            }
            if (element.dataset.i18nTarget === 'html') {
                element.innerHTML = value;
            } else if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                element.value = value;
            } else {
                element.textContent = value;
            }
        });

        document.querySelectorAll('[data-en-placeholder][data-de-placeholder]').forEach((element) => {
            element.setAttribute('placeholder', nextLang === 'de' ? element.dataset.dePlaceholder : element.dataset.enPlaceholder);
        });

        document.querySelectorAll('[data-en-aria][data-de-aria]').forEach((element) => {
            element.setAttribute('aria-label', nextLang === 'de' ? element.dataset.deAria : element.dataset.enAria);
        });

        const title = document.querySelector('title[data-en][data-de]');
        if (title) {
            title.textContent = nextLang === 'de' ? title.dataset.de : title.dataset.en;
        }

        const metaDescription = document.querySelector('meta[name="description"][data-en][data-de]');
        if (metaDescription) {
            metaDescription.setAttribute('content', nextLang === 'de' ? metaDescription.dataset.de : metaDescription.dataset.en);
        }

        document.querySelectorAll('[data-lang-button]').forEach((button) => {
            button.classList.toggle('active', button.dataset.langButton === nextLang);
        });

        document.dispatchEvent(new CustomEvent('beagle:langchange', { detail: { lang: nextLang } }));
    }

    function initLanguageSwitcher() {
        const preferred = localStorage.getItem(STORAGE_KEY) || defaultLang;
        applyLanguage(preferred);

        document.querySelectorAll('[data-lang-button]').forEach((button) => {
            button.addEventListener('click', () => applyLanguage(button.dataset.langButton));
        });
    }

    function initNavigation() {
        const toggle = document.querySelector('[data-nav-toggle]');
        const panel = document.querySelector('[data-nav-panel]');
        if (!toggle || !panel) {
            return;
        }

        toggle.addEventListener('click', () => {
            const open = panel.classList.toggle('open');
            toggle.setAttribute('aria-expanded', String(open));
        });

        panel.querySelectorAll('a').forEach((link) => {
            link.addEventListener('click', () => {
                panel.classList.remove('open');
                toggle.setAttribute('aria-expanded', 'false');
            });
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        initLanguageSwitcher();
        initNavigation();
    });
})();
