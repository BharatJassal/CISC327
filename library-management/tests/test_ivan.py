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