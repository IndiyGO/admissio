import pytest

from admissio.logins import LoginGenerator, fold, name_tokens

DEFAULT = ["{first}.{last}", "{second}.{last}", "{first}.{last}{n}"]


def test_fold_strips_accents_and_punctuation():
    assert fold("Maria José D'Ávila-Neto") == "maria jose davila neto"


def test_particles_are_ignored():
    assert name_tokens("José da Silva dos Santos") == ["jose", "silva", "santos"]


def test_priority_order():
    got = list(LoginGenerator(DEFAULT, max_suffix=3).candidates("João Pedro de Oliveira"))
    assert got == ["joao.oliveira", "pedro.oliveira", "joao.oliveira2", "joao.oliveira3"]


def test_second_name_pattern_skipped_for_two_word_names():
    got = list(LoginGenerator(DEFAULT, max_suffix=2).candidates("Ana Souza"))
    assert got == ["ana.souza", "ana.souza2"]


def test_suffix_survives_truncation():
    gen = LoginGenerator(["{first}.{last}", "{first}.{last}{n}"], max_suffix=2, max_length=12)
    assert list(gen.candidates("Maximiliano Albuquerque")) == ["maximiliano", "maximiliano2"]


def test_single_word_name_yields_nothing_for_last_name_patterns():
    assert list(LoginGenerator(DEFAULT).candidates("Cher")) == []
    assert list(LoginGenerator(["{first}"]).candidates("Cher")) == ["cher"]


def test_initials_pattern():
    gen = LoginGenerator(["{f}{middle_initials}{last}"])
    assert list(gen.candidates("Ana Beatriz Costa Souza")) == ["abcsouza"]


def test_unknown_field_rejected():
    with pytest.raises(ValueError, match="nickname"):
        LoginGenerator(["{nickname}"])
