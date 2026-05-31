#!/usr/bin/env python3
"""Extract images embedded in a PDF and split tall images into readable chunks."""

import argparse
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--out-dir", default="/tmp/entity_delta_images")
    parser.add_argument("--chunk-height", type=int, default=1800)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(args.pdf)
    outputs = []
    for page_i, page in enumerate(reader.pages, 1):
        for image_i, image in enumerate(page.images, 1):
            raw_path = out_dir / f"page{page_i:02d}_image{image_i:02d}_{image.name}"
            raw_path.write_bytes(image.data)
            im = Image.open(raw_path)
            png_path = out_dir / f"page{page_i:02d}_image{image_i:02d}.png"
            im.save(png_path)
            outputs.append(str(png_path))

            if im.height > args.chunk_height:
                for chunk_i, y in enumerate(range(0, im.height, args.chunk_height), 1):
                    crop = im.crop((0, y, im.width, min(y + args.chunk_height, im.height)))
                    chunk_path = out_dir / f"page{page_i:02d}_image{image_i:02d}_chunk{chunk_i:02d}.png"
                    crop.save(chunk_path)
                    outputs.append(str(chunk_path))

    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
