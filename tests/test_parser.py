from polish_tool.cli import apply_replacements, load_replacements, prepare_spoken
from polish_tool.parser import parse_entries


SAMPLE = """Q: Jak się masz?|Q: How are you?
A: Mam się dobrze.|A: I am fine.
|
Q: Gdzie mieszkasz?|Q: Where do you live?
A: Mieszkam w Krakowie.|A: I live in Krakow.
   Z rodziną.|With family.
|
"""


def test_parse_entries_reads_first_column() -> None:
    entries = parse_entries(SAMPLE.splitlines(), column=0)

    assert len(entries) == 2
    assert entries[0].question == "Q: Jak się masz?"
    assert entries[0].answer == "A: Mam się dobrze."
    assert entries[1].question == "Q: Gdzie mieszkasz?"
    assert entries[1].answer == "A: Mieszkam w Krakowie. Z rodziną."


def test_parse_entries_reads_second_column() -> None:
    entries = parse_entries(SAMPLE.splitlines(), column=1)

    assert len(entries) == 2
    assert entries[0].question == "Q: How are you?"
    assert entries[1].answer == "A: I live in Krakow. With family."


def test_prepare_spoken_strips_labels_by_default() -> None:
    assert prepare_spoken("Q: Jak się masz?", keep_labels=False) == "Jak się masz?"
    assert prepare_spoken("A: Mam się dobrze.", keep_labels=False) == "Mam się dobrze."


def test_apply_replacements_updates_names_for_pronunciation() -> None:
    text = "Mój mąż ma na imię Pankaj i pracuje w StoneX Inc."
    replacements = [("Pankaj", "Pankadż"), ("StoneX Inc.", "Stone Eks Ink")]

    assert apply_replacements(text, replacements) == "Mój mąż ma na imię Pankadż i pracuje w Stone Eks Ink"


def test_load_replacements_sorts_longest_match_first(tmp_path) -> None:
    replacements_file = tmp_path / "replacements.json"
    replacements_file.write_text(
        '{"Pankaj": "Pankadż", "Mój mąż ma na imię Pankaj.": "Mój mąż ma na imię Pankadż."}',
        encoding="utf-8",
    )

    replacements = load_replacements(str(replacements_file))

    assert replacements[0][0] == "Mój mąż ma na imię Pankaj."
