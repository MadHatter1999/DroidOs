/* DroidOS safety controller firmware (spec §24).
 *
 * Portable C over a small board HAL. Owns the motor-power contactor, which defaults
 * OPEN at reset. Enters the safe state (power removed) on emergency stop, any fault,
 * or host silence. This device is authoritative for motor power; the Linux host and
 * the LLM cannot override it.
 *
 * Implement the hal_* functions for your board (see hal.h). The control loop below
 * is board-independent.
 */
#include <stdint.h>
#include <stdbool.h>
#include "protocol.h"
#include "hal.h"

#define LOOP_HZ            1000u   /* 1 kHz control loop */
#define STATE_TX_HZ        50u     /* status to host at 50 Hz */
#define HOST_TIMEOUT_MS    100u    /* host silence beyond this -> safe state */
#define OVERTEMP_C         85      /* controller-reported motor fault temperature */

typedef struct {
    bool     estop_latched;
    bool     power_requested;   /* host has asked for power */
    bool     power_on;          /* actual contactor state */
    uint8_t  faults;            /* FAULT_* bit flags */
    uint32_t last_host_ms;      /* time of last valid host frame */
} safety_t;

static safety_t S;

/* --- helpers ----------------------------------------------------------- */
static void enter_safe_state(uint8_t fault_bit) {
    S.faults |= fault_bit;
    S.power_on = false;
    hal_contactor_set(false);   /* physically open the motor-power contactor */
}

static bool may_enable_power(void) {
    return !S.estop_latched
        && S.faults == 0
        && (hal_millis() - S.last_host_ms) < HOST_TIMEOUT_MS;
}

/* --- host frames ------------------------------------------------------- */
static void on_host_message(uint8_t type, const uint8_t *payload, uint8_t len) {
    S.last_host_ms = hal_millis();       /* any valid frame is a heartbeat */
    switch (type) {
        case MSG_HEARTBEAT:
            break;
        case MSG_ENABLE_POWER:
            S.power_requested = true;
            break;
        case MSG_DISABLE_POWER:
            S.power_requested = false;
            S.power_on = false;
            hal_contactor_set(false);
            break;
        case MSG_CLEAR_FAULT:
            /* e-stop is a hard latch cleared only by the physical reset path */
            S.faults &= (uint8_t)~(FAULT_OVERTEMP | FAULT_JOINT_LIMIT
                                   | FAULT_WATCHDOG | FAULT_HOST_SILENT);
            break;
        case MSG_REPORT_FAULT:
            if (len >= 1) enter_safe_state(payload[0]);
            break;
        default:
            /* unknown/invalid command is treated conservatively */
            enter_safe_state(0);
            break;
    }
}

/* --- periodic checks --------------------------------------------------- */
static void poll_hardware_faults(void) {
    if (hal_estop_asserted()) {
        S.estop_latched = true;
        enter_safe_state(FAULT_ESTOP);
    }
    if (hal_max_motor_temp_c() >= OVERTEMP_C) {
        enter_safe_state(FAULT_OVERTEMP);
    }
    if (hal_joint_limit_tripped()) {
        enter_safe_state(FAULT_JOINT_LIMIT);
    }
    if ((hal_millis() - S.last_host_ms) >= HOST_TIMEOUT_MS) {
        enter_safe_state(FAULT_HOST_SILENT);   /* host went quiet -> safe state */
    }
}

static void update_contactor(void) {
    if (S.power_requested && may_enable_power()) {
        S.power_on = true;
        hal_contactor_set(true);
    } else {
        S.power_on = false;
        hal_contactor_set(false);
    }
}

static void send_state(void) {
    uint8_t flags = STATE_WATCHDOG_OK;
    if ((hal_millis() - S.last_host_ms) < HOST_TIMEOUT_MS) flags |= STATE_ALIVE;
    if (S.power_on) flags |= STATE_POWER_ON;
    uint8_t payload[2] = { flags, S.faults };
    hal_uart_send_frame(MSG_STATE, payload, sizeof(payload));
}

/* --- entry ------------------------------------------------------------- */
int main(void) {
    hal_init();
    hal_contactor_set(false);   /* power OFF at reset (spec §8, §40) */
    S.last_host_ms = hal_millis();

    uint32_t next_state_tx = 0;
    const uint32_t state_period = 1000u / STATE_TX_HZ;

    for (;;) {
        hal_watchdog_pet();

        uint8_t type, len;
        uint8_t payload[64];
        while (hal_uart_read_frame(&type, payload, &len)) {
            on_host_message(type, payload, len);
        }

        poll_hardware_faults();
        update_contactor();

        uint32_t now = hal_millis();
        if (now >= next_state_tx) {
            send_state();
            next_state_tx = now + state_period;
        }

        hal_delay_until_next_tick(1000u / LOOP_HZ);
    }
    return 0;
}

/* CRC-8 (poly 0x07) used by the framing layer. */
uint8_t crc8(const uint8_t *data, uint16_t len) {
    uint8_t crc = 0;
    for (uint16_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (uint8_t b = 0; b < 8; b++)
            crc = (crc & 0x80u) ? (uint8_t)((crc << 1) ^ 0x07u) : (uint8_t)(crc << 1);
    }
    return crc;
}
