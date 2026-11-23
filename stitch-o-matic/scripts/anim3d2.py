"""3D animation of an embroidery file being sewn: the design in a hoop seen at an angle, a needle
going up and down, the thread appearing stitch by stitch.

    python3 anim3d2.py "<file>.pes" out.mp4 60 3 [test]

60 = frames per second, 3 = frames per stitch. With `test` no video is made: a few frames are saved
as out_<frame>.png (at 10 %, 50 % and 90 % of the stitches) to look at before the full render.
"""
import math
import subprocess
import sys

import numpy as np
import pyembroidery as pe
from PIL import Image, ImageChops, ImageDraw, ImageFont

from texts import TEXT

WIDTH, HEIGHT = 1280, 720
SUPERSAMPLE = 2                     # drawn at 2x, scaled down for every frame
HOOP_MARGIN = 20                    # mm of fabric round the design inside the hoop
FIELD_OF_VIEW = 34                  # degrees
ELEVATION = math.radians(52)        # camera height angle

BACKGROUND = (255, 255, 255)        # fabric
FRAME_BACKGROUND = (228, 228, 230)
THREAD = (16, 38, 148)
THREAD_DARK = (8, 20, 90)
THREAD_LIGHT = (80, 105, 210)

NEEDLE_LENGTH = 260                 # on screen, px at 1x
LIFT = 22                           # needle lift height, px at 1x


def read_sequence(file_name):
    """[(x, y, 'st' | 'jump' | 'trim')] in mm (trim has no position)"""
    sequence = []
    for x, y, command in pe.read(file_name).stitches:
        command &= pe.COMMAND_MASK
        if command == pe.STITCH:
            sequence.append((x / 10, y / 10, 'st'))
        elif command == pe.JUMP:
            sequence.append((x / 10, y / 10, 'jump'))
        elif command == pe.TRIM:
            sequence.append((None, None, 'trim'))
    return sequence


class Camera:
    """static camera looking down at the hoop; project() maps mm (x, y on the fabric, z up) to pixels at 2x"""

    def __init__(self, centre, hoop_box):
        self.cx, self.cy = centre
        x0, x1, y0, y1 = hoop_box
        size = max(x1 - x0, (y1 - y0) * 1.3)
        distance = size * 1.75
        self.eye = np.array([0, -distance * math.cos(ELEVATION), distance * math.sin(ELEVATION)])
        forward = np.array([0, 6.0, 0]) - self.eye
        forward /= np.linalg.norm(forward)
        right = np.cross(forward, np.array([0, 0, 1.0]))
        right /= np.linalg.norm(right)
        self.right, self.up, self.forward = right, np.cross(right, forward), forward
        self.focal = (HEIGHT * SUPERSAMPLE / 2) / math.tan(math.radians(FIELD_OF_VIEW / 2))

    def project(self, x, y, z=0.0):
        d = np.array([x - self.cx, -(y - self.cy), z]) - self.eye
        k = self.focal / (d @ self.forward)
        return (WIDTH * SUPERSAMPLE / 2 + (d @ self.right) * k, HEIGHT * SUPERSAMPLE / 2 - 40 * SUPERSAMPLE - (d @ self.up) * k)


def rounded_rectangle(xa, ya, xb, yb, radius, steps=12):
    points = []
    for (cx, cy, start) in [(xb - radius, ya + radius, -90), (xb - radius, yb - radius, 0), (xa + radius, yb - radius, 90), (xa + radius, ya + radius, 180)]:
        for i in range(steps + 1):
            a = math.radians(start + 90 * i / steps)
            points.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return points


def hoop_picture(camera, hoop_box):
    """frame background, wooden hoop with depth, white fabric inside (2x size)"""
    x0, x1, y0, y1 = hoop_box
    project = camera.project
    picture = Image.new('RGB', (WIDTH * SUPERSAMPLE, HEIGHT * SUPERSAMPLE), FRAME_BACKGROUND)
    draw = ImageDraw.Draw(picture)
    thickness, depth = 7.0, 6.0
    outer = rounded_rectangle(x0 - thickness, y0 - thickness, x1 + thickness, y1 + thickness, 16 + thickness)
    inner = rounded_rectangle(x0, y0, x1, y1, 16)
    shadow = rounded_rectangle(x0 - thickness + 1.5, y0 - thickness + 3, x1 + thickness + 1.5, y1 + thickness + 3, 16 + thickness)
    draw.polygon([project(x, y, 0) for x, y in shadow], fill=(212, 212, 215))        # soft contact shadow
    draw.polygon([project(x, y, 0) for x, y in outer], fill=(150, 116, 72))
    draw.polygon([project(x, y, depth) for x, y in outer], fill=(196, 160, 110))
    inner_top = [project(x, y, depth) for x, y in inner]
    draw.polygon(inner_top, fill=(170, 134, 88))                                       # visible inner wall (far side)
    fabric = Image.new('L', picture.size, 0)
    ImageDraw.Draw(fabric).polygon([project(x, y, 0) for x, y in inner], fill=255)
    clip = Image.new('L', picture.size, 0)
    ImageDraw.Draw(clip).polygon(inner_top, fill=255)
    picture.paste(BACKGROUND, (0, 0), ImageChops.multiply(fabric, clip))
    return picture


def draw_needle(image, tip, lift, thread_from):
    """needle bar, shank and blade above the tip, lifted by `lift` px; thread from the last stitch"""
    draw = ImageDraw.Draw(image)
    x, y = tip
    top = y - lift
    # shadow on fabric (vertical needle -> short slanted shadow)
    draw.line(((x + 4, y + 2), (x + 4 + 0.25 * NEEDLE_LENGTH, y + 2 - 0.08 * NEEDLE_LENGTH)), fill=(226, 226, 230), width=5)
    if thread_from is not None:
        draw.line((thread_from, (x, top - 10)), fill=THREAD, width=2)
    # needle bar
    draw.rectangle((x - 7, top - NEEDLE_LENGTH, x + 7, top - NEEDLE_LENGTH + 120), fill=(158, 160, 166))
    draw.rectangle((x - 2, top - NEEDLE_LENGTH, x + 2, top - NEEDLE_LENGTH + 120), fill=(214, 216, 222))
    # needle shank + blade (vertical)
    draw.rectangle((x - 3, top - NEEDLE_LENGTH + 120, x + 3, top - 40), fill=(130, 132, 138))
    draw.line((x, top - NEEDLE_LENGTH + 120, x, top - 40), fill=(236, 237, 242), width=1)
    draw.polygon([(x - 2, top - 40), (x + 2, top - 40), (x, top)], fill=(120, 122, 128))
    draw.line((x, top - 40, x, top - 2), fill=(236, 237, 242), width=1)
    draw.ellipse((x - 1.5, top - 14, x + 1.5, top - 6), fill=(50, 50, 56))


def main():
    source, output = sys.argv[1], sys.argv[2]
    fps = int(sys.argv[3])
    frames_per_stitch = int(sys.argv[4])
    test = len(sys.argv) > 5

    sequence = read_sequence(source)
    points = [(x, y) for x, y, k in sequence if x is not None]
    x0, x1 = min(x for x, y in points), max(x for x, y in points)
    y0, y1 = min(y for x, y in points), max(y for x, y in points)
    hoop_box = (x0 - HOOP_MARGIN, x1 + HOOP_MARGIN, y0 - HOOP_MARGIN, y1 + HOOP_MARGIN)
    camera = Camera(((x0 + x1) / 2, (y0 + y1) / 2), hoop_box)
    project = camera.project

    canvas = hoop_picture(camera, hoop_box)          # the sewn thread is drawn onto this, at 2x
    canvas_draw = ImageDraw.Draw(canvas)
    small = canvas.resize((WIDTH, HEIGHT), Image.LANCZOS)
    try:
        bold = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 24)
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
    except Exception:
        bold = font = ImageFont.load_default()
    name = source.split('/')[-1]
    stitch_count = sum(1 for s in sequence if s[2] == 'st')

    encoder = None
    if not test:
        encoder = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{WIDTH}x{HEIGHT}', '-r', str(fps), '-i', '-',
                                    '-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', output], stdin=subprocess.PIPE)
    frame_count = [0]
    test_frames = set()
    if test:
        estimate = stitch_count * frames_per_stitch
        test_frames = {int(estimate * f) for f in (0.1, 0.5, 0.9)} | {int(estimate * 0.5) + 1}

    def emit(tip, lift, done, thread_from, show=True):
        """one frame: the sewn thread so far, the needle, name and stitch counter"""
        image = small.copy()
        if show:
            draw_needle(image, tip, lift, thread_from)
        draw = ImageDraw.Draw(image)
        draw.text((28, 20), name, font=bold, fill=THREAD)
        draw.text((WIDTH - 28, 22), TEXT['animation_stitches'].format(done=done, total=stitch_count), font=font, fill=THREAD, anchor='ra')
        if test:
            if frame_count[0] in test_frames:
                image.save(output.replace('.mp4', f'_{frame_count[0]}.png'))
        else:
            encoder.stdin.write(image.tobytes())
        frame_count[0] += 1

    def on_screen(x, y):
        return tuple(v / SUPERSAMPLE for v in project(x, y))

    position = None              # needle position, mm
    previous_px = None           # last stitch's needle point on the 2x canvas
    done = 0
    visible = False              # thread from the last stitch to the needle
    last_screen = None
    for (x, y, kind) in sequence:
        if test and frame_count[0] > max(test_frames):
            break
        if kind == 'trim':       # needle up and thread cut
            if position is not None:
                for i in range(3):
                    emit(on_screen(*position), LIFT * (1 + i), done, None)
            previous_px = None
            last_screen = None
            visible = False
            continue
        target = (x, y)
        if kind == 'jump':
            if position is not None and math.dist(position, target) > 0.5:
                n = max(3, min(12, int(math.dist(position, target) / 3)))
                for i in range(1, n + 1):
                    t = i / n
                    q = (position[0] + (target[0] - position[0]) * t, position[1] + (target[1] - position[1]) * t)
                    emit(on_screen(*q), LIFT * 2, done, last_screen if visible else None)
            position = target
            previous_px = project(x, y)
            continue
        # stitch: move (needle up) then go down
        start = position if position is not None else target
        for i in range(frames_per_stitch):
            t = (i + 1) / frames_per_stitch
            if t < 0.66:
                m = t / 0.66
                q = (start[0] + (target[0] - start[0]) * m, start[1] + (target[1] - start[1]) * m)
                lift = LIFT
            else:
                q = target
                lift = LIFT * (1 - (t - 0.66) / 0.34)
            if i == frames_per_stitch - 1:
                needle_px = project(x, y)
                if previous_px is not None:
                    canvas_draw.line((previous_px, needle_px), fill=THREAD_DARK, width=4)
                    canvas_draw.line((previous_px, needle_px), fill=THREAD, width=3)
                    canvas_draw.line(((previous_px[0] - 0.8, previous_px[1] - 0.8), (needle_px[0] - 0.8, needle_px[1] - 0.8)), fill=THREAD_LIGHT, width=1)
                    small = canvas.resize((WIDTH, HEIGHT), Image.LANCZOS)
                done += 1
                previous_px = needle_px
                last_screen = on_screen(x, y)
                visible = True
            emit(on_screen(*q), lift, done, last_screen)
        position = target
    # hold the end, needle raised away
    for i in range(fps * 2):
        emit(on_screen(*position), LIFT + i * 6, done, None, show=i < 20)
    if encoder:
        encoder.stdin.close()
        encoder.wait()
        print('rc', encoder.returncode, 'frames', frame_count[0], 'sec', frame_count[0] / fps)


if __name__ == '__main__':
    main()
