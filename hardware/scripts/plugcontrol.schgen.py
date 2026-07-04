#!/usr/bin/env python3
"""PlugControl manifest — generates the schematic with parts PLACED (not wired).

Second actuation PCB in the reefvolt-sensorbuddy repo (alongside sensorbuddy +
drycontact); shares this repo's engine (scripts/kschgen.py), Makefile, and lib
tables.

PlugControl is a 2-channel AC heater carrier on the SensorBuddy CAN cluster. It
reuses the line's shared core (STM32G0B1 + TCAN1044 + TPS54202 + LM1117 + USBLC6
— custom symbols already in lib/symbols/sensorbuddy.kicad_sym) and adds:
  * 2x SSR (Panasonic AQH / Sharp S216, zero-cross) for per-channel switching,
  * a master mechanical relay (Omron G5LE-14-DC5) upstream of both SSRs as a
    diverse-technology backup cutoff, driven by an AO3400 FET,
  * 2x low-side current sense (INA181A1 + shunt) for welded-relay / open-heater
    detection,
  * an INDEPENDENT analog safety chain (REF3330 ref + own NTC divider, TLV3202
    dual comparator window, 74HC74 SR latch with POR-to-fault, 74HC08 AND gating
    tree, TPS3823 watchdog) that kills all outputs regardless of MCU/CAN state.
Default state at power-on is everything OFF. See hardware/plugcontrol/DESIGN.md
for the full architecture + BOM rationale.

Substitutions where KiCad has no exact bundled symbol (value/LCSC/MPN carry the
real part — the symbol is cosmetic for a placed-not-wired skeleton):
  * TLV3202 dual comparator  -> Comparator:LMV393     (dual comparator, SOIC-8)
  * SN74HC08 quad AND        -> 74xx:74LS08           (same 74x08 pinout)
  * REF3330 3.0V reference   -> Reference_Voltage:REF3030 (3.0V SOT-23-3)
  * TPS3823-33 watchdog      -> Power_Supervisor:TPS3823-xxDBV
  * SSR (Panasonic AQH/S216) -> Relay_SolidState:AQH0213A  (footprint TBD, DIP-6)

Sheets: MCU (STM32/CAN/USB/power), Safety (analog interlock), Actuation (SSRs +
master relay + current sense + gating). Components are PLACED, not wired — wire
them in eeschema using the per-sheet notes as the spec. Regenerate BEFORE wiring;
regen reassigns UUIDs.  `make gen-plugcontrol`
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kschgen as K

HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # hardware/
PROJ_DIR = os.path.join(HW, "plugcontrol")
SB_SYM = os.path.join(HW, "lib", "symbols", "sensorbuddy.kicad_sym")
ROOT_UUID = "c0000000-0000-4c01-8000-000000000001"   # keep stable across regens

# ---- symbol libraries -------------------------------------------------------
K.register_stdlib("Device", "R", "C", "L", "LED", "D", "D_Schottky")
K.register_stdlib("Comparator", "LMV393")                     # ~ TLV3202 (dual)
K.register_stdlib("74xx", "74HC74", "74LS08")                 # SR latch + AND (~74HC08)
K.register_stdlib("Reference_Voltage", "REF3030")             # ~ REF3330 (3.0V)
K.register_stdlib("Power_Supervisor", "TPS3823-xxDBV")        # MCU watchdog
K.register_stdlib("Amplifier_Current", "INA181")             # current-sense amp
K.register_stdlib("Relay", "G5LE-1")                          # master mechanical relay
K.register_stdlib("Relay_SolidState", "AQH0213A")            # ~ SSR (Panasonic AQH / Sharp S216)
K.register_stdlib("Transistor_FET", "AO3400A")               # relay-coil driver FET
K.register_stdlib("Connector", "USB_C_Receptacle_USB2.0_16P")
K.register_stdlib("Connector_Generic", "Conn_01x02", "Conn_01x03", "Conn_02x03_Odd_Even")
# shared line parts — custom symbols already in the project lib
K.register_lib("sensorbuddy", SB_SYM,
               "STM32G0B1KBU6", "TCAN1044VDRQ1", "TPS54202DDCR",
               "LM1117IMP-3.3", "USBLC6-4SC6")

# ---- footprint shorthands ---------------------------------------------------
R0402  = "Resistor_SMD:R_0402_1005Metric"
R0603  = "Resistor_SMD:R_0603_1608Metric"          # safety-chain 0.1% precision
R2512  = "Resistor_SMD:R_2512_6332Metric"          # current-sense shunt (1W)
C0402  = "Capacitor_SMD:C_0402_1005Metric"
C0805  = "Capacitor_SMD:C_0805_2012Metric"
C1210  = "Capacitor_SMD:C_1210_3225Metric"
LED0402 = "LED_SMD:LED_0402_1005Metric"
SOT23   = "Package_TO_SOT_SMD:SOT-23"              # 3-pin (REF3030, AO3400)
SOT235  = "Package_TO_SOT_SMD:SOT-23-5"            # TPS3823 watchdog
SOT236  = "Package_TO_SOT_SMD:SOT-23-6"            # TPS54202, USBLC6, INA181
SOT2233 = "Package_TO_SOT_SMD:SOT-223-3_TabPin2"   # LM1117
SOIC8   = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"    # TCAN1044, TLV3202
SOIC14  = "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm"   # 74HC74, 74HC08
QFN32   = "sensorbuddy:UFQFPN-32"                  # custom fp + STM32_UFQFPN-32 3D model
SMA     = "Diode_SMD:D_SMA"
SOD123  = "Diode_SMD:D_SOD-123"
SRN4018 = "Inductor_SMD:L_Bourns-SRN4018"
RELAY   = "Relay_THT:Relay_SPDT_Omron-G5LE-1"      # master mechanical relay
SSRFP   = "Package_DIP:DIP-6_W7.62mm"              # SSR placeholder (final part TBD)
USBC    = "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12"
UFIT6   = "Connector_Molex:Molex_Micro-Fit_3.0_43045-0612_2x03_P3.00mm_Vertical"
PHX2    = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MPT-0,5-2-2.54_1x02_P2.54mm_Horizontal"
MKDS3   = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal"  # mains screw, L/N/PE

RLCSC = {"5.1k": "C27834", "10k": "C25744", "100k": "C25741", "22.1k": "C25765",
         "1k": "C11702", "4.7k": "C25900", "0R": "C17168", "100R": "C106232"}
CLCSC = {"100nF": "C1525", "1uF": "C29266", "10uF": "C15850",
         "22uF": "C45783", "4.7uF": "C1611"}


def R(ref, val, fp=R0402, **kw):
    return dict(ref=ref, lib_id="Device:R", value=val, fp=fp,
                lcsc=RLCSC.get(val, ""), **kw)


def C(ref, val, fp=C0402, **kw):
    return dict(ref=ref, lib_id="Device:C", value=val, fp=fp,
                lcsc=CLCSC.get(val, ""), **kw)


# ============================ MCU / CAN / Power sheet ========================
MCU = dict(name="MCU", file="mcu.kicad_sch",
    title="MCU (STM32G0B1) / FDCAN (TCAN1044) / USB-C / 12-24V->5V->3V3 x2", page="2",
    big=[
        dict(ref="U1", lib_id="sensorbuddy:STM32G0B1KBU6", value="STM32G0B1KBU6",
             fp=QFN32, lcsc="C5159549", mpn="STM32G0B1KBU6N", mfr="ST"),
        dict(ref="U2", lib_id="sensorbuddy:TCAN1044VDRQ1", value="TCAN1044VDRQ1",
             fp=SOIC8, lcsc="C1852061", mpn="TCAN1044VDRQ1", mfr="TI"),
        dict(ref="U3", lib_id="sensorbuddy:USBLC6-4SC6", value="USBLC6-4SC6",
             fp=SOT236, lcsc="C5197386", mpn="USBLC6-4SC6", mfr="ST"),
        dict(ref="U4", lib_id="sensorbuddy:TPS54202DDCR", value="TPS54202DDCR",
             fp=SOT236, lcsc="C191884", mpn="TPS54202DDCR", mfr="TI"),
        dict(ref="U5", lib_id="sensorbuddy:LM1117IMP-3.3", value="LM1117-3.3 (MCU)",
             fp=SOT2233, lcsc="C23984", mpn="LM1117IMPX-3.3/NOPB", mfr="TI"),
        dict(ref="U6", lib_id="sensorbuddy:LM1117IMP-3.3", value="LM1117-3.3 (safety)",
             fp=SOT2233, lcsc="C23984", mpn="LM1117IMPX-3.3/NOPB", mfr="TI"),
        dict(ref="J1", lib_id="Connector:USB_C_Receptacle_USB2.0_16P",
             value="USB-C prog/pwr", fp=USBC, lcsc="C165948",
             mpn="TYPE-C-31-M-12", mfr="Korean Hroparts"),
        dict(ref="J2", lib_id="Connector_Generic:Conn_02x03_Odd_Even",
             value="CAN Micro-Fit 6p", fp=UFIT6, lcsc="", mpn="43045-0612", mfr="Molex"),
        dict(ref="J3", lib_id="Connector_Generic:Conn_01x02",
             value="DC IN 12-24V", fp=PHX2, lcsc="", mpn="MPT-0,5/2-2,54", mfr="Phoenix"),
    ],
    small=[
        C("C1", "100nF"), C("C2", "100nF"), C("C3", "100nF"),   # STM32 VDD decouple
        C("C4", "4.7uF", C0805),                                # STM32 VDD bulk
        C("C5", "100nF"),                                       # VDDA / VREF+
        C("C6", "100nF"),                                       # TCAN1044 VCC decouple
        C("C7", "100nF"),                                       # NRST
        C("C8", "100nF"),                                       # TCAN VIO / USBLC6
        R("R1", "5.1k"), R("R2", "5.1k"),                       # USB-C CC1/CC2 (UFP)
        R("R3", "10k"),                                         # BOOT0 pulldown
        R("R4", "10k"),                                         # NRST pullup
        R("R7", "120R"),                                        # CAN termination (end node only)
        dict(ref="D2", lib_id="Device:LED", value="PWR grn", fp=LED0402,
             lcsc="C72043", mpn="KT-0402G", mfr="Hubei KENTO"),
        R("R5", "1k"),                                          # PWR LED series
        dict(ref="D3", lib_id="Device:LED", value="STAT blu", fp=LED0402,
             lcsc="C72041", mpn="KT-0402B", mfr="Hubei KENTO"),
        R("R6", "1k"),                                          # STAT LED series
        # --- 12-24V -> 5V buck (TPS54202) ---
        dict(ref="L1", lib_id="Device:L", value="4.7uH", fp=SRN4018,
             lcsc="C408412", mpn="SRN4018-4R7M", mfr="Bourns"),
        dict(ref="D1", lib_id="Device:D_Schottky", value="SS14", fp=SMA,
             lcsc="C2480", mpn="SS14", mfr="MDD"),                  # reverse polarity
        C("C10", "4.7uF", C1210),                                  # buck VIN
        C("C11", "22uF", C1210),                                   # buck VOUT (5V)
        C("C12", "100nF"),                                         # buck bootstrap
        R("R10", "100k"), R("R11", "22.1k"),                       # buck FB divider -> 5V
        # --- dual 5V -> 3V3 LDO (MCU rail + independent safety rail) ---
        C("C13", "22uF", C1210),                                   # LDO1 3V3 (MCU)
        C("C14", "22uF", C1210),                                   # LDO2 3V3A (safety)
        C("C15", "100nF"), C("C16", "100nF"),                      # LDO in bypass
    ],
    note=(12, 150, """MCU/CAN/PWR — STM32G0B1KBU6 (UFQFPN-32) FDCAN node + power tree.  PLACED, not wired.
 CAN:   PB9 FDCAN_TX -> U2.1 (TXD)   PB8 FDCAN_RX <- U2.4 (RXD)   U2: 3=VCC(5V,C6) 2=GND 8=STBY->GND 7=CANH 6=CANL 5=VIO(3V3)
 J2 Micro-Fit 6p (CAN + bus power):  1=CANH 2=CANL 3=GND 4=V+ (12-24V) 5=GND 6=V+   R7 120R CANH--CANL (end node only)
 USB:   J1 D+/D- -> U3 (USBLC6) -> STM32 PA12/PA11 ;  R1/R2 5.1k CC1/CC2 -> GND (UFP) ;  U3: 1=IO1 2=GND 3=IO2 4=IO2 5=VBUS 6=IO1
 STM32 pwr: VDD/VDDA -> 3V3 (C1..C5) ;  BOOT0 R3 10k -> GND ;  NRST R4 10k -> 3V3 + C7 100nF
 PWR: J3 DC-IN 1=V+ 2=GND ; D1 SS14 reverse-polarity ; U4 TPS54202 (SOT-23-6) 1 BOOT 2 VIN 3 EN 4 GND 5 FB 6 SW
   C10 4.7uF VIN--GND   L1 4.7uH SW--5V   C11 22uF 5V--GND   C12 100nF BOOT--SW   FB: R10 100k 5V--FB, R11 22.1k FB--GND (~5.0V)
 U5 LM1117-3.3 (MCU 3V3, C13 22uF) and U6 LM1117-3.3 (INDEPENDENT safety-chain 3V3A, C14 22uF) — separate LDOs so an MCU-rail
   brownout cannot pull down the safety-chain reference/comparators.  5V -> relay coil + SSR gate + TPS3823 watchdog.
 LEDs: D2 PWR (3V3->R5->D2->GND)   D3 STAT (PAx->R6->D3->GND heartbeat).  Node address auto-assigned from STM32 UID — NO strap."""))

# ============================ Safety sheet ==================================
# Independent analog interlock: REF3330 -> own NTC divider -> TLV3202 window
# -> 74HC74 SR latch (POR to fault) -> SAFETY_OK.  TPS3823 watchdog -> WDT_OK.
SAFETY = dict(name="Safety", file="safety.kicad_sch",
    title="Analog safety chain — REF3330 / NTC window (TLV3202) / SR latch (74HC74) / WDT (TPS3823)", page="3",
    big=[
        dict(ref="U7", lib_id="Reference_Voltage:REF3030", value="REF3330AIDBZT",
             fp=SOT23, lcsc="C2156496", mpn="REF3330AIDBZT", mfr="TI"),        # ~REF3330 3.0V
        dict(ref="U8", lib_id="Comparator:LMV393", value="TLV3202AIDR",
             fp=SOIC8, lcsc="C129325", mpn="TLV3202AIDR", mfr="TI"),           # dual comparator window
        dict(ref="U9", lib_id="74xx:74HC74", value="SN74HC74DR",
             fp=SOIC14, lcsc="C6762", mpn="SN74HC74DR", mfr="TI"),             # SR latch (POR to fault)
        dict(ref="U10", lib_id="Power_Supervisor:TPS3823-xxDBV", value="TPS3823-33",
             fp=SOT235, lcsc="C7719", mpn="TPS3823-33DBVR", mfr="TI"),         # MCU watchdog
        dict(ref="J4", lib_id="Connector_Generic:Conn_01x02",
             value="NTC probe (own)", fp=PHX2, lcsc="", mpn="MPT-0,5/2-2,54", mfr="Phoenix"),
    ],
    small=[
        R("R30", "10k", R0603),        # NTC divider bottom leg (R_FIX, 0.1% 25ppm)
        R("R31", "10k", R0603), R("R32", "10k", R0603),   # FAULT_HOT threshold divider (0.1%)
        R("R33", "100k", R0603), R("R34", "10k", R0603),  # FAULT_OPEN threshold divider (0.1%)
        R("R35", "10k"), R("R36", "10k"),                 # comparator output pull-ups
        R("R37", "100k"),                                 # POR RC (with C20 -> ~10ms)
        R("R38", "10k"),                                  # MCU latch-clear series (gated)
        R("R39", "10k"),                                  # SAFETY_OK readback series
        C("C20", "100nF"),                                # POR cap (RC -> latch=fault at power-on)
        C("C21", "100nF"),                                # 74HC74 VCC decouple
        C("C22", "100nF"),                                # TLV3202 VCC decouple
        C("C23", "100nF"),                                # REF3330 VIN bypass
        C("C24", "1uF"),                                  # REF3330 VOUT bypass
        C("C25", "100nF"),                                # TPS3823 VDD decouple
        dict(ref="D4", lib_id="Device:D", value="1N4148W", fp=SOD123,
             lcsc="C81598", mpn="1N4148W", mfr="Changjiang"),   # diode-OR FAULT_HOT -> latch set
        dict(ref="D5", lib_id="Device:D", value="1N4148W", fp=SOD123,
             lcsc="C81598", mpn="1N4148W", mfr="Changjiang"),   # diode-OR FAULT_OPEN -> latch set
    ],
    note=(12, 145, """Safety — independent analog interlock (works with NO MCU/CAN).  PLACED, not wired.  Powered from 3V3A (U6).
 REF: U7 REF3330 (SOT-23-3) 1=IN(3V3A) 2=GND 3=OUT(3.0V)  C23 100nF IN, C24 1uF OUT.  Divider: 3.0V -> J4/NTC -> V_SENSE -> R30 10k 0.1% -> GND.
 NTC probe is OWN sensor via J4 (2-pos) — NOT on the PCB, NOT shared with SensorBuddy (sensor diversity).
 WINDOW: U8 TLV3202 (~LMV393 sym, SOIC-8).  a: V_SENSE vs V_HOT (R31/R32) -> FAULT_HOT (over-temp).  b: V_SENSE vs V_OPEN (R33/R34) -> FAULT_OPEN.
   R35/R36 10k pull-ups on comparator outputs.  D4/D5 (1N4148W) diode-OR both faults -> latch SET (preset/clr).
 LATCH: U9 74HC74 (½), D tied high, async PRE/CLR as set/reset.  POR: R37 100k + C20 100nF (~10ms) forces latch INTO fault at power-on.
   MCU clear (R38, gated) can only clear when V_SENSE < V_RESET_OK — MCU cannot override a real over-temp.  Q = SAFETY_OK.
 WATCHDOG: U10 TPS3823-33 (SOT-23-5) 1=VDD(5V) 2=GND 3=WDI(<-STM32 heartbeat >=10Hz) 4=/RESET 5=/MR.  /RESET -> WDT_OK.  C25 100nF.
   Powered from 5V (independent of MCU LDO).  SAFETY_OK (R39) read back by STM32 ADC/GPIO.  SAFETY_OK & WDT_OK feed the Actuation AND tree."""))

# ============================ Actuation sheet ===============================
# 2x SSR (heater switch) downstream of a master mechanical relay; per-channel
# low-side current sense; 74HC08 AND gates the kill chain into every actuator.
ACT = dict(name="Actuation", file="actuation.kicad_sch",
    title="Actuation — 2x SSR + master relay (G5LE) + 2x INA181 current sense + 74HC08 gating", page="4",
    big=[
        dict(ref="U11", lib_id="74xx:74LS08", value="SN74HC08DR",
             fp=SOIC14, lcsc="C337768", mpn="SN74HC08DR", mfr="TI"),           # ~74HC08 quad AND (gating)
        dict(ref="U12", lib_id="Amplifier_Current:INA181", value="INA181A1IDBVR",
             fp=SOT236, lcsc="C2058943", mpn="INA181A1IDBVR", mfr="TI"),       # CH_A current sense
        dict(ref="U13", lib_id="Amplifier_Current:INA181", value="INA181A1IDBVR",
             fp=SOT236, lcsc="C2058943", mpn="INA181A1IDBVR", mfr="TI"),       # CH_B current sense
        dict(ref="K1", lib_id="Relay:G5LE-1", value="G5LE-14 5VDC",
             fp=RELAY, lcsc="C116963", mpn="G5LE-14 DC5", mfr="Omron"),        # master mechanical relay (backup cutoff)
        dict(ref="K2", lib_id="Relay_SolidState:AQH0213A", value="SSR AQH/S216 (TBD)",
             fp=SSRFP, lcsc="", mpn="AQH0213 / S216S02", mfr="Panasonic/Sharp"),   # SSR_A
        dict(ref="K3", lib_id="Relay_SolidState:AQH0213A", value="SSR AQH/S216 (TBD)",
             fp=SSRFP, lcsc="", mpn="AQH0213 / S216S02", mfr="Panasonic/Sharp"),   # SSR_B
        dict(ref="Q1", lib_id="Transistor_FET:AO3400A", value="AO3400A",
             fp=SOT23, lcsc="C20917", mpn="AO3400A", mfr="AOS"),               # master relay coil driver
        dict(ref="J5", lib_id="Connector_Generic:Conn_01x03",
             value="AC IN L/N/PE", fp=MKDS3, lcsc="", mpn="MKDS-1,5/3-5,08", mfr="Phoenix"),
        dict(ref="J6", lib_id="Connector_Generic:Conn_01x03",
             value="AC OUT A L/N/PE", fp=MKDS3, lcsc="", mpn="MKDS-1,5/3-5,08", mfr="Phoenix"),
        dict(ref="J7", lib_id="Connector_Generic:Conn_01x03",
             value="AC OUT B L/N/PE", fp=MKDS3, lcsc="", mpn="MKDS-1,5/3-5,08", mfr="Phoenix"),
    ],
    small=[
        dict(ref="R50", lib_id="Device:R", value="50mR 1W", fp=R2512, lcsc="", mpn="", mfr=""),  # CH_A shunt
        dict(ref="R51", lib_id="Device:R", value="50mR 1W", fp=R2512, lcsc="", mpn="", mfr=""),  # CH_B shunt
        dict(ref="D6", lib_id="Device:D_Schottky", value="SS14", fp=SMA,
             lcsc="C2480", mpn="SS14", mfr="MDD"),                             # master relay coil flyback
        R("R54", "100k"),                                  # Q1 gate pulldown (default OFF)
        R("R55", "100R"),                                  # Q1 gate series
        R("R56", "470R"), R("R57", "470R"),                # SSR input-LED series (5V drive)
        R("R58", "10k"), R("R59", "10k"),                  # SSR gate pulldowns (default OFF)
        R("R60", "10k"), R("R61", "10k"),                  # MCU_CMD_A/B pulldowns into AND
        C("C30", "100nF"), C("C31", "100nF"),              # INA181 VS decouple
        C("C34", "100nF"),                                 # 74HC08 VCC decouple
        dict(ref="D7", lib_id="Device:LED", value="CH_A", fp=LED0402, lcsc="C72041", mpn="KT-0402B", mfr="KENTO"),
        dict(ref="D8", lib_id="Device:LED", value="CH_B", fp=LED0402, lcsc="C72041", mpn="KT-0402B", mfr="KENTO"),
        R("R62", "1k"), R("R63", "1k"),                    # channel status LED series
    ],
    note=(12, 150, """Actuation — 2x SSR downstream of a master mechanical relay + per-ch current sense.  PLACED, not wired.  DEFAULT = ALL OFF.
 AC PATH:  J5 AC-IN(L) -> K1 master relay (G5LE, NO) -> node -> K2 SSR_A -> J6 OUT_A(L) ;  same node -> K3 SSR_B -> J7 OUT_B(L).
   N and PE pass straight through J5->J6/J7.  Maintain >=6mm creepage; keep AC copper wide + short (see DESIGN Layout Notes).
 GATING (U11 74HC08 quad AND, kill chain into every actuator):
   K1 master coil:  AND(SAFETY_OK, WDT_OK) -> Q1 gate (R55 series, R54 100k pulldown) ; coil low-side -> Q1 drain, high-side 5V ; D6 SS14 flyback.
   K2 SSR_A gate :  AND(SAFETY_OK, WDT_OK, MCU_CMD_A) -> R56 470R -> SSR_A input LED ; R58 10k pulldown.  (3-input via two AND stages)
   K3 SSR_B gate :  AND(SAFETY_OK, WDT_OK, MCU_CMD_B) -> R57 470R -> SSR_B input LED ; R59 10k pulldown.
   MCU_CMD_A/B pulled down by R60/R61 10k (OFF if MCU floats).  C34 100nF U11 decouple.
 CURRENT SENSE (low side, between SSR out and N return, Kelvin to INA):  R50/R51 50mR 1W (2512).
   U12 INA181A1 (gain 20) CH_A: IN+/IN- across R50, OUT -> STM32 ADC ;  U13 CH_B across R51.  C30/C31 100nF VS.  50mR*0.6A*20 ~= 600mV.
   FW: current when MCU_CMD OFF => welded SSR/relay -> drop K1, latch, refuse re-enable.  No current when ON => open heater -> log/report.
 STATUS: D7/D8 (+R62/R63 1k) mirror per-channel drive.  SSR (K2/K3) footprint is a DIP-6 PLACEHOLDER — final Panasonic AQH / Sharp S216 pinout TBD."""))


# ============================ generate =======================================
K.build(
    project="plugcontrol", proj_dir=PROJ_DIR, root_uuid=ROOT_UUID,
    title=dict(title="ReefVolt PlugControl — 2ch AC heater carrier", date="2026-07-04", rev="0.1",
               company="blueAcro / ReefVolt",
               comments=["2-channel AC heater carrier with independent hardware safety interlock",
                         "STM32G0B1 + TCAN1044; 2x SSR + master G5LE relay; analog safety chain (REF3330/TLV3202/74HC74/74HC08/TPS3823)"]),
    sheets=[MCU, SAFETY, ACT],
)
