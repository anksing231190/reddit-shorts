"""Generate photoreal 'woman shrugging' candidates (Pollinations Flux, free) and cut them out (rembg)."""
import time
import urllib.parse
from pathlib import Path

import requests
from PIL import Image

OUT = Path(__file__).resolve().parent / "v3"
PROMPT = ("candid photo, medium shot from the waist up: a woman in her late 20s doing a big exaggerated shrug - "
          "both elbows bent, forearms out to the sides, both palms open and facing up at chest height, shoulders "
          "raised to her ears, head tilted, eyebrows raised high, eyes wide, lips pursed, a funny 'what did I do?' "
          "face. Ponytail, oversized crew-neck orange hoodie, standing in front of a plain light grey wall, "
          "even daylight, realistic photo, natural skin, both hands fully visible with five fingers each, no text")
SEEDS = [5, 18, 33, 47, 71, 90]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    from rembg import remove
    last = 0.0
    for i, seed in enumerate(SEEDS, 1):
        raw = OUT / f"photo_{i}.jpg"
        url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(PROMPT, safe="")
               + f"?width=1344&height=896&seed={seed}&model=flux&nologo=true&private=true")
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
