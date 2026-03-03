#   _____                   ________  ________ 
#  /  _  \   _____ ______  /  _____/ /  _____/ 
# /  /_\  \ /     \\____ \/   \  ___/   \  ___ 
#/    |    \  Y Y  \  |_> >    \_\  \    \_\  \
#\____|__  /__|_|  /   __/ \______  /\______  /
#        \/      \/|__|           \/        \/ 
#                           Made by CrxticScripts/


import threading
import time
import json
import math
import random
import tkinter as tk
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import deque

# ═══════════════════════════════════════════════════════════════════════════════
#  AMPGG
# ═══════════════════════════════════════════════════════════════════════════════

WINDOW_W   = 210
WINDOW_H   = 95
BOMB_TIME  = 40.0
SERVER_PORT = 3000

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG        = "#05080F"
C_BG2       = "#080C18"
C_CYAN      = "#00E5FF"
C_CYAN_DIM  = "#006070"
C_WHITE     = "#E8EEF5"
C_DIM       = "#1E2A38"
C_ORANGE    = "#FF8C00"
C_RED       = "#FF1A1A"
C_RED_DIM   = "#4A0000"
C_GREEN     = "#00FF88"
C_GRID      = "#0A1020"
C_BORDER    = "#0D1F35"
C_ACCENT    = "#003344"

# ═══════════════════════════════════════════════════════════════════════════════
#  SHARED STATE
# ═══════════════════════════════════════════════════════════════════════════════
state = {
    "planted":       False,
    "plant_time":    None,
    "map_name":      "WAIT",
    "defused":       False,
    "exploded":      False,
    "active":        False,
    "round_wins_ct": 0,
    "round_wins_t":  0,
}
state_lock = threading.Lock()

# ═══════════════════════════════════════════════════════════════════════════════
#  GSI HTTP SERVER
#  Bomb logic ported from Flask reference — handles all edge cases:
#    • round phase resets (over / freezetime)
#    • dual bomb-state paths: round.bomb AND bomb.state (CS2 sends both)
#    • active guard so re-broadcasts don't reset the plant timer
#    • defused / exploded captured as distinct events for UI flash
# ═══════════════════════════════════════════════════════════════════════════════
class GSIHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode("utf-8")
        self.send_response(200)
        self.end_headers()
        try:
            data = json.loads(body)
        except Exception:
            return

        # ── Parse all relevant fields ─────────────────────────────────────────
        map_data   = data.get("map",   {})
        bomb_data  = data.get("bomb",  {})
        round_data = data.get("round", {})

        # Map name — strip de_ prefix, uppercase
        map_name = map_data.get("name", "")
        map_name = map_name.replace("de_", "").upper() or "WAIT"

        # Scores
        ct_score = map_data.get("team_ct", {}).get("score", 0)
        t_score  = map_data.get("team_t",  {}).get("score", 0)

        # Round phase (freezetime / over = reset)
        round_phase = round_data.get("phase", "")

        # Bomb status — CS2 sends it in TWO places; check both like Flask version
        bomb_status = (
            round_data.get("bomb")          # round.bomb  (older path)
            or bomb_data.get("state")       # bomb.state  (newer path)
            or ""
        )

        # ── Update shared state under lock ────────────────────────────────────
        with state_lock:
            state["map_name"]      = map_name
            state["round_wins_ct"] = ct_score
            state["round_wins_t"]  = t_score

            # 1. Round ended or freeze — full reset
            if round_phase in ("over", "freezetime"):
                state["planted"]    = False
                state["plant_time"] = None
                state["defused"]    = False
                state["exploded"]   = False
                state["active"]     = False

            # 2. Bomb just planted — only trigger once (active guard)
            elif bomb_status == "planted" and not state["active"]:
                state["planted"]    = True
                state["plant_time"] = time.time()
                state["active"]     = True
                state["defused"]    = False
                state["exploded"]   = False

            # 3. Bomb defused
            elif bomb_status == "defused":
                state["planted"]    = False
                state["plant_time"] = None
                state["active"]     = False
                state["defused"]    = True
                state["exploded"]   = False

            # 4. Bomb exploded
            elif bomb_status == "exploded":
                state["planted"]    = False
                state["plant_time"] = None
                state["active"]     = False
                state["defused"]    = False
                state["exploded"]   = True

    def log_message(self, *args):
        pass   # silence HTTP access log spam

def run_server():
    server = HTTPServer(("127.0.0.1", SERVER_PORT), GSIHandler)
    server.serve_forever()

# ═══════════════════════════════════════════════════════════════════════════════
#  PARTICLE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
class Particle:
    def __init__(self, x, y, color):
        self.x     = x
        self.y     = y
        self.vx    = random.uniform(-1.5, 1.5)
        self.vy    = random.uniform(-2.5, -0.5)
        self.life  = 1.0
        self.decay = random.uniform(0.04, 0.09)
        self.color = color
        self.size  = random.randint(1, 3)

    def update(self):
        self.x    += self.vx
        self.y    += self.vy
        self.vy   += 0.05
        self.life -= self.decay
        return self.life > 0

class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit(self, x, y, count=6, color=C_CYAN):
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def update(self):
        self.particles = [p for p in self.particles if p.update()]

    def draw(self, canvas):
        for p in self.particles:
            brightness = p.life
            base = p.color.lstrip("#")
            r = int(int(base[0:2], 16) * brightness)
            g = int(int(base[2:4], 16) * brightness)
            b = int(int(base[4:6], 16) * brightness)
            col = f"#{r:02x}{g:02x}{b:02x}"
            canvas.create_rectangle(
                p.x, p.y, p.x + p.size, p.y + p.size,
                fill=col, outline=""
            )

# ═══════════════════════════════════════════════════════════════════════════════
#  CRT EFFECTS
# ═══════════════════════════════════════════════════════════════════════════════
class CRTEffects:
    def __init__(self, canvas, w, h):
        self.canvas = canvas
        self.w = w
        self.h = h
        self._scanline_ids = []
        self._corner_ids   = []
        self._noise_ids    = []
        self._frame        = 0

    def draw_scanlines(self):
        for sid in self._scanline_ids:
            self.canvas.delete(sid)
        self._scanline_ids.clear()
        for y in range(0, self.h, 3):
            sid = self.canvas.create_line(
                0, y, self.w, y,
                fill="#000000", width=1,
                stipple="gray25"
            )
            self._scanline_ids.append(sid)

    def draw_corner_glow(self, color=C_CYAN_DIM):
        for cid in self._corner_ids:
            self.canvas.delete(cid)
        self._corner_ids.clear()
        for i in range(8):
            cid = self.canvas.create_arc(
                -i*3, -i*3, i*6, i*6,
                start=0, extent=90,
                outline=color, width=1, style=tk.ARC
            )
            self._corner_ids.append(cid)
        for i in range(8):
            cid = self.canvas.create_arc(
                self.w - i*6, -i*3, self.w + i*3, i*6,
                start=90, extent=90,
                outline=color, width=1, style=tk.ARC
            )
            self._corner_ids.append(cid)

    def draw_noise(self):
        for nid in self._noise_ids:
            self.canvas.delete(nid)
        self._noise_ids.clear()
        self._frame += 1
        if self._frame % 3 == 0:
            for _ in range(4):
                x = random.randint(0, self.w)
                y = random.randint(0, self.h)
                nid = self.canvas.create_rectangle(
                    x, y, x+1, y+1,
                    fill="#FFFFFF", outline=""
                )
                self._noise_ids.append(nid)

# ═══════════════════════════════════════════════════════════════════════════════
#  WAVEFORM BAR
# ═══════════════════════════════════════════════════════════════════════════════
class WaveformBar:
    def __init__(self, canvas, x, y, w, h):
        self.canvas  = canvas
        self.x, self.y, self.w, self.h = x, y, w, h
        self.history = deque(maxlen=w)
        self._ids    = []

    def push(self, value, max_val=BOMB_TIME):
        self.history.append(value / max_val)

    def draw(self, color=C_CYAN):
        for i in self._ids:
            self.canvas.delete(i)
        self._ids.clear()
        n = len(self.history)
        if n < 2:
            return
        for i, v in enumerate(self.history):
            bar_h = max(1, int(v * self.h))
            x0 = self.x + i
            y0 = self.y + self.h - bar_h
            y1 = self.y + self.h
            brightness = 0.2 + 0.8 * (i / n)
            base = color.lstrip("#")
            r = int(int(base[0:2], 16) * brightness)
            g = int(int(base[2:4], 16) * brightness)
            b = int(int(base[4:6], 16) * brightness)
            col = f"#{r:02x}{g:02x}{b:02x}"
            iid = self.canvas.create_line(x0, y0, x0, y1, fill=col, width=1)
            self._ids.append(iid)

# ═══════════════════════════════════════════════════════════════════════════════
#  ANIMATED BORDER
# ═══════════════════════════════════════════════════════════════════════════════
class AnimatedBorder:
    def __init__(self, canvas, w, h, radius=8):
        self.canvas = canvas
        self.w, self.h = w, h
        self.r = radius
        self._ids = []
        self._t   = 0.0

    def draw(self, color, pulse_speed=2.0):
        for i in self._ids:
            self.canvas.delete(i)
        self._ids.clear()
        self._t += 0.05 * pulse_speed
        glow = 0.4 + 0.6 * abs(math.sin(self._t))
        base = color.lstrip("#")
        r = int(int(base[0:2], 16) * glow)
        g = int(int(base[2:4], 16) * glow)
        b = int(int(base[4:6], 16) * glow)
        col = f"#{r:02x}{g:02x}{b:02x}"
        r2  = self.r
        pad = 1
        for item in [
            self.canvas.create_line(r2, pad, self.w-r2, pad, fill=col, width=1),
            self.canvas.create_line(r2, self.h-pad, self.w-r2, self.h-pad, fill=col, width=1),
            self.canvas.create_line(pad, r2, pad, self.h-r2, fill=col, width=1),
            self.canvas.create_line(self.w-pad, r2, self.w-pad, self.h-r2, fill=col, width=1),
        ]:
            self._ids.append(item)
        for x0, y0, x1, y1, start in [
            (pad, pad, r2*2, r2*2, 90),
            (self.w-r2*2, pad, self.w-pad, r2*2, 0),
            (pad, self.h-r2*2, r2*2, self.h-pad, 180),
            (self.w-r2*2, self.h-r2*2, self.w-pad, self.h-pad, 270),
        ]:
            iid = self.canvas.create_arc(
                x0, y0, x1, y1,
                start=start, extent=90,
                outline=col, width=1, style=tk.ARC
            )
            self._ids.append(iid)
        # inner dim ring
        dim_r = max(0, int(int(base[0:2], 16) * glow * 0.18))
        dim_g = max(0, int(int(base[2:4], 16) * glow * 0.18))
        dim_b = max(0, int(int(base[4:6], 16) * glow * 0.18))
        dim_col = f"#{dim_r:02x}{dim_g:02x}{dim_b:02x}"
        iid = self.canvas.create_rectangle(3, 3, self.w-3, self.h-3, outline=dim_col, width=1)
        self._ids.append(iid)

# ═══════════════════════════════════════════════════════════════════════════════
#  SEGMENT DISPLAY  (7-segment style digits)
# ═══════════════════════════════════════════════════════════════════════════════
class SegmentDisplay:
    # segment index → (x0, y0, x1, y1) in a 9x16 cell
    SEG_RECTS = {
        0: (1,  0,  8,  2),   # top
        1: (0,  1,  2,  8),   # top-left
        2: (7,  1,  9,  8),   # top-right
        3: (1,  7,  8,  9),   # mid
        4: (0,  8,  2, 15),   # bot-left
        5: (7,  8,  9, 15),   # bot-right
        6: (1, 13,  8, 15),   # bot
        7: (3, 13,  6, 15),   # dot
    }
    DIGIT_SEGS = {
        '0': [0,1,2,4,5,6],
        '1': [2,5],
        '2': [0,2,3,4,6],
        '3': [0,2,3,5,6],
        '4': [1,2,3,5],
        '5': [0,1,3,5,6],
        '6': [0,1,3,4,5,6],
        '7': [0,2,5],
        '8': [0,1,2,3,4,5,6],
        '9': [0,1,2,3,5,6],
        '.': [7],
        ' ': [],
    }

    def __init__(self, canvas, x, y, scale=1.55):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.scale = scale
        self._ids  = []

    def _sr(self, idx):
        r = self.SEG_RECTS[idx]
        s = self.scale
        return (int(r[0]*s), int(r[1]*s), int(r[2]*s), int(r[3]*s))

    def render(self, text, color, dim_color):
        for i in self._ids:
            self.canvas.delete(i)
        self._ids.clear()
        cx = self.x
        for ch in text:
            on_segs  = self.DIGIT_SEGS.get(ch, [])
            off_segs = [s for s in range(7) if s not in on_segs]
            cw = int(10 * self.scale)
            if ch == '.':
                cw = int(5 * self.scale)
            for seg in on_segs:
                r = self._sr(seg)
                iid = self.canvas.create_rectangle(
                    cx+r[0], self.y+r[1], cx+r[2], self.y+r[3],
                    fill=color, outline=""
                )
                self._ids.append(iid)
            for seg in off_segs:
                r = self._sr(seg)
                iid = self.canvas.create_rectangle(
                    cx+r[0], self.y+r[1], cx+r[2], self.y+r[3],
                    fill=dim_color, outline=""
                )
                self._ids.append(iid)
            cx += cw

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN OVERLAY
# ═══════════════════════════════════════════════════════════════════════════════
class Overlay:
    TICK_MS = 33   # ~30 fps

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AMPGG")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.93)
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}+1700+50")
        self.root.configure(bg=C_BG)
        self.root.resizable(False, False)

        self.cv = tk.Canvas(
            self.root,
            width=WINDOW_W, height=WINDOW_H,
            bg=C_BG, highlightthickness=0
        )
        self.cv.pack()

        # sub-systems
        self.particles = ParticleSystem()
        self.crt       = CRTEffects(self.cv, WINDOW_W, WINDOW_H)
        self.border    = AnimatedBorder(self.cv, WINDOW_W, WINDOW_H, radius=10)
        self.waveform  = WaveformBar(self.cv, 5, 83, WINDOW_W - 10, 6)
        self.seg       = SegmentDisplay(self.cv, 0, 0, scale=1.55)

        # animation state
        self._frame         = 0
        self._flash_alpha   = 0.0
        self._flash_color   = C_CYAN
        self._last_mode     = "standby"
        self._blink_state   = True
        self._blink_counter = 0
        self._heartbeat_t   = 0.0
        self._dyn_ids       = []

        # static background (drawn once)
        self._draw_static_bg()

        # scanlines + corners (drawn once on top of static bg)
        self.crt.draw_scanlines()
        self.crt.draw_corner_glow()

        # drag
        self._drag_x = 0
        self._drag_y = 0
        self.root.bind("<ButtonPress-1>",   self._drag_start)
        self.root.bind("<B1-Motion>",       self._drag_motion)
        # right-double-click to quit
        self.root.bind("<Double-Button-3>", lambda e: self.root.destroy())

        self._tick()

    # ─────────────────────────────────────────────────────────────────────────
    def _draw_static_bg(self):
        cv = self.cv
        cv.create_rectangle(0, 0, WINDOW_W, WINDOW_H, fill=C_BG, outline="")
        # grid
        for x in range(0, WINDOW_W, 10):
            cv.create_line(x, 0, x, WINDOW_H, fill=C_GRID, width=1)
        for y in range(0, WINDOW_H, 10):
            cv.create_line(0, y, WINDOW_W, y, fill=C_GRID, width=1)
        # top/bottom accent lines
        cv.create_rectangle(0, 0,  WINDOW_W, 1,  fill=C_CYAN_DIM, outline="")
        cv.create_rectangle(0, WINDOW_H-2, WINDOW_W, WINDOW_H, fill=C_CYAN_DIM, outline="")
        # left bar
        cv.create_rectangle(0, 0, 2, WINDOW_H, fill=C_ACCENT, outline="")
        # right bar
        cv.create_rectangle(WINDOW_W-2, 0, WINDOW_W, WINDOW_H, fill=C_ACCENT, outline="")
        # diagonal accents top-right
        for i in range(4):
            off = 12 + i * 6
            cv.create_line(WINDOW_W-off, 0, WINDOW_W, off, fill=C_BORDER, width=1)
        # header separator
        cv.create_line(0, 14, WINDOW_W, 14, fill=C_BORDER, width=1)
        # bottom separator (above waveform)
        cv.create_line(0, 80, WINDOW_W, 80, fill=C_BORDER, width=1)
        # AMPGG micro-logo
        cv.create_text(8, 7, text="AMPGG", font=("Courier", 6, "bold"),
                       fill=C_CYAN_DIM, anchor="w")
        # dot-matrix grid decoration top-right
        for row in range(3):
            for col in range(4):
                cv.create_rectangle(
                    WINDOW_W-22+col*4, 3+row*4,
                    WINDOW_W-21+col*4, 4+row*4,
                    fill=C_CYAN_DIM, outline=""
                )
        # signal bars bottom-right
        for i in range(4):
            h = 3 + i * 2
            cv.create_rectangle(
                WINDOW_W-14+i*3, WINDOW_H-12-h,
                WINDOW_W-13+i*3, WINDOW_H-12,
                fill=C_CYAN_DIM, outline=""
            )

    # ─────────────────────────────────────────────────────────────────────────
    def _clear_dyn(self):
        for i in self._dyn_ids:
            self.cv.delete(i)
        self._dyn_ids.clear()

    def _dim_color(self, color, factor):
        base = color.lstrip("#")
        r = max(0, int(int(base[0:2], 16) * factor))
        g = max(0, int(int(base[2:4], 16) * factor))
        b = max(0, int(int(base[4:6], 16) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    # ─────────────────────────────────────────────────────────────────────────
    def _draw_header(self, map_name, ct_score, t_score, color):
        cv = self.cv
        iid = cv.create_text(WINDOW_W//2, 7, text=f"// {map_name} //",
                              font=("Courier", 7, "bold"), fill=color, anchor="center")
        self._dyn_ids.append(iid)
        iid = cv.create_text(7, 7, text=f"CT:{ct_score}",
                              font=("Courier", 6), fill="#5599FF", anchor="w")
        self._dyn_ids.append(iid)
        iid = cv.create_text(WINDOW_W-7, 7, text=f"T:{t_score}",
                              font=("Courier", 6), fill="#FFAA00", anchor="e")
        self._dyn_ids.append(iid)

    # ─────────────────────────────────────────────────────────────────────────
    def _draw_timer(self, remaining, color):
        txt     = f"{remaining:05.2f}"
        dim_col = self._dim_color(color, 0.07)
        # measure total width to center
        char_w  = int(10 * self.seg.scale)
        dot_w   = int(5  * self.seg.scale)
        total_w = 0
        for ch in txt:
            total_w += dot_w if ch == '.' else char_w
        self.seg.x = (WINDOW_W - total_w) // 2
        self.seg.y = 20
        self.seg.render(txt, color, dim_col)
        for iid in self.seg._ids:
            self._dyn_ids.append(iid)

    # ─────────────────────────────────────────────────────────────────────────
    def _draw_progress(self, frac, color):
        cv     = self.cv
        x0, y0 = 5, 71
        x1, y1 = WINDOW_W-5, 76
        # track
        iid = cv.create_rectangle(x0, y0, x1, y1, fill="#080C18", outline=C_DIM)
        self._dyn_ids.append(iid)
        # fill
        fill_x = x0 + int((x1-x0) * frac)
        if fill_x > x0:
            iid = cv.create_rectangle(x0, y0, fill_x, y1, fill=color, outline="")
            self._dyn_ids.append(iid)
        # animated glint
        glint_pos = abs(math.sin(self._frame * 0.06))
        gx = x0 + int((fill_x - x0) * glint_pos) if fill_x > x0 else x0
        iid = cv.create_rectangle(gx-1, y0, gx+3, y1, fill="#FFFFFF", outline="")
        self._dyn_ids.append(iid)
        # tick marks at 10s / 20s / 30s
        for t_sec in [10, 20, 30]:
            tx = x0 + int((x1-x0) * (1 - t_sec / BOMB_TIME))
            iid = cv.create_line(tx, y0-1, tx, y1+1, fill="#FFFFFF", width=1)
            self._dyn_ids.append(iid)
            iid = cv.create_text(tx, y0-4, text=str(t_sec),
                                  font=("Courier", 4), fill=C_DIM, anchor="center")
            self._dyn_ids.append(iid)

    # ─────────────────────────────────────────────────────────────────────────
    def _draw_heartbeat(self, color, intensity=1.0):
        cv = self.cv
        self._heartbeat_t += 0.15 * max(0.3, intensity)
        t    = self._heartbeat_t
        pts  = []
        y_base = 64
        for x in range(5, WINDOW_W-5, 2):
            xn   = (x - 5) / (WINDOW_W - 10)
            xmod = (xn * 3.5 + t) % 1.0
            spike = 0.0
            if 0.28 < xmod < 0.32:
                spike = -5 * math.sin((xmod-0.28)/0.04 * math.pi)
            elif 0.32 < xmod < 0.38:
                spike = 10 * math.sin((xmod-0.32)/0.06 * math.pi) * intensity
            elif 0.38 < xmod < 0.43:
                spike = -3 * math.sin((xmod-0.38)/0.05 * math.pi)
            y = y_base + spike
            pts.extend([x, y])
        if len(pts) >= 4:
            iid = cv.create_line(*pts, fill=color, width=1, smooth=True)
            self._dyn_ids.append(iid)

    # ─────────────────────────────────────────────────────────────────────────
    def _draw_status(self, text, color, blink=False):
        if blink and not self._blink_state:
            return
        iid = self.cv.create_text(WINDOW_W//2, 46, text=text,
                                   font=("Courier", 16, "bold"),
                                   fill=color, anchor="center")
        self._dyn_ids.append(iid)

    # ─────────────────────────────────────────────────────────────────────────
    def _draw_flash(self):
        if self._flash_alpha <= 0:
            return
        col = self._dim_color(self._flash_color, self._flash_alpha)
        iid = self.cv.create_rectangle(0, 0, WINDOW_W, WINDOW_H,
                                        fill=col, outline="")
        self._dyn_ids.append(iid)
        self._flash_alpha = max(0.0, self._flash_alpha - 0.035)

    # ─────────────────────────────────────────────────────────────────────────
    def _tick_blink(self, speed=9):
        self._blink_counter += 1
        if self._blink_counter >= speed:
            self._blink_counter = 0
            self._blink_state   = not self._blink_state

    # ─────────────────────────────────────────────────────────────────────────
    def _tick(self):
        self._frame += 1
        self._tick_blink()

        with state_lock:
            planted    = state["planted"]
            plant_time = state["plant_time"]
            map_name   = state["map_name"]
            defused    = state["defused"]
            exploded   = state["exploded"]
            ct_score   = state["round_wins_ct"]
            t_score    = state["round_wins_t"]

        self._clear_dyn()

        remaining = BOMB_TIME
        if planted and plant_time:
            remaining = max(0.0, BOMB_TIME - (time.time() - plant_time))

        # determine mode + colors
        if planted:
            if remaining > 10:
                color, border_col, pulse = C_WHITE,  C_CYAN,   1.0
            elif remaining > 5:
                color, border_col, pulse = C_ORANGE, C_ORANGE, 3.5
            else:
                color, border_col, pulse = C_RED,    C_RED,    7.0
            mode = "active"
        elif defused:
            color, border_col, pulse, mode = C_GREEN, C_GREEN, 2.0, "defused"
        elif exploded:
            color, border_col, pulse, mode = C_RED,   C_RED,   5.0, "exploded"
        else:
            color, border_col, pulse, mode = C_DIM, C_CYAN_DIM, 0.7, "standby"

        # transitions
        if mode != self._last_mode:
            if mode == "defused":
                self._flash_alpha = 0.4
                self._flash_color = C_GREEN
                self.particles.emit(WINDOW_W//2, WINDOW_H//2, 24, C_GREEN)
            elif mode == "exploded":
                self._flash_alpha = 0.5
                self._flash_color = C_RED
                self.particles.emit(WINDOW_W//2, WINDOW_H//2, 24, C_RED)
            elif mode == "active":
                self._flash_alpha = 0.18
                self._flash_color = C_CYAN
                self.particles.emit(WINDOW_W//2, WINDOW_H//2, 10, C_CYAN)
            self._last_mode = mode

        # ── render stack ──────────────────────────────────────────────────────

        # 1. Animated border
        self.border.draw(border_col, pulse)
        for iid in self.border._ids:
            self._dyn_ids.append(iid)

        # 2. Header (map + scores)
        self._draw_header(map_name, ct_score, t_score, C_CYAN)

        # 3. Main content area
        if planted:
            self._draw_timer(remaining, color)
            intensity = 1.0 + 1.5 * (1 - remaining / BOMB_TIME)
            self._draw_heartbeat(color, intensity)
            self._draw_progress(remaining / BOMB_TIME, color)
            self.waveform.push(remaining)
            self.waveform.draw(color)
        elif defused:
            self._draw_status("DEFUSED",  C_GREEN, blink=True)
            self._draw_heartbeat(C_GREEN, 0.5)
        elif exploded:
            self._draw_status("EXPLODED", C_RED, blink=True)
            self._draw_heartbeat(C_RED, 2.5)
        else:
            self._draw_status("STANDBY", C_DIM, blink=False)
            self._draw_heartbeat(C_CYAN_DIM, 0.35)

        # 4. Particles
        self.particles.update()
        self.particles.draw(self.cv)

        # 5. CRT noise dots
        self.crt.draw_noise()

        # 6. Flash overlay (topmost)
        self._draw_flash()

        self.root.after(self.TICK_MS, self._tick)

    # ─────────────────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._drag_x = e.x
        self._drag_y = e.y

    def _drag_motion(self, e):
        x = self.root.winfo_x() + (e.x - self._drag_x)
        y = self.root.winfo_y() + (e.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def run(self):
        self.root.mainloop()

# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    Overlay().run()

 #  Made by Claude Haiku 4.5
 #  optimized by Claude Opus 4.5  
 #  Put together in a hurry by CrxticScripts.