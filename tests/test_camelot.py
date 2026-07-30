import pytest

from cuekey.camelot import MAJOR, MINOR, Key, parse_key


@pytest.mark.parametrize(
    ("name", "camelot"),
    [
        ("C", "8B"),
        ("G", "9B"),
        ("D", "10B"),
        ("A", "11B"),
        ("E", "12B"),
        ("B", "1B"),
        ("F#", "2B"),
        ("F", "7B"),
        ("Am", "8A"),
        ("Em", "9A"),
        ("Bm", "10A"),
        ("F#m", "11A"),
        ("C#m", "12A"),
        ("G#m", "1A"),
        ("Fm", "4A"),
        ("Cm", "5A"),
        ("Dm", "7A"),
    ],
)
def test_camelot_wheel_mapping(name: str, camelot: str) -> None:
    assert parse_key(name).camelot == camelot


@pytest.mark.parametrize(
    ("name", "openkey"),
    [
        ("C", "1d"),
        ("Am", "1m"),
        ("G", "2d"),
        ("B", "6d"),
        ("Em", "2m"),
    ],
)
def test_openkey_mapping(name: str, openkey: str) -> None:
    assert parse_key(name).openkey == openkey


def test_parse_key_flats_and_modes() -> None:
    assert parse_key("Bb") == Key(10, MAJOR)
    assert parse_key("Ebm") == Key(3, MINOR)
    assert parse_key("Am").standard == "Am"


def test_invalid_keys_rejected() -> None:
    with pytest.raises(ValueError):
        parse_key("H")
    with pytest.raises(ValueError):
        Key(12, MAJOR)
    with pytest.raises(ValueError):
        Key(0, "dorian")


def test_notation_dispatch() -> None:
    key = parse_key("Am")
    assert key.notation("camelot") == "8A"
    assert key.notation("openkey") == "1m"
    assert key.notation("standard") == "Am"
    with pytest.raises(ValueError):
        key.notation("solfege")
