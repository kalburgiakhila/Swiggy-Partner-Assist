import os
import re


def _make_client():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _extract_csrf(html: str) -> str:
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "csrf_token hidden input not found"
    return m.group(1)


def test_cart_add_requires_csrf():
    client = _make_client()
    resp = client.post("/cart/add/1")
    assert resp.status_code == 400
    assert b"CSRF token is missing" in resp.data


def test_cart_add_with_csrf_ok():
    client = _make_client()
    html = client.get("/r/1").data.decode("utf-8", errors="ignore")
    token = _extract_csrf(html)
    resp = client.post("/cart/add/1", data={"csrf_token": token}, follow_redirects=False)
    assert resp.status_code in (302, 303)

