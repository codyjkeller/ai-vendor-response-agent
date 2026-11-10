"""Input-handling helpers: filenames, spreadsheet cells, and the audit log."""
import csv
import os
import re
from datetime import datetime

from config import ALLOWED_UPLOAD_EXTENSIONS

AUDIT_LOG_HEADER = ["Timestamp", "User", "Action", "Details"]

# A cell that starts with one of these is evaluated as a formula by Excel and
# other spreadsheet tools.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

_SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._ ()-]")


def sanitize_filename(name):
    """Returns a filename that is safe to join onto the data directory.

    Raises ValueError when nothing usable is left or the type is not allowed.
    """
    # Browsers may send either separator; keep the last path component only.
    base = str(name).replace("\\", "/").split("/")[-1]
    base = _SAFE_FILENAME_CHARS.sub("_", base).strip(" .")
    if not base:
        raise ValueError("Invalid file name.")
    extension = base.rsplit(".", 1)[-1].lower() if "." in base else ""
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {base}")
    return base


def safe_data_path(data_dir, filename):
    """Joins filename onto data_dir and confirms the result stays inside it."""
    root = os.path.realpath(data_dir)
    path = os.path.realpath(os.path.join(root, sanitize_filename(filename)))
    if os.path.commonpath([root, path]) != root:
        raise ValueError("Invalid file path.")
    return path


def neutralize_formula(value):
    """Prefixes text that a spreadsheet would run as a formula with an apostrophe."""
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def append_audit_log(path, user, action, details):
    """Appends one properly quoted row to the audit log CSV."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        if is_new:
            writer.writerow(AUDIT_LOG_HEADER)
        writer.writerow([
            timestamp,
            neutralize_formula(_single_line(user)),
            neutralize_formula(_single_line(action)),
            neutralize_formula(_single_line(details)),
        ])


def _single_line(value):
    return " ".join(str(value).split())
