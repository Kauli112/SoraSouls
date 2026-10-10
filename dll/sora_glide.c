/* SoraSouls – Glide + High Jump levels (v42: warp fallback for gliding without moving) + v45 KH-style MP Charge and Drive gauge. Original code, loaded by ModEngine2 as an external DLL. OFFLINE USE ONLY.
 *
 * What it does: while Sora is falling and the player HOLDS the roll/jump button (B / Circle, or Space on keyboard),
 * gravity is switched off and Sora sinks slowly. Releasing the button, landing, death or a loading screen ends the
 * glide. v36 (in-game 2026-10-07): works, 0.8 m/s feels like max-level Glide.
 * v37 levels, read from event flags set by tools/movement_levels.py (unlocked in order, by bosses):
 *   Glide      none until flag 9820 | LV1 9820: 2.0 m/s | LV2 9821: 1.3 m/s | MAX 9822: 0.8 m/s
 *   High Jump  LV1 always (jump animation) | LV2 9823: rise x1.5 | MAX 9824: rise x2.0 – while Sora rises faster
 *              than JUMP_RISE m/s (only the modded jump does that; ladders/lifts are slower) the DLL adds the extra
 *              share of each tick's climb.
 *
 * How (no game code is patched or hooked; only the player's own character data on the heap is read/written):
 *   - WorldChrMan static pointer: found at start-up by scanning the game's .text for the instruction pattern
 *     "48 8B 05 ?? ?? ?? ?? 48 8B 48 68 48 85 C9 0F 84 ..." (rip-relative load). Layout facts taken from the
 *     public, GPL-3 DSR Gadget project (JKAnderson/DSR-Gadget, DSROffsets.cs) – facts only, no code copied:
 *       player ChrIns   = *(WorldChrMan + 0x68)
 *       chr flags 1     = ChrIns + 0x284 (+0x20 on game versions after 1.03; this exe's image size 0x319B000 is
 *                         newer than every version Gadget lists, and Gadget applies +0x20 to unknown versions)
 *       NoGravity bit   = 0x00004000
 *       ChrMapData      = *(ChrIns + 0x48 (+0x20)),  position data = *(ChrMapData + 0x28),  y = +0x14 (float)
 *       event flags     = **(slot of "48 8B 0D ?? ?? ?? ?? 99 33 C2 45 33 C0 2B C2 8D 50 F6"); flag 0000SNNN (S = digit
 *                         5 of the 8-digit id, NNN = last 3) -> u32 at S*128 + (NNN/32)*4, bit 0x80000000 >> (NNN%32)
 *                         (group 0 / area 000 only – all SoraSouls flags are 9xxx)
 *   - Input: XInput (xinput1_4 / 1_3 / 9_1_0, first that loads), plus GetAsyncKeyState(VK_SPACE) when the game
 *     window has focus.
 * Every pointer is checked with VirtualQuery before it is read; nothing is written unless the whole chain is valid.
 * A log is written next to the DLL (sora_glide.log): start-up results, then one line per glide start/end.
 *
 * v45 MP CHARGE + DRIVE GAUGE (user choices 2026-10-08: "KH2 MP Charge"; Drive filled by kills AND damage taken).
 *   Offsets found by the v44 probe in this exe (log 2026-10-08), not from Gadget:
 *     PlayerGameData   = *(ChrIns + 0x578)  (same pointer as *(GameDataMan + 0x10))
 *     attuned spells   = *(PlayerGameData + 0x418): (int32 spell id, int32 remaining) pairs; the remaining value
 *                        is 3 per cast (Fire 16 casts = 48; one cast 36 -> 33; rest -> 48)
 *     HP               = ChrIns + 0x3E8 (616 -> 562 when hit, back to 616 at a bonfire); max HP read at +0x3EC
 *     souls            = PlayerGameData + 0x94 (NOT yet verified – logged on every change so the user can compare)
 *   MP: Sora's spells (ids 3900-3932) share one MP pool. A cast lowers that spell's remaining value; every other
 *       attuned Sora spell is set to the same fraction. Cure/Cura/Curaga use all MP (KH2). When MP hits 0 it is
 *       "MP Charge": all stay at 0 for MP_CHARGE_S seconds, then all refill. A bonfire rest refills as before.
 *   Drive (v47): the gauge fills by HIT_POINTS per landed hit (flag 9854, set by an event from a hit-sensor SpEffect)
 *       and DRIVE_DAMAGE points per full HP bar lost; at 100 one
 *       spent use of every Drive Form comes back (its charge flag 9960 + 4*form + n is cleared).
 *   HUD (v46, user choice "KH-style bar overlay", plays Borderless/Windowed): a small click-through, always-on-top,
 *       colour-keyed window drawn with GDI over the bottom-right of the game window: MP bar (blue; pink while MP
 *       Charge refills) and Drive gauge (yellow). Shown only while the game window is in front and Sora is loaded.
 *       It is a separate window – nothing in the game's rendering is touched. Exclusive Fullscreen hides it.
 *   Messages: the DLL sets flags 9832 (charging), 9833 (MP restored), 9834 (Drive restored); events show them.
 *
 * v44 RESEARCH PROBE (read-only; for KH-style MP Charge and the Drive gauge): finds where the game keeps the attuned
 * spells' remaining casts, the player's HP and souls. Nothing is written by the probe.
 *   1. Scan: every committed private read/write memory region is searched for (int32 SoraSouls spell id 3900-3932,
 *      int32 0..99) pairs = candidate "attuned spell + remaining casts". Runs 15 s after the character appears and
 *      again on F11.
 *   2. Watch: every 0.5 s each candidate is re-read; changes are logged. A cast lowers the real one by 1.
 *   3. Path: for a candidate that went down, pointers from ChrIns / WorldChrMan / GameDataMan (depth <= 2) that
 *      lead near it are logged, and the struct holding it is diff-watched (small-integer fields that change are
 *      logged), as is ChrIns – to spot HP (drops when hit) and souls (rise on kills).
 *   Log volume is capped. Test procedure: load, cast twice, get hit once, kill one enemy, rest, quit.
 */
typedef unsigned char u8; typedef unsigned short u16; typedef unsigned int u32; typedef unsigned long long u64;
typedef long long i64; typedef int BOOL; typedef void *HANDLE; typedef u64 SIZE_T;

#define WINAPI __stdcall
#define IMPORT __declspec(dllimport)

typedef struct { void *BaseAddress, *AllocationBase; u32 AllocationProtect; u16 PartitionId; SIZE_T RegionSize;
                 u32 State, Protect, Type; } MBI;
typedef struct { u32 dwPacketNumber; u16 wButtons; u8 bLeftTrigger, bRightTrigger; short sThumbLX, sThumbLY,
                 sThumbRX, sThumbRY; } XSTATE;
typedef u32 (WINAPI *XInputGetState_t)(u32, XSTATE *);

IMPORT HANDLE WINAPI CreateThread(void *, SIZE_T, u32 (WINAPI *)(void *), void *, u32, u32 *);
IMPORT void WINAPI Sleep(u32);
IMPORT void *WINAPI GetModuleHandleA(const char *);
IMPORT u32 WINAPI GetModuleFileNameA(void *, char *, u32);
IMPORT void *WINAPI LoadLibraryA(const char *);
IMPORT void *WINAPI GetProcAddress(void *, const char *);
IMPORT SIZE_T WINAPI VirtualQuery(const void *, MBI *, SIZE_T);
IMPORT BOOL WINAPI QueryPerformanceCounter(i64 *);
IMPORT BOOL WINAPI QueryPerformanceFrequency(i64 *);
IMPORT HANDLE WINAPI CreateFileA(const char *, u32, u32, void *, u32, u32, HANDLE);
IMPORT BOOL WINAPI WriteFile(HANDLE, const void *, u32, u32 *, void *);
IMPORT BOOL WINAPI DisableThreadLibraryCalls(void *);
IMPORT u32 WINAPI GetCurrentProcessId(void);
IMPORT short WINAPI GetAsyncKeyState(int);
IMPORT void *WINAPI GetForegroundWindow(void);
IMPORT u32 WINAPI GetWindowThreadProcessId(void *, u32 *);
typedef struct { int l, t, r, b; } RECT; typedef struct { int x, y; } POINT;
typedef i64 (*WNDPROC)(void *, u32, u64, i64);
typedef struct { u32 style; WNDPROC proc; int cls_extra, wnd_extra; void *inst, *icon, *cursor, *bg; const char *menu, *cls; } WNDCLASSA;
IMPORT u16 WINAPI RegisterClassA(const WNDCLASSA *);
IMPORT void *WINAPI CreateWindowExA(u32, const char *, const char *, u32, int, int, int, int, void *, void *, void *, void *);
IMPORT i64 WINAPI DefWindowProcA(void *, u32, u64, i64);
IMPORT BOOL WINAPI SetLayeredWindowAttributes(void *, u32, u8, u32);
IMPORT BOOL WINAPI SetWindowPos(void *, void *, int, int, int, int, u32);
IMPORT BOOL WINAPI ShowWindow(void *, int);
IMPORT BOOL WINAPI PeekMessageA(void *, void *, u32, u32, u32);
IMPORT BOOL WINAPI TranslateMessage(const void *);
IMPORT i64 WINAPI DispatchMessageA(const void *);
IMPORT void *WINAPI GetDC(void *);
IMPORT int WINAPI ReleaseDC(void *, void *);
IMPORT BOOL WINAPI GetClientRect(void *, RECT *);
IMPORT BOOL WINAPI ClientToScreen(void *, POINT *);
IMPORT BOOL WINAPI IsIconic(void *);
IMPORT int WINAPI GetClassNameA(void *, char *, int);
IMPORT BOOL WINAPI IsWindowVisible(void *);
IMPORT void *WINAPI WindowFromPoint(POINT);
IMPORT void *WINAPI GetAncestor(void *, u32);
IMPORT int WINAPI FillRect(void *, const RECT *, void *);
IMPORT void *WINAPI CreateSolidBrush(u32);
IMPORT BOOL WINAPI DeleteObject(void *);
IMPORT int WINAPI SetBkMode(void *, int);
IMPORT u32 WINAPI SetTextColor(void *, u32);
IMPORT BOOL WINAPI TextOutA(void *, int, int, const char *, int);
IMPORT void *WINAPI SelectObject(void *, void *);
IMPORT void *WINAPI CreateFontA(int, int, int, int, int, u32, u32, u32, u32, u32, u32, u32, u32, const char *);
IMPORT void *WINAPI CreateCompatibleDC(void *);
IMPORT void *WINAPI CreateCompatibleBitmap(void *, int, int);
IMPORT BOOL WINAPI BitBlt(void *, int, int, int, int, void *, int, int, u32);
IMPORT BOOL WINAPI DeleteDC(void *);
IMPORT BOOL WINAPI GetTextExtentPoint32A(void *, const char *, int, POINT *);
#include "hud_data.h"   /* generated by tools/build_abilities.py: pop-up texts + abilities list */

/* ---- tuning ---- */
static const float GLIDE_SINK[4] = { 0.0f, 2.0f, 1.3f, 0.8f };   /* m/s by Glide level (0 = locked) */
/* v43: the boost only runs while Sora rises faster than JUMP_RISE for JUMP_HOLD_S (sprinting up stairs reached 3 m/s
   and step snaps spiked higher – v42 bug "can't sprint up stairs"). That window covers ~61 % of the jump's climb, so
   the multipliers are raised to keep the v37 totals (x1.5 / x2.0 overall) the user liked. */
static const float JUMP_MULT[4]  = { 1.0f, 1.0f, 1.82f, 2.64f };
#define JUMP_RISE         4.5f    /* m/s: the modded jump starts at ~7 m/s; stairs/lifts stay below */
#define JUMP_HOLD_S       0.025f  /* must rise that fast for this long (>= 2 ticks) before boosting */
#define FLAG_GLIDE1       9820
#define FLAG_JUMP2        9823
#define TEST_KEYS         0       /* v115: off for release (was 1: v37 test build: F9 cycles Glide level, F10 cycles High Jump level (override, logged) */
#define VK_F9 0x78
#define VK_F10 0x79
#define VK_F11 0x7A
#define PROBE 0                 /* v44 research probe (read-only) – done */
#define PROBE_PGD 1             /* v45: log changes of PlayerGameData small ints (to confirm souls) – off for release */
#define MP_CHARGE_S       20.0f
#define DRIVE_FULL        100.0f
#define DRIVE_DAMAGE      100.0f  /* gauge points for losing one full HP bar */
#define KILL_POINTS       0.0f    /* v47: user "Drive should fill on hit not on kill" – kills no longer count */
#define HIT_POINTS        4.0f    /* v47: gauge points per landed hit (25 hits = one Drive use) */
#define FLAG_HIT          9854    /* set by event 9853 when Sora's attack lands (hit-sensor SpEffect) */
#define OFF_PGD           0x578
#define OFF_ATTUNE        0x418
#define OFF_HP            0x3E8
#define OFF_HPMAX         0x3EC
#define OFF_SOULS         0x94
#define FLAG_MP_CHARGING  9832
#define FLAG_MP_RESTORED  9833
#define FLAG_DRIVE_DONE   9834
#define FLAG_DRIVE_CHARGE 9960
#define FALL_TRIGGER     -5.0f    /* v43: was -1.5 – sprinting (B held) down stairs/slopes started a glide on the ground */
#define GROUND_STILL_S    0.25f   /* y unchanged this long while gliding = landed */
#define CHR_BOOST         0x20

#define OFF_CHRINS        0x68
#define OFF_FLAGS1        (0x284 + CHR_BOOST)
#define FLAG_NOGRAVITY    0x00004000u
#define OFF_MAPDATA       (0x48 + CHR_BOOST)
#define OFF_POSDATA       0x28
#define OFF_POS_Y         0x14
#define OFF_POS_ANGLE     0x04
#define OFF_POS_X         0x10
#define OFF_POS_Z         0x18
/* warp (teleport) request in ChrMapData – DSR Gadget facts: flag +0x108, x/y/z +0x110/+0x114/+0x118, angle +0x124 */
#define OFF_WARP_FLAG     0x108
#define OFF_WARP_X        0x110
#define OFF_WARP_ANGLE    0x124
#define STILL_SPEED       0.5f    /* v43: horizontal m/s below which a glide tick uses the warp request */
#define XI_B              0x2000
#define VK_SPACE          0x20

int _fltused = 0;                                    /* required by MSVC-ABI float code without a CRT */
static void *g_self;
static HANDLE g_log = (HANDLE)-1;
/* v46 HUD state, written by the worker thread, drawn by the HUD thread */
static volatile float g_mp_frac = -1.0f, g_drive = 0.0f, g_charge_frac = 0.0f;   /* g_mp_frac < 0: no Sora spell attuned */
static volatile int g_mp_charging, g_live;
static volatile float g_mp_msg_t, g_drive_msg_t;   /* v47: seconds left to flash "MP RESTORED" / "DRIVE +1" in the HUD */

/* ---- tiny helpers (freestanding: no C runtime) ---- */
void *memset(void *d, int c, SIZE_T n) { u8 *p = d; while (n--) *p++ = (u8)c; return d; }
static int slen(const char *s) { int n = 0; while (s[n]) n++; return n; }
static void logs(const char *s) { u32 w; if (g_log != (HANDLE)-1) WriteFile(g_log, s, (u32)slen(s), &w, 0); }
static void logx(const char *label, u64 v) {
    char b[64]; int i = 0, k; const char *h = "0123456789ABCDEF";
    while (label[i] && i < 40) { b[i] = label[i]; i++; }
    b[i++] = '0'; b[i++] = 'x';
    for (k = 60; k >= 0; k -= 4) { u32 d = (u32)(v >> k) & 15; if (d || k == 0 || i > 0 && b[i - 1] != 'x') b[i++] = h[d]; }
    b[i++] = '\r'; b[i++] = '\n'; b[i] = 0; logs(b);
}
static void logf1(const char *label, float f) {   /* one decimal place, enough for a log */
    char b[64]; int i = 0, neg = f < 0, ip, fp, n = 0; char t[16];
    if (neg) f = -f;
    ip = (int)f; fp = (int)((f - (float)ip) * 100.0f + 0.5f); if (fp >= 100) { ip++; fp -= 100; }
    while (label[i] && i < 40) { b[i] = label[i]; i++; }
    if (neg) b[i++] = '-';
    do { t[n++] = (char)('0' + ip % 10); ip /= 10; } while (ip);
    while (n) b[i++] = t[--n];
    b[i++] = '.'; b[i++] = (char)('0' + fp / 10); b[i++] = (char)('0' + fp % 10);
    b[i++] = '\r'; b[i++] = '\n'; b[i] = 0; logs(b);
}

static int readable(const void *p, SIZE_T n) {
    MBI m; u32 ok = 0x02 | 0x04 | 0x08 | 0x20 | 0x40 | 0x80;   /* RO, RW, WC, XR, XRW, XWC */
    if ((u64)p < 0x10000) return 0;
    if (!VirtualQuery(p, &m, sizeof m)) return 0;
    if (m.State != 0x1000 || !(m.Protect & ok) || (m.Protect & 0x100)) return 0;   /* committed, no guard page */
    return (u8 *)p + n <= (u8 *)m.BaseAddress + m.RegionSize;
}
static int writable(const void *p, SIZE_T n) {
    MBI m;
    if (!readable(p, n) || !VirtualQuery(p, &m, sizeof m)) return 0;
    return (m.Protect & (0x04 | 0x08 | 0x40 | 0x80)) != 0;
}
static u64 rd64(u64 a) { return readable((void *)a, 8) ? *(volatile u64 *)a : 0; }

/* ---- pattern scan of the main module's first executable section ---- */
static const short PAT_WCM[] = { 0x48,0x8B,0x05,-1,-1,-1,-1,0x48,0x8B,0x48,0x68,0x48,0x85,0xC9,0x0F,0x84,-1,-1,-1,-1,
                                 0x48,0x39,0x5E,0x10,0x0F,0x84,-1,-1,-1,-1,0x48 };
/* v78: ChrFollowCam / CamMan patterns from DSR-Gadget (its "Loaded" test: [[[followcam]+0x60]+0x60] != 0) */
static const short PAT_FOLLOWCAM[] = { 0x48,0x8B,0x0D,-1,-1,-1,-1,0xE8,-1,-1,-1,-1,0x48,0x8B,0x4E,0x68,0x48,0x8B,0x05,-1,-1,-1,-1,
                                       0x48,0x89,0x48,0x60 };
static const short PAT_CAMMAN[] = { 0x48,0x8B,0x05,-1,-1,-1,-1,0x48,0x63,0xD1,0x48,0x8B,0x44,0xD0,0x08,0xC3 };
static u64 g_followcam_slot, g_camman_slot;
static volatile int g_cam_ok = 1;          /* v78: 0 while the game has no follow camera (loading screens) */
static int drive_known(void);
static const short PAT_FLAGS[] = { 0x48,0x8B,0x0D,-1,-1,-1,-1,0x99,0x33,0xC2,0x45,0x33,0xC0,0x2B,0xC2,0x8D,0x50,0xF6 };
/* returns the rip-relative target of the 7-byte "mov reg, [rip+rel32]" at the start of the first match */
static u64 find_slot(const short *PATTERN, int plen, const char *what) {
    u8 *base = GetModuleHandleA(0);
    u32 pe = *(u32 *)(base + 0x3C), nsec = *(u16 *)(base + pe + 6), opt = *(u16 *)(base + pe + 20), s;
    u8 *sec = base + pe + 24 + opt;
    for (s = 0; s < nsec; s++, sec += 40) {
        u32 va = *(u32 *)(sec + 12), vs = *(u32 *)(sec + 8), ch = *(u32 *)(sec + 36);
        u8 *p, *end;
        if (!(ch & 0x20000000)) continue;              /* executable sections only */
        p = base + va; end = p + vs - plen;
        if (!readable(p, 1)) continue;
        for (; p < end; p++) {
            int k;
            if (p[0] != (u8)PATTERN[0] || p[1] != (u8)PATTERN[1] || p[2] != (u8)PATTERN[2]) continue;
            for (k = 3; k < plen; k++) if (PATTERN[k] >= 0 && p[k] != (u8)PATTERN[k]) break;
            if (k == plen) {
                int rel = *(int *)(p + 3);
                logs(what); logx(" pattern at ", (u64)p);
                return (u64)(p + 7 + rel);
            }
        }
    }
    return 0;
}

static u64 g_flags_slot;
static int flag_on(int id) {                       /* group 0 / area 000 flags (id < 100000) only */
    u64 base = rd64(g_flags_slot); u32 off; volatile u32 *w;
    base = base ? rd64(base) : 0;
    if (!base || id < 0 || id >= 100000) return 0;
    off = (u32)((id / 1000) % 10) * 128 + (u32)((id % 1000) / 32) * 4;
    w = (volatile u32 *)(base + off);
    if (!readable((void *)w, 4)) return 0;
    return (*w & (0x80000000u >> ((id % 1000) % 32))) != 0;
}

static XInputGetState_t load_xinput(void) {
    const char *names[] = { "xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll" };
    int i;
    for (i = 0; i < 3; i++) {
        void *m = LoadLibraryA(names[i]);
        if (m) { void *f = GetProcAddress(m, "XInputGetState"); if (f) { logs("xinput: "); logs(names[i]); logs("\r\n"); return (XInputGetState_t)f; } }
    }
    logs("xinput: none (keyboard only)\r\n");
    return 0;
}

/* v51 (log v50: the Claude app window reported the GAME's process id – Chrome_WidgetWin_1, pid = DSR's – so a pid
   test can't tell "game in front" apart): the game is in front only when the front window's class is exactly
   "DARK SOULS" (the render window, seen in the v50 log). Used for the HUD and every keyboard test. */
static int is_game_window(void *w) {
    char cls[32]; int n, k; const char *want = "DARK SOULS"; u32 pid = 0;
    if (!w) return 0;
    GetWindowThreadProcessId(w, &pid);
    if (pid != GetCurrentProcessId()) return 0;
    n = GetClassNameA(w, cls, 31);
    if (n != 10) return 0;
    for (k = 0; k < 10; k++) if (cls[k] != want[k]) return 0;
    return 1;
}
static int game_focused(void) { return is_game_window(GetForegroundWindow()); }
static XInputGetState_t g_xget;   /* v62: set by the worker, read by party_tick */
static int move_held(void) {      /* left stick pushed or W/A/S/D held (game focused) */
    u32 i;
    if (!game_focused()) return 0;
    if (g_xget) for (i = 0; i < 4; i++) {
        XSTATE st; int x, y; memset(&st, 0, sizeof st);
        if (g_xget(i, &st) != 0) continue;
        x = st.sThumbLX; y = st.sThumbLY;
        if (x * x + y * y > 12000 * 12000) return 1;
    }
    return (GetAsyncKeyState(0x57) | GetAsyncKeyState(0x41) | GetAsyncKeyState(0x53) | GetAsyncKeyState(0x44)) & 0x8000 ? 1 : 0;
}
static int glide_button(XInputGetState_t xget) {
    u32 pid = 0, i;
    if (xget) {
        for (i = 0; i < 4; i++) { XSTATE st; memset(&st, 0, sizeof st); if (xget(i, &st) == 0 && (st.wButtons & XI_B)) return 1; }
    }
    GetWindowThreadProcessId(GetForegroundWindow(), &pid);
    (void)pid;
    return game_focused() && (GetAsyncKeyState(VK_SPACE) & 0x8000);
}


/* ===================== v44 research probe (read-only) ===================== */
static const int SPELL_IDS[] = { 3900,3901,3902,3910,3911,3912,3920,3921,3922,3930,3931,3932 };
#define MAXC 2048
static u64 c_addr[MAXC]; static int c_id[MAXC], c_cnt[MAXC], c_done[MAXC], n_cand;
static u64 g_gdm_slot;
static int g_loglines;
static int is_spell(int v) { int i; for (i = 0; i < 12; i++) if (SPELL_IDS[i] == v) return 1; return 0; }
static void logn(const char *label, u64 a, int x, int y) {   /* "label addr x -> y" */
    char b[160]; int i = 0, k; const char *h = "0123456789ABCDEF"; char t[16]; int n, v, neg;
    if (g_loglines > 4000) return;
    g_loglines++;
    while (label[i] && i < 60) { b[i] = label[i]; i++; }
    b[i++] = '0'; b[i++] = 'x'; for (k = 44; k >= 0; k -= 4) b[i++] = h[(a >> k) & 15];
    for (k = 0; k < 2; k++) {
        v = k ? y : x; neg = v < 0; if (neg) v = -v; n = 0;
        b[i++] = ' '; if (k) { b[i++] = '-'; b[i++] = '>'; b[i++] = ' '; } if (neg) b[i++] = '-';
        do { t[n++] = (char)('0' + v % 10); v /= 10; } while (v);
        while (n) b[i++] = t[--n];
    }
    b[i++] = '\r'; b[i++] = '\n'; b[i] = 0; logs(b);
}
static void probe_scan(void) {
    u8 *a = (u8 *)0x10000; MBI m; u64 regions = 0, bytes = 0;
    n_cand = 0;
    while ((u64)a < 0x7FFFFFFF0000ull && VirtualQuery(a, &m, sizeof m)) {
        u8 *b = (u8 *)m.BaseAddress, *e = b + m.RegionSize;
        if (m.State == 0x1000 && m.Type == 0x20000 && m.Protect == 0x04 && m.RegionSize <= 0x20000000ull) {
            u8 *p;
            regions++; bytes += m.RegionSize;
            for (p = b; p + 8 <= e && n_cand < MAXC; p += 4) {
                int v = *(volatile int *)p, c;
                if (v < 3900 || v > 3932 || !is_spell(v)) continue;
                c = *(volatile int *)(p + 4);
                if (c < 0 || c > 99) continue;
                c_addr[n_cand] = (u64)p; c_id[n_cand] = v; c_cnt[n_cand] = c; c_done[n_cand] = 0; n_cand++;
            }
        }
        a = e;
    }
    logx("probe scan: regions ", regions); logx("probe scan: bytes ", bytes); logx("probe scan: candidates ", (u64)n_cand);
    { int i; for (i = 0; i < n_cand && i < 64; i++) logn("  cand ", c_addr[i], c_id[i], c_cnt[i]); }
}
/* pointer paths (depth <= 2) from a root to within 0x2000 bytes after target */
static void probe_paths(const char *rname, u64 root, u64 target) {
    u32 o1, o2; int found = 0;
    if (!root || !readable((void *)root, 0x1000)) return;
    for (o1 = 0; o1 < 0x1000 && found < 6; o1 += 8) {
        u64 q = *(volatile u64 *)(root + o1);
        if (q < 0x10000 || (q & 7)) continue;
        if (target >= q && target < q + 0x2000) { logs(rname); logn(" path1 off/delta ", target, (int)o1, (int)(target - q)); found++; continue; }
        if (!readable((void *)q, 0x1000)) continue;
        for (o2 = 0; o2 < 0x1000; o2 += 8) {
            u64 r = *(volatile u64 *)(q + o2);
            if (target >= r && target < r + 0x2000 && r >= 0x10000) {
                logs(rname); logn(" path2 off1 ", (u64)o1, (int)o2, (int)(target - r)); found++;
                if (found >= 6) break;
            }
        }
    }
}
#define WSZ 0x1000
static u64 w_base[2]; static int w_snap[2][WSZ / 4]; static int w_have[2];
static void watch_set(int k, u64 base) {
    if (w_base[k] == base) return;
    w_base[k] = base; w_have[k] = 0; logn(k ? "watch struct " : "watch ChrIns ", base, 0, 0);
}
static void watch_tick(int k) {
    int i; u64 b = w_base[k];
    if (!b || !readable((void *)b, WSZ)) return;
    for (i = 0; i < WSZ / 4; i++) {
        int v = *(volatile int *)(b + 4 * i);
        if (w_have[k] && v != w_snap[k][i] && v > -2 && v < 10000000 && w_snap[k][i] > -2 && w_snap[k][i] < 10000000)
            logn(k ? "  struct+off " : "  chrins+off ", (u64)(4 * i), w_snap[k][i], v);
        w_snap[k][i] = v;
    }
    w_have[k] = 1;
}
static void probe_tick(u64 wcm, u64 chr) {
    int i;
    for (i = 0; i < n_cand; i++) {
        int v, c;
        if (!readable((void *)c_addr[i], 8)) continue;
        v = *(volatile int *)c_addr[i]; c = *(volatile int *)(c_addr[i] + 4);
        if (v != c_id[i]) continue;
        if (c != c_cnt[i]) {
            logn("cand changed ", c_addr[i], c_cnt[i], c);
            if (c < c_cnt[i] && !c_done[i]) {
                u64 gdm = g_gdm_slot ? rd64(g_gdm_slot) : 0;
                c_done[i] = 1;
                logn("  -> spell id ", c_addr[i], c_id[i], c);
                probe_paths("  ChrIns", chr, c_addr[i]);
                probe_paths("  WorldChrMan", wcm, c_addr[i]);
                probe_paths("  GameDataMan", gdm, c_addr[i]);
                /* watch the 4 KB page-aligned block holding it (struct start unknown until the paths are read) */
                watch_set(1, (c_addr[i] - 0x800) & ~0xFull);
            }
            c_cnt[i] = c;
        }
    }
    if (chr) { watch_set(0, chr); watch_tick(0); }
    watch_tick(1);
}
/* candidate GameDataMan pattern (public CE-table knowledge, unverified for this exe – only logged) */
static const short PAT_GDM[] = { 0x48,0x8B,0x05,-1,-1,-1,-1,0x48,0x85,0xC0,-1,-1,0xF3,0x0F,0x58,0x80,0xAC,0x00,0x00,0x00 };

/* ===================== v45 MP Charge + Drive gauge ===================== */
static const int MP_IDS[12]   = { 3900,3901,3902,3910,3911,3912,3920,3921,3922,3930,3931,3932 };
static const int MP_CASTS[12] = {   16,  12,   8,  16,  12,   6,  12,   8,   5,   3,   3,   3 };   /* Magic BaseCastCount */
static const int DRIVE_CHARGES[4] = { 2, 2, 1, 1 };   /* Valor, Wisdom, Master, Final (drive_forms.py) */
#define MAXS 16
static u64 s_addr[MAXS]; static int s_prev[MAXS], s_max[MAXS], s_unit[MAXS], s_cure[MAXS], n_s;
static int mp_charging; static float mp_timer, gauge; static int prev_hp = -1, prev_souls = -1;

static int set_flag(int id, int on) {
    u64 base = rd64(g_flags_slot); u32 off; volatile u32 *w; u32 bit;
    base = base ? rd64(base) : 0;
    if (!base || id < 0 || id >= 100000) return 0;
    off = (u32)((id / 1000) % 10) * 128 + (u32)((id % 1000) / 32) * 4;
    w = (volatile u32 *)(base + off); bit = 0x80000000u >> ((id % 1000) % 32);
    if (!writable((void *)w, 4)) return 0;
    if (on) *w |= bit; else *w &= ~bit;
    return 1;
}
static int mp_index(int id) { int i; for (i = 0; i < 12; i++) if (MP_IDS[i] == id) return i; return -1; }
static void logi(const char *label, int v) { logn(label, 0, v, v); }

/* refresh the slot list from the attunement block; returns number of Sora spells attuned */
static int mp_slots(u64 pgd) {
    u64 blk = pgd ? rd64(pgd + OFF_ATTUNE) : 0; int k, n = 0; u64 na[MAXS]; int np[MAXS], nm[MAXS], nu[MAXS], nc[MAXS];
    if (!blk || !writable((void *)blk, 0x100)) { n_s = 0; return 0; }
    for (k = 0; k < 0x100 && n < MAXS; k += 8) {
        int id = *(volatile int *)(blk + k), cur = *(volatile int *)(blk + k + 4), t = mp_index(id), j, found = -1;
        if (t < 0 || cur < 0 || cur > 999) continue;
        for (j = 0; j < n_s; j++) if (s_addr[j] == blk + k) found = j;
        na[n] = blk + k; nc[n] = (id >= 3930);
        if (found >= 0) { np[n] = s_prev[found]; nm[n] = s_max[found]; nu[n] = s_unit[found]; }
        else { np[n] = cur; nu[n] = 3; nm[n] = MP_CASTS[t] * 3; if (cur > nm[n]) nm[n] = cur; nu[n] = nm[n] / MP_CASTS[t];
               logn("mp: slot spell/remaining ", blk + k, id, cur); }
        n++;
    }
    for (k = 0; k < n; k++) { s_addr[k] = na[k]; s_prev[k] = np[k]; s_max[k] = nm[k]; s_unit[k] = nu[k] ? nu[k] : 1; s_cure[k] = nc[k]; }
    n_s = n;
    return n;
}
static void mp_set_all(int full) {
    int i;
    for (i = 0; i < n_s; i++) { int v = full ? s_max[i] : 0; *(volatile int *)(s_addr[i] + 4) = v; s_prev[i] = v; }
}
static void mp_publish(void) {
    g_mp_charging = mp_charging;
    g_charge_frac = mp_charging ? 1.0f - mp_timer / MP_CHARGE_S : 0.0f;
    g_mp_frac = n_s ? (float)*(volatile int *)(s_addr[0] + 4) / (float)s_max[0] : -1.0f;
}
static void mp_tick_inner(u64 chr, float dt, int fresh);
static void mp_tick(u64 chr, float dt, int fresh) { mp_tick_inner(chr, dt, fresh); mp_publish(); }
static void mp_tick_inner(u64 chr, float dt, int fresh) {
    u64 pgd = chr ? rd64(chr + OFF_PGD) : 0; int i, cast = -1;
    if (!mp_slots(pgd)) return;
    if (fresh) {                                    /* loaded/respawned: resume a charge if MP was left empty */
        int empty = 1; for (i = 0; i < n_s; i++) if (*(volatile int *)(s_addr[i] + 4) > 0) empty = 0;
        if (empty && !mp_charging) { mp_charging = 1; mp_timer = MP_CHARGE_S; set_flag(FLAG_MP_CHARGING, 1); logs("mp: empty on load -> MP Charge\r\n"); }
        if (!empty) { mp_charging = 0; set_flag(FLAG_MP_CHARGING, 0); }   /* flags are saved: never leave 9832 stuck on */
    }
    for (i = 0; i < n_s; i++) {
        int cur = *(volatile int *)(s_addr[i] + 4);
        if (cur > s_max[i]) { s_max[i] = cur; logn("mp: max learned ", s_addr[i], cur, cur); }
        if (cur > s_prev[i]) {                      /* the game refilled it (bonfire rest) */
            if (mp_charging) { mp_charging = 0; set_flag(FLAG_MP_CHARGING, 0); logs("mp: refilled by the game (rest) - charge cancelled\r\n"); }
            s_prev[i] = cur;
        } else if (cur < s_prev[i] && cast < 0) cast = i;
    }
    if (mp_charging) {
        mp_set_all(0);
        mp_timer -= dt;
        if (mp_timer <= 0) {
            mp_set_all(1); mp_charging = 0;
            set_flag(FLAG_MP_CHARGING, 0); g_mp_msg_t = 2.5f;
            logs("mp: MP Charge done - all spells refilled\r\n");
        }
        return;
    }
    if (cast >= 0) {
        int cur = *(volatile int *)(s_addr[cast] + 4), empty;
        float f = s_cure[cast] ? 0.0f : (float)cur / (float)s_max[cast];
        logn("mp: cast, remaining/max ", s_addr[cast], cur, s_max[cast]);
        for (i = 0; i < n_s; i++) {
            int v;
            if (i == cast) { s_prev[i] = s_cure[cast] ? 0 : cur; if (s_cure[cast]) *(volatile int *)(s_addr[i] + 4) = 0; continue; }
            v = (int)(f * (float)s_max[i] / (float)s_unit[i]) * s_unit[i];      /* whole casts, rounded down */
            if (v < *(volatile int *)(s_addr[i] + 4)) *(volatile int *)(s_addr[i] + 4) = v;
            s_prev[i] = *(volatile int *)(s_addr[i] + 4);
        }
        empty = 1; for (i = 0; i < n_s; i++) if (s_prev[i] > 0) empty = 0;
        if (s_cure[cast] || f <= 0.0f || empty) {
            mp_set_all(0); mp_charging = 1; mp_timer = MP_CHARGE_S;
            set_flag(FLAG_MP_CHARGING, 1); logs("mp: MP empty -> MP Charge\r\n");
        }
    }
}
static void drive_add(float pts, const char *why) {
    int f, n, restored = 0;
    gauge += pts;
    g_drive = gauge > DRIVE_FULL ? DRIVE_FULL : gauge;
    logn(why, 0, (int)pts, (int)gauge);
    if (gauge < DRIVE_FULL) return;
    for (f = 0; f < 4; f++)
        for (n = DRIVE_CHARGES[f] - 1; n >= 0; n--)
            if (flag_on(FLAG_DRIVE_CHARGE + 4 * f + n)) { set_flag(FLAG_DRIVE_CHARGE + 4 * f + n, 0); restored++; break; }
    if (restored) { gauge -= DRIVE_FULL; g_drive_msg_t = 2.5f; logi("drive: gauge full - uses restored ", restored); }
    else gauge = DRIVE_FULL;                         /* nothing spent: hold the gauge full */
    g_drive = gauge;
}
/* v122 Drive Recovery items: events set these flags when an item is used (tools/mp_drive.py DRIVE_ITEMS) */
#define FLAG_DRIVE_RECOVERY      9989    /* Drive Recovery: half the gauge */
#define FLAG_HIGH_DRIVE_RECOVERY 9990    /* High Drive Recovery: every spent use back */
static void drive_items_tick(void) {
    int k;
    if (flag_on(FLAG_DRIVE_RECOVERY)) { set_flag(FLAG_DRIVE_RECOVERY, 0); drive_add(DRIVE_FULL * 0.5f, "drive: Drive Recovery used, pts/gauge "); }
    if (flag_on(FLAG_HIGH_DRIVE_RECOVERY)) {
        set_flag(FLAG_HIGH_DRIVE_RECOVERY, 0);
        for (k = 0; k < 3; k++) drive_add(DRIVE_FULL, "drive: High Drive Recovery used, pts/gauge ");   /* max 2 uses per form */
    }
}
static void drive_tick(u64 chr, int fresh) {
    u64 pgd = chr ? rd64(chr + OFF_PGD) : 0; int hp, hpmax, souls;
    /* v48: hits come from hits_tick (enemy HP tracking); the v47 sensor flag is no longer used */
    if (!readable((void *)(chr + OFF_HP), 8)) return;
    hp = *(volatile int *)(chr + OFF_HP); hpmax = *(volatile int *)(chr + OFF_HPMAX);
    if (hpmax <= 0 || hpmax > 100000 || hpmax < hp) hpmax = hp > 0 ? hp : 1;
    if (fresh || prev_hp < 0) prev_hp = hp;
    if (hp > 0 && hp < prev_hp) drive_add((float)(prev_hp - hp) * DRIVE_DAMAGE / (float)hpmax, "drive: damage taken, pts/gauge ");
    prev_hp = hp;
    if (!pgd || !readable((void *)(pgd + OFF_SOULS), 4)) return;
    souls = *(volatile int *)(pgd + OFF_SOULS);
    if (fresh || prev_souls < 0) { prev_souls = souls; logi("drive: souls (check this matches the game) ", souls); return; }
    if (souls != prev_souls) logn("drive: souls changed ", 0, prev_souls, souls);
    if (KILL_POINTS > 0 && souls > prev_souls && souls - prev_souls < 200000) drive_add(KILL_POINTS, "drive: souls gained, pts/gauge ");
    prev_souls = souls;
}
static int pgd_snap[0x200 / 4], pgd_have; static u64 pgd_last;
static void pgd_watch(u64 chr) {
    u64 pgd = chr ? rd64(chr + OFF_PGD) : 0; int i;
    if (!pgd || !readable((void *)pgd, 0x200)) return;
    if (pgd != pgd_last) { pgd_last = pgd; pgd_have = 0; logx("PlayerGameData ", pgd); }
    for (i = 0; i < 0x200 / 4; i++) {
        int v = *(volatile int *)(pgd + 4 * i);
        if (pgd_have && v != pgd_snap[i] && v > -2 && v < 10000000 && pgd_snap[i] > -2 && pgd_snap[i] < 10000000)
            logn("  pgd+off ", (u64)(4 * i), pgd_snap[i], v);
        pgd_snap[i] = v;
    }
    pgd_have = 1;
}

/* ===================== v46 HUD overlay (separate window, GDI) ===================== */
#define RGBC(r, g, b) ((u32)(r) | ((u32)(g) << 8) | ((u32)(b) << 16))
#define KEY_COLOR RGBC(255, 0, 255)
static i64 hud_proc(void *h, u32 m, u64 w, i64 l) { if (m == 0x14) return 1; /* WM_ERASEBKGND: we paint all */ return DefWindowProcA(h, m, w, l); }
static void bar(void *dc, int x, int y, int w, int h, float f, u32 col, u32 back) {
    RECT r; void *b;
    if (f < 0) f = 0; if (f > 1) f = 1;
    r.l = x - 2; r.t = y - 2; r.r = x + w + 2; r.b = y + h + 2; b = CreateSolidBrush(RGBC(12, 12, 20)); FillRect(dc, &r, b); DeleteObject(b);
    r.l = x; r.t = y; r.r = x + w; r.b = y + h; b = CreateSolidBrush(back); FillRect(dc, &r, b); DeleteObject(b);
    r.r = x + (int)(w * f); if (r.r > x) { b = CreateSolidBrush(col); FillRect(dc, &r, b); DeleteObject(b); }
}
/* v48 HUD state (worker -> HUD thread) */
#define MSGQ 4
static const char *volatile g_msgq[MSGQ]; static volatile int g_msg_n; static volatile float g_msg_t;
static volatile u8 g_learned[HUD_NABILS]; static volatile int g_panel;
/* v78: the Drive gauge shows only once Sora has learned a Drive Form (category "Drive Forms" in hud_data.h) */
static int drive_known(void) {
    int c, i;
    for (c = 0; c < HUD_NCATS; c++) {
        const char *a = HUD_CATS[c], *b = "Drive Forms";
        while (*a && *a == *b) { a++; b++; }
        if (*a || *b) continue;
        for (i = 0; i < HUD_NABILS; i++) if (HUD_ABILS[i].cat == c && g_learned[i]) return 1;
        return 0;
    }
    return 1;
}
static void msg_push(const char *t) { if (g_msg_n < MSGQ) { g_msgq[g_msg_n] = t; g_msg_n++; } }
static void text_c(void *dc, const char *t, int cx, int cy) {   /* centred on (cx, cy) */
    POINT sz; int n = slen(t); GetTextExtentPoint32A(dc, t, n, &sz); TextOutA(dc, cx - sz.x / 2, cy - sz.y / 2, t, n);
}
static void text_r(void *dc, const char *t, int rx, int cy) {   /* right-aligned at rx, centred on cy */
    POINT sz; int n = slen(t); GetTextExtentPoint32A(dc, t, n, &sz); TextOutA(dc, rx - sz.x, cy - sz.y / 2, t, n);
}
static void fill(void *dc, int l, int t, int r, int b, u32 c) { RECT q; void *br = CreateSolidBrush(c); q.l = l; q.t = t; q.r = r; q.b = b; FillRect(dc, &q, br); DeleteObject(br); }
static u32 WINAPI hud_thread(void *arg) {
    WNDCLASSA wc; void *hwnd, *game = 0, *font = 0, *small = 0; u8 msg[64]; int shown = 0, last_h = 0, was_ok = -1; u32 pid; float t = 0, full_t = 0;
    (void)arg;
    memset(&wc, 0, sizeof wc);
    wc.proc = hud_proc; wc.inst = g_self; wc.cls = "SoraSoulsHUD";
    RegisterClassA(&wc);
    hwnd = CreateWindowExA(0x80000 | 0x20 | 0x8 | 0x80 | 0x08000000, "SoraSoulsHUD", "SoraSouls HUD", 0x80000000u,
                           0, 0, 10, 10, 0, 0, g_self, 0);
    if (!hwnd) { logs("hud: window creation failed\r\n"); return 0; }
    SetLayeredWindowAttributes(hwnd, KEY_COLOR, 235, 0x1 | 0x2);   /* LWA_COLORKEY | LWA_ALPHA */
    logs("hud: overlay window ready\r\n");
    for (;;) {
        void *fg; RECT cr; POINT o; int W, H, ok, wx, wy, ww, wh, barl, barr, bht, lab, msg_h, y_msg, y1, y2, ptop;
        while (PeekMessageA(msg, 0, 0, 0, 1)) { TranslateMessage(msg); DispatchMessageA(msg); }
        Sleep(33); t += 0.033f;
        if (g_mp_msg_t > 0) g_mp_msg_t -= 0.033f;
        if (g_drive_msg_t > 0) g_drive_msg_t -= 0.033f;
        if (g_msg_n) { g_msg_t += 0.033f; if (g_msg_t > 3.5f) { int i; for (i = 1; i < g_msg_n; i++) g_msgq[i - 1] = g_msgq[i]; g_msg_n--; g_msg_t = 0; } }
        /* v49 (in-game v72: "HUD shows up when I tab out"): only the game's own render window counts – not the
           ModEngine debug console or any other window of this process – and the HUD hides whenever that exact window
           is not in front, is minimised, or is tiny. */
        fg = GetForegroundWindow(); pid = 0; GetWindowThreadProcessId(fg, &pid);
        if (fg && fg != hwnd && is_game_window(fg) && IsWindowVisible(fg)) game = fg;
        /* v78 (playtest: "the hud shows up during cutscenes and loading screens"): also hidden while the game has no
           follow camera (DSR-Gadget's "loaded" test) */
        ok = game && fg == game && !IsIconic(game) && IsWindowVisible(game) && g_live && g_cam_ok && GetClientRect(game, &cr) && cr.r >= 640 && cr.b >= 360;
        if (ok) {   /* v50 (in-game v73: HUD still over the Claude app): the game window must also be the window actually
                       on screen at the HUD's corner – any other app's window covering that spot hides the HUD */
            POINT c; void *top; c.x = (int)(cr.r * 0.86f); c.y = (int)(cr.b * 0.83f); ClientToScreen(game, &c);   /* where the bars sit */
            top = WindowFromPoint(c); if (top) top = GetAncestor(top, 2);   /* GA_ROOT */
            if (top && top != game && top != hwnd) ok = 0;
        }
        if (ok != was_ok) {
            char cls[64]; int n = fg ? GetClassNameA(fg, cls, 63) : 0; cls[n > 0 ? n : 0] = 0;
            logs(ok ? "hud: shown (front window: " : "hud: hidden (front window: "); logs(cls); logx(", pid ", pid);
            was_ok = ok;
        }
        if (!ok) { if (shown) { ShowWindow(hwnd, 0); shown = 0; } continue; }
        W = cr.r; H = cr.b; o.x = 0; o.y = 0; ClientToScreen(game, &o);
        /* v48: bars span exactly the souls counter box (16:9 HUD: x 0.806W .. 0.9235W), just above it */
        barl = (int)(W * 0.806f); barr = (int)(W * 0.9235f); bht = (int)(H * 0.017f); lab = (int)(H * 0.075f);
        msg_h = (int)(H * 0.035f);
        wx = barl - lab; ww = (int)(W * 0.995f) - wx;
        wh = msg_h + (int)(H * 0.062f);
        ptop = 0;
        if (g_panel) { ptop = (int)(H * 0.52f); wh += ptop; wx = (int)(W * 0.60f); ww = (int)(W * 0.995f) - wx; }
        wy = (int)(H * (1.0f - 0.128f)) - wh;
        SetWindowPos(hwnd, (void *)-1, o.x + wx, o.y + wy, ww, wh, 0x10 | 0x40);
        shown = 1;
        if (H != last_h || !font) {
            if (font) DeleteObject(font);
            if (small) DeleteObject(small);
            font = CreateFontA(-(int)(H * 0.019f), 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 3, 0, "Arial");
            small = CreateFontA(-(int)(H * 0.016f), 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 3, 0, "Arial");
            last_h = H;
        }
        {
            void *dc = GetDC(hwnd), *mdc = CreateCompatibleDC(dc), *bmp = CreateCompatibleBitmap(dc, ww, wh), *ob, *of;
            int bl = barl - wx, br = barr - wx, bw = br - bl, cx = bl + bw / 2;
            ob = SelectObject(mdc, bmp); of = SelectObject(mdc, font);
            fill(mdc, 0, 0, ww, wh, KEY_COLOR);
            SetBkMode(mdc, 1);
            y_msg = ptop + msg_h / 2; y1 = ptop + msg_h + (int)(H * 0.012f); y2 = y1 + (int)(H * 0.03f);
            if (g_panel) {                                   /* Abilities panel */
                int i, c, col = 0, rowh = (int)(H * 0.0215f), x0 = (int)(ww * 0.04f), colw = (int)(ww * 0.32f), y = (int)(H * 0.05f);
                int pw = ww - 4, rows_y[3];
                fill(mdc, 0, 0, pw, ptop - (int)(H * 0.01f), RGBC(14, 16, 30));
                fill(mdc, 0, 0, pw, 3, RGBC(255, 200, 30));
                SetTextColor(mdc, RGBC(255, 220, 90)); text_c(mdc, "SORA  -  ABILITIES", pw / 2, (int)(H * 0.025f));
                SelectObject(mdc, small);
                rows_y[0] = rows_y[1] = rows_y[2] = y;
                for (c = 0; c < HUD_NCATS; c++) {
                    col = rows_y[0] <= rows_y[1] ? (rows_y[0] <= rows_y[2] ? 0 : 2) : (rows_y[1] <= rows_y[2] ? 1 : 2);
                    y = rows_y[col];
                    SetTextColor(mdc, RGBC(140, 190, 255)); TextOutA(mdc, x0 + col * colw, y, HUD_CATS[c], slen(HUD_CATS[c])); y += rowh;
                    for (i = 0; i < HUD_NABILS; i++) {
                        if (HUD_ABILS[i].cat != c) continue;
                        if (g_learned[i]) { SetTextColor(mdc, RGBC(235, 235, 235)); TextOutA(mdc, x0 + col * colw + rowh, y, HUD_ABILS[i].name, slen(HUD_ABILS[i].name)); }
                        else { SetTextColor(mdc, RGBC(90, 90, 110)); TextOutA(mdc, x0 + col * colw + rowh, y, "? ? ?", 5); }
                        y += rowh;
                    }
                    rows_y[col] = y + rowh / 2;
                }
                SelectObject(mdc, font);
            }
            if (g_msg_n) {                                   /* message line (pop-ups moved here, v48) */
                fill(mdc, 0, ptop, ww, ptop + msg_h, RGBC(14, 16, 30));
                {   /* v121 (user: "messages are too long for the bar"): smaller font when a message doesn't fit */
                    POINT sz; GetTextExtentPoint32A(mdc, g_msgq[0], slen(g_msgq[0]), &sz);
                    if (sz.x > ww - (int)(W * 0.02f)) SelectObject(mdc, small);
                    SetTextColor(mdc, RGBC(255, 255, 255)); text_r(mdc, g_msgq[0], ww - (int)(W * 0.01f), y_msg);
                    SelectObject(mdc, font);
                }
            }
            if (g_mp_frac >= 0) {
                SetTextColor(mdc, g_mp_charging ? RGBC(255, 140, 200) : RGBC(140, 190, 255)); text_r(mdc, "MP", bl - (int)(H * 0.008f), y1 + bht / 2);
                if (g_mp_charging) {
                    bar(mdc, bl, y1, bw, bht, g_charge_frac, RGBC(255, 105, 180), RGBC(60, 20, 45));
                    SetTextColor(mdc, RGBC(255, 255, 255)); SelectObject(mdc, small); text_c(mdc, "MP CHARGE", cx, y1 + bht / 2); SelectObject(mdc, font);
                } else {
                    int flash = g_mp_msg_t > 0 && ((int)(t * 6) & 1);
                    bar(mdc, bl, y1, bw, bht, g_mp_frac, flash ? RGBC(170, 220, 255) : RGBC(40, 120, 255), RGBC(15, 30, 60));
                    if (g_mp_msg_t > 0) { SetTextColor(mdc, RGBC(255, 255, 255)); SelectObject(mdc, small); text_c(mdc, "MP RESTORED", cx, y1 + bht / 2); SelectObject(mdc, font); }
                }
            }
            if (drive_known()) {   /* v78 (playtest: "drive gauge shouldn't be visible with no drive forms") */
                float shown_drive = g_drive_msg_t > 0 ? 100.0f : g_drive;     /* v48: hold the full bar while "+1" shows */
                int full = shown_drive >= 99.9f, pulse;
                full_t = full ? full_t + 0.033f : 0;          /* v50: pulse for 2 s when it fills, then stay bright */
                pulse = full && full_t < 2.0f && ((int)(t * 3) & 1);
                SetTextColor(mdc, RGBC(255, 220, 90)); text_r(mdc, "DRIVE", bl - (int)(H * 0.008f), y2 + bht / 2);
                bar(mdc, bl, y2, bw, bht, shown_drive / 100.0f, pulse ? RGBC(255, 255, 190) : full ? RGBC(255, 225, 80) : RGBC(255, 200, 30), RGBC(50, 40, 10));
                if (g_drive_msg_t > 0) { SetTextColor(mdc, RGBC(60, 30, 0)); SelectObject(mdc, small); text_c(mdc, "DRIVE +1", cx, y2 + bht / 2); SelectObject(mdc, font); }
            }
            BitBlt(dc, 0, 0, ww, wh, mdc, 0, 0, 0x00CC0020);
            SelectObject(mdc, of); SelectObject(mdc, ob); DeleteObject(bmp); DeleteDC(mdc); ReleaseDC(hwnd, dc);
        }
    }
}


/* ===================== v120 Drive Form outfits (test) =====================
 * User: "change his model so his outfit matches the form he is in". KH2's form models are Sora's normal mesh with
 * other textures, so each form has its own armor set (EquipParamProtector, built by tools/drive_outfits.py): normal
 * Sora = Knight rows 390000-393000 (+upgrade level), Valor 9580000, Wisdom 9590000, Master 9600000, Final 9610000,
 * Anti 9620000 (head, +1000 body, +2000 arms, +3000 legs). Events mirror "form k active" into flags 9984+k.
 * While a flag is on, every place in PlayerGameData (+0..0x1000) and the player ChrIns (+0..0x2000) that holds the
 * four equipped armor ids in a row gets the form's ids (same upgrade levels); when it goes off they go back.
 * UNVERIFIED (first in-game test decides): whether the game redraws the outfit when these ids change. Everything
 * found/written is logged. Heap writes only. */
#define FORM_FLAG_BASE 9984
#define FORM_COUNT     5
static const int FORM_ARMOR[FORM_COUNT] = { 9580000, 9590000, 9600000, 9610000, 9620000 };
#define NORMAL_ARMOR   390000
static int armor_base(int id) {            /* set base of an armor id (any of ours), or 0 */
    int b = id - id % 1000 - ((id / 1000) % 10) * 1000, k;   /* strip level and part */
    if (b == NORMAL_ARMOR) return b;
    for (k = 0; k < FORM_COUNT; k++) if (b == FORM_ARMOR[k]) return b;
    return 0;
}
static int armor_quad(volatile int *v) {   /* v[0..3] = head/body/arms/legs of one of our sets */
    int b = armor_base(v[0]), j;
    if (!b) return 0;
    for (j = 0; j < 4; j++) if (v[j] - v[j] % 1000 != b + 1000 * j || v[j] % 1000 > 10) return 0;
    return b;
}
static int form_set(u64 base, SIZE_T len, int target, const char *where) {
    int n = 0; SIZE_T o;
    if (!base || !readable((void *)base, len)) return 0;
    for (o = 0; o + 16 <= len; o += 4) {
        volatile int *v = (volatile int *)(base + o); int b = armor_quad(v), j;
        if (!b) continue;
        n++;
        if (b == target) continue;
        logn(where, (u64)o, v[0], target + v[0] % 1000);
        for (j = 0; j < 4; j++) v[j] = target + 1000 * j + v[j] % 1000;
    }
    return n;
}
static int form_cur = -2;
static void form_tick(u64 chr) {
    int k, want = -1, target, n1, n2;
    for (k = 0; k < FORM_COUNT; k++) if (flag_on(FORM_FLAG_BASE + k)) { want = k; break; }
    if (want == form_cur) return;
    target = want < 0 ? NORMAL_ARMOR : FORM_ARMOR[want];
    n1 = form_set(chr ? rd64(chr + OFF_PGD) : 0, 0x1000, target, "form outfit: PlayerGameData +off id -> ");
    n2 = form_set(chr, 0x2000, target, "form outfit: ChrIns +off id -> ");
    logn("form outfit: form (-1 none) / armor sets found pgd*100+chr ", 0, want, n1 * 100 + n2);
    if (n1 + n2 > 0 || want < 0) form_cur = want;          /* retry next tick if nothing was found yet */
}

/* ===================== v48 enemy hit tracker (Drive fills on landed hits) =====================
 * The v47 hit-sensor SpEffect never reached Sora (log: no "hit landed"). Instead: a background thread finds
 * character objects (ChrIns layout: vtable in the game image, ChrMapData chain at +0x68 -> +0x28 position,
 * HP +0x3E8 <= max HP +0x3EC) in the game's large private heaps every SCAN_S seconds; the worker re-checks them
 * every tick and counts a hit when an enemy within HIT_RANGE m of Sora loses HP. Read-only. */
#define MAXE 384
#define SCAN_S 8.0f
#define HIT_RANGE 12.0f
static u64 g_mod_lo, g_mod_hi;
static u64 sc_addr[MAXE]; static int sc_n; static volatile int g_scan_ready;      /* scanner -> worker hand-over */
static u64 e_addr[MAXE], e_vt[MAXE]; static int e_hp[MAXE], e_n; static float e_cool[MAXE];
static volatile u64 g_player;
static volatile int g_scan_soon;   /* v78: set on a new area / reload – scan after 1.5 s instead of waiting up to 8 s */
static int chr_like(u64 p) {               /* cheap tests first, VirtualQuery-backed ones last */
    u64 vt = *(volatile u64 *)p, map, pos; int hp, mx;
    if (vt < g_mod_lo || vt >= g_mod_hi || (vt & 7)) return 0;
    hp = *(volatile int *)(p + OFF_HP); mx = *(volatile int *)(p + OFF_HPMAX);
    if (hp <= 0 || mx <= 0 || hp > mx || mx > 1000000) return 0;
    map = *(volatile u64 *)(p + OFF_MAPDATA);
    if (map < 0x10000 || (map & 7) || !readable((void *)(map + OFF_POSDATA), 8)) return 0;
    pos = *(volatile u64 *)(map + OFF_POSDATA);
    return pos >= 0x10000 && !(pos & 7) && readable((void *)(pos + OFF_POS_Z), 4);
}
static u32 WINAPI scan_thread(void *arg) {
    (void)arg;
    for (;;) {
        u8 *a = (u8 *)0x10000; MBI m; int n = 0, w;
        /* v78 (playtest: Donald & Goofy "load in weird places and don't teleport closer"): after a load they stood on
           their map spawn spot until the next scan found them (up to 8 s) */
        for (w = 0; w < (int)(SCAN_S * 4) && !g_scan_soon; w++) Sleep(250);
        if (g_scan_soon) { g_scan_soon = 0; Sleep(1500); }
        if (!g_live || g_scan_ready || !g_player) continue;
        while ((u64)a < 0x7FFFFFFF0000ull && VirtualQuery(a, &m, sizeof m) && n < MAXE) {
            u8 *b = (u8 *)m.BaseAddress, *e = b + m.RegionSize;
            /* the game's own large heap arenas only (committed, private, read/write, >= 1 MB) */
            if (m.State == 0x1000 && m.Type == 0x20000 && m.Protect == 0x04 && m.RegionSize >= 0x100000 && m.RegionSize <= 0x40000000ull) {
                u8 *q;
                for (q = b; q + 0x400 <= e && n < MAXE; q += 16)
                    if ((u64)q != g_player && chr_like((u64)q)) sc_addr[n++] = (u64)q;
            }
            a = e;
        }
        sc_n = n; g_scan_ready = 1;
    }
}
static float dist2_to_player(u64 p, u64 player) {
    u64 m1 = rd64(p + OFF_MAPDATA), p1 = m1 ? rd64(m1 + OFF_POSDATA) : 0;
    u64 m2 = rd64(player + OFF_MAPDATA), p2 = m2 ? rd64(m2 + OFF_POSDATA) : 0; float dx, dy, dz;
    if (!p1 || !p2 || !readable((void *)(p1 + OFF_POS_X), 12) || !readable((void *)(p2 + OFF_POS_X), 12)) return 1e9f;
    dx = *(volatile float *)(p1 + OFF_POS_X) - *(volatile float *)(p2 + OFF_POS_X);
    dy = *(volatile float *)(p1 + OFF_POS_Y) - *(volatile float *)(p2 + OFF_POS_Y);
    dz = *(volatile float *)(p1 + OFF_POS_Z) - *(volatile float *)(p2 + OFF_POS_Z);
    return dx * dx + dy * dy + dz * dz;
}
static void drive_add(float pts, const char *why);
static float fall_t[2];
static u64 pm_addr[2];   /* party members (v61: their damage is not Sora's hit) */
static void hits_tick(u64 chr, float dt) {
    int i, hits = 0;
    g_player = chr;
    if (g_scan_ready) {                     /* merge the new scan, keeping known objects' last HP */
        int k, j, n = 0; u64 na[MAXE], nv[MAXE]; int nh[MAXE]; float nc[MAXE];
        for (k = 0; k < sc_n && n < MAXE; k++) {
            u64 p = sc_addr[k]; int found = -1;
            if (!readable((void *)p, 0x400) || !chr_like(p)) continue;
            for (j = 0; j < e_n; j++) if (e_addr[j] == p) found = j;
            na[n] = p; nv[n] = *(volatile u64 *)p;
            nh[n] = found >= 0 && e_vt[found] == nv[n] ? e_hp[found] : *(volatile int *)(p + OFF_HP);
            nc[n] = found >= 0 ? e_cool[found] : 0; n++;
        }
        for (k = 0; k < n; k++) { e_addr[k] = na[k]; e_vt[k] = nv[k]; e_hp[k] = nh[k]; e_cool[k] = nc[k]; }
        if (n != e_n) logi("hits: tracking characters ", n);
        e_n = n; g_scan_ready = 0;
    }
    for (i = 0; i < e_n; i++) {
        u64 p = e_addr[i]; int hp;
        if (e_cool[i] > 0) e_cool[i] -= dt;
        if (!readable((void *)p, 0x400) || *(volatile u64 *)p != e_vt[i]) { e_hp[i] = -1; continue; }
        hp = *(volatile int *)(p + OFF_HP);
        /* v61 (in-game v60 log: Donald losing HP counted as "hit landed"): skip Donald & Goofy */
        if (e_hp[i] > 0 && hp < e_hp[i] && hp >= 0 && e_cool[i] <= 0 && p != pm_addr[0] && p != pm_addr[1]
            && dist2_to_player(p, chr) < HIT_RANGE * HIT_RANGE) {
            hits++; e_cool[i] = 0.25f;             /* one count per hit (multi-hitbox swings report once) */
        }
        e_hp[i] = hp;
    }
    while (hits-- > 0) drive_add(HIT_POINTS, "drive: hit landed, pts/gauge ");
    {   /* v55 party debug: while the party flag is on, log characters within 6 m of Sora every 3 s */
        static float near_t; static int near_logs;
        near_t -= dt;
        if (near_t <= 0 && flag_on(9855) && near_logs < 40) {
            int k, n = 0;
            near_t = 3.0f;
            for (k = 0; k < e_n; k++) {
                float d2 = dist2_to_player(e_addr[k], chr);
                if (d2 < 36.0f && readable((void *)e_addr[k], 0x400)) {
                    n++; logn("party debug: near char hp/max ", e_addr[k], *(volatile int *)(e_addr[k] + OFF_HP), *(volatile int *)(e_addr[k] + OFF_HPMAX));
                }
            }
            logi("party debug: characters within 6 m ", n); near_logs++;
        }
    }
}

/* ===================== v56 party finder (Donald & Goofy) =====================
 * In-game v81: the map script enables and "moves" Donald & Goofy (they exist, are alive and loaded) but nothing
 * appears near Sora. This finds them among the tracked characters by their NpcParam id (6950 Donald / 6951 Goofy
 * stored as an int somewhere in the character object – the offset is logged so it can be fixed later), logs where
 * they are, and if they are more than PARTY_CATCHUP m from Sora while the party flag is on, places them beside him
 * with the character's own warp request (ChrMapData +0x108/+0x110, the same mechanism Glide uses for Sora). */
#define PARTY_FLAG 9855
#define PARTY_CATCHUP 7.0f     /* v57: was 10 m */
#define PARTY_CATCHUP_FAR 15.0f /* v59: once their home point follows Sora they walk after him; placing is the fallback */
/* v58 (in-game v57: "they sometimes warp outside of bounds"): instead of a fixed x/z offset from Sora (which can land
 * inside a wall or off a ledge), they are placed on Sora's own recent footsteps – spots he stood on the ground a moment
 * ago, so the spot is walkable. Sora's position is sampled every 0.25 s; a sample counts as "on the ground" when his
 * height barely changed since the previous one (not falling, jumping or gliding). */
#define TRAIL_N 24
#define TRAIL_DT 0.25f
static float tr_x[TRAIL_N], tr_y[TRAIL_N], tr_z[TRAIL_N]; static int tr_n, tr_head; static float tr_t, tr_py; static int tr_have;
static void trail_tick(u64 chr, float dt) {
    u64 m = rd64(chr + OFF_MAPDATA), p = m ? rd64(m + OFF_POSDATA) : 0; float x, y, z;
    tr_t -= dt;
    if (tr_t > 0) return;
    tr_t = TRAIL_DT;
    if (!p || !readable((void *)(p + OFF_POS_X), 12)) { tr_have = 0; return; }
    x = *(volatile float *)(p + OFF_POS_X); y = *(volatile float *)(p + OFF_POS_Y); z = *(volatile float *)(p + OFF_POS_Z);
    if (tr_have && (y - tr_py < 0.15f && tr_py - y < 0.15f)) {
        if (tr_n) {   /* new sample far from the last one: Sora warped/loaded somewhere else -> start a new trail */
            int last = (tr_head + TRAIL_N - 1) % TRAIL_N; float dx = x - tr_x[last], dz = z - tr_z[last];
            if (dx * dx + dz * dz > 25.0f) tr_n = 0;
        }
        int last = (tr_head + TRAIL_N - 1) % TRAIL_N;
        float lx = x - tr_x[last], lz = z - tr_z[last];
        /* v65: standing still adds no footsteps (in-game v64: while Sora stood pushing against Donald/Goofy the
           trail filled with his own spot, leaving no spot behind him to send them to) */
        if (!tr_n || lx * lx + lz * lz >= 0.09f) {
            tr_x[tr_head] = x; tr_y[tr_head] = y; tr_z[tr_head] = z;
            tr_head = (tr_head + 1) % TRAIL_N; if (tr_n < TRAIL_N) tr_n++;
        }
    }
    tr_py = y; tr_have = 1;
}
/* newest footstep between lo and hi metres (horizontal) from (sx, sz) and at least 1 m from the spot already given to
 * the other member; returns its index or -1 */
/* v68 (in-game v67 log: the 3 m safety net fired over and over): footsteps are only recorded on the ground, so after a
 * ladder / jump / drop the newest ones can be far below Sora. Picks must now be within 1.5 m of his current height
 * (tp_y, set by party_tick). */
static float tp_y;
static int sora_grounded(float sx, float sy, float sz) {   /* his newest footstep is where he stands now */
    int j; float dx, dy, dz;
    if (!tr_n) return 0;
    j = (tr_head + TRAIL_N - 1) % TRAIL_N; dx = tr_x[j] - sx; dy = tr_y[j] - sy; dz = tr_z[j] - sz;
    return dx * dx + dz * dz < 0.36f && dy < 0.3f && dy > -0.3f;
}
static int trail_pick(float sx, float sz, float lo, float hi, int avoid) {
    int i;
    for (i = 1; i <= tr_n; i++) {
        int j = (tr_head + TRAIL_N - i) % TRAIL_N; float dx = tr_x[j] - sx, dz = tr_z[j] - sz, d = dx * dx + dz * dz;
        if (d < lo * lo || d > hi * hi) continue;
        if (tr_y[j] - tp_y > 1.5f || tp_y - tr_y[j] > 1.5f) continue;
        if (avoid >= 0) { float ax = tr_x[j] - tr_x[avoid], az = tr_z[j] - tr_z[avoid]; if (ax * ax + az * az < 1.0f) continue; }
        return j;
    }
    return -1;
}
/* v59/v60 home point ("nest"). When not fighting, the AI walks back to its home point (the map spawn spot) and ignores
 * enemies on the way. In-game v59 (DLL search of every stored copy of the spawn spot): writing the copies to Sora's
 * footstep made them walk after him – the copies inside each character that did it are ChrIns +0x130 and +0x140
 * (both start equal to the MSB spawn position and stay put when the character moves). v60 writes only those two, on
 * each character's own ChrIns (v59's search also hit the other member's data and a shared object, since both spawn on
 * the same spot). The spot is checked to look like a position (finite, near the spawn spot) before the first write. */
#define NEST_A 0x130
#define NEST_B 0x140
static int ns_ok[2]; static float ns_h[2][3]; static int ns_have[2];
static int pos_like(volatile float *f, const float *ref) {
    float dx = f[0] - ref[0], dy = f[1] - ref[1], dz = f[2] - ref[2];
    return dx < 0.5f && dx > -0.5f && dy < 2.0f && dy > -2.0f && dz < 0.5f && dz > -0.5f;
}
static void nest_discover(int k, u64 p) {
    u64 m = rd64(p + OFF_MAPDATA), pos = m ? rd64(m + OFF_POSDATA) : 0; float p0[3];
    ns_ok[k] = 0; ns_have[k] = 0;
    if (!pos || !readable((void *)(pos + OFF_POS_X), 12) || !readable((void *)(p + NEST_B), 12)) return;
    p0[0] = *(volatile float *)(pos + OFF_POS_X); p0[1] = *(volatile float *)(pos + OFF_POS_Y); p0[2] = *(volatile float *)(pos + OFF_POS_Z);
    ns_ok[k] = pos_like((volatile float *)(p + NEST_A), p0) && pos_like((volatile float *)(p + NEST_B), p0);
    logi(k ? "party nest: Goofy home point at +0x130/+0x140 confirmed (1) / not (0) " : "party nest: Donald home point at +0x130/+0x140 confirmed (1) / not (0) ", ns_ok[k]);
}
static void nest_set(int k, u64 p, float hx, float hy, float hz) {
    volatile float *a = (volatile float *)(p + NEST_A), *b = (volatile float *)(p + NEST_B);
    if (!ns_ok[k] || !writable((void *)a, 12) || !writable((void *)b, 12)) return;
    a[0] = b[0] = hx; a[1] = b[1] = hy; a[2] = b[2] = hz;
    ns_h[k][0] = hx; ns_h[k][1] = hy; ns_h[k][2] = hz; ns_have[k] = 1;
}
static int pm_off[2] = { -1, -1 }; static float pm_t;
/* v62-v67 – out of Sora's way. DS1 has no per-pair collision switch, and turning a member's character collision off
 * for good dropped him through the floor (in-game v92). v67 (user: "they still have collision but just not against
 * Sora"): collision is only off while Sora pushes into a member –
 *   push   – stick / WASD held and the member less than 1.3 m away, with Sora hardly moving (< 0.6 m/s) or the member
 *            within 75 deg of the way Sora walks (1.4 m), for 0.2 s -> flag 9982 (Donald) / 9983 (Goofy) on: the
 *            map's ghost event turns his character collision AND gravity off (so he cannot drop), Sora walks through;
 *   release – once he is more than 1.6 m from Sora, or Sora lets go of the stick, (at least 0.6 s after) or after
 *            4 s at most -> flag off: collision and gravity back on. */
static float pb_t[2], pr_cool[2], pg_t[2], pg_rel[2]; static int pb_slide[2], pg_on[2], pg_init;
static void nest_set(int k, u64 p, float hx, float hy, float hz);
static float fsin(float x) {                   /* |x| <= pi, enough for a direction test */
    float x2;
    while (x > 3.14159265f) x -= 6.2831853f;
    while (x < -3.14159265f) x += 6.2831853f;
    x2 = x * x;
    return x * (1 - x2 / 6 * (1 - x2 / 20 * (1 - x2 / 42 * (1 - x2 / 72))));
}
static float fcos(float x) { return fsin(x + 1.5707963f); }
static float fsqrt(float v) { float r = v > 1 ? v : 1; int i; if (v <= 0) return 0; for (i = 0; i < 20; i++) r = 0.5f * (r + v / r); return r; }
#define GHOST_PUSH 0
#define SWAP_AFTER 0.2f   /* s of pushing before the quick swap (v71: 0.5 s) */
#define PUSH_DIAG 0
static int stuck_now;
static void ghost_set(int k, int on) {
    if (pg_on[k] == on) return;
    pg_on[k] = on; pg_t[k] = 0; set_flag(9982 + k, on);
    logi(k ? (on ? "party: Sora pushing into Goofy -> no collision " : "party: Goofy collision back on ") :
             (on ? "party: Sora pushing into Donald -> no collision " : "party: Donald collision back on "), on);
}
static void party_unblock(u64 chr, float dt) {
    u64 pm = rd64(chr + OFF_MAPDATA), pp = pm ? rd64(pm + OFF_POSDATA) : 0; float sx, sz, fx = 0, fz = 0, fl; int k, i, held;
    if (!pg_init) { pg_init = 1; set_flag(9982, 0); set_flag(9983, 0); }   /* flags are saved: never start "on" */
    if (!pp || !readable((void *)(pp + OFF_POS_X), 16) || !pm_addr[0]) return;
    sx = *(volatile float *)(pp + OFF_POS_X); sz = *(volatile float *)(pp + OFF_POS_Z);
    for (i = 1; i <= tr_n && i <= 6; i++) {    /* way he is walking: a recent footstep at least 0.4 m behind him */
        int j = (tr_head + TRAIL_N - i) % TRAIL_N; float dx = sx - tr_x[j], dz = sz - tr_z[j];
        if (dx * dx + dz * dz >= 0.16f) { fx = dx; fz = dz; break; }
    }
    if (fx == 0 && fz == 0) {                  /* standing against them: his facing */
        /* v69: in-game v68 log – pushing into a member read cos -0.85..-0.99 from the facing fallback while walking
           (footsteps) read +0.8: the game's facing is (-sin a, -cos a) */
        float a = *(volatile float *)(pp + OFF_POS_ANGLE);
        fx = -fsin(a); fz = -fcos(a);
    }
    fl = fx * fx + fz * fz;
    held = move_held();
    {   /* Sora's speed over the last 0.3 s – held stick/WASD but hardly moving = something is in his way */
        static float hx[3], hz[3]; static int hn;
        float ox = hx[hn % 3], oz = hz[hn % 3], vx = sx - ox, vz = sz - oz;
        stuck_now = hn >= 3 && vx * vx + vz * vz < 0.18f * 0.18f;      /* < 0.6 m/s */
        hx[hn % 3] = sx; hz[hn % 3] = sz; hn++;
    }
    for (k = 0; k < 2; k++) {
        u64 p = pm_addr[k], m, q; float dx, dz, d2, dot;
        pb_slide[k] = 0;
        if (!p) { ghost_set(k, 0); continue; }
        m = rd64(p + OFF_MAPDATA); q = m ? rd64(m + OFF_POSDATA) : 0;
        if (!q || !readable((void *)(q + OFF_POS_X), 16)) { pb_t[k] = 0; continue; }
        dx = *(volatile float *)(q + OFF_POS_X) - sx; dz = *(volatile float *)(q + OFF_POS_Z) - sz;
        d2 = dx * dx + dz * dz;
        if (!pg_on[k] && pg_t[k] > 0) pg_t[k] -= dt;
        if (pg_on[k]) {
            pg_t[k] += dt;
            /* v69: in-game v68 collision came back before Sora got through – now only once he is 1.8 m clear
               (at least 1 s), or the stick has been released for 1 s, or after 5 s */
            if (held) pg_rel[k] = 0; else pg_rel[k] += dt;
            if ((pg_t[k] >= 1.0f && d2 > 3.24f) || pg_rel[k] >= 1.0f || pg_t[k] >= 5.0f) ghost_set(k, 0);
            continue;
        }
        dot = dx * fx + dz * fz;               /* cos(angle) > 0.26 ~ within 75 deg of his walking direction */
        {   /* v68 diagnostics: Sora moving and a member within 2 m – log what the push test sees (0.5 s, 80 lines) */
            static float dg_t[2]; static int dg_n;
            dg_t[k] -= dt;
            if (PUSH_DIAG && held && d2 < 4.0f && dg_t[k] <= 0 && dg_n < 80) {
                dg_t[k] = 0.5f; dg_n++;
                logn(k ? "push test Goofy: dist cm / stuck " : "push test Donald: dist cm / stuck ", 0, (int)(fsqrt(d2) * 100), stuck_now);
                logi(fl > 0.0001f && d2 > 0 ? "   in front (cos x100) " : "   no direction ", fl > 0.0001f && d2 > 0 ? (int)(100 * dot / fsqrt(d2 * fl)) : 0);
            }
        }
        /* v71: pushing = stick held and the member within 1.3 m with Sora hardly moving, or in front of him (1.6 m),
           or simply closer than 1.0 m */
        if (held && ((stuck_now && d2 < 1.69f) || d2 < 1.0f
                     || (fl > 0.0001f && d2 < 2.56f && dot > 0 && dot * dot > 0.0676f * d2 * fl)))
            pb_t[k] += dt; else pb_t[k] = 0;
        /* v70: in-game v95 – Sora was still blocked while their collision was off (the event switch is map collision
           only), so the switch is no longer used; a thinner body (NpcParam HitRadius) lets Sora brush past instead */
        if (pb_t[k] >= 0.15f && GHOST_PUSH) { pb_t[k] = 0; pg_rel[k] = 0; ghost_set(k, 1); }
        /* v71 quick swap (user choice after v96: character-vs-character collision can't be switched off): pushing for
           0.5 s -> the member is placed on a footstep 1-3 m behind Sora at his height (the newest one at least 0.6 m
           behind if none), which also becomes his home point; 1 s cooldown */
        if (pb_t[k] >= SWAP_AFTER && pg_t[k] <= 0) {   /* v72: 0.2 s (in-game v71: "goes off slowly") */
            int j = trail_pick(sx, sz, 1.0f, 3.0f, -1);
            if (j < 0) j = trail_pick(sx, sz, 0.6f, 5.0f, -1);
            pb_t[k] = 0;
            if (j < 0) { static int nf; if (nf++ < 10) logi("party: swap wanted but no footstep behind Sora ", k); continue; }
            if (writable((void *)(m + OFF_WARP_ANGLE), 4)) {
                volatile float *w = (volatile float *)(m + OFF_WARP_X);
                w[0] = tr_x[j]; w[1] = tr_y[j] + 0.1f; w[2] = tr_z[j];
                *(volatile float *)(m + OFF_WARP_ANGLE) = *(volatile float *)(pp + OFF_POS_ANGLE);
                *(volatile u8 *)(m + OFF_WARP_FLAG) = 1;
                nest_set(k, p, tr_x[j], tr_y[j], tr_z[j]);
                pg_t[k] = 1.0f;                 /* cooldown (pg_t counts down while the ghost switch is unused) */
                logi(k ? "party: Sora pushing into Goofy -> swapped behind him " : "party: Sora pushing into Donald -> swapped behind him ", j);
            }
        }
    }
}
static void party_tick(u64 chr, float dt) {
    int i, k, used = -1, home_used = -1;
    trail_tick(chr, dt);
    party_unblock(chr, dt);
    for (k = 0; k < 2; k++) if (pr_cool[k] > 0) pr_cool[k] -= dt;
    pm_t -= dt;
    if (pm_t > 0) return;
    pm_t = 0.25f;          /* v63: was 1 s */
    if (!flag_on(PARTY_FLAG)) { ghost_set(0, 0); ghost_set(1, 0); return; }
    for (k = 0; k < 2; k++) {                       /* re-validate known members */
        u64 p = pm_addr[k];
        if (p && (!readable((void *)(p + pm_off[k]), 4) || *(volatile int *)(p + pm_off[k]) != 6950 + k)) pm_addr[k] = 0;
    }
    if (!pm_addr[0] || !pm_addr[1]) {
        /* both ids must sit at the SAME offset in two different characters (6950 alone also occurs as an
           animation id, e.g. in Sora's own ChrIns) */
        static u64 ca[64]; static int co[64], cv[64]; int n = 0, a, b;
        for (i = 0; i < e_n && n < 64; i++) {
            u64 p = e_addr[i]; int o;
            if (!readable((void *)p, 0x800)) continue;
            for (o = 0; o < 0x800 && n < 64; o += 4) {
                int v = *(volatile int *)(p + o);
                if (v == 6950 || v == 6951) { ca[n] = p; co[n] = o; cv[n] = v; n++; }
            }
        }
        for (a = 0; a < n; a++) for (b = 0; b < n; b++)
            if (cv[a] == 6950 && cv[b] == 6951 && co[a] == co[b] && ca[a] != ca[b] && !pm_addr[0]) {
                pm_addr[0] = ca[a]; pm_addr[1] = ca[b]; pm_off[0] = pm_off[1] = co[a];
                logn("party: Donald & Goofy found, npc id offset ", ca[a], co[a], co[a]);
                logx("party: Goofy at ", ca[b]);
                nest_discover(0, ca[a]); nest_discover(1, ca[b]);
            }
        if (!pm_addr[0]) { static int miss; if (miss++ < 5) logi("party: Donald/Goofy not among tracked characters, candidates ", n); }
    }
    for (k = 0; k < 2; k++) {
        u64 p = pm_addr[k], map, pmap, ppos; float d2, sx, sy, sz, catchup;
        if (!p) continue;
        pmap = rd64(chr + OFF_MAPDATA); ppos = pmap ? rd64(pmap + OFF_POSDATA) : 0;
        if (!ppos || !readable((void *)(ppos + OFF_POS_X), 16)) continue;
        sx = *(volatile float *)(ppos + OFF_POS_X); sy = *(volatile float *)(ppos + OFF_POS_Y); sz = *(volatile float *)(ppos + OFF_POS_Z);
        tp_y = sy;
        /* v60: home point = a footstep behind Sora (not his own spot, which they can never reach), a different one
           for each. v63 (in-game v62: "doesn't save immediately or takes a while ... they walk to that direction or
           don't follow closely enough"): moved once Sora is 2.5 m from it (was 4 m), to a footstep 1.2-2.5 m behind
           him; and when the member is lagging (more than 3.5 m from Sora) the map script is asked to re-plan his AI
           (flag 9980/9981) so he heads for the new spot at once instead of finishing the old walk. */
        if (ns_ok[k] && !pb_slide[k]) {
            float hx = ns_h[k][0] - sx, hz = ns_h[k][2] - sz;
            if (!ns_have[k] || hx * hx + hz * hz > 6.25f) {
                int h = trail_pick(sx, sz, 1.2f, 2.5f, home_used);
                if (h < 0) h = trail_pick(sx, sz, 0.8f, 4.0f, home_used);
                if (h >= 0) {
                    home_used = h; nest_set(k, p, tr_x[h], tr_y[h], tr_z[h]);
                    if (dist2_to_player(p, chr) > 3.5f * 3.5f && pr_cool[k] <= 0) { set_flag(9980 + k, 1); pr_cool[k] = 1.5f; }
                } else if ((!ns_have[k] || hx * hx + hz * hz > 36.0f) && sora_grounded(sx, sy, sz))   /* beside him */
                    nest_set(k, p, sx + (k ? -1.5f : 1.5f), sy, sz);
            } else if (ns_have[k]) nest_set(k, p, ns_h[k][0], ns_h[k][1], ns_h[k][2]);   /* keep it (the AI may reset it) */
        }
        catchup = ns_ok[k] ? PARTY_CATCHUP_FAR : PARTY_CATCHUP;
        d2 = dist2_to_player(p, chr);
        {   /* v66 safety net (character collision is off from v92): more than 3 m below Sora = fell -> place him */
            u64 mm = rd64(p + OFF_MAPDATA), qq = mm ? rd64(mm + OFF_POSDATA) : 0;
            /* v73 (in-game v72: "they keep teleporting to catch up" – log: mostly this net, firing whenever Sora
               went up stairs/ramps faster than they did): only a real fall – 10 m+ below, or 3 m+ below for 4 s */
            float my = qq && readable((void *)(qq + OFF_POS_Y), 4) ? *(volatile float *)(qq + OFF_POS_Y) : sy;
            if (my < sy - 3.0f) fall_t[k] += 0.25f; else fall_t[k] = 0;
            if ((my < sy - 10.0f || fall_t[k] >= 4.0f) && sora_grounded(sx, sy, sz)) {
                fall_t[k] = 0;
                static int fl_log; if (fl_log++ < 20) logi(k ? "party: Goofy 3 m+ below Sora -> placed behind him " : "party: Donald 3 m+ below Sora -> placed behind him ", 0);
                d2 = 1e9f; pb_slide[k] = 0;
            }
        }
        if (d2 > catchup * catchup && !pb_slide[k]) {
            map = rd64(p + OFF_MAPDATA);
            if (map && writable((void *)(map + OFF_WARP_ANGLE), 4)) {
                volatile float *w = (volatile float *)(map + OFF_WARP_X);
                float side = k ? -0.6f : 0.6f;
                int j = trail_pick(sx, sz, 1.5f, 4.5f, used);
                if (j < 0) j = trail_pick(sx, sz, 0.8f, 6.0f, used);
                if (j >= 0) { used = j; w[0] = tr_x[j]; w[1] = tr_y[j] + 0.1f; w[2] = tr_z[j]; }
                /* v59 (in-game v58: "they don't show up immediately, I have to walk a little"): Sora hasn't left
                   footsteps yet (just loaded / standing still) -> right beside where he stands */
                else if (sora_grounded(sx, sy, sz)) { w[0] = sx + side; w[1] = sy + 0.1f; w[2] = sz; }
                else continue;                  /* v68: Sora in the air / on a ladder: wait until he lands */
                *(volatile float *)(map + OFF_WARP_ANGLE) = *(volatile float *)(ppos + OFF_POS_ANGLE);
                *(volatile u8 *)(map + OFF_WARP_FLAG) = 1;
                logn(k ? "party: Goofy far (dist^2) -> placed by Sora " : "party: Donald far (dist^2) -> placed by Sora ", p, (int)d2, j);
            }
        }
    }
}
/* messages + learned list, polled from event flags */
static void hud_flags_tick(void) {
    int i;
    for (i = 0; i < HUD_NMSGS; i++)
        if (flag_on(HUD_MSGS[i].flag)) { set_flag(HUD_MSGS[i].flag, 0); msg_push(HUD_MSGS[i].text); logs("hud msg: "); logs(HUD_MSGS[i].text); logs("\r\n"); }
    for (i = 0; i < HUD_NABILS; i++) {
        int fa = HUD_ABILS[i].fa, fb = HUD_ABILS[i].fb;
        g_learned[i] = (u8)(fa == 0 || (fa > 0 && flag_on(fa)) || (fb > 0 && flag_on(fb)));
    }
}

static u32 WINAPI worker(void *arg) {
    char path[600]; int n; u64 slot; XInputGetState_t xget;
    i64 freq, t0, t1; float prev_y = 0, prev_x = 0, prev_z = 0, still = 0, rise_t = 0, level_timer = 0;
    int have_prev = 0, gliding = 0, warp_mode = 0; u64 last_chr = 0;
    int glide_lv = 0, jump_lv = 1, last_glide_lv = -1, last_jump_lv = -1;
    int test_glide = -1, test_jump = -1, f9_was = 0, f10_was = 0, f11_was = 0;
    float probe_wait = 15.0f, probe_t = 0, md_t = 0, pgd_t = 0, hf_t = 0, back_t = 0; int probe_scanned = 0, md_fresh = 1, j_was = 0, back_done = 0;
    (void)arg;
    n = (int)GetModuleFileNameA(g_self, path, 560);
    while (n > 0 && path[n - 1] != '\\' && path[n - 1] != '/') n--;
    { const char *f = "sora_glide.log"; int i = 0; while (f[i]) { path[n + i] = f[i]; i++; } path[n + i] = 0; }
    g_log = CreateFileA(path, 0x40000000, 1, 0, 2, 0x80, 0);   /* GENERIC_WRITE, share read, CREATE_ALWAYS */
    logs("SoraSouls glide v78 (MP Charge + Drive gauge + HUD + abilities + party msgs; HUD hides while loading) started\r\n");

    Sleep(5000);                                       /* let the game finish unpacking/initialising */
    logx("module base ", (u64)GetModuleHandleA(0));
    { u8 *mb = GetModuleHandleA(0); u32 pe = *(u32 *)(mb + 0x3C); g_mod_lo = (u64)mb; g_mod_hi = (u64)mb + *(u32 *)(mb + pe + 0x50); }
    slot = find_slot(PAT_WCM, sizeof PAT_WCM / sizeof PAT_WCM[0], "WorldChrMan");
    g_flags_slot = find_slot(PAT_FLAGS, sizeof PAT_FLAGS / sizeof PAT_FLAGS[0], "EventFlags");
    g_followcam_slot = find_slot(PAT_FOLLOWCAM, sizeof PAT_FOLLOWCAM / sizeof PAT_FOLLOWCAM[0], "ChrFollowCam");
    g_camman_slot = find_slot(PAT_CAMMAN, sizeof PAT_CAMMAN / sizeof PAT_CAMMAN[0], "CamMan");
    logx("ChrFollowCam slot ", g_followcam_slot); logx("CamMan slot ", g_camman_slot);
    if (!g_flags_slot) logs("WARNING: EventFlags pattern not found - Glide stays locked\r\n");
    if (PROBE) { g_gdm_slot = find_slot(PAT_GDM, sizeof PAT_GDM / sizeof PAT_GDM[0], "GameDataMan?"); logx("GameDataMan slot ", g_gdm_slot);
                 if (g_gdm_slot) { u64 g = rd64(g_gdm_slot); logx("GameDataMan ", g); logx("GameDataMan+0x10 ", g ? rd64(g + 0x10) : 0); } }
    if (!slot) { logs("ERROR: WorldChrMan pattern not found - glide disabled\r\n"); return 0; }
    logx("WorldChrMan slot ", slot);
    xget = load_xinput(); g_xget = xget;
    QueryPerformanceFrequency(&freq); QueryPerformanceCounter(&t0);

    for (;;) {
        u64 wcm, chr, map, pos; volatile u32 *flags; volatile float *py; float y, dt, vy;
        Sleep(10);
        QueryPerformanceCounter(&t1); dt = (float)(t1 - t0) / (float)freq; t0 = t1;
        if (dt <= 0 || dt > 0.25f) { have_prev = 0; continue; }

        if (g_followcam_slot) {   /* v78: loading-screen test + camera log (to find a cutscene signal) */
            static u64 last_cam = 1, last_active = 1;
            u64 c0 = rd64(g_followcam_slot), c1 = c0 ? rd64(c0 + 0x60) : 0, c2 = c1 ? rd64(c1 + 0x60) : 0;
            u64 cm = g_camman_slot ? rd64(g_camman_slot) : 0, active = cm ? rd64(cm + 0x10) : 0;
            g_cam_ok = c2 != 0;
            if ((c2 != 0) != (last_cam != 0) || active != last_active) {
                logx("camera: follow cam ", c2); logx("        CamMan+0x10 ", active);
                last_cam = c2; last_active = active;
            }
        }
        wcm = rd64(slot); chr = wcm ? rd64(wcm + OFF_CHRINS) : 0;
        map = chr ? rd64(chr + OFF_MAPDATA) : 0; pos = map ? rd64(map + OFF_POSDATA) : 0;
        if (!pos || !writable((void *)(chr + OFF_FLAGS1), 4) || !writable((void *)(pos + OFF_POS_Y), 4)) {
            if (gliding) logs("glide end: character data gone (loading/death)\r\n");
            g_live = 0;
            gliding = 0; have_prev = 0; last_chr = 0; continue;
        }
        if (chr != last_chr) { logx("player ChrIns ", chr); last_chr = chr; have_prev = 0; gliding = 0; md_fresh = 1; g_scan_soon = 1; }
        flags = (volatile u32 *)(chr + OFF_FLAGS1); py = (volatile float *)(pos + OFF_POS_Y);
        if (TEST_KEYS) {
            u32 pid = 0; int f9, f10;
            GetWindowThreadProcessId(GetForegroundWindow(), &pid);
            f9 = game_focused() && (GetAsyncKeyState(VK_F9) & 0x8000);
            f10 = game_focused() && (GetAsyncKeyState(VK_F10) & 0x8000);
            if (f9 && !f9_was) { test_glide = (glide_lv + 1) % 4; level_timer = 0; logs("test key: glide level override\r\n"); }
            if (f10 && !f10_was) { test_jump = jump_lv % 3 + 1; level_timer = 0; logs("test key: high jump level override\r\n"); }
            f9_was = f9; f10_was = f10;
        }
        g_live = 1;
        md_t -= dt;
        if (md_t <= 0) { md_t = 0.1f; mp_tick(chr, 0.1f, md_fresh); drive_tick(chr, md_fresh); hits_tick(chr, 0.1f); party_tick(chr, 0.1f); form_tick(chr); drive_items_tick(); md_fresh = 0; }
        hf_t -= dt;
        if (hf_t <= 0) { hf_t = 0.2f; hud_flags_tick(); }
        {   /* v48 Abilities panel: J key, or (v50) hold L3 (left stick click) for 0.8 s – BACK also opened gestures */
            u32 pid = 0; int jk, back = 0, i;
            GetWindowThreadProcessId(GetForegroundWindow(), &pid);
            jk = game_focused() && (GetAsyncKeyState(0x4A) & 0x8000);
            if (jk && !j_was) { g_panel = !g_panel; logs("panel toggled (J)\r\n"); }
            j_was = jk;
            if (xget) for (i = 0; i < 4; i++) { XSTATE st; memset(&st, 0, sizeof st); if (xget(i, &st) == 0 && (st.wButtons & 0x0040)) back = 1; }   /* XINPUT_GAMEPAD_LEFT_THUMB */
            if (back) { back_t += dt; if (back_t > 0.8f && !back_done) { g_panel = !g_panel; back_done = 1; logs("panel toggled (L3)\r\n"); } }
            else { back_t = 0; back_done = 0; }
        }
        if (PROBE_PGD) { pgd_t -= dt; if (pgd_t <= 0) { pgd_t = 0.5f; pgd_watch(chr); } }
        if (TEST_KEYS) {
            u32 pid = 0; int f11;
            GetWindowThreadProcessId(GetForegroundWindow(), &pid);
            f11 = game_focused() && (GetAsyncKeyState(VK_F11) & 0x8000);
            if (f11 && !f11_was) drive_add(DRIVE_FULL, "test key F11: drive gauge +100, pts/gauge ");
            f11_was = f11;
        }
        if (PROBE) {
            u32 pid = 0; int f11;
            GetWindowThreadProcessId(GetForegroundWindow(), &pid);
            f11 = game_focused() && (GetAsyncKeyState(VK_F11) & 0x8000);
            if (!probe_scanned) { probe_wait -= dt; if (probe_wait <= 0) { probe_scan(); probe_scanned = 1; } }
            if (f11 && !f11_was) { logs("F11: probe rescan\r\n"); probe_scan(); probe_scanned = 1; }
            f11_was = f11;
            probe_t -= dt;
            if (probe_t <= 0) { probe_t = 0.5f; probe_tick(wcm, chr); }
        }
        level_timer -= dt;
        if (level_timer <= 0) {
            int i;
            level_timer = 0.5f;
            glide_lv = 0; for (i = 0; i < 3 && flag_on(FLAG_GLIDE1 + i); i++) glide_lv++;
            jump_lv = 1;  for (i = 0; i < 2 && flag_on(FLAG_JUMP2 + i); i++) jump_lv++;
            if (test_glide >= 0) glide_lv = test_glide;
            if (test_jump >= 0) jump_lv = test_jump;
            if (glide_lv != last_glide_lv || jump_lv != last_jump_lv) {
                logx("levels: glide ", (u64)glide_lv); logx("        high jump ", (u64)jump_lv);
                last_glide_lv = glide_lv; last_jump_lv = jump_lv;
            }
        }
        y = *py;
        {
            float x = *(volatile float *)(pos + OFF_POS_X), z = *(volatile float *)(pos + OFF_POS_Z), hs;
            if (!have_prev) { prev_y = y; prev_x = x; prev_z = z; have_prev = 1; continue; }
            hs = ((x - prev_x) * (x - prev_x) + (z - prev_z) * (z - prev_z)) / (dt * dt);
            warp_mode = hs < STILL_SPEED * STILL_SPEED;          /* squared speeds */
            prev_x = x; prev_z = z;
        }
        vy = (y - prev_y) / dt;
        if (vy > JUMP_RISE) rise_t += dt; else rise_t = 0;

        if (!gliding && rise_t >= JUMP_HOLD_S && jump_lv > 1) {   /* High Jump LV2/MAX: add the extra share of the climb */
            float boosted = prev_y + (y - prev_y) * JUMP_MULT[jump_lv];
            *py = boosted; y = boosted;
        }

        if (!gliding) {
            if (glide_lv > 0 && vy < FALL_TRIGGER && glide_button(xget)) {
                gliding = 1; still = 0;
                *flags |= FLAG_NOGRAVITY;
                logf1("glide start, fall speed ", vy);
            }
        } else {
            int stop = 0;
            if (!glide_button(xget)) { stop = 1; logs("glide end: button released\r\n"); }
            else {
                /* prev_y is the height we wrote last tick. If the game keeps putting Sora back above it, he is
                   standing on something (or our writes are being ignored – the log tells the two apart by the
                   time since glide start). */
                float want = y - GLIDE_SINK[glide_lv] * dt;     /* sink slowly from where he is now */
                /* v42: standing still in the air the game undoes plain height writes (it only re-reads the
                   position while Sora moves) -> stutter + hover. If our write keeps getting undone, switch this
                   glide to the game's own warp request, which moves the character properly. */
                if (y > prev_y + 0.002f) still += dt; else still = 0;
                if (still > GROUND_STILL_S) { stop = 1; logf1("glide end: landed at y ", y); }
                else if (warp_mode && writable((void *)(map + OFF_WARP_ANGLE), 4)) {
                    volatile float *w = (volatile float *)(map + OFF_WARP_X);
                    w[0] = *(volatile float *)(pos + OFF_POS_X); w[1] = want; w[2] = *(volatile float *)(pos + OFF_POS_Z);
                    *(volatile float *)(map + OFF_WARP_ANGLE) = *(volatile float *)(pos + OFF_POS_ANGLE);
                    *(volatile u8 *)(map + OFF_WARP_FLAG) = 1;
                    y = want;
                }
                else { *py = want; y = want; }
            }
            if (stop) { *flags &= ~FLAG_NOGRAVITY; gliding = 0; }
        }
        prev_y = y;
    }
}

BOOL WINAPI DllMain(void *inst, u32 reason, void *reserved) {
    (void)reserved;
    if (reason == 1) {                                  /* DLL_PROCESS_ATTACH */
        g_self = inst;
        DisableThreadLibraryCalls(inst);
        CreateThread(0, 0, worker, 0, 0, 0);
        CreateThread(0, 0, hud_thread, 0, 0, 0);
        CreateThread(0, 0, scan_thread, 0, 0, 0);
    }
    return 1;
}
