"""
TROPICAL BEACH VISUALIZER TEMPLATE.

Sunset sky + palm trees + waves + sand + a giant title + reflections panel.
Palette: sunset orange / water blue / green / tan.

CRITICAL for non-washed-out scenes: use BLOCK chars (█▓▒░) for water/sand/
palms so the sky gradient doesn't show through. Thin chars (~-._) are for
stars/overlays only.
"""
import os, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from claudewave.lib import viz


# ================= CONFIGURE =================
W, H = 1920, 1080
FPS = 60
CELL_W, CELL_H = 11, 15
COLS, ROWS = W // CELL_W, H // CELL_H   # 174 × 72

# palette — warm sunset + tropical
SKY_TOP     = (255, 125,  55)
SKY_MID     = (230,  95, 125)
SKY_BOT     = ( 40,  55, 100)
SUN         = (255, 215, 120)
SUN_GLOW    = (255, 160,  80)
WATER       = ( 60, 160, 220)
WATER_DK    = ( 25,  95, 160)
PALM_TRUNK  = (110,  70,  35)
PALM_LEAF   = ( 70, 175,  85)
PALM_LEAF_DK= ( 40, 110,  55)
SAND        = (210, 170, 110)
SAND_DK     = (160, 125,  80)
TITLE_COL   = (255, 180,  85)
CREAM       = (245, 230, 200)

# Your track title, split into block-letter rows (or use figlet/pyfiglet)
TITLE_ART = [
"██████╗ ██████╗  █████╗ ███████╗██╗██╗     ",
"██╔══██╗██╔══██╗██╔══██╗╚══███╔╝██║██║     ",
"██████╔╝██████╔╝███████║  ███╔╝ ██║██║     ",
"██╔══██╗██╔══██╗██╔══██║ ███╔╝  ██║██║     ",
"██████╔╝██║  ██║██║  ██║███████╗██║███████╗",
"╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝╚══════╝",
]

# Replace with your song's (start_s, end_s, [lines]) tuples, timed to sung vocals
THOUGHTS = [
    (0.0, 30.0, [
        "※ session.begin()",
        "※ replace this with your song's reflections",
    ]),
]


# ================= FRAME COMPOSITION =================
def make_sky(w, h):
    """Sky gradient that STOPS at horizon — water/sand zones use dark base."""
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    dark_water = (8, 20, 45)
    dark_sand  = (25, 15, 12)
    horizon_frac, sand_frac = 0.52, 0.82
    for y in range(h):
        f = y/max(1, h-1)
        if f < horizon_frac:
            local = f / horizon_frac
            if local < 0.55:
                ff = local / 0.55
                c = tuple(int(SKY_TOP[i]*(1-ff)+SKY_MID[i]*ff) for i in range(3))
            else:
                ff = (local-0.55)/0.45
                c = tuple(int(SKY_MID[i]*(1-ff)+SKY_BOT[i]*ff) for i in range(3))
        elif f < sand_frac:
            c = dark_water
        else:
            c = dark_sand
        arr[y, :, :] = c
    return Image.fromarray(arr)


def draw_water(grid, t):
    """Block-character water. Time-only animation (no audio reactivity → not twitchy)."""
    horizon = int(ROWS * 0.52); sand_top = int(ROWS * 0.82)
    rng = random.Random(int(t*0.5) + 777)
    for r in range(horizon, sand_top):
        depth = (r - horizon) / max(1, sand_top - horizon)
        col = tuple(int(WATER_DK[i]*(1-depth) + WATER[i]*depth) for i in range(3))
        col_crest = tuple(min(255, int(col[i]*0.6 + CREAM[i]*0.4)) for i in range(3))
        for c in range(COLS):
            p = math.sin(c*0.18 + t*0.9 + r*0.22)
            p2 = math.sin(c*0.07 - t*0.55 + r*0.31)
            combo = 0.7*p + 0.3*p2
            if combo > 0.78 + rng.random()*0.1: grid[r][c] = ("▀", col_crest)
            elif combo > 0.45: grid[r][c] = ("▓", col_crest)
            elif combo > 0.0:  grid[r][c] = ("█", col)
            elif combo > -0.4:
                ck = tuple(int(col[i]*0.85) for i in range(3))
                grid[r][c] = ("▓", ck)
            else:
                ck = tuple(int(col[i]*0.7) for i in range(3))
                grid[r][c] = ("▒", ck)


def draw_beach(grid):
    """Block-character sand. Time-invariant (static texture)."""
    sand_top = int(ROWS * 0.82)
    rng = random.Random(4242)
    for r in range(sand_top, ROWS):
        depth = (r - sand_top) / max(1, ROWS - sand_top)
        col = tuple(int(SAND_DK[i]*(1-depth) + SAND[i]*depth) for i in range(3))
        col_dk = tuple(int(c*0.75) for c in col)
        for c in range(COLS):
            p = rng.random()
            if p < 0.1:   grid[r][c] = ("▒", col_dk)
            elif p < 0.3: grid[r][c] = ("░", col)
            elif p < 0.6: grid[r][c] = ("▓", col)
            elif p < 0.85:grid[r][c] = ("█", col)
            else:         grid[r][c] = ("░", col)


def draw_palm(grid, x, base_y, tilt_deg, facing=1, scale=1.4):
    """Thick block-palm. Trunk + 9 fronds."""
    TRUNK_DK = (70, 40, 15)
    trunk_h = int(22*scale); trunk_w = 5 if scale >= 1.3 else 3
    for i in range(trunk_h):
        y = base_y - i
        dx = int(tilt_deg * (i/trunk_h) * 1.2 * facing)
        for tw in range(trunk_w):
            c = x + dx + tw - trunk_w//2
            if 0 <= y < ROWS and 0 <= c < COLS:
                ch, col = ("█", PALM_TRUNK) if tw == trunk_w//2 else ("▓", TRUNK_DK)
                grid[y][c] = (ch, col)
    crown_y = base_y - trunk_h; crown_x = x + int(tilt_deg * 1.2 * facing)
    L = int(14*scale)
    fronds = [
        (-1, -0.5, PALM_LEAF_DK, int(L*0.8), -0.02),
        (+1, -0.5, PALM_LEAF_DK, int(L*0.8), +0.02),
        (-1, -0.1, PALM_LEAF,    L,          -0.03),
        (+1, -0.1, PALM_LEAF,    L,          +0.03),
        (-1,  0.2, PALM_LEAF,    int(L*0.9), -0.03),
        (+1,  0.2, PALM_LEAF,    int(L*0.9), +0.03),
        (-1,  0.55, PALM_LEAF_DK, int(L*0.7), -0.02),
        (+1,  0.55, PALM_LEAF_DK, int(L*0.7), +0.02),
        ( 0, -0.9, PALM_LEAF_DK,  int(L*0.4),  0.0),
    ]
    for dx_dir, dy_slope, color, length, curve in fronds:
        for i in range(1, length):
            cy = crown_y + int((dy_slope + curve*i) * i)
            cx = crown_x + dx_dir * i
            if 0 <= cy < ROWS and 0 <= cx < COLS:
                grid[cy][cx] = ("█", color)


def compose_frame(fi, t, feats, extra):
    """Main frame composition. extra holds the fonts dict + star_seeds."""
    fonts = extra["fonts"]
    rms_val = float(feats['rms'][fi])
    mel32 = feats['mel32'][:, fi]

    img = make_sky(W, H).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    grid = [[(" ", (90, 80, 70)) for _ in range(COLS)] for _ in range(ROWS)]

    # Sun (time-only pulse)
    cx, cy = COLS//2, int(ROWS*0.18)
    r = 6 + int(2*math.sin(t*0.35))
    for dy in range(-r, r+1):
        for dx in range(-int(r*2), int(r*2)+1):
            if (dx/2.0)**2 + dy**2 <= r*r:
                y, xc = cy+dy, cx+dx
                if 0 <= y < ROWS and 0 <= xc < COLS:
                    ch = "█" if (dx/2.0)**2 + dy**2 < (r-2)**2 else "▓"
                    grid[y][xc] = (ch, SUN)

    # Title
    h_art = len(TITLE_ART); w_art = max(len(r) for r in TITLE_ART)
    cy_art = int(ROWS*0.35) - h_art//2; cx_art = COLS//2 - w_art//2
    for i, line in enumerate(TITLE_ART):
        for j, ch in enumerate(line):
            r_, c_ = cy_art+i, cx_art+j
            if ch != " " and 0 <= r_ < ROWS and 0 <= c_ < COLS:
                grid[r_][c_] = (ch, TITLE_COL)

    # Horizon line + water + beach + palms (order matters — later overwrites)
    horizon = int(ROWS * 0.52)
    for c in range(COLS):
        grid[horizon][c] = ("─", (150, 120, 120))
    draw_water(grid, t)
    draw_beach(grid)
    # Palm tilt: slow time-only sway (not audio-reactive, not twitchy)
    tilt = math.sin(t*0.22) * 1.2
    draw_palm(grid, x=int(COLS*0.12), base_y=int(ROWS*0.87), tilt_deg=tilt, facing=1, scale=1.4)
    draw_palm(grid, x=int(COLS*0.42), base_y=int(ROWS*0.85), tilt_deg=-tilt*0.7, facing=-1, scale=0.85)

    viz.render_grid_rle(draw, grid, fonts['cell'], CELL_W, CELL_H)

    # Reflections panel (see viz.typewritten_lines)
    _draw_reflections(draw, t, fonts)

    # HUD — spectrogram bars are the ONLY audio-reactive element
    _draw_hud(draw, t, feats['duration'], rms_val, mel32, fonts)

    # FX
    img = img.convert("RGB")
    img = viz.chrom_shift(img, shift=1)
    img = viz.grain_pass(img, fi, amount=5)
    img = viz.scanlines(img, every_n=4, brightness=0.97)
    return img


def _draw_reflections(draw, t, fonts):
    th = next(((s,e,l) for s,e,l in THOUGHTS if s <= t <= e), None)
    if th is None: return
    s, e, lines = th
    px, py = W - 560, 130
    pw, ph = 540, 850
    draw.rectangle([px, py, px+pw, py+ph], fill=(35, 22, 18, 215), outline=TITLE_COL+(230,), width=2)
    draw.text((px+22, py+15), "— journal —", font=fonts['ui_small'], fill=TITLE_COL+(220,))
    draw.line([(px+22, py+42), (px+pw-22, py+42)], fill=(80, 70, 55, 180))
    revealed = viz.typewritten_lines(s, t, lines, char_rate=26.0)
    ly = py + 62; line_h = 31
    for i, visible, full in revealed:
        txt = full[:visible]
        if visible < len(full) and int(t*3) % 2 == 0: txt += "▌"
        col = TITLE_COL if full.startswith("※") else CREAM
        fnt = fonts['serif_it'] if not full.startswith("※") else fonts['ui_small']
        draw.text((px+26, ly), txt, font=fnt, fill=col+(240,))
        ly += line_h


def _draw_hud(draw, t, duration, rms_val, mel32, fonts):
    draw.rectangle([0, 0, W, 40], fill=(0, 0, 0, 180))
    draw.text((15, 11), "[ claudewave // session://claude ]", font=fonts['ui'], fill=TITLE_COL+(240,))
    mm, ss = int(t)//60, int(t)%60
    dmm, dss = int(duration)//60, int(duration)%60
    draw.text((W-230, 11), f"RMS {rms_val:4.2f}   {mm:02d}:{ss:02d} / {dmm:02d}:{dss:02d}",
              font=fonts['ui'], fill=CREAM+(255,))
    # bottom bar — only element that's audio-reactive
    draw.rectangle([0, H-40, W, H], fill=(0, 0, 0, 180))
    footer = "YOUR TRACK (artist / claudewave)"
    bbox = draw.textbbox((0,0), footer, font=fonts['ui'])
    tw_ = bbox[2]-bbox[0]; fx = W - tw_ - 15
    draw.text((fx, H-25), footer, font=fonts['ui'], fill=CREAM+(220,))
    bar_x = 15; bar_w = fx - bar_x - 15; bw = max(3, bar_w//32)
    for i in range(32):
        bh = int(float(mel32[i])*30)
        x = bar_x + i*bw
        draw.rectangle([x, H-10-bh, x+bw-2, H-10], fill=TITLE_COL+(230,))


# ================= ENTRY POINT =================
if __name__ == "__main__":
    from PIL import ImageFont
    AUDIO = "work/your_song_remix.wav"
    VID_SILENT = "work/your_song_silent.mp4"
    FINAL = "your_song_video.mp4"
    FONT_BOLD = r"C:\Windows\Fonts\consolab.ttf"
    FONT_SERIF_IT = r"C:\Windows\Fonts\georgiai.ttf"

    # The worker-side fonts (cannot be passed directly in extra — they're not picklable)
    # so we initialize them in the worker via the `extra` dict holding paths.
    # Easiest: pre-load in the main script and pass via a module that the worker imports.
    # For simplicity here we inline:
    extra = {
        "fonts": {
            'cell':     ImageFont.truetype(FONT_BOLD, 13),
            'ui':       ImageFont.truetype(FONT_BOLD, 16),
            'ui_small': ImageFont.truetype(FONT_BOLD, 14),
            'serif_it': ImageFont.truetype(FONT_SERIF_IT, 21),
        }
    }
    # For multiprocessing, use a custom render loop (fonts need to be constructed
    # inside each worker). See visualize_brazil.py in the example project for a
    # full working pattern with _init_worker.
    viz.render_video(AUDIO, VID_SILENT, __name__, "compose_frame",
                     W, H, FPS, extra_state=extra,
                     use_nvenc=True, cq=22, preset="p4")
    viz.mux_audio_video(AUDIO, VID_SILENT, FINAL, audio_codec="mp3")
    print(f"DONE: {FINAL}")
