/* DroidOS safety-controller serial protocol (spec §12.2, §24).
 *
 * Length-prefixed frames over UART between the host (droid-safety-gateway) and the
 * independent safety microcontroller. Deliberately tiny and auditable.
 *
 *   frame: [SYNC=0xD1][TYPE][LEN][PAYLOAD...][CRC8]
 */
#ifndef DROIDOS_SAFETY_PROTOCOL_H
#define DROIDOS_SAFETY_PROTOCOL_H

#include <stdint.h>

#define DROIDOS_SYNC 0xD1u

/* Host -> controller */
#define MSG_HEARTBEAT     0x01u  /* proves the host is alive; pets the watchdog */
#define MSG_ENABLE_POWER  0x02u  /* request the contactor close (may be refused) */
#define MSG_DISABLE_POWER 0x03u  /* request the contactor open */
#define MSG_CLEAR_FAULT   0x04u  /* clear a non-latching fault after recovery */
#define MSG_REPORT_FAULT  0x05u  /* host-detected fault; payload = fault code */

/* Controller -> host */
#define MSG_STATE         0x80u  /* periodic status (see safety_state_flags) */

/* Fault codes (bit flags in the STATE payload). */
#define FAULT_ESTOP       0x01u
#define FAULT_OVERTEMP    0x02u
#define FAULT_JOINT_LIMIT 0x04u
#define FAULT_WATCHDOG    0x08u
#define FAULT_HOST_SILENT 0x10u

/* STATE payload flags. */
#define STATE_ALIVE       0x01u
#define STATE_POWER_ON    0x02u
#define STATE_WATCHDOG_OK 0x04u

uint8_t crc8(const uint8_t *data, uint16_t len);

#endif /* DROIDOS_SAFETY_PROTOCOL_H */
