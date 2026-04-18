version: 2
ethernets:
  primary:
    match:
      macaddress: "__NETWORK_MAC__"
    dhcp4: true
    dhcp6: false