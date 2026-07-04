from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import edge_tts


@dataclass(slots=True)
class TTSConfig:
    voice: str = "pl-PL-ZofiaNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"


async def synthesize_text(text: str, output_file: Path, config: TTSConfig) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(
        text=text,
        voice=config.voice,
        rate=config.rate,
        pitch=config.pitch,
        volume=config.volume,
    )
    await communicate.save(str(output_file))


async def synthesize_many(items: Iterable[tuple[str, Path]], config: TTSConfig) -> None:
    for text, output_file in items:
        await synthesize_text(text, output_file, config)


def run_synthesis(items: Iterable[tuple[str, Path]], config: TTSConfig) -> None:
    asyncio.run(synthesize_many(items, config))
