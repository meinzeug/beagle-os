#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
PROVIDERS_DIR = Path(__file__).resolve().parents[1] / "providers"
SERVICES_DIR = Path(__file__).resolve().parents[1] / "services"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(PROVIDERS_DIR) not in sys.path:
    sys.path.insert(0, str(PROVIDERS_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from service_registry import *  # noqa: F401,F403
from service_registry import (  # private helpers used in main()
    _bootstrap_secret,
    _secret_store,
    _start_recording_retention_thread,
    _start_backup_scheduler_thread,
    _start_fleet_remediation_thread,
    initialize_job_worker_handlers,
)
import service_registry as _svc_registry  # needed to update module-level secrets in main()
from request_handler_mixin import HandlerMixin

from control_plane_handler import Handler  # noqa: F401  (Handler class extracted to services/control_plane_handler.py)


def main() -> int:
    global API_TOKEN, SCIM_BEARER_TOKEN, PAIRING_TOKEN_SECRET  # noqa: PLW0603
    # Auto-bootstrap: if secrets not set via env, load or generate from SecretStore.
    # Must update BOTH service_registry module globals (used by factory functions)
    # and control-plane.py module globals (used by Handler class at request time).
    _svc_registry.API_TOKEN = _bootstrap_secret("manager-api-token", _svc_registry.API_TOKEN, generate=True)
    _svc_registry.SCIM_BEARER_TOKEN = _bootstrap_secret("scim-bearer-token", _svc_registry.SCIM_BEARER_TOKEN, generate=False)
    _svc_registry.PAIRING_TOKEN_SECRET = _bootstrap_secret("pairing-token-secret", _svc_registry.PAIRING_TOKEN_SECRET, generate=True)
    API_TOKEN = _svc_registry.API_TOKEN
    SCIM_BEARER_TOKEN = _svc_registry.SCIM_BEARER_TOKEN
    PAIRING_TOKEN_SECRET = _svc_registry.PAIRING_TOKEN_SECRET
    # Wire AuditLogService into SecretStoreService (audit fn must be set after audit log is ready)
    def _audit_secret_event(event: str, details: dict) -> None:
        # Never include secret values in audit events
        safe_details = {k: v for k, v in details.items() if k != "value"}
        audit_log_service().write_event(event, "ok", details=safe_details)
    _secret_store()._audit_fn = _audit_secret_event
    effective_data_dir = ensure_data_dir()
    ensure_cluster_rpc_listener()
    initialize_job_worker_handlers()
    _start_recording_retention_thread()
    _start_backup_scheduler_thread()
    _start_fleet_remediation_thread()
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(
        json.dumps(
            {
                "service": "beagle-control-plane",
                "version": VERSION,
                "listen_host": LISTEN_HOST,
                "listen_port": LISTEN_PORT,
                "allow_localhost_noauth": ALLOW_LOCALHOST_NOAUTH,
                "data_dir": str(effective_data_dir),
            }
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if _svc_registry.RECORDING_RETENTION_STOP_EVENT is not None:
            _svc_registry.RECORDING_RETENTION_STOP_EVENT.set()
        if _svc_registry.RECORDING_RETENTION_THREAD is not None:
            _svc_registry.RECORDING_RETENTION_THREAD.join(timeout=5)
        if _svc_registry.BACKUP_SCHEDULER_STOP_EVENT is not None:
            _svc_registry.BACKUP_SCHEDULER_STOP_EVENT.set()
        if _svc_registry.BACKUP_SCHEDULER_THREAD is not None:
            _svc_registry.BACKUP_SCHEDULER_THREAD.join(timeout=5)
        if _svc_registry.FLEET_REMEDIATION_STOP_EVENT is not None:
            _svc_registry.FLEET_REMEDIATION_STOP_EVENT.set()
        if _svc_registry.FLEET_REMEDIATION_THREAD is not None:
            _svc_registry.FLEET_REMEDIATION_THREAD.join(timeout=5)
        if _svc_registry.CLUSTER_RPC_SERVER is not None:
            _svc_registry.CLUSTER_RPC_SERVER.shutdown()
            _svc_registry.CLUSTER_RPC_SERVER.server_close()
        if _svc_registry.CLUSTER_RPC_THREAD is not None:
            _svc_registry.CLUSTER_RPC_THREAD.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
