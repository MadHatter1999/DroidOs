/* Board HAL for the DroidOS safety controller (spec §24).
 *
 * Implement these for your MCU (STM32/RP2040/AVR). The control loop in main.c is
 * board-independent and depends only on this interface.
 */
#ifndef DROIDOS_SAFETY_HAL_H
#define DROIDOS_SAFETY_HAL_H

#include <stdint.h>
#include <stdbool.h>

void     hal_init(void);
uint32_t hal_millis(void);
void     hal_delay_until_next_tick(uint32_t period_ms);

/* Motor-power contactor: true = closed (power on), false = open (power off). */
void     hal_contactor_set(bool closed);

/* Hardware watchdog: must be petted every loop or the MCU resets. */
void     hal_watchdog_pet(void);

/* Safety inputs. */
bool     hal_estop_asserted(void);       /* physical e-stop button / loop */
int      hal_max_motor_temp_c(void);     /* hottest controller-reported temp */
bool     hal_joint_limit_tripped(void);  /* any hard joint-limit switch */

/* Framed UART to the host (droid-safety-gateway). Returns true if a frame was read. */
bool     hal_uart_read_frame(uint8_t *type, uint8_t *payload, uint8_t *len);
void     hal_uart_send_frame(uint8_t type, const uint8_t *payload, uint8_t len);

#endif /* DROIDOS_SAFETY_HAL_H */
