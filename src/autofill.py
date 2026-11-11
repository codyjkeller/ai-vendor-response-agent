"""Fills the answer column of a questionnaire worksheet."""
from security import neutralize_formula

# Only these results are written into a questionnaire by Auto-Fill.
FILLABLE_STATUSES = ("✅ Verified (Bank)", "🤖 AI Generated")


def fill_worksheet(ws, agent, q_idx, a_idx, product=None, subsidiary=None, on_progress=None):
    """Answers each question row in ws and returns one review record per question.

    q_idx and a_idx are zero-based column positions. Only real answers are
    written. "Review Required", search-only and error results leave the cell
    untouched so that tool messages never reach the assessor.
    """
    review_rows = []
    for i, row in enumerate(ws.iter_rows(min_row=2), 2):
        q_txt = str(row[q_idx].value) if row[q_idx].value else ""
        if len(q_txt) > 5:
            resp = agent.generate_responses([q_txt], product=product, subsidiary=subsidiary)
            if not resp.empty:
                status = resp.iloc[0]['Status']
                if status in FILLABLE_STATUSES:
                    ws.cell(row=i, column=a_idx+1, value=neutralize_formula(resp.iloc[0]['AI_Response']))
                ev = resp.iloc[0].get('Evidence')
                review_rows.append({
                    "Row": i,
                    "Question": q_txt,
                    "Result": status if status in FILLABLE_STATUSES else f"Left blank ({status})",
                    "Evidence": ev if isinstance(ev, str) else "",
                })
        if on_progress:
            on_progress(min(i/ws.max_row, 1.0))
    return review_rows
