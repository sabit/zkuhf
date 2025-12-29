import time
import hid
from .exceptions import ZkUhfError

VID = 0x0416
PID = 0xB00B
INTERFACE_NUMBER = 0
REPORT_LEN = 64

def _pad(cmd: bytes) -> bytes:
    return cmd + bytes(REPORT_LEN - len(cmd))

# === Commands (verified from capture) ===
CMD_CONNECT  = _pad(bytes.fromhex("AA FF DC 01 00 01 BF 84 55"))
CMD_WORKMODE = _pad(bytes.fromhex("AA FF EF 00 00 01 E1 55"))
CMD_ANTENNA  = _pad(bytes.fromhex("AA FF ED 00 00 A0 21 55"))
CMD_POWER    = _pad(bytes.fromhex("AA FF EB 00 00 40 20 55"))
CMD_READ     = _pad(bytes.fromhex("AA FF F6 00 00 D0 26 55"))


class ZkUhfReader:
    """
    ZKTeco / Winbond UHF reader (Linux, HID)

    Usage:
        r = ZkUhfReader()
        r.connect()
        card = r.read_once()
        r.close()
    """

    def __init__(self):
        self._dev: hid.Device | None = None

    # ----------------------------
    # Low-level helpers
    # ----------------------------

    def _send(self, cmd: bytes, delay: float = 0.05):
        # HID interrupt OUT with report ID 0x00
        self._dev.write(b"\x00" + cmd)
        time.sleep(delay)

    # ----------------------------
    # Public API
    # ----------------------------

    def connect(self):
        """Open device and run CONNECT sequence (mandatory)."""
        for d in hid.enumerate(VID, PID):
            if d.get("interface_number") == INTERFACE_NUMBER:
                self._dev = hid.Device(path=d["path"])
                self._dev.nonblocking = True
                break
        else:
            raise ZkUhfError("UHF reader not found")

        # CONNECT sequence (exact demo behavior)
        self._send(CMD_CONNECT)
        self._send(CMD_WORKMODE)
        self._send(CMD_ANTENNA)
        self._send(CMD_POWER)

    def close(self):
        if self._dev:
            self._dev.close()
            self._dev = None

    def read_once(self, timeout: float = 1.5) -> str | None:
        """
        Perform a single inventory round.
        Returns 8-digit card number or None.
        """
        if not self._dev:
            raise ZkUhfError("Reader not connected")

        self._send(CMD_READ, delay=0.01)

        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self._dev.read(REPORT_LEN)
            if data:
                card = self._decode_card_number(bytes(data))
                if card:
                    return card
            time.sleep(0.01)

        return None

    # ----------------------------
    # EPC decoding (final, correct)
    # ----------------------------

    @staticmethod
    def _decode_card_number(data: bytes) -> str | None:
        """
        Decode card number from EPC frame.
        Rule:
        - Use EPC payload length
        - Extract 3-byte values
        - Select value that appears twice
        """
        if len(data) < 8 or data[0] != 0xAA or data[2] != 0xC8:
            return None

        epc_len = data[3]
        epc = data[4:4 + epc_len]

        candidates = []
        for i in range(len(epc) - 2):
            v = int.from_bytes(epc[i:i+3], "big")
            if 1 <= v <= 50_000_000:
                candidates.append(v)

        for v in set(candidates):
            if candidates.count(v) >= 2:
                return f"{v:08d}"

        return None

