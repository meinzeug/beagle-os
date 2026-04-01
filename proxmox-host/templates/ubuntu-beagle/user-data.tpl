#cloud-config
autoinstall:
  version: 1
  locale: en_US.UTF-8
  keyboard:
    layout: us
  identity:
    hostname: __HOSTNAME__
    username: __GUEST_USER__
    password: "__GUEST_PASSWORD_HASH__"
  ssh:
    install-server: true
    allow-pw: true
  packages:
    - qemu-guest-agent
    - openssh-server
    - curl
    - ca-certificates
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
          ConditionPathExists=!/var/lib/beagle/ubuntu-firstboot.done

          [Service]
          Type=oneshot
          ExecStart=/usr/local/sbin/beagle-ubuntu-firstboot.sh
          Restart=on-failure
          RestartSec=15
          RemainAfterExit=yes

          [Install]
          WantedBy=multi-user.target
    runcmd:
      - [ systemctl, enable, --now, qemu-guest-agent.service ]
      - [ systemctl, enable, --now, beagle-ubuntu-firstboot.service ]
  late-commands:
    - curtin in-target --target=/target -- systemctl enable qemu-guest-agent.service
    - curtin in-target --target=/target -- sh -c 'for attempt in $(seq 1 20); do curl -fsS __PREPARE_FIRSTBOOT_CURL_ARGS__ --connect-timeout 5 --max-time 20 --retry 2 --retry-delay 2 -X POST "__PREPARE_FIRSTBOOT_URL__" >/dev/null && exit 0; sleep 5; done; exit 0'
