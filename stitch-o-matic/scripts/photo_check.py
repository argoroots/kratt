"""Compare a photo of the stitched result with the embroidery file.

    python3 photo_check.py photo.jpg "outpos/Name 100.pes" [--box x0,y0,x1,y1] [--thread "#102694"] [--out check/photo.png]

--box: the part of the photo with this design (photo pixels), when the photo shows more than one.
--thread: thread colour; default: the PES colour (or the most saturated colour in the box).

1. Thread in the photo: pixels near the thread colour (Lab distance, threshold by Otsu).
2. Expected thread: the file's stitches drawn 0.4 mm wide.
3. The two are lined up (shift, turn, scale; the photo should be taken from straight above, the
   fabric flat in the hoop): first by centre, size and main axis, then refined (OpenCV ECC).
4. Differences, in mm on the design (x, y from the top left of the PES):
   - missing: expected thread with none in the photo (a gap, a part that did not stitch, a crack);
   - extra: thread in the photo where none is expected (pulled out of shape, stitches over the edge).
   Small differences (< 0.6 mm wide) are left out: photo blur, thread fluff.
Output: report lines and a picture (grey = matches, red = missing, blue = extra).
Limits: a photo from an angle, shadows, glare and thread close to the fabric colour make it less
exact; read the result as places to look at, not as a measurement.
"""
import argparse, math, sys
import numpy as np
import cv2
import pyembroidery as pe
from scipy import ndimage

PXMM = 10            # working resolution, pixels per mm
THREAD = 0.4


def expected_mask(pes_file):
    p = pe.read(pes_file)
    st = [(x / 10, y / 10, c & pe.COMMAND_MASK) for x, y, c in p.stitches]
    pts = [(x, y) for x, y, c in st if c == pe.STITCH]
    x0, y0 = min(x for x, y in pts), min(y for x, y in pts)
    W = int((max(x for x, y in pts) - x0 + 4) * PXMM); H = int((max(y for x, y in pts) - y0 + 4) * PXMM)
    m = np.zeros((H, W), np.uint8); prev = None
    for x, y, c in st:
        if c != pe.STITCH: prev = None; continue
        q = (int(round((x - x0 + 2) * PXMM)), int(round((y - y0 + 2) * PXMM)))
        if prev is not None: cv2.line(m, prev, q, 255, max(1, int(round(THREAD * PXMM))))
        prev = q
    col = p.threadlist[0].hex_color() if p.threadlist else None
    return m, (x0 - 2, y0 - 2), col


def thread_mask(img, hexcol):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    if hexcol:
        r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
        ref = cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2LAB).astype(np.float32)[0, 0]
        # photos shift colours: compare hue/chroma more than lightness
        d = np.sqrt(0.3 * (lab[..., 0] - ref[0]) ** 2 + (lab[..., 1] - ref[1]) ** 2 + (lab[..., 2] - ref[2]) ** 2)
    else:
        d = -np.sqrt((lab[..., 1] - 128) ** 2 + (lab[..., 2] - 128) ** 2)
    d8 = cv2.normalize(d, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, m = cv2.threshold(d8, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    lab_, n = ndimage.label(m)                       # keep the parts big enough to be thread
    if n:
        sizes = ndimage.sum(m > 0, lab_, range(1, n + 1))
        keep = np.isin(lab_, 1 + np.flatnonzero(sizes >= max(20, 0.002 * sizes.sum())))
        m = (keep * 255).astype(np.uint8)
    return m


def moments_pose(m):
    ys, xs = np.nonzero(m)
    c = np.array([xs.mean(), ys.mean()])
    cov = np.cov(np.vstack([xs - c[0], ys - c[1]]))
    ev, evec = np.linalg.eigh(cov)
    ang = math.atan2(evec[1, 1], evec[0, 1])
    return c, math.sqrt(len(xs)), ang, math.sqrt(ev[1])


def align(exp, ph):
    """2x3 matrix taking photo pixels to expected-mask pixels"""
    ce, ae, ange, se = moments_pose(exp); cp, ap, angp, sp = moments_pose(ph)
    s = se / sp                                      # spread along the main axis (thread width differs, area does not scale)
    best = None
    for flip in (0, math.pi):                        # main axis has two directions
        a = ange - angp + flip
        R = np.array([[s * math.cos(a), -s * math.sin(a)], [s * math.sin(a), s * math.cos(a)]])
        t = ce - R @ cp
        M = np.hstack([R, t[:, None]]).astype(np.float32)
        warped = cv2.warpAffine(ph, M, (exp.shape[1], exp.shape[0]))
        score = (np.logical_and(warped > 0, cv2.dilate(exp, np.ones((9, 9), np.uint8)) > 0)).sum()
        if best is None or score > best[0]: best = (score, M)
    M = best[1]
    try:
        e = cv2.GaussianBlur(exp, (0, 0), 4).astype(np.float32) / 255
        w = cv2.GaussianBlur(ph, (0, 0), 4 / max(1e-6, math.sqrt(abs(np.linalg.det(M[:, :2]))))).astype(np.float32) / 255
        # ECC finds photo->template warp in the opposite sense; work on the warped photo instead
        w0 = cv2.warpAffine(w, M, (exp.shape[1], exp.shape[0]))
        W2 = np.eye(2, 3, dtype=np.float32)
        _, W2 = cv2.findTransformECC(e, w0, W2, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), None, 5)
        Minv = cv2.invertAffineTransform(W2)          # w0 coordinates -> template: apply inverse of the found warp
        M = (np.vstack([Minv, [0, 0, 1]]) @ np.vstack([M, [0, 0, 1]]))[:2].astype(np.float32)
    except cv2.error:
        pass
    return M


def compare(photo, pes_file, box=None, thread=None, out=None, min_mm=0.6):
    img = cv2.imread(photo)
    if img is None:
        from PIL import Image
        img = cv2.cvtColor(np.array(Image.open(photo).convert('RGB')), cv2.COLOR_RGB2BGR)
    if box: x0, y0, x1, y1 = box; img = img[y0:y1, x0:x1]
    exp, origin, col = expected_mask(pes_file)
    ph = thread_mask(img, thread or col)
    M = align(exp, ph)
    w = cv2.warpAffine(ph, M, (exp.shape[1], exp.shape[0]), flags=cv2.INTER_NEAREST)
    tol = int(round(0.3 * PXMM)) * 2 + 1
    missing = (exp > 0) & ~(cv2.dilate(w, np.ones((tol, tol), np.uint8)) > 0)
    extra = (w > 0) & ~(cv2.dilate(exp, np.ones((tol, tol), np.uint8)) > 0)
    res = {}
    for name, m in (('missing', missing), ('extra', extra)):
        lab, n = ndimage.label(m); found = []
        if n:
            dist = ndimage.distance_transform_edt(m)
            for i, sl in enumerate(ndimage.find_objects(lab), start=1):
                d = dist[sl] * (lab[sl] == i); size = 2 * float(d.max()) / PXMM
                if size >= min_mm:
                    yy, xx = np.unravel_index(np.argmax(d), d.shape)
                    area_mm2 = float((lab[sl] == i).sum()) / PXMM ** 2
                    found.append(dict(x=round((xx + sl[1].start) / PXMM - 2, 1), y=round((yy + sl[0].start) / PXMM - 2, 1),   # mm from the stitches' top left
                                      size=round(size, 1), length=round(area_mm2 / max(size, 0.1), 1)))
        res[name] = sorted(found, key=lambda f: -f['size'] * f['length'])
    match = float(((exp > 0) & (w > 0)).sum()) / max(1, float((exp > 0).sum()))
    sc = math.sqrt(abs(np.linalg.det(M[:, :2])))
    res['matched'] = round(match, 3); res['photo_px_per_mm'] = round(PXMM / sc, 1)
    if out:
        vis = np.full(exp.shape + (3,), 255, np.uint8)
        vis[(exp > 0) & (w > 0)] = (170, 170, 170); vis[(exp > 0) & ~(w > 0)] = (215, 215, 215)
        vis[(w > 0) & ~(exp > 0)] = (235, 215, 200)
        vis[missing] = (0, 0, 220); vis[extra] = (220, 60, 0)
        cv2.imwrite(out, vis)
    return res


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('photo'); ap.add_argument('pes')
    ap.add_argument('--box'); ap.add_argument('--thread'); ap.add_argument('--out', default='check/photo.png')
    a = ap.parse_args()
    import os; os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    r = compare(a.photo, a.pes, [int(v) for v in a.box.split(',')] if a.box else None, a.thread, a.out)
    print(f"matched {r['matched'] * 100:.0f} % of the expected thread; photo {r['photo_px_per_mm']} px/mm")
    for k, label in (('missing', 'missing (expected, not in photo)'), ('extra', 'extra (in photo, not expected)')):
        for f in r[k][:10]: print(f"{label}: {f['size']} mm wide, ~{f['length']} mm long at x {f['x']}, y {f['y']}")
    print('picture:', a.out)
