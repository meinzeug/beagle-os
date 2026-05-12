# Update SSH password and copy files
export SSHPASS='ZVyeJ8xFtPDX5Wwut8Mt7i'

# Find the files (paths might be different in the repo root)
BOOTSTRAP_PATH="thin-client-assistant/runtime/runtime_systemd_bootstrap.sh"
STARTX11_PATH="thin-client-assistant/live-build/config/includes.chroot/usr/local/bin/pve-thin-client-start-x11"

echo "Copying $BOOTSTRAP_PATH and $STARTX11_PATH"

sshpass -e scp -o StrictHostKeyChecking=no "$BOOTSTRAP_PATH" root@192.168.123.229:/usr/local/lib/pve-thin-client/runtime/runtime_systemd_bootstrap.sh
sshpass -e scp -o StrictHostKeyChecking=no "$STARTX11_PATH" root@192.168.123.229:/usr/local/bin/pve-thin-client-start-x11

# Run commands on guest
sshpass -e ssh -o StrictHostKeyChecking=no root@192.168.123.229 << 'GUEST_EOF'
rm -f /etc/systemd/system/getty@.service.d/zz-beagle-default.conf
mkdir -p /etc/systemd/system/getty@tty1.service.d/
cat << 'CONF' > /etc/systemd/system/getty@tty1.service.d/zz-beagle-autologin.conf
[Service]
ExecStart=
ExecStart=-/usr/local/bin/pve-thin-client-tty-login %I $TERM
CONF

# Fix the pve-thin-client-tty-login permissions if it was just copied (though we copied start-x11)
# Actually the query didn't ask to copy tty-login, but it's referenced in ExecStart.
# Let's check if it exists and is executable.
chmod +x /usr/local/bin/pve-thin-client-start-x11

systemctl daemon-reload
systemctl disable --now pve-thin-client-runtime.service
systemctl enable getty@tty1.service
systemctl restart getty@tty1.service
sleep 10

echo "--- systemctl cat getty@tty1.service ---"
systemctl cat getty@tty1.service
echo "--- ps output ---"
ps -ef | grep -E 'agetty|Xorg|xinit|start-pve-thin-client|launch-session|beagle-stream' | grep -v grep
echo "--- loginctl list-sessions ---"
loginctl list-sessions
echo "--- tail /tmp/pve-thin-client-logs/start-x11.log ---"
tail -n 20 /tmp/pve-thin-client-logs/start-x11.log
echo "--- latest Xorg log ---"
tail -n 20 /var/log/Xorg.0.log
echo "--- port 50000 check ---"
ss -tln | grep :50000 || echo "Port 50000 closed"

# Screenshot attempt
if [ -e /dev/fb0 ]; then
  cat /dev/fb0 > /tmp/beagle-vm100-liveusb-test-ttyfix.png
fi
ls -lh /tmp/beagle-vm100-liveusb-test-ttyfix.png || echo "No screenshot"
GUEST_EOF

sshpass -e scp -o StrictHostKeyChecking=no root@192.168.123.229:/tmp/beagle-vm100-liveusb-test-ttyfix.png /tmp/beagle-vm100-liveusb-test-ttyfix.png || true
ls -lh /tmp/beagle-vm100-liveusb-test-ttyfix.png || echo "Local screenshot missing"
