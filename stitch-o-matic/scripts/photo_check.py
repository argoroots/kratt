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
import argparse
import math
import os

import cv2
import numpy as np
import pyembroidery as pe
from scipy import ndimage

PX_PER_MM = 10       # working resolution
THREAD = 0.4         # mm
MARGIN = 2           # mm round the stitches in the expected mask


def expected_mask(pes_file):
    """the file's stitches drawn as thread: (mask, mm position of pixel (0, 0), first thread colour)"""
    pattern = pe.read(pes_file)
    stitches = [(x / 10, y / 10, c & pe.COMMAND_MASK) for x, y, c in pattern.stitches]
    points = [(x, y) for x, y, c in stitches if c == pe.STITCH]
    x0, y0 = min(x for x, y in points), min(y for x, y in points)
    width = int((max(x for x, y in points) - x0 + 2 * MARGIN) * PX_PER_MM)
    height = int((max(y for x, y in points) - y0 + 2 * MARGIN) * PX_PER_MM)
    mask = np.zeros((height, width), np.uint8)
    previous = None
    for x, y, command in stitches:
        if command != pe.STITCH:
            previous = None
            continue
        q = (int(round((x - x0 + MARGIN) * PX_PER_MM)), int(round((y - y0 + MARGIN) * PX_PER_MM)))
        if previous is not None:
            cv2.line(mask, previous, q, 255, max(1, int(round(THREAD * PX_PER_MM))))
        previous = q
    colour = pattern.threadlist[0].hex_color() if pattern.threadlist else None
    return mask, (x0 - MARGIN, y0 - MARGIN), colour


def thread_mask(image, hex_colour):
    """pixels of the photo that are thread: near the thread colour (or the most saturated ones)"""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    if hex_colour:
        r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
        reference = cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2LAB).astype(np.float32)[0, 0]
        # photos shift colours: compare hue/chroma more than lightness
        distance = np.sqrt(0.3 * (lab[..., 0] - reference[0]) ** 2 + (lab[..., 1] - reference[1]) ** 2 + (lab[..., 2] - reference[2]) ** 2)
    else:
        distance = -np.sqrt((lab[..., 1] - 128) ** 2 + (lab[..., 2] - 128) ** 2)
    distance8 = cv2.normalize(distance, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, mask = cv2.threshold(distance8, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    labels, count = ndimage.label(mask)                       # keep the parts big enough to be thread
    if count:
        sizes = ndimage.sum(mask > 0, labels, range(1, count + 1))
        keep = np.isin(labels, 1 + np.flatnonzero(sizes >= max(20, 0.002 * sizes.sum())))
        mask = (keep * 255).astype(np.uint8)
    return mask


def moments_pose(mask):
    """centre, size (sqrt of area), main axis angle and spread along it"""
    ys, xs = np.nonzero(mask)
    centre = np.array([xs.mean(), ys.mean()])
    eigenvalues, eigenvectors = np.linalg.eigh(np.cov(np.vstack([xs - centre[0], ys - centre[1]])))
    angle = math.atan2(eigenvectors[1, 1], eigenvectors[0, 1])
    return centre, math.sqrt(len(xs)), angle, math.sqrt(eigenvalues[1])


def align(expected, photo):
    """2x3 matrix taking photo pixels to expected-mask pixels"""
    centre_e, _, angle_e, spread_e = moments_pose(expected)
    centre_p, _, angle_p, spread_p = moments_pose(photo)
    scale = spread_e / spread_p                    # spread along the main axis (thread width differs, area does not scale)
    best = None
    for flip in (0, math.pi):                      # the main axis has two directions
        a = angle_e - angle_p + flip
        rotation = np.array([[scale * math.cos(a), -scale * math.sin(a)], [scale * math.sin(a), scale * math.cos(a)]])
        shift = centre_e - rotation @ centre_p
        matrix = np.hstack([rotation, shift[:, None]]).astype(np.float32)
        warped = cv2.warpAffine(photo, matrix, (expected.shape[1], expected.shape[0]))
        score = (np.logical_and(warped > 0, cv2.dilate(expected, np.ones((9, 9), np.uint8)) > 0)).sum()
        if best is None or score > best[0]:
            best = (score, matrix)
    matrix = best[1]
    try:
        template = cv2.GaussianBlur(expected, (0, 0), 4).astype(np.float32) / 255
        blurred = cv2.GaussianBlur(photo, (0, 0), 4 / max(1e-6, math.sqrt(abs(np.linalg.det(matrix[:, :2]))))).astype(np.float32) / 255
        # ECC finds photo->template warp in the opposite sense; work on the warped photo instead
        warped = cv2.warpAffine(blurred, matrix, (expected.shape[1], expected.shape[0]))
        refine = np.eye(2, 3, dtype=np.float32)
        _, refine = cv2.findTransformECC(template, warped, refine, cv2.MOTION_AFFINE,
                                         (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), None, 5)
        inverse = cv2.invertAffineTransform(refine)          # warped coordinates -> template
        matrix = (np.vstack([inverse, [0, 0, 1]]) @ np.vstack([matrix, [0, 0, 1]]))[:2].astype(np.float32)
    except cv2.error:
        pass
    return matrix


def differences(mask, min_mm):
    """connected areas of a difference mask at least min_mm wide: x, y (mm from the stitches' top
    left), size (widest circle), length (area / width), biggest first"""
    labels, count = ndimage.label(mask)
    found = []
    if count:
        distance = ndimage.distance_transform_edt(mask)
        for i, box in enumerate(ndimage.find_objects(labels), start=1):
            d = distance[box] * (labels[box] == i)
            size = 2 * float(d.max()) / PX_PER_MM
            if size >= min_mm:
                yy, xx = np.unravel_index(np.argmax(d), d.shape)
                area_mm2 = float((labels[box] == i).sum()) / PX_PER_MM ** 2
                found.append(dict(x=round((xx + box[1].start) / PX_PER_MM - MARGIN, 1), y=round((yy + box[0].start) / PX_PER_MM - MARGIN, 1),
                                  size=round(size, 1), length=round(area_mm2 / max(size, 0.1), 1)))
    return sorted(found, key=lambda f: -f['size'] * f['length'])


def compare(photo, pes_file, box=None, thread=None, out=None, min_mm=0.6):
    image = cv2.imread(photo)
    if image is None:                              # a format OpenCV cannot read (HEIC, ...)
        from PIL import Image
        image = cv2.cvtColor(np.array(Image.open(photo).convert('RGB')), cv2.COLOR_RGB2BGR)
    if box:
        x0, y0, x1, y1 = box
        image = image[y0:y1, x0:x1]
    expected, origin, colour = expected_mask(pes_file)
    in_photo = thread_mask(image, thread or colour)
    matrix = align(expected, in_photo)
    warped = cv2.warpAffine(in_photo, matrix, (expected.shape[1], expected.shape[0]), flags=cv2.INTER_NEAREST)
    tolerance = int(round(0.3 * PX_PER_MM)) * 2 + 1
    missing = (expected > 0) & ~(cv2.dilate(warped, np.ones((tolerance, tolerance), np.uint8)) > 0)
    extra = (warped > 0) & ~(cv2.dilate(expected, np.ones((tolerance, tolerance), np.uint8)) > 0)
    result = {'missing': differences(missing, min_mm), 'extra': differences(extra, min_mm)}
    matched = float(((expected > 0) & (warped > 0)).sum()) / max(1, float((expected > 0).sum()))
    scale = math.sqrt(abs(np.linalg.det(matrix[:, :2])))
    result['matched'] = round(matched, 3)
    result['photo_px_per_mm'] = round(PX_PER_MM / scale, 1)
    if out:
        picture = np.full(expected.shape + (3,), 255, np.uint8)
        picture[(expected > 0) & (warped > 0)] = (170, 170, 170)
        picture[(expected > 0) & ~(warped > 0)] = (215, 215, 215)
        picture[(warped > 0) & ~(expected > 0)] = (235, 215, 200)
        picture[missing] = (0, 0, 220)
        picture[extra] = (220, 60, 0)
        cv2.imwrite(out, picture)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('photo')
    parser.add_argument('pes')
    parser.add_argument('--box')
    parser.add_argument('--thread')
    parser.add_argument('--out', default='check/photo.png')
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    result = compare(args.photo, args.pes, [int(v) for v in args.box.split(',')] if args.box else None, args.thread, args.out)
    print(f"matched {result['matched'] * 100:.0f} % of the expected thread; photo {result['photo_px_per_mm']} px/mm")
    for key, label in (('missing', 'missing (expected, not in photo)'), ('extra', 'extra (in photo, not expected)')):
        for f in result[key][:10]:
            print(f"{label}: {f['size']} mm wide, ~{f['length']} mm long at x {f['x']}, y {f['y']}")
    print('picture:', args.out)


if __name__ == '__main__':
    main()
