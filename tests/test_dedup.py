"""Дедуп: точний дубль, перефраз вище порогу, різні тексти нижче порогу."""

from hookgen.dedup import duplicate_flag, find_duplicate, normalize

HISTORY = ["Where do all the missing socks actually go?",
           "I've lost 47 socks this year. Then I found these."]


def test_normalize():
    assert normalize("  Where do ALL the socks... go?! ") == "where do all the socks go"


def test_exact_duplicate():
    match = find_duplicate("Where do all the missing socks actually go?", HISTORY)
    assert match is not None and match[1] == 100


def test_paraphrase_above_threshold():
    match = find_duplicate("Where do all the missing socks go, actually?", HISTORY)
    assert match is not None and match[0] == HISTORY[0]


def test_different_text_below_threshold():
    assert find_duplicate("My socks are in a committed relationship now.", HISTORY) is None


def test_threshold_is_configurable():
    text = "Where did my missing socks go?"
    assert find_duplicate(text, HISTORY, threshold=99) is None
    assert find_duplicate(text, HISTORY, threshold=50) is not None


def test_duplicate_flag_checks_history_then_batch():
    flag = duplicate_flag("Where do all the missing socks actually go?", HISTORY, [])
    assert flag.code == "DUPLICATE" and flag.severity == "block" and "історії" in flag.message
    flag = duplicate_flag("Snap. Wash. Still a pair.", HISTORY, ["Snap, wash, still a pair!"])
    assert flag is not None and "батчі" in flag.message
    assert duplicate_flag("Snap. Wash. Still a pair.", HISTORY, []) is None
