# Aivideogenthingy: her own video model

A video generator with one star. **Mika Sorensen**, a fictional 23-year-old Eurasian woman (half Japanese,
half Danish), is trained into the weights of an open-source video model (Wan 2.x). Every video it generates
is of her: write *"Mika walks through a rainy neon-lit street at night"* and you get that clip, with her face.

```
character.yaml ──► her dataset ──────► fine-tune (LoRA) ──────► generate
 who she is        ~40 consistent       Wan 2.x learns the       "Mika ..." → mp4
                   photos of her        token "mksrn woman"
```

1. **Anchor portrait.** An image model draws her from the description in `character.yaml`. You pick the best
   of a few candidates; that image defines her face.
2. **Dataset.** An identity-preserving image model redraws her in ~40 varied shots: angles, distances,
   expressions, outfits, places and light. Captions name the trigger tag `mksrn woman` plus everything that should
   stay controllable, and never her face, so the model binds her face to the tag.
3. **Training.** A LoRA fine-tune of Wan (diffusers + PEFT, flow-matching objective). The result,
   `runs/<name>/final/pytorch_lora_weights.safetensors`, is her model: weights you own.
4. **Generation.** Base model + her LoRA. Mentions of "Mika" are rewritten to the trigger tag automatically.

## Meet her

Everything about her lives in [`character.yaml`](character.yaml): name, trigger word, age, heritage, face,
eyes, skin, hair, build, a beauty mark under her left eye, and a signature outfit. Edit it to change her,
but changing her look after training means rebuilding the dataset and retraining.

`aivideogen character` prints her full description and shows how prompts get rewritten.

## Try the pipeline on any machine (no GPU)

```bash
pip install -e '.[ui,dev]'
aivideogen demo
```

This runs every stage on a tiny, randomly-initialized Wan model and a cartoon stand-in dataset: anchor,
dataset, caching, training, saving her LoRA, reloading it, and rendering an mp4. It takes about a minute
on a CPU. The video is abstract noise; it proves the plumbing works before you rent a GPU.

## Train her real model

You need an NVIDIA GPU, your own or rented (see [cloud GPUs](#cloud-gpus)). Pick a preset:

| Preset | Base model | GPU memory | Notes |
| --- | --- | --- | --- |
| `configs/wan21_14b.yaml` | Wan 2.1 T2V 14B | 48 GB+ (A6000, L40S, A100, H100) | Best likeness |
| `configs/wan21_14b_24gb.yaml` | Wan 2.1 T2V 14B, fp8 base weights | 24 GB (RTX 3090/4090/5090) | Near-best; generate with `--memory low` |
| `configs/wan22_5b.yaml` | Wan 2.2 TI2V 5B | 24 GB | 720p at 24 fps |
| `configs/wan21_1.3b.yaml` | Wan 2.1 T2V 1.3B | 16 GB | Fast, weaker likeness; good first try |

Install PyTorch with CUDA for your machine, then:

```bash
pip install -e '.[ui]'

# 1. Her anchor portrait: draws 4 candidates into data/dataset/anchors/
aivideogen dataset anchor --backend qwen     # open Qwen-Image models on your GPU (~48 GB VRAM)
aivideogen dataset pick 2                    # choose the candidate that looks right

# 2. Her dataset: 40 shots that keep her identity
aivideogen dataset build --backend qwen --count 40
#    Review data/dataset/images (or the Dataset tab of `aivideogen ui`) and delete every
#    image where she doesn't look like herself. Then:
aivideogen dataset check

# 3. Train her model
aivideogen train --config configs/wan21_14b.yaml

# 4. Generate videos of her
aivideogen generate "Mika walks through a rainy neon-lit street at night, cinematic tracking shot"
aivideogen generate "she laughs while baking cookies in a bright kitchen" --count 3 --seed 1
```

Base model weights download from Hugging Face on first use: about 70 GB for the 14B model with its text encoder.

**Image backends for steps 1–2.**

- `qwen` (default) runs open Qwen-Image / Qwen-Image-Edit-2511 locally, with no API keys.
- `replicate` uses the hosted Nano Banana model. It has the best identity consistency, needs no GPU, and costs a few cents an image (`pip install -e '.[replicate]'`, set `REPLICATE_API_TOKEN`). A good option is to build the dataset this way on a laptop, then train on a GPU box.
- **Your own images.** If you already have images of her from Midjourney or another tool, add them with
  `aivideogen dataset import path/to/folder`. A `.txt` caption next to an image is kept, and the trigger tag is added.

**During training,** preview clips land in `runs/<name>/samples/` every few hundred steps, all from the same
seed so you can watch her come into focus. Checkpoints go to `runs/<name>/checkpoints/`. `--resume` continues
an interrupted run, or extends a finished one with `--set train.steps=4000`. Any setting can be overridden, for
example `--set train.learning_rate=5e-5`.

## Web UI

```bash
aivideogen ui            # http://127.0.0.1:7860   (add --share for a public link on a cloud GPU)
```

- **Generate:** type what she does, pick a checkpoint, and adjust size, length, steps and likeness strength.
- **Dataset:** browse her training images, edit captions, and delete off-model shots.
- **Train:** start, stop or resume a preset, with live step, loss and ETA, the log, and the latest preview clip.

## Cloud GPUs

- **RunPod, Vast, Lambda and similar:** start a PyTorch machine with a 48–80 GB GPU, `git clone` this repo,
  and follow the steps above. Use `aivideogen ui --share` to drive it from your browser.
- **Modal** (no SSH, billed per second): run every heavy step from your own machine:

  ```bash
  pip install -e '.[cloud]' && modal setup
  modal run modal_app.py::dataset --count 40        # builds her dataset on an H100, downloads it for review
  modal run modal_app.py::train --config configs/wan21_14b.yaml   # uploads data/dataset, trains, downloads her LoRA
  modal run modal_app.py::generate --prompt "Mika dances in the rain at night"
  ```

  Set `AIVIDEOGEN_GPU=A100-80GB` (or another Modal GPU type) to change hardware.

## Using her model elsewhere

```bash
aivideogen export comfyui     # LoRA with Wan's original key names, for ComfyUI and other Wan tools
aivideogen export merged      # base model with her LoRA fused in, saved as its own standalone model
```

The merged model in `models/<name>/` loads with `WanPipeline.from_pretrained("models/<name>")`, with no LoRA step.

## Getting a strong likeness

- **The dataset is the model.** 25–50 images, and every one has to be unmistakably her. Delete drifted faces
  without mercy.
- **Keep the variety.** Close-ups, full body, different angles, expressions, outfits, places and light.
  Images are never mirrored during training, because her beauty mark is on one side.
- **Compare the samples across steps.** If she looks right at step 1500 and later looks stiff or "baked",
  generate from that checkpoint: `--lora runs/<name>/checkpoints/step-001500`.
- **Tune with `--lora-scale`.** If the likeness is too weak, try 1.1–1.2 or more steps. If the look is overcooked,
  try 0.8–0.9 or an earlier checkpoint.

## Responsible use

- Mika is fictional and an adult. `character.yaml` refuses any age under 18, and every prompt (dataset synthesis,
  training samples, generation) passes a guard that rejects depicting her as a minor.
- Don't train this on photos of a real person without their explicit consent.
- Check the licenses of the base models you use (Wan 2.x and Qwen-Image are Apache 2.0) and the terms of any
  hosted service.

## Project layout

```
character.yaml                 who she is
configs/                       training presets (GPU sizes) + tiny CPU demo
src/aivideogen/
  character.py, safety.py      her definition, prompt rewriting, minor-depiction guard
  dataset/                     shot list, image backends (qwen / replicate / mock), build, import, checks
  train/                       config, aspect buckets + latent/text cache, LoRA trainer
  generate.py, export.py       video generation, ComfyUI / merged-model export
  webui.py, cli.py, tiny.py    Gradio UI, command line, tiny test model
modal_app.py                   optional cloud-GPU runner
tests/                         47 tests; full train→generate→export runs on the tiny model
```

## Development

```bash
pip install -e '.[dev]'
pytest          # ~10 s on CPU
ruff check . && ruff format --check .
```
