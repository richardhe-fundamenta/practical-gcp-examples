"""Build the two README GUI slideshows. One-off; lives in scratchpad.

Quantizer per group, because the two frame sets fail differently at 256 colors:
median cut keeps the near-white Streamlit fills but starves the chalkboard's few
saturated strokes; octree keeps those strokes but merges the fills into white.
Either way the palette is built from the content, not the padded canvas.
"""
from PIL import Image

DOCS = "/Users/rocketech/repos/practical-gcp-examples/script-to-video-generator/docs"
BOX = (800, 900)
GROUPS = {
    "gui-tour": (Image.MEDIANCUT,
                 ["gui-form.png", "gui-advanced.png", "gui-outputs.png"]),
    "gui-review": (Image.FASTOCTREE,
                   ["gui-review-progress.png", "gui-review-slide.png",
                    "gui-review-cues.png"]),
}


def frame(path, method):
    im = Image.open(f"{DOCS}/{path}").convert("RGB")
    im.thumbnail(BOX, Image.LANCZOS)
    x, y = (BOX[0] - im.width) // 2, (BOX[1] - im.height) // 2
    canvas = Image.new("RGB", BOX, "white")
    canvas.paste(im, (x, y))
    pal = im.quantize(colors=255, method=method, dither=Image.NONE)
    return canvas.quantize(palette=pal, dither=Image.NONE)


for name, (method, files) in GROUPS.items():
    frames = [frame(f, method) for f in files]
    out = f"{DOCS}/{name}.gif"
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=1400, loop=0, optimize=True, disposal=2)
    print(out, len(frames), "frames")
