# Cluster Store PoC (GoFuture 07 Schritt 1)

Dieser Ordner enthaelt bewusst nicht-produktive PoC-Helfer fuer die
Cluster-Store-Entscheidung in 7.0.

## Inhalte

- `store_poc.py`
  - `etcd`: prueft Leader-Election via `etcdctl move-leader`.
  - `sqlite-eval`: liefert Vergleichsmatrix etcd vs SQLite+Litestream.
- `run_etcd_cluster_poc.sh`
  - startet drei lokale etcd-Member (`host-a`, `host-b`, `witness`),
    fuehrt den PoC aus und beendet alle Prozesse wieder.

## Voraussetzungen

- `python3`
- `etcd` + `etcdctl` (z. B. `etcd-server`, `etcd-client`)

## Schneller Lauf

```bash
cd /home/dennis/beagle-os
chmod +x providers/beagle/cluster/run_etcd_cluster_poc.sh
providers/beagle/cluster/run_etcd_cluster_poc.sh
```

Erwartung: Ausgabe mit `"result": "pass"` fuer den etcd-PoC und
`ETCD_POC_RESULT=PASS` am Ende.

## Hinweis zur Architektur

Das PoC zeigt: etcd liefert native Leader-Election; fuer einen Zwei-Host-Betrieb
ist ein dritter Witness fuer sichere Quorum-Mehrheit erforderlich. SQLite+Litestream
ist fuer Replikation interessant, ersetzt aber keine Leader-Election-Authority.
