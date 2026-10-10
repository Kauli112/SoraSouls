"""Generate data/bone_map_sora.json: KH2 Sora (P_EX100) bone index -> DSR c0000 bone name.

Rule: explicit ANCHORS for the left side (+X, hypothesis: +X = Sora's left); the right side is the
mirror (index offset). Every other bone inherits the mapping of its nearest mapped ancestor, so cloth,
hair and helper bones become rigid on their parent DSR bone.
Run: python gen_bone_map.py <path to P_EX100.mdlx> <output json>
"""
import json, struct, sys

LEFT = {  # Sora bone index -> DSR bone (left side / centre)
    0: "Pelvis",
    10: "L_Thigh", 23: "L_Thigh", 12: "L_Calf", 19: "L_Calf", 21: "L_Calf",
    13: "L_Foot", 17: "L_Toe0",
    64: "Spine", 67: "Spine1", 128: "Spine", 130: "Spine", 132: "Spine", 134: "Spine",
    136: "Neck", 141: "Head",
    74: "L_Clavicle", 116: "L_Clavicle", 121: "L_Clavicle",
    # 109-115 are KH2 sleeve helpers whose vertices sit on the upper arm. v1 mapped them to DSR twist
    # bones, but LUpArmTwist hangs off L_Clavicle, so the sleeve stayed horizontal when the arm moved.
    76: "L_UpperArm", 109: "L_UpperArm", 79: "L_Forearm", 80: "L_Hand",
    87: "L_Finger0", 89: "L_Finger01", 91: "L_Finger02",
    93: "L_Finger1", 95: "L_Finger11", 96: "L_Finger12",
    97: "L_Finger2", 99: "L_Finger21", 100: "L_Finger22",
    101: "L_Finger2", 103: "L_Finger21", 104: "L_Finger22",
    105: "L_Finger2", 107: "L_Finger21", 108: "L_Finger22",
}
# Right-side counterparts: legs +29, arm/shoulder/hip-cloth +92 (verified by mirrored positions).
MIRROR_LEG, MIRROR_ARM = 29, 92
CENTRE = {0, 64, 67, 128, 130, 132, 134, 136, 141}
CENTRE_MIRRORS = {128: 220, 130: 222, 132: 224, 134: 226}  # belt/jacket hem pieces

def load_parents(path):
    b = open(path, "rb").read()
    m = b[64 + 0x90:]  # first BAR entry (model) at 64, PS2 header 0x90
    count, _, off = struct.unpack_from("<hhi", m, 16)
    return [struct.unpack_from("<hhiii", m, off + i * 64)[2] for i in range(count)]

def main(mdlx, out):
    parents = load_parents(mdlx)
    anchors = {}
    for i, name in LEFT.items():
        anchors[i] = name
        if i in CENTRE:
            if i in CENTRE_MIRRORS: anchors[CENTRE_MIRRORS[i]] = name
            continue
        j = i + (MIRROR_LEG if i < 64 else MIRROR_ARM)
        anchors[j] = name.replace("L_", "R_").replace("LUp", "RUp")
    result = {}
    for i in range(len(parents)):
        k = i
        while k not in anchors:
            k = parents[k]
            if k < 0: raise SystemExit(f"bone {i} has no mapped ancestor")
        result[i] = {"dsr": anchors[k], "via": k}
    json.dump({"source": "P_EX100.mdlx", "target": "DSR c0000", "bones": result}, open(out, "w"), indent=1)
    print(f"mapped {len(result)} bones onto {len(set(v['dsr'] for v in result.values()))} DSR bones")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
