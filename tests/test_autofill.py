import openpyxl
import pandas as pd

import autofill


class ScriptedAgent:
    """Returns a fixed (answer, status) per question and records the scope it was given."""

    def __init__(self, script):
        self.script = script
        self.calls = []

    def generate_responses(self, questions, product=None, subsidiary=None):
        self.calls.append((questions[0], product, subsidiary))
        answer, status = self.script[questions[0]]
        row = {"Question": questions[0], "AI_Response": answer, "Status": status}
        if status != "❌ Failed":
            row["Evidence"] = "policy.pdf (Pg. 2)"
        return pd.DataFrame([row])


def make_sheet(questions):
    ws = openpyxl.Workbook().active
    ws.append(["Question", "Answer"])
    for q in questions:
        ws.append([q, None])
    return ws


def test_only_real_answers_are_written():
    script = {
        "Do you use MFA?": ("Yes, via Okta.", "✅ Verified (Bank)"),
        "Is data encrypted at rest?": ("AES-256.", "🤖 AI Generated"),
        "Do you have ISO 27001?": ("Review Required", "⚠️ Review"),
        "What is your RTO?": ("API Key Required for Answer", "🔍 Search Result"),
        "Who is your DPO?": ("Error: provider down", "❌ Failed"),
    }
    ws = make_sheet(list(script))
    rows = autofill.fill_worksheet(ws, ScriptedAgent(script), 0, 1)

    assert [ws.cell(row=r, column=2).value for r in range(2, 7)] == ["Yes, via Okta.", "AES-256.", None, None, None]
    assert [r["Result"] for r in rows] == [
        "✅ Verified (Bank)", "🤖 AI Generated",
        "Left blank (⚠️ Review)", "Left blank (🔍 Search Result)", "Left blank (❌ Failed)",
    ]
    assert rows[4]["Evidence"] == ""


def test_existing_answer_is_kept_when_result_needs_review():
    ws = make_sheet(["Do you have ISO 27001?"])
    ws.cell(row=2, column=2, value="Previously entered by hand")
    autofill.fill_worksheet(ws, ScriptedAgent({"Do you have ISO 27001?": ("Review Required", "⚠️ Review")}), 0, 1)
    assert ws.cell(row=2, column=2).value == "Previously entered by hand"


def test_formula_like_answer_is_neutralized():
    ws = make_sheet(["What is your uptime?"])
    autofill.fill_worksheet(ws, ScriptedAgent({"What is your uptime?": ("=1+1", "🤖 AI Generated")}), 0, 1)
    assert ws.cell(row=2, column=2).value == "'=1+1"


def test_short_and_empty_rows_are_skipped_and_scope_is_passed():
    ws = make_sheet(["N/A", None, "Do you use MFA?"])
    agent = ScriptedAgent({"Do you use MFA?": ("Yes.", "✅ Verified (Bank)")})
    progress = []
    rows = autofill.fill_worksheet(ws, agent, 0, 1, product="Alpha", subsidiary="EU", on_progress=progress.append)
    assert agent.calls == [("Do you use MFA?", "Alpha", "EU")]
    assert [r["Row"] for r in rows] == [4]
    assert progress[-1] == 1.0
