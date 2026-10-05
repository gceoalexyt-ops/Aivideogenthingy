"""Turn her trained LoRA into other forms.

- ``comfyui``: the LoRA with original Wan key names, loadable by ComfyUI and most other Wan tools.
- ``merged``: base model with the LoRA fused in, saved as its own standalone diffusers model.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import save_file

_MODULE_MAP = [
    (re.compile(r"\.attn1\.to_q$"), ".self_attn.q"),
    (re.compile(r"\.attn1\.to_k$"), ".self_attn.k"),
    (re.compile(r"\.attn1\.to_v$"), ".self_attn.v"),
    (re.compile(r"\.attn1\.to_out\.0$"), ".self_attn.o"),
    (re.compile(r"\.attn2\.to_q$"), ".cross_attn.q"),
    (re.compile(r"\.attn2\.to_k$"), ".cross_attn.k"),
    (re.compile(r"\.attn2\.to_v$"), ".cross_attn.v"),
    (re.compile(r"\.attn2\.to_out\.0$"), ".cross_attn.o"),
    (re.compile(r"\.ffn\.net\.0\.proj$"), ".ffn.0"),
    (re.compile(r"\.ffn\.net\.2$"), ".ffn.2"),
]


def _lora_alpha(lora_file: Path) -> float | None:
    with safe_open(str(lora_file), "pt") as f:
        metadata = f.metadata() or {}
    raw = metadata.get("lora_adapter_metadata")
    if not raw:
        return None
    info = json.loads(raw)
    for key in ("transformer.lora_alpha", "lora_alpha"):
        if key in info:
            return float(info[key])
    return None


def to_comfyui(lora_file: Path, out_file: Path) -> Path:
    """Rename diffusers LoRA keys to Wan's original names.

    ``transformer.blocks.0.attn1.to_q`` becomes ``diffusion_model.blocks.0.self_attn.q``.
    """
    tensors = {}
    with safe_open(str(lora_file), "pt") as f:
        for key in f.keys():
            tensors[key] = f.get_tensor(key)
    alpha = _lora_alpha(lora_file)
    converted: dict[str, torch.Tensor] = {}
    for key, value in tensors.items():
        module, _, param = key.removeprefix("transformer.").partition(".lora_")
        for pattern, replacement in _MODULE_MAP:
            if pattern.search(module):
                module = pattern.sub(replacement, module)
                break
        else:
            raise ValueError(f"don't know the Wan name for LoRA module {module!r}")
        target = f"diffusion_model.{module}"
        converted[f"{target}.lora_{param}"] = value.contiguous()
        if alpha is not None and param == "A.weight":
            converted[f"{target}.alpha"] = torch.tensor(alpha)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    save_file(converted, str(out_file))
    return out_file


def merged_model(
    base: str, lora_file: Path, out_dir: Path, scale: float = 1.0, precision: str = "bf16"
) -> Path:
    """Save base + LoRA fused into one standalone model directory (``WanPipeline.from_pretrained(out)``)."""
    from diffusers import WanPipeline

    from aivideogen.wan import dtype_kwarg

    dtype = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[precision]
    pipe = WanPipeline.from_pretrained(base, **dtype_kwarg(dtype))
    pipe.load_lora_weights(str(lora_file.parent), weight_name=lora_file.name, adapter_name="character")
    pipe.fuse_lora(lora_scale=scale)
    pipe.unload_lora_weights()
    pipe.save_pretrained(out_dir, safe_serialization=True)
    character = lora_file.parent / "character.yaml"
    if character.exists():
        shutil.copyfile(character, out_dir / "character.yaml")
    (out_dir / "README.md").write_text(
        f"# Standalone character model\n\n{base} with the LoRA `{lora_file}` fused in at scale {scale}.\n\n"
        "```python\nfrom diffusers import WanPipeline\n"
        f'pipe = WanPipeline.from_pretrained("{out_dir}")\n```\n'
    )
    return out_dir
