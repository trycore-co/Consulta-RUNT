from PIL import Image
from typing import List
from pathlib import Path


def images_to_pdf(image_paths: List[str], output_pdf: str):
    if not image_paths:
        raise ValueError("No images to build PDF")
    pil_imgs = []
    for p in image_paths:
        img = Image.open(p).convert("RGB")
        pil_imgs.append(img)
    first, rest = pil_imgs[0], pil_imgs[1:]
    Path(output_pdf).parent.mkdir(parents=True, exist_ok=True)
    first.save(output_pdf, save_all=True, append_images=rest)
    return output_pdf
