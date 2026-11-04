"""Name the models in a finished consensus report, after the consensus agent is done.

The agent only ever sees run IDs. This writes consensus_unblinded.html beside the blinded
consensus.html, with each run ID replaced by its model name.
"""
import json
import re
from collections import Counter
from pathlib import Path

BLINDED = "consensus.html"
UNBLINDED = "consensus_unblinded.html"
MAPPING = "run_models.json"
# A run ID inside a path, a longer identifier or a base64 blob is left alone.
TOKEN_CHARS = r"A-Za-z0-9+/=_\-"


def display_names(mapping: dict[str, str]) -> dict[str, str]:
    """run_id -> model; a model that audited more than once keeps its run ID beside it."""
    counts = Counter(mapping.values())
    return {run: model if counts[model] == 1 else f"{model} ({run})" for run, model in mapping.items()}


def unblind_text(text: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return text
    names = display_names(mapping)
    ids = "|".join(re.escape(r) for r in sorted(names, key=len, reverse=True))
    pattern = re.compile(rf"(?<![{TOKEN_CHARS}])(?:{ids})(?![{TOKEN_CHARS}])")
    return pattern.sub(lambda m: names[m.group(0)], text)


def unblind_report(consensus_dir: Path) -> Path:
    consensus_dir = Path(consensus_dir)
    mapping = json.loads((consensus_dir / MAPPING).read_text(encoding="utf-8"))
    text = (consensus_dir / BLINDED).read_text(encoding="utf-8")
    out = consensus_dir / UNBLINDED
    out.write_text(unblind_text(text, mapping), encoding="utf-8")
    return out
