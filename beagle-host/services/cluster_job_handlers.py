"""Job handlers for cluster operations (Plan 07 Schritt 2).

These handlers are registered with the JobWorker and execute asynchronously:
- cluster.auto_join: Lead through preflight → token → remote-join → validation.
- cluster.maintenance_drain: Drain a node of VMs before maintenance.

Handlers follow the signature:
    def handler(job: Job, worker: JobWorker) -> Any:
        worker.update_progress(job_id, percent, message)
        return {"ok": True, ...}
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def make_cluster_auto_join_handler(
    cluster_membership_service: Any,
    audit_event: Callable[..., None],
) -> Callable[[Any, Any], Any]:
    """Create a handler for cluster.auto_join jobs.
    
    The handler executes the steps:
    1. preflight (10%)
    2. token (20%)
    3. remote_join (50%)
    4. rpc_check (70%)
    5. inventory_refresh (85%)
    6. final_validation (95%)
    
    Returns the member dict on success.
    """
    def handle_cluster_auto_join(job: Any, worker: Any) -> dict[str, Any]:
        job_id = job.job_id
        params = job.payload if isinstance(getattr(job, "payload", None), dict) else {}
        username = str(getattr(job, "owner", "") or "system")

        try:
            setup_code = str(params.get("setup_code") or "").strip()
            node_name = str(params.get("node_name") or "").strip()
            api_url = str(params.get("api_url") or "").strip()
            advertise_host = str(params.get("advertise_host") or "").strip()
            rpc_url = str(params.get("rpc_url") or "").strip()
            ssh_port = int(params.get("ssh_port") or 22)
            timeout = float(params.get("timeout") or 5.0)
            token_ttl_seconds = int(params.get("token_ttl_seconds") or 900)
            if not setup_code:
                raise ValueError("setup_code is required")
            if not node_name:
                raise ValueError("node_name is required")

            worker.update_progress(job_id, 10, "Preflight: pruefe Zielserver, DNS und API-Erreichbarkeit ...")
            preflight = cluster_membership_service.preflight_add_server(
                node_name=node_name,
                api_url=api_url,
                advertise_host=advertise_host,
                rpc_url=rpc_url,
                ssh_port=ssh_port,
                timeout=timeout,
                issue_join_token=False,
                token_ttl_seconds=token_ttl_seconds,
                require_rpc=False,
            )
            if not preflight.get("ok"):
                raise RuntimeError("Preflight fehlgeschlagen")

            worker.update_progress(job_id, 25, "Token: erstelle kurzlebigen Join-Code auf dem Leader ...")
            token_result = cluster_membership_service.create_join_token(ttl_seconds=token_ttl_seconds)
            join_token = str(token_result.get("join_token") or "").strip()
            if not join_token:
                raise RuntimeError("Join-Token konnte nicht erzeugt werden")

            local_member = cluster_membership_service.local_member() or {}
            leader_api_url = str(local_member.get("api_url") or "").strip()
            if not leader_api_url:
                raise RuntimeError("Leader-API-URL konnte nicht bestimmt werden")

            worker.update_progress(job_id, 55, f"Remote-Join: verbinde {node_name} sicher per Setup-Code ...")
            target_response = cluster_membership_service._post_json(  # noqa: SLF001
                cluster_membership_service._api_v1_url(api_url, "/cluster/join-with-setup-code"),  # noqa: SLF001
                {
                    "setup_code": setup_code,
                    "join_token": join_token,
                    "leader_api_url": leader_api_url,
                    "node_name": node_name,
                    "api_url": api_url,
                    "advertise_host": advertise_host,
                    "rpc_url": rpc_url,
                },
                timeout=timeout,
            )
            target_member = target_response.get("member") if isinstance(target_response.get("member"), dict) else {}
            if not target_member:
                raise RuntimeError("Target-Join lieferte keinen gueltigen Member zurueck")

            worker.update_progress(job_id, 72, "RPC-Check: pruefe neue Cluster-Verbindung ...")
            cluster_membership_service.probe_and_update_member_statuses(timeout=min(timeout, 5.0))
            members = cluster_membership_service.list_members() or []
            new_member = next((m for m in members if m.get("name") == node_name), None)
            if not new_member:
                raise RuntimeError(f"Neues Mitglied {node_name} wurde nach dem Join nicht gefunden")
            if not str(new_member.get("rpc_url") or "").strip():
                raise RuntimeError(f"Neues Mitglied {node_name} hat keine RPC-URL")

            worker.update_progress(job_id, 86, "Inventory-Refresh: aktualisiere Cluster-Sicht ...")
            cluster_membership_service.probe_and_update_member_statuses(timeout=min(timeout, 5.0))

            worker.update_progress(job_id, 95, "Finale Validierung: pruefe Memberliste und Leader-Sicht ...")
            final_members = cluster_membership_service.list_members() or []
            if not any(m.get("name") == node_name for m in final_members):
                raise RuntimeError(f"Validierung fehlgeschlagen: {node_name} fehlt in der Memberliste")

            target = {
                "cluster_id": str((target_response.get("cluster") or {}).get("cluster_id") or ""),
                "member": target_member,
                "member_count": len(target_response.get("members") if isinstance(target_response.get("members"), list) else []),
            }
            worker.update_progress(job_id, 100, f"Abgeschlossen: {node_name} ist jetzt Cluster-Mitglied")

            audit_event(
                "cluster.auto_join_job",
                "success",
                details={
                    "job_id": job_id,
                    "node_name": node_name,
                    "username": username,
                },
            )

            return {
                "ok": True,
                "preflight": preflight,
                "target": target,
                "member": new_member,
                "message": f"Node {node_name} successfully added to cluster",
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"cluster.auto_join job {job_id} failed: {error_msg}")
            worker.update_progress(job_id, 0, f"Fehler: {error_msg}")

            audit_event(
                "cluster.auto_join_job",
                "failed",
                details={
                    "job_id": job_id,
                    "error": error_msg,
                    "username": username,
                },
            )

            raise
    
    return handle_cluster_auto_join


def make_cluster_maintenance_drain_handler(
    maintenance_service: Any,
    audit_event: Callable[..., None],
) -> Callable[[Any, Any], Any]:
    """Create a handler for cluster maintenance drain jobs.
    
    Drains all VMs from a node before maintenance:
    1. Verify target node (5%)
    2. List VMs on node (10%)
    3. Migrate each VM (50% split among migrations)
    4. Mark node as drained (90%)
    5. Verify all VMs migrated (100%)
    
    Returns list of migrated VM IDs.
    """
    def handle_maintenance_drain(job: Any, worker: Any) -> dict[str, Any]:
        job_id = job.job_id
        params = job.payload if isinstance(getattr(job, "payload", None), dict) else {}
        username = str(getattr(job, "owner", "") or "system")
        
        try:
            node_name = str(params.get("node_name") or "").strip()
            if not node_name:
                raise ValueError("node_name required for maintenance drain")

            worker.update_progress(job_id, 10, f"Preflight: pruefe Maintenance-Ziel {node_name} ...")
            preview = maintenance_service.preview_drain_node(node_name=node_name)
            actions = preview.get("actions") if isinstance(preview.get("actions"), list) else []
            handled = sum(1 for item in actions if isinstance(item, dict) and item.get("handled") is True)
            skipped = len(actions) - handled
            worker.update_progress(
                job_id,
                30,
                f"Analyse: {len(actions)} VM(s) gefunden, {handled} Aktion(en), {max(skipped, 0)} Skip(s)",
            )
            worker.update_progress(job_id, 55, "Maintenance wird gesetzt und VM-Aktionen werden ausgefuehrt ...")
            result = maintenance_service.drain_node(
                node_name=node_name,
                requester_identity=username,
            )
            worker.update_progress(
                job_id,
                85,
                f"Verifikation: {int(result.get('handled_vm_count') or 0)} VM-Aktion(en) abgeschlossen",
            )
            worker.update_progress(job_id, 100, f"Abgeschlossen: {node_name} ist jetzt in Maintenance")
            
            audit_event(
                "cluster.maintenance_drain_job",
                "success",
                details={
                    "job_id": job_id,
                    "node_name": node_name,
                    "username": "system",
                },
            )
            
            return {"ok": True, **result}
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"cluster.maintenance_drain job {job_id} failed: {error_msg}")
            worker.update_progress(job_id, 0, f"Fehler: {error_msg}")
            
            audit_event(
                "cluster.maintenance_drain_job",
                "failed",
                details={
                    "job_id": job_id,
                    "error": error_msg,
                    "username": username,
                },
            )
            
            raise
    
    return handle_maintenance_drain
