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

**Decision:** ADM3260 + OPA2376 buffer + ADS1115 differential for
galvanic isolation. Architecture proven in the reefpi-pico pH module
(see `reference/reefpi_pico_ph.svg` for that design's schematic).

#### Isolation

- **ADM3260ARSZ** (20-SSOP, LCSC C208558): Bidirectional I2C isolator
  with integrated isoPower DC/DC (150mW at 3.3V). Eliminates discrete
  isolated DC/DC. ~$5.30.
- All components downstream of the ADM3260 live on ISO_VDD / ISO_GND.
  The only connection crossing the barrier is I2C (digital, isolated).

#### Probe Buffer Amplifier

- **OPA2376AIDR** (dual, SOIC-8, LCSC C46316, stock ~7528): CMOS
  rail-to-rail opamp, 10pA max input bias, 25µV max offset, 5.5MHz GBW,
  0.76mA/channel, 2.2–5.5V. ~$2.50.
- Configured as **unity-gain voltage followers** — one per probe channel.
  Buffers the high-impedance probe signal (~100MΩ for pH, lower for ORP)
  so the ADS1115 sees a low-impedance source.
- At 100MΩ probe impedance, 10pA worst-case bias = 1µV error
  (negligible vs 59mV/pH Nernst slope).
- 220Ω series resistor + 100pF cap on output for stability (per
  reefpi-pico design).
- Powered from ISO_VDD (3.3V from ADM3260 isoPower).
- Quiescent: 1.52mA total → 5mW on ISO_VDD. Well within ADM3260's
  150mW isoPower budget (~1.3mA other loads).

Alternative considered: **MAX9638** (dual version of OPA2376, TDFN-10,
LCSC C2060285, stock ~2620) — 0.1pA typ bias, 36µA/ch quiescent, 1.5MHz
GBW. Lower power and bias, but lower bandwidth, harder-to-solder package,
and lower stock. The OPA2376 is a **single** opamp (not dual) — would
need two. OPA2376 chosen for better availability, SOIC-8 solderability,
and adequate specs for this application.

#### ADC

- **ADS1115IDGST** (10-VSSOP, LCSC C468683): 16-bit delta-sigma ADC,
  2 differential channels. I2C address 0x48 (ADDR → GND).
- pH probe: PGA gain=8 (±0.512V FS), 0.015mV/count → sub-0.01 pH
  resolution, limited by probe accuracy not ADC.
- ORP probe: PGA gain=1 (±4.096V FS), 0.125mV/count — covers full
  ORP range (±2V) with margin.
- Powered from ISO_VDD.

#### Bias Voltage

pH/ORP probes output a voltage centered around 0V (differential). To
keep the signal within the ADS1115's common-mode input range on ISO_VDD
(must be between ISO_GND−0.3V and ISO_VDD+0.3V):

- Apply a **mid-rail bias** of ISO_VDD/2 (~1.65V) to the reference
  electrode side (ADS1115 AINn) via a precision resistor divider.
- Probe signal goes through the OPA2376 buffer to ADS1115 AINp.
- Differential reading = V_probe, centered at 0, independent of bias.
- Bias divider: 2x 100kΩ 0.1% from ISO_VDD, decoupled with 0.1µF.

#### Probe Connectors

- 2x BNC vertical (panel-mount or PCB-mount), on the isolated ground
  domain. Center pin = glass/sensing electrode, shield = reference.
- Both channels are generic — pH vs ORP assigned in firmware.

**Total isolated probe BOM:** ADM3260 ($5.30) + OPA2376 ($2.50) +
ADS1115 ($3) + passives (~$0.50) ≈ **$11.30** for two isolated
differential probe channels.

### Power Supply

```
  12-24V DC ─┬─ TPS54202DDCR ──── 5V rail
   (barrel   │   (sync buck,       │
    jack or  │    4.7µH, 2A)       ├── TCAN1044V (CAN xcvr, ~70mA)
    Phoenix) │                     ├── OLED carrier (if 5V variant)
             │                     │
             │                     └── LM1117IMP-3.3 ──── 3.3V rail
             │                          (LDO, 800mA,       │
             │                           SOT-223)           ├── ESP32-S3-MINI (~300mA peak WiFi TX)
             │                                              ├── STM32G0B1 (~20mA)
             │                                              ├── ADM3260 VDD1 (~10mA)
             │                                              ├── NTC pull-ups, LEDs, etc.
             │                                              │
             │                     ADM3260 isoPower ──── ISO_3V3 (isolated)
             │                      (150mW from 3.3V)       │
             │                                              ├── ADS1115 (~0.7mA)
             │                                              ├── OPA2376 (~0.5mA)
             │                                              └── Bias divider (~0.03mA)
             │
             └── Reverse polarity protection (SS14 or P-FET)
```

#### Buck: TPS54202DDCR (12-24V → 5V)

- 4.5-28V input, 2A synchronous buck (SOT-23-6, LCSC stock 25220)
- External components (per OsmoBuddy proven design):
  - L: 4.7µH shielded inductor (SRN4018-4R7M)
  - C_in: 4.7µF 50V X7R 1210 + 0.1µF 50V 0603
  - C_out: 22µF 25V X7R 1210 + 0.1µF 0603
  - C_boot: 0.1µF 0603
  - R_FB: 100kΩ / 22.1kΩ divider (5.53V → 5.0V with 1.224V ref)
  - EN: tied to VIN through 100kΩ (always on)

#### LDO: LM1117IMP-3.3 (5V → 3.3V)

- 800mA, SOT-223 (LCSC stock 35646)
- Dropout ~1.2V at full load → ok at 5V in, 3.3V out
- C_in: 0.1µF, C_out: 22µF (tantalum or MLCC, ESR matters for stability)
- Thermal: worst case (5V−3.3V) × 0.5A = 0.85W → warm in SOT-223 but fine
  with copper pour. ESP32 peak TX current is brief (~10ms bursts).

#### Isolated Power: ADM3260 isoPower

- Integrated in the ADM3260, no external DC/DC needed
- 150mW at 3.3V output = ~45mA max
- Actual load: ADS1115 (0.7mA) + OPA2376 (0.5mA) + bias divider (0.03mA)
  = **~1.3mA** — well within budget
- External caps: 0.1µF + 10µF on ISO_VDD per datasheet

#### Input Protection

- **Reverse polarity:** SS14 Schottky in series (simple, ~0.4V drop) or
  P-FET reverse protection (lower drop, more parts). SS14 matches existing
  ReefVolt designs.
- **Overvoltage:** TVS diode (SMBJ28A or similar, 28V standoff) across input
- **Bulk cap:** 56µF 63V aluminum electrolytic (same as DCBuddy/OsmoBuddy)

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

```
  3.3V ──── R_fixed (10kΩ 0.1% 25ppm) ──┬── STM32 ADC input
                                          │
                                     NTC (10kΩ)
                                          │
                                        GND
```

- Connected to STM32G0B1 internal 12-bit ADC (3 channels: PA0, PA1, PA4)
- Voltage divider: 3.3V — R_fixed (top) — ADC — NTC (bottom) — GND
  - NTC on bottom leg so open-circuit reads 0V (detectable as fault)
  - 10kΩ / 10kΩ at 25°C gives ~1.65V mid-scale
- R_fixed: 10kΩ 0.1% 25ppm/°C (Vishay CRCW series or similar)
- 0.1µF cap from ADC pin to GND for noise filtering
  (RC time constant with 10k||10k = 5kΩ × 100nF = 500µs — fine for
  slow temperature sampling at ~1Hz)
- 12-bit ADC at 3.3V: 0.806mV/count. At 25°C (half-scale), sensitivity
  is ~18mV/°F → ~22 counts/°F → **~0.045°F resolution**
- NTC spec options:
  - **Standard:** 10kΩ B3435 ±1% epoxy-coated bead, ring terminals
    (cheap, good for ambient/sump)
  - **Heater-grade:** 10kΩ B3988 ±1% glass-encap in SS316L thermowell
    with silicone cable (for submersed/heater cross-check use)
- Connectors: Phoenix COMBICON 2-pos (1803277) per channel — 3 headers

### 1-Wire / DS18B20 (x2 buses)

```
  3.3V ──── 4.7kΩ ──┬── DQ ──── Phoenix 3-pos (VDD/DQ/GND)
                     │                │
               STM32 USART TX    100Ω series
               (half-duplex)         │
                                  100pF to GND
                                (damper for >1m cables)
```

- 2 independent buses on STM32G0B1 USART2 (PA2) and USART3 (PA3)
- Each USART in half-duplex open-drain mode (standard 1-Wire over UART):
  - 9600 baud for reset/presence pulse
  - 115200 baud for bit read/write
  - Single-pin TX/RX on open-drain pad
- 4.7kΩ pull-up per bus from DQ to 3.3V
- 100Ω series + 100pF to GND on MCU side for cable runs >1m
- TVS diode (PESD5V0S1BA or similar) on DQ for ESD/surge protection
- 3-wire powered mode (VDD + DQ + GND) — no parasitic power
- Connectors: Phoenix COMBICON 3-pos (1803280) per bus — 2 headers
- DS18B20 probe form factor: waterproof SS316 tube, silicone cable
- **Firmware:** LwOW library (MIT, github.com/MaJerle/onewire-uart) —
  UART-based 1-Wire with ROM search, CRC-8, DS18B20 driver included.
  One LwOW instance per bus, thin HAL driver maps to STM32 USART
  half-duplex. Boot-time ROM scan enumerates sensors, then 1 Hz
  conversion cycles.

### Float Switches (x4)

```
  3.3V (internal pull-up) ──── STM32 GPIO ──── Phoenix 2-pos ──── switch ──── GND
                                   │
                                 100nF (debounce cap)
```

- Connected to STM32G0B1 GPIO with internal pull-ups (PA5, PA6, PA7, PB0)
- 100nF cap from GPIO to GND for hardware debounce (~1ms RC with 33kΩ pull-up)
- Software debounce via timer interrupt (50ms window, majority-vote)
- NO or NC — firmware-configurable polarity per channel
- Typical assignment: ATO reservoir low, sump high, sump low, leak detect
- Connectors: Phoenix COMBICON 2-pos (1803277) per switch — 4 headers
- ESD protection: internal STM32 clamping diodes sufficient for
  short cable runs; add TVS if cables >2m

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

## Parts List

### Active Components

| Part | MPN | Package | Qty | Purpose | LCSC |
|------|-----|---------|-----|---------|------|
| ESP32-S3-MINI-1-N8 | ESP32-S3-MINI-1-N8 | Module | 1 | WiFi/BLE MCU, OLED, USB | stock 5071 |
| STM32G0B1KBU6 | STM32G0B1KBU6N | UFQFPN-32 | 1 | Sensor MCU + FDCAN | stock 2631 |
| TCAN1044VDRQ1 | TCAN1044VDRQ1 | SOIC-8 | 1 | CAN transceiver | stock 4328 |
| ADM3260ARSZ | ADM3260ARSZ-RL7 | SSOP-20 | 1 | I2C isolator + isoPower | C208558, stock 467 |
| OPA2376AIDR | OPA2376AIDR | SOIC-8 | 1 | Dual probe buffer (isolated) | C46316, stock 7528 |
| ADS1115IDGST | ADS1115IDGST | VSSOP-10 | 1 | 16-bit diff ADC (isolated) | C468683, stock 220 |
| TPS54202DDCR | TPS54202DDCR | SOT-23-6 | 1 | Buck 12-24V → 5V | stock 25220 |
| LM1117IMP-3.3 | LM1117IMPX-3.3/NOPB | SOT-223 | 1 | LDO 5V → 3.3V (800mA) | stock 35646 |
| USBLC6-4SC6 | USBLC6-4SC6 | SOT-23-6 | 1 | USB ESD protection | — |

### Connectors

| Part | MPN | Qty | Purpose |
|------|-----|-----|---------|
| BNC vertical | TBD | 2 | pH / ORP probes (isolated side) |
| USB-C 16-pin | 10155435-00011LF | 1 | Programming + power (ESP32 native USB) |
| Micro-Fit 3.0 6-pos | 43045-0601 | 1 | CAN bus |
| Phoenix COMBICON 2-pos | 1803277 | 8 | NTC (x3), float (x4), power in |
| Phoenix COMBICON 3-pos | 1803280 | 2 | 1-Wire buses (VDD/DQ/GND) |
| OLED carrier header | 0901471104 | 1 | Display (4-pin, 2.54mm) |
| Barrel jack | PJ-0XX | 1 | DC power input |

### Power Passives

| Part | Value | Package | Qty | Purpose |
|------|-------|---------|-----|---------|
| Inductor | 4.7µH shielded | SRN4018 | 1 | TPS54202 buck |
| Bulk cap | 56µF 63V alum. | 10mm SMD | 1 | Input bulk (FKG series) |
| Input cap | 4.7µF 50V X7R | 1210 | 1 | TPS54202 input |
| Output cap | 22µF 25V X7R | 1210 | 1 | TPS54202 output |
| LDO output | 22µF 25V X7R | 1210 | 1 | LM1117 output |
| Boot cap | 0.1µF 50V X7R | 0603 | 1 | TPS54202 bootstrap |
| Decoupling | 0.1µF 50V X7R | 0603 | ~12 | IC decoupling (throughout) |
| Decoupling | 4.7µF 50V X7R | 1210 | 2 | VDD bulk (ESP32, STM32) |
| ISO decoupling | 0.1µF + 10µF | 0603/0805 | 2 | ADM3260 ISO_VDD |
| FB divider top | 100kΩ 1% | 0603 | 1 | TPS54202 feedback |
| FB divider bot | 22.1kΩ 0.1% | 0603 | 1 | TPS54202 feedback |
| Schottky | SS14 | SMA | 1 | Reverse polarity protection |

### Sensor Passives

| Part | Value | Package | Qty | Purpose |
|------|-------|---------|-----|---------|
| NTC fixed R | 10kΩ 0.1% 25ppm | 0603 | 3 | NTC divider top leg |
| NTC filter | 0.1µF 50V X7R | 0603 | 3 | ADC input filter |
| 1-Wire pullup | 4.7kΩ | 0603 | 2 | DQ bus pull-up |
| 1-Wire damper R | 100Ω | 0603 | 2 | Series damper for long cables |
| 1-Wire damper C | 100pF | 0603 | 2 | Shunt damper for long cables |
| Float debounce | 100nF | 0603 | 4 | GPIO debounce cap |
| CAN term | 120Ω | 1210 | 1 | CAN bus termination |

### Isolated Probe Passives

| Part | Value | Package | Qty | Purpose |
|------|-------|---------|-----|---------|
| Bias divider | 100kΩ 0.1% | 0603 | 4 | Mid-rail bias (2 per probe) |
| Bias decoupling | 0.1µF | 0603 | 2 | Bias midpoint filter |
| Buffer series R | 220Ω | 0603 | 2 | OPA2376 output stability |
| Buffer output C | 100pF | 0603 | 2 | OPA2376 output filter |
| ADS1115 decoupling | 0.1µF + 4.7µF | 0603 | 2 | ADC power filtering |

### Other Passives

| Part | Value | Package | Qty | Purpose |
|------|-------|---------|-----|---------|
| USB CC resistors | 5.1kΩ | 0402 | 2 | USB-C CC1/CC2 pull-downs |
| ESP32 pull-ups | 10kΩ | 0603 | 2-4 | EN, BOOT, etc. |
| STM32 BOOT0 pull-down | 10kΩ | 0603 | 1 | Default boot from flash |
| Reset cap | 100nF | 0603 | 1 | STM32 NRST filter |
| LED resistors | 1kΩ | 0603 | 2-3 | Status LEDs |
| Status LEDs | red/green | 0603 | 2-3 | Power, status, fault |
| Tactile switch | PTS526SK15SMTR2LFS | SMD | 2 | BOOT + RESET |

---

## Schematic Sheet Plan

| Sheet | Contents |
|-------|----------|
| sensorbuddy.kicad_sch | Top-level: ESP32-S3, STM32, inter-MCU I2C, CAN, USB, display |
| psu.kicad_sch | Power supply: input, buck, LDOs, bulk caps |
| sensors.kicad_sch | Sensor interfaces: isolated probes, NTC, 1-Wire, float switches |

---

## Firmware Dependencies (STM32G0B1)

| Library | License | Purpose | Source |
|---------|---------|---------|--------|
| LwOW v3.x | MIT | 1-Wire over UART: ROM search, CRC-8, DS18B20 driver | github.com/MaJerle/onewire-uart |
| STM32CubeG0 HAL | BSD-3 | Low-level peripheral drivers (USART, ADC, FDCAN, I2C, GPIO) | ST |

Architecture: superloop with timer interrupts (no RTOS). 1 Hz sensor
sampling (NTC ADC + DS18B20 conversion), float switch polling, FDCAN
TX/RX, USART1 gateway to ESP32.
