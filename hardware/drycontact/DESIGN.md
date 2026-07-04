# DryContact — 4-Channel Dry-Contact Output Carrier

## Overview

Four-channel **dry-contact** (floating relay) output board for the SensorBuddy CAN cluster.
Receives commands from SensorBuddy over CAN and closes/opens isolated **Form-C (SPDT)** relay
contacts. Where PlugControl switches mains for heaters, DryContact provides signal-level dry
contacts so sensors can actuate arbitrary external gear — other controllers' switch inputs, ATO
pump/solenoid control inputs, alarm inputs, etc.

Like PlugControl, this board is **pure actuation** — it makes no control decisions, it only
executes commanded relay states and enforces its power-on / fail-safe defaults.

## Design decisions (locked 2026-07-04)

| Parameter | Choice | Rationale |
|-----------|--------|-----------|
| Contact rating | **≤ 2 A / 30 VDC** (signal level) | Classic dry contact — trigger inputs, not power. No mains creepage on the board. |
| Relay form | **Form C / SPDT** (COM + NO + NC) | Supports close-on-activate *and* fail-safe/alarm (open-on-activate) wiring. |
| Channels | **4** | Maps to direct STM32 GPIO — no I/O expander needed. Small, cheap board. |
| CAN-loss behavior | **Per-channel configurable** | Each channel independently picks fail-safe (de-energize) vs hold-last. |
| CAN ID scheme | **29-bit extended (J1939-style)** | Cluster-wide decision — see `firmware/shared/` protocol. |
| Node address | **Dynamic, UID auto-assigned** | SensorBuddy assigns addresses keyed on the STM32 96-bit UID. **No address strap on this board.** |

**Dry = floating.** Nothing on the board is wired to the relay contacts; the external circuit
provides its own voltage. Each channel exposes COM/NO/NC on its own connector.

---

## Block Diagram

```
                         ┌──────────────────────────────────────────────┐
                         │              DryContact PCB                   │
                         │                                              │
  CAN bus ───────────────┤  TCAN1044VDRQ1 ── FDCAN ── STM32G0B1KBU6     │
  (Micro-Fit, from       │                              │               │
   SensorBuddy)          │        ┌─────────────────────┤               │
                         │        │ 4x GPIO (coil drive) │               │
                         │        │ 4x GPIO (contact sns)│               │
  12-24V DC ─────────────┤  TPS54202 → 5V ─┬─ LM1117 → 3.3V (STM32)      │
  (shared bus)           │                 │                            │
                         │                 ▼                            │
                         │        ┌──────────────────────────────┐      │
                         │        │  ULN2003A coil driver (x4)   │      │
                         │        │   + flyback clamp per coil   │      │
                         │        └───────┬──────────────────────┘      │
                         │                │                             │
                         │     ┌──────────▼──────────┐  (x4 channels)   │
                         │     │  Form-C signal relay │                 │
                         │     │   COM ─┬─ NO         │                 │
                         │     │        └─ NC         │                 │
                         │     └──────────┬──────────┘                  │
                         │                │  COM/NO/NC                  │
  Dry contacts out ──────┤────────────────┴──── Phoenix 3-pos (x4) ─────┤
   (floating, ≤2A/30V)   │                                              │
                         └──────────────────────────────────────────────┘
```

Default at power-on: **all coils de-energized** → each relay sits at COM–NC closed, COM–NO open.

---

## Per-Channel Output Stage (x4)

- **Relay:** Form-C (SPDT) signal relay, coil 5V, contacts rated ≥ 2 A / 30 VDC (dry).
  Candidate families: Panasonic TQ2SA-5V / Omron G6K-2F-Y / equivalent (final pick in BOM step).
- **Coil driver:** one channel of a **ULN2003A** darlington array (shared across all 4 coils),
  integrated flyback clamp diode to the 5V rail. STM32 GPIO drives the input directly.
- **Status LED:** per-channel, mirrors coil-energized state (driven from the coil node or a
  parallel GPIO).
- **Contact sense (optional):** STM32 GPIO reads COM against a weak pull to confirm the relay
  actually transferred — reports back over CAN as a diagnostic (welded/stuck detection).
- **Output connector:** Phoenix COMBICON 3-pos per channel = COM / NO / NC.

### CAN-loss behavior (per channel)

- **Fail-safe:** on heartbeat loss the channel de-energizes (relay returns to rest, COM–NC).
- **Hold-last:** on heartbeat loss the channel keeps its last commanded state.
- Selection is stored per channel and set over CAN config; enforced by the STM32 firmware
  watchdog driven off the broadcast master heartbeat (address-independent, so it works even
  before the node is addressed).

---

## MCU / CAN

- **STM32G0B1KBU6** (same MCU as SensorBuddy / PlugControl) — FDCAN, plenty of GPIO for 4
  coils + 4 sense + LEDs.
- **TCAN1044VDRQ1** transceiver (shared line part).
- **29-bit extended IDs, J1939-style.** Node address is **auto-assigned by SensorBuddy** using
  the STM32 96-bit UID as the durable identity — there is **no DIP/rotary address switch**.
  Un-addressed nodes stay de-energized and still run the heartbeat-loss watchdog. Full message
  catalog lives in `firmware/shared/` (single source of truth for every board on the bus).
- **USB-C** for STM32 programming/console and as an alternate 5V source.

---

## Power

- **Input:** 12-24V DC from the shared ReefVolt bus (via the Micro-Fit CAN connector V+/GND and
  a Phoenix COMBICON feed).
- **5V rail (TPS54202DDCR sync buck):** relay coils (worst case = all 4 energized) + TCAN1044.
- **3.3V rail (LM1117IMP-3.3):** STM32G0B1.
- Reverse-polarity (SS14) + TVS clamp on the DC input.

---

## Connectors

| Connector | Type | Qty | Purpose |
|-----------|------|-----|---------|
| CAN bus | Micro-Fit 3.0 6-pos | 1 (or 2 for daisy-chain) | To SensorBuddy / next node |
| DC power in | Phoenix COMBICON 2-pos | 1 | 12-24V from shared bus |
| Relay output | Phoenix COMBICON 3-pos | 4 | COM / NO / NC per channel |
| USB-C | USB-C receptacle | 1 | Programming + console + alt 5V |

---

## KiCad Sheets

| File | Contents |
|------|----------|
| drycontact.kicad_sch | Top-level: STM32G0B1, TCAN1044, USB-C, connectors |
| psu.kicad_sch | Power: DC in protection, TPS54202 5V, LM1117 3.3V |
| relays.kicad_sch | 4x Form-C relays, ULN2003 coil driver, flyback, LEDs, contact sense |

Build outputs (from `hardware/`):

```
make images-drycontact   # schematic + PCB SVGs, 3D renders
make bom-drycontact      # JLCPCB BOM CSV
make jlc-drycontact      # JLCPCB fab + assembly zip
```

---

## Bill of Materials (JLCPCB assembly)

Verified in-stock on LCSC (jlcsearch, 2026-07-04). All actives are JLC **Extended**
(normal for this class); passives are **Basic** (no feeder fee). The `schgen`
manifest (`scripts/drycontact.schgen.py`) carries these LCSC numbers as the source
of truth — `make bom-drycontact` emits the assembly BOM.

| Block | Ref | Part | LCSC | Pkg |
|---|---|---|---|---|
| MCU | U1 | STM32G0B1KBU6N | `C5159549` | UFQFPN-32 |
| CAN | U2 | TCAN1044VDRQ1 | `C1852061` | SOIC-8 |
| USB ESD | U3 | USBLC6-4SC6 | `C5197386` | SOT-23-6 |
| Buck 5V | U4 | TPS54202DDCR | `C191884` | SOT-23-6 |
| LDO 3V3 | U5 | LM1117IMPX-3.3 | `C23984` | SOT-223 |
| Coil driver | U6 | ULN2003ADR | `C7512` | SOIC-16 |
| Relay ×4 | K1–K4 | Omron G6K-2F-Y DC5 | `C47190` | SMD (both poles ∥ → ~2A/30V) |
| Buck L | L1 | SRN4018-4R7M | `C408412` | 4.7µH |
| Rev-prot | D3 | SS14 | `C2480` | SMA |

Passives (Basic): 0402 R/C decoupling, 100k/22.1k buck FB, USB-C 5.1k CC, LED series;
buck/LDO caps 1210. USB-C `C165948` (HRO TYPE-C-31-M-12).

**Assembly strategy:** Economic (top-only SMD) with the G6K SMD relay; ~8 unique
Extended ICs. The **STM32G0B1 (~2.6k stock)** is the only supply-watch item (whole
line depends on it). Connectors are hand-soldered — see `drycontact-handsolder.txt`.

## Open Questions

1. **Relay part:** latching vs non-latching. Latching holds state through a power blip (good)
   but complicates the fail-safe path (needs an explicit reset pulse) — leaning non-latching so
   power-loss == de-energized == safe.
2. **Contact sense:** include the per-channel readback, or drop it to save GPIO/BOM? Useful for
   stuck-relay reporting; not strictly required for a signal-level board.
3. **Per-channel CAN-loss config persistence:** store in STM32 flash (survives reboot) vs
   re-push from SensorBuddy on every connect. Flash is more autonomous.
4. **Daisy-chain:** one Micro-Fit (stub) or two (chain-through) for bus topology + termination.
5. **Board home:** keep as a 3rd PCB in `reefvolt-sensorbuddy` (current) vs split to its own repo
   once it matures.
6. **Working name:** DryContact vs ContactControl (parallel to PlugControl).
