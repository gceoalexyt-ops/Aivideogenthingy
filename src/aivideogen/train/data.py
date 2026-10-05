"""Training data: aspect-ratio buckets, media loading and the latent/text-embedding cache.

The VAE and the (large) UMT5 text encoder run once over the dataset; training then only needs the
transformer in memory.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from safetensors import safe_open
from safetensors.torch import load_file, save_file
from torch.utils.data import Dataset, Sampler

from aivideogen.dataset.files import Sample
from aivideogen.wan import encode_texts, latent_stats, pad_embeds

ASPECTS = (9 / 16, 2 / 3, 3 / 4, 4 / 5, 1.0, 5 / 4, 4 / 3, 3 / 2, 16 / 9)
CACHE_VERSION = "1"


def make_buckets(resolution: int, multiple: int) -> list[tuple[int, int]]:
    """(height, width) pairs with about resolution^2 pixels for common aspect ratios."""
    area = resolution * resolution
    buckets = set()
    for aspect in ASPECTS:  # aspect = width / height
        width = round(math.sqrt(area * aspect) / multiple) * multiple
        height = round(math.sqrt(area / aspect) / multiple) * multiple
        buckets.add((max(multiple, height), max(multiple, width)))
    return sorted(buckets)


def nearest_bucket(height: int, width: int, buckets: list[tuple[int, int]]) -> tuple[int, int]:
    target = math.log(width / height)
    return min(buckets, key=lambda hw: abs(math.log(hw[1] / hw[0]) - target))


def _fit(image: Image.Image, height: int, width: int) -> Image.Image:
    """Resize to cover (height, width) and center-crop. No flips: faces and hair partings are asymmetric."""
    scale = max(width / image.width, height / image.height)
    resized = image.resize(
        (max(width, math.ceil(image.width * scale)), max(height, math.ceil(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left, top = (resized.width - width) // 2, (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _to_tensor(frames: list[Image.Image]) -> torch.Tensor:
    """List of PIL frames -> (3, F, H, W) float tensor in [-1, 1]."""
    array = np.stack([np.asarray(f.convert("RGB"), dtype=np.float32) for f in frames])  # F, H, W, 3
    return torch.from_numpy(array).permute(3, 0, 1, 2) / 127.5 - 1.0


def media_size(sample: Sample) -> tuple[int, int]:
    """(height, width) of an image or the first frame of a clip."""
    if sample.is_video:
        import imageio.v2 as imageio

        with imageio.get_reader(sample.media, "ffmpeg") as reader:
            width, height = reader.get_meta_data()["size"]
        return height, width
    with Image.open(sample.media) as im:
        im = ImageOps.exif_transpose(im)
        return im.height, im.width


def load_frames(sample: Sample, max_frames: int, fps: int) -> list[Image.Image]:
    """One frame for images; up to ``max_frames`` frames (4k+1) resampled to ``fps`` for clips."""
    if not sample.is_video:
        with Image.open(sample.media) as im:
            return [ImageOps.exif_transpose(im).convert("RGB")]
    import imageio.v2 as imageio

    frames = []
    with imageio.get_reader(sample.media, "ffmpeg") as reader:
        source_fps = reader.get_meta_data().get("fps") or fps
        stride = max(1, round(source_fps / fps))
        for i, frame in enumerate(reader):
            if i % stride == 0:
                frames.append(Image.fromarray(frame))
                if len(frames) == max_frames:
                    break
    usable = (len(frames) - 1) // 4 * 4 + 1  # the VAE compresses time 4x after the first frame
    if usable < 1:
        raise ValueError(f"{sample.media}: no readable frames")
    return frames[:usable]


@dataclass(frozen=True)
class CacheEntry:
    path: Path
    shape: tuple[int, ...]  # latent shape (C, F, H, W); samples are batched by equal shape


class LatentCache:
    """Encodes media and captions once; results live as safetensors files keyed by their inputs."""

    def __init__(self, cache_dir: Path, base_model: str, max_sequence_length: int):
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.base_model = base_model
        self.max_sequence_length = max_sequence_length

    def _key(self, *parts) -> str:
        text = "|".join(str(p) for p in (CACHE_VERSION, self.base_model, self.max_sequence_length, *parts))
        return hashlib.sha1(text.encode()).hexdigest()[:24]

    def build(
        self,
        samples: list[Sample],
        vae,
        text_pipe,
        device: torch.device,
        resolution: int,
        multiple: int,
        video_frames: int,
        video_fps: int,
        log: Callable[[str], None] = print,
    ) -> list[CacheEntry]:
        buckets = make_buckets(resolution, multiple)
        mean, std = latent_stats(vae)
        entries = []
        for i, sample in enumerate(samples, 1):
            height, width = nearest_bucket(*media_size(sample), buckets)
            stat = sample.media.stat()
            frames = video_frames if sample.is_video else 1
            key = self._key(
                sample.media.resolve(),
                stat.st_mtime_ns,
                stat.st_size,
                height,
                width,
                frames,
                video_fps,
                sample.caption,
            )
            path = self.dir / f"{key}.safetensors"
            if not path.exists():
                log(f"encoding {i}/{len(samples)}: {sample.media.name} -> {width}x{height}")
                pixels = _to_tensor([_fit(f, height, width) for f in load_frames(sample, frames, video_fps)])
                with torch.no_grad():
                    latents = vae.encode(pixels.unsqueeze(0).to(device, vae.dtype)).latent_dist.mode()
                latents = ((latents.float().cpu() - mean) / std)[0]
                embeds = encode_texts(text_pipe, [sample.caption], self.max_sequence_length, device)[0]
                save_file({"latents": latents.contiguous(), "prompt_embeds": embeds.contiguous()}, str(path))
            with safe_open(str(path), "pt") as f:
                shape = tuple(f.get_slice("latents").get_shape())
            entries.append(CacheEntry(path, shape))
        return entries

    def texts(self, prompts: list[str], text_pipe, device: torch.device) -> list[torch.Tensor]:
        """Embeddings for arbitrary prompts (empty caption, sample prompts, negative prompt), cached."""
        out = []
        for prompt in prompts:
            path = self.dir / f"text_{self._key('text', prompt)}.safetensors"
            if not path.exists():
                if text_pipe is None:
                    raise RuntimeError("text encoder not loaded")
                embeds = encode_texts(text_pipe, [prompt], self.max_sequence_length, device)[0]
                save_file({"prompt_embeds": embeds.contiguous()}, str(path))
            out.append(load_file(str(path))["prompt_embeds"])
        return out


class CachedLatents(Dataset):
    def __init__(self, entries: list[CacheEntry], repeats: int = 1):
        self.entries = entries * max(1, repeats)

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        return load_file(str(self.entries[index].path))

    @property
    def shapes(self) -> list[tuple[int, ...]]:
        return [e.shape for e in self.entries]


class BucketBatchSampler(Sampler[list[int]]):
    """Endless stream of batches whose samples share a latent shape, reshuffled every epoch."""

    def __init__(self, shapes: list[tuple[int, ...]], batch_size: int, seed: int = 0):
        self.shapes = shapes
        self.batch_size = batch_size
        self.rng = random.Random(seed)

    def __iter__(self) -> Iterator[list[int]]:
        while True:
            groups: dict[tuple, list[int]] = defaultdict(list)
            for index, shape in enumerate(self.shapes):
                groups[shape].append(index)
            batches = []
            for indices in groups.values():
                self.rng.shuffle(indices)
                batches += [indices[i : i + self.batch_size] for i in range(0, len(indices), self.batch_size)]
            self.rng.shuffle(batches)
            yield from batches


def collate(
    items: list[dict[str, torch.Tensor]], max_sequence_length: int
) -> tuple[torch.Tensor, torch.Tensor]:
    latents = torch.stack([item["latents"] for item in items])
    embeds = pad_embeds([item["prompt_embeds"] for item in items], max_sequence_length)
    return latents, embeds
