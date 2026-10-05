"""Dataset folder conventions: every image or clip sits next to a ``.txt`` caption with the same stem.

data/dataset/
  anchors/            candidate anchor portraits (pick one)
  anchor.png          her identity reference
  images/             training media + captions  (001.png + 001.txt, clip.mp4 + clip.txt, ...)
  manifest.jsonl      how each synthesized image was made
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from aivideogen.character import Character

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS


@dataclass(frozen=True)
class DatasetPaths:
    root: Path

    @property
    def anchors(self) -> Path:
        return self.root / "anchors"

    @property
    def anchor(self) -> Path:
        return self.root / "anchor.png"

    @property
    def images(self) -> Path:
        return self.root / "images"

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.jsonl"


@dataclass(frozen=True)
class Sample:
    media: Path
    caption: str

    @property
    def is_video(self) -> bool:
        return self.media.suffix.lower() in VIDEO_EXTS


def list_samples(images_dir: Path) -> list[Sample]:
    """All media files that have a caption, sorted by name."""
    images_dir = Path(images_dir)
    if not images_dir.is_dir():
        return []
    samples = []
    for media in sorted(images_dir.iterdir()):
        caption_file = media.with_suffix(".txt")
        if media.suffix.lower() in MEDIA_EXTS and caption_file.exists():
            samples.append(Sample(media, caption_file.read_text(encoding="utf-8").strip()))
    return samples


def ensure_tagged(caption: str, character: Character) -> str:
    caption = " ".join(caption.split())
    if character.trigger in caption.split(",")[0]:
        return caption
    return f"{character.tag}, {caption}" if caption else character.tag


def import_media(source: Path, paths: DatasetPaths, character: Character) -> int:
    """Copy your own images/clips of her into the dataset.

    A ``.txt`` caption next to a source file is kept (with the trigger tag added if missing); files without
    one get just the tag, which you should then extend with what's in the picture (outfit, place, light).
    """
    paths.images.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in sorted(Path(source).iterdir()):
        if src.suffix.lower() not in MEDIA_EXTS:
            continue
        dest = paths.images / f"user_{src.stem}{src.suffix.lower()}"
        shutil.copy2(src, dest)
        sidecar = src.with_suffix(".txt")
        caption = sidecar.read_text(encoding="utf-8") if sidecar.exists() else ""
        dest.with_suffix(".txt").write_text(ensure_tagged(caption, character) + "\n", encoding="utf-8")
        count += 1
    return count


@dataclass
class DatasetReport:
    images: int = 0
    videos: int = 0
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def __str__(self) -> str:
        lines = [f"{self.images} images, {self.videos} video clips"]
        lines += [f"  problem: {p}" for p in self.problems]
        lines += [f"  warning: {w}" for w in self.warnings]
        return "\n".join(lines)


def check_dataset(images_dir: Path, character: Character, min_side: int = 384) -> DatasetReport:
    report = DatasetReport()
    images_dir = Path(images_dir)
    if not images_dir.is_dir():
        report.problems.append(f"{images_dir} does not exist")
        return report
    seen: dict[str, Path] = {}
    for media in sorted(images_dir.iterdir()):
        ext = media.suffix.lower()
        if ext not in MEDIA_EXTS:
            continue
        caption_file = media.with_suffix(".txt")
        if not caption_file.exists():
            report.problems.append(f"{media.name}: no caption file ({caption_file.name})")
        elif character.trigger not in caption_file.read_text(encoding="utf-8"):
            report.problems.append(
                f"{media.name}: caption doesn't contain the trigger word {character.trigger!r}"
            )
        digest = hashlib.sha1(media.read_bytes()).hexdigest()
        if digest in seen:
            report.warnings.append(f"{media.name} is a duplicate of {seen[digest].name}")
        seen[digest] = media
        if ext in VIDEO_EXTS:
            report.videos += 1
            continue
        report.images += 1
        try:
            with Image.open(media) as im:
                if min(im.size) < min_side:
                    report.warnings.append(
                        f"{media.name} is small ({im.size[0]}x{im.size[1]}); detail will suffer"
                    )
        except OSError:
            report.problems.append(f"{media.name}: unreadable image")
    total = report.images + report.videos
    if total == 0:
        report.problems.append("dataset is empty")
    elif total < 15:
        report.warnings.append(
            f"only {total} samples; 25-50 varied images give a much more reliable likeness"
        )
    return report
