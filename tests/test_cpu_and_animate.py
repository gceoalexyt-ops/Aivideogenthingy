"""The no-GPU path: bf16 on CPU, one-model-at-a-time loading, animating her photo, and the downloader."""

import json
from types import SimpleNamespace

import pytest
import torch
from PIL import Image

from aivideogen.download import download_model, shrink
from aivideogen.generate import GenerationSettings, VideoGenerator, fit_to_image
from aivideogen.train.trainer import Trainer
from aivideogen.wan import cpu_supports_bf16, resolve_dtype
from tests.conftest import quiet


@pytest.fixture(scope="module")
def tiny_ti2v(tmp_path_factory, character):
    from aivideogen.tiny import build_tiny_wan

    vocab = [character.prompt_for("she sips her coffee and smiles at the camera")]
    return build_tiny_wan(tmp_path_factory.mktemp("ti2v") / "tiny-ti2v", vocab, image_to_video=True)


@pytest.fixture
def photo(tmp_path):
    path = tmp_path / "profile.jpg"
    Image.new("RGB", (300, 400), "tan").save(path)
    return path


def test_fit_to_image_keeps_the_photo_aspect():
    assert fit_to_image(640 * 480, (1086, 1448), 32) == (480, 640)
    width, height = fit_to_image(832 * 480, (1920, 1080), 16)
    assert width % 16 == 0 and height % 16 == 0 and width > height


def test_cpu_precision_follows_the_hardware():
    cpu = torch.device("cpu")
    assert resolve_dtype("fp32", cpu) == torch.float32
    assert resolve_dtype("bf16", cpu) == (torch.bfloat16 if cpu_supports_bf16() else torch.float32)


def test_animate_her_photo_on_cpu_one_model_at_a_time(tiny_ti2v, photo, tmp_path, character):
    generator = VideoGenerator(str(tiny_ti2v), None, character, device="cpu", precision="fp32")
    assert generator.sequential
    assert generator.load().text_encoder is None, "text encoder and video model never share RAM"
    settings = GenerationSettings(width=64, height=48, num_frames=5, fps=8, steps=2, seed=3)
    video = generator.generate("she sips her coffee and smiles", settings, tmp_path, image=photo)
    assert video.exists() and video.stat().st_size > 0
    assert generator._pipe is None, "the video model is freed before decoding"
    info = json.loads(video.with_suffix(".json").read_text())
    assert info["image"] == str(photo)
    assert (info["width"], info["height"]) == (48, 64), "portrait photo -> portrait video"
    import imageio.v3 as iio

    frames = iio.imread(video)
    assert frames.shape[0] == 5 and frames.shape[1:3] == (64, 48)
    # The next clip, with a new prompt, reloads what it needs.
    generator.generate("mksrn woman laughs", settings, tmp_path, image=photo)
    assert len(generator._embeds) == 3


def test_text_to_video_models_refuse_to_animate(tiny_model, photo, tmp_path, character):
    generator = VideoGenerator(str(tiny_model), None, character, device="cpu", precision="fp32")
    with pytest.raises(ValueError, match="TI2V"):
        generator.generate(
            "she waves", GenerationSettings(width=32, height=32, num_frames=5, steps=1), tmp_path, image=photo
        )


def test_cli_animate_uses_the_profile_photo(tiny_ti2v, photo, tmp_path, monkeypatch):
    import yaml

    from aivideogen.cli import main
    from tests.conftest import CHARACTER_FILE

    data = yaml.safe_load(CHARACTER_FILE.read_text())
    data["reference_image"] = str(photo)
    character_file = tmp_path / "her.yaml"
    character_file.write_text(yaml.safe_dump(data))
    main(
        [
            "--character",
            str(character_file),
            "animate",
            "she smiles",
            "--base",
            str(tiny_ti2v),
            "--width",
            "64",
            "--height",
            "48",
            "--frames",
            "5",
            "--steps",
            "2",
            "--device",
            "cpu",
            "--precision",
            "fp32",
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert len(list((tmp_path / "out").glob("*.mp4"))) == 1


@pytest.mark.skipif(not cpu_supports_bf16(), reason="needs a CPU with AMX or AVX512-BF16")
def test_bf16_training_on_cpu(make_config):
    cfg = make_config(steps=3)
    cfg.model.precision = "bf16"
    trainer = Trainer(cfg, log=quiet)
    assert trainer.dtype == torch.bfloat16
    trainer.run()
    losses = [json.loads(line)["loss"] for line in (trainer.run_dir / "log.jsonl").read_text().splitlines()]
    assert len(losses) == 3 and all(torch.isfinite(torch.tensor(losses)))


def test_shrink_casts_only_float32(tmp_path):
    from safetensors.torch import load_file, save_file

    path = tmp_path / "w.safetensors"
    save_file({"a": torch.ones(2, dtype=torch.float32), "b": torch.ones(2, dtype=torch.int64)}, str(path))
    assert shrink(path)
    loaded = load_file(str(path))
    assert loaded["a"].dtype == torch.bfloat16 and loaded["b"].dtype == torch.int64
    assert not shrink(path), "already bf16: nothing to do"


def test_download_shrinks_the_model_for_small_disks(tiny_model, tmp_path, monkeypatch):
    """Serve the tiny model as a fake Hugging Face repo and check what lands on disk."""
    import shutil

    import huggingface_hub
    from diffusers import WanPipeline

    files = sorted(p.relative_to(tiny_model).as_posix() for p in tiny_model.rglob("*") if p.is_file())
    siblings = [SimpleNamespace(rfilename=f, size=(tiny_model / f).stat().st_size) for f in files]
    siblings.append(SimpleNamespace(rfilename="README.md", size=10))

    class FakeApi:
        def model_info(self, repo, files_metadata=False):
            return SimpleNamespace(siblings=siblings)

    def fake_download(repo, filename, local_dir):
        assert filename != "README.md", "docs and images are skipped"
        target = local_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tiny_model / filename, target)
        return str(target)

    monkeypatch.setattr(huggingface_hub, "HfApi", FakeApi)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", fake_download)
    out = download_model("some/repo", tmp_path / "model", log=quiet)

    def tensors(component):
        from safetensors.torch import load_file

        return load_file(str(next((out / component).glob("*.safetensors"))))

    assert {t.dtype for t in tensors("transformer").values()} == {torch.bfloat16}
    assert {t.dtype for t in tensors("vae").values()} == {torch.bfloat16}
    text = tensors("text_encoder")
    assert text["encoder.block.0.layer.0.SelfAttention.q.weight"].dtype == torch.float8_e4m3fn
    assert text["encoder.block.0.layer.0.SelfAttention.q.fp8_scale"].dtype == torch.float32
    assert text["shared.weight"].dtype == torch.bfloat16, "embeddings stay bf16"
    assert (out / "text_encoder" / "fp8.json").exists()

    # The compact text encoder loads and gives nearly the same embeddings as the original.
    from transformers import UMT5EncoderModel

    from aivideogen.wan import load_text_encoder

    original = UMT5EncoderModel.from_pretrained(tiny_model, subfolder="text_encoder")
    compact = load_text_encoder(str(out), torch.float32)
    ids = torch.tensor([[3, 4, 5, 6, 1]])
    with torch.no_grad():
        a, b = original(ids).last_hidden_state, compact(ids).last_hidden_state
    assert torch.nn.functional.cosine_similarity(a.flatten(), b.flatten(), dim=0) > 0.99
    WanPipeline.from_pretrained(out)  # still a loadable model
    assert download_model("some/repo", tmp_path / "model", log=quiet) == out  # resumable no-op
