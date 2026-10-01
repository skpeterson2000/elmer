#!/usr/bin/env python3
"""Turn Natural Earth's shaded relief into the pictures the reach map lays
its cloud over.

    python3 tools/relief.py <HYP_50M_SR_W.tif>

Source, public domain, from Natural Earth: Cross Blended Hypso with Shaded
Relief and Water, 1:50m (https://www.naturalearthdata.com/downloads/
50m-raster-data/50m-cross-blend-hypso/, HYP_50M_SR_W.zip) - 10800 x 5400,
plate carree, -180 to 180 and 90 to -90, one pixel to two minutes.

The reach map's land and sea were two flat tints, close to the background so
the band's color was the only thing on the map. With the forecast drawn as a
cloud over the ground instead, the ground can be the ground: the raised-relief
globe's greens, tans and snow, the shelf pale and the deep sea dark. Turned
down a touch from Natural Earth's own - nine-tenths the saturation, and 95%
the brightness - so a white cloud stands off it. Two sizes, as JPEG: one with
the page, one fetched the first time the map is zoomed in to want it. The
kiosks have no network, so these ship with the program.
"""
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from elmer import logs  # noqa: E402

OUT = ROOT / "elmer" / "static" / "maps"
log = logging.getLogger("elmer.relief")

# (output, width; the height is half of it)
SIZES = [("relief.jpg", 2048), ("relief-4k.jpg", 4096)]
SATURATION = 0.9
BRIGHTNESS = 0.95
QUALITY = 84


def main(src):
    logs.setup(level="INFO", to_file=False)
    import numpy as np
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None            # 58 million pixels, a known file, not a bomb
    try:
        with Image.open(src) as im:
            base = im.convert("RGB")
    except OSError as exc:
        log.error("cannot read the relief %s: %s", src, exc)
        return 1
    if base.width != 2 * base.height:
        log.error("%s is %dx%d - wanted a whole world at two to one", src, base.width, base.height)
        return 1
    a = np.asarray(base, dtype=np.float32)
    grey = a.mean(axis=2, keepdims=True)
    a = (grey + (a - grey) * SATURATION) * BRIGHTNESS
    toned = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
    for name, width in SIZES:
        out = OUT / name
        try:
            sized = toned.resize((width, width // 2), Image.LANCZOS)
            sized.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        except OSError as exc:
            log.error("cannot write %s: %s", out, exc)
            return 1
        print(f"{name}: {width}x{width // 2}, {out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[2].strip())
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
