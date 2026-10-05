"""The one character every training image and every generated video is about."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator

DEFAULT_CHARACTER_FILE = Path("character.yaml")


class Appearance(BaseModel):
    face: str
    eyes: str
    skin: str
    hair: str
    build: str
    marks: str = ""


class Character(BaseModel):
    name: str
    trigger: str
    age: int
    class_word: str = "woman"
    heritage: str = ""
    appearance: Appearance
    signature_outfit: str
    style: str = "photorealistic, natural skin texture"
    # A photo that defines her face. When set, it is her identity anchor instead of a generated portrait.
    reference_image: Path | None = None
    reference_caption: str = ""  # what the reference photo shows (framing, pose, outfit, place, light)

    @field_validator("age")
    @classmethod
    def _must_be_adult(cls, age: int) -> int:
        if age < 18:
            raise ValueError("the character must be an adult (age 18 or older)")
        return age

    @field_validator("trigger")
    @classmethod
    def _trigger_is_a_single_token(cls, trigger: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,31}", trigger):
            raise ValueError(
                "trigger must be 3-32 lowercase letters/digits/underscores, starting with a letter"
            )
        return trigger

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CHARACTER_FILE) -> Character:
        with open(path, encoding="utf-8") as f:
            character = cls.model_validate(yaml.safe_load(f))
        if character.reference_image and not character.reference_image.is_absolute():
            character.reference_image = Path(path).parent / character.reference_image
        return character

    @property
    def first_name(self) -> str:
        return self.name.split()[0]

    @property
    def tag(self) -> str:
        """How captions and prompts refer to her, e.g. ``mksrn woman``."""
        return f"{self.trigger} {self.class_word}"

    def looks(self) -> str:
        """Full physical description, used only when synthesizing her training images.

        Training captions deliberately leave these details out so the model binds them to the trigger word
        instead of to the words themselves.
        """
        a = self.appearance
        features = [a.face, a.eyes, a.skin, a.hair, a.build, a.marks]
        who = " ".join(w for w in [f"a {self.age}-year-old", self.heritage, self.class_word] if w)
        return f"{who} with " + "; ".join(f for f in features if f)

    def prompt_for(self, scene: str) -> str:
        """Rewrite a free-form scene description so it features her.

        Mentions of her name become the trigger tag; if she isn't mentioned at all, the tag is prepended.
        """
        scene = " ".join(scene.split()).strip().rstrip(".")
        names = sorted({self.name, self.first_name}, key=len, reverse=True)
        pattern = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b", re.IGNORECASE)
        if pattern.search(scene):
            # "Mika dances in Mika's room" -> "mksrn woman dances in mksrn woman's room".
            return pattern.sub(self.tag, scene)
        if re.search(rf"\b{re.escape(self.trigger)}\b", scene, re.IGNORECASE):
            return scene
        return f"{self.tag}, {scene}" if scene else self.tag
