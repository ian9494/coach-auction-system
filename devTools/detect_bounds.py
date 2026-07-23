import numpy as np
from PIL import Image
from scipy import ndimage
import sys

img = Image.open(sys.argv[1]).convert("RGBA")
a = np.array(img)
if (a[..., 3] < 250).mean() > 0.02:
    mask = a[..., 3] > 8
else:
    rgb = a[..., :3].astype(int)
    corners = np.concatenate([rgb[:10, :10].reshape(-1, 3), rgb[:10, -10:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    mask = np.abs(rgb - bg).max(axis=2) > 25

lbl, _ = ndimage.label(mask)
boxes = []
for sl in ndimage.find_objects(lbl):
    if mask[sl].sum() < 2000: continue
    x0, y0, x1, y1 = sl[1].start, sl[0].start, sl[1].stop, sl[0].stop
    boxes.append((x0, y0, x1, y1, x1-x0, y1-y0))

boxes.sort(key=lambda b: (b[1], b[0]))
print(f"Detected {len(boxes)} elements:")
for i, (x0, y0, x1, y1, w, h) in enumerate(boxes):
    print(f"  #{i}: x={x0}-{x1} (w={w}), y={y0}-{y1} (h={h})")
