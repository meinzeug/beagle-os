# 01 — WebUI: app.js → ES-Module aufteilen

Stand: 2026-04-20  
Priorität: **Sofort** (April 2026)  
Betroffene Dateien: `website/app.js`, `website/main.js` (neu), `website/ui/*.js` (neu)

---

## Hintergrund

`website/app.js` enthält heute 4 379 Zeilen als einzelnes IIFE ohne jegliche Modul-Grenzen.
Alle ~100 Funktionen teilen denselben globalen Scope, was Wartung, Tests und paralleles
Arbeiten erheblich erschwert. Ziel ist die Aufteilung in 17 ES-Module unter `website/ui/`,
die native `import/export`-Syntax nutzen und ohne Build-Toolchain im Browser laufen.
Der Browser-CSP (`script-src 'self'`) erlaubt `type="module"` auf gleichem Origin bereits.
Die globalen Abhängigkeiten (`window.BeagleBrowserCommon`, `window.BEAGLE_WEB_UI_CONFIG`)
bleiben als klassische `<script>`-Tags vor dem Modul-Einstiegspunkt erhalten.

---

## Schritte

### Schritt 1 — Verzeichnis `website/ui/` anlegen und `state.js` erstellen

- [x] Verzeichnis `website/ui/` erzeugen.
- [x] Datei `website/ui/state.js` anlegen mit allen Konstanten und dem geteilten `state`-Objekt.

`state.js` hat keinerlei Imports und ist damit das unterste Blatt im Dependency-Graph.
Es exportiert ein einziges mutablees `state`-Objekt, das Panel-Zustand, Auth-Token, Flags
und Ladezustände enthält. Alle anderen Module importieren dieses Objekt und greifen darüber
auf den globalen Anwendungszustand zu. Die Konstanten (`SESSION_IDLE_TIMEOUT_MS`,
`FETCH_TIMEOUT_MS`, `MIN_PASSWORD_LEN`, `MIN_GUEST_PASSWORD_LEN`, `MAX_USERNAME_LEN`,
`USAGE_WARN_THRESHOLD`, `USAGE_INFO_THRESHOLD`, `USERNAME_PATTERN`, `ROLE_NAME_PATTERN`,
`POLICY_NAME_PATTERN`, `DISK_KEY_PATTERN`, `NET_KEY_PATTERN`, `VM_MAIN_KEYS`) wandern
ebenfalls hierher. `BULK_ACTION_BUTTON_IDS` und `panelMeta` gehören ebenfalls in diese Datei.
State wird nie direkt von außen überschrieben, sondern über definierte setter-Funktionen
in den jeweiligen Modulen modifiziert. Das Objekt enthält keine privaten Methoden.
Jeder Feldzugriff auf `state` ist damit vollständig nachvollziehbar und testbar.

---

### Schritt 2 — `website/ui/dom.js` erstellen

- [x] Datei `website/ui/dom.js` anlegen.
- [x] Alle UI-Hilfsfunktionen aus `app.js` hierher verschieben.

`dom.js` importiert nur `state.js` und exportiert alle rein präsentationalen Helfer.
Das sind: `qs` (querySelector-Wrapper), `text` (sicheres Text-setzen), `escapeHtml`,
`chip` (Status-Badge-Generator), `fieldBlock` (Key-Value-Zeile), `actionButton`
(Schaltflächen-Builder), `usageBar` (Fortschrittsbalken), `formatDate`, `formatGiB`,
`formatBytes`, `maskedFieldBlock` und `downloadTextFile`. Diese Funktionen haben keinerlei
Seiteneffekte auf den Netzwerk- oder Auth-Zustand und können damit isoliert unit-getestet
werden. Sie erzeugen HTML-Strings oder manipulieren DOM-Elemente, niemals API-Aufrufe.
Die strikte Trennung von DOM-Helfer und Business-Logik ist Voraussetzung für spätere
Storybook-ähnliche Entwicklung einzelner UI-Komponenten. `escapeHtml` und alle Funktionen
die HTML als String erzeugen müssen lückenlos jeden Nutzereingabe-Input escapen.

---

### Schritt 3 — `website/ui/api.js` erstellen

- [x] Datei `website/ui/api.js` anlegen.
- [x] Alle Netzwerk- und URL-Hilfsfunktionen aus `app.js` hierher verschieben.

`api.js` importiert `state.js` und `dom.js` und behandelt ausschließlich HTTP-Kommunikation.
Exportiert: `apiBase`, `resolveApiTarget`, `runSingleFlight`, `fetchWithTimeout`, `request`,
`blobRequest`, `postJson`, `downloadsBase`, `webUiUrl`, `isSafeExternalUrl`,
`trustedApiOrigins`, `normalizedOrigin`. Die `request`-Funktion enthält die gesamte
Retry-Logik inklusive Bearer-Token-Refresh; sie ruft `auth.js`-Funktionen über Parameter
entgegen, kein direktes zirkuläres Import auf Modulebene. `isSafeExternalUrl` blockiert
SSRF-Versuche durch Whitelist-Check gegen `trustedApiOrigins`. `runSingleFlight` verhindert
parallele gleichartige Requests bei Doppelklick. `fetchWithTimeout` wrapped native fetch mit
AbortController und konfigurierbarem Timeout aus `FETCH_TIMEOUT_MS`. Alle Fehler landen
als strukturierte Objekte mit `status` und `message` zurück beim Aufrufer.

---

### Schritt 4 — `website/ui/auth.js` erstellen

- [x] Datei `website/ui/auth.js` anlegen.
- [x] Alle Token-Store-, Session- und Auth-Funktionen aus `app.js` hierher verschieben.

`auth.js` importiert `state`, `dom`, `api` und enthält die gesamte Authentifizierungslogik.
Exportiert: `initTokenStores` (einmalig aus `main.js` aufgerufen, setzt `tokenStore` und
`refreshTokenStore` auf Basis von `window.BeagleBrowserCommon`), `buildAuthHeaders`,
`markSessionActivity`, `clearSessionState`, `logoutSession`, `refreshAccessToken`,
`lockSession`, `checkSessionTimeout`, `loginWithCredentials`, `saveToken`, `isAuthLocked`,
`recordAuthSuccess`, `recordAuthFailure`, `updateConnectButton`, `startAuthLockCountdown`,
`canRefreshAfterAuthError`, `shouldHardLockOnUnauthorized`, `sanitizeIdentifier`,
`sanitizePassword`. Token-Store-Instanzen sind Modul-private Variablen, nicht exportiert.
Refresh-in-Flight wird ebenfalls als Modul-private Variable verwaltet. Der Session-Idle-
Timer läuft über `checkSessionTimeout` als periodischer Check. Keine Klartext-Credentials
dürfen je in den State geschrieben werden.

---

### Schritt 5 — `website/ui/panels.js` erstellen

- [x] Datei `website/ui/panels.js` anlegen.
- [x] Panel-Navigation, Hash-Routing, Modals, Onboarding hierher verschieben.

`panels.js` steuert die gesamte Navigations- und Overlay-Logik der Anwendung.
Exportiert: `setActivePanel`, `setActiveDetailPanel`, `syncHash`, `parseAppHash`,
`consumeTokenFromLocation`, `applyTitle`, `setAuthMode`, `setBanner`, `requestConfirm`,
`updateSessionChrome`, `openAuthModal`, `closeAuthModal`, `openOnboardingModal`,
`closeOnboardingModal`, `fetchOnboardingStatus`, `completeOnboarding`, `accountShell`,
`closeAccountMenu`. Die Hash-Routing-Logik (`parseAppHash`/`syncHash`) parst
`window.location.hash` in ein strukturiertes Objekt mit `panel`, `detail` und `sub`.
`requestConfirm` öffnet ein einheitliches Bestätigungs-Modal und gibt ein Promise zurück.
`setAuthMode` blendet Shell-Chrome ein oder aus je nach Login-Zustand. `setBanner` zeigt
Erfolgs-, Warn- und Fehler-Nachrichten über dem Content-Bereich an.

---

### Schritt 6 — `website/ui/theme.js` erstellen

- [x] Datei `website/ui/theme.js` anlegen.
- [x] Dark-Mode-Logik isolieren.

`theme.js` hat keine Imports und ist vollständig in sich geschlossen.
Exportiert: `loadDarkModePreference`, `toggleDarkMode`, `updateDarkModeButton`.
Das Modul liest und schreibt `localStorage` unter dem Key `beagle-dark-mode`.
Beim Laden wird die Präferenz sofort auf `document.documentElement` angewendet,
um Flash-Of-Unstyled-Content zu vermeiden. `toggleDarkMode` toggelt die Klasse
`dark` auf dem `<html>`-Element und persistiert die neue Einstellung.
`updateDarkModeButton` aktualisiert das Icon im Header-Button. Das Modul ist
bewusst klein gehalten — kein State, keine API-Calls, keine DOM-Queries außerhalb.

---

### Schritt 7 — `website/ui/activity.js` erstellen

- [x] Datei `website/ui/activity.js` anlegen.
- [x] Activity-Log und Dashboard-Polling hierher verschieben.

`activity.js` importiert `state` und `dom` und verwaltet das Aktivitätsprotokoll.
Exportiert: `addToActivityLog`, `renderActivityLog`, `updateFleetHealthAlert`,
`startDashboardPoll`, `stopDashboardPoll`, `toggleAutoRefresh`, `updateAutoRefreshButton`.
Das Aktivitätsprotokoll ist ein Modul-privates Array mit maximal 100 Einträgen (FIFO).
`startDashboardPoll` startet einen `setInterval` der `loadDashboard` aus `dashboard.js`
periodisch aufruft; das Intervall-Handle wird Modul-privat gehalten.
`updateFleetHealthAlert` setzt oder entfernt den globalen Alert-Banner basierend
auf dem aktuellen Fleet-Health-Objekt. Auto-Refresh-Zustand wird in `state` gehalten.

---

### Schritt 8 — `website/ui/inventory.js` erstellen

- [x] Datei `website/ui/inventory.js` anlegen.
- [x] Inventory-Rendering, Filter, Bulk-Aktionen, Export hierher verschieben.

`inventory.js` importiert `state`, `dom`, `api` und enthält die gesamte VM-/Endpoint-
Listenlogik. Exportiert: `profileOf`, `roleOf`, `isBeagleVm`, `isEligible`,
`matchesRoleFilter`, `filteredInventory`, `resetInventoryFilters`,
`openInventoryWithNodeFilter`, `renderInventory`, `updateBulkUiState`,
`runVmPowerAction`, `bulkVmPowerAction`, `bulkAction`, `selectedVmidsFromInventory`,
`exportInventoryJson`, `exportInventoryCsv`, `exportEndpointsJson`,
`renderEndpointsOverview`, `renderDetail`, `loadDetail`, `clearSecretVault`,
`actionLabel`, `powerActionLabel`, `updateStateLabel`, `parseCommaList`.
`renderDetail` ist die größte Einzelfunktion (~300 Zeilen HTML-Builder) und bleibt
zunächst monolithisch; ein späterer Schritt kann sie in Sub-Renderer aufteilen.
Export-Funktionen nutzen `downloadTextFile` aus `dom.js` und bauen Daten aus `state`.
`clearSecretVault` löscht das Modul-private `secretVault`-Objekt sicher.

---

### Schritt 9 — `website/ui/virtualization.js` erstellen

- [x] Datei `website/ui/virtualization.js` anlegen.
- [x] Virtualisierungs-Panel, VM-Config, Inspector hierher verschieben.

`virtualization.js` importiert `state`, `dom`, `api` und rendert alle
Virtualisierungs-bezogenen Panels. Exportiert: `renderVirtualizationPanel`,
`renderVmConfigPanel`, `loadVmConfig`, `renderVirtualizationOverview`,
`renderVirtualizationInspector`, `loadVirtualizationInspector`,
`setVirtualizationNodeFilter`. Der Node-Filter für die Virtualisierungsansicht
ist Modul-privat als Variable gehalten und wird per `setVirtualizationNodeFilter`
gesetzt. `loadVirtualizationInspector` lädt Live-Stats (CPU, RAM, Netzwerk)
für eine einzelne VM und aktualisiert den Inspector-Bereich. `renderVmConfigPanel`
zeigt die editierbare VM-Konfiguration und nutzt `fieldBlock` aus `dom.js`.

---

### Schritt 10 — `website/ui/provisioning.js` erstellen

- [x] Datei `website/ui/provisioning.js` anlegen.
- [x] Provisioning-Workflow, Progress-Modal, Katalog hierher verschieben.

`provisioning.js` importiert `state`, `dom`, `api` sowie `loadDetail` aus `inventory.js`.
Exportiert: `renderProvisioningWorkspace`, `loadProvisioningCatalog`,
`createProvisionedVmWithPrefix`, `createProvisionedVm`, `createProvisionedVmFromModal`,
`openProvisionModal`, `closeProvisionModal`, `openProvisionProgressModal`,
`setProvisionProgressMessage`, `setProvisionProgressStep`, `finishProvisionProgress`,
`closeProvisionProgressModal`, `setProvisionCreateButtonsDisabled`,
`openProvisioningWorkspace`. Der mehrstufige Provision-Progress-State ist ein Modul-
privates Objekt mit `step`, `total` und `message`. `createProvisionedVm` führt den
gesamten API-Workflow durch (Template laden → VM anlegen → Config setzen → Start) und
aktualisiert Progress-Anzeige bei jedem Schritt. Nach erfolgreichem Anlegen wird
`loadDetail` aufgerufen, um direkt zur neuen VM zu navigieren.

---

### Schritt 11 — `website/ui/policies.js` erstellen

- [x] Datei `website/ui/policies.js` anlegen.
- [x] Policy-Editor, Speichern, Löschen hierher verschieben.

`policies.js` importiert `state`, `dom`, `api` und verwaltet den Policy-Editor.
Exportiert: `renderPolicies`, `resetPolicyEditor`, `loadPolicyIntoEditor`,
`savePolicy`, `deleteSelectedPolicy`, `parseJsonField`. `renderPolicies` baut die
Policy-Tabelle und den Editor-Bereich als HTML-String. `loadPolicyIntoEditor` lädt
eine existierende Policy in den Editor und befüllt alle Formularfelder. `savePolicy`
validiert das Formular, ruft die API auf und zeigt das Ergebnis-Banner an.
`deleteSelectedPolicy` fordert eine Bestätigung über `requestConfirm` aus `panels.js`
an. `parseJsonField` ist ein Hilfsparsing für JSON-Textarea-Inputs mit
nutzerverständlichen Fehlermeldungen bei Syntax-Fehlern.

---

### Schritt 12 — `website/ui/iam.js` erstellen

- [x] Datei `website/ui/iam.js` anlegen.
- [x] Alle IAM-CRUD-Funktionen (User, Roles) hierher verschieben.

`iam.js` importiert `state`, `dom`, `api` und enthält die gesamte IAM-Oberfläche.
Exportiert: `renderIam`, `renderIamUsers`, `renderIamRoles`, `renderIamRoleSelect`,
`resetIamUserEditor`, `resetIamRoleEditor`, `loadIamUserIntoEditor`,
`loadIamRoleIntoEditor`, `refreshIamData`, `saveIamUser`, `deleteIamUser`,
`revokeIamUserSessions`, `saveIamRole`, `deleteIamRole`, `parsePermissions`.
`refreshIamData` lädt User- und Role-Listen parallel über `Promise.all` und aktualisiert
den State. `revokeIamUserSessions` sendet einen separaten API-Call und benötigt
explizite Bestätigung. Passwörter werden niemals in den State gespeichert; der
Passwort-Input wird nach dem API-Call per `form.reset()` geleert.
`parsePermissions` wandelt Checkbox-Formulardaten in ein strukturiertes
Permission-Objekt für die API um.

---

### Schritt 13 — `website/ui/dashboard.js` erstellen

- [x] Datei `website/ui/dashboard.js` anlegen.
- [x] `loadDashboard` und `statCardFromHealth` hierher verschieben.

`dashboard.js` ist der zentrale Daten-Aggregator und importiert `state`, `api`,
`dom` sowie alle Render-Module (`inventory`, `virtualization`, `provisioning`, `iam`).
Exportiert: `loadDashboard`, `statCardFromHealth`. `loadDashboard` ist die
Masterfunktion die nach Login und periodisch durch das Dashboard-Polling aufgerufen
wird; sie lädt Health, Inventory, Nodes und weitere Datenpunkte und ruft dann
die jeweiligen Render-Funktionen auf. `statCardFromHealth` erzeugt einen KPI-Karten-
HTML-String aus einem Health-Datenobjekt. In-Flight-Deduplizierung verhindert parallele
`loadDashboard`-Aufrufe; die `dashboardLoadInFlight`-Flag ist Modul-privat.

---

### Schritt 14 — `website/ui/settings.js` erstellen

- [x] Datei `website/ui/settings.js` anlegen.
- [x] Alle Settings-Panel-Lade- und Speicherfunktionen hierher verschieben.

`settings.js` importiert `state`, `dom`, `api`, `auth` und enthält alle
Server-Settings-Panels. Exportiert: `isAdminRole`, `updateSettingsVisibility`,
`loadSettingsForPanel`, `bindSettingsEvents` sowie alle einzelnen
`loadSettings*`/`saveSettings*`-Funktionen. `loadSettingsForPanel` dispatcht
anhand des aktiven Sub-Panels auf die zugehörige Ladefunktion.
`bindSettingsEvents` registriert alle Form-Submit-Handler für Settings-Formulare.
`updateSettingsVisibility` zeigt oder versteckt admin-only Bereiche basierend auf
der aktuellen Rolle in `state`. Backup- und Restore-Funktionen laufen asynchron
und zeigen Progress-Feedback über `setBanner` aus `panels.js`.

---

### Schritt 15 — `website/ui/actions.js` erstellen

- [x] Datei `website/ui/actions.js` anlegen.
- [x] `executeAction` hierher verschieben.

`actions.js` importiert alle relevanten Module und enthält `executeAction`.
`executeAction` ist der zentrale Event-Dispatcher für VM-Aktionen (Start, Stop,
Reboot, Suspend, Reset, Shutdown, Console, Snapshot, Clone etc.). Jedes Action-Label
wird gegen einen switch-Baum verglichen und an die zugehörige Service-Funktion
delegiert. Aktionen die destruktiv sind (Delete, Reset) fordern via `requestConfirm`
eine Bestätigung an. Nach erfolgreicher Aktion wird der Inventory-State aktualisiert
und das Detail-Panel neu gerendert. Dieser Dispatcher-Ansatz hält die Events-
und Panel-Module von direkter Aktion-Logik getrennt.

---

### Schritt 16 — `website/ui/events.js` erstellen

- [x] Datei `website/ui/events.js` anlegen.
- [x] `bindEvents` hierher verschieben.

`events.js` importiert alle Module und registriert alle Event-Listener der Anwendung.
Exportiert: `bindEvents`. Diese Funktion wird einmalig aus `main.js` beim Bootstrap
aufgerufen und registriert alle `click`, `submit`, `keydown`, `change` und
`hashchange`-Listener. Event-Delegation über den `document`-Body wird für dynamisch
gerenderte Elemente (Tabellen-Buttons etc.) verwendet. Jeder Listener, der
sicherheitsrelevante Aktionen auslöst (Login, Passwort ändern, VM löschen), prüft
zusätzlich den aktuellen Auth-Zustand aus `state`. Kein Event-Listener darf in einem
anderen Modul außerhalb von `events.js` registriert werden (Ausnahme: Settings-spezifische
Listener in `bindSettingsEvents`).

---

### Schritt 17 — `website/main.js` als Einstiegspunkt erstellen

- [x] Datei `website/main.js` anlegen.
- [x] Bootstrap-Sequenz aus dem alten IIFE-Ende als `type="module"` Einstieg überführen.

`main.js` ist der einzige `<script type="module">`-Einstiegspunkt.
Er importiert `initTokenStores` aus `auth.js`, `loadDarkModePreference` aus `theme.js`,
`bindEvents` aus `events.js`, `loadDashboard` aus `dashboard.js` und weitere.
Als erste Aktion prüft er, ob `window.BeagleBrowserCommon` vorhanden ist und ruft
dann `initTokenStores(window.BeagleBrowserCommon)` auf. Danach startet er:
Dark-Mode-Präferenz laden, Event-Listener binden, Hash-Route parsen,
Onboarding-Status prüfen, Session prüfen, initiales Dashboard laden.
Der gesamte Bootstrap-Ablauf ist sequenziell und linear damit Fehler einfach
lokalisierbar sind. Das frühere Backup-Fallback über `app.js` wurde nach
Modultests entfernt.

---

## Testpflicht nach Abschluss

- [ ] Login funktioniert (Token wird korrekt gesetzt, `state.token` ist befüllt).
- [ ] Inventory lädt, Filter funktionieren, Bulk-Aktionen funktionieren.
- [ ] Provisioning-Workflow läuft durch (VM anlegen, Progress-Modal).
- [ ] IAM User und Roles CRUD funktionieren.
- [ ] Settings-Panels laden und speichern.
- [x] Dark Mode toggelt korrekt.
- [x] Hash-Navigation (`#panel=inventory`) ist funktionsfähig.
- [x] CSP-Verstöße in Browser-Devtools: keine.
