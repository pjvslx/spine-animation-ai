#!/usr/bin/env python3
"""
split_character.py — Generate a sprite-sheet atlas from a full character image
using OpenAI gpt-image-2 image editing, then segment individual body parts via
OpenCV connected-components analysis.

Usage:
    python split_character.py <input_image> [--output-dir output_parts]
        [--atlas-out atlas.png] [--min-area 500] [--padding 12]
        [--bg-threshold 240]

Requires:
    pip install requests opencv-python Pillow numpy
    Environment variable OPENAI_API_KEY must be set.
"""

import argparse
import base64
import os
import sys

import cv2
import numpy as np
import requests
from PIL import Image


def get_openai_config():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(
            "ERROR: OPENAI_API_KEY environment variable is not set.\n"
            "Get an API key at: https://platform.openai.com/api-keys\n"
            "Then run:\n"
            "  set OPENAI_API_KEY=your_key_here",
            file=sys.stderr,
        )
        sys.exit(1)

    base_url = (
        os.environ.get("OPENAI_IMAGE_API_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    )
    base_url = (
        base_url.strip()
        .rstrip("/")
        .removesuffix("/images/generations")
        .removesuffix("/images/edits")
        .removesuffix("/chat/completions")
        .rstrip("/")
    )
    return api_key, base_url


POSITIVE_PROMPT = (
    "A complete 2D game sprite sheet texture atlas for Spine animation of the "
    "exact character in the reference image. The character is completely "
    "deconstructed into separated, isolated body parts. Separated individual "
    "parts laid out flatly: isolated head, isolated torso, isolated upper arms, "
    "lower arms, hands, upper legs, lower legs, and feet. Spread out with clear "
    "space between every single body part. No overlapping parts. Clean solid "
    "white background. CRITICAL: Maintain the exact same art style, exact same "
    "shading, exact face, and exact color palette as the reference image. "
    "Identical style match, 2D game asset, flat layout, character design sheet."
)

NEGATIVE_PROMPT = (
    "3D, realistic, altered style, different art style, different face, "
    "redesign, overlapping parts, connected limbs, full body standing, dynamic "
    "pose, background scenery, shadows, gradients on background, messy layout, "
    "missing limbs, merged layers, text, watermarks."
)


def _image_to_data_url(input_image_path: str) -> str:
    with open(input_image_path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")


def generate_atlas(config: tuple[str, str], input_image_path: str, atlas_out: str) -> str:
    """Send the reference image to gpt-image-2 and save the generated atlas PNG."""
    api_key, base_url = config
    prompt = f"{POSITIVE_PROMPT}\n\nNegative prompt: {NEGATIVE_PROMPT}"
    with Image.open(input_image_path) as im:
        w, h = im.size
    size = _normalize_size(max(1024, w), max(1024, h))

    payload = {
        "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2"),
        "prompt": prompt,
        "images": [{"image_url": _image_to_data_url(input_image_path)}],
        "n": 1,
        "size": f"{size[0]}x{size[1]}",
        "output_format": "png",
    }
    r = requests.post(
        f"{base_url}/images/edits",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=180,
    )
    if not r.ok:
        print(f"ERROR: OpenAI Image API failed: {r.status_code} {r.text}", file=sys.stderr)
        sys.exit(1)

    data = r.json()
    item = (data.get("data") or [None])[0]
    if not item:
        print("ERROR: OpenAI Image API returned no image data.", file=sys.stderr)
        sys.exit(1)

    if item.get("b64_json"):
        image_data = base64.b64decode(item["b64_json"])
    elif item.get("url"):
        img = requests.get(item["url"], timeout=180)
        if not img.ok:
            print(f"ERROR: failed to download generated image: {img.status_code} {img.text}", file=sys.stderr)
            sys.exit(1)
        image_data = img.content
    else:
        print("ERROR: OpenAI Image API returned neither b64_json nor url.", file=sys.stderr)
        sys.exit(1)

    with open(atlas_out, "wb") as f:
        f.write(image_data)
    return atlas_out


def _normalize_size(w: int, h: int) -> tuple[int, int]:
    w = max(16, min(3840, int(round(w / 16) * 16)))
    h = max(16, min(3840, int(round(h / 16) * 16)))
    if w / h > 3:
        w = min(w, h * 3)
    elif h / w > 3:
        h = min(h, w * 3)
    return w, h


def segment_parts(
    atlas_path: str,
    output_dir: str,
    min_area: int = 500,
    padding: int = 12,
    bg_threshold: int = 240,
) -> list[str]:
    """Detect individual parts in the atlas using connected-components analysis.

    Returns a list of saved part file paths.
    """
    img = cv2.imread(atlas_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"ERROR: Could not read atlas image: {atlas_path}", file=sys.stderr)
        sys.exit(1)

    # Convert to RGBA if needed
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

    # Build a foreground mask: pixels whose RGB channels are all below the
    # background threshold are considered foreground.
    bgr = img[:, :, :3]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, bg_threshold, 255, cv2.THRESH_BINARY_INV)

    # Connected-components analysis (8-connectivity)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask, connectivity=8
    )

    os.makedirs(output_dir, exist_ok=True)

    saved: list[str] = []
    part_idx = 0
    h_img, w_img = img.shape[:2]

    for label_id in range(1, num_labels):  # skip background (label 0)
        area = stats[label_id, cv2.CC_STAT_AREA]
        if area < min_area:
            continue

        x = stats[label_id, cv2.CC_STAT_LEFT]
        y = stats[label_id, cv2.CC_STAT_TOP]
        w = stats[label_id, cv2.CC_STAT_WIDTH]
        h = stats[label_id, cv2.CC_STAT_HEIGHT]

        # Apply padding (clamped to image bounds)
        x1 = max(x - padding, 0)
        y1 = max(y - padding, 0)
        x2 = min(x + w + padding, w_img)
        y2 = min(y + h + padding, h_img)

        # Crop the RGBA region
        crop = img[y1:y2, x1:x2].copy()

        # Zero-out pixels that don't belong to this component (make transparent)
        label_region = labels[y1:y2, x1:x2]
        component_mask = label_region == label_id
        crop[~component_mask] = [0, 0, 0, 0]

        out_path = os.path.join(output_dir, f"part_{part_idx:02d}.png")
        cv2.imwrite(out_path, crop)
        saved.append(out_path)
        part_idx += 1

    return saved


def main():
    parser = argparse.ArgumentParser(
        description="Generate a sprite atlas from a character image using "
        "gpt-image-2, then segment into individual body parts."
    )
    parser.add_argument("input_image", help="Path to the character reference image")
    parser.add_argument(
        "--output-dir",
        default="output_parts",
        help="Directory for cropped part PNGs (default: output_parts)",
    )
    parser.add_argument(
        "--atlas-out",
        default="atlas.png",
        help="Output path for the generated atlas PNG (default: atlas.png)",
    )
    parser.add_argument(
        "--min-area",
        type=int,
        default=500,
        help="Minimum component area in pixels to keep (default: 500)",
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=12,
        help="Padding in pixels around each cropped part (default: 12)",
    )
    parser.add_argument(
        "--bg-threshold",
        type=int,
        default=240,
        help="Grayscale threshold above which pixels are treated as background (default: 240)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.input_image):
        print(f"ERROR: Input image not found: {args.input_image}", file=sys.stderr)
        sys.exit(1)

    # --- Step 1: Generate atlas ---
    print("[1/3] Generating atlas …")
    config = get_openai_config()
    generate_atlas(config, args.input_image, args.atlas_out)
    print(f"      Atlas saved to {args.atlas_out}")

    # --- Step 2: Segment parts ---
    print("[2/3] Segmenting parts …")
    parts = segment_parts(
        args.atlas_out,
        args.output_dir,
        min_area=args.min_area,
        padding=args.padding,
        bg_threshold=args.bg_threshold,
    )
    print(f"      Found {len(parts)} parts → {args.output_dir}/")
    for p in parts:
        print(f"        • {os.path.basename(p)}")

    # --- Step 3: Done ---
    print("[3/3] Done ✓")
    print(f"\nParts are in: {args.output_dir}/")
    print("You can now feed them into position_parts.py (Step 1 of the Spine pipeline).")


if __name__ == "__main__":
    main()
