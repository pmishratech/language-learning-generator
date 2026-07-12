import json
from argparse import Namespace

from language_learning_tool.cli import generate_audio, generate_site
from language_learning_tool.parser import align_entries, load_entries


SAMPLE = """Q: Jak się masz?|Q: How are you?
A: Mam się dobrze.|A: I am fine.
|
Q: Gdzie mieszkasz?|Q: Where do you live?
A: Mieszkam w Krakowie.|A: I live in Krakow.
   Z rodziną.|With family.
|
"""


def test_align_entries_reads_study_and_reference_columns(tmp_path) -> None:
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text(SAMPLE, encoding="utf-8")

    aligned = align_entries(sample_file, study_column=0, reference_column=1)

    assert len(aligned) == 2
    assert aligned[0].study.question == "Q: Jak się masz?"
    assert aligned[0].reference.question == "Q: How are you?"
    assert aligned[1].study.answer == "A: Mieszkam w Krakowie. Z rodziną."
    assert aligned[1].reference.answer == "A: I live in Krakow. With family."


def test_generate_audio_writes_bundle_and_dashboard(tmp_path, monkeypatch) -> None:
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text(SAMPLE, encoding="utf-8")
    out_dir = tmp_path / "out"
    captured_jobs = []

    def fake_run_synthesis(items, config) -> None:
        captured_jobs.extend(list(items))

    monkeypatch.setattr("language_learning_tool.cli.run_synthesis", fake_run_synthesis)

    args = Namespace(
        command="generate",
        input_file=str(sample_file),
        study_column=0,
        column=None,
        reference_column=1,
        mode="both",
        voice="pl-PL-ZofiaNeural",
        rate="+0%",
        pitch="+0Hz",
        volume="+0%",
        output_dir=str(out_dir),
        limit=None,
        profile_file=None,
        pronunciation_file=None,
        replacements_file=None,
        keep_labels=False,
        study_language_name="Polish",
        reference_language_name="English",
        dashboard_title="Polish ↔ English practice",
        dashboard_subtitle="A generated dashboard for study.",
        dashboard_file_name="dashboard.html",
        manifest_data_file_name="manifest-data.js",
        skip_dashboard=False,
    )

    exit_code = generate_audio(args)

    assert exit_code == 0
    assert len(captured_jobs) == 4

    bundle = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert bundle["meta"]["study_language_name"] == "Polish"
    assert bundle["meta"]["reference_language_name"] == "English"
    assert bundle["items"][0]["display_text"] == "Jak się masz?"
    assert bundle["items"][0]["translation_text"] == "How are you?"
    assert bundle["items"][0]["output_file"] == "audio/0001-entry-0001-question.mp3"
    assert (out_dir / "manifest-data.js").exists()
    assert (out_dir / "dashboard.html").exists()


def test_load_entries_reads_json_deck_by_language_index(tmp_path) -> None:
    deck = {
        "meta": {
            "language_order": ["en", "hi"],
            "languages": {"en": "English", "hi": "Hindi"},
        },
        "entries": [
            {
                "id": "greeting",
                "q": {"en": "What is your name?", "hi": "आपका नाम क्या है?"},
                "a": {"en": "My name is {{full_name}}.", "hi": "मेरा नाम {{full_name}} है।"},
            }
        ],
    }
    deck_file = tmp_path / "deck.json"
    deck_file.write_text(json.dumps(deck, ensure_ascii=False, indent=2), encoding="utf-8")

    english_entries = load_entries(deck_file, column=0)
    hindi_entries = load_entries(deck_file, column=1)

    assert english_entries[0].question == "What is your name?"
    assert hindi_entries[0].answer == "मेरा नाम {{full_name}} है।"


def test_generate_site_writes_index_and_catalog(tmp_path, monkeypatch) -> None:
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text(SAMPLE, encoding="utf-8")
    site_config = tmp_path / "site.json"
    site_config.write_text(
        json.dumps(
            {
                "site": {
                    "title": "Common language practice",
                    "subtitle": "Choose the language deck you want.",
                    "output_dir": str(tmp_path / "site-output"),
                },
                "decks": [
                    {
                        "slug": "polish-english",
                        "label": "Polish → English",
                        "input_file": str(sample_file),
                        "study_column": 0,
                        "reference_column": 1,
                        "voice": "pl-PL-ZofiaNeural",
                        "study_language_name": "Polish",
                        "reference_language_name": "English",
                    },
                    {
                        "slug": "english-polish",
                        "label": "English → Polish",
                        "input_file": str(sample_file),
                        "study_column": 1,
                        "reference_column": 0,
                        "voice": "en-US-AriaNeural",
                        "study_language_name": "English",
                        "reference_language_name": "Polish",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    captured_jobs = []

    def fake_run_synthesis(items, config) -> None:
        captured_jobs.extend(list(items))

    monkeypatch.setattr("language_learning_tool.cli.run_synthesis", fake_run_synthesis)

    args = Namespace(command="generate-site", site_config=str(site_config), output_dir=None)
    exit_code = generate_site(args)

    site_output = tmp_path / "site-output"
    catalog = json.loads((site_output / "catalog.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert len(catalog["decks"]) == 2
    assert (site_output / "index.html").exists()
    assert (site_output / "catalog-data.js").exists()
    assert (site_output / "polish-english" / "dashboard.html").exists()
    assert (site_output / "english-polish" / "dashboard.html").exists()
    assert captured_jobs


def test_generate_site_removes_stale_deck_directories(tmp_path, monkeypatch) -> None:
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text(SAMPLE, encoding="utf-8")
    site_output = tmp_path / "site-output"
    stale_dir = site_output / "english-audio"
    stale_dir.mkdir(parents=True, exist_ok=True)
    (stale_dir / "dashboard.html").write_text("old dashboard", encoding="utf-8")

    site_config = tmp_path / "site.json"
    site_config.write_text(
        json.dumps(
            {
                "site": {
                    "output_dir": str(site_output),
                },
                "decks": [
                    {
                        "slug": "hindi-audio",
                        "label": "Hindi audio",
                        "input_file": str(sample_file),
                        "study_column": 0,
                        "reference_column": 1,
                        "voice": "hi-IN-SwaraNeural",
                        "study_language_name": "Hindi",
                        "reference_language_name": "English",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    def fake_run_synthesis(items, config) -> None:
        _ = list(items)
        _ = config

    monkeypatch.setattr("language_learning_tool.cli.run_synthesis", fake_run_synthesis)

    exit_code = generate_site(Namespace(command="generate-site", site_config=str(site_config), output_dir=None))

    assert exit_code == 0
    assert not stale_dir.exists()
    assert (site_output / "hindi-audio" / "dashboard.html").exists()
