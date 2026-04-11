#!/usr/bin/env bash

runtime_network_dir() {
  printf '%s\n' "${RUNTIME_NETWORK_DIR:-/run/systemd/network}"
}

runtime_network_file() {
  local network_dir
  network_dir="$(runtime_network_dir)"
  printf '%s\n' "${NETWORK_FILE:-$network_dir/90-pve-thin-client.network}"
}

runtime_nm_connection_dir() {
  printf '%s\n' "${NM_CONNECTION_DIR:-/etc/NetworkManager/system-connections}"
}

runtime_nm_connection_file() {
  local connection_dir
  connection_dir="$(runtime_nm_connection_dir)"
  printf '%s\n' "${NM_CONNECTION_FILE:-$connection_dir/beagle-thinclient.nmconnection}"
}

runtime_resolv_conf_path() {
  printf '%s\n' "${RESOLV_CONF:-/etc/resolv.conf}"
}

resolve_dns_servers() {
  if [[ -n "${PVE_THIN_CLIENT_NETWORK_DNS_SERVERS:-}" ]]; then
    printf '%s\n' "${PVE_THIN_CLIENT_NETWORK_DNS_SERVERS}"
    return 0
  fi

  printf '%s\n' "${PVE_THIN_CLIENT_DEFAULT_DNS_SERVERS:-1.1.1.1 9.9.9.9 8.8.8.8}"
}

write_network_file() {
  local iface="$1"
  local network_dir network_file dns_servers static_cidr

  network_dir="$(runtime_network_dir)"
  network_file="$(runtime_network_file)"
  install -d -m 0755 "$network_dir"
  dns_servers="$(resolve_dns_servers)"
  static_cidr="$(static_ipv4_cidr 2>/dev/null || true)"

  {
    echo "[Match]"
    echo "Name=$iface"
    echo
    echo "[Network]"
    if [[ "${PVE_THIN_CLIENT_NETWORK_MODE:-dhcp}" == "static" ]]; then
      echo "Address=${PVE_THIN_CLIENT_NETWORK_STATIC_ADDRESS}/${PVE_THIN_CLIENT_NETWORK_STATIC_PREFIX:-24}"
      [[ -n "${PVE_THIN_CLIENT_NETWORK_GATEWAY:-}" ]] && echo "Gateway=${PVE_THIN_CLIENT_NETWORK_GATEWAY}"
      echo "DHCP=no"
    else
      echo "DHCP=yes"
    fi
    for dns in $dns_servers; do
      echo "DNS=$dns"
    done
    if [[ "${PVE_THIN_CLIENT_NETWORK_MODE:-dhcp}" == "static" && -n "$static_cidr" ]]; then
      echo
      echo "[Route]"
      echo "Destination=$static_cidr"
      echo "Scope=link"
      if [[ -n "${PVE_THIN_CLIENT_NETWORK_GATEWAY:-}" ]]; then
        echo
        echo "[Route]"
        echo "Destination=0.0.0.0/0"
        echo "Gateway=${PVE_THIN_CLIENT_NETWORK_GATEWAY}"
        echo "GatewayOnLink=yes"
      fi
    fi
  } >"$network_file"
}

write_nmconnection() {
  local iface="$1"
  local connection_dir connection_file dns_servers dns_csv address_line

  connection_dir="$(runtime_nm_connection_dir)"
  connection_file="$(runtime_nm_connection_file)"
  install -d -m 0700 "$connection_dir"
  dns_servers="$(resolve_dns_servers)"
  dns_csv="$(printf '%s\n' "$dns_servers" | tr ' ' ',' | sed 's/,$//')"

  {
    echo "[connection]"
    echo "id=beagle-thinclient"
    echo "uuid=3f5f30fe-1b98-45e1-a7ef-79f3f0cdfb27"
    echo "type=ethernet"
    echo "autoconnect=true"
    [[ -n "$iface" ]] && echo "interface-name=$iface"
    echo
    echo "[ethernet]"
    echo
    echo "[ipv4]"
    if [[ "${PVE_THIN_CLIENT_NETWORK_MODE:-dhcp}" == "static" ]]; then
      echo "method=manual"
      address_line="${PVE_THIN_CLIENT_NETWORK_STATIC_ADDRESS}/${PVE_THIN_CLIENT_NETWORK_STATIC_PREFIX:-24}"
      if [[ -n "${PVE_THIN_CLIENT_NETWORK_GATEWAY:-}" ]]; then
        address_line="${address_line},${PVE_THIN_CLIENT_NETWORK_GATEWAY}"
      fi
      echo "address1=${address_line}"
    else
      echo "method=auto"
    fi
    if [[ -n "$dns_csv" ]]; then
      echo "dns=$dns_csv;"
      echo "ignore-auto-dns=true"
    fi
    echo
    echo "[ipv6]"
    echo "method=ignore"
    echo
    echo "[proxy]"
  } >"$connection_file"

  chmod 0600 "$connection_file"
}

write_resolv_conf() {
  local dns_servers target_path resolv_conf

  resolv_conf="$(runtime_resolv_conf_path)"
  if [[ -L "$resolv_conf" ]]; then
    target_path="$(readlink -f "$resolv_conf" 2>/dev/null || true)"
    case "$target_path" in
      /run/systemd/resolve/stub-resolv.conf|/run/systemd/resolve/resolv.conf|"")
        rm -f "$resolv_conf" >/dev/null 2>&1 || true
        ;;
    esac
  fi

  if [[ -e "$resolv_conf" && ! -w "$resolv_conf" ]]; then
    return 0
  fi

  dns_servers="$(resolve_dns_servers)"

  {
    for dns in $dns_servers; do
      printf 'nameserver %s\n' "$dns"
    done
    printf 'options timeout:1 attempts:3 rotate\n'
  } >"$resolv_conf"

  chmod 0644 "$resolv_conf"
}
