#!/usr/bin/env python3
"""DryContact manifest — generates the schematic with parts PLACED (not wired).

Third PCB in the reefvolt-sensorbuddy repo (alongside sensorbuddy + plugcontrol);
shares this repo's engine (scripts/kschgen.py), Makefile, and lib tables.

DryContact is a dumb 4-channel Form-C dry-contact output carrier on the SensorBuddy
CAN cluster. It reuses the line's shared core (STM32G0B1 + TCAN1044 + TPS54202 +
LM1117 + USBLC6 — custom symbols already in lib/symbols/sensorbuddy.kicad_sym) and
adds a ULN2003 coil driver + 4x Omron G6K-2F-Y signal relays (both poles paralleled
per channel -> ~2A/30V dry contact). Node address is auto-assigned over CAN from the
STM32 UID (no strap). See hardware/drycontact/DESIGN.md for the full BOM + rationale.

Sheets: MCU/CAN, PWR, Relays. Components are PLACED, not wired — wire them in
eeschema using the per-sheet notes as the spec. Regenerate BEFORE wiring; regen
reassigns UUIDs.  `make gen-drycontact`
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kschgen as K

HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # hardware/
PROJ_DIR = os.path.join(HW, "drycontact")
SB_SYM = os.path.join(HW, "lib", "symbols", "sensorbuddy.kicad_sym")
ROOT_UUID = "d0000000-0000-4dc0-8000-000000000001"   # keep stable across regens

# ---- symbol libraries -------------------------------------------------------
K.register_stdlib("Device", "R", "C", "L", "LED", "D_Schottky")
K.register_stdlib("Transistor_Array", "ULN2003A")
K.register_stdlib("Relay", "G6K-2")
K.register_stdlib("Connector", "USB_C_Receptacle_USB2.0_16P")
K.register_stdlib("Connector_Generic", "Conn_01x02", "Conn_01x03", "Conn_02x03_Odd_Even")
# shared line parts — custom symbols already in the project lib
K.register_lib("sensorbuddy", SB_SYM,
               "STM32G0B1KBU6", "TCAN1044VDRQ1", "TPS54202DDCR",
               "LM1117IMP-3.3", "USBLC6-4SC6")

# ---- footprint shorthands ---------------------------------------------------
R0402  = "Resistor_SMD:R_0402_1005Metric"
C0402  = "Capacitor_SMD:C_0402_1005Metric"
C0805  = "Capacitor_SMD:C_0805_2012Metric"
C1210  = "Capacitor_SMD:C_1210_3225Metric"
LED0402 = "LED_SMD:LED_0402_1005Metric"
SOT236  = "Package_TO_SOT_SMD:SOT-23-6"
SOT2233 = "Package_TO_SOT_SMD:SOT-223-3_TabPin2"
SOIC8   = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
SOIC16  = "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"
QFN32   = "sensorbuddy:UFQFPN-32"          # custom fp + STM32_UFQFPN-32 3D model
SMA     = "Diode_SMD:D_SMA"
SRN4018 = "Inductor_SMD:L_Bourns-SRN4018"
RELAY   = "Relay_SMD:Relay_DPDT_Omron_G6K-2F-Y"
USBC    = "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12"
UFIT6   = "Connector_Molex:Molex_Micro-Fit_3.0_43045-0612_2x03_P3.00mm_Vertical"
PHX2    = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MPT-0,5-2-2.54_1x02_P2.54mm_Horizontal"
PHX3    = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MPT-0,5-3-2.54_1x03_P2.54mm_Horizontal"

RLCSC = {"5.1k": "C27834", "10k": "C25744", "100k": "C25741", "22.1k": "C25765",
         "1k": "C11702", "4.7k": "C25900", "0R": "C17168", "100R": "C106232"}
CLCSC = {"100nF": "C1525", "1uF": "C29266", "10uF": "C15850",
         "22uF": "C45783", "4.7uF": "C1611"}


def R(ref, val, **kw):
    return dict(ref=ref, lib_id="Device:R", value=val, fp=R0402,
               lcsc=RLCSC.get(val, ""), **kw)


def C(ref, val, fp=C0402, **kw):
    return dict(ref=ref, lib_id="Device:C", value=val, fp=fp,
               lcsc=CLCSC.get(val, ""), **kw)


# ============================ MCU / CAN sheet ================================
MCU = dict(name="MCU", file="mcu.kicad_sch",
    title="MCU (STM32G0B1) / FDCAN (TCAN1044) / USB-C — CAN node, UID auto-address", page="2",
    big=[
        dict(ref="U1", lib_id="sensorbuddy:STM32G0B1KBU6", value="STM32G0B1KBU6",
             fp=QFN32, lcsc="C5159549", mpn="STM32G0B1KBU6N", mfr="ST"),
        dict(ref="U2", lib_id="sensorbuddy:TCAN1044VDRQ1", value="TCAN1044VDRQ1",
             fp=SOIC8, lcsc="C1852061", mpn="TCAN1044VDRQ1", mfr="TI"),
        dict(ref="U3", lib_id="sensorbuddy:USBLC6-4SC6", value="USBLC6-4SC6",
             fp=SOT236, lcsc="C5197386", mpn="USBLC6-4SC6", mfr="ST"),
        dict(ref="J1", lib_id="Connector:USB_C_Receptacle_USB2.0_16P",
             value="USB-C prog/pwr", fp=USBC, lcsc="C165948",
             mpn="TYPE-C-31-M-12", mfr="Korean Hroparts"),
        dict(ref="J2", lib_id="Connector_Generic:Conn_02x03_Odd_Even",
             value="CAN Micro-Fit 6p", fp=UFIT6, lcsc="", mpn="43045-0612", mfr="Molex"),
    ],
    small=[
        C("C1", "100nF"), C("C2", "100nF"), C("C3", "100nF"),   # STM32 VDD decouple
        C("C4", "4.7uF", C0805),                                # STM32 VDD bulk
        C("C5", "100nF"),                                       # TCAN1044 VCC decouple
        C("C6", "100nF"),                                       # VDDA / VREF
        R("R1", "5.1k"), R("R2", "5.1k"),                       # USB-C CC1/CC2 (UFP)
        R("R3", "10k"),                                         # BOOT0 pulldown
        R("R4", "10k"),                                         # NRST pullup (opt)
        dict(ref="D1", lib_id="Device:LED", value="PWR grn", fp=LED0402,
             lcsc="C72043", mpn="KT-0402G", mfr="Hubei KENTO"),
        R("R5", "1k"),                                          # PWR LED series
        dict(ref="D2", lib_id="Device:LED", value="STAT blu", fp=LED0402,
             lcsc="C72041", mpn="KT-0402B", mfr="Hubei KENTO"),
        R("R6", "1k"),                                          # STAT LED series
        R("R7", "120R"),                                        # CAN termination (fit on end nodes)
    ],
    note=(12, 150, """MCU/CAN — STM32G0B1KBU6 (UFQFPN-32) FDCAN node.  PLACED, not wired.
 CAN:   PB9 FDCAN_TX -> U2.1 (TXD)   PB8 FDCAN_RX <- U2.4 (RXD)   U2: 3=VCC(5V,C5) 2=GND 8=STBY->GND 7=CANH 6=CANL 5=VIO(3V3)
 J2 Micro-Fit 6p (CAN + bus power):  1=CANH 2=CANL 3=GND 4=V+ (12-24V) 5=GND 6=V+   R7 120R CANH--CANL (end node only)
 USB:   J1 D+/D- -> U3 (USBLC6) -> STM32 PA12/PA11 ;  J1 VBUS -> 5V (ORing) ;  R1/R2 5.1k CC1/CC2 -> GND (UFP)
 U3 USBLC6-4SC6: 1=IO1 2=GND 3=IO2 4=IO2 5=VBUS 6=IO1   (ESD clamp on D+/D-)
 STM32 pwr: VDD/VDDA -> 3V3 (C1..C4) ;  BOOT0 R3 10k -> GND ;  NRST R4 10k -> 3V3 + 100nF
 LEDs: D1 PWR (3V3->R5->D1->GND)   D2 STAT (PAx->R6->D2->GND, firmware/CAN-link heartbeat)
 Node address is auto-assigned by SensorBuddy from the STM32 96-bit UID — NO strap."""))

# ============================ PWR sheet ======================================
PWR = dict(name="PWR", file="psu.kicad_sch",
    title="Power: 12-24V (CAN bus) -> TPS54202 5V -> LM1117 3.3V", page="3",
    big=[
        dict(ref="U4", lib_id="sensorbuddy:TPS54202DDCR", value="TPS54202DDCR",
             fp=SOT236, lcsc="C191884", mpn="TPS54202DDCR", mfr="TI"),
        dict(ref="U5", lib_id="sensorbuddy:LM1117IMP-3.3", value="LM1117IMP-3.3",
             fp=SOT2233, lcsc="C23984", mpn="LM1117IMPX-3.3/NOPB", mfr="TI"),
        dict(ref="J3", lib_id="Connector_Generic:Conn_01x02",
             value="DC IN 12-24V", fp=PHX2, lcsc="", mpn="MPT-0,5/2-2,54", mfr="Phoenix"),
    ],
    small=[
        dict(ref="L1", lib_id="Device:L", value="4.7uH", fp=SRN4018,
             lcsc="C408412", mpn="SRN4018-4R7M", mfr="Bourns"),
        dict(ref="D3", lib_id="Device:D_Schottky", value="SS14", fp=SMA,
             lcsc="C2480", mpn="SS14", mfr="MDD"),                  # reverse polarity
        C("C10", "4.7uF", C1210),                                  # buck VIN
        C("C11", "22uF", C1210),                                   # buck VOUT (5V)
        C("C12", "22uF", C1210),                                   # LDO VOUT (3V3)
        C("C13", "100nF"),                                         # buck bootstrap
        R("R10", "100k"), R("R11", "22.1k"),                       # buck FB divider -> 5V
    ],
    note=(12, 130, """PWR — 12-24V (from J2/CAN bus) -> 5V buck -> 3.3V LDO.  PLACED, not wired.
 J3 DC IN:  1 = V+ (12-24V, = J2.4/6)   2 = GND     D3 SS14: A=V+ K=VIN  (reverse-polarity)
 U4 TPS54202 (SOT-23-6):  1 BOOT  2 VIN  3 EN  4 GND  5 FB  6 SW
   C10 4.7uF VIN--GND   L1 4.7uH SW--5V   C11 22uF 5V--GND   C13 100nF BOOT--SW
   FB divider: R10 100k 5V--FB , R11 22.1k FB--GND  (Vout = 0.596*(1+R10/R11) ~= 5.0V)
 U5 LM1117-3.3 (SOT-223):  1 GND/ADJ  2 OUT(3V3)  3 IN(5V)   C12 22uF 3V3--GND
 RAILS OUT:  5V -> relay coils (Relays sheet, ULN2003 COM) + TCAN1044 VCC ;  3V3 -> STM32, USBLC6 VIO"""))

# ============================ Relays sheet ===================================
# 4x Form-C dry contact. Each channel: STM32 GPIO -> ULN2003 -> G6K-2F-Y coil
# (both poles paralleled -> ~2A/30V). ULN2003 COM (pin 9) -> 5V = internal flyback.
def relay(n, kref, jref):
    return [
        dict(ref=kref, lib_id="Relay:G6K-2", value="G6K-2F-Y 5V",
             fp=RELAY, lcsc="C47190", mpn="G6K-2F-Y DC5", mfr="Omron"),
        dict(ref=jref, lib_id="Connector_Generic:Conn_01x03",
             value=f"CH{n} COM/NO/NC", fp=PHX3, lcsc="", mpn="MPT-0,5/3-2,54", mfr="Phoenix"),
    ]
RELAYS = dict(name="Relays", file="relays.kicad_sch",
    title="4x Form-C dry-contact outputs — ULN2003 + Omron G6K-2F-Y", page="4",
    big=[
        dict(ref="U6", lib_id="Transistor_Array:ULN2003A", value="ULN2003A",
             fp=SOIC16, lcsc="C7512", mpn="ULN2003ADR", mfr="TI"),
        *relay(1, "K1", "J4"), *relay(2, "K2", "J5"),
        *relay(3, "K3", "J6"), *relay(4, "K4", "J7"),
    ],
    small=[
        C("C20", "100nF"),                                        # ULN2003 supply decouple
        # per-channel status LED (mirrors coil energized)
        dict(ref="D4", lib_id="Device:LED", value="CH1", fp=LED0402, lcsc="C72041", mpn="KT-0402B", mfr="KENTO"),
        dict(ref="D5", lib_id="Device:LED", value="CH2", fp=LED0402, lcsc="C72041", mpn="KT-0402B", mfr="KENTO"),
        dict(ref="D6", lib_id="Device:LED", value="CH3", fp=LED0402, lcsc="C72041", mpn="KT-0402B", mfr="KENTO"),
        dict(ref="D7", lib_id="Device:LED", value="CH4", fp=LED0402, lcsc="C72041", mpn="KT-0402B", mfr="KENTO"),
        R("R20", "1k"), R("R21", "1k"), R("R22", "1k"), R("R23", "1k"),   # LED series
    ],
    note=(12, 135, """Relays — 4x Form-C dry contact.  PLACED, not wired.  Dry = floating; ext circuit provides V.
 U6 ULN2003A (SOIC-16):  IN 1..7 = pins 1..7   OUT 1..7 = pins 16..10   8 GND   9 COM
   COM (pin 9) -> 5V  ==> internal freewheel diodes clamp each coil (NO external flyback needed)
 Drive:  STM32 GPIO -> U6.IN{1..4} ;  U6.OUT{1..4} -> K{1..4} coil low side ;  coil high side -> 5V
 Each relay K1..K4 = Omron G6K-2F-Y (2 Form C).  PARALLEL both poles per channel -> COM/NO/NC ~2A/30V:
   K.COM1+COM2 -> Jn.1 (COM)   K.NO1+NO2 -> Jn.2 (NO)   K.NC1+NC2 -> Jn.3 (NC)
 Outputs J4..J7 = Phoenix 3-pos (COM/NO/NC).  Power-on default = coils OFF (relay at rest, COM-NC closed).
 Status LEDs D4..D7 (+ R20..R23 1k) mirror coil state.  Per-channel CAN-loss mode (fail-safe/hold) in firmware."""))


# ============================ generate =======================================
K.build(
    project="drycontact", proj_dir=PROJ_DIR, root_uuid=ROOT_UUID,
    title=dict(title="ReefVolt DryContact — 4ch Form-C carrier", date="2026-07-04", rev="0.1",
               company="blueAcro / ReefVolt",
               comments=["4-channel Form-C dry-contact output carrier for the SensorBuddy CAN cluster",
                         "STM32G0B1 + TCAN1044 + ULN2003 + 4x Omron G6K-2F-Y; 29-bit CAN, UID auto-address"]),
    sheets=[MCU, PWR, RELAYS],
)
