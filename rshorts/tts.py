"""Text-to-speech with word-level timestamps (for synced captions).

Engines:
  edge   - Microsoft Edge neural voices (free, online, very natural). Default.
  kokoro - Kokoro-82M, runs fully offline on CPU (~330 MB model, auto-downloaded).
"""
from __future__ import annotations

import asyncio
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from .text import sentences

SR = 24000
ROOT = Path(__file__).resolve().parent.parent

EDGE_VOICES = {
    "christopher": "en-US-ChristopherNeural",  # deep, serious male - classic story voice
    "guy": "en-US-GuyNeural",
    "andrew": "en-US-AndrewNeural",            # warm, natural male
    "brian": "en-US-BrianNeural",
    "eric": "en-US-EricNeural",
    "aria": "en-US-AriaNeural",                # expressive female
    "jenny": "en-US-JennyNeural",
    "ava": "en-US-AvaNeural",
    "emma": "en-US-EmmaNeural",
    "ryan": "en-GB-RyanNeural",                # British male
    "sonia": "en-GB-SoniaNeural",
}
KOKORO_VOICES = ["am_michael", "am_adam", "am_onyx", "am_fenrir", "am_puck", "bm_george", "bm_fable",
                 "af_heart", "af_bella", "af_nicole", "af_sarah", "bf_emma"]


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Speech:
    audio: np.ndarray  # mono float32 @ SR
    words: list[Word]

    @property
    def duration(self) -> float:
        return len(self.audio) / SR


def _silence(sec: float) -> np.ndarray:
    return np.zeros(int(sec * SR), dtype=np.float32)


def concat(chunks: list[Speech | float]) -> tuple[Speech, list[float]]:
    """Join Speech objects / silence gaps; returns combined speech and start offset of each item."""
    audio, words, offsets, t = [], [], [], 0.0
    for c in chunks:
        offsets.append(t)
        if isinstance(c, (int, float)):
            a = _silence(c)
        else:
            a = c.audio
            words += [Word(w.start + t, w.end + t, w.text) for w in c.words]
        audio.append(a)
        t += len(a) / SR
    return Speech(np.concatenate(audio).astype(np.float32), words), offsets


# --------------------------------------------------------------------- edge
def _edge(text: str, voice: str, rate: str, pitch: str) -> Speech:
    import edge_tts

    voice = EDGE_VOICES.get(voice.lower(), voice)

    async def run():
        com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
        audio, words = bytearray(), []
        async for ch in com.stream():
            if ch["type"] == "audio":
                audio += ch["data"]
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append(Word(s, s + ch["duration"] / 1e7, ch["text"]))
        return bytes(audio), words

    mp3, words = asyncio.run(run())
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td, "a.mp3"), Path(td, "a.wav")
        src.write_bytes(mp3)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", str(SR), str(dst)],
                       check=True)
        audio, _ = sf.read(dst, dtype="float32")
    _attach_punctuation(text, words)
    return Speech(audio, words)


def _attach_punctuation(text: str, words: list[Word]):
    """Edge returns bare words; re-attach the punctuation from the source text for nicer captions."""
    pos = 0
    for w in words:
        i = text.find(w.text, pos)
        if i < 0:
            continue
        j = i + len(w.text)
        m = re.match(r"[^\s]*", text[j:])
        tail = m.group(0) if m else ""
        w.text = w.text + tail
        pos = j + len(tail)


# ------------------------------------------------------------------- kokoro
_kokoro = None


def _get_kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro

        mdir = ROOT / "models"
        mdir.mkdir(exist_ok=True)
        files = {
            "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
            "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
        }
        for name, url in files.items():
            if not (mdir / name).exists():
                import requests

                print(f"  downloading {name} (one time)...")
                with requests.get(url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(mdir / (name + ".part"), "wb") as f:
                        for b in r.iter_content(1 << 20):
                            f.write(b)
                (mdir / (name + ".part")).rename(mdir / name)
        _kokoro = Kokoro(str(mdir / "kokoro-v1.0.onnx"), str(mdir / "voices-v1.0.bin"))
    return _kokoro


def _estimate_words(sentence: str, audio: np.ndarray) -> list[Word]:
    """Kokoro has no timestamps: spread words over the voiced region weighted by length + pauses."""
    env = np.abs(audio)
    voiced = np.where(env > 0.02 * (env.max() or 1))[0]
    a, b = (voiced[0] / SR, voiced[-1] / SR) if len(voiced) else (0.0, len(audio) / SR)
    toks = sentence.split()
    weights, pauses = [], []
    for tk in toks:
        core = re.sub(r"[^\w']", "", tk)
        weights.append(max(len(core), 1) + 1.5 + (3 if any(ch.isdigit() for ch in core) else 0))
        pauses.append(4 if re.search(r"[,;:\-]$", tk) else 6 if re.search(r"[.!?]$", tk) else 0)
    pauses[-1] = 0
    total = sum(weights) + sum(pauses)
    unit = (b - a) / total if total else 0
    t, out = a, []
    for tk, w, p in zip(toks, weights, pauses):
        out.append(Word(t, t + w * unit, tk))
        t += (w + p) * unit
    return out


def _kokoro_tts(text: str, voice: str, speed: float) -> Speech:
    k = _get_kokoro()
    chunks: list[Speech | float] = []
    for s in sentences(text):
        if not re.search(r"\w", s):
            continue
        audio, sr = k.create(s, voice=voice, speed=speed, lang="en-gb" if voice[0] == "b" else "en-us")
        audio = audio.astype(np.float32)
        if sr != SR:
            raise RuntimeError(f"unexpected sample rate {sr}")
        chunks += [Speech(audio, _estimate_words(s, audio)), 0.05]
    return concat(chunks)[0]


# ---------------------------------------------------------------------- api
def synthesize(text: str, engine: str = "edge", voice: str = "christopher", speed: float = 1.1) -> Speech:
    if engine == "edge":
        rate = f"{round((speed - 1) * 100):+d}%"
        return _edge(text, voice, rate, "+0Hz")
    if engine == "kokoro":
        return _kokoro_tts(text, voice if voice in KOKORO_VOICES else "am_michael", speed)
    raise ValueError(f"unknown engine {engine}")


def save_wav(speech: Speech, path: Path):
    peak = float(np.abs(speech.audio).max() or 1)
    sf.write(path, speech.audio * (0.95 / peak), SR)
