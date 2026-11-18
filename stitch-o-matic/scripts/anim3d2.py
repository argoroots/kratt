import sys, subprocess, math
import numpy as np
import pyembroidery as pe
from PIL import Image, ImageDraw, ImageFont

src, out = sys.argv[1], sys.argv[2]
FPS = int(sys.argv[3]); FPST = int(sys.argv[4])  # fps, frames per stitch
TEST = len(sys.argv) > 5
W, H = 1280, 720; SS = 2

p = pe.read(src)
seq = []
for x, y, c in p.stitches:
    c &= pe.COMMAND_MASK
    if c == pe.STITCH: seq.append((x / 10, y / 10, 'st'))
    elif c == pe.JUMP: seq.append((x / 10, y / 10, 'jump'))
    elif c == pe.TRIM: seq.append((None, None, 'trim'))
pts = [(x, y) for x, y, k in seq if x is not None]
x0 = min(x for x, y in pts); x1 = max(x for x, y in pts); y0 = min(y for x, y in pts); y1 = max(y for x, y in pts)
cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
M = 20
HX0, HX1, HY0, HY1 = x0 - M, x1 + M, y0 - M, y1 + M

# ---- static camera
def look(eye, tgt):
    f = tgt - eye; f /= np.linalg.norm(f)
    r = np.cross(f, np.array([0, 0, 1.0])); r /= np.linalg.norm(r)
    u = np.cross(r, f); return r, u, f
FOV = 34; dist = 270; elev = math.radians(52)
size = max(HX1 - HX0, (HY1 - HY0) * 1.3)
dist = size * 1.75
EYE = np.array([0, -dist * math.cos(elev), dist * math.sin(elev)]); R, U, Fw = look(EYE, np.array([0, 6.0, 0]))
KF = (H * SS / 2) / math.tan(math.radians(FOV / 2))
def proj(x, y, z=0.0):
    d = np.array([x - cx, -(y - cy), z]) - EYE
    zc = d @ Fw; k = KF / zc
    return (W * SS / 2 + (d @ R) * k, H * SS / 2 - 40 * SS - (d @ U) * k)

BG = (255, 255, 255); FRAMEBG = (228, 228, 230)
COL = (16, 38, 148); DARK = (8, 20, 90); HI = (80, 105, 210)

def rrect(xa, ya, xb, yb, r, n=12):
    out = []
    for (cxr, cyr, a0) in [(xb - r, ya + r, -90), (xb - r, yb - r, 0), (xa + r, yb - r, 90), (xa + r, ya + r, 180)]:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n); out.append((cxr + r * math.cos(a), cyr + r * math.sin(a)))
    return out

base = Image.new('RGB', (W * SS, H * SS), FRAMEBG); bd = ImageDraw.Draw(base)
# hoop: outer ring (wood) with depth, inner ring
T = 7.0; Hh = 6.0
outer = rrect(HX0 - T, HY0 - T, HX1 + T, HY1 + T, 16 + T)
inner = rrect(HX0, HY0, HX1, HY1, 16)
bd.polygon([proj(x, y, 0) for x, y in rrect(HX0 - T + 1.5, HY0 - T + 3, HX1 + T + 1.5, HY1 + T + 3, 16 + T)], fill=(212, 212, 215))  # soft contact shadow
bd.polygon([proj(x, y, 0) for x, y in outer], fill=(150, 116, 72))
bd.polygon([proj(x, y, Hh) for x, y in outer], fill=(196, 160, 110))
inner_top = [proj(x, y, Hh) for x, y in inner]
bd.polygon(inner_top, fill=(170, 134, 88))  # visible inner wall (far side)
fab = Image.new('L', (W * SS, H * SS), 0); ImageDraw.Draw(fab).polygon([proj(x, y, 0) for x, y in inner], fill=255)
clip = Image.new('L', (W * SS, H * SS), 0); ImageDraw.Draw(clip).polygon(inner_top, fill=255)
from PIL import ImageChops
base.paste(BG, (0, 0), ImageChops.multiply(fab, clip))
canvas = base.copy(); cdraw = ImageDraw.Draw(canvas)
small = canvas.resize((W, H), Image.LANCZOS)

try:
    FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 24)
    F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
except Exception:
    FB = F = ImageFont.load_default()
name = src.split('/')[-1]
nst = sum(1 for s in seq if s[2] == 'st')

NL = 260; LIFT = 22  # needle length on screen, lift height (px at 1x)
def needle(im, tip_xy, lift, thread_from):
    d = ImageDraw.Draw(im)
    x, y = tip_xy; ty = y - lift
    # shadow on fabric (vertical needle -> short slanted shadow)
    d.line(((x + 4, y + 2), (x + 4 + 0.25 * (NL), y + 2 - 0.08 * NL)), fill=(226, 226, 230), width=5)
    if thread_from is not None:
        d.line((thread_from, (x, ty - 10)), fill=COL, width=2)
    # needle bar
    d.rectangle((x - 7, ty - NL, x + 7, ty - NL + 120), fill=(158, 160, 166)); d.rectangle((x - 2, ty - NL, x + 2, ty - NL + 120), fill=(214, 216, 222))
    # needle shank + blade (vertical)
    d.rectangle((x - 3, ty - NL + 120, x + 3, ty - 40), fill=(130, 132, 138)); d.line((x, ty - NL + 120, x, ty - 40), fill=(236, 237, 242), width=1)
    d.polygon([(x - 2, ty - 40), (x + 2, ty - 40), (x, ty)], fill=(120, 122, 128)); d.line((x, ty - 40, x, ty - 2), fill=(236, 237, 242), width=1)
    d.ellipse((x - 1.5, ty - 14, x + 1.5, ty - 6), fill=(50, 50, 56))

ff = None
if not TEST:
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)

fcount = [0]; shots = set()
def emit(tip, lift, done, thread_from, show=True):
    im = small.copy()
    if show: needle(im, tip, lift, thread_from)
    d = ImageDraw.Draw(im)
    d.text((28, 20), name, font=FB, fill=COL)
    d.text((W - 28, 22), f'pisted {done}/{nst}', font=F, fill=COL, anchor='ra')
    if TEST:
        if fcount[0] in shots: im.save(out.replace('.mp4', f'_{fcount[0]}.png'))
    else:
        ff.stdin.write(im.tobytes())
    fcount[0] += 1

S1 = lambda x, y: tuple(v / SS for v in proj(x, y))
total_frames_est = nst * FPST
if TEST: shots = {int(total_frames_est * f) for f in (0.1, 0.5, 0.9)} | {int(total_frames_est * 0.5) + 1}
cur = None; prevp = None; done = 0; visible = False; last_scr = None
for (x, y, k) in seq:
    if TEST and fcount[0] > max(shots): break
    if k == 'trim':
        # needle up and thread cut
        if cur is not None:
            for i in range(3): emit(S1(*cur), LIFT * (1 + i), done, None)
        prevp = None; last_scr = None; visible = False; continue
    tgt = (x, y)
    if k == 'jump':
        if cur is not None and math.dist(cur, tgt) > 0.5:
            n = max(3, min(12, int(math.dist(cur, tgt) / 3)))
            for i in range(1, n + 1):
                t = i / n; q = (cur[0] + (tgt[0] - cur[0]) * t, cur[1] + (tgt[1] - cur[1]) * t)
                emit(S1(*q), LIFT * 2, done, last_scr if visible else None)
        cur = tgt; prevp = proj(x, y); continue
    # stitch: move (needle up) then go down
    a = cur if cur is not None else tgt
    for i in range(FPST):
        t = (i + 1) / FPST
        if t < 0.66:
            m = t / 0.66; q = (a[0] + (tgt[0] - a[0]) * m, a[1] + (tgt[1] - a[1]) * m); lift = LIFT
        else:
            q = tgt; lift = LIFT * (1 - (t - 0.66) / 0.34)
        if i == FPST - 1:
            qq = proj(x, y)
            if prevp is not None:
                cdraw.line((prevp, qq), fill=DARK, width=4); cdraw.line((prevp, qq), fill=COL, width=3)
                cdraw.line(((prevp[0] - 0.8, prevp[1] - 0.8), (qq[0] - 0.8, qq[1] - 0.8)), fill=HI, width=1)
                small = canvas.resize((W, H), Image.LANCZOS)
            done += 1; prevp = qq; last_scr = S1(x, y); visible = True
        emit(S1(*q), lift, done, last_scr)
    cur = tgt
# hold end, needle raised away
for i in range(FPS * 2): emit(S1(*cur), LIFT + i * 6, done, None, show=i < 20)
if ff: ff.stdin.close(); ff.wait(); print('rc', ff.returncode, 'frames', fcount[0], 'sec', fcount[0] / FPS)
