/**
 * @file test_reefvolt_can.c
 * @brief Host unit tests for the ReefVolt CAN catalog.
 *
 * Build/run:  make && ./build/test_reefvolt_can
 * SPDX-License-Identifier: Apache-2.0
 */
#include <stdio.h>
#include <string.h>
#include "reefvolt_can.h"

static int failures = 0;
static int checks = 0;
#define CHECK(cond)                                                      \
    do {                                                                 \
        ++checks;                                                        \
        if (!(cond)) {                                                   \
            printf("  FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);     \
            ++failures;                                                  \
        }                                                                \
    } while (0)

static void test_id_roundtrip(void)
{
    /* representative frames spanning the field ranges */
    const uint8_t prio[] = {0, 3, 7};
    const uint8_t msg[]  = {RVCAN_MSG_HEARTBEAT, RVCAN_MSG_DRYCONTACT_CMD, 0xFF};
    const uint8_t dest[] = {RVCAN_ADDR_MASTER, 0x2A, RVCAN_ADDR_BROADCAST};
    const uint8_t src[]  = {RVCAN_ADDR_MASTER, 0x2A, RVCAN_ADDR_UNCONFIGURED};

    for (size_t i = 0; i < 3; ++i) {
        uint32_t id = rvcan_pack_id(prio[i], msg[i], dest[i], src[i]);
        CHECK(id <= 0x1FFFFFFFu);               /* fits in 29 bits */
        CHECK(RVCAN_ID_PRIO(id) == prio[i]);
        CHECK(RVCAN_ID_MSG(id)  == msg[i]);
        CHECK(RVCAN_ID_DEST(id) == dest[i]);
        CHECK(RVCAN_ID_SRC(id)  == src[i]);
        CHECK(rvcan_pack_id(prio[i], msg[i], dest[i], src[i]) == RVCAN_ID(prio[i], msg[i], dest[i], src[i]));
    }
}

static void test_field_masking(void)
{
    /* over-wide inputs must truncate to their field, not bleed into neighbours.
     * Exercise the macro directly (rvcan_pack_id's uint8_t params can't overflow). */
    uint32_t id = RVCAN_ID(0x1F, 0x1FF, 0x1FF, 0x1FF);
    CHECK(RVCAN_ID_PRIO(id) == 0x7);
    CHECK(RVCAN_ID_MSG(id)  == 0xFF);
    CHECK(RVCAN_ID_DEST(id) == 0xFF);
    CHECK(RVCAN_ID_SRC(id)  == 0xFF);
    CHECK((id & 0x3u) == 0);                    /* reserved low bits stay 0 */
}

static void test_arbitration_priority(void)
{
    /* lower PRIO number -> lower raw id -> wins CAN arbitration */
    uint32_t emerg = rvcan_pack_id(RVCAN_PRIO_EMERGENCY, RVCAN_MSG_FAULT,
                                   RVCAN_ADDR_MASTER, 0x20);
    uint32_t telem = rvcan_pack_id(RVCAN_PRIO_TELEMETRY, RVCAN_MSG_TEMPERATURE,
                                   RVCAN_ADDR_MASTER, 0x20);
    CHECK(emerg < telem);

    /* a broadcast heartbeat outranks a command */
    uint32_t hb  = rvcan_pack_id(RVCAN_PRIO_NETWORK, RVCAN_MSG_HEARTBEAT,
                                 RVCAN_ADDR_BROADCAST, RVCAN_ADDR_MASTER);
    uint32_t cmd = rvcan_pack_id(RVCAN_PRIO_COMMAND, RVCAN_MSG_DRYCONTACT_CMD,
                                 0x03, RVCAN_ADDR_MASTER);
    CHECK(hb < cmd);
}

static void test_is_for_me(void)
{
    CHECK(rvcan_is_for_me(0x03, 0x03) == true);              /* exact match */
    CHECK(rvcan_is_for_me(RVCAN_ADDR_BROADCAST, 0x03) == true);
    CHECK(rvcan_is_for_me(0x04, 0x03) == false);             /* other node */
    CHECK(rvcan_is_for_me(RVCAN_ADDR_MASTER, 0x03) == false);
}

static void test_crc32_known_vector(void)
{
    /* canonical CRC-32 check value for "123456789" is 0xCBF43926 */
    CHECK(rvcan_crc32("123456789", 9) == 0xCBF43926u);
    CHECK(rvcan_crc32("", 0) == 0x00000000u);
}

static void test_uid_token(void)
{
    uint32_t a = rvcan_uid_token(0x11111111u, 0x22222222u, 0x33333333u);
    uint32_t b = rvcan_uid_token(0x11111111u, 0x22222222u, 0x33333333u);
    uint32_t c = rvcan_uid_token(0x11111111u, 0x22222222u, 0x33333334u);
    CHECK(a == b);   /* deterministic */
    CHECK(a != c);   /* one-bit UID change flips the token */
}

static void test_payload_sizes(void)
{
    CHECK(sizeof(rvcan_heartbeat_t) == RVCAN_DLC);
    CHECK(sizeof(rvcan_drycontact_cmd_t) == RVCAN_DLC);
    CHECK(sizeof(rvcan_addr_request_t) == RVCAN_DLC);
    CHECK(sizeof(rvcan_config_t) == RVCAN_DLC);
}

int main(void)
{
    test_id_roundtrip();
    test_field_masking();
    test_arbitration_priority();
    test_is_for_me();
    test_crc32_known_vector();
    test_uid_token();
    test_payload_sizes();

    printf("reefvolt_can: %d checks, %d failures\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
