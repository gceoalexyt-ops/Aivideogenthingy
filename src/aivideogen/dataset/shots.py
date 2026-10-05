"""The shot list for her training dataset.

A good identity dataset shows the same person across many angles, expressions, outfits, places and
lighting setups, so the model learns *her* rather than one photo. The first shots form a classic character
sheet on a plain backdrop; the rest are seeded random combinations so the list is reproducible.

Captions describe everything that should stay controllable (framing, pose, outfit, place, light) and
nothing about her face or hair, so those get bound to the trigger word.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

from aivideogen.character import Character

STUDIO = "in front of a plain light-gray studio backdrop"
STUDIO_LIGHT = "soft even studio lighting"

FRAMINGS = {
    "close-up portrait": (0.30, ["1:1", "4:5"]),
    "head-and-shoulders shot": (0.20, ["4:5", "3:4"]),
    "medium shot from the waist up": (0.30, ["3:4", "16:9", "4:5"]),
    "full-body shot": (0.20, ["9:16", "2:3"]),
}

ANGLES = [
    "facing the camera",
    "in three-quarter view turned to her left",
    "in three-quarter view turned to her right",
    "in profile",
    "seen from slightly above",
    "seen from slightly below",
    "looking back over her shoulder",
]

EXPRESSIONS = [
    "with a relaxed neutral expression",
    "with a soft closed-mouth smile",
    "laughing with a big open smile",
    "with a thoughtful look",
    "with a surprised expression",
    "with a playful smirk",
    "with a serious focused expression",
    "with her eyes closed, calm",
]

# Close framings only show the head, so their "poses" are head and hand gestures.
POSES = {
    "close": [
        "",
        "tilting her head slightly",
        "tucking her hair behind her ear",
        "resting her chin on her hand",
        "looking slightly off camera",
    ],
    "wide": [
        "standing",
        "walking toward the camera",
        "sitting",
        "leaning against a wall",
        "holding a coffee cup",
        "with her arms crossed",
        "stretching her arms overhead",
        "mid-stride, walking past the camera",
    ],
}

OUTFITS = [
    "a black leather jacket over a white t-shirt and black jeans",
    "a flowy floral summer sundress",
    "a tailored navy blazer over a silk blouse",
    "an oversized gray hoodie",
    "a fitted black athletic set",
    "an elegant emerald evening dress",
    "a denim jacket over a striped top",
    "a camel winter coat and a red knit scarf",
    "a crisp white button-up shirt",
    "a pastel pink cardigan over a white camisole",
]

# Each setting carries lighting that makes physical sense there.
SETTINGS = [
    ("in a cozy cafe by the window", ["warm window light", "soft overcast daylight through the window"]),
    ("on a busy city street at night", ["neon signs and street lights", "rain-slick reflections of neon"]),
    ("on a sunny beach", ["bright midday sun", "golden hour sunlight"]),
    ("in an autumn park with fallen leaves", ["golden hour sunlight", "soft overcast daylight"]),
    ("in a minimalist apartment living room", ["soft natural daylight", "warm lamp light in the evening"]),
    ("in a modern open-plan office", ["cool even office lighting", "soft natural daylight"]),
    ("on a rooftop at sunset with a city skyline behind her", ["golden hour sunlight", "pink dusk light"]),
    ("between tall bookshelves in a quiet library", ["warm lamp light", "soft natural daylight"]),
    ("on a snowy street in winter", ["soft overcast daylight", "warm shop-window light at dusk"]),
    ("in a bright modern kitchen", ["soft natural daylight", "warm morning sunlight"]),
    ("on a train platform", ["cool overcast daylight", "fluorescent station lighting at night"]),
    ("in a blooming flower garden", ["bright morning sunlight", "dappled sunlight through trees"]),
    ("in a modern gym", ["bright even gym lighting", "dramatic overhead lighting"]),
    ("in a white-walled art gallery", ["soft gallery spotlights", "cool even daylight"]),
    (STUDIO, [STUDIO_LIGHT, "dramatic side lighting"]),
]


@dataclass(frozen=True)
class Shot:
    index: int
    framing: str
    angle: str
    expression: str
    pose: str
    outfit: str
    setting: str
    lighting: str
    aspect_ratio: str

    @property
    def stem(self) -> str:
        return f"{self.index:03d}"

    def _details(self) -> list[str]:
        parts = [self.framing, self.angle, self.expression]
        if self.pose:
            parts.append(self.pose)
        parts += [f"wearing {self.outfit}", self.setting, self.lighting]
        return parts

    def caption(self, character: Character) -> str:
        """Training caption: trigger tag + controllable details, no facial description."""
        return ", ".join([character.tag, *self._details()])

    def generation_prompt(self, character: Character) -> str:
        """Instruction for an identity-preserving image model, given her anchor portrait as reference."""
        return (
            "Create a new photograph of the exact same woman shown in the reference image. Keep her identity "
            "identical: the same face shape, eyes, nose, lips, skin tone, distinguishing marks and hair. "
            f"She is {character.looks()}. "
            f"Shot: {', '.join(self._details())}. "
            f"{character.style}, realistic photo, single person, no text, no watermark."
        )

    def to_dict(self) -> dict:
        return asdict(self)


def anchor_prompt(character: Character) -> str:
    """Text-to-image prompt for her canonical portrait, the identity reference for every other shot."""
    return (
        f"Photorealistic studio portrait photograph of {character.looks()}. "
        f"She faces the camera with a relaxed neutral expression, head and shoulders visible, "
        f"wearing {character.signature_outfit}, {STUDIO}, {STUDIO_LIGHT}, sharp focus, 85mm lens, "
        f"{character.style}, single person, no text."
    )


def anchor_caption(character: Character) -> str:
    return ", ".join(
        [
            character.tag,
            "head-and-shoulders shot",
            "facing the camera",
            "with a relaxed neutral expression",
            f"wearing {character.signature_outfit}",
            STUDIO,
            STUDIO_LIGHT,
        ]
    )


def _character_sheet(character: Character) -> list[Shot]:
    sig = character.signature_outfit
    rows = [
        ("close-up portrait", "facing the camera", EXPRESSIONS[0], "", "1:1"),
        ("close-up portrait", ANGLES[1], EXPRESSIONS[1], "", "4:5"),
        ("close-up portrait", ANGLES[2], EXPRESSIONS[1], "", "4:5"),
        ("head-and-shoulders shot", "in profile", EXPRESSIONS[0], "", "4:5"),
        ("medium shot from the waist up", "facing the camera", EXPRESSIONS[2], "standing", "3:4"),
        ("full-body shot", "facing the camera", EXPRESSIONS[0], "standing", "9:16"),
        ("full-body shot", ANGLES[1], EXPRESSIONS[1], "walking toward the camera", "9:16"),
        ("close-up portrait", ANGLES[6], EXPRESSIONS[5], "", "4:5"),
    ]
    return [
        Shot(i + 1, framing, angle, expr, pose, sig, STUDIO, STUDIO_LIGHT, ar)
        for i, (framing, angle, expr, pose, ar) in enumerate(rows)
    ]


def plan_shots(character: Character, count: int = 40, seed: int = 0) -> list[Shot]:
    """Return ``count`` varied shots: the character sheet first, then seeded random combinations."""
    if count < 1:
        raise ValueError("count must be at least 1")
    rng = random.Random(seed)
    shots = _character_sheet(character)[:count]

    framings = list(FRAMINGS)
    weights = [FRAMINGS[f][0] for f in framings]
    settings = [s for s in SETTINGS if s[0] != STUDIO]
    setting_pool: list[tuple[str, list[str]]] = []
    outfits = [character.signature_outfit, *OUTFITS]
    outfit_pool: list[str] = []

    while len(shots) < count:
        # Cycle through settings and outfits before repeating any, so coverage is even.
        if not setting_pool:
            setting_pool = rng.sample(settings, len(settings))
        if not outfit_pool:
            outfit_pool = rng.sample(outfits, len(outfits))
        setting, lights = setting_pool.pop()
        framing = rng.choices(framings, weights)[0]
        close = framing in ("close-up portrait", "head-and-shoulders shot")
        shots.append(
            Shot(
                index=len(shots) + 1,
                framing=framing,
                angle=rng.choice(ANGLES),
                expression=rng.choice(EXPRESSIONS),
                pose=rng.choice(POSES["close" if close else "wide"]),
                outfit=outfit_pool.pop(),
                setting=setting,
                lighting=rng.choice(lights),
                aspect_ratio=rng.choice(FRAMINGS[framing][1]),
            )
        )
    return shots
