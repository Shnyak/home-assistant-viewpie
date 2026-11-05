from pathlib import Path
from PIL import Image

path = Path("custom_components/viewpie/brand/icon.png")
with Image.open(path) as source:
    image = source.convert("RGBA")
    alpha = image.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise SystemExit("brand icon is fully transparent")
    cropped = image.crop(bounds)
    # Keep the original artwork and colors intact. Only remove transparent
    # canvas margins, then scale the same artwork to the 256x256 brand canvas.
    cropped.thumbnail((256, 256), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    x = (256 - cropped.width) // 2
    y = (256 - cropped.height) // 2
    canvas.alpha_composite(cropped, (x, y))
    canvas.save(path, format="PNG", optimize=True)
