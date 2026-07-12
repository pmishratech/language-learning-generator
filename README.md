# language-learning-generator

A free CLI tool that reads pipe-delimited study material and generates multilingual audio, reusable manifests, and learner dashboards using `edge-tts`.

## What it does

- Parses files where each line contains multiple language columns separated by `|`
- Parses JSON lesson decks with reusable bilingual question/answer entries
- Treats one column as the study language and another as the reference/translation language
- Supports profile/content replacements separately from pronunciation-only overrides
- Generates one MP3 per spoken item
- Writes a reusable manifest bundle JSON file plus an embedded JS version for local viewing
- Generates a modern dashboard with search, filters, inline audio, and flashcard mode
- Still keeps the old `polish-tool` command working for backward compatibility

## Why this approach

This project uses `edge-tts` because it is the best practical free option for:

- good pronunciation across many languages
- neural voices such as `pl-PL-ZofiaNeural`, `en-US-AriaNeural`, and others
- no paid API keys
- easy setup

## Suggested repo structure

- `content/` — canonical lesson files
- `profiles/` — learner/persona/content overrides
- `pronunciation/` — speech-only phonetic tuning
- `output*/` — generated manifests, dashboards, and audio

The current sample files in the repo root still work, but the long-term direction is to place new material in those folders.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev]
```

## Basic usage

Generate audio + dashboard from the first two columns of the sample file:

```bash
language-dashboard generate Polish-English-pipe.txt \
  --study-language-name Polish \
  --reference-language-name English \
  --output-dir output-demo-pack
```

This creates audio plus dashboard assets under `output/`.

## Useful examples

Questions only:

```bash
language-dashboard generate Polish-English-pipe.txt --mode questions
```

Answers only:

```bash
language-dashboard generate Polish-English-pipe.txt --mode answers
```

Use a different voice:

```bash
language-dashboard generate Polish-English-pipe.txt --voice pl-PL-MarekNeural
```

Generate just a few files while testing:

```bash
language-dashboard generate Polish-English-pipe.txt --mode questions --limit 5
```

Choose different study and reference columns (zero-based index):

```bash
language-dashboard generate some-file.txt --study-column 0 --reference-column 1
```

Slower speaking rate for study practice:

```bash
language-dashboard generate Polish-English-pipe.txt --rate=-15%
```

Use content/profile replacements plus pronunciation tweaks:

```bash
language-dashboard generate Polish-English-pipe.txt \
  --profile-file profiles/demo-profile.json \
  --pronunciation-file pronunciation/examples/pl-PL.json \
  --output-dir output-demo-pack
```

Keep using the legacy command if you want:

```bash
polish-tool generate Polish-English-pipe.txt --study-language-name Polish --reference-language-name English --output-dir output-demo-pack
```

Generate a full multi-language site with a language chooser home page:

```bash
language-dashboard generate-site content/common-language-site.json
```

## Input format expected

The parser supports files like this:

- entries are grouped by blank lines and `|` separator lines
- each content line has `left-language|right-language`
- continuation lines are allowed
- labels like `Q:` and `A:` are preserved in parsing but stripped from spoken output by default
- additional labels still parse safely, which makes the format reusable for other lesson sets

Example:

```text
Q: Jak się masz?|Q: How are you?
A: Mam się dobrze.|A: I am fine.
|
Q: Gdzie mieszkasz?|Q: Where do you live?
A: Mieszkam w Krakowie.|A: I live in Krakow.
```

It also supports JSON decks like the new starter files in `content/`:

```json
{
  "meta": {
    "language_order": ["en", "hi"],
    "languages": {"en": "English", "hi": "Hindi"}
  },
  "entries": [
    {
      "id": "001",
      "q": {"en": "What is your full name?", "hi": "आपका पूरा नाम क्या है?"},
      "a": {"en": "My full name is {{full_name}}.", "hi": "मेरा पूरा नाम {{full_name}} है।"}
    }
  ]
}
```

Use `--study-column 0 --reference-column 1` for the first language in `language_order`, or swap them to reverse the spoken/translation side.

## Output

Inside `output/` you will get:

- `audio/0001-entry-0001-question.mp3` etc.
- `manifest.json` — schema v2 bundle with metadata + items
- `manifest-data.js` — embedded bundle for local HTML loading
- `dashboard.html` — searchable dashboard + flashcards

When using `generate-site`, you will also get:

- `index.html` — home page for choosing a deck/language
- `catalog.json` — site metadata and available decks
- `catalog-data.js` — embedded site catalog for the home page
- one dashboard folder per deck

## Manifest schema

The generated `manifest.json` now contains:

- `meta` — bundle metadata such as language names, voice, source file, and counts
- `items` — one record per generated audio item, including:
  - `display_text`
  - `translation_text`
  - `spoken_text`
  - `kind`
  - `entry_index`
  - `output_file`

This makes the output reusable for future dashboards, apps, or study workflows.

## Starter content added

The repo now includes reusable starter decks with placeholders for names, addresses, dates, and similar personal details:

- `content/common-english-hindi.json` — 100 English/Hindi Q&A pairs, which gives roughly 200 common study utterances
- `content/common-english-german.json` — 100 English/German Q&A pairs, also roughly 200 common study utterances
- `content/common-language-site.json` — ready-to-run site config with:
  - Hindi audio + English text visible on screen
  - German audio + English text visible on screen
  - existing Polish audio + English text visible on screen

The generated dashboards will automatically show a deck switcher when they are opened as part of a generated site.

If you already know English, the intended setup is:

- English stays visible on screen as the reference text
- Hindi, German, or Polish is the only spoken audio
- users click the target-language audio directly from the dashboard

## Notes

- `edge-tts` is online, but free to use for personal tooling.
- For best pronunciation, keep the canonical content correct in the original lesson file.
- Use `--profile-file` for semantic or learner-specific changes.
- Use `--pronunciation-file` only for TTS phonetics.
- Proper names from other languages may still need manual pronunciation adjustments.
