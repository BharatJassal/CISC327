"""
File:        tests/test_ivan.py
Author:      Ivan Lin (20483619), Group 9
Description: Tests for the features assigned to Ivan in Table B:
             add, search, view, update and delete books; check out,
             return, and look up loans. Each test points to the
             requirement (F-ID) it checks.
"""
 
 
def make_book(client, title="Clean Code", author="Robert Martin", isbn="111", copies=1):
    return client.post("/books", json={
        "title": title, "author": author, "isbn": isbn, "total_copies": copies,
    }).get_json()
 
 
def make_member(client, name="Ann Lee", email="ann@example.com"):
    return client.post("/members", json={"name": name, "email": email}).get_json()
 
 
def checkout(client, book_id, member_id):
    return client.post("/loans", json={"book_id": book_id, "member_id": member_id})
 
 
# ---------------- Books ----------------
 
def test_add_book_saves_fields_and_get_returns_same_data(client):
    """F39: a new book keeps its title, author and isbn, and starts fully available."""
    response = client.post("/books", json={
        "title": "Dune", "author": "Frank Herbert", "isbn": "978-0441", "total_copies": 3,
    })
    assert response.status_code == 201
    book = response.get_json()
 
    saved = client.get(f"/books/{book['id']}").get_json()
    assert saved["title"] == "Dune"
    assert saved["author"] == "Frank Herbert"
    assert saved["isbn"] == "978-0441"
    assert saved["total_copies"] == 3
    assert saved["available_copies"] == 3
 
 
def test_add_book_without_copies_defaults_to_one(client):
    response = client.post("/books", json={"title": "T", "author": "A", "isbn": "9"})
    book = response.get_json()
    assert book["total_copies"] == 1
    assert book["available_copies"] == 1
 
 
def test_search_partial_title_is_case_insensitive(client):
    """F9: partial match search on title."""
    make_book(client, title="The Pragmatic Programmer", isbn="1")
    make_book(client, title="Dune", author="Frank Herbert", isbn="2")
 
    results = client.get("/books?search=pragMATIC").get_json()
    assert [b["title"] for b in results] == ["The Pragmatic Programmer"]
 
 
def test_search_by_author(client):
    """F9: look up a book by author."""
    make_book(client, title="Dune", author="Frank Herbert", isbn="1")
    make_book(client, title="Clean Code", author="Robert Martin", isbn="2")
 
    results = client.get("/books?search=herbert").get_json()
    assert len(results) == 1
    assert results[0]["title"] == "Dune"
 
 
def test_search_by_barcode_finds_book(client):
    """F9: look up a book by barcode (isbn). Expected to FAIL: search only checks title and author."""
    make_book(client, title="Dune", isbn="978-0441")
 
    results = client.get("/books?search=978-0441").get_json()
    assert len(results) == 1
 
 
def test_get_unknown_book_returns_404(client):
    response = client.get("/books/999")
    assert response.status_code == 404
    assert response.get_json()["error"] == "Book not found"
 
 
def test_update_book_changes_are_saved(client):
    book = make_book(client)
 
    client.put(f"/books/{book['id']}", json={"title": "Clean Code 2nd Ed"})
 
    saved = client.get(f"/books/{book['id']}").get_json()
    assert saved["title"] == "Clean Code 2nd Ed"
    assert saved["author"] == "Robert Martin"  # fields not sent stay the same
 
 
def test_update_unknown_book_returns_404(client):
    response = client.put("/books/999", json={"title": "X"})
    assert response.status_code == 404
 
 
def test_delete_book_removes_it(client):
    book = make_book(client)
 
    response = client.delete(f"/books/{book['id']}")
    assert response.status_code == 204
    assert client.get(f"/books/{book['id']}").status_code == 404
    assert client.get("/books").get_json() == []
 
 
def test_delete_unknown_book_returns_404(client):
    assert client.delete("/books/999").status_code == 404


# ---------------- Check out and return ----------------
 
def test_checkout_creates_loan_and_lowers_available_copies(client):
    """F1: staff check out a book to a member."""
    book = make_book(client, copies=2)
    member = make_member(client)
 
    response = checkout(client, book["id"], member["id"])
    assert response.status_code == 201
    loan = response.get_json()
    assert loan["book_id"] == book["id"]
    assert loan["member_id"] == member["id"]
    assert loan["return_date"] is None
 
    assert client.get(f"/books/{book['id']}").get_json()["available_copies"] == 1
 
 
def test_checkout_due_date_is_21_days_after_checkout(client):
    """F34: due date is 21 days after checkout. Expected to FAIL: the app uses 14 days."""
    from datetime import date
    book = make_book(client)
    member = make_member(client)
 
    loan = checkout(client, book["id"], member["id"]).get_json()
    days = (date.fromisoformat(loan["due_date"]) - date.fromisoformat(loan["loan_date"])).days
    assert days == 21
 
 
def test_checkout_unknown_book_returns_404(client):
    member = make_member(client)
    response = checkout(client, 999, member["id"])
    assert response.status_code == 404
    assert client.get("/loans").get_json() == []
 
 
def test_checkout_refused_when_no_copies_left(client):
    """F5: available copies must stay accurate. Expected to FAIL: count goes to -1."""
    book = make_book(client, copies=1)
    first = make_member(client)
    second = make_member(client, name="Bo", email="bo@example.com")
 
    assert checkout(client, book["id"], first["id"]).status_code == 201
    response = checkout(client, book["id"], second["id"])
 
    assert response.status_code >= 400
    assert client.get(f"/books/{book['id']}").get_json()["available_copies"] == 0
 
 
def test_checkout_refused_for_unknown_member(client):
    """F1: checkout uses the member's card, so the member must exist. Expected to FAIL."""
    book = make_book(client)
 
    response = checkout(client, book["id"], 999)
 
    assert response.status_code >= 400
    assert client.get(f"/books/{book['id']}").get_json()["available_copies"] == 1
 
 
def test_member_cannot_have_more_than_10_loans(client):
    """F7: limit of 10 items per member. Expected to FAIL: the 11th checkout is allowed."""
    book = make_book(client, copies=20)
    member = make_member(client)
 
    for _ in range(10):
        assert checkout(client, book["id"], member["id"]).status_code == 201
    eleventh = checkout(client, book["id"], member["id"])
 
    assert eleventh.status_code >= 400
    assert client.get(f"/books/{book['id']}").get_json()["available_copies"] == 10
 
 
def test_return_restores_copy_and_records_return_date(client):
    """F6 and F11: availability updates on return, and the return date is the scan date."""
    from datetime import date
    book = make_book(client)
    member = make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()
 
    response = client.put(f"/loans/{loan['id']}/return")
    assert response.status_code == 200
    assert response.get_json()["return_date"] == date.today().isoformat()
    assert client.get(f"/books/{book['id']}").get_json()["available_copies"] == 1
 
 
def test_returning_twice_is_rejected_and_count_not_doubled(client):
    book = make_book(client)
    member = make_member(client)
    loan = checkout(client, book["id"], member["id"]).get_json()
    client.put(f"/loans/{loan['id']}/return")
 
    second = client.put(f"/loans/{loan['id']}/return")
    assert second.status_code == 400
    assert second.get_json()["error"] == "Loan already returned"
    assert client.get(f"/books/{book['id']}").get_json()["available_copies"] == 1
 
 
def test_return_unknown_loan_returns_404(client):
    assert client.put("/loans/999/return").status_code == 404
 
 
def test_returned_copy_can_be_checked_out_again(client):
    """F6: once returned, the copy is available to the next member."""
    book = make_book(client, copies=1)
    first = make_member(client)
    second = make_member(client, name="Bo", email="bo@example.com")
 
    loan = checkout(client, book["id"], first["id"]).get_json()
    client.put(f"/loans/{loan['id']}/return")
    response = checkout(client, book["id"], second["id"])
 
    assert response.status_code == 201
    assert client.get(f"/books/{book['id']}").get_json()["available_copies"] == 0
 
 
# ---------------- Loan lookup ----------------
 
def test_lookup_loans_by_book_id(client):
    book1 = make_book(client, isbn="1")
    book2 = make_book(client, title="Dune", isbn="2")
    member = make_member(client)
    checkout(client, book1["id"], member["id"])
    checkout(client, book2["id"], member["id"])
 
    results = client.get(f"/loans?book_id={book2['id']}").get_json()
    assert len(results) == 1
    assert results[0]["book_id"] == book2["id"]
 
 
def test_lookup_loans_by_member_id_shows_only_that_member(client):
    """F16: a member sees only their own loans. Expected to FAIL: the filter compares book_id."""
    book1 = make_book(client, isbn="1")
    book2 = make_book(client, title="Dune", isbn="2", copies=2)
    ann = make_member(client)
    bo = make_member(client, name="Bo", email="bo@example.com")
    checkout(client, book2["id"], ann["id"])
    checkout(client, book1["id"], bo["id"])
 
    results = client.get(f"/loans?member_id={ann['id']}").get_json()
    assert len(results) == 1
    assert all(l["member_id"] == ann["id"] for l in results)
 
 
def test_lookup_with_no_filter_lists_all_loans(client):
    book = make_book(client, copies=3)
    member = make_member(client)
    for _ in range(3):
        checkout(client, book["id"], member["id"])
 
    assert len(client.get("/loans").get_json()) == 3