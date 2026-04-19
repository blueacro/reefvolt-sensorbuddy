# PlugControl — Heater Relay Carrier Board

## Overview

Two-channel AC plug controller with hardware safety interlock for aquarium
heater control. Receives commands from SensorBuddy over CAN bus. Each channel
has two stages of switching (SSR for control, relay for backup cutoff) plus
per-channel current monitoring. An independent analog safety chain using its
own NTC thermistor can kill all outputs regardless of MCU or CAN state.

Designed to be paired with SensorBuddy, which owns the sensor array
(DS18B20, NTC, pH/ORP) and runs the control loop. PlugControl is pure
actuation + hardware safety — it does not make heating decisions, it only
executes them and enforces hardware limits.

## Safety Architecture

Three independent kill paths, using diverse technologies:

1. **SSR gate (per-channel)** — MCU command AND'd with SAFETY_OK and WDT_OK.
   Triac-based, can fail shorted. This is the normal control path.
2. **Master relay (shared)** — Mechanical contactor upstream of both SSRs.
   Driven by SAFETY_OK AND WDT_OK. Different technology from SSRs, so a
   welded SSR doesn't bypass the kill chain.
3. **Thermal fuse (per-heater, external)** — One-shot, bonded to heater
   element body. Last resort if all electronics fail. Not on this PCB.

```
  AC IN ──── Master Relay ──┬── SSR_A ──── CH_A OUT (plug)
             (normally off) │
                            └── SSR_B ──── CH_B OUT (plug)

  Master Relay coil ← AND(SAFETY_OK, WDT_OK)
  SSR_A gate         ← AND(SAFETY_OK, WDT_OK, MCU_CMD_A)
  SSR_B gate         ← AND(SAFETY_OK, WDT_OK, MCU_CMD_B)
```

**Default state at power-on: everything OFF.** The SR latch powers up in
fault state (POR pulse), the watchdog starts tripped, and SSR gates have
pull-downs. No heater can turn on until the MCU explicitly clears the
safety latch (only possible when temperature is safe) and CAN heartbeat
is established.

---

## Block Diagram

```
                         ┌──────────────────────────────────────────────┐
                         │              PlugControl PCB                 │
                         │                                              │
                         │  ┌─────────────────────────────────────┐     │
                         │  │ Analog Safety Chain (no MCU needed) │     │
  NTC (SS316, own) ──────┤  │                                     │     │
                         │  │ REF3330 (3.0V) ─┬─ NTC ─┬─ R_FIX   │     │
                         │  │                 │       │           │     │
                         │  │          TLV3202a ──────┤ FAULT_HOT │     │
                         │  │          TLV3202b ──────┤ FAULT_OPEN│     │
                         │  │                         │           │     │
                         │  │              OR ── 74HC74 (SR latch)│     │
                         │  │              │    POR → fault state  │     │
                         │  │         SAFETY_OK                   │     │
                         │  └──────────┬──────────────────────────┘     │
                         │             │                                │
                         │  ┌──────────▼──────────────────────────┐     │
                         │  │ Gating Logic (74HC08 quad AND)      │     │
                         │  │                                     │     │
  CAN bus ───────────────┤  │  SAFETY_OK ──┬── AND ── Master Relay│     │
  (from SensorBuddy)     │  │  WDT_OK    ──┤                      │     │
                         │  │              ├── AND ── MCU_A → SSR_A│    │
                         │  │              └── AND ── MCU_B → SSR_B│    │
                         │  └─────────────────────────────────────┘     │
                         │                                              │
                         │  ┌─────────────────────────────────────┐     │
                         │  │ STM32G0B1 (FDCAN)                   │     │
                         │  │ ├─ CAN RX: heartbeat, commands      │     │
                         │  │ ├─ CAN TX: status, current, faults  │     │
                         │  │ ├─ GPIO: MCU_CMD_A, MCU_CMD_B       │     │
                         │  │ ├─ GPIO: safety latch clear         │     │
                         │  │ ├─ ADC: NTC (diagnostic readback)   │     │
                         │  │ ├─ ADC: current sense CH_A, CH_B    │     │
                         │  │ ├─ GPIO: WDT heartbeat out          │     │
                         │  │ └─ ADC: SAFETY_OK readback          │     │
                         │  └─────────────────────────────────────┘     │
                         │                                              │
  AC IN ─────────────────┤── Master Relay ──┬── SSR_A ── CH_A OUT ──────┤
                         │                  │    │                      │
                         │                  │  Shunt+INA181 → ADC      │
                         │                  │                          │
                         │                  └── SSR_B ── CH_B OUT ──────┤
                         │                       │                      │
                         │                     Shunt+INA181 → ADC      │
                         └──────────────────────────────────────────────┘
```

---

## Analog Safety Chain

Operates independently of the MCU. If the MCU crashes, CAN dies, or
firmware has a bug, this chain still kills the heaters at the hardware
trip point.

### NTC Sensor

- **Own sensor, not shared with SensorBuddy.** Different physical probe,
  different measurement path. Provides sensor diversity.
- 10kΩ NTC, B=3988, ±1% R25 and B tolerance, glass-encapsulated bead
  in SS316L thermowell with silicone cable
- Divider: VREF(3.0V) — NTC — V_SENSE — R_FIX(10k 0.1% 25ppm/°C) — GND

### Comparator Window (TLV3202, dual)

Two comparators detect over-temperature and open-sensor:

| Condition | V_SENSE | Comparator | Action |
|-----------|---------|------------|--------|
| Cold/OK (32°F) | 0.69V | — | Safe |
| Setpoint (78°F) | 1.52V | — | Safe |
| **Over-temp (82°F)** | **1.63V** | **TLV3202a trips** | **FAULT_HOT** |
| Very hot (120°F) | 2.18V | TLV3202a tripped | Latched |
| **Open sensor** | **0.00V** | **TLV3202b trips** | **FAULT_OPEN** |
| Shorted sensor | 3.00V | TLV3202a tripped | Latched |

### SR Latch (½ 74HC74)

- D tied high, async preset/clear used as set/reset
- POR pulse (RC, ~10ms) forces latch INTO fault state at power-on
- MCU clear line is gated: can only clear when V_SENSE < V_RESET_OK
  (MCU cannot override a genuine over-temp condition)
- Once tripped, stays tripped until explicit MCU clear + safe temperature

### Threshold Resistors

Fixed resistor divider from REF3330. No DAC, no EEPROM, cannot be
misprogrammed. Trip point set by 0.1% resistors at assembly time.

---

## Actuation

### Per-Channel SSR (x2)

- Panasonic AQH series or Sharp S216 (Omron G3MB-202P is obsolete)
- Triac-based, zero-cross switching, photo-isolated
- 2A @ 240VAC rating (heaters draw ~0.6A @ 120VAC for 75W)
- 5V DC control input
- Gate driven by AND(SAFETY_OK, WDT_OK, MCU_CMD_x) via 74HC08

### Master Relay (x1)

- Omron G5LE-14-DC5 or equivalent (10A SPDT, 5V coil, mechanical)
- **Different technology from SSRs** — a welded SSR contact cannot
  bypass the mechanical relay
- Upstream of both SSRs — interrupts AC to both channels
- Coil driven by AND(SAFETY_OK, WDT_OK) via AO3400 NFET
- Freewheeling diode across coil (SS14 or 1N4148)

### Current Sensing (x2)

- Low-side shunt resistor: 10-50mΩ, 1W (per channel)
- INA181A1IDBVR current-sense amplifier (SOT-23-6, gain=20)
- Output to STM32 ADC
- Firmware checks every control loop iteration:
  - Current flowing when MCU_CMD is OFF → **welded relay detected** →
    drop master, latch fault, refuse to re-enable
  - No current when MCU_CMD is ON → **open heater or blown fuse** →
    log fault, report via CAN

---

## Watchdog

- **TPS3823-33DBVR** (SOT-23-5)
- STM32 toggles heartbeat pin at ≥10Hz
- If heartbeat stops (MCU crash, firmware hang): WDO goes low within ~1.6s
- WDO feeds into AND tree as WDT_OK
- **Powered from independent rail** — if MCU's LDO browns out, watchdog
  must still function and trip the safety chain
- The watchdog monitors the local MCU only. The CAN heartbeat from
  SensorBuddy is monitored by firmware — if SensorBuddy stops sending
  heartbeats, firmware stops pulsing the watchdog → hardware trip.

---

## MCU: STM32G0B1 (UFQFPN-32 or smaller)

Same MCU family as SensorBuddy for firmware commonality. Could potentially
use a smaller variant (STM32G031) since this board has fewer peripherals,
but FDCAN requires the G0B1 line.

### Firmware Responsibilities

- Receive CAN messages from SensorBuddy: heartbeat, heater enable/disable
- Assert/deassert MCU_CMD_A, MCU_CMD_B GPIO outputs
- Pulse watchdog heartbeat (stops if CAN heartbeat from SensorBuddy lost)
- Read current-sense ADC: detect welded relays, open heaters
- Read NTC ADC: diagnostic cross-check (not safety-critical, that's the
  analog chain's job)
- Read SAFETY_OK latch state
- Clear safety latch (only when temperature is safe)
- Report status on CAN: channel state, current readings, fault flags,
  NTC temperature, safety latch state

### Pin Budget (preliminary)

| Function | Pins | Notes |
|----------|------|-------|
| FDCAN TX/RX | 2 | PB8/PB9 (AF3) |
| MCU_CMD_A | 1 | GPIO out → AND gate |
| MCU_CMD_B | 1 | GPIO out → AND gate |
| WDT heartbeat | 1 | GPIO out → TPS3823 WDI |
| Safety latch clear | 1 | GPIO out → 74HC74 CLR (gated) |
| SAFETY_OK readback | 1 | GPIO in ← latch Q output |
| ADC: NTC sense | 1 | Diagnostic readback of V_SENSE |
| ADC: current CH_A | 1 | ← INA181 output |
| ADC: current CH_B | 1 | ← INA181 output |
| Status LED | 1 | GPIO out |
| SWD | 2 | SWDIO + SWCLK |
| BOOT0 | 1 | For programming (test pad or CAN bootloader) |
| NRST | 1 | Reset |
| VDD, VSS | 2 | Power |
| **Total** | **~17** | **11+ spare on UFQFPN-32** |

Spare pins available for: relay state readback, fault LED, buzzer,
additional current channels, I2C expansion.

---

## Power Supply

- **Input:** 12-24V DC from shared ReefVolt power bus (Phoenix COMBICON)
- **5V rail:** For relay coil, SSR gate drive, watchdog
  - TPS54202DDCR or TPS70950DBVT (depending on current draw)
  - Master relay coil draws ~80mA (G5LE-14-DC5), SSR gates ~10mA each
  - Total 5V load: ~100-150mA
- **3.3V rail:** For STM32, analog safety chain (comparators, latch, reference)
  - LDO from 5V rail
- **Safety chain power:** REF3330 and TLV3202 powered from 3.3V rail.
  Consider separate LDO for safety chain so MCU brownout doesn't affect it.
- **AC power:** Passes through the board (in → master relay → SSRs → out).
  Not converted or regulated. Board layout must maintain creepage/clearance
  for mains voltage.

---

## Connectors

| Connector | Type | Qty | Purpose |
|-----------|------|-----|---------|
| CAN bus | Micro-Fit 3.0 6-pos | 1 | To SensorBuddy |
| DC power in | Phoenix COMBICON 2-pos | 1 | 12-24V from shared bus |
| NTC sensor | Phoenix COMBICON 2-pos | 1 | Safety thermistor probe |
| AC input | IEC or screw terminal | 1 | Mains power in |
| AC output CH_A | IEC or screw terminal | 1 | Heater A plug |
| AC output CH_B | IEC or screw terminal | 1 | Heater B plug |

AC connectors TBD — depends on enclosure and regional plug standards.
Screw terminals rated ≥10A for mains. Consider panel-mount IEC C14 inlet
+ C13 outlets for universal compatibility.

---

## Layout Notes

- **Creepage/clearance:** Maintain ≥6mm between mains AC traces and
  low-voltage control circuitry. Use routed slots in PCB if board size
  is tight. Follow IPC-2221B for reinforced insulation at working voltage.
- **Ground topology:** Star-ground the safety chain (REF3330, comparators,
  latch, threshold dividers) with single tie to main ground. Relay coil
  switching transients must not bounce comparator references.
- **Current sense shunts:** Place on low side (between SSR output and
  neutral return). Keep Kelvin sense traces short to INA181 inputs.
- **Relay placement:** Master relay near AC input. SSRs near their
  respective output connectors. Keep high-current AC paths short and wide.
- **Thermal:** SSRs may need copper pour for heat dissipation at full load.
  At 0.6A typical, self-heating is minimal (<0.5W per SSR).

---

## CAN Protocol

### Messages received (from SensorBuddy)

| ID | Name | Payload | Rate |
|----|------|---------|------|
| 0x100 | Heartbeat | sequence counter, SensorBuddy status | 10 Hz |
| 0x110 | Heater command | CH_A enable, CH_B enable, setpoint | On change |
| 0x120 | Safety clear | Clear latch request (only if temp safe) | On demand |

### Messages sent (to SensorBuddy)

| ID | Name | Payload | Rate |
|----|------|---------|------|
| 0x200 | Status | CH_A/B state, latch state, WDT state | 2 Hz |
| 0x210 | Current | CH_A mA, CH_B mA | 1 Hz |
| 0x220 | NTC temp | Local NTC reading (°C × 100) | 1 Hz |
| 0x230 | Fault | Fault code, channel, timestamp | On event |

### Fault codes

| Code | Meaning | Action |
|------|---------|--------|
| 0x01 | Over-temperature (analog chain tripped) | Master relay drops |
| 0x02 | Open NTC sensor (analog chain tripped) | Master relay drops |
| 0x03 | CAN heartbeat lost | WDT trips → master relay drops |
| 0x04 | Welded relay (current when off) | Firmware drops master, latches |
| 0x05 | Open heater (no current when on) | Log + report, no safety action |
| 0x06 | MCU watchdog timeout | Hardware WDT trips → master drops |

---

## Open Questions

1. **STM32 variant:** G0B1KBU6 (UFQFPN-32, same as SensorBuddy) or smaller
   G0B1KBN6 (UFQFPN-28)? Pin count is generous either way.
2. **SSR part number:** Panasonic AQH vs Sharp S216 vs other? Need to check
   JLCPCB/LCSC availability.
3. **AC connectors:** Screw terminal vs IEC C14/C13 vs panel-mount?
   Drives enclosure design.
4. **Current sense shunt value:** 10mΩ (lower insertion loss) vs 50mΩ
   (bigger signal, easier ADC)? At 0.6A typical: 50mΩ × 0.6A × 20 gain
   = 600mV — good ADC signal. 10mΩ × 0.6A × 20 = 120mV — marginal.
   Leaning toward 50mΩ.
5. **CAN bootloader:** Can the STM32G0B1 ROM bootloader work over FDCAN?
   If yes, SensorBuddy could flash PlugControl firmware over the CAN bus
   (no UART/SWD needed after initial programming).
6. **Trip point configurability:** Fixed resistor divider only (recommended),
   or add MCP4728 DAC option for field-adjustable trip points?
7. **Number of channels:** 2 is the current plan (dual-heater redundancy).
   Could expand to 4 for chiller + heater setups, but adds complexity.
8. **Enclosure rating:** IP44 or higher for splash resistance near aquarium?

---

## Schematic Sheet Plan

| Sheet | Contents |
|-------|----------|
| plugcontrol.kicad_sch | Top-level: STM32, CAN, power, connectors |
| safety.kicad_sch | Analog safety chain: NTC, REF3330, comparators, latch |
| actuation.kicad_sch | SSRs, master relay, current sensing, gating logic |

---

## Parts List (preliminary)

### Active — Safety Chain

| Part | MPN | Package | Qty | Purpose |
|------|-----|---------|-----|---------|
| Voltage reference | REF3330AIDBZT | SOT-23-3 | 1 | 3.0V precision ref for NTC divider |
| Dual comparator | TLV3202IDR | SOIC-8 | 1 | Over-temp + open-sensor detection |
| D flip-flop | SN74HC74DR | SOIC-14 | 1 | SR latch (½ used), POR to fault |
| Quad AND gate | SN74HC08DR | SOIC-14 | 1 | Enable gating tree |
| Watchdog | TPS3823-33DBVR | SOT-23-5 | 1 | MCU heartbeat monitor |

### Active — Actuation

| Part | MPN | Package | Qty | Purpose |
|------|-----|---------|-----|---------|
| SSR | TBD (Panasonic AQH) | SIP/SMD | 2 | Per-channel heater switching |
| Master relay | G5LE-14-DC5 | THT | 1 | Mechanical backup cutoff (10A SPDT) |
| Current sense amp | INA181A1IDBVR | SOT-23-6 | 2 | Per-channel current monitoring |
| Relay driver FET | AO3400A | SOT-23 | 1 | Master relay coil driver |

### Active — MCU + CAN

| Part | MPN | Package | Qty | Purpose |
|------|-----|---------|-----|---------|
| MCU | STM32G0B1KBU6N | UFQFPN-32 | 1 | CAN gateway + control logic |
| CAN transceiver | TCAN1044VDRQ1 | SOIC-8 | 1 | CAN bus physical layer |

### Active — Power

| Part | MPN | Package | Qty | Purpose |
|------|-----|---------|-----|---------|
| Buck converter | TPS54202DDCR | SOT-23-6 | 1 | 12-24V → 5V |
| LDO 3.3V (MCU) | TBD | SOT-23 | 1 | 5V → 3.3V for MCU |
| LDO 3.3V (safety) | TBD | SOT-23 | 1 | Independent 3.3V for safety chain |

### Passives (key)

| Part | Value | Package | Qty | Purpose |
|------|-------|---------|-----|---------|
| NTC fixed resistor | 10kΩ 0.1% 25ppm | 0603 | 1 | Divider bottom leg |
| Threshold resistors | TBD (0.1% 25ppm) | 0603 | 2-4 | Comparator trip points |
| Current shunt | 50mΩ 1% 1W | 2512 | 2 | Per-channel current sense |
| CAN termination | 120Ω | 1210 | 1 | Jumper-selectable |
| Relay flyback diode | SS14 | SMA | 1 | Master relay coil protection |
