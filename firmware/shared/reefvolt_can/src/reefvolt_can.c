/**
 * @file reefvolt_can.c
 * @brief Helpers for the ReefVolt cluster CAN catalog (see reefvolt_can.h).
 *
 * Copyright (c) 2026 blueAcro / Yann Ramin
 * SPDX-License-Identifier: Apache-2.0
 */
#include "reefvolt_can.h"

uint32_t rvcan_pack_id(uint8_t prio, uint8_t msg, uint8_t dest, uint8_t src)
{
    return RVCAN_ID(prio, msg, dest, src);
}

bool rvcan_is_for_me(uint8_t dest, uint8_t my_addr)
{
    return dest == my_addr || dest == RVCAN_ADDR_BROADCAST;
}

/* CRC-32 (IEEE 802.3, reflected, poly 0xEDB88320), no table — a handful of
 * bytes per call, so the bitwise form is plenty fast and keeps flash small. */
uint32_t rvcan_crc32(const void *data, size_t len)
{
    const uint8_t *p = (const uint8_t *)data;
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; ++i) {
        crc ^= p[i];
        for (int b = 0; b < 8; ++b) {
            uint32_t mask = -(crc & 1u);
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    return ~crc;
}

uint32_t rvcan_uid_token(uint32_t uid_w0, uint32_t uid_w1, uint32_t uid_w2)
{
    /* Little-endian byte image of the 96-bit UID, so the token is stable
     * regardless of host endianness. */
    uint8_t buf[12];
    const uint32_t w[3] = { uid_w0, uid_w1, uid_w2 };
    for (int i = 0; i < 3; ++i) {
        buf[i * 4 + 0] = (uint8_t)(w[i] & 0xFFu);
        buf[i * 4 + 1] = (uint8_t)((w[i] >> 8) & 0xFFu);
        buf[i * 4 + 2] = (uint8_t)((w[i] >> 16) & 0xFFu);
        buf[i * 4 + 3] = (uint8_t)((w[i] >> 24) & 0xFFu);
    }
    return rvcan_crc32(buf, sizeof(buf));
}
