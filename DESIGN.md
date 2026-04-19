# SensorBuddy Design Document

## Overview

Aquarium sensor interface board with isolated probe inputs, temperature sensing,
float switches, and CAN bus output. Designed for Home Assistant integration via
ESPHome on ESP32-S3, with an STM32G0 coprocessor for real-time sensor sampling.

## Architecture Decisions

### MCU: ESP32-S3-MINI-1-N8

- Replaces ESP32-C3-MINI used in DCBuddy/OsmoBuddy
- ~36 usable GPIOs eliminates need for PCA9554 I/O expander
- Native USB (no UART bridge)
- Proven in tsumikoro bridge and ledbrick projects
- **Not on CAN bus** — communicates with STM32 via USART only.
  STM32 is the sole CAN bus master and relays data to/from ESP32.
- I2C for OLED display
- UART to STM32 (data exchange + bootloader flashing)
- Controls STM32 BOOT0 + NRST for in-system firmware updates

### MCU: STM32G0B1KBU6 (sensor coprocessor)

- UFQFPN-32 package (same as tsumikoro ministepper — footprint already exists)
- 128KB flash, 144KB RAM
- **FDCAN controller** — direct CAN bus access for safety-critical heater
  heartbeat and control, independent of ESP32/WiFi
- 12-bit ADC with multiple external channels for NTC thermistors
- 2x USART for dual 1-Wire buses (half-duplex mode)
- GPIO for float switch inputs with hardware debounce via timers
- I2C peripheral to communicate with ESP32-S3
- USART bootloader — ESP32-S3 can reflash the STM32 in-system
  (ESP32 drives STM32 BOOT0 + NRST, then streams firmware over USART)

### Isolated Probe Domain (pH / ORP)

**Decision:** Use ADM3260 + ADS1115 differential for galvanic isolation.

- **ADM3260ARSZ** (20-SSOP): Bidirectional I2C isolator with integrated
  isoPower DC/DC (150mW output at 3.3V). Eliminates separate isolated
  DC/DC converter. ~$5.30 (LCSC C208558).
- **ADS1115IDGSR** (10-VSSOP): 16-bit delta-sigma ADC, 2 differential
  channels. Reads pH and ORP probes with sub-0.01 pH resolution at
  PGA gain=8 (±0.512V, 0.015mV/count). ~$3.
- **Two BNC connectors** on isolated ground domain. Both channels are
  generic — pH vs ORP assignment is firmware configuration.
- Total isolation BOM: ~$8.30 for two ICs, no discrete DC/DC.

**Why differential:** pH/ORP probes are floating Nernst cells with no
relationship to system ground. Differential rejects common-mode noise
from pumps, heaters, and powerheads sharing the tank water.

**Why not STM32 ADC for pH:** 12-bit over 3.3V gives 0.8mV/count.
Nernst slope is ~59mV/pH at 25°C. That's marginal for 0.01 pH
resolution. The ADS1115 at gain=8 gives 0.015mV/count — limited by
probe accuracy, not ADC.

### Power Supply

- **Input:** 12-24V DC (barrel jack or Phoenix connector, matching other ReefVolt boards)
- **TPS54202DDCR:** Synchronous buck, 4.5-28V in, regulated output (5V or 3.3V TBD)
- **TPS70950DBVT:** 5V LDO (150mA) for sensors, display, probe excitation
- **3.3V rail:** For ESP32-S3 and STM32G031 — either second LDO or buck output directly
- **Isolated 3.3V:** Provided by ADM3260 isoPower (up to 150mW, plenty for ADS1115)

### Display

- 1.3" SH1106 128x64 OLED on carrier board
- Same carrier board footprint as DCBuddy and OsmoBuddy (OLED_1_3_CARRIERBOARD)
- 4-pin header (Molex 0901471104, 2.54mm pitch)
- Need to convert Altium footprint + STEP model to KiCad format
- Driven by ESP32-S3 via I2C

### CAN Bus (STM32-only)

- **TCAN1044VDRQ1** transceiver (same as DCBuddy/OsmoBuddy)
- **STM32G0B1 FDCAN is the sole CAN controller** — no TX sharing issues
- STM32 owns all CAN traffic: heater heartbeat, temperature broadcasts,
  enable/disable commands, status queries to carrier boards
- ESP32 is **not on the CAN bus**. It communicates with the STM32 over
  USART. The STM32 acts as gateway, relaying CAN data to/from WiFi/HA.
- If ESP32 crashes or WiFi is down, STM32 continues CAN autonomously —
  safety heartbeat to heater carrier board is never interrupted by WiFi issues
- Micro-Fit 3.0 connector (matching other ReefVolt boards)
- 120R termination resistor (jumper-selectable TBD)

---

## Sensor Interfaces

### Isolated Probes (pH / ORP)

| Channel | ADS1115 Pair | Connector | Signal |
|---------|-------------|-----------|--------|
| Probe A | AIN0 / AIN1 | BNC | pH or ORP (firmware-assigned) |
| Probe B | AIN2 / AIN3 | BNC | pH or ORP (firmware-assigned) |

- Both probes share the isolated ground domain (ISO_GND)
- pH probe output: ~0 to ±350mV (Nernst, temperature-dependent)
- ORP probe output: ~-2V to +2V (wider range, may need resistive divider or lower PGA gain)
- **TODO:** Decide if ORP range needs input conditioning or if ADS1115 PGA gain=1 (±4.096V) is sufficient
- **TODO:** Input protection (ESD, overvoltage clamping) on BNC inputs

### NTC Thermistors (x3)

- Connected to STM32G0B1 internal 12-bit ADC (3 channels)
- Voltage divider topology: VDD — R_fixed — ADC_pin — NTC — GND
- 10k NTC with 10k fixed resistor (0.1% 25ppm/°C for heater safety use)
- 12-bit ADC gives ~0.1°C resolution in typical aquarium range (20-30°C)
- Intended placement: tank, sump, ambient (or heater cross-check)
- **TODO:** Connector type (2-pin Phoenix? JST PH?)
- **TODO:** NTC spec: 10k B3988 glass-encap in SS316 sheath (per heater
  design doc) or simpler probe for non-heater use

### 1-Wire / DS18B20 (x2 buses)

- 2 independent buses, each on a dedicated STM32G0B1 USART in half-duplex mode
- Each bus supports daisy-chained DS18B20 sensors (unlimited per bus)
- 3-wire connectors: VDD, DQ, GND (avoid parasitic power for reliability)
- 4.7kΩ pullup per bus on DQ line
- Waterproof SS316 probe assemblies with silicone cable (standard aquarium form factor)
- **TODO:** Connector type (3-pin Phoenix COMBICON? JST PH?)
- **TODO:** TVS + 100Ω/100pF damper for long cable runs

### Float Switches (x4)

- Connected to STM32G0B1 GPIO with internal pull-ups
- Software debounce via timer interrupt
- 4 inputs: e.g., ATO reservoir low, sump high, sump low, leak detect
- NO or NC — firmware-configurable polarity per channel
- **TODO:** Connector type (2-pin screw terminal per switch, or shared multi-pin?)

---

## Pin Budget: STM32G0B1KBU6 (UFQFPN-32)

32 pins total. Same package as tsumikoro ministepper — footprint exists.
Pin assignments based on G0B1 datasheet AF mapping. Needs verification.

**Peripherals required:**
- FDCAN (TX + RX) — 2 pins
- USART1 (TX + RX) — 2 pins (to ESP32-S3: data exchange + bootloader)
- USART2 (TX, half-duplex) — 1 pin (1-Wire bus 1)
- USART3 (TX, half-duplex) — 1 pin (1-Wire bus 2)
- I2C1 (SCL + SDA) — 2 pins (to ADM3260 isolated probe ADC)
- ADC (3 channels) — 3 pins (NTC thermistors)
- GPIO (4 inputs) — 4 pins (float switches)
- GPIO (1 output) — 1 pin (status LED)
- GPIO (1 output) — 1 pin (BOOT0, driven by ESP32)
- SWD — 2 pins (SWDIO + SWCLK)
- NRST — 1 pin (driven by ESP32 for bootloader entry)
- VDD, VSS, EP — 3 pins

**Total: ~23 signal pins used of 28 available (4-5 spare)**

| Pin | MCU | Function | AF / Notes |
|-----|-----|----------|------------|
| 1 | PB9 | FDCAN TX | AF3 FDCAN1_TX |
| 2 | PC14 | Spare | |
| 3 | PC15 | Spare | |
| 4 | VDD/VDDA | 3.3V | 100nF + 4.7µF |
| 5 | VSS/VSSA | GND | |
| 6 | PF2/NRST | Reset | 100nF to GND; ESP32 drives for bootloader |
| 7 | PA0 | ADC CH0 | NTC thermistor 1 |
| 8 | PA1 | ADC CH1 | NTC thermistor 2 |
| 9 | PA2 | USART2 TX | AF1, 1-Wire bus 1 (half-duplex) |
| 10 | PA3 | USART3 TX | AF4(?), 1-Wire bus 2 (half-duplex) |
| 11 | PA4 | ADC CH4 | NTC thermistor 3 |
| 12 | PA5 | GPIO in | Float switch 1 |
| 13 | PA6 | GPIO in | Float switch 2 |
| 14 | PA7 | GPIO in | Float switch 3 |
| 15 | PB0 | GPIO in | Float switch 4 |
| 16 | PB1 | GPIO out | Status LED |
| 17 | PB2 | BOOT0 ctrl | ESP32 drives high for bootloader entry |
| 18 | PA8 | USART1 TX | AF1, to ESP32 RX (data + bootloader) |
| 19 | PA9 | USART1 RX | AF1, from ESP32 TX (data + bootloader) |
| 20 | PC6 | Spare | |
| 21 | PA10 | Spare | |
| 22 | PA11 | Spare | |
| 23 | PA12 | Spare | |
| 24 | PA13 | SWDIO | Debug |
| 25 | PA14 | SWCLK | Debug |
| 26 | PA15 | Spare | |
| 27 | PB3 | Spare | |
| 28 | PB4 | Spare | |
| 29 | PB5 | Spare | |
| 30 | PB6 | I2C1 SCL | AF6 (to ADM3260 isolated I2C) |
| 31 | PB7 | I2C1 SDA | AF6 (to ADM3260 isolated I2C) |
| 32 | PB8 | FDCAN RX | AF3 FDCAN1_RX |
| EP | VSS | GND | Exposed pad, via stitching |

**Inter-MCU communication (USART1, PA8/PA9):**
- Normal mode: STM32 ↔ ESP32 bidirectional data (sensor readings,
  CAN relay, commands). Protocol TBD (binary framed or COBS).
- Bootloader mode: ESP32 drives BOOT0 high, pulses NRST low.
  STM32 enters ROM bootloader. ESP32 streams firmware over same UART.
  After flash, ESP32 releases BOOT0 low, pulses NRST → STM32 boots app.
- Single USART handles both roles — no pin sharing conflict.

**CAN bus wiring:**
- STM32 FDCAN TX (PB9) → TCAN1044V TXD
- TCAN1044V RXD → STM32 FDCAN RX (PB8)
- ESP32 is not connected to the CAN transceiver.
- STM32 relays CAN data to ESP32 over USART1.

**Note:** Pin assignments are preliminary. Verify against STM32G0B1
datasheet for AF availability on the UFQFPN-32 package specifically.
The tsumikoro ministepper pin map (CLAUDE.md §Ministepper PCB Pin Map)
is a useful cross-reference for validated AF assignments on this package.
Key difference: ministepper uses PA2/PA3 for RS-485 (USART2), PA11/PA12
for USB — we reuse PA2 for 1-Wire and PA11/PA12 are spare.

---

## Heater Controller Extension (Optional)

SensorBuddy can serve as the sensor/brain for a water heater control system.
The actuation side is the **PlugControl** board (see
`hardware/plugcontrol/DESIGN.md` for full design, and
`water-heater-controller-design.md` for the original failsafe analysis).

### Architecture Split

The heater controller design separates into two boards:

1. **SensorBuddy (this board)** — sensor acquisition + supervisory logic
   - DS18B20 measurement path (1-Wire, median-filtered, 3+ sensors)
   - NTC safety path (independent analog sensor, STM32 ADC)
   - Control loop runs on ESP32-S3 (bang-bang with hysteresis, staged dual-heater)
   - **STM32G0B1 FDCAN** sends heater heartbeat + enable/disable commands
     directly on CAN bus. ESP32 is not on the bus — STM32 is the sole
     CAN master. If ESP32 crashes, STM32 continues autonomously.
   - NTC cross-check: firmware compares NTC reading against DS18B20 median,
     flags fault if disagreement >2°F for >10s

2. **PlugControl board** (`hardware/plugcontrol/`) — actuation + safety interlock
   - STM32G0B1 with FDCAN (receives commands from SensorBuddy over CAN)
   - 2x SSRs (triac, zero-cross) for per-channel heater control
   - Master mechanical relay (different technology, upstream of SSRs)
   - **Own NTC sensor** for hardware-only analog safety chain:
     REF3330 → NTC divider → TLV3202 comparators → 74HC74 SR latch
     (purely hardware, independent of any MCU or CAN)
   - TPS3823 watchdog: MCU pulses heartbeat; stops pulsing if CAN
     heartbeat from SensorBuddy is lost → hardware trip
   - INA181 current-sense per channel for welded-relay detection
   - See `hardware/plugcontrol/DESIGN.md` for full details

### NTC Dual Role

The NTC thermistor inputs on SensorBuddy serve two purposes:
- **Normal mode:** Temperature measurement (tank, sump, etc.)
- **Heater mode:** Safety cross-check against DS18B20 readings. The NTC
  provides an independent measurement technology — no single contamination,
  EMI, or probe failure can blind both the digital and analog paths.

The analog safety comparator chain (REF3330 + TLV3202 + 74HC74 latch)
lives on the heater carrier board, not on SensorBuddy. SensorBuddy reads
the NTC via its own ADC for firmware cross-checks only.

### CAN Protocol for Heater Control

- SensorBuddy sends periodic heartbeat + temperature readings on CAN
- Heater carrier board watchdog expects heartbeat; trips master contactor
  if heartbeat stops (MCU lockup, cable disconnect, CAN failure)
- SensorBuddy sends explicit heater enable/disable commands per channel
- Heater carrier board reports back: SSR state, current readings, fault flags

---

## Resolved Decisions

- **STM32 variant:** STM32G0B1KBU6 (UFQFPN-32) — FDCAN, 128KB flash, proven in tsumikoro
- **NTC channel count:** 3 (tank, sump, ambient/spare)
- **1-Wire port count:** 2 independent buses (2 USART half-duplex)
- **Float switch count:** 4
- **Probe count:** 2 differential (pH + ORP, or 2x pH)
- **CAN architecture:** STM32 FDCAN only, single TCAN1044V. ESP32 not on CAN bus.
  STM32 is sole CAN master, relays to ESP32 over USART.
- **Heater carrier interface:** CAN-only; carrier has its own NTC for hardware failsafe
- **ESP32 flashes STM32:** Via USART bootloader (BOOT0 + NRST + UART)

## Open Questions

1. ~~**Connector types**~~ **RESOLVED:** Phoenix COMBICON pluggable headers (1803277 2-pos, 1803280 3-pos) matching OsmoBuddy. Use for all sensor/switch/power connections.
2. **ORP input conditioning:** Does ORP voltage range (up to ±2V) fit within ADS1115 PGA=1 range (±4.096V)?
3. **CAN termination:** Jumper-selectable 120R or always-on?
4. **Power input connector:** Barrel jack only, or also Phoenix COMBICON (like OsmoBuddy)?
5. **USB-C:** Programming + power input, or programming only?
6. **Enclosure:** Same case style as DCBuddy/OsmoBuddy? Drives board outline and connector placement.
7. **NTC spec:** 10k B3988 glass-encap in SS316 sheath (per heater design doc) or simpler probe?
8. **USART3 AF on PA3:** Verify USART3_TX alternate function is available on PA3
   for the UFQFPN-32 package. If not, may need different pin or use LPUART1.
9. **Inter-MCU USART protocol:** Binary framed, COBS, or protobuf-based?
   Needs to carry sensor data, CAN relay frames, and bootloader traffic.

---

## Parts List (preliminary)

### Active Components

| Part | MPN | Package | Qty | Purpose | LCSC |
|------|-----|---------|-----|---------|------|
| ESP32-S3-MINI-1-N8 | ESP32-S3-MINI-1-N8 | Module | 1 | WiFi/BLE MCU | — |
| STM32G0B1KBU6 | STM32G0B1KBU6N | UFQFPN-32 | 1 | Sensor coprocessor + FDCAN | — |
| TCAN1044VDRQ1 | TCAN1044VDRQ1 | SOIC-8 | 1 | CAN transceiver (shared) | — |
| ADM3260ARSZ | ADM3260ARSZ | SSOP-20 | 1 | I2C isolator + isoPower | C208558 |
| ADS1115IDGSR | ADS1115IDGSR | VSSOP-10 | 1 | 16-bit diff ADC (isolated) | — |
| TPS54202DDCR | TPS54202DDCR | SOT-23-6 | 1 | Buck converter | — |
| TPS70950DBVT | TPS70950DBVT | SOT-23-5 | 1 | 5V LDO | — |
| USBLC6-4SC6 | USBLC6-4SC6 | SOT-23-6 | 1 | USB ESD protection | — |

### Connectors

| Part | MPN | Qty | Purpose |
|------|-----|-----|---------|
| BNC vertical | TBD | 2 | pH / ORP probes (isolated) |
| USB-C 16-pin | 10155435-00011LF | 1 | Programming + power |
| Micro-Fit 3.0 6-pos | 43045-0601 | 1 | CAN bus |
| Phoenix COMBICON 2-pos | 1803277 | ~8 | NTC (x3), float (x4), power in |
| Phoenix COMBICON 3-pos | 1803280 | 2 | 1-Wire buses (VDD/DQ/GND) |
| OLED carrier header | 0901471104 | 1 | Display (4-pin, 2.54mm) |
| Barrel jack | PJ-0XX | 1 | DC power input |

### Passives

Standard ReefVolt passives (0603 resistors, 0603/1210 capacitors).
See DCBuddy/OsmoBuddy BOMs for exact MPN consolidation.

---

## Schematic Sheet Plan

| Sheet | Contents |
|-------|----------|
| sensorbuddy.kicad_sch | Top-level: ESP32-S3, STM32, inter-MCU I2C, CAN, USB, display |
| psu.kicad_sch | Power supply: input, buck, LDOs, bulk caps |
| sensors.kicad_sch | Sensor interfaces: isolated probes, NTC, 1-Wire, float switches |
