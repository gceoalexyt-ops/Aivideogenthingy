"""LoRA fine-tuning of a Wan text-to-video model so it learns her identity.

Flow-matching objective, as used to pre-train Wan: with clean latents x0, noise n and sigma in (0, 1),
the model sees x_t = (1 - sigma) * x0 + sigma * n at timestep 1000 * sigma and learns to predict n - x0.
Only the low-rank adapters train; the base model stays frozen.
"""

from __future__ import annotations

import json
import math
import random
import shutil
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from aivideogen.character import Character
from aivideogen.dataset.files import list_samples
from aivideogen.safety import check_prompt
from aivideogen.train.config import RunConfig
from aivideogen.train.data import BucketBatchSampler, CachedLatents, LatentCache, collate
from aivideogen.wan import (
    DEFAULT_NEGATIVE_PROMPT,
    dtype_kwarg,
    free_memory,
    make_scheduler,
    pad_embeds,
    resolve_device,
    resolve_dtype,
    spatial_multiple,
    store_frozen_linears_in_fp8,
    text_encoding_pipeline,
)

LORA_WEIGHTS = "pytorch_lora_weights.safetensors"
Log = Callable[[str], None]


class Trainer:
    def __init__(self, cfg: RunConfig, log: Log = print):
        self.cfg = cfg
        self.log = log
        self.character = Character.load(cfg.character_file)
        self.device = resolve_device(cfg.device)
        self.dtype = resolve_dtype(cfg.model.precision, self.device)
        self.run_dir = cfg.run_dir
        self.status: dict = {"state": "starting", "step": 0, "steps": cfg.train.steps}

    # ------------------------------------------------------------------ bookkeeping

    def _write_status(self, **updates) -> None:
        self.status.update(updates, updated=time.strftime("%Y-%m-%dT%H:%M:%S"))
        (self.run_dir / "status.json").write_text(json.dumps(self.status, indent=2))

    def _append_log(self, record: dict) -> None:
        with open(self.run_dir / "log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    # ------------------------------------------------------------------ stages

    def _cache(self):
        """Encode the dataset (and prompts used later) with the VAE and text encoder, then free them."""
        from diffusers import AutoencoderKLWan
        from transformers import AutoTokenizer, UMT5EncoderModel

        cfg = self.cfg
        samples = list_samples(cfg.data.dataset_dir)
        if not samples:
            raise FileNotFoundError(
                f"No captioned images or clips in {cfg.data.dataset_dir}. Build the dataset first "
                "(`aivideogen dataset build`) or import your own (`aivideogen dataset import`)."
            )
        missing_tag = [s.media.name for s in samples if self.character.trigger not in s.caption]
        if missing_tag:
            self.log(
                f"warning: {len(missing_tag)} captions lack the trigger "
                f"{self.character.trigger!r}: {missing_tag[:5]}"
            )

        self._write_status(state="caching")
        base = cfg.model.base
        self.log(f"loading VAE and text encoder from {base}")
        # The Wan VAE is small and is meant to run in float32.
        vae = AutoencoderKLWan.from_pretrained(base, subfolder="vae", **dtype_kwarg(torch.float32)).to(
            self.device
        )
        tokenizer = AutoTokenizer.from_pretrained(base, subfolder="tokenizer")
        text_encoder = UMT5EncoderModel.from_pretrained(base, subfolder="text_encoder", dtype=self.dtype)
        text_pipe = text_encoding_pipeline(tokenizer, text_encoder.to(self.device))

        from diffusers import WanTransformer3DModel

        transformer_config = WanTransformer3DModel.load_config(base, subfolder="transformer")
        cache = LatentCache(cfg.data.cache_dir, base, cfg.data.max_sequence_length)
        entries = cache.build(
            samples,
            vae,
            text_pipe,
            self.device,
            resolution=cfg.data.resolution,
            multiple=spatial_multiple(vae, transformer_config),
            video_frames=cfg.data.video_frames,
            video_fps=cfg.data.video_fps,
            log=self.log,
        )
        self.sample_prompts = [check_prompt(self.character.prompt_for(p)) for p in cfg.sample.prompts]
        empty, negative, *sample_embeds = cache.texts(
            ["", DEFAULT_NEGATIVE_PROMPT, *self.sample_prompts], text_pipe, self.device
        )
        self.empty_embeds, self.negative_embeds, self.sample_embeds = empty, negative, sample_embeds

        del text_pipe, text_encoder
        self.vae = vae.to("cpu")  # only needed again to decode preview samples
        free_memory()
        self.log(f"cached {len(entries)} samples in {cfg.data.cache_dir}")
        return entries

    def _load_transformer(self):
        from diffusers import WanTransformer3DModel
        from diffusers.training_utils import cast_training_params
        from peft import LoraConfig

        cfg = self.cfg
        self.log("loading transformer")
        transformer = WanTransformer3DModel.from_pretrained(
            cfg.model.base, subfolder="transformer", **dtype_kwarg(self.dtype)
        )
        transformer.requires_grad_(False)
        if cfg.train.gradient_checkpointing:
            transformer.enable_gradient_checkpointing()
        transformer.add_adapter(
            LoraConfig(
                r=cfg.lora.rank,
                lora_alpha=cfg.lora.alpha,
                lora_dropout=cfg.lora.dropout,
                init_lora_weights=True,
                target_modules=cfg.lora.target_modules,
            )
        )
        if cfg.model.base_weights == "fp8":
            converted = store_frozen_linears_in_fp8(transformer)
            self.log(f"stored {converted} frozen linear layers in fp8")
        transformer.to(self.device)  # device only: a dtype cast here would undo fp8 storage
        cast_training_params(transformer, dtype=torch.float32)  # adapters train in full precision
        trainable = sum(p.numel() for p in transformer.parameters() if p.requires_grad)
        self.log(f"LoRA rank {cfg.lora.rank}: {trainable / 1e6:.2f}M trainable parameters")
        return transformer

    def _optimizer(self, params):
        cfg = self.cfg.train
        if cfg.optimizer == "adamw8bit":
            import bitsandbytes as bnb

            return bnb.optim.AdamW8bit(params, lr=cfg.learning_rate, weight_decay=cfg.weight_decay)
        return torch.optim.AdamW(params, lr=cfg.learning_rate, weight_decay=cfg.weight_decay)

    def _sigmas(self, batch_size: int) -> torch.Tensor:
        cfg = self.cfg.train
        if cfg.timestep_sampling == "logit_normal":
            u = torch.sigmoid(torch.randn(batch_size) * cfg.logit_std + cfg.logit_mean)
        else:
            u = torch.rand(batch_size)
        shift = cfg.timestep_shift
        sigmas = shift * u / (1 + (shift - 1) * u)
        return sigmas.clamp(1e-3, 1.0)

    def _loss(self, transformer, latents: torch.Tensor, embeds: torch.Tensor) -> torch.Tensor:
        x0 = latents.to(self.device, torch.float32)
        noise = torch.randn_like(x0)
        sigmas = self._sigmas(x0.shape[0]).to(self.device)
        s = sigmas.view(-1, 1, 1, 1, 1)
        noisy = (1 - s) * x0 + s * noise
        autocast = self.device.type == "cuda" and self.dtype != torch.float32
        with torch.autocast(self.device.type, dtype=self.dtype, enabled=autocast):
            pred = transformer(
                hidden_states=noisy.to(self.dtype),
                timestep=sigmas * 1000,
                encoder_hidden_states=embeds.to(self.device, self.dtype),
                return_dict=False,
            )[0]
        return F.mse_loss(pred.float(), noise - x0)

    @torch.no_grad()
    def _render_samples(self, transformer, step: int) -> list[Path]:
        from diffusers import WanPipeline
        from diffusers.utils import export_to_video

        cfg = self.cfg.sample
        out_dir = self.run_dir / "samples"
        out_dir.mkdir(parents=True, exist_ok=True)
        self._write_status(state="sampling")
        transformer.eval()
        self.vae.to(self.device)
        pipe = WanPipeline(
            tokenizer=None,
            text_encoder=None,
            vae=self.vae,
            scheduler=make_scheduler(self.cfg.model.base, cfg.flow_shift),
            transformer=transformer,
        )
        pipe.set_progress_bar_config(disable=True)
        max_len = self.cfg.data.max_sequence_length
        negative = pad_embeds([self.negative_embeds], max_len).to(self.device, self.dtype)
        paths = []
        for i, embeds in enumerate(self.sample_embeds):
            frames = pipe(
                prompt_embeds=pad_embeds([embeds], max_len).to(self.device, self.dtype),
                negative_prompt_embeds=negative,
                height=cfg.height,
                width=cfg.width,
                num_frames=cfg.num_frames,
                num_inference_steps=cfg.steps,
                guidance_scale=cfg.guidance,
                generator=torch.Generator("cpu").manual_seed(cfg.seed),  # same noise every time: comparable
                output_type="np",
            ).frames[0]
            path = out_dir / f"step{step:06d}_{i}.mp4"
            export_to_video(list(frames), str(path), fps=cfg.fps)
            paths.append(path)
        self.vae.to("cpu")
        free_memory()
        transformer.train()
        self.log(f"samples: {', '.join(p.name for p in paths)}")
        return paths

    def _save_lora(self, transformer, directory: Path, dtype: torch.dtype = torch.float32) -> Path:
        from diffusers import WanPipeline
        from diffusers.training_utils import _collate_lora_metadata
        from peft.utils import get_peft_model_state_dict

        directory.mkdir(parents=True, exist_ok=True)
        state = {k: v.detach().to("cpu", dtype) for k, v in get_peft_model_state_dict(transformer).items()}
        WanPipeline.save_lora_weights(
            directory,
            transformer_lora_layers=state,
            weight_name=LORA_WEIGHTS,
            **_collate_lora_metadata({"transformer": transformer}),
        )
        return directory / LORA_WEIGHTS

    def _save_checkpoint(self, transformer, optimizer, lr_scheduler, step: int) -> Path:
        directory = self.run_dir / "checkpoints" / f"step-{step:06d}"
        self._save_lora(transformer, directory)  # full precision so resuming is exact
        state = {
            "step": step,
            "optimizer": optimizer.state_dict(),
            "lr_scheduler": lr_scheduler.state_dict(),
            "rng": torch.get_rng_state(),
            "python_rng": random.getstate(),
        }
        torch.save(state, directory / "training_state.pt")
        checkpoints = sorted((self.run_dir / "checkpoints").glob("step-*"))
        for old in checkpoints[: -self.cfg.keep_checkpoints] if self.cfg.keep_checkpoints > 0 else []:
            shutil.rmtree(old)
        return directory

    def _resume(self, transformer, optimizer, lr_scheduler) -> int:
        from peft.utils import set_peft_model_state_dict
        from safetensors.torch import load_file

        checkpoints = sorted((self.run_dir / "checkpoints").glob("step-*"))
        if not checkpoints:
            self.log("no checkpoint to resume from; starting fresh")
            return 0
        latest = checkpoints[-1]
        lora = load_file(str(latest / LORA_WEIGHTS))
        lora = {k.removeprefix("transformer."): v for k, v in lora.items()}
        set_peft_model_state_dict(transformer, lora)
        state = torch.load(latest / "training_state.pt", map_location="cpu", weights_only=False)
        optimizer.load_state_dict(state["optimizer"])
        lr_scheduler.load_state_dict(state["lr_scheduler"])
        torch.set_rng_state(state["rng"])
        random.setstate(state["python_rng"])
        self.log(f"resumed from {latest.name}")
        return int(state["step"])

    def _write_model_card(self, directory: Path) -> None:
        c, cfg = self.character, self.cfg
        (directory / "README.md").write_text(
            f"# {c.name}: LoRA for {cfg.model.base}\n\n"
            f"A fine-tune that teaches the base model one fictional adult character, {c.name}.\n\n"
            f"- Trigger: `{c.tag}` (or write her name, `aivideogen generate` swaps it in)\n"
            f"- Rank {cfg.lora.rank}, alpha {cfg.lora.alpha}, "
            f"{cfg.train.steps} steps at {cfg.data.resolution}px\n\n"
            "```bash\n"
            f'aivideogen generate "{c.first_name} walks through a rainy neon-lit street at night" '
            f"--lora {directory}\n"
            "```\n"
        )

    # ------------------------------------------------------------------ main loop

    def run(self, resume: bool = False) -> Path:
        from diffusers.optimization import get_scheduler

        cfg = self.cfg
        self.run_dir.mkdir(parents=True, exist_ok=True)
        cfg.dump(self.run_dir / "config.yaml")
        shutil.copyfile(cfg.character_file, self.run_dir / "character.yaml")
        torch.manual_seed(cfg.train.seed)
        random.seed(cfg.train.seed)
        self.log(f"device {self.device}, precision {self.dtype}, run dir {self.run_dir}")

        try:
            entries = self._cache()
            transformer = self._load_transformer()
            params = [p for p in transformer.parameters() if p.requires_grad]
            optimizer = self._optimizer(params)
            lr_scheduler = get_scheduler(
                cfg.train.lr_scheduler,
                optimizer,
                num_warmup_steps=cfg.train.warmup_steps,
                num_training_steps=cfg.train.steps,
            )
            start = self._resume(transformer, optimizer, lr_scheduler) if resume else 0

            dataset = CachedLatents(entries, cfg.data.repeats)
            loader = DataLoader(
                dataset,
                batch_sampler=BucketBatchSampler(
                    dataset.shapes, cfg.train.batch_size, seed=cfg.train.seed + start
                ),
                collate_fn=partial(collate, max_sequence_length=cfg.data.max_sequence_length),
            )
            batches = iter(loader)
            empty = pad_embeds([self.empty_embeds], cfg.data.max_sequence_length)[0]

            transformer.train()
            self.log(f"training {cfg.train.steps - start} steps on {len(entries)} samples")
            smoothed, started, last_sample = None, time.time(), None
            for step in range(start + 1, cfg.train.steps + 1):
                total = 0.0
                for _ in range(cfg.train.grad_accum):
                    latents, embeds = next(batches)
                    drop = torch.rand(embeds.shape[0]) < cfg.data.caption_dropout
                    embeds[drop] = empty.to(embeds.dtype)
                    loss = self._loss(transformer, latents, embeds)
                    (loss / cfg.train.grad_accum).backward()
                    total += loss.item() / cfg.train.grad_accum
                if not math.isfinite(total):
                    raise FloatingPointError(f"loss became {total} at step {step}; lower the learning rate")
                grad_norm = torch.nn.utils.clip_grad_norm_(params, cfg.train.max_grad_norm)
                optimizer.step()
                lr_scheduler.step()
                optimizer.zero_grad(set_to_none=True)

                smoothed = total if smoothed is None else 0.95 * smoothed + 0.05 * total
                per_step = (time.time() - started) / (step - start)
                record = {
                    "step": step,
                    "loss": round(total, 5),
                    "loss_avg": round(smoothed, 5),
                    "lr": lr_scheduler.get_last_lr()[0],
                    "grad_norm": round(float(grad_norm), 4),
                    "sec_per_step": round(per_step, 3),
                }
                self._append_log(record)
                if step % 10 == 0 or step == start + 1 or step == cfg.train.steps:
                    eta = per_step * (cfg.train.steps - step)
                    self.log(
                        f"step {step}/{cfg.train.steps}  loss {total:.4f} (avg {smoothed:.4f})  "
                        f"{per_step:.2f}s/step  eta {eta / 60:.1f} min"
                    )
                self._write_status(
                    state="training",
                    step=step,
                    loss=smoothed,
                    eta_sec=round(per_step * (cfg.train.steps - step)),
                )
                last_step = step == cfg.train.steps
                if (cfg.save_every and step % cfg.save_every == 0) or last_step:
                    # Checkpoint the last step too, so `--resume` with more steps extends a finished run.
                    path = self._save_checkpoint(transformer, optimizer, lr_scheduler, step)
                    self._write_status(last_checkpoint=str(path))
                if cfg.sample.every and step % cfg.sample.every == 0 and not last_step:
                    last_sample = self._render_samples(transformer, step)
                    self._write_status(last_samples=[str(p) for p in last_sample])

            final = self.run_dir / "final"
            weights = self._save_lora(transformer, final, dtype=self.dtype)  # bf16 on GPU: half the file size
            shutil.copyfile(cfg.character_file, final / "character.yaml")
            cfg.dump(final / "config.yaml")
            self._write_model_card(final)
            self.log(f"saved her LoRA: {weights}")
            if cfg.sample.every:
                last_sample = self._render_samples(transformer, cfg.train.steps)
                self._write_status(last_samples=[str(p) for p in last_sample])
            self._write_status(state="done", final=str(weights))
            return final
        except BaseException as e:
            self._write_status(state="failed", error=f"{type(e).__name__}: {e}")
            raise


def train(cfg: RunConfig, resume: bool = False, log: Log = print) -> Path:
    return Trainer(cfg, log).run(resume=resume)
