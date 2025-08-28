# probe_pm103.py
import time
from anyvisa import AnyVisa

TARGET = "USB0::0x1313::0x807A::M00847676::INSTR"  # your PM103

devs = AnyVisa.FindResources("?*")
dev = next(d for d in devs if TARGET in str(d))

with dev as pm:                         # open the VISA session
    pm.write("*CLS\n")
    pm.write("*IDN?\n")                 # try LF
    time.sleep(0.2)
    print("IDN (LF):", pm.read_bytes(512))

    pm.write("*IDN?\r\n")               # try CRLF as well
    time.sleep(0.2)
    print("IDN (CRLF):", pm.read_bytes(512))

    pm.write("SYST:ERR?\n")
    time.sleep(0.2)
    print("SYST:ERR?:", pm.read_bytes(512))
