<?php
session_start();
// Generate a fresh CSRF token for this page load
if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}
$csrf = htmlspecialchars($_SESSION['csrf_token'], ENT_QUOTES, 'UTF-8');
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title data-en="Beagle OS | Commercial License" data-de="Beagle OS | Kommerzielle Lizenz">Beagle OS | Commercial License</title>
    <meta name="description" data-en="Request a commercial license for Beagle OS. Private use is free. Commercial use requires a license." data-de="Kommerzielle Lizenz fuer Beagle OS anfragen. Private Nutzung ist kostenlos. Kommerzielle Nutzung erfordert eine Lizenz." content="Request a commercial license for Beagle OS. Private use is free. Commercial use requires a license.">
    <link rel="icon" href="/favicon.svg" type="image/svg+xml">
    <link rel="stylesheet" href="/assets/css/main.css">
    <script defer src="/assets/js/lang.js"></script>
    <style>
        .contact-form { max-width: 640px; }
        .form-group { display: flex; flex-direction: column; gap: .4rem; margin-bottom: 1.25rem; }
        .form-group label { font-size: .85rem; font-weight: 600; color: var(--text-muted, #888); text-transform: uppercase; letter-spacing: .04em; }
        .form-group input,
        .form-group select,
        .form-group textarea { width: 100%; padding: .65rem .85rem; border: 1px solid var(--border, #2a2a2a); border-radius: 6px; background: var(--surface, #111); color: var(--text, #eee); font-size: 1rem; font-family: inherit; transition: border-color .15s; }
        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus { outline: none; border-color: var(--accent, #e85d04); }
        .form-group textarea { resize: vertical; min-height: 140px; }
        .form-group .hint { font-size: .8rem; color: var(--text-muted, #777); }
        .form-honeypot { display: none !important; }
        .form-status { margin-top: 1rem; padding: .75rem 1rem; border-radius: 6px; font-size: .95rem; display: none; }
        .form-status.success { background: rgba(0,200,100,.12); border: 1px solid rgba(0,200,100,.3); color: #4caf7d; }
        .form-status.error   { background: rgba(220,50,50,.12);  border: 1px solid rgba(220,50,50,.3);  color: #e06060; }
        .license-info { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2.5rem; }
        .license-info article { padding: 1.25rem 1.5rem; border: 1px solid var(--border, #2a2a2a); border-radius: 10px; background: var(--surface, #111); }
        .license-info article h3 { margin: 0 0 .5rem; font-size: 1rem; }
        .license-info article p  { margin: 0; font-size: .9rem; color: var(--text-muted, #888); }
        @media (max-width: 560px) { .license-info { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <header class="site-header"><div class="container nav-shell"><a class="brand" href="/"><img src="/logo.svg" alt="Beagle OS"><span>Beagle OS</span></a><button class="nav-toggle" type="button" aria-label="Toggle navigation" aria-expanded="false" data-nav-toggle><span></span><span></span><span></span></button><div class="nav-panel" data-nav-panel><nav class="nav-links"><a href="/download/" data-en="Download" data-de="Herunterladen">Download</a><a href="/docs/" data-en="Documentation" data-de="Dokumentation">Documentation</a><a href="/about/" data-en="About" data-de="Ueber uns">About</a><a href="/saas/" data-en="SaaS" data-de="SaaS">SaaS</a><a href="https://github.com/meinzeug/beagle-os" target="_blank" rel="noreferrer">GitHub</a></nav><div class="nav-actions"><a class="btn btn-outline" href="https://beagle.meinzeug.cloud/auth/login">Login</a><a class="btn btn-primary" href="https://beagle.meinzeug.cloud/auth/register" data-en="Create Account" data-de="Konto erstellen">Create Account</a><div class="lang-switcher"><button type="button" data-lang-button="en">EN</button><button type="button" data-lang-button="de">DE</button></div></div></div></div></header>
    <main>
        <section class="section">
            <div class="container">
                <div class="page-hero">
                    <div class="eyebrow" data-en="License" data-de="Lizenz">License</div>
                    <h1 data-en="Request a Commercial License" data-de="Kommerzielle Lizenz anfragen">Request a Commercial License</h1>
                    <p data-en="Beagle OS is free for private and non-commercial use. If you intend to use it in a commercial environment, please fill out the form below and we will get back to you." data-de="Beagle OS ist fuer private und nicht-kommerzielle Nutzung kostenlos. Wenn du es in einem kommerziellen Umfeld einsetzen moechtest, fuell bitte das Formular aus und wir melden uns bei dir.">Beagle OS is free for private and non-commercial use. If you intend to use it in a commercial environment, please fill out the form below and we will get back to you.</p>
                </div>
            </div>
        </section>
        <section class="section section-alt">
            <div class="container">
                <div class="license-info">
                    <article>
                        <h3 data-en="Private Use — Free" data-de="Private Nutzung — Kostenlos">Private Use — Free</h3>
                        <p data-en="Personal, non-commercial use. No license required. Download, run, and self-host at no cost." data-de="Persoenliche, nicht-kommerzielle Nutzung. Keine Lizenz erforderlich. Herunterladen, betreiben und self-hosten ohne Kosten.">Personal, non-commercial use. No license required. Download, run, and self-host at no cost.</p>
                    </article>
                    <article>
                        <h3 data-en="Commercial Use — License Required" data-de="Kommerzielle Nutzung — Lizenz erforderlich">Commercial Use — License Required</h3>
                        <p data-en="Any use within a company, for revenue-generating activities, or in a production environment operated by a business entity requires a commercial license." data-de="Jede Nutzung innerhalb eines Unternehmens, fuer Aktivitaeten zur Umsatzgenerierung oder in einer von einer Geschaeftseinheit betriebenen Produktionsumgebung erfordert eine kommerzielle Lizenz.">Any use within a company, for revenue-generating activities, or in a production environment operated by a business entity requires a commercial license.</p>
                    </article>
                </div>
                <div class="contact-form">
                    <form id="license-form" novalidate>
                        <input type="hidden" name="csrf_token" value="<?= $csrf ?>">
                        <!-- Honeypot: hidden from real users, bots will fill this -->
                        <div class="form-honeypot" aria-hidden="true">
                            <label for="website">Website</label>
                            <input type="text" id="website" name="website" tabindex="-1" autocomplete="off">
                        </div>
                        <div class="form-group">
                            <label for="name" data-en="Name *" data-de="Name *">Name *</label>
                            <input type="text" id="name" name="name" required maxlength="120" autocomplete="name"
                                data-placeholder-en="Your full name" data-placeholder-de="Vollstaendiger Name"
                                placeholder="Your full name">
                        </div>
                        <div class="form-group">
                            <label for="company" data-en="Company / Organization" data-de="Unternehmen / Organisation">Company / Organization</label>
                            <input type="text" id="company" name="company" maxlength="250" autocomplete="organization"
                                data-placeholder-en="Company name (optional)" data-placeholder-de="Unternehmensname (optional)"
                                placeholder="Company name (optional)">
                        </div>
                        <div class="form-group">
                            <label for="email" data-en="E-Mail *" data-de="E-Mail *">E-Mail *</label>
                            <input type="email" id="email" name="email" required maxlength="200" autocomplete="email"
                                data-placeholder-en="your@email.com" data-placeholder-de="ihre@email.de"
                                placeholder="your@email.com">
                        </div>
                        <div class="form-group">
                            <label for="endpoints" data-en="Number of Endpoints" data-de="Anzahl Endpoints">Number of Endpoints</label>
                            <input type="number" id="endpoints" name="endpoints" min="1" max="99999"
                                data-placeholder-en="Estimated number of endpoints" data-placeholder-de="Geschaetzte Anzahl Endpoints"
                                placeholder="Estimated number of endpoints">
                            <span class="hint" data-en="Approximate number of endpoints you plan to operate." data-de="Ungefaehre Anzahl der Endpoints, die du betreiben moechtest.">Approximate number of endpoints you plan to operate.</span>
                        </div>
                        <div class="form-group">
                            <label for="message" data-en="Message *" data-de="Nachricht *">Message *</label>
                            <textarea id="message" name="message" required maxlength="5000"
                                data-placeholder-en="Describe your use case, deployment size, and any questions about commercial licensing."
                                data-placeholder-de="Beschreibe deinen Use-Case, die Deployment-Groesse und eventuelle Fragen zur kommerziellen Lizenzierung."
                                placeholder="Describe your use case, deployment size, and any questions about commercial licensing."></textarea>
                        </div>
                        <button class="btn btn-primary" type="submit" id="submit-btn"
                            data-en="Send License Request" data-de="Lizenzanfrage senden">Send License Request</button>
                        <div class="form-status" id="form-status" role="alert"></div>
                    </form>
                </div>
            </div>
        </section>
    </main>
    <footer class="footer"><div class="container"><div class="footer-grid"><div><h3>Beagle OS</h3><p data-en="Official website and documentation for the Beagle OS virtualization platform." data-de="Offizielle Website und Dokumentation fuer die Beagle OS Virtualisierungsplattform.">Official website and documentation for the Beagle OS virtualization platform.</p></div><div class="footer-links"><h4 data-en="Product" data-de="Produkt">Product</h4><a href="/download/" data-en="Download" data-de="Herunterladen">Download</a><a href="/docs/" data-en="Documentation" data-de="Dokumentation">Documentation</a><a href="/saas/" data-en="SaaS" data-de="SaaS">SaaS</a></div><div class="footer-links"><h4 data-en="Docs" data-de="Docs">Docs</h4><a href="/docs/architecture/" data-en="Architecture" data-de="Architektur">Architecture</a><a href="/docs/security/" data-en="Security" data-de="Sicherheit">Security</a><a href="/docs/release-notes/" data-en="Release Notes" data-de="Versionshinweise">Release Notes</a></div><div class="footer-links"><h4 data-en="Access" data-de="Zugang">Access</h4><a href="https://beagle.meinzeug.cloud/auth/login">Login</a><a href="https://beagle.meinzeug.cloud/auth/register" data-en="Register" data-de="Registrieren">Register</a><a href="https://beagle.meinzeug.cloud/dashboard">Dashboard</a></div><div class="footer-links"><h4 data-en="Resources" data-de="Ressourcen">Resources</h4><a href="https://github.com/meinzeug/beagle-os" target="_blank" rel="noreferrer">GitHub</a><a href="/contact/" data-en="Commercial License" data-de="Kommerzielle Lizenz">Commercial License</a><a href="/about/" data-en="About" data-de="Ueber uns">About</a></div></div><div class="footer-bottom">© 2026 Dennis Wicht</div></div></footer>
    <script>
    (function () {
        var form   = document.getElementById('license-form');
        var status = document.getElementById('form-status');
        var btn    = document.getElementById('submit-btn');

        // Translate placeholders on lang switch (basic support)
        function applyLang(lang) {
            form.querySelectorAll('[data-placeholder-' + lang + ']').forEach(function (el) {
                el.placeholder = el.getAttribute('data-placeholder-' + lang);
            });
        }
        document.querySelectorAll('[data-lang-button]').forEach(function (b) {
            b.addEventListener('click', function () { applyLang(b.getAttribute('data-lang-button')); });
        });

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            status.style.display = 'none';
            status.className = 'form-status';
            btn.disabled = true;

            var data = new FormData(form);

            fetch('/contact/send.php', { method: 'POST', body: data })
                .then(function (r) { return r.json(); })
                .then(function (json) {
                    if (json.success) {
                        status.textContent = document.documentElement.lang === 'de'
                            ? 'Danke! Deine Anfrage wurde gesendet. Wir melden uns in Kuerze.'
                            : 'Thank you! Your request has been sent. We will get back to you shortly.';
                        status.className = 'form-status success';
                        form.reset();
                    } else {
                        status.textContent = json.error || 'An error occurred. Please try again.';
                        status.className = 'form-status error';
                        btn.disabled = false;
                    }
                    status.style.display = 'block';
                })
                .catch(function () {
                    status.textContent = 'Network error. Please try again.';
                    status.className = 'form-status error';
                    status.style.display = 'block';
                    btn.disabled = false;
                });
        });
    })();
    </script>
</body>
</html>
