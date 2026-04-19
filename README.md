# ReefVolt SensorBuddy

Open-source aquarium sensor interface board with CAN bus output for hardwired control integration.

## Features

- **Isolated probe inputs**: 2x BNC connectors for pH and/or ORP probes, galvanically isolated (ADM3260 + ADS1115 differential)
- **Temperature sensing**: NTC thermistor inputs (STM32 ADC) + Dallas 1-Wire (DS18B20) support
- **Float switches**: Multiple float switch inputs for water level detection
- **CAN bus output**: Hardwired control interface to other ReefVolt devices (DCBuddy, OsmoBuddy)
- **WiFi/BLE**: ESP32-S3-MINI for Home Assistant integration via ESPHome
- **STM32G0 coprocessor**: Dedicated MCU for real-time sensor sampling and signal conditioning

## Architecture

```
                        ┌────── isolation barrier ──────┐
                        │                               │
STM32G0B1 ──I2C──┬──────┤  ADM3260 (isoPower 3.3V)      │
                 │      │     │                         │
                 │      │  ADS1115 (differential)       │
                 │      │  ├─ AIN0/1: Probe A (BNC)     │
                 │      │  └─ AIN2/3: Probe B (BNC)     │
                 │      └───────────────────────────────┘
                 │
      FDCAN ─────┤── TCAN1044V ──── CAN bus (heater carrier, etc.)
                 │
      USART1 ────┤── ESP32-S3-MINI (WiFi/HA/OLED)
                 │     (ESP32 also controls BOOT0+NRST for STM32 flashing)
                 │
      ADC (int) ─┤── NTC thermistors (x3)
      USART x2 ──┤── 1-Wire DS18B20 (2 buses)
      GPIO ──────┤── Float switches (x4)

USB-C ──────────── Power + Programming (ESP32 native USB)
12-24V DC ─────── TPS54202 → TPS70950 (5V) → 3.3V
```

## Repository Structure

```
reefvolt-sensorbuddy/
├── hardware/                    # PCB designs (KiCad 10, CERN-OHL-P v2)
│   ├── lib/
│   │   ├── symbols/             # Project-specific KiCad symbols
│   │   ├── footprints.pretty/   # Project-specific KiCad footprints
│   │   └── 3dmodels/            # 3D STEP models
│   ├── sensorbuddy/             # Sensor interface board
│   │   ├── sensorbuddy.kicad_pro
│   │   ├── sensorbuddy.kicad_sch
│   │   ├── psu.kicad_sch        # Power supply sub-sheet
│   │   ├── sensors.kicad_sch    # Sensor inputs sub-sheet
│   │   └── jlcpcb/              # Fabrication outputs
│   ├── plugcontrol/             # Heater relay carrier board
│   │   ├── plugcontrol.kicad_pro
│   │   ├── plugcontrol.kicad_sch
│   │   ├── safety.kicad_sch     # Analog safety chain sub-sheet
│   │   ├── actuation.kicad_sch  # SSRs, relay, current sense sub-sheet
│   │   └── jlcpcb/
│   ├── scripts/
│   ├── Makefile
│   ├── sym-lib-table
│   └── fp-lib-table
├── firmware/
│   ├── sensorbuddy-bridge/      # ESP32-S3 ESPHome firmware
│   │   ├── esphome/
│   │   └── components/
│   ├── sensorbuddy-stm32/       # STM32G0B1 sensor coprocessor firmware
│   ├── plugcontrol-stm32/       # STM32G0B1 relay controller firmware
│   ├── common/                  # Shared HAL/utilities
│   └── shared/                  # Shared protocol definitions (CAN IDs, etc.)
└── LICENSE
```

## Key Components (planned)

| Component | Part | Purpose |
|-----------|------|---------|
| WiFi/BLE MCU | ESP32-S3-MINI-1-N8 | Home Assistant bridge, CAN controller, OLED |
| Sensor MCU | STM32G0B1KBU6 | Real-time ADC, 1-Wire, float switches, FDCAN |
| CAN transceiver | TCAN1044VDRQ1 | CAN bus interface |
| I2C isolator | ADM3260ARSZ | I2C isolation + isoPower DC/DC for probe domain |
| Probe ADC | ADS1115IDGSR | 16-bit differential ADC, isolated side (pH/ORP) |
| Buck converter | TPS54202DDCR | 12-24V input to regulated rail |
| LDO 5V | TPS70950DBVT | 5V for sensors/display |
| Display | SH1106 128x64 OLED | Status display (carrier board) |
| ESD protection | USBLC6-4SC6 | USB and I/O ESD suppression |
| USB connector | USB-C 16-pin | Programming and power input |

## Common Parts with Other ReefVolt Designs

Shared with DCBuddy, OsmoBuddy, and LEDBrick for BOM consolidation:
- ESP32-S3-MINI-1-N8, TCAN1044VDRQ1, ADS1115IDGSR
- TPS54202DDCR (buck), TPS70950DBVT (5V LDO), USBLC6-4SC6 (ESD)
- PTS526SK15SMTR2LFS (tactile switches)
- SH1106 OLED carrier board
- Phoenix COMBICON connectors, Micro-Fit 3.0 (CAN)
- 5.1k USB CC resistors, 120R CAN termination

## License

- **Hardware**: CERN-OHL-P v2 (permissive open hardware)
- **Firmware**: Apache 2.0

Copyright (c) 2025-2026 Yann Ramin
