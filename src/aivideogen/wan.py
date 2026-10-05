"""Wan 2.x helpers shared by training and generation (diffusers-format base models)."""

from __future__ import annotations

import gc
import re
import types
from dataclasses import dataclass

import torch
import torch.nn.functional as F

# Wan's official negative prompt (it was trained with Chinese prompts). In English: garish colors,
# overexposed, static, blurry details, subtitles, style, artwork, painting, still frame, grayish, worst
# quality, low quality, JPEG artifacts, ugly, mutilated, extra fingers, badly drawn hands, badly drawn face,
# deformed, disfigured, malformed limbs, fused fingers, motionless frame, cluttered background, three legs,
# crowded background, walking backwards.
DEFAULT_NEGATIVE_PROMPT = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，"
    "JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，"
    "手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"
)


@dataclass(frozen=True)
class ModelDefaults:
    width: int = 832
    height: int = 480
    num_frames: int = 81
    fps: int = 16
    guidance: float = 5.0
    flow_shift: float = 3.0
    steps: int = 30


MODEL_DEFAULTS = {
    "Wan2.1-T2V-1.3B": ModelDefaults(),
    "Wan2.1-T2V-14B": ModelDefaults(),
    "Wan2.2-TI2V-5B": ModelDefaults(width=1280, height=704, num_frames=121, fps=24, flow_shift=5.0, steps=40),
}


def defaults_for(base: str) -> ModelDefaults:
    for key, defaults in MODEL_DEFAULTS.items():
        if key.lower() in base.lower():
            return defaults
    return ModelDefaults()


def resolve_device(preference: str = "auto") -> torch.device:
    if preference != "auto":
        return torch.device(preference)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def resolve_dtype(precision: str, device: torch.device) -> torch.dtype:
    if device.type == "cpu":
        return torch.float32  # half precision on CPU is slow and poorly supported
    return {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[precision]


def dtype_kwarg(dtype: torch.dtype) -> dict:
    """``from_pretrained`` dtype argument for diffusers: renamed to ``dtype`` in 0.40, older releases need
    ``torch_dtype`` (and would silently ignore ``dtype``, loading full precision)."""
    import diffusers

    major_minor = tuple(int(x) for x in re.findall(r"\d+", diffusers.__version__)[:2])
    return {"dtype": dtype} if major_minor >= (0, 40) else {"torch_dtype": dtype}


def free_memory() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def latent_stats(vae) -> tuple[torch.Tensor, torch.Tensor]:
    """Per-channel mean/std that normalize VAE latents to the space the transformer works in."""
    shape = (1, vae.config.z_dim, 1, 1, 1)
    mean = torch.tensor(vae.config.latents_mean, dtype=torch.float32).view(shape)
    std = torch.tensor(vae.config.latents_std, dtype=torch.float32).view(shape)
    return mean, std


def spatial_multiple(vae, transformer_config) -> int:
    """Pixel sizes must be divisible by this (VAE downsampling x transformer patch size)."""
    return vae.config.scale_factor_spatial * transformer_config["patch_size"][1]


def text_encoding_pipeline(tokenizer, text_encoder):
    """A WanPipeline with only the text stack, so prompts are cleaned and padded exactly as at inference."""
    from diffusers import WanPipeline

    return WanPipeline(
        tokenizer=tokenizer, text_encoder=text_encoder, vae=None, scheduler=None, transformer=None
    )


@torch.no_grad()
def encode_texts(text_pipe, prompts: list[str], max_sequence_length: int, device) -> list[torch.Tensor]:
    """UMT5 embeddings per prompt, with the zero padding trimmed off (re-padded at batch time)."""
    embeds = text_pipe._get_t5_prompt_embeds(
        prompt=prompts,
        max_sequence_length=max_sequence_length,
        device=device,
        dtype=text_pipe.text_encoder.dtype,
    )
    out = []
    for e in embeds:
        used = (e.abs().sum(-1) > 0).nonzero()
        length = int(used.max()) + 1 if len(used) else 1
        out.append(e[:length].cpu())
    return out


def pad_embeds(embeds: list[torch.Tensor], max_sequence_length: int) -> torch.Tensor:
    padded = []
    for e in embeds:
        e = e[:max_sequence_length]
        padded.append(torch.cat([e, e.new_zeros(max_sequence_length - e.shape[0], e.shape[1])]))
    return torch.stack(padded)


def make_scheduler(base: str, flow_shift: float):
    from diffusers import UniPCMultistepScheduler

    scheduler = UniPCMultistepScheduler.from_pretrained(base, subfolder="scheduler")
    return UniPCMultistepScheduler.from_config(scheduler.config, flow_shift=flow_shift)


def _fp8_linear_forward(self, x: torch.Tensor) -> torch.Tensor:
    weight = self.weight.to(x.dtype) * self.fp8_scale.to(x.dtype)
    return F.linear(x, weight, self.bias)


def store_frozen_linears_in_fp8(model: torch.nn.Module) -> int:
    """Keep frozen Linear weights inside the transformer blocks in float8 (per-tensor scaled).

    Weights are upcast on the fly inside a functional forward, so autograd still sees a regular
    matmul and LoRA layers (which require grad) are left untouched. Halves the VRAM of the base model.
    """
    converted = 0
    for name, module in model.named_modules():
        if not (isinstance(module, torch.nn.Linear) and name.startswith("blocks.")):
            continue
        if module.weight.requires_grad or module.weight.dtype == torch.float8_e4m3fn:
            continue
        weight = module.weight.data.float()
        scale = weight.abs().amax().clamp(min=1e-12) / torch.finfo(torch.float8_e4m3fn).max
        module.register_buffer("fp8_scale", scale.reshape(1))
        module.weight.data = (weight / scale).to(torch.float8_e4m3fn)
        module.forward = types.MethodType(_fp8_linear_forward, module)
        converted += 1
    return converted
