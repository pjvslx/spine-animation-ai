#!/usr/bin/env python3
"""Convert position_parts.py layout.json into build_spine_json.py config."""

import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Convert layout.json to Spine skeleton config")
    parser.add_argument("--layout", required=True, help="layout.json from position_parts.py")
    parser.add_argument("--parts", required=True, help="Directory with part PNG files")
    parser.add_argument("--output", default="spine_config.json", help="Output config JSON")
    parser.add_argument("--name", default="generated-character", help="Skeleton name")
    parser.add_argument(
        "--animations",
        default="idle,walk,wave,jump,run,attack",
        help="Comma-separated template animations to request",
    )
    args = parser.parse_args()

    with open(args.layout, "r", encoding="utf-8") as f:
        layout = json.load(f)

    canvas_w = int(layout.get("canvas_width", 1024))
    canvas_h = int(layout.get("canvas_height", 1024))
    parts = layout.get("parts", {})
    z_order = layout.get("z_order") or list(parts.keys())

    bones = [{"name": "root"}]
    slots = []
    attachments = {}

    for name in z_order:
        part = parts.get(name)
        if not part:
            continue
        width = int(part.get("width", 1))
        height = int(part.get("height", 1))
        x = float(part.get("x", 0)) + width / 2 - canvas_w / 2
        y = canvas_h - (float(part.get("y", 0)) + height / 2)

        bone_name = name
        bones.append({
            "name": bone_name,
            "parent": "root",
            "x": round(x, 2),
            "y": round(y, 2),
            "length": max(10, round(max(width, height) / 2, 2)),
        })
        slots.append({"name": name, "bone": bone_name, "attachment": name})
        attachments[name] = {
            "type": "region",
            "path": name,
            "width": width,
            "height": height,
            "x": 0,
            "y": 0,
        }

    config = {
        "skeleton": {"name": args.name, "width": canvas_w, "height": canvas_h},
        "bones": bones,
        "slots": slots,
        "attachments": attachments,
        "animations": [a.strip() for a in args.animations.split(",") if a.strip()],
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print(f"Saved: {args.output}")
    print(f"  Parts: {len(slots)}")
    print(f"  Canvas: {canvas_w}x{canvas_h}")


if __name__ == "__main__":
    main()
