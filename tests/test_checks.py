"""Кожен прапорець checks.py: позитивний і негативний кейс."""

from hookgen.checks import (check_banned, check_length, check_off_brand_fact,
                            check_personal_attribute, check_unverifiable, run_checks,
                            status_from_flags)


def codes(flags):
    return [f.code for f in flags]


def test_too_long(brand):
    assert codes(check_length("on_screen", "x" * 41, brand)) == ["TOO_LONG"]
    assert check_length("on_screen", "x" * 40, brand) == []
    assert check_length("hook", "x" * 90, brand) == []


def test_banned_phrase_case_insensitive(brand):
    assert codes(check_banned("GUARANTEED to stay paired", brand)) == ["BANNED_PHRASE"]
    assert codes(check_banned("Works 100% of the time", brand)) == ["BANNED_PHRASE"]
    assert check_banned("Pairs stay together in the wash", brand) == []


def test_banned_phrase_respects_word_boundaries(brand):
    # "cure" не має ловитися всередині "secure" чи "curious".
    assert check_banned("A secure snap. Curious?", brand) == []


def test_winner_itself_is_flagged(brand):
    # Текст переможця містить абсолютну обіцянку — і це навмисно ловиться.
    assert "BANNED_PHRASE" in codes(run_checks("on_screen", "Never lose a sock again", brand))


def test_unverifiable_claim():
    for text in ["95% fewer lost socks", "The #1 sock fix", "Always paired",
                 "Clinically tested socks", "Proven to work"]:
        flags = check_unverifiable(text)
        assert codes(flags) == ["UNVERIFIABLE_CLAIM"] and flags[0].severity == "warn", text
    assert check_unverifiable("Pairs that stick together") == []


def test_personal_attribute():
    for text in ["Are you tired of lost socks?", "You have a sock problem",
                 "Fix your laundry problem today"]:
        flags = check_personal_attribute(text)
        assert codes(flags) == ["PERSONAL_ATTRIBUTE"] and flags[0].severity == "warn", text
    assert check_personal_attribute("Laundry day, but make it easy") == []


def test_off_brand_fact(brand):
    assert codes(check_off_brand_fact("Get 5 pairs for $19", brand)) == ["OFF_BRAND_FACT"]
    assert codes(check_off_brand_fact("10 pairs for $29", brand)) == ["OFF_BRAND_FACT"]
    assert check_off_brand_fact("5 pairs for $29, every quarter", brand) == []
    assert check_off_brand_fact("I lost 47 socks", brand) == []


def test_status_from_flags(brand):
    assert status_from_flags(run_checks("hook", "Are you tired of lost socks?", brand)) == "ready"
    assert status_from_flags(run_checks("hook", "Guaranteed pairs", brand)) == "rejected"
