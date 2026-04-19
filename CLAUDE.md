# Claude Code Assistant Guidelines

## General Rules
- Do not run cat or stty commands
- Use makefile targets when possible
- This is a KiCad 10 project — use kicad-cli for schematic/PCB operations
- Use `uv` for all Python operations (install, run, etc.) — never use bare pip

## Project Context
- ReefVolt SensorBuddy: aquarium sensor interface (temp, pH, float, CAN)
- Sister projects: reefvolt-dcbuddy, reefvolt-osmobuddy (Altium, in sibling dirs)
- Structure modeled after tsumikoro/ (KiCad, STM32G0 + ESP32)
- ESP32-C3-MINI-1-N4 as WiFi/HA bridge, STM32G0 as sensor coprocessor

## Hardware
- KiCad project files live in hardware/sensorbuddy/
- Shared symbols: hardware/lib/symbols/sensorbuddy.kicad_sym
- Shared footprints: hardware/lib/footprints.pretty/
- Generate JLCPCB outputs: `cd hardware && make jlc`
- Generate docs/images: `cd hardware && make docs`

## Firmware
- ESP32-C3 bridge: firmware/sensorbuddy-bridge/ (ESPHome)
- STM32G0 coprocessor: firmware/sensorbuddy-stm32/ (bare-metal or FreeRTOS)

## Key Parts (shared with DCBuddy/OsmoBuddy)
- ESP32-C3-MINI-1-N4 (WiFi/BLE MCU)
- TCAN1044VDRQ1 (CAN transceiver)
- PCA9554APW (I2C I/O expander)
- ADS1115IDGSR (16-bit ADC)
- TPS54202DDCR or TPS70950DBVT (power)
- USBLC6-4SC6 (ESD protection)
