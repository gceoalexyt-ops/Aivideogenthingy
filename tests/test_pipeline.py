"""Train -> save -> load -> generate -> export, on the miniature Wan model (CPU, a few seconds each)."""

import json

import pytest
import torch
from safetensors.torch import load_file

from aivideogen.export import merged_model, to_comfyui
from aivideogen.generate import GenerationSettings, VideoGenerator, base_model_of, find_lora
from aivideogen.train.trainer import LORA_WEIGHTS, Trainer, train
from tests.conftest import quiet


@pytest.fixture(scope="module")
def trained(tmp_path_factory, tiny_model, dataset):
    """One finished run shared by the tests that only read its outputs."""
    from aivideogen.train.config import (
        DataSection,
        LoraSection,
        ModelSection,
        OptimSection,
        RunConfig,
        SampleSection,
    )
    from tests.conftest import CHARACTER_FILE

    root = tmp_path_factory.mktemp("trained")
    cfg = RunConfig(
        name="shared",
        output_dir=root / "runs",
        character_file=CHARACTER_FILE,
        device="cpu",
        save_every=5,
        model=ModelSection(base=str(tiny_model), precision="fp32"),
        lora=LoraSection(rank=4, alpha=8),
        data=DataSection(
            dataset_dir=dataset.images,
            cache_dir=root / "cache",
            resolution=64,
            max_sequence_length=32,
            video_frames=9,
            video_fps=8,
        ),
        train=OptimSection(steps=12, learning_rate=2e-3, warmup_steps=0),
        sample=SampleSection(every=6, width=32, height=32, num_frames=5, steps=2, fps=8),
    )
    final = train(cfg, log=quiet)
    return cfg, final


def test_training_produces_lora_samples_checkpoints_and_status(trained):
    cfg, final = trained
    weights = final / LORA_WEIGHTS
    assert weights.exists()
    lora = load_file(str(weights))
    assert any(k.startswith("transformer.blocks.0.attn1.to_q.lora_A") for k in lora)
    assert any(".ffn.net.2.lora_B" in k for k in lora)
    assert any(v.abs().sum() > 0 for k, v in lora.items() if "lora_B" in k), "LoRA never moved from its init"
    assert (final / "character.yaml").exists() and (final / "README.md").exists()

    run = cfg.run_dir
    status = json.loads((run / "status.json").read_text())
    assert status["state"] == "done" and status["step"] == 12
    assert len((run / "log.jsonl").read_text().splitlines()) == 12
    assert sorted(p.name for p in (run / "samples").glob("*.mp4")) == [
        "step000006_0.mp4",
        "step000006_1.mp4",
        "step000012_0.mp4",
        "step000012_1.mp4",
    ]
    checkpoints = [p.name for p in sorted((run / "checkpoints").glob("step-*"))]
    assert checkpoints == ["step-000005", "step-000010", "step-000012"]
    assert (run / "checkpoints" / "step-000012" / "training_state.pt").exists()


def test_video_clips_are_cached_with_their_frames(trained):
    cfg, _ = trained
    shapes = {
        tuple(load_file(str(p))["latents"].shape) for p in cfg.data.cache_dir.glob("[0-9a-f]*.safetensors")
    }
    frames = {shape[1] for shape in shapes}
    assert frames == {1, 3}, "images encode to 1 latent frame, the 9-frame clip to 3"


def test_resume_extends_a_finished_run(make_config):
    first = make_config(steps=6)
    train(first, log=quiet)
    more = make_config(steps=9)
    messages = []
    Trainer(more, log=messages.append).run(resume=True)
    assert any("resumed from step-000006" in m for m in messages)
    steps = [json.loads(line)["step"] for line in (more.run_dir / "log.jsonl").read_text().splitlines()]
    assert steps == [1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_fp8_base_weights_train(make_config):
    messages = []
    trainer = Trainer(make_config(steps=3, base_weights="fp8"), log=messages.append)
    final = trainer.run()
    converted = [m for m in messages if "in fp8" in m]
    assert converted and not converted[0].startswith("stored 0 "), converted
    assert (final / LORA_WEIGHTS).exists()
    losses = [json.loads(line)["loss"] for line in (trainer.run_dir / "log.jsonl").read_text().splitlines()]
    assert len(losses) == 3 and all(torch.isfinite(torch.tensor(losses)))


def test_store_frozen_linears_in_fp8_matches_full_precision(tiny_model):
    from diffusers import WanTransformer3DModel

    from aivideogen.wan import store_frozen_linears_in_fp8

    model = WanTransformer3DModel.from_pretrained(tiny_model, subfolder="transformer").requires_grad_(False)
    x = torch.randn(1, 4, 1, 8, 8)
    t = torch.tensor([500.0])
    text = torch.randn(1, 8, 32)
    with torch.no_grad():
        reference = model(x, t, text, return_dict=False)[0]
        assert store_frozen_linears_in_fp8(model) > 0
        quantized = model(x, t, text, return_dict=False)[0]
    assert model.blocks[0].attn1.to_q.weight.dtype == torch.float8_e4m3fn
    assert torch.allclose(reference, quantized, atol=0.15), (reference - quantized).abs().max()


def test_generate_writes_video_with_metadata(trained, tmp_path, character):
    cfg, final = trained
    lora = find_lora(final)
    assert base_model_of(lora) == cfg.model.base
    generator = VideoGenerator(cfg.model.base, lora, character, device="cpu", precision="fp32")
    settings = GenerationSettings(width=32, height=32, num_frames=5, fps=8, steps=2, seed=7, lora_scale=0.8)
    video = generator.generate("Mika waves hello", settings, tmp_path)
    assert video.suffix == ".mp4" and video.stat().st_size > 0
    info = json.loads(video.with_suffix(".json").read_text())
    assert info["prompt"] == "mksrn woman waves hello"
    assert info["seed"] == 7 and info["lora_scale"] == 0.8


def test_generate_rejects_unsafe_prompts(trained, character):
    cfg, final = trained
    from aivideogen.safety import UnsafePromptError

    generator = VideoGenerator(cfg.model.base, find_lora(final), character, device="cpu", precision="fp32")
    with pytest.raises(UnsafePromptError):
        generator.generate(
            "Mika as a teenager", GenerationSettings(width=32, height=32, num_frames=5, steps=1)
        )


def _transformer_output(pipe) -> torch.Tensor:
    torch.manual_seed(0)
    x = torch.randn(1, 4, 1, 8, 8)
    text = torch.randn(1, 8, 32)
    with torch.no_grad():
        return pipe.transformer(x, torch.tensor([400.0]), text, return_dict=False)[0]


def test_comfyui_export_round_trips(trained, tmp_path):
    from diffusers import WanPipeline

    cfg, final = trained
    lora = final / LORA_WEIGHTS
    comfy = to_comfyui(lora, tmp_path / "mika_comfyui.safetensors")
    keys = load_file(str(comfy)).keys()
    assert all(k.startswith("diffusion_model.blocks.") for k in keys)
    assert "diffusion_model.blocks.0.self_attn.q.lora_A.weight" in keys
    assert "diffusion_model.blocks.1.ffn.2.lora_B.weight" in keys
    assert "diffusion_model.blocks.0.cross_attn.o.alpha" in keys

    base = WanPipeline.from_pretrained(cfg.model.base)
    plain = _transformer_output(base)
    base.load_lora_weights(str(final), weight_name=LORA_WEIGHTS, adapter_name="ours")
    ours = _transformer_output(base)
    other = WanPipeline.from_pretrained(cfg.model.base)
    other.load_lora_weights(str(comfy), adapter_name="comfy")  # diffusers converts Wan-format keys back
    assert not torch.allclose(plain, ours), "the LoRA should change the model"
    assert torch.allclose(ours, _transformer_output(other), atol=1e-5)


def test_merged_model_is_standalone_and_matches(trained, tmp_path):
    from diffusers import WanPipeline

    cfg, final = trained
    out = merged_model(cfg.model.base, final / LORA_WEIGHTS, tmp_path / "merged", precision="fp32")
    assert (out / "model_index.json").exists() and (out / "character.yaml").exists()
    with_lora = WanPipeline.from_pretrained(cfg.model.base)
    with_lora.load_lora_weights(str(final), weight_name=LORA_WEIGHTS)
    merged = WanPipeline.from_pretrained(out)
    assert torch.allclose(_transformer_output(with_lora), _transformer_output(merged), atol=1e-4)


def test_base_model_is_found_for_checkpoints_too(trained):
    cfg, _ = trained
    checkpoint = cfg.run_dir / "checkpoints" / "step-000010" / LORA_WEIGHTS
    assert base_model_of(checkpoint) == cfg.model.base


def test_low_memory_mode_fuses_lora_and_reloads_on_new_strength(trained, tmp_path, character, monkeypatch):
    from diffusers import WanPipeline

    monkeypatch.setattr(WanPipeline, "enable_model_cpu_offload", lambda self, *a, **k: None)  # needs a GPU
    cfg, final = trained
    generator = VideoGenerator(cfg.model.base, find_lora(final), character, device="cpu", memory="low")
    settings = GenerationSettings(width=32, height=32, num_frames=5, fps=8, steps=2, seed=1, lora_scale=0.7)
    assert generator.generate("she smiles", settings, tmp_path).exists()
    first = generator._pipe
    assert generator._memory_used == "low" and generator._lora_scale == 0.7
    assert not any("lora_" in name for name, _ in first.transformer.named_parameters()), "not fused"
    settings.lora_scale = 1.0
    generator.generate("she smiles", settings, tmp_path)
    assert generator._pipe is not first and generator._lora_scale == 1.0
