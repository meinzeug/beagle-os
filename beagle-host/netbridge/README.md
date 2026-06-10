# Beagle NetBridge

Make network devices that live on the **thin client's local LAN** usable from
inside the **streamed VM**.

A Beagle thin client streams the desktop of a VM that runs on a remote host
(`srv1`). The VM only has a network route to the thin client across the Beagle
WireGuard tunnel — it cannot see the thin client's local LAN (e.g.
`192.168.178.0/24`) where the user's Wi-Fi printer lives. NetBridge closes that
gap.

```
   VM (192.168.123.114)            srv1 (host)              Thin client            Local LAN
  ┌────────────────────┐   wg    ┌────────────┐    wg    ┌──────────────┐        ┌──────────┐
  │ beagle-netbridge-  │◀───────▶│  forward   │◀────────▶│ beagle-      │───────▶│ HP Wi-Fi │
  │ client → CUPS      │ 10.88.* │ virbr10↔wg │ 10.88.*  │ netbridge-   │  LAN   │ printer  │
  └────────────────────┘         └────────────┘          │ agent (proxy)│        └──────────┘
                                                          └──────────────┘
```

## Components

### `beagle-netbridge-agent` (thin client)
* Browses the local LAN for printer services via multicast DNS
  (`_ipp._tcp`, `_ipps._tcp`, `_pdl-datastream._tcp`, `_printer._tcp`).
  Pure standard-library mDNS — no dependency on `avahi`.
* Opens one plain TCP proxy per device service, bound to the WireGuard address
  (`10.88.1.x`) so only tunnel peers can reach it.
* Serves a JSON device catalog on the control port (`47100`).

Diagnostic run: `beagle-netbridge-agent --once` prints discovered devices.

Useful environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `BEAGLE_NETBRIDGE_BIND` | auto (wg-beagle IP) | address proxies/catalog bind to |
| `BEAGLE_NETBRIDGE_CONTROL_PORT` | `47100` | catalog control port |
| `BEAGLE_NETBRIDGE_DISCOVERY_INTERVAL` | `30` | seconds between LAN scans |
| `BEAGLE_NETBRIDGE_STATIC_PRINTERS` | – | `ip:port:rp,…` fallback if mDNS is unavailable |

### `beagle-netbridge-client` (VM)
* Connects to the agent (default `10.88.1.1:47100`, override via
  `/etc/beagle/netbridge.env`).
* Reconciles each bridged printer into CUPS with `lpadmin`, preferring driver-
  less IPP Everywhere and falling back to a raw JetDirect socket queue.
* Managed queues are named `beagle-net-*`; queues for devices that disappear are
  removed automatically.

`/etc/beagle/netbridge.env`:

```
BEAGLE_NETBRIDGE_AGENTS=10.88.1.1:47100
```

## Installation

* **VM**: installed automatically by the Ubuntu Beagle first-boot provisioning
  (`firstboot-provision.sh.tpl` → `install_beagle_netbridge_client`), which also
  pulls in the CUPS client tooling.
* **Thin client**: shipped in the thin-client image and enabled as
  `beagle-netbridge-agent.service`.
