/**
 * @file reefvolt_can.h
 * @brief ReefVolt cluster CAN message catalog — the shared source of truth.
 *
 * Every board on the SensorBuddy CAN bus (SensorBuddy master, PlugControl,
 * DryContact, future carriers) speaks this protocol. It is intentionally
 * header-first: the catalog IS the definitions below. Firmware links this;
 * host tooling / the ESP32 bridge can reuse the same header.
 *
 * ## 29-bit extended identifier (J1939-inspired)
 *
 *   bit 28      26 25         18 17         10 9          2 1  0
 *      +----------+-------------+-------------+-------------+----+
 *      |   PRIO   |    MSGID    |    DEST     |    SRC      |RSVD|
 *      |   (3)    |     (8)     |     (8)     |     (8)     | (2)|
 *      +----------+-------------+-------------+-------------+----+
 *
 * - PRIO  : 0 = highest .. 7 = lowest. CAN arbitration favours the lower raw
 *           id, so PRIO 0 (emergency/safety) always wins the bus.
 * - MSGID : message / function code (see RVCAN_MSG_*).
 * - DEST  : destination node address (RVCAN_ADDR_BROADCAST = all).
 * - SRC   : source node address.
 * - RSVD  : reserved, transmit 0.
 *
 * ## Addressing — dynamic, keyed on the STM32 UID
 *
 * There are NO address straps. SensorBuddy (the sole master, fixed address
 * RVCAN_ADDR_MASTER) hands out node addresses: an un-addressed carrier boots,
 * sends ADDR_REQUEST from RVCAN_ADDR_UNCONFIGURED carrying a 32-bit token
 * derived from its 96-bit STM32 UID, and the master replies ADDR_ASSIGN
 * (matched by token). The master persists token->address in flash so a given
 * physical board keeps its address across reboots (stable Home Assistant
 * entities). Fail-safe is address-independent: an un-addressed carrier stays
 * de-energized and still runs its heartbeat-loss watchdog off the broadcast
 * master heartbeat.
 *
 * Wire uses CLASSIC CAN frames (8-byte payloads); every payload struct below
 * is padded to 8 bytes so DLC is always 8.
 *
 * Copyright (c) 2026 blueAcro / Yann Ramin
 * SPDX-License-Identifier: Apache-2.0
 */
#ifndef REEFVOLT_CAN_H
#define REEFVOLT_CAN_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------- */
/* Version                                                                     */
/* -------------------------------------------------------------------------- */
#define RVCAN_PROTOCOL_VERSION_MAJOR 0
#define RVCAN_PROTOCOL_VERSION_MINOR 1  /* v0.1: initial 29-bit catalog */

#define RVCAN_DLC 8u                    /* all frames are 8-byte classic CAN */

/* -------------------------------------------------------------------------- */
/* 29-bit identifier field layout                                              */
/* -------------------------------------------------------------------------- */
#define RVCAN_PRIO_POS  26u
#define RVCAN_MSG_POS   18u
#define RVCAN_DEST_POS  10u
#define RVCAN_SRC_POS    2u

#define RVCAN_PRIO_MASK 0x07u
#define RVCAN_MSG_MASK  0xFFu
#define RVCAN_DEST_MASK 0xFFu
#define RVCAN_SRC_MASK  0xFFu

/** Build a 29-bit id from its fields. */
#define RVCAN_ID(prio, msg, dest, src)                                     \
    ((((uint32_t)(prio) & RVCAN_PRIO_MASK) << RVCAN_PRIO_POS) |            \
     (((uint32_t)(msg)  & RVCAN_MSG_MASK)  << RVCAN_MSG_POS)  |            \
     (((uint32_t)(dest) & RVCAN_DEST_MASK) << RVCAN_DEST_POS) |            \
     (((uint32_t)(src)  & RVCAN_SRC_MASK)  << RVCAN_SRC_POS))

#define RVCAN_ID_PRIO(id) (((uint32_t)(id) >> RVCAN_PRIO_POS) & RVCAN_PRIO_MASK)
#define RVCAN_ID_MSG(id)  (((uint32_t)(id) >> RVCAN_MSG_POS)  & RVCAN_MSG_MASK)
#define RVCAN_ID_DEST(id) (((uint32_t)(id) >> RVCAN_DEST_POS) & RVCAN_DEST_MASK)
#define RVCAN_ID_SRC(id)  (((uint32_t)(id) >> RVCAN_SRC_POS)  & RVCAN_SRC_MASK)

/* -------------------------------------------------------------------------- */
/* Priorities (lower value wins arbitration)                                   */
/* -------------------------------------------------------------------------- */
enum {
    RVCAN_PRIO_EMERGENCY = 0, /* faults, safety trips */
    RVCAN_PRIO_SAFETY    = 1, /* safety-critical heartbeat/commands */
    RVCAN_PRIO_NETWORK   = 2, /* address mgmt, master heartbeat */
    RVCAN_PRIO_COMMAND   = 3, /* actuator commands */
    RVCAN_PRIO_STATUS    = 4, /* node status/liveness */
    RVCAN_PRIO_CONFIG    = 5, /* config get/set */
    RVCAN_PRIO_TELEMETRY = 6, /* currents, temperatures */
    RVCAN_PRIO_LOWEST    = 7
};

/* -------------------------------------------------------------------------- */
/* Node addresses                                                              */
/* -------------------------------------------------------------------------- */
#define RVCAN_ADDR_MASTER        0x00u /* SensorBuddy — the sole CAN master */
#define RVCAN_ADDR_ASSIGN_MIN    0x01u /* first assignable carrier address */
#define RVCAN_ADDR_ASSIGN_MAX    0xEFu /* last assignable carrier address */
#define RVCAN_ADDR_RESERVED_MIN  0xF0u
#define RVCAN_ADDR_UNCONFIGURED  0xFDu /* SRC used by a node awaiting an address */
#define RVCAN_ADDR_RESERVED      0xFEu
#define RVCAN_ADDR_BROADCAST     0xFFu /* DEST = all nodes */

/* -------------------------------------------------------------------------- */
/* Message / function codes (MSGID)                                            */
/* -------------------------------------------------------------------------- */
enum {
    /* network management + dynamic addressing (0x00-0x0F) */
    RVCAN_MSG_HEARTBEAT     = 0x00, /* master -> broadcast, PRIO_NETWORK */
    RVCAN_MSG_ADDR_REQUEST  = 0x01, /* unconfigured node -> master */
    RVCAN_MSG_ADDR_ASSIGN   = 0x02, /* master -> node (matched by uid token) */
    RVCAN_MSG_ADDR_NAK      = 0x03, /* master -> node: request rejected/conflict */
    RVCAN_MSG_ANNOUNCE      = 0x04, /* node -> master: identity after addressing */
    RVCAN_MSG_RESET         = 0x05, /* master -> broadcast: drop addr, re-enumerate */

    /* emergency / faults (0x10-0x1F), PRIO_EMERGENCY */
    RVCAN_MSG_FAULT         = 0x10, /* node -> master */

    /* node status / liveness (0x20-0x2F), PRIO_STATUS */
    RVCAN_MSG_NODE_STATUS   = 0x20, /* node -> master */

    /* actuator commands (0x30-0x3F), PRIO_COMMAND (heater = PRIO_SAFETY) */
    RVCAN_MSG_DRYCONTACT_CMD = 0x30, /* master -> DryContact */
    RVCAN_MSG_HEATER_CMD     = 0x31, /* master -> PlugControl */
    RVCAN_MSG_SAFETY_CLEAR   = 0x32, /* master -> PlugControl: clear safety latch */

    /* telemetry (0x40-0x4F), PRIO_TELEMETRY */
    RVCAN_MSG_DRYCONTACT_STATE = 0x40, /* DryContact -> master */
    RVCAN_MSG_CURRENT          = 0x41, /* PlugControl -> master */
    RVCAN_MSG_TEMPERATURE      = 0x42, /* node -> master */

    /* config (0x50-0x5F), PRIO_CONFIG */
    RVCAN_MSG_CONFIG_GET    = 0x50, /* master -> node */
    RVCAN_MSG_CONFIG_SET    = 0x51, /* master -> node */
    RVCAN_MSG_CONFIG_REPORT = 0x52  /* node -> master */
};

/* -------------------------------------------------------------------------- */
/* Device types (in ADDR_REQUEST / ANNOUNCE)                                   */
/* -------------------------------------------------------------------------- */
enum {
    RVCAN_DEV_UNKNOWN     = 0x00,
    RVCAN_DEV_SENSORBUDDY = 0x01, /* the master */
    RVCAN_DEV_PLUGCONTROL = 0x02,
    RVCAN_DEV_DRYCONTACT  = 0x03,
    RVCAN_DEV_OSMOBUDDY   = 0x04, /* future */
    RVCAN_DEV_DCBUDDY     = 0x05  /* future */
};

/* -------------------------------------------------------------------------- */
/* Fault codes (rvcan_fault_t.fault_code)                                       */
/* -------------------------------------------------------------------------- */
enum {
    RVCAN_FAULT_NONE          = 0x00,
    RVCAN_FAULT_OVERTEMP      = 0x01, /* PlugControl analog chain tripped */
    RVCAN_FAULT_OPEN_NTC      = 0x02,
    RVCAN_FAULT_HEARTBEAT_LOST= 0x03, /* master heartbeat timed out */
    RVCAN_FAULT_WELDED_RELAY  = 0x04,
    RVCAN_FAULT_OPEN_HEATER   = 0x05,
    RVCAN_FAULT_WATCHDOG      = 0x06,
    RVCAN_FAULT_COIL_FAULT    = 0x10, /* DryContact coil driver */
    RVCAN_FAULT_STUCK_CONTACT = 0x11  /* DryContact contact-sense mismatch */
};

/* -------------------------------------------------------------------------- */
/* DryContact per-channel command mode + CAN-loss behaviour                    */
/* -------------------------------------------------------------------------- */
enum {
    RVCAN_DC_MODE_LEVEL = 0x0, /* follow channel_mask bit directly */
    RVCAN_DC_MODE_PULSE = 0x1  /* energize for pulse_ms then release */
};
enum {
    RVCAN_DC_ONLOSS_FAILSAFE = 0x0, /* de-energize on heartbeat loss (default) */
    RVCAN_DC_ONLOSS_HOLD     = 0x1  /* hold last commanded state */
};

/* Master run-state (rvcan_heartbeat_t.master_state) */
enum {
    RVCAN_MASTER_BOOT   = 0x0,
    RVCAN_MASTER_RUN    = 0x1,
    RVCAN_MASTER_FAULT  = 0x2
};

/* -------------------------------------------------------------------------- */
/* Payload structs — all padded to RVCAN_DLC (8) bytes                         */
/* -------------------------------------------------------------------------- */
typedef struct __attribute__((packed)) {
    uint8_t  seq;          /* rolling sequence counter */
    uint8_t  master_state; /* RVCAN_MASTER_* */
    uint16_t uptime_s;     /* master uptime seconds (wraps) */
    uint8_t  flags;
    uint8_t  reserved[3];
} rvcan_heartbeat_t;

typedef struct __attribute__((packed)) {
    uint32_t uid_token;  /* CRC32 of the 96-bit STM32 UID */
    uint8_t  device_type;
    uint8_t  caps;       /* device-defined capability bits */
    uint8_t  fw_major;
    uint8_t  fw_minor;
} rvcan_addr_request_t;

typedef struct __attribute__((packed)) {
    uint32_t uid_token;      /* echoes the requester's token */
    uint8_t  assigned_addr;  /* 0x01..0xEF */
    uint8_t  reserved[3];
} rvcan_addr_assign_t;

typedef struct __attribute__((packed)) {
    uint8_t device_type;
    uint8_t fw_major;
    uint8_t fw_minor;
    uint8_t num_channels;
    uint8_t caps;
    uint8_t reserved[3];
} rvcan_announce_t;

typedef struct __attribute__((packed)) {
    uint8_t  fault_code; /* RVCAN_FAULT_* */
    uint8_t  channel;    /* 0xFF = board-wide */
    uint16_t detail;
    uint8_t  reserved[4];
} rvcan_fault_t;

typedef struct __attribute__((packed)) {
    uint8_t  state;          /* device-defined run state */
    uint8_t  flags;
    uint8_t  heartbeat_age_ds; /* deciseconds since last master heartbeat */
    uint8_t  reserved[5];
} rvcan_node_status_t;

typedef struct __attribute__((packed)) {
    uint8_t  channel_mask; /* bit per ch: desired energized state (LEVEL mode) */
    uint8_t  mode_mask;    /* bit per ch: RVCAN_DC_MODE_PULSE vs LEVEL */
    uint16_t pulse_ms;     /* pulse duration for PULSE-mode channels */
    uint8_t  reserved[4];
} rvcan_drycontact_cmd_t;

typedef struct __attribute__((packed)) {
    uint8_t contact_mask;    /* actual energized state per channel */
    uint8_t fault_mask;      /* coil/stuck fault per channel */
    uint8_t onloss_mask;     /* per-ch RVCAN_DC_ONLOSS_HOLD vs FAILSAFE */
    uint8_t heartbeat_age_ds;
    uint8_t reserved[4];
} rvcan_drycontact_state_t;

typedef struct __attribute__((packed)) {
    uint8_t enable_mask;     /* bit0 = CH_A, bit1 = CH_B */
    int16_t setpoint_c_x10;  /* target temperature, 0.1 C */
    uint8_t reserved[5];
} rvcan_heater_cmd_t;

typedef struct __attribute__((packed)) {
    uint16_t ch_a_ma;
    uint16_t ch_b_ma;
    uint8_t  reserved[4];
} rvcan_current_t;

typedef struct __attribute__((packed)) {
    uint8_t sensor_id;
    int16_t temp_c_x100;  /* temperature, 0.01 C */
    uint8_t status;
    uint8_t reserved[4];
} rvcan_temperature_t;

typedef struct __attribute__((packed)) {
    uint8_t  key;
    uint8_t  channel;
    uint32_t value;
    uint8_t  reserved[2];
} rvcan_config_t;

/* Every frame is exactly 8 bytes on the wire. */
_Static_assert(sizeof(rvcan_heartbeat_t)        == RVCAN_DLC, "heartbeat != 8");
_Static_assert(sizeof(rvcan_addr_request_t)     == RVCAN_DLC, "addr_request != 8");
_Static_assert(sizeof(rvcan_addr_assign_t)      == RVCAN_DLC, "addr_assign != 8");
_Static_assert(sizeof(rvcan_announce_t)         == RVCAN_DLC, "announce != 8");
_Static_assert(sizeof(rvcan_fault_t)            == RVCAN_DLC, "fault != 8");
_Static_assert(sizeof(rvcan_node_status_t)      == RVCAN_DLC, "node_status != 8");
_Static_assert(sizeof(rvcan_drycontact_cmd_t)   == RVCAN_DLC, "drycontact_cmd != 8");
_Static_assert(sizeof(rvcan_drycontact_state_t) == RVCAN_DLC, "drycontact_state != 8");
_Static_assert(sizeof(rvcan_heater_cmd_t)       == RVCAN_DLC, "heater_cmd != 8");
_Static_assert(sizeof(rvcan_current_t)          == RVCAN_DLC, "current != 8");
_Static_assert(sizeof(rvcan_temperature_t)      == RVCAN_DLC, "temperature != 8");
_Static_assert(sizeof(rvcan_config_t)           == RVCAN_DLC, "config != 8");

/* -------------------------------------------------------------------------- */
/* Helpers (see reefvolt_can.c)                                                 */
/* -------------------------------------------------------------------------- */

/** Pack the four id fields into a 29-bit extended identifier. */
uint32_t rvcan_pack_id(uint8_t prio, uint8_t msg, uint8_t dest, uint8_t src);

/** True if a frame addressed to @p dest should be processed by @p my_addr. */
bool rvcan_is_for_me(uint8_t dest, uint8_t my_addr);

/**
 * Derive the stable node token from the three 32-bit words of the STM32
 * 96-bit unique device ID (read from the UID registers on-target). CRC-32
 * (IEEE 802.3, reflected) — deterministic per board, effectively unique.
 */
uint32_t rvcan_uid_token(uint32_t uid_w0, uint32_t uid_w1, uint32_t uid_w2);

/** CRC-32 (IEEE, reflected) over an arbitrary buffer — used by uid_token. */
uint32_t rvcan_crc32(const void *data, size_t len);

#ifdef __cplusplus
}
#endif

#endif /* REEFVOLT_CAN_H */
