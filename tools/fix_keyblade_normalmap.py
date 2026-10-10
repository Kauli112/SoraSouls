"""SoraSouls – flat normal map for the Kingdom Key part (v65). Its KEYBLADE_n was pure black (same bug as SORA_n,
see fix_sora_normalmap.py), which lights the blade unevenly by direction. Only that TPF entry changes.
Usage: python fix_keyblade_normalmap.py <in WP_A_0204.partsbnd.dcx> <out WP_A_0204.partsbnd.dcx>
"""
import os, sys
from soulstruct.containers import Binder
from soulstruct.containers.tpf import TPF
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fix_sora_normalmap import flat_dxt1

b = Binder.from_path(sys.argv[1])
te = next(e for e in b.entries if e.path.lower().endswith(".tpf"))
tpf = TPF.from_bytes(te.data)
n = [t for t in tpf.textures if t.stem == "KEYBLADE_n"]
if len(n) != 1:
    raise RuntimeError(f"KEYBLADE_n found {len(n)} times")
n[0].data, n[0].format = flat_dxt1(), 0
te.set_from_binary_file(tpf)
b.write(sys.argv[2])
print("KEYBLADE_n replaced with a flat normal map")
