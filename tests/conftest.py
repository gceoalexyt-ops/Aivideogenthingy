from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import pytest

from aivideogen.character import Character
from aivideogen.dataset.backends import MockBackend
from aivideogen.dataset.build import build_images, make_anchor_candidates
from aivideogen.dataset.files import DatasetPaths
from aivideogen.dataset.shots import plan_shots
from aivideogen.train.config import (
    DEFAULT_SAMPLE_PROMPTS,
    DataSection,
    LoraSection,
    ModelSection,
    OptimSection,
    RunConfig,
    SampleSection,
)
from aivideogen.wan import DEFAULT_NEGATIVE_PROMPT

REPO = Path(__file__).resolve().parent.parent
CHARACTER_FILE = REPO / "character.yaml"


def quiet(_message: str) -> None:
    pass


@pytest.fixture(scope="session")
def character() -> Character:
    return Character.load(CHARACTER_FILE)


@pytest.fixture(scope="session")
def tiny_model(tmp_path_factory, character) -> Path:
    from aivideogen.tiny import build_tiny_wan

    vocab = [s.caption(character) for s in plan_shots(character, 40)]
    vocab += [character.prompt_for(p) for p in DEFAULT_SAMPLE_PROMPTS] + [DEFAULT_NEGATIVE_PROMPT]
    return build_tiny_wan(tmp_path_factory.mktemp("models") / "tiny-wan", vocab)


@pytest.fixture(scope="session")
def dataset(tmp_path_factory, character) -> DatasetPaths:
    """Eight cartoon images of her plus one short video clip."""
    paths = DatasetPaths(tmp_path_factory.mktemp("data") / "dataset")
    backend = MockBackend()
    make_anchor_candidates(character, backend, paths, count=1, log=quiet)
    build_images(character, backend, paths, count=8, log=quiet)
    frames = [
        np.asarray(backend.text_to_image(f"medium shot {i}", aspect_ratio="16:9", seed=i)) for i in range(12)
    ]
    imageio.mimsave(paths.images / "clip.mp4", frames, fps=8)
    (paths.images / "clip.txt").write_text(
        f"{character.tag}, medium shot, walking toward the camera, in a park\n"
    )
    return paths


@pytest.fixture
def make_config(tmp_path, tiny_model, dataset):
    def _make(base_weights: str = "default", sample_every: int = 0, **train) -> RunConfig:
        return RunConfig(
            name="test",
            output_dir=tmp_path / "runs",
            character_file=CHARACTER_FILE,
            device="cpu",
            save_every=5,
            keep_checkpoints=2,
            model=ModelSection(base=str(tiny_model), precision="fp32", base_weights=base_weights),
            lora=LoraSection(rank=4, alpha=4),
            data=DataSection(
                dataset_dir=dataset.images,
                cache_dir=tmp_path / "cache",
                resolution=64,
                max_sequence_length=32,
                video_frames=9,
                video_fps=8,
            ),
            train=OptimSection(**{"steps": 10, "learning_rate": 1e-3, "warmup_steps": 0, **train}),
            sample=SampleSection(every=sample_every, width=32, height=32, num_frames=5, steps=2, fps=8),
        )

    return _make
