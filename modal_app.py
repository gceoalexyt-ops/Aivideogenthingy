"""Run the GPU-heavy steps on a Modal cloud GPU from any machine, including a laptop without a GPU.

    pip install -e '.[cloud]' && modal setup                 # once
    modal run modal_app.py::dataset --count 40    # synthesize her dataset with the open Qwen models
    modal run modal_app.py::train --config configs/wan21_14b.yaml
    modal run modal_app.py::generate --prompt "Mika walks through a rainy neon-lit street at night"

Model weights, the dataset, caches, runs and outputs persist on the Modal volume ``aivideogen``. A dataset in
the local ``data/dataset`` folder (e.g. one built with ``--backend replicate`` or imported photos) is uploaded
before training; the trained LoRA and generated videos are downloaded back into ``runs/`` and ``outputs/``.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import modal

GPU = os.environ.get("AIVIDEOGEN_GPU", "H100")
VOL = "/vol"

app = modal.App("aivideogen")
volume = modal.Volume.from_name("aivideogen", create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .uv_pip_install(
        "torch>=2.5",
        "diffusers>=0.36",
        "transformers>=4.56",
        "peft>=0.17",
        "accelerate>=1.0",
        "safetensors",
        "sentencepiece",
        "ftfy",
        "numpy",
        "pillow",
        "pyyaml",
        "pydantic>=2",
        "imageio[ffmpeg]",
    )
    .env({"HF_HOME": f"{VOL}/hf"})
    .add_local_file("character.yaml", "/app/character.yaml")
    .add_local_dir("configs", "/app/configs")
    .add_local_python_source("aivideogen")
)
remote = app.function(image=image, gpu=GPU, volumes={VOL: volume}, timeout=12 * 3600)


def _enter_volume() -> None:
    """Work inside the volume so the repo's relative paths (data/, runs/, outputs/) persist."""
    volume.reload()
    os.chdir(VOL)
    shutil.copyfile("/app/character.yaml", "character.yaml")


@remote
def build_dataset_remote(count: int, anchors: int, seed: int) -> None:
    from aivideogen.cli import main

    _enter_volume()
    if not Path("data/dataset/anchor.png").exists():
        main(["dataset", "anchor", "--backend", "qwen", "--count", str(anchors), "--seed", str(seed)])
    main(["dataset", "build", "--backend", "qwen", "--count", str(count), "--seed", str(seed)])
    volume.commit()


@remote
def train_remote(config_name: str, resume: bool, overrides: list[str]) -> str:
    from aivideogen.cli import main
    from aivideogen.train.config import RunConfig

    _enter_volume()
    config = f"/app/configs/{config_name}"
    args = ["train", "--config", config, *(["--resume"] if resume else [])]
    for override in overrides:
        args += ["--set", override]
    try:
        main(args)
    finally:
        volume.commit()  # keep checkpoints even if training stops early
    return RunConfig.load(config).name


@remote
def generate_remote(prompt: str, run: str, extra: list[str]) -> tuple[str, bytes]:
    from aivideogen.cli import main

    _enter_volume()
    main(["generate", prompt, *(["--lora", f"runs/{run}"] if run else []), "--out", "outputs", *extra])
    volume.commit()
    video = max(Path("outputs").glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    return video.name, video.read_bytes()


def _download(remote_dir: str, local_dir: Path) -> int:
    count = 0
    for entry in volume.listdir(remote_dir, recursive=True):
        if entry.type != modal.volume.FileEntryType.FILE:
            continue
        target = local_dir / Path(entry.path).relative_to(remote_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as f:
            for chunk in volume.read_file(entry.path):
                f.write(chunk)
        count += 1
    return count


@app.local_entrypoint()
def dataset(count: int = 40, anchors: int = 4, seed: int = 0):
    build_dataset_remote.remote(count, anchors, seed)
    print(f"downloaded {_download('data/dataset', Path('data/dataset'))} files into data/dataset")
    print("Review the images, delete bad ones, then run: modal run modal_app.py::train")


@app.local_entrypoint()
def train(config: str = "configs/wan21_14b.yaml", resume: bool = False, steps: int = 0, upload: bool = True):
    local = Path("data/dataset")
    if upload and (local / "images").is_dir():
        with volume.batch_upload(force=True) as batch:
            batch.put_directory(str(local), "/data/dataset")
        print(f"uploaded {local} to the volume")
    name = train_remote.remote(Path(config).name, resume, [f"train.steps={steps}"] if steps else [])
    files = _download(f"runs/{name}/final", Path("runs") / name / "final")
    _download(f"runs/{name}/samples", Path("runs") / name / "samples")
    print(f"downloaded her LoRA ({files} files) to runs/{name}/final")


@app.local_entrypoint()
def generate(prompt: str, run: str = "", frames: int = 0, seed: int = -1, lora_scale: float = 1.0):
    extra = ["--lora-scale", str(lora_scale)]
    if frames:
        extra += ["--frames", str(frames)]
    if seed >= 0:
        extra += ["--seed", str(seed)]
    name, data = generate_remote.remote(prompt, run, extra)
    out = Path("outputs") / name
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(data)
    print(f"saved {out}")
