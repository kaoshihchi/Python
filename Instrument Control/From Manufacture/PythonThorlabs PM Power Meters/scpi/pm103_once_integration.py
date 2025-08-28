# pm103_once_integration.py
# One-shot 0.1 s energy integration (PM103 + S120VC) using fast mode
# Requires: anyvisa 0.3.x

import time, struct
from anyvisa import AnyVisa

# --- user settings (adjust the wavelength to match your S120VC/laser) ---
RESOURCE = "USB0::0x1313::0x807A::M00847676::INSTR"   # your PM103 (USBTMC INSTR)
WAVELENGTH_NM = 532                                   # <-- set your laser wavelength (nm)
INTEGRATION_S = 0.1                                   # 0.1 s integration window

def find_device(resource_substr: str):
    for d in AnyVisa.FindResources("?*"):
        if resource_substr in str(d):
            return d
    raise RuntimeError(f"Device not found: {resource_substr}")

def parse_pm103_fast(buf: bytes):
    """
    PM103 fast fetch format: ASCII prefix until first ',' then repeated tuples:
      <uint32 little-endian timestamp_us> <float32 little-endian power_W>
    Returns: list[(t_us:int, power_W:float)]
    """
    if not buf:
        return []
    # empty-frame flag (first byte '0')
    if buf[:1] == b'0':
        return []
    i = buf.find(b',')
    if i < 0:
        return []
    i += 1
    out = []
    end = len(buf)
    while i + 8 <= end:
        t_us = struct.unpack('<I', buf[i:i+4])[0]
        p_w  = struct.unpack('<f', buf[i+4:i+8])[0]
        out.append((t_us, p_w))
        i += 8
    return out

def integrate_trapz(samples):
    """
    samples: list[(t_us, p_w)] covering at least INTEGRATION_S seconds span.
    Returns energy in joules via trapezoidal integration.
    """
    if len(samples) < 2:
        return 0.0
    E = 0.0
    for k in range(len(samples) - 1):
        t0, p0 = samples[k]
        t1, p1 = samples[k+1]
        dt_s = (t1 - t0) * 1e-6
        if dt_s > 0:
            E += 0.5 * (p0 + p1) * dt_s
    return E

def main():
    dev = find_device(RESOURCE)
    with dev as pm:
        # --- identify & clear ---
        pm.write("*CLS\n")
        try:
            idn = pm.auto_query("*IDN?\n")
            print("IDN:", idn.strip() if idn else "<no response>")
        except Exception as e:
            print("IDN query warning:", e)

        # --- basic sensor setup (per manual) ---
        # set wavelength for S120VC calibration curve
        pm.write(f"SENS:CORR:WAV {WAVELENGTH_NM}\n")
        # ensure power unit is watts and enable autorange
        pm.write("SENS:POW:UNIT W\n")
        pm.write("SENS:POW:RANG:AUTO 1\n")

        # --- fast mode: power stream + reset FIFO ---
        pm.write("ACQ:FAST:POW\n")
        pm.write("ACQ:FAST:RESET\n")

        # optional: small warm-up fetch
        pm.write("ACQ:FAST:FETC?\n")
        time.sleep(0.05)
        _ = pm.read_bytes(4096)

        # --- acquire until span >= INTEGRATION_S ---
        collected = []
        t_start = None
        deadline_s = 2.0  # safety (don’t wait forever if nothing arrives)
        t0 = time.perf_counter()
        while True:
            pm.write("ACQ:FAST:FETC?\n")
            time.sleep(0.02)  # give the device a moment to answer
            buf = pm.read_bytes(4096)
            block = parse_pm103_fast(buf)
            if block:
                if t_start is None:
                    t_start = block[0][0]  # first tuple timestamp
                # keep only tuples within [t_start, t_start + INTEGRATION_S]
                t_end = t_start + int(INTEGRATION_S * 1e6)
                for t_us, p_w in block:
                    if t_us >= t_start:
                        collected.append((t_us, p_w))
                    # optional early stop if latest timestamp passes end of window
                if collected and collected[-1][0] >= t_end:
                    # cut to exact window (≤ end)
                    collected = [tp for tp in collected if tp[0] <= t_end]
                    break
            if time.perf_counter() - t0 > deadline_s:
                print("Timeout waiting for enough fast data; integrating whatever was collected.")
                break

        # --- integrate once over the 0.1 s window ---
        # (guard against empty/too-short capture)
        if not collected:
            print("No samples captured.")
            return
        # make sure samples are sorted (should already be)
        collected.sort(key=lambda x: x[0])
        energy_j = integrate_trapz(collected)
        print(f"Samples: {len(collected)}  |  Span: {(collected[-1][0]-collected[0][0])*1e-6:.4f} s")
        print(f"Pulse energy over {INTEGRATION_S:.3f} s = {energy_j:.6e} J")

if __name__ == "__main__":
    main()
