from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable

LABEL_RE = re.compile(r"^(?P<label>[A-Za-zÀ-ÿ]+):\s*")
SEPARATOR_RE = re.compile(r"^\s*\|\s*$")


@dataclass(slots=True)
class Segment:
    kind: str
    text: str
    source_lines: list[str]

    def spoken_text(self, strip_labels: bool = True) -> str:
        text = self.text.strip()
        if strip_labels:
            text = LABEL_RE.sub("", text)
        return normalize_whitespace(text)


@dataclass(slots=True)
class Entry:
    index: int
    question: str = ""
    answer: str = ""
    other: list[str] | None = None

    def combined(self) -> str:
        parts = [part for part in [self.question, self.answer] if part.strip()]
        return " ".join(parts).strip()

    def to_manifest_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["combined"] = self.combined()
        return data


@dataclass(slots=True)
class AlignedEntry:
    index: int
    study: Entry
    reference: Entry | None = None


def normalize_whitespace(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def load_json_deck(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON deck must contain a top-level JSON object.")
    if not isinstance(payload.get("entries"), list):
        raise ValueError("JSON deck must contain an 'entries' array.")
    return payload


def get_json_language_order(payload: dict[str, Any]) -> list[str]:
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("JSON deck must contain a 'meta' object.")
    language_order = meta.get("language_order")
    if not isinstance(language_order, list) or not language_order or not all(isinstance(item, str) for item in language_order):
        raise ValueError("JSON deck meta must contain a non-empty 'language_order' string array.")
    return language_order


def extract_localized_text(value: Any, language_code: str) -> str:
    if not isinstance(value, dict):
        return ""
    return normalize_whitespace(str(value.get(language_code, "")))


def extract_localized_other(value: Any, language_code: str) -> list[str] | None:
    if not isinstance(value, dict):
        return None

    localized_value = value.get(language_code)
    if isinstance(localized_value, list):
        extracted = [normalize_whitespace(str(item)) for item in localized_value if str(item).strip()]
        return extracted or None
    if isinstance(localized_value, str) and localized_value.strip():
        return [normalize_whitespace(localized_value)]
    return None


def parse_json_entries(payload: dict[str, Any], column: int = 0) -> list[Entry]:
    language_order = get_json_language_order(payload)
    if column >= len(language_order):
        raise ValueError(
            f"Requested language column {column} but JSON deck only defines {len(language_order)} language(s)."
        )

    language_code = language_order[column]
    entries: list[Entry] = []

    for index, raw_entry in enumerate(payload.get("entries", []), start=1):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"JSON deck entry {index} must be an object.")

        question_map = raw_entry.get("question") if "question" in raw_entry else raw_entry.get("q")
        answer_map = raw_entry.get("answer") if "answer" in raw_entry else raw_entry.get("a")
        other_map = raw_entry.get("other")

        question = extract_localized_text(question_map, language_code)
        answer = extract_localized_text(answer_map, language_code)
        other = extract_localized_other(other_map, language_code)

        entries.append(Entry(index=index, question=question, answer=answer, other=other))

    return entries


def split_columns(raw_line: str) -> list[str]:
    return [part.strip() for part in raw_line.split("|")]


def extract_column(line: str, column: int) -> str:
    columns = split_columns(line.rstrip("\n"))
    if column >= len(columns):
        return ""
    return columns[column].strip()


def parse_segments(lines: Iterable[str], column: int = 0) -> list[Segment]:
    segments: list[Segment] = []
    current_kind: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_kind, current_lines
        if not current_kind or not current_lines:
            current_kind = None
            current_lines = []
            return
        raw = normalize_whitespace(" ".join(current_lines))
        segments.append(Segment(kind=current_kind, text=raw, source_lines=current_lines.copy()))
        current_kind = None
        current_lines = []

    for raw_line in lines:
        line = extract_column(raw_line, column)
        if not line or SEPARATOR_RE.match(line):
            flush()
            continue

        match = LABEL_RE.match(line)
        if match:
            flush()
            current_kind = match.group("label").lower()
            current_lines = [line]
        elif current_kind:
            current_lines.append(line)
        else:
            current_kind = "other"
            current_lines = [line]

    flush()
    return segments


def parse_entries(lines: Iterable[str], column: int = 0) -> list[Entry]:
    segments = parse_segments(lines, column=column)
    entries: list[Entry] = []
    pending_question = ""
    pending_answer = ""
    pending_other: list[str] = []

    def flush_entry() -> None:
        nonlocal pending_question, pending_answer, pending_other
        if not any([pending_question.strip(), pending_answer.strip(), pending_other]):
            return
        entries.append(
            Entry(
                index=len(entries) + 1,
                question=normalize_whitespace(pending_question),
                answer=normalize_whitespace(pending_answer),
                other=pending_other.copy() or None,
            )
        )
        pending_question = ""
        pending_answer = ""
        pending_other = []

    for segment in segments:
        spoken = segment.spoken_text(strip_labels=False)
        if segment.kind == "q":
            if pending_question or pending_answer or pending_other:
                flush_entry()
            pending_question = spoken
        elif segment.kind == "a":
            if pending_answer:
                flush_entry()
            pending_answer = spoken
        else:
            pending_other.append(spoken)

    flush_entry()
    return entries


def load_entries(path: str | Path, column: int = 0) -> list[Entry]:
    file_path = Path(path)
    if file_path.suffix.lower() == ".json":
        return parse_json_entries(load_json_deck(file_path), column=column)
    return parse_entries(file_path.read_text(encoding="utf-8").splitlines(), column=column)


def align_entries(path: str | Path, study_column: int = 0, reference_column: int | None = 1) -> list[AlignedEntry]:
    study_entries = load_entries(path, column=study_column)

    if reference_column is None:
        return [AlignedEntry(index=entry.index, study=entry, reference=None) for entry in study_entries]

    reference_entries = load_entries(path, column=reference_column)
    if len(study_entries) != len(reference_entries):
        raise ValueError(
            "Study and reference columns produced a different number of entries. "
            "Check the source file structure or choose a different column pair."
        )

    aligned: list[AlignedEntry] = []
    for study_entry, reference_entry in zip(study_entries, reference_entries, strict=True):
        aligned.append(
            AlignedEntry(
                index=study_entry.index,
                study=study_entry,
                reference=reference_entry,
            )
        )
    return aligned


def write_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_manifest(path: str | Path, entries: list[dict[str, Any]]) -> None:
    write_json(path, entries)
