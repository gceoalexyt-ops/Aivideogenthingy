import json

import pytest
from PIL import Image

from aivideogen.dataset.backends import ASPECT_RATIOS, MockBackend, size_for
from aivideogen.dataset.build import build_images, make_anchor_candidates, pick_anchor
from aivideogen.dataset.files import DatasetPaths, check_dataset, import_media, list_samples
from aivideogen.dataset.shots import plan_shots
from aivideogen.train.data import make_buckets, nearest_bucket
from tests.conftest import quiet


def test_shot_plan_is_reproducible_and_varied(character):
    shots = plan_shots(character, 40, seed=3)
    assert shots == plan_shots(character, 40, seed=3)
    assert shots != plan_shots(character, 40, seed=4)
    assert len(shots) == 40
    assert [s.index for s in shots] == list(range(1, 41))
    assert len({s.setting for s in shots}) >= 10
    assert len({s.outfit for s in shots}) >= 8
    assert all(s.aspect_ratio in ASPECT_RATIOS for s in shots)
    # The character sheet comes first: front-facing close-up on a plain backdrop.
    assert shots[0].framing == "close-up portrait" and shots[0].angle == "facing the camera"


def test_captions_bind_identity_to_the_trigger(character):
    for shot in plan_shots(character, 20):
        caption = shot.caption(character)
        assert caption.startswith("mksrn woman, ")
        # Her face and hair must not be described in captions, so the model attaches them to the trigger.
        for feature_word in ("hazel", "freckles", "beauty mark", "dark-brown", "Eurasian"):
            assert feature_word not in caption
        assert "hazel-brown eyes" in shot.generation_prompt(character)


@pytest.mark.parametrize("ratio", list(ASPECT_RATIOS))
def test_size_for_respects_ratio_and_multiple(ratio):
    w, h = size_for(ratio, 1024 * 1024, multiple=32)
    rw, rh = ASPECT_RATIOS[ratio]
    assert w % 32 == 0 and h % 32 == 0
    assert abs(w / h - rw / rh) < 0.06
    assert 0.85 < w * h / (1024 * 1024) < 1.15


def test_buckets_pick_the_closest_aspect():
    buckets = make_buckets(512, 16)
    assert all(h % 16 == 0 and w % 16 == 0 for h, w in buckets)
    assert (
        nearest_bucket(1080, 1920, buckets)[1] > nearest_bucket(1080, 1920, buckets)[0]
    )  # landscape stays landscape
    assert nearest_bucket(1000, 1000, buckets) == (512, 512)


def test_build_is_resumable_and_writes_manifest(tmp_path, character):
    paths = DatasetPaths(tmp_path / "ds")
    backend = MockBackend()
    make_anchor_candidates(character, backend, paths, count=2, log=quiet)
    assert paths.anchor.exists()
    pick_anchor(paths, 2)
    made, failures = build_images(character, backend, paths, count=5, log=quiet)
    assert (made, failures) == (5, [])
    assert build_images(character, backend, paths, count=5, log=quiet)[0] == 0
    samples = list_samples(paths.images)
    assert len(samples) == 6  # anchor + 5 shots
    assert all(s.caption.startswith(character.tag) for s in samples)
    records = [json.loads(line) for line in paths.manifest.read_text().splitlines()]
    assert len(records) == 5 and records[0]["backend"] == "mock"
    assert check_dataset(paths.images, character).ok


def test_build_needs_an_anchor(tmp_path, character):
    with pytest.raises(FileNotFoundError, match="anchor"):
        build_images(character, MockBackend(), DatasetPaths(tmp_path / "empty"), count=1, log=quiet)


def test_one_failed_image_does_not_stop_the_batch(tmp_path, character):
    class Flaky(MockBackend):
        def edit(self, prompt, references, *, aspect_ratio, seed):
            if seed == 2:
                raise RuntimeError("refused")
            return super().edit(prompt, references, aspect_ratio=aspect_ratio, seed=seed)

    paths = DatasetPaths(tmp_path / "ds")
    make_anchor_candidates(character, Flaky(), paths, count=1, log=quiet)
    made, failures = build_images(character, Flaky(), paths, count=3, log=quiet)
    assert made == 2 and len(failures) == 1 and "refused" in failures[0]


def test_import_tags_captions_and_check_reports_problems(tmp_path, character):
    source = tmp_path / "mine"
    source.mkdir()
    for name in ("a", "b"):
        Image.new("RGB", (600, 800), "gray").save(source / f"{name}.jpg")
    (source / "a.txt").write_text("sitting on a bench in a park")
    paths = DatasetPaths(tmp_path / "ds")
    assert import_media(source, paths, character) == 2
    captions = {s.media.name: s.caption for s in list_samples(paths.images)}
    assert captions["user_a.jpg"] == "mksrn woman, sitting on a bench in a park"
    assert captions["user_b.jpg"] == "mksrn woman"

    (paths.images / "user_b.txt").write_text("no trigger here")
    Image.new("RGB", (100, 100)).save(paths.images / "orphan.png")
    report = check_dataset(paths.images, character)
    assert not report.ok
    assert any("trigger" in p for p in report.problems)
    assert any("orphan.png" in p for p in report.problems)
    assert any("small" in w for w in report.warnings)
