"""Command line: build her dataset, train her model, generate videos of her."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aivideogen.character import DEFAULT_CHARACTER_FILE, Character
from aivideogen.dataset.files import DatasetPaths

DEFAULT_DATASET = Path("data/dataset")


def _character(args) -> Character:
    return Character.load(args.character)


def cmd_character(args) -> None:
    from aivideogen.dataset.shots import anchor_prompt

    c = _character(args)
    print(f"{c.name}, {c.age} — trigger tag: {c.tag!r}\n")
    print("Her look (used to synthesize the dataset):\n  " + c.looks() + "\n")
    if c.reference_image:
        found = "found" if c.reference_image.exists() else "MISSING: put her photo there"
        print(f"Her face comes from the profile photo {c.reference_image} ({found}).\n")
    else:
        print("Anchor portrait prompt:\n  " + anchor_prompt(c) + "\n")
    print("Example: 'Mika dances in the rain' becomes:\n  " + c.prompt_for("Mika dances in the rain"))


def cmd_dataset_anchor(args) -> None:
    from aivideogen.dataset.backends import get_backend
    from aivideogen.dataset.build import install_reference, make_anchor_candidates

    paths = DatasetPaths(args.dataset)
    character = _character(args)
    if character.reference_image and not args.generate:
        print(f"anchor set from her profile photo: {install_reference(character, paths)}")
        print("(pass --generate to draw candidate portraits from her text description instead)")
        return
    backend = get_backend(args.backend, args.model)
    try:
        made = make_anchor_candidates(character, backend, paths, count=args.count, seed=args.seed)
    finally:
        backend.close()
    print(f"\n{len(made)} candidates in {paths.anchors}. Using {paths.anchor} as her reference;")
    print("look through them and run `aivideogen dataset pick N` to choose a different one.")


def cmd_dataset_pick(args) -> None:
    from aivideogen.dataset.build import pick_anchor

    print(f"anchor set: {pick_anchor(DatasetPaths(args.dataset), args.choice, _character(args))}")


def cmd_dataset_build(args) -> None:
    from aivideogen.dataset.backends import get_backend
    from aivideogen.dataset.build import build_images

    paths = DatasetPaths(args.dataset)
    backend = get_backend(args.backend, args.model)
    try:
        made, failures = build_images(
            _character(args), backend, paths, count=args.count, seed=args.seed, overwrite=args.overwrite
        )
    finally:
        backend.close()
    print(
        f"\n{made} new images in {paths.images}"
        + (f", {len(failures)} failed (re-run to retry)" if failures else "")
    )
    print("Delete any image where she doesn't look like herself, then run `aivideogen dataset check`.")


def cmd_dataset_import(args) -> None:
    from aivideogen.dataset.files import import_media

    count = import_media(args.source, DatasetPaths(args.dataset), _character(args))
    print(f"imported {count} files into {DatasetPaths(args.dataset).images}")


def cmd_dataset_check(args) -> None:
    from aivideogen.dataset.files import check_dataset

    report = check_dataset(DatasetPaths(args.dataset).images, _character(args))
    print(report)
    if not report.ok:
        sys.exit(1)


def _overrides(pairs: list[str]) -> dict:
    import yaml

    out = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"--set expects key=value, got {pair!r}")
        out[key] = yaml.safe_load(value)
    return out


def cmd_train(args) -> None:
    from aivideogen.train.config import RunConfig
    from aivideogen.train.trainer import train

    cfg = RunConfig.load(args.config, _overrides(args.set))
    final = train(cfg, resume=args.resume)
    print(f'\nDone. Her model: {final}\nTry: aivideogen generate "she waves at the camera" --lora {final}')


def cmd_generate(args) -> None:
    from aivideogen.generate import GenerationSettings, VideoGenerator, base_model_of, find_lora

    lora = find_lora(args.lora)
    if lora is None and not args.no_lora:
        raise SystemExit("No trained LoRA found under runs/. Train one first, pass --lora, or use --no-lora.")
    if args.no_lora:
        lora = None
    base = args.base or (base_model_of(lora) if lora else None) or "Wan-AI/Wan2.1-T2V-14B-Diffusers"
    settings = GenerationSettings.for_model(
        base,
        width=args.width,
        height=args.height,
        num_frames=args.frames,
        fps=args.fps,
        steps=args.steps,
        guidance=args.guidance,
        flow_shift=args.flow_shift,
        seed=args.seed,
        lora_scale=args.lora_scale,
    )
    generator = VideoGenerator(
        base, lora, _character(args), device=args.device, precision=args.precision, memory=args.memory
    )
    print(f"prompt: {generator.build_prompt(args.prompt)}")
    for i in range(args.count):
        if i and settings.seed is not None:
            settings.seed += 1
        print(f"saved {generator.generate(args.prompt, settings, Path(args.out))}")


def cmd_export(args) -> None:
    from aivideogen.export import merged_model, to_comfyui
    from aivideogen.generate import base_model_of, find_lora

    lora = find_lora(args.lora)
    if lora is None:
        raise SystemExit("No trained LoRA found; pass --lora.")
    if args.format == "comfyui":
        out = Path(args.out or lora.parent / f"{lora.parent.parent.name}_comfyui.safetensors")
        print(f"wrote {to_comfyui(lora, out)}")
    else:
        base = args.base or base_model_of(lora)
        if not base:
            raise SystemExit("Pass --base: couldn't tell which base model this LoRA was trained on.")
        out = Path(args.out or Path("models") / lora.parent.parent.name)
        print(f"wrote {merged_model(base, lora, out, scale=args.scale)}")


def cmd_ui(args) -> None:
    from aivideogen.webui import launch

    launch(character_file=args.character, host=args.host, port=args.port, share=args.share)


def cmd_demo(args) -> None:
    """Every stage, end to end, on a tiny model and cartoon dataset. Runs on CPU in about a minute."""
    from aivideogen.dataset.backends import MockBackend
    from aivideogen.dataset.build import build_images, make_anchor_candidates
    from aivideogen.dataset.shots import plan_shots
    from aivideogen.generate import GenerationSettings, VideoGenerator
    from aivideogen.tiny import build_tiny_wan
    from aivideogen.train.config import RunConfig
    from aivideogen.train.trainer import train
    from aivideogen.wan import DEFAULT_NEGATIVE_PROMPT

    character = _character(args)
    cfg = RunConfig.load(args.config, _overrides(args.set))
    root = Path(cfg.model.base).parent
    print("1/4  building a tiny randomly-initialized Wan model (stand-in for the real 14B one)")
    if not Path(cfg.model.base, "model_index.json").exists():
        vocab = [s.caption(character) for s in plan_shots(character, 60)] + cfg.sample.prompts
        build_tiny_wan(Path(cfg.model.base), [*vocab, character.prompt_for(""), DEFAULT_NEGATIVE_PROMPT])
    print("2/4  synthesizing a cartoon stand-in dataset of her")
    paths = DatasetPaths(cfg.data.dataset_dir.parent)
    backend = MockBackend()
    if not paths.anchor.exists():
        make_anchor_candidates(character, backend, paths, count=2, log=lambda m: None)
    build_images(character, backend, paths, count=args.images, log=lambda m: None)
    print("3/4  training her LoRA")
    final = train(cfg)
    print("4/4  generating a video with her LoRA")
    generator = VideoGenerator(
        cfg.model.base,
        final / "pytorch_lora_weights.safetensors",
        character,
        device=cfg.device,
        precision=cfg.model.precision,
    )
    settings = GenerationSettings(
        width=cfg.sample.width,
        height=cfg.sample.height,
        num_frames=cfg.sample.num_frames,
        fps=cfg.sample.fps,
        steps=cfg.sample.steps,
        seed=0,
    )
    video = generator.generate("Mika waves at the camera in a cozy cafe", settings, root / "outputs")
    print(
        f"\nDemo complete. Pipeline verified end to end:\n  dataset  {paths.images}\n  LoRA     {final}\n"
        f"  video    {video}\n"
        "(The tiny model makes abstract noise; real results need the real base model on a GPU.)"
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aivideogen", description=__doc__)
    p.add_argument("--character", type=Path, default=DEFAULT_CHARACTER_FILE, help="character definition YAML")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("character", help="show her description and how prompts get rewritten").set_defaults(
        fn=cmd_character
    )

    ds = sub.add_parser("dataset", help="build, import and check her training dataset")
    ds_sub = ds.add_subparsers(dest="dataset_command", required=True)

    def with_dataset(parser):
        parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
        return parser

    def with_backend(parser):
        parser.add_argument(
            "--backend",
            choices=["qwen", "replicate", "mock"],
            default="qwen",
            help="qwen: open models on your GPU; replicate: hosted Nano Banana; mock: test cartoon",
        )
        parser.add_argument("--model", help="override the backend's image model")
        parser.add_argument("--seed", type=int, default=0)
        return parser

    a = with_backend(
        with_dataset(ds_sub.add_parser("anchor", help="set her identity reference (profile photo or drawn)"))
    )
    a.add_argument("--count", type=int, default=4)
    a.add_argument(
        "--generate", action="store_true", help="draw candidates from text even if a profile photo is set"
    )
    a.set_defaults(fn=cmd_dataset_anchor)

    pk = with_dataset(ds_sub.add_parser("pick", help="choose which candidate is her reference"))
    pk.add_argument("choice", help="candidate number (e.g. 2) or a path to any image of her")
    pk.set_defaults(fn=cmd_dataset_pick)

    b = with_backend(
        with_dataset(ds_sub.add_parser("build", help="generate her training images from the anchor"))
    )
    b.add_argument("--count", type=int, default=40)
    b.add_argument("--overwrite", action="store_true", help="regenerate images that already exist")
    b.set_defaults(fn=cmd_dataset_build)

    im = with_dataset(
        ds_sub.add_parser("import", help="add your own images/clips of her (with optional .txt captions)")
    )
    im.add_argument("source", type=Path)
    im.set_defaults(fn=cmd_dataset_import)

    with_dataset(ds_sub.add_parser("check", help="validate captions, sizes and duplicates")).set_defaults(
        fn=cmd_dataset_check
    )

    t = sub.add_parser("train", help="fine-tune the video model on her dataset")
    t.add_argument("--config", type=Path, default=Path("configs/wan21_14b.yaml"))
    t.add_argument("--resume", action="store_true", help="continue from the latest checkpoint")
    t.add_argument(
        "--set", action="append", default=[], metavar="KEY=VALUE", help="override, e.g. train.steps=3000"
    )
    t.set_defaults(fn=cmd_train)

    g = sub.add_parser("generate", help="make a video of her from a text prompt")
    g.add_argument("prompt", help='what she does, e.g. "Mika walks through a rainy street at night"')
    g.add_argument("--lora", type=Path, help="LoRA file or run directory (default: newest run in runs/)")
    g.add_argument("--no-lora", action="store_true", help="use the plain base model (for comparison)")
    g.add_argument("--base", help="base model (default: the one the LoRA was trained on)")
    g.add_argument("--width", type=int)
    g.add_argument("--height", type=int)
    g.add_argument("--frames", type=int, help="number of frames (4k+1, e.g. 81 = 5s at 16fps)")
    g.add_argument("--fps", type=int)
    g.add_argument("--steps", type=int)
    g.add_argument("--guidance", type=float)
    g.add_argument("--flow-shift", type=float)
    g.add_argument("--lora-scale", type=float, default=1.0, help="how strongly to apply her LoRA")
    g.add_argument("--seed", type=int)
    g.add_argument("--count", type=int, default=1, help="number of videos")
    g.add_argument("--out", default="outputs")
    g.add_argument("--device", default="auto")
    g.add_argument("--precision", default="bf16", choices=["bf16", "fp16", "fp32"])
    g.add_argument(
        "--memory",
        default="auto",
        choices=["auto", "gpu", "offload", "low"],
        help="low = fp8 weights + CPU offload, for 24 GB cards with the 14B model",
    )
    g.set_defaults(fn=cmd_generate)

    e = sub.add_parser("export", help="export her LoRA for ComfyUI, or as a standalone merged model")
    e.add_argument("format", choices=["comfyui", "merged"])
    e.add_argument("--lora", type=Path)
    e.add_argument("--base")
    e.add_argument("--scale", type=float, default=1.0)
    e.add_argument("--out")
    e.set_defaults(fn=cmd_export)

    u = sub.add_parser("ui", help="web interface for generating, reviewing the dataset and training")
    u.add_argument("--host", default="127.0.0.1")
    u.add_argument("--port", type=int, default=7860)
    u.add_argument("--share", action="store_true", help="public gradio.live link (useful on cloud GPUs)")
    u.set_defaults(fn=cmd_ui)

    d = sub.add_parser("demo", help="verify the whole pipeline on CPU with a tiny model")
    d.add_argument("--config", type=Path, default=Path("configs/tiny_cpu.yaml"))
    d.add_argument("--images", type=int, default=12)
    d.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    d.set_defaults(fn=cmd_demo)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
