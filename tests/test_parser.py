from ntindex.parser import ParsedTitle, parse_title


def test_parse_title_extracts_swap_parts():
    assert parse_title("Furina as Nahida | Genshin Impact Model Swap") == ParsedTitle(
        source="Furina",
        target="Nahida",
        game="Genshin Impact",
    )


def test_parse_title_normalizes_spacing():
    assert parse_title("  Furina   as   Nahida  |  Genshin Impact   Model Swap ") == ParsedTitle(
        source="Furina",
        target="Nahida",
        game="Genshin Impact",
    )


def test_parse_title_rejects_unmatched_titles():
    assert parse_title("Furina and Nahida gameplay") is None
