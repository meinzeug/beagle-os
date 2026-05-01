(function () {
    function normalize(value) {
        return String(value || '').trim().toLowerCase();
    }

    function applyFilter() {
        const input = document.querySelector('[data-doc-search]');
        const status = document.querySelector('[data-doc-search-status]');
        const cards = Array.from(document.querySelectorAll('[data-doc-card]'));

        if (!input || !cards.length) {
            return;
        }

        const lang = document.documentElement.lang === 'de' ? 'de' : 'en';
        const query = normalize(input.value);
        let visible = 0;

        cards.forEach((card) => {
            const haystack = normalize(card.dataset['search' + lang.charAt(0).toUpperCase() + lang.slice(1)] || '');
            const show = !query || haystack.includes(query);
            card.classList.toggle('hidden', !show);
            if (show) {
                visible += 1;
            }
        });

        if (status) {
            status.textContent = lang === 'de'
                ? `${visible} Dokumentationsseite(n) sichtbar`
                : `${visible} documentation page(s) visible`;
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        const input = document.querySelector('[data-doc-search]');
        if (!input) {
            return;
        }
        input.addEventListener('input', applyFilter);
        document.addEventListener('beagle:langchange', applyFilter);
        applyFilter();
    });
})();
