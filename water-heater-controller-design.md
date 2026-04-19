# Water Heater Controller — Design Document

**Target application:** Maintain water between 76–80 °F using two independent heaters, with an MCU supervisory control loop and an independent analog safety layer. Typical application: aquarium, fermentation vessel, reptile habitat, or similar low-power water-heating duty.

---

## 1. Design goals and constraints

### Functional requirements

- Control water temperature within 76–80 °F (24.4–26.7 °C)
- Measure broader range (~50–120 °F / 10–49 °C) for diagnostics and warmup visibility
- Never heat when water is outside the control band
- Tolerate single-point failures — either heater, either control relay, or the MCU itself may fail without creating a hazard
- Survive sensor disconnection, shorted sensor, MCU lockup, and relay contact welding

### Non-functional requirements

- Cheap and manufacturable on JLCPCB
- Low part count and simple failure surface
- Long-term stability in wet environments (months to years of continuous submersion)
- Control resolution ≤ 0.1 °F, safety trip accuracy ≤ 1 °F

---

## 2. Architecture overview

The design separates three concerns into independent paths:

1. **Measurement path** — digital sensors, read by MCU, drives control loop
2. **Safety path** — purely analog, independent sensor, gates the heater power downstream of the MCU
3. **Actuation path** — redundant heaters with diverse cutoff technologies (triac SSRs per heater, mechanical contactor as master)

Diversity between paths is intentional. The measurement and safety sensors use different technologies (digital IC vs. analog thermistor), so no single contamination, EMI, or probe-housing failure can blind both. The actuation path uses triac SSRs for normal per-heater control and a mechanical contactor as the master cutoff, so a single welded-contact failure mode cannot disable the kill switch.

### Block diagram

```
                ┌───────────────────────────┐
                │      Water vessel         │
                │                           │
   DS18B20 #1 ──┤                           │
   DS18B20 #2 ──┤  (measurement sensors)    │
   DS18B20 #3 ──┤                           │
                │                           │
   NTC (SS316) ─┤  (safety sensor)          │
                │                           │
   Heater A ────┤  ←──┐                     │
   Heater B ────┤  ←──┼── [thermal fuses]   │
                └─────┼─────────────────────┘
                      │
     ┌────────────────┴──────────────┐
     │                               │
   SSR_A ─ Heater A    SSR_B ─ Heater B
     │                               │
     └──────────┬────────────────────┘
                │
        Master contactor ──── AC mains
                ▲
                │
            ┌───┴───┐ AND gate
            │       │
       SAFETY_OK   WDT_OK
            ▲       ▲
            │       │
     Analog chain  Watchdog IC
            ▲       ▲
            │       │
          NTC    MCU heartbeat

    ┌──────────────────────┐
    │       MCU            │
    │                      │
    │  reads DS18B20s (1-Wire)
    │  reads NTC via ADC (diagnostic)
    │  reads SSR currents (sanity)
    │  commands SSR_A, SSR_B (permissive)
    │  pulses WDT heartbeat
    │  I²C to DAC (if used)
    └──────────────────────┘
```

---

## 3. Sizing rationale

### Heater sizing

For a typical indoor vessel (20 L water, 72 °F ambient, modest insulation) the hold-load is ~20–40 W. Each heater is sized at 50–75 W. This gives:

- Either heater alone can hold setpoint under worst-case ambient (redundancy)
- Together they warm up in reasonable time
- Neither is powerful enough to cause a scary runaway even with a stuck relay (water's thermal mass gives firmware and watchdog minutes of response time)

Deliberate undersizing is strictly safer than one big heater of the same total wattage.

### Sensor count

- **Three DS18B20s** for measurement: median filtering rejects single-sensor drift or fault, and placement diversity (near Heater A outflow, near Heater B outflow, in the bulk water) gives stratification visibility.
- **One NTC** for safety: single trip channel is sufficient given the diversity with the measurement path.

### Safety trip threshold

- **Over-temp trip: 82 °F (27.8 °C)** — 2 °F above the control upper bound gives comparator hysteresis and threshold tolerance room without being sloppy.
- **Thermal fuse: ~94 °C (201 °F)** — one-shot, bonded to each heater element body, catches absolute runaway if all electronic safeguards fail.

---

## 4. Measurement path (DS18B20)

### Why DS18B20 over analog RTDs

- 1-Wire bus — arbitrary number of sensors on a single GPIO, $1–3 each
- 12-bit mode gives 0.0625 °C (0.11 °F) resolution, which is finer than the water's thermal time constant permits to matter
- ±0.5 °C absolute accuracy, much better differential stability (~0.05 °C drift over years)
- 64-bit unique ID per sensor — no hardware addressing headaches
- CRC-protected communication rejects bit errors silently

### Sensor form factor

Use waterproof stainless steel probe assemblies with silicone cable — the pre-built kind with the sensor potted in the tip of a ~6 × 50 mm SS316 tube and 1–3 m of silicone lead. Silicone (not PVC) is important for continuous submersion above ~60 °C. Chinese vendors mostly ship SS304 with epoxy potting; spec SS316 for chloride resistance if the water has any salt content.

### Calibration

One-shot calibrate each DS18B20 in an ice-water bath on install, store per-sensor offsets in MCU flash. This brings absolute accuracy to better than ±0.1 °C, limited primarily by the ice-bath methodology.

### Wiring

- 3-wire (VCC, GND, DQ) — avoid parasitic power mode for reliability
- 4.7 kΩ pullup on DQ, shared across all sensors on the bus
- For cables >1 m, add 100 Ω series + 100 pF to ground on the MCU side to tame reflections
- Consider TVS diode to GND on the DQ line if the environment is electrically noisy

---

## 5. Safety path (NTC + comparator)

### Topology

Simple resistive divider from a precision voltage reference, feeding a comparator window, feeding an SR latch:

```
 VREF 3.0V (REF3330)
    │
    ├── R_NTC (10k @ 25°C, B=3988, glass-encap, SS316 sheath)
    │
    V_SENSE ──┬──→ MCU ADC (diagnostic only)
    │         │
    │         ├──→ TLV3202a +          FAULT_HOT ──┐
    │         │              ──────────────────────│
    │         │   V_TH_HOT − │                     │
    │         │   (~1.63V                          │
    │         │    from div)                       OR ──→ ½ 74HC74 ──→ SAFE
    │         │                                    │    (SR latch,
    │         │                                    │     POR-set
    │         └──→ TLV3202b −                      │     to fault state)
    │                        ── FAULT_OPEN ────────┘
    │         V_TH_OPEN +
    │         (~0.30V
    │          from div)
    │
   R_FIX (10k 0.1% 25ppm/°C)
    │
   GND
```

**Two comparators, not one.** An open thermistor reads as 0 V, which a single over-temp comparator interprets as "very cold, keep heating." The open-sensor comparator catches this failure mode. The two outputs are OR'd so either fault latches the safety chain.

### Trip point math

10 kΩ NTC, B=3988, in a 10 kΩ/10 kΩ divider from 3.0 V:

| Temp (°F) | R_NTC | V_SENSE | State |
|-----------|-------|---------|-------|
| 32 | 33.6 kΩ | 0.69 V | cold, OK |
| 78 | 9.76 kΩ | 1.52 V | setpoint, OK |
| 82 | 8.48 kΩ | 1.63 V | **trip threshold** |
| 120 | 3.74 kΩ | 2.18 V | very hot, tripped |
| open | ∞ | 0.00 V | **open-detect threshold (<0.30V)** |
| short | 0 | 3.00 V | very hot, tripped |

Sensitivity near trip is ~18 mV/°F. Comparator hysteresis of ~1–2 mV (via feedback resistors) gives ~0.1 °F of thermal hysteresis. No noise or nuisance-trip issues at this signal level.

### Latch behavior

- SR latch built from half a 74HC74 (D tied high, async preset/clear pins used as set/reset)
- Power-on reset pulse (RC, ~10 ms) forces the latch *into* fault state at startup, so MCU must explicitly clear before heater can ever run
- Clear line from MCU is gated through `(MCU_reset_pulse AND V_SENSE < V_RESET_OK)` — MCU cannot clear a latch while sensor still reads hot
- Once tripped, only an explicit clear pulse (plus safe temperature) re-enables the heater chain

### Threshold options

- **Fixed resistor divider** from REF3330 — cheapest, zero EEPROM failure risk, cannot be misprogrammed. Recommended for a fixed-threshold application.
- **MCP4728 DAC channel** — programmable, writeable from MCU, survives power loss via EEPROM. Use only if field-configurable trip points are actually needed. If used, include a fixed resistor divider in series/parallel so the trip point can never exceed an absolute hardware maximum regardless of DAC code.

---

## 6. Actuation path

### Per-heater SSR (×2)

**Omron G3MB-202P** or equivalent: 2 A @ 240 VAC, 5 V DC control, built-in zero-cross phototriac isolation. Note that G3MB-202P is marked obsolete by Omron — for new designs consider Panasonic AQH series (SMT) or Sharp S216 series as drop-in alternatives.

For a 50–75 W heater at 120 VAC this is ~0.6 A, well within the 2 A rating. At 240 VAC even more margin.

### Master contactor

**Different technology from the SSRs.** Since the per-heater path is a triac-based SSR (can fail shorted), make the master a mechanical relay:

- Omron G5LE-14-DC5 (10 A SPDT, 5 V coil) or similar
- Driven from `SAFETY_OK AND WDT_OK` via an AO3400 MOSFET or TBD62003 driver
- Interrupts the supply to both heaters upstream of the SSRs

This gives three independent disable paths: per-heater SSR gate (via AND with SAFETY_OK), master contactor coil (via same AND), and thermal fuse (mechanical, non-resettable).

### Gating logic

```
  SAFETY_OK ──┐
  WDT_OK    ──┼── AND ── MCU_cmd_1 ── AND ── SSR_1
              │                         
              ├── AND ── MCU_cmd_2 ── AND ── SSR_2
              │
              └── AND ── Master contactor
```

Built from 74HC08 quad AND gates (one IC covers the whole tree).

### Current sensing (per heater)

Low-side shunt (10–50 mΩ) + INA181A1 current-sense amp in SOT-23-6, into MCU ADC. Checked every loop: if current flows when command is off → welded relay → log fault, drop master, refuse to re-enable.

At <3 A heater currents this is cheaper, smaller, and more accurate than ACS712 Hall sensors. Use ACS712 only if isolation between the sense path and mains is needed (usually not, if the shunt is on the low side after the SSR).

### Thermal fuses

One per heater element. 94 °C (or similar, sized to worst-case normal operation plus margin), bonded to the heater body with thermal epoxy. NEC/SEFUSE SF-series or equivalent. One-shot, non-resettable — exactly what you want as the last line.

---

## 7. Watchdog

**TPS3823-33** in SOT-23-5. MCU toggles a heartbeat pin at ≥10 Hz; if the pulse train stops, WDO goes low within ~1.6 s. WDO feeds into the AND tree as `WDT_OK`.

Power the watchdog from a rail that's independent of the MCU's internal regulator — if the MCU browns out, the WDT should still be alive to trip.

---

## 8. Control strategy

### Bang-bang with hysteresis

For a 4 °F control band with water's thermal mass, bang-bang is better than PID:
- Heater A turns on at 77.5 °F
- If temp keeps dropping and hits 76.8 °F, Heater B also comes on (staged response)
- Both off at 78.5 °F

Staged response keeps single-heater operation as the normal case, which means the "one heater is enough" assumption is being implicitly tested constantly. The second heater's activation is itself a useful diagnostic signal.

### Alternation

Rotate which heater is "primary" daily or weekly — equalizes wear on relays and elements, and ensures neither heater goes unused long enough for corrosion or scale to accumulate.

### Periodic redundancy test

Once a day, when temperature is mid-band and stable, deliberately shut off the active heater for 5 minutes and verify the other can hold temp. Rotate which one gets tested. Actively verifies redundancy rather than assuming it.

### Firmware-level safety cross-checks

With three measurement sensors plus one safety sensor read independently through the ADC, firmware has multiple consistency checks available:

- **DS18B20 median filter** — reject any single sensor disagreeing with the median by >1 °F persistently
- **NTC vs. DS18B20 cross-check** — if PT100/NTC-derived temp disagrees with DS18B20 median by >2 °F for >10 s, flag fault and drop enable
- **Heater effectiveness check** — if heater commanded on but median temp falls or flat-lines for >5 min, flag sensor or heater fault
- **Short detection** — NTC reading physically impossible values (<32 °F while heating) flags a sensor short
- **Welded-relay detection** — current flowing when command off → log + latch

These firmware checks handle everything the analog safety chain doesn't need to. Single hardware requirement: "if water gets too hot, the heater dies regardless of what the MCU is doing." Everything else is firmware.

---

## 9. Bill of materials

### Measurement path

| Qty | Part | JLCPCB / LCSC | Notes |
|-----|------|---------------|-------|
| 3 | Waterproof DS18B20 probe, SS316, silicone cable | LCSC; buy as assembly add | Search "DS18B20 waterproof probe"; verify genuine Maxim/ADI |
| 1 | 4.7 kΩ 0402 pullup | JLCPCB basic | On DQ line |
| 1 | 100 Ω 0402 + 100 pF 0402 | JLCPCB basic | Optional RC damper for long cables |

### Safety path

| Qty | Part | JLCPCB / LCSC | Notes |
|-----|------|---------------|-------|
| 1 | TDK B57560G1103F000 NTC element | LCSC (verify C-number) | Glass-encapsulated bead, 10 kΩ ±1%, B=3988 ±1% |
| 1 | SS316L thermowell, 5–6 mm OD × ~50 mm | Homebrew supplier (McMaster, etc.) | Plus thermal epoxy (Aremco 568 or MG 8329TCF) and silicone cable |
| 1 | REF3330AIDBZT | C2156496 | 3.0 V precision reference, SOT-23-3 |
| 1 | TLV3202IDR (dual comparator) | Search LCSC | 2 channels = over-temp + open-detect, SOIC-8 |
| 1 | 74HC74D dual D flip-flop | Search LCSC (SN74HC74DR) | Half used as SR latch, SOIC-14 |
| 1 | 74HC32D quad OR (optional) | Search LCSC | If using DAC for thresholds; not needed with fixed divider |
| 4 | 0.1% 25 ppm/°C resistors | JLCPCB basic | Divider + threshold |
| 1 | R_FIX 10 kΩ 0.1% 25 ppm/°C | JLCPCB basic | Divider bottom leg |

### Actuation path

| Qty | Part | JLCPCB / LCSC | Notes |
|-----|------|---------------|-------|
| 2 | Omron G3MB-202P (or Panasonic AQH) | Search LCSC | Per-heater SSR, zero-cross |
| 1 | Omron G5LE-14-DC5 | Search LCSC | Master contactor, 10 A SPDT |
| 1 | AO3400 N-MOSFET or TBD62003 | JLCPCB basic | Relay driver |
| 2 | Shunt resistor (10–50 mΩ, 1 W) | JLCPCB extended | Per-heater current sensing |
| 2 | INA181A1IDBVR | Search LCSC | Current-sense amp, SOT-23-6 |
| 2 | Thermal fuse, 94 °C | Not JLCPCB — install post-assembly | NEC/SEFUSE SF94E or similar, bonded to heater body |

### Supervisory logic

| Qty | Part | JLCPCB / LCSC | Notes |
|-----|------|---------------|-------|
| 1 | 74HC08D quad AND | Search LCSC (SN74HC08DR) | Enable gating tree |
| 1 | TPS3823-33DBVR | Search LCSC | Watchdog, SOT-23-5 |
| 1 | MCU (STM32G031K8, RP2040, etc.) | JLCPCB basic/extended | Any MCU with I²C, ADC, GPIO |
| 1 | MCP4728-E/UN (optional) | C108207 | Only if programmable safety threshold is needed |

### Power

| Qty | Part | JLCPCB / LCSC | Notes |
|-----|------|---------------|-------|
| 1 | 5 V supply (wall-wart or onboard AC-DC) | varies | Budget 500 mA |
| 1 | 3.3 V LDO for MCU | JLCPCB basic | e.g., AMS1117-3.3 |
| 1 | Separate LDO for safety chain | JLCPCB basic | Independent of MCU rail so browning out MCU doesn't compromise safety chain |

---

## 10. Design evolution notes

This design went through several iterations worth documenting so the rationale isn't lost:

- **Initial design** used dual PT100 RTDs for both measurement and safety. Rejected because shared sensor technology creates common-cause failure modes, and the analog front end (INA333 + bridge + precision reference) was complex and noise-limited.
- **ADS1220-driven RTDs** considered for measurement — collapses a lot of parts (bridge, INA, separate ADC) into one chip with proper ratiometric excitation. Kept as an option but superseded.
- **Initial safety chain** had four comparators per sensor (over-temp, hard ceiling, short detect, cross-check). Simplified to one comparator per sensor once requirements clarified to "hardware signal on temp too high only."
- **Bridge-based front end for NTC** considered but rejected — NTC's high fractional sensitivity means a plain divider gives a huge signal with no INA needed, which is simpler and cheaper.
- **DS18B20 + NTC diversity** is the final architecture. The move from "two of the same sensor with analog redundancy" to "different sensor technologies on different paths" is the key insight — it provides better fault coverage with fewer parts.

---

## 11. Known gotchas and layout notes

- **Ground topology:** Star-ground the safety chain (RTD front end, comparators, DAC, latches, AND gates) with a single tie point to main ground. A ground bounce from relay switching that shifts comparator references by even 5 mV can cause nuisance trips.
- **Independent rails:** Safety chain, watchdog, and MCU should each have their own LDO (or at least their own bulk caps from a shared bulk rail). If the MCU rail collapses, safety and watchdog must still function.
- **Power-on sequencing:** Default state of every gate, latch, and driver must be "heater off" before the MCU boots. The POR pulse on the safety latch handles this for the safety chain. Pull-downs on SSR gate lines handle it for actuation.
- **REF input impedance:** If any instrumentation amp is used, its REF pin must be driven from a low-impedance source (op-amp buffer), not a raw resistor divider. Gain accuracy degrades otherwise.
- **Thermistor self-heating:** At ~150 µA through the NTC in the 10k/10k divider configuration, self-heating is ~0.16 °C in still water — calibrate out of the trip threshold, or go to 100k/100k to reduce by 100×.
- **B-value tolerance dominates trip accuracy:** A 3% B-tolerance on the NTC shifts the trip point by ~2 °F. Spec 1%/1% or tighter on both R25 and B.
- **Food/water contact:** If the water touches food (fermentation, brewing, anything consumable) or aquatic life, thermal epoxy and silicone cables must be food-safe grades. Aremco 568 cures food-safe; most generic epoxies don't.

---

## 12. Open questions and future work

- **Dry-fire protection:** Current design relies on thermal fuse bonded to each heater element. Consider a dedicated thermistor on the heater body (not in the water) for early dry-fire detection via firmware.
- **Galvanic isolation:** For aquarium use, PT100/NTC leads are at water potential, which is effectively earth-referenced through fish and other grounded equipment. Consider GFCI/RCD on the AC side at minimum; fully isolated sensor front end is cleaner but costs parts.
- **Field trip-point reconfiguration:** If the application later needs adjustable trip points (different species, different vessels), swap the fixed divider for an MCP4728 channel per the earlier sections.
- **Sensor cable EMI:** For long sensor cable runs (>3 m) in industrial environments, add TVS clamping and common-mode chokes on the 1-Wire bus.
