"""
File : tests/test_bharat.py
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
    jane = make_member(client, name="Jane Doe", email="jane@example.com")

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