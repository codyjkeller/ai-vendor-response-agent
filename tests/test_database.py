import pytest
from sqlalchemy.exc import IntegrityError

from database import AnswerBank, Document, User, init_db


def test_init_db_is_idempotent():
    init_db()
    init_db()


def test_answer_bank_round_trip(db_session):
    db_session.add(AnswerBank(question="Q?", answer="A.", product="P", subsidiary="S",
                              verified_by="tester", date_added="2026-01-01"))
    db_session.commit()

    row = db_session.query(AnswerBank).one()
    assert (row.question, row.answer, row.product, row.subsidiary) == ("Q?", "A.", "P", "S")


def test_user_email_is_unique(db_session):
    db_session.add(User(email="a@example.com"))
    db_session.commit()
    db_session.add(User(email="a@example.com"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_document_filename_is_unique(db_session):
    db_session.add(Document(filename="policy.pdf"))
    db_session.commit()
    db_session.add(Document(filename="policy.pdf"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_user_role_defaults_to_viewer(db_session):
    db_session.add(User(email="b@example.com"))
    db_session.commit()
    assert db_session.query(User).one().role == "Viewer"
