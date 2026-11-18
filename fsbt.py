#!/usr/bin/env python3
"""
fsbt.py - control a Philips ORT7500 (Frontier Silicon "NetRemote") radio over Bluetooth SPP.

Protocol reverse-engineered from com.philips.cl.dabradio 1.0.0 (Philips DigitalRadio app),
library com.frontier_silicon.NetRemoteLib.RadioBluetooth. Pure Python stdlib, Linux only
(uses AF_BLUETOOTH / BTPROTO_RFCOMM).

  python3 fsbt.py AA:BB:CC:DD:EE:FF get sys.power
  python3 fsbt.py AA:BB:CC:DD:EE:FF set sys.power ON
  python3 fsbt.py AA:BB:CC:DD:EE:FF set sys.audio.volume 12
  python3 fsbt.py AA:BB:CC:DD:EE:FF list sys.caps.validModes
  python3 fsbt.py AA:BB:CC:DD:EE:FF dump          # read every readable scalar node
  python3 fsbt.py AA:BB:CC:DD:EE:FF listen        # print notifications from the radio
  python3 fsbt.py - set sys.power ON              # '-' = offline: just print the bytes
  python3 fsbt.py - nodes                         # list known nodes
"""
import argparse, socket, sys, time

# name (without "netRemote.") : (address, read_only, [(field, type, maxlen)], enum-or-None)
NODES = {
    'nav.action.dabPrune': (0x1020A040, False, [(None, 'E8', None)], ['IDLE', 'PRUNE']),
    'nav.action.dabScan': (0x1020A050, False, [(None, 'E8', None)], ['IDLE', 'SCAN']),
    'nav.action.navigate': (0x1020A010, False, [(None, 'U32', None)], None),
    'nav.action.selectItem': (0x1020A020, False, [(None, 'U32', None)], None),
    'nav.action.selectPreset': (0x1020A030, False, [(None, 'U32', None)], None),
    'nav.caps': (0x10202000, True, [(None, 'U32', None)], None),
    'nav.dabScanUpdate': (0x10209000, True, [(None, 'U32', None)], None),
    'nav.errorStr': (0x10204000, True, [(None, 'C8', 128)], None),
    'nav.list': (0x10206000, True, [('key', 'U32', 1), ('name', 'C8', 766), ('type', 'E8', 1), ('subType', 'E8', 1)], None),
    'nav.numItems': (0x10205000, True, [(None, 'S32', None)], None),
    'nav.presets': (0x10207000, True, [('key', 'U32', 1), ('name', 'C8', 65)], None),
    'nav.searchTerm': (0x10208000, False, [(None, 'C8', 256)], None),
    'nav.state': (0x10201000, False, [(None, 'E8', None)], ['OFF', 'ON']),
    'nav.status': (0x10203000, True, [(None, 'E8', None)], ['WAITING', 'READY', 'FAIL', 'FATAL_ERR', 'READY_ROOT']),
    'play.addPreset': (0x1030E000, False, [(None, 'U32', None)], None),
    'play.caps': (0x10302000, True, [(None, 'U32', None)], None),
    'play.control': (0x10305000, False, [(None, 'E8', None)], ['STOP', 'PLAY', 'PAUSE', 'NEXT', 'PREVIOUS']),
    'play.errorStr': (0x10303000, True, [(None, 'C8', 128)], None),
    'play.feedback': (0x10308000, False, [(None, 'E8', None)], ['IDLE', 'POSITIVE', 'NEGATIVE']),
    'play.frequency': (0x1030C000, False, [(None, 'U32', None)], None),
    'play.info.album': (0x10304050, True, [(None, 'C8', 129)], None),
    'play.info.artist': (0x10304040, True, [(None, 'C8', 129)], None),
    'play.info.duration': (0x10304030, True, [(None, 'U32', None)], None),
    'play.info.graphicUri': (0x10304060, True, [(None, 'C8', 257)], None),
    'play.info.name': (0x10304010, True, [(None, 'C8', 65)], None),
    'play.info.text': (0x10304020, True, [(None, 'C8', 129)], None),
    'play.position': (0x10307000, False, [(None, 'U32', None)], None),
    'play.rate': (0x10306000, False, [(None, 'S8', None)], None),
    'play.repeat': (0x1030A000, False, [(None, 'E8', None)], ['OFF', 'ON']),
    'play.scrobble': (0x1030B000, False, [(None, 'E8', None)], ['OFF', 'ON']),
    'play.serviceIds.dabEnsembleId': (0x1030F030, True, [(None, 'U16', None)], None),
    'play.serviceIds.dabScids': (0x1030F050, True, [(None, 'U8', None)], None),
    'play.serviceIds.dabServiceId': (0x1030F040, True, [(None, 'U32', None)], None),
    'play.serviceIds.ecc': (0x1030F010, True, [(None, 'U8', None)], None),
    'play.serviceIds.fmRdsPi': (0x1030F020, True, [(None, 'U16', None)], None),
    'play.shuffle': (0x10309000, False, [(None, 'E8', None)], ['OFF', 'ON']),
    'play.signalStrength': (0x1030D000, True, [(None, 'U8', None)], None),
    'play.status': (0x10301000, True, [(None, 'E8', None)], ['IDLE', 'BUFFERING', 'PLAYING', 'PAUSED', 'REBUFFERING', 'ERROR']),
    'sys.audio.eqCustom.param0': (0x10105401, False, [(None, 'S16', None)], None),
    'sys.audio.eqCustom.param1': (0x10105402, False, [(None, 'S16', None)], None),
    'sys.audio.eqCustom.param2': (0x10105403, False, [(None, 'S16', None)], None),
    'sys.audio.eqCustom.param3': (0x10105404, False, [(None, 'S16', None)], None),
    'sys.audio.eqCustom.param4': (0x10105405, False, [(None, 'S16', None)], None),
    'sys.audio.eqLoudness': (0x10105500, False, [(None, 'E8', None)], ['OFF', 'ON']),
    'sys.audio.eqPreset': (0x10105300, False, [(None, 'U8', None)], None),
    'sys.audio.mute': (0x10105200, False, [(None, 'E8', None)], ['NOT_MUTE', 'MUTE']),
    'sys.audio.volume': (0x10105100, False, [(None, 'U8', None)], None),
    'sys.caps.dabFreqList': (0x10102700, True, [('key', 'U32', 1), ('freq', 'U32', 1), ('label', 'C8', 8)], None),
    'sys.caps.eqBands': (0x10102400, True, [('key', 'U32', 1), ('label', 'C8', 32), ('min', 'S16', 1), ('max', 'S16', 1)], None),
    'sys.caps.eqPresets': (0x10102300, True, [('key', 'U32', 1), ('label', 'C8', 32)], None),
    'sys.caps.fmFreqRange.lower': (0x10102601, True, [(None, 'U32', None)], None),
    'sys.caps.fmFreqRange.stepSize': (0x10102603, True, [(None, 'U32', None)], None),
    'sys.caps.fmFreqRange.upper': (0x10102602, True, [(None, 'U32', None)], None),
    'sys.caps.validLang': (0x10102500, True, [('key', 'U32', 1), ('langLabel', 'C8', 32)], None),
    'sys.caps.validModes': (0x10102100, True, [('key', 'U32', 1), ('id', 'C8', 8), ('selectable', 'E8', 1), ('label', 'C8', 32)], None),
    'sys.caps.volumeSteps': (0x10102200, True, [(None, 'U8', None)], None),
    'sys.clock.dst': (0x10107500, False, [(None, 'E8', None)], ['OFF', 'ON']),
    'sys.clock.localDate': (0x10107200, False, [(None, 'C8', 11)], None),
    'sys.clock.localTime': (0x10107300, False, [(None, 'C8', 9)], None),
    'sys.clock.mode': (0x10107600, False, [(None, 'E8', None)], ['_12_HOUR', '_24_HOUR']),
    'sys.clock.source': (0x10107100, False, [(None, 'U8', None)], None),
    'sys.clock.utcOffset': (0x10107400, False, [(None, 'S32', None)], None),
    'sys.info.friendlyName': (0x10101010, False, [(None, 'C8', 33)], None),
    'sys.info.radioId': (0x10101030, True, [(None, 'C8', 18)], None),
    'sys.info.radioPin': (0x10101040, False, [(None, 'C8', 5)], None),
    'sys.info.version': (0x10101020, True, [(None, 'C8', 129)], None),
    'sys.isu.control': (0x10108200, False, [(None, 'E8', None)], ['IDLE', 'UPDATE_FIRMWARE', 'CHECK_FOR_UPDATE']),
    'sys.isu.state': (0x10108100, True, [(None, 'E8', None)], ['IDLE', 'CHECK_IN_PROGRESS', 'UPDATE_AVAILABLE', 'UPDATE_NOT_AVAILABLE']),
    'sys.isu.version': (0x10108300, True, [(None, 'C8', 99)], None),
    'sys.lang': (0x10109000, False, [(None, 'U32', None)], None),
    'sys.mode': (0x10104000, False, [(None, 'U32', None)], None),
    'sys.net.commitChanges': (0x10106500, False, [(None, 'E8', None)], ['NO', 'YES']),
    'sys.net.ipConfig.address': (0x10106302, False, [(None, 'U32', None)], None),
    'sys.net.ipConfig.dhcp': (0x10106301, False, [(None, 'E8', None)], ['NO', 'YES']),
    'sys.net.ipConfig.dnsPrimary': (0x10106305, False, [(None, 'U32', None)], None),
    'sys.net.ipConfig.dnsSecondary': (0x10106306, False, [(None, 'U32', None)], None),
    'sys.net.ipConfig.gateway': (0x10106304, False, [(None, 'U32', None)], None),
    'sys.net.ipConfig.subnetMask': (0x10106303, False, [(None, 'U32', None)], None),
    'sys.net.keepConnected': (0x10106400, False, [(None, 'E8', None)], ['NO', 'YES']),
    'sys.net.wired.interfaceEnable': (0x10106101, False, [(None, 'E8', None)], ['INTERFACE_DISABLE', 'INTERFACE_ENABLE']),
    'sys.net.wired.macAddress': (0x10106102, True, [(None, 'C8', 18)], None),
    'sys.net.wlan.connectedSSID': (0x10106208, True, [(None, 'U8', 32)], None),
    'sys.net.wlan.interfaceEnable': (0x10106201, False, [(None, 'E8', None)], ['INTERFACE_DISABLE', 'INTERFACE_ENABLE']),
    'sys.net.wlan.macAddress': (0x10106202, True, [(None, 'C8', 18)], None),
    'sys.net.wlan.performFCC': (0x10106213, False, [(None, 'E8', None)], ['TEST_STOP', 'TEST_START']),
    'sys.net.wlan.performWPS': (0x1010620E, False, [(None, 'E8', None)], ['WPS_IDLE', 'WPS_PBC', 'WPS_PIN']),
    'sys.net.wlan.region': (0x10106203, False, [(None, 'E8', None)], ['INVALID', 'USA', 'CANADA', 'MOST_OF_EUROPE', 'SPAIN', 'FRANCE', 'JAPAN', 'SINGAPORE']),
    'sys.net.wlan.rssi': (0x1010620C, True, [(None, 'U8', None)], None),
    'sys.net.wlan.scan': (0x10106204, False, [(None, 'E8', None)], ['IDLE', 'SCAN']),
    'sys.net.wlan.scanList': (0x10106205, True, [('key', 'U32', 1), ('ssid', 'U8', 32), ('privacy', 'E8', 1), ('wpsCapability', 'E8', 1)], None),
    'sys.net.wlan.selectAP': (0x10106207, False, [(None, 'U32', None)], None),
    'sys.net.wlan.setAuthType': (0x1010620B, False, [(None, 'E8', None)], ['OPEN', 'PSK', 'WPA', 'WPA2']),
    'sys.net.wlan.setEncType': (0x1010620A, False, [(None, 'E8', None)], ['NONE', 'WEP', 'TKIP', 'AES']),
    'sys.net.wlan.setFccTestChanNum': (0x1010620F, False, [(None, 'U8', None)], None),
    'sys.net.wlan.setFccTestDataRate': (0x10106210, False, [(None, 'E8', None)], ['_1M', '_2M', '_5_5M', '_11M', '_22M', '_6M', '_9M', '_12M', '_18M', '_24M', '_36M', '_48M', '_54M', '_72M']),
    'sys.net.wlan.setFccTestTxDataPattern': (0x10106211, False, [(None, 'U32', None)], None),
    'sys.net.wlan.setFccTestTxPower': (0x10106212, False, [(None, 'U8', None)], None),
    'sys.net.wlan.setFccTxOff': (0x10106214, False, [(None, 'E8', None)], ['TX_ON', 'TX_OFF']),
    'sys.net.wlan.setPassphrase': (0x10106206, False, [(None, 'C8', 65)], None),
    'sys.net.wlan.setSSID': (0x10106209, False, [(None, 'C8', 32)], None),
    'sys.net.wlan.wpsPinRead': (0x1010620D, True, [(None, 'C8', 9)], None),
    'sys.power': (0x10103000, False, [(None, 'E8', None)], ['OFF', 'ON']),
    'sys.rsa.publicKey': (0x1010A200, True, [(None, 'C8', 512)], None),
    'sys.rsa.status': (0x1010A100, True, [(None, 'E8', None)], ['GENERATION_IN_PROGRESS', 'KEY_AVAILABLE']),}

STATUS = {0: 'FS_OK', 1: 'FS_LIST_END', 128: 'FS_PACKET_BAD', 129: 'FS_NODE_DOES_NOT_EXIST',
          130: 'FS_ITEM_DOES_NOT_EXIST', 131: 'FS_NODE_BLOCKED', 133: 'FS_FAIL'}
OP_GET, OP_LIST_GET, OP_LIST_NEXT, OP_SET, OP_LIST_NEXT_MULTI, OP_LIST_PREV_MULTI = 0x00, 0x01, 0x02, 0x04, 0x09, 0x0A
OP_GET_RSP, OP_SET_RSP, OP_ERR_RSP, OP_LIST_RSP, OP_NOTIFY = 0x80, 0x84, 0x87, 0x89, 0xC6
SIZE = {'E8': 1, 'U8': 1, 'S8': 1, 'U16': 2, 'S16': 2, 'U32': 4, 'S32': 4}
SLIP_END, SLIP_ESC, SLIP_ESC_END, SLIP_ESC_ESC = 0xC0, 0xDB, 0xDC, 0xDD
MAGIC = b'Philips_001'  # R.string.btMagicOpeningMsg; library default is b'Frontier-Silicon'
ADDR2NAME = {v[0]: k for k, v in NODES.items()}


def hexs(b): return ' '.join(f'{x:02x}' for x in b)


def checksum(data):
    s1 = s2 = 0
    for b in data:
        s1 = (s1 + b) & 0xFF
        s2 = (s2 + s1) & 0xFF
    return (s1 ^ s2) & 0xFF


def slip_encode(payload):
    body = bytes(payload) + bytes([checksum(payload)])
    out = bytearray([SLIP_END])
    for b in body:
        if b == SLIP_END: out += bytes([SLIP_ESC, SLIP_ESC_END])
        elif b == SLIP_ESC: out += bytes([SLIP_ESC, SLIP_ESC_ESC])
        else: out.append(b)
    out.append(SLIP_END)
    return bytes(out)


def slip_decode(frame):
    out, i = bytearray(), 0
    while i < len(frame):
        b = frame[i]
        if b == SLIP_ESC and i + 1 < len(frame) and frame[i + 1] in (SLIP_ESC_END, SLIP_ESC_ESC):
            out.append(SLIP_END if frame[i + 1] == SLIP_ESC_END else SLIP_ESC); i += 2
        else:
            out.append(b); i += 1
    return bytes(out)


def resolve(name):
    n = name[10:] if name.lower().startswith('netremote.') else name
    for k in NODES:
        if k.lower() == n.lower(): return k
    hits = [k for k in NODES if k.lower().endswith(n.lower())]
    if len(hits) == 1: return hits[0]
    sys.exit(f'unknown/ambiguous node {name!r}' + (f': {hits}' if hits else '') + ' (try: nodes)')


def is_list(node): return len(NODES[node][2]) > 1


def be(v, n, signed=False): return int(v).to_bytes(n, 'big', signed=signed)


def build_get(frame, node):
    return be(frame, 2) + bytes([OP_GET, 1]) + be(NODES[node][0], 4)


def build_list(frame, node, start_key=-1, max_items=255):
    addr, _, fields, _ = NODES[node]
    nf = len(fields) - 1  # 'key' is not requested explicitly
    return (be(frame, 2) + bytes([OP_LIST_NEXT_MULTI]) + be(addr, 4) + be(start_key & 0xFFFFFFFF, 4)
            + bytes([min(max_items, 255), nf]) + bytes(range(1, nf + 1)) + b'\x00\x00')


def encode_value(node, value):
    _, _, fields, enum = NODES[node]
    t = fields[0][1]
    if t == 'C8':
        data = value.encode('utf-8') + b'\x00'
        return be(len(data), 2) + data
    if enum and not value.lstrip('-').isdigit():
        up = [e.upper() for e in enum]
        if value.upper() not in up: sys.exit(f'{node}: value must be one of {enum} or a number')
        v = up.index(value.upper())
    else:
        v = int(value, 0)
    if v < 0 and t.startswith('U'): v &= (1 << (8 * SIZE[t])) - 1  # e.g. -1 -> 0xFFFFFFFF
    return be(SIZE[t], 2) + be(v, SIZE[t], signed=t.startswith('S'))


def build_set(frame, node, value):
    return be(frame, 2) + bytes([OP_SET, 1]) + be(NODES[node][0], 4) + encode_value(node, value)


def decode_field(t, raw, enum=None):
    if t == 'C8': return raw.split(b'\x00')[0].decode('utf-8', 'replace')
    v = int.from_bytes(raw, 'big', signed=t.startswith('S'))
    return f'{v} ({enum[v]})' if enum and 0 <= v < len(enum) else v


def read_field(t, data, p, with_len=True):
    """Returns (raw, new_p). Responses carry a 2-byte length; notifications don't."""
    if with_len:
        n = int.from_bytes(data[p:p + 2], 'big'); p += 2
    elif t == 'C8':
        n = data.index(0, p) + 1 - p if 0 in data[p:] else len(data) - p
    else:
        n = SIZE[t]
    return data[p:p + n], p + n


def decode_packet(pkt, node=None):
    """pkt = unslipped payload without checksum. Returns a human readable dict."""
    frame = int.from_bytes(pkt[0:2], 'big')
    op = pkt[2]
    r = {'frame': frame, 'op': f'0x{op:02x}'}
    if frame == 0:  # notification: 00 00 C6 addr(4) value...
        addr = int.from_bytes(pkt[3:7], 'big')
        node = ADDR2NAME.get(addr, f'0x{addr:08X}')
        r.update(type='notify', node=node)
        if node in NODES and not is_list(node):
            t = NODES[node][2][0][1]
            raw, _ = read_field(t, pkt, 7, with_len=False)
            r['value'] = decode_field(t, raw, NODES[node][3])
        else:
            r['raw'] = hexs(pkt[7:])
        return r
    if op == OP_SET_RSP:  # fr fr 84 01 status
        r.update(type='set-rsp', status=STATUS.get(pkt[4], pkt[4]))
    elif op == OP_GET_RSP:  # fr fr 80 01 status len(2) value
        r.update(type='get-rsp', status=STATUS.get(pkt[4], pkt[4]))
        if pkt[4] == 0 and node:
            t = NODES[node][2][0][1]
            raw, _ = read_field(t, pkt, 5)
            r['value'] = decode_field(t, raw, NODES[node][3])
    elif op == OP_LIST_RSP:  # fr fr 89 status count { key(4) nfields { len(2) data } }
        r.update(type='list-rsp', status=STATUS.get(pkt[3], pkt[3]))
        if pkt[3] in (0, 1) and node and len(pkt) > 4:
            fields = NODES[node][2]
            items, p = [], 5
            for _ in range(pkt[4]):
                item = {'key': int.from_bytes(pkt[p:p + 4], 'big')}; p += 4
                p += 1  # number of fields that follow
                for fname, t, _ in fields[1:]:
                    raw, p = read_field(t, pkt, p)
                    item[fname] = decode_field(t, raw)
                items.append(item)
            r['items'] = items
            r['list_end'] = pkt[3] == 1
    else:
        r.update(type='other', raw=hexs(pkt))
    return r


class Radio:
    def __init__(self, mac, channel=1, verbose=False, timeout=5.0):
        self.v = verbose
        self.frame = 0
        self.buf = bytearray()
        self.s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self.s.settimeout(timeout)
        self.s.connect((mac, channel))
        # The radio greets with a magic string; the app checks it to recognise a radio.
        greet = b''
        try:
            while len(greet) < len(MAGIC):
                c = self.s.recv(len(MAGIC) - len(greet))
                if not c: break
                greet += c
        except socket.timeout:
            pass
        print(f'# connected, greeting: {greet!r}' + ('' if greet == MAGIC else f'  (expected {MAGIC!r})'))

    def _next_frame(self):
        self.frame = self.frame % 0xFFFF + 1  # never 0 (0 is reserved for notifications)
        return self.frame

    def send(self, payload):
        wire = slip_encode(payload)
        if self.v: print(f'TX {hexs(wire)}')
        self.s.sendall(wire)

    def recv_packet(self, timeout=5.0):
        end = time.time() + timeout
        while True:
            if SLIP_END in self.buf:
                i = self.buf.index(SLIP_END)
                frame, self.buf = bytes(self.buf[:i]), self.buf[i + 1:]
                if not frame: continue
                pkt = slip_decode(frame)
                if self.v: print(f'RX {hexs(pkt)}')
                body, cs = pkt[:-1], pkt[-1]
                if cs != checksum(body) and cs != 0xEF:
                    print(f'# checksum mismatch, dropped: {hexs(pkt)}'); continue
                return body
            left = end - time.time()
            if left <= 0: return None
            self.s.settimeout(left)
            try:
                c = self.s.recv(4096)
            except socket.timeout:
                return None
            if not c: raise ConnectionError('radio closed the connection')
            self.buf += c

    def request(self, payload, node):
        frame = int.from_bytes(payload[:2], 'big')
        self.send(payload)
        while True:
            pkt = self.recv_packet()
            if pkt is None: return {'error': 'timeout'}
            if int.from_bytes(pkt[:2], 'big') == 0:
                print('# notify', decode_packet(pkt)); continue
            if int.from_bytes(pkt[:2], 'big') == frame:
                return decode_packet(pkt, node)
            print('# unexpected', hexs(pkt))

    def get(self, node):
        if is_list(node): return self.list(node)
        return self.request(build_get(self._next_frame(), node), node)

    def set(self, node, value):
        return self.request(build_set(self._next_frame(), node, value), node)

    def list(self, node, start_key=-1, max_items=20):
        return self.request(build_list(self._next_frame(), node, start_key, max_items), node)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mac', help="radio Bluetooth address, or '-' for offline (print packets only)")
    ap.add_argument('cmd', choices=['get', 'set', 'list', 'dump', 'listen', 'nodes', 'raw'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('-c', '--channel', type=int, default=1, help='RFCOMM channel (app uses 1)')
    ap.add_argument('-v', '--verbose', action='store_true', help='print raw TX/RX bytes')
    a = ap.parse_args()

    if a.cmd == 'nodes':
        for k, (addr, ro, f, e) in NODES.items():
            typ = ' '.join(f'{n + ":" if n else ""}{t}' for n, t, _ in f)
            print(f'0x{addr:08X} {"RO" if ro else "RW"} {k:42} {typ}' + (f'  {dict(enumerate(e))}' if e else ''))
        return

    if a.mac == '-':  # offline: show what would be sent
        node = resolve(a.args[0])
        p = {'get': lambda: build_list(1, node) if is_list(node) else build_get(1, node),
             'list': lambda: build_list(1, node),
             'set': lambda: build_set(1, node, a.args[1])}[a.cmd]()
        print(f'payload : {hexs(p)}\nchecksum: {checksum(p):02x}\nwire    : {hexs(slip_encode(p))}')
        return

    r = Radio(a.mac, a.channel, a.verbose)
    if a.cmd == 'get':
        for n in a.args: print(resolve(n), r.get(resolve(n)))
    elif a.cmd == 'list':
        n = resolve(a.args[0]); print(n, r.list(n))
    elif a.cmd == 'set':
        n = resolve(a.args[0]); print(n, r.set(n, a.args[1]))
    elif a.cmd == 'raw':  # raw hex payload (without frame/checksum), e.g. "00 01 10 10 30 00"
        r.send(r._next_frame().to_bytes(2, 'big') + bytes.fromhex(''.join(a.args)))
        print(r.recv_packet())
    elif a.cmd == 'dump':
        for n, (addr, ro, f, e) in NODES.items():
            if len(f) == 1 and not n.startswith(('sys.net.wlan.setFcc', 'sys.net.wlan.performFCC')):
                print(f'{n:42}', r.get(n))
    elif a.cmd == 'listen':
        print('# listening for notifications, Ctrl-C to stop')
        while True:
            pkt = r.recv_packet(timeout=3600)
            if pkt: print(decode_packet(pkt))


if __name__ == '__main__':
    main()
