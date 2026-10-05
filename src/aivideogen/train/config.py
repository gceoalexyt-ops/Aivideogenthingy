"""Training run configuration (YAML presets live in ``configs/``)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

DEFAULT_SAMPLE_PROMPTS = [
    "close-up portrait, she smiles and looks into the camera, soft window light in a cozy cafe",
    "she walks along a busy city street at night, neon lights, cinematic tracking shot",
]


class ModelSection(BaseModel):
    base: str = "Wan-AI/Wan2.1-T2V-14B-Diffusers"
    precision: Literal["bf16", "fp16", "fp32"] = "bf16"
    # fp8 stores the frozen base weights in 8 bits (about half the VRAM) at a small quality cost.
    base_weights: Literal["default", "fp8"] = "default"


class LoraSection(BaseModel):
    rank: int = 32
    alpha: float = 32
    dropout: float = 0.0
    target_modules: list[str] = ["to_q", "to_k", "to_v", "to_out.0", "ffn.net.0.proj", "ffn.net.2"]


class DataSection(BaseModel):
    dataset_dir: Path = Path("data/dataset/images")
    cache_dir: Path = Path("data/cache")
    resolution: int = 512  # training area is resolution x resolution, split into aspect-ratio buckets
    video_frames: int = 33  # frames per training clip (must be 4k+1)
    video_fps: int = 16
    repeats: int = 1
    caption_dropout: float = 0.05
    max_sequence_length: int = 512

    @field_validator("video_frames")
    @classmethod
    def _four_k_plus_one(cls, v: int) -> int:
        if v < 1 or (v - 1) % 4:
            raise ValueError("video_frames must be 4k+1 (e.g. 17, 33, 49, 81)")
        return v


class OptimSection(BaseModel):
    steps: int = 2000
    batch_size: int = 1
    grad_accum: int = 1
    learning_rate: float = 1e-4
    lr_scheduler: str = "constant_with_warmup"
    warmup_steps: int = 50
    weight_decay: float = 1e-4
    max_grad_norm: float = 1.0
    optimizer: Literal["adamw", "adamw8bit"] = "adamw"
    timestep_sampling: Literal["logit_normal", "uniform"] = "logit_normal"
    logit_mean: float = 0.0
    logit_std: float = 1.0
    # >1 shifts training toward noisier timesteps (composition/likeness); 1.0 leaves the sampler as is.
    timestep_shift: float = 1.0
    gradient_checkpointing: bool = True
    seed: int = 42


class SampleSection(BaseModel):
    every: int = 250  # 0 disables sampling during training
    prompts: list[str] = Field(default_factory=lambda: list(DEFAULT_SAMPLE_PROMPTS))
    width: int = 832
    height: int = 480
    num_frames: int = 33
    steps: int = 30
    guidance: float = 5.0
    flow_shift: float = 3.0
    fps: int = 16
    seed: int = 42


class RunConfig(BaseModel):
    name: str = "mika"
    output_dir: Path = Path("runs")
    character_file: Path = Path("character.yaml")
    device: str = "auto"
    save_every: int = 250
    keep_checkpoints: int = 3
    model: ModelSection = Field(default_factory=ModelSection)
    lora: LoraSection = Field(default_factory=LoraSection)
    data: DataSection = Field(default_factory=DataSection)
    train: OptimSection = Field(default_factory=OptimSection)
    sample: SampleSection = Field(default_factory=SampleSection)

    @property
    def run_dir(self) -> Path:
        return self.output_dir / self.name

    @classmethod
    def load(cls, path: str | Path, overrides: dict | None = None) -> RunConfig:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for dotted, value in (overrides or {}).items():
            node = data
            *parents, leaf = dotted.split(".")
            for key in parents:
                node = node.setdefault(key, {})
            node[leaf] = value
        return cls.model_validate(data)

    def dump(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.model_dump(mode="json"), f, sort_keys=False)
