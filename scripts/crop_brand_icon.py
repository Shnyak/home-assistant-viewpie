from pathlib import Path
from PIL import Image

brand = Path("custom_components/viewpie/brand")
icon_path = brand / "icon.png"

with Image.open(icon_path) as source:
    image = source.convert("RGBA")
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise SystemExit("brand icon is fully transparent")
    artwork = image.crop(bounds)

    # Keep the approved artwork pixel-for-pixel in shape and color. The
    # square icon remains untouched; the Marketplace logo gets its own
    # landscape canvas, trimmed to the artwork and scaled to the full
    # supported shortest-side size.
    for filename, shortest_side in (("logo.png", 256), ("logo@2x.png", 512)):
        scale = shortest_side / min(artwork.width, artwork.height)
        size = (round(artwork.width * scale), round(artwork.height * scale))
        logo = artwork.resize(size, Image.Resampling.LANCZOS)
        logo.save(brand / filename, format="PNG", optimize=True)
