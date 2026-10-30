"""
File: tests/test_bharat.py
Author: Bharat Jassal (20463821), group 9
Description: Tests for the features assigned to Bharat in Table B. Members, renew, fine, reservations and ui.
"""

def make_book(client, title="Clean Code", author="Robert Martin", isbn="111", copies=1):
    return client.post("/books", json={
        "title": title, "author": author, "isbn": isbn, "total_copies": copies,
    }).get_json()

def make_member(client, name="John Doe", email="john.doe@example.com"):
    return client.post("/members", json={
        "name": name,
        "email": email
    }).get_json()

def checkout(client, book_id, member_id):
    return client.post("/loans", json={"book_id": book_id, "member_id": member_id})


# Members

def test_add_member_saves_fields_and_get_returns_same_data(client):
    """F10: a new member keeps their name and email, and joins today."""
    from datetime import date
    response = client.post("/members", json={"name": "John Doe", "email": "john.doe@example.com"})
    assert response.status_code == 201
    member = response.get_json()

    saved = client.get(f"/members/{member['id']}").get_json()
    assert saved["name"] == "John Doe"
    assert saved["email"] == "john.doe@example.com"
    assert saved["membership_date"] == date.today().isoformat()

def test_add_member_keeps_address(client):
    """F10: registration records name, address and contact info.
    Expected to Fail: the address sent is dropped."""
    response = client.post("/members", json={
        "name": "John Doe", "email": "john.doe@example.com", "address": "1 Union St"})
    member = response.get_json()

    saved = client.get(f"/members/{member['id']}").get_json()
    assert saved.get("address") == "1 Union St"

def test_each_member_gets_unique_id_and_is_listed(client):
    """F10/F36: Ids act as card numbers, so they are unique. GET /members lists everyone."""
    john = make_member(client)
    jane = make_member(client, name="Jane Doe", email="jane.doe@example.com")

    members = client.get("/members").get_json()
    assert john["id"] != jane["id"]
    assert [m["name"] for m in members] == ["John Doe", "Jane Doe"]

def test_look_up_member_by_name(client):
    """F36: staff look up member by name.
    Expected to Fail: Search parameter is ignored and every member is then returned."""
    make_member(client)
    make_member(client, name="Jane Doe", email="jane.doe@example.com")

    results = client.get("/members?search=jane").get_json()
    assert [m["name"] for m in results] == ["Jane Doe"]

def test_update_member_changes_email_and_keeps_other_fields(client):
    """Update a member: New email is saved, name and join date stay exactly the same."""
    member = make_member(client)

    response = client.put(f"/members/{member['id']}", json={"email": "new.john@example.com"})
    assert response.status_code == 200

    saved = client.get(f"/members/{member['id']}").get_json()
    assert saved["email"] == "new.john@example.com"
    assert saved["name"] == "John Doe"
    assert saved["membership_date"] == member["membership_date"]

def test_delete_member_removes_them(client):
    member = make_member(client)

    response = client.delete(f"/members/{member['id']}")
    assert response.status_code == 204
    assert client.get(f"/members/{member['id']}").status_code == 404
    assert client.get("/members").get_json() == []


def test_delete_member_twice_returns_404(client):
    member = make_member(client)
    client.delete(f"/members/{member['id']}")

    response = client.delete(f"/members/{member['id']}")
    assert response.status_code == 404
    assert response.get_json()["error"] == "Member not found"

# renew
def test_renew_extends_due_date_and_is_saved(client):
    """F18: renewing pushes the due date back one loan period which is 14 days, and a later GET shows it."""
    from datetime import date
    book = make_book(client)
    member = make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()

    response = client.put(f"/loans/{loan['id']}/renew")
    assert response.status_code == 200
    new_due = response.get_json()["due_date"]
    days = (date.fromisoformat(new_due) - date.fromisoformat(loan["due_date"])).days
    assert days == 14

    saved = client.get(f"/loans?book_id={book['id']}").get_json()[0]
    assert saved["due_date"] == new_due

def test_renew_refused_when_another_member_reserved_the_book(client):
    """F18: no renewal allowed while another member has the book reserved.
    Expected to Fail: renew ignores reservations."""
    book = make_book(client)
    john = make_member(client)
    jane = make_member(client, name="Jane Doe", email="jane.doe@example.com")
    loan = checkout(client, book["id"], john["id"]).get_json()
    client.post("/reservations", json={"book_id": book["id"], "member_id": jane["id"]})

    response = client.put(f"/loans/{loan['id']}/renew")
    assert response.status_code >= 400
# Fine
def test_fine_for_overdue_loan_is_daily_rate_times_days_late(client):
    """F23: 4 days late at $0.25/day is $1.00. The test moves the due date back in the store."""
    from datetime import date, timedelta
    from app import store
    book = make_book(client)
    member = make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()
    store.loans[loan["id"]].due_date = date.today() - timedelta(days=4)

    response = client.get(f"/loans/{loan['id']}/fine")
    assert response.status_code == 200
    assert response.get_json()["fine_amount"] == 1.0


def test_fine_stops_growing_once_book_is_returned(client):
    """F23: a returned loan is only charged up to its return date.
    Due 10 days ago, returned 6 days ago = 4 days late = $1.00.
    Expected to Fail: the app counts up to today and charges $2.50."""
    from datetime import date, timedelta
    from app import store
    book = make_book(client)
    member = make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()
    client.put(f"/loans/{loan['id']}/return")
    store.loans[loan["id"]].due_date = date.today() - timedelta(days=10)
    store.loans[loan["id"]].return_date = date.today() - timedelta(days=6)

    response = client.get(f"/loans/{loan['id']}/fine")
    assert response.get_json()["fine_amount"] == 1.0

# reservation
def test_create_reservation_records_member_book_and_date(client):
    """F17: Reservation stores who reserved what book and when, and shows up in GET."""
    from datetime import date
    book = make_book(client)
    member = make_member(client)

    response = client.post("/reservations", json={"book_id": book["id"], "member_id": member["id"]})
    assert response.status_code == 201
    created = response.get_json()
    assert created["book_id"] == book["id"]
    assert created["member_id"] == member["id"]
    assert created["reservation_date"] == date.today().isoformat()
    assert created["fulfilled"] is False
    assert client.get("/reservations").get_json() == [created]


def test_reservation_with_unknown_book_or_member_is_rejected(client):
    book = make_book(client)
    member = make_member(client)

    bad_book = client.post("/reservations", json={"book_id": 999, "member_id": member["id"]})
    bad_member = client.post("/reservations", json={"book_id": book["id"], "member_id": 999})

    assert bad_book.status_code == 404
    assert bad_book.get_json()["error"] == "Book not found"
    assert bad_member.status_code == 404
    assert bad_member.get_json()["error"] == "Member not found"
    assert client.get("/reservations").get_json() == []


def test_lookup_reservations_by_book_keeps_queue_order(client):
    """F17/F35: Reservations for a book come back in the same order as they were placed, and the member filter shows only that member's holds."""
    book1 = make_book(client)
    book2 = make_book(client, title="Dune", author="Frank Herbert", isbn="222")
    john = make_member(client)
    jane = make_member(client, name="Jane Doe", email="jane.doe@example.com")
    client.post("/reservations", json={"book_id": book1["id"], "member_id": jane["id"]})
    client.post("/reservations", json={"book_id": book1["id"], "member_id": john["id"]})
    client.post("/reservations", json={"book_id": book2["id"], "member_id": john["id"]})

    for_book1 = client.get(f"/reservations?book_id={book1['id']}").get_json()
    for_john = client.get(f"/reservations?member_id={john['id']}").get_json()

    assert [r["member_id"] for r in for_book1] == [jane["id"], john["id"]]
    assert sorted(r["book_id"] for r in for_john) == [book1["id"], book2["id"]]

# web ui

def test_ui_add_book_form_creates_book(client):
    """F15: a book added through the web form is stored and shown with its availability."""
    response = client.post("/ui/books", data={
        "title": "Dune", "author": "Frank Herbert", "isbn": "222", "total_copies": "2"})
    assert response.status_code == 302

    books = client.get("/books").get_json()
    assert books[0]["title"] == "Dune"
    assert books[0]["available_copies"] == 2
    assert "Dune" in client.get("/ui/books").get_data(as_text=True)


def test_ui_checkout_and_return_update_available_copies(client):
    """F6/F11 through the web forms: checkout lowers the count, return restores it."""
    from datetime import date
    book = make_book(client)
    member = make_member(client)

    client.post("/ui/loans", data={"book_id": str(book["id"]), "member_id": str(member["id"])})
    assert client.get(f"/books/{book['id']}").get_json()["available_copies"] == 0
    loan_id = client.get("/loans").get_json()[0]["id"]

    client.post(f"/ui/loans/{loan_id}/return")
    assert client.get(f"/books/{book['id']}").get_json()["available_copies"] == 1
    assert client.get("/loans").get_json()[0]["return_date"] == date.today().isoformat()