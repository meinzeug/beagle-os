#!/bin/bash
##############################################################################
# VM Pause-Flag Fix - Deployment Skript
# Deployment-Anleitung: 2026-04-20
#
# Dieses Skript deployed die VM Pause-Flag Fix auf beagle-server
# und startet den beagle-control-plane service neu.
#
# Ausführung: 
#   ./DEPLOYMENT-VM-PAUSE-FIX.sh
#
# Voraussetzungen:
#   - SSH-Schlüssel zu root@192.168.122.51 konfiguriert (oder .ssh/config)
#   - Im beagle-os Repository-Verzeichnis ausführen
#   - sudo oder root-Zugang für SSH
##############################################################################

set -euo pipefail

readonly REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
readonly HOST="192.168.122.51"
readonly BEAGLE_HOST_REMOTE="/opt/beagle/beagle-host"

# Dateien, die deployed werden
declare -a FILES=(
    "beagle-host/providers/host_provider_contract.py"
    "beagle-host/providers/beagle_host_provider.py"
    "beagle-host/providers/beagle_host_provider.py"
    "beagle-host/services/ubuntu_beagle_provisioning.py"
)

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          VM Pause-Flag Fix - Deployment                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Repository:  $REPO_DIR"
echo "Host:        $HOST"
echo "Remote Dir:  $BEAGLE_HOST_REMOTE"
echo ""

# Step 1: Verify connectivity
echo "[1/4] Überprüfe SSH-Verbindung zu beagle-server..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes root@"$HOST" "echo 'SSH OK'" >/dev/null 2>&1; then
    echo "✗ SSH-Verbindung zu $HOST fehlgeschlagen"
    echo ""
    echo "Versuche es mit:"
    echo "  ssh -i ~/.ssh/meinzeug_ed25519 root@$HOST"
    echo "oder konfiguriere ~/.ssh/config"
    exit 1
fi
echo "✓ SSH verbunden"
echo ""

# Step 2: Backup
echo "[2/4] Erstelle Backups auf beagle-server..."
ssh -o ConnectTimeout=10 root@"$HOST" bash -c "
  cd $BEAGLE_HOST_REMOTE
  BACKUP_TS=\$(date +%Y%m%d-%H%M%S)
  
  for file in providers/host_provider_contract.py providers/beagle_host_provider.py providers/beagle_host_provider.py services/ubuntu_beagle_provisioning.py; do
    if [[ -f \"\$file\" ]]; then
      cp \"\$file\" \"\$file.backup-\$BACKUP_TS\" 2>/dev/null && echo \"  ✓ \$file.backup-\$BACKUP_TS\" || true
    fi
  done
" || {
    echo "✗ Backup-Erstellung fehlgeschlagen - fahre trotzdem fort"
}
echo ""

# Step 3: Deploy Dateien (parallel)
echo "[3/4] Deploys Dateien..."
declare -a PIDS=()

for file in "${FILES[@]}"; do
    if [[ ! -f "$REPO_DIR/$file" ]]; then
        echo "✗ $file nicht gefunden!"
        exit 1
    fi
    
    target_dir=$(dirname "$BEAGLE_HOST_REMOTE/${file#beagle-host/}")
    target_file=$(basename "$file")
    
    # Copy parallel mit timeout
    (
        timeout 60 scp -p "$REPO_DIR/$file" root@"$HOST:$target_dir/" >/dev/null 2>&1 && \
        echo "  ✓ $file" || \
        echo "  ✗ $file (FAILED)"
    ) &
    PIDS+=($!)
done

# Wait for all parallel copies
for pid in "${PIDS[@]}"; do
    wait "$pid"
done

echo ""

# Step 4: Restart service
echo "[4/4] Starte beagle-control-plane service neu..."
ssh -o ConnectTimeout=10 root@"$HOST" bash -c '
  systemctl restart beagle-control-plane.service || {
    echo "Service-Restart fehlgeschlagen!"
    exit 1
  }
  sleep 2
  
  # Verify service is running
  if systemctl is-active --quiet beagle-control-plane.service; then
    echo "  ✓ Service aktiv und laufend"
    systemctl status beagle-control-plane.service --no-pager | head -8
  else
    echo "  ✗ Service ist nicht laufend"
    systemctl status beagle-control-plane.service --no-pager
    exit 1
  fi
' || {
    echo "✗ Service-Restart fehlgeschlagen"
    exit 1
}

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  ✓ DEPLOYMENT ERFOLGREICH ABGESCHLOSSEN                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "VM Pause-Flag Fix ist jetzt AKTIV!"
echo ""
echo "Nächste Schritte:"
echo "  1. Erstelle eine neue Test-VM über die Web-UI"
echo "  2. Beobachte, ob XFCE Desktop sofort nach Installation erscheint"
echo "  3. Falls Desktop nicht erscheint: Fehlerdiagnose im Provisioning-State"
echo ""
echo "Deployment-Logs sind verfügbar mit:"
echo "  ssh root@$HOST journalctl -u beagle-control-plane.service -f"
echo ""
