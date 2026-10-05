"""Generate videos of her: the Wan base model plus her trained LoRA."""

from __future__ import annotations

import json
import random
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import torch
import yaml

from aivideogen.character import Character
from aivideogen.safety import check_prompt
from aivideogen.train.trainer import LORA_WEIGHTS
from aivideogen.wan import (
    DEFAULT_NEGATIVE_PROMPT,
    defaults_for,
    dtype_kwarg,
    free_memory,
    resolve_device,
    resolve_dtype,
)


@dataclass
class GenerationSettings:
    width: int = 832
    height: int = 480
    num_frames: int = 81
    fps: int = 16
    steps: int = 30
    guidance: float = 5.0
    flow_shift: float = 3.0
    seed: int | None = None
    lora_scale: float = 1.0
    negative_prompt: str = field(default=DEFAULT_NEGATIVE_PROMPT, repr=False)

    @classmethod
    def for_model(cls, base: str, **overrides) -> GenerationSettings:
        d = defaults_for(base)
        settings = cls(d.width, d.height, d.num_frames, d.fps, d.steps, d.guidance, d.flow_shift)
        for key, value in overrides.items():
            if value is not None:
                setattr(settings, key, value)
        return settings


def find_lora(path: str | Path | None = None, runs_dir: Path = Path("runs")) -> Path | None:
    """Resolve LoRA weights from a file, a directory holding one, a run directory, or the newest run."""
    if path is None:
        finals = sorted(Path(runs_dir).glob(f"*/final/{LORA_WEIGHTS}"), key=lambda p: p.stat().st_mtime)
        return finals[-1] if finals else None
    path = Path(path)
    for candidate in (path, path / LORA_WEIGHTS, path / "final" / LORA_WEIGHTS):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"No LoRA weights found at {path}")


def base_model_of(lora_file: Path) -> str | None:
    """The base model a LoRA was trained on, from the run config saved next to it or in its run directory.

    Covers ``runs/<name>/final/`` and ``runs/<name>/checkpoints/step-N/`` layouts.
    """
    for directory in list(Path(lora_file).parents)[:3]:
        config = directory / "config.yaml"
        if config.is_file():
            return (yaml.safe_load(config.read_text()) or {}).get("model", {}).get("base")
    return None


def _slug(text: str, limit: int = 48) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit] or "video"


class VideoGenerator:
    """Loads the pipeline once; call :meth:`generate` as often as you like."""

    def __init__(
        self,
        base: str,
        lora: Path | None = None,
        character: Character | None = None,
        device: str = "auto",
        precision: str = "bf16",
        memory: str = "auto",
    ):
        self.base = base
        self.lora = lora
        self.character = character
        self.device = resolve_device(device)
        self.dtype = resolve_dtype(precision, self.device)
        self.memory = memory
        self._pipe = None
        self._flow_shift: float | None = None
        self._lora_scale: float | None = None

    def _memory_mode(self, pipe) -> str:
        if self.memory != "auto" or self.device.type != "cuda":
            return self.memory if self.memory != "auto" else "gpu"
        vram = torch.cuda.get_device_properties(self.device).total_memory
        transformer = sum(p.numel() * p.element_size() for p in pipe.transformer.parameters())
        text_encoder = sum(p.numel() * p.element_size() for p in pipe.text_encoder.parameters())
        if vram > (transformer + text_encoder) * 1.25:
            return "gpu"
        if vram > transformer * 1.3:
            return "offload"
        return "low"

    def load(self, lora_scale: float = 1.0):
        if self._pipe is not None:
            return self._pipe
        from diffusers import AutoencoderKLWan, WanPipeline

        vae = AutoencoderKLWan.from_pretrained(self.base, subfolder="vae", **dtype_kwarg(torch.float32))
        pipe = WanPipeline.from_pretrained(self.base, vae=vae, **dtype_kwarg(self.dtype))
        if self.lora is not None:
            pipe.load_lora_weights(
                str(self.lora.parent), weight_name=self.lora.name, adapter_name="character"
            )
        mode = self._memory_mode(pipe)
        if mode == "low":
            # Bake the LoRA in, then keep transformer weights in fp8 and offload idle components to CPU.
            if self.lora is not None:
                pipe.fuse_lora(lora_scale=lora_scale)
                pipe.unload_lora_weights()
                self._lora_scale = lora_scale
            pipe.transformer.enable_layerwise_casting(
                storage_dtype=torch.float8_e4m3fn, compute_dtype=self.dtype
            )
            pipe.enable_model_cpu_offload()
        elif mode == "offload":
            pipe.enable_model_cpu_offload()
        else:
            pipe.to(self.device)
        self._memory_used = mode
        self._pipe = pipe
        return pipe

    def build_prompt(self, scene: str) -> str:
        prompt = self.character.prompt_for(scene) if self.character else scene
        return check_prompt(prompt)

    def generate(self, scene: str, settings: GenerationSettings, out_dir: Path = Path("outputs")) -> Path:
        from diffusers import UniPCMultistepScheduler
        from diffusers.utils import export_to_video

        prompt = self.build_prompt(scene)
        if self._pipe is not None and self._memory_used == "low" and settings.lora_scale != self._lora_scale:
            # In low-memory mode the LoRA is fused into the weights; a new strength means reloading.
            self._pipe = None
            free_memory()
        pipe = self.load(settings.lora_scale)
        if settings.flow_shift != self._flow_shift:
            pipe.scheduler = UniPCMultistepScheduler.from_config(
                pipe.scheduler.config, flow_shift=settings.flow_shift
            )
            self._flow_shift = settings.flow_shift
        if self.lora is not None and self._memory_used != "low" and settings.lora_scale != self._lora_scale:
            pipe.set_adapters(["character"], [settings.lora_scale])
            self._lora_scale = settings.lora_scale
        seed = settings.seed if settings.seed is not None else random.randrange(2**31)

        started = time.time()
        frames = pipe(
            prompt=prompt,
            negative_prompt=settings.negative_prompt,
            height=settings.height,
            width=settings.width,
            num_frames=settings.num_frames,
            num_inference_steps=settings.steps,
            guidance_scale=settings.guidance,
            generator=torch.Generator("cpu").manual_seed(seed),
            output_type="np",
        ).frames[0]

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{time.strftime('%Y%m%d-%H%M%S')}_{_slug(scene)}.mp4"
        export_to_video(list(frames), str(path), fps=settings.fps)
        info = {
            "scene": scene,
            "prompt": prompt,
            "seed": seed,
            "base": self.base,
            "lora": str(self.lora) if self.lora else None,
            "seconds": round(time.time() - started, 1),
            **{k: v for k, v in asdict(settings).items() if k not in ("seed", "negative_prompt")},
        }
        path.with_suffix(".json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
        return path
