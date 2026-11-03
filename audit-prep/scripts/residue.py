# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Recognise residue (environments, caches, earlier audit output) and data-only directories."""
import os
from fnmatch import fnmatchcase
from pathlib import Path

# Matched on the basename, exactly or as a glob.
RESIDUE_PATTERNS = (
    ".git", ".venv", "venv", ".pytest_cache", "__pycache__", ".DS_Store", "renv", ".Rproj.user",
    ".Rhistory", ".quarto", "node_modules", ".ipynb_checkpoints", "audit-*", "*_files", "figs_paper",
    "*_audit.qmd", "*_audit.html", "osf_prereg",
)
DATA_SUFFIXES = (
    ".csv", ".tsv", ".json", ".mat", ".rds", ".rda", ".sav", ".nii", ".nii.gz", ".hdr", ".img",
    ".parquet", ".xlsx", ".txt", ".dat", ".h5", ".npy", ".zip",
)
IGNORED_FILES = {".DS_Store", "Icon\r"}


def is_residue_name(name: str) -> bool:
    return any(fnmatchcase(name, pattern) for pattern in RESIDUE_PATTERNS)


def is_data_file(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(DATA_SUFFIXES) or ".tar" in Path(lower).suffixes


def _files_under(folder: Path):
    for _, _, files in os.walk(folder):
        yield from (f for f in files if f not in IGNORED_FILES)


def is_data_only_dir(folder: Path) -> bool:
    """True when the directory holds at least one file and every file is data-like."""
    names = list(_files_under(folder))
    return bool(names) and all(is_data_file(n) for n in names)
