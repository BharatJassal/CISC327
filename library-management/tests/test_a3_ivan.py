"""
File:        tests/test_a3_ivan.py
Author:      Ivan Lin (20483619), Group 9
Description: Assignment 3 tests for Member A.
             1. Overdue reminder (POST /loans/<id>/remind), success path:
                a stub returning True and a mock checking the recipient,
                subject and message, plus error cases.
             2. Coverage-directed tests for loans.py lines 70, 72, 82
                and members.py line 35 from the baseline report.
"""

from datetime import date, timedelta
from unittest.mock import patch

import notification_service
from app import store

SEND = "app.routes.loans.send_notification"   # patch where loans.py uses it


def make_book(client, title="Clean Code", isbn="111", copies=1):
    return client.post("/books", json={
        "title": title, "author": "Robert Martin", "isbn": isbn, "total_copies": copies,
    }).get_json()


def make_member(client, name="Ann Lee", email="ann@example.com"):
    return client.post("/members", json={"name": name, "email": email}).get_json()


def make_overdue_loan(client, days_late=3, title="Clean Code"):
    book = make_book(client, title=title)
    member = make_member(client)
    loan = client.post("/loans", json={"book_id": book["id"], "member_id": member["id"]}).get_json()
    store.loans[loan["id"]].due_date = date.today() - timedelta(days=days_late)
    return loan["id"], book, member


# ---------------- Overdue reminder: success path ----------------

def test_overdue_reminder_reports_sent_and_marks_loan(client, monkeypatch):
    """Stub: the service succeeds, so the app reports it and records the reminder date."""
    monkeypatch.setattr(SEND, lambda recipient, subject, message: True)
    loan_id, _, _ = make_overdue_loan(client, days_late=3)

    response = client.post(f"/loans/{loan_id}/remind")

    assert response.status_code == 200
    body = response.get_json()
    assert body["notified"] is True
    assert body["days_overdue"] == 3
    assert body["last_reminder_date"] == date.today().isoformat()
    saved = client.get(f"/loans?book_id={store.loans[loan_id].book_id}").get_json()[0]
    assert saved["last_reminder_date"] == date.today().isoformat()


def test_overdue_reminder_sends_expected_notification(client):
    """Mock: called once with the member's email, the subject and the full message."""
    loan_id, _, _ = make_overdue_loan(client, days_late=5, title="Dune")
    due = (date.today() - timedelta(days=5)).isoformat()

    with patch(SEND, return_value=True) as mock_send:
        response = client.post(f"/loans/{loan_id}/remind")

    assert response.status_code == 200
    assert response.get_json()["notified"] is True
    mock_send.assert_called_once_with(
        "ann@example.com",
        "Overdue book reminder",
        f"Hi Ann Lee, 'Dune' was due on {due} and is 5 day(s) overdue. Please return it.",
    )


def test_reminder_one_day_overdue_is_sent(client):
    """Boundary: one day past the due date already counts as overdue."""
    loan_id, _, _ = make_overdue_loan(client, days_late=1)

    with patch(SEND, return_value=True) as mock_send:
        response = client.post(f"/loans/{loan_id}/remind")

    assert response.get_json()["days_overdue"] == 1
    assert response.get_json()["notified"] is True
    mock_send.assert_called_once()


def test_reminder_uses_book_id_when_book_was_deleted(client):
    """The reminder still goes out if the book record was deleted while on loan."""
    loan_id, book, _ = make_overdue_loan(client, days_late=2)
    client.delete(f"/books/{book['id']}")

    with patch(SEND, return_value=True) as mock_send:
        response = client.post(f"/loans/{loan_id}/remind")

    assert response.get_json()["notified"] is True
    message = mock_send.call_args.args[2]
    assert f"'Book #{book['id']}'" in message


def test_reminder_is_recorded_by_real_simulator_with_prefix(client):
    """No double: the customized simulator records the reminder with the [City Library] prefix."""
    notification_service.clear_notifications()
    loan_id, _, _ = make_overdue_loan(client, days_late=2)

    response = client.post(f"/loans/{loan_id}/remind")

    assert response.get_json()["notified"] is True
    records = notification_service.get_notifications()
    assert len(records) == 1
    assert records[0]["recipient"] == "ann@example.com"
    assert records[0]["subject"] == "[City Library] Overdue book reminder"
    notification_service.clear_notifications()


# ---------------- Overdue reminder: error cases ----------------

def test_reminder_for_unknown_loan_returns_404_and_sends_nothing(client):
    with patch(SEND) as mock_send:
        response = client.post("/loans/999/remind")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Loan not found"
    mock_send.assert_not_called()


def test_reminder_for_deleted_member_returns_404_and_sends_nothing(client):
    loan_id, _, member = make_overdue_loan(client)
    client.delete(f"/members/{member['id']}")

    with patch(SEND) as mock_send:
        response = client.post(f"/loans/{loan_id}/remind")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Member not found"
    assert store.loans[loan_id].last_reminder_date is None
    mock_send.assert_not_called()


# ---------------- Coverage-directed: loans.py and members.py ----------------

def test_renew_unknown_loan_returns_404(client):
    """loans.py line 70."""
    response = client.put("/loans/999/renew")
    assert response.status_code == 404
    assert response.get_json()["error"] == "Loan not found"


def test_renew_returned_loan_is_rejected_and_due_date_unchanged(client):
    """loans.py line 72."""
    loan_id, _, _ = make_overdue_loan(client, days_late=0)
    client.put(f"/loans/{loan_id}/return")
    due_before = store.loans[loan_id].due_date

    response = client.put(f"/loans/{loan_id}/renew")

    assert response.status_code == 400
    assert response.get_json()["error"] == "Loan already returned"
    assert store.loans[loan_id].due_date == due_before


def test_renew_active_loan_extends_due_date_by_one_period(client):
    """Normal case for renew, next to the two error branches above."""
    loan_id, _, _ = make_overdue_loan(client, days_late=0)
    due_before = store.loans[loan_id].due_date

    response = client.put(f"/loans/{loan_id}/renew")

    assert response.status_code == 200
    expected = due_before + timedelta(days=14)
    assert response.get_json()["due_date"] == expected.isoformat()


def test_fine_for_unknown_loan_returns_404(client):
    """loans.py line 82."""
    response = client.get("/loans/999/fine")
    assert response.status_code == 404
    assert response.get_json()["error"] == "Loan not found"


def test_update_unknown_member_returns_404_and_creates_nothing(client):
    """members.py line 35."""
    response = client.put("/members/999", json={"name": "Ghost"})

    assert response.status_code == 404
    assert response.get_json()["error"] == "Member not found"
    assert client.get("/members").get_json() == []