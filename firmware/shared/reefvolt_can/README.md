# ReefVolt CAN — cluster message catalog

**Status:** v0.1 (initial catalog) · **License:** Apache-2.0

The shared source of truth for the SensorBuddy CAN cluster. Every board links
[`include/reefvolt_can.h`](include/reefvolt_can.h) — SensorBuddy (the master),
PlugControl, DryContact, and future carriers — so a message defined once is
identical on the wire, in firmware, and in host/bridge tooling.

- **Physical bus:** 1 Mbit classic CAN over the Micro-Fit daisy-chain (CAN-H/L +
  12–24 V + GND). All nodes are STM32G0B1 FDCAN peripherals running classic frames.
- **Transceiver:** TCAN1044VDRQ1 on every board.

## Identifier (29-bit extended, J1939-inspired)

```
 bit 28      26 25         18 17         10 9          2 1  0
    +----------+-------------+-------------+-------------+----+
    |   PRIO   |    MSGID    |    DEST     |    SRC      |RSVD|
    |   (3)    |     (8)     |     (8)     |     (8)     | (2)|
    +----------+-------------+-------------+-------------+----+
```

`RVCAN_ID(prio, msg, dest, src)` builds it; `RVCAN_ID_PRIO/MSG/DEST/SRC(id)`
decode it. Lower raw id wins CAN arbitration, so **PRIO 0 (emergency) always
beats PRIO 6 (telemetry)** regardless of who is transmitting.

## Addresses

| Address | Meaning |
|---|---|
| `0x00` | **SensorBuddy** — the sole master |
| `0x01`–`0xEF` | assignable carrier node addresses |
| `0xFD` | un-configured (SRC used by a node awaiting an address) |
| `0xFF` | broadcast (DEST = all) |

There are **no address straps** — see enumeration below.

## Priorities

| Value | Name | Used by |
|---|---|---|
| 0 | EMERGENCY | faults, safety trips |
| 1 | SAFETY | heater heartbeat / safety commands |
| 2 | NETWORK | master heartbeat, address management |
| 3 | COMMAND | actuator commands |
| 4 | STATUS | node status / liveness |
| 5 | CONFIG | config get/set |
| 6 | TELEMETRY | currents, temperatures |

## Message catalog

All payloads are exactly 8 bytes (classic CAN, DLC 8); structs in the header
carry the field layout. `_Static_assert`s enforce the size.

| MSGID | Name | Dir | Prio | Payload struct |
|---|---|---|---|---|
| `0x00` | HEARTBEAT | master → broadcast | NETWORK | `rvcan_heartbeat_t` |
| `0x01` | ADDR_REQUEST | unconfigured → master | NETWORK | `rvcan_addr_request_t` |
| `0x02` | ADDR_ASSIGN | master → node | NETWORK | `rvcan_addr_assign_t` |
| `0x03` | ADDR_NAK | master → node | NETWORK | — |
| `0x04` | ANNOUNCE | node → master | NETWORK | `rvcan_announce_t` |
| `0x05` | RESET | master → broadcast | NETWORK | — |
| `0x10` | FAULT | node → master | EMERGENCY | `rvcan_fault_t` |
| `0x20` | NODE_STATUS | node → master | STATUS | `rvcan_node_status_t` |
| `0x30` | DRYCONTACT_CMD | master → DryContact | COMMAND | `rvcan_drycontact_cmd_t` |
| `0x31` | HEATER_CMD | master → PlugControl | SAFETY | `rvcan_heater_cmd_t` |
| `0x32` | SAFETY_CLEAR | master → PlugControl | SAFETY | — |
| `0x40` | DRYCONTACT_STATE | DryContact → master | TELEMETRY | `rvcan_drycontact_state_t` |
| `0x41` | CURRENT | PlugControl → master | TELEMETRY | `rvcan_current_t` |
| `0x42` | TEMPERATURE | node → master | TELEMETRY | `rvcan_temperature_t` |
| `0x50` | CONFIG_GET | master → node | CONFIG | `rvcan_config_t` |
| `0x51` | CONFIG_SET | master → node | CONFIG | `rvcan_config_t` |
| `0x52` | CONFIG_REPORT | node → master | CONFIG | `rvcan_config_t` |

## Dynamic addressing (UID auto-assign)

No straps. Each STM32's 96-bit UID becomes a stable 32-bit **token**
(`rvcan_uid_token()` = CRC-32 of the UID). Boot handshake:

```
  node (SRC=0xFD)                          master (0x00)
     |-- ADDR_REQUEST(token, type, fw) ------->|   0xFD -> 0xFF
     |                                         |   (look up token in flash;
     |                                         |    allocate next free addr)
     |<------------- ADDR_ASSIGN(token, addr) -|   0x00 -> 0xFF
     |  adopt SRC=addr                         |
     |-- ANNOUNCE(type, fw, caps, nch) ------->|   addr -> 0x00
     |          ... normal operation ...       |
```

The master **persists token→address in flash**, so a physical board keeps its
address across reboots (stable Home Assistant entities). New board → new token
→ new address. `RESET` forces re-enumeration.

> **Collision handling:** all un-configured nodes share `SRC=0xFD`, so two booting
> simultaneously would emit `ADDR_REQUEST` frames with identical ids (CAN cannot
> arbitrate equal ids carrying different data → error frames). The addressing
> state machine must therefore back off by a **UID-token-seeded random delay**
> before (re)transmitting `ADDR_REQUEST`, relying on CAN's native retransmit to
> resolve the rare clash. (Enumeration is gated on first hearing a heartbeat, so
> requests are already staggered against the master, not each other.)

## Fail-safe (address-independent)

The master heartbeat (`0x00`, broadcast) is not addressed, so **even an
un-addressed carrier watches it and runs its heartbeat-loss watchdog**. On
timeout a carrier applies its fail-safe:
- **DryContact:** per-channel `RVCAN_DC_ONLOSS_FAILSAFE` (de-energize) or `HOLD`.
- **PlugControl:** the hardware safety chain drops the heater regardless of firmware.

A node with no valid address never actuates — addressing can't weaken safety.

## Build / test

```
cd tests && make test      # host unit tests (gcc/clang, C11)
```

Link into a board via CMake: `add_subdirectory(../shared/reefvolt_can)` then
`target_link_libraries(<board> PRIVATE reefvolt_can)`.

## Versioning

`RVCAN_PROTOCOL_VERSION_MAJOR/MINOR`. Bump MINOR for additive messages/fields,
MAJOR for wire-breaking changes. All boards on a bus must share the MAJOR.
