"""SoraSouls – Donald & Goofy's own AI logic script, 006950_logic.lua (v90), written for SoraSouls.

In-game v89: "they don't keep up since they just walk instead of running when I'm further away". Outside battle the
shared Dark Souls logic (logic 10000 -> COMMON_EasySetup3) walks a character back to its home point, which the DLL
keeps 1.2-2.5 m behind Sora. This logic runs first:

    function SoraParty6950_Logic(ai)
        if not ai:IsSearchTarget(TARGET_ENE_0) and ai:GetDist(POINT_INIT_POSE) > RUN_DIST then
            ai:AddTopGoal(GOAL_COMMON_ApproachTarget, RUN_LIFE, POINT_INIT_POSE, ARRIVE, TARGET_SELF, false, -1)
        else
            COMMON_EasySetup3(ai)          -- the normal logic: battle (bandit battle goal), walking home when close
        end
    end
    function SoraParty6950_Interupt(ai, goal) end
    REGISTER_LOGIC_FUNC(6950, "SoraParty6950_Logic", "SoraParty6950_Interupt")

i.e. no enemy known and more than RUN_DIST from home -> run there (ApproachTarget with isWalk = false) for RUN_LIFE
seconds, then think again. Everything else is the vanilla logic. The call shapes are the ones the game's own scripts
use (ApproachTarget: life, target, distance, turn target, isWalk, guard action; AddTopGoal on the ai object;
POINT_INIT_POSE = the home point the shared logic walks back to). No Lua 5.0 compiler is available here, so the
function above is assembled by hand with lua50.py.
"""
import lua50
from lua50 import enc

LOGIC_ID = 6950
NAME, INTERUPT = b"SoraParty6950_Logic", b"SoraParty6950_Interupt"
SCRIPT_PATH = r"N:\FRPG\data\INTERROOT_x64\script\ai\out\bin\006950_logic.lua"
RUN_DIST = 4.0     # m from the home point before they run (closer: the normal walk home)
RUN_LIFE = 2.0     # s per run goal, then the logic decides again (enemy seen -> battle)
ARRIVE = 1.0       # m: run goal done this close to the home point
RK = 250           # Lua 5.0: B/C >= 250 are constants


def _logic_proto():
    p = lua50.Proto()
    k = [b"IsSearchTarget", b"TARGET_ENE_0", b"GetDist", b"POINT_INIT_POSE", RUN_DIST, b"AddTopGoal",
         b"GOAL_COMMON_ApproachTarget", RUN_LIFE, ARRIVE, b"TARGET_SELF", -1.0, b"COMMON_EasySetup3"]
    p.consts = k
    K = {v: i for i, v in enumerate(k)}
    ELSE = 20
    code = [
        enc("SELF", 1, 0, RK + K[b"IsSearchTarget"]),          # 0  R1 = ai.IsSearchTarget, R2 = ai
        enc("GETGLOBAL", 3, bx=K[b"TARGET_ENE_0"]),             # 1
        enc("CALL", 1, 3, 2),                                   # 2  R1 = ai:IsSearchTarget(TARGET_ENE_0)
        enc("TEST", 1, 1, 1),                                   # 3  enemy known -> next (jump to ELSE)
        enc("JMP", 0, sbx=ELSE - 5),                            # 4
        enc("SELF", 1, 0, RK + K[b"GetDist"]),                  # 5
        enc("GETGLOBAL", 3, bx=K[b"POINT_INIT_POSE"]),          # 6
        enc("CALL", 1, 3, 2),                                   # 7  R1 = ai:GetDist(POINT_INIT_POSE)
        enc("LT", 0, RK + K[RUN_DIST], 1),                      # 8  RUN_DIST < dist -> skip the jump
        enc("JMP", 0, sbx=ELSE - 10),                           # 9
        enc("SELF", 1, 0, RK + K[b"AddTopGoal"]),               # 10 R1 = ai.AddTopGoal, R2 = ai
        enc("GETGLOBAL", 3, bx=K[b"GOAL_COMMON_ApproachTarget"]),  # 11
        enc("LOADK", 4, bx=K[RUN_LIFE]),                        # 12
        enc("GETGLOBAL", 5, bx=K[b"POINT_INIT_POSE"]),          # 13
        enc("LOADK", 6, bx=K[ARRIVE]),                          # 14
        enc("GETGLOBAL", 7, bx=K[b"TARGET_SELF"]),              # 15
        enc("LOADBOOL", 8, 0, 0),                               # 16 isWalk = false -> run
        enc("LOADK", 9, bx=K[-1.0]),                            # 17
        enc("CALL", 1, 9, 1),                                   # 18 ai:AddTopGoal(8 args)
        enc("RETURN", 0, 1),                                    # 19
        enc("GETGLOBAL", 1, bx=K[b"COMMON_EasySetup3"]),        # 20 ELSE
        enc("MOVE", 2, 0),                                      # 21
        enc("CALL", 1, 2, 1),                                   # 22 COMMON_EasySetup3(ai)
        enc("RETURN", 0, 1),                                    # 23
    ]
    p.code, p.line, p.nparams, p.maxstack = code, 11, 1, 10
    p.lines = [12] * len(code)
    p.locvars = [(b"ai", 0, len(code) - 1)]
    return p


def _interupt_proto():
    p = lua50.Proto()
    p.code, p.line, p.nparams, p.maxstack = [enc("RETURN", 0, 1)], 21, 2, 2
    p.lines = [23]
    p.locvars = [(b"ai", 0, 0), (b"goal", 0, 0)]
    return p


def build():
    m = lua50.Proto()
    m.source = b"@N:\\FRPG\\data\\INTERROOT_x64\\script\\ai\\out\\006950_logic.lua"
    m.consts = [b"REGISTER_LOGIC_FUNC", float(LOGIC_ID), NAME, INTERUPT]
    m.code = [
        enc("GETGLOBAL", 0, bx=0),
        enc("LOADK", 1, bx=1),
        enc("LOADK", 2, bx=2),
        enc("LOADK", 3, bx=3),
        enc("CALL", 0, 4, 1),            # REGISTER_LOGIC_FUNC(6950, name, interupt)
        enc("CLOSURE", 0, bx=0),
        enc("SETGLOBAL", 0, bx=2),
        enc("CLOSURE", 0, bx=1),
        enc("SETGLOBAL", 0, bx=3),
        enc("RETURN", 0, 1),
    ]
    m.maxstack = 4
    m.lines = [5, 5, 5, 5, 5, 14, 11, 23, 21, 23]
    m.protos = [_logic_proto(), _interupt_proto()]
    data = lua50.dump(m)
    assert lua50.dump(lua50.load(data)) == data
    return data


# LuaInfo record (goal id, name, logic-interrupt name, flags): logic goals carry 0x100 (as Witch6520_Logic does)
INFO_RECORD = (LOGIC_ID, NAME, INTERUPT, 0x100)
GNL_NAMES = [NAME, INTERUPT]

if __name__ == "__main__":
    print("\n".join(lua50.listing(lua50.load(build()))))
