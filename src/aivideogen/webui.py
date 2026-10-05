"""Web interface (``aivideogen ui``): generate videos of her, curate her dataset, run and watch training."""

# No `from __future__ import annotations` here: Gradio reads the `gr.SelectData` annotation at runtime.

import json
import subprocess
import sys
import threading
from pathlib import Path

from aivideogen.character import Character
from aivideogen.dataset.files import DatasetPaths, check_dataset, list_samples
from aivideogen.train.config import RunConfig
from aivideogen.train.trainer import LORA_WEIGHTS


class App:
    """UI state and actions, kept free of Gradio so they're easy to test."""

    def __init__(
        self,
        character_file: Path = Path("character.yaml"),
        dataset: Path = Path("data/dataset"),
        runs_dir: Path = Path("runs"),
        configs_dir: Path = Path("configs"),
        outputs: Path = Path("outputs"),
    ):
        self.character_file = character_file
        self.character = Character.load(character_file)
        self.paths = DatasetPaths(dataset)
        self.runs_dir, self.configs_dir, self.outputs = runs_dir, configs_dir, outputs
        self._generator = None
        self._generator_key: tuple | None = None
        self._lock = threading.Lock()
        self._training: subprocess.Popen | None = None
        self._training_config: RunConfig | None = None

    # ---------------------------------------------------------------- generate

    def loras(self) -> list[str]:
        finals = sorted(self.runs_dir.glob(f"*/final/{LORA_WEIGHTS}"), key=lambda p: -p.stat().st_mtime)
        checkpoints = sorted(self.runs_dir.glob(f"*/checkpoints/*/{LORA_WEIGHTS}"), reverse=True)
        return [str(p) for p in [*finals, *checkpoints]]

    def generate(
        self,
        scene: str,
        lora: str | None,
        width: int,
        height: int,
        frames: int,
        fps: int,
        steps: int,
        guidance: float,
        flow_shift: float,
        lora_scale: float,
        seed: int,
    ) -> tuple[str, str]:
        from aivideogen.generate import GenerationSettings, VideoGenerator, base_model_of

        if not scene.strip():
            raise ValueError("Describe what she should do.")
        if not lora:
            raise ValueError("No trained LoRA yet: train her model first (Train tab).")
        lora_path = Path(lora)
        base = base_model_of(lora_path)
        if base is None:
            raise ValueError(
                f"Can't tell which base model {lora} was trained on (no config.yaml next to it)."
            )
        with self._lock:  # one GPU, one generation at a time
            key = (base, lora_path)
            if self._generator_key != key:
                self._generator = None
                self._generator = VideoGenerator(base, lora_path, self.character)
                self._generator_key = key
            settings = GenerationSettings(
                width=int(width),
                height=int(height),
                num_frames=int(frames),
                fps=int(fps),
                steps=int(steps),
                guidance=float(guidance),
                flow_shift=float(flow_shift),
                lora_scale=float(lora_scale),
                seed=None if seed is None or int(seed) < 0 else int(seed),
            )
            video = self._generator.generate(scene, settings, self.outputs)
        info = json.loads(video.with_suffix(".json").read_text())
        return str(video), f"**Prompt:** {info['prompt']}  \n**Seed:** {info['seed']} · {info['seconds']} s"

    def recent_videos(self, limit: int = 12) -> list[str]:
        return [str(p) for p in sorted(self.outputs.glob("*.mp4"), key=lambda p: -p.stat().st_mtime)[:limit]]

    # ---------------------------------------------------------------- dataset

    def dataset_items(self) -> list[tuple[str, str]]:
        return [(str(s.media), s.caption) for s in list_samples(self.paths.images) if not s.is_video]

    def dataset_report(self) -> str:
        report = check_dataset(self.paths.images, self.character)
        return "```\n" + str(report) + "\n```"

    def save_caption(self, media: str, caption: str) -> str:
        path = self._dataset_file(media)
        path.with_suffix(".txt").write_text(caption.strip() + "\n", encoding="utf-8")
        return f"Saved caption for {path.name}"

    def delete_sample(self, media: str) -> str:
        path = self._dataset_file(media)
        path.unlink()
        path.with_suffix(".txt").unlink(missing_ok=True)
        return f"Deleted {path.name}"

    def _dataset_file(self, media: str) -> Path:
        path = Path(media).resolve()
        if path.parent != self.paths.images.resolve() or not path.exists():
            raise ValueError("Pick an image from the dataset first.")
        return path

    # ---------------------------------------------------------------- training

    def configs(self) -> list[str]:
        return sorted(str(p) for p in self.configs_dir.glob("*.yaml") if p.name != "tiny_cpu.yaml")

    def start_training(self, config: str, resume: bool) -> str:
        if self._training and self._training.poll() is None:
            return "Training is already running."
        cfg = RunConfig.load(config)
        cfg.run_dir.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            "-m",
            "aivideogen",
            "--character",
            str(self.character_file),
            "train",
            "--config",
            config,
            *(["--resume"] if resume else []),
        ]
        log = open(cfg.run_dir / "train_output.log", "a", encoding="utf-8")  # noqa: SIM115 - owned by the child
        self._training = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        self._training_config = cfg
        return f"Started training `{cfg.name}` (pid {self._training.pid})."

    def stop_training(self) -> str:
        if not self._training or self._training.poll() is not None:
            return "Nothing is running."
        self._training.terminate()
        return "Stopping training. Resume later with the resume box ticked."

    def training_status(self, config: str | None) -> tuple[str, str, str | None]:
        cfg = self._training_config or (RunConfig.load(config) if config else None)
        if cfg is None:
            return "No run selected.", "", None
        status_file = cfg.run_dir / "status.json"
        status = json.loads(status_file.read_text()) if status_file.exists() else {}
        running = self._training is not None and self._training.poll() is None
        lines = [
            f"**Run:** `{cfg.name}` · **state:** {status.get('state', 'not started')}"
            + (" (process running)" if running else "")
        ]
        if "step" in status and status.get("state") in ("training", "sampling", "done"):
            lines.append(f"**Step** {status['step']}/{status['steps']}")
            if status.get("loss") is not None:
                lines.append(
                    f"**Loss** {status['loss']:.4f} · **ETA** {status.get('eta_sec', 0) / 60:.0f} min"
                )
        if status.get("error"):
            lines.append(f"**Error:** {status['error']}")
        log_file = cfg.run_dir / "train_output.log"
        tail = "\n".join(log_file.read_text(errors="replace").splitlines()[-25:]) if log_file.exists() else ""
        samples = status.get("last_samples") or []
        return "  \n".join(lines), tail, samples[0] if samples else None


def build(app: App):
    import gradio as gr

    c = app.character
    with gr.Blocks(title=f"{c.name} — video model") as ui:
        gr.Markdown(
            f"# {c.name}\nHer own fine-tuned video model. Trigger tag: `{c.tag}`. "
            f"Write her name or *she* in prompts and she'll be in the video."
        )
        with gr.Tab("Generate"):
            with gr.Row():
                with gr.Column(scale=1):
                    scene = gr.Textbox(
                        label="What does she do?",
                        lines=3,
                        placeholder=f"{c.first_name} walks through a rainy neon-lit street at night",
                    )
                    loras = app.loras()
                    lora = gr.Dropdown(loras, value=loras[0] if loras else None, label="Her model (LoRA)")
                    refresh = gr.Button("Refresh model list", size="sm")
                    with gr.Accordion("Settings", open=False):
                        width = gr.Slider(256, 1280, 832, step=16, label="Width")
                        height = gr.Slider(256, 1280, 480, step=16, label="Height")
                        frames = gr.Slider(1, 121, 81, step=4, label="Frames (81 = 5 s at 16 fps)")
                        fps = gr.Slider(8, 30, 16, step=1, label="FPS")
                        steps = gr.Slider(4, 60, 30, step=1, label="Steps")
                        guidance = gr.Slider(1, 10, 5, step=0.5, label="Guidance")
                        flow_shift = gr.Slider(1, 8, 3, step=0.5, label="Flow shift (3 for 480p, 5 for 720p)")
                        lora_scale = gr.Slider(0, 1.5, 1, step=0.05, label="Likeness strength (LoRA scale)")
                        seed = gr.Number(-1, label="Seed (-1 = random)", precision=0)
                    go = gr.Button("Generate video", variant="primary")
                with gr.Column(scale=1):
                    video = gr.Video(label="Result", autoplay=True)
                    info = gr.Markdown()
            go.click(
                app.generate,
                [scene, lora, width, height, frames, fps, steps, guidance, flow_shift, lora_scale, seed],
                [video, info],
            )
            refresh.click(lambda: gr.Dropdown(choices=app.loras()), None, lora)

        with gr.Tab("Dataset"):
            gr.Markdown(
                f"Her training images. Delete any where she doesn't look like herself; captions should "
                f"start with `{c.tag}` and describe outfit, pose, place and light, never her face."
            )
            report = gr.Markdown(app.dataset_report())
            gallery = gr.Gallery(app.dataset_items(), columns=6, height=520, label="Dataset")
            selected = gr.Textbox(visible=False)
            caption = gr.Textbox(label="Caption", lines=2)
            with gr.Row():
                save = gr.Button("Save caption")
                delete = gr.Button("Delete image", variant="stop")
                reload = gr.Button("Reload")
            message = gr.Markdown()

            def on_select(evt: gr.SelectData):
                items = app.dataset_items()
                media, text = items[evt.index]
                return media, text

            def after_change(msg):
                return msg, app.dataset_items(), app.dataset_report()

            gallery.select(on_select, None, [selected, caption])
            save.click(
                lambda m, t: after_change(app.save_caption(m, t)),
                [selected, caption],
                [message, gallery, report],
            )
            delete.click(lambda m: after_change(app.delete_sample(m)), [selected], [message, gallery, report])
            reload.click(lambda: after_change(""), None, [message, gallery, report])

        with gr.Tab("Train"):
            configs = app.configs()
            config = gr.Dropdown(
                configs, value=configs[0] if configs else None, label="Preset (see configs/)"
            )
            resume = gr.Checkbox(label="Resume from the latest checkpoint")
            with gr.Row():
                start = gr.Button("Start training", variant="primary")
                stop = gr.Button("Stop", variant="stop")
            started = gr.Markdown()
            status = gr.Markdown()
            sample = gr.Video(label="Latest preview sample")
            log = gr.Textbox(label="Output", lines=12, max_lines=12)
            start.click(app.start_training, [config, resume], started)
            stop.click(app.stop_training, None, started)
            gr.Timer(5).tick(app.training_status, [config], [status, log, sample])
    return ui


def launch(
    character_file: Path = Path("character.yaml"),
    host: str = "127.0.0.1",
    port: int = 7860,
    share: bool = False,
    **paths,
) -> None:
    app = App(character_file, **paths)
    build(app).queue().launch(server_name=host, server_port=port, share=share)
