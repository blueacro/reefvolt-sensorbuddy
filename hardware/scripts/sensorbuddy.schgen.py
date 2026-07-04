#!/usr/bin/env python3
"""SensorBuddy manifest — generates the schematic with parts PLACED (not wired).

Flagship board of the reefvolt-sensorbuddy repo (CAN master of the cluster;
siblings plugcontrol + drycontact). Shares this repo's engine (scripts/kschgen.py),
Makefile, and lib tables. Aquarium sensor interface: ESP32-S3 WiFi bridge +
STM32G0B1 sensor coprocessor/FDCAN + isolated pH/ORP probes (ADM3260 + ADS1115 +
OPA2376) + NTC + 1-Wire DS18B20 + float switches. Full BOM in ../DESIGN.md.

Reuses the existing root UUID so the sheet identity stays stable. build() OVERWRITES
the placeholder sensorbuddy/psu/sensors sheets with placed-parts versions. Parts are
PLACED, not wired — wire in eeschema using the per-sheet notes.  `make gen-sensorbuddy`
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kschgen as K

HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ_DIR = os.path.join(HW, "sensorbuddy")
SB_SYM = os.path.join(HW, "lib", "symbols", "sensorbuddy.kicad_sym")
ROOT_UUID = "a1b2c3d4-e5f6-7890-abcd-ef0123456789"   # existing sensorbuddy root — keep stable

# ---- symbol libraries -------------------------------------------------------
K.register_stdlib("Device", "R", "C", "L", "LED", "D_Schottky")
K.register_stdlib("Switch", "SW_Push")
K.register_stdlib("Connector", "USB_C_Receptacle_USB2.0_16P", "Conn_Coaxial")
K.register_stdlib("Connector_Generic", "Conn_01x02", "Conn_01x03", "Conn_01x04",
                  "Conn_02x03_Odd_Even")
K.register_lib("sensorbuddy", SB_SYM,
               "ESP32-S3-MINI-1", "STM32G0B1KBU6", "TCAN1044VDRQ1", "USBLC6-4SC6",
               "TPS54202DDCR", "LM1117IMP-3.3", "ADM3260ARSZ", "ADS1115IDGST",
               "OPA2376AIDR")

# ---- footprint shorthands ---------------------------------------------------
R0402  = "Resistor_SMD:R_0402_1005Metric"
R0603  = "Resistor_SMD:R_0603_1608Metric"
C0402  = "Capacitor_SMD:C_0402_1005Metric"
C0603  = "Capacitor_SMD:C_0603_1608Metric"
C0805  = "Capacitor_SMD:C_0805_2012Metric"
C1210  = "Capacitor_SMD:C_1210_3225Metric"
LED0603 = "LED_SMD:LED_0603_1608Metric"
SOT236  = "Package_TO_SOT_SMD:SOT-23-6"
SOT2233 = "Package_TO_SOT_SMD:SOT-223-3_TabPin2"
SOIC8   = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
SSOP20  = "Package_SO:SSOP-20_3.9x8.7mm_P0.635mm"
VSSOP10 = "Package_SO:VSSOP-10_3x3mm_P0.5mm"
QFN32   = "sensorbuddy:UFQFPN-32"
ESP32MOD = "sensorbuddy:ESP32-S3-MINI-1"
SMA     = "Diode_SMD:D_SMA"
SRN4018 = "Inductor_SMD:L_Bourns-SRN4018"
USBC    = "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12"
UFIT6   = "Connector_Molex:Molex_Micro-Fit_3.0_43045-0612_2x03_P3.00mm_Vertical"
PHX2    = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MPT-0,5-2-2.54_1x02_P2.54mm_Horizontal"
PHX3    = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MPT-0,5-3-2.54_1x03_P2.54mm_Horizontal"
BNC     = "Connector_Coaxial:BNC_Amphenol_B6252HB-NPP3G-50_Horizontal"
SWPUSH  = "Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2"
HDR4    = "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"

RLCSC = {"5.1k": "C27834", "10k": "C25804", "100k": "C25803", "22.1k": "C25765",
         "4.7k": "C25905", "100R": "C22775", "220R": "C22962", "1k": "C21190",
         "120R": "C22787"}
CLCSC = {"100nF": "C14663", "1uF": "C15849", "4.7uF": "C19666", "10uF": "C19702",
         "22uF": "C45783", "100pF": "C14858"}


def R(ref, val, fp=R0603, **kw):
    return dict(ref=ref, lib_id="Device:R", value=val, fp=fp,
               lcsc=RLCSC.get(val, ""), **kw)


def C(ref, val, fp=C0603, **kw):
    return dict(ref=ref, lib_id="Device:C", value=val, fp=fp,
               lcsc=CLCSC.get(val, ""), **kw)


def led(ref, val, lcsc="C72043"):
    return dict(ref=ref, lib_id="Device:LED", value=val, fp=LED0603,
               lcsc=lcsc, mpn="KT-0603", mfr="Hubei KENTO")


def phx2(ref, val):
    return dict(ref=ref, lib_id="Connector_Generic:Conn_01x02", value=val,
               fp=PHX2, lcsc="", mpn="MPT-0,5/2-2,54", mfr="Phoenix")


def phx3(ref, val):
    return dict(ref=ref, lib_id="Connector_Generic:Conn_01x03", value=val,
               fp=PHX3, lcsc="", mpn="MPT-0,5/3-2,54", mfr="Phoenix")


# ============================ MAIN sheet =====================================
MAIN = dict(name="MAIN", file="main.kicad_sch",
    title="ESP32-S3 + STM32G0B1 + CAN + USB — sensor MCU / WiFi bridge", page="1",
    big=[
        dict(ref="U1", lib_id="sensorbuddy:ESP32-S3-MINI-1", value="ESP32-S3-MINI-1-N8",
             fp=ESP32MOD, lcsc="C2913204", mpn="ESP32-S3-MINI-1-N8", mfr="Espressif"),
        dict(ref="U2", lib_id="sensorbuddy:STM32G0B1KBU6", value="STM32G0B1KBU6",
             fp=QFN32, lcsc="C5159549", mpn="STM32G0B1KBU6N", mfr="ST"),
        dict(ref="U3", lib_id="sensorbuddy:TCAN1044VDRQ1", value="TCAN1044VDRQ1",
             fp=SOIC8, lcsc="C1852061", mpn="TCAN1044VDRQ1", mfr="TI"),
        dict(ref="U4", lib_id="sensorbuddy:USBLC6-4SC6", value="USBLC6-4SC6",
             fp=SOT236, lcsc="C5197386", mpn="USBLC6-4SC6", mfr="ST"),
        dict(ref="J1", lib_id="Connector:USB_C_Receptacle_USB2.0_16P",
             value="USB-C prog/pwr", fp=USBC, lcsc="C165948", mpn="TYPE-C-31-M-12", mfr="Korean Hroparts"),
        dict(ref="J2", lib_id="Connector_Generic:Conn_02x03_Odd_Even",
             value="CAN Micro-Fit 6p", fp=UFIT6, lcsc="", mpn="43045-0612", mfr="Molex"),
        dict(ref="J3", lib_id="Connector_Generic:Conn_01x04",
             value="OLED I2C 4p", fp=HDR4, lcsc="", mpn="0901471104", mfr="Molex"),
    ],
    small=[
        C("C1", "100nF"), C("C2", "100nF"), C("C3", "100nF"), C("C4", "100nF"),  # MCU/ESP decouple
        C("C5", "4.7uF", C0805), C("C6", "4.7uF", C0805),                        # ESP32/STM32 VDD bulk
        C("C7", "100nF"),                                                        # TCAN1044 VCC
        R("R1", "5.1k", R0402), R("R2", "5.1k", R0402),                          # USB-C CC1/CC2
        R("R3", "10k"), R("R4", "10k"),                                          # ESP32 EN/BOOT pullups
        R("R5", "10k"),                                                          # STM32 BOOT0 pulldown
        C("C8", "100nF"),                                                        # STM32 NRST filter
        R("R6", "120R", C1210),                                                  # CAN termination
        dict(ref="SW1", lib_id="Switch:SW_Push", value="BOOT", fp=SWPUSH, lcsc="C318884", mpn="PTS526", mfr="C&K"),
        dict(ref="SW2", lib_id="Switch:SW_Push", value="RESET", fp=SWPUSH, lcsc="C318884", mpn="PTS526", mfr="C&K"),
        led("D1", "PWR grn", "C72043"), R("R7", "1k"),
        led("D2", "STAT blu", "C72041"), R("R8", "1k"),
    ],
    note=(12, 150, """MAIN — ESP32-S3 (WiFi bridge) + STM32G0B1 (sensor MCU / FDCAN master).  PLACED, not wired.
 Inter-MCU:  ESP32 USART1 <-> STM32 USART1 (data + STM32 bootloader) ;  ESP32 GPIO -> STM32 BOOT0(R5)+NRST (in-system flash)
 CAN:  STM32 PB9 FDCAN_TX -> U3.1  PB8 FDCAN_RX <- U3.4 ;  U3: 3=VCC(5V,C7) 8=STBY->GND 7=CANH 6=CANL 5=VIO(3V3) ;  R6 120R CANH--CANL
 J2 Micro-Fit 6p:  1 CANH  2 CANL  3 GND  4 V+(12-24V)  5 GND  6 V+
 USB:  J1 D+/D- -> U4 USBLC6 -> ESP32 native USB ;  R1/R2 5.1k CC -> GND ;  VBUS -> 5V
 J3 OLED (4p 2.54):  1 GND  2 3V3  3 SCL  4 SDA (ESP32 I2C)   SW1 BOOT / SW2 RESET on ESP32
 LEDs D1 PWR / D2 STAT (+ R7/R8 1k).   Node is the SOLE CAN master; ESP32 is NOT on the bus (USART only)."""))

# ============================ PSU sheet ======================================
PSU = dict(name="PSU", file="psu.kicad_sch",
    title="Power: 12-24V -> TPS54202 5V -> LM1117 3.3V (+ barrel/Phoenix in)", page="2",
    big=[
        dict(ref="U5", lib_id="sensorbuddy:TPS54202DDCR", value="TPS54202DDCR",
             fp=SOT236, lcsc="C191884", mpn="TPS54202DDCR", mfr="TI"),
        dict(ref="U6", lib_id="sensorbuddy:LM1117IMP-3.3", value="LM1117IMP-3.3",
             fp=SOT2233, lcsc="C23984", mpn="LM1117IMPX-3.3/NOPB", mfr="TI"),
        phx2("J4", "DC IN 12-24V"),
    ],
    small=[
        dict(ref="L1", lib_id="Device:L", value="4.7uH", fp=SRN4018,
             lcsc="C408412", mpn="SRN4018-4R7M", mfr="Bourns"),
        dict(ref="D3", lib_id="Device:D_Schottky", value="SS14", fp=SMA,
             lcsc="C2480", mpn="SS14", mfr="MDD"),
        C("C10", "4.7uF", C1210), C("C11", "22uF", C1210), C("C12", "22uF", C1210),
        C("C13", "100nF"),
        R("R10", "100k"), R("R11", "22.1k"),
    ],
    note=(12, 120, """PSU — 12-24V -> 5V buck -> 3.3V LDO.  PLACED, not wired.
 J4 DC IN:  1 = V+ (12-24V)  2 = GND    D3 SS14 reverse-polarity (A=V+ K=VIN)
 U5 TPS54202 (SOT-23-6):  1 BOOT 2 VIN 3 EN 4 GND 5 FB 6 SW ;  C10 VIN  L1 4.7uH SW--5V  C11 22uF 5V
   FB: R10 100k 5V--FB, R11 22.1k FB--GND (~5.0V) ;  C13 100nF BOOT--SW
 U6 LM1117-3.3 (SOT-223): 3 IN(5V) 2 OUT(3V3) 1 GND ;  C12 22uF 3V3
 RAILS:  5V -> TCAN1044, ADM3260 VDD1 ;  3V3 -> ESP32, STM32, USBLC6 VIO.  ISO_3V3 made on SENSORS sheet (ADM3260)."""))

# ============================ SENSORS sheet ==================================
def probe(idx, uref, bnc, bias_a, bias_b, rser, cout):
    """One isolated pH/ORP probe front-end (bias divider + OPA2376 buffer to ADS1115)."""
    return [dict(ref=bnc, lib_id="Connector:Conn_Coaxial", value=f"PROBE {idx} BNC",
                 fp=BNC, lcsc="", mpn="BNC-vert", mfr="generic"),
            R(bias_a, "100k"), R(bias_b, "100k"), R(rser, "220R"), C(cout, "100pF")]

SENSORS = dict(name="SENSORS", file="sensors.kicad_sch",
    title="Isolated pH/ORP probes (ADM3260+ADS1115+OPA2376), NTC, 1-Wire, floats", page="3",
    big=[
        dict(ref="U7", lib_id="sensorbuddy:ADM3260ARSZ", value="ADM3260ARSZ",
             fp=SSOP20, lcsc="C208558", mpn="ADM3260ARSZ-RL7", mfr="ADI"),
        dict(ref="U8", lib_id="sensorbuddy:ADS1115IDGST", value="ADS1115IDGST",
             fp=VSSOP10, lcsc="C468683", mpn="ADS1115IDGST", mfr="TI"),
        dict(ref="U9", lib_id="sensorbuddy:OPA2376AIDR", value="OPA2376AIDR",
             fp=SOIC8, lcsc="C46316", mpn="OPA2376AIDR", mfr="TI"),
        # NTC probe inputs (x3), 1-Wire buses (x2), float switch inputs (x4)
        phx2("J7", "NTC1"), phx2("J8", "NTC2"), phx2("J9", "NTC3"),
        phx3("J10", "1-Wire A"), phx3("J11", "1-Wire B"),
        phx2("J12", "FLOAT1"), phx2("J13", "FLOAT2"), phx2("J14", "FLOAT3"), phx2("J15", "FLOAT4"),
    ],
    small=[
        # isolated probe front-end (2 probes)
        *probe(1, "U9", "J5", "R20", "R21", "R24", "C20"),
        *probe(2, "U9", "J6", "R22", "R23", "R25", "C21"),
        C("C22", "100nF"), C("C23", "100nF"),            # bias midpoint filters
        C("C24", "100nF"), C("C25", "4.7uF", C0805),     # ADS1115 decoupling
        C("C26", "100nF"),                               # ADM3260 ISO decouple
        # NTC dividers: fixed R + filter cap per channel
        R("R30", "10k"), C("C30", "100nF"),
        R("R31", "10k"), C("C31", "100nF"),
        R("R32", "10k"), C("C32", "100nF"),
        # 1-Wire: pull-up + series damper + shunt damper per bus
        R("R33", "4.7k"), R("R34", "100R"), C("C33", "100pF"),
        R("R35", "4.7k"), R("R36", "100R"), C("C34", "100pF"),
        # float switch debounce
        C("C35", "100nF"), C("C36", "100nF"), C("C37", "100nF"), C("C38", "100nF"),
    ],
    note=(12, 165, """SENSORS — isolated probes + NTC + 1-Wire + floats.  PLACED, not wired.
 ISOLATION:  U7 ADM3260 = bidirectional I2C isolator + isoPower.  VDD1(5V)/GND1 = MCU side ;  VISO/GNDISO = probe side (ISO_3V3).
   STM32 I2C1 (SCL/SDA) -> U7 side-1 -> side-2 -> U8 ADS1115 I2C (addr 0x48, ADDR->GND).  C26 ISO decouple.
 PROBES (x2, isolated):  BNC J5/J6 center -> bias midpoint (R20/R21, R22/R23 = 100k to VISO/GNDISO) -> U9 OPA2376 buffer
   -> Rser 220R (R24/R25) + Cout 100pF (C20/C21) -> ADS1115 AIN0/1 (probe A), AIN2/3 (probe B).  C24/C25 ADS decouple.
 NTC (x3):  J7/J8/J9 = VDD--NTC--Vsense--Rfix(10k R30/R31/R32)--GND ;  Cfilt 100nF (C30/C31/C32) -> STM32 ADC.
 1-WIRE (x2):  J10/J11 3-pos (VDD/DQ/GND) ;  Rpu 4.7k (R33/R35) DQ--3V3 ;  Rdmp 100R (R34/R36) + Cdmp 100pF (C33/C34) for long cable.
 FLOATS (x4):  J12..J15 2-pos -> STM32 GPIO ;  debounce Cdb 100nF (C35..C38) GPIO--GND."""))


# ============================ generate =======================================
K.build(
    project="sensorbuddy", proj_dir=PROJ_DIR, root_uuid=ROOT_UUID,
    title=dict(title="ReefVolt SensorBuddy — Main", date="2026-07-04", rev="0.1",
               company="blueAcro / ReefVolt",
               comments=["Aquarium sensor interface — CAN master of the SensorBuddy cluster",
                         "ESP32-S3 + STM32G0B1 + isolated pH/ORP + NTC + 1-Wire + floats"]),
    sheets=[MAIN, PSU, SENSORS],
)
