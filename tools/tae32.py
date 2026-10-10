"""SoraSouls – read-only parser for DSR *player* TAE files (c0000.anibnd: version 0x1000B, 32-bit offsets).

soulstruct's TAE reader only handles the 64-bit layout (0x1000C), and its writer is not implemented. This reader
mirrors the same TAE3 structure with 32-bit offsets and keeps the absolute byte offset of every event's data block,
so later edits can be done as same-size in-place patches (no re-serialisation).

Layout (verified against a02.tae, 2026-10-05):
  0x00 "TAE "  0x08 version  0x0C file size  0x50 tae id  0x54 anim count  0x58 anims offset
  anim table: (int32 anim id, int32 anim offset) * count
  anim struct (0x1C): event_count, event_headers_off, group_count, groups_off, times_count, times_off,
               anim_file_off
  event header: start_time_off, end_time_off, event_data_off (each -> float / data)
  event data: int32 type, int32 data_off (= pos + 8, or 0 for payload-less events), then type-specific bytes
"""
import struct
from dataclasses import dataclass, field


@dataclass
class Event:
    type: int
    start: float
    end: float
    data_offset: int          # absolute offset of the type-specific payload (after type + pointer)
    start_offset: int
    end_offset: int
    payload: bytes = b""      # first 32 bytes after data_offset (enough for every DS1 event we inspect)

    def i32(self, n):
        return struct.unpack_from("<i", self.payload, 4 * n)[0]


@dataclass
class Animation:
    id: int
    offset: int
    events: list = field(default_factory=list)
    file_ref: bool = False
    file_name_offset: int = 0


@dataclass
class TAE32:
    raw: bytes
    tae_id: int
    animations: list

    @classmethod
    def parse(cls, data: bytes):
        if data[:4] != b"TAE ":
            raise ValueError("not a TAE")
        version, = struct.unpack_from("<i", data, 0x08)
        if version != 0x1000B:
            raise ValueError(f"unexpected TAE version {version:#x}")
        if struct.unpack_from("<4i", data, 0x10) != (0x40, 1, 0x50, 0x70):
            raise ValueError("unexpected 32-bit fixed header values")
        tae_id, count, anims_off = struct.unpack_from("<iii", data, 0x50)
        anims = []
        for k in range(count):
            aid, aoff = struct.unpack_from("<ii", data, anims_off + 8 * k)
            ev_n, ev_off, grp_n, grp_off, times_n, times_off, file_off = struct.unpack_from("<7i", data, aoff)
            a = Animation(aid, aoff)
            for j in range(ev_n):
                s_off, e_off, d_off = struct.unpack_from("<iii", data, ev_off + 12 * j)
                st, = struct.unpack_from("<f", data, s_off)
                en, = struct.unpack_from("<f", data, e_off)
                etype, ptr = struct.unpack_from("<ii", data, d_off)
                if ptr == 0:   # event type without a payload
                    a.events.append(Event(etype, st, en, -1, s_off, e_off, b""))
                    continue
                if ptr != d_off + 8:
                    raise ValueError(f"anim {aid} event {j}: data pointer {ptr:#x} != {d_off + 8:#x}")
                a.events.append(Event(etype, st, en, d_off + 8, s_off, e_off, data[d_off + 8:d_off + 40]))
            anims.append(a)
        return cls(data, tae_id, anims)
