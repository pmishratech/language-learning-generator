import json
from argparse import Namespace

from language_learning_tool.cli import generate_audio
from language_learning_tool.parser import align_entries


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
