import csv
import os

import pytest

import security


@pytest.mark.parametrize("raw, expected", [
    ("policy.pdf", "policy.pdf"),
    ("../../etc/passwd.txt", "passwd.txt"),
    ("..\\..\\windows\\system.txt", "system.txt"),
    ("/abs/path/report.PDF", "report.PDF"),
    ("SOC 2 (2026).pdf", "SOC 2 (2026).pdf"),
    ("bad<name>;rm -rf.txt", "bad_name__rm -rf.txt"),
])
def test_sanitize_filename(raw, expected):
    assert security.sanitize_filename(raw) == expected


@pytest.mark.parametrize("raw", ["", "..", "../", "notes.md", "run.exe", "archive.pdf.exe", "noextension"])
def test_sanitize_filename_rejects(raw):
    with pytest.raises(ValueError):
        security.sanitize_filename(raw)


def test_safe_data_path_stays_inside_data_dir(tmp_path):
    path = security.safe_data_path(str(tmp_path), "../../outside.txt")
    assert os.path.dirname(path) == os.path.realpath(str(tmp_path))
    assert os.path.basename(path) == "outside.txt"


@pytest.mark.parametrize("raw, expected", [
    ("Yes, MFA is enforced.", "Yes, MFA is enforced."),
    ("=HYPERLINK(\"http://x\")", "'=HYPERLINK(\"http://x\")"),
    ("+1", "'+1"),
    ("-1", "'-1"),
    ("@SUM(A1)", "'@SUM(A1)"),
    (None, ""),
])
def test_neutralize_formula(raw, expected):
    assert security.neutralize_formula(raw) == expected


def test_audit_log_is_quoted_and_single_line(tmp_path):
    log = tmp_path / "audit_log.csv"
    security.append_audit_log(str(log), "a@example.com", "QUERY_AI", 'one, two\n"three"')
    security.append_audit_log(str(log), "a@example.com", "QUERY_AI", "=cmd|' /C calc'!A0")

    with open(log, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == security.AUDIT_LOG_HEADER
    assert len(rows) == 3
    assert rows[1][1:] == ["a@example.com", "QUERY_AI", 'one, two "three"']
    assert rows[2][3].startswith("'=")
