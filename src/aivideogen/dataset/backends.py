"""Image generators used to synthesize her training dataset.

Every backend does two things: draw her anchor portrait from text, and redraw her (given the anchor as an
identity reference) in a new shot.

- ``qwen``: open models on your own GPU (Qwen-Image + Qwen-Image-Edit-2511). No API keys; needs ~48 GB VRAM
  to be comfortable (works on less with CPU offload, slowly).
- ``replicate``: hosted Nano Banana (Gemini image) via Replicate. Best identity consistency, no GPU needed,
  a few cents per image. Needs ``REPLICATE_API_TOKEN``.
- ``mock``: draws a cartoon stand-in locally. Only for tests and the CPU demo.
"""

from __future__ import annotations

import hashlib
import io
import math
import os
import urllib.request
from abc import ABC, abstractmethod
from contextlib import ExitStack
from pathlib import Path

from PIL import Image, ImageDraw

ASPECT_RATIOS = {
    "1:1": (1, 1),
    "4:5": (4, 5),
    "3:4": (3, 4),
    "2:3": (2, 3),
    "9:16": (9, 16),
    "5:4": (5, 4),
    "4:3": (4, 3),
    "3:2": (3, 2),
    "16:9": (16, 9),
}


def size_for(aspect_ratio: str, area: int, multiple: int = 16) -> tuple[int, int]:
    """(width, height) of about ``area`` pixels at the aspect ratio, sides divisible by ``multiple``."""
    rw, rh = ASPECT_RATIOS[aspect_ratio]
    width = math.sqrt(area * rw / rh)
    height = width * rh / rw
    return (
        max(multiple, round(width / multiple) * multiple),
        max(multiple, round(height / multiple) * multiple),
    )


class ImageBackend(ABC):
    name: str

    @abstractmethod
    def text_to_image(self, prompt: str, *, aspect_ratio: str, seed: int) -> Image.Image: ...

    @abstractmethod
    def edit(self, prompt: str, references: list[Path], *, aspect_ratio: str, seed: int) -> Image.Image: ...

    def close(self) -> None:  # noqa: B027 - optional hook
        pass


class MockBackend(ImageBackend):
    """Draws a simple, consistent cartoon face. The scene text only changes the background and pose."""

    name = "mock"

    def __init__(self, area: int = 256 * 256):
        self.area = area

    def text_to_image(self, prompt: str, *, aspect_ratio: str, seed: int) -> Image.Image:
        return self._draw(prompt, aspect_ratio, seed)

    def edit(self, prompt: str, references: list[Path], *, aspect_ratio: str, seed: int) -> Image.Image:
        return self._draw(prompt, aspect_ratio, seed)

    def _draw(self, prompt: str, aspect_ratio: str, seed: int) -> Image.Image:
        w, h = size_for(aspect_ratio, self.area)
        digest = hashlib.sha256(f"{prompt}|{seed}".encode()).digest()
        bg = tuple(60 + b % 160 for b in digest[:3])
        img = Image.new("RGB", (w, h), bg)
        d = ImageDraw.Draw(img)
        # Head size depends on framing words so close-ups and full-body shots differ.
        scale = 0.42 if "close-up" in prompt else 0.3 if "head-and-shoulders" in prompt else 0.2
        r = int(min(w, h) * scale)
        cx = w // 2 + (digest[3] % 21 - 10) * w // 200
        cy = int(h * (0.45 if r > min(w, h) * 0.25 else 0.3))
        hair = (52, 33, 24)
        skin = (241, 214, 190)
        d.ellipse([cx - r * 1.15, cy - r * 1.2, cx + r * 1.15, cy + r * 1.6], fill=hair)
        d.ellipse([cx - r, cy - r * 1.1, cx + r, cy + r * 1.1], fill=skin)
        d.rectangle([cx - r, cy - r * 1.15, cx + r, cy - r * 0.55], fill=hair)  # curtain bangs
        eye_y = cy - r * 0.1
        for ex in (cx - r * 0.38, cx + r * 0.38):
            d.ellipse(
                [ex - r * 0.16, eye_y - r * 0.09, ex + r * 0.16, eye_y + r * 0.09], fill=(255, 255, 255)
            )
            d.ellipse([ex - r * 0.08, eye_y - r * 0.08, ex + r * 0.08, eye_y + r * 0.08], fill=(122, 92, 52))
        mark_x = cx + r * 0.38  # her left is the viewer's right
        d.ellipse(
            [mark_x - r * 0.03, eye_y + r * 0.22, mark_x + r * 0.03, eye_y + r * 0.28], fill=(70, 45, 35)
        )
        lips = (196, 92, 98)
        if "smil" in prompt or "laugh" in prompt:
            d.chord([cx - r * 0.3, cy + r * 0.35, cx + r * 0.3, cy + r * 0.65], 0, 180, fill=lips)
        else:
            d.line(
                [cx - r * 0.25, cy + r * 0.45, cx + r * 0.25, cy + r * 0.45], fill=lips, width=max(1, r // 20)
            )
        return img


class ReplicateBackend(ImageBackend):
    """Hosted image models on Replicate (``pip install 'aivideogen[replicate]'``)."""

    name = "replicate"

    def __init__(self, model: str = "google/nano-banana"):
        try:
            import replicate
        except ImportError as e:
            raise RuntimeError("The replicate backend needs: pip install 'aivideogen[replicate]'") from e
        if not os.environ.get("REPLICATE_API_TOKEN"):
            raise RuntimeError("Set REPLICATE_API_TOKEN (https://replicate.com/account/api-tokens).")
        self._replicate = replicate
        self.model = model

    def text_to_image(self, prompt: str, *, aspect_ratio: str, seed: int) -> Image.Image:
        return self._run(prompt, [], aspect_ratio, seed)

    def edit(self, prompt: str, references: list[Path], *, aspect_ratio: str, seed: int) -> Image.Image:
        return self._run(prompt, references, aspect_ratio, seed)

    def _inputs(self, prompt: str, refs: list, aspect_ratio: str, seed: int) -> dict:
        if self.model.startswith("black-forest-labs/flux-kontext"):
            inputs = {"prompt": prompt, "aspect_ratio": aspect_ratio, "seed": seed, "output_format": "png"}
            if refs:
                inputs["input_image"] = refs[0]  # Kontext takes a single reference
            return inputs
        # Nano Banana family (and other models using the same image_input convention). No seed parameter.
        inputs = {"prompt": prompt, "image_input": refs, "aspect_ratio": aspect_ratio, "output_format": "png"}
        if self.model.endswith("-pro"):
            inputs["resolution"] = "2K"
        return inputs

    def _run(self, prompt: str, references: list[Path], aspect_ratio: str, seed: int) -> Image.Image:
        with ExitStack() as stack:
            refs = [stack.enter_context(open(p, "rb")) for p in references]
            output = self._replicate.run(self.model, input=self._inputs(prompt, refs, aspect_ratio, seed))
        if isinstance(output, list):
            output = output[0]
        data = output.read() if hasattr(output, "read") else urllib.request.urlopen(str(output)).read()
        return Image.open(io.BytesIO(data)).convert("RGB")


class QwenLocalBackend(ImageBackend):
    """Open-weight Qwen-Image (text-to-image) and Qwen-Image-Edit (reference edit), run with diffusers."""

    name = "qwen"

    def __init__(
        self,
        t2i_model: str = "Qwen/Qwen-Image",
        edit_model: str = "Qwen/Qwen-Image-Edit-2511",
        steps: int = 40,
        area: int = 1024 * 1024,
    ):
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError(
                "The qwen backend needs an NVIDIA GPU. Use --backend replicate on machines without one."
            )
        self.torch = torch
        self.t2i_model, self.edit_model = t2i_model, edit_model
        self.steps, self.area = steps, area
        self._pipe = None
        self._loaded: str | None = None

    def _load(self, which: str):
        if self._loaded == which:
            return self._pipe
        self.close()
        from diffusers import QwenImageEditPlusPipeline, QwenImagePipeline

        from aivideogen.wan import dtype_kwarg

        cls, repo = (
            (QwenImagePipeline, self.t2i_model)
            if which == "t2i"
            else (QwenImageEditPlusPipeline, self.edit_model)
        )
        pipe = cls.from_pretrained(repo, **dtype_kwarg(self.torch.bfloat16))
        vram_gb = self.torch.cuda.get_device_properties(0).total_memory / 2**30
        if vram_gb >= 75:
            pipe.to("cuda")
        elif vram_gb >= 44:
            pipe.enable_model_cpu_offload()
        else:
            print(f"[qwen] {vram_gb:.0f} GB VRAM: using sequential CPU offload, expect this to be slow.")
            pipe.enable_sequential_cpu_offload()
        self._pipe, self._loaded = pipe, which
        return pipe

    def _generator(self, seed: int):
        return self.torch.Generator(device="cpu").manual_seed(seed)

    def text_to_image(self, prompt: str, *, aspect_ratio: str, seed: int) -> Image.Image:
        w, h = size_for(aspect_ratio, self.area, multiple=32)
        pipe = self._load("t2i")
        return pipe(
            prompt=prompt,
            negative_prompt=" ",
            width=w,
            height=h,
            num_inference_steps=50,
            true_cfg_scale=4.0,
            generator=self._generator(seed),
        ).images[0]

    def edit(self, prompt: str, references: list[Path], *, aspect_ratio: str, seed: int) -> Image.Image:
        w, h = size_for(aspect_ratio, self.area, multiple=32)
        pipe = self._load("edit")
        images = [Image.open(p).convert("RGB") for p in references]
        return pipe(
            image=images,
            prompt=prompt,
            negative_prompt=" ",
            width=w,
            height=h,
            num_inference_steps=self.steps,
            true_cfg_scale=4.0,
            guidance_scale=1.0,
            generator=self._generator(seed),
        ).images[0]

    def close(self) -> None:
        if self._pipe is not None:
            del self._pipe
            self._pipe, self._loaded = None, None
            self.torch.cuda.empty_cache()


def get_backend(name: str, model: str | None = None) -> ImageBackend:
    if name == "mock":
        return MockBackend()
    if name == "replicate":
        return ReplicateBackend(model or "google/nano-banana")
    if name == "qwen":
        return QwenLocalBackend(edit_model=model) if model else QwenLocalBackend()
    raise ValueError(f"unknown image backend {name!r} (choose: qwen, replicate, mock)")
