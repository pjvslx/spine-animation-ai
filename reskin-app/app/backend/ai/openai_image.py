"""OpenAI gpt-image-2 image-edit provider."""
from __future__ import annotations

import base64
import os
from pathlib import Path

import requests
from PIL import Image


DEFAULT_MODEL = "gpt-image-2"
DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIImageProvider:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def _api_key(self) -> str:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set — get one at https://platform.openai.com/api-keys")
        return api_key

    def _base_url(self) -> str:
        base_url = os.environ.get("OPENAI_IMAGE_API_URL") or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL
        return (
            base_url.strip()
            .rstrip("/")
            .removesuffix("/images/generations")
            .removesuffix("/images/edits")
            .removesuffix("/chat/completions")
            .rstrip("/")
        )

    async def edit_image(
        self,
        image_path: Path,
        prompt: str,
        *,
        negative_prompt: str = "",
        out_path: Path | None = None,
        reference_images: list[Path] = (),
        metadata: dict | None = None,
    ) -> Path:
        original = Image.open(image_path).convert("RGBA")
        orig_w, orig_h = original.size
        size_w, size_h = _normalize_size(orig_w, orig_h)
        request_prompt = prompt
        if negative_prompt:
            request_prompt = f"{request_prompt}\n\nNegative prompt: {negative_prompt}"

        refs = [Path(p) for p in reference_images or () if Path(p).is_file()]
        images = [_path_to_data_url(p) for p in refs]
        images.append(_image_to_data_url(original))

        if metadata is not None:
            metadata["model"] = self.model
            metadata["provider"] = "openai"
            metadata["endpoint"] = "/images/edits"
            metadata["orig_size"] = [orig_w, orig_h]
            metadata["requested_size"] = [size_w, size_h]
            metadata["reference_count"] = len(refs)
            metadata["reference_sizes"] = [_image_size(p) for p in refs]
            metadata["prompt_chars"] = len(prompt)
            metadata["prompt_preview"] = prompt[:400] + ("…" if len(prompt) > 400 else "")
            metadata["negative_prompt"] = negative_prompt
            metadata["contents_summary"] = [
                {"kind": "text", "chars": len(request_prompt), "preview": request_prompt[:80] + ("…" if len(request_prompt) > 80 else "")},
                *({"kind": "image", "size": s, "role": "reference"} for s in [_image_size(p) for p in refs]),
                {"kind": "image", "size": [orig_w, orig_h], "role": "target"},
            ]
            metadata["padded_image_pil"] = original.copy()

        payload = {
            "model": self.model,
            "prompt": request_prompt,
            "images": [{"image_url": data_url} for data_url in images],
            "n": 1,
            "size": f"{size_w}x{size_h}",
            "output_format": "png",
        }
        r = requests.post(
            f"{self._base_url()}/images/edits",
            headers={
                "Authorization": f"Bearer {self._api_key()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
        if not r.ok:
            raise RuntimeError(f"OpenAI Image API error: {r.status_code} {r.text}")

        data = r.json()
        item = (data.get("data") or [None])[0]
        if not item:
            raise RuntimeError("OpenAI Image API returned no image data")

        if out_path is None:
            out_path = image_path.with_name(image_path.stem + "_reskinned.png")

        b64 = item.get("b64_json")
        if b64:
            raw = base64.b64decode(b64)
        elif item.get("url"):
            img_resp = requests.get(item["url"], timeout=180)
            if not img_resp.ok:
                raise RuntimeError(f"failed to download OpenAI image URL: {img_resp.status_code} {img_resp.text}")
            raw = img_resp.content
        else:
            raise RuntimeError("OpenAI Image API returned neither b64_json nor url")

        import io
        generated = Image.open(io.BytesIO(raw)).convert("RGBA")
        if metadata is not None:
            metadata["model_output_size"] = [generated.width, generated.height]
            metadata["resized_to_input"] = generated.size != (orig_w, orig_h)
            metadata["response_format"] = "b64_json" if b64 else "url"
        if generated.size != (orig_w, orig_h):
            generated = generated.resize((orig_w, orig_h), Image.LANCZOS)
        generated.save(out_path, format="PNG")
        return out_path

    async def segment(self, image_path: Path):
        raise NotImplementedError("OpenAIImageProvider does not implement segment()")


def _image_size(path: Path) -> list[int]:
    try:
        with Image.open(path) as im:
            return [im.width, im.height]
    except Exception:
        return [0, 0]


def _path_to_data_url(path: Path) -> str:
    with Image.open(path) as im:
        return _image_to_data_url(im.convert("RGBA"))


def _image_to_data_url(im: Image.Image) -> str:
    import io
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _normalize_size(w: int, h: int) -> tuple[int, int]:
    w = max(16, min(3840, int(round(w / 16) * 16)))
    h = max(16, min(3840, int(round(h / 16) * 16)))
    if w / h > 3:
        w = min(w, h * 3)
    elif h / w > 3:
        h = min(h, w * 3)
    return int(w), int(h)
