from __future__ import annotations
import random
from dataclasses import dataclass
from typing import List

VOWELS = "aeiouy"
CONSONANTS = "bcdfghjklmnpqrstvwxz"

DEFAULT_SYLLABLES = [
    "an","ar","ba","bel","cor","dar","del","dor","el","en","far","fen","gar","hal","iv",
    "ka","kel","kor","lan","lor","mor","nel","nor","or","per","quin","ran","rel","sar",
    "sel","sha","tor","ul","val","vor","wen","yor","zan"
]

@dataclass
class NameGenConfig:
    style: str = "Fantasy"
    count: int = 50
    min_syllables: int = 2
    max_syllables: int = 4
    allow_apostrophes: bool = False
    capitalize: bool = True
    seed: int | None = None

def _pick_syllable(rng: random.Random, style: str) -> str:
    # Simple style knobs. Expand later with grammars/markov/culture packs.
    if style == "Guttural":
        base = ["gr", "kr", "zg", "uk", "rag", "mog", "dur", "gar", "th", "zor", "rak", "mok"]
        return rng.choice(base)
    if style == "Elven":
        base = ["ae", "ia", "li", "ri", "el", "thil", "syl", "mir", "loth", "enya", "fina", "vara"]
        return rng.choice(base)
    if style == "Dwarven":
        base = ["grim", "bar", "dur", "kaz", "gor", "thar", "brun", "kund", "bald", "orn", "dun"]
        return rng.choice(base)
    # Default fantasy syllables
    return rng.choice(DEFAULT_SYLLABLES)

def _maybe_apostrophe(rng: random.Random) -> str:
    return "'" if rng.random() < 0.15 else ""

def generate_names(cfg: NameGenConfig, rng: random.Random | None = None) -> List[str]:
    rng = rng or random.Random()
    if cfg.seed is not None:
        rng.seed(cfg.seed)

    out: List[str] = []
    for _ in range(max(1, cfg.count)):
        syl_count = rng.randint(cfg.min_syllables, cfg.max_syllables)
        parts = [_pick_syllable(rng, cfg.style) for _ in range(syl_count)]

        name = "".join(parts)

        if cfg.allow_apostrophes and len(name) >= 6:
            # insert apostrophe somewhere near middle
            i = rng.randint(2, len(name) - 3)
            name = name[:i] + _maybe_apostrophe(rng) + name[i:]

        # quick cleanup: avoid triple vowels
        while any(name[i] in VOWELS and name[i+1] in VOWELS and name[i+2] in VOWELS for i in range(len(name)-2)):
            # tweak by swapping one char to consonant
            j = rng.randint(0, len(name)-1)
            name = name[:j] + rng.choice(CONSONANTS) + name[j+1:]

        if cfg.capitalize:
            name = name[:1].upper() + name[1:]

        out.append(name)

    return out
