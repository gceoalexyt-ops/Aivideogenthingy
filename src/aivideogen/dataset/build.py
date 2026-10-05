"""Synthesize her training dataset: one anchor portrait, then many shots that keep her identity."""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageOps

from aivideogen.character import Character
from aivideogen.dataset.backends import ImageBackend
from aivideogen.dataset.files import DatasetPaths, ensure_tagged
from aivideogen.dataset.shots import anchor_caption, anchor_prompt, plan_shots
from aivideogen.safety import check_prompt

Log = Callable[[str], None]


def make_anchor_candidates(
    character: Character,
    backend: ImageBackend,
    paths: DatasetPaths,
    count: int = 4,
    seed: int = 0,
    log: Log = print,
) -> list[Path]:
    """Draw ``count`` candidate portraits of her. Pick the best one with :func:`pick_anchor`."""
    paths.anchors.mkdir(parents=True, exist_ok=True)
    prompt = check_prompt(anchor_prompt(character))
    out = []
    for i in range(1, count + 1):
        target = paths.anchors / f"candidate_{i}.png"
        log(f"anchor candidate {i}/{count} -> {target}")
        backend.text_to_image(prompt, aspect_ratio="1:1", seed=seed + i).save(target)
        out.append(target)
    if not paths.anchor.exists() and out:
        pick_anchor(paths, 1, character)
    return out


def set_anchor(paths: DatasetPaths, source: Path, caption: str) -> Path:
    """Make ``source`` her identity reference. The caption describing it is kept alongside."""
    paths.root.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        ImageOps.exif_transpose(image).convert("RGB").save(paths.anchor)
    paths.anchor.with_suffix(".txt").write_text(caption + "\n", encoding="utf-8")
    return paths.anchor


def pick_anchor(paths: DatasetPaths, choice: str | int | Path, character: Character) -> Path:
    """Make a generated candidate (by number, e.g. ``2``) or any image of her (by path) the anchor."""
    if isinstance(choice, int) or str(choice).isdigit():
        source, caption = paths.anchors / f"candidate_{int(choice)}.png", anchor_caption(character)
    else:
        # An arbitrary photo: we don't know what it shows, so the caption is just her tag.
        source, caption = Path(choice), character.tag
    if not source.exists():
        raise FileNotFoundError(source)
    return set_anchor(paths, source, caption)


def install_reference(character: Character, paths: DatasetPaths) -> Path:
    """Use the profile photo named in character.yaml (``reference_image``) as her anchor."""
    photo = character.reference_image
    if photo is None:
        raise ValueError("character.yaml has no reference_image")
    if not photo.exists():
        raise FileNotFoundError(
            f"Her profile photo {photo} is missing (it isn't committed to git). Put the photo there, "
            "or remove reference_image from character.yaml to generate her face from text instead."
        )
    return set_anchor(paths, photo, ensure_tagged(character.reference_caption, character))


def build_images(
    character: Character,
    backend: ImageBackend,
    paths: DatasetPaths,
    count: int = 40,
    seed: int = 0,
    overwrite: bool = False,
    log: Log = print,
) -> tuple[int, list[str]]:
    """Generate the shot list with her anchor as identity reference. Existing images are kept (resumable).

    Returns (number of new images, list of failures).
    """
    if not paths.anchor.exists():
        if character.reference_image is None:
            raise FileNotFoundError(
                f"No anchor portrait at {paths.anchor}. Run `aivideogen dataset anchor` first."
            )
        install_reference(character, paths)
        log(f"using her profile photo {character.reference_image} as the anchor")
    paths.images.mkdir(parents=True, exist_ok=True)

    anchor_copy = paths.images / "000_anchor.png"
    if overwrite or not anchor_copy.exists():
        shutil.copyfile(paths.anchor, anchor_copy)
        caption_file = paths.anchor.with_suffix(".txt")
        caption = caption_file.read_text(encoding="utf-8").strip() if caption_file.exists() else ""
        anchor_copy.with_suffix(".txt").write_text(
            (caption or anchor_caption(character)) + "\n", encoding="utf-8"
        )

    shots = plan_shots(character, count, seed)
    made, failures = 0, []
    with open(paths.manifest, "a", encoding="utf-8") as manifest:
        for shot in shots:
            target = paths.images / f"{shot.stem}.png"
            if target.exists() and not overwrite:
                continue
            prompt = check_prompt(shot.generation_prompt(character))
            log(f"[{shot.index}/{len(shots)}] {shot.framing}, {shot.setting}")
            try:
                image = backend.edit(
                    prompt, [paths.anchor], aspect_ratio=shot.aspect_ratio, seed=seed + shot.index
                )
            except Exception as e:  # one refused or failed image shouldn't stop the batch
                failures.append(f"{shot.stem}: {e}")
                log(f"  failed: {e}")
                continue
            image.save(target)
            target.with_suffix(".txt").write_text(shot.caption(character) + "\n", encoding="utf-8")
            record = {
                "file": target.name,
                "caption": shot.caption(character),
                "prompt": prompt,
                "backend": backend.name,
                "seed": seed + shot.index,
                "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "shot": shot.to_dict(),
            }
            manifest.write(json.dumps(record) + "\n")
            manifest.flush()
            made += 1
    return made, failures
