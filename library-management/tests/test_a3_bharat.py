"""
File: tests/test_a3_bharat.py
Author: Bharat Jassal (20463821), group 9
Description: Assignment 3 tests for Member B.
             1. Coverage-directed tests for the web UI in app/routes/views.py
                (baseline lines 15, 38-39, 44-49, 54-55, 75).
             2. Overdue reminder (POST /loans/<id>/remind), failure and
                non-trigger paths: a stub returning False and mocks checking
                that no notification is sent when the loan is not overdue.
"""

from datetime import date, timedelta
from unittest.mock import patch

import notification_service
from app import store

SEND = "app.routes.loans.send_notification"


def make_book(client, title="Clean Code", author="Robert Martin", isbn="111", copies=1):
    return client.post("/books", json={
        "title": title, "author": author, "isbn": isbn, "total_copies": copies,
    }).get_json()

def make_member(client, name="John Doe", email="john.doe@example.com"):
    return client.post("/members", json={"name": name, "email": email}).get_json()


def test_ui_home_page_links_to_books_members_and_loans(client):
    response = client.get("/")
    assert response.status_code == 200

    page = response.get_data(as_text=True)
    assert 'href="/ui/books"' in page
    assert 'href="/ui/members"' in page
    assert 'href="/ui/loans"' in page


def test_ui_delete_book_removes_it_and_redirects_to_books_page(client):
    keep = make_book(client, title="Dune", isbn="222")
    gone = make_book(client)

    response = client.post(f"/ui/books/{gone['id']}/delete")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/ui/books")

    assert client.get(f"/books/{gone['id']}").status_code == 404
    assert [b["title"] for b in client.get("/books").get_json()] == ["Dune"]
    assert keep["id"] != gone["id"]

def test_ui_delete_unknown_book_changes_nothing(client):
    make_book(client)

    response = client.post("/ui/books/999/delete")
    assert response.status_code == 302
    assert len(client.get("/books").get_json()) == 1



def test_ui_add_member_form_creates_member_and_lists_them(client):
    response = client.post("/ui/members", data={"name": "Jane Doe", "email": "jane.doe@example.com"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/ui/members")

    members = client.get("/members").get_json()
    assert len(members) == 1
    assert members[0]["name"] == "Jane Doe"
    assert members[0]["email"] == "jane.doe@example.com"
    assert members[0]["membership_date"] == date.today().isoformat()

    page = client.get("/ui/members").get_data(as_text=True)
    assert "Jane Doe" in page
    assert "jane.doe@example.com" in page

def test_ui_delete_member_removes_only_that_member(client):
    john = make_member(client)
    jane = make_member(client, name="Jane Doe", email="jane.doe@example.com")

    response = client.post(f"/ui/members/{john['id']}/delete")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/ui/members")

    assert client.get(f"/members/{john['id']}").status_code == 404
    assert client.get(f"/members/{jane['id']}").status_code == 200
    assert "John Doe" not in client.get("/ui/members").get_data(as_text=True)


def test_ui_loans_page_lists_existing_loans(client):
    book = make_book(client)
    member = make_member(client)
    loan = client.post("/loans", json={"book_id": book["id"], "member_id": member["id"]}).get_json()

    response = client.get("/ui/loans")
    assert response.status_code == 200
    assert loan["due_date"] in response.get_data(as_text=True)

def test_ui_checkout_unknown_book_creates_no_loan(client):
    member = make_member(client)

    response = client.post("/ui/loans", data={"book_id": "999", "member_id": str(member["id"])})
    assert response.status_code == 302
    assert client.get("/loans").get_json() == []

def test_ui_returning_a_loan_twice_only_adds_the_copy_back_once(client):
    book = make_book(client)
    member = make_member(client)
    client.post("/ui/loans", data={"book_id": str(book["id"]), "member_id": str(member["id"])})
    loan_id = client.get("/loans").get_json()[0]["id"]

    client.post(f"/ui/loans/{loan_id}/return")
    client.post(f"/ui/loans/{loan_id}/return")

    assert client.get(f"/books/{book['id']}").get_json()["available_copies"] == 1


def make_loan(client, due_in_days, email="john.doe@example.com"):
    """Check out a book and set its due date relative to today (negative = overdue)."""
    book = make_book(client)
    member = make_member(client, email=email)
    loan = client.post("/loans", json={"book_id": book["id"], "member_id": member["id"]}).get_json()
    store.loans[loan["id"]].due_date = date.today() + timedelta(days=due_in_days)
    return loan["id"]

def test_failed_reminder_still_succeeds_and_does_not_mark_loan(client, monkeypatch):
    """Stub: the service fails, so the request still returns 200 but reports notified false."""
    monkeypatch.setattr(SEND, lambda recipient, subject, message: False)
    loan_id = make_loan(client, due_in_days=-3)

    response = client.post(f"/loans/{loan_id}/remind")

    assert response.status_code == 200
    body = response.get_json()
    assert body["notified"] is False
    assert body["days_overdue"] == 3
    assert body["last_reminder_date"] is None
    assert store.loans[loan_id].last_reminder_date is None

def test_reminder_to_member_with_invalid_email_is_not_recorded(client):
    """No double: the customized simulator rejects a recipient without "@"."""
    notification_service.clear_notifications()
    loan_id = make_loan(client, due_in_days=-2, email="john.doe")

    response = client.post(f"/loans/{loan_id}/remind")

    assert response.get_json()["notified"] is False
    assert store.loans[loan_id].last_reminder_date is None
    assert notification_service.get_notifications() == []
    notification_service.clear_notifications()


def test_no_reminder_for_loan_not_yet_due(client):
    loan_id = make_loan(client, due_in_days=5)

    with patch(SEND) as mock_send:
        response = client.post(f"/loans/{loan_id}/remind")

    assert response.status_code == 200
    assert response.get_json() == {"loan_id": loan_id, "notified": False,
                                   "reason": "Loan is not overdue"}
    mock_send.assert_not_called()

def test_no_reminder_on_the_due_date(client):
    """Boundary: a loan due today is not overdue yet."""
    loan_id = make_loan(client, due_in_days=0)

    with patch(SEND) as mock_send:
        response = client.post(f"/loans/{loan_id}/remind")

    assert response.get_json()["notified"] is False
    assert store.loans[loan_id].last_reminder_date is None
    mock_send.assert_not_called()

def test_no_reminder_for_returned_loan_even_if_returned_late(client):
    loan_id = make_loan(client, due_in_days=-4)
    assert client.put(f"/loans/{loan_id}/return").status_code == 200

    with patch(SEND) as mock_send:
        response = client.post(f"/loans/{loan_id}/remind")

    assert response.get_json()["reason"] == "Loan is not overdue"
    assert store.loans[loan_id].last_reminder_date is None
    mock_send.assert_not_called()