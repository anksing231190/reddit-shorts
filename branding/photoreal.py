"""Generate photoreal 'woman shrugging' candidates (Pollinations Flux, free) and cut them out (rembg)."""
import time
import urllib.parse
from pathlib import Path

import requests
from PIL import Image

OUT = Path(__file__).resolve().parent / "v3"
PROMPT = ("photorealistic waist-up photo of a friendly woman in her late 20s shrugging with both palms up and open at "
          "shoulder height, eyebrows raised, eyes wide, mouth slightly open, a playful 'was I wrong?' expression, "
          "wavy shoulder-length brown hair, casual lavender sweater, looking at the camera, centered, plain light grey "
          "studio backdrop, soft studio lighting, sharp focus, 85mm portrait photography, natural skin texture, "
          "full arms and hands visible, no text")
SEEDS = [11, 27, 42, 63]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    from rembg import remove
    last = 0.0
    for i, seed in enumerate(SEEDS, 1):
        raw = OUT / f"photo_{i}.jpg"
        url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(PROMPT, safe="")
               + f"?width=1024&height=1024&seed={seed}&model=flux&nologo=true&private=true")
        for attempt in range(4):
            time.sleep(max(0, 46 - (time.time() - last)))
            r = requests.get(url, timeout=240, headers={"User-Agent": "branding/1.0"})
            last = time.time()
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                break
            time.sleep(20 * (attempt + 1))
        else:
            print("no image for seed", seed)
            continue
        raw.write_bytes(r.content)
        im = Image.open(raw).convert("RGB")
        im = im.crop((0, 0, im.width, int(im.height * 0.94)))   # drop the free-tier watermark strip
        im.save(raw, quality=95)
        cut = remove(im)
        cut.save(OUT / f"cutout_{i}.png")
        print("ok", i)


if __name__ == "__main__":
    main()
