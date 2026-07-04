from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable

from language_learning_tool.dashboard import write_dashboard_html, write_manifest_bundle, write_manifest_data_js
from language_learning_tool.parser import AlignedEntry, Entry, align_entries, load_entries
from language_learning_tool.tts import TTSConfig, run_synthesis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="language-dashboard",
        description="Generate multilingual study audio, manifests, and dashboards from pipe-delimited source files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate audio, manifest, and dashboard files from a source file")
    generate.add_argument("input_file", help="Path to the source text file")
    generate.add_argument("--study-column", type=int, default=0, help="Zero-based language column used for spoken study text")
    generate.add_argument("--column", type=int, default=None, help="Backward-compatible alias for --study-column")
    generate.add_argument(
        "--reference-column",
        type=int,
        default=1,
        help="Zero-based reference language column for the dashboard. Use -1 to disable reference text.",
    )
    generate.add_argument(
        "--mode",
        choices=["questions", "answers", "both"],
        default="both",
        help="Choose which parts of each entry to turn into audio",
    )
    generate.add_argument("--voice", default="pl-PL-ZofiaNeural", help="Voice name for synthesis")
    generate.add_argument("--rate", default="+0%", help="Speech rate, e.g. -15%% or +10%%")
    generate.add_argument("--pitch", default="+0Hz", help="Speech pitch, e.g. +0Hz")
    generate.add_argument("--volume", default="+0%", help="Speech volume, e.g. +0%%")
    generate.add_argument("--output-dir", default="output", help="Directory for generated files")
    generate.add_argument("--limit", type=int, default=None, help="Only generate the first N selected audio items")
    generate.add_argument("--profile-file", default=None, help="Optional JSON file with content/profile replacements")
    generate.add_argument(
        "--pronunciation-file",
        default=None,
        help="Optional JSON file with pronunciation-only replacements applied to spoken audio text",
    )
    generate.add_argument(
        "--replacements-file",
        default=None,
        help="Backward-compatible alias for --profile-file",
    )
    generate.add_argument(
        "--keep-labels",
        action="store_true",
        help="Keep Q:/A: labels in spoken text instead of stripping them",
    )
    generate.add_argument("--study-language-name", default="Study language", help="Display name for the study language")
    generate.add_argument(
        "--reference-language-name",
        default="Reference language",
        help="Display name for the reference language",
    )
    generate.add_argument(
        "--dashboard-title",
        default="Everyday Conversation Practice",
        help="Title shown at the top of the generated dashboard",
    )
    generate.add_argument(
        "--dashboard-subtitle",
        default="Build confidence with common questions, useful answers, translations, flashcards, and audio.",
        help="Subtitle shown at the top of the generated dashboard",
    )
    generate.add_argument(
        "--dashboard-file-name",
        default="dashboard.html",
        help="Name of the dashboard HTML file written inside the output directory",
    )
    generate.add_argument(
        "--manifest-data-file-name",
        default="manifest-data.js",
        help="Name of the JS file that embeds the manifest bundle for local-file browsing",
    )
    generate.add_argument(
        "--skip-dashboard",
        action="store_true",
        help="Skip writing the dashboard HTML file",
    )
    return parser


def prepare_spoken(text: str, keep_labels: bool) -> str:
    if keep_labels:
        return text.strip()
    if text[:2].lower() in {"q:", "a:"}:
        return text[2:].strip()
    return text.strip()


def load_replacements(path: str | None) -> list[tuple[str, str]]:
    if not path:
        return []

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Replacements file must contain a JSON object of search-to-replacement pairs.")
    replacements = [(str(search), str(replace)) for search, replace in raw.items()]
    return sorted(replacements, key=lambda item: len(item[0]), reverse=True)


def apply_replacements(text: str, replacements: list[tuple[str, str]]) -> str:
    updated = text
    for search, replace in replacements:
        updated = updated.replace(search, replace)
    return updated


def select_items(entries: list[Entry], mode: str, keep_labels: bool) -> list[tuple[Entry, str, str]]:
    items: list[tuple[Entry, str, str]] = []
    for entry in entries:
        if mode in {"questions", "both"} and entry.question.strip():
            items.append((entry, "question", prepare_spoken(entry.question, keep_labels)))
        if mode in {"answers", "both"} and entry.answer.strip():
            items.append((entry, "answer", prepare_spoken(entry.answer, keep_labels)))
    return items


def select_aligned_items(aligned_entries: list[AlignedEntry], mode: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for aligned in aligned_entries:
        if mode in {"questions", "both"} and aligned.study.question.strip():
            items.append(
                {
                    "entry": aligned,
                    "kind": "question",
                    "study_text": aligned.study.question,
                    "reference_text": aligned.reference.question if aligned.reference else "",
                }
            )
        if mode in {"answers", "both"} and aligned.study.answer.strip():
            items.append(
                {
                    "entry": aligned,
                    "kind": "answer",
                    "study_text": aligned.study.answer,
                    "reference_text": aligned.reference.answer if aligned.reference else "",
                }
            )
    return items


def resolve_study_column(args: argparse.Namespace) -> int:
    return args.column if args.column is not None else args.study_column


def resolve_reference_column(args: argparse.Namespace) -> int | None:
    return None if args.reference_column < 0 else args.reference_column


def resolve_profile_file(args: argparse.Namespace) -> str | None:
    return args.profile_file or args.replacements_file


def build_manifest_bundle(args: argparse.Namespace) -> tuple[dict[str, Any], list[tuple[str, Path]]]:
    input_path = Path(args.input_file)
    study_column = resolve_study_column(args)
    reference_column = resolve_reference_column(args)
    aligned_entries = align_entries(input_path, study_column=study_column, reference_column=reference_column)
    selected_items = select_aligned_items(aligned_entries, mode=args.mode)

    if args.limit is not None:
        selected_items = selected_items[: args.limit]

    profile_replacements = load_replacements(resolve_profile_file(args))
    pronunciation_replacements = load_replacements(args.pronunciation_file)
    output_dir = Path(args.output_dir)
    jobs: list[tuple[str, Path]] = []
    items: list[dict[str, Any]] = []

    for ordinal, selected in enumerate(selected_items, start=1):
        aligned = selected["entry"]
        kind = selected["kind"]
        raw_study_text = selected["study_text"]
        raw_reference_text = selected["reference_text"]
        display_study_text = apply_replacements(raw_study_text, profile_replacements)
        display_reference_text = apply_replacements(raw_reference_text, profile_replacements)
        display_text = prepare_spoken(display_study_text, keep_labels=False)
        translation_text = prepare_spoken(display_reference_text, keep_labels=False) if display_reference_text else ""
        spoken_text = prepare_spoken(display_study_text, keep_labels=args.keep_labels)
        spoken_text = apply_replacements(spoken_text, pronunciation_replacements)
        file_name = f"{ordinal:04d}-entry-{aligned.index:04d}-{kind}.mp3"
        relative_output = Path("audio") / file_name
        absolute_output = output_dir / relative_output
        jobs.append((spoken_text, absolute_output))
        items.append(
            {
                "ordinal": ordinal,
                "entry_index": aligned.index,
                "kind": kind,
                "display_text": display_text,
                "translation_text": translation_text,
                "spoken_text": spoken_text,
                "text": spoken_text,
                "original_text": prepare_spoken(raw_study_text, keep_labels=args.keep_labels),
                "original_reference_text": prepare_spoken(raw_reference_text, keep_labels=False) if raw_reference_text else "",
                "display_question": apply_replacements(aligned.study.question, profile_replacements),
                "display_answer": apply_replacements(aligned.study.answer, profile_replacements),
                "reference_question": apply_replacements(aligned.reference.question, profile_replacements) if aligned.reference else "",
                "reference_answer": apply_replacements(aligned.reference.answer, profile_replacements) if aligned.reference else "",
                "source_question": apply_replacements(aligned.study.question, profile_replacements),
                "source_answer": apply_replacements(aligned.study.answer, profile_replacements),
                "output_file": relative_output.as_posix(),
                "output_file_from_repo_root": (output_dir.name + "/" + relative_output.as_posix()),
            }
        )

    bundle = {
        "meta": {
            "schema_version": "2.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input_file": str(input_path),
            "study_column": study_column,
            "reference_column": reference_column,
            "mode": args.mode,
            "voice": args.voice,
            "study_language_name": args.study_language_name,
            "reference_language_name": args.reference_language_name,
            "dashboard_title": args.dashboard_title,
            "dashboard_subtitle": args.dashboard_subtitle,
            "output_dir_name": output_dir.name,
            "profile_file": resolve_profile_file(args),
            "pronunciation_file": args.pronunciation_file,
            "entry_count": len({item['entry_index'] for item in items}),
            "item_count": len(items),
        },
        "items": items,
    }
    return bundle, jobs


def generate_audio(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle, jobs = build_manifest_bundle(args)

    run_synthesis(
        jobs,
        TTSConfig(
            voice=args.voice,
            rate=args.rate,
            pitch=args.pitch,
            volume=args.volume,
        ),
    )

    manifest_path = output_dir / "manifest.json"
    manifest_data_path = output_dir / args.manifest_data_file_name
    write_manifest_bundle(manifest_path, bundle)
    write_manifest_data_js(manifest_data_path, bundle)

    if not args.skip_dashboard:
        write_dashboard_html(output_dir / args.dashboard_file_name, default_manifest_label=manifest_path.name)

    print(f"Generated {len(jobs)} audio files in {output_dir / 'audio'}")
    print(f"Manifest bundle written to {manifest_path}")
    print(f"Embedded manifest data written to {manifest_data_path}")
    if not args.skip_dashboard:
        print(f"Dashboard written to {output_dir / args.dashboard_file_name}")
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "generate":
        return generate_audio(args)

    parser.error("Unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
