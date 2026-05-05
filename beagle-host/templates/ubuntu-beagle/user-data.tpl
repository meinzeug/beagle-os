#cloud-config
autoinstall:
  version: 1
  shutdown: poweroff
  # Skip downloading security updates during autoinstall (handled in firstboot)
  updates: none
  locale: __IDENTITY_LOCALE__
  network:
    version: 2
    ethernets:
      primary:
        match:
          macaddress: "__NETWORK_MAC__"
        dhcp4: true
        dhcp6: false
  keyboard:
    layout: __IDENTITY_KEYMAP__
  identity:
    hostname: __HOSTNAME__
    username: __GUEST_USER__
    password: "__GUEST_PASSWORD_HASH__"
  ssh:
    install-server: true
    allow-pw: true
  user-data:
    disable_root: true
    write_files:
      - path: /usr/local/sbin/beagle-ubuntu-firstboot.sh
        owner: root:root
        permissions: '0755'
        content: |
__FIRSTBOOT_SCRIPT__
      - path: /etc/systemd/system/beagle-ubuntu-firstboot.service
        owner: root:root
        permissions: '0644'
        content: |
          [Unit]
          Description=Beagle Ubuntu Desktop First Boot Provisioning
          After=network-online.target systemd-resolved.service
          Wants=network-online.target systemd-resolved.service
          StartLimitIntervalSec=0
          # Keep rerunning until callback+reboot handoff completed, even if
          # package/setup phase already finished and wrote ubuntu-firstboot.done.
          ConditionPathExists=!/var/lib/beagle/ubuntu-firstboot-callback.done

          [Service]
          Type=oneshot
          ExecStart=/usr/local/sbin/beagle-ubuntu-firstboot.sh
          Restart=on-failure
          RestartSec=15
          RemainAfterExit=yes

          [Install]
          WantedBy=multi-user.target
__DESKTOP_WALLPAPER_WRITE_FILE__
    runcmd:
      - [ systemctl, enable, --now, beagle-ubuntu-firstboot.service ]
  late-commands:
    - sh -c 'for attempt in $(seq 1 20); do if command -v curl >/dev/null 2>&1; then curl -fsS __PREPARE_FIRSTBOOT_CURL_ARGS__ --connect-timeout 5 --max-time 20 --retry 2 --retry-delay 2 -X POST "__PREPARE_FIRSTBOOT_URL__" >/dev/null && exit 0; elif command -v wget >/dev/null 2>&1; then wget -qO- --no-check-certificate --timeout=20 --post-data="" "__PREPARE_FIRSTBOOT_URL__" >/dev/null && exit 0; elif command -v python3 >/dev/null 2>&1; then python3 -c "import ssl,urllib.request; ctx=ssl._create_unverified_context(); req=urllib.request.Request(\"__PREPARE_FIRSTBOOT_URL__\", data=b\"\", method=\"POST\"); urllib.request.urlopen(req, timeout=20, context=ctx).read()" >/dev/null 2>&1 && exit 0; fi; sleep 5; done; exit 0'
    - curtin in-target --target=/target -- sh -c 'for attempt in $(seq 1 20); do if command -v curl >/dev/null 2>&1; then curl -fsS __PREPARE_FIRSTBOOT_CURL_ARGS__ --connect-timeout 5 --max-time 20 --retry 2 --retry-delay 2 -X POST "__PREPARE_FIRSTBOOT_URL__" >/dev/null && exit 0; elif command -v wget >/dev/null 2>&1; then wget -qO- --no-check-certificate --timeout=20 --post-data="" "__PREPARE_FIRSTBOOT_URL__" >/dev/null && exit 0; elif command -v python3 >/dev/null 2>&1; then python3 -c "import ssl,urllib.request; ctx=ssl._create_unverified_context(); req=urllib.request.Request(\"__PREPARE_FIRSTBOOT_URL__\", data=b\"\", method=\"POST\"); urllib.request.urlopen(req, timeout=20, context=ctx).read()" >/dev/null 2>&1 && exit 0; fi; sleep 5; done; exit 0'
