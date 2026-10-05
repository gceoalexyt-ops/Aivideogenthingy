"""A miniature, randomly initialized Wan pipeline with the real architecture.

It lets the whole dataset -> train -> LoRA -> generate path run in a minute on a CPU (tests and
``aivideogen demo``). It produces abstract noise, not real video; it exists to prove the plumbing works.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import torch


def build_tiny_wan(out_dir: Path, vocabulary_texts: Iterable[str] = ()) -> Path:
    from diffusers import AutoencoderKLWan, UniPCMultistepScheduler, WanPipeline, WanTransformer3DModel
    from tokenizers import Tokenizer, models, normalizers, pre_tokenizers, processors, trainers
    from transformers import PreTrainedTokenizerFast, UMT5Config, UMT5EncoderModel

    torch.manual_seed(0)
    words = sorted({w for text in vocabulary_texts for w in re.findall(r"\w+|[^\w\s]", text.lower())})
    tok = Tokenizer(models.WordLevel(unk_token="<unk>"))
    tok.normalizer = normalizers.Lowercase()
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    tok.train_from_iterator(
        [" ".join(words) or "hello"], trainers.WordLevelTrainer(special_tokens=["<pad>", "</s>", "<unk>"])
    )
    tok.post_processor = processors.TemplateProcessing(single="$A </s>", special_tokens=[("</s>", 1)])
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=tok, pad_token="<pad>", eos_token="</s>", unk_token="<unk>"
    )

    text_dim = 32
    text_encoder = UMT5EncoderModel(
        UMT5Config(
            vocab_size=tok.get_vocab_size(),
            d_model=text_dim,
            d_kv=8,
            d_ff=64,
            num_layers=2,
            num_heads=4,
            relative_attention_num_buckets=8,
            relative_attention_max_distance=16,
            pad_token_id=0,
            eos_token_id=1,
            decoder_start_token_id=0,
        )
    )
    z_dim = 4
    vae = AutoencoderKLWan(
        base_dim=8,
        z_dim=z_dim,
        dim_mult=[1, 2, 2, 2],
        num_res_blocks=1,
        attn_scales=[],
        temperal_downsample=[False, True, True],
        latents_mean=[0.0] * z_dim,
        latents_std=[1.0] * z_dim,
    )
    transformer = WanTransformer3DModel(
        patch_size=(1, 2, 2),
        num_attention_heads=2,
        attention_head_dim=12,
        in_channels=z_dim,
        out_channels=z_dim,
        text_dim=text_dim,
        freq_dim=32,
        ffn_dim=64,
        num_layers=2,
        rope_max_seq_len=64,
    )
    scheduler = UniPCMultistepScheduler(
        prediction_type="flow_prediction", use_flow_sigmas=True, num_train_timesteps=1000, flow_shift=3.0
    )
    pipe = WanPipeline(
        tokenizer=tokenizer, text_encoder=text_encoder, vae=vae, scheduler=scheduler, transformer=transformer
    )
    out_dir = Path(out_dir)
    pipe.save_pretrained(out_dir)
    return out_dir
