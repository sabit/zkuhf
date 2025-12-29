import hid
import time

VID = 0x0416
PID = 0xB00B
INTERFACE = 0
REPORT_LEN = 64

def pad(cmd):
    return cmd + bytes(REPORT_LEN - len(cmd))

CMD_CONNECT  = pad(bytes.fromhex("AA FF DC 01 00 01 BF 84 55"))
CMD_WORKMODE = pad(bytes.fromhex("AA FF EF 00 00 01 E1 55"))
CMD_ANTENNA  = pad(bytes.fromhex("AA FF ED 00 00 A0 21 55"))
CMD_POWER    = pad(bytes.fromhex("AA FF EB 00 00 40 20 55"))
CMD_READ     = pad(bytes.fromhex("AA FF F6 00 00 D0 26 55"))

def decode_card_number(data: bytes) -> str | None:
    # Must be EPC inventory frame
    if len(data) < 8 or data[0] != 0xAA or data[2] != 0xC8:
        return None

    epc_len = data[3]
    epc_start = 4
    epc_end = epc_start + epc_len

    if len(data) < epc_end:
        return None

    epc = data[epc_start:epc_end]

    candidates = []

    # slide 3-byte window across EPC payload
    for i in range(len(epc) - 2):
        val = int.from_bytes(epc[i:i+3], "big")
        if 1 <= val <= 50_000_000:
            candidates.append(val)

    if not candidates:
        return None

    # choose the value that repeats
    for v in set(candidates):
        if candidates.count(v) >= 2:
            return f"{v:08d}"

    return None

def main():
    for d in hid.enumerate(VID, PID):
        if d.get("interface_number") == INTERFACE:
            dev = hid.Device(path=d["path"])
            dev.nonblocking = True
            break
    else:
        raise RuntimeError("Reader not found")

    def send(cmd):
        dev.write(b"\x00" + cmd)
        time.sleep(0.05)

    # CONNECT sequence (once)
    send(CMD_CONNECT)
    send(CMD_WORKMODE)
    send(CMD_ANTENNA)
    send(CMD_POWER)

    print("Connected. Press Enter to READ (Ctrl+C to exit).")

    try:
        while True:
            input()
            send(CMD_READ)

            end = time.time() + 1.5
            while time.time() < end:
                data = dev.read(REPORT_LEN)
                if data and data[2] == 0xC8:
                    card = decode_card_number(bytes(data))
                    if card:
                        print("CARD:", card)
                    else:
                        print("EPC:", bytes(data).hex())
                time.sleep(0.01)
    finally:
        dev.close()

if __name__ == "__main__":
    main()

