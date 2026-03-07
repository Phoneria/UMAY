import cv2
import pygame
import math
import random
import time
import numpy as np
import threading
import tkinter as tk
from tkinter import ttk

# ─────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────
SCREEN_W, SCREEN_H = 960, 540
MAP_SIZE  = 110
MAP_X, MAP_Y = 10, SCREEN_H - MAP_SIZE - 10
MAP_GRID  = 5

PIP_W, PIP_H = 200, 120          # rear cam
PIP_X = SCREEN_W - PIP_W - 10
PIP_Y = SCREEN_H - PIP_H - 10

DRONE_W, DRONE_H = 200, 120      # drone feed  – left-middle
DRONE_X = 10
DRONE_Y = SCREEN_H // 2 - DRONE_H // 2

METERS_PER_PIXEL = 0.5

# ─────────────────────────────────────────
#  SHARED STATE
# ─────────────────────────────────────────
shared = {
    "cam_mode":      "NORMAL",
    "tactic":        "STANDBY",
    "alarm":         False,
    "show_rear":     True,
    "show_drone":    False,
    "team": {
        "ALPHA":   "ACTIVE",
        "BRAVO":   "ACTIVE",
        "CHARLIE": "ACTIVE",
    },
    "measure_active": False,
    # drone detections: list of dicts added by mock generator
    "detections": [],   # {type, label, rx, ry, ts}
    # toasts: list of dicts for HUD notifications
    "toasts": [],       # {msg, color, ts}
}
shared_lock = threading.Lock()

# ─────────────────────────────────────────
#  COLORS
# ─────────────────────────────────────────
C_BG        = (5,  10,  5)
C_GREEN     = (0,  255, 80)
C_GREEN_DIM = (0,  100, 40)
C_RED       = (255, 60, 60)
C_AMBER     = (255, 180, 0)
C_GRID      = (0,  60,  25)
C_CYAN      = (0,  220, 255)
C_WHITE     = (220, 220, 220)
C_ORANGE    = (255, 140, 0)
C_PURPLE    = (180, 80, 255)

CAM_COLORS  = {"NORMAL": (0,255,80), "THERMAL": (255,140,0), "NIGHT": (80,255,120)}
TAC_COLORS  = {
    "STANDBY": (100,100,100), "HOLD": (255,200,0),
    "ADVANCE": (0,255,80),    "RETREAT": (255,60,60), "FLANK": (0,200,255)
}
TEAM_COLORS = {"ACTIVE": (0,255,80), "KIA": (255,60,60), "MIA": (255,180,0)}
DET_COLORS  = {"human": C_CYAN, "vehicle": C_ORANGE}

# ─────────────────────────────────────────
#  MOCK DATA
# ─────────────────────────────────────────
MOCK_TARGETS = [
    {"rx":  0.2, "ry": -0.3, "label": "TGT-01"},
    {"rx": -0.4, "ry":  0.5, "label": "TGT-02"},
    {"rx":  0.6, "ry":  0.2, "label": "TGT-03"},
]

HUMAN_AGES    = ["20s", "30s", "40s", "teen"]
HUMAN_GENDERS = ["M", "F"]
VEHICLE_TYPES = ["sedan", "SUV", "truck", "motorcycle", "APC"]

def mock_detection_generator():
    """Periodically inject fake drone detections into shared state."""
    while True:
        time.sleep(random.uniform(4, 9))
        if not shared["show_drone"]:
            continue

        det_type = random.choice(["human", "vehicle"])
        if det_type == "human":
            count  = random.randint(1, 4)
            age    = random.choice(HUMAN_AGES)
            gender = random.choice(HUMAN_GENDERS)
            label  = f"HUMAN x{count} [{gender}/{age}]"
            color  = C_CYAN
        else:
            count  = random.randint(1, 3)
            vtype  = random.choice(VEHICLE_TYPES)
            label  = f"VEHICLE x{count} [{vtype}]"
            color  = C_ORANGE

        det = {
            "type":  det_type,
            "label": label,
            "rx":    random.uniform(-0.85, 0.85),
            "ry":    random.uniform(-0.85, 0.85),
            "ts":    time.time(),
        }
        toast = {
            "msg":   f"▶ DRONE: {label}",
            "color": color,
            "ts":    time.time(),
        }
        with shared_lock:
            shared["detections"].append(det)
            shared["toasts"].append(toast)
            # keep max 10 detections on map
            if len(shared["detections"]) > 10:
                shared["detections"].pop(0)

threading.Thread(target=mock_detection_generator, daemon=True).start()


# ─────────────────────────────────────────
#  FILTERS
# ─────────────────────────────────────────
def apply_filter(frame, mode):
    if mode == "THERMAL":
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        return cv2.cvtColor(cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO), cv2.COLOR_BGR2RGB)
    if mode == "NIGHT":
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        out  = np.zeros_like(frame)
        out[:,:,1] = np.clip(
            gray.astype(np.int16) + np.random.randint(0,20,gray.shape,np.uint8),
            0, 255).astype(np.uint8)
        return out
    return frame


# ─────────────────────────────────────────
#  TKINTER COMMAND CENTER
# ─────────────────────────────────────────
def launch_control_panel():
    BG     = "#060f06"
    BG2    = "#0d1f0d"
    BORDER = "#1a3a1a"
    FG     = "#00ff50"
    FG_DIM = "#006622"
    ACCENT = "#00ff50"
    FONT_H = ("Courier New", 10, "bold")
    FONT_N = ("Courier New", 9)

    root = tk.Tk()
    root.title("UMAY // COMMAND CENTER")
    root.geometry("360x640")
    root.configure(bg=BG)
    root.resizable(False, False)

    tk.Label(root, text="▣  UMAY COMMAND CENTER  ▣",
             bg=BG, fg=FG, font=("Courier New", 11, "bold")).pack(pady=(10,4))
    tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=10)

    style = ttk.Style()
    style.theme_use("default")
    style.configure("TNotebook",     background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=BG2, foreground=FG_DIM,
                    font=FONT_H, padding=[8,4])
    style.map("TNotebook.Tab",
              background=[("selected", BG)],
              foreground=[("selected", FG)])

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=6)

    def make_tab(label):
        f = tk.Frame(nb, bg=BG)
        nb.add(f, text=label)
        return f

    tab_cam  = make_tab("  CAM  ")
    tab_tac  = make_tab("  TAC  ")
    tab_team = make_tab(" TEAM  ")
    tab_drn  = make_tab(" DRONE ")

    def section(parent, title):
        tk.Label(parent, text=title, bg=BG, fg=FG_DIM,
                 font=FONT_H, anchor="w").pack(fill="x", padx=10, pady=(12,4))
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=10)

    def active_btn(parent, text, cmd, color=ACCENT):
        return tk.Button(parent, text=text, command=cmd,
                         bg=BG2, fg=FG_DIM, activebackground=color,
                         activeforeground="#000", font=FONT_H,
                         bd=0, cursor="hand2", pady=6, relief="flat")

    def highlight_group(buttons, active_key):
        for k, b in buttons.items():
            b.config(bg=ACCENT if k==active_key else BG2,
                     fg="#000" if k==active_key else FG_DIM)

    def toggle_btn(parent, key, on_text, off_text, on_color="#00ff50"):
        var = tk.BooleanVar(value=shared[key])
        def _toggle():
            shared[key] = var.get()
            btn.config(
                bg=on_color if shared[key] else BG2,
                fg="#000"   if shared[key] else FG_DIM,
                text=on_text if shared[key] else off_text,
            )
        btn = tk.Checkbutton(parent, text=off_text, variable=var,
                             command=_toggle, bg=BG2, fg=FG_DIM,
                             selectcolor=BG2, activebackground=on_color,
                             activeforeground="#000", font=FONT_H,
                             bd=0, cursor="hand2", indicatoron=False,
                             pady=6, relief="flat")
        btn.pack(fill="x", padx=14, pady=4)
        return btn

    # ── CAM ─────────────────────────────────
    section(tab_cam, "CAMERA MODE")
    cam_btns = {}
    for mode, col in [("NORMAL","#00ff50"),("THERMAL","#ff8c00"),("NIGHT","#50ff78")]:
        def _set(m=mode): shared["cam_mode"]=m; highlight_group(cam_btns, m)
        b = active_btn(tab_cam, mode, _set, col)
        b.pack(fill="x", padx=14, pady=3)
        cam_btns[mode] = b
    highlight_group(cam_btns, "NORMAL")

    section(tab_cam, "FEEDS")
    toggle_btn(tab_cam, "show_rear",  "◉  REAR CAM ON",  "◎  REAR CAM OFF")
    shared["show_rear"] = True   # default on

    section(tab_cam, "ALARM")
    alarm_var = tk.BooleanVar(value=False)
    def toggle_alarm():
        shared["alarm"] = alarm_var.get()
        alarm_btn.config(
            bg="#ff3030" if shared["alarm"] else BG2,
            fg="#fff"    if shared["alarm"] else FG_DIM,
            text="⚠  ALARM ACTIVE" if shared["alarm"] else "⚠  TRIGGER ALARM"
        )
    alarm_btn = tk.Checkbutton(tab_cam, text="⚠  TRIGGER ALARM",
                                variable=alarm_var, command=toggle_alarm,
                                bg=BG2, fg=FG_DIM, selectcolor=BG2,
                                activebackground="#ff3030", activeforeground="#fff",
                                font=FONT_H, bd=0, cursor="hand2",
                                indicatoron=False, pady=6, relief="flat")
    alarm_btn.pack(fill="x", padx=14, pady=6)

    # ── TAC ─────────────────────────────────
    section(tab_tac, "TACTICAL ORDER")
    tac_btns = {}
    for tac, col in [("STANDBY","#646464"),("HOLD","#ffc800"),
                     ("ADVANCE","#00ff50"),("RETREAT","#ff3c3c"),("FLANK","#00c8ff")]:
        def _set(t=tac): shared["tactic"]=t; highlight_group(tac_btns, t)
        b = active_btn(tab_tac, tac, _set, col)
        b.pack(fill="x", padx=14, pady=3)
        tac_btns[tac] = b
    highlight_group(tac_btns, "STANDBY")

    section(tab_tac, "MEASURE TOOL")
    meas_var = tk.BooleanVar(value=False)
    def toggle_measure():
        shared["measure_active"] = meas_var.get()
        meas_btn.config(
            bg=ACCENT if shared["measure_active"] else BG2,
            fg="#000"  if shared["measure_active"] else FG_DIM,
            text="◎  MEASURE ON" if shared["measure_active"] else "◎  MEASURE OFF"
        )
    meas_btn = tk.Checkbutton(tab_tac, text="◎  MEASURE OFF",
                               variable=meas_var, command=toggle_measure,
                               bg=BG2, fg=FG_DIM, selectcolor=BG2,
                               activebackground=ACCENT, activeforeground="#000",
                               font=FONT_H, bd=0, cursor="hand2",
                               indicatoron=False, pady=6, relief="flat")
    meas_btn.pack(fill="x", padx=14, pady=6)
    tk.Label(tab_tac, text="Click two points on HUD to measure distance.",
             bg=BG, fg=FG_DIM, font=FONT_N, wraplength=300, justify="left").pack(padx=14, anchor="w")

    # ── TEAM ────────────────────────────────
    section(tab_team, "UNIT STATUS")
    status_colors = {"ACTIVE": "#00ff50", "KIA": "#ff3c3c", "MIA": "#ffc800"}
    for unit in ["ALPHA", "BRAVO", "CHARLIE"]:
        row = tk.Frame(tab_team, bg=BG)
        row.pack(fill="x", padx=14, pady=4)
        tk.Label(row, text=f"[{unit}]", bg=BG, fg=FG,
                 font=FONT_H, width=9, anchor="w").pack(side="left")
        lbl = tk.Label(row, text="● ACTIVE", bg=BG,
                       fg=status_colors["ACTIVE"], font=FONT_H)
        lbl.pack(side="right")
        def make_menu(u=unit, l=lbl):
            def _set(s):
                shared["team"][u] = s
                l.config(text=f"● {s}", fg=status_colors[s])
            m = tk.Menu(root, tearoff=0, bg=BG2, fg=FG,
                        activebackground=ACCENT, activeforeground="#000", font=FONT_N)
            for s in ["ACTIVE","KIA","MIA"]:
                m.add_command(label=s, command=lambda st=s: _set(st))
            return m
        menu = make_menu()
        tk.Button(row, text="▾", bg=BG2, fg=FG_DIM, bd=0, font=FONT_H,
                  cursor="hand2",
                  command=lambda m=menu: m.tk_popup(
                      root.winfo_pointerx(), root.winfo_pointery())
                  ).pack(side="right", padx=4)

    # ── DRONE ───────────────────────────────
    section(tab_drn, "DRONE FEED")
    drone_var = tk.BooleanVar(value=False)
    def toggle_drone():
        shared["show_drone"] = drone_var.get()
        drone_btn.config(
            bg="#00ff50" if shared["show_drone"] else BG2,
            fg="#000"    if shared["show_drone"] else FG_DIM,
            text="◉  DRONE FEED ON"  if shared["show_drone"] else "◎  DRONE FEED OFF"
        )
    drone_btn = tk.Checkbutton(tab_drn, text="◎  DRONE FEED OFF",
                                variable=drone_var, command=toggle_drone,
                                bg=BG2, fg=FG_DIM, selectcolor=BG2,
                                activebackground="#00ff50", activeforeground="#000",
                                font=FONT_H, bd=0, cursor="hand2",
                                indicatoron=False, pady=6, relief="flat")
    drone_btn.pack(fill="x", padx=14, pady=4)

    section(tab_drn, "DETECTION LOG")
    log_frame = tk.Frame(tab_drn, bg=BG)
    log_frame.pack(fill="both", expand=True, padx=14, pady=4)
    log_text = tk.Text(log_frame, bg=BG2, fg=FG_DIM, font=FONT_N,
                       height=10, bd=0, state="disabled", wrap="word")
    log_text.pack(fill="both", expand=True)

    def clear_log():
        with shared_lock:
            shared["detections"].clear()
        log_text.config(state="normal")
        log_text.delete("1.0", "end")
        log_text.config(state="disabled")

    tk.Button(tab_drn, text="✕  CLEAR LOG", command=clear_log,
              bg=BG2, fg=FG_DIM, font=FONT_N, bd=0, cursor="hand2",
              pady=4, relief="flat").pack(fill="x", padx=14, pady=(0,4))

    def refresh_log():
        with shared_lock:
            dets = list(shared["detections"])
        log_text.config(state="normal")
        log_text.delete("1.0", "end")
        for d in reversed(dets):
            t = time.strftime("%H:%M:%S", time.localtime(d["ts"]))
            log_text.insert("end", f"[{t}] {d['label']}\n")
        log_text.config(state="disabled")
        root.after(2000, refresh_log)

    root.after(2000, refresh_log)

    # ── Footer ──────────────────────────────
    tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=10, pady=(4,0))
    tk.Label(root, text="ESC to quit HUD  |  UMAY v0.1",
             bg=BG, fg=FG_DIM, font=FONT_N).pack(pady=4)

    root.mainloop()


# ─────────────────────────────────────────
#  HUD DRAW HELPERS
# ─────────────────────────────────────────
def draw_panel_box(surface, x, y, w, h, label, font_tiny):
    """Shared bracketed panel box."""
    pygame.draw.rect(surface, (0,0,0), (x, y, w, h))
    b = 8
    for bx,by in [(x,y),(x+w-b,y),(x,y+h-b),(x+w-b,y+h-b)]:
        dx = 1 if bx==x else -1; dy = 1 if by==y else -1
        pygame.draw.line(surface, C_GREEN, (bx,by), (bx+dx*b,by), 2)
        pygame.draw.line(surface, C_GREEN, (bx,by), (bx,by+dy*b), 2)
    surface.blit(font_tiny.render(label, True, C_GREEN_DIM), (x+4, y+4))


def draw_minimap(surface, font_tiny, tick):
    s = pygame.Surface((MAP_SIZE, MAP_SIZE), pygame.SRCALPHA)
    s.fill((5, 15, 8, 200))
    pygame.draw.rect(s, C_GREEN, (0,0,MAP_SIZE,MAP_SIZE), 1)

    b = 10
    for bx,by in [(0,0),(MAP_SIZE-b-1,0),(0,MAP_SIZE-b-1),(MAP_SIZE-b-1,MAP_SIZE-b-1)]:
        dx = 1 if bx==0 else -1; dy = 1 if by==0 else -1
        pygame.draw.line(s, C_GREEN, (bx,by), (bx+dx*b,by), 1)
        pygame.draw.line(s, C_GREEN, (bx,by), (bx,by+dy*b), 1)

    step = MAP_SIZE // MAP_GRID
    for i in range(1, MAP_GRID):
        pygame.draw.line(s, C_GRID, (i*step,0), (i*step,MAP_SIZE), 1)
        pygame.draw.line(s, C_GRID, (0,i*step), (MAP_SIZE,i*step), 1)

    cx = cy = MAP_SIZE // 2
    sweep = math.radians((tick*2)%360)
    pygame.draw.line(s, (0,180,60,80), (cx,cy),
                     (int(cx+math.cos(sweep)*MAP_SIZE), int(cy+math.sin(sweep)*MAP_SIZE)), 1)
    for r in [MAP_SIZE//6, MAP_SIZE//3, MAP_SIZE//2-2]:
        pygame.draw.circle(s, C_GRID, (cx,cy), r, 1)
    for lbl,pos in [("S",(cx-4,MAP_SIZE-13)),("W",(3,cy-5)),("E",(MAP_SIZE-11,cy-5))]:
        s.blit(font_tiny.render(lbl, True, C_GREEN_DIM), pos)

    # Static targets
    for t in MOCK_TARGETS:
        tx = int(cx + t["rx"]*(MAP_SIZE//2-14))
        ty = int(cy + t["ry"]*(MAP_SIZE//2-14))
        pygame.draw.polygon(s, C_RED, [(tx,ty-5),(tx-4,ty+3),(tx+4,ty+3)])
        s.blit(font_tiny.render(t["label"], True, C_AMBER), (tx+6,ty-5))

    # Drone detections on map
    with shared_lock:
        dets = list(shared["detections"])
    for d in dets:
        tx = int(cx + d["rx"]*(MAP_SIZE//2-14))
        ty = int(cy + d["ry"]*(MAP_SIZE//2-14))
        col = DET_COLORS[d["type"]]
        if d["type"] == "human":
            pygame.draw.circle(s, col, (tx, ty), 4)
            pygame.draw.circle(s, col, (tx, ty), 4, 1)
        else:
            pygame.draw.rect(s, col, (tx-4, ty-3, 8, 6), 1)

    # Player dot
    pulse = int(3 + 2*math.sin(tick*0.1))
    pygame.draw.circle(s, C_GREEN, (cx,cy), pulse)
    pygame.draw.circle(s, (180,255,200), (cx,cy), 2)
    s.blit(font_tiny.render("TACTICAL MAP", True, C_GREEN_DIM), (4,MAP_SIZE-12))
    surface.blit(s, (MAP_X, MAP_Y))


def draw_north_arrow(surface, font_tiny):
    ax = MAP_X + MAP_SIZE//2
    ay = MAP_Y - 22
    pygame.draw.polygon(surface, C_GREEN, [(ax,ay),(ax-5,ay+10),(ax+5,ay+10)])
    surface.blit(font_tiny.render("N", True, C_GREEN), (ax-4, ay-13))


def draw_pip(surface, frame, font_tiny):
    if not shared["show_rear"]:
        return
    pf = cv2.resize(cv2.flip(frame,1), (PIP_W,PIP_H))
    surface.blit(pygame.surfarray.make_surface(pf.swapaxes(0,1)), (PIP_X,PIP_Y))
    draw_panel_box(surface, PIP_X, PIP_Y, PIP_W, PIP_H, "REAR CAM", font_tiny)


def draw_drone(surface, font_tiny, font_small):
    if not shared["show_drone"]:
        return
    draw_panel_box(surface, DRONE_X, DRONE_Y, DRONE_W, DRONE_H, "DRONE", font_tiny)
    # Centered DRONE label
    lbl = font_small.render("[ NO SIGNAL ]", True, C_GREEN_DIM)
    surface.blit(lbl, (DRONE_X + DRONE_W//2 - lbl.get_width()//2,
                       DRONE_Y + DRONE_H//2 - lbl.get_height()//2))


def draw_cam_mode(surface, font_small):
    mode  = shared["cam_mode"]
    color = CAM_COLORS[mode]
    txt   = font_small.render(f"[ {mode} ]", True, color)
    surface.blit(txt, (SCREEN_W - txt.get_width() - 12, 10))


def draw_tactic(surface, font_small):
    tac   = shared["tactic"]
    color = TAC_COLORS[tac]
    txt   = font_small.render(f"» {tac}", True, color)
    surface.blit(txt, (12, 10))


def draw_team(surface, font_tiny):
    x, y = SCREEN_W - 130, 36
    surface.blit(font_tiny.render("── TEAM ──", True, C_GREEN_DIM), (x, y)); y += 14
    for unit, status in shared["team"].items():
        col = TEAM_COLORS[status]
        surface.blit(font_tiny.render(f"{unit:<8} {status}", True, col), (x, y))
        y += 13


def draw_alarm_overlay(surface, tick):
    if not shared["alarm"]:
        return
    if (tick // 8) % 2 == 0:
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        pygame.draw.rect(ov, (255,0,0,40), (0,0,SCREEN_W,SCREEN_H))
        for t in range(4):
            pygame.draw.rect(ov, (255,0,0,80), (t,t,SCREEN_W-t*2,SCREEN_H-t*2), 1)
        surface.blit(ov, (0,0))


def draw_toasts(surface, font_tiny):
    """Draw stacked toast notifications on left side."""
    now = time.time()
    TOAST_TTL   = 4.0   # seconds visible
    TOAST_FADE  = 1.0   # fade out last 1s
    TOAST_W     = 280
    TOAST_H     = 28

    with shared_lock:
        # purge expired
        shared["toasts"] = [t for t in shared["toasts"] if now - t["ts"] < TOAST_TTL]
        toasts = list(shared["toasts"])

    # Draw newest at bottom, stack up (max 6)
    visible = toasts[-6:]
    base_y  = SCREEN_H - MAP_SIZE - 30 - len(visible) * (TOAST_H + 4)
    # push right of drone if drone is open
    base_x  = DRONE_X + DRONE_W + 14 if shared["show_drone"] else MAP_X + MAP_SIZE + 14

    for i, toast in enumerate(visible):
        age   = now - toast["ts"]
        alpha = int(255 * max(0, 1 - max(0, age - (TOAST_TTL - TOAST_FADE)) / TOAST_FADE))
        ty    = base_y + i * (TOAST_H + 4)

        bg_surf = pygame.Surface((TOAST_W, TOAST_H), pygame.SRCALPHA)
        bg_surf.fill((5, 20, 5, min(200, alpha)))
        pygame.draw.rect(bg_surf, (*toast["color"], alpha), (0,0,TOAST_W,TOAST_H), 1)
        surface.blit(bg_surf, (base_x, ty))

        col = (*toast["color"][:3],)
        txt = font_tiny.render(toast["msg"], True, col)
        surface.blit(txt, (base_x + 6, ty + (TOAST_H - txt.get_height())//2))


def draw_measure(surface, font_tiny, points):
    for p in points:
        pygame.draw.circle(surface, C_CYAN, p, 5)
        pygame.draw.circle(surface, C_WHITE, p, 3)
    if len(points) == 2:
        pygame.draw.line(surface, C_CYAN, points[0], points[1], 1)
        dx = points[1][0] - points[0][0]
        dy = points[1][1] - points[0][1]
        dist_m = math.hypot(dx, dy) * METERS_PER_PIXEL
        mid = ((points[0][0]+points[1][0])//2, (points[0][1]+points[1][1])//2)
        surface.blit(font_tiny.render(f"{dist_m:.1f} m", True, C_CYAN), (mid[0]+6, mid[1]-8))


# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
def main():
    threading.Thread(target=launch_control_panel, daemon=True).start()

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("UMAY HUD")
    clock  = pygame.time.Clock()

    font_small = pygame.font.SysFont("Courier New", 13, bold=True)
    font_tiny  = pygame.font.SysFont("Courier New", 11)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  960)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)

    tick        = 0
    running     = True
    measure_pts = []

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if shared["measure_active"]:
                    if len(measure_pts) < 2:
                        measure_pts.append(event.pos)
                    else:
                        measure_pts = [event.pos]

        ret, frame = cap.read()
        if ret:
            frame = cv2.resize(frame, (SCREEN_W, SCREEN_H))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = apply_filter(frame, shared["cam_mode"])
            screen.blit(pygame.surfarray.make_surface(frame.swapaxes(0,1)), (0,0))
        else:
            screen.fill(C_BG)

        draw_minimap(screen, font_tiny, tick)
        draw_north_arrow(screen, font_tiny)
        if ret:
            draw_pip(screen, frame, font_tiny)
        draw_drone(screen, font_tiny, font_small)
        draw_cam_mode(screen, font_small)
        draw_tactic(screen, font_small)
        draw_team(screen, font_tiny)
        draw_alarm_overlay(screen, tick)
        draw_toasts(screen, font_tiny)
        if shared["measure_active"] or measure_pts:
            draw_measure(screen, font_tiny, measure_pts)
        if not shared["measure_active"]:
            measure_pts.clear()

        pygame.display.flip()
        clock.tick(30)
        tick += 1

    cap.release()
    pygame.quit()


if __name__ == "__main__":
    main()