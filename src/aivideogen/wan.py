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


def cpu_supports_bf16() -> bool:
    """True on CPUs with AMX or AVX512-BF16, where bf16 matmuls run several times faster than fp32."""
    try:
        return bool(torch.cpu._is_amx_tile_supported() or torch.cpu._is_avx512_bf16_supported())
    except AttributeError:
        return False


def resolve_dtype(precision: str, device: torch.device) -> torch.dtype:
    dtypes = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}
    if device.type == "cpu" and not (precision == "bf16" and cpu_supports_bf16()):
        return torch.float32  # other half-precision paths on CPU are slow or unsupported
    return dtypes[precision]


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


FP8 = torch.float8_e4m3fn
FP8_MARKER = "fp8.json"  # written into a text_encoder folder whose Linear weights are stored as scaled fp8


def quantize_fp8(weight: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Per-tensor scaled float8: returns (fp8 weight, float32 scale of shape (1,))."""
    weight = weight.float()
    scale = weight.abs().amax().clamp(min=1e-12) / torch.finfo(FP8).max
    return (weight / scale).to(FP8), scale.reshape(1)


def is_t5_linear_weight(key: str, tensor: torch.Tensor) -> bool:
    """UMT5 matmul weights that can be stored in fp8: not embeddings, norms, or the feed-forward output
    projection ``wo``, whose dtype transformers' T5 code casts the activations to."""
    keep = ("shared", "embed_tokens", "relative_attention_bias", "DenseReluDense.wo")
    return tensor.ndim == 2 and key.endswith(".weight") and not any(name in key for name in keep)


def _fp8_linear_forward(self, x: torch.Tensor) -> torch.Tensor:
    weight = self.weight.to(x.dtype) * self.fp8_scale.to(x.dtype)
    return F.linear(x, weight, self.bias)


def _use_fp8_weight(module: torch.nn.Linear, weight: torch.Tensor, scale: torch.Tensor) -> None:
    module.weight = torch.nn.Parameter(weight, requires_grad=False)
    module.register_buffer("fp8_scale", scale.reshape(1).float())
    module.forward = types.MethodType(_fp8_linear_forward, module)


def load_text_encoder(base: str, dtype: torch.dtype):
    """The UMT5 text encoder, including the scaled-fp8 layout `aivideogen download` writes to save disk.

    fp8 Linear weights stay fp8 in memory (~8 GB instead of ~11 GB) and are upcast per matmul.
    """
    from pathlib import Path

    from safetensors import safe_open
    from transformers import UMT5Config, UMT5EncoderModel

    folder = Path(base) / "text_encoder"
    if not (folder / FP8_MARKER).exists():
        return UMT5EncoderModel.from_pretrained(base, subfolder="text_encoder", dtype=dtype)
    with torch.device("meta"):
        model = UMT5EncoderModel(UMT5Config.from_pretrained(folder))
    for shard in sorted(folder.glob("*.safetensors")):
        with safe_open(str(shard), "pt") as f:
            keys = set(f.keys())
            for key in keys:
                if key.endswith(".fp8_scale"):
                    continue
                module_name, _, attr = key.rpartition(".")
                module = model.get_submodule(module_name)
                tensor = f.get_tensor(key)
                if tensor.dtype == FP8:
                    _use_fp8_weight(module, tensor, f.get_tensor(key.removesuffix("weight") + "fp8_scale"))
                else:
                    setattr(module, attr, torch.nn.Parameter(tensor.to(dtype), requires_grad=False))
    if model.encoder.embed_tokens.weight.is_meta:  # tied to `shared` and stored once
        model.encoder.embed_tokens.weight = model.shared.weight
    leftover = [name for name, p in model.named_parameters() if p.is_meta]
    if leftover:
        raise ValueError(f"text encoder weights missing from {folder}: {leftover[:3]}")
    return model.eval()


def store_frozen_linears_in_fp8(model: torch.nn.Module) -> int:
    """Keep frozen Linear weights inside the transformer blocks in float8 (per-tensor scaled).

    Weights are upcast on the fly inside a functional forward, so autograd still sees a regular
    matmul and LoRA layers (which require grad) are left untouched. Halves the VRAM of the base model.
    """
    converted = 0
    for name, module in model.named_modules():
        if not (isinstance(module, torch.nn.Linear) and name.startswith("blocks.")):
            continue
        if module.weight.requires_grad or module.weight.dtype == FP8:
            continue
        weight, scale = quantize_fp8(module.weight.data)
        module.register_buffer("fp8_scale", scale)
        module.weight.data = weight
        module.forward = types.MethodType(_fp8_linear_forward, module)
        converted += 1
    return converted


@torch.no_grad()
def decode_latents(vae, latents: torch.Tensor, video_processor):
    """Latents from a pipeline run with ``output_type="latent"`` -> frames (F, H, W, 3) in [0, 1]."""
    shape = (1, vae.config.z_dim, 1, 1, 1)
    mean = torch.tensor(vae.config.latents_mean).view(shape).to(latents.device, vae.dtype)
    std = torch.tensor(vae.config.latents_std).view(shape).to(latents.device, vae.dtype)
    video = vae.decode(latents.to(vae.dtype) * std + mean, return_dict=False)[0]
    return video_processor.postprocess_video(video, output_type="np")[0]
