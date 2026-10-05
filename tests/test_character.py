import pytest
import yaml
from pydantic import ValidationError

from aivideogen.character import Character
from aivideogen.safety import UnsafePromptError, check_prompt


def test_repo_character_is_an_adult_with_a_trigger(character):
    assert character.age >= 18
    assert character.tag == "mksrn woman"
    assert character.looks().startswith(f"a {character.age}-year-old woman with ")
    assert character.appearance.eyes in character.looks()


def test_heritage_is_optional_and_joins_the_description(character):
    described = character.model_copy(update={"heritage": "Eurasian"})
    assert described.looks().startswith(f"a {character.age}-year-old Eurasian woman with ")


def test_reference_image_resolves_next_to_the_character_file(tmp_path, character):
    data = character.model_dump(mode="json")
    data["reference_image"] = "private/me.jpg"
    (tmp_path / "her.yaml").write_text(yaml.safe_dump(data))
    assert Character.load(tmp_path / "her.yaml").reference_image == tmp_path / "private" / "me.jpg"


def _raw(character, **changes):
    data = character.model_dump()
    data.update(changes)
    return data


def test_minor_age_is_rejected(character):
    with pytest.raises(ValidationError, match="adult"):
        Character.model_validate(_raw(character, age=17))


@pytest.mark.parametrize("trigger", ["Mika", "a", "two words", "1abc"])
def test_trigger_must_be_a_single_lowercase_token(character, trigger):
    with pytest.raises(ValidationError):
        Character.model_validate(_raw(character, trigger=trigger))


def test_prompt_for_swaps_her_name_for_the_tag(character):
    assert character.prompt_for("Mika dances in the rain.") == "mksrn woman dances in the rain"
    assert (
        character.prompt_for("Mika Sorensen reads in mika's room")
        == "mksrn woman reads in mksrn woman's room"
    )


def test_prompt_for_prefixes_the_tag_when_she_is_not_named(character):
    assert character.prompt_for("  she   waves at the camera ") == "mksrn woman, she waves at the camera"
    assert character.prompt_for("mksrn woman waves") == "mksrn woman waves"


@pytest.mark.parametrize(
    "prompt",
    [
        "she is a teenager at the mall",
        "mksrn woman as a child",
        "dressed as a schoolgirl",
        "a 16-year-old girl",
        "she is 15 years old",
        "aged 12",
        "a young girl on a swing",
    ],
)
def test_guard_blocks_minor_depictions(prompt):
    with pytest.raises(UnsafePromptError):
        check_prompt(prompt)


@pytest.mark.parametrize(
    "prompt",
    [
        "mksrn woman walks through a canteen",
        "she is 23 years old",
        "she reads a book to kids at the library",
        "she steps on stage at age 25",
        "the girl smiles at the camera",
    ],
)
def test_guard_allows_ordinary_prompts(prompt):
    assert check_prompt(prompt) == prompt
