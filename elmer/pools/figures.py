"""Extract the diagrams every pool leans on into data/figures/<pool>/<id>.<ext>.

Sources differ by pool:

* Extra ships real SVGs in a zip, named exactly as the pool references them.
* Technician and General ship one-diagram-per-page PDFs, so each page is
  rendered and trimmed to its ink.
* The FCC pools embed the drawings as raster images inline with the questions,
  so images are pulled out with ``pdfimages`` and matched to the figure
  captions found on the same page.
"""
import hashlib
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from PIL import Image, ImageChops

RE_FCC_CAPTION = re.compile(r"(?:figure|fig\.?)\s*(\d[A-Z]\d+)", re.I)


def _trim(path, pad=12, bg=255):
    """Crop uniform margins off a rendered page so the diagram fills the frame."""
    img = Image.open(path).convert("RGB")
    bbox = ImageChops.difference(img, Image.new("RGB", img.size, (bg,) * 3)).getbbox()
    if bbox:
        box = (max(0, bbox[0] - pad), max(0, bbox[1] - pad),
               min(img.width, bbox[2] + pad), min(img.height, bbox[3] + pad))
        img = img.crop(box)
    img.save(path)


def _render_pages(pdf, out_dir, names, dpi=170):
    """Render selected pages of a one-figure-per-page PDF: {page: figure_id}."""
    written = {}
    with tempfile.TemporaryDirectory() as tmp:
        for page, fig_id in names.items():
            stem = Path(tmp) / f"p{page}"
            subprocess.run(["pdftoppm", "-png", "-r", str(dpi), "-f", str(page),
                            "-l", str(page), str(pdf), str(stem)], check=True)
            src = next(Path(tmp).glob(f"p{page}-*.png"))
            dst = out_dir / f"{fig_id}.png"
            shutil.move(str(src), dst)
            _trim(dst)
            written[fig_id] = dst.name
    return written


def _page_captions(pdf, page):
    txt = subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page),
                          str(pdf), "-"], check=True, capture_output=True).stdout
    seen, out = set(), []
    for m in RE_FCC_CAPTION.finditer(txt.decode("utf-8", "replace")):
        fig = m.group(1).upper()
        if fig not in seen:
            seen.add(fig)
            out.append(fig)
    return out


def extract_fcc(pdf, out_dir, wanted):
    """Pull embedded drawings out of an FCC pool PDF and name them by caption.

    A drawing is often reused on the next page (the questions that reference it
    spill over), so identical images are de-duplicated by content hash and the
    first page that names a figure wins.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written, by_hash = {}, {}
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdfimages", "-png", "-p", str(pdf), f"{tmp}/img"], check=True)
        pages = {}
        for f in sorted(Path(tmp).glob("img-*.png")):
            # filename is img-<page>-<index>.png
            parts = f.stem.split("-")
            pages.setdefault(int(parts[1]), []).append(f)

        for page in sorted(pages):
            # Pair every caption on the page with the images in placement
            # order.  A drawing repeated from an earlier page still occupies a
            # slot, so already-resolved captions must stay in the list or the
            # remaining ones shift onto the wrong image.
            captions = [c for c in _page_captions(pdf, page) if c in wanted]
            images = sorted(pages[page])
            for fig_id, src in zip(captions, images):
                if fig_id in written:
                    continue
                digest = hashlib.sha1(src.read_bytes()).hexdigest()
                if digest in by_hash:
                    written[fig_id] = by_hash[digest]
                    continue
                dst = out_dir / f"{fig_id}.png"
                shutil.copy(src, dst)
                _trim(dst, pad=6)
                by_hash[digest] = dst.name
                written[fig_id] = dst.name
    return written


def extract_svg_zip(zip_path, out_dir, wanted):
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            fig_id = Path(name).stem.upper()
            if fig_id in wanted:
                (out_dir / f"{fig_id}.svg").write_bytes(zf.read(name))
                written[fig_id] = f"{fig_id}.svg"
    return written


def extract_page_pdf(pdf, out_dir, page_map):
    out_dir.mkdir(parents=True, exist_ok=True)
    return _render_pages(pdf, out_dir, page_map)
