from collections.abc import Callable, Mapping, Sequence
from enum import IntEnum
from typing import Any, Final, Literal, Protocol, TypeAlias, overload, type_check_only

from gi import _gi
from gi.repository import Gio, GLib, GObject
from typing_extensions import TypeVarTuple, Unpack

_DataTs = TypeVarTuple("_DataTs", default=Unpack[tuple[()]])

ACCESS_POINT_BANDWIDTH: Final = "bandwidth"
ACCESS_POINT_BSSID: Final = "bssid"
ACCESS_POINT_FLAGS: Final = "flags"
ACCESS_POINT_FREQUENCY: Final = "frequency"
ACCESS_POINT_HW_ADDRESS: Final = "hw-address"
ACCESS_POINT_LAST_SEEN: Final = "last-seen"
ACCESS_POINT_MAX_BITRATE: Final = "max-bitrate"
ACCESS_POINT_MODE: Final = "mode"
ACCESS_POINT_RSN_FLAGS: Final = "rsn-flags"
ACCESS_POINT_SSID: Final = "ssid"
ACCESS_POINT_STRENGTH: Final = "strength"
ACCESS_POINT_WPA_FLAGS: Final = "wpa-flags"
ACTIVE_CONNECTION_CONNECTION: Final = "connection"
ACTIVE_CONNECTION_CONTROLLER: Final = "controller"
ACTIVE_CONNECTION_DEFAULT: Final = "default"
ACTIVE_CONNECTION_DEFAULT6: Final = "default6"
ACTIVE_CONNECTION_DEVICES: Final = "devices"
ACTIVE_CONNECTION_DHCP4_CONFIG: Final = "dhcp4-config"
ACTIVE_CONNECTION_DHCP6_CONFIG: Final = "dhcp6-config"
ACTIVE_CONNECTION_ID: Final = "id"
ACTIVE_CONNECTION_IP4_CONFIG: Final = "ip4-config"
ACTIVE_CONNECTION_IP6_CONFIG: Final = "ip6-config"
ACTIVE_CONNECTION_MASTER: Final = "master"
ACTIVE_CONNECTION_SPECIFIC_OBJECT_PATH: Final = "specific-object-path"
ACTIVE_CONNECTION_STATE: Final = "state"
ACTIVE_CONNECTION_STATE_FLAGS: Final = "state-flags"
ACTIVE_CONNECTION_TYPE: Final = "type"
ACTIVE_CONNECTION_UUID: Final = "uuid"
ACTIVE_CONNECTION_VPN: Final = "vpn"
BRIDGE_VLAN_VID_MAX: Final[int]
BRIDGE_VLAN_VID_MIN: Final[int]
CHECKPOINT_CREATED: Final = "created"
CHECKPOINT_DEVICES: Final = "devices"
CHECKPOINT_ROLLBACK_TIMEOUT: Final = "rollback-timeout"
CLIENT_ACTIVATING_CONNECTION: Final = "activating-connection"
CLIENT_ACTIVE_CONNECTIONS: Final = "active-connections"
CLIENT_ACTIVE_CONNECTION_ADDED: Final = "active-connection-added"
CLIENT_ACTIVE_CONNECTION_REMOVED: Final = "active-connection-removed"
CLIENT_ALL_DEVICES: Final = "all-devices"
CLIENT_ANY_DEVICE_ADDED: Final = "any-device-added"
CLIENT_ANY_DEVICE_REMOVED: Final = "any-device-removed"
CLIENT_CAN_MODIFY: Final = "can-modify"
CLIENT_CAPABILITIES: Final = "capabilities"
CLIENT_CHECKPOINTS: Final = "checkpoints"
CLIENT_CONNECTIONS: Final = "connections"
CLIENT_CONNECTION_ADDED: Final = "connection-added"
CLIENT_CONNECTION_REMOVED: Final = "connection-removed"
CLIENT_CONNECTIVITY: Final = "connectivity"
CLIENT_CONNECTIVITY_CHECK_AVAILABLE: Final = "connectivity-check-available"
CLIENT_CONNECTIVITY_CHECK_ENABLED: Final = "connectivity-check-enabled"
CLIENT_CONNECTIVITY_CHECK_URI: Final = "connectivity-check-uri"
CLIENT_DBUS_CONNECTION: Final = "dbus-connection"
CLIENT_DBUS_NAME_OWNER: Final = "dbus-name-owner"
CLIENT_DEVICES: Final = "devices"
CLIENT_DEVICE_ADDED: Final = "device-added"
CLIENT_DEVICE_REMOVED: Final = "device-removed"
CLIENT_DNS_CONFIGURATION: Final = "dns-configuration"
CLIENT_DNS_MODE: Final = "dns-mode"
CLIENT_DNS_RC_MANAGER: Final = "dns-rc-manager"
CLIENT_HOSTNAME: Final = "hostname"
CLIENT_INSTANCE_FLAGS: Final = "instance-flags"
CLIENT_METERED: Final = "metered"
CLIENT_NETWORKING_ENABLED: Final = "networking-enabled"
CLIENT_NM_RUNNING: Final = "nm-running"
CLIENT_PERMISSIONS_STATE: Final = "permissions-state"
CLIENT_PERMISSION_CHANGED: Final = "permission-changed"
CLIENT_PRIMARY_CONNECTION: Final = "primary-connection"
CLIENT_RADIO_FLAGS: Final = "radio-flags"
CLIENT_STARTUP: Final = "startup"
CLIENT_STATE: Final = "state"
CLIENT_VERSION: Final = "version"
CLIENT_VERSION_INFO: Final = "version-info"
CLIENT_WIMAX_ENABLED: Final = "wimax-enabled"
CLIENT_WIMAX_HARDWARE_ENABLED: Final = "wimax-hardware-enabled"
CLIENT_WIRELESS_ENABLED: Final = "wireless-enabled"
CLIENT_WIRELESS_HARDWARE_ENABLED: Final = "wireless-hardware-enabled"
CLIENT_WWAN_ENABLED: Final = "wwan-enabled"
CLIENT_WWAN_HARDWARE_ENABLED: Final = "wwan-hardware-enabled"
CONNECTION_CHANGED: Final = "changed"
CONNECTION_NORMALIZE_PARAM_IP4_CONFIG_METHOD: Final = "ip4-config-method"
CONNECTION_NORMALIZE_PARAM_IP6_CONFIG_METHOD: Final = "ip6-config-method"
CONNECTION_SECRETS_CLEARED: Final = "secrets-cleared"
CONNECTION_SECRETS_UPDATED: Final = "secrets-updated"
DBUS_INTERFACE: Final = "org.freedesktop.NetworkManager"
DBUS_INTERFACE_DNS_MANAGER: Final = "org.freedesktop.NetworkManager.DnsManager"
DBUS_INTERFACE_SETTINGS: Final = "org.freedesktop.NetworkManager.Settings"
DBUS_INTERFACE_SETTINGS_CONNECTION: Final = (
    "org.freedesktop.NetworkManager.Settings.Connection"
)
DBUS_INTERFACE_SETTINGS_CONNECTION_SECRETS: Final[str]
DBUS_INTERFACE_VPN: Final = "org.freedesktop.NetworkManager.VPN.Manager"
DBUS_INTERFACE_VPN_CONNECTION: Final = "org.freedesktop.NetworkManager.VPN.Connection"
DBUS_INVALID_VPN_CONNECTION: Final[str]
DBUS_NO_ACTIVE_VPN_CONNECTION: Final[str]
DBUS_NO_VPN_CONNECTIONS: Final[str]
DBUS_PATH: Final = "/org/freedesktop/NetworkManager"
DBUS_PATH_AGENT_MANAGER: Final = "/org/freedesktop/NetworkManager/AgentManager"
DBUS_PATH_DNS_MANAGER: Final = "/org/freedesktop/NetworkManager/DnsManager"
DBUS_PATH_SECRET_AGENT: Final = "/org/freedesktop/NetworkManager/SecretAgent"
DBUS_PATH_SETTINGS: Final = "/org/freedesktop/NetworkManager/Settings"
DBUS_PATH_SETTINGS_CONNECTION: Final[str]
DBUS_PATH_VPN: Final = "/org/freedesktop/NetworkManager/VPN/Manager"
DBUS_PATH_VPN_CONNECTION: Final = "/org/freedesktop/NetworkManager/VPN/Connection"
DBUS_SERVICE: Final = "org.freedesktop.NetworkManager"
DBUS_VPN_ALREADY_STARTED: Final = "AlreadyStarted"
DBUS_VPN_ALREADY_STOPPED: Final = "AlreadyStopped"
DBUS_VPN_BAD_ARGUMENTS: Final = "BadArguments"
DBUS_VPN_ERROR_PREFIX: Final = "org.freedesktop.NetworkManager.VPN.Error"
DBUS_VPN_INTERACTIVE_NOT_SUPPORTED: Final = "InteractiveNotSupported"
DBUS_VPN_SIGNAL_CONNECT_FAILED: Final = "ConnectFailed"
DBUS_VPN_SIGNAL_IP4_CONFIG: Final = "IP4Config"
DBUS_VPN_SIGNAL_IP_CONFIG_BAD: Final = "IPConfigBad"
DBUS_VPN_SIGNAL_LAUNCH_FAILED: Final = "LaunchFailed"
DBUS_VPN_SIGNAL_LOGIN_BANNER: Final = "LoginBanner"
DBUS_VPN_SIGNAL_LOGIN_FAILED: Final = "LoginFailed"
DBUS_VPN_SIGNAL_STATE_CHANGE: Final = "StateChange"
DBUS_VPN_SIGNAL_VPN_CONFIG_BAD: Final = "VPNConfigBad"
DBUS_VPN_STARTING_IN_PROGRESS: Final = "StartingInProgress"
DBUS_VPN_STOPPING_IN_PROGRESS: Final = "StoppingInProgress"
DBUS_VPN_WRONG_STATE: Final = "WrongState"
DEVICE_6LOWPAN_HW_ADDRESS: Final = "hw-address"
DEVICE_6LOWPAN_PARENT: Final = "parent"
DEVICE_ACTIVE_CONNECTION: Final = "active-connection"
DEVICE_ADSL_CARRIER: Final = "carrier"
DEVICE_AUTOCONNECT: Final = "autoconnect"
DEVICE_AVAILABLE_CONNECTIONS: Final = "available-connections"
DEVICE_BOND_CARRIER: Final = "carrier"
DEVICE_BOND_HW_ADDRESS: Final = "hw-address"
DEVICE_BOND_SLAVES: Final = "slaves"
DEVICE_BRIDGE_CARRIER: Final = "carrier"
DEVICE_BRIDGE_HW_ADDRESS: Final = "hw-address"
DEVICE_BRIDGE_SLAVES: Final = "slaves"
DEVICE_BT_CAPABILITIES: Final = "bt-capabilities"
DEVICE_BT_HW_ADDRESS: Final = "hw-address"
DEVICE_BT_NAME: Final = "name"
DEVICE_CAPABILITIES: Final = "capabilities"
DEVICE_DEVICE_TYPE: Final = "device-type"
DEVICE_DHCP4_CONFIG: Final = "dhcp4-config"
DEVICE_DHCP6_CONFIG: Final = "dhcp6-config"
DEVICE_DRIVER: Final = "driver"
DEVICE_DRIVER_VERSION: Final = "driver-version"
DEVICE_DUMMY_HW_ADDRESS: Final = "hw-address"
DEVICE_ETHERNET_CARRIER: Final = "carrier"
DEVICE_ETHERNET_HW_ADDRESS: Final = "hw-address"
DEVICE_ETHERNET_PERMANENT_HW_ADDRESS: Final = "perm-hw-address"
DEVICE_ETHERNET_S390_SUBCHANNELS: Final = "s390-subchannels"
DEVICE_ETHERNET_SPEED: Final = "speed"
DEVICE_FIRMWARE_MISSING: Final = "firmware-missing"
DEVICE_FIRMWARE_VERSION: Final = "firmware-version"
DEVICE_GENERIC_HW_ADDRESS: Final = "hw-address"
DEVICE_GENERIC_TYPE_DESCRIPTION: Final = "type-description"
DEVICE_GENEVE_DF: Final = "df"
DEVICE_GENEVE_DST_PORT: Final = "dst-port"
DEVICE_GENEVE_ID: Final = "id"
DEVICE_GENEVE_REMOTE: Final = "remote"
DEVICE_GENEVE_TOS: Final = "tos"
DEVICE_GENEVE_TTL: Final = "ttl"
DEVICE_HSR_MULTICAST_SPEC: Final = "multicast-spec"
DEVICE_HSR_PORT1: Final = "port1"
DEVICE_HSR_PORT2: Final = "port2"
DEVICE_HSR_PRP: Final = "prp"
DEVICE_HSR_SUPERVISION_ADDRESS: Final = "supervision-address"
DEVICE_HW_ADDRESS: Final = "hw-address"
DEVICE_INFINIBAND_CARRIER: Final = "carrier"
DEVICE_INFINIBAND_HW_ADDRESS: Final = "hw-address"
DEVICE_INTERFACE: Final = "interface"
DEVICE_INTERFACE_FLAGS: Final = "interface-flags"
DEVICE_IP4_CONFIG: Final = "ip4-config"
DEVICE_IP4_CONNECTIVITY: Final = "ip4-connectivity"
DEVICE_IP6_CONFIG: Final = "ip6-config"
DEVICE_IP6_CONNECTIVITY: Final = "ip6-connectivity"
DEVICE_IPVLAN_MODE: Final = "mode"
DEVICE_IPVLAN_PARENT: Final = "parent"
DEVICE_IPVLAN_PRIVATE: Final = "private"
DEVICE_IPVLAN_VEPA: Final = "vepa"
DEVICE_IP_INTERFACE: Final = "ip-interface"
DEVICE_IP_TUNNEL_ENCAPSULATION_LIMIT: Final = "encapsulation-limit"
DEVICE_IP_TUNNEL_FLAGS: Final = "flags"
DEVICE_IP_TUNNEL_FLOW_LABEL: Final = "flow-label"
DEVICE_IP_TUNNEL_FWMARK: Final = "fwmark"
DEVICE_IP_TUNNEL_INPUT_KEY: Final = "input-key"
DEVICE_IP_TUNNEL_LOCAL: Final = "local"
DEVICE_IP_TUNNEL_MODE: Final = "mode"
DEVICE_IP_TUNNEL_OUTPUT_KEY: Final = "output-key"
DEVICE_IP_TUNNEL_PARENT: Final = "parent"
DEVICE_IP_TUNNEL_PATH_MTU_DISCOVERY: Final = "path-mtu-discovery"
DEVICE_IP_TUNNEL_REMOTE: Final = "remote"
DEVICE_IP_TUNNEL_TOS: Final = "tos"
DEVICE_IP_TUNNEL_TTL: Final = "ttl"
DEVICE_LLDP_NEIGHBORS: Final = "lldp-neighbors"
DEVICE_MACSEC_CIPHER_SUITE: Final = "cipher-suite"
DEVICE_MACSEC_ENCODING_SA: Final = "encoding-sa"
DEVICE_MACSEC_ENCRYPT: Final = "encrypt"
DEVICE_MACSEC_ES: Final = "es"
DEVICE_MACSEC_HW_ADDRESS: Final = "hw-address"
DEVICE_MACSEC_ICV_LENGTH: Final = "icv-length"
DEVICE_MACSEC_INCLUDE_SCI: Final = "include-sci"
DEVICE_MACSEC_PARENT: Final = "parent"
DEVICE_MACSEC_PROTECT: Final = "protect"
DEVICE_MACSEC_REPLAY_PROTECT: Final = "replay-protect"
DEVICE_MACSEC_SCB: Final = "scb"
DEVICE_MACSEC_SCI: Final = "sci"
DEVICE_MACSEC_VALIDATION: Final = "validation"
DEVICE_MACSEC_WINDOW: Final = "window"
DEVICE_MACVLAN_HW_ADDRESS: Final = "hw-address"
DEVICE_MACVLAN_MODE: Final = "mode"
DEVICE_MACVLAN_NO_PROMISC: Final = "no-promisc"
DEVICE_MACVLAN_PARENT: Final = "parent"
DEVICE_MACVLAN_TAP: Final = "tap"
DEVICE_MANAGED: Final = "managed"
DEVICE_METERED: Final = "metered"
DEVICE_MODEM_APN: Final = "apn"
DEVICE_MODEM_CURRENT_CAPABILITIES: Final = "current-capabilities"
DEVICE_MODEM_DEVICE_ID: Final = "device-id"
DEVICE_MODEM_MODEM_CAPABILITIES: Final = "modem-capabilities"
DEVICE_MODEM_OPERATOR_CODE: Final = "operator-code"
DEVICE_MTU: Final = "mtu"
DEVICE_NM_PLUGIN_MISSING: Final = "nm-plugin-missing"
DEVICE_OLPC_MESH_ACTIVE_CHANNEL: Final = "active-channel"
DEVICE_OLPC_MESH_COMPANION: Final = "companion"
DEVICE_OLPC_MESH_HW_ADDRESS: Final = "hw-address"
DEVICE_OVS_BRIDGE_SLAVES: Final = "slaves"
DEVICE_OVS_PORT_SLAVES: Final = "slaves"
DEVICE_PATH: Final = "path"
DEVICE_PHYSICAL_PORT_ID: Final = "physical-port-id"
DEVICE_PORTS: Final = "ports"
DEVICE_PRODUCT: Final = "product"
DEVICE_REAL: Final = "real"
DEVICE_STATE: Final = "state"
DEVICE_STATE_REASON: Final = "state-reason"
DEVICE_TEAM_CARRIER: Final = "carrier"
DEVICE_TEAM_CONFIG: Final = "config"
DEVICE_TEAM_HW_ADDRESS: Final = "hw-address"
DEVICE_TEAM_SLAVES: Final = "slaves"
DEVICE_TUN_GROUP: Final = "group"
DEVICE_TUN_HW_ADDRESS: Final = "hw-address"
DEVICE_TUN_MODE: Final = "mode"
DEVICE_TUN_MULTI_QUEUE: Final = "multi-queue"
DEVICE_TUN_NO_PI: Final = "no-pi"
DEVICE_TUN_OWNER: Final = "owner"
DEVICE_TUN_VNET_HDR: Final = "vnet-hdr"
DEVICE_UDI: Final = "udi"
DEVICE_VENDOR: Final = "vendor"
DEVICE_VETH_PEER: Final = "peer"
DEVICE_VLAN_CARRIER: Final = "carrier"
DEVICE_VLAN_HW_ADDRESS: Final = "hw-address"
DEVICE_VLAN_PARENT: Final = "parent"
DEVICE_VLAN_VLAN_ID: Final = "vlan-id"
DEVICE_VRF_TABLE: Final = "table"
DEVICE_VXLAN_AGEING: Final = "ageing"
DEVICE_VXLAN_CARRIER: Final = "carrier"
DEVICE_VXLAN_DST_PORT: Final = "dst-port"
DEVICE_VXLAN_GROUP: Final = "group"
DEVICE_VXLAN_HW_ADDRESS: Final = "hw-address"
DEVICE_VXLAN_ID: Final = "id"
DEVICE_VXLAN_L2MISS: Final = "l2miss"
DEVICE_VXLAN_L3MISS: Final = "l3miss"
DEVICE_VXLAN_LEARNING: Final = "learning"
DEVICE_VXLAN_LIMIT: Final = "limit"
DEVICE_VXLAN_LOCAL: Final = "local"
DEVICE_VXLAN_PARENT: Final = "parent"
DEVICE_VXLAN_PROXY: Final = "proxy"
DEVICE_VXLAN_RSC: Final = "rsc"
DEVICE_VXLAN_SRC_PORT_MAX: Final = "src-port-max"
DEVICE_VXLAN_SRC_PORT_MIN: Final = "src-port-min"
DEVICE_VXLAN_TOS: Final = "tos"
DEVICE_VXLAN_TTL: Final = "ttl"
DEVICE_WIFI_ACCESS_POINTS: Final = "access-points"
DEVICE_WIFI_ACTIVE_ACCESS_POINT: Final = "active-access-point"
DEVICE_WIFI_BITRATE: Final = "bitrate"
DEVICE_WIFI_CAPABILITIES: Final = "wireless-capabilities"
DEVICE_WIFI_HW_ADDRESS: Final = "hw-address"
DEVICE_WIFI_LAST_SCAN: Final = "last-scan"
DEVICE_WIFI_MODE: Final = "mode"
DEVICE_WIFI_P2P_HW_ADDRESS: Final = "hw-address"
DEVICE_WIFI_P2P_PEERS: Final = "peers"
DEVICE_WIFI_P2P_WFDIES: Final = "wfdies"
DEVICE_WIFI_PERMANENT_HW_ADDRESS: Final = "perm-hw-address"
DEVICE_WIMAX_ACTIVE_NSP: Final = "active-nsp"
DEVICE_WIMAX_BSID: Final = "bsid"
DEVICE_WIMAX_CENTER_FREQUENCY: Final = "center-frequency"
DEVICE_WIMAX_CINR: Final = "cinr"
DEVICE_WIMAX_HW_ADDRESS: Final = "hw-address"
DEVICE_WIMAX_NSPS: Final = "nsps"
DEVICE_WIMAX_RSSI: Final = "rssi"
DEVICE_WIMAX_TX_POWER: Final = "tx-power"
DEVICE_WIREGUARD_FWMARK: Final = "fwmark"
DEVICE_WIREGUARD_LISTEN_PORT: Final = "listen-port"
DEVICE_WIREGUARD_PUBLIC_KEY: Final = "public-key"
DEVICE_WPAN_HW_ADDRESS: Final = "hw-address"
DHCP_CONFIG_FAMILY: Final = "family"
DHCP_CONFIG_OPTIONS: Final = "options"
ETHTOOL_OPTNAME_CHANNELS_COMBINED: Final = "channels-combined"
ETHTOOL_OPTNAME_CHANNELS_OTHER: Final = "channels-other"
ETHTOOL_OPTNAME_CHANNELS_RX: Final = "channels-rx"
ETHTOOL_OPTNAME_CHANNELS_TX: Final = "channels-tx"
ETHTOOL_OPTNAME_COALESCE_ADAPTIVE_RX: Final = "coalesce-adaptive-rx"
ETHTOOL_OPTNAME_COALESCE_ADAPTIVE_TX: Final = "coalesce-adaptive-tx"
ETHTOOL_OPTNAME_COALESCE_PKT_RATE_HIGH: Final = "coalesce-pkt-rate-high"
ETHTOOL_OPTNAME_COALESCE_PKT_RATE_LOW: Final = "coalesce-pkt-rate-low"
ETHTOOL_OPTNAME_COALESCE_RX_FRAMES: Final = "coalesce-rx-frames"
ETHTOOL_OPTNAME_COALESCE_RX_FRAMES_HIGH: Final = "coalesce-rx-frames-high"
ETHTOOL_OPTNAME_COALESCE_RX_FRAMES_IRQ: Final = "coalesce-rx-frames-irq"
ETHTOOL_OPTNAME_COALESCE_RX_FRAMES_LOW: Final = "coalesce-rx-frames-low"
ETHTOOL_OPTNAME_COALESCE_RX_USECS: Final = "coalesce-rx-usecs"
ETHTOOL_OPTNAME_COALESCE_RX_USECS_HIGH: Final = "coalesce-rx-usecs-high"
ETHTOOL_OPTNAME_COALESCE_RX_USECS_IRQ: Final = "coalesce-rx-usecs-irq"
ETHTOOL_OPTNAME_COALESCE_RX_USECS_LOW: Final = "coalesce-rx-usecs-low"
ETHTOOL_OPTNAME_COALESCE_SAMPLE_INTERVAL: Final = "coalesce-sample-interval"
ETHTOOL_OPTNAME_COALESCE_STATS_BLOCK_USECS: Final = "coalesce-stats-block-usecs"
ETHTOOL_OPTNAME_COALESCE_TX_FRAMES: Final = "coalesce-tx-frames"
ETHTOOL_OPTNAME_COALESCE_TX_FRAMES_HIGH: Final = "coalesce-tx-frames-high"
ETHTOOL_OPTNAME_COALESCE_TX_FRAMES_IRQ: Final = "coalesce-tx-frames-irq"
ETHTOOL_OPTNAME_COALESCE_TX_FRAMES_LOW: Final = "coalesce-tx-frames-low"
ETHTOOL_OPTNAME_COALESCE_TX_USECS: Final = "coalesce-tx-usecs"
ETHTOOL_OPTNAME_COALESCE_TX_USECS_HIGH: Final = "coalesce-tx-usecs-high"
ETHTOOL_OPTNAME_COALESCE_TX_USECS_IRQ: Final = "coalesce-tx-usecs-irq"
ETHTOOL_OPTNAME_COALESCE_TX_USECS_LOW: Final = "coalesce-tx-usecs-low"
ETHTOOL_OPTNAME_EEE_ENABLED: Final = "eee-enabled"
ETHTOOL_OPTNAME_FEATURE_ESP_HW_OFFLOAD: Final = "feature-esp-hw-offload"
ETHTOOL_OPTNAME_FEATURE_ESP_TX_CSUM_HW_OFFLOAD: Final = "feature-esp-tx-csum-hw-offload"
ETHTOOL_OPTNAME_FEATURE_FCOE_MTU: Final = "feature-fcoe-mtu"
ETHTOOL_OPTNAME_FEATURE_GRO: Final = "feature-gro"
ETHTOOL_OPTNAME_FEATURE_GSO: Final = "feature-gso"
ETHTOOL_OPTNAME_FEATURE_HIGHDMA: Final = "feature-highdma"
ETHTOOL_OPTNAME_FEATURE_HW_TC_OFFLOAD: Final = "feature-hw-tc-offload"
ETHTOOL_OPTNAME_FEATURE_L2_FWD_OFFLOAD: Final = "feature-l2-fwd-offload"
ETHTOOL_OPTNAME_FEATURE_LOOPBACK: Final = "feature-loopback"
ETHTOOL_OPTNAME_FEATURE_LRO: Final = "feature-lro"
ETHTOOL_OPTNAME_FEATURE_MACSEC_HW_OFFLOAD: Final = "feature-macsec-hw-offload"
ETHTOOL_OPTNAME_FEATURE_NTUPLE: Final = "feature-ntuple"
ETHTOOL_OPTNAME_FEATURE_RX: Final = "feature-rx"
ETHTOOL_OPTNAME_FEATURE_RXHASH: Final = "feature-rxhash"
ETHTOOL_OPTNAME_FEATURE_RXVLAN: Final = "feature-rxvlan"
ETHTOOL_OPTNAME_FEATURE_RX_ALL: Final = "feature-rx-all"
ETHTOOL_OPTNAME_FEATURE_RX_FCS: Final = "feature-rx-fcs"
ETHTOOL_OPTNAME_FEATURE_RX_GRO_HW: Final = "feature-rx-gro-hw"
ETHTOOL_OPTNAME_FEATURE_RX_GRO_LIST: Final = "feature-rx-gro-list"
ETHTOOL_OPTNAME_FEATURE_RX_UDP_GRO_FORWARDING: Final = "feature-rx-udp-gro-forwarding"
ETHTOOL_OPTNAME_FEATURE_RX_UDP_TUNNEL_PORT_OFFLOAD: Final = (
    "feature-rx-udp_tunnel-port-offload"
)
ETHTOOL_OPTNAME_FEATURE_RX_VLAN_FILTER: Final = "feature-rx-vlan-filter"
ETHTOOL_OPTNAME_FEATURE_RX_VLAN_STAG_FILTER: Final = "feature-rx-vlan-stag-filter"
ETHTOOL_OPTNAME_FEATURE_RX_VLAN_STAG_HW_PARSE: Final = "feature-rx-vlan-stag-hw-parse"
ETHTOOL_OPTNAME_FEATURE_SG: Final = "feature-sg"
ETHTOOL_OPTNAME_FEATURE_TLS_HW_RECORD: Final = "feature-tls-hw-record"
ETHTOOL_OPTNAME_FEATURE_TLS_HW_RX_OFFLOAD: Final = "feature-tls-hw-rx-offload"
ETHTOOL_OPTNAME_FEATURE_TLS_HW_TX_OFFLOAD: Final = "feature-tls-hw-tx-offload"
ETHTOOL_OPTNAME_FEATURE_TSO: Final = "feature-tso"
ETHTOOL_OPTNAME_FEATURE_TX: Final = "feature-tx"
ETHTOOL_OPTNAME_FEATURE_TXVLAN: Final = "feature-txvlan"
ETHTOOL_OPTNAME_FEATURE_TX_CHECKSUM_FCOE_CRC: Final = "feature-tx-checksum-fcoe-crc"
ETHTOOL_OPTNAME_FEATURE_TX_CHECKSUM_IPV4: Final = "feature-tx-checksum-ipv4"
ETHTOOL_OPTNAME_FEATURE_TX_CHECKSUM_IPV6: Final = "feature-tx-checksum-ipv6"
ETHTOOL_OPTNAME_FEATURE_TX_CHECKSUM_IP_GENERIC: Final = "feature-tx-checksum-ip-generic"
ETHTOOL_OPTNAME_FEATURE_TX_CHECKSUM_SCTP: Final = "feature-tx-checksum-sctp"
ETHTOOL_OPTNAME_FEATURE_TX_ESP_SEGMENTATION: Final = "feature-tx-esp-segmentation"
ETHTOOL_OPTNAME_FEATURE_TX_FCOE_SEGMENTATION: Final = "feature-tx-fcoe-segmentation"
ETHTOOL_OPTNAME_FEATURE_TX_GRE_CSUM_SEGMENTATION: Final = (
    "feature-tx-gre-csum-segmentation"
)
ETHTOOL_OPTNAME_FEATURE_TX_GRE_SEGMENTATION: Final = "feature-tx-gre-segmentation"
ETHTOOL_OPTNAME_FEATURE_TX_GSO_LIST: Final = "feature-tx-gso-list"
ETHTOOL_OPTNAME_FEATURE_TX_GSO_PARTIAL: Final = "feature-tx-gso-partial"
ETHTOOL_OPTNAME_FEATURE_TX_GSO_ROBUST: Final = "feature-tx-gso-robust"
ETHTOOL_OPTNAME_FEATURE_TX_IPXIP4_SEGMENTATION: Final = "feature-tx-ipxip4-segmentation"
ETHTOOL_OPTNAME_FEATURE_TX_IPXIP6_SEGMENTATION: Final = "feature-tx-ipxip6-segmentation"
ETHTOOL_OPTNAME_FEATURE_TX_NOCACHE_COPY: Final = "feature-tx-nocache-copy"
ETHTOOL_OPTNAME_FEATURE_TX_SCATTER_GATHER: Final = "feature-tx-scatter-gather"
ETHTOOL_OPTNAME_FEATURE_TX_SCATTER_GATHER_FRAGLIST: Final = (
    "feature-tx-scatter-gather-fraglist"
)
ETHTOOL_OPTNAME_FEATURE_TX_SCTP_SEGMENTATION: Final = "feature-tx-sctp-segmentation"
ETHTOOL_OPTNAME_FEATURE_TX_TCP6_SEGMENTATION: Final = "feature-tx-tcp6-segmentation"
ETHTOOL_OPTNAME_FEATURE_TX_TCP_ECN_SEGMENTATION: Final = (
    "feature-tx-tcp-ecn-segmentation"
)
ETHTOOL_OPTNAME_FEATURE_TX_TCP_MANGLEID_SEGMENTATION: Final = (
    "feature-tx-tcp-mangleid-segmentation"
)
ETHTOOL_OPTNAME_FEATURE_TX_TCP_SEGMENTATION: Final = "feature-tx-tcp-segmentation"
ETHTOOL_OPTNAME_FEATURE_TX_TUNNEL_REMCSUM_SEGMENTATION: Final = (
    "feature-tx-tunnel-remcsum-segmentation"
)
ETHTOOL_OPTNAME_FEATURE_TX_UDP_SEGMENTATION: Final = "feature-tx-udp-segmentation"
ETHTOOL_OPTNAME_FEATURE_TX_UDP_TNL_CSUM_SEGMENTATION: Final = (
    "feature-tx-udp_tnl-csum-segmentation"
)
ETHTOOL_OPTNAME_FEATURE_TX_UDP_TNL_SEGMENTATION: Final = (
    "feature-tx-udp_tnl-segmentation"
)
ETHTOOL_OPTNAME_FEATURE_TX_VLAN_STAG_HW_INSERT: Final = "feature-tx-vlan-stag-hw-insert"
ETHTOOL_OPTNAME_FEC_MODE: Final = "fec-mode"
ETHTOOL_OPTNAME_PAUSE_AUTONEG: Final = "pause-autoneg"
ETHTOOL_OPTNAME_PAUSE_RX: Final = "pause-rx"
ETHTOOL_OPTNAME_PAUSE_TX: Final = "pause-tx"
ETHTOOL_OPTNAME_RING_RX: Final = "ring-rx"
ETHTOOL_OPTNAME_RING_RX_JUMBO: Final = "ring-rx-jumbo"
ETHTOOL_OPTNAME_RING_RX_MINI: Final = "ring-rx-mini"
ETHTOOL_OPTNAME_RING_TX: Final = "ring-tx"
IP_ADDRESS_ATTRIBUTE_LABEL: Final = "label"
IP_CONFIG_ADDRESSES: Final = "addresses"
IP_CONFIG_CLAT_ADDRESS: Final = "clat-address"
IP_CONFIG_CLAT_PREF64: Final = "clat-pref64"
IP_CONFIG_DOMAINS: Final = "domains"
IP_CONFIG_FAMILY: Final = "family"
IP_CONFIG_GATEWAY: Final = "gateway"
IP_CONFIG_NAMESERVERS: Final = "nameservers"
IP_CONFIG_ROUTES: Final = "routes"
IP_CONFIG_SEARCHES: Final = "searches"
IP_CONFIG_WINS_SERVERS: Final = "wins-servers"
IP_ROUTE_ATTRIBUTE_ADVMSS: Final = "advmss"
IP_ROUTE_ATTRIBUTE_CWND: Final = "cwnd"
IP_ROUTE_ATTRIBUTE_FROM: Final = "from"
IP_ROUTE_ATTRIBUTE_INITCWND: Final = "initcwnd"
IP_ROUTE_ATTRIBUTE_INITRWND: Final = "initrwnd"
IP_ROUTE_ATTRIBUTE_LOCK_ADVMSS: Final = "lock-advmss"
IP_ROUTE_ATTRIBUTE_LOCK_CWND: Final = "lock-cwnd"
IP_ROUTE_ATTRIBUTE_LOCK_INITCWND: Final = "lock-initcwnd"
IP_ROUTE_ATTRIBUTE_LOCK_INITRWND: Final = "lock-initrwnd"
IP_ROUTE_ATTRIBUTE_LOCK_MTU: Final = "lock-mtu"
IP_ROUTE_ATTRIBUTE_LOCK_WINDOW: Final = "lock-window"
IP_ROUTE_ATTRIBUTE_MTU: Final = "mtu"
IP_ROUTE_ATTRIBUTE_ONLINK: Final = "onlink"
IP_ROUTE_ATTRIBUTE_QUICKACK: Final = "quickack"
IP_ROUTE_ATTRIBUTE_RTO_MIN: Final = "rto_min"
IP_ROUTE_ATTRIBUTE_SCOPE: Final = "scope"
IP_ROUTE_ATTRIBUTE_SRC: Final = "src"
IP_ROUTE_ATTRIBUTE_TABLE: Final = "table"
IP_ROUTE_ATTRIBUTE_TOS: Final = "tos"
IP_ROUTE_ATTRIBUTE_TYPE: Final = "type"
IP_ROUTE_ATTRIBUTE_WEIGHT: Final = "weight"
IP_ROUTE_ATTRIBUTE_WINDOW: Final = "window"
LLDP_ATTR_CHASSIS_ID: Final = "chassis-id"
LLDP_ATTR_CHASSIS_ID_TYPE: Final = "chassis-id-type"
LLDP_ATTR_DESTINATION: Final = "destination"
LLDP_ATTR_IEEE_802_1_PPVID: Final = "ieee-802-1-ppvid"
LLDP_ATTR_IEEE_802_1_PPVIDS: Final = "ieee-802-1-ppvids"
LLDP_ATTR_IEEE_802_1_PPVID_FLAGS: Final = "ieee-802-1-ppvid-flags"
LLDP_ATTR_IEEE_802_1_PVID: Final = "ieee-802-1-pvid"
LLDP_ATTR_IEEE_802_1_VID: Final = "ieee-802-1-vid"
LLDP_ATTR_IEEE_802_1_VLANS: Final = "ieee-802-1-vlans"
LLDP_ATTR_IEEE_802_1_VLAN_NAME: Final = "ieee-802-1-vlan-name"
LLDP_ATTR_IEEE_802_3_MAC_PHY_CONF: Final = "ieee-802-3-mac-phy-conf"
LLDP_ATTR_IEEE_802_3_MAX_FRAME_SIZE: Final = "ieee-802-3-max-frame-size"
LLDP_ATTR_IEEE_802_3_POWER_VIA_MDI: Final = "ieee-802-3-power-via-mdi"
LLDP_ATTR_MANAGEMENT_ADDRESSES: Final = "management-addresses"
LLDP_ATTR_MUD_URL: Final = "mud-url"
LLDP_ATTR_PORT_DESCRIPTION: Final = "port-description"
LLDP_ATTR_PORT_ID: Final = "port-id"
LLDP_ATTR_PORT_ID_TYPE: Final = "port-id-type"
LLDP_ATTR_RAW: Final = "raw"
LLDP_ATTR_SYSTEM_CAPABILITIES: Final = "system-capabilities"
LLDP_ATTR_SYSTEM_DESCRIPTION: Final = "system-description"
LLDP_ATTR_SYSTEM_NAME: Final = "system-name"
LLDP_DEST_NEAREST_BRIDGE: Final = "nearest-bridge"
LLDP_DEST_NEAREST_CUSTOMER_BRIDGE: Final = "nearest-customer-bridge"
LLDP_DEST_NEAREST_NON_TPMR_BRIDGE: Final = "nearest-non-tpmr-bridge"
MAJOR_VERSION: Final[int]
MICRO_VERSION: Final[int]
MINOR_VERSION: Final[int]
OBJECT_CLIENT: Final = "client"
OBJECT_PATH: Final = "path"
REMOTE_CONNECTION_DBUS_CONNECTION: Final = "dbus-connection"
REMOTE_CONNECTION_FILENAME: Final = "filename"
REMOTE_CONNECTION_FLAGS: Final = "flags"
REMOTE_CONNECTION_PATH: Final = "path"
REMOTE_CONNECTION_UNSAVED: Final = "unsaved"
REMOTE_CONNECTION_VERSION_ID: Final = "version-id"
REMOTE_CONNECTION_VISIBLE: Final = "visible"
SECRET_AGENT_OLD_AUTO_REGISTER: Final = "auto-register"
SECRET_AGENT_OLD_CAPABILITIES: Final = "capabilities"
SECRET_AGENT_OLD_DBUS_CONNECTION: Final = "dbus-connection"
SECRET_AGENT_OLD_IDENTIFIER: Final = "identifier"
SECRET_AGENT_OLD_REGISTERED: Final = "registered"
SECRET_TAG_DYNAMIC_CHALLENGE: Final = "x-dynamic-challenge:"
SECRET_TAG_DYNAMIC_CHALLENGE_ECHO: Final = "x-dynamic-challenge-echo:"
SECRET_TAG_VPN_MSG: Final = "x-vpn-message:"
SETTING_6LOWPAN_PARENT: Final = "parent"
SETTING_6LOWPAN_SETTING_NAME: Final = "6lowpan"
SETTING_802_1X_ALTSUBJECT_MATCHES: Final = "altsubject-matches"
SETTING_802_1X_ANONYMOUS_IDENTITY: Final = "anonymous-identity"
SETTING_802_1X_AUTH_TIMEOUT: Final = "auth-timeout"
SETTING_802_1X_CA_CERT: Final = "ca-cert"
SETTING_802_1X_CA_CERT_PASSWORD: Final = "ca-cert-password"
SETTING_802_1X_CA_CERT_PASSWORD_FLAGS: Final = "ca-cert-password-flags"
SETTING_802_1X_CA_PATH: Final = "ca-path"
SETTING_802_1X_CERT_SCHEME_PREFIX_PATH: Final = "file://"
SETTING_802_1X_CERT_SCHEME_PREFIX_PKCS11: Final = "pkcs11:"
SETTING_802_1X_CLIENT_CERT: Final = "client-cert"
SETTING_802_1X_CLIENT_CERT_PASSWORD: Final = "client-cert-password"
SETTING_802_1X_CLIENT_CERT_PASSWORD_FLAGS: Final = "client-cert-password-flags"
SETTING_802_1X_DOMAIN_MATCH: Final = "domain-match"
SETTING_802_1X_DOMAIN_SUFFIX_MATCH: Final = "domain-suffix-match"
SETTING_802_1X_EAP: Final = "eap"
SETTING_802_1X_IDENTITY: Final = "identity"
SETTING_802_1X_OPENSSL_CIPHERS: Final = "openssl-ciphers"
SETTING_802_1X_OPTIONAL: Final = "optional"
SETTING_802_1X_PAC_FILE: Final = "pac-file"
SETTING_802_1X_PASSWORD: Final = "password"
SETTING_802_1X_PASSWORD_FLAGS: Final = "password-flags"
SETTING_802_1X_PASSWORD_RAW: Final = "password-raw"
SETTING_802_1X_PASSWORD_RAW_FLAGS: Final = "password-raw-flags"
SETTING_802_1X_PHASE1_AUTH_FLAGS: Final = "phase1-auth-flags"
SETTING_802_1X_PHASE1_FAST_PROVISIONING: Final = "phase1-fast-provisioning"
SETTING_802_1X_PHASE1_PEAPLABEL: Final = "phase1-peaplabel"
SETTING_802_1X_PHASE1_PEAPVER: Final = "phase1-peapver"
SETTING_802_1X_PHASE2_ALTSUBJECT_MATCHES: Final = "phase2-altsubject-matches"
SETTING_802_1X_PHASE2_AUTH: Final = "phase2-auth"
SETTING_802_1X_PHASE2_AUTHEAP: Final = "phase2-autheap"
SETTING_802_1X_PHASE2_CA_CERT: Final = "phase2-ca-cert"
SETTING_802_1X_PHASE2_CA_CERT_PASSWORD: Final = "phase2-ca-cert-password"
SETTING_802_1X_PHASE2_CA_CERT_PASSWORD_FLAGS: Final = "phase2-ca-cert-password-flags"
SETTING_802_1X_PHASE2_CA_PATH: Final = "phase2-ca-path"
SETTING_802_1X_PHASE2_CLIENT_CERT: Final = "phase2-client-cert"
SETTING_802_1X_PHASE2_CLIENT_CERT_PASSWORD: Final = "phase2-client-cert-password"
SETTING_802_1X_PHASE2_CLIENT_CERT_PASSWORD_FLAGS: Final = (
    "phase2-client-cert-password-flags"
)
SETTING_802_1X_PHASE2_DOMAIN_MATCH: Final = "phase2-domain-match"
SETTING_802_1X_PHASE2_DOMAIN_SUFFIX_MATCH: Final = "phase2-domain-suffix-match"
SETTING_802_1X_PHASE2_PRIVATE_KEY: Final = "phase2-private-key"
SETTING_802_1X_PHASE2_PRIVATE_KEY_PASSWORD: Final = "phase2-private-key-password"
SETTING_802_1X_PHASE2_PRIVATE_KEY_PASSWORD_FLAGS: Final = (
    "phase2-private-key-password-flags"
)
SETTING_802_1X_PHASE2_SUBJECT_MATCH: Final = "phase2-subject-match"
SETTING_802_1X_PIN: Final = "pin"
SETTING_802_1X_PIN_FLAGS: Final = "pin-flags"
SETTING_802_1X_PRIVATE_KEY: Final = "private-key"
SETTING_802_1X_PRIVATE_KEY_PASSWORD: Final = "private-key-password"
SETTING_802_1X_PRIVATE_KEY_PASSWORD_FLAGS: Final = "private-key-password-flags"
SETTING_802_1X_SETTING_NAME: Final = "802-1x"
SETTING_802_1X_SUBJECT_MATCH: Final = "subject-match"
SETTING_802_1X_SYSTEM_CA_CERTS: Final = "system-ca-certs"
SETTING_ADSL_ENCAPSULATION: Final = "encapsulation"
SETTING_ADSL_ENCAPSULATION_LLC: Final = "llc"
SETTING_ADSL_ENCAPSULATION_VCMUX: Final = "vcmux"
SETTING_ADSL_PASSWORD: Final = "password"
SETTING_ADSL_PASSWORD_FLAGS: Final = "password-flags"
SETTING_ADSL_PROTOCOL: Final = "protocol"
SETTING_ADSL_PROTOCOL_IPOATM: Final = "ipoatm"
SETTING_ADSL_PROTOCOL_PPPOA: Final = "pppoa"
SETTING_ADSL_PROTOCOL_PPPOE: Final = "pppoe"
SETTING_ADSL_SETTING_NAME: Final = "adsl"
SETTING_ADSL_USERNAME: Final = "username"
SETTING_ADSL_VCI: Final = "vci"
SETTING_ADSL_VPI: Final = "vpi"
SETTING_BLUETOOTH_BDADDR: Final = "bdaddr"
SETTING_BLUETOOTH_SETTING_NAME: Final = "bluetooth"
SETTING_BLUETOOTH_TYPE: Final = "type"
SETTING_BLUETOOTH_TYPE_DUN: Final = "dun"
SETTING_BLUETOOTH_TYPE_NAP: Final = "nap"
SETTING_BLUETOOTH_TYPE_PANU: Final = "panu"
SETTING_BOND_OPTIONS: Final = "options"
SETTING_BOND_OPTION_ACTIVE_SLAVE: Final = "active_slave"
SETTING_BOND_OPTION_AD_ACTOR_SYSTEM: Final = "ad_actor_system"
SETTING_BOND_OPTION_AD_ACTOR_SYS_PRIO: Final = "ad_actor_sys_prio"
SETTING_BOND_OPTION_AD_SELECT: Final = "ad_select"
SETTING_BOND_OPTION_AD_USER_PORT_KEY: Final = "ad_user_port_key"
SETTING_BOND_OPTION_ALL_SLAVES_ACTIVE: Final = "all_slaves_active"
SETTING_BOND_OPTION_ARP_ALL_TARGETS: Final = "arp_all_targets"
SETTING_BOND_OPTION_ARP_INTERVAL: Final = "arp_interval"
SETTING_BOND_OPTION_ARP_IP_TARGET: Final = "arp_ip_target"
SETTING_BOND_OPTION_ARP_MISSED_MAX: Final = "arp_missed_max"
SETTING_BOND_OPTION_ARP_VALIDATE: Final = "arp_validate"
SETTING_BOND_OPTION_BALANCE_SLB: Final = "balance-slb"
SETTING_BOND_OPTION_DOWNDELAY: Final = "downdelay"
SETTING_BOND_OPTION_FAIL_OVER_MAC: Final = "fail_over_mac"
SETTING_BOND_OPTION_LACP_ACTIVE: Final = "lacp_active"
SETTING_BOND_OPTION_LACP_RATE: Final = "lacp_rate"
SETTING_BOND_OPTION_LP_INTERVAL: Final = "lp_interval"
SETTING_BOND_OPTION_MIIMON: Final = "miimon"
SETTING_BOND_OPTION_MIN_LINKS: Final = "min_links"
SETTING_BOND_OPTION_MODE: Final = "mode"
SETTING_BOND_OPTION_NS_IP6_TARGET: Final = "ns_ip6_target"
SETTING_BOND_OPTION_NUM_GRAT_ARP: Final = "num_grat_arp"
SETTING_BOND_OPTION_NUM_UNSOL_NA: Final = "num_unsol_na"
SETTING_BOND_OPTION_PACKETS_PER_SLAVE: Final = "packets_per_slave"
SETTING_BOND_OPTION_PEER_NOTIF_DELAY: Final = "peer_notif_delay"
SETTING_BOND_OPTION_PRIMARY: Final = "primary"
SETTING_BOND_OPTION_PRIMARY_RESELECT: Final = "primary_reselect"
SETTING_BOND_OPTION_RESEND_IGMP: Final = "resend_igmp"
SETTING_BOND_OPTION_TLB_DYNAMIC_LB: Final = "tlb_dynamic_lb"
SETTING_BOND_OPTION_UPDELAY: Final = "updelay"
SETTING_BOND_OPTION_USE_CARRIER: Final = "use_carrier"
SETTING_BOND_OPTION_XMIT_HASH_POLICY: Final = "xmit_hash_policy"
SETTING_BOND_PORT_PRIO: Final = "prio"
SETTING_BOND_PORT_QUEUE_ID: Final = "queue-id"
SETTING_BOND_PORT_SETTING_NAME: Final = "bond-port"
SETTING_BOND_SETTING_NAME: Final = "bond"
SETTING_BRIDGE_AGEING_TIME: Final = "ageing-time"
SETTING_BRIDGE_FORWARD_DELAY: Final = "forward-delay"
SETTING_BRIDGE_GROUP_ADDRESS: Final = "group-address"
SETTING_BRIDGE_GROUP_FORWARD_MASK: Final = "group-forward-mask"
SETTING_BRIDGE_HELLO_TIME: Final = "hello-time"
SETTING_BRIDGE_MAC_ADDRESS: Final = "mac-address"
SETTING_BRIDGE_MAX_AGE: Final = "max-age"
SETTING_BRIDGE_MULTICAST_HASH_MAX: Final = "multicast-hash-max"
SETTING_BRIDGE_MULTICAST_LAST_MEMBER_COUNT: Final = "multicast-last-member-count"
SETTING_BRIDGE_MULTICAST_LAST_MEMBER_INTERVAL: Final = "multicast-last-member-interval"
SETTING_BRIDGE_MULTICAST_MEMBERSHIP_INTERVAL: Final = "multicast-membership-interval"
SETTING_BRIDGE_MULTICAST_QUERIER: Final = "multicast-querier"
SETTING_BRIDGE_MULTICAST_QUERIER_INTERVAL: Final = "multicast-querier-interval"
SETTING_BRIDGE_MULTICAST_QUERY_INTERVAL: Final = "multicast-query-interval"
SETTING_BRIDGE_MULTICAST_QUERY_RESPONSE_INTERVAL: Final = (
    "multicast-query-response-interval"
)
SETTING_BRIDGE_MULTICAST_QUERY_USE_IFADDR: Final = "multicast-query-use-ifaddr"
SETTING_BRIDGE_MULTICAST_ROUTER: Final = "multicast-router"
SETTING_BRIDGE_MULTICAST_SNOOPING: Final = "multicast-snooping"
SETTING_BRIDGE_MULTICAST_STARTUP_QUERY_COUNT: Final = "multicast-startup-query-count"
SETTING_BRIDGE_MULTICAST_STARTUP_QUERY_INTERVAL: Final = (
    "multicast-startup-query-interval"
)
SETTING_BRIDGE_PORT_HAIRPIN_MODE: Final = "hairpin-mode"
SETTING_BRIDGE_PORT_PATH_COST: Final = "path-cost"
SETTING_BRIDGE_PORT_PRIORITY: Final = "priority"
SETTING_BRIDGE_PORT_SETTING_NAME: Final = "bridge-port"
SETTING_BRIDGE_PORT_VLANS: Final = "vlans"
SETTING_BRIDGE_PRIORITY: Final = "priority"
SETTING_BRIDGE_SETTING_NAME: Final = "bridge"
SETTING_BRIDGE_STP: Final = "stp"
SETTING_BRIDGE_VLANS: Final = "vlans"
SETTING_BRIDGE_VLAN_DEFAULT_PVID: Final = "vlan-default-pvid"
SETTING_BRIDGE_VLAN_FILTERING: Final = "vlan-filtering"
SETTING_BRIDGE_VLAN_PROTOCOL: Final = "vlan-protocol"
SETTING_BRIDGE_VLAN_STATS_ENABLED: Final = "vlan-stats-enabled"
SETTING_CDMA_MTU: Final = "mtu"
SETTING_CDMA_NUMBER: Final = "number"
SETTING_CDMA_PASSWORD: Final = "password"
SETTING_CDMA_PASSWORD_FLAGS: Final = "password-flags"
SETTING_CDMA_SETTING_NAME: Final = "cdma"
SETTING_CDMA_USERNAME: Final = "username"
SETTING_CONNECTION_AUTH_RETRIES: Final = "auth-retries"
SETTING_CONNECTION_AUTOCONNECT: Final = "autoconnect"
SETTING_CONNECTION_AUTOCONNECT_PORTS: Final = "autoconnect-ports"
SETTING_CONNECTION_AUTOCONNECT_PRIORITY: Final = "autoconnect-priority"
SETTING_CONNECTION_AUTOCONNECT_PRIORITY_DEFAULT: Final[int]
SETTING_CONNECTION_AUTOCONNECT_PRIORITY_MAX: Final[int]
SETTING_CONNECTION_AUTOCONNECT_PRIORITY_MIN: Final[int]
SETTING_CONNECTION_AUTOCONNECT_RETRIES: Final = "autoconnect-retries"
SETTING_CONNECTION_AUTOCONNECT_SLAVES: Final = "autoconnect-slaves"
SETTING_CONNECTION_CONTROLLER: Final = "controller"
SETTING_CONNECTION_DNSSEC: Final = "dnssec"
SETTING_CONNECTION_DNS_OVER_TLS: Final = "dns-over-tls"
SETTING_CONNECTION_DOWN_ON_POWEROFF: Final = "down-on-poweroff"
SETTING_CONNECTION_GATEWAY_PING_TIMEOUT: Final = "gateway-ping-timeout"
SETTING_CONNECTION_ID: Final = "id"
SETTING_CONNECTION_INTERFACE_NAME: Final = "interface-name"
SETTING_CONNECTION_IP_PING_ADDRESSES: Final = "ip-ping-addresses"
SETTING_CONNECTION_IP_PING_ADDRESSES_REQUIRE_ALL: Final = (
    "ip-ping-addresses-require-all"
)
SETTING_CONNECTION_IP_PING_TIMEOUT: Final = "ip-ping-timeout"
SETTING_CONNECTION_LLDP: Final = "lldp"
SETTING_CONNECTION_LLMNR: Final = "llmnr"
SETTING_CONNECTION_MASTER: Final = "master"
SETTING_CONNECTION_MDNS: Final = "mdns"
SETTING_CONNECTION_METERED: Final = "metered"
SETTING_CONNECTION_MPTCP_FLAGS: Final = "mptcp-flags"
SETTING_CONNECTION_MUD_URL: Final = "mud-url"
SETTING_CONNECTION_MULTI_CONNECT: Final = "multi-connect"
SETTING_CONNECTION_PERMISSIONS: Final = "permissions"
SETTING_CONNECTION_PORT_TYPE: Final = "port-type"
SETTING_CONNECTION_READ_ONLY: Final = "read-only"
SETTING_CONNECTION_SECONDARIES: Final = "secondaries"
SETTING_CONNECTION_SETTING_NAME: Final = "connection"
SETTING_CONNECTION_SLAVE_TYPE: Final = "slave-type"
SETTING_CONNECTION_STABLE_ID: Final = "stable-id"
SETTING_CONNECTION_TIMESTAMP: Final = "timestamp"
SETTING_CONNECTION_TYPE: Final = "type"
SETTING_CONNECTION_UUID: Final = "uuid"
SETTING_CONNECTION_WAIT_ACTIVATION_DELAY: Final = "wait-activation-delay"
SETTING_CONNECTION_WAIT_DEVICE_TIMEOUT: Final = "wait-device-timeout"
SETTING_CONNECTION_ZONE: Final = "zone"
SETTING_DCB_APP_FCOE_FLAGS: Final = "app-fcoe-flags"
SETTING_DCB_APP_FCOE_MODE: Final = "app-fcoe-mode"
SETTING_DCB_APP_FCOE_PRIORITY: Final = "app-fcoe-priority"
SETTING_DCB_APP_FIP_FLAGS: Final = "app-fip-flags"
SETTING_DCB_APP_FIP_PRIORITY: Final = "app-fip-priority"
SETTING_DCB_APP_ISCSI_FLAGS: Final = "app-iscsi-flags"
SETTING_DCB_APP_ISCSI_PRIORITY: Final = "app-iscsi-priority"
SETTING_DCB_FCOE_MODE_FABRIC: Final = "fabric"
SETTING_DCB_FCOE_MODE_VN2VN: Final = "vn2vn"
SETTING_DCB_PRIORITY_BANDWIDTH: Final = "priority-bandwidth"
SETTING_DCB_PRIORITY_FLOW_CONTROL: Final = "priority-flow-control"
SETTING_DCB_PRIORITY_FLOW_CONTROL_FLAGS: Final = "priority-flow-control-flags"
SETTING_DCB_PRIORITY_GROUP_BANDWIDTH: Final = "priority-group-bandwidth"
SETTING_DCB_PRIORITY_GROUP_FLAGS: Final = "priority-group-flags"
SETTING_DCB_PRIORITY_GROUP_ID: Final = "priority-group-id"
SETTING_DCB_PRIORITY_STRICT_BANDWIDTH: Final = "priority-strict-bandwidth"
SETTING_DCB_PRIORITY_TRAFFIC_CLASS: Final = "priority-traffic-class"
SETTING_DCB_SETTING_NAME: Final = "dcb"
SETTING_DNS_OPTION_ATTEMPTS: Final = "attempts"
SETTING_DNS_OPTION_DEBUG: Final = "debug"
SETTING_DNS_OPTION_EDNS0: Final = "edns0"
SETTING_DNS_OPTION_INET6: Final = "inet6"
SETTING_DNS_OPTION_INTERNAL_NO_ADD_EDNS0: Final = "_no-add-edns0"
SETTING_DNS_OPTION_INTERNAL_NO_ADD_TRUST_AD: Final = "_no-add-trust-ad"
SETTING_DNS_OPTION_IP6_BYTESTRING: Final = "ip6-bytestring"
SETTING_DNS_OPTION_IP6_DOTINT: Final = "ip6-dotint"
SETTING_DNS_OPTION_NDOTS: Final = "ndots"
SETTING_DNS_OPTION_NO_AAAA: Final = "no-aaaa"
SETTING_DNS_OPTION_NO_CHECK_NAMES: Final = "no-check-names"
SETTING_DNS_OPTION_NO_IP6_DOTINT: Final = "no-ip6-dotint"
SETTING_DNS_OPTION_NO_RELOAD: Final = "no-reload"
SETTING_DNS_OPTION_NO_TLD_QUERY: Final = "no-tld-query"
SETTING_DNS_OPTION_ROTATE: Final = "rotate"
SETTING_DNS_OPTION_SINGLE_REQUEST: Final = "single-request"
SETTING_DNS_OPTION_SINGLE_REQUEST_REOPEN: Final = "single-request-reopen"
SETTING_DNS_OPTION_TIMEOUT: Final = "timeout"
SETTING_DNS_OPTION_TRUST_AD: Final = "trust-ad"
SETTING_DNS_OPTION_USE_VC: Final = "use-vc"
SETTING_DUMMY_SETTING_NAME: Final = "dummy"
SETTING_ETHTOOL_SETTING_NAME: Final = "ethtool"
SETTING_GENERIC_DEVICE_HANDLER: Final = "device-handler"
SETTING_GENERIC_SETTING_NAME: Final = "generic"
SETTING_GENEVE_DESTINATION_PORT: Final = "destination-port"
SETTING_GENEVE_DF: Final = "df"
SETTING_GENEVE_ID: Final = "id"
SETTING_GENEVE_REMOTE: Final = "remote"
SETTING_GENEVE_SETTING_NAME: Final = "geneve"
SETTING_GENEVE_TOS: Final = "tos"
SETTING_GENEVE_TTL: Final = "ttl"
SETTING_GSM_APN: Final = "apn"
SETTING_GSM_AUTO_CONFIG: Final = "auto-config"
SETTING_GSM_DEVICE_ID: Final = "device-id"
SETTING_GSM_DEVICE_UID: Final = "device-uid"
SETTING_GSM_HOME_ONLY: Final = "home-only"
SETTING_GSM_INITIAL_EPS_BEARER_APN: Final = "initial-eps-bearer-apn"
SETTING_GSM_INITIAL_EPS_BEARER_CONFIGURE: Final = "initial-eps-bearer-configure"
SETTING_GSM_INITIAL_EPS_BEARER_NOAUTH: Final = "initial-eps-bearer-noauth"
SETTING_GSM_INITIAL_EPS_BEARER_PASSWORD: Final = "initial-eps-bearer-password"
SETTING_GSM_INITIAL_EPS_BEARER_PASSWORD_FLAGS: Final = (
    "initial-eps-bearer-password-flags"
)
SETTING_GSM_INITIAL_EPS_BEARER_REFUSE_CHAP: Final = "initial-eps-bearer-refuse-chap"
SETTING_GSM_INITIAL_EPS_BEARER_REFUSE_EAP: Final = "initial-eps-bearer-refuse-eap"
SETTING_GSM_INITIAL_EPS_BEARER_REFUSE_MSCHAP: Final = "initial-eps-bearer-refuse-mschap"
SETTING_GSM_INITIAL_EPS_BEARER_REFUSE_MSCHAPV2: Final = (
    "initial-eps-bearer-refuse-mschapv2"
)
SETTING_GSM_INITIAL_EPS_BEARER_REFUSE_PAP: Final = "initial-eps-bearer-refuse-pap"
SETTING_GSM_INITIAL_EPS_BEARER_USERNAME: Final = "initial-eps-bearer-username"
SETTING_GSM_MTU: Final = "mtu"
SETTING_GSM_NETWORK_ID: Final = "network-id"
SETTING_GSM_NUMBER: Final = "number"
SETTING_GSM_PASSWORD: Final = "password"
SETTING_GSM_PASSWORD_FLAGS: Final = "password-flags"
SETTING_GSM_PIN: Final = "pin"
SETTING_GSM_PIN_FLAGS: Final = "pin-flags"
SETTING_GSM_SETTING_NAME: Final = "gsm"
SETTING_GSM_SIM_ID: Final = "sim-id"
SETTING_GSM_SIM_OPERATOR_ID: Final = "sim-operator-id"
SETTING_GSM_USERNAME: Final = "username"
SETTING_HOSTNAME_FROM_DHCP: Final = "from-dhcp"
SETTING_HOSTNAME_FROM_DNS_LOOKUP: Final = "from-dns-lookup"
SETTING_HOSTNAME_ONLY_FROM_DEFAULT: Final = "only-from-default"
SETTING_HOSTNAME_PRIORITY: Final = "priority"
SETTING_HOSTNAME_SETTING_NAME: Final = "hostname"
SETTING_HSR_INTERLINK: Final = "interlink"
SETTING_HSR_MULTICAST_SPEC: Final = "multicast-spec"
SETTING_HSR_PORT1: Final = "port1"
SETTING_HSR_PORT2: Final = "port2"
SETTING_HSR_PROTOCOL_VERSION: Final = "protocol-version"
SETTING_HSR_PRP: Final = "prp"
SETTING_HSR_SETTING_NAME: Final = "hsr"
SETTING_INFINIBAND_MAC_ADDRESS: Final = "mac-address"
SETTING_INFINIBAND_MTU: Final = "mtu"
SETTING_INFINIBAND_PARENT: Final = "parent"
SETTING_INFINIBAND_P_KEY: Final = "p-key"
SETTING_INFINIBAND_SETTING_NAME: Final = "infiniband"
SETTING_INFINIBAND_TRANSPORT_MODE: Final = "transport-mode"
SETTING_IP4_CONFIG_CLAT: Final = "clat"
SETTING_IP4_CONFIG_DHCP_CLIENT_ID: Final = "dhcp-client-id"
SETTING_IP4_CONFIG_DHCP_FQDN: Final = "dhcp-fqdn"
SETTING_IP4_CONFIG_DHCP_IPV6_ONLY_PREFERRED: Final = "dhcp-ipv6-only-preferred"
SETTING_IP4_CONFIG_DHCP_VENDOR_CLASS_IDENTIFIER: Final = "dhcp-vendor-class-identifier"
SETTING_IP4_CONFIG_LINK_LOCAL: Final = "link-local"
SETTING_IP4_CONFIG_METHOD_AUTO: Final = "auto"
SETTING_IP4_CONFIG_METHOD_DISABLED: Final = "disabled"
SETTING_IP4_CONFIG_METHOD_LINK_LOCAL: Final = "link-local"
SETTING_IP4_CONFIG_METHOD_MANUAL: Final = "manual"
SETTING_IP4_CONFIG_METHOD_SHARED: Final = "shared"
SETTING_IP4_CONFIG_SETTING_NAME: Final = "ipv4"
SETTING_IP6_CONFIG_ADDR_GEN_MODE: Final = "addr-gen-mode"
SETTING_IP6_CONFIG_DHCP_DUID: Final = "dhcp-duid"
SETTING_IP6_CONFIG_DHCP_PD_HINT: Final = "dhcp-pd-hint"
SETTING_IP6_CONFIG_IP6_PRIVACY: Final = "ip6-privacy"
SETTING_IP6_CONFIG_METHOD_AUTO: Final = "auto"
SETTING_IP6_CONFIG_METHOD_DHCP: Final = "dhcp"
SETTING_IP6_CONFIG_METHOD_DISABLED: Final = "disabled"
SETTING_IP6_CONFIG_METHOD_IGNORE: Final = "ignore"
SETTING_IP6_CONFIG_METHOD_LINK_LOCAL: Final = "link-local"
SETTING_IP6_CONFIG_METHOD_MANUAL: Final = "manual"
SETTING_IP6_CONFIG_METHOD_SHARED: Final = "shared"
SETTING_IP6_CONFIG_MTU: Final = "mtu"
SETTING_IP6_CONFIG_RA_TIMEOUT: Final = "ra-timeout"
SETTING_IP6_CONFIG_SETTING_NAME: Final = "ipv6"
SETTING_IP6_CONFIG_TEMP_PREFERRED_LIFETIME: Final = "temp-preferred-lifetime"
SETTING_IP6_CONFIG_TEMP_VALID_LIFETIME: Final = "temp-valid-lifetime"
SETTING_IP6_CONFIG_TOKEN: Final = "token"
SETTING_IPVLAN_MODE: Final = "mode"
SETTING_IPVLAN_PARENT: Final = "parent"
SETTING_IPVLAN_PRIVATE: Final = "private"
SETTING_IPVLAN_SETTING_NAME: Final = "ipvlan"
SETTING_IPVLAN_VEPA: Final = "vepa"
SETTING_IP_CONFIG_ADDRESSES: Final = "addresses"
SETTING_IP_CONFIG_AUTO_ROUTE_EXT_GW: Final = "auto-route-ext-gw"
SETTING_IP_CONFIG_DAD_TIMEOUT: Final = "dad-timeout"
SETTING_IP_CONFIG_DAD_TIMEOUT_MAX: Final[int]
SETTING_IP_CONFIG_DHCP_DSCP: Final = "dhcp-dscp"
SETTING_IP_CONFIG_DHCP_HOSTNAME: Final = "dhcp-hostname"
SETTING_IP_CONFIG_DHCP_HOSTNAME_FLAGS: Final = "dhcp-hostname-flags"
SETTING_IP_CONFIG_DHCP_IAID: Final = "dhcp-iaid"
SETTING_IP_CONFIG_DHCP_REJECT_SERVERS: Final = "dhcp-reject-servers"
SETTING_IP_CONFIG_DHCP_SEND_HOSTNAME: Final = "dhcp-send-hostname"
SETTING_IP_CONFIG_DHCP_SEND_HOSTNAME_V2: Final = "dhcp-send-hostname-v2"
SETTING_IP_CONFIG_DHCP_SEND_RELEASE: Final = "dhcp-send-release"
SETTING_IP_CONFIG_DHCP_TIMEOUT: Final = "dhcp-timeout"
SETTING_IP_CONFIG_DNS: Final = "dns"
SETTING_IP_CONFIG_DNS_OPTIONS: Final = "dns-options"
SETTING_IP_CONFIG_DNS_PRIORITY: Final = "dns-priority"
SETTING_IP_CONFIG_DNS_SEARCH: Final = "dns-search"
SETTING_IP_CONFIG_FORWARDING: Final = "forwarding"
SETTING_IP_CONFIG_GATEWAY: Final = "gateway"
SETTING_IP_CONFIG_IGNORE_AUTO_DNS: Final = "ignore-auto-dns"
SETTING_IP_CONFIG_IGNORE_AUTO_ROUTES: Final = "ignore-auto-routes"
SETTING_IP_CONFIG_MAY_FAIL: Final = "may-fail"
SETTING_IP_CONFIG_METHOD: Final = "method"
SETTING_IP_CONFIG_NEVER_DEFAULT: Final = "never-default"
SETTING_IP_CONFIG_REPLACE_LOCAL_RULE: Final = "replace-local-rule"
SETTING_IP_CONFIG_REQUIRED_TIMEOUT: Final = "required-timeout"
SETTING_IP_CONFIG_ROUTED_DNS: Final = "routed-dns"
SETTING_IP_CONFIG_ROUTES: Final = "routes"
SETTING_IP_CONFIG_ROUTE_METRIC: Final = "route-metric"
SETTING_IP_CONFIG_ROUTE_TABLE: Final = "route-table"
SETTING_IP_CONFIG_ROUTING_RULES: Final = "routing-rules"
SETTING_IP_CONFIG_SHARED_DHCP_LEASE_TIME: Final = "shared-dhcp-lease-time"
SETTING_IP_CONFIG_SHARED_DHCP_RANGE: Final = "shared-dhcp-range"
SETTING_IP_TUNNEL_ENCAPSULATION_LIMIT: Final = "encapsulation-limit"
SETTING_IP_TUNNEL_FLAGS: Final = "flags"
SETTING_IP_TUNNEL_FLOW_LABEL: Final = "flow-label"
SETTING_IP_TUNNEL_FWMARK: Final = "fwmark"
SETTING_IP_TUNNEL_INPUT_KEY: Final = "input-key"
SETTING_IP_TUNNEL_LOCAL: Final = "local"
SETTING_IP_TUNNEL_MODE: Final = "mode"
SETTING_IP_TUNNEL_MTU: Final = "mtu"
SETTING_IP_TUNNEL_OUTPUT_KEY: Final = "output-key"
SETTING_IP_TUNNEL_PARENT: Final = "parent"
SETTING_IP_TUNNEL_PATH_MTU_DISCOVERY: Final = "path-mtu-discovery"
SETTING_IP_TUNNEL_REMOTE: Final = "remote"
SETTING_IP_TUNNEL_SETTING_NAME: Final = "ip-tunnel"
SETTING_IP_TUNNEL_TOS: Final = "tos"
SETTING_IP_TUNNEL_TTL: Final = "ttl"
SETTING_LINK_GRO_MAX_SIZE: Final = "gro-max-size"
SETTING_LINK_GSO_MAX_SEGMENTS: Final = "gso-max-segments"
SETTING_LINK_GSO_MAX_SIZE: Final = "gso-max-size"
SETTING_LINK_SETTING_NAME: Final = "link"
SETTING_LINK_TX_QUEUE_LENGTH: Final = "tx-queue-length"
SETTING_LOOPBACK_MTU: Final = "mtu"
SETTING_LOOPBACK_SETTING_NAME: Final = "loopback"
SETTING_MACSEC_ENCRYPT: Final = "encrypt"
SETTING_MACSEC_MKA_CAK: Final = "mka-cak"
SETTING_MACSEC_MKA_CAK_FLAGS: Final = "mka-cak-flags"
SETTING_MACSEC_MKA_CAK_LENGTH: Final[int]
SETTING_MACSEC_MKA_CKN: Final = "mka-ckn"
SETTING_MACSEC_MKA_CKN_LENGTH: Final[int]
SETTING_MACSEC_MODE: Final = "mode"
SETTING_MACSEC_OFFLOAD: Final = "offload"
SETTING_MACSEC_PARENT: Final = "parent"
SETTING_MACSEC_PORT: Final = "port"
SETTING_MACSEC_SEND_SCI: Final = "send-sci"
SETTING_MACSEC_SETTING_NAME: Final = "macsec"
SETTING_MACSEC_VALIDATION: Final = "validation"
SETTING_MACVLAN_MODE: Final = "mode"
SETTING_MACVLAN_PARENT: Final = "parent"
SETTING_MACVLAN_PROMISCUOUS: Final = "promiscuous"
SETTING_MACVLAN_SETTING_NAME: Final = "macvlan"
SETTING_MACVLAN_TAP: Final = "tap"
SETTING_MATCH_DRIVER: Final = "driver"
SETTING_MATCH_INTERFACE_NAME: Final = "interface-name"
SETTING_MATCH_KERNEL_COMMAND_LINE: Final = "kernel-command-line"
SETTING_MATCH_PATH: Final = "path"
SETTING_MATCH_SETTING_NAME: Final = "match"
SETTING_NAME: Final = "name"
SETTING_OLPC_MESH_CHANNEL: Final = "channel"
SETTING_OLPC_MESH_DHCP_ANYCAST_ADDRESS: Final = "dhcp-anycast-address"
SETTING_OLPC_MESH_SETTING_NAME: Final = "802-11-olpc-mesh"
SETTING_OLPC_MESH_SSID: Final = "ssid"
SETTING_OVS_BRIDGE_DATAPATH_TYPE: Final = "datapath-type"
SETTING_OVS_BRIDGE_FAIL_MODE: Final = "fail-mode"
SETTING_OVS_BRIDGE_MCAST_SNOOPING_ENABLE: Final = "mcast-snooping-enable"
SETTING_OVS_BRIDGE_RSTP_ENABLE: Final = "rstp-enable"
SETTING_OVS_BRIDGE_SETTING_NAME: Final = "ovs-bridge"
SETTING_OVS_BRIDGE_STP_ENABLE: Final = "stp-enable"
SETTING_OVS_DPDK_DEVARGS: Final = "devargs"
SETTING_OVS_DPDK_LSC_INTERRUPT: Final = "lsc-interrupt"
SETTING_OVS_DPDK_N_RXQ: Final = "n-rxq"
SETTING_OVS_DPDK_N_RXQ_DESC: Final = "n-rxq-desc"
SETTING_OVS_DPDK_N_TXQ_DESC: Final = "n-txq-desc"
SETTING_OVS_DPDK_SETTING_NAME: Final = "ovs-dpdk"
SETTING_OVS_EXTERNAL_IDS_DATA: Final = "data"
SETTING_OVS_EXTERNAL_IDS_SETTING_NAME: Final = "ovs-external-ids"
SETTING_OVS_INTERFACE_OFPORT_REQUEST: Final = "ofport-request"
SETTING_OVS_INTERFACE_SETTING_NAME: Final = "ovs-interface"
SETTING_OVS_INTERFACE_TYPE: Final = "type"
SETTING_OVS_OTHER_CONFIG_DATA: Final = "data"
SETTING_OVS_OTHER_CONFIG_SETTING_NAME: Final = "ovs-other-config"
SETTING_OVS_PATCH_PEER: Final = "peer"
SETTING_OVS_PATCH_SETTING_NAME: Final = "ovs-patch"
SETTING_OVS_PORT_BOND_DOWNDELAY: Final = "bond-downdelay"
SETTING_OVS_PORT_BOND_MODE: Final = "bond-mode"
SETTING_OVS_PORT_BOND_UPDELAY: Final = "bond-updelay"
SETTING_OVS_PORT_LACP: Final = "lacp"
SETTING_OVS_PORT_SETTING_NAME: Final = "ovs-port"
SETTING_OVS_PORT_TAG: Final = "tag"
SETTING_OVS_PORT_TRUNKS: Final = "trunks"
SETTING_OVS_PORT_VLAN_MODE: Final = "vlan-mode"
SETTING_PARAM_FUZZY_IGNORE: Final[int]
SETTING_PARAM_REQUIRED: Final[int]
SETTING_PARAM_SECRET: Final[int]
SETTING_PPPOE_PARENT: Final = "parent"
SETTING_PPPOE_PASSWORD: Final = "password"
SETTING_PPPOE_PASSWORD_FLAGS: Final = "password-flags"
SETTING_PPPOE_SERVICE: Final = "service"
SETTING_PPPOE_SETTING_NAME: Final = "pppoe"
SETTING_PPPOE_USERNAME: Final = "username"
SETTING_PPP_BAUD: Final = "baud"
SETTING_PPP_CRTSCTS: Final = "crtscts"
SETTING_PPP_LCP_ECHO_FAILURE: Final = "lcp-echo-failure"
SETTING_PPP_LCP_ECHO_INTERVAL: Final = "lcp-echo-interval"
SETTING_PPP_MPPE_STATEFUL: Final = "mppe-stateful"
SETTING_PPP_MRU: Final = "mru"
SETTING_PPP_MTU: Final = "mtu"
SETTING_PPP_NOAUTH: Final = "noauth"
SETTING_PPP_NOBSDCOMP: Final = "nobsdcomp"
SETTING_PPP_NODEFLATE: Final = "nodeflate"
SETTING_PPP_NO_VJ_COMP: Final = "no-vj-comp"
SETTING_PPP_REFUSE_CHAP: Final = "refuse-chap"
SETTING_PPP_REFUSE_EAP: Final = "refuse-eap"
SETTING_PPP_REFUSE_MSCHAP: Final = "refuse-mschap"
SETTING_PPP_REFUSE_MSCHAPV2: Final = "refuse-mschapv2"
SETTING_PPP_REFUSE_PAP: Final = "refuse-pap"
SETTING_PPP_REQUIRE_MPPE: Final = "require-mppe"
SETTING_PPP_REQUIRE_MPPE_128: Final = "require-mppe-128"
SETTING_PPP_SETTING_NAME: Final = "ppp"
SETTING_PREFIX_DELEGATION_SETTING_NAME: Final = "prefix-delegation"
SETTING_PREFIX_DELEGATION_SUBNET_ID: Final = "subnet-id"
SETTING_PROXY_BROWSER_ONLY: Final = "browser-only"
SETTING_PROXY_METHOD: Final = "method"
SETTING_PROXY_PAC_SCRIPT: Final = "pac-script"
SETTING_PROXY_PAC_URL: Final = "pac-url"
SETTING_PROXY_SETTING_NAME: Final = "proxy"
SETTING_SERIAL_BAUD: Final = "baud"
SETTING_SERIAL_BITS: Final = "bits"
SETTING_SERIAL_PARITY: Final = "parity"
SETTING_SERIAL_SEND_DELAY: Final = "send-delay"
SETTING_SERIAL_SETTING_NAME: Final = "serial"
SETTING_SERIAL_STOPBITS: Final = "stopbits"
SETTING_SRIOV_AUTOPROBE_DRIVERS: Final = "autoprobe-drivers"
SETTING_SRIOV_ESWITCH_ENCAP_MODE: Final = "eswitch-encap-mode"
SETTING_SRIOV_ESWITCH_INLINE_MODE: Final = "eswitch-inline-mode"
SETTING_SRIOV_ESWITCH_MODE: Final = "eswitch-mode"
SETTING_SRIOV_PRESERVE_ON_DOWN: Final = "preserve-on-down"
SETTING_SRIOV_SETTING_NAME: Final = "sriov"
SETTING_SRIOV_TOTAL_VFS: Final = "total-vfs"
SETTING_SRIOV_VFS: Final = "vfs"
SETTING_TC_CONFIG_QDISCS: Final = "qdiscs"
SETTING_TC_CONFIG_SETTING_NAME: Final = "tc"
SETTING_TC_CONFIG_TFILTERS: Final = "tfilters"
SETTING_TEAM_CONFIG: Final = "config"
SETTING_TEAM_LINK_WATCHERS: Final = "link-watchers"
SETTING_TEAM_MCAST_REJOIN_COUNT: Final = "mcast-rejoin-count"
SETTING_TEAM_MCAST_REJOIN_INTERVAL: Final = "mcast-rejoin-interval"
SETTING_TEAM_NOTIFY_MCAST_COUNT_ACTIVEBACKUP_DEFAULT: Final[int]
SETTING_TEAM_NOTIFY_PEERS_COUNT: Final = "notify-peers-count"
SETTING_TEAM_NOTIFY_PEERS_COUNT_ACTIVEBACKUP_DEFAULT: Final[int]
SETTING_TEAM_NOTIFY_PEERS_INTERVAL: Final = "notify-peers-interval"
SETTING_TEAM_PORT_CONFIG: Final = "config"
SETTING_TEAM_PORT_LACP_KEY: Final = "lacp-key"
SETTING_TEAM_PORT_LACP_PRIO: Final = "lacp-prio"
SETTING_TEAM_PORT_LACP_PRIO_DEFAULT: Final[int]
SETTING_TEAM_PORT_LINK_WATCHERS: Final = "link-watchers"
SETTING_TEAM_PORT_PRIO: Final = "prio"
SETTING_TEAM_PORT_QUEUE_ID: Final = "queue-id"
SETTING_TEAM_PORT_QUEUE_ID_DEFAULT: Final[int]
SETTING_TEAM_PORT_SETTING_NAME: Final = "team-port"
SETTING_TEAM_PORT_STICKY: Final = "sticky"
SETTING_TEAM_RUNNER: Final = "runner"
SETTING_TEAM_RUNNER_ACTIVE: Final = "runner-active"
SETTING_TEAM_RUNNER_ACTIVEBACKUP: Final = "activebackup"
SETTING_TEAM_RUNNER_AGG_SELECT_POLICY: Final = "runner-agg-select-policy"
SETTING_TEAM_RUNNER_AGG_SELECT_POLICY_BANDWIDTH: Final = "bandwidth"
SETTING_TEAM_RUNNER_AGG_SELECT_POLICY_COUNT: Final = "count"
SETTING_TEAM_RUNNER_AGG_SELECT_POLICY_LACP_PRIO: Final = "lacp_prio"
SETTING_TEAM_RUNNER_AGG_SELECT_POLICY_LACP_PRIO_STABLE: Final = "lacp_prio_stable"
SETTING_TEAM_RUNNER_AGG_SELECT_POLICY_PORT_CONFIG: Final = "port_config"
SETTING_TEAM_RUNNER_BROADCAST: Final = "broadcast"
SETTING_TEAM_RUNNER_FAST_RATE: Final = "runner-fast-rate"
SETTING_TEAM_RUNNER_HWADDR_POLICY: Final = "runner-hwaddr-policy"
SETTING_TEAM_RUNNER_HWADDR_POLICY_BY_ACTIVE: Final = "by_active"
SETTING_TEAM_RUNNER_HWADDR_POLICY_ONLY_ACTIVE: Final = "only_active"
SETTING_TEAM_RUNNER_HWADDR_POLICY_SAME_ALL: Final = "same_all"
SETTING_TEAM_RUNNER_LACP: Final = "lacp"
SETTING_TEAM_RUNNER_LOADBALANCE: Final = "loadbalance"
SETTING_TEAM_RUNNER_MIN_PORTS: Final = "runner-min-ports"
SETTING_TEAM_RUNNER_RANDOM: Final = "random"
SETTING_TEAM_RUNNER_ROUNDROBIN: Final = "roundrobin"
SETTING_TEAM_RUNNER_SYS_PRIO: Final = "runner-sys-prio"
SETTING_TEAM_RUNNER_SYS_PRIO_DEFAULT: Final[int]
SETTING_TEAM_RUNNER_TX_BALANCER: Final = "runner-tx-balancer"
SETTING_TEAM_RUNNER_TX_BALANCER_INTERVAL: Final = "runner-tx-balancer-interval"
SETTING_TEAM_RUNNER_TX_BALANCER_INTERVAL_DEFAULT: Final[int]
SETTING_TEAM_RUNNER_TX_HASH: Final = "runner-tx-hash"
SETTING_TEAM_SETTING_NAME: Final = "team"
SETTING_TUN_GROUP: Final = "group"
SETTING_TUN_MODE: Final = "mode"
SETTING_TUN_MULTI_QUEUE: Final = "multi-queue"
SETTING_TUN_OWNER: Final = "owner"
SETTING_TUN_PI: Final = "pi"
SETTING_TUN_SETTING_NAME: Final = "tun"
SETTING_TUN_VNET_HDR: Final = "vnet-hdr"
SETTING_USER_DATA: Final = "data"
SETTING_USER_SETTING_NAME: Final = "user"
SETTING_VETH_PEER: Final = "peer"
SETTING_VETH_SETTING_NAME: Final = "veth"
SETTING_VLAN_EGRESS_PRIORITY_MAP: Final = "egress-priority-map"
SETTING_VLAN_FLAGS: Final = "flags"
SETTING_VLAN_ID: Final = "id"
SETTING_VLAN_INGRESS_PRIORITY_MAP: Final = "ingress-priority-map"
SETTING_VLAN_PARENT: Final = "parent"
SETTING_VLAN_PROTOCOL: Final = "protocol"
SETTING_VLAN_SETTING_NAME: Final = "vlan"
SETTING_VPN_DATA: Final = "data"
SETTING_VPN_PERSISTENT: Final = "persistent"
SETTING_VPN_SECRETS: Final = "secrets"
SETTING_VPN_SERVICE_TYPE: Final = "service-type"
SETTING_VPN_SETTING_NAME: Final = "vpn"
SETTING_VPN_TIMEOUT: Final = "timeout"
SETTING_VPN_USER_NAME: Final = "user-name"
SETTING_VRF_SETTING_NAME: Final = "vrf"
SETTING_VRF_TABLE: Final = "table"
SETTING_VXLAN_AGEING: Final = "ageing"
SETTING_VXLAN_DESTINATION_PORT: Final = "destination-port"
SETTING_VXLAN_ID: Final = "id"
SETTING_VXLAN_L2_MISS: Final = "l2-miss"
SETTING_VXLAN_L3_MISS: Final = "l3-miss"
SETTING_VXLAN_LEARNING: Final = "learning"
SETTING_VXLAN_LIMIT: Final = "limit"
SETTING_VXLAN_LOCAL: Final = "local"
SETTING_VXLAN_PARENT: Final = "parent"
SETTING_VXLAN_PROXY: Final = "proxy"
SETTING_VXLAN_REMOTE: Final = "remote"
SETTING_VXLAN_RSC: Final = "rsc"
SETTING_VXLAN_SETTING_NAME: Final = "vxlan"
SETTING_VXLAN_SOURCE_PORT_MAX: Final = "source-port-max"
SETTING_VXLAN_SOURCE_PORT_MIN: Final = "source-port-min"
SETTING_VXLAN_TOS: Final = "tos"
SETTING_VXLAN_TTL: Final = "ttl"
SETTING_WIFI_P2P_PEER: Final = "peer"
SETTING_WIFI_P2P_SETTING_NAME: Final = "wifi-p2p"
SETTING_WIFI_P2P_WFD_IES: Final = "wfd-ies"
SETTING_WIFI_P2P_WPS_METHOD: Final = "wps-method"
SETTING_WIMAX_MAC_ADDRESS: Final = "mac-address"
SETTING_WIMAX_NETWORK_NAME: Final = "network-name"
SETTING_WIMAX_SETTING_NAME: Final = "wimax"
SETTING_WIRED_ACCEPT_ALL_MAC_ADDRESSES: Final = "accept-all-mac-addresses"
SETTING_WIRED_AUTO_NEGOTIATE: Final = "auto-negotiate"
SETTING_WIRED_CLONED_MAC_ADDRESS: Final = "cloned-mac-address"
SETTING_WIRED_DUPLEX: Final = "duplex"
SETTING_WIRED_GENERATE_MAC_ADDRESS_MASK: Final = "generate-mac-address-mask"
SETTING_WIRED_MAC_ADDRESS: Final = "mac-address"
SETTING_WIRED_MAC_ADDRESS_BLACKLIST: Final = "mac-address-blacklist"
SETTING_WIRED_MAC_ADDRESS_DENYLIST: Final = "mac-address-denylist"
SETTING_WIRED_MTU: Final = "mtu"
SETTING_WIRED_PORT: Final = "port"
SETTING_WIRED_S390_NETTYPE: Final = "s390-nettype"
SETTING_WIRED_S390_OPTIONS: Final = "s390-options"
SETTING_WIRED_S390_SUBCHANNELS: Final = "s390-subchannels"
SETTING_WIRED_SETTING_NAME: Final = "802-3-ethernet"
SETTING_WIRED_SPEED: Final = "speed"
SETTING_WIRED_WAKE_ON_LAN: Final = "wake-on-lan"
SETTING_WIRED_WAKE_ON_LAN_PASSWORD: Final = "wake-on-lan-password"
SETTING_WIREGUARD_FWMARK: Final = "fwmark"
SETTING_WIREGUARD_IP4_AUTO_DEFAULT_ROUTE: Final = "ip4-auto-default-route"
SETTING_WIREGUARD_IP6_AUTO_DEFAULT_ROUTE: Final = "ip6-auto-default-route"
SETTING_WIREGUARD_LISTEN_PORT: Final = "listen-port"
SETTING_WIREGUARD_MTU: Final = "mtu"
SETTING_WIREGUARD_PEERS: Final = "peers"
SETTING_WIREGUARD_PEER_ROUTES: Final = "peer-routes"
SETTING_WIREGUARD_PRIVATE_KEY: Final = "private-key"
SETTING_WIREGUARD_PRIVATE_KEY_FLAGS: Final = "private-key-flags"
SETTING_WIREGUARD_SETTING_NAME: Final = "wireguard"
SETTING_WIRELESS_AP_ISOLATION: Final = "ap-isolation"
SETTING_WIRELESS_BAND: Final = "band"
SETTING_WIRELESS_BSSID: Final = "bssid"
SETTING_WIRELESS_CHANNEL: Final = "channel"
SETTING_WIRELESS_CHANNEL_WIDTH: Final = "channel-width"
SETTING_WIRELESS_CLONED_MAC_ADDRESS: Final = "cloned-mac-address"
SETTING_WIRELESS_GENERATE_MAC_ADDRESS_MASK: Final = "generate-mac-address-mask"
SETTING_WIRELESS_HIDDEN: Final = "hidden"
SETTING_WIRELESS_MAC_ADDRESS: Final = "mac-address"
SETTING_WIRELESS_MAC_ADDRESS_BLACKLIST: Final = "mac-address-blacklist"
SETTING_WIRELESS_MAC_ADDRESS_DENYLIST: Final = "mac-address-denylist"
SETTING_WIRELESS_MAC_ADDRESS_RANDOMIZATION: Final = "mac-address-randomization"
SETTING_WIRELESS_MODE: Final = "mode"
SETTING_WIRELESS_MODE_ADHOC: Final = "adhoc"
SETTING_WIRELESS_MODE_AP: Final = "ap"
SETTING_WIRELESS_MODE_INFRA: Final = "infrastructure"
SETTING_WIRELESS_MODE_MESH: Final = "mesh"
SETTING_WIRELESS_MTU: Final = "mtu"
SETTING_WIRELESS_POWERSAVE: Final = "powersave"
SETTING_WIRELESS_RATE: Final = "rate"
SETTING_WIRELESS_SECURITY_AUTH_ALG: Final = "auth-alg"
SETTING_WIRELESS_SECURITY_FILS: Final = "fils"
SETTING_WIRELESS_SECURITY_GROUP: Final = "group"
SETTING_WIRELESS_SECURITY_KEY_MGMT: Final = "key-mgmt"
SETTING_WIRELESS_SECURITY_LEAP_PASSWORD: Final = "leap-password"
SETTING_WIRELESS_SECURITY_LEAP_PASSWORD_FLAGS: Final = "leap-password-flags"
SETTING_WIRELESS_SECURITY_LEAP_USERNAME: Final = "leap-username"
SETTING_WIRELESS_SECURITY_PAIRWISE: Final = "pairwise"
SETTING_WIRELESS_SECURITY_PMF: Final = "pmf"
SETTING_WIRELESS_SECURITY_PROTO: Final = "proto"
SETTING_WIRELESS_SECURITY_PSK: Final = "psk"
SETTING_WIRELESS_SECURITY_PSK_FLAGS: Final = "psk-flags"
SETTING_WIRELESS_SECURITY_SETTING_NAME: Final = "802-11-wireless-security"
SETTING_WIRELESS_SECURITY_WEP_KEY0: Final = "wep-key0"
SETTING_WIRELESS_SECURITY_WEP_KEY1: Final = "wep-key1"
SETTING_WIRELESS_SECURITY_WEP_KEY2: Final = "wep-key2"
SETTING_WIRELESS_SECURITY_WEP_KEY3: Final = "wep-key3"
SETTING_WIRELESS_SECURITY_WEP_KEY_FLAGS: Final = "wep-key-flags"
SETTING_WIRELESS_SECURITY_WEP_KEY_TYPE: Final = "wep-key-type"
SETTING_WIRELESS_SECURITY_WEP_TX_KEYIDX: Final = "wep-tx-keyidx"
SETTING_WIRELESS_SECURITY_WPS_METHOD: Final = "wps-method"
SETTING_WIRELESS_SEEN_BSSIDS: Final = "seen-bssids"
SETTING_WIRELESS_SETTING_NAME: Final = "802-11-wireless"
SETTING_WIRELESS_SSID: Final = "ssid"
SETTING_WIRELESS_TX_POWER: Final = "tx-power"
SETTING_WIRELESS_WAKE_ON_WLAN: Final = "wake-on-wlan"
SETTING_WPAN_CHANNEL: Final = "channel"
SETTING_WPAN_CHANNEL_DEFAULT: Final[int]
SETTING_WPAN_MAC_ADDRESS: Final = "mac-address"
SETTING_WPAN_PAGE: Final = "page"
SETTING_WPAN_PAGE_DEFAULT: Final[int]
SETTING_WPAN_PAN_ID: Final = "pan-id"
SETTING_WPAN_SETTING_NAME: Final = "wpan"
SETTING_WPAN_SHORT_ADDRESS: Final = "short-address"
SRIOV_VF_ATTRIBUTE_MAC: Final = "mac"
SRIOV_VF_ATTRIBUTE_MAX_TX_RATE: Final = "max-tx-rate"
SRIOV_VF_ATTRIBUTE_MIN_TX_RATE: Final = "min-tx-rate"
SRIOV_VF_ATTRIBUTE_SPOOF_CHECK: Final = "spoof-check"
SRIOV_VF_ATTRIBUTE_TRUST: Final = "trust"
TEAM_LINK_WATCHER_ARP_PING: Final = "arp_ping"
TEAM_LINK_WATCHER_ETHTOOL: Final = "ethtool"
TEAM_LINK_WATCHER_NSNA_PING: Final = "nsna_ping"
UTILS_HWADDR_LEN_MAX: Final[int]
VLAN_FLAGS_ALL: Final[int]
VPN_CONNECTION_BANNER: Final = "banner"
VPN_CONNECTION_VPN_STATE: Final = "vpn-state"
VPN_DBUS_PLUGIN_INTERFACE: Final = "org.freedesktop.NetworkManager.VPN.Plugin"
VPN_DBUS_PLUGIN_PATH: Final = "/org/freedesktop/NetworkManager/VPN/Plugin"
VPN_EDITOR_PLUGIN_DESCRIPTION: Final = "description"
VPN_EDITOR_PLUGIN_NAME: Final = "name"
VPN_EDITOR_PLUGIN_SERVICE: Final = "service"
VPN_PLUGIN_CAN_PERSIST: Final = "can-persist"
VPN_PLUGIN_CONFIG_BANNER: Final = "banner"
VPN_PLUGIN_CONFIG_EXT_GATEWAY: Final = "gateway"
VPN_PLUGIN_CONFIG_HAS_IP4: Final = "has-ip4"
VPN_PLUGIN_CONFIG_HAS_IP6: Final = "has-ip6"
VPN_PLUGIN_CONFIG_MTU: Final = "mtu"
VPN_PLUGIN_CONFIG_PROXY_PAC: Final = "pac"
VPN_PLUGIN_CONFIG_TUNDEV: Final = "tundev"
VPN_PLUGIN_INFO_FILENAME: Final = "filename"
VPN_PLUGIN_INFO_KEYFILE: Final = "keyfile"
VPN_PLUGIN_INFO_KF_GROUP_CONNECTION: Final = "VPN Connection"
VPN_PLUGIN_INFO_KF_GROUP_GNOME: Final = "GNOME"
VPN_PLUGIN_INFO_KF_GROUP_LIBNM: Final = "libnm"
VPN_PLUGIN_INFO_NAME: Final = "name"
VPN_PLUGIN_IP4_CONFIG_ADDRESS: Final = "address"
VPN_PLUGIN_IP4_CONFIG_DNS: Final = "dns"
VPN_PLUGIN_IP4_CONFIG_DOMAIN: Final = "domain"
VPN_PLUGIN_IP4_CONFIG_DOMAINS: Final = "domains"
VPN_PLUGIN_IP4_CONFIG_INT_GATEWAY: Final = "internal-gateway"
VPN_PLUGIN_IP4_CONFIG_MSS: Final = "mss"
VPN_PLUGIN_IP4_CONFIG_NBNS: Final = "nbns"
VPN_PLUGIN_IP4_CONFIG_NEVER_DEFAULT: Final = "never-default"
VPN_PLUGIN_IP4_CONFIG_PREFIX: Final = "prefix"
VPN_PLUGIN_IP4_CONFIG_PRESERVE_ROUTES: Final = "preserve-routes"
VPN_PLUGIN_IP4_CONFIG_PTP: Final = "ptp"
VPN_PLUGIN_IP4_CONFIG_ROUTES: Final = "routes"
VPN_PLUGIN_IP6_CONFIG_ADDRESS: Final = "address"
VPN_PLUGIN_IP6_CONFIG_DNS: Final = "dns"
VPN_PLUGIN_IP6_CONFIG_DOMAIN: Final = "domain"
VPN_PLUGIN_IP6_CONFIG_DOMAINS: Final = "domains"
VPN_PLUGIN_IP6_CONFIG_INT_GATEWAY: Final = "internal-gateway"
VPN_PLUGIN_IP6_CONFIG_MSS: Final = "mss"
VPN_PLUGIN_IP6_CONFIG_NEVER_DEFAULT: Final = "never-default"
VPN_PLUGIN_IP6_CONFIG_PREFIX: Final = "prefix"
VPN_PLUGIN_IP6_CONFIG_PRESERVE_ROUTES: Final = "preserve-routes"
VPN_PLUGIN_IP6_CONFIG_PTP: Final = "ptp"
VPN_PLUGIN_IP6_CONFIG_ROUTES: Final = "routes"
VPN_PLUGIN_OLD_DBUS_SERVICE_NAME: Final = "service-name"
VPN_PLUGIN_OLD_STATE: Final = "state"
VPN_SERVICE_PLUGIN_DBUS_SERVICE_NAME: Final = "service-name"
VPN_SERVICE_PLUGIN_DBUS_WATCH_PEER: Final = "watch-peer"
VPN_SERVICE_PLUGIN_STATE: Final = "state"
WIFI_P2P_PEER_FLAGS: Final = "flags"
WIFI_P2P_PEER_HW_ADDRESS: Final = "hw-address"
WIFI_P2P_PEER_LAST_SEEN: Final = "last-seen"
WIFI_P2P_PEER_MANUFACTURER: Final = "manufacturer"
WIFI_P2P_PEER_MODEL: Final = "model"
WIFI_P2P_PEER_MODEL_NUMBER: Final = "model-number"
WIFI_P2P_PEER_NAME: Final = "name"
WIFI_P2P_PEER_SERIAL: Final = "serial"
WIFI_P2P_PEER_STRENGTH: Final = "strength"
WIFI_P2P_PEER_WFD_IES: Final = "wfd-ies"
WIMAX_NSP_NAME: Final = "name"
WIMAX_NSP_NETWORK_TYPE: Final = "network-type"
WIMAX_NSP_SIGNAL_QUALITY: Final = "signal-quality"
WIREGUARD_PEER_ATTR_ALLOWED_IPS: Final = "allowed-ips"
WIREGUARD_PEER_ATTR_ENDPOINT: Final = "endpoint"
WIREGUARD_PEER_ATTR_PERSISTENT_KEEPALIVE: Final = "persistent-keepalive"
WIREGUARD_PEER_ATTR_PRESHARED_KEY: Final = "preshared-key"
WIREGUARD_PEER_ATTR_PRESHARED_KEY_FLAGS: Final = "preshared-key-flags"
WIREGUARD_PEER_ATTR_PUBLIC_KEY: Final = "public-key"
WIREGUARD_PUBLIC_KEY_LEN: Final[int]
WIREGUARD_SYMMETRIC_KEY_LEN: Final[int]

def agent_manager_error_quark() -> int: ...
def bridge_vlan_from_str(str: str) -> BridgeVlan: ...
def client_error_quark() -> int: ...
def conn_wireguard_import(filename: str) -> Connection: ...
def connection_error_quark() -> int: ...
def crypto_error_quark() -> int: ...
def device_error_quark() -> int: ...
def dns_server_validate(str: str, family: int) -> bool: ...
def ethtool_optname_is_channels(optname: str | None = None) -> bool: ...
def ethtool_optname_is_coalesce(optname: str | None = None) -> bool: ...
def ethtool_optname_is_eee(optname: str | None = None) -> bool: ...
def ethtool_optname_is_feature(optname: str | None = None) -> bool: ...
def ethtool_optname_is_fec(optname: str | None = None) -> bool: ...
def ethtool_optname_is_pause(optname: str | None = None) -> bool: ...
def ethtool_optname_is_ring(optname: str | None = None) -> bool: ...
def ip_route_attribute_validate(
    name: str, value: GLib.Variant, family: int
) -> tuple[bool, bool]: ...
def ip_route_get_variant_attribute_spec() -> VariantAttributeSpec: ...
def ip_routing_rule_from_string(
    str: str,
    to_string_flags: _IPRoutingRuleAsStringFlagsValueType,
    extra_args: Mapping[int | Any | None, int | Any | None] | None = None,
) -> IPRoutingRule: ...
def keyfile_read(
    keyfile: GLib.KeyFile,
    base_dir: str,
    handler_flags: _KeyfileHandlerFlagsValueType,
    handler: Callable[
        [
            GLib.KeyFile,
            Connection,
            _KeyfileHandlerTypeValueType,
            KeyfileHandlerData,
            Unpack[_DataTs],
        ],
        bool,
    ]
    | None = None,
    *user_data: Unpack[_DataTs],
) -> Connection: ...
def keyfile_write(
    connection: Connection,
    handler_flags: _KeyfileHandlerFlagsValueType,
    handler: Callable[
        [
            Connection,
            GLib.KeyFile,
            _KeyfileHandlerTypeValueType,
            KeyfileHandlerData,
            Unpack[_DataTs],
        ],
        bool,
    ]
    | None = None,
    *user_data: Unpack[_DataTs],
) -> GLib.KeyFile: ...
def manager_error_quark() -> int: ...
def range_from_str(str: str) -> Range: ...
def secret_agent_error_quark() -> int: ...
def settings_error_quark() -> int: ...
def sriov_vf_attribute_validate(
    name: str, value: GLib.Variant
) -> tuple[bool, bool]: ...
def utils_ap_mode_security_valid(
    type: _UtilsSecurityTypeValueType, wifi_caps: _DeviceWifiCapabilitiesValueType
) -> bool: ...
def utils_base64secret_decode(
    base64_key: str, required_key_len: int
) -> tuple[bool, int]: ...
def utils_bin2hexstr(src: Sequence[int], final_len: int) -> str: ...
def utils_bond_mode_int_to_string(mode: int) -> str: ...
def utils_bond_mode_string_to_int(mode: str) -> int: ...
def utils_check_virtual_device_compatibility(
    virtual_type: type[Any], other_type: type[Any]
) -> bool: ...
def utils_copy_cert_as_user(filename: str, user: str) -> str: ...
def utils_ensure_gtypes() -> None: ...
def utils_enum_from_str(type: type[Any], str: str) -> tuple[bool, int, str | None]: ...
def utils_enum_get_values(type: type[Any], from_: int, to: int) -> list[str]: ...
def utils_enum_to_str(type: type[Any], value: int) -> str: ...
def utils_escape_ssid(ssid: Sequence[int]) -> str: ...
def utils_file_is_certificate(filename: str) -> bool: ...
def utils_file_is_pkcs12(filename: str) -> bool: ...
def utils_file_is_private_key(filename: str) -> tuple[bool, bool]: ...
def utils_file_search_in_paths(
    progname: str,
    try_first: str | None,
    paths: str | None,
    file_test_flags: GLib.FileTest,
    predicate: Callable[[str, Unpack[_DataTs]], bool],
    *user_data: Unpack[_DataTs],
) -> str: ...
def utils_format_variant_attributes(
    attributes: Mapping[str, GLib.Variant],
    attr_separator: int,
    key_value_separator: int,
) -> str: ...
def utils_get_timestamp_msec() -> int: ...
def utils_hexstr2bin(hex: str) -> GLib.Bytes: ...
def utils_hwaddr_atoba(asc: str, length: int) -> bytes: ...
def utils_hwaddr_aton(asc: str, buffer: Sequence[int]) -> int: ...
def utils_hwaddr_canonical(asc: str, length: int) -> str: ...
def utils_hwaddr_len(type: int) -> int: ...
def utils_hwaddr_matches(
    hwaddr1: int | Any | None,
    hwaddr1_len: int,
    hwaddr2: int | Any | None,
    hwaddr2_len: int,
) -> bool: ...
def utils_hwaddr_ntoa(addr: Sequence[int]) -> str: ...
def utils_hwaddr_valid(asc: str, length: int) -> bool: ...
def utils_iface_valid_name(name: str | None = None) -> bool: ...
def utils_ip4_addresses_from_variant(
    value: GLib.Variant,
) -> tuple[list[IPAddress], str | None]: ...
def utils_ip4_addresses_to_variant(
    addresses: Sequence[IPAddress], gateway: str | None = None
) -> GLib.Variant: ...
def utils_ip4_dns_from_variant(value: GLib.Variant) -> str: ...
def utils_ip4_dns_to_variant(dns: str) -> GLib.Variant: ...
def utils_ip4_get_default_prefix(ip: int) -> int: ...
def utils_ip4_netmask_to_prefix(netmask: int) -> int: ...
def utils_ip4_prefix_to_netmask(prefix: int) -> int: ...
def utils_ip4_routes_from_variant(value: GLib.Variant) -> list[IPRoute]: ...
def utils_ip4_routes_to_variant(routes: Sequence[IPRoute]) -> GLib.Variant: ...
def utils_ip6_addresses_from_variant(
    value: GLib.Variant,
) -> tuple[list[IPAddress], str | None]: ...
def utils_ip6_addresses_to_variant(
    addresses: Sequence[IPAddress], gateway: str | None = None
) -> GLib.Variant: ...
def utils_ip6_dns_from_variant(value: GLib.Variant) -> str: ...
def utils_ip6_dns_to_variant(dns: str) -> GLib.Variant: ...
def utils_ip6_routes_from_variant(value: GLib.Variant) -> list[IPRoute]: ...
def utils_ip6_routes_to_variant(routes: Sequence[IPRoute]) -> GLib.Variant: ...
def utils_ip_addresses_from_variant(
    value: GLib.Variant, family: int
) -> list[IPAddress]: ...
def utils_ip_addresses_to_variant(addresses: Sequence[IPAddress]) -> GLib.Variant: ...
def utils_ip_routes_from_variant(value: GLib.Variant, family: int) -> list[IPRoute]: ...
def utils_ip_routes_to_variant(routes: Sequence[IPRoute]) -> GLib.Variant: ...
def utils_ipaddr_valid(family: int, ip: str) -> bool: ...
def utils_is_empty_ssid(ssid: Sequence[int]) -> bool: ...
def utils_is_json_object(str: str) -> bool: ...
def utils_is_uuid(str: str | None = None) -> bool: ...
def utils_is_valid_iface_name(name: str | None = None) -> bool: ...
def utils_parse_variant_attributes(
    string: str,
    attr_separator: int,
    key_value_separator: int,
    ignore_unknown: bool,
    spec: VariantAttributeSpec,
) -> dict[str, GLib.Variant]: ...
def utils_print(output_mode: int, msg: str) -> None: ...
def utils_same_ssid(
    ssid1: Sequence[int], ssid2: Sequence[int], ignore_trailing_null: bool
) -> bool: ...
def utils_security_valid(
    type: _UtilsSecurityTypeValueType,
    wifi_caps: _DeviceWifiCapabilitiesValueType,
    have_ap: bool,
    adhoc: bool,
    ap_flags: GObject.GFlags,
    ap_wpa: GObject.GFlags,
    ap_rsn: GObject.GFlags,
) -> bool: ...
def utils_sriov_vf_from_str(str: str) -> SriovVF: ...
def utils_sriov_vf_to_str(vf: SriovVF, omit_index: bool) -> str: ...
def utils_ssid_to_utf8(ssid: Sequence[int]) -> str: ...
def utils_tc_action_from_str(str: str) -> TCAction: ...
def utils_tc_action_to_str(action: TCAction) -> str: ...
def utils_tc_qdisc_from_str(str: str) -> TCQdisc: ...
def utils_tc_qdisc_to_str(qdisc: TCQdisc) -> str: ...
def utils_tc_tfilter_from_str(str: str) -> TCTfilter: ...
def utils_tc_tfilter_to_str(tfilter: TCTfilter) -> str: ...
def utils_uuid_generate() -> str: ...
def utils_version() -> int: ...
def utils_wep_key_valid(key: str, wep_type: _WepKeyTypeValueType) -> bool: ...
def utils_wifi_2ghz_freqs() -> int: ...
def utils_wifi_5ghz_freqs() -> int: ...
def utils_wifi_6ghz_freqs() -> int: ...
def utils_wifi_channel_to_freq(channel: int, band: str) -> int: ...
def utils_wifi_find_next_channel(channel: int, direction: int, band: str) -> int: ...
def utils_wifi_freq_to_band(freq: int) -> WifiBand: ...
def utils_wifi_freq_to_channel(freq: int) -> int: ...
def utils_wifi_is_channel_valid(channel: int, band: str) -> bool: ...
def utils_wifi_strength_bars(strength: int) -> str: ...
def utils_wpa_psk_valid(psk: str) -> bool: ...
def vpn_editor_plugin_load(plugin_name: str, check_service: str) -> VpnEditorPlugin: ...
def vpn_editor_plugin_load_from_file(
    plugin_name: str,
    check_service: str,
    check_owner: int,
    check_file: Callable[[str, int | Any | None, Unpack[_DataTs]], bool],
    *user_data: Unpack[_DataTs],
) -> VpnEditorPlugin: ...
def vpn_plugin_error_quark() -> int: ...

class AccessPoint(Object):
    """
    :Constructors:

    ::

        AccessPoint(**properties)

    Object NMAccessPoint

    Properties from NMAccessPoint:
      flags -> NM80211ApFlags:

      wpa-flags -> NM80211ApSecurityFlags:

      rsn-flags -> NM80211ApSecurityFlags:

      ssid -> GBytes:

      frequency -> guint:

      hw-address -> gchararray:

      mode -> NM80211Mode:

      max-bitrate -> guint:

      bandwidth -> guint:

      strength -> guchar:

      bssid -> gchararray:

      last-seen -> gint:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Object.Props):
        @property
        def bandwidth(self) -> int: ...
        @property
        def bssid(self) -> str: ...
        @property
        def flags(self) -> GObject.GFlags: ...
        @property
        def frequency(self) -> int: ...
        @property
        def hw_address(self) -> str | None: ...
        @property
        def last_seen(self) -> int: ...
        @property
        def max_bitrate(self) -> int: ...
        @property
        def mode(self) -> GObject.GEnum: ...
        @property
        def rsn_flags(self) -> GObject.GFlags: ...
        @property
        def ssid(self) -> GLib.Bytes: ...
        @property
        def strength(self) -> int: ...
        @property
        def wpa_flags(self) -> GObject.GFlags: ...

    @property
    def props(self) -> Props: ...
    def connection_valid(self, connection: Connection) -> bool: ...
    def filter_connections(
        self, connections: Sequence[Connection]
    ) -> list[Connection]: ...
    def get_bandwidth(self) -> int: ...
    def get_bssid(self) -> str: ...
    def get_flags(self) -> GObject.GFlags: ...
    def get_frequency(self) -> int: ...
    def get_last_seen(self) -> int: ...
    def get_max_bitrate(self) -> int: ...
    def get_mode(self) -> GObject.GEnum: ...
    def get_rsn_flags(self) -> GObject.GFlags: ...
    def get_ssid(self) -> GLib.Bytes: ...
    def get_strength(self) -> int: ...
    def get_wpa_flags(self) -> GObject.GFlags: ...

class AccessPointClass(_gi.Struct): ...

class ActiveConnection(Object):
    """
    :Constructors:

    ::

        ActiveConnection(**properties)

    Object NMActiveConnection

    Signals from NMActiveConnection:
      state-changed (guint, guint)

    Properties from NMActiveConnection:
      connection -> NMRemoteConnection:

      id -> gchararray:

      uuid -> gchararray:

      type -> gchararray:

      specific-object-path -> gchararray:

      devices -> GPtrArray:

      state -> NMActiveConnectionState:

      state-flags -> guint:

      default -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      default6 -> gboolean:

      ip6-config -> NMIPConfig:

      dhcp6-config -> NMDhcpConfig:

      vpn -> gboolean:

      master -> NMDevice:

      controller -> NMDevice:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Object.Props):
        @property
        def connection(self) -> RemoteConnection: ...
        @property
        def controller(self) -> Device: ...
        @property
        def default(self) -> bool: ...
        @property
        def default6(self) -> bool: ...
        @property
        def devices(self) -> list[Device]: ...
        @property
        def dhcp4_config(self) -> DhcpConfig: ...
        @property
        def dhcp6_config(self) -> DhcpConfig: ...
        @property
        def id(self) -> str: ...
        @property
        def ip4_config(self) -> IPConfig: ...
        @property
        def ip6_config(self) -> IPConfig: ...
        @property
        def master(self) -> Device: ...
        @property
        def specific_object_path(self) -> str: ...
        @property
        def state(self) -> ActiveConnectionState: ...
        @property
        def state_flags(self) -> int: ...
        @property
        def type(self) -> str | None: ...
        @property
        def uuid(self) -> str: ...
        @property
        def vpn(self) -> bool: ...

    @property
    def props(self) -> Props: ...
    def get_connection(self) -> RemoteConnection: ...
    def get_connection_type(self) -> str: ...
    def get_controller(self) -> Device: ...
    def get_default(self) -> bool: ...
    def get_default6(self) -> bool: ...
    def get_devices(self) -> list[Device]: ...
    def get_dhcp4_config(self) -> DhcpConfig: ...
    def get_dhcp6_config(self) -> DhcpConfig: ...
    def get_id(self) -> str: ...
    def get_ip4_config(self) -> IPConfig: ...
    def get_ip6_config(self) -> IPConfig: ...
    def get_master(self) -> Device: ...
    def get_specific_object_path(self) -> str: ...
    def get_state(self) -> ActiveConnectionState: ...
    def get_state_flags(self) -> ActivationStateFlags: ...
    def get_state_reason(self) -> ActiveConnectionStateReason: ...
    def get_uuid(self) -> str: ...
    def get_vpn(self) -> bool: ...

class ActiveConnectionClass(_gi.Struct): ...

class BridgeVlan(GObject.GBoxed):
    """
    :Constructors:

    ::

        new(vid_start:int, vid_end:int) -> NM.BridgeVlan
    """
    def __init__(self, vid_start: int, vid_end: int) -> None: ...
    def cmp(self, b: BridgeVlan) -> int: ...
    @staticmethod
    def from_str(str: str) -> BridgeVlan: ...
    def get_vid_range(self) -> tuple[bool, int, int]: ...
    def is_pvid(self) -> bool: ...
    def is_sealed(self) -> bool: ...
    def is_untagged(self) -> bool: ...
    @classmethod
    def new(cls, vid_start: int, vid_end: int) -> BridgeVlan: ...
    def new_clone(self) -> BridgeVlan: ...
    def ref(self) -> BridgeVlan: ...
    def seal(self) -> None: ...
    def set_pvid(self, value: bool) -> None: ...
    def set_untagged(self, value: bool) -> None: ...
    def to_str(self) -> str: ...
    def unref(self) -> None: ...

class Checkpoint(Object):
    """
    :Constructors:

    ::

        Checkpoint(**properties)

    Object NMCheckpoint

    Properties from NMCheckpoint:
      devices -> GPtrArray:

      created -> gint64:

      rollback-timeout -> guint:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Object.Props):
        @property
        def created(self) -> int: ...
        @property
        def devices(self) -> list[Device]: ...
        @property
        def rollback_timeout(self) -> int: ...

    @property
    def props(self) -> Props: ...
    def get_created(self) -> int: ...
    def get_devices(self) -> list[Device]: ...
    def get_rollback_timeout(self) -> int: ...

class CheckpointClass(_gi.Struct): ...

class Client(GObject.Object, Gio.AsyncInitable, Gio.Initable):
    """
    :Constructors:

    ::

        Client(**properties)
        new(cancellable:Gio.Cancellable=None) -> NM.Client
        new_finish(result:Gio.AsyncResult) -> NM.Client

    Object NMClient

    Signals from NMClient:
      device-added (GObject)
      device-removed (GObject)
      any-device-added (GObject)
      any-device-removed (GObject)
      permission-changed (guint, guint)
      connection-added (NMRemoteConnection)
      connection-removed (NMRemoteConnection)
      active-connection-added (NMActiveConnection)
      active-connection-removed (NMActiveConnection)

    Properties from NMClient:
      dbus-connection -> GDBusConnection:

      dbus-name-owner -> gchararray:

      version -> gchararray:

      instance-flags -> guint:

      state -> NMState:

      startup -> gboolean:

      nm-running -> gboolean:

      networking-enabled -> gboolean:

      wireless-enabled -> gboolean:

      wireless-hardware-enabled -> gboolean:

      wwan-enabled -> gboolean:

      wwan-hardware-enabled -> gboolean:

      wimax-enabled -> gboolean:

      wimax-hardware-enabled -> gboolean:

      radio-flags -> guint:

      active-connections -> GPtrArray:

      connectivity -> NMConnectivityState:

      connectivity-check-uri -> gchararray:

      connectivity-check-available -> gboolean:

      connectivity-check-enabled -> gboolean:

      primary-connection -> NMActiveConnection:

      activating-connection -> NMActiveConnection:

      devices -> GPtrArray:

      all-devices -> GPtrArray:

      connections -> GPtrArray:

      hostname -> gchararray:

      can-modify -> gboolean:

      metered -> guint:

      dns-mode -> gchararray:

      dns-rc-manager -> gchararray:

      dns-configuration -> GPtrArray:

      checkpoints -> GPtrArray:

      version-info -> GArray:

      capabilities -> GArray:

      permissions-state -> NMTernary:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(GObject.Object.Props):
        @property
        def activating_connection(self) -> ActiveConnection: ...
        @property
        def active_connections(self) -> list[ActiveConnection]: ...
        @property
        def all_devices(self) -> list[Device]: ...
        @property
        def can_modify(self) -> bool: ...
        @property
        def capabilities(self) -> list[int]: ...
        @property
        def checkpoints(self) -> list[Checkpoint]: ...
        @property
        def connections(self) -> list[RemoteConnection]: ...
        @property
        def connectivity(self) -> ConnectivityState: ...
        @property
        def connectivity_check_available(self) -> bool: ...
        connectivity_check_enabled: bool
        @property
        def connectivity_check_uri(self) -> str | None: ...
        @property
        def dbus_connection(self) -> Gio.DBusConnection: ...
        @property
        def dbus_name_owner(self) -> str: ...
        @property
        def devices(self) -> list[Device]: ...
        @property
        def dns_configuration(self) -> list[DnsEntry]: ...
        @property
        def dns_mode(self) -> str: ...
        @property
        def dns_rc_manager(self) -> str: ...
        @property
        def hostname(self) -> str | None: ...
        instance_flags: int
        @property
        def metered(self) -> int: ...
        networking_enabled: bool
        @property
        def nm_running(self) -> bool: ...
        @property
        def permissions_state(self) -> Ternary: ...
        @property
        def primary_connection(self) -> ActiveConnection: ...
        @property
        def radio_flags(self) -> int: ...
        @property
        def startup(self) -> bool: ...
        @property
        def state(self) -> State: ...
        @property
        def version(self) -> str: ...
        @property
        def version_info(self) -> list[int]: ...
        wimax_enabled: bool
        @property
        def wimax_hardware_enabled(self) -> bool: ...
        wireless_enabled: bool
        @property
        def wireless_hardware_enabled(self) -> bool: ...
        wwan_enabled: bool
        @property
        def wwan_hardware_enabled(self) -> bool: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        connectivity_check_enabled: bool = ...,
        dbus_connection: Gio.DBusConnection | None = ...,
        instance_flags: int = ...,
        networking_enabled: bool = ...,
        wimax_enabled: bool = ...,
        wireless_enabled: bool = ...,
        wwan_enabled: bool = ...,
    ) -> None: ...
    @overload
    def activate_connection_async(
        self,
        connection: Connection | None = None,
        device: Device | None = None,
        specific_object: str | None = None,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[ActiveConnection]: ...
    @overload
    def activate_connection_async(
        self,
        connection: Connection | None,
        device: Device | None,
        specific_object: str | None,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def activate_connection_async(
        self,
        connection: Connection | None = None,
        device: Device | None = None,
        specific_object: str | None = None,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def activate_connection_finish(
        self, result: Gio.AsyncResult
    ) -> ActiveConnection: ...
    @overload
    def add_and_activate_connection2(
        self,
        partial: Connection | None,
        device: Device | None,
        specific_object: str | None,
        options: GLib.Variant,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[tuple[ActiveConnection, GLib.Variant | None]]: ...
    @overload
    def add_and_activate_connection2(
        self,
        partial: Connection | None,
        device: Device | None,
        specific_object: str | None,
        options: GLib.Variant,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def add_and_activate_connection2(
        self,
        partial: Connection | None,
        device: Device | None,
        specific_object: str | None,
        options: GLib.Variant,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def add_and_activate_connection2_finish(
        self, result: Gio.AsyncResult
    ) -> tuple[ActiveConnection, GLib.Variant | None]: ...
    @overload
    def add_and_activate_connection_async(
        self,
        partial: Connection | None = None,
        device: Device | None = None,
        specific_object: str | None = None,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[ActiveConnection]: ...
    @overload
    def add_and_activate_connection_async(
        self,
        partial: Connection | None,
        device: Device | None,
        specific_object: str | None,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def add_and_activate_connection_async(
        self,
        partial: Connection | None = None,
        device: Device | None = None,
        specific_object: str | None = None,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def add_and_activate_connection_finish(
        self, result: Gio.AsyncResult
    ) -> ActiveConnection: ...
    @overload
    def add_connection2(
        self,
        settings: GLib.Variant,
        flags: _SettingsAddConnection2FlagsValueType,
        args: GLib.Variant | None,
        ignore_out_result: bool,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[tuple[RemoteConnection, GLib.Variant | None]]: ...
    @overload
    def add_connection2(
        self,
        settings: GLib.Variant,
        flags: _SettingsAddConnection2FlagsValueType,
        args: GLib.Variant | None,
        ignore_out_result: bool,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def add_connection2(
        self,
        settings: GLib.Variant,
        flags: _SettingsAddConnection2FlagsValueType,
        args: GLib.Variant | None,
        ignore_out_result: bool,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def add_connection2_finish(
        self, result: Gio.AsyncResult
    ) -> tuple[RemoteConnection, GLib.Variant | None]: ...
    @overload
    def add_connection_async(
        self,
        connection: Connection,
        save_to_disk: bool,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[RemoteConnection]: ...
    @overload
    def add_connection_async(
        self,
        connection: Connection,
        save_to_disk: bool,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def add_connection_async(
        self,
        connection: Connection,
        save_to_disk: bool,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def add_connection_finish(self, result: Gio.AsyncResult) -> RemoteConnection: ...
    def check_connectivity(
        self, cancellable: Gio.Cancellable | None = None
    ) -> ConnectivityState: ...
    @overload
    def check_connectivity_async(
        self, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[ConnectivityState]: ...
    @overload
    def check_connectivity_async(
        self,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def check_connectivity_async(
        self,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def check_connectivity_finish(
        self, result: Gio.AsyncResult
    ) -> ConnectivityState: ...
    @overload
    def checkpoint_adjust_rollback_timeout(
        self,
        checkpoint_path: str,
        add_timeout: int,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[bool]: ...
    @overload
    def checkpoint_adjust_rollback_timeout(
        self,
        checkpoint_path: str,
        add_timeout: int,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def checkpoint_adjust_rollback_timeout(
        self,
        checkpoint_path: str,
        add_timeout: int,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def checkpoint_adjust_rollback_timeout_finish(
        self, result: Gio.AsyncResult
    ) -> bool: ...
    @overload
    def checkpoint_create(
        self,
        devices: Sequence[Device],
        rollback_timeout: int,
        flags: _CheckpointCreateFlagsValueType,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[Checkpoint]: ...
    @overload
    def checkpoint_create(
        self,
        devices: Sequence[Device],
        rollback_timeout: int,
        flags: _CheckpointCreateFlagsValueType,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def checkpoint_create(
        self,
        devices: Sequence[Device],
        rollback_timeout: int,
        flags: _CheckpointCreateFlagsValueType,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def checkpoint_create_finish(self, result: Gio.AsyncResult) -> Checkpoint: ...
    @overload
    def checkpoint_destroy(
        self, checkpoint_path: str, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def checkpoint_destroy(
        self,
        checkpoint_path: str,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def checkpoint_destroy(
        self,
        checkpoint_path: str,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def checkpoint_destroy_finish(self, result: Gio.AsyncResult) -> bool: ...
    @overload
    def checkpoint_rollback(
        self, checkpoint_path: str, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[dict[str, int]]: ...
    @overload
    def checkpoint_rollback(
        self,
        checkpoint_path: str,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def checkpoint_rollback(
        self,
        checkpoint_path: str,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def checkpoint_rollback_finish(self, result: Gio.AsyncResult) -> dict[str, int]: ...
    def connectivity_check_get_available(self) -> bool: ...
    def connectivity_check_get_enabled(self) -> bool: ...
    def connectivity_check_get_uri(self) -> str: ...
    def connectivity_check_set_enabled(self, enabled: bool) -> None: ...
    @overload
    def dbus_call(
        self,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant | None,
        reply_type: GLib.VariantType | None,
        timeout_msec: int,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[GLib.Variant]: ...
    @overload
    def dbus_call(
        self,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant | None,
        reply_type: GLib.VariantType | None,
        timeout_msec: int,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def dbus_call(
        self,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant | None,
        reply_type: GLib.VariantType | None,
        timeout_msec: int,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def dbus_call_finish(self, result: Gio.AsyncResult) -> GLib.Variant: ...
    @overload
    def dbus_set_property(
        self,
        object_path: str,
        interface_name: str,
        property_name: str,
        value: GLib.Variant,
        timeout_msec: int,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[bool]: ...
    @overload
    def dbus_set_property(
        self,
        object_path: str,
        interface_name: str,
        property_name: str,
        value: GLib.Variant,
        timeout_msec: int,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def dbus_set_property(
        self,
        object_path: str,
        interface_name: str,
        property_name: str,
        value: GLib.Variant,
        timeout_msec: int,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def dbus_set_property_finish(self, result: Gio.AsyncResult) -> bool: ...
    def deactivate_connection(
        self, active: ActiveConnection, cancellable: Gio.Cancellable | None = None
    ) -> bool: ...
    @overload
    def deactivate_connection_async(
        self, active: ActiveConnection, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def deactivate_connection_async(
        self,
        active: ActiveConnection,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def deactivate_connection_async(
        self,
        active: ActiveConnection,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def deactivate_connection_finish(self, result: Gio.AsyncResult) -> bool: ...
    def get_activating_connection(self) -> ActiveConnection: ...
    def get_active_connections(self) -> list[ActiveConnection]: ...
    def get_all_devices(self) -> list[Device]: ...
    def get_capabilities(self) -> list[int]: ...
    def get_checkpoints(self) -> list[Checkpoint]: ...
    def get_connection_by_id(self, id: str) -> RemoteConnection: ...
    def get_connection_by_path(self, path: str) -> RemoteConnection: ...
    def get_connection_by_uuid(self, uuid: str) -> RemoteConnection: ...
    def get_connections(self) -> list[RemoteConnection]: ...
    def get_connectivity(self) -> ConnectivityState: ...
    def get_context_busy_watcher(self) -> GObject.Object: ...
    def get_dbus_connection(self) -> Gio.DBusConnection: ...
    def get_dbus_name_owner(self) -> str: ...
    def get_device_by_iface(self, iface: str) -> Device: ...
    def get_device_by_path(self, object_path: str) -> Device: ...
    def get_devices(self) -> list[Device]: ...
    def get_dns_configuration(self) -> list[DnsEntry]: ...
    def get_dns_mode(self) -> str: ...
    def get_dns_rc_manager(self) -> str: ...
    def get_instance_flags(self) -> ClientInstanceFlags: ...
    def get_logging(self) -> tuple[bool, str | None, str | None]: ...
    def get_main_context(self) -> GLib.MainContext: ...
    def get_metered(self) -> Metered: ...
    def get_nm_running(self) -> bool: ...
    def get_object_by_path(self, dbus_path: str) -> Object: ...
    def get_permission_result(
        self, permission: _ClientPermissionValueType
    ) -> ClientPermissionResult: ...
    def get_permissions_state(self) -> Ternary: ...
    def get_primary_connection(self) -> ActiveConnection: ...
    def get_radio_flags(self) -> RadioFlags: ...
    def get_startup(self) -> bool: ...
    def get_state(self) -> State: ...
    def get_version(self) -> str: ...
    def get_version_info(self) -> list[int]: ...
    def load_connections(
        self, filenames: Sequence[str], cancellable: Gio.Cancellable | None = None
    ) -> tuple[bool, str]: ...
    @overload
    def load_connections_async(
        self, filenames: Sequence[str], cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[tuple[bool, list[str]]]: ...
    @overload
    def load_connections_async(
        self,
        filenames: Sequence[str],
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def load_connections_async(
        self,
        filenames: Sequence[str],
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def load_connections_finish(
        self, result: Gio.AsyncResult
    ) -> tuple[bool, list[str]]: ...
    def networking_get_enabled(self) -> bool: ...
    def networking_set_enabled(self, enabled: bool) -> bool: ...
    @classmethod
    def new(cls, cancellable: Gio.Cancellable | None = None) -> Client: ...
    @overload
    @staticmethod
    def new_async(cancellable: Gio.Cancellable | None = None) -> _gi.Async[Client]: ...
    @overload
    @staticmethod
    def new_async(
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[None, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    @staticmethod
    def new_async(
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[None] | None,
    ) -> None: ...
    @classmethod
    def new_finish(cls, result: Gio.AsyncResult) -> Client: ...
    @overload
    def reload(
        self,
        flags: _ManagerReloadFlagsValueType,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[bool]: ...
    @overload
    def reload(
        self,
        flags: _ManagerReloadFlagsValueType,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def reload(
        self,
        flags: _ManagerReloadFlagsValueType,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def reload_connections(
        self, cancellable: Gio.Cancellable | None = None
    ) -> bool: ...
    @overload
    def reload_connections_async(
        self, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def reload_connections_async(
        self,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def reload_connections_async(
        self,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def reload_connections_finish(self, result: Gio.AsyncResult) -> bool: ...
    def reload_finish(self, result: Gio.AsyncResult) -> bool: ...
    def save_hostname(
        self, hostname: str | None = None, cancellable: Gio.Cancellable | None = None
    ) -> bool: ...
    @overload
    def save_hostname_async(
        self, hostname: str | None = None, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def save_hostname_async(
        self,
        hostname: str | None,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def save_hostname_async(
        self,
        hostname: str | None = None,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    def save_hostname_finish(self, result: Gio.AsyncResult) -> bool: ...
    def set_logging(
        self, level: str | None = None, domains: str | None = None
    ) -> bool: ...
    @overload
    def wait_shutdown(
        self, integrate_maincontext: bool, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def wait_shutdown(
        self,
        integrate_maincontext: bool,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Client, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def wait_shutdown(
        self,
        integrate_maincontext: bool,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Client] | None,
    ) -> None: ...
    @staticmethod
    def wait_shutdown_finish(result: Gio.AsyncResult) -> bool: ...
    def wimax_get_enabled(self) -> bool: ...
    def wimax_hardware_get_enabled(self) -> bool: ...
    def wimax_set_enabled(self, enabled: bool) -> None: ...
    def wireless_get_enabled(self) -> bool: ...
    def wireless_hardware_get_enabled(self) -> bool: ...
    def wireless_set_enabled(self, enabled: bool) -> None: ...
    def wwan_get_enabled(self) -> bool: ...
    def wwan_hardware_get_enabled(self) -> bool: ...
    def wwan_set_enabled(self, enabled: bool) -> None: ...

class ClientClass(_gi.Struct): ...

class Connection(GObject.GInterface, Protocol):
    """
    Interface NMConnection

    Signals from GObject:
      notify (GParam)
    """
    def add_setting(self, setting: Setting) -> None: ...
    def clear_secrets(self) -> None: ...
    def clear_secrets_with_flags(
        self,
        func: Callable[
            [Setting, str, _SettingSecretFlagsValueType, Unpack[_DataTs]], bool
        ]
        | None = None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    def clear_settings(self) -> None: ...
    def compare(self, b: Connection, flags: _SettingCompareFlagsValueType) -> bool: ...
    def dump(self) -> None: ...
    def for_each_setting_value(
        self,
        func: Callable[[Setting, str, Any, GObject.ParamFlags, Unpack[_DataTs]], None],
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    def get_connection_type(self) -> str: ...
    def get_id(self) -> str: ...
    def get_interface_name(self) -> str: ...
    def get_path(self) -> str: ...
    def get_setting(self, setting_type: type[Any]) -> Setting: ...
    def get_setting_802_1x(self) -> Setting8021x: ...
    def get_setting_adsl(self) -> SettingAdsl: ...
    def get_setting_bluetooth(self) -> SettingBluetooth: ...
    def get_setting_bond(self) -> SettingBond: ...
    def get_setting_bridge(self) -> SettingBridge: ...
    def get_setting_bridge_port(self) -> SettingBridgePort: ...
    def get_setting_by_name(self, name: str) -> Setting: ...
    def get_setting_cdma(self) -> SettingCdma: ...
    def get_setting_connection(self) -> SettingConnection: ...
    def get_setting_dcb(self) -> SettingDcb: ...
    def get_setting_dummy(self) -> SettingDummy: ...
    def get_setting_generic(self) -> SettingGeneric: ...
    def get_setting_geneve(self) -> SettingGeneve: ...
    def get_setting_gsm(self) -> SettingGsm: ...
    def get_setting_infiniband(self) -> SettingInfiniband: ...
    def get_setting_ip4_config(self) -> SettingIP4Config: ...
    def get_setting_ip6_config(self) -> SettingIP6Config: ...
    def get_setting_ip_tunnel(self) -> SettingIPTunnel: ...
    def get_setting_macsec(self) -> SettingMacsec: ...
    def get_setting_macvlan(self) -> SettingMacvlan: ...
    def get_setting_olpc_mesh(self) -> SettingOlpcMesh: ...
    def get_setting_ovs_bridge(self) -> SettingOvsBridge: ...
    def get_setting_ovs_interface(self) -> SettingOvsInterface: ...
    def get_setting_ovs_patch(self) -> SettingOvsPatch: ...
    def get_setting_ovs_port(self) -> SettingOvsPort: ...
    def get_setting_ppp(self) -> SettingPpp: ...
    def get_setting_pppoe(self) -> SettingPppoe: ...
    def get_setting_proxy(self) -> SettingProxy: ...
    def get_setting_serial(self) -> SettingSerial: ...
    def get_setting_tc_config(self) -> SettingTCConfig: ...
    def get_setting_team(self) -> SettingTeam: ...
    def get_setting_team_port(self) -> SettingTeamPort: ...
    def get_setting_tun(self) -> SettingTun: ...
    def get_setting_vlan(self) -> SettingVlan: ...
    def get_setting_vpn(self) -> SettingVpn: ...
    def get_setting_vxlan(self) -> SettingVxlan: ...
    def get_setting_wimax(self) -> SettingWimax: ...
    def get_setting_wired(self) -> SettingWired: ...
    def get_setting_wireless(self) -> SettingWireless: ...
    def get_setting_wireless_security(self) -> SettingWirelessSecurity: ...
    def get_settings(self) -> list[Setting]: ...
    def get_uuid(self) -> str: ...
    def get_virtual_device_description(self) -> str: ...
    def is_type(self, type: str) -> bool: ...
    def is_virtual(self) -> bool: ...
    def need_secrets(self) -> tuple[str | None, list[str]]: ...
    def normalize(
        self, parameters: Mapping[str, int | Any | None] | None = None
    ) -> tuple[bool, bool]: ...
    def remove_setting(self, setting_type: type[Any]) -> None: ...
    def replace_settings(self, new_settings: GLib.Variant) -> bool: ...
    def replace_settings_from_connection(self, new_connection: Connection) -> None: ...
    def set_path(self, path: str) -> None: ...
    def to_dbus(
        self, flags: _ConnectionSerializationFlagsValueType
    ) -> GLib.Variant: ...
    def update_secrets(self, setting_name: str, secrets: GLib.Variant) -> bool: ...
    def verify(self) -> bool: ...
    def verify_secrets(self) -> bool: ...

class ConnectionInterface(_gi.Struct):
    """
    :Constructors:

    ::

        ConnectionInterface()
    """
    @property
    def parent(self) -> GObject.TypeInterface: ...
    @property
    def secrets_updated(self) -> Callable[[Connection, str], None]: ...
    @property
    def secrets_cleared(self) -> Callable[[Connection], None]: ...
    @property
    def changed(self) -> Callable[[Connection], None]: ...

class Device(Object):
    """
    :Constructors:

    ::

        Device(**properties)

    Object NMDevice

    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Object.Props):
        @property
        def active_connection(self) -> ActiveConnection: ...
        autoconnect: bool
        @property
        def available_connections(self) -> list[RemoteConnection]: ...
        @property
        def capabilities(self) -> DeviceCapabilities: ...
        @property
        def device_type(self) -> DeviceType: ...
        @property
        def dhcp4_config(self) -> DhcpConfig: ...
        @property
        def dhcp6_config(self) -> DhcpConfig: ...
        @property
        def driver(self) -> str: ...
        @property
        def driver_version(self) -> str: ...
        @property
        def firmware_missing(self) -> bool: ...
        @property
        def firmware_version(self) -> str: ...
        @property
        def hw_address(self) -> str: ...
        @property
        def interface(self) -> str | None: ...
        @property
        def interface_flags(self) -> int: ...
        @property
        def ip_interface(self) -> str | None: ...
        @property
        def ip4_config(self) -> IPConfig: ...
        @property
        def ip4_connectivity(self) -> ConnectivityState: ...
        @property
        def ip6_config(self) -> IPConfig: ...
        @property
        def ip6_connectivity(self) -> ConnectivityState: ...
        @property
        def lldp_neighbors(self) -> list[int]: ...
        @property
        def managed(self) -> bool: ...
        @property
        def metered(self) -> int: ...
        @property
        def mtu(self) -> int: ...
        @property
        def nm_plugin_missing(self) -> bool: ...
        @property
        def path(self) -> str: ...
        @property
        def physical_port_id(self) -> str: ...
        @property
        def ports(self) -> list[int]: ...
        @property
        def product(self) -> str: ...
        @property
        def real(self) -> bool: ...
        @property
        def state(self) -> DeviceState: ...
        @property
        def state_reason(self) -> int: ...
        @property
        def udi(self) -> str: ...
        @property
        def vendor(self) -> str: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def connection_compatible(self, connection: Connection) -> bool: ...
    def connection_valid(self, connection: Connection) -> bool: ...
    def delete(self, cancellable: Gio.Cancellable | None = None) -> bool: ...
    @overload
    def delete_async(
        self, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def delete_async(
        self,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Device, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def delete_async(
        self,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Device] | None,
    ) -> None: ...
    def delete_finish(self, result: Gio.AsyncResult) -> bool: ...
    @staticmethod
    def disambiguate_names(devices: Sequence[Device]) -> list[str]: ...
    def disconnect(self, cancellable: Gio.Cancellable | None = None) -> bool: ...
    @overload
    def disconnect_async(
        self, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def disconnect_async(
        self,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Device, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def disconnect_async(
        self,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Device] | None,
    ) -> None: ...
    def disconnect_finish(self, result: Gio.AsyncResult) -> bool: ...
    def filter_connections(
        self, connections: Sequence[Connection]
    ) -> list[Connection]: ...
    def get_active_connection(self) -> ActiveConnection: ...
    def get_applied_connection(
        self, flags: int, cancellable: Gio.Cancellable | None = None
    ) -> tuple[Connection, int]: ...
    @overload
    def get_applied_connection_async(
        self, flags: int, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[tuple[Connection, int]]: ...
    @overload
    def get_applied_connection_async(
        self,
        flags: int,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Device, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def get_applied_connection_async(
        self,
        flags: int,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Device] | None,
    ) -> None: ...
    def get_applied_connection_finish(
        self, result: Gio.AsyncResult
    ) -> tuple[Connection, int]: ...
    def get_autoconnect(self) -> bool: ...
    def get_available_connections(self) -> list[RemoteConnection]: ...
    def get_capabilities(self) -> DeviceCapabilities: ...
    def get_connectivity(self, addr_family: int) -> ConnectivityState: ...
    def get_description(self) -> str: ...
    def get_device_type(self) -> DeviceType: ...
    def get_dhcp4_config(self) -> DhcpConfig: ...
    def get_dhcp6_config(self) -> DhcpConfig: ...
    def get_driver(self) -> str: ...
    def get_driver_version(self) -> str: ...
    def get_firmware_missing(self) -> bool: ...
    def get_firmware_version(self) -> str: ...
    def get_hw_address(self) -> str: ...
    def get_iface(self) -> str: ...
    def get_interface_flags(self) -> DeviceInterfaceFlags: ...
    def get_ip4_config(self) -> IPConfig: ...
    def get_ip6_config(self) -> IPConfig: ...
    def get_ip_iface(self) -> str: ...
    def get_lldp_neighbors(self) -> list[LldpNeighbor]: ...
    def get_managed(self) -> bool: ...
    def get_metered(self) -> Metered: ...
    def get_mtu(self) -> int: ...
    def get_nm_plugin_missing(self) -> bool: ...
    def get_path(self) -> str: ...
    def get_physical_port_id(self) -> str: ...
    def get_ports(self) -> list[Device]: ...
    def get_product(self) -> str: ...
    def get_setting_type(self) -> type[Any]: ...
    def get_state(self) -> DeviceState: ...
    def get_state_reason(self) -> DeviceStateReason: ...
    def get_type_description(self) -> str: ...
    def get_udi(self) -> str: ...
    def get_vendor(self) -> str: ...
    def is_real(self) -> bool: ...
    def is_software(self) -> bool: ...
    def reapply(
        self,
        connection: Connection | None,
        version_id: int,
        flags: int,
        cancellable: Gio.Cancellable | None = None,
    ) -> bool: ...
    @overload
    def reapply_async(
        self,
        connection: Connection | None,
        version_id: int,
        flags: int,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[bool]: ...
    @overload
    def reapply_async(
        self,
        connection: Connection | None,
        version_id: int,
        flags: int,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Device, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def reapply_async(
        self,
        connection: Connection | None,
        version_id: int,
        flags: int,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Device] | None,
    ) -> None: ...
    def reapply_finish(self, result: Gio.AsyncResult) -> bool: ...
    def set_autoconnect(self, autoconnect: bool) -> None: ...
    def set_managed(self, managed: bool) -> None: ...
    @overload
    def set_managed_async(
        self,
        managed: _DeviceManagedValueType,
        flags: _DeviceManagedFlagsValueType,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[bool]: ...
    @overload
    def set_managed_async(
        self,
        managed: _DeviceManagedValueType,
        flags: _DeviceManagedFlagsValueType,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[Device, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def set_managed_async(
        self,
        managed: _DeviceManagedValueType,
        flags: _DeviceManagedFlagsValueType,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[Device] | None,
    ) -> None: ...
    def set_managed_finish(self, result: Gio.AsyncResult) -> bool: ...

class Device6Lowpan(Device):
    """
    :Constructors:

    ::

        Device6Lowpan(**properties)

    Object NMDevice6Lowpan

    Properties from NMDevice6Lowpan:
      parent -> NMDevice:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def parent(self) -> Device: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_parent(self) -> Device: ...

class Device6LowpanClass(_gi.Struct): ...

class DeviceAdsl(Device):
    """
    :Constructors:

    ::

        DeviceAdsl(**properties)

    Object NMDeviceAdsl

    Properties from NMDeviceAdsl:
      carrier -> gboolean:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def carrier(self) -> bool: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_carrier(self) -> bool: ...

class DeviceAdslClass(_gi.Struct): ...

class DeviceBond(Device):
    """
    :Constructors:

    ::

        DeviceBond(**properties)

    Object NMDeviceBond

    Properties from NMDeviceBond:
      carrier -> gboolean:

      slaves -> GPtrArray:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def carrier(self) -> bool: ...
        @property
        def slaves(self) -> list[Device]: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_carrier(self) -> bool: ...
    def get_slaves(self) -> list[Device]: ...

class DeviceBondClass(_gi.Struct): ...

class DeviceBridge(Device):
    """
    :Constructors:

    ::

        DeviceBridge(**properties)

    Object NMDeviceBridge

    Properties from NMDeviceBridge:
      carrier -> gboolean:

      slaves -> GPtrArray:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def carrier(self) -> bool: ...
        @property
        def slaves(self) -> list[Device]: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_carrier(self) -> bool: ...
    def get_slaves(self) -> list[Device]: ...

class DeviceBridgeClass(_gi.Struct): ...

class DeviceBt(Device):
    """
    :Constructors:

    ::

        DeviceBt(**properties)

    Object NMDeviceBt

    Properties from NMDeviceBt:
      name -> gchararray:

      bt-capabilities -> NMBluetoothCapabilities:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def bt_capabilities(self) -> BluetoothCapabilities: ...
        @property
        def name(self) -> str: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_capabilities(self) -> BluetoothCapabilities: ...
    def get_name(self) -> str: ...

class DeviceBtClass(_gi.Struct): ...
class DeviceClass(_gi.Struct): ...

class DeviceDummy(Device):
    """
    :Constructors:

    ::

        DeviceDummy(**properties)

    Object NMDeviceDummy

    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    def __init__(self, *, autoconnect: bool = ...) -> None: ...

class DeviceDummyClass(_gi.Struct): ...

class DeviceEthernet(Device):
    """
    :Constructors:

    ::

        DeviceEthernet(**properties)

    Object NMDeviceEthernet

    Properties from NMDeviceEthernet:
      perm-hw-address -> gchararray:

      speed -> guint:

      carrier -> gboolean:

      s390-subchannels -> GStrv:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def carrier(self) -> bool: ...
        @property
        def perm_hw_address(self) -> str | None: ...
        @property
        def s390_subchannels(self) -> list[str]: ...
        @property
        def speed(self) -> int: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_carrier(self) -> bool: ...
    def get_permanent_hw_address(self) -> str: ...
    def get_s390_subchannels(self) -> list[str]: ...
    def get_speed(self) -> int: ...

class DeviceEthernetClass(_gi.Struct): ...

class DeviceGeneric(Device):
    """
    :Constructors:

    ::

        DeviceGeneric(**properties)

    Object NMDeviceGeneric

    Properties from NMDeviceGeneric:
      type-description -> gchararray:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def type_description(self) -> str | None: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...

class DeviceGenericClass(_gi.Struct): ...

class DeviceGeneve(Device):
    """
    :Constructors:

    ::

        DeviceGeneve(**properties)

    Object NMDeviceGeneve

    Properties from NMDeviceGeneve:
      id -> guint:

      remote -> gchararray:

      tos -> guchar:

      ttl -> gint:

      dst-port -> guint:

      df -> guchar:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def df(self) -> int: ...
        @property
        def dst_port(self) -> int: ...
        @property
        def id(self) -> int: ...
        @property
        def remote(self) -> str: ...
        @property
        def tos(self) -> int: ...
        @property
        def ttl(self) -> int: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_df(self) -> int: ...
    def get_dst_port(self) -> int: ...
    def get_id(self) -> int: ...
    def get_remote(self) -> str: ...
    def get_tos(self) -> int: ...
    def get_ttl(self) -> int: ...

class DeviceGeneveClass(_gi.Struct): ...

class DeviceHsr(Device):
    """
    :Constructors:

    ::

        DeviceHsr(**properties)

    Object NMDeviceHsr

    Properties from NMDeviceHsr:
      port1 -> NMDevice:

      port2 -> NMDevice:

      supervision-address -> gchararray:

      multicast-spec -> guchar:

      prp -> gboolean:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def multicast_spec(self) -> int: ...
        @property
        def port1(self) -> Device: ...
        @property
        def port2(self) -> Device: ...
        @property
        def prp(self) -> bool: ...
        @property
        def supervision_address(self) -> str: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_multicast_spec(self) -> int: ...
    def get_port1(self) -> Device: ...
    def get_port2(self) -> Device: ...
    def get_prp(self) -> bool: ...
    def get_supervision_address(self) -> str: ...

class DeviceHsrClass(_gi.Struct): ...

class DeviceIPTunnel(Device):
    """
    :Constructors:

    ::

        DeviceIPTunnel(**properties)

    Object NMDeviceIPTunnel

    Properties from NMDeviceIPTunnel:
      mode -> guint:

      parent -> NMDevice:

      local -> gchararray:

      remote -> gchararray:

      ttl -> guchar:

      tos -> guchar:

      path-mtu-discovery -> gboolean:

      input-key -> gchararray:

      output-key -> gchararray:

      encapsulation-limit -> guchar:

      flow-label -> guint:

      fwmark -> guint:

      flags -> guint:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def encapsulation_limit(self) -> int: ...
        @property
        def flags(self) -> int: ...
        @property
        def flow_label(self) -> int: ...
        @property
        def fwmark(self) -> int: ...
        @property
        def input_key(self) -> str: ...
        @property
        def local(self) -> str: ...
        @property
        def mode(self) -> int: ...
        @property
        def output_key(self) -> str: ...
        @property
        def parent(self) -> Device: ...
        @property
        def path_mtu_discovery(self) -> bool: ...
        @property
        def remote(self) -> str: ...
        @property
        def tos(self) -> int: ...
        @property
        def ttl(self) -> int: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_encapsulation_limit(self) -> int: ...
    def get_flags(self) -> IPTunnelFlags: ...
    def get_flow_label(self) -> int: ...
    def get_fwmark(self) -> int: ...
    def get_input_key(self) -> str: ...
    def get_local(self) -> str: ...
    def get_mode(self) -> IPTunnelMode: ...
    def get_output_key(self) -> str: ...
    def get_parent(self) -> Device: ...
    def get_path_mtu_discovery(self) -> bool: ...
    def get_remote(self) -> str: ...
    def get_tos(self) -> int: ...
    def get_ttl(self) -> int: ...

class DeviceIPTunnelClass(_gi.Struct): ...

class DeviceInfiniband(Device):
    """
    :Constructors:

    ::

        DeviceInfiniband(**properties)

    Object NMDeviceInfiniband

    Properties from NMDeviceInfiniband:
      carrier -> gboolean:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def carrier(self) -> bool: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_carrier(self) -> bool: ...

class DeviceInfinibandClass(_gi.Struct): ...

class DeviceIpvlan(Device):
    """
    :Constructors:

    ::

        DeviceIpvlan(**properties)

    Object NMDeviceIpvlan

    Properties from NMDeviceIpvlan:
      parent -> NMDevice:

      mode -> gchararray:

      private -> gboolean:

      vepa -> gboolean:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def mode(self) -> str: ...
        @property
        def parent(self) -> Device: ...
        @property
        def private(self) -> bool: ...
        @property
        def vepa(self) -> bool: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_mode(self) -> str: ...
    def get_parent(self) -> Device: ...
    def get_private(self) -> bool: ...
    def get_vepa(self) -> bool: ...

class DeviceIpvlanClass(_gi.Struct): ...

class DeviceLoopback(Device):
    """
    :Constructors:

    ::

        DeviceLoopback(**properties)

    Object NMDeviceLoopback

    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    def __init__(self, *, autoconnect: bool = ...) -> None: ...

class DeviceLoopbackClass(_gi.Struct): ...

class DeviceMacsec(Device):
    """
    :Constructors:

    ::

        DeviceMacsec(**properties)

    Object NMDeviceMacsec

    Properties from NMDeviceMacsec:
      parent -> NMDevice:

      sci -> guint64:

      cipher-suite -> guint64:

      icv-length -> guchar:

      window -> guint:

      encoding-sa -> guchar:

      encrypt -> gboolean:

      protect -> gboolean:

      include-sci -> gboolean:

      es -> gboolean:

      scb -> gboolean:

      replay-protect -> gboolean:

      validation -> gchararray:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def cipher_suite(self) -> int: ...
        @property
        def encoding_sa(self) -> int: ...
        @property
        def encrypt(self) -> bool: ...
        @property
        def es(self) -> bool: ...
        @property
        def icv_length(self) -> int: ...
        @property
        def include_sci(self) -> bool: ...
        @property
        def parent(self) -> Device: ...
        @property
        def protect(self) -> bool: ...
        @property
        def replay_protect(self) -> bool: ...
        @property
        def scb(self) -> bool: ...
        @property
        def sci(self) -> int: ...
        @property
        def validation(self) -> str: ...
        @property
        def window(self) -> int: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_cipher_suite(self) -> int: ...
    def get_encoding_sa(self) -> int: ...
    def get_encrypt(self) -> bool: ...
    def get_es(self) -> bool: ...
    def get_icv_length(self) -> int: ...
    def get_include_sci(self) -> bool: ...
    def get_parent(self) -> Device: ...
    def get_protect(self) -> bool: ...
    def get_replay_protect(self) -> bool: ...
    def get_scb(self) -> bool: ...
    def get_sci(self) -> int: ...
    def get_validation(self) -> str: ...
    def get_window(self) -> int: ...

class DeviceMacsecClass(_gi.Struct): ...

class DeviceMacvlan(Device):
    """
    :Constructors:

    ::

        DeviceMacvlan(**properties)

    Object NMDeviceMacvlan

    Properties from NMDeviceMacvlan:
      parent -> NMDevice:

      mode -> gchararray:

      no-promisc -> gboolean:

      tap -> gboolean:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def mode(self) -> str: ...
        @property
        def no_promisc(self) -> bool: ...
        @property
        def parent(self) -> Device: ...
        @property
        def tap(self) -> bool: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_mode(self) -> str: ...
    def get_no_promisc(self) -> bool: ...
    def get_parent(self) -> Device: ...
    def get_tap(self) -> bool: ...

class DeviceMacvlanClass(_gi.Struct): ...

class DeviceModem(Device):
    """
    :Constructors:

    ::

        DeviceModem(**properties)

    Object NMDeviceModem

    Properties from NMDeviceModem:
      modem-capabilities -> NMDeviceModemCapabilities:

      current-capabilities -> NMDeviceModemCapabilities:

      device-id -> gchararray:

      operator-code -> gchararray:

      apn -> gchararray:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def apn(self) -> str: ...
        @property
        def current_capabilities(self) -> DeviceModemCapabilities: ...
        @property
        def device_id(self) -> str: ...
        @property
        def modem_capabilities(self) -> DeviceModemCapabilities: ...
        @property
        def operator_code(self) -> str: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_apn(self) -> str: ...
    def get_current_capabilities(self) -> DeviceModemCapabilities: ...
    def get_device_id(self) -> str: ...
    def get_modem_capabilities(self) -> DeviceModemCapabilities: ...
    def get_operator_code(self) -> str: ...

class DeviceModemClass(_gi.Struct): ...

class DeviceOlpcMesh(Device):
    """
    :Constructors:

    ::

        DeviceOlpcMesh(**properties)

    Object NMDeviceOlpcMesh

    Properties from NMDeviceOlpcMesh:
      companion -> NMDeviceWifi:

      active-channel -> guint:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def active_channel(self) -> int: ...
        @property
        def companion(self) -> DeviceWifi: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_active_channel(self) -> int: ...
    def get_companion(self) -> DeviceWifi: ...

class DeviceOlpcMeshClass(_gi.Struct): ...

class DeviceOvsBridge(Device):
    """
    :Constructors:

    ::

        DeviceOvsBridge(**properties)

    Object NMDeviceOvsBridge

    Properties from NMDeviceOvsBridge:
      slaves -> GPtrArray:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def slaves(self) -> list[Device]: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_slaves(self) -> list[Device]: ...

class DeviceOvsBridgeClass(_gi.Struct): ...

class DeviceOvsInterface(Device):
    """
    :Constructors:

    ::

        DeviceOvsInterface(**properties)

    Object NMDeviceOvsInterface

    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    def __init__(self, *, autoconnect: bool = ...) -> None: ...

class DeviceOvsInterfaceClass(_gi.Struct): ...

class DeviceOvsPort(Device):
    """
    :Constructors:

    ::

        DeviceOvsPort(**properties)

    Object NMDeviceOvsPort

    Properties from NMDeviceOvsPort:
      slaves -> GPtrArray:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def slaves(self) -> list[Device]: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_slaves(self) -> list[Device]: ...

class DeviceOvsPortClass(_gi.Struct): ...

class DevicePpp(Device):
    """
    :Constructors:

    ::

        DevicePpp(**properties)

    Object NMDevicePpp

    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    def __init__(self, *, autoconnect: bool = ...) -> None: ...

class DevicePppClass(_gi.Struct): ...

class DeviceTeam(Device):
    """
    :Constructors:

    ::

        DeviceTeam(**properties)

    Object NMDeviceTeam

    Properties from NMDeviceTeam:
      carrier -> gboolean:

      slaves -> GPtrArray:

      config -> gchararray:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def carrier(self) -> bool: ...
        @property
        def config(self) -> str: ...
        @property
        def slaves(self) -> list[Device]: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_carrier(self) -> bool: ...
    def get_config(self) -> str: ...
    def get_slaves(self) -> list[Device]: ...

class DeviceTeamClass(_gi.Struct): ...

class DeviceTun(Device):
    """
    :Constructors:

    ::

        DeviceTun(**properties)

    Object NMDeviceTun

    Properties from NMDeviceTun:
      mode -> gchararray:

      owner -> gint64:

      group -> gint64:

      no-pi -> gboolean:

      vnet-hdr -> gboolean:

      multi-queue -> gboolean:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def group(self) -> int: ...
        @property
        def mode(self) -> str: ...
        @property
        def multi_queue(self) -> bool: ...
        @property
        def no_pi(self) -> bool: ...
        @property
        def owner(self) -> int: ...
        @property
        def vnet_hdr(self) -> bool: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_group(self) -> int: ...
    def get_mode(self) -> str: ...
    def get_multi_queue(self) -> bool: ...
    def get_no_pi(self) -> bool: ...
    def get_owner(self) -> int: ...
    def get_vnet_hdr(self) -> bool: ...

class DeviceTunClass(_gi.Struct): ...

class DeviceVeth(DeviceEthernet):
    """
    :Constructors:

    ::

        DeviceVeth(**properties)

    Object NMDeviceVeth

    Properties from NMDeviceVeth:
      peer -> NMDevice:


    Properties from NMDeviceEthernet:
      perm-hw-address -> gchararray:

      speed -> guint:

      carrier -> gboolean:

      s390-subchannels -> GStrv:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(DeviceEthernet.Props):
        @property
        def peer(self) -> Device: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_peer(self) -> Device: ...

class DeviceVethClass(_gi.Struct): ...

class DeviceVlan(Device):
    """
    :Constructors:

    ::

        DeviceVlan(**properties)

    Object NMDeviceVlan

    Properties from NMDeviceVlan:
      carrier -> gboolean:

      parent -> NMDevice:

      vlan-id -> guint:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def carrier(self) -> bool: ...
        @property
        def parent(self) -> Device: ...
        @property
        def vlan_id(self) -> int: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_carrier(self) -> bool: ...
    def get_parent(self) -> Device: ...
    def get_vlan_id(self) -> int: ...

class DeviceVlanClass(_gi.Struct): ...

class DeviceVrf(Device):
    """
    :Constructors:

    ::

        DeviceVrf(**properties)

    Object NMDeviceVrf

    Properties from NMDeviceVrf:
      table -> guint:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def table(self) -> int: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_table(self) -> int: ...

class DeviceVrfClass(_gi.Struct): ...

class DeviceVxlan(Device):
    """
    :Constructors:

    ::

        DeviceVxlan(**properties)

    Object NMDeviceVxlan

    Properties from NMDeviceVxlan:
      carrier -> gboolean:

      parent -> NMDevice:

      id -> guint:

      group -> gchararray:

      local -> gchararray:

      tos -> guchar:

      ttl -> guchar:

      limit -> guint:

      learning -> gboolean:

      ageing -> guint:

      dst-port -> guint:

      src-port-min -> guint:

      src-port-max -> guint:

      proxy -> gboolean:

      rsc -> gboolean:

      l2miss -> gboolean:

      l3miss -> gboolean:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def ageing(self) -> int: ...
        @property
        def carrier(self) -> bool: ...
        @property
        def dst_port(self) -> int: ...
        @property
        def group(self) -> str: ...
        @property
        def id(self) -> int: ...
        @property
        def l2miss(self) -> bool: ...
        @property
        def l3miss(self) -> bool: ...
        @property
        def learning(self) -> bool: ...
        @property
        def limit(self) -> int: ...
        @property
        def local(self) -> str: ...
        @property
        def parent(self) -> Device: ...
        @property
        def proxy(self) -> bool: ...
        @property
        def rsc(self) -> bool: ...
        @property
        def src_port_max(self) -> int: ...
        @property
        def src_port_min(self) -> int: ...
        @property
        def tos(self) -> int: ...
        @property
        def ttl(self) -> int: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_ageing(self) -> int: ...
    def get_carrier(self) -> bool: ...
    def get_dst_port(self) -> int: ...
    def get_group(self) -> str: ...
    def get_id(self) -> int: ...
    def get_l2miss(self) -> bool: ...
    def get_l3miss(self) -> bool: ...
    def get_learning(self) -> bool: ...
    def get_limit(self) -> int: ...
    def get_local(self) -> str: ...
    def get_parent(self) -> Device: ...
    def get_proxy(self) -> bool: ...
    def get_rsc(self) -> bool: ...
    def get_src_port_max(self) -> int: ...
    def get_src_port_min(self) -> int: ...
    def get_tos(self) -> int: ...
    def get_ttl(self) -> int: ...

class DeviceVxlanClass(_gi.Struct): ...

class DeviceWifi(Device):
    """
    :Constructors:

    ::

        DeviceWifi(**properties)

    Object NMDeviceWifi

    Signals from NMDeviceWifi:
      access-point-added (GObject)
      access-point-removed (GObject)

    Properties from NMDeviceWifi:
      perm-hw-address -> gchararray:

      mode -> NM80211Mode:

      bitrate -> guint:

      access-points -> GPtrArray:

      active-access-point -> NMAccessPoint:

      wireless-capabilities -> NMDeviceWifiCapabilities:

      last-scan -> gint64:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def access_points(self) -> list[AccessPoint]: ...
        @property
        def active_access_point(self) -> AccessPoint: ...
        @property
        def bitrate(self) -> int: ...
        @property
        def last_scan(self) -> int: ...
        @property
        def mode(self) -> GObject.GEnum: ...
        @property
        def perm_hw_address(self) -> str | None: ...
        @property
        def wireless_capabilities(self) -> DeviceWifiCapabilities: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_access_point_by_path(self, path: str) -> AccessPoint: ...
    def get_access_points(self) -> list[AccessPoint]: ...
    def get_active_access_point(self) -> AccessPoint: ...
    def get_bitrate(self) -> int: ...
    def get_capabilities(self) -> DeviceWifiCapabilities: ...
    def get_last_scan(self) -> int: ...
    def get_mode(self) -> GObject.GEnum: ...
    def get_permanent_hw_address(self) -> str: ...
    def request_scan(self, cancellable: Gio.Cancellable | None = None) -> bool: ...
    @overload
    def request_scan_async(
        self, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def request_scan_async(
        self,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[DeviceWifi, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def request_scan_async(
        self,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[DeviceWifi] | None,
    ) -> None: ...
    def request_scan_finish(self, result: Gio.AsyncResult) -> bool: ...
    def request_scan_options(
        self, options: GLib.Variant, cancellable: Gio.Cancellable | None = None
    ) -> bool: ...
    def request_scan_options_async(
        self,
        options: GLib.Variant,
        cancellable: Gio.Cancellable | None = None,
        callback: Gio._AsyncReadyVarArgsCallback[DeviceWifi, Unpack[_DataTs]]
        | None = None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...

class DeviceWifiClass(_gi.Struct): ...

class DeviceWifiP2P(Device):
    """
    :Constructors:

    ::

        DeviceWifiP2P(**properties)

    Object NMDeviceWifiP2P

    Signals from NMDeviceWifiP2P:
      peer-added (GObject)
      peer-removed (GObject)

    Properties from NMDeviceWifiP2P:
      peers -> GPtrArray:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def peers(self) -> list[WifiP2PPeer]: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_peer_by_path(self, path: str) -> WifiP2PPeer: ...
    def get_peers(self) -> list[WifiP2PPeer]: ...
    @overload
    def start_find(
        self,
        options: GLib.Variant | None = None,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[bool]: ...
    @overload
    def start_find(
        self,
        options: GLib.Variant | None,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[DeviceWifiP2P, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def start_find(
        self,
        options: GLib.Variant | None = None,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[DeviceWifiP2P] | None,
    ) -> None: ...
    def start_find_finish(self, result: Gio.AsyncResult) -> bool: ...
    @overload
    def stop_find(
        self, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def stop_find(
        self,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[DeviceWifiP2P, Unpack[_DataTs]] | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def stop_find(
        self,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[DeviceWifiP2P] | None,
    ) -> None: ...
    def stop_find_finish(self, result: Gio.AsyncResult) -> bool: ...

class DeviceWifiP2PClass(_gi.Struct): ...

class DeviceWimax(Device):
    """
    :Constructors:

    ::

        DeviceWimax(**properties)

    Object NMDeviceWimax

    Signals from NMDeviceWimax:
      nsp-added (GObject)
      nsp-removed (GObject)

    Properties from NMDeviceWimax:
      hw-address -> gchararray:

      active-nsp -> NMWimaxNsp:

      center-frequency -> guint:

      rssi -> gint:

      cinr -> gint:

      tx-power -> gint:

      bsid -> gchararray:

      nsps -> GPtrArray:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def active_nsp(self) -> WimaxNsp: ...
        @property
        def bsid(self) -> str: ...
        @property
        def center_frequency(self) -> int: ...
        @property
        def cinr(self) -> int: ...
        @property
        def hw_address(self) -> str: ...
        @property
        def nsps(self) -> list[WimaxNsp]: ...
        @property
        def rssi(self) -> int: ...
        @property
        def tx_power(self) -> int: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_active_nsp(self) -> WimaxNsp: ...
    def get_bsid(self) -> str: ...
    def get_center_frequency(self) -> int: ...
    def get_cinr(self) -> int: ...
    def get_hw_address(self) -> str: ...
    def get_nsp_by_path(self, path: str) -> WimaxNsp: ...
    def get_nsps(self) -> list[WimaxNsp]: ...
    def get_rssi(self) -> int: ...
    def get_tx_power(self) -> int: ...

class DeviceWimaxClass(_gi.Struct): ...

class DeviceWireGuard(Device):
    """
    :Constructors:

    ::

        DeviceWireGuard(**properties)

    Object NMDeviceWireGuard

    Properties from NMDeviceWireGuard:
      public-key -> GBytes:

      listen-port -> guint:

      fwmark -> guint:


    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Device.Props):
        @property
        def fwmark(self) -> int: ...
        @property
        def listen_port(self) -> int: ...
        @property
        def public_key(self) -> GLib.Bytes: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, autoconnect: bool = ...) -> None: ...
    def get_fwmark(self) -> int: ...
    def get_listen_port(self) -> int: ...
    def get_public_key(self) -> GLib.Bytes: ...

class DeviceWireGuardClass(_gi.Struct): ...

class DeviceWpan(Device):
    """
    :Constructors:

    ::

        DeviceWpan(**properties)

    Object NMDeviceWpan

    Signals from NMDevice:
      state-changed (guint, guint, guint)

    Properties from NMDevice:
      interface -> gchararray:

      udi -> gchararray:

      path -> gchararray:

      driver -> gchararray:

      driver-version -> gchararray:

      firmware-version -> gchararray:

      capabilities -> NMDeviceCapabilities:

      real -> gboolean:

      managed -> gboolean:

      autoconnect -> gboolean:

      firmware-missing -> gboolean:

      nm-plugin-missing -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      ip6-config -> NMIPConfig:

      state -> NMDeviceState:

      state-reason -> guint:

      product -> gchararray:

      vendor -> gchararray:

      dhcp6-config -> NMDhcpConfig:

      ip-interface -> gchararray:

      device-type -> NMDeviceType:

      active-connection -> NMActiveConnection:

      available-connections -> GPtrArray:

      physical-port-id -> gchararray:

      mtu -> guint:

      metered -> guint:

      lldp-neighbors -> GPtrArray:

      ip4-connectivity -> NMConnectivityState:

      ip6-connectivity -> NMConnectivityState:

      interface-flags -> guint:

      hw-address -> gchararray:

      ports -> GPtrArray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    def __init__(self, *, autoconnect: bool = ...) -> None: ...

class DeviceWpanClass(_gi.Struct): ...

class DhcpConfig(Object):
    """
    :Constructors:

    ::

        DhcpConfig(**properties)

    Object NMDhcpConfig

    Properties from NMDhcpConfig:
      family -> gint:

      options -> GHashTable:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Object.Props):
        @property
        def family(self) -> int: ...
        @property
        def options(self) -> dict[str, str]: ...

    @property
    def props(self) -> Props: ...
    def get_family(self) -> int: ...
    def get_one_option(self, option: str) -> str: ...
    def get_options(self) -> dict[str, str]: ...

class DhcpConfigClass(_gi.Struct): ...

class DnsEntry(GObject.GBoxed):
    def get_domains(self) -> list[str]: ...
    def get_interface(self) -> str: ...
    def get_nameservers(self) -> list[str]: ...
    def get_priority(self) -> int: ...
    def get_vpn(self) -> bool: ...
    def unref(self) -> None: ...

class IPAddress(GObject.GBoxed):
    """
    :Constructors:

    ::

        new(family:int, addr:str, prefix:int) -> NM.IPAddress
        new_binary(family:int, addr=None, prefix:int) -> NM.IPAddress
    """
    def __init__(self, family: int, addr: str, prefix: int) -> None: ...
    def cmp_full(self, b: IPAddress, cmp_flags: _IPAddressCmpFlagsValueType) -> int: ...
    def dup(self) -> IPAddress: ...
    def equal(self, other: IPAddress) -> bool: ...
    def get_address(self) -> str: ...
    def get_attribute(self, name: str) -> GLib.Variant: ...
    def get_attribute_names(self) -> list[str]: ...
    def get_family(self) -> int: ...
    def get_prefix(self) -> int: ...
    @classmethod
    def new(cls, family: int, addr: str, prefix: int) -> IPAddress: ...
    @classmethod
    def new_binary(
        cls, family: int, addr: int | Any | None, prefix: int
    ) -> IPAddress: ...
    def ref(self) -> None: ...
    def set_address(self, addr: str) -> None: ...
    def set_attribute(self, name: str, value: GLib.Variant | None = None) -> None: ...
    def set_prefix(self, prefix: int) -> None: ...
    def unref(self) -> None: ...

class IPConfig(Object):
    """
    :Constructors:

    ::

        IPConfig(**properties)

    Object NMIPConfig

    Properties from NMIPConfig:
      family -> gint:

      gateway -> gchararray:

      addresses -> GPtrArray:

      routes -> GPtrArray:

      nameservers -> GStrv:

      domains -> GStrv:

      searches -> GStrv:

      wins-servers -> GStrv:

      clat-address -> gchararray:

      clat-pref64 -> gchararray:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Object.Props):
        @property
        def addresses(self) -> list[int]: ...
        @property
        def clat_address(self) -> str: ...
        @property
        def clat_pref64(self) -> str: ...
        @property
        def domains(self) -> list[str]: ...
        @property
        def family(self) -> int: ...
        @property
        def gateway(self) -> str: ...
        @property
        def nameservers(self) -> list[str]: ...
        @property
        def routes(self) -> list[IPRoute]: ...
        @property
        def searches(self) -> list[str]: ...
        @property
        def wins_servers(self) -> list[str]: ...

    @property
    def props(self) -> Props: ...
    def get_addresses(self) -> list[IPAddress]: ...
    def get_clat_address(self) -> str: ...
    def get_clat_pref64(self) -> str: ...
    def get_domains(self) -> list[str]: ...
    def get_family(self) -> int: ...
    def get_gateway(self) -> str: ...
    def get_nameservers(self) -> list[str]: ...
    def get_routes(self) -> list[IPRoute]: ...
    def get_searches(self) -> list[str]: ...
    def get_wins_servers(self) -> list[str]: ...

class IPConfigClass(_gi.Struct): ...

class IPRoute(GObject.GBoxed):
    """
    :Constructors:

    ::

        new(family:int, dest:str, prefix:int, next_hop:str=None, metric:int) -> NM.IPRoute
        new_binary(family:int, dest=None, prefix:int, next_hop=None, metric:int) -> NM.IPRoute
    """
    def __init__(
        self, family: int, dest: str, prefix: int, next_hop: str | None, metric: int
    ) -> None: ...
    @staticmethod
    def attribute_validate(
        name: str, value: GLib.Variant, family: int
    ) -> tuple[bool, bool]: ...
    def dup(self) -> IPRoute: ...
    def equal(self, other: IPRoute) -> bool: ...
    def equal_full(self, other: IPRoute, cmp_flags: int) -> bool: ...
    def get_attribute(self, name: str) -> GLib.Variant: ...
    def get_attribute_names(self) -> list[str]: ...
    def get_dest(self) -> str: ...
    def get_family(self) -> int: ...
    def get_metric(self) -> int: ...
    def get_next_hop(self) -> str: ...
    def get_prefix(self) -> int: ...
    @staticmethod
    def get_variant_attribute_spec() -> VariantAttributeSpec: ...
    @classmethod
    def new(
        cls, family: int, dest: str, prefix: int, next_hop: str | None, metric: int
    ) -> IPRoute: ...
    @classmethod
    def new_binary(
        cls,
        family: int,
        dest: int | Any | None,
        prefix: int,
        next_hop: int | Any | None,
        metric: int,
    ) -> IPRoute: ...
    def ref(self) -> None: ...
    def set_attribute(self, name: str, value: GLib.Variant | None = None) -> None: ...
    def set_dest(self, dest: str) -> None: ...
    def set_metric(self, metric: int) -> None: ...
    def set_next_hop(self, next_hop: str | None = None) -> None: ...
    def set_prefix(self, prefix: int) -> None: ...
    def unref(self) -> None: ...

class IPRoutingRule(GObject.GBoxed):
    """
    :Constructors:

    ::

        new(addr_family:int) -> NM.IPRoutingRule
    """
    def __init__(self, addr_family: int) -> None: ...
    def cmp(self, other: IPRoutingRule | None = None) -> int: ...
    @staticmethod
    def from_string(
        str: str,
        to_string_flags: _IPRoutingRuleAsStringFlagsValueType,
        extra_args: Mapping[int | Any | None, int | Any | None] | None = None,
    ) -> IPRoutingRule: ...
    def get_action(self) -> int: ...
    def get_addr_family(self) -> int: ...
    def get_destination_port_end(self) -> int: ...
    def get_destination_port_start(self) -> int: ...
    def get_from(self) -> str: ...
    def get_from_len(self) -> int: ...
    def get_fwmark(self) -> int: ...
    def get_fwmask(self) -> int: ...
    def get_iifname(self) -> str: ...
    def get_invert(self) -> bool: ...
    def get_ipproto(self) -> int: ...
    def get_oifname(self) -> str: ...
    def get_priority(self) -> int: ...
    def get_source_port_end(self) -> int: ...
    def get_source_port_start(self) -> int: ...
    def get_suppress_prefixlength(self) -> int: ...
    def get_table(self) -> int: ...
    def get_to(self) -> str: ...
    def get_to_len(self) -> int: ...
    def get_tos(self) -> int: ...
    def get_uid_range(self) -> tuple[bool, int, int]: ...
    def is_sealed(self) -> bool: ...
    @classmethod
    def new(cls, addr_family: int) -> IPRoutingRule: ...
    def new_clone(self) -> IPRoutingRule: ...
    def ref(self) -> IPRoutingRule: ...
    def seal(self) -> None: ...
    def set_action(self, action: int) -> None: ...
    def set_destination_port(self, start: int, end: int) -> None: ...
    def set_from(self, from_: str | None, len: int) -> None: ...
    def set_fwmark(self, fwmark: int, fwmask: int) -> None: ...
    def set_iifname(self, iifname: str | None = None) -> None: ...
    def set_invert(self, invert: bool) -> None: ...
    def set_ipproto(self, ipproto: int) -> None: ...
    def set_oifname(self, oifname: str | None = None) -> None: ...
    def set_priority(self, priority: int) -> None: ...
    def set_source_port(self, start: int, end: int) -> None: ...
    def set_suppress_prefixlength(self, suppress_prefixlength: int) -> None: ...
    def set_table(self, table: int) -> None: ...
    def set_to(self, to: str | None, len: int) -> None: ...
    def set_tos(self, tos: int) -> None: ...
    def set_uid_range(self, uid_range_start: int, uid_range_end: int) -> None: ...
    def to_string(
        self,
        to_string_flags: _IPRoutingRuleAsStringFlagsValueType,
        extra_args: Mapping[int | Any | None, int | Any | None] | None = None,
    ) -> str: ...
    def unref(self) -> None: ...
    def validate(self) -> bool: ...

class KeyfileHandlerData(_gi.Struct):
    def fail_with_error(self, src: GLib.Error) -> None: ...
    def get_context(
        self,
    ) -> tuple[str | None, str | None, Setting | None, str | None]: ...
    def warn_get(self) -> tuple[str, KeyfileWarnSeverity]: ...

class LldpNeighbor(GObject.GBoxed):
    """
    :Constructors:

    ::

        new() -> NM.LldpNeighbor
    """
    def __init__(self) -> None: ...
    def get_attr_names(self) -> list[str]: ...
    def get_attr_string_value(self, name: str) -> tuple[bool, str | None]: ...
    def get_attr_type(self, name: str) -> GLib.VariantType: ...
    def get_attr_uint_value(self, name: str) -> tuple[bool, int]: ...
    def get_attr_value(self, name: str) -> GLib.Variant: ...
    @classmethod
    def new(cls) -> LldpNeighbor: ...
    def ref(self) -> None: ...
    def unref(self) -> None: ...

class Object(GObject.Object):
    """
    :Constructors:

    ::

        Object(**properties)

    Object NMObject

    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(GObject.Object.Props):
        @property
        def client(self) -> Client: ...
        @property
        def path(self) -> str: ...

    @property
    def props(self) -> Props: ...
    def get_client(self) -> Client: ...
    def get_path(self) -> str: ...

class ObjectClass(_gi.Struct): ...

class Range(GObject.GBoxed):
    """
    :Constructors:

    ::

        new(start:int, end:int) -> NM.Range
    """
    def __init__(self, start: int, end: int) -> None: ...
    def cmp(self, b: Range) -> int: ...
    @staticmethod
    def from_str(str: str) -> Range: ...
    def get_range(self) -> tuple[bool, int, int]: ...
    @classmethod
    def new(cls, start: int, end: int) -> Range: ...
    def ref(self) -> Range: ...
    def to_str(self) -> str: ...
    def unref(self) -> None: ...

class RemoteConnection(Object, Connection):
    """
    :Constructors:

    ::

        RemoteConnection(**properties)

    Object NMRemoteConnection

    Properties from NMRemoteConnection:
      unsaved -> gboolean:

      flags -> guint:

      filename -> gchararray:

      version-id -> guint64:

      visible -> gboolean:


    Signals from NMConnection:
      secrets-updated (gchararray)
      secrets-cleared ()
      changed ()

    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Object.Props):
        @property
        def filename(self) -> str: ...
        @property
        def flags(self) -> int: ...
        @property
        def unsaved(self) -> bool: ...
        @property
        def version_id(self) -> int: ...
        @property
        def visible(self) -> bool: ...

    @property
    def props(self) -> Props: ...
    def commit_changes(
        self, save_to_disk: bool, cancellable: Gio.Cancellable | None = None
    ) -> bool: ...
    @overload
    def commit_changes_async(
        self, save_to_disk: bool, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def commit_changes_async(
        self,
        save_to_disk: bool,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[RemoteConnection, Unpack[_DataTs]]
        | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def commit_changes_async(
        self,
        save_to_disk: bool,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[RemoteConnection] | None,
    ) -> None: ...
    def commit_changes_finish(self, result: Gio.AsyncResult) -> bool: ...
    def delete(self, cancellable: Gio.Cancellable | None = None) -> bool: ...
    @overload
    def delete_async(
        self, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def delete_async(
        self,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[RemoteConnection, Unpack[_DataTs]]
        | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def delete_async(
        self,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[RemoteConnection] | None,
    ) -> None: ...
    def delete_finish(self, result: Gio.AsyncResult) -> bool: ...
    def get_filename(self) -> str: ...
    def get_flags(self) -> SettingsConnectionFlags: ...
    def get_secrets(
        self, setting_name: str, cancellable: Gio.Cancellable | None = None
    ) -> GLib.Variant: ...
    @overload
    def get_secrets_async(
        self, setting_name: str, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[GLib.Variant]: ...
    @overload
    def get_secrets_async(
        self,
        setting_name: str,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[RemoteConnection, Unpack[_DataTs]]
        | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def get_secrets_async(
        self,
        setting_name: str,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[RemoteConnection] | None,
    ) -> None: ...
    def get_secrets_finish(self, result: Gio.AsyncResult) -> GLib.Variant: ...
    def get_unsaved(self) -> bool: ...
    def get_version_id(self) -> int: ...
    def get_visible(self) -> bool: ...
    def save(self, cancellable: Gio.Cancellable | None = None) -> bool: ...
    @overload
    def save_async(
        self, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def save_async(
        self,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[RemoteConnection, Unpack[_DataTs]]
        | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def save_async(
        self,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[RemoteConnection] | None,
    ) -> None: ...
    def save_finish(self, result: Gio.AsyncResult) -> bool: ...
    @overload
    def update2(
        self,
        settings: GLib.Variant | None,
        flags: _SettingsUpdate2FlagsValueType,
        args: GLib.Variant | None = None,
        cancellable: Gio.Cancellable | None = None,
    ) -> _gi.Async[GLib.Variant]: ...
    @overload
    def update2(
        self,
        settings: GLib.Variant | None,
        flags: _SettingsUpdate2FlagsValueType,
        args: GLib.Variant | None,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[RemoteConnection, Unpack[_DataTs]]
        | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def update2(
        self,
        settings: GLib.Variant | None,
        flags: _SettingsUpdate2FlagsValueType,
        args: GLib.Variant | None = None,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[RemoteConnection] | None,
    ) -> None: ...
    def update2_finish(self, result: Gio.AsyncResult) -> GLib.Variant: ...

class RemoteConnectionClass(_gi.Struct): ...

class SecretAgentOld(GObject.Object, Gio.AsyncInitable, Gio.Initable):
    """
    :Constructors:

    ::

        SecretAgentOld(**properties)

    Object NMSecretAgentOld

    Properties from NMSecretAgentOld:
      identifier -> gchararray:

      auto-register -> gboolean:

      registered -> gboolean:

      capabilities -> NMSecretAgentCapabilities:

      dbus-connection -> GDBusConnection:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(GObject.Object.Props):
        auto_register: bool
        @property
        def capabilities(self) -> SecretAgentCapabilities: ...
        @capabilities.setter
        def capabilities(self, value: _SecretAgentCapabilitiesValueType) -> None: ...
        @property
        def dbus_connection(self) -> Gio.DBusConnection: ...
        @property
        def identifier(self) -> str | None: ...
        @property
        def registered(self) -> bool: ...

    @property
    def props(self) -> Props: ...
    @property
    def parent(self) -> GObject.Object: ...
    def __init__(
        self,
        *,
        auto_register: bool = ...,
        capabilities: _SecretAgentCapabilitiesValueType = ...,
        dbus_connection: Gio.DBusConnection | None = ...,
        identifier: str | None = ...,
    ) -> None: ...
    def delete_secrets(
        self,
        connection: Connection,
        callback: Callable[
            [SecretAgentOld, Connection, GLib.Error | None, Unpack[_DataTs]], None
        ],
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    def destroy(self) -> None: ...
    def do_cancel_get_secrets(
        self, connection_path: str, setting_name: str, /
    ) -> None: ...
    def do_delete_secrets(
        self,
        connection: Connection,
        connection_path: str,
        callback: Callable[
            [SecretAgentOld, Connection, GLib.Error | None, Any | None], None
        ],
        user_data: int | Any | None,
        /,
    ) -> None: ...
    def do_get_secrets(
        self,
        connection: Connection,
        connection_path: str,
        setting_name: str,
        hints: Sequence[str],
        flags: _SecretAgentGetSecretsFlagsValueType,
        callback: Callable[
            [
                SecretAgentOld,
                Connection,
                GLib.Variant | None,
                GLib.Error | None,
                Any | None,
            ],
            None,
        ],
        user_data: int | Any | None,
        /,
    ) -> None: ...
    def do_save_secrets(
        self,
        connection: Connection,
        connection_path: str,
        callback: Callable[
            [SecretAgentOld, Connection, GLib.Error | None, Any | None], None
        ],
        user_data: int | Any | None,
        /,
    ) -> None: ...
    def enable(self, enable: bool) -> None: ...
    def get_context_busy_watcher(self) -> GObject.Object: ...
    def get_dbus_connection(self) -> Gio.DBusConnection: ...
    def get_dbus_name_owner(self) -> str: ...
    def get_main_context(self) -> GLib.MainContext: ...
    def get_registered(self) -> bool: ...
    def get_secrets(
        self,
        connection: Connection,
        setting_name: str,
        hints: Sequence[str],
        flags: _SecretAgentGetSecretsFlagsValueType,
        callback: Callable[
            [
                SecretAgentOld,
                Connection,
                GLib.Variant | None,
                GLib.Error | None,
                Unpack[_DataTs],
            ],
            None,
        ],
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    def register(self, cancellable: Gio.Cancellable | None = None) -> bool: ...
    @overload
    def register_async(
        self, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def register_async(
        self,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[SecretAgentOld, Unpack[_DataTs]]
        | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def register_async(
        self,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[SecretAgentOld] | None,
    ) -> None: ...
    def register_finish(self, result: Gio.AsyncResult) -> bool: ...
    def save_secrets(
        self,
        connection: Connection,
        callback: Callable[
            [SecretAgentOld, Connection, GLib.Error | None, Unpack[_DataTs]], None
        ],
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    def unregister(self, cancellable: Gio.Cancellable | None = None) -> bool: ...
    @overload
    def unregister_async(
        self, cancellable: Gio.Cancellable | None = None
    ) -> _gi.Async[bool]: ...
    @overload
    def unregister_async(
        self,
        cancellable: Gio.Cancellable | None,
        callback: Gio._AsyncReadyVarArgsCallback[SecretAgentOld, Unpack[_DataTs]]
        | None,
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    @overload
    def unregister_async(
        self,
        cancellable: Gio.Cancellable | None = None,
        *,
        callback: Gio._AsyncReadyVarArgsCallback[SecretAgentOld] | None,
    ) -> None: ...
    def unregister_finish(self, result: Gio.AsyncResult) -> bool: ...

class SecretAgentOldClass(_gi.Struct):
    """
    :Constructors:

    ::

        SecretAgentOldClass()
    """
    @property
    def parent(self) -> GObject.ObjectClass: ...
    @property
    def get_secrets(
        self,
    ) -> Callable[
        [
            SecretAgentOld,
            Connection,
            str,
            str,
            Sequence[str],
            _SecretAgentGetSecretsFlagsValueType,
            Callable[
                [
                    SecretAgentOld,
                    Connection,
                    GLib.Variant | None,
                    GLib.Error | None,
                    Any | None,
                ],
                None,
            ],
            Any | None,
        ],
        None,
    ]: ...
    @property
    def cancel_get_secrets(self) -> Callable[[SecretAgentOld, str, str], None]: ...
    @property
    def save_secrets(
        self,
    ) -> Callable[
        [
            SecretAgentOld,
            Connection,
            str,
            Callable[[SecretAgentOld, Connection, GLib.Error | None, Any | None], None],
            Any | None,
        ],
        None,
    ]: ...
    @property
    def delete_secrets(
        self,
    ) -> Callable[
        [
            SecretAgentOld,
            Connection,
            str,
            Callable[[SecretAgentOld, Connection, GLib.Error | None, Any | None], None],
            Any | None,
        ],
        None,
    ]: ...
    @property
    def padding(self) -> list[int]: ...

class Setting(GObject.Object):
    """
    :Constructors:

    ::

        Setting(**properties)

    Object NMSetting

    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(GObject.Object.Props):
        @property
        def name(self) -> str: ...

    @property
    def props(self) -> Props: ...
    def compare(self, b: Setting, flags: _SettingCompareFlagsValueType) -> bool: ...
    def diff(
        self,
        b: Setting,
        flags: _SettingCompareFlagsValueType,
        invert_results: bool,
        results: Mapping[str, int],
    ) -> tuple[bool, dict[str, int]]: ...
    def duplicate(self) -> Setting: ...
    def enumerate_values(
        self,
        func: Callable[[Setting, str, Any, GObject.ParamFlags, Unpack[_DataTs]], None],
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    def get_dbus_property_type(self, property_name: str) -> GLib.VariantType: ...
    @staticmethod
    def get_enum_property_type(
        setting_type: type[Any], property_name: str
    ) -> type[Any]: ...
    def get_name(self) -> str: ...
    def get_secret_flags(
        self, secret_name: str, out_flags: _SettingSecretFlagsValueType
    ) -> bool: ...
    @staticmethod
    def lookup_type(name: str) -> type[Any]: ...
    def option_clear_by_name(
        self, predicate: Callable[[str], bool] | None = None
    ) -> None: ...
    def option_get(self, opt_name: str) -> GLib.Variant: ...
    def option_get_all_names(self) -> list[str]: ...
    def option_get_boolean(self, opt_name: str) -> tuple[bool, bool | None]: ...
    def option_get_uint32(self, opt_name: str) -> tuple[bool, int | None]: ...
    def option_set(
        self, opt_name: str, variant: GLib.Variant | None = None
    ) -> None: ...
    def option_set_boolean(self, opt_name: str, value: bool) -> None: ...
    def option_set_uint32(self, opt_name: str, value: int) -> None: ...
    def set_secret_flags(
        self, secret_name: str, flags: _SettingSecretFlagsValueType
    ) -> bool: ...
    def to_string(self) -> str: ...
    def verify(self, connection: Connection | None = None) -> bool: ...
    def verify_secrets(self, connection: Connection | None = None) -> bool: ...

class Setting6Lowpan(Setting):
    """
    :Constructors:

    ::

        Setting6Lowpan(**properties)
        new() -> NM.Setting

    Object NMSetting6Lowpan

    Properties from NMSetting6Lowpan:
      parent -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def parent(self) -> str: ...
        @parent.setter
        def parent(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, parent: str | None = ...) -> None: ...
    def get_parent(self) -> str: ...
    @classmethod
    def new(cls) -> Setting6Lowpan: ...

class Setting6LowpanClass(_gi.Struct): ...

class Setting8021x(Setting):
    """
    :Constructors:

    ::

        Setting8021x(**properties)
        new() -> NM.Setting

    Object NMSetting8021x

    Properties from NMSetting8021x:
      eap -> GStrv:

      identity -> gchararray:

      anonymous-identity -> gchararray:

      pac-file -> gchararray:

      ca-cert -> GBytes:

      ca-cert-password -> gchararray:

      ca-cert-password-flags -> NMSettingSecretFlags:

      ca-path -> gchararray:

      subject-match -> gchararray:

      altsubject-matches -> GStrv:

      domain-suffix-match -> gchararray:

      domain-match -> gchararray:

      client-cert -> GBytes:

      client-cert-password -> gchararray:

      client-cert-password-flags -> NMSettingSecretFlags:

      phase1-peapver -> gchararray:

      phase1-peaplabel -> gchararray:

      phase1-fast-provisioning -> gchararray:

      phase1-auth-flags -> guint:

      phase2-auth -> gchararray:

      phase2-autheap -> gchararray:

      phase2-ca-cert -> GBytes:

      phase2-ca-cert-password -> gchararray:

      phase2-ca-cert-password-flags -> NMSettingSecretFlags:

      phase2-ca-path -> gchararray:

      phase2-subject-match -> gchararray:

      phase2-altsubject-matches -> GStrv:

      phase2-domain-suffix-match -> gchararray:

      phase2-domain-match -> gchararray:

      phase2-client-cert -> GBytes:

      phase2-client-cert-password -> gchararray:

      phase2-client-cert-password-flags -> NMSettingSecretFlags:

      password -> gchararray:

      password-flags -> NMSettingSecretFlags:

      password-raw -> GBytes:

      password-raw-flags -> NMSettingSecretFlags:

      private-key -> GBytes:

      private-key-password -> gchararray:

      private-key-password-flags -> NMSettingSecretFlags:

      phase2-private-key -> GBytes:

      phase2-private-key-password -> gchararray:

      phase2-private-key-password-flags -> NMSettingSecretFlags:

      pin -> gchararray:

      pin-flags -> NMSettingSecretFlags:

      system-ca-certs -> gboolean:

      optional -> gboolean:

      auth-timeout -> gint:

      openssl-ciphers -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def altsubject_matches(self) -> list[str]: ...
        @altsubject_matches.setter
        def altsubject_matches(self, value: Sequence[str] | None) -> None: ...
        @property
        def anonymous_identity(self) -> str: ...
        @anonymous_identity.setter
        def anonymous_identity(self, value: str | None) -> None: ...
        auth_timeout: int
        @property
        def ca_cert(self) -> GLib.Bytes | None: ...
        @ca_cert.setter
        def ca_cert(self, value: GLib.Bytes) -> None: ...
        @property
        def ca_cert_password(self) -> str: ...
        @ca_cert_password.setter
        def ca_cert_password(self, value: str | None) -> None: ...
        @property
        def ca_cert_password_flags(self) -> SettingSecretFlags: ...
        @ca_cert_password_flags.setter
        def ca_cert_password_flags(
            self, value: _SettingSecretFlagsValueType
        ) -> None: ...
        @property
        def ca_path(self) -> str: ...
        @ca_path.setter
        def ca_path(self, value: str | None) -> None: ...
        @property
        def client_cert(self) -> GLib.Bytes | None: ...
        @client_cert.setter
        def client_cert(self, value: GLib.Bytes) -> None: ...
        @property
        def client_cert_password(self) -> str: ...
        @client_cert_password.setter
        def client_cert_password(self, value: str | None) -> None: ...
        @property
        def client_cert_password_flags(self) -> SettingSecretFlags: ...
        @client_cert_password_flags.setter
        def client_cert_password_flags(
            self, value: _SettingSecretFlagsValueType
        ) -> None: ...
        @property
        def domain_match(self) -> str: ...
        @domain_match.setter
        def domain_match(self, value: str | None) -> None: ...
        @property
        def domain_suffix_match(self) -> str: ...
        @domain_suffix_match.setter
        def domain_suffix_match(self, value: str | None) -> None: ...
        @property
        def eap(self) -> list[str]: ...
        @eap.setter
        def eap(self, value: Sequence[str] | None) -> None: ...
        @property
        def identity(self) -> str: ...
        @identity.setter
        def identity(self, value: str | None) -> None: ...
        @property
        def openssl_ciphers(self) -> str: ...
        @openssl_ciphers.setter
        def openssl_ciphers(self, value: str | None) -> None: ...
        optional: bool
        @property
        def pac_file(self) -> str: ...
        @pac_file.setter
        def pac_file(self, value: str | None) -> None: ...
        @property
        def password(self) -> str: ...
        @password.setter
        def password(self, value: str | None) -> None: ...
        @property
        def password_flags(self) -> SettingSecretFlags: ...
        @password_flags.setter
        def password_flags(self, value: _SettingSecretFlagsValueType) -> None: ...
        @property
        def password_raw(self) -> GLib.Bytes: ...
        @password_raw.setter
        def password_raw(self, value: GLib.Bytes | None) -> None: ...
        @property
        def password_raw_flags(self) -> SettingSecretFlags: ...
        @password_raw_flags.setter
        def password_raw_flags(self, value: _SettingSecretFlagsValueType) -> None: ...
        phase1_auth_flags: int
        @property
        def phase1_fast_provisioning(self) -> str: ...
        @phase1_fast_provisioning.setter
        def phase1_fast_provisioning(self, value: str | None) -> None: ...
        @property
        def phase1_peaplabel(self) -> str: ...
        @phase1_peaplabel.setter
        def phase1_peaplabel(self, value: str | None) -> None: ...
        @property
        def phase1_peapver(self) -> str: ...
        @phase1_peapver.setter
        def phase1_peapver(self, value: str | None) -> None: ...
        @property
        def phase2_altsubject_matches(self) -> list[str]: ...
        @phase2_altsubject_matches.setter
        def phase2_altsubject_matches(self, value: Sequence[str] | None) -> None: ...
        @property
        def phase2_auth(self) -> str: ...
        @phase2_auth.setter
        def phase2_auth(self, value: str | None) -> None: ...
        @property
        def phase2_autheap(self) -> str: ...
        @phase2_autheap.setter
        def phase2_autheap(self, value: str | None) -> None: ...
        @property
        def phase2_ca_cert(self) -> GLib.Bytes | None: ...
        @phase2_ca_cert.setter
        def phase2_ca_cert(self, value: GLib.Bytes) -> None: ...
        @property
        def phase2_ca_cert_password(self) -> str: ...
        @phase2_ca_cert_password.setter
        def phase2_ca_cert_password(self, value: str | None) -> None: ...
        @property
        def phase2_ca_cert_password_flags(self) -> SettingSecretFlags: ...
        @phase2_ca_cert_password_flags.setter
        def phase2_ca_cert_password_flags(
            self, value: _SettingSecretFlagsValueType
        ) -> None: ...
        @property
        def phase2_ca_path(self) -> str: ...
        @phase2_ca_path.setter
        def phase2_ca_path(self, value: str | None) -> None: ...
        @property
        def phase2_client_cert(self) -> GLib.Bytes | None: ...
        @phase2_client_cert.setter
        def phase2_client_cert(self, value: GLib.Bytes) -> None: ...
        @property
        def phase2_client_cert_password(self) -> str: ...
        @phase2_client_cert_password.setter
        def phase2_client_cert_password(self, value: str | None) -> None: ...
        @property
        def phase2_client_cert_password_flags(self) -> SettingSecretFlags: ...
        @phase2_client_cert_password_flags.setter
        def phase2_client_cert_password_flags(
            self, value: _SettingSecretFlagsValueType
        ) -> None: ...
        @property
        def phase2_domain_match(self) -> str: ...
        @phase2_domain_match.setter
        def phase2_domain_match(self, value: str | None) -> None: ...
        @property
        def phase2_domain_suffix_match(self) -> str: ...
        @phase2_domain_suffix_match.setter
        def phase2_domain_suffix_match(self, value: str | None) -> None: ...
        @property
        def phase2_private_key(self) -> GLib.Bytes | None: ...
        @phase2_private_key.setter
        def phase2_private_key(self, value: GLib.Bytes) -> None: ...
        @property
        def phase2_private_key_password(self) -> str: ...
        @phase2_private_key_password.setter
        def phase2_private_key_password(self, value: str | None) -> None: ...
        @property
        def phase2_private_key_password_flags(self) -> SettingSecretFlags: ...
        @phase2_private_key_password_flags.setter
        def phase2_private_key_password_flags(
            self, value: _SettingSecretFlagsValueType
        ) -> None: ...
        @property
        def phase2_subject_match(self) -> str: ...
        @phase2_subject_match.setter
        def phase2_subject_match(self, value: str | None) -> None: ...
        @property
        def pin(self) -> str: ...
        @pin.setter
        def pin(self, value: str | None) -> None: ...
        @property
        def pin_flags(self) -> SettingSecretFlags: ...
        @pin_flags.setter
        def pin_flags(self, value: _SettingSecretFlagsValueType) -> None: ...
        @property
        def private_key(self) -> GLib.Bytes | None: ...
        @private_key.setter
        def private_key(self, value: GLib.Bytes) -> None: ...
        @property
        def private_key_password(self) -> str: ...
        @private_key_password.setter
        def private_key_password(self, value: str | None) -> None: ...
        @property
        def private_key_password_flags(self) -> SettingSecretFlags: ...
        @private_key_password_flags.setter
        def private_key_password_flags(
            self, value: _SettingSecretFlagsValueType
        ) -> None: ...
        @property
        def subject_match(self) -> str: ...
        @subject_match.setter
        def subject_match(self, value: str | None) -> None: ...
        system_ca_certs: bool

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        altsubject_matches: Sequence[str] | None = ...,
        anonymous_identity: str | None = ...,
        auth_timeout: int = ...,
        ca_cert: GLib.Bytes = ...,
        ca_cert_password: str | None = ...,
        ca_cert_password_flags: _SettingSecretFlagsValueType = ...,
        ca_path: str | None = ...,
        client_cert: GLib.Bytes = ...,
        client_cert_password: str | None = ...,
        client_cert_password_flags: _SettingSecretFlagsValueType = ...,
        domain_match: str | None = ...,
        domain_suffix_match: str | None = ...,
        eap: Sequence[str] | None = ...,
        identity: str | None = ...,
        openssl_ciphers: str | None = ...,
        optional: bool = ...,
        pac_file: str | None = ...,
        password: str | None = ...,
        password_flags: _SettingSecretFlagsValueType = ...,
        password_raw: GLib.Bytes | None = ...,
        password_raw_flags: _SettingSecretFlagsValueType = ...,
        phase1_auth_flags: int = ...,
        phase1_fast_provisioning: str | None = ...,
        phase1_peaplabel: str | None = ...,
        phase1_peapver: str | None = ...,
        phase2_altsubject_matches: Sequence[str] | None = ...,
        phase2_auth: str | None = ...,
        phase2_autheap: str | None = ...,
        phase2_ca_cert: GLib.Bytes = ...,
        phase2_ca_cert_password: str | None = ...,
        phase2_ca_cert_password_flags: _SettingSecretFlagsValueType = ...,
        phase2_ca_path: str | None = ...,
        phase2_client_cert: GLib.Bytes = ...,
        phase2_client_cert_password: str | None = ...,
        phase2_client_cert_password_flags: _SettingSecretFlagsValueType = ...,
        phase2_domain_match: str | None = ...,
        phase2_domain_suffix_match: str | None = ...,
        phase2_private_key: GLib.Bytes = ...,
        phase2_private_key_password: str | None = ...,
        phase2_private_key_password_flags: _SettingSecretFlagsValueType = ...,
        phase2_subject_match: str | None = ...,
        pin: str | None = ...,
        pin_flags: _SettingSecretFlagsValueType = ...,
        private_key: GLib.Bytes = ...,
        private_key_password: str | None = ...,
        private_key_password_flags: _SettingSecretFlagsValueType = ...,
        subject_match: str | None = ...,
        system_ca_certs: bool = ...,
    ) -> None: ...
    def add_altsubject_match(self, altsubject_match: str) -> bool: ...
    def add_eap_method(self, eap: str) -> bool: ...
    def add_phase2_altsubject_match(self, phase2_altsubject_match: str) -> bool: ...
    @staticmethod
    def check_cert_scheme(
        pdata: int | Any | None, length: int
    ) -> Setting8021xCKScheme: ...
    def clear_altsubject_matches(self) -> None: ...
    def clear_eap_methods(self) -> None: ...
    def clear_phase2_altsubject_matches(self) -> None: ...
    def get_altsubject_match(self, i: int) -> str: ...
    def get_anonymous_identity(self) -> str: ...
    def get_auth_timeout(self) -> int: ...
    def get_ca_cert_blob(self) -> GLib.Bytes: ...
    def get_ca_cert_password(self) -> str: ...
    def get_ca_cert_password_flags(self) -> SettingSecretFlags: ...
    def get_ca_cert_path(self) -> str: ...
    def get_ca_cert_scheme(self) -> Setting8021xCKScheme: ...
    def get_ca_cert_uri(self) -> str: ...
    def get_ca_path(self) -> str: ...
    def get_client_cert_blob(self) -> GLib.Bytes: ...
    def get_client_cert_password(self) -> str: ...
    def get_client_cert_password_flags(self) -> SettingSecretFlags: ...
    def get_client_cert_path(self) -> str: ...
    def get_client_cert_scheme(self) -> Setting8021xCKScheme: ...
    def get_client_cert_uri(self) -> str: ...
    def get_domain_match(self) -> str: ...
    def get_domain_suffix_match(self) -> str: ...
    def get_eap_method(self, i: int) -> str: ...
    def get_identity(self) -> str: ...
    def get_num_altsubject_matches(self) -> int: ...
    def get_num_eap_methods(self) -> int: ...
    def get_num_phase2_altsubject_matches(self) -> int: ...
    def get_openssl_ciphers(self) -> str: ...
    def get_optional(self) -> bool: ...
    def get_pac_file(self) -> str: ...
    def get_password(self) -> str: ...
    def get_password_flags(self) -> SettingSecretFlags: ...
    def get_password_raw(self) -> GLib.Bytes: ...
    def get_password_raw_flags(self) -> SettingSecretFlags: ...
    def get_phase1_auth_flags(self) -> Setting8021xAuthFlags: ...
    def get_phase1_fast_provisioning(self) -> str: ...
    def get_phase1_peaplabel(self) -> str: ...
    def get_phase1_peapver(self) -> str: ...
    def get_phase2_altsubject_match(self, i: int) -> str: ...
    def get_phase2_auth(self) -> str: ...
    def get_phase2_autheap(self) -> str: ...
    def get_phase2_ca_cert_blob(self) -> GLib.Bytes: ...
    def get_phase2_ca_cert_password(self) -> str: ...
    def get_phase2_ca_cert_password_flags(self) -> SettingSecretFlags: ...
    def get_phase2_ca_cert_path(self) -> str: ...
    def get_phase2_ca_cert_scheme(self) -> Setting8021xCKScheme: ...
    def get_phase2_ca_cert_uri(self) -> str: ...
    def get_phase2_ca_path(self) -> str: ...
    def get_phase2_client_cert_blob(self) -> GLib.Bytes: ...
    def get_phase2_client_cert_password(self) -> str: ...
    def get_phase2_client_cert_password_flags(self) -> SettingSecretFlags: ...
    def get_phase2_client_cert_path(self) -> str: ...
    def get_phase2_client_cert_scheme(self) -> Setting8021xCKScheme: ...
    def get_phase2_client_cert_uri(self) -> str: ...
    def get_phase2_domain_match(self) -> str: ...
    def get_phase2_domain_suffix_match(self) -> str: ...
    def get_phase2_private_key_blob(self) -> GLib.Bytes: ...
    def get_phase2_private_key_format(self) -> Setting8021xCKFormat: ...
    def get_phase2_private_key_password(self) -> str: ...
    def get_phase2_private_key_password_flags(self) -> SettingSecretFlags: ...
    def get_phase2_private_key_path(self) -> str: ...
    def get_phase2_private_key_scheme(self) -> Setting8021xCKScheme: ...
    def get_phase2_private_key_uri(self) -> str: ...
    def get_phase2_subject_match(self) -> str: ...
    def get_pin(self) -> str: ...
    def get_pin_flags(self) -> SettingSecretFlags: ...
    def get_private_key_blob(self) -> GLib.Bytes: ...
    def get_private_key_format(self) -> Setting8021xCKFormat: ...
    def get_private_key_password(self) -> str: ...
    def get_private_key_password_flags(self) -> SettingSecretFlags: ...
    def get_private_key_path(self) -> str: ...
    def get_private_key_scheme(self) -> Setting8021xCKScheme: ...
    def get_private_key_uri(self) -> str: ...
    def get_subject_match(self) -> str: ...
    def get_system_ca_certs(self) -> bool: ...
    @classmethod
    def new(cls) -> Setting8021x: ...
    def remove_altsubject_match(self, i: int) -> None: ...
    def remove_altsubject_match_by_value(self, altsubject_match: str) -> bool: ...
    def remove_eap_method(self, i: int) -> None: ...
    def remove_eap_method_by_value(self, eap: str) -> bool: ...
    def remove_phase2_altsubject_match(self, i: int) -> None: ...
    def remove_phase2_altsubject_match_by_value(
        self, phase2_altsubject_match: str
    ) -> bool: ...
    def set_ca_cert(
        self,
        value: str,
        scheme: _Setting8021xCKSchemeValueType,
        out_format: _Setting8021xCKFormatValueType,
    ) -> bool: ...
    def set_client_cert(
        self,
        value: str,
        scheme: _Setting8021xCKSchemeValueType,
        out_format: _Setting8021xCKFormatValueType,
    ) -> bool: ...
    def set_phase2_ca_cert(
        self,
        value: str,
        scheme: _Setting8021xCKSchemeValueType,
        out_format: _Setting8021xCKFormatValueType,
    ) -> bool: ...
    def set_phase2_client_cert(
        self,
        value: str,
        scheme: _Setting8021xCKSchemeValueType,
        out_format: _Setting8021xCKFormatValueType,
    ) -> bool: ...
    def set_phase2_private_key(
        self,
        value: str,
        password: str,
        scheme: _Setting8021xCKSchemeValueType,
        out_format: _Setting8021xCKFormatValueType,
    ) -> bool: ...
    def set_private_key(
        self,
        value: str,
        password: str,
        scheme: _Setting8021xCKSchemeValueType,
        out_format: _Setting8021xCKFormatValueType,
    ) -> bool: ...

class Setting8021xClass(_gi.Struct): ...

class SettingAdsl(Setting):
    """
    :Constructors:

    ::

        SettingAdsl(**properties)
        new() -> NM.Setting

    Object NMSettingAdsl

    Properties from NMSettingAdsl:
      username -> gchararray:

      password -> gchararray:

      password-flags -> NMSettingSecretFlags:

      protocol -> gchararray:

      encapsulation -> gchararray:

      vpi -> guint:

      vci -> guint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def encapsulation(self) -> str: ...
        @encapsulation.setter
        def encapsulation(self, value: str | None) -> None: ...
        @property
        def password(self) -> str: ...
        @password.setter
        def password(self, value: str | None) -> None: ...
        @property
        def password_flags(self) -> SettingSecretFlags: ...
        @password_flags.setter
        def password_flags(self, value: _SettingSecretFlagsValueType) -> None: ...
        @property
        def protocol(self) -> str: ...
        @protocol.setter
        def protocol(self, value: str | None) -> None: ...
        @property
        def username(self) -> str: ...
        @username.setter
        def username(self, value: str | None) -> None: ...
        vci: int
        vpi: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        encapsulation: str | None = ...,
        password: str | None = ...,
        password_flags: _SettingSecretFlagsValueType = ...,
        protocol: str | None = ...,
        username: str | None = ...,
        vci: int = ...,
        vpi: int = ...,
    ) -> None: ...
    def get_encapsulation(self) -> str: ...
    def get_password(self) -> str: ...
    def get_password_flags(self) -> SettingSecretFlags: ...
    def get_protocol(self) -> str: ...
    def get_username(self) -> str: ...
    def get_vci(self) -> int: ...
    def get_vpi(self) -> int: ...
    @classmethod
    def new(cls) -> SettingAdsl: ...

class SettingAdslClass(_gi.Struct): ...

class SettingBluetooth(Setting):
    """
    :Constructors:

    ::

        SettingBluetooth(**properties)
        new() -> NM.Setting

    Object NMSettingBluetooth

    Properties from NMSettingBluetooth:
      bdaddr -> gchararray:

      type -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def bdaddr(self) -> str: ...
        @bdaddr.setter
        def bdaddr(self, value: str | None) -> None: ...
        type: str | None

    @property
    def props(self) -> Props: ...
    def __init__(self, *, bdaddr: str | None = ..., type: str | None = ...) -> None: ...
    def get_bdaddr(self) -> str: ...
    def get_connection_type(self) -> str: ...
    @classmethod
    def new(cls) -> SettingBluetooth: ...

class SettingBluetoothClass(_gi.Struct): ...

class SettingBond(Setting):
    """
    :Constructors:

    ::

        SettingBond(**properties)
        new() -> NM.Setting

    Object NMSettingBond

    Properties from NMSettingBond:
      options -> GHashTable:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def options(self) -> dict[str, str] | None: ...
        @options.setter
        def options(self, value: Mapping[str, str] | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, options: Mapping[str, str] | None = ...) -> None: ...
    def add_option(self, name: str, value: str) -> bool: ...
    def get_num_options(self) -> int: ...
    def get_option(self, idx: int) -> tuple[bool, str, str]: ...
    def get_option_by_name(self, name: str) -> str: ...
    def get_option_default(self, name: str) -> str: ...
    def get_option_normalized(self, name: str) -> str: ...
    def get_valid_options(self) -> list[str]: ...
    @classmethod
    def new(cls) -> SettingBond: ...
    def remove_option(self, name: str) -> bool: ...
    @staticmethod
    def validate_option(name: str, value: str | None = None) -> bool: ...

class SettingBondClass(_gi.Struct): ...

class SettingBondPort(Setting):
    """
    :Constructors:

    ::

        SettingBondPort(**properties)
        new() -> NM.Setting

    Object NMSettingBondPort

    Properties from NMSettingBondPort:
      queue-id -> guint:

      prio -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        prio: int
        queue_id: int

    @property
    def props(self) -> Props: ...
    def __init__(self, *, prio: int = ..., queue_id: int = ...) -> None: ...
    def get_prio(self) -> int: ...
    def get_queue_id(self) -> int: ...
    @classmethod
    def new(cls) -> SettingBondPort: ...

class SettingBondPortClass(_gi.Struct): ...

class SettingBridge(Setting):
    """
    :Constructors:

    ::

        SettingBridge(**properties)
        new() -> NM.Setting

    Object NMSettingBridge

    Properties from NMSettingBridge:
      mac-address -> gchararray:

      stp -> gboolean:

      priority -> guint:

      forward-delay -> guint:

      hello-time -> guint:

      max-age -> guint:

      ageing-time -> guint:

      group-address -> gchararray:

      group-forward-mask -> guint:

      multicast-hash-max -> guint:

      multicast-last-member-count -> guint:

      multicast-last-member-interval -> guint64:

      multicast-membership-interval -> guint64:

      multicast-router -> gchararray:

      multicast-querier -> gboolean:

      multicast-querier-interval -> guint64:

      multicast-query-interval -> guint64:

      multicast-query-response-interval -> guint64:

      multicast-query-use-ifaddr -> gboolean:

      multicast-snooping -> gboolean:

      multicast-startup-query-count -> guint:

      multicast-startup-query-interval -> guint64:

      vlan-filtering -> gboolean:

      vlan-default-pvid -> guint:

      vlan-protocol -> gchararray:

      vlan-stats-enabled -> gboolean:

      vlans -> GPtrArray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        ageing_time: int
        forward_delay: int
        @property
        def group_address(self) -> str: ...
        @group_address.setter
        def group_address(self, value: str | None) -> None: ...
        group_forward_mask: int
        hello_time: int
        @property
        def mac_address(self) -> str: ...
        @mac_address.setter
        def mac_address(self, value: str | None) -> None: ...
        max_age: int
        multicast_hash_max: int
        multicast_last_member_count: int
        multicast_last_member_interval: int
        multicast_membership_interval: int
        multicast_querier: bool
        multicast_querier_interval: int
        multicast_query_interval: int
        multicast_query_response_interval: int
        multicast_query_use_ifaddr: bool
        @property
        def multicast_router(self) -> str: ...
        @multicast_router.setter
        def multicast_router(self, value: str | None) -> None: ...
        multicast_snooping: bool
        multicast_startup_query_count: int
        multicast_startup_query_interval: int
        priority: int
        stp: bool
        vlan_default_pvid: int
        vlan_filtering: bool
        @property
        def vlan_protocol(self) -> str: ...
        @vlan_protocol.setter
        def vlan_protocol(self, value: str | None) -> None: ...
        vlan_stats_enabled: bool
        @property
        def vlans(self) -> list[BridgeVlan]: ...
        @vlans.setter
        def vlans(self, value: Sequence[BridgeVlan] | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        ageing_time: int = ...,
        forward_delay: int = ...,
        group_address: str | None = ...,
        group_forward_mask: int = ...,
        hello_time: int = ...,
        mac_address: str | None = ...,
        max_age: int = ...,
        multicast_hash_max: int = ...,
        multicast_last_member_count: int = ...,
        multicast_last_member_interval: int = ...,
        multicast_membership_interval: int = ...,
        multicast_querier: bool = ...,
        multicast_querier_interval: int = ...,
        multicast_query_interval: int = ...,
        multicast_query_response_interval: int = ...,
        multicast_query_use_ifaddr: bool = ...,
        multicast_router: str | None = ...,
        multicast_snooping: bool = ...,
        multicast_startup_query_count: int = ...,
        multicast_startup_query_interval: int = ...,
        priority: int = ...,
        stp: bool = ...,
        vlan_default_pvid: int = ...,
        vlan_filtering: bool = ...,
        vlan_protocol: str | None = ...,
        vlan_stats_enabled: bool = ...,
        vlans: Sequence[BridgeVlan] | None = ...,
    ) -> None: ...
    def add_vlan(self, vlan: BridgeVlan) -> None: ...
    def clear_vlans(self) -> None: ...
    def get_ageing_time(self) -> int: ...
    def get_forward_delay(self) -> int: ...
    def get_group_address(self) -> str: ...
    def get_group_forward_mask(self) -> int: ...
    def get_hello_time(self) -> int: ...
    def get_mac_address(self) -> str: ...
    def get_max_age(self) -> int: ...
    def get_multicast_hash_max(self) -> int: ...
    def get_multicast_last_member_count(self) -> int: ...
    def get_multicast_last_member_interval(self) -> int: ...
    def get_multicast_membership_interval(self) -> int: ...
    def get_multicast_querier(self) -> bool: ...
    def get_multicast_querier_interval(self) -> int: ...
    def get_multicast_query_interval(self) -> int: ...
    def get_multicast_query_response_interval(self) -> int: ...
    def get_multicast_query_use_ifaddr(self) -> bool: ...
    def get_multicast_router(self) -> str: ...
    def get_multicast_snooping(self) -> bool: ...
    def get_multicast_startup_query_count(self) -> int: ...
    def get_multicast_startup_query_interval(self) -> int: ...
    def get_num_vlans(self) -> int: ...
    def get_priority(self) -> int: ...
    def get_stp(self) -> bool: ...
    def get_vlan(self, idx: int) -> BridgeVlan: ...
    def get_vlan_default_pvid(self) -> int: ...
    def get_vlan_filtering(self) -> bool: ...
    def get_vlan_protocol(self) -> str: ...
    def get_vlan_stats_enabled(self) -> bool: ...
    @classmethod
    def new(cls) -> SettingBridge: ...
    def remove_vlan(self, idx: int) -> None: ...
    def remove_vlan_by_vid(self, vid_start: int, vid_end: int) -> bool: ...

class SettingBridgeClass(_gi.Struct): ...

class SettingBridgePort(Setting):
    """
    :Constructors:

    ::

        SettingBridgePort(**properties)
        new() -> NM.Setting

    Object NMSettingBridgePort

    Properties from NMSettingBridgePort:
      priority -> guint:

      path-cost -> guint:

      hairpin-mode -> gboolean:

      vlans -> GPtrArray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        hairpin_mode: bool
        path_cost: int
        priority: int
        @property
        def vlans(self) -> list[BridgeVlan]: ...
        @vlans.setter
        def vlans(self, value: Sequence[BridgeVlan] | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        hairpin_mode: bool = ...,
        path_cost: int = ...,
        priority: int = ...,
        vlans: Sequence[BridgeVlan] | None = ...,
    ) -> None: ...
    def add_vlan(self, vlan: BridgeVlan) -> None: ...
    def clear_vlans(self) -> None: ...
    def get_hairpin_mode(self) -> bool: ...
    def get_num_vlans(self) -> int: ...
    def get_path_cost(self) -> int: ...
    def get_priority(self) -> int: ...
    def get_vlan(self, idx: int) -> BridgeVlan: ...
    @classmethod
    def new(cls) -> SettingBridgePort: ...
    def remove_vlan(self, idx: int) -> None: ...
    def remove_vlan_by_vid(self, vid_start: int, vid_end: int) -> bool: ...

class SettingBridgePortClass(_gi.Struct): ...

class SettingCdma(Setting):
    """
    :Constructors:

    ::

        SettingCdma(**properties)
        new() -> NM.Setting

    Object NMSettingCdma

    Properties from NMSettingCdma:
      number -> gchararray:

      username -> gchararray:

      password -> gchararray:

      password-flags -> NMSettingSecretFlags:

      mtu -> guint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        mtu: int
        @property
        def number(self) -> str: ...
        @number.setter
        def number(self, value: str | None) -> None: ...
        @property
        def password(self) -> str: ...
        @password.setter
        def password(self, value: str | None) -> None: ...
        @property
        def password_flags(self) -> SettingSecretFlags: ...
        @password_flags.setter
        def password_flags(self, value: _SettingSecretFlagsValueType) -> None: ...
        @property
        def username(self) -> str: ...
        @username.setter
        def username(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        mtu: int = ...,
        number: str | None = ...,
        password: str | None = ...,
        password_flags: _SettingSecretFlagsValueType = ...,
        username: str | None = ...,
    ) -> None: ...
    def get_mtu(self) -> int: ...
    def get_number(self) -> str: ...
    def get_password(self) -> str: ...
    def get_password_flags(self) -> SettingSecretFlags: ...
    def get_username(self) -> str: ...
    @classmethod
    def new(cls) -> SettingCdma: ...

class SettingCdmaClass(_gi.Struct): ...
class SettingClass(_gi.Struct): ...

class SettingConnection(Setting):
    """
    :Constructors:

    ::

        SettingConnection(**properties)
        new() -> NM.Setting

    Object NMSettingConnection

    Properties from NMSettingConnection:
      id -> gchararray:

      uuid -> gchararray:

      interface-name -> gchararray:

      type -> gchararray:

      permissions -> GStrv:

      autoconnect -> gboolean:

      autoconnect-priority -> gint:

      autoconnect-retries -> gint:

      multi-connect -> gint:

      timestamp -> guint64:

      read-only -> gboolean:

      zone -> gchararray:

      master -> gchararray:

      controller -> gchararray:

      slave-type -> gchararray:

      port-type -> gchararray:

      autoconnect-slaves -> NMSettingConnectionAutoconnectSlaves:

      autoconnect-ports -> gint:

      secondaries -> GStrv:

      gateway-ping-timeout -> guint:

      ip-ping-timeout -> guint:

      ip-ping-addresses -> GStrv:

      ip-ping-addresses-require-all -> gint:

      metered -> NMMetered:

      lldp -> gint:

      mdns -> gint:

      llmnr -> gint:

      dns-over-tls -> gint:

      dnssec -> gint:

      mptcp-flags -> guint:

      stable-id -> gchararray:

      auth-retries -> gint:

      wait-device-timeout -> gint:

      mud-url -> gchararray:

      wait-activation-delay -> gint:

      down-on-poweroff -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        auth_retries: int
        autoconnect: bool
        autoconnect_ports: int
        autoconnect_priority: int
        autoconnect_retries: int
        @property
        def autoconnect_slaves(self) -> SettingConnectionAutoconnectSlaves: ...
        @autoconnect_slaves.setter
        def autoconnect_slaves(
            self, value: _SettingConnectionAutoconnectSlavesValueType
        ) -> None: ...
        @property
        def controller(self) -> str: ...
        @controller.setter
        def controller(self, value: str | None) -> None: ...
        dns_over_tls: int
        dnssec: int
        down_on_poweroff: int
        gateway_ping_timeout: int
        @property
        def id(self) -> str: ...
        @id.setter
        def id(self, value: str | None) -> None: ...
        @property
        def interface_name(self) -> str: ...
        @interface_name.setter
        def interface_name(self, value: str | None) -> None: ...
        @property
        def ip_ping_addresses(self) -> list[str]: ...
        @ip_ping_addresses.setter
        def ip_ping_addresses(self, value: Sequence[str] | None) -> None: ...
        ip_ping_addresses_require_all: int
        ip_ping_timeout: int
        lldp: int
        llmnr: int
        @property
        def master(self) -> str: ...
        @master.setter
        def master(self, value: str | None) -> None: ...
        mdns: int
        @property
        def metered(self) -> Metered: ...
        @metered.setter
        def metered(self, value: _MeteredValueType) -> None: ...
        mptcp_flags: int
        @property
        def mud_url(self) -> str: ...
        @mud_url.setter
        def mud_url(self, value: str | None) -> None: ...
        multi_connect: int
        @property
        def permissions(self) -> list[str]: ...
        @permissions.setter
        def permissions(self, value: Sequence[str] | None) -> None: ...
        @property
        def port_type(self) -> str: ...
        @port_type.setter
        def port_type(self, value: str | None) -> None: ...
        read_only: bool
        @property
        def secondaries(self) -> list[str]: ...
        @secondaries.setter
        def secondaries(self, value: Sequence[str] | None) -> None: ...
        @property
        def slave_type(self) -> str: ...
        @slave_type.setter
        def slave_type(self, value: str | None) -> None: ...
        @property
        def stable_id(self) -> str: ...
        @stable_id.setter
        def stable_id(self, value: str | None) -> None: ...
        timestamp: int
        type: str | None
        @property
        def uuid(self) -> str: ...
        @uuid.setter
        def uuid(self, value: str | None) -> None: ...
        wait_activation_delay: int
        wait_device_timeout: int
        @property
        def zone(self) -> str: ...
        @zone.setter
        def zone(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        auth_retries: int = ...,
        autoconnect: bool = ...,
        autoconnect_ports: int = ...,
        autoconnect_priority: int = ...,
        autoconnect_retries: int = ...,
        autoconnect_slaves: _SettingConnectionAutoconnectSlavesValueType = ...,
        controller: str | None = ...,
        dns_over_tls: int = ...,
        dnssec: int = ...,
        down_on_poweroff: int = ...,
        gateway_ping_timeout: int = ...,
        id: str | None = ...,
        interface_name: str | None = ...,
        ip_ping_addresses: Sequence[str] | None = ...,
        ip_ping_addresses_require_all: int = ...,
        ip_ping_timeout: int = ...,
        lldp: int = ...,
        llmnr: int = ...,
        master: str | None = ...,
        mdns: int = ...,
        metered: _MeteredValueType = ...,
        mptcp_flags: int = ...,
        mud_url: str | None = ...,
        multi_connect: int = ...,
        permissions: Sequence[str] | None = ...,
        port_type: str | None = ...,
        read_only: bool = ...,
        secondaries: Sequence[str] | None = ...,
        slave_type: str | None = ...,
        stable_id: str | None = ...,
        timestamp: int = ...,
        type: str | None = ...,
        uuid: str | None = ...,
        wait_activation_delay: int = ...,
        wait_device_timeout: int = ...,
        zone: str | None = ...,
    ) -> None: ...
    def add_ip_ping_address(self, address: str) -> bool: ...
    def add_permission(
        self, ptype: str, pitem: str, detail: str | None = None
    ) -> bool: ...
    def add_secondary(self, sec_uuid: str) -> bool: ...
    def clear_ip_ping_addresses(self) -> None: ...
    def get_auth_retries(self) -> int: ...
    def get_autoconnect(self) -> bool: ...
    def get_autoconnect_ports(self) -> Ternary: ...
    def get_autoconnect_priority(self) -> int: ...
    def get_autoconnect_retries(self) -> int: ...
    def get_autoconnect_slaves(self) -> SettingConnectionAutoconnectSlaves: ...
    def get_connection_type(self) -> str: ...
    def get_controller(self) -> str: ...
    def get_dns_over_tls(self) -> SettingConnectionDnsOverTls: ...
    def get_dnssec(self) -> SettingConnectionDnssec: ...
    def get_down_on_poweroff(self) -> SettingConnectionDownOnPoweroff: ...
    def get_gateway_ping_timeout(self) -> int: ...
    def get_id(self) -> str: ...
    def get_interface_name(self) -> str: ...
    def get_ip_ping_address(self, idx: int) -> str: ...
    def get_ip_ping_addresses_require_all(self) -> Ternary: ...
    def get_ip_ping_timeout(self) -> int: ...
    def get_lldp(self) -> SettingConnectionLldp: ...
    def get_llmnr(self) -> SettingConnectionLlmnr: ...
    def get_master(self) -> str: ...
    def get_mdns(self) -> SettingConnectionMdns: ...
    def get_metered(self) -> Metered: ...
    def get_mptcp_flags(self) -> MptcpFlags: ...
    def get_mud_url(self) -> str: ...
    def get_multi_connect(self) -> ConnectionMultiConnect: ...
    def get_num_permissions(self) -> int: ...
    def get_num_secondaries(self) -> int: ...
    def get_permission(
        self, idx: int, out_ptype: str, out_pitem: str, out_detail: str
    ) -> bool: ...
    def get_port_type(self) -> str: ...
    def get_read_only(self) -> bool: ...
    def get_secondary(self, idx: int) -> str: ...
    def get_slave_type(self) -> str: ...
    def get_stable_id(self) -> str: ...
    def get_timestamp(self) -> int: ...
    def get_uuid(self) -> str: ...
    def get_wait_activation_delay(self) -> int: ...
    def get_wait_device_timeout(self) -> int: ...
    def get_zone(self) -> str: ...
    def is_slave_type(self, type: str) -> bool: ...
    @classmethod
    def new(cls) -> SettingConnection: ...
    def permissions_user_allowed(self, uname: str) -> bool: ...
    def remove_ip_ping_address(self, idx: int) -> None: ...
    def remove_ip_ping_address_by_value(self, address: str) -> bool: ...
    def remove_permission(self, idx: int) -> None: ...
    def remove_permission_by_value(
        self, ptype: str, pitem: str, detail: str | None = None
    ) -> bool: ...
    def remove_secondary(self, idx: int) -> None: ...
    def remove_secondary_by_value(self, sec_uuid: str) -> bool: ...

class SettingConnectionClass(_gi.Struct): ...

class SettingDcb(Setting):
    """
    :Constructors:

    ::

        SettingDcb(**properties)
        new() -> NM.Setting

    Object NMSettingDcb

    Properties from NMSettingDcb:
      app-fcoe-flags -> NMSettingDcbFlags:

      app-fcoe-priority -> gint:

      app-fcoe-mode -> gchararray:

      app-iscsi-flags -> NMSettingDcbFlags:

      app-iscsi-priority -> gint:

      app-fip-flags -> NMSettingDcbFlags:

      app-fip-priority -> gint:

      priority-flow-control-flags -> NMSettingDcbFlags:

      priority-flow-control -> GArray:

      priority-group-flags -> NMSettingDcbFlags:

      priority-group-id -> GArray:

      priority-group-bandwidth -> GArray:

      priority-bandwidth -> GArray:

      priority-strict-bandwidth -> GArray:

      priority-traffic-class -> GArray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def app_fcoe_flags(self) -> SettingDcbFlags: ...
        @app_fcoe_flags.setter
        def app_fcoe_flags(self, value: _SettingDcbFlagsValueType) -> None: ...
        @property
        def app_fcoe_mode(self) -> str: ...
        @app_fcoe_mode.setter
        def app_fcoe_mode(self, value: str | None) -> None: ...
        app_fcoe_priority: int
        @property
        def app_fip_flags(self) -> SettingDcbFlags: ...
        @app_fip_flags.setter
        def app_fip_flags(self, value: _SettingDcbFlagsValueType) -> None: ...
        app_fip_priority: int
        @property
        def app_iscsi_flags(self) -> SettingDcbFlags: ...
        @app_iscsi_flags.setter
        def app_iscsi_flags(self, value: _SettingDcbFlagsValueType) -> None: ...
        app_iscsi_priority: int
        @property
        def priority_bandwidth(self) -> list[int]: ...
        @priority_bandwidth.setter
        def priority_bandwidth(self, value: Sequence[int]) -> None: ...
        @property
        def priority_flow_control(self) -> list[bool]: ...
        @priority_flow_control.setter
        def priority_flow_control(self, value: Sequence[bool]) -> None: ...
        @property
        def priority_flow_control_flags(self) -> SettingDcbFlags: ...
        @priority_flow_control_flags.setter
        def priority_flow_control_flags(
            self, value: _SettingDcbFlagsValueType
        ) -> None: ...
        @property
        def priority_group_bandwidth(self) -> list[int]: ...
        @priority_group_bandwidth.setter
        def priority_group_bandwidth(self, value: Sequence[int]) -> None: ...
        @property
        def priority_group_flags(self) -> SettingDcbFlags: ...
        @priority_group_flags.setter
        def priority_group_flags(self, value: _SettingDcbFlagsValueType) -> None: ...
        @property
        def priority_group_id(self) -> list[int]: ...
        @priority_group_id.setter
        def priority_group_id(self, value: Sequence[int]) -> None: ...
        @property
        def priority_strict_bandwidth(self) -> list[bool]: ...
        @priority_strict_bandwidth.setter
        def priority_strict_bandwidth(self, value: Sequence[bool]) -> None: ...
        @property
        def priority_traffic_class(self) -> list[int]: ...
        @priority_traffic_class.setter
        def priority_traffic_class(self, value: Sequence[int]) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        app_fcoe_flags: _SettingDcbFlagsValueType = ...,
        app_fcoe_mode: str | None = ...,
        app_fcoe_priority: int = ...,
        app_fip_flags: _SettingDcbFlagsValueType = ...,
        app_fip_priority: int = ...,
        app_iscsi_flags: _SettingDcbFlagsValueType = ...,
        app_iscsi_priority: int = ...,
        priority_bandwidth: Sequence[int] = ...,
        priority_flow_control: Sequence[bool] = ...,
        priority_flow_control_flags: _SettingDcbFlagsValueType = ...,
        priority_group_bandwidth: Sequence[int] = ...,
        priority_group_flags: _SettingDcbFlagsValueType = ...,
        priority_group_id: Sequence[int] = ...,
        priority_strict_bandwidth: Sequence[bool] = ...,
        priority_traffic_class: Sequence[int] = ...,
    ) -> None: ...
    def get_app_fcoe_flags(self) -> SettingDcbFlags: ...
    def get_app_fcoe_mode(self) -> str: ...
    def get_app_fcoe_priority(self) -> int: ...
    def get_app_fip_flags(self) -> SettingDcbFlags: ...
    def get_app_fip_priority(self) -> int: ...
    def get_app_iscsi_flags(self) -> SettingDcbFlags: ...
    def get_app_iscsi_priority(self) -> int: ...
    def get_priority_bandwidth(self, user_priority: int) -> int: ...
    def get_priority_flow_control(self, user_priority: int) -> bool: ...
    def get_priority_flow_control_flags(self) -> SettingDcbFlags: ...
    def get_priority_group_bandwidth(self, group_id: int) -> int: ...
    def get_priority_group_flags(self) -> SettingDcbFlags: ...
    def get_priority_group_id(self, user_priority: int) -> int: ...
    def get_priority_strict_bandwidth(self, user_priority: int) -> bool: ...
    def get_priority_traffic_class(self, user_priority: int) -> int: ...
    @classmethod
    def new(cls) -> SettingDcb: ...
    def set_priority_bandwidth(
        self, user_priority: int, bandwidth_percent: int
    ) -> None: ...
    def set_priority_flow_control(self, user_priority: int, enabled: bool) -> None: ...
    def set_priority_group_bandwidth(
        self, group_id: int, bandwidth_percent: int
    ) -> None: ...
    def set_priority_group_id(self, user_priority: int, group_id: int) -> None: ...
    def set_priority_strict_bandwidth(
        self, user_priority: int, strict: bool
    ) -> None: ...
    def set_priority_traffic_class(
        self, user_priority: int, traffic_class: int
    ) -> None: ...

class SettingDcbClass(_gi.Struct): ...

class SettingDummy(Setting):
    """
    :Constructors:

    ::

        SettingDummy(**properties)
        new() -> NM.Setting

    Object NMSettingDummy

    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @classmethod
    def new(cls) -> SettingDummy: ...

class SettingDummyClass(_gi.Struct): ...

class SettingEthtool(Setting):
    """
    :Constructors:

    ::

        SettingEthtool(**properties)
        new() -> NM.Setting

    Object NMSettingEthtool

    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    def clear_features(self) -> None: ...
    def get_feature(self, optname: str) -> Ternary: ...
    def get_optnames(self) -> tuple[list[str], int]: ...
    @classmethod
    def new(cls) -> SettingEthtool: ...
    def set_feature(self, optname: str, value: _TernaryValueType) -> None: ...

class SettingEthtoolClass(_gi.Struct): ...

class SettingGeneric(Setting):
    """
    :Constructors:

    ::

        SettingGeneric(**properties)
        new() -> NM.Setting

    Object NMSettingGeneric

    Properties from NMSettingGeneric:
      device-handler -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def device_handler(self) -> str: ...
        @device_handler.setter
        def device_handler(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, device_handler: str | None = ...) -> None: ...
    def get_device_handler(self) -> str: ...
    @classmethod
    def new(cls) -> SettingGeneric: ...

class SettingGenericClass(_gi.Struct): ...

class SettingGeneve(Setting):
    """
    :Constructors:

    ::

        SettingGeneve(**properties)
        new() -> NM.Setting

    Object NMSettingGeneve

    Properties from NMSettingGeneve:
      id -> guint:

      remote -> gchararray:

      destination-port -> guint:

      tos -> guint:

      ttl -> gint:

      df -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        destination_port: int
        df: int
        id: int
        @property
        def remote(self) -> str: ...
        @remote.setter
        def remote(self, value: str | None) -> None: ...
        tos: int
        ttl: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        destination_port: int = ...,
        df: int = ...,
        id: int = ...,
        remote: str | None = ...,
        tos: int = ...,
        ttl: int = ...,
    ) -> None: ...
    def get_destination_port(self) -> int: ...
    def get_df(self) -> SettingGeneveDf: ...
    def get_id(self) -> int: ...
    def get_remote(self) -> str: ...
    def get_tos(self) -> int: ...
    def get_ttl(self) -> int: ...
    @classmethod
    def new(cls) -> SettingGeneve: ...

class SettingGeneveClass(_gi.Struct): ...

class SettingGsm(Setting):
    """
    :Constructors:

    ::

        SettingGsm(**properties)
        new() -> NM.Setting

    Object NMSettingGsm

    Properties from NMSettingGsm:
      auto-config -> gboolean:

      number -> gchararray:

      username -> gchararray:

      password -> gchararray:

      password-flags -> NMSettingSecretFlags:

      apn -> gchararray:

      network-id -> gchararray:

      pin -> gchararray:

      pin-flags -> NMSettingSecretFlags:

      home-only -> gboolean:

      device-id -> gchararray:

      sim-id -> gchararray:

      sim-operator-id -> gchararray:

      mtu -> guint:

      initial-eps-bearer-configure -> gboolean:

      initial-eps-bearer-apn -> gchararray:

      initial-eps-bearer-username -> gchararray:

      initial-eps-bearer-password -> gchararray:

      initial-eps-bearer-password-flags -> NMSettingSecretFlags:

      initial-eps-bearer-noauth -> gboolean:

      initial-eps-bearer-refuse-eap -> gboolean:

      initial-eps-bearer-refuse-pap -> gboolean:

      initial-eps-bearer-refuse-chap -> gboolean:

      initial-eps-bearer-refuse-mschap -> gboolean:

      initial-eps-bearer-refuse-mschapv2 -> gboolean:

      device-uid -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def apn(self) -> str: ...
        @apn.setter
        def apn(self, value: str | None) -> None: ...
        auto_config: bool
        @property
        def device_id(self) -> str: ...
        @device_id.setter
        def device_id(self, value: str | None) -> None: ...
        @property
        def device_uid(self) -> str: ...
        @device_uid.setter
        def device_uid(self, value: str | None) -> None: ...
        home_only: bool
        initial_eps_bearer_apn: str | None
        initial_eps_bearer_configure: bool
        initial_eps_bearer_noauth: bool
        initial_eps_bearer_password: str | None
        @property
        def initial_eps_bearer_password_flags(self) -> SettingSecretFlags: ...
        @initial_eps_bearer_password_flags.setter
        def initial_eps_bearer_password_flags(
            self, value: _SettingSecretFlagsValueType
        ) -> None: ...
        initial_eps_bearer_refuse_chap: bool
        initial_eps_bearer_refuse_eap: bool
        initial_eps_bearer_refuse_mschap: bool
        initial_eps_bearer_refuse_mschapv2: bool
        initial_eps_bearer_refuse_pap: bool
        initial_eps_bearer_username: str | None
        mtu: int
        @property
        def network_id(self) -> str: ...
        @network_id.setter
        def network_id(self, value: str | None) -> None: ...
        @property
        def number(self) -> str: ...
        @number.setter
        def number(self, value: str | None) -> None: ...
        @property
        def password(self) -> str: ...
        @password.setter
        def password(self, value: str | None) -> None: ...
        @property
        def password_flags(self) -> SettingSecretFlags: ...
        @password_flags.setter
        def password_flags(self, value: _SettingSecretFlagsValueType) -> None: ...
        @property
        def pin(self) -> str: ...
        @pin.setter
        def pin(self, value: str | None) -> None: ...
        @property
        def pin_flags(self) -> SettingSecretFlags: ...
        @pin_flags.setter
        def pin_flags(self, value: _SettingSecretFlagsValueType) -> None: ...
        @property
        def sim_id(self) -> str: ...
        @sim_id.setter
        def sim_id(self, value: str | None) -> None: ...
        @property
        def sim_operator_id(self) -> str: ...
        @sim_operator_id.setter
        def sim_operator_id(self, value: str | None) -> None: ...
        @property
        def username(self) -> str: ...
        @username.setter
        def username(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        apn: str | None = ...,
        auto_config: bool = ...,
        device_id: str | None = ...,
        device_uid: str | None = ...,
        home_only: bool = ...,
        initial_eps_bearer_apn: str | None = ...,
        initial_eps_bearer_configure: bool = ...,
        initial_eps_bearer_noauth: bool = ...,
        initial_eps_bearer_password: str | None = ...,
        initial_eps_bearer_password_flags: _SettingSecretFlagsValueType = ...,
        initial_eps_bearer_refuse_chap: bool = ...,
        initial_eps_bearer_refuse_eap: bool = ...,
        initial_eps_bearer_refuse_mschap: bool = ...,
        initial_eps_bearer_refuse_mschapv2: bool = ...,
        initial_eps_bearer_refuse_pap: bool = ...,
        initial_eps_bearer_username: str | None = ...,
        mtu: int = ...,
        network_id: str | None = ...,
        number: str | None = ...,
        password: str | None = ...,
        password_flags: _SettingSecretFlagsValueType = ...,
        pin: str | None = ...,
        pin_flags: _SettingSecretFlagsValueType = ...,
        sim_id: str | None = ...,
        sim_operator_id: str | None = ...,
        username: str | None = ...,
    ) -> None: ...
    def get_apn(self) -> str: ...
    def get_auto_config(self) -> bool: ...
    def get_device_id(self) -> str: ...
    def get_device_uid(self) -> str: ...
    def get_home_only(self) -> bool: ...
    def get_initial_eps_apn(self) -> str: ...
    def get_initial_eps_config(self) -> bool: ...
    def get_initial_eps_noauth(self) -> bool: ...
    def get_initial_eps_password(self) -> str: ...
    def get_initial_eps_refuse_chap(self) -> bool: ...
    def get_initial_eps_refuse_eap(self) -> bool: ...
    def get_initial_eps_refuse_mschap(self) -> bool: ...
    def get_initial_eps_refuse_mschapv2(self) -> bool: ...
    def get_initial_eps_refuse_pap(self) -> bool: ...
    def get_initial_eps_username(self) -> str: ...
    def get_mtu(self) -> int: ...
    def get_network_id(self) -> str: ...
    def get_number(self) -> str: ...
    def get_password(self) -> str: ...
    def get_password_flags(self) -> SettingSecretFlags: ...
    def get_pin(self) -> str: ...
    def get_pin_flags(self) -> SettingSecretFlags: ...
    def get_sim_id(self) -> str: ...
    def get_sim_operator_id(self) -> str: ...
    def get_username(self) -> str: ...
    @classmethod
    def new(cls) -> SettingGsm: ...

class SettingGsmClass(_gi.Struct): ...

class SettingHostname(Setting):
    """
    :Constructors:

    ::

        SettingHostname(**properties)
        new() -> NM.Setting

    Object NMSettingHostname

    Properties from NMSettingHostname:
      priority -> gint:

      from-dhcp -> NMTernary:

      from-dns-lookup -> NMTernary:

      only-from-default -> NMTernary:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def from_dhcp(self) -> Ternary: ...
        @from_dhcp.setter
        def from_dhcp(self, value: _TernaryValueType) -> None: ...
        @property
        def from_dns_lookup(self) -> Ternary: ...
        @from_dns_lookup.setter
        def from_dns_lookup(self, value: _TernaryValueType) -> None: ...
        @property
        def only_from_default(self) -> Ternary: ...
        @only_from_default.setter
        def only_from_default(self, value: _TernaryValueType) -> None: ...
        priority: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        from_dhcp: _TernaryValueType = ...,
        from_dns_lookup: _TernaryValueType = ...,
        only_from_default: _TernaryValueType = ...,
        priority: int = ...,
    ) -> None: ...
    def get_from_dhcp(self) -> Ternary: ...
    def get_from_dns_lookup(self) -> Ternary: ...
    def get_only_from_default(self) -> Ternary: ...
    def get_priority(self) -> int: ...
    @classmethod
    def new(cls) -> SettingHostname: ...

class SettingHostnameClass(_gi.Struct): ...

class SettingHsr(Setting):
    """
    :Constructors:

    ::

        SettingHsr(**properties)
        new() -> NM.Setting

    Object NMSettingHsr

    Properties from NMSettingHsr:
      port1 -> gchararray:

      port2 -> gchararray:

      multicast-spec -> guint:

      prp -> gboolean:

      protocol-version -> gint:

      interlink -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def interlink(self) -> str: ...
        @interlink.setter
        def interlink(self, value: str | None) -> None: ...
        multicast_spec: int
        @property
        def port1(self) -> str: ...
        @port1.setter
        def port1(self, value: str | None) -> None: ...
        @property
        def port2(self) -> str: ...
        @port2.setter
        def port2(self, value: str | None) -> None: ...
        protocol_version: int
        prp: bool

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        interlink: str | None = ...,
        multicast_spec: int = ...,
        port1: str | None = ...,
        port2: str | None = ...,
        protocol_version: int = ...,
        prp: bool = ...,
    ) -> None: ...
    def get_interlink(self) -> str: ...
    def get_multicast_spec(self) -> int: ...
    def get_port1(self) -> str: ...
    def get_port2(self) -> str: ...
    def get_protocol_version(self) -> SettingHsrProtocolVersion: ...
    def get_prp(self) -> bool: ...
    @classmethod
    def new(cls) -> SettingHsr: ...

class SettingHsrClass(_gi.Struct): ...

class SettingIP4Config(SettingIPConfig):
    """
    :Constructors:

    ::

        SettingIP4Config(**properties)
        new() -> NM.Setting

    Object NMSettingIP4Config

    Properties from NMSettingIP4Config:
      dhcp-client-id -> gchararray:

      dhcp-fqdn -> gchararray:

      dhcp-vendor-class-identifier -> gchararray:

      link-local -> gint:

      dhcp-ipv6-only-preferred -> gint:

      clat -> gint:


    Properties from NMSettingIPConfig:
      method -> gchararray:

      dns -> GStrv:

      dns-search -> GStrv:

      dns-options -> GStrv:

      dns-priority -> gint:

      addresses -> GPtrArray:

      gateway -> gchararray:

      routes -> GPtrArray:

      route-metric -> gint64:

      route-table -> guint:

      ignore-auto-routes -> gboolean:

      ignore-auto-dns -> gboolean:

      dhcp-hostname -> gchararray:

      dhcp-dscp -> gchararray:

      dhcp-hostname-flags -> guint:

      dhcp-send-hostname -> gboolean:

      dhcp-send-hostname-v2 -> gint:

      never-default -> gboolean:

      may-fail -> gboolean:

      dad-timeout -> gint:

      dhcp-timeout -> gint:

      required-timeout -> gint:

      dhcp-iaid -> gchararray:

      dhcp-reject-servers -> GStrv:

      auto-route-ext-gw -> NMTernary:

      replace-local-rule -> NMTernary:

      dhcp-send-release -> NMTernary:

      routed-dns -> gint:

      shared-dhcp-range -> gchararray:

      shared-dhcp-lease-time -> gint:

      forwarding -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(SettingIPConfig.Props):
        clat: int
        @property
        def dhcp_client_id(self) -> str: ...
        @dhcp_client_id.setter
        def dhcp_client_id(self, value: str | None) -> None: ...
        @property
        def dhcp_fqdn(self) -> str: ...
        @dhcp_fqdn.setter
        def dhcp_fqdn(self, value: str | None) -> None: ...
        dhcp_ipv6_only_preferred: int
        @property
        def dhcp_vendor_class_identifier(self) -> str: ...
        @dhcp_vendor_class_identifier.setter
        def dhcp_vendor_class_identifier(self, value: str | None) -> None: ...
        link_local: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        clat: int = ...,
        dhcp_client_id: str | None = ...,
        dhcp_fqdn: str | None = ...,
        dhcp_ipv6_only_preferred: int = ...,
        dhcp_vendor_class_identifier: str | None = ...,
        link_local: int = ...,
        addresses: Sequence[IPAddress] | None = ...,
        auto_route_ext_gw: _TernaryValueType = ...,
        dad_timeout: int = ...,
        dhcp_dscp: str | None = ...,
        dhcp_hostname: str | None = ...,
        dhcp_hostname_flags: int = ...,
        dhcp_iaid: str | None = ...,
        dhcp_reject_servers: Sequence[str] | None = ...,
        dhcp_send_hostname: bool = ...,
        dhcp_send_hostname_v2: int = ...,
        dhcp_send_release: _TernaryValueType = ...,
        dhcp_timeout: int = ...,
        dns: Sequence[str] | None = ...,
        dns_options: Sequence[str] | None = ...,
        dns_priority: int = ...,
        dns_search: Sequence[str] | None = ...,
        forwarding: int = ...,
        gateway: str | None = ...,
        ignore_auto_dns: bool = ...,
        ignore_auto_routes: bool = ...,
        may_fail: bool = ...,
        method: str | None = ...,
        never_default: bool = ...,
        replace_local_rule: _TernaryValueType = ...,
        required_timeout: int = ...,
        route_metric: int = ...,
        route_table: int = ...,
        routed_dns: int = ...,
        routes: Sequence[IPRoute] | None = ...,
        shared_dhcp_lease_time: int = ...,
        shared_dhcp_range: str | None = ...,
    ) -> None: ...
    def get_clat(self) -> SettingIp4ConfigClat: ...
    def get_dhcp_client_id(self) -> str: ...
    def get_dhcp_fqdn(self) -> str: ...
    def get_dhcp_ipv6_only_preferred(self) -> SettingIP4DhcpIpv6OnlyPreferred: ...
    def get_dhcp_vendor_class_identifier(self) -> str: ...
    def get_link_local(self) -> SettingIP4LinkLocal: ...
    @classmethod
    def new(cls) -> SettingIP4Config: ...

class SettingIP4ConfigClass(_gi.Struct): ...

class SettingIP6Config(SettingIPConfig):
    """
    :Constructors:

    ::

        SettingIP6Config(**properties)
        new() -> NM.Setting

    Object NMSettingIP6Config

    Properties from NMSettingIP6Config:
      ip6-privacy -> NMSettingIP6ConfigPrivacy:

      temp-valid-lifetime -> gint:

      temp-preferred-lifetime -> gint:

      addr-gen-mode -> gint:

      token -> gchararray:

      dhcp-duid -> gchararray:

      ra-timeout -> gint:

      mtu -> guint:

      dhcp-pd-hint -> gchararray:


    Properties from NMSettingIPConfig:
      method -> gchararray:

      dns -> GStrv:

      dns-search -> GStrv:

      dns-options -> GStrv:

      dns-priority -> gint:

      addresses -> GPtrArray:

      gateway -> gchararray:

      routes -> GPtrArray:

      route-metric -> gint64:

      route-table -> guint:

      ignore-auto-routes -> gboolean:

      ignore-auto-dns -> gboolean:

      dhcp-hostname -> gchararray:

      dhcp-dscp -> gchararray:

      dhcp-hostname-flags -> guint:

      dhcp-send-hostname -> gboolean:

      dhcp-send-hostname-v2 -> gint:

      never-default -> gboolean:

      may-fail -> gboolean:

      dad-timeout -> gint:

      dhcp-timeout -> gint:

      required-timeout -> gint:

      dhcp-iaid -> gchararray:

      dhcp-reject-servers -> GStrv:

      auto-route-ext-gw -> NMTernary:

      replace-local-rule -> NMTernary:

      dhcp-send-release -> NMTernary:

      routed-dns -> gint:

      shared-dhcp-range -> gchararray:

      shared-dhcp-lease-time -> gint:

      forwarding -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(SettingIPConfig.Props):
        addr_gen_mode: int
        @property
        def dhcp_duid(self) -> str: ...
        @dhcp_duid.setter
        def dhcp_duid(self, value: str | None) -> None: ...
        @property
        def dhcp_pd_hint(self) -> str: ...
        @dhcp_pd_hint.setter
        def dhcp_pd_hint(self, value: str | None) -> None: ...
        @property
        def ip6_privacy(self) -> SettingIP6ConfigPrivacy: ...
        @ip6_privacy.setter
        def ip6_privacy(self, value: _SettingIP6ConfigPrivacyValueType) -> None: ...
        mtu: int
        ra_timeout: int
        temp_preferred_lifetime: int
        temp_valid_lifetime: int
        @property
        def token(self) -> str: ...
        @token.setter
        def token(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        addr_gen_mode: int = ...,
        dhcp_duid: str | None = ...,
        dhcp_pd_hint: str | None = ...,
        ip6_privacy: _SettingIP6ConfigPrivacyValueType = ...,
        mtu: int = ...,
        ra_timeout: int = ...,
        temp_preferred_lifetime: int = ...,
        temp_valid_lifetime: int = ...,
        token: str | None = ...,
        addresses: Sequence[IPAddress] | None = ...,
        auto_route_ext_gw: _TernaryValueType = ...,
        dad_timeout: int = ...,
        dhcp_dscp: str | None = ...,
        dhcp_hostname: str | None = ...,
        dhcp_hostname_flags: int = ...,
        dhcp_iaid: str | None = ...,
        dhcp_reject_servers: Sequence[str] | None = ...,
        dhcp_send_hostname: bool = ...,
        dhcp_send_hostname_v2: int = ...,
        dhcp_send_release: _TernaryValueType = ...,
        dhcp_timeout: int = ...,
        dns: Sequence[str] | None = ...,
        dns_options: Sequence[str] | None = ...,
        dns_priority: int = ...,
        dns_search: Sequence[str] | None = ...,
        forwarding: int = ...,
        gateway: str | None = ...,
        ignore_auto_dns: bool = ...,
        ignore_auto_routes: bool = ...,
        may_fail: bool = ...,
        method: str | None = ...,
        never_default: bool = ...,
        replace_local_rule: _TernaryValueType = ...,
        required_timeout: int = ...,
        route_metric: int = ...,
        route_table: int = ...,
        routed_dns: int = ...,
        routes: Sequence[IPRoute] | None = ...,
        shared_dhcp_lease_time: int = ...,
        shared_dhcp_range: str | None = ...,
    ) -> None: ...
    def get_addr_gen_mode(self) -> SettingIP6ConfigAddrGenMode: ...
    def get_dhcp_duid(self) -> str: ...
    def get_dhcp_pd_hint(self) -> str: ...
    def get_ip6_privacy(self) -> SettingIP6ConfigPrivacy: ...
    def get_mtu(self) -> int: ...
    def get_ra_timeout(self) -> int: ...
    def get_temp_preferred_lifetime(self) -> int: ...
    def get_temp_valid_lifetime(self) -> int: ...
    def get_token(self) -> str: ...
    @classmethod
    def new(cls) -> SettingIP6Config: ...

class SettingIP6ConfigClass(_gi.Struct): ...

class SettingIPConfig(Setting):
    """
    :Constructors:

    ::

        SettingIPConfig(**properties)

    Object NMSettingIPConfig

    Properties from NMSettingIPConfig:
      method -> gchararray:

      dns -> GStrv:

      dns-search -> GStrv:

      dns-options -> GStrv:

      dns-priority -> gint:

      addresses -> GPtrArray:

      gateway -> gchararray:

      routes -> GPtrArray:

      route-metric -> gint64:

      route-table -> guint:

      ignore-auto-routes -> gboolean:

      ignore-auto-dns -> gboolean:

      dhcp-hostname -> gchararray:

      dhcp-dscp -> gchararray:

      dhcp-hostname-flags -> guint:

      dhcp-send-hostname -> gboolean:

      dhcp-send-hostname-v2 -> gint:

      never-default -> gboolean:

      may-fail -> gboolean:

      dad-timeout -> gint:

      dhcp-timeout -> gint:

      required-timeout -> gint:

      dhcp-iaid -> gchararray:

      dhcp-reject-servers -> GStrv:

      auto-route-ext-gw -> NMTernary:

      replace-local-rule -> NMTernary:

      dhcp-send-release -> NMTernary:

      routed-dns -> gint:

      shared-dhcp-range -> gchararray:

      shared-dhcp-lease-time -> gint:

      forwarding -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def addresses(self) -> list[IPAddress]: ...
        @addresses.setter
        def addresses(self, value: Sequence[IPAddress] | None) -> None: ...
        @property
        def auto_route_ext_gw(self) -> Ternary: ...
        @auto_route_ext_gw.setter
        def auto_route_ext_gw(self, value: _TernaryValueType) -> None: ...
        dad_timeout: int
        @property
        def dhcp_dscp(self) -> str: ...
        @dhcp_dscp.setter
        def dhcp_dscp(self, value: str | None) -> None: ...
        @property
        def dhcp_hostname(self) -> str: ...
        @dhcp_hostname.setter
        def dhcp_hostname(self, value: str | None) -> None: ...
        dhcp_hostname_flags: int
        @property
        def dhcp_iaid(self) -> str: ...
        @dhcp_iaid.setter
        def dhcp_iaid(self, value: str | None) -> None: ...
        @property
        def dhcp_reject_servers(self) -> list[str]: ...
        @dhcp_reject_servers.setter
        def dhcp_reject_servers(self, value: Sequence[str] | None) -> None: ...
        dhcp_send_hostname: bool
        dhcp_send_hostname_v2: int
        @property
        def dhcp_send_release(self) -> Ternary: ...
        @dhcp_send_release.setter
        def dhcp_send_release(self, value: _TernaryValueType) -> None: ...
        dhcp_timeout: int
        @property
        def dns(self) -> list[str]: ...
        @dns.setter
        def dns(self, value: Sequence[str] | None) -> None: ...
        @property
        def dns_options(self) -> list[str]: ...
        @dns_options.setter
        def dns_options(self, value: Sequence[str] | None) -> None: ...
        dns_priority: int
        @property
        def dns_search(self) -> list[str]: ...
        @dns_search.setter
        def dns_search(self, value: Sequence[str] | None) -> None: ...
        forwarding: int
        @property
        def gateway(self) -> str: ...
        @gateway.setter
        def gateway(self, value: str | None) -> None: ...
        ignore_auto_dns: bool
        ignore_auto_routes: bool
        may_fail: bool
        @property
        def method(self) -> str: ...
        @method.setter
        def method(self, value: str | None) -> None: ...
        never_default: bool
        @property
        def replace_local_rule(self) -> Ternary: ...
        @replace_local_rule.setter
        def replace_local_rule(self, value: _TernaryValueType) -> None: ...
        required_timeout: int
        route_metric: int
        route_table: int
        routed_dns: int
        @property
        def routes(self) -> list[IPRoute]: ...
        @routes.setter
        def routes(self, value: Sequence[IPRoute] | None) -> None: ...
        shared_dhcp_lease_time: int
        @property
        def shared_dhcp_range(self) -> str: ...
        @shared_dhcp_range.setter
        def shared_dhcp_range(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        addresses: Sequence[IPAddress] | None = ...,
        auto_route_ext_gw: _TernaryValueType = ...,
        dad_timeout: int = ...,
        dhcp_dscp: str | None = ...,
        dhcp_hostname: str | None = ...,
        dhcp_hostname_flags: int = ...,
        dhcp_iaid: str | None = ...,
        dhcp_reject_servers: Sequence[str] | None = ...,
        dhcp_send_hostname: bool = ...,
        dhcp_send_hostname_v2: int = ...,
        dhcp_send_release: _TernaryValueType = ...,
        dhcp_timeout: int = ...,
        dns: Sequence[str] | None = ...,
        dns_options: Sequence[str] | None = ...,
        dns_priority: int = ...,
        dns_search: Sequence[str] | None = ...,
        forwarding: int = ...,
        gateway: str | None = ...,
        ignore_auto_dns: bool = ...,
        ignore_auto_routes: bool = ...,
        may_fail: bool = ...,
        method: str | None = ...,
        never_default: bool = ...,
        replace_local_rule: _TernaryValueType = ...,
        required_timeout: int = ...,
        route_metric: int = ...,
        route_table: int = ...,
        routed_dns: int = ...,
        routes: Sequence[IPRoute] | None = ...,
        shared_dhcp_lease_time: int = ...,
        shared_dhcp_range: str | None = ...,
    ) -> None: ...
    def add_address(self, address: IPAddress) -> bool: ...
    def add_dhcp_reject_server(self, server: str) -> None: ...
    def add_dns(self, dns: str) -> bool: ...
    def add_dns_option(self, dns_option: str) -> bool: ...
    def add_dns_search(self, dns_search: str) -> bool: ...
    def add_route(self, route: IPRoute) -> bool: ...
    def add_routing_rule(self, routing_rule: IPRoutingRule) -> None: ...
    def clear_addresses(self) -> None: ...
    def clear_dhcp_reject_servers(self) -> None: ...
    def clear_dns(self) -> None: ...
    def clear_dns_options(self, is_set: bool) -> None: ...
    def clear_dns_searches(self) -> None: ...
    def clear_routes(self) -> None: ...
    def clear_routing_rules(self) -> None: ...
    def get_address(self, idx: int) -> IPAddress: ...
    def get_auto_route_ext_gw(self) -> Ternary: ...
    def get_dad_timeout(self) -> int: ...
    def get_dhcp_dscp(self) -> str: ...
    def get_dhcp_hostname(self) -> str: ...
    def get_dhcp_hostname_flags(self) -> DhcpHostnameFlags: ...
    def get_dhcp_iaid(self) -> str: ...
    def get_dhcp_reject_servers(self) -> list[str]: ...
    def get_dhcp_send_hostname(self) -> bool: ...
    def get_dhcp_send_hostname_v2(self) -> Ternary: ...
    def get_dhcp_send_release(self) -> Ternary: ...
    def get_dhcp_timeout(self) -> int: ...
    def get_dns(self, idx: int) -> str: ...
    def get_dns_option(self, idx: int) -> str: ...
    def get_dns_priority(self) -> int: ...
    def get_dns_search(self, idx: int) -> str: ...
    def get_forwarding(self) -> SettingIPConfigForwarding: ...
    def get_gateway(self) -> str: ...
    def get_ignore_auto_dns(self) -> bool: ...
    def get_ignore_auto_routes(self) -> bool: ...
    def get_may_fail(self) -> bool: ...
    def get_method(self) -> str: ...
    def get_never_default(self) -> bool: ...
    def get_num_addresses(self) -> int: ...
    def get_num_dns(self) -> int: ...
    def get_num_dns_options(self) -> int: ...
    def get_num_dns_searches(self) -> int: ...
    def get_num_routes(self) -> int: ...
    def get_num_routing_rules(self) -> int: ...
    def get_replace_local_rule(self) -> Ternary: ...
    def get_required_timeout(self) -> int: ...
    def get_route(self, idx: int) -> IPRoute: ...
    def get_route_metric(self) -> int: ...
    def get_route_table(self) -> int: ...
    def get_routed_dns(self) -> SettingIPConfigRoutedDns: ...
    def get_routing_rule(self, idx: int) -> IPRoutingRule: ...
    def get_shared_dhcp_lease_time(self) -> int: ...
    def get_shared_dhcp_range(self) -> str: ...
    def has_dns_options(self) -> bool: ...
    def remove_address(self, idx: int) -> None: ...
    def remove_address_by_value(self, address: IPAddress) -> bool: ...
    def remove_dhcp_reject_server(self, idx: int) -> None: ...
    def remove_dns(self, idx: int) -> None: ...
    def remove_dns_by_value(self, dns: str) -> bool: ...
    def remove_dns_option(self, idx: int) -> None: ...
    def remove_dns_option_by_value(self, dns_option: str) -> bool: ...
    def remove_dns_search(self, idx: int) -> None: ...
    def remove_dns_search_by_value(self, dns_search: str) -> bool: ...
    def remove_route(self, idx: int) -> None: ...
    def remove_route_by_value(self, route: IPRoute) -> bool: ...
    def remove_routing_rule(self, idx: int) -> None: ...

class SettingIPConfigClass(_gi.Struct): ...

class SettingIPTunnel(Setting):
    """
    :Constructors:

    ::

        SettingIPTunnel(**properties)
        new() -> NM.Setting

    Object NMSettingIPTunnel

    Properties from NMSettingIPTunnel:
      parent -> gchararray:

      mode -> guint:

      local -> gchararray:

      remote -> gchararray:

      ttl -> guint:

      tos -> guint:

      path-mtu-discovery -> gboolean:

      input-key -> gchararray:

      output-key -> gchararray:

      encapsulation-limit -> guint:

      flow-label -> guint:

      fwmark -> guint:

      mtu -> guint:

      flags -> guint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        encapsulation_limit: int
        flags: int
        flow_label: int
        fwmark: int
        @property
        def input_key(self) -> str: ...
        @input_key.setter
        def input_key(self, value: str | None) -> None: ...
        @property
        def local(self) -> str: ...
        @local.setter
        def local(self, value: str | None) -> None: ...
        mode: int
        mtu: int
        @property
        def output_key(self) -> str: ...
        @output_key.setter
        def output_key(self, value: str | None) -> None: ...
        @property
        def parent(self) -> str: ...
        @parent.setter
        def parent(self, value: str | None) -> None: ...
        path_mtu_discovery: bool
        @property
        def remote(self) -> str: ...
        @remote.setter
        def remote(self, value: str | None) -> None: ...
        tos: int
        ttl: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        encapsulation_limit: int = ...,
        flags: int = ...,
        flow_label: int = ...,
        fwmark: int = ...,
        input_key: str | None = ...,
        local: str | None = ...,
        mode: int = ...,
        mtu: int = ...,
        output_key: str | None = ...,
        parent: str | None = ...,
        path_mtu_discovery: bool = ...,
        remote: str | None = ...,
        tos: int = ...,
        ttl: int = ...,
    ) -> None: ...
    def get_encapsulation_limit(self) -> int: ...
    def get_flags(self) -> IPTunnelFlags: ...
    def get_flow_label(self) -> int: ...
    def get_fwmark(self) -> int: ...
    def get_input_key(self) -> str: ...
    def get_local(self) -> str: ...
    def get_mode(self) -> IPTunnelMode: ...
    def get_mtu(self) -> int: ...
    def get_output_key(self) -> str: ...
    def get_parent(self) -> str: ...
    def get_path_mtu_discovery(self) -> bool: ...
    def get_remote(self) -> str: ...
    def get_tos(self) -> int: ...
    def get_ttl(self) -> int: ...
    @classmethod
    def new(cls) -> SettingIPTunnel: ...

class SettingIPTunnelClass(_gi.Struct): ...

class SettingInfiniband(Setting):
    """
    :Constructors:

    ::

        SettingInfiniband(**properties)
        new() -> NM.Setting

    Object NMSettingInfiniband

    Properties from NMSettingInfiniband:
      mac-address -> gchararray:

      mtu -> guint:

      transport-mode -> gchararray:

      p-key -> gint:

      parent -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def mac_address(self) -> str: ...
        @mac_address.setter
        def mac_address(self, value: str | None) -> None: ...
        mtu: int
        p_key: int
        @property
        def parent(self) -> str: ...
        @parent.setter
        def parent(self, value: str | None) -> None: ...
        @property
        def transport_mode(self) -> str: ...
        @transport_mode.setter
        def transport_mode(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        mac_address: str | None = ...,
        mtu: int = ...,
        p_key: int = ...,
        parent: str | None = ...,
        transport_mode: str | None = ...,
    ) -> None: ...
    def get_mac_address(self) -> str: ...
    def get_mtu(self) -> int: ...
    def get_p_key(self) -> int: ...
    def get_parent(self) -> str: ...
    def get_transport_mode(self) -> str: ...
    def get_virtual_interface_name(self) -> str: ...
    @classmethod
    def new(cls) -> SettingInfiniband: ...

class SettingInfinibandClass(_gi.Struct): ...

class SettingIpvlan(Setting):
    """
    :Constructors:

    ::

        SettingIpvlan(**properties)
        new() -> NM.Setting

    Object NMSettingIpvlan

    Properties from NMSettingIpvlan:
      parent -> gchararray:

      mode -> guint:

      private -> gboolean:

      vepa -> gboolean:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        mode: int
        @property
        def parent(self) -> str: ...
        @parent.setter
        def parent(self, value: str | None) -> None: ...
        private: bool
        vepa: bool

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        mode: int = ...,
        parent: str | None = ...,
        private: bool = ...,
        vepa: bool = ...,
    ) -> None: ...
    def get_mode(self) -> SettingIpvlanMode: ...
    def get_parent(self) -> str: ...
    def get_private(self) -> bool: ...
    def get_vepa(self) -> bool: ...
    @classmethod
    def new(cls) -> SettingIpvlan: ...

class SettingIpvlanClass(_gi.Struct): ...

class SettingLink(Setting):
    """
    :Constructors:

    ::

        SettingLink(**properties)
        new() -> NM.Setting

    Object NMSettingLink

    Properties from NMSettingLink:
      tx-queue-length -> gint64:

      gso-max-size -> gint64:

      gso-max-segments -> gint64:

      gro-max-size -> gint64:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        gro_max_size: int
        gso_max_segments: int
        gso_max_size: int
        tx_queue_length: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        gro_max_size: int = ...,
        gso_max_segments: int = ...,
        gso_max_size: int = ...,
        tx_queue_length: int = ...,
    ) -> None: ...
    def get_gro_max_size(self) -> int: ...
    def get_gso_max_segments(self) -> int: ...
    def get_gso_max_size(self) -> int: ...
    def get_tx_queue_length(self) -> int: ...
    @classmethod
    def new(cls) -> SettingLink: ...

class SettingLinkClass(_gi.Struct): ...

class SettingLoopback(Setting):
    """
    :Constructors:

    ::

        SettingLoopback(**properties)
        new() -> NM.Setting

    Object NMSettingLoopback

    Properties from NMSettingLoopback:
      mtu -> guint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        mtu: int

    @property
    def props(self) -> Props: ...
    def __init__(self, *, mtu: int = ...) -> None: ...
    def get_mtu(self) -> int: ...
    @classmethod
    def new(cls) -> SettingLoopback: ...

class SettingLoopbackClass(_gi.Struct): ...

class SettingMacsec(Setting):
    """
    :Constructors:

    ::

        SettingMacsec(**properties)
        new() -> NM.Setting

    Object NMSettingMacsec

    Properties from NMSettingMacsec:
      parent -> gchararray:

      mode -> gint:

      encrypt -> gboolean:

      mka-cak -> gchararray:

      mka-cak-flags -> NMSettingSecretFlags:

      mka-ckn -> gchararray:

      port -> gint:

      validation -> gint:

      send-sci -> gboolean:

      offload -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        encrypt: bool
        @property
        def mka_cak(self) -> str: ...
        @mka_cak.setter
        def mka_cak(self, value: str | None) -> None: ...
        @property
        def mka_cak_flags(self) -> SettingSecretFlags: ...
        @mka_cak_flags.setter
        def mka_cak_flags(self, value: _SettingSecretFlagsValueType) -> None: ...
        @property
        def mka_ckn(self) -> str: ...
        @mka_ckn.setter
        def mka_ckn(self, value: str | None) -> None: ...
        mode: int
        offload: int
        @property
        def parent(self) -> str: ...
        @parent.setter
        def parent(self, value: str | None) -> None: ...
        port: int
        send_sci: bool
        validation: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        encrypt: bool = ...,
        mka_cak: str | None = ...,
        mka_cak_flags: _SettingSecretFlagsValueType = ...,
        mka_ckn: str | None = ...,
        mode: int = ...,
        offload: int = ...,
        parent: str | None = ...,
        port: int = ...,
        send_sci: bool = ...,
        validation: int = ...,
    ) -> None: ...
    def get_encrypt(self) -> bool: ...
    def get_mka_cak(self) -> str: ...
    def get_mka_cak_flags(self) -> SettingSecretFlags: ...
    def get_mka_ckn(self) -> str: ...
    def get_mode(self) -> SettingMacsecMode: ...
    def get_offload(self) -> SettingMacsecOffload: ...
    def get_parent(self) -> str: ...
    def get_port(self) -> int: ...
    def get_send_sci(self) -> bool: ...
    def get_validation(self) -> SettingMacsecValidation: ...
    @classmethod
    def new(cls) -> SettingMacsec: ...

class SettingMacsecClass(_gi.Struct): ...

class SettingMacvlan(Setting):
    """
    :Constructors:

    ::

        SettingMacvlan(**properties)
        new() -> NM.Setting

    Object NMSettingMacvlan

    Properties from NMSettingMacvlan:
      parent -> gchararray:

      mode -> guint:

      promiscuous -> gboolean:

      tap -> gboolean:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        mode: int
        @property
        def parent(self) -> str: ...
        @parent.setter
        def parent(self, value: str | None) -> None: ...
        promiscuous: bool
        tap: bool

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        mode: int = ...,
        parent: str | None = ...,
        promiscuous: bool = ...,
        tap: bool = ...,
    ) -> None: ...
    def get_mode(self) -> SettingMacvlanMode: ...
    def get_parent(self) -> str: ...
    def get_promiscuous(self) -> bool: ...
    def get_tap(self) -> bool: ...
    @classmethod
    def new(cls) -> SettingMacvlan: ...

class SettingMacvlanClass(_gi.Struct): ...

class SettingMatch(Setting):
    """
    :Constructors:

    ::

        SettingMatch(**properties)
        new() -> NM.Setting

    Object NMSettingMatch

    Properties from NMSettingMatch:
      interface-name -> GStrv:

      kernel-command-line -> GStrv:

      driver -> GStrv:

      path -> GStrv:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def driver(self) -> list[str]: ...
        @driver.setter
        def driver(self, value: Sequence[str] | None) -> None: ...
        @property
        def interface_name(self) -> list[str]: ...
        @interface_name.setter
        def interface_name(self, value: Sequence[str] | None) -> None: ...
        @property
        def kernel_command_line(self) -> list[str]: ...
        @kernel_command_line.setter
        def kernel_command_line(self, value: Sequence[str] | None) -> None: ...
        @property
        def path(self) -> list[str]: ...
        @path.setter
        def path(self, value: Sequence[str] | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        driver: Sequence[str] | None = ...,
        interface_name: Sequence[str] | None = ...,
        kernel_command_line: Sequence[str] | None = ...,
        path: Sequence[str] | None = ...,
    ) -> None: ...
    def add_driver(self, driver: str) -> None: ...
    def add_interface_name(self, interface_name: str) -> None: ...
    def add_kernel_command_line(self, kernel_command_line: str) -> None: ...
    def add_path(self, path: str) -> None: ...
    def clear_drivers(self) -> None: ...
    def clear_interface_names(self) -> None: ...
    def clear_kernel_command_lines(self) -> None: ...
    def clear_paths(self) -> None: ...
    def get_driver(self, idx: int) -> str: ...
    def get_drivers(self) -> list[str]: ...
    def get_interface_name(self, idx: int) -> str: ...
    def get_interface_names(self) -> list[str]: ...
    def get_kernel_command_line(self, idx: int) -> str: ...
    def get_kernel_command_lines(self) -> list[str]: ...
    def get_num_drivers(self) -> int: ...
    def get_num_interface_names(self) -> int: ...
    def get_num_kernel_command_lines(self) -> int: ...
    def get_num_paths(self) -> int: ...
    def get_path(self, idx: int) -> str: ...
    def get_paths(self) -> list[str]: ...
    @classmethod
    def new(cls) -> SettingMatch: ...
    def remove_driver(self, idx: int) -> None: ...
    def remove_driver_by_value(self, driver: str) -> bool: ...
    def remove_interface_name(self, idx: int) -> None: ...
    def remove_interface_name_by_value(self, interface_name: str) -> bool: ...
    def remove_kernel_command_line(self, idx: int) -> None: ...
    def remove_kernel_command_line_by_value(self, kernel_command_line: str) -> bool: ...
    def remove_path(self, idx: int) -> None: ...
    def remove_path_by_value(self, path: str) -> bool: ...

class SettingMatchClass(_gi.Struct): ...

class SettingOlpcMesh(Setting):
    """
    :Constructors:

    ::

        SettingOlpcMesh(**properties)
        new() -> NM.Setting

    Object NMSettingOlpcMesh

    Properties from NMSettingOlpcMesh:
      ssid -> GBytes:

      channel -> guint:

      dhcp-anycast-address -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        channel: int
        @property
        def dhcp_anycast_address(self) -> str: ...
        @dhcp_anycast_address.setter
        def dhcp_anycast_address(self, value: str | None) -> None: ...
        @property
        def ssid(self) -> GLib.Bytes: ...
        @ssid.setter
        def ssid(self, value: GLib.Bytes | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        channel: int = ...,
        dhcp_anycast_address: str | None = ...,
        ssid: GLib.Bytes | None = ...,
    ) -> None: ...
    def get_channel(self) -> int: ...
    def get_dhcp_anycast_address(self) -> str: ...
    def get_ssid(self) -> GLib.Bytes: ...
    @classmethod
    def new(cls) -> SettingOlpcMesh: ...

class SettingOlpcMeshClass(_gi.Struct): ...

class SettingOvsBridge(Setting):
    """
    :Constructors:

    ::

        SettingOvsBridge(**properties)
        new() -> NM.Setting

    Object NMSettingOvsBridge

    Properties from NMSettingOvsBridge:
      fail-mode -> gchararray:

      mcast-snooping-enable -> gboolean:

      rstp-enable -> gboolean:

      stp-enable -> gboolean:

      datapath-type -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def datapath_type(self) -> str: ...
        @datapath_type.setter
        def datapath_type(self, value: str | None) -> None: ...
        @property
        def fail_mode(self) -> str: ...
        @fail_mode.setter
        def fail_mode(self, value: str | None) -> None: ...
        mcast_snooping_enable: bool
        rstp_enable: bool
        stp_enable: bool

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        datapath_type: str | None = ...,
        fail_mode: str | None = ...,
        mcast_snooping_enable: bool = ...,
        rstp_enable: bool = ...,
        stp_enable: bool = ...,
    ) -> None: ...
    def get_datapath_type(self) -> str: ...
    def get_fail_mode(self) -> str: ...
    def get_mcast_snooping_enable(self) -> bool: ...
    def get_rstp_enable(self) -> bool: ...
    def get_stp_enable(self) -> bool: ...
    @classmethod
    def new(cls) -> SettingOvsBridge: ...

class SettingOvsBridgeClass(_gi.Struct): ...

class SettingOvsDpdk(Setting):
    """
    :Constructors:

    ::

        SettingOvsDpdk(**properties)
        new() -> NM.Setting

    Object NMSettingOvsDpdk

    Properties from NMSettingOvsDpdk:
      devargs -> gchararray:

      n-rxq -> guint:

      n-rxq-desc -> guint:

      n-txq-desc -> guint:

      lsc-interrupt -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def devargs(self) -> str: ...
        @devargs.setter
        def devargs(self, value: str | None) -> None: ...
        lsc_interrupt: int
        n_rxq: int
        n_rxq_desc: int
        n_txq_desc: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        devargs: str | None = ...,
        lsc_interrupt: int = ...,
        n_rxq: int = ...,
        n_rxq_desc: int = ...,
        n_txq_desc: int = ...,
    ) -> None: ...
    def get_devargs(self) -> str: ...
    def get_lsc_interrupt(self) -> SettingOvsDpdkLscInterrupt: ...
    def get_n_rxq(self) -> int: ...
    def get_n_rxq_desc(self) -> int: ...
    def get_n_txq_desc(self) -> int: ...
    @classmethod
    def new(cls) -> SettingOvsDpdk: ...

class SettingOvsDpdkClass(_gi.Struct): ...

class SettingOvsExternalIDs(Setting):
    """
    :Constructors:

    ::

        SettingOvsExternalIDs(**properties)
        new() -> NM.SettingOvsExternalIDs

    Object NMSettingOvsExternalIDs

    Properties from NMSettingOvsExternalIDs:
      data -> GHashTable:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def data(self) -> dict[str, str]: ...
        @data.setter
        def data(self, value: Mapping[str, str]) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, data: Mapping[str, str] = ...) -> None: ...
    @staticmethod
    def check_key(key: str | None = None) -> bool: ...
    @staticmethod
    def check_val(val: str | None = None) -> bool: ...
    def get_data(self, key: str) -> str: ...
    def get_data_keys(self) -> list[str]: ...
    @classmethod
    def new(cls) -> SettingOvsExternalIDs: ...
    def set_data(self, key: str, val: str | None = None) -> None: ...

class SettingOvsExternalIDsClass(_gi.Struct): ...

class SettingOvsInterface(Setting):
    """
    :Constructors:

    ::

        SettingOvsInterface(**properties)
        new() -> NM.Setting

    Object NMSettingOvsInterface

    Properties from NMSettingOvsInterface:
      type -> gchararray:

      ofport-request -> guint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        ofport_request: int
        type: str | None

    @property
    def props(self) -> Props: ...
    def __init__(
        self, *, ofport_request: int = ..., type: str | None = ...
    ) -> None: ...
    def get_interface_type(self) -> str: ...
    def get_ofport_request(self) -> int: ...
    @classmethod
    def new(cls) -> SettingOvsInterface: ...

class SettingOvsInterfaceClass(_gi.Struct): ...

class SettingOvsOtherConfig(Setting):
    """
    :Constructors:

    ::

        SettingOvsOtherConfig(**properties)
        new() -> NM.SettingOvsOtherConfig

    Object NMSettingOvsOtherConfig

    Properties from NMSettingOvsOtherConfig:
      data -> GHashTable:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def data(self) -> dict[str, str]: ...
        @data.setter
        def data(self, value: Mapping[str, str]) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, data: Mapping[str, str] = ...) -> None: ...
    def get_data(self, key: str) -> str: ...
    def get_data_keys(self) -> list[str]: ...
    @classmethod
    def new(cls) -> SettingOvsOtherConfig: ...
    def set_data(self, key: str, val: str | None = None) -> None: ...

class SettingOvsOtherConfigClass(_gi.Struct): ...

class SettingOvsPatch(Setting):
    """
    :Constructors:

    ::

        SettingOvsPatch(**properties)
        new() -> NM.Setting

    Object NMSettingOvsPatch

    Properties from NMSettingOvsPatch:
      peer -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def peer(self) -> str: ...
        @peer.setter
        def peer(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, peer: str | None = ...) -> None: ...
    def get_peer(self) -> str: ...
    @classmethod
    def new(cls) -> SettingOvsPatch: ...

class SettingOvsPatchClass(_gi.Struct): ...

class SettingOvsPort(Setting):
    """
    :Constructors:

    ::

        SettingOvsPort(**properties)
        new() -> NM.Setting

    Object NMSettingOvsPort

    Properties from NMSettingOvsPort:
      vlan-mode -> gchararray:

      tag -> guint:

      trunks -> GPtrArray:

      lacp -> gchararray:

      bond-mode -> gchararray:

      bond-updelay -> guint:

      bond-downdelay -> guint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        bond_downdelay: int
        @property
        def bond_mode(self) -> str: ...
        @bond_mode.setter
        def bond_mode(self, value: str | None) -> None: ...
        bond_updelay: int
        @property
        def lacp(self) -> str: ...
        @lacp.setter
        def lacp(self, value: str | None) -> None: ...
        tag: int
        @property
        def trunks(self) -> list[Range]: ...
        @trunks.setter
        def trunks(self, value: Sequence[Range] | None) -> None: ...
        @property
        def vlan_mode(self) -> str: ...
        @vlan_mode.setter
        def vlan_mode(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        bond_downdelay: int = ...,
        bond_mode: str | None = ...,
        bond_updelay: int = ...,
        lacp: str | None = ...,
        tag: int = ...,
        trunks: Sequence[Range] | None = ...,
        vlan_mode: str | None = ...,
    ) -> None: ...
    def add_trunk(self, trunk: Range) -> None: ...
    def clear_trunks(self) -> None: ...
    def get_bond_downdelay(self) -> int: ...
    def get_bond_mode(self) -> str: ...
    def get_bond_updelay(self) -> int: ...
    def get_lacp(self) -> str: ...
    def get_num_trunks(self) -> int: ...
    def get_tag(self) -> int: ...
    def get_trunk(self, idx: int) -> Range: ...
    def get_vlan_mode(self) -> str: ...
    @classmethod
    def new(cls) -> SettingOvsPort: ...
    def remove_trunk(self, idx: int) -> None: ...
    def remove_trunk_by_value(self, start: int, end: int) -> bool: ...

class SettingOvsPortClass(_gi.Struct): ...

class SettingPpp(Setting):
    """
    :Constructors:

    ::

        SettingPpp(**properties)
        new() -> NM.Setting

    Object NMSettingPpp

    Properties from NMSettingPpp:
      noauth -> gboolean:

      refuse-eap -> gboolean:

      refuse-pap -> gboolean:

      refuse-chap -> gboolean:

      refuse-mschap -> gboolean:

      refuse-mschapv2 -> gboolean:

      nobsdcomp -> gboolean:

      nodeflate -> gboolean:

      no-vj-comp -> gboolean:

      require-mppe -> gboolean:

      require-mppe-128 -> gboolean:

      mppe-stateful -> gboolean:

      crtscts -> gboolean:

      baud -> guint:

      mru -> guint:

      mtu -> guint:

      lcp-echo-failure -> guint:

      lcp-echo-interval -> guint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        baud: int
        crtscts: bool
        lcp_echo_failure: int
        lcp_echo_interval: int
        mppe_stateful: bool
        mru: int
        mtu: int
        no_vj_comp: bool
        noauth: bool
        nobsdcomp: bool
        nodeflate: bool
        refuse_chap: bool
        refuse_eap: bool
        refuse_mschap: bool
        refuse_mschapv2: bool
        refuse_pap: bool
        require_mppe: bool
        require_mppe_128: bool

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        baud: int = ...,
        crtscts: bool = ...,
        lcp_echo_failure: int = ...,
        lcp_echo_interval: int = ...,
        mppe_stateful: bool = ...,
        mru: int = ...,
        mtu: int = ...,
        no_vj_comp: bool = ...,
        noauth: bool = ...,
        nobsdcomp: bool = ...,
        nodeflate: bool = ...,
        refuse_chap: bool = ...,
        refuse_eap: bool = ...,
        refuse_mschap: bool = ...,
        refuse_mschapv2: bool = ...,
        refuse_pap: bool = ...,
        require_mppe: bool = ...,
        require_mppe_128: bool = ...,
    ) -> None: ...
    def get_baud(self) -> int: ...
    def get_crtscts(self) -> bool: ...
    def get_lcp_echo_failure(self) -> int: ...
    def get_lcp_echo_interval(self) -> int: ...
    def get_mppe_stateful(self) -> bool: ...
    def get_mru(self) -> int: ...
    def get_mtu(self) -> int: ...
    def get_no_vj_comp(self) -> bool: ...
    def get_noauth(self) -> bool: ...
    def get_nobsdcomp(self) -> bool: ...
    def get_nodeflate(self) -> bool: ...
    def get_refuse_chap(self) -> bool: ...
    def get_refuse_eap(self) -> bool: ...
    def get_refuse_mschap(self) -> bool: ...
    def get_refuse_mschapv2(self) -> bool: ...
    def get_refuse_pap(self) -> bool: ...
    def get_require_mppe(self) -> bool: ...
    def get_require_mppe_128(self) -> bool: ...
    @classmethod
    def new(cls) -> SettingPpp: ...

class SettingPppClass(_gi.Struct): ...

class SettingPppoe(Setting):
    """
    :Constructors:

    ::

        SettingPppoe(**properties)
        new() -> NM.Setting

    Object NMSettingPppoe

    Properties from NMSettingPppoe:
      parent -> gchararray:

      service -> gchararray:

      username -> gchararray:

      password -> gchararray:

      password-flags -> NMSettingSecretFlags:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def parent(self) -> str: ...
        @parent.setter
        def parent(self, value: str | None) -> None: ...
        @property
        def password(self) -> str: ...
        @password.setter
        def password(self, value: str | None) -> None: ...
        @property
        def password_flags(self) -> SettingSecretFlags: ...
        @password_flags.setter
        def password_flags(self, value: _SettingSecretFlagsValueType) -> None: ...
        @property
        def service(self) -> str: ...
        @service.setter
        def service(self, value: str | None) -> None: ...
        @property
        def username(self) -> str: ...
        @username.setter
        def username(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        parent: str | None = ...,
        password: str | None = ...,
        password_flags: _SettingSecretFlagsValueType = ...,
        service: str | None = ...,
        username: str | None = ...,
    ) -> None: ...
    def get_parent(self) -> str: ...
    def get_password(self) -> str: ...
    def get_password_flags(self) -> SettingSecretFlags: ...
    def get_service(self) -> str: ...
    def get_username(self) -> str: ...
    @classmethod
    def new(cls) -> SettingPppoe: ...

class SettingPppoeClass(_gi.Struct): ...

class SettingPrefixDelegation(Setting):
    """
    :Constructors:

    ::

        SettingPrefixDelegation(**properties)
        new() -> NM.Setting

    Object NMSettingPrefixDelegation

    Properties from NMSettingPrefixDelegation:
      subnet-id -> gint64:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        subnet_id: int

    @property
    def props(self) -> Props: ...
    def __init__(self, *, subnet_id: int = ...) -> None: ...
    def get_subnet_id(self) -> int: ...
    @classmethod
    def new(cls) -> SettingPrefixDelegation: ...

class SettingPrefixDelegationClass(_gi.Struct): ...

class SettingProxy(Setting):
    """
    :Constructors:

    ::

        SettingProxy(**properties)
        new() -> NM.Setting

    Object NMSettingProxy

    Properties from NMSettingProxy:
      method -> gint:

      browser-only -> gboolean:

      pac-url -> gchararray:

      pac-script -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        browser_only: bool
        method: int
        @property
        def pac_script(self) -> str: ...
        @pac_script.setter
        def pac_script(self, value: str | None) -> None: ...
        @property
        def pac_url(self) -> str: ...
        @pac_url.setter
        def pac_url(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        browser_only: bool = ...,
        method: int = ...,
        pac_script: str | None = ...,
        pac_url: str | None = ...,
    ) -> None: ...
    def get_browser_only(self) -> bool: ...
    def get_method(self) -> SettingProxyMethod: ...
    def get_pac_script(self) -> str: ...
    def get_pac_url(self) -> str: ...
    @classmethod
    def new(cls) -> SettingProxy: ...

class SettingProxyClass(_gi.Struct): ...

class SettingSerial(Setting):
    """
    :Constructors:

    ::

        SettingSerial(**properties)
        new() -> NM.Setting

    Object NMSettingSerial

    Properties from NMSettingSerial:
      baud -> guint:

      bits -> guint:

      parity -> NMSettingSerialParity:

      stopbits -> guint:

      send-delay -> guint64:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        baud: int
        bits: int
        @property
        def parity(self) -> SettingSerialParity: ...
        @parity.setter
        def parity(self, value: _SettingSerialParityValueType) -> None: ...
        send_delay: int
        stopbits: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        baud: int = ...,
        bits: int = ...,
        parity: _SettingSerialParityValueType = ...,
        send_delay: int = ...,
        stopbits: int = ...,
    ) -> None: ...
    def get_baud(self) -> int: ...
    def get_bits(self) -> int: ...
    def get_parity(self) -> SettingSerialParity: ...
    def get_send_delay(self) -> int: ...
    def get_stopbits(self) -> int: ...
    @classmethod
    def new(cls) -> SettingSerial: ...

class SettingSerialClass(_gi.Struct): ...

class SettingSriov(Setting):
    """
    :Constructors:

    ::

        SettingSriov(**properties)
        new() -> NM.Setting

    Object NMSettingSriov

    Properties from NMSettingSriov:
      total-vfs -> guint:

      vfs -> GPtrArray:

      preserve-on-down -> gint:

      autoprobe-drivers -> NMTernary:

      eswitch-mode -> gint:

      eswitch-inline-mode -> gint:

      eswitch-encap-mode -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def autoprobe_drivers(self) -> Ternary: ...
        @autoprobe_drivers.setter
        def autoprobe_drivers(self, value: _TernaryValueType) -> None: ...
        eswitch_encap_mode: int
        eswitch_inline_mode: int
        eswitch_mode: int
        preserve_on_down: int
        total_vfs: int
        @property
        def vfs(self) -> list[SriovVF]: ...
        @vfs.setter
        def vfs(self, value: Sequence[SriovVF] | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        autoprobe_drivers: _TernaryValueType = ...,
        eswitch_encap_mode: int = ...,
        eswitch_inline_mode: int = ...,
        eswitch_mode: int = ...,
        preserve_on_down: int = ...,
        total_vfs: int = ...,
        vfs: Sequence[SriovVF] | None = ...,
    ) -> None: ...
    def add_vf(self, vf: SriovVF) -> None: ...
    def clear_vfs(self) -> None: ...
    def get_autoprobe_drivers(self) -> Ternary: ...
    def get_eswitch_encap_mode(self) -> SriovEswitchEncapMode: ...
    def get_eswitch_inline_mode(self) -> SriovEswitchInlineMode: ...
    def get_eswitch_mode(self) -> SriovEswitchMode: ...
    def get_num_vfs(self) -> int: ...
    def get_preserve_on_down(self) -> SriovPreserveOnDown: ...
    def get_total_vfs(self) -> int: ...
    def get_vf(self, idx: int) -> SriovVF: ...
    @classmethod
    def new(cls) -> SettingSriov: ...
    def remove_vf(self, idx: int) -> None: ...
    def remove_vf_by_index(self, index: int) -> bool: ...

class SettingSriovClass(_gi.Struct): ...

class SettingTCConfig(Setting):
    """
    :Constructors:

    ::

        SettingTCConfig(**properties)
        new() -> NM.Setting

    Object NMSettingTCConfig

    Properties from NMSettingTCConfig:
      qdiscs -> GPtrArray:

      tfilters -> GPtrArray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def qdiscs(self) -> list[TCQdisc]: ...
        @qdiscs.setter
        def qdiscs(self, value: Sequence[TCQdisc] | None) -> None: ...
        @property
        def tfilters(self) -> list[TCTfilter]: ...
        @tfilters.setter
        def tfilters(self, value: Sequence[TCTfilter] | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        qdiscs: Sequence[TCQdisc] | None = ...,
        tfilters: Sequence[TCTfilter] | None = ...,
    ) -> None: ...
    def add_qdisc(self, qdisc: TCQdisc) -> bool: ...
    def add_tfilter(self, tfilter: TCTfilter) -> bool: ...
    def clear_qdiscs(self) -> None: ...
    def clear_tfilters(self) -> None: ...
    def get_num_qdiscs(self) -> int: ...
    def get_num_tfilters(self) -> int: ...
    def get_qdisc(self, idx: int) -> TCQdisc: ...
    def get_tfilter(self, idx: int) -> TCTfilter: ...
    @classmethod
    def new(cls) -> SettingTCConfig: ...
    def remove_qdisc(self, idx: int) -> None: ...
    def remove_qdisc_by_value(self, qdisc: TCQdisc) -> bool: ...
    def remove_tfilter(self, idx: int) -> None: ...
    def remove_tfilter_by_value(self, tfilter: TCTfilter) -> bool: ...

class SettingTCConfigClass(_gi.Struct): ...

class SettingTeam(Setting):
    """
    :Constructors:

    ::

        SettingTeam(**properties)
        new() -> NM.Setting

    Object NMSettingTeam

    Properties from NMSettingTeam:
      config -> gchararray:

      link-watchers -> GPtrArray:

      notify-peers-count -> gint:

      notify-peers-interval -> gint:

      mcast-rejoin-count -> gint:

      mcast-rejoin-interval -> gint:

      runner -> gchararray:

      runner-hwaddr-policy -> gchararray:

      runner-tx-hash -> GStrv:

      runner-tx-balancer -> gchararray:

      runner-tx-balancer-interval -> gint:

      runner-active -> gboolean:

      runner-fast-rate -> gboolean:

      runner-sys-prio -> gint:

      runner-min-ports -> gint:

      runner-agg-select-policy -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def config(self) -> str: ...
        @config.setter
        def config(self, value: str | None) -> None: ...
        @property
        def link_watchers(self) -> list[TeamLinkWatcher]: ...
        @link_watchers.setter
        def link_watchers(self, value: Sequence[TeamLinkWatcher] | None) -> None: ...
        mcast_rejoin_count: int
        mcast_rejoin_interval: int
        notify_peers_count: int
        notify_peers_interval: int
        @property
        def runner(self) -> str: ...
        @runner.setter
        def runner(self, value: str | None) -> None: ...
        runner_active: bool
        @property
        def runner_agg_select_policy(self) -> str: ...
        @runner_agg_select_policy.setter
        def runner_agg_select_policy(self, value: str | None) -> None: ...
        runner_fast_rate: bool
        @property
        def runner_hwaddr_policy(self) -> str: ...
        @runner_hwaddr_policy.setter
        def runner_hwaddr_policy(self, value: str | None) -> None: ...
        runner_min_ports: int
        runner_sys_prio: int
        @property
        def runner_tx_balancer(self) -> str: ...
        @runner_tx_balancer.setter
        def runner_tx_balancer(self, value: str | None) -> None: ...
        runner_tx_balancer_interval: int
        @property
        def runner_tx_hash(self) -> list[str]: ...
        @runner_tx_hash.setter
        def runner_tx_hash(self, value: Sequence[str] | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        config: str | None = ...,
        link_watchers: Sequence[TeamLinkWatcher] | None = ...,
        mcast_rejoin_count: int = ...,
        mcast_rejoin_interval: int = ...,
        notify_peers_count: int = ...,
        notify_peers_interval: int = ...,
        runner: str | None = ...,
        runner_active: bool = ...,
        runner_agg_select_policy: str | None = ...,
        runner_fast_rate: bool = ...,
        runner_hwaddr_policy: str | None = ...,
        runner_min_ports: int = ...,
        runner_sys_prio: int = ...,
        runner_tx_balancer: str | None = ...,
        runner_tx_balancer_interval: int = ...,
        runner_tx_hash: Sequence[str] | None = ...,
    ) -> None: ...
    def add_link_watcher(self, link_watcher: TeamLinkWatcher) -> bool: ...
    def add_runner_tx_hash(self, txhash: str) -> bool: ...
    def clear_link_watchers(self) -> None: ...
    def get_config(self) -> str: ...
    def get_link_watcher(self, idx: int) -> TeamLinkWatcher: ...
    def get_mcast_rejoin_count(self) -> int: ...
    def get_mcast_rejoin_interval(self) -> int: ...
    def get_notify_peers_count(self) -> int: ...
    def get_notify_peers_interval(self) -> int: ...
    def get_num_link_watchers(self) -> int: ...
    def get_num_runner_tx_hash(self) -> int: ...
    def get_runner(self) -> str: ...
    def get_runner_active(self) -> bool: ...
    def get_runner_agg_select_policy(self) -> str: ...
    def get_runner_fast_rate(self) -> bool: ...
    def get_runner_hwaddr_policy(self) -> str: ...
    def get_runner_min_ports(self) -> int: ...
    def get_runner_sys_prio(self) -> int: ...
    def get_runner_tx_balancer(self) -> str: ...
    def get_runner_tx_balancer_interval(self) -> int: ...
    def get_runner_tx_hash(self, idx: int) -> str: ...
    @classmethod
    def new(cls) -> SettingTeam: ...
    def remove_link_watcher(self, idx: int) -> None: ...
    def remove_link_watcher_by_value(self, link_watcher: TeamLinkWatcher) -> bool: ...
    def remove_runner_tx_hash(self, idx: int) -> None: ...
    def remove_runner_tx_hash_by_value(self, txhash: str) -> bool: ...

class SettingTeamClass(_gi.Struct): ...

class SettingTeamPort(Setting):
    """
    :Constructors:

    ::

        SettingTeamPort(**properties)
        new() -> NM.Setting

    Object NMSettingTeamPort

    Properties from NMSettingTeamPort:
      config -> gchararray:

      link-watchers -> GPtrArray:

      queue-id -> gint:

      prio -> gint:

      sticky -> gboolean:

      lacp-prio -> gint:

      lacp-key -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def config(self) -> str: ...
        @config.setter
        def config(self, value: str | None) -> None: ...
        lacp_key: int
        lacp_prio: int
        @property
        def link_watchers(self) -> list[TeamLinkWatcher]: ...
        @link_watchers.setter
        def link_watchers(self, value: Sequence[TeamLinkWatcher] | None) -> None: ...
        prio: int
        queue_id: int
        sticky: bool

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        config: str | None = ...,
        lacp_key: int = ...,
        lacp_prio: int = ...,
        link_watchers: Sequence[TeamLinkWatcher] | None = ...,
        prio: int = ...,
        queue_id: int = ...,
        sticky: bool = ...,
    ) -> None: ...
    def add_link_watcher(self, link_watcher: TeamLinkWatcher) -> bool: ...
    def clear_link_watchers(self) -> None: ...
    def get_config(self) -> str: ...
    def get_lacp_key(self) -> int: ...
    def get_lacp_prio(self) -> int: ...
    def get_link_watcher(self, idx: int) -> TeamLinkWatcher: ...
    def get_num_link_watchers(self) -> int: ...
    def get_prio(self) -> int: ...
    def get_queue_id(self) -> int: ...
    def get_sticky(self) -> bool: ...
    @classmethod
    def new(cls) -> SettingTeamPort: ...
    def remove_link_watcher(self, idx: int) -> None: ...
    def remove_link_watcher_by_value(self, link_watcher: TeamLinkWatcher) -> bool: ...

class SettingTeamPortClass(_gi.Struct): ...

class SettingTun(Setting):
    """
    :Constructors:

    ::

        SettingTun(**properties)
        new() -> NM.Setting

    Object NMSettingTun

    Properties from NMSettingTun:
      mode -> guint:

      owner -> gchararray:

      group -> gchararray:

      pi -> gboolean:

      vnet-hdr -> gboolean:

      multi-queue -> gboolean:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def group(self) -> str: ...
        @group.setter
        def group(self, value: str | None) -> None: ...
        mode: int
        multi_queue: bool
        @property
        def owner(self) -> str: ...
        @owner.setter
        def owner(self, value: str | None) -> None: ...
        pi: bool
        vnet_hdr: bool

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        group: str | None = ...,
        mode: int = ...,
        multi_queue: bool = ...,
        owner: str | None = ...,
        pi: bool = ...,
        vnet_hdr: bool = ...,
    ) -> None: ...
    def get_group(self) -> str: ...
    def get_mode(self) -> SettingTunMode: ...
    def get_multi_queue(self) -> bool: ...
    def get_owner(self) -> str: ...
    def get_pi(self) -> bool: ...
    def get_vnet_hdr(self) -> bool: ...
    @classmethod
    def new(cls) -> SettingTun: ...

class SettingTunClass(_gi.Struct): ...

class SettingUser(Setting):
    """
    :Constructors:

    ::

        SettingUser(**properties)
        new() -> NM.Setting

    Object NMSettingUser

    Properties from NMSettingUser:
      data -> GHashTable:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def data(self) -> dict[str, str]: ...
        @data.setter
        def data(self, value: Mapping[str, str]) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, data: Mapping[str, str] = ...) -> None: ...
    @staticmethod
    def check_key(key: str) -> bool: ...
    @staticmethod
    def check_val(val: str) -> bool: ...
    def get_data(self, key: str) -> str: ...
    def get_keys(self) -> list[str]: ...
    @classmethod
    def new(cls) -> SettingUser: ...
    def set_data(self, key: str, val: str | None = None) -> bool: ...

class SettingUserClass(_gi.Struct): ...

class SettingVeth(Setting):
    """
    :Constructors:

    ::

        SettingVeth(**properties)
        new() -> NM.Setting

    Object NMSettingVeth

    Properties from NMSettingVeth:
      peer -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def peer(self) -> str: ...
        @peer.setter
        def peer(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(self, *, peer: str | None = ...) -> None: ...
    def get_peer(self) -> str: ...
    @classmethod
    def new(cls) -> SettingVeth: ...

class SettingVethClass(_gi.Struct): ...

class SettingVlan(Setting):
    """
    :Constructors:

    ::

        SettingVlan(**properties)
        new() -> NM.Setting

    Object NMSettingVlan

    Properties from NMSettingVlan:
      parent -> gchararray:

      id -> guint:

      flags -> NMVlanFlags:

      protocol -> gchararray:

      ingress-priority-map -> GStrv:

      egress-priority-map -> GStrv:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def egress_priority_map(self) -> list[str]: ...
        @egress_priority_map.setter
        def egress_priority_map(self, value: Sequence[str] | None) -> None: ...
        @property
        def flags(self) -> VlanFlags: ...
        @flags.setter
        def flags(self, value: _VlanFlagsValueType) -> None: ...
        id: int
        @property
        def ingress_priority_map(self) -> list[str]: ...
        @ingress_priority_map.setter
        def ingress_priority_map(self, value: Sequence[str] | None) -> None: ...
        @property
        def parent(self) -> str: ...
        @parent.setter
        def parent(self, value: str | None) -> None: ...
        @property
        def protocol(self) -> str: ...
        @protocol.setter
        def protocol(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        egress_priority_map: Sequence[str] | None = ...,
        flags: _VlanFlagsValueType = ...,
        id: int = ...,
        ingress_priority_map: Sequence[str] | None = ...,
        parent: str | None = ...,
        protocol: str | None = ...,
    ) -> None: ...
    def add_priority(
        self, map: _VlanPriorityMapValueType, from_: int, to: int
    ) -> bool: ...
    def add_priority_str(self, map: _VlanPriorityMapValueType, str: str) -> bool: ...
    def clear_priorities(self, map: _VlanPriorityMapValueType) -> None: ...
    def get_flags(self) -> int: ...
    def get_id(self) -> int: ...
    def get_num_priorities(self, map: _VlanPriorityMapValueType) -> int: ...
    def get_parent(self) -> str: ...
    def get_priority(
        self, map: _VlanPriorityMapValueType, idx: int
    ) -> tuple[bool, int, int]: ...
    def get_protocol(self) -> str: ...
    @classmethod
    def new(cls) -> SettingVlan: ...
    def remove_priority(self, map: _VlanPriorityMapValueType, idx: int) -> None: ...
    def remove_priority_by_value(
        self, map: _VlanPriorityMapValueType, from_: int, to: int
    ) -> bool: ...
    def remove_priority_str_by_value(
        self, map: _VlanPriorityMapValueType, str: str
    ) -> bool: ...

class SettingVlanClass(_gi.Struct): ...

class SettingVpn(Setting):
    """
    :Constructors:

    ::

        SettingVpn(**properties)
        new() -> NM.Setting

    Object NMSettingVpn

    Properties from NMSettingVpn:
      service-type -> gchararray:

      user-name -> gchararray:

      persistent -> gboolean:

      data -> GHashTable:

      secrets -> GHashTable:

      timeout -> guint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def data(self) -> dict[str, str] | None: ...
        @data.setter
        def data(self, value: Mapping[str, str] | None) -> None: ...
        persistent: bool
        @property
        def secrets(self) -> dict[str, str] | None: ...
        @secrets.setter
        def secrets(self, value: Mapping[str, str] | None) -> None: ...
        @property
        def service_type(self) -> str: ...
        @service_type.setter
        def service_type(self, value: str | None) -> None: ...
        timeout: int
        @property
        def user_name(self) -> str: ...
        @user_name.setter
        def user_name(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        data: Mapping[str, str] | None = ...,
        persistent: bool = ...,
        secrets: Mapping[str, str] | None = ...,
        service_type: str | None = ...,
        timeout: int = ...,
        user_name: str | None = ...,
    ) -> None: ...
    def add_data_item(self, key: str, item: str | None = None) -> None: ...
    def add_secret(self, key: str, secret: str | None = None) -> None: ...
    def foreach_data_item(
        self,
        func: Callable[[str, str, Unpack[_DataTs]], None],
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    def foreach_secret(
        self,
        func: Callable[[str, str, Unpack[_DataTs]], None],
        *user_data: Unpack[_DataTs],
    ) -> None: ...
    def get_data_item(self, key: str) -> str: ...
    def get_data_keys(self) -> list[str]: ...
    def get_num_data_items(self) -> int: ...
    def get_num_secrets(self) -> int: ...
    def get_persistent(self) -> bool: ...
    def get_secret(self, key: str) -> str: ...
    def get_secret_keys(self) -> list[str]: ...
    def get_service_type(self) -> str: ...
    def get_timeout(self) -> int: ...
    def get_user_name(self) -> str: ...
    @classmethod
    def new(cls) -> SettingVpn: ...
    def remove_data_item(self, key: str) -> bool: ...
    def remove_secret(self, key: str) -> bool: ...

class SettingVpnClass(_gi.Struct): ...

class SettingVrf(Setting):
    """
    :Constructors:

    ::

        SettingVrf(**properties)
        new() -> NM.Setting

    Object NMSettingVrf

    Properties from NMSettingVrf:
      table -> guint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        table: int

    @property
    def props(self) -> Props: ...
    def __init__(self, *, table: int = ...) -> None: ...
    def get_table(self) -> int: ...
    @classmethod
    def new(cls) -> SettingVrf: ...

class SettingVrfClass(_gi.Struct): ...

class SettingVxlan(Setting):
    """
    :Constructors:

    ::

        SettingVxlan(**properties)
        new() -> NM.Setting

    Object NMSettingVxlan

    Properties from NMSettingVxlan:
      parent -> gchararray:

      id -> guint:

      local -> gchararray:

      remote -> gchararray:

      source-port-min -> guint:

      source-port-max -> guint:

      destination-port -> guint:

      tos -> guint:

      ttl -> guint:

      ageing -> guint:

      limit -> guint:

      learning -> gboolean:

      proxy -> gboolean:

      rsc -> gboolean:

      l2-miss -> gboolean:

      l3-miss -> gboolean:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        ageing: int
        destination_port: int
        id: int
        l2_miss: bool
        l3_miss: bool
        learning: bool
        limit: int
        @property
        def local(self) -> str: ...
        @local.setter
        def local(self, value: str | None) -> None: ...
        @property
        def parent(self) -> str: ...
        @parent.setter
        def parent(self, value: str | None) -> None: ...
        proxy: bool
        @property
        def remote(self) -> str: ...
        @remote.setter
        def remote(self, value: str | None) -> None: ...
        rsc: bool
        source_port_max: int
        source_port_min: int
        tos: int
        ttl: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        ageing: int = ...,
        destination_port: int = ...,
        id: int = ...,
        l2_miss: bool = ...,
        l3_miss: bool = ...,
        learning: bool = ...,
        limit: int = ...,
        local: str | None = ...,
        parent: str | None = ...,
        proxy: bool = ...,
        remote: str | None = ...,
        rsc: bool = ...,
        source_port_max: int = ...,
        source_port_min: int = ...,
        tos: int = ...,
        ttl: int = ...,
    ) -> None: ...
    def get_ageing(self) -> int: ...
    def get_destination_port(self) -> int: ...
    def get_id(self) -> int: ...
    def get_l2_miss(self) -> bool: ...
    def get_l3_miss(self) -> bool: ...
    def get_learning(self) -> bool: ...
    def get_limit(self) -> int: ...
    def get_local(self) -> str: ...
    def get_parent(self) -> str: ...
    def get_proxy(self) -> bool: ...
    def get_remote(self) -> str: ...
    def get_rsc(self) -> bool: ...
    def get_source_port_max(self) -> int: ...
    def get_source_port_min(self) -> int: ...
    def get_tos(self) -> int: ...
    def get_ttl(self) -> int: ...
    @classmethod
    def new(cls) -> SettingVxlan: ...

class SettingVxlanClass(_gi.Struct): ...

class SettingWifiP2P(Setting):
    """
    :Constructors:

    ::

        SettingWifiP2P(**properties)
        new() -> NM.Setting

    Object NMSettingWifiP2P

    Properties from NMSettingWifiP2P:
      peer -> gchararray:

      wps-method -> guint:

      wfd-ies -> GBytes:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def peer(self) -> str: ...
        @peer.setter
        def peer(self, value: str | None) -> None: ...
        @property
        def wfd_ies(self) -> GLib.Bytes: ...
        @wfd_ies.setter
        def wfd_ies(self, value: GLib.Bytes | None) -> None: ...
        wps_method: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        peer: str | None = ...,
        wfd_ies: GLib.Bytes | None = ...,
        wps_method: int = ...,
    ) -> None: ...
    def get_peer(self) -> str: ...
    def get_wfd_ies(self) -> GLib.Bytes: ...
    def get_wps_method(self) -> SettingWirelessSecurityWpsMethod: ...
    @classmethod
    def new(cls) -> SettingWifiP2P: ...

class SettingWifiP2PClass(_gi.Struct): ...

class SettingWimax(Setting):
    """
    :Constructors:

    ::

        SettingWimax(**properties)
        new() -> NM.Setting

    Object NMSettingWimax

    Properties from NMSettingWimax:
      network-name -> gchararray:

      mac-address -> gchararray:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def mac_address(self) -> str: ...
        @mac_address.setter
        def mac_address(self, value: str | None) -> None: ...
        @property
        def network_name(self) -> str: ...
        @network_name.setter
        def network_name(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self, *, mac_address: str | None = ..., network_name: str | None = ...
    ) -> None: ...
    def get_mac_address(self) -> str: ...
    def get_network_name(self) -> str: ...
    @classmethod
    def new(cls) -> SettingWimax: ...

class SettingWimaxClass(_gi.Struct): ...

class SettingWireGuard(Setting):
    """
    :Constructors:

    ::

        SettingWireGuard(**properties)
        new() -> NM.Setting

    Object NMSettingWireGuard

    Properties from NMSettingWireGuard:
      fwmark -> guint:

      ip4-auto-default-route -> NMTernary:

      ip6-auto-default-route -> NMTernary:

      listen-port -> guint:

      mtu -> guint:

      peer-routes -> gboolean:

      private-key -> gchararray:

      private-key-flags -> NMSettingSecretFlags:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        fwmark: int
        @property
        def ip4_auto_default_route(self) -> Ternary: ...
        @ip4_auto_default_route.setter
        def ip4_auto_default_route(self, value: _TernaryValueType) -> None: ...
        @property
        def ip6_auto_default_route(self) -> Ternary: ...
        @ip6_auto_default_route.setter
        def ip6_auto_default_route(self, value: _TernaryValueType) -> None: ...
        listen_port: int
        mtu: int
        peer_routes: bool
        @property
        def private_key(self) -> str: ...
        @private_key.setter
        def private_key(self, value: str | None) -> None: ...
        @property
        def private_key_flags(self) -> SettingSecretFlags: ...
        @private_key_flags.setter
        def private_key_flags(self, value: _SettingSecretFlagsValueType) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        fwmark: int = ...,
        ip4_auto_default_route: _TernaryValueType = ...,
        ip6_auto_default_route: _TernaryValueType = ...,
        listen_port: int = ...,
        mtu: int = ...,
        peer_routes: bool = ...,
        private_key: str | None = ...,
        private_key_flags: _SettingSecretFlagsValueType = ...,
    ) -> None: ...
    def append_peer(self, peer: WireGuardPeer) -> None: ...
    def clear_peers(self) -> int: ...
    def get_fwmark(self) -> int: ...
    def get_ip4_auto_default_route(self) -> Ternary: ...
    def get_ip6_auto_default_route(self) -> Ternary: ...
    def get_listen_port(self) -> int: ...
    def get_mtu(self) -> int: ...
    def get_peer(self, idx: int) -> WireGuardPeer: ...
    def get_peer_by_public_key(
        self, public_key: str
    ) -> tuple[WireGuardPeer | None, int]: ...
    def get_peer_routes(self) -> bool: ...
    def get_peers_len(self) -> int: ...
    def get_private_key(self) -> str: ...
    def get_private_key_flags(self) -> SettingSecretFlags: ...
    @classmethod
    def new(cls) -> SettingWireGuard: ...
    def remove_peer(self, idx: int) -> bool: ...
    def set_peer(self, peer: WireGuardPeer, idx: int) -> None: ...

class SettingWireGuardClass(_gi.Struct): ...

class SettingWired(Setting):
    """
    :Constructors:

    ::

        SettingWired(**properties)
        new() -> NM.Setting

    Object NMSettingWired

    Properties from NMSettingWired:
      port -> gchararray:

      speed -> guint:

      duplex -> gchararray:

      auto-negotiate -> gboolean:

      mac-address -> gchararray:

      cloned-mac-address -> gchararray:

      generate-mac-address-mask -> gchararray:

      mac-address-blacklist -> GStrv:

      mac-address-denylist -> GStrv:

      mtu -> guint:

      s390-subchannels -> GStrv:

      s390-nettype -> gchararray:

      s390-options -> GHashTable:

      wake-on-lan -> guint:

      wake-on-lan-password -> gchararray:

      accept-all-mac-addresses -> NMTernary:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def accept_all_mac_addresses(self) -> Ternary: ...
        @accept_all_mac_addresses.setter
        def accept_all_mac_addresses(self, value: _TernaryValueType) -> None: ...
        auto_negotiate: bool
        @property
        def cloned_mac_address(self) -> str: ...
        @cloned_mac_address.setter
        def cloned_mac_address(self, value: str | None) -> None: ...
        @property
        def duplex(self) -> str: ...
        @duplex.setter
        def duplex(self, value: str | None) -> None: ...
        @property
        def generate_mac_address_mask(self) -> str: ...
        @generate_mac_address_mask.setter
        def generate_mac_address_mask(self, value: str | None) -> None: ...
        @property
        def mac_address(self) -> str: ...
        @mac_address.setter
        def mac_address(self, value: str | None) -> None: ...
        @property
        def mac_address_blacklist(self) -> list[str]: ...
        @mac_address_blacklist.setter
        def mac_address_blacklist(self, value: Sequence[str] | None) -> None: ...
        @property
        def mac_address_denylist(self) -> list[str]: ...
        @mac_address_denylist.setter
        def mac_address_denylist(self, value: Sequence[str] | None) -> None: ...
        mtu: int
        @property
        def port(self) -> str: ...
        @port.setter
        def port(self, value: str | None) -> None: ...
        @property
        def s390_nettype(self) -> str: ...
        @s390_nettype.setter
        def s390_nettype(self, value: str | None) -> None: ...
        @property
        def s390_options(self) -> dict[str, str] | None: ...
        @s390_options.setter
        def s390_options(self, value: Mapping[str, str] | None) -> None: ...
        @property
        def s390_subchannels(self) -> list[str]: ...
        @s390_subchannels.setter
        def s390_subchannels(self, value: Sequence[str] | None) -> None: ...
        speed: int
        wake_on_lan: int
        @property
        def wake_on_lan_password(self) -> str: ...
        @wake_on_lan_password.setter
        def wake_on_lan_password(self, value: str | None) -> None: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        accept_all_mac_addresses: _TernaryValueType = ...,
        auto_negotiate: bool = ...,
        cloned_mac_address: str | None = ...,
        duplex: str | None = ...,
        generate_mac_address_mask: str | None = ...,
        mac_address: str | None = ...,
        mac_address_blacklist: Sequence[str] | None = ...,
        mac_address_denylist: Sequence[str] | None = ...,
        mtu: int = ...,
        port: str | None = ...,
        s390_nettype: str | None = ...,
        s390_options: Mapping[str, str] | None = ...,
        s390_subchannels: Sequence[str] | None = ...,
        speed: int = ...,
        wake_on_lan: int = ...,
        wake_on_lan_password: str | None = ...,
    ) -> None: ...
    def add_mac_blacklist_item(self, mac: str) -> bool: ...
    def add_mac_denylist_item(self, mac: str) -> bool: ...
    def add_s390_option(self, key: str, value: str) -> bool: ...
    def clear_mac_blacklist_items(self) -> None: ...
    def clear_mac_denylist_items(self) -> None: ...
    def get_accept_all_mac_addresses(self) -> Ternary: ...
    def get_auto_negotiate(self) -> bool: ...
    def get_cloned_mac_address(self) -> str: ...
    def get_duplex(self) -> str: ...
    def get_generate_mac_address_mask(self) -> str: ...
    def get_mac_address(self) -> str: ...
    def get_mac_address_blacklist(self) -> list[str]: ...
    def get_mac_address_denylist(self) -> list[str]: ...
    def get_mac_blacklist_item(self, idx: int) -> str: ...
    def get_mac_denylist_item(self, idx: int) -> str: ...
    def get_mtu(self) -> int: ...
    def get_num_mac_blacklist_items(self) -> int: ...
    def get_num_mac_denylist_items(self) -> int: ...
    def get_num_s390_options(self) -> int: ...
    def get_port(self) -> str: ...
    def get_s390_nettype(self) -> str: ...
    def get_s390_option(self, idx: int) -> tuple[bool, str | None, str | None]: ...
    def get_s390_option_by_key(self, key: str) -> str: ...
    def get_s390_subchannels(self) -> list[str]: ...
    def get_speed(self) -> int: ...
    def get_valid_s390_options(self) -> list[str]: ...
    def get_wake_on_lan(self) -> SettingWiredWakeOnLan: ...
    def get_wake_on_lan_password(self) -> str: ...
    @classmethod
    def new(cls) -> SettingWired: ...
    def remove_mac_blacklist_item(self, idx: int) -> None: ...
    def remove_mac_blacklist_item_by_value(self, mac: str) -> bool: ...
    def remove_mac_denylist_item(self, idx: int) -> None: ...
    def remove_mac_denylist_item_by_value(self, mac: str) -> bool: ...
    def remove_s390_option(self, key: str) -> bool: ...

class SettingWiredClass(_gi.Struct): ...

class SettingWireless(Setting):
    """
    :Constructors:

    ::

        SettingWireless(**properties)
        new() -> NM.Setting

    Object NMSettingWireless

    Properties from NMSettingWireless:
      ssid -> GBytes:

      mode -> gchararray:

      band -> gchararray:

      channel -> guint:

      bssid -> gchararray:

      rate -> guint:

      tx-power -> guint:

      mac-address -> gchararray:

      cloned-mac-address -> gchararray:

      generate-mac-address-mask -> gchararray:

      mac-address-blacklist -> GStrv:

      mac-address-denylist -> GStrv:

      mtu -> guint:

      seen-bssids -> GStrv:

      hidden -> gboolean:

      powersave -> guint:

      mac-address-randomization -> guint:

      wake-on-wlan -> guint:

      ap-isolation -> NMTernary:

      channel-width -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def ap_isolation(self) -> Ternary: ...
        @ap_isolation.setter
        def ap_isolation(self, value: _TernaryValueType) -> None: ...
        @property
        def band(self) -> str: ...
        @band.setter
        def band(self, value: str | None) -> None: ...
        @property
        def bssid(self) -> str: ...
        @bssid.setter
        def bssid(self, value: str | None) -> None: ...
        channel: int
        channel_width: int
        @property
        def cloned_mac_address(self) -> str: ...
        @cloned_mac_address.setter
        def cloned_mac_address(self, value: str | None) -> None: ...
        @property
        def generate_mac_address_mask(self) -> str: ...
        @generate_mac_address_mask.setter
        def generate_mac_address_mask(self, value: str | None) -> None: ...
        hidden: bool
        @property
        def mac_address(self) -> str: ...
        @mac_address.setter
        def mac_address(self, value: str | None) -> None: ...
        @property
        def mac_address_blacklist(self) -> list[str]: ...
        @mac_address_blacklist.setter
        def mac_address_blacklist(self, value: Sequence[str] | None) -> None: ...
        @property
        def mac_address_denylist(self) -> list[str]: ...
        @mac_address_denylist.setter
        def mac_address_denylist(self, value: Sequence[str] | None) -> None: ...
        mac_address_randomization: int
        @property
        def mode(self) -> str: ...
        @mode.setter
        def mode(self, value: str | None) -> None: ...
        mtu: int
        powersave: int
        rate: int
        @property
        def seen_bssids(self) -> list[str]: ...
        @seen_bssids.setter
        def seen_bssids(self, value: Sequence[str] | None) -> None: ...
        @property
        def ssid(self) -> GLib.Bytes: ...
        @ssid.setter
        def ssid(self, value: GLib.Bytes | None) -> None: ...
        tx_power: int
        wake_on_wlan: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        ap_isolation: _TernaryValueType = ...,
        band: str | None = ...,
        bssid: str | None = ...,
        channel: int = ...,
        channel_width: int = ...,
        cloned_mac_address: str | None = ...,
        generate_mac_address_mask: str | None = ...,
        hidden: bool = ...,
        mac_address: str | None = ...,
        mac_address_blacklist: Sequence[str] | None = ...,
        mac_address_denylist: Sequence[str] | None = ...,
        mac_address_randomization: int = ...,
        mode: str | None = ...,
        mtu: int = ...,
        powersave: int = ...,
        rate: int = ...,
        seen_bssids: Sequence[str] | None = ...,
        ssid: GLib.Bytes | None = ...,
        tx_power: int = ...,
        wake_on_wlan: int = ...,
    ) -> None: ...
    def add_mac_blacklist_item(self, mac: str) -> bool: ...
    def add_mac_denylist_item(self, mac: str) -> bool: ...
    def add_seen_bssid(self, bssid: str) -> bool: ...
    def ap_security_compatible(
        self,
        s_wireless_sec: SettingWirelessSecurity,
        ap_flags: GObject.GFlags,
        ap_wpa: GObject.GFlags,
        ap_rsn: GObject.GFlags,
        ap_mode: GObject.GEnum,
    ) -> bool: ...
    def clear_mac_blacklist_items(self) -> None: ...
    def clear_mac_denylist_items(self) -> None: ...
    def get_ap_isolation(self) -> Ternary: ...
    def get_band(self) -> str: ...
    def get_bssid(self) -> str: ...
    def get_channel(self) -> int: ...
    def get_channel_width(self) -> SettingWirelessChannelWidth: ...
    def get_cloned_mac_address(self) -> str: ...
    def get_generate_mac_address_mask(self) -> str: ...
    def get_hidden(self) -> bool: ...
    def get_mac_address(self) -> str: ...
    def get_mac_address_blacklist(self) -> list[str]: ...
    def get_mac_address_denylist(self) -> list[str]: ...
    def get_mac_address_randomization(self) -> SettingMacRandomization: ...
    def get_mac_blacklist_item(self, idx: int) -> str: ...
    def get_mac_denylist_item(self, idx: int) -> str: ...
    def get_mode(self) -> str: ...
    def get_mtu(self) -> int: ...
    def get_num_mac_blacklist_items(self) -> int: ...
    def get_num_mac_denylist_items(self) -> int: ...
    def get_num_seen_bssids(self) -> int: ...
    def get_powersave(self) -> int: ...
    def get_rate(self) -> int: ...
    def get_seen_bssid(self, i: int) -> str: ...
    def get_ssid(self) -> GLib.Bytes: ...
    def get_tx_power(self) -> int: ...
    def get_wake_on_wlan(self) -> SettingWirelessWakeOnWLan: ...
    @classmethod
    def new(cls) -> SettingWireless: ...
    def remove_mac_blacklist_item(self, idx: int) -> None: ...
    def remove_mac_blacklist_item_by_value(self, mac: str) -> bool: ...
    def remove_mac_denylist_item(self, idx: int) -> None: ...
    def remove_mac_denylist_item_by_value(self, mac: str) -> bool: ...

class SettingWirelessClass(_gi.Struct): ...

class SettingWirelessSecurity(Setting):
    """
    :Constructors:

    ::

        SettingWirelessSecurity(**properties)
        new() -> NM.Setting

    Object NMSettingWirelessSecurity

    Properties from NMSettingWirelessSecurity:
      key-mgmt -> gchararray:

      wep-tx-keyidx -> guint:

      auth-alg -> gchararray:

      proto -> GStrv:

      pairwise -> GStrv:

      group -> GStrv:

      pmf -> gint:

      leap-username -> gchararray:

      wep-key0 -> gchararray:

      wep-key1 -> gchararray:

      wep-key2 -> gchararray:

      wep-key3 -> gchararray:

      wep-key-flags -> NMSettingSecretFlags:

      wep-key-type -> NMWepKeyType:

      psk -> gchararray:

      psk-flags -> NMSettingSecretFlags:

      leap-password -> gchararray:

      leap-password-flags -> NMSettingSecretFlags:

      wps-method -> guint:

      fils -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        @property
        def auth_alg(self) -> str: ...
        @auth_alg.setter
        def auth_alg(self, value: str | None) -> None: ...
        fils: int
        @property
        def group(self) -> list[str]: ...
        @group.setter
        def group(self, value: Sequence[str] | None) -> None: ...
        @property
        def key_mgmt(self) -> str: ...
        @key_mgmt.setter
        def key_mgmt(self, value: str | None) -> None: ...
        @property
        def leap_password(self) -> str: ...
        @leap_password.setter
        def leap_password(self, value: str | None) -> None: ...
        @property
        def leap_password_flags(self) -> SettingSecretFlags: ...
        @leap_password_flags.setter
        def leap_password_flags(self, value: _SettingSecretFlagsValueType) -> None: ...
        @property
        def leap_username(self) -> str: ...
        @leap_username.setter
        def leap_username(self, value: str | None) -> None: ...
        @property
        def pairwise(self) -> list[str]: ...
        @pairwise.setter
        def pairwise(self, value: Sequence[str] | None) -> None: ...
        pmf: int
        @property
        def proto(self) -> list[str]: ...
        @proto.setter
        def proto(self, value: Sequence[str] | None) -> None: ...
        @property
        def psk(self) -> str: ...
        @psk.setter
        def psk(self, value: str | None) -> None: ...
        @property
        def psk_flags(self) -> SettingSecretFlags: ...
        @psk_flags.setter
        def psk_flags(self, value: _SettingSecretFlagsValueType) -> None: ...
        @property
        def wep_key_flags(self) -> SettingSecretFlags: ...
        @wep_key_flags.setter
        def wep_key_flags(self, value: _SettingSecretFlagsValueType) -> None: ...
        @property
        def wep_key_type(self) -> WepKeyType: ...
        @wep_key_type.setter
        def wep_key_type(self, value: _WepKeyTypeValueType) -> None: ...
        wep_key0: str | None
        wep_key1: str | None
        wep_key2: str | None
        wep_key3: str | None
        wep_tx_keyidx: int
        wps_method: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        auth_alg: str | None = ...,
        fils: int = ...,
        group: Sequence[str] | None = ...,
        key_mgmt: str | None = ...,
        leap_password: str | None = ...,
        leap_password_flags: _SettingSecretFlagsValueType = ...,
        leap_username: str | None = ...,
        pairwise: Sequence[str] | None = ...,
        pmf: int = ...,
        proto: Sequence[str] | None = ...,
        psk: str | None = ...,
        psk_flags: _SettingSecretFlagsValueType = ...,
        wep_key_flags: _SettingSecretFlagsValueType = ...,
        wep_key_type: _WepKeyTypeValueType = ...,
        wep_key0: str | None = ...,
        wep_key1: str | None = ...,
        wep_key2: str | None = ...,
        wep_key3: str | None = ...,
        wep_tx_keyidx: int = ...,
        wps_method: int = ...,
    ) -> None: ...
    def add_group(self, group: str) -> bool: ...
    def add_pairwise(self, pairwise: str) -> bool: ...
    def add_proto(self, proto: str) -> bool: ...
    def clear_groups(self) -> None: ...
    def clear_pairwise(self) -> None: ...
    def clear_protos(self) -> None: ...
    def get_auth_alg(self) -> str: ...
    def get_fils(self) -> SettingWirelessSecurityFils: ...
    def get_group(self, i: int) -> str: ...
    def get_key_mgmt(self) -> str: ...
    def get_leap_password(self) -> str: ...
    def get_leap_password_flags(self) -> SettingSecretFlags: ...
    def get_leap_username(self) -> str: ...
    def get_num_groups(self) -> int: ...
    def get_num_pairwise(self) -> int: ...
    def get_num_protos(self) -> int: ...
    def get_pairwise(self, i: int) -> str: ...
    def get_pmf(self) -> SettingWirelessSecurityPmf: ...
    def get_proto(self, i: int) -> str: ...
    def get_psk(self) -> str: ...
    def get_psk_flags(self) -> SettingSecretFlags: ...
    def get_wep_key(self, idx: int) -> str: ...
    def get_wep_key_flags(self) -> SettingSecretFlags: ...
    def get_wep_key_type(self) -> WepKeyType: ...
    def get_wep_tx_keyidx(self) -> int: ...
    def get_wps_method(self) -> SettingWirelessSecurityWpsMethod: ...
    @classmethod
    def new(cls) -> SettingWirelessSecurity: ...
    def remove_group(self, i: int) -> None: ...
    def remove_group_by_value(self, group: str) -> bool: ...
    def remove_pairwise(self, i: int) -> None: ...
    def remove_pairwise_by_value(self, pairwise: str) -> bool: ...
    def remove_proto(self, i: int) -> None: ...
    def remove_proto_by_value(self, proto: str) -> bool: ...
    def set_wep_key(self, idx: int, key: str) -> None: ...

class SettingWirelessSecurityClass(_gi.Struct): ...

class SettingWpan(Setting):
    """
    :Constructors:

    ::

        SettingWpan(**properties)
        new() -> NM.Setting

    Object NMSettingWpan

    Properties from NMSettingWpan:
      mac-address -> gchararray:

      pan-id -> guint:

      short-address -> guint:

      page -> gint:

      channel -> gint:


    Properties from NMSetting:
      name -> gchararray:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Setting.Props):
        channel: int
        @property
        def mac_address(self) -> str: ...
        @mac_address.setter
        def mac_address(self, value: str | None) -> None: ...
        page: int
        pan_id: int
        short_address: int

    @property
    def props(self) -> Props: ...
    def __init__(
        self,
        *,
        channel: int = ...,
        mac_address: str | None = ...,
        page: int = ...,
        pan_id: int = ...,
        short_address: int = ...,
    ) -> None: ...
    def get_channel(self) -> int: ...
    def get_mac_address(self) -> str: ...
    def get_page(self) -> int: ...
    def get_pan_id(self) -> int: ...
    def get_short_address(self) -> int: ...
    @classmethod
    def new(cls) -> SettingWpan: ...

class SettingWpanClass(_gi.Struct): ...

class SimpleConnection(GObject.Object, Connection):
    """
    :Constructors:

    ::

        SimpleConnection(**properties)

    Object NMSimpleConnection

    Signals from NMConnection:
      secrets-updated (gchararray)
      secrets-cleared ()
      changed ()

    Signals from GObject:
      notify (GParam)
    """
    @staticmethod
    def new() -> Connection: ...
    @staticmethod
    def new_clone(connection: Connection) -> Connection: ...
    @staticmethod
    def new_from_dbus(dict: GLib.Variant) -> Connection: ...

class SimpleConnectionClass(_gi.Struct): ...

class SriovVF(GObject.GBoxed):
    """
    :Constructors:

    ::

        new(index:int) -> NM.SriovVF
    """
    def __init__(self, index: int) -> None: ...
    def add_vlan(self, vlan_id: int) -> bool: ...
    @staticmethod
    def attribute_validate(name: str, value: GLib.Variant) -> tuple[bool, bool]: ...
    def dup(self) -> SriovVF: ...
    def equal(self, other: SriovVF) -> bool: ...
    def get_attribute(self, name: str) -> GLib.Variant: ...
    def get_attribute_names(self) -> list[str]: ...
    def get_index(self) -> int: ...
    def get_vlan_ids(self) -> list[int]: ...
    def get_vlan_protocol(self, vlan_id: int) -> SriovVFVlanProtocol: ...
    def get_vlan_qos(self, vlan_id: int) -> int: ...
    @classmethod
    def new(cls, index: int) -> SriovVF: ...
    def ref(self) -> None: ...
    def remove_vlan(self, vlan_id: int) -> bool: ...
    def set_attribute(self, name: str, value: GLib.Variant | None = None) -> None: ...
    def set_vlan_protocol(
        self, vlan_id: int, protocol: _SriovVFVlanProtocolValueType
    ) -> None: ...
    def set_vlan_qos(self, vlan_id: int, qos: int) -> None: ...
    def unref(self) -> None: ...

class TCAction(GObject.GBoxed):
    """
    :Constructors:

    ::

        new(kind:str) -> NM.TCAction
    """
    def __init__(self, kind: str) -> None: ...
    def dup(self) -> TCAction: ...
    def equal(self, other: TCAction) -> bool: ...
    def get_attribute(self, name: str) -> GLib.Variant: ...
    def get_attribute_names(self) -> list[str]: ...
    def get_kind(self) -> str: ...
    @classmethod
    def new(cls, kind: str) -> TCAction: ...
    def ref(self) -> None: ...
    def set_attribute(self, name: str, value: GLib.Variant | None = None) -> None: ...
    def unref(self) -> None: ...

class TCQdisc(GObject.GBoxed):
    """
    :Constructors:

    ::

        new(kind:str, parent:int) -> NM.TCQdisc
    """
    def __init__(self, kind: str, parent: int) -> None: ...
    def dup(self) -> TCQdisc: ...
    def equal(self, other: TCQdisc) -> bool: ...
    def get_attribute(self, name: str) -> GLib.Variant: ...
    def get_attribute_names(self) -> list[str]: ...
    def get_handle(self) -> int: ...
    def get_kind(self) -> str: ...
    def get_parent(self) -> int: ...
    @classmethod
    def new(cls, kind: str, parent: int) -> TCQdisc: ...
    def ref(self) -> None: ...
    def set_attribute(self, name: str, value: GLib.Variant | None = None) -> None: ...
    def set_handle(self, handle: int) -> None: ...
    def unref(self) -> None: ...

class TCTfilter(GObject.GBoxed):
    """
    :Constructors:

    ::

        new(kind:str, parent:int) -> NM.TCTfilter
    """
    def __init__(self, kind: str, parent: int) -> None: ...
    def dup(self) -> TCTfilter: ...
    def equal(self, other: TCTfilter) -> bool: ...
    def get_action(self) -> TCAction: ...
    def get_handle(self) -> int: ...
    def get_kind(self) -> str: ...
    def get_parent(self) -> int: ...
    @classmethod
    def new(cls, kind: str, parent: int) -> TCTfilter: ...
    def ref(self) -> None: ...
    def set_action(self, action: TCAction) -> None: ...
    def set_handle(self, handle: int) -> None: ...
    def unref(self) -> None: ...

class TeamLinkWatcher(GObject.GBoxed):
    """
    :Constructors:

    ::

        new_arp_ping(init_wait:int, interval:int, missed_max:int, target_host:str, source_host:str, flags:NM.TeamLinkWatcherArpPingFlags) -> NM.TeamLinkWatcher
        new_arp_ping2(init_wait:int, interval:int, missed_max:int, vlanid:int, target_host:str, source_host:str, flags:NM.TeamLinkWatcherArpPingFlags) -> NM.TeamLinkWatcher
        new_ethtool(delay_up:int, delay_down:int) -> NM.TeamLinkWatcher
        new_nsna_ping(init_wait:int, interval:int, missed_max:int, target_host:str) -> NM.TeamLinkWatcher
    """
    def dup(self) -> TeamLinkWatcher: ...
    def equal(self, other: TeamLinkWatcher) -> bool: ...
    def get_delay_down(self) -> int: ...
    def get_delay_up(self) -> int: ...
    def get_flags(self) -> TeamLinkWatcherArpPingFlags: ...
    def get_init_wait(self) -> int: ...
    def get_interval(self) -> int: ...
    def get_missed_max(self) -> int: ...
    def get_name(self) -> str: ...
    def get_source_host(self) -> str: ...
    def get_target_host(self) -> str: ...
    def get_vlanid(self) -> int: ...
    @classmethod
    def new_arp_ping(
        cls,
        init_wait: int,
        interval: int,
        missed_max: int,
        target_host: str,
        source_host: str,
        flags: _TeamLinkWatcherArpPingFlagsValueType,
    ) -> TeamLinkWatcher: ...
    @classmethod
    def new_arp_ping2(
        cls,
        init_wait: int,
        interval: int,
        missed_max: int,
        vlanid: int,
        target_host: str,
        source_host: str,
        flags: _TeamLinkWatcherArpPingFlagsValueType,
    ) -> TeamLinkWatcher: ...
    @classmethod
    def new_ethtool(cls, delay_up: int, delay_down: int) -> TeamLinkWatcher: ...
    @classmethod
    def new_nsna_ping(
        cls, init_wait: int, interval: int, missed_max: int, target_host: str
    ) -> TeamLinkWatcher: ...
    def ref(self) -> None: ...
    def unref(self) -> None: ...

class VariantAttributeSpec(_gi.Struct): ...

class VpnConnection(ActiveConnection):
    """
    :Constructors:

    ::

        VpnConnection(**properties)

    Object NMVpnConnection

    Signals from NMVpnConnection:
      vpn-state-changed (guint, guint)

    Properties from NMVpnConnection:
      vpn-state -> NMVpnConnectionState:

      banner -> gchararray:


    Signals from NMActiveConnection:
      state-changed (guint, guint)

    Properties from NMActiveConnection:
      connection -> NMRemoteConnection:

      id -> gchararray:

      uuid -> gchararray:

      type -> gchararray:

      specific-object-path -> gchararray:

      devices -> GPtrArray:

      state -> NMActiveConnectionState:

      state-flags -> guint:

      default -> gboolean:

      ip4-config -> NMIPConfig:

      dhcp4-config -> NMDhcpConfig:

      default6 -> gboolean:

      ip6-config -> NMIPConfig:

      dhcp6-config -> NMDhcpConfig:

      vpn -> gboolean:

      master -> NMDevice:

      controller -> NMDevice:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(ActiveConnection.Props):
        @property
        def banner(self) -> str: ...
        @property
        def vpn_state(self) -> VpnConnectionState: ...

    @property
    def props(self) -> Props: ...
    def get_banner(self) -> str: ...
    def get_vpn_state(self) -> VpnConnectionState: ...

class VpnConnectionClass(_gi.Struct): ...

class VpnEditor(GObject.GInterface, Protocol):
    """
    Interface NMVpnEditor

    Signals from GObject:
      notify (GParam)
    """
    def get_widget(self) -> GObject.Object: ...
    def update_connection(self, connection: Connection) -> bool: ...

class VpnEditorInterface(_gi.Struct):
    """
    :Constructors:

    ::

        VpnEditorInterface()
    """
    @property
    def g_iface(self) -> GObject.TypeInterface: ...
    @property
    def get_widget(self) -> Callable[[VpnEditor], GObject.Object]: ...
    @property
    def placeholder(self) -> Callable[[], None]: ...
    @property
    def update_connection(self) -> Callable[[VpnEditor, Connection], bool]: ...
    @property
    def changed(self) -> Callable[[VpnEditor], None]: ...

class VpnEditorPlugin(GObject.GInterface, Protocol):
    """
    Interface NMVpnEditorPlugin

    Signals from GObject:
      notify (GParam)
    """
    def export(self, path: str, connection: Connection) -> bool: ...
    def get_capabilities(self) -> VpnEditorPluginCapability: ...
    def get_editor(self, connection: Connection) -> VpnEditor: ...
    def get_plugin_info(self) -> VpnPluginInfo: ...
    def get_suggested_filename(self, connection: Connection) -> str: ...
    def get_vt(self, vt_size: int) -> tuple[int, VpnEditorPluginVT]: ...
    def import_(self, path: str) -> Connection: ...
    @staticmethod
    def load(plugin_name: str, check_service: str) -> VpnEditorPlugin: ...
    @staticmethod
    def load_from_file(
        plugin_name: str,
        check_service: str,
        check_owner: int,
        check_file: Callable[[str, int | Any | None, Unpack[_DataTs]], bool],
        *user_data: Unpack[_DataTs],
    ) -> VpnEditorPlugin: ...
    def set_plugin_info(self, plugin_info: VpnPluginInfo | None = None) -> None: ...

class VpnEditorPluginInterface(_gi.Struct):
    """
    :Constructors:

    ::

        VpnEditorPluginInterface()
    """
    @property
    def g_iface(self) -> GObject.TypeInterface: ...
    @property
    def get_editor(self) -> Callable[[VpnEditorPlugin, Connection], VpnEditor]: ...
    @property
    def get_capabilities(
        self,
    ) -> Callable[[VpnEditorPlugin], VpnEditorPluginCapability]: ...
    @property
    def import_from_file(self) -> int: ...
    @property
    def export_to_file(self) -> Callable[[VpnEditorPlugin, str, Connection], bool]: ...
    @property
    def get_suggested_filename(
        self,
    ) -> Callable[[VpnEditorPlugin, Connection], str]: ...
    @property
    def notify_plugin_info_set(
        self,
    ) -> Callable[[VpnEditorPlugin, VpnPluginInfo], None]: ...
    @property
    def get_vt(self) -> Callable[[VpnEditorPlugin, int], VpnEditorPluginVT]: ...

class VpnEditorPluginVT(_gi.Struct): ...

class VpnPluginInfo(GObject.Object, Gio.Initable):
    """
    :Constructors:

    ::

        VpnPluginInfo(**properties)
        new_from_file(filename:str) -> NM.VpnPluginInfo
        new_search_file(name:str=None, service:str=None) -> NM.VpnPluginInfo or None
        new_with_data(filename:str, keyfile:GLib.KeyFile) -> NM.VpnPluginInfo

    Object NMVpnPluginInfo

    Properties from NMVpnPluginInfo:
      name -> gchararray:

      filename -> gchararray:

      keyfile -> GKeyFile:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(GObject.Object.Props):
        @property
        def filename(self) -> str: ...
        @property
        def name(self) -> str: ...

    @property
    def props(self) -> Props: ...
    def __init__(
        self, *, filename: str | None = ..., keyfile: GLib.KeyFile | None = ...
    ) -> None: ...
    def get_aliases(self) -> list[str]: ...
    def get_auth_dialog(self) -> str: ...
    def get_editor_plugin(self) -> VpnEditorPlugin: ...
    def get_filename(self) -> str: ...
    def get_name(self) -> str: ...
    def get_plugin(self) -> str: ...
    def get_program(self) -> str: ...
    def get_service(self) -> str: ...
    @staticmethod
    def list_add(list: list[VpnPluginInfo], plugin_info: VpnPluginInfo) -> bool: ...
    @staticmethod
    def list_find_by_filename(
        list: list[VpnPluginInfo], filename: str
    ) -> VpnPluginInfo: ...
    @staticmethod
    def list_find_by_name(list: list[VpnPluginInfo], name: str) -> VpnPluginInfo: ...
    @staticmethod
    def list_find_by_service(
        list: list[VpnPluginInfo], service: str
    ) -> VpnPluginInfo: ...
    @staticmethod
    def list_find_service_type(list: list[VpnPluginInfo], name: str) -> str: ...
    @staticmethod
    def list_get_service_types(
        list: list[VpnPluginInfo], only_existing: bool, with_abbreviations: bool
    ) -> list[str]: ...
    @staticmethod
    def list_load() -> list[VpnPluginInfo]: ...
    @staticmethod
    def list_remove(list: list[VpnPluginInfo], plugin_info: VpnPluginInfo) -> bool: ...
    def load_editor_plugin(self) -> VpnEditorPlugin: ...
    def lookup_property(self, group: str, key: str) -> str: ...
    @classmethod
    def new_from_file(cls, filename: str) -> VpnPluginInfo: ...
    @classmethod
    def new_search_file(
        cls, name: str | None = None, service: str | None = None
    ) -> VpnPluginInfo | None: ...
    @classmethod
    def new_with_data(cls, filename: str, keyfile: GLib.KeyFile) -> VpnPluginInfo: ...
    def set_editor_plugin(self, plugin: VpnEditorPlugin | None = None) -> None: ...
    def supports_hints(self) -> bool: ...
    def supports_multiple(self) -> bool: ...
    def supports_safe_private_file_access(self) -> bool: ...
    @staticmethod
    def validate_filename(filename: str) -> bool: ...

class VpnPluginInfoClass(_gi.Struct): ...

class VpnPluginOld(GObject.Object, Gio.Initable):
    """
    :Constructors:

    ::

        VpnPluginOld(**properties)

    Object NMVpnPluginOld

    Signals from NMVpnPluginOld:
      ip4-config (GVariant)
      ip6-config (GVariant)
      state-changed (guint)
      config (GVariant)
      secrets-required (gchararray, GStrv)
      login-banner (gchararray)
      failure (guint)
      quit ()

    Properties from NMVpnPluginOld:
      service-name -> gchararray:

      state -> NMVpnServiceState:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(GObject.Object.Props):
        @property
        def service_name(self) -> str | None: ...
        @property
        def state(self) -> VpnServiceState: ...
        @state.setter
        def state(self, value: _VpnServiceStateValueType) -> None: ...

    @property
    def props(self) -> Props: ...
    @property
    def parent(self) -> GObject.Object: ...
    def __init__(
        self, *, service_name: str | None = ..., state: _VpnServiceStateValueType = ...
    ) -> None: ...
    def disconnect(self) -> bool: ...
    def do_config(self, config: GLib.Variant, /) -> None: ...
    def do_connect(self, connection: Connection, /) -> bool: ...
    def do_connect_interactive(
        self, connection: Connection, details: GLib.Variant, /
    ) -> bool: ...
    def do_disconnect(self) -> bool: ...
    def do_failure(self, reason: _VpnPluginFailureValueType, /) -> None: ...
    def do_ip4_config(self, ip4_config: GLib.Variant, /) -> None: ...
    def do_ip6_config(self, config: GLib.Variant, /) -> None: ...
    def do_login_banner(self, banner: str, /) -> None: ...
    def do_need_secrets(self, connection: Connection, setting_name: str, /) -> bool: ...
    def do_new_secrets(self, connection: Connection, /) -> bool: ...
    def do_quit(self) -> None: ...
    def do_state_changed(self, state: _VpnServiceStateValueType, /) -> None: ...
    def failure(self, reason: _VpnPluginFailureValueType) -> None: ...
    def get_connection(self) -> Gio.DBusConnection: ...
    @staticmethod
    def get_secret_flags(
        data: Mapping[int | Any | None, int | Any | None], secret_name: str
    ) -> tuple[bool, SettingSecretFlags]: ...
    def get_state(self) -> VpnServiceState: ...
    @staticmethod
    def read_vpn_details(fd: int) -> tuple[bool, dict[int, int], dict[int, int]]: ...
    def secrets_required(self, message: str, hints: str) -> None: ...
    def set_ip4_config(self, ip4_config: GLib.Variant) -> None: ...
    def set_login_banner(self, banner: str) -> None: ...
    def set_state(self, state: _VpnServiceStateValueType) -> None: ...

class VpnPluginOldClass(_gi.Struct):
    """
    :Constructors:

    ::

        VpnPluginOldClass()
    """
    @property
    def parent(self) -> GObject.ObjectClass: ...
    @property
    def state_changed(
        self,
    ) -> Callable[[VpnPluginOld, _VpnServiceStateValueType], None]: ...
    @property
    def ip4_config(self) -> Callable[[VpnPluginOld, GLib.Variant], None]: ...
    @property
    def login_banner(self) -> Callable[[VpnPluginOld, str], None]: ...
    @property
    def failure(self) -> Callable[[VpnPluginOld, _VpnPluginFailureValueType], None]: ...
    @property
    def quit(self) -> Callable[[VpnPluginOld], None]: ...
    @property
    def config(self) -> Callable[[VpnPluginOld, GLib.Variant], None]: ...
    @property
    def ip6_config(self) -> Callable[[VpnPluginOld, GLib.Variant], None]: ...
    @property
    def connect(self) -> Callable[[VpnPluginOld, Connection], bool]: ...
    @property
    def need_secrets(self) -> Callable[[VpnPluginOld, Connection, str], bool]: ...
    @property
    def disconnect(self) -> Callable[[VpnPluginOld], bool]: ...
    @property
    def new_secrets(self) -> Callable[[VpnPluginOld, Connection], bool]: ...
    @property
    def connect_interactive(
        self,
    ) -> Callable[[VpnPluginOld, Connection, GLib.Variant], bool]: ...
    @property
    def padding(self) -> list[int]: ...

class VpnServicePlugin(GObject.Object, Gio.Initable):
    """
    :Constructors:

    ::

        VpnServicePlugin(**properties)

    Object NMVpnServicePlugin

    Signals from NMVpnServicePlugin:
      ip4-config (GVariant)
      ip6-config (GVariant)
      state-changed (guint)
      config (GVariant)
      secrets-required (gchararray, GStrv)
      login-banner (gchararray)
      failure (guint)
      quit ()

    Properties from NMVpnServicePlugin:
      service-name -> gchararray:

      watch-peer -> gboolean:

      state -> NMVpnServiceState:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(GObject.Object.Props):
        @property
        def service_name(self) -> str | None: ...
        @property
        def state(self) -> VpnServiceState: ...
        @state.setter
        def state(self, value: _VpnServiceStateValueType) -> None: ...
        @property
        def watch_peer(self) -> bool: ...

    @property
    def props(self) -> Props: ...
    @property
    def parent(self) -> GObject.Object: ...
    def __init__(
        self,
        *,
        service_name: str | None = ...,
        state: _VpnServiceStateValueType = ...,
        watch_peer: bool = ...,
    ) -> None: ...
    def disconnect(self) -> bool: ...
    def do_config(self, config: GLib.Variant, /) -> None: ...
    def do_connect(self, connection: Connection, /) -> bool: ...
    def do_connect_interactive(
        self, connection: Connection, details: GLib.Variant, /
    ) -> bool: ...
    def do_disconnect(self) -> bool: ...
    def do_failure(self, reason: _VpnPluginFailureValueType, /) -> None: ...
    def do_ip4_config(self, ip4_config: GLib.Variant, /) -> None: ...
    def do_ip6_config(self, config: GLib.Variant, /) -> None: ...
    def do_login_banner(self, banner: str, /) -> None: ...
    def do_need_secrets(self, connection: Connection, setting_name: str, /) -> bool: ...
    def do_new_secrets(self, connection: Connection, /) -> bool: ...
    def do_quit(self) -> None: ...
    def do_state_changed(self, state: _VpnServiceStateValueType, /) -> None: ...
    def failure(self, reason: _VpnPluginFailureValueType) -> None: ...
    def get_connection(self) -> Gio.DBusConnection: ...
    @staticmethod
    def get_secret_flags(
        data: Mapping[int | Any | None, int | Any | None], secret_name: str
    ) -> tuple[bool, SettingSecretFlags]: ...
    @staticmethod
    def read_vpn_details(fd: int) -> tuple[bool, dict[int, int], dict[int, int]]: ...
    def secrets_required(self, message: str, hints: str) -> None: ...
    def set_config(self, config: GLib.Variant) -> None: ...
    def set_ip4_config(self, ip4_config: GLib.Variant) -> None: ...
    def set_ip6_config(self, ip6_config: GLib.Variant) -> None: ...
    def set_login_banner(self, banner: str) -> None: ...
    def shutdown(self) -> None: ...

class VpnServicePluginClass(_gi.Struct):
    """
    :Constructors:

    ::

        VpnServicePluginClass()
    """
    @property
    def parent(self) -> GObject.ObjectClass: ...
    @property
    def state_changed(
        self,
    ) -> Callable[[VpnServicePlugin, _VpnServiceStateValueType], None]: ...
    @property
    def ip4_config(self) -> Callable[[VpnServicePlugin, GLib.Variant], None]: ...
    @property
    def login_banner(self) -> Callable[[VpnServicePlugin, str], None]: ...
    @property
    def failure(
        self,
    ) -> Callable[[VpnServicePlugin, _VpnPluginFailureValueType], None]: ...
    @property
    def quit(self) -> Callable[[VpnServicePlugin], None]: ...
    @property
    def config(self) -> Callable[[VpnServicePlugin, GLib.Variant], None]: ...
    @property
    def ip6_config(self) -> Callable[[VpnServicePlugin, GLib.Variant], None]: ...
    @property
    def connect(self) -> Callable[[VpnServicePlugin, Connection], bool]: ...
    @property
    def need_secrets(self) -> Callable[[VpnServicePlugin, Connection, str], bool]: ...
    @property
    def disconnect(self) -> Callable[[VpnServicePlugin], bool]: ...
    @property
    def new_secrets(self) -> Callable[[VpnServicePlugin, Connection], bool]: ...
    @property
    def connect_interactive(
        self,
    ) -> Callable[[VpnServicePlugin, Connection, GLib.Variant], bool]: ...
    @property
    def padding(self) -> list[int]: ...

class WifiP2PPeer(Object):
    """
    :Constructors:

    ::

        WifiP2PPeer(**properties)

    Object NMWifiP2PPeer

    Properties from NMWifiP2PPeer:
      flags -> NM80211ApFlags:

      name -> gchararray:

      manufacturer -> gchararray:

      model -> gchararray:

      model-number -> gchararray:

      serial -> gchararray:

      wfd-ies -> GBytes:

      hw-address -> gchararray:

      strength -> guchar:

      last-seen -> gint:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Object.Props):
        @property
        def flags(self) -> GObject.GFlags: ...
        @property
        def hw_address(self) -> str: ...
        @property
        def last_seen(self) -> int: ...
        @property
        def manufacturer(self) -> str: ...
        @property
        def model(self) -> str: ...
        @property
        def model_number(self) -> str: ...
        @property
        def name(self) -> str: ...
        @property
        def serial(self) -> str: ...
        @property
        def strength(self) -> int: ...
        @property
        def wfd_ies(self) -> GLib.Bytes: ...

    @property
    def props(self) -> Props: ...
    def connection_valid(self, connection: Connection) -> bool: ...
    def filter_connections(
        self, connections: Sequence[Connection]
    ) -> list[Connection]: ...
    def get_flags(self) -> GObject.GFlags: ...
    def get_hw_address(self) -> str: ...
    def get_last_seen(self) -> int: ...
    def get_manufacturer(self) -> str: ...
    def get_model(self) -> str: ...
    def get_model_number(self) -> str: ...
    def get_name(self) -> str: ...
    def get_serial(self) -> str: ...
    def get_strength(self) -> int: ...
    def get_wfd_ies(self) -> GLib.Bytes: ...

class WifiP2PPeerClass(_gi.Struct): ...

class WimaxNsp(Object):
    """
    :Constructors:

    ::

        WimaxNsp(**properties)

    Object NMWimaxNsp

    Properties from NMWimaxNsp:
      name -> gchararray:

      signal-quality -> guint:

      network-type -> NMWimaxNspNetworkType:


    Properties from NMObject:
      path -> gchararray:

      client -> NMClient:


    Signals from GObject:
      notify (GParam)
    """
    @type_check_only
    class Props(Object.Props):
        @property
        def name(self) -> str: ...
        @property
        def network_type(self) -> WimaxNspNetworkType: ...
        @property
        def signal_quality(self) -> int: ...

    @property
    def props(self) -> Props: ...
    def connection_valid(self, connection: Connection) -> bool: ...
    def filter_connections(
        self, connections: Sequence[Connection]
    ) -> list[Connection]: ...
    def get_name(self) -> str: ...
    def get_network_type(self) -> WimaxNspNetworkType: ...
    def get_signal_quality(self) -> int: ...

class WimaxNspClass(_gi.Struct): ...

class WireGuardPeer(GObject.GBoxed):
    """
    :Constructors:

    ::

        new() -> NM.WireGuardPeer
    """
    def __init__(self) -> None: ...
    def append_allowed_ip(self, allowed_ip: str, accept_invalid: bool) -> bool: ...
    def clear_allowed_ips(self) -> None: ...
    def cmp(
        self, b: WireGuardPeer | None, compare_flags: _SettingCompareFlagsValueType
    ) -> int: ...
    def get_allowed_ip(
        self, idx: int, out_is_valid: bool | None = None
    ) -> str | None: ...
    def get_allowed_ips_len(self) -> int: ...
    def get_endpoint(self) -> str: ...
    def get_persistent_keepalive(self) -> int: ...
    def get_preshared_key(self) -> str: ...
    def get_preshared_key_flags(self) -> SettingSecretFlags: ...
    def get_public_key(self) -> str: ...
    def is_sealed(self) -> bool: ...
    def is_valid(self, check_non_secrets: bool, check_secrets: bool) -> bool: ...
    @classmethod
    def new(cls) -> WireGuardPeer: ...
    def new_clone(self, with_secrets: bool) -> WireGuardPeer: ...
    def ref(self) -> WireGuardPeer: ...
    def remove_allowed_ip(self, idx: int) -> bool: ...
    def seal(self) -> None: ...
    def set_endpoint(self, endpoint: str, allow_invalid: bool) -> bool: ...
    def set_persistent_keepalive(self, persistent_keepalive: int) -> None: ...
    def set_preshared_key(
        self, preshared_key: str | None, accept_invalid: bool
    ) -> bool: ...
    def set_preshared_key_flags(
        self, preshared_key_flags: _SettingSecretFlagsValueType
    ) -> None: ...
    def set_public_key(self, public_key: str | None, accept_invalid: bool) -> bool: ...
    def unref(self) -> None: ...

class ActivationStateFlags(GObject.GFlags):
    CONTROLLER_HAS_PORTS = 32
    EXTERNAL = 128
    IP4_READY = 8
    IP6_READY = 16
    IS_CONTROLLER = 1
    IS_PORT = 2
    LAYER2_READY = 4
    LIFETIME_BOUND_TO_PROFILE_VISIBILITY = 64
    NONE = 0

_ActivationStateFlagsLiteralType: TypeAlias = Literal[
    "NM_ACTIVATION_STATE_FLAG_CONTROLLER_HAS_PORTS",
    "NM_ACTIVATION_STATE_FLAG_EXTERNAL",
    "NM_ACTIVATION_STATE_FLAG_IP4_READY",
    "NM_ACTIVATION_STATE_FLAG_IP6_READY",
    "NM_ACTIVATION_STATE_FLAG_IS_CONTROLLER",
    "NM_ACTIVATION_STATE_FLAG_IS_PORT",
    "NM_ACTIVATION_STATE_FLAG_LAYER2_READY",
    "NM_ACTIVATION_STATE_FLAG_LIFETIME_BOUND_TO_PROFILE_VISIBILITY",
    "NM_ACTIVATION_STATE_FLAG_NONE",
    "controller-has-ports",
    "external",
    "ip4-ready",
    "ip6-ready",
    "is-controller",
    "is-port",
    "layer2-ready",
    "lifetime-bound-to-profile-visibility",
    "none",
]
_ActivationStateFlagsValueType: TypeAlias = (
    ActivationStateFlags
    | _ActivationStateFlagsLiteralType
    | tuple[_ActivationStateFlagsLiteralType, ...]
)

class BluetoothCapabilities(GObject.GFlags):
    DUN = 1
    NAP = 2
    NONE = 0

_BluetoothCapabilitiesLiteralType: TypeAlias = Literal[
    "NM_BT_CAPABILITY_DUN",
    "NM_BT_CAPABILITY_NAP",
    "NM_BT_CAPABILITY_NONE",
    "dun",
    "nap",
    "none",
]
_BluetoothCapabilitiesValueType: TypeAlias = (
    BluetoothCapabilities
    | _BluetoothCapabilitiesLiteralType
    | tuple[_BluetoothCapabilitiesLiteralType, ...]
)

class CheckpointCreateFlags(GObject.GFlags):
    ALLOW_OVERLAPPING = 8
    DELETE_NEW_CONNECTIONS = 2
    DESTROY_ALL = 1
    DISCONNECT_NEW_DEVICES = 4
    NONE = 0
    NO_PRESERVE_EXTERNAL_PORTS = 16
    TRACK_INTERNAL_GLOBAL_DNS = 32

_CheckpointCreateFlagsLiteralType: TypeAlias = Literal[
    "NM_CHECKPOINT_CREATE_FLAG_ALLOW_OVERLAPPING",
    "NM_CHECKPOINT_CREATE_FLAG_DELETE_NEW_CONNECTIONS",
    "NM_CHECKPOINT_CREATE_FLAG_DESTROY_ALL",
    "NM_CHECKPOINT_CREATE_FLAG_DISCONNECT_NEW_DEVICES",
    "NM_CHECKPOINT_CREATE_FLAG_NONE",
    "NM_CHECKPOINT_CREATE_FLAG_NO_PRESERVE_EXTERNAL_PORTS",
    "NM_CHECKPOINT_CREATE_FLAG_TRACK_INTERNAL_GLOBAL_DNS",
    "allow-overlapping",
    "delete-new-connections",
    "destroy-all",
    "disconnect-new-devices",
    "no-preserve-external-ports",
    "none",
    "track-internal-global-dns",
]
_CheckpointCreateFlagsValueType: TypeAlias = (
    CheckpointCreateFlags
    | _CheckpointCreateFlagsLiteralType
    | tuple[_CheckpointCreateFlagsLiteralType, ...]
)

class ClientInstanceFlags(GObject.GFlags):
    INITIALIZED_BAD = 4
    INITIALIZED_GOOD = 2
    NONE = 0
    NO_AUTO_FETCH_PERMISSIONS = 1

_ClientInstanceFlagsLiteralType: TypeAlias = Literal[
    "NM_CLIENT_INSTANCE_FLAGS_INITIALIZED_BAD",
    "NM_CLIENT_INSTANCE_FLAGS_INITIALIZED_GOOD",
    "NM_CLIENT_INSTANCE_FLAGS_NONE",
    "NM_CLIENT_INSTANCE_FLAGS_NO_AUTO_FETCH_PERMISSIONS",
    "initialized-bad",
    "initialized-good",
    "no-auto-fetch-permissions",
    "none",
]
_ClientInstanceFlagsValueType: TypeAlias = (
    ClientInstanceFlags
    | _ClientInstanceFlagsLiteralType
    | tuple[_ClientInstanceFlagsLiteralType, ...]
)

class ConnectionSerializationFlags(GObject.GFlags):
    ALL = 0
    NO_SECRETS = 1
    ONLY_SECRETS = 2
    WITH_NON_SECRET = 1
    WITH_SECRETS = 2
    WITH_SECRETS_AGENT_OWNED = 4
    WITH_SECRETS_NOT_SAVED = 16
    WITH_SECRETS_SYSTEM_OWNED = 8

_ConnectionSerializationFlagsLiteralType: TypeAlias = Literal[
    "NM_CONNECTION_SERIALIZE_ALL",
    "NM_CONNECTION_SERIALIZE_NO_SECRETS",
    "NM_CONNECTION_SERIALIZE_ONLY_SECRETS",
    "NM_CONNECTION_SERIALIZE_WITH_NON_SECRET",
    "NM_CONNECTION_SERIALIZE_WITH_SECRETS",
    "NM_CONNECTION_SERIALIZE_WITH_SECRETS_AGENT_OWNED",
    "NM_CONNECTION_SERIALIZE_WITH_SECRETS_NOT_SAVED",
    "NM_CONNECTION_SERIALIZE_WITH_SECRETS_SYSTEM_OWNED",
    "all",
    "no-secrets",
    "only-secrets",
    "with-non-secret",
    "with-secrets",
    "with-secrets-agent-owned",
    "with-secrets-not-saved",
    "with-secrets-system-owned",
]
_ConnectionSerializationFlagsValueType: TypeAlias = (
    ConnectionSerializationFlags
    | _ConnectionSerializationFlagsLiteralType
    | tuple[_ConnectionSerializationFlagsLiteralType, ...]
)

class DeviceCapabilities(GObject.GFlags):
    CARRIER_DETECT = 2
    IS_SOFTWARE = 4
    NM_SUPPORTED = 1
    NONE = 0
    SRIOV = 8

_DeviceCapabilitiesLiteralType: TypeAlias = Literal[
    "NM_DEVICE_CAP_CARRIER_DETECT",
    "NM_DEVICE_CAP_IS_SOFTWARE",
    "NM_DEVICE_CAP_NM_SUPPORTED",
    "NM_DEVICE_CAP_NONE",
    "NM_DEVICE_CAP_SRIOV",
    "carrier-detect",
    "is-software",
    "nm-supported",
    "none",
    "sriov",
]
_DeviceCapabilitiesValueType: TypeAlias = (
    DeviceCapabilities
    | _DeviceCapabilitiesLiteralType
    | tuple[_DeviceCapabilitiesLiteralType, ...]
)

class DeviceInterfaceFlags(GObject.GFlags):
    CARRIER = 65536
    LLDP_CLIENT_ENABLED = 131072
    LOWER_UP = 2
    PROMISC = 4
    UP = 1

_DeviceInterfaceFlagsLiteralType: TypeAlias = Literal[
    "NM_DEVICE_INTERFACE_FLAG_CARRIER",
    "NM_DEVICE_INTERFACE_FLAG_LLDP_CLIENT_ENABLED",
    "NM_DEVICE_INTERFACE_FLAG_LOWER_UP",
    "NM_DEVICE_INTERFACE_FLAG_PROMISC",
    "NM_DEVICE_INTERFACE_FLAG_UP",
    "carrier",
    "lldp-client-enabled",
    "lower-up",
    "promisc",
    "up",
]
_DeviceInterfaceFlagsValueType: TypeAlias = (
    DeviceInterfaceFlags
    | _DeviceInterfaceFlagsLiteralType
    | tuple[_DeviceInterfaceFlagsLiteralType, ...]
)

class DeviceManagedFlags(GObject.GFlags):
    ALL = 31
    NONE = 0
    PERMANENT = 2
    PERMANENT_BY_MAC = 8
    PERMANENT_BY_NAME = 4
    RUNTIME = 1
    SET_ADMIN_STATE = 16

_DeviceManagedFlagsLiteralType: TypeAlias = Literal[
    "NM_DEVICE_MANAGED_FLAGS_ALL",
    "NM_DEVICE_MANAGED_FLAGS_NONE",
    "NM_DEVICE_MANAGED_FLAGS_PERMANENT",
    "NM_DEVICE_MANAGED_FLAGS_PERMANENT_BY_MAC",
    "NM_DEVICE_MANAGED_FLAGS_PERMANENT_BY_NAME",
    "NM_DEVICE_MANAGED_FLAGS_RUNTIME",
    "NM_DEVICE_MANAGED_FLAGS_SET_ADMIN_STATE",
    "all",
    "none",
    "permanent",
    "permanent-by-mac",
    "permanent-by-name",
    "runtime",
    "set-admin-state",
]
_DeviceManagedFlagsValueType: TypeAlias = (
    DeviceManagedFlags
    | _DeviceManagedFlagsLiteralType
    | tuple[_DeviceManagedFlagsLiteralType, ...]
)

class DeviceModemCapabilities(GObject.GFlags):
    CDMA_EVDO = 2
    GSM_UMTS = 4
    LTE = 8
    NONE = 0
    POTS = 1

_DeviceModemCapabilitiesLiteralType: TypeAlias = Literal[
    "NM_DEVICE_MODEM_CAPABILITY_CDMA_EVDO",
    "NM_DEVICE_MODEM_CAPABILITY_GSM_UMTS",
    "NM_DEVICE_MODEM_CAPABILITY_LTE",
    "NM_DEVICE_MODEM_CAPABILITY_NONE",
    "NM_DEVICE_MODEM_CAPABILITY_POTS",
    "cdma-evdo",
    "gsm-umts",
    "lte",
    "none",
    "pots",
]
_DeviceModemCapabilitiesValueType: TypeAlias = (
    DeviceModemCapabilities
    | _DeviceModemCapabilitiesLiteralType
    | tuple[_DeviceModemCapabilitiesLiteralType, ...]
)

class DeviceReapplyFlags(GObject.GFlags):
    NONE = 0
    PRESERVE_EXTERNAL_IP = 1

_DeviceReapplyFlagsLiteralType: TypeAlias = Literal[
    "NM_DEVICE_REAPPLY_FLAGS_NONE",
    "NM_DEVICE_REAPPLY_FLAGS_PRESERVE_EXTERNAL_IP",
    "none",
    "preserve-external-ip",
]
_DeviceReapplyFlagsValueType: TypeAlias = (
    DeviceReapplyFlags
    | _DeviceReapplyFlagsLiteralType
    | tuple[_DeviceReapplyFlagsLiteralType, ...]
)

class DeviceWifiCapabilities(GObject.GFlags):
    ADHOC = 128
    AP = 64
    CIPHER_CCMP = 8
    CIPHER_TKIP = 4
    CIPHER_WEP104 = 2
    CIPHER_WEP40 = 1
    FREQ_2GHZ = 512
    FREQ_5GHZ = 1024
    FREQ_6GHZ = 2048
    FREQ_VALID = 256
    IBSS_RSN = 8192
    MESH = 4096
    NONE = 0
    RSN = 32
    WPA = 16

_DeviceWifiCapabilitiesLiteralType: TypeAlias = Literal[
    "NM_WIFI_DEVICE_CAP_ADHOC",
    "NM_WIFI_DEVICE_CAP_AP",
    "NM_WIFI_DEVICE_CAP_CIPHER_CCMP",
    "NM_WIFI_DEVICE_CAP_CIPHER_TKIP",
    "NM_WIFI_DEVICE_CAP_CIPHER_WEP104",
    "NM_WIFI_DEVICE_CAP_CIPHER_WEP40",
    "NM_WIFI_DEVICE_CAP_FREQ_2GHZ",
    "NM_WIFI_DEVICE_CAP_FREQ_5GHZ",
    "NM_WIFI_DEVICE_CAP_FREQ_6GHZ",
    "NM_WIFI_DEVICE_CAP_FREQ_VALID",
    "NM_WIFI_DEVICE_CAP_IBSS_RSN",
    "NM_WIFI_DEVICE_CAP_MESH",
    "NM_WIFI_DEVICE_CAP_NONE",
    "NM_WIFI_DEVICE_CAP_RSN",
    "NM_WIFI_DEVICE_CAP_WPA",
    "adhoc",
    "ap",
    "cipher-ccmp",
    "cipher-tkip",
    "cipher-wep104",
    "cipher-wep40",
    "freq-2ghz",
    "freq-5ghz",
    "freq-6ghz",
    "freq-valid",
    "ibss-rsn",
    "mesh",
    "none",
    "rsn",
    "wpa",
]
_DeviceWifiCapabilitiesValueType: TypeAlias = (
    DeviceWifiCapabilities
    | _DeviceWifiCapabilitiesLiteralType
    | tuple[_DeviceWifiCapabilitiesLiteralType, ...]
)

class DhcpHostnameFlags(GObject.GFlags):
    FQDN_CLEAR_FLAGS = 8
    FQDN_ENCODED = 2
    FQDN_NO_UPDATE = 4
    FQDN_SERV_UPDATE = 1
    NONE = 0

_DhcpHostnameFlagsLiteralType: TypeAlias = Literal[
    "NM_DHCP_HOSTNAME_FLAG_FQDN_CLEAR_FLAGS",
    "NM_DHCP_HOSTNAME_FLAG_FQDN_ENCODED",
    "NM_DHCP_HOSTNAME_FLAG_FQDN_NO_UPDATE",
    "NM_DHCP_HOSTNAME_FLAG_FQDN_SERV_UPDATE",
    "NM_DHCP_HOSTNAME_FLAG_NONE",
    "fqdn-clear-flags",
    "fqdn-encoded",
    "fqdn-no-update",
    "fqdn-serv-update",
    "none",
]
_DhcpHostnameFlagsValueType: TypeAlias = (
    DhcpHostnameFlags
    | _DhcpHostnameFlagsLiteralType
    | tuple[_DhcpHostnameFlagsLiteralType, ...]
)

class IPAddressCmpFlags(GObject.GFlags):
    NONE = 0
    WITH_ATTRS = 1

_IPAddressCmpFlagsLiteralType: TypeAlias = Literal[
    "NM_IP_ADDRESS_CMP_FLAGS_NONE",
    "NM_IP_ADDRESS_CMP_FLAGS_WITH_ATTRS",
    "none",
    "with-attrs",
]
_IPAddressCmpFlagsValueType: TypeAlias = (
    IPAddressCmpFlags
    | _IPAddressCmpFlagsLiteralType
    | tuple[_IPAddressCmpFlagsLiteralType, ...]
)

class IPRoutingRuleAsStringFlags(GObject.GFlags):
    AF_INET = 1
    AF_INET6 = 2
    NONE = 0
    VALIDATE = 4

_IPRoutingRuleAsStringFlagsLiteralType: TypeAlias = Literal[
    "NM_IP_ROUTING_RULE_AS_STRING_FLAGS_AF_INET",
    "NM_IP_ROUTING_RULE_AS_STRING_FLAGS_AF_INET6",
    "NM_IP_ROUTING_RULE_AS_STRING_FLAGS_NONE",
    "NM_IP_ROUTING_RULE_AS_STRING_FLAGS_VALIDATE",
    "af-inet",
    "af-inet6",
    "none",
    "validate",
]
_IPRoutingRuleAsStringFlagsValueType: TypeAlias = (
    IPRoutingRuleAsStringFlags
    | _IPRoutingRuleAsStringFlagsLiteralType
    | tuple[_IPRoutingRuleAsStringFlagsLiteralType, ...]
)

class IPTunnelFlags(GObject.GFlags):
    IP6_IGN_ENCAP_LIMIT = 1
    IP6_MIP6_DEV = 8
    IP6_RCV_DSCP_COPY = 16
    IP6_USE_ORIG_FLOWLABEL = 4
    IP6_USE_ORIG_FWMARK = 32
    IP6_USE_ORIG_TCLASS = 2
    NONE = 0

_IPTunnelFlagsLiteralType: TypeAlias = Literal[
    "NM_IP_TUNNEL_FLAG_IP6_IGN_ENCAP_LIMIT",
    "NM_IP_TUNNEL_FLAG_IP6_MIP6_DEV",
    "NM_IP_TUNNEL_FLAG_IP6_RCV_DSCP_COPY",
    "NM_IP_TUNNEL_FLAG_IP6_USE_ORIG_FLOWLABEL",
    "NM_IP_TUNNEL_FLAG_IP6_USE_ORIG_FWMARK",
    "NM_IP_TUNNEL_FLAG_IP6_USE_ORIG_TCLASS",
    "NM_IP_TUNNEL_FLAG_NONE",
    "ip6-ign-encap-limit",
    "ip6-mip6-dev",
    "ip6-rcv-dscp-copy",
    "ip6-use-orig-flowlabel",
    "ip6-use-orig-fwmark",
    "ip6-use-orig-tclass",
    "none",
]
_IPTunnelFlagsValueType: TypeAlias = (
    IPTunnelFlags | _IPTunnelFlagsLiteralType | tuple[_IPTunnelFlagsLiteralType, ...]
)

class KeyfileHandlerFlags(GObject.GFlags):
    NONE = 0

_KeyfileHandlerFlagsLiteralType: TypeAlias = Literal[
    "NM_KEYFILE_HANDLER_FLAGS_NONE", "none"
]
_KeyfileHandlerFlagsValueType: TypeAlias = (
    KeyfileHandlerFlags
    | _KeyfileHandlerFlagsLiteralType
    | tuple[_KeyfileHandlerFlagsLiteralType, ...]
)

class ManagerReloadFlags(GObject.GFlags):
    CONF = 1
    DNS_FULL = 4
    DNS_RC = 2

_ManagerReloadFlagsLiteralType: TypeAlias = Literal[
    "NM_MANAGER_RELOAD_FLAG_CONF",
    "NM_MANAGER_RELOAD_FLAG_DNS_FULL",
    "NM_MANAGER_RELOAD_FLAG_DNS_RC",
    "conf",
    "dns-full",
    "dns-rc",
]
_ManagerReloadFlagsValueType: TypeAlias = (
    ManagerReloadFlags
    | _ManagerReloadFlagsLiteralType
    | tuple[_ManagerReloadFlagsLiteralType, ...]
)

class MptcpFlags(GObject.GFlags):
    ALSO_WITHOUT_DEFAULT_ROUTE = 8
    ALSO_WITHOUT_SYSCTL = 4
    BACKUP = 64
    DISABLED = 1
    ENABLED = 2
    FULLMESH = 128
    LAMINAR = 256
    NONE = 0
    SIGNAL = 16
    SUBFLOW = 32

_MptcpFlagsLiteralType: TypeAlias = Literal[
    "NM_MPTCP_FLAGS_ALSO_WITHOUT_DEFAULT_ROUTE",
    "NM_MPTCP_FLAGS_ALSO_WITHOUT_SYSCTL",
    "NM_MPTCP_FLAGS_BACKUP",
    "NM_MPTCP_FLAGS_DISABLED",
    "NM_MPTCP_FLAGS_ENABLED",
    "NM_MPTCP_FLAGS_FULLMESH",
    "NM_MPTCP_FLAGS_LAMINAR",
    "NM_MPTCP_FLAGS_NONE",
    "NM_MPTCP_FLAGS_SIGNAL",
    "NM_MPTCP_FLAGS_SUBFLOW",
    "also-without-default-route",
    "also-without-sysctl",
    "backup",
    "disabled",
    "enabled",
    "fullmesh",
    "laminar",
    "none",
    "signal",
    "subflow",
]
_MptcpFlagsValueType: TypeAlias = (
    MptcpFlags | _MptcpFlagsLiteralType | tuple[_MptcpFlagsLiteralType, ...]
)

class RadioFlags(GObject.GFlags):
    NONE = 0
    WLAN_AVAILABLE = 1
    WWAN_AVAILABLE = 2

_RadioFlagsLiteralType: TypeAlias = Literal[
    "NM_RADIO_FLAG_NONE",
    "NM_RADIO_FLAG_WLAN_AVAILABLE",
    "NM_RADIO_FLAG_WWAN_AVAILABLE",
    "none",
    "wlan-available",
    "wwan-available",
]
_RadioFlagsValueType: TypeAlias = (
    RadioFlags | _RadioFlagsLiteralType | tuple[_RadioFlagsLiteralType, ...]
)

class SecretAgentCapabilities(GObject.GFlags):
    LAST = 1
    NONE = 0
    VPN_HINTS = 1

_SecretAgentCapabilitiesLiteralType: TypeAlias = Literal[
    "NM_SECRET_AGENT_CAPABILITY_LAST",
    "NM_SECRET_AGENT_CAPABILITY_NONE",
    "NM_SECRET_AGENT_CAPABILITY_VPN_HINTS",
    "last",
    "none",
    "vpn-hints",
]
_SecretAgentCapabilitiesValueType: TypeAlias = (
    SecretAgentCapabilities
    | _SecretAgentCapabilitiesLiteralType
    | tuple[_SecretAgentCapabilitiesLiteralType, ...]
)

class SecretAgentGetSecretsFlags(GObject.GFlags):
    ALLOW_INTERACTION = 1
    NONE = 0
    NO_ERRORS = 1073741824
    ONLY_SYSTEM = 2147483648
    REQUEST_NEW = 2
    USER_REQUESTED = 4
    WPS_PBC_ACTIVE = 8

_SecretAgentGetSecretsFlagsLiteralType: TypeAlias = Literal[
    "NM_SECRET_AGENT_GET_SECRETS_FLAG_ALLOW_INTERACTION",
    "NM_SECRET_AGENT_GET_SECRETS_FLAG_NONE",
    "NM_SECRET_AGENT_GET_SECRETS_FLAG_NO_ERRORS",
    "NM_SECRET_AGENT_GET_SECRETS_FLAG_ONLY_SYSTEM",
    "NM_SECRET_AGENT_GET_SECRETS_FLAG_REQUEST_NEW",
    "NM_SECRET_AGENT_GET_SECRETS_FLAG_USER_REQUESTED",
    "NM_SECRET_AGENT_GET_SECRETS_FLAG_WPS_PBC_ACTIVE",
    "allow-interaction",
    "no-errors",
    "none",
    "only-system",
    "request-new",
    "user-requested",
    "wps-pbc-active",
]
_SecretAgentGetSecretsFlagsValueType: TypeAlias = (
    SecretAgentGetSecretsFlags
    | _SecretAgentGetSecretsFlagsLiteralType
    | tuple[_SecretAgentGetSecretsFlagsLiteralType, ...]
)

class Setting8021xAuthFlags(GObject.GFlags):
    ALL = 511
    NONE = 0
    TLS_1_0_DISABLE = 1
    TLS_1_0_ENABLE = 32
    TLS_1_1_DISABLE = 2
    TLS_1_1_ENABLE = 64
    TLS_1_2_DISABLE = 4
    TLS_1_2_ENABLE = 128
    TLS_1_3_DISABLE = 16
    TLS_1_3_ENABLE = 256
    TLS_DISABLE_TIME_CHECKS = 8

_Setting8021xAuthFlagsLiteralType: TypeAlias = Literal[
    "NM_SETTING_802_1X_AUTH_FLAGS_ALL",
    "NM_SETTING_802_1X_AUTH_FLAGS_NONE",
    "NM_SETTING_802_1X_AUTH_FLAGS_TLS_1_0_DISABLE",
    "NM_SETTING_802_1X_AUTH_FLAGS_TLS_1_0_ENABLE",
    "NM_SETTING_802_1X_AUTH_FLAGS_TLS_1_1_DISABLE",
    "NM_SETTING_802_1X_AUTH_FLAGS_TLS_1_1_ENABLE",
    "NM_SETTING_802_1X_AUTH_FLAGS_TLS_1_2_DISABLE",
    "NM_SETTING_802_1X_AUTH_FLAGS_TLS_1_2_ENABLE",
    "NM_SETTING_802_1X_AUTH_FLAGS_TLS_1_3_DISABLE",
    "NM_SETTING_802_1X_AUTH_FLAGS_TLS_1_3_ENABLE",
    "NM_SETTING_802_1X_AUTH_FLAGS_TLS_DISABLE_TIME_CHECKS",
    "all",
    "none",
    "tls-1-0-disable",
    "tls-1-0-enable",
    "tls-1-1-disable",
    "tls-1-1-enable",
    "tls-1-2-disable",
    "tls-1-2-enable",
    "tls-1-3-disable",
    "tls-1-3-enable",
    "tls-disable-time-checks",
]
_Setting8021xAuthFlagsValueType: TypeAlias = (
    Setting8021xAuthFlags
    | _Setting8021xAuthFlagsLiteralType
    | tuple[_Setting8021xAuthFlagsLiteralType, ...]
)

class SettingDcbFlags(GObject.GFlags):
    ADVERTISE = 2
    ENABLE = 1
    NONE = 0
    WILLING = 4

_SettingDcbFlagsLiteralType: TypeAlias = Literal[
    "NM_SETTING_DCB_FLAG_ADVERTISE",
    "NM_SETTING_DCB_FLAG_ENABLE",
    "NM_SETTING_DCB_FLAG_NONE",
    "NM_SETTING_DCB_FLAG_WILLING",
    "advertise",
    "enable",
    "none",
    "willing",
]
_SettingDcbFlagsValueType: TypeAlias = (
    SettingDcbFlags
    | _SettingDcbFlagsLiteralType
    | tuple[_SettingDcbFlagsLiteralType, ...]
)

class SettingEthtoolFecMode(GObject.GFlags):
    AUTO = 2
    BASER = 16
    LLRS = 32
    OFF = 4
    RS = 8

_SettingEthtoolFecModeLiteralType: TypeAlias = Literal[
    "NM_SETTING_ETHTOOL_FEC_MODE_AUTO",
    "NM_SETTING_ETHTOOL_FEC_MODE_BASER",
    "NM_SETTING_ETHTOOL_FEC_MODE_LLRS",
    "NM_SETTING_ETHTOOL_FEC_MODE_OFF",
    "NM_SETTING_ETHTOOL_FEC_MODE_RS",
    "auto",
    "baser",
    "llrs",
    "off",
    "rs",
]
_SettingEthtoolFecModeValueType: TypeAlias = (
    SettingEthtoolFecMode
    | _SettingEthtoolFecModeLiteralType
    | tuple[_SettingEthtoolFecModeLiteralType, ...]
)

class SettingSecretFlags(GObject.GFlags):
    AGENT_OWNED = 1
    NONE = 0
    NOT_REQUIRED = 4
    NOT_SAVED = 2

_SettingSecretFlagsLiteralType: TypeAlias = Literal[
    "NM_SETTING_SECRET_FLAG_AGENT_OWNED",
    "NM_SETTING_SECRET_FLAG_NONE",
    "NM_SETTING_SECRET_FLAG_NOT_REQUIRED",
    "NM_SETTING_SECRET_FLAG_NOT_SAVED",
    "agent-owned",
    "none",
    "not-required",
    "not-saved",
]
_SettingSecretFlagsValueType: TypeAlias = (
    SettingSecretFlags
    | _SettingSecretFlagsLiteralType
    | tuple[_SettingSecretFlagsLiteralType, ...]
)

class SettingWiredWakeOnLan(GObject.GFlags):
    ARP = 32
    BROADCAST = 16
    DEFAULT = 1
    IGNORE = 32768
    MAGIC = 64
    MULTICAST = 8
    PHY = 2
    UNICAST = 4

_SettingWiredWakeOnLanLiteralType: TypeAlias = Literal[
    "NM_SETTING_WIRED_WAKE_ON_LAN_ARP",
    "NM_SETTING_WIRED_WAKE_ON_LAN_BROADCAST",
    "NM_SETTING_WIRED_WAKE_ON_LAN_DEFAULT",
    "NM_SETTING_WIRED_WAKE_ON_LAN_IGNORE",
    "NM_SETTING_WIRED_WAKE_ON_LAN_MAGIC",
    "NM_SETTING_WIRED_WAKE_ON_LAN_MULTICAST",
    "NM_SETTING_WIRED_WAKE_ON_LAN_PHY",
    "NM_SETTING_WIRED_WAKE_ON_LAN_UNICAST",
    "arp",
    "broadcast",
    "default",
    "ignore",
    "magic",
    "multicast",
    "phy",
    "unicast",
]
_SettingWiredWakeOnLanValueType: TypeAlias = (
    SettingWiredWakeOnLan
    | _SettingWiredWakeOnLanLiteralType
    | tuple[_SettingWiredWakeOnLanLiteralType, ...]
)

class SettingWirelessSecurityWpsMethod(GObject.GFlags):
    AUTO = 2
    DEFAULT = 0
    DISABLED = 1
    PBC = 4
    PIN = 8

_SettingWirelessSecurityWpsMethodLiteralType: TypeAlias = Literal[
    "NM_SETTING_WIRELESS_SECURITY_WPS_METHOD_AUTO",
    "NM_SETTING_WIRELESS_SECURITY_WPS_METHOD_DEFAULT",
    "NM_SETTING_WIRELESS_SECURITY_WPS_METHOD_DISABLED",
    "NM_SETTING_WIRELESS_SECURITY_WPS_METHOD_PBC",
    "NM_SETTING_WIRELESS_SECURITY_WPS_METHOD_PIN",
    "auto",
    "default",
    "disabled",
    "pbc",
    "pin",
]
_SettingWirelessSecurityWpsMethodValueType: TypeAlias = (
    SettingWirelessSecurityWpsMethod
    | _SettingWirelessSecurityWpsMethodLiteralType
    | tuple[_SettingWirelessSecurityWpsMethodLiteralType, ...]
)

class SettingWirelessWakeOnWLan(GObject.GFlags):
    ALL = 510
    ANY = 2
    DEFAULT = 1
    DISCONNECT = 4
    EAP_IDENTITY_REQUEST = 32
    GTK_REKEY_FAILURE = 16
    IGNORE = 32768
    MAGIC = 8
    RFKILL_RELEASE = 128
    TCP = 256

_SettingWirelessWakeOnWLanLiteralType: TypeAlias = Literal[
    "4way-handshake",
    "NM_SETTING_WIRELESS_WAKE_ON_WLAN_4WAY_HANDSHAKE",
    "NM_SETTING_WIRELESS_WAKE_ON_WLAN_ALL",
    "NM_SETTING_WIRELESS_WAKE_ON_WLAN_ANY",
    "NM_SETTING_WIRELESS_WAKE_ON_WLAN_DEFAULT",
    "NM_SETTING_WIRELESS_WAKE_ON_WLAN_DISCONNECT",
    "NM_SETTING_WIRELESS_WAKE_ON_WLAN_EAP_IDENTITY_REQUEST",
    "NM_SETTING_WIRELESS_WAKE_ON_WLAN_GTK_REKEY_FAILURE",
    "NM_SETTING_WIRELESS_WAKE_ON_WLAN_IGNORE",
    "NM_SETTING_WIRELESS_WAKE_ON_WLAN_MAGIC",
    "NM_SETTING_WIRELESS_WAKE_ON_WLAN_RFKILL_RELEASE",
    "NM_SETTING_WIRELESS_WAKE_ON_WLAN_TCP",
    "all",
    "any",
    "default",
    "disconnect",
    "eap-identity-request",
    "gtk-rekey-failure",
    "ignore",
    "magic",
    "rfkill-release",
    "tcp",
]
_SettingWirelessWakeOnWLanValueType: TypeAlias = (
    SettingWirelessWakeOnWLan
    | _SettingWirelessWakeOnWLanLiteralType
    | tuple[_SettingWirelessWakeOnWLanLiteralType, ...]
)

class SettingsAddConnection2Flags(GObject.GFlags):
    BLOCK_AUTOCONNECT = 32
    IN_MEMORY = 2
    NONE = 0
    TO_DISK = 1

_SettingsAddConnection2FlagsLiteralType: TypeAlias = Literal[
    "NM_SETTINGS_ADD_CONNECTION2_FLAG_BLOCK_AUTOCONNECT",
    "NM_SETTINGS_ADD_CONNECTION2_FLAG_IN_MEMORY",
    "NM_SETTINGS_ADD_CONNECTION2_FLAG_NONE",
    "NM_SETTINGS_ADD_CONNECTION2_FLAG_TO_DISK",
    "block-autoconnect",
    "in-memory",
    "none",
    "to-disk",
]
_SettingsAddConnection2FlagsValueType: TypeAlias = (
    SettingsAddConnection2Flags
    | _SettingsAddConnection2FlagsLiteralType
    | tuple[_SettingsAddConnection2FlagsLiteralType, ...]
)

class SettingsConnectionFlags(GObject.GFlags):
    EXTERNAL = 8
    NM_GENERATED = 2
    NONE = 0
    UNSAVED = 1
    VOLATILE = 4

_SettingsConnectionFlagsLiteralType: TypeAlias = Literal[
    "NM_SETTINGS_CONNECTION_FLAG_EXTERNAL",
    "NM_SETTINGS_CONNECTION_FLAG_NM_GENERATED",
    "NM_SETTINGS_CONNECTION_FLAG_NONE",
    "NM_SETTINGS_CONNECTION_FLAG_UNSAVED",
    "NM_SETTINGS_CONNECTION_FLAG_VOLATILE",
    "external",
    "nm-generated",
    "none",
    "unsaved",
    "volatile",
]
_SettingsConnectionFlagsValueType: TypeAlias = (
    SettingsConnectionFlags
    | _SettingsConnectionFlagsLiteralType
    | tuple[_SettingsConnectionFlagsLiteralType, ...]
)

class SettingsUpdate2Flags(GObject.GFlags):
    BLOCK_AUTOCONNECT = 32
    IN_MEMORY = 2
    IN_MEMORY_DETACHED = 4
    IN_MEMORY_ONLY = 8
    NONE = 0
    NO_REAPPLY = 64
    TO_DISK = 1
    VOLATILE = 16

_SettingsUpdate2FlagsLiteralType: TypeAlias = Literal[
    "NM_SETTINGS_UPDATE2_FLAG_BLOCK_AUTOCONNECT",
    "NM_SETTINGS_UPDATE2_FLAG_IN_MEMORY",
    "NM_SETTINGS_UPDATE2_FLAG_IN_MEMORY_DETACHED",
    "NM_SETTINGS_UPDATE2_FLAG_IN_MEMORY_ONLY",
    "NM_SETTINGS_UPDATE2_FLAG_NONE",
    "NM_SETTINGS_UPDATE2_FLAG_NO_REAPPLY",
    "NM_SETTINGS_UPDATE2_FLAG_TO_DISK",
    "NM_SETTINGS_UPDATE2_FLAG_VOLATILE",
    "block-autoconnect",
    "in-memory",
    "in-memory-detached",
    "in-memory-only",
    "no-reapply",
    "none",
    "to-disk",
    "volatile",
]
_SettingsUpdate2FlagsValueType: TypeAlias = (
    SettingsUpdate2Flags
    | _SettingsUpdate2FlagsLiteralType
    | tuple[_SettingsUpdate2FlagsLiteralType, ...]
)

class TeamLinkWatcherArpPingFlags(GObject.GFlags):
    SEND_ALWAYS = 8
    VALIDATE_ACTIVE = 2
    VALIDATE_INACTIVE = 4

_TeamLinkWatcherArpPingFlagsLiteralType: TypeAlias = Literal[
    "NM_TEAM_LINK_WATCHER_ARP_PING_FLAG_SEND_ALWAYS",
    "NM_TEAM_LINK_WATCHER_ARP_PING_FLAG_VALIDATE_ACTIVE",
    "NM_TEAM_LINK_WATCHER_ARP_PING_FLAG_VALIDATE_INACTIVE",
    "send-always",
    "validate-active",
    "validate-inactive",
]
_TeamLinkWatcherArpPingFlagsValueType: TypeAlias = (
    TeamLinkWatcherArpPingFlags
    | _TeamLinkWatcherArpPingFlagsLiteralType
    | tuple[_TeamLinkWatcherArpPingFlagsLiteralType, ...]
)

class VlanFlags(GObject.GFlags):
    GVRP = 2
    LOOSE_BINDING = 4
    MVRP = 8
    REORDER_HEADERS = 1

_VlanFlagsLiteralType: TypeAlias = Literal[
    "NM_VLAN_FLAG_GVRP",
    "NM_VLAN_FLAG_LOOSE_BINDING",
    "NM_VLAN_FLAG_MVRP",
    "NM_VLAN_FLAG_REORDER_HEADERS",
    "gvrp",
    "loose-binding",
    "mvrp",
    "reorder-headers",
]
_VlanFlagsValueType: TypeAlias = (
    VlanFlags | _VlanFlagsLiteralType | tuple[_VlanFlagsLiteralType, ...]
)

class VpnEditorPluginCapability(GObject.GFlags):
    EXPORT = 2
    IMPORT = 1
    IPV6 = 4
    NONE = 0
    NO_EDITOR = 8

_VpnEditorPluginCapabilityLiteralType: TypeAlias = Literal[
    "NM_VPN_EDITOR_PLUGIN_CAPABILITY_EXPORT",
    "NM_VPN_EDITOR_PLUGIN_CAPABILITY_IMPORT",
    "NM_VPN_EDITOR_PLUGIN_CAPABILITY_IPV6",
    "NM_VPN_EDITOR_PLUGIN_CAPABILITY_NONE",
    "NM_VPN_EDITOR_PLUGIN_CAPABILITY_NO_EDITOR",
    "export",
    "import",
    "ipv6",
    "no-editor",
    "none",
]
_VpnEditorPluginCapabilityValueType: TypeAlias = (
    VpnEditorPluginCapability
    | _VpnEditorPluginCapabilityLiteralType
    | tuple[_VpnEditorPluginCapabilityLiteralType, ...]
)

class ActiveConnectionState(GObject.GEnum):
    ACTIVATED = 2
    ACTIVATING = 1
    DEACTIVATED = 4
    DEACTIVATING = 3
    UNKNOWN = 0

_ActiveConnectionStateLiteralType: TypeAlias = Literal[
    "NM_ACTIVE_CONNECTION_STATE_ACTIVATED",
    "NM_ACTIVE_CONNECTION_STATE_ACTIVATING",
    "NM_ACTIVE_CONNECTION_STATE_DEACTIVATED",
    "NM_ACTIVE_CONNECTION_STATE_DEACTIVATING",
    "NM_ACTIVE_CONNECTION_STATE_UNKNOWN",
    "activated",
    "activating",
    "deactivated",
    "deactivating",
    "unknown",
]
_ActiveConnectionStateValueType: TypeAlias = (
    ActiveConnectionState | _ActiveConnectionStateLiteralType
)

class ActiveConnectionStateReason(GObject.GEnum):
    CONNECTION_REMOVED = 11
    CONNECT_TIMEOUT = 6
    DEPENDENCY_FAILED = 12
    DEVICE_DISCONNECTED = 3
    DEVICE_REALIZE_FAILED = 13
    DEVICE_REMOVED = 14
    IP_CONFIG_INVALID = 5
    LOGIN_FAILED = 10
    NONE = 1
    NO_SECRETS = 9
    SERVICE_START_FAILED = 8
    SERVICE_START_TIMEOUT = 7
    SERVICE_STOPPED = 4
    UNKNOWN = 0
    USER_DISCONNECTED = 2

_ActiveConnectionStateReasonLiteralType: TypeAlias = Literal[
    "NM_ACTIVE_CONNECTION_STATE_REASON_CONNECTION_REMOVED",
    "NM_ACTIVE_CONNECTION_STATE_REASON_CONNECT_TIMEOUT",
    "NM_ACTIVE_CONNECTION_STATE_REASON_DEPENDENCY_FAILED",
    "NM_ACTIVE_CONNECTION_STATE_REASON_DEVICE_DISCONNECTED",
    "NM_ACTIVE_CONNECTION_STATE_REASON_DEVICE_REALIZE_FAILED",
    "NM_ACTIVE_CONNECTION_STATE_REASON_DEVICE_REMOVED",
    "NM_ACTIVE_CONNECTION_STATE_REASON_IP_CONFIG_INVALID",
    "NM_ACTIVE_CONNECTION_STATE_REASON_LOGIN_FAILED",
    "NM_ACTIVE_CONNECTION_STATE_REASON_NONE",
    "NM_ACTIVE_CONNECTION_STATE_REASON_NO_SECRETS",
    "NM_ACTIVE_CONNECTION_STATE_REASON_SERVICE_START_FAILED",
    "NM_ACTIVE_CONNECTION_STATE_REASON_SERVICE_START_TIMEOUT",
    "NM_ACTIVE_CONNECTION_STATE_REASON_SERVICE_STOPPED",
    "NM_ACTIVE_CONNECTION_STATE_REASON_UNKNOWN",
    "NM_ACTIVE_CONNECTION_STATE_REASON_USER_DISCONNECTED",
    "connect-timeout",
    "connection-removed",
    "dependency-failed",
    "device-disconnected",
    "device-realize-failed",
    "device-removed",
    "ip-config-invalid",
    "login-failed",
    "no-secrets",
    "none",
    "service-start-failed",
    "service-start-timeout",
    "service-stopped",
    "unknown",
    "user-disconnected",
]
_ActiveConnectionStateReasonValueType: TypeAlias = (
    ActiveConnectionStateReason | _ActiveConnectionStateReasonLiteralType
)

class AgentManagerError(GObject.GEnum):
    FAILED = 0
    INVALIDIDENTIFIER = 2
    NOSECRETS = 4
    NOTREGISTERED = 3
    PERMISSIONDENIED = 1
    USERCANCELED = 5
    @staticmethod
    def quark() -> int: ...

_AgentManagerErrorLiteralType: TypeAlias = Literal[
    "Failed",
    "InvalidIdentifier",
    "NM_AGENT_MANAGER_ERROR_FAILED",
    "NM_AGENT_MANAGER_ERROR_INVALID_IDENTIFIER",
    "NM_AGENT_MANAGER_ERROR_NOT_REGISTERED",
    "NM_AGENT_MANAGER_ERROR_NO_SECRETS",
    "NM_AGENT_MANAGER_ERROR_PERMISSION_DENIED",
    "NM_AGENT_MANAGER_ERROR_USER_CANCELED",
    "NoSecrets",
    "NotRegistered",
    "PermissionDenied",
    "UserCanceled",
]
_AgentManagerErrorValueType: TypeAlias = (
    AgentManagerError | _AgentManagerErrorLiteralType
)

class Capability(GObject.GEnum):
    OVS = 2
    TEAM = 1

_CapabilityLiteralType: TypeAlias = Literal[
    "NM_CAPABILITY_OVS", "NM_CAPABILITY_TEAM", "ovs", "team"
]
_CapabilityValueType: TypeAlias = Capability | _CapabilityLiteralType

class ClientError(GObject.GEnum):
    FAILED = 0
    MANAGER_NOT_RUNNING = 1
    OBJECT_CREATION_FAILED = 2
    @staticmethod
    def quark() -> int: ...

_ClientErrorLiteralType: TypeAlias = Literal[
    "NM_CLIENT_ERROR_FAILED",
    "NM_CLIENT_ERROR_MANAGER_NOT_RUNNING",
    "NM_CLIENT_ERROR_OBJECT_CREATION_FAILED",
    "failed",
    "manager-not-running",
    "object-creation-failed",
]
_ClientErrorValueType: TypeAlias = ClientError | _ClientErrorLiteralType

class ClientPermission(GObject.GEnum):
    CHECKPOINT_ROLLBACK = 14
    ENABLE_DISABLE_CONNECTIVITY_CHECK = 16
    ENABLE_DISABLE_NETWORK = 1
    ENABLE_DISABLE_STATISTICS = 15
    ENABLE_DISABLE_WIFI = 2
    ENABLE_DISABLE_WIMAX = 4
    ENABLE_DISABLE_WWAN = 3
    LAST = 17
    NETWORK_CONTROL = 6
    NONE = 0
    RELOAD = 13
    SETTINGS_MODIFY_GLOBAL_DNS = 12
    SETTINGS_MODIFY_HOSTNAME = 11
    SETTINGS_MODIFY_OWN = 10
    SETTINGS_MODIFY_SYSTEM = 9
    SLEEP_WAKE = 5
    WIFI_SCAN = 17
    WIFI_SHARE_OPEN = 8
    WIFI_SHARE_PROTECTED = 7

_ClientPermissionLiteralType: TypeAlias = Literal[
    "NM_CLIENT_PERMISSION_CHECKPOINT_ROLLBACK",
    "NM_CLIENT_PERMISSION_ENABLE_DISABLE_CONNECTIVITY_CHECK",
    "NM_CLIENT_PERMISSION_ENABLE_DISABLE_NETWORK",
    "NM_CLIENT_PERMISSION_ENABLE_DISABLE_STATISTICS",
    "NM_CLIENT_PERMISSION_ENABLE_DISABLE_WIFI",
    "NM_CLIENT_PERMISSION_ENABLE_DISABLE_WIMAX",
    "NM_CLIENT_PERMISSION_ENABLE_DISABLE_WWAN",
    "NM_CLIENT_PERMISSION_NETWORK_CONTROL",
    "NM_CLIENT_PERMISSION_NONE",
    "NM_CLIENT_PERMISSION_RELOAD",
    "NM_CLIENT_PERMISSION_SETTINGS_MODIFY_GLOBAL_DNS",
    "NM_CLIENT_PERMISSION_SETTINGS_MODIFY_HOSTNAME",
    "NM_CLIENT_PERMISSION_SETTINGS_MODIFY_OWN",
    "NM_CLIENT_PERMISSION_SETTINGS_MODIFY_SYSTEM",
    "NM_CLIENT_PERMISSION_SLEEP_WAKE",
    "NM_CLIENT_PERMISSION_WIFI_SCAN",
    "NM_CLIENT_PERMISSION_WIFI_SHARE_OPEN",
    "NM_CLIENT_PERMISSION_WIFI_SHARE_PROTECTED",
    "checkpoint-rollback",
    "enable-disable-connectivity-check",
    "enable-disable-network",
    "enable-disable-statistics",
    "enable-disable-wifi",
    "enable-disable-wimax",
    "enable-disable-wwan",
    "network-control",
    "none",
    "reload",
    "settings-modify-global-dns",
    "settings-modify-hostname",
    "settings-modify-own",
    "settings-modify-system",
    "sleep-wake",
    "wifi-scan",
    "wifi-share-open",
    "wifi-share-protected",
]
_ClientPermissionValueType: TypeAlias = ClientPermission | _ClientPermissionLiteralType

class ClientPermissionResult(GObject.GEnum):
    AUTH = 2
    NO = 3
    UNKNOWN = 0
    YES = 1

_ClientPermissionResultLiteralType: TypeAlias = Literal[
    "NM_CLIENT_PERMISSION_RESULT_AUTH",
    "NM_CLIENT_PERMISSION_RESULT_NO",
    "NM_CLIENT_PERMISSION_RESULT_UNKNOWN",
    "NM_CLIENT_PERMISSION_RESULT_YES",
    "auth",
    "no",
    "unknown",
    "yes",
]
_ClientPermissionResultValueType: TypeAlias = (
    ClientPermissionResult | _ClientPermissionResultLiteralType
)

class ConnectionError(GObject.GEnum):
    FAILED = 0
    INVALIDPROPERTY = 7
    INVALIDSETTING = 5
    MISSINGPROPERTY = 6
    MISSINGSETTING = 4
    PROPERTYNOTFOUND = 2
    PROPERTYNOTSECRET = 3
    SETTINGNOTFOUND = 1
    @staticmethod
    def quark() -> int: ...

_ConnectionErrorLiteralType: TypeAlias = Literal[
    "Failed",
    "InvalidProperty",
    "InvalidSetting",
    "MissingProperty",
    "MissingSetting",
    "NM_CONNECTION_ERROR_FAILED",
    "NM_CONNECTION_ERROR_INVALID_PROPERTY",
    "NM_CONNECTION_ERROR_INVALID_SETTING",
    "NM_CONNECTION_ERROR_MISSING_PROPERTY",
    "NM_CONNECTION_ERROR_MISSING_SETTING",
    "NM_CONNECTION_ERROR_PROPERTY_NOT_FOUND",
    "NM_CONNECTION_ERROR_PROPERTY_NOT_SECRET",
    "NM_CONNECTION_ERROR_SETTING_NOT_FOUND",
    "PropertyNotFound",
    "PropertyNotSecret",
    "SettingNotFound",
]
_ConnectionErrorValueType: TypeAlias = ConnectionError | _ConnectionErrorLiteralType

class ConnectionMultiConnect(GObject.GEnum):
    DEFAULT = 0
    MANUAL_MULTIPLE = 2
    MULTIPLE = 3
    SINGLE = 1

_ConnectionMultiConnectLiteralType: TypeAlias = Literal[
    "NM_CONNECTION_MULTI_CONNECT_DEFAULT",
    "NM_CONNECTION_MULTI_CONNECT_MANUAL_MULTIPLE",
    "NM_CONNECTION_MULTI_CONNECT_MULTIPLE",
    "NM_CONNECTION_MULTI_CONNECT_SINGLE",
    "default",
    "manual-multiple",
    "multiple",
    "single",
]
_ConnectionMultiConnectValueType: TypeAlias = (
    ConnectionMultiConnect | _ConnectionMultiConnectLiteralType
)

class ConnectivityState(GObject.GEnum):
    FULL = 4
    LIMITED = 3
    NONE = 1
    PORTAL = 2
    UNKNOWN = 0

_ConnectivityStateLiteralType: TypeAlias = Literal[
    "NM_CONNECTIVITY_FULL",
    "NM_CONNECTIVITY_LIMITED",
    "NM_CONNECTIVITY_NONE",
    "NM_CONNECTIVITY_PORTAL",
    "NM_CONNECTIVITY_UNKNOWN",
    "full",
    "limited",
    "none",
    "portal",
    "unknown",
]
_ConnectivityStateValueType: TypeAlias = (
    ConnectivityState | _ConnectivityStateLiteralType
)

class CryptoError(GObject.GEnum):
    DECRYPTION_FAILED = 4
    ENCRYPTION_FAILED = 5
    FAILED = 0
    INVALID_DATA = 1
    INVALID_PASSWORD = 2
    UNKNOWN_CIPHER = 3
    @staticmethod
    def quark() -> int: ...

_CryptoErrorLiteralType: TypeAlias = Literal[
    "NM_CRYPTO_ERROR_DECRYPTION_FAILED",
    "NM_CRYPTO_ERROR_ENCRYPTION_FAILED",
    "NM_CRYPTO_ERROR_FAILED",
    "NM_CRYPTO_ERROR_INVALID_DATA",
    "NM_CRYPTO_ERROR_INVALID_PASSWORD",
    "NM_CRYPTO_ERROR_UNKNOWN_CIPHER",
    "decryption-failed",
    "encryption-failed",
    "failed",
    "invalid-data",
    "invalid-password",
    "unknown-cipher",
]
_CryptoErrorValueType: TypeAlias = CryptoError | _CryptoErrorLiteralType

class DeviceError(GObject.GEnum):
    CREATIONFAILED = 1
    FAILED = 0
    INCOMPATIBLECONNECTION = 3
    INVALIDARGUMENT = 10
    INVALIDCONNECTION = 2
    MISSINGDEPENDENCIES = 9
    NOTACTIVE = 4
    NOTALLOWED = 6
    NOTSOFTWARE = 5
    SPECIFICOBJECTNOTFOUND = 7
    VERSIONIDMISMATCH = 8
    @staticmethod
    def quark() -> int: ...

_DeviceErrorLiteralType: TypeAlias = Literal[
    "CreationFailed",
    "Failed",
    "IncompatibleConnection",
    "InvalidArgument",
    "InvalidConnection",
    "MissingDependencies",
    "NM_DEVICE_ERROR_CREATION_FAILED",
    "NM_DEVICE_ERROR_FAILED",
    "NM_DEVICE_ERROR_INCOMPATIBLE_CONNECTION",
    "NM_DEVICE_ERROR_INVALID_ARGUMENT",
    "NM_DEVICE_ERROR_INVALID_CONNECTION",
    "NM_DEVICE_ERROR_MISSING_DEPENDENCIES",
    "NM_DEVICE_ERROR_NOT_ACTIVE",
    "NM_DEVICE_ERROR_NOT_ALLOWED",
    "NM_DEVICE_ERROR_NOT_SOFTWARE",
    "NM_DEVICE_ERROR_SPECIFIC_OBJECT_NOT_FOUND",
    "NM_DEVICE_ERROR_VERSION_ID_MISMATCH",
    "NotActive",
    "NotAllowed",
    "NotSoftware",
    "SpecificObjectNotFound",
    "VersionIdMismatch",
]
_DeviceErrorValueType: TypeAlias = DeviceError | _DeviceErrorLiteralType

class DeviceManaged(GObject.GEnum):
    NO = 0
    RESET = 2
    YES = 1

_DeviceManagedLiteralType: TypeAlias = Literal[
    "NM_DEVICE_MANAGED_NO",
    "NM_DEVICE_MANAGED_RESET",
    "NM_DEVICE_MANAGED_YES",
    "no",
    "reset",
    "yes",
]
_DeviceManagedValueType: TypeAlias = DeviceManaged | _DeviceManagedLiteralType

class DeviceState(GObject.GEnum):
    ACTIVATED = 100
    CONFIG = 50
    DEACTIVATING = 110
    DISCONNECTED = 30
    FAILED = 120
    IP_CHECK = 80
    IP_CONFIG = 70
    NEED_AUTH = 60
    PREPARE = 40
    SECONDARIES = 90
    UNAVAILABLE = 20
    UNKNOWN = 0
    UNMANAGED = 10

_DeviceStateLiteralType: TypeAlias = Literal[
    "NM_DEVICE_STATE_ACTIVATED",
    "NM_DEVICE_STATE_CONFIG",
    "NM_DEVICE_STATE_DEACTIVATING",
    "NM_DEVICE_STATE_DISCONNECTED",
    "NM_DEVICE_STATE_FAILED",
    "NM_DEVICE_STATE_IP_CHECK",
    "NM_DEVICE_STATE_IP_CONFIG",
    "NM_DEVICE_STATE_NEED_AUTH",
    "NM_DEVICE_STATE_PREPARE",
    "NM_DEVICE_STATE_SECONDARIES",
    "NM_DEVICE_STATE_UNAVAILABLE",
    "NM_DEVICE_STATE_UNKNOWN",
    "NM_DEVICE_STATE_UNMANAGED",
    "activated",
    "config",
    "deactivating",
    "disconnected",
    "failed",
    "ip-check",
    "ip-config",
    "need-auth",
    "prepare",
    "secondaries",
    "unavailable",
    "unknown",
    "unmanaged",
]
_DeviceStateValueType: TypeAlias = DeviceState | _DeviceStateLiteralType

class DeviceStateReason(GObject.GEnum):
    AUTOIP_ERROR = 21
    AUTOIP_FAILED = 22
    AUTOIP_START_FAILED = 20
    BR2684_FAILED = 51
    BT_FAILED = 44
    CARRIER = 40
    CONFIG_FAILED = 4
    CONNECTION_ASSUMED = 41
    CONNECTION_REMOVED = 38
    DCB_FCOE_FAILED = 55
    DEPENDENCY_FAILED = 50
    DEVICE_HANDLER_FAILED = 68
    DHCP_ERROR = 16
    DHCP_FAILED = 17
    DHCP_START_FAILED = 15
    FIRMWARE_MISSING = 35
    GSM_APN_FAILED = 29
    GSM_PIN_CHECK_FAILED = 34
    GSM_REGISTRATION_DENIED = 31
    GSM_REGISTRATION_FAILED = 33
    GSM_REGISTRATION_NOT_SEARCHING = 30
    GSM_REGISTRATION_TIMEOUT = 32
    GSM_SIM_NOT_INSERTED = 45
    GSM_SIM_PIN_REQUIRED = 46
    GSM_SIM_PUK_REQUIRED = 47
    GSM_SIM_WRONG = 48
    INFINIBAND_MODE = 49
    IP_ADDRESS_DUPLICATE = 64
    IP_CONFIG_EXPIRED = 6
    IP_CONFIG_UNAVAILABLE = 5
    IP_METHOD_UNSUPPORTED = 65
    MODEM_AVAILABLE = 58
    MODEM_BUSY = 23
    MODEM_DIAL_FAILED = 27
    MODEM_DIAL_TIMEOUT = 26
    MODEM_FAILED = 57
    MODEM_INIT_FAILED = 28
    MODEM_MANAGER_UNAVAILABLE = 52
    MODEM_NOT_FOUND = 43
    MODEM_NO_CARRIER = 25
    MODEM_NO_DIAL_TONE = 24
    MODEM_NO_OPERATOR_CODE = 79
    NETWORKING_OFF = 78
    NEW_ACTIVATION = 60
    NONE = 0
    NOW_MANAGED = 2
    NOW_UNMANAGED = 3
    NO_SECRETS = 7
    OVSDB_FAILED = 63
    PARENT_CHANGED = 61
    PARENT_MANAGED_CHANGED = 62
    PEER_NOT_FOUND = 67
    PPP_DISCONNECT = 13
    PPP_FAILED = 14
    PPP_START_FAILED = 12
    REMOVED = 36
    SECONDARY_CONNECTION_FAILED = 54
    SHARED_FAILED = 19
    SHARED_START_FAILED = 18
    SIM_PIN_INCORRECT = 59
    SLEEPING = 37
    SRIOV_CONFIGURATION_FAILED = 66
    SSID_NOT_FOUND = 53
    SUPPLICANT_AVAILABLE = 42
    SUPPLICANT_CONFIG_FAILED = 9
    SUPPLICANT_DISCONNECT = 8
    SUPPLICANT_FAILED = 10
    SUPPLICANT_TIMEOUT = 11
    TEAMD_CONTROL_FAILED = 56
    UNKNOWN = 1
    UNMANAGED_BY_DEFAULT = 69
    UNMANAGED_EXTERNAL_DOWN = 70
    UNMANAGED_LINK_NOT_INIT = 71
    UNMANAGED_MANAGER_DISABLED = 73
    UNMANAGED_QUITTING = 72
    UNMANAGED_SLEEPING = 73
    UNMANAGED_USER_CONF = 74
    UNMANAGED_USER_EXPLICIT = 75
    UNMANAGED_USER_SETTINGS = 76
    UNMANAGED_USER_UDEV = 77
    USER_REQUESTED = 39

_DeviceStateReasonLiteralType: TypeAlias = Literal[
    "NM_DEVICE_STATE_REASON_AUTOIP_ERROR",
    "NM_DEVICE_STATE_REASON_AUTOIP_FAILED",
    "NM_DEVICE_STATE_REASON_AUTOIP_START_FAILED",
    "NM_DEVICE_STATE_REASON_BR2684_FAILED",
    "NM_DEVICE_STATE_REASON_BT_FAILED",
    "NM_DEVICE_STATE_REASON_CARRIER",
    "NM_DEVICE_STATE_REASON_CONFIG_FAILED",
    "NM_DEVICE_STATE_REASON_CONNECTION_ASSUMED",
    "NM_DEVICE_STATE_REASON_CONNECTION_REMOVED",
    "NM_DEVICE_STATE_REASON_DCB_FCOE_FAILED",
    "NM_DEVICE_STATE_REASON_DEPENDENCY_FAILED",
    "NM_DEVICE_STATE_REASON_DEVICE_HANDLER_FAILED",
    "NM_DEVICE_STATE_REASON_DHCP_ERROR",
    "NM_DEVICE_STATE_REASON_DHCP_FAILED",
    "NM_DEVICE_STATE_REASON_DHCP_START_FAILED",
    "NM_DEVICE_STATE_REASON_FIRMWARE_MISSING",
    "NM_DEVICE_STATE_REASON_GSM_APN_FAILED",
    "NM_DEVICE_STATE_REASON_GSM_PIN_CHECK_FAILED",
    "NM_DEVICE_STATE_REASON_GSM_REGISTRATION_DENIED",
    "NM_DEVICE_STATE_REASON_GSM_REGISTRATION_FAILED",
    "NM_DEVICE_STATE_REASON_GSM_REGISTRATION_NOT_SEARCHING",
    "NM_DEVICE_STATE_REASON_GSM_REGISTRATION_TIMEOUT",
    "NM_DEVICE_STATE_REASON_GSM_SIM_NOT_INSERTED",
    "NM_DEVICE_STATE_REASON_GSM_SIM_PIN_REQUIRED",
    "NM_DEVICE_STATE_REASON_GSM_SIM_PUK_REQUIRED",
    "NM_DEVICE_STATE_REASON_GSM_SIM_WRONG",
    "NM_DEVICE_STATE_REASON_INFINIBAND_MODE",
    "NM_DEVICE_STATE_REASON_IP_ADDRESS_DUPLICATE",
    "NM_DEVICE_STATE_REASON_IP_CONFIG_EXPIRED",
    "NM_DEVICE_STATE_REASON_IP_CONFIG_UNAVAILABLE",
    "NM_DEVICE_STATE_REASON_IP_METHOD_UNSUPPORTED",
    "NM_DEVICE_STATE_REASON_MODEM_AVAILABLE",
    "NM_DEVICE_STATE_REASON_MODEM_BUSY",
    "NM_DEVICE_STATE_REASON_MODEM_DIAL_FAILED",
    "NM_DEVICE_STATE_REASON_MODEM_DIAL_TIMEOUT",
    "NM_DEVICE_STATE_REASON_MODEM_FAILED",
    "NM_DEVICE_STATE_REASON_MODEM_INIT_FAILED",
    "NM_DEVICE_STATE_REASON_MODEM_MANAGER_UNAVAILABLE",
    "NM_DEVICE_STATE_REASON_MODEM_NOT_FOUND",
    "NM_DEVICE_STATE_REASON_MODEM_NO_CARRIER",
    "NM_DEVICE_STATE_REASON_MODEM_NO_DIAL_TONE",
    "NM_DEVICE_STATE_REASON_MODEM_NO_OPERATOR_CODE",
    "NM_DEVICE_STATE_REASON_NETWORKING_OFF",
    "NM_DEVICE_STATE_REASON_NEW_ACTIVATION",
    "NM_DEVICE_STATE_REASON_NONE",
    "NM_DEVICE_STATE_REASON_NOW_MANAGED",
    "NM_DEVICE_STATE_REASON_NOW_UNMANAGED",
    "NM_DEVICE_STATE_REASON_NO_SECRETS",
    "NM_DEVICE_STATE_REASON_OVSDB_FAILED",
    "NM_DEVICE_STATE_REASON_PARENT_CHANGED",
    "NM_DEVICE_STATE_REASON_PARENT_MANAGED_CHANGED",
    "NM_DEVICE_STATE_REASON_PEER_NOT_FOUND",
    "NM_DEVICE_STATE_REASON_PPP_DISCONNECT",
    "NM_DEVICE_STATE_REASON_PPP_FAILED",
    "NM_DEVICE_STATE_REASON_PPP_START_FAILED",
    "NM_DEVICE_STATE_REASON_REMOVED",
    "NM_DEVICE_STATE_REASON_SECONDARY_CONNECTION_FAILED",
    "NM_DEVICE_STATE_REASON_SHARED_FAILED",
    "NM_DEVICE_STATE_REASON_SHARED_START_FAILED",
    "NM_DEVICE_STATE_REASON_SIM_PIN_INCORRECT",
    "NM_DEVICE_STATE_REASON_SLEEPING",
    "NM_DEVICE_STATE_REASON_SRIOV_CONFIGURATION_FAILED",
    "NM_DEVICE_STATE_REASON_SSID_NOT_FOUND",
    "NM_DEVICE_STATE_REASON_SUPPLICANT_AVAILABLE",
    "NM_DEVICE_STATE_REASON_SUPPLICANT_CONFIG_FAILED",
    "NM_DEVICE_STATE_REASON_SUPPLICANT_DISCONNECT",
    "NM_DEVICE_STATE_REASON_SUPPLICANT_FAILED",
    "NM_DEVICE_STATE_REASON_SUPPLICANT_TIMEOUT",
    "NM_DEVICE_STATE_REASON_TEAMD_CONTROL_FAILED",
    "NM_DEVICE_STATE_REASON_UNKNOWN",
    "NM_DEVICE_STATE_REASON_UNMANAGED_BY_DEFAULT",
    "NM_DEVICE_STATE_REASON_UNMANAGED_EXTERNAL_DOWN",
    "NM_DEVICE_STATE_REASON_UNMANAGED_LINK_NOT_INIT",
    "NM_DEVICE_STATE_REASON_UNMANAGED_QUITTING",
    "NM_DEVICE_STATE_REASON_UNMANAGED_SLEEPING",
    "NM_DEVICE_STATE_REASON_UNMANAGED_USER_CONF",
    "NM_DEVICE_STATE_REASON_UNMANAGED_USER_EXPLICIT",
    "NM_DEVICE_STATE_REASON_UNMANAGED_USER_SETTINGS",
    "NM_DEVICE_STATE_REASON_UNMANAGED_USER_UDEV",
    "NM_DEVICE_STATE_REASON_USER_REQUESTED",
    "autoip-error",
    "autoip-failed",
    "autoip-start-failed",
    "br2684-failed",
    "bt-failed",
    "carrier",
    "config-failed",
    "connection-assumed",
    "connection-removed",
    "dcb-fcoe-failed",
    "dependency-failed",
    "device-handler-failed",
    "dhcp-error",
    "dhcp-failed",
    "dhcp-start-failed",
    "firmware-missing",
    "gsm-apn-failed",
    "gsm-pin-check-failed",
    "gsm-registration-denied",
    "gsm-registration-failed",
    "gsm-registration-not-searching",
    "gsm-registration-timeout",
    "gsm-sim-not-inserted",
    "gsm-sim-pin-required",
    "gsm-sim-puk-required",
    "gsm-sim-wrong",
    "infiniband-mode",
    "ip-address-duplicate",
    "ip-config-expired",
    "ip-config-unavailable",
    "ip-method-unsupported",
    "modem-available",
    "modem-busy",
    "modem-dial-failed",
    "modem-dial-timeout",
    "modem-failed",
    "modem-init-failed",
    "modem-manager-unavailable",
    "modem-no-carrier",
    "modem-no-dial-tone",
    "modem-no-operator-code",
    "modem-not-found",
    "networking-off",
    "new-activation",
    "no-secrets",
    "none",
    "now-managed",
    "now-unmanaged",
    "ovsdb-failed",
    "parent-changed",
    "parent-managed-changed",
    "peer-not-found",
    "ppp-disconnect",
    "ppp-failed",
    "ppp-start-failed",
    "removed",
    "secondary-connection-failed",
    "shared-failed",
    "shared-start-failed",
    "sim-pin-incorrect",
    "sleeping",
    "sriov-configuration-failed",
    "ssid-not-found",
    "supplicant-available",
    "supplicant-config-failed",
    "supplicant-disconnect",
    "supplicant-failed",
    "supplicant-timeout",
    "teamd-control-failed",
    "unknown",
    "unmanaged-by-default",
    "unmanaged-external-down",
    "unmanaged-link-not-init",
    "unmanaged-quitting",
    "unmanaged-sleeping",
    "unmanaged-user-conf",
    "unmanaged-user-explicit",
    "unmanaged-user-settings",
    "unmanaged-user-udev",
    "user-requested",
]
_DeviceStateReasonValueType: TypeAlias = (
    DeviceStateReason | _DeviceStateReasonLiteralType
)

class DeviceType(GObject.GEnum):
    ADSL = 12
    BOND = 10
    BRIDGE = 13
    BT = 5
    DUMMY = 22
    ETHERNET = 1
    GENERIC = 14
    GENEVE = 35
    HSR = 33
    INFINIBAND = 9
    IPVLAN = 34
    IP_TUNNEL = 17
    LOOPBACK = 32
    MACSEC = 21
    MACVLAN = 18
    MODEM = 8
    OLPC_MESH = 6
    OVS_BRIDGE = 26
    OVS_INTERFACE = 24
    OVS_PORT = 25
    PPP = 23
    TEAM = 15
    TUN = 16
    UNKNOWN = 0
    UNUSED1 = 3
    UNUSED2 = 4
    VETH = 20
    VLAN = 11
    VRF = 31
    VXLAN = 19
    WIFI = 2
    WIFI_P2P = 30
    WIMAX = 7
    WIREGUARD = 29
    WPAN = 27

_DeviceTypeLiteralType: TypeAlias = Literal[
    "NM_DEVICE_TYPE_ADSL",
    "NM_DEVICE_TYPE_BOND",
    "NM_DEVICE_TYPE_BRIDGE",
    "NM_DEVICE_TYPE_BT",
    "NM_DEVICE_TYPE_DUMMY",
    "NM_DEVICE_TYPE_ETHERNET",
    "NM_DEVICE_TYPE_GENERIC",
    "NM_DEVICE_TYPE_GENEVE",
    "NM_DEVICE_TYPE_HSR",
    "NM_DEVICE_TYPE_INFINIBAND",
    "NM_DEVICE_TYPE_IPVLAN",
    "NM_DEVICE_TYPE_IP_TUNNEL",
    "NM_DEVICE_TYPE_LOOPBACK",
    "NM_DEVICE_TYPE_MACSEC",
    "NM_DEVICE_TYPE_MACVLAN",
    "NM_DEVICE_TYPE_MODEM",
    "NM_DEVICE_TYPE_OLPC_MESH",
    "NM_DEVICE_TYPE_OVS_BRIDGE",
    "NM_DEVICE_TYPE_OVS_INTERFACE",
    "NM_DEVICE_TYPE_OVS_PORT",
    "NM_DEVICE_TYPE_PPP",
    "NM_DEVICE_TYPE_TEAM",
    "NM_DEVICE_TYPE_TUN",
    "NM_DEVICE_TYPE_UNKNOWN",
    "NM_DEVICE_TYPE_UNUSED1",
    "NM_DEVICE_TYPE_UNUSED2",
    "NM_DEVICE_TYPE_VETH",
    "NM_DEVICE_TYPE_VLAN",
    "NM_DEVICE_TYPE_VRF",
    "NM_DEVICE_TYPE_VXLAN",
    "NM_DEVICE_TYPE_WIFI",
    "NM_DEVICE_TYPE_WIFI_P2P",
    "NM_DEVICE_TYPE_WIMAX",
    "NM_DEVICE_TYPE_WIREGUARD",
    "NM_DEVICE_TYPE_WPAN",
    "adsl",
    "bond",
    "bridge",
    "bt",
    "dummy",
    "ethernet",
    "generic",
    "geneve",
    "hsr",
    "infiniband",
    "ip-tunnel",
    "ipvlan",
    "loopback",
    "macsec",
    "macvlan",
    "modem",
    "olpc-mesh",
    "ovs-bridge",
    "ovs-interface",
    "ovs-port",
    "ppp",
    "team",
    "tun",
    "unknown",
    "unused1",
    "unused2",
    "veth",
    "vlan",
    "vrf",
    "vxlan",
    "wifi",
    "wifi-p2p",
    "wimax",
    "wireguard",
    "wpan",
]
_DeviceTypeValueType: TypeAlias = DeviceType | _DeviceTypeLiteralType

class IPTunnelMode(GObject.GEnum):
    GRE = 2
    GRETAP = 10
    IP6GRE = 8
    IP6GRETAP = 11
    IP6IP6 = 6
    IPIP = 1
    IPIP6 = 7
    ISATAP = 4
    SIT = 3
    UNKNOWN = 0
    VTI = 5
    VTI6 = 9

_IPTunnelModeLiteralType: TypeAlias = Literal[
    "NM_IP_TUNNEL_MODE_GRE",
    "NM_IP_TUNNEL_MODE_GRETAP",
    "NM_IP_TUNNEL_MODE_IP6GRE",
    "NM_IP_TUNNEL_MODE_IP6GRETAP",
    "NM_IP_TUNNEL_MODE_IP6IP6",
    "NM_IP_TUNNEL_MODE_IPIP",
    "NM_IP_TUNNEL_MODE_IPIP6",
    "NM_IP_TUNNEL_MODE_ISATAP",
    "NM_IP_TUNNEL_MODE_SIT",
    "NM_IP_TUNNEL_MODE_UNKNOWN",
    "NM_IP_TUNNEL_MODE_VTI",
    "NM_IP_TUNNEL_MODE_VTI6",
    "gre",
    "gretap",
    "ip6gre",
    "ip6gretap",
    "ip6ip6",
    "ipip",
    "ipip6",
    "isatap",
    "sit",
    "unknown",
    "vti",
    "vti6",
]
_IPTunnelModeValueType: TypeAlias = IPTunnelMode | _IPTunnelModeLiteralType

class KeyfileHandlerType(GObject.GEnum):
    WARN = 1
    WRITE_CERT = 2

_KeyfileHandlerTypeLiteralType: TypeAlias = Literal[
    "NM_KEYFILE_HANDLER_TYPE_WARN",
    "NM_KEYFILE_HANDLER_TYPE_WRITE_CERT",
    "warn",
    "write-cert",
]
_KeyfileHandlerTypeValueType: TypeAlias = (
    KeyfileHandlerType | _KeyfileHandlerTypeLiteralType
)

class KeyfileWarnSeverity(GObject.GEnum):
    DEBUG = 1000
    INFO = 2000
    INFO_MISSING_FILE = 2901
    WARN = 3000

_KeyfileWarnSeverityLiteralType: TypeAlias = Literal[
    "NM_KEYFILE_WARN_SEVERITY_DEBUG",
    "NM_KEYFILE_WARN_SEVERITY_INFO",
    "NM_KEYFILE_WARN_SEVERITY_INFO_MISSING_FILE",
    "NM_KEYFILE_WARN_SEVERITY_WARN",
    "debug",
    "info",
    "info-missing-file",
    "warn",
]
_KeyfileWarnSeverityValueType: TypeAlias = (
    KeyfileWarnSeverity | _KeyfileWarnSeverityLiteralType
)

class ManagerError(GObject.GEnum):
    ALREADYASLEEPORAWAKE = 8
    ALREADYENABLEDORDISABLED = 9
    CONNECTIONALREADYACTIVE = 6
    CONNECTIONNOTACTIVE = 5
    CONNECTIONNOTAVAILABLE = 4
    DEPENDENCYFAILED = 7
    FAILED = 0
    INVALIDARGUMENTS = 12
    MISSINGPLUGIN = 13
    PERMISSIONDENIED = 1
    UNKNOWNCONNECTION = 2
    UNKNOWNDEVICE = 3
    UNKNOWNLOGDOMAIN = 11
    UNKNOWNLOGLEVEL = 10
    @staticmethod
    def quark() -> int: ...

_ManagerErrorLiteralType: TypeAlias = Literal[
    "AlreadyAsleepOrAwake",
    "AlreadyEnabledOrDisabled",
    "ConnectionAlreadyActive",
    "ConnectionNotActive",
    "ConnectionNotAvailable",
    "DependencyFailed",
    "Failed",
    "InvalidArguments",
    "MissingPlugin",
    "NM_MANAGER_ERROR_ALREADY_ASLEEP_OR_AWAKE",
    "NM_MANAGER_ERROR_ALREADY_ENABLED_OR_DISABLED",
    "NM_MANAGER_ERROR_CONNECTION_ALREADY_ACTIVE",
    "NM_MANAGER_ERROR_CONNECTION_NOT_ACTIVE",
    "NM_MANAGER_ERROR_CONNECTION_NOT_AVAILABLE",
    "NM_MANAGER_ERROR_DEPENDENCY_FAILED",
    "NM_MANAGER_ERROR_FAILED",
    "NM_MANAGER_ERROR_INVALID_ARGUMENTS",
    "NM_MANAGER_ERROR_MISSING_PLUGIN",
    "NM_MANAGER_ERROR_PERMISSION_DENIED",
    "NM_MANAGER_ERROR_UNKNOWN_CONNECTION",
    "NM_MANAGER_ERROR_UNKNOWN_DEVICE",
    "NM_MANAGER_ERROR_UNKNOWN_LOG_DOMAIN",
    "NM_MANAGER_ERROR_UNKNOWN_LOG_LEVEL",
    "PermissionDenied",
    "UnknownConnection",
    "UnknownDevice",
    "UnknownLogDomain",
    "UnknownLogLevel",
]
_ManagerErrorValueType: TypeAlias = ManagerError | _ManagerErrorLiteralType

class Metered(GObject.GEnum):
    GUESS_NO = 4
    GUESS_YES = 3
    NO = 2
    UNKNOWN = 0
    YES = 1

_MeteredLiteralType: TypeAlias = Literal[
    "NM_METERED_GUESS_NO",
    "NM_METERED_GUESS_YES",
    "NM_METERED_NO",
    "NM_METERED_UNKNOWN",
    "NM_METERED_YES",
    "guess-no",
    "guess-yes",
    "no",
    "unknown",
    "yes",
]
_MeteredValueType: TypeAlias = Metered | _MeteredLiteralType

class RollbackResult(IntEnum):
    ERR_DEVICE_UNMANAGED = 2
    ERR_FAILED = 3
    ERR_NO_DEVICE = 1
    OK = 0

class SecretAgentError(GObject.GEnum):
    AGENTCANCELED = 4
    FAILED = 0
    INVALIDCONNECTION = 2
    NOSECRETS = 5
    PERMISSIONDENIED = 1
    USERCANCELED = 3
    @staticmethod
    def quark() -> int: ...

_SecretAgentErrorLiteralType: TypeAlias = Literal[
    "AgentCanceled",
    "Failed",
    "InvalidConnection",
    "NM_SECRET_AGENT_ERROR_AGENT_CANCELED",
    "NM_SECRET_AGENT_ERROR_FAILED",
    "NM_SECRET_AGENT_ERROR_INVALID_CONNECTION",
    "NM_SECRET_AGENT_ERROR_NO_SECRETS",
    "NM_SECRET_AGENT_ERROR_PERMISSION_DENIED",
    "NM_SECRET_AGENT_ERROR_USER_CANCELED",
    "NoSecrets",
    "PermissionDenied",
    "UserCanceled",
]
_SecretAgentErrorValueType: TypeAlias = SecretAgentError | _SecretAgentErrorLiteralType

class Setting8021xCKFormat(GObject.GEnum):
    PKCS12 = 3
    RAW_KEY = 2
    UNKNOWN = 0
    X509 = 1

_Setting8021xCKFormatLiteralType: TypeAlias = Literal[
    "NM_SETTING_802_1X_CK_FORMAT_PKCS12",
    "NM_SETTING_802_1X_CK_FORMAT_RAW_KEY",
    "NM_SETTING_802_1X_CK_FORMAT_UNKNOWN",
    "NM_SETTING_802_1X_CK_FORMAT_X509",
    "pkcs12",
    "raw-key",
    "unknown",
    "x509",
]
_Setting8021xCKFormatValueType: TypeAlias = (
    Setting8021xCKFormat | _Setting8021xCKFormatLiteralType
)

class Setting8021xCKScheme(GObject.GEnum):
    BLOB = 1
    PATH = 2
    PKCS11 = 3
    UNKNOWN = 0

_Setting8021xCKSchemeLiteralType: TypeAlias = Literal[
    "NM_SETTING_802_1X_CK_SCHEME_BLOB",
    "NM_SETTING_802_1X_CK_SCHEME_PATH",
    "NM_SETTING_802_1X_CK_SCHEME_PKCS11",
    "NM_SETTING_802_1X_CK_SCHEME_UNKNOWN",
    "blob",
    "path",
    "pkcs11",
    "unknown",
]
_Setting8021xCKSchemeValueType: TypeAlias = (
    Setting8021xCKScheme | _Setting8021xCKSchemeLiteralType
)

class SettingCompareFlags(GObject.GEnum):
    DIFF_RESULT_NO_DEFAULT = 64
    DIFF_RESULT_WITH_DEFAULT = 32
    EXACT = 0
    FUZZY = 1
    IGNORE_AGENT_OWNED_SECRETS = 8
    IGNORE_ID = 2
    IGNORE_NOT_SAVED_SECRETS = 16
    IGNORE_SECRETS = 4
    IGNORE_TIMESTAMP = 128

_SettingCompareFlagsLiteralType: TypeAlias = Literal[
    "NM_SETTING_COMPARE_FLAG_DIFF_RESULT_NO_DEFAULT",
    "NM_SETTING_COMPARE_FLAG_DIFF_RESULT_WITH_DEFAULT",
    "NM_SETTING_COMPARE_FLAG_EXACT",
    "NM_SETTING_COMPARE_FLAG_FUZZY",
    "NM_SETTING_COMPARE_FLAG_IGNORE_AGENT_OWNED_SECRETS",
    "NM_SETTING_COMPARE_FLAG_IGNORE_ID",
    "NM_SETTING_COMPARE_FLAG_IGNORE_NOT_SAVED_SECRETS",
    "NM_SETTING_COMPARE_FLAG_IGNORE_SECRETS",
    "NM_SETTING_COMPARE_FLAG_IGNORE_TIMESTAMP",
    "diff-result-no-default",
    "diff-result-with-default",
    "exact",
    "fuzzy",
    "ignore-agent-owned-secrets",
    "ignore-id",
    "ignore-not-saved-secrets",
    "ignore-secrets",
    "ignore-timestamp",
]
_SettingCompareFlagsValueType: TypeAlias = (
    SettingCompareFlags | _SettingCompareFlagsLiteralType
)

class SettingConnectionAutoconnectSlaves(GObject.GEnum):
    DEFAULT = -1
    NO = 0
    YES = 1

_SettingConnectionAutoconnectSlavesLiteralType: TypeAlias = Literal[
    "NM_SETTING_CONNECTION_AUTOCONNECT_SLAVES_DEFAULT",
    "NM_SETTING_CONNECTION_AUTOCONNECT_SLAVES_NO",
    "NM_SETTING_CONNECTION_AUTOCONNECT_SLAVES_YES",
    "default",
    "no",
    "yes",
]
_SettingConnectionAutoconnectSlavesValueType: TypeAlias = (
    SettingConnectionAutoconnectSlaves | _SettingConnectionAutoconnectSlavesLiteralType
)

class SettingConnectionDnsOverTls(GObject.GEnum):
    DEFAULT = -1
    NO = 0
    OPPORTUNISTIC = 1
    YES = 2

_SettingConnectionDnsOverTlsLiteralType: TypeAlias = Literal[
    "NM_SETTING_CONNECTION_DNS_OVER_TLS_DEFAULT",
    "NM_SETTING_CONNECTION_DNS_OVER_TLS_NO",
    "NM_SETTING_CONNECTION_DNS_OVER_TLS_OPPORTUNISTIC",
    "NM_SETTING_CONNECTION_DNS_OVER_TLS_YES",
    "default",
    "no",
    "opportunistic",
    "yes",
]
_SettingConnectionDnsOverTlsValueType: TypeAlias = (
    SettingConnectionDnsOverTls | _SettingConnectionDnsOverTlsLiteralType
)

class SettingConnectionDnssec(GObject.GEnum):
    ALLOW_DOWNGRADE = 1
    DEFAULT = -1
    NO = 0
    YES = 2

_SettingConnectionDnssecLiteralType: TypeAlias = Literal[
    "NM_SETTING_CONNECTION_DNSSEC_ALLOW_DOWNGRADE",
    "NM_SETTING_CONNECTION_DNSSEC_DEFAULT",
    "NM_SETTING_CONNECTION_DNSSEC_NO",
    "NM_SETTING_CONNECTION_DNSSEC_YES",
    "allow-downgrade",
    "default",
    "no",
    "yes",
]
_SettingConnectionDnssecValueType: TypeAlias = (
    SettingConnectionDnssec | _SettingConnectionDnssecLiteralType
)

class SettingConnectionDownOnPoweroff(GObject.GEnum):
    DEFAULT = -1
    NO = 0
    YES = 1

_SettingConnectionDownOnPoweroffLiteralType: TypeAlias = Literal[
    "NM_SETTING_CONNECTION_DOWN_ON_POWEROFF_DEFAULT",
    "NM_SETTING_CONNECTION_DOWN_ON_POWEROFF_NO",
    "NM_SETTING_CONNECTION_DOWN_ON_POWEROFF_YES",
    "default",
    "no",
    "yes",
]
_SettingConnectionDownOnPoweroffValueType: TypeAlias = (
    SettingConnectionDownOnPoweroff | _SettingConnectionDownOnPoweroffLiteralType
)

class SettingConnectionLldp(GObject.GEnum):
    DEFAULT = -1
    DISABLE = 0
    ENABLE_RX = 1

_SettingConnectionLldpLiteralType: TypeAlias = Literal[
    "NM_SETTING_CONNECTION_LLDP_DEFAULT",
    "NM_SETTING_CONNECTION_LLDP_DISABLE",
    "NM_SETTING_CONNECTION_LLDP_ENABLE_RX",
    "default",
    "disable",
    "enable-rx",
]
_SettingConnectionLldpValueType: TypeAlias = (
    SettingConnectionLldp | _SettingConnectionLldpLiteralType
)

class SettingConnectionLlmnr(GObject.GEnum):
    DEFAULT = -1
    NO = 0
    RESOLVE = 1
    YES = 2

_SettingConnectionLlmnrLiteralType: TypeAlias = Literal[
    "NM_SETTING_CONNECTION_LLMNR_DEFAULT",
    "NM_SETTING_CONNECTION_LLMNR_NO",
    "NM_SETTING_CONNECTION_LLMNR_RESOLVE",
    "NM_SETTING_CONNECTION_LLMNR_YES",
    "default",
    "no",
    "resolve",
    "yes",
]
_SettingConnectionLlmnrValueType: TypeAlias = (
    SettingConnectionLlmnr | _SettingConnectionLlmnrLiteralType
)

class SettingConnectionMdns(GObject.GEnum):
    DEFAULT = -1
    NO = 0
    RESOLVE = 1
    YES = 2

_SettingConnectionMdnsLiteralType: TypeAlias = Literal[
    "NM_SETTING_CONNECTION_MDNS_DEFAULT",
    "NM_SETTING_CONNECTION_MDNS_NO",
    "NM_SETTING_CONNECTION_MDNS_RESOLVE",
    "NM_SETTING_CONNECTION_MDNS_YES",
    "default",
    "no",
    "resolve",
    "yes",
]
_SettingConnectionMdnsValueType: TypeAlias = (
    SettingConnectionMdns | _SettingConnectionMdnsLiteralType
)

class SettingDiffResult(GObject.GEnum):
    IN_A = 1
    IN_A_DEFAULT = 4
    IN_B = 2
    IN_B_DEFAULT = 8
    UNKNOWN = 0

_SettingDiffResultLiteralType: TypeAlias = Literal[
    "NM_SETTING_DIFF_RESULT_IN_A",
    "NM_SETTING_DIFF_RESULT_IN_A_DEFAULT",
    "NM_SETTING_DIFF_RESULT_IN_B",
    "NM_SETTING_DIFF_RESULT_IN_B_DEFAULT",
    "NM_SETTING_DIFF_RESULT_UNKNOWN",
    "in-a",
    "in-a-default",
    "in-b",
    "in-b-default",
    "unknown",
]
_SettingDiffResultValueType: TypeAlias = (
    SettingDiffResult | _SettingDiffResultLiteralType
)

class SettingGeneveDf(GObject.GEnum):
    INHERIT = 2
    SET = 1
    UNSET = 0

_SettingGeneveDfLiteralType: TypeAlias = Literal[
    "NM_SETTING_GENEVE_DF_INHERIT",
    "NM_SETTING_GENEVE_DF_SET",
    "NM_SETTING_GENEVE_DF_UNSET",
    "inherit",
    "set",
    "unset",
]
_SettingGeneveDfValueType: TypeAlias = SettingGeneveDf | _SettingGeneveDfLiteralType

class SettingHsrProtocolVersion(GObject.GEnum):
    DEFAULT = -1
    HSR_2010 = 0
    HSR_2012 = 1

_SettingHsrProtocolVersionLiteralType: TypeAlias = Literal[
    "NM_SETTING_HSR_PROTOCOL_VERSION_DEFAULT",
    "NM_SETTING_HSR_PROTOCOL_VERSION_HSR_2010",
    "NM_SETTING_HSR_PROTOCOL_VERSION_HSR_2012",
    "default",
    "hsr-2010",
    "hsr-2012",
]
_SettingHsrProtocolVersionValueType: TypeAlias = (
    SettingHsrProtocolVersion | _SettingHsrProtocolVersionLiteralType
)

class SettingIP4DhcpIpv6OnlyPreferred(GObject.GEnum):
    AUTO = 2
    DEFAULT = -1
    NO = 0
    YES = 1

_SettingIP4DhcpIpv6OnlyPreferredLiteralType: TypeAlias = Literal[
    "NM_SETTING_IP4_DHCP_IPV6_ONLY_PREFERRED_AUTO",
    "NM_SETTING_IP4_DHCP_IPV6_ONLY_PREFERRED_DEFAULT",
    "NM_SETTING_IP4_DHCP_IPV6_ONLY_PREFERRED_NO",
    "NM_SETTING_IP4_DHCP_IPV6_ONLY_PREFERRED_YES",
    "auto",
    "default",
    "no",
    "yes",
]
_SettingIP4DhcpIpv6OnlyPreferredValueType: TypeAlias = (
    SettingIP4DhcpIpv6OnlyPreferred | _SettingIP4DhcpIpv6OnlyPreferredLiteralType
)

class SettingIP4LinkLocal(GObject.GEnum):
    AUTO = 1
    DEFAULT = 0
    DISABLED = 2
    ENABLED = 3
    FALLBACK = 4

_SettingIP4LinkLocalLiteralType: TypeAlias = Literal[
    "NM_SETTING_IP4_LL_AUTO",
    "NM_SETTING_IP4_LL_DEFAULT",
    "NM_SETTING_IP4_LL_DISABLED",
    "NM_SETTING_IP4_LL_ENABLED",
    "NM_SETTING_IP4_LL_FALLBACK",
    "auto",
    "default",
    "disabled",
    "enabled",
    "fallback",
]
_SettingIP4LinkLocalValueType: TypeAlias = (
    SettingIP4LinkLocal | _SettingIP4LinkLocalLiteralType
)

class SettingIP6ConfigAddrGenMode(GObject.GEnum):
    DEFAULT = 3
    DEFAULT_OR_EUI64 = 2
    EUI64 = 0
    STABLE_PRIVACY = 1

_SettingIP6ConfigAddrGenModeLiteralType: TypeAlias = Literal[
    "NM_SETTING_IP6_CONFIG_ADDR_GEN_MODE_DEFAULT",
    "NM_SETTING_IP6_CONFIG_ADDR_GEN_MODE_DEFAULT_OR_EUI64",
    "NM_SETTING_IP6_CONFIG_ADDR_GEN_MODE_EUI64",
    "NM_SETTING_IP6_CONFIG_ADDR_GEN_MODE_STABLE_PRIVACY",
    "default",
    "default-or-eui64",
    "eui64",
    "stable-privacy",
]
_SettingIP6ConfigAddrGenModeValueType: TypeAlias = (
    SettingIP6ConfigAddrGenMode | _SettingIP6ConfigAddrGenModeLiteralType
)

class SettingIP6ConfigPrivacy(GObject.GEnum):
    DISABLED = 0
    PREFER_PUBLIC_ADDR = 1
    PREFER_TEMP_ADDR = 2
    UNKNOWN = -1

_SettingIP6ConfigPrivacyLiteralType: TypeAlias = Literal[
    "NM_SETTING_IP6_CONFIG_PRIVACY_DISABLED",
    "NM_SETTING_IP6_CONFIG_PRIVACY_PREFER_PUBLIC_ADDR",
    "NM_SETTING_IP6_CONFIG_PRIVACY_PREFER_TEMP_ADDR",
    "NM_SETTING_IP6_CONFIG_PRIVACY_UNKNOWN",
    "disabled",
    "prefer-public-addr",
    "prefer-temp-addr",
    "unknown",
]
_SettingIP6ConfigPrivacyValueType: TypeAlias = (
    SettingIP6ConfigPrivacy | _SettingIP6ConfigPrivacyLiteralType
)

class SettingIPConfigForwarding(GObject.GEnum):
    AUTO = 2
    DEFAULT = -1
    NO = 0
    YES = 1

_SettingIPConfigForwardingLiteralType: TypeAlias = Literal[
    "NM_SETTING_IP_CONFIG_FORWARDING_AUTO",
    "NM_SETTING_IP_CONFIG_FORWARDING_DEFAULT",
    "NM_SETTING_IP_CONFIG_FORWARDING_NO",
    "NM_SETTING_IP_CONFIG_FORWARDING_YES",
    "auto",
    "default",
    "no",
    "yes",
]
_SettingIPConfigForwardingValueType: TypeAlias = (
    SettingIPConfigForwarding | _SettingIPConfigForwardingLiteralType
)

class SettingIPConfigRoutedDns(GObject.GEnum):
    DEFAULT = -1
    NO = 0
    YES = 1

_SettingIPConfigRoutedDnsLiteralType: TypeAlias = Literal[
    "NM_SETTING_IP_CONFIG_ROUTED_DNS_DEFAULT",
    "NM_SETTING_IP_CONFIG_ROUTED_DNS_NO",
    "NM_SETTING_IP_CONFIG_ROUTED_DNS_YES",
    "default",
    "no",
    "yes",
]
_SettingIPConfigRoutedDnsValueType: TypeAlias = (
    SettingIPConfigRoutedDns | _SettingIPConfigRoutedDnsLiteralType
)

class SettingIp4ConfigClat(GObject.GEnum):
    AUTO = 1
    DEFAULT = -1
    FORCE = 2
    NO = 0

_SettingIp4ConfigClatLiteralType: TypeAlias = Literal[
    "NM_SETTING_IP4_CONFIG_CLAT_AUTO",
    "NM_SETTING_IP4_CONFIG_CLAT_DEFAULT",
    "NM_SETTING_IP4_CONFIG_CLAT_FORCE",
    "NM_SETTING_IP4_CONFIG_CLAT_NO",
    "auto",
    "default",
    "force",
    "no",
]
_SettingIp4ConfigClatValueType: TypeAlias = (
    SettingIp4ConfigClat | _SettingIp4ConfigClatLiteralType
)

class SettingIpvlanMode(GObject.GEnum):
    L2 = 1
    L3 = 2
    L3S = 3
    UNKNOWN = 0

_SettingIpvlanModeLiteralType: TypeAlias = Literal[
    "NM_SETTING_IPVLAN_MODE_L2",
    "NM_SETTING_IPVLAN_MODE_L3",
    "NM_SETTING_IPVLAN_MODE_L3S",
    "NM_SETTING_IPVLAN_MODE_UNKNOWN",
    "l2",
    "l3",
    "l3s",
    "unknown",
]
_SettingIpvlanModeValueType: TypeAlias = (
    SettingIpvlanMode | _SettingIpvlanModeLiteralType
)

class SettingMacRandomization(GObject.GEnum):
    ALWAYS = 2
    DEFAULT = 0
    NEVER = 1

_SettingMacRandomizationLiteralType: TypeAlias = Literal[
    "NM_SETTING_MAC_RANDOMIZATION_ALWAYS",
    "NM_SETTING_MAC_RANDOMIZATION_DEFAULT",
    "NM_SETTING_MAC_RANDOMIZATION_NEVER",
    "always",
    "default",
    "never",
]
_SettingMacRandomizationValueType: TypeAlias = (
    SettingMacRandomization | _SettingMacRandomizationLiteralType
)

class SettingMacsecMode(GObject.GEnum):
    EAP = 1
    PSK = 0

_SettingMacsecModeLiteralType: TypeAlias = Literal[
    "NM_SETTING_MACSEC_MODE_EAP", "NM_SETTING_MACSEC_MODE_PSK", "eap", "psk"
]
_SettingMacsecModeValueType: TypeAlias = (
    SettingMacsecMode | _SettingMacsecModeLiteralType
)

class SettingMacsecOffload(GObject.GEnum):
    DEFAULT = -1
    MAC = 2
    OFF = 0
    PHY = 1

_SettingMacsecOffloadLiteralType: TypeAlias = Literal[
    "NM_SETTING_MACSEC_OFFLOAD_DEFAULT",
    "NM_SETTING_MACSEC_OFFLOAD_MAC",
    "NM_SETTING_MACSEC_OFFLOAD_OFF",
    "NM_SETTING_MACSEC_OFFLOAD_PHY",
    "default",
    "mac",
    "off",
    "phy",
]
_SettingMacsecOffloadValueType: TypeAlias = (
    SettingMacsecOffload | _SettingMacsecOffloadLiteralType
)

class SettingMacsecValidation(GObject.GEnum):
    CHECK = 1
    DISABLE = 0
    STRICT = 2

_SettingMacsecValidationLiteralType: TypeAlias = Literal[
    "NM_SETTING_MACSEC_VALIDATION_CHECK",
    "NM_SETTING_MACSEC_VALIDATION_DISABLE",
    "NM_SETTING_MACSEC_VALIDATION_STRICT",
    "check",
    "disable",
    "strict",
]
_SettingMacsecValidationValueType: TypeAlias = (
    SettingMacsecValidation | _SettingMacsecValidationLiteralType
)

class SettingMacvlanMode(GObject.GEnum):
    BRIDGE = 2
    PASSTHRU = 4
    PRIVATE = 3
    SOURCE = 5
    UNKNOWN = 0
    VEPA = 1

_SettingMacvlanModeLiteralType: TypeAlias = Literal[
    "NM_SETTING_MACVLAN_MODE_BRIDGE",
    "NM_SETTING_MACVLAN_MODE_PASSTHRU",
    "NM_SETTING_MACVLAN_MODE_PRIVATE",
    "NM_SETTING_MACVLAN_MODE_SOURCE",
    "NM_SETTING_MACVLAN_MODE_UNKNOWN",
    "NM_SETTING_MACVLAN_MODE_VEPA",
    "bridge",
    "passthru",
    "private",
    "source",
    "unknown",
    "vepa",
]
_SettingMacvlanModeValueType: TypeAlias = (
    SettingMacvlanMode | _SettingMacvlanModeLiteralType
)

class SettingOvsDpdkLscInterrupt(GObject.GEnum):
    DISABLED = 0
    ENABLED = 1
    IGNORE = -1

_SettingOvsDpdkLscInterruptLiteralType: TypeAlias = Literal[
    "NM_SETTING_OVS_DPDK_LSC_INTERRUPT_DISABLED",
    "NM_SETTING_OVS_DPDK_LSC_INTERRUPT_ENABLED",
    "NM_SETTING_OVS_DPDK_LSC_INTERRUPT_IGNORE",
    "disabled",
    "enabled",
    "ignore",
]
_SettingOvsDpdkLscInterruptValueType: TypeAlias = (
    SettingOvsDpdkLscInterrupt | _SettingOvsDpdkLscInterruptLiteralType
)

class SettingProxyMethod(GObject.GEnum):
    AUTO = 1
    NONE = 0

_SettingProxyMethodLiteralType: TypeAlias = Literal[
    "NM_SETTING_PROXY_METHOD_AUTO", "NM_SETTING_PROXY_METHOD_NONE", "auto", "none"
]
_SettingProxyMethodValueType: TypeAlias = (
    SettingProxyMethod | _SettingProxyMethodLiteralType
)

class SettingSerialParity(GObject.GEnum):
    EVEN = 1
    NONE = 0
    ODD = 2

_SettingSerialParityLiteralType: TypeAlias = Literal[
    "NM_SETTING_SERIAL_PARITY_EVEN",
    "NM_SETTING_SERIAL_PARITY_NONE",
    "NM_SETTING_SERIAL_PARITY_ODD",
    "even",
    "none",
    "odd",
]
_SettingSerialParityValueType: TypeAlias = (
    SettingSerialParity | _SettingSerialParityLiteralType
)

class SettingTunMode(GObject.GEnum):
    TAP = 2
    TUN = 1
    UNKNOWN = 0

_SettingTunModeLiteralType: TypeAlias = Literal[
    "NM_SETTING_TUN_MODE_TAP",
    "NM_SETTING_TUN_MODE_TUN",
    "NM_SETTING_TUN_MODE_UNKNOWN",
    "tap",
    "tun",
    "unknown",
]
_SettingTunModeValueType: TypeAlias = SettingTunMode | _SettingTunModeLiteralType

class SettingWirelessChannelWidth(GObject.GEnum):
    AUTO = 0

_SettingWirelessChannelWidthLiteralType: TypeAlias = Literal[
    "NM_SETTING_WIRELESS_CHANNEL_WIDTH_AUTO", "auto"
]
_SettingWirelessChannelWidthValueType: TypeAlias = (
    SettingWirelessChannelWidth | _SettingWirelessChannelWidthLiteralType
)

class SettingWirelessPowersave(GObject.GEnum):
    DEFAULT = 0
    DISABLE = 2
    ENABLE = 3
    IGNORE = 1

_SettingWirelessPowersaveLiteralType: TypeAlias = Literal[
    "NM_SETTING_WIRELESS_POWERSAVE_DEFAULT",
    "NM_SETTING_WIRELESS_POWERSAVE_DISABLE",
    "NM_SETTING_WIRELESS_POWERSAVE_ENABLE",
    "NM_SETTING_WIRELESS_POWERSAVE_IGNORE",
    "default",
    "disable",
    "enable",
    "ignore",
]
_SettingWirelessPowersaveValueType: TypeAlias = (
    SettingWirelessPowersave | _SettingWirelessPowersaveLiteralType
)

class SettingWirelessSecurityFils(GObject.GEnum):
    DEFAULT = 0
    DISABLE = 1
    OPTIONAL = 2
    REQUIRED = 3

_SettingWirelessSecurityFilsLiteralType: TypeAlias = Literal[
    "NM_SETTING_WIRELESS_SECURITY_FILS_DEFAULT",
    "NM_SETTING_WIRELESS_SECURITY_FILS_DISABLE",
    "NM_SETTING_WIRELESS_SECURITY_FILS_OPTIONAL",
    "NM_SETTING_WIRELESS_SECURITY_FILS_REQUIRED",
    "default",
    "disable",
    "optional",
    "required",
]
_SettingWirelessSecurityFilsValueType: TypeAlias = (
    SettingWirelessSecurityFils | _SettingWirelessSecurityFilsLiteralType
)

class SettingWirelessSecurityPmf(GObject.GEnum):
    DEFAULT = 0
    DISABLE = 1
    OPTIONAL = 2
    REQUIRED = 3

_SettingWirelessSecurityPmfLiteralType: TypeAlias = Literal[
    "NM_SETTING_WIRELESS_SECURITY_PMF_DEFAULT",
    "NM_SETTING_WIRELESS_SECURITY_PMF_DISABLE",
    "NM_SETTING_WIRELESS_SECURITY_PMF_OPTIONAL",
    "NM_SETTING_WIRELESS_SECURITY_PMF_REQUIRED",
    "default",
    "disable",
    "optional",
    "required",
]
_SettingWirelessSecurityPmfValueType: TypeAlias = (
    SettingWirelessSecurityPmf | _SettingWirelessSecurityPmfLiteralType
)

class SettingsError(GObject.GEnum):
    FAILED = 0
    FEATUREDISABLED = 10
    FEATUREREMOVED = 11
    INVALIDARGUMENTS = 7
    INVALIDCONNECTION = 3
    INVALIDHOSTNAME = 6
    NOTSUPPORTED = 2
    NOTSUPPORTEDBYPLUGIN = 9
    PERMISSIONDENIED = 1
    READONLYCONNECTION = 4
    UUIDEXISTS = 5
    VERSIONIDMISMATCH = 8
    @staticmethod
    def quark() -> int: ...

_SettingsErrorLiteralType: TypeAlias = Literal[
    "Failed",
    "FeatureDisabled",
    "FeatureRemoved",
    "InvalidArguments",
    "InvalidConnection",
    "InvalidHostname",
    "NM_SETTINGS_ERROR_FAILED",
    "NM_SETTINGS_ERROR_FEATURE_DISABLED",
    "NM_SETTINGS_ERROR_FEATURE_REMOVED",
    "NM_SETTINGS_ERROR_INVALID_ARGUMENTS",
    "NM_SETTINGS_ERROR_INVALID_CONNECTION",
    "NM_SETTINGS_ERROR_INVALID_HOSTNAME",
    "NM_SETTINGS_ERROR_NOT_SUPPORTED",
    "NM_SETTINGS_ERROR_NOT_SUPPORTED_BY_PLUGIN",
    "NM_SETTINGS_ERROR_PERMISSION_DENIED",
    "NM_SETTINGS_ERROR_READ_ONLY_CONNECTION",
    "NM_SETTINGS_ERROR_UUID_EXISTS",
    "NM_SETTINGS_ERROR_VERSION_ID_MISMATCH",
    "NotSupported",
    "NotSupportedByPlugin",
    "PermissionDenied",
    "ReadOnlyConnection",
    "UuidExists",
    "VersionIdMismatch",
]
_SettingsErrorValueType: TypeAlias = SettingsError | _SettingsErrorLiteralType

class SriovEswitchEncapMode(GObject.GEnum):
    BASIC = 1
    NONE = 0
    PRESERVE = -1

_SriovEswitchEncapModeLiteralType: TypeAlias = Literal[
    "NM_SRIOV_ESWITCH_ENCAP_MODE_BASIC",
    "NM_SRIOV_ESWITCH_ENCAP_MODE_NONE",
    "NM_SRIOV_ESWITCH_ENCAP_MODE_PRESERVE",
    "basic",
    "none",
    "preserve",
]
_SriovEswitchEncapModeValueType: TypeAlias = (
    SriovEswitchEncapMode | _SriovEswitchEncapModeLiteralType
)

class SriovEswitchInlineMode(GObject.GEnum):
    LINK = 1
    NETWORK = 2
    NONE = 0
    PRESERVE = -1
    TRANSPORT = 3

_SriovEswitchInlineModeLiteralType: TypeAlias = Literal[
    "NM_SRIOV_ESWITCH_INLINE_MODE_LINK",
    "NM_SRIOV_ESWITCH_INLINE_MODE_NETWORK",
    "NM_SRIOV_ESWITCH_INLINE_MODE_NONE",
    "NM_SRIOV_ESWITCH_INLINE_MODE_PRESERVE",
    "NM_SRIOV_ESWITCH_INLINE_MODE_TRANSPORT",
    "link",
    "network",
    "none",
    "preserve",
    "transport",
]
_SriovEswitchInlineModeValueType: TypeAlias = (
    SriovEswitchInlineMode | _SriovEswitchInlineModeLiteralType
)

class SriovEswitchMode(GObject.GEnum):
    LEGACY = 0
    PRESERVE = -1
    SWITCHDEV = 1

_SriovEswitchModeLiteralType: TypeAlias = Literal[
    "NM_SRIOV_ESWITCH_MODE_LEGACY",
    "NM_SRIOV_ESWITCH_MODE_PRESERVE",
    "NM_SRIOV_ESWITCH_MODE_SWITCHDEV",
    "legacy",
    "preserve",
    "switchdev",
]
_SriovEswitchModeValueType: TypeAlias = SriovEswitchMode | _SriovEswitchModeLiteralType

class SriovPreserveOnDown(GObject.GEnum):
    DEFAULT = -1
    NO = 0
    YES = 1

_SriovPreserveOnDownLiteralType: TypeAlias = Literal[
    "NM_SRIOV_PRESERVE_ON_DOWN_DEFAULT",
    "NM_SRIOV_PRESERVE_ON_DOWN_NO",
    "NM_SRIOV_PRESERVE_ON_DOWN_YES",
    "default",
    "no",
    "yes",
]
_SriovPreserveOnDownValueType: TypeAlias = (
    SriovPreserveOnDown | _SriovPreserveOnDownLiteralType
)

class SriovVFVlanProtocol(GObject.GEnum): ...

class State(GObject.GEnum):
    ASLEEP = 10
    CONNECTED_GLOBAL = 70
    CONNECTED_LOCAL = 50
    CONNECTED_SITE = 60
    CONNECTING = 40
    DISABLED = 10
    DISCONNECTED = 20
    DISCONNECTING = 30
    UNKNOWN = 0

_StateLiteralType: TypeAlias = Literal[
    "NM_STATE_ASLEEP",
    "NM_STATE_CONNECTED_GLOBAL",
    "NM_STATE_CONNECTED_LOCAL",
    "NM_STATE_CONNECTED_SITE",
    "NM_STATE_CONNECTING",
    "NM_STATE_DISCONNECTED",
    "NM_STATE_DISCONNECTING",
    "NM_STATE_UNKNOWN",
    "asleep",
    "connected-global",
    "connected-local",
    "connected-site",
    "connecting",
    "disconnected",
    "disconnecting",
    "unknown",
]
_StateValueType: TypeAlias = State | _StateLiteralType

class Ternary(GObject.GEnum):
    DEFAULT = -1
    FALSE = 0
    TRUE = 1

_TernaryLiteralType: TypeAlias = Literal[
    "NM_TERNARY_DEFAULT",
    "NM_TERNARY_FALSE",
    "NM_TERNARY_TRUE",
    "default",
    "false",
    "true",
]
_TernaryValueType: TypeAlias = Ternary | _TernaryLiteralType

class UtilsSecurityType(GObject.GEnum):
    DYNAMIC_WEP = 4
    INVALID = 0
    LEAP = 3
    NONE = 1
    OWE = 10
    SAE = 9
    STATIC_WEP = 2
    WPA2_ENTERPRISE = 8
    WPA2_PSK = 7
    WPA3_SUITE_B_192 = 11
    WPA_ENTERPRISE = 6
    WPA_PSK = 5

_UtilsSecurityTypeLiteralType: TypeAlias = Literal[
    "NMU_SEC_DYNAMIC_WEP",
    "NMU_SEC_INVALID",
    "NMU_SEC_LEAP",
    "NMU_SEC_NONE",
    "NMU_SEC_OWE",
    "NMU_SEC_SAE",
    "NMU_SEC_STATIC_WEP",
    "NMU_SEC_WPA2_ENTERPRISE",
    "NMU_SEC_WPA2_PSK",
    "NMU_SEC_WPA3_SUITE_B_192",
    "NMU_SEC_WPA_ENTERPRISE",
    "NMU_SEC_WPA_PSK",
    "dynamic-wep",
    "invalid",
    "leap",
    "none",
    "owe",
    "sae",
    "static-wep",
    "wpa-enterprise",
    "wpa-psk",
    "wpa2-enterprise",
    "wpa2-psk",
    "wpa3-suite-b-192",
]
_UtilsSecurityTypeValueType: TypeAlias = (
    UtilsSecurityType | _UtilsSecurityTypeLiteralType
)

class VersionInfoCapability(GObject.GEnum):
    IP4_FORWARDING = 1
    SRIOV_PRESERVE_ON_DOWN = 2
    SYNC_ROUTE_WITH_TABLE = 0

_VersionInfoCapabilityLiteralType: TypeAlias = Literal[
    "NM_VERSION_INFO_CAPABILITY_IP4_FORWARDING",
    "NM_VERSION_INFO_CAPABILITY_SRIOV_PRESERVE_ON_DOWN",
    "NM_VERSION_INFO_CAPABILITY_SYNC_ROUTE_WITH_TABLE",
    "ip4-forwarding",
    "sriov-preserve-on-down",
    "sync-route-with-table",
]
_VersionInfoCapabilityValueType: TypeAlias = (
    VersionInfoCapability | _VersionInfoCapabilityLiteralType
)

class VlanPriorityMap(GObject.GEnum):
    EGRESS_MAP = 1
    INGRESS_MAP = 0

_VlanPriorityMapLiteralType: TypeAlias = Literal[
    "NM_VLAN_EGRESS_MAP", "NM_VLAN_INGRESS_MAP", "egress-map", "ingress-map"
]
_VlanPriorityMapValueType: TypeAlias = VlanPriorityMap | _VlanPriorityMapLiteralType

class VpnConnectionState(GObject.GEnum):
    ACTIVATED = 5
    CONNECT = 3
    DISCONNECTED = 7
    FAILED = 6
    IP_CONFIG_GET = 4
    NEED_AUTH = 2
    PREPARE = 1
    UNKNOWN = 0

_VpnConnectionStateLiteralType: TypeAlias = Literal[
    "NM_VPN_CONNECTION_STATE_ACTIVATED",
    "NM_VPN_CONNECTION_STATE_CONNECT",
    "NM_VPN_CONNECTION_STATE_DISCONNECTED",
    "NM_VPN_CONNECTION_STATE_FAILED",
    "NM_VPN_CONNECTION_STATE_IP_CONFIG_GET",
    "NM_VPN_CONNECTION_STATE_NEED_AUTH",
    "NM_VPN_CONNECTION_STATE_PREPARE",
    "NM_VPN_CONNECTION_STATE_UNKNOWN",
    "activated",
    "connect",
    "disconnected",
    "failed",
    "ip-config-get",
    "need-auth",
    "prepare",
    "unknown",
]
_VpnConnectionStateValueType: TypeAlias = (
    VpnConnectionState | _VpnConnectionStateLiteralType
)

class VpnConnectionStateReason(GObject.GEnum):
    CONNECTION_REMOVED = 11
    CONNECT_TIMEOUT = 6
    DEVICE_DISCONNECTED = 3
    IP_CONFIG_INVALID = 5
    LOGIN_FAILED = 10
    NONE = 1
    NO_SECRETS = 9
    SERVICE_START_FAILED = 8
    SERVICE_START_TIMEOUT = 7
    SERVICE_STOPPED = 4
    UNKNOWN = 0
    USER_DISCONNECTED = 2

_VpnConnectionStateReasonLiteralType: TypeAlias = Literal[
    "NM_VPN_CONNECTION_STATE_REASON_CONNECTION_REMOVED",
    "NM_VPN_CONNECTION_STATE_REASON_CONNECT_TIMEOUT",
    "NM_VPN_CONNECTION_STATE_REASON_DEVICE_DISCONNECTED",
    "NM_VPN_CONNECTION_STATE_REASON_IP_CONFIG_INVALID",
    "NM_VPN_CONNECTION_STATE_REASON_LOGIN_FAILED",
    "NM_VPN_CONNECTION_STATE_REASON_NONE",
    "NM_VPN_CONNECTION_STATE_REASON_NO_SECRETS",
    "NM_VPN_CONNECTION_STATE_REASON_SERVICE_START_FAILED",
    "NM_VPN_CONNECTION_STATE_REASON_SERVICE_START_TIMEOUT",
    "NM_VPN_CONNECTION_STATE_REASON_SERVICE_STOPPED",
    "NM_VPN_CONNECTION_STATE_REASON_UNKNOWN",
    "NM_VPN_CONNECTION_STATE_REASON_USER_DISCONNECTED",
    "connect-timeout",
    "connection-removed",
    "device-disconnected",
    "ip-config-invalid",
    "login-failed",
    "no-secrets",
    "none",
    "service-start-failed",
    "service-start-timeout",
    "service-stopped",
    "unknown",
    "user-disconnected",
]
_VpnConnectionStateReasonValueType: TypeAlias = (
    VpnConnectionStateReason | _VpnConnectionStateReasonLiteralType
)

class VpnPluginError(GObject.GEnum):
    ALREADYSTARTED = 2
    ALREADYSTOPPED = 4
    BADARGUMENTS = 6
    FAILED = 0
    INTERACTIVENOTSUPPORTED = 9
    INVALIDCONNECTION = 8
    LAUNCHFAILED = 7
    STARTINGINPROGRESS = 1
    STOPPINGINPROGRESS = 3
    WRONGSTATE = 5
    @staticmethod
    def quark() -> int: ...

_VpnPluginErrorLiteralType: TypeAlias = Literal[
    "AlreadyStarted",
    "AlreadyStopped",
    "BadArguments",
    "Failed",
    "InteractiveNotSupported",
    "InvalidConnection",
    "LaunchFailed",
    "NM_VPN_PLUGIN_ERROR_ALREADY_STARTED",
    "NM_VPN_PLUGIN_ERROR_ALREADY_STOPPED",
    "NM_VPN_PLUGIN_ERROR_BAD_ARGUMENTS",
    "NM_VPN_PLUGIN_ERROR_FAILED",
    "NM_VPN_PLUGIN_ERROR_INTERACTIVE_NOT_SUPPORTED",
    "NM_VPN_PLUGIN_ERROR_INVALID_CONNECTION",
    "NM_VPN_PLUGIN_ERROR_LAUNCH_FAILED",
    "NM_VPN_PLUGIN_ERROR_STARTING_IN_PROGRESS",
    "NM_VPN_PLUGIN_ERROR_STOPPING_IN_PROGRESS",
    "NM_VPN_PLUGIN_ERROR_WRONG_STATE",
    "StartingInProgress",
    "StoppingInProgress",
    "WrongState",
]
_VpnPluginErrorValueType: TypeAlias = VpnPluginError | _VpnPluginErrorLiteralType

class VpnPluginFailure(GObject.GEnum):
    BAD_IP_CONFIG = 2
    CONNECT_FAILED = 1
    LOGIN_FAILED = 0

_VpnPluginFailureLiteralType: TypeAlias = Literal[
    "NM_VPN_PLUGIN_FAILURE_BAD_IP_CONFIG",
    "NM_VPN_PLUGIN_FAILURE_CONNECT_FAILED",
    "NM_VPN_PLUGIN_FAILURE_LOGIN_FAILED",
    "bad-ip-config",
    "connect-failed",
    "login-failed",
]
_VpnPluginFailureValueType: TypeAlias = VpnPluginFailure | _VpnPluginFailureLiteralType

class VpnServiceState(GObject.GEnum):
    INIT = 1
    SHUTDOWN = 2
    STARTED = 4
    STARTING = 3
    STOPPED = 6
    STOPPING = 5
    UNKNOWN = 0

_VpnServiceStateLiteralType: TypeAlias = Literal[
    "NM_VPN_SERVICE_STATE_INIT",
    "NM_VPN_SERVICE_STATE_SHUTDOWN",
    "NM_VPN_SERVICE_STATE_STARTED",
    "NM_VPN_SERVICE_STATE_STARTING",
    "NM_VPN_SERVICE_STATE_STOPPED",
    "NM_VPN_SERVICE_STATE_STOPPING",
    "NM_VPN_SERVICE_STATE_UNKNOWN",
    "init",
    "shutdown",
    "started",
    "starting",
    "stopped",
    "stopping",
    "unknown",
]
_VpnServiceStateValueType: TypeAlias = VpnServiceState | _VpnServiceStateLiteralType

class WepKeyType(GObject.GEnum):
    KEY = 1
    PASSPHRASE = 2
    UNKNOWN = 0

_WepKeyTypeLiteralType: TypeAlias = Literal[
    "NM_WEP_KEY_TYPE_KEY",
    "NM_WEP_KEY_TYPE_PASSPHRASE",
    "NM_WEP_KEY_TYPE_UNKNOWN",
    "key",
    "passphrase",
    "unknown",
]
_WepKeyTypeValueType: TypeAlias = WepKeyType | _WepKeyTypeLiteralType

class WifiBand(GObject.GEnum):
    UNKNOWN = 0

_WifiBandLiteralType: TypeAlias = Literal["NM_WIFI_BAND_UNKNOWN", "unknown"]
_WifiBandValueType: TypeAlias = WifiBand | _WifiBandLiteralType

class WimaxNspNetworkType(GObject.GEnum):
    HOME = 1
    PARTNER = 2
    ROAMING_PARTNER = 3
    UNKNOWN = 0

_WimaxNspNetworkTypeLiteralType: TypeAlias = Literal[
    "NM_WIMAX_NSP_NETWORK_TYPE_HOME",
    "NM_WIMAX_NSP_NETWORK_TYPE_PARTNER",
    "NM_WIMAX_NSP_NETWORK_TYPE_ROAMING_PARTNER",
    "NM_WIMAX_NSP_NETWORK_TYPE_UNKNOWN",
    "home",
    "partner",
    "roaming-partner",
    "unknown",
]
_WimaxNspNetworkTypeValueType: TypeAlias = (
    WimaxNspNetworkType | _WimaxNspNetworkTypeLiteralType
)
