"""Download a diffusers-format base model in a disk-friendly layout.

The official Wan "-Diffusers" repos are large (Wan 2.2 5B: ~34 GB, transformer and VAE in float32). As each
file arrives it is rewritten: transformer and VAE weights in bf16, and the UMT5 text encoder's matmul weights
in per-tensor-scaled fp8 (as ComfyUI ships it). Wan 2.2 5B then takes ~19 GB on disk and the text encoder
~8 GB of RAM. Everything runs in bf16 anyway; the VAE is upcast to float32 at load where that's wanted.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path

import torch

from aivideogen.wan import FP8_MARKER

KNOWN_MODELS = {
    "wan22-5b": "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
    "wan21-1.3b": "Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
    "wan21-14b": "Wan-AI/Wan2.1-T2V-14B-Diffusers",
}
SKIP_SUFFIXES = (".md", ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".pth", ".bin", ".pt", ".gitattributes")


def shrink(path: Path, dtype: torch.dtype = torch.bfloat16) -> bool:
    """Rewrite a safetensors file with its float32 tensors cast to ``dtype``. Returns True if it changed."""
    from safetensors import safe_open
    from safetensors.torch import save_file

    with safe_open(str(path), "pt") as f:
        metadata = f.metadata()
        tensors = {key: f.get_tensor(key) for key in f.keys()}
    changed = False
    for key, tensor in tensors.items():
        if tensor.dtype == torch.float32:
            tensors[key] = tensor.to(dtype)
            changed = True
    if changed:
        tmp = path.with_name(path.name + ".tmp")
        save_file(tensors, str(tmp), metadata=metadata)
        os.replace(tmp, path)
    return changed


def to_fp8_text_encoder(path: Path) -> None:
    """Rewrite a UMT5 shard: matmul weights -> scaled fp8 (+ ``.fp8_scale``), everything else -> bf16."""
    from safetensors import safe_open
    from safetensors.torch import save_file

    from aivideogen.wan import is_t5_linear_weight, quantize_fp8

    out = {}
    with safe_open(str(path), "pt") as f:
        metadata = f.metadata()
        for key in f.keys():
            tensor = f.get_tensor(key)
            if is_t5_linear_weight(key, tensor):
                out[key], out[key.removesuffix("weight") + "fp8_scale"] = quantize_fp8(tensor)
            else:
                out[key] = tensor.to(torch.bfloat16) if tensor.is_floating_point() else tensor
    tmp = path.with_name(path.name + ".tmp")
    save_file(out, str(tmp), metadata=metadata)
    os.replace(tmp, path)


def _order(rfilename: str) -> int:
    # Biggest float32 files first, while the disk is emptiest: their conversion briefly needs extra space.
    for rank, component in enumerate(("transformer", "vae", "text_encoder")):
        if rfilename.startswith(component + "/"):
            return rank
    return 3


def download_model(
    name: str,
    out_dir: Path | None = None,
    dtype: torch.dtype | None = torch.bfloat16,
    text_encoder_fp8: bool = True,
    log: Callable = print,
) -> Path:
    """Fetch ``name`` (a key of KNOWN_MODELS or any repo id) into ``out_dir``; resumable."""
    from huggingface_hub import HfApi, hf_hub_download

    repo = KNOWN_MODELS.get(name, name)
    out = Path(out_dir or Path("models") / repo.split("/")[-1])
    out.mkdir(parents=True, exist_ok=True)
    siblings = HfApi().model_info(repo, files_metadata=True).siblings
    files = [s for s in siblings if not s.rfilename.endswith(SKIP_SUFFIXES)]
    weights = sorted(
        (f for f in files if f.rfilename.endswith(".safetensors")), key=lambda f: _order(f.rfilename)
    )
    log(f"{repo}: {len(weights)} weight files, {sum(f.size or 0 for f in weights) / 1e9:.1f} GB to download")
    for f in files:
        if not f.rfilename.endswith(".safetensors"):
            hf_hub_download(repo, f.rfilename, local_dir=out)
    for f in weights:
        target = out / f.rfilename
        done = target.with_name(target.name + ".done")
        if done.exists():
            continue
        need, free = (f.size or 0) * 1.05, shutil.disk_usage(out).free
        if free < need:
            raise OSError(f"{f.rfilename} needs {need / 1e9:.1f} GB of disk, only {free / 1e9:.1f} GB free")
        log(f"downloading {f.rfilename} ({(f.size or 0) / 1e9:.1f} GB)")
        path = Path(hf_hub_download(repo, f.rfilename, local_dir=out))
        if text_encoder_fp8 and f.rfilename.startswith("text_encoder/"):
            to_fp8_text_encoder(path)
            log(f"  stored as scaled fp8: {path.stat().st_size / 1e9:.1f} GB")
        elif dtype is not None and shrink(path, dtype):
            log(f"  stored as {str(dtype).removeprefix('torch.')}: {path.stat().st_size / 1e9:.1f} GB")
        done.touch()
    if text_encoder_fp8 and any(f.rfilename.startswith("text_encoder/") for f in weights):
        (out / "text_encoder" / FP8_MARKER).write_text(
            '{"linear_weights": "float8_e4m3fn, per-tensor scale"}\n'
        )
    return out
