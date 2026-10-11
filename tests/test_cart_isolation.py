import os
import re


def _make_app():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    return app


def _extract_csrf(html: str) -> str:
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    assert m, "csrf_token hidden input not found"
    return m.group(1)


def _login(client, email: str, password: str):
    html = client.get("/auth/login").data.decode("utf-8", errors="ignore")
    token = _extract_csrf(html)
    return client.post(
        "/auth/login",
        data={"csrf_token": token, "email": email, "password": password, "remember": "y"},
        follow_redirects=False,
    )


def test_cart_not_shared_between_customers_same_browser():
    app = _make_app()
    client = app.test_client()

    # Guest adds to cart (session)
    html = client.get("/r/1").data.decode("utf-8", errors="ignore")
    token = _extract_csrf(html)
    resp = client.post("/cart/add/1", data={"csrf_token": token}, follow_redirects=False)
    assert resp.status_code in (302, 303)

    # Login as customer@demo.com (merge guest cart -> customer cart)
    resp = _login(client, "customer@demo.com", "Customer@1234")
    assert resp.status_code in (302, 303)
    cart_page = client.get("/cart").data.decode("utf-8", errors="ignore")
    assert "Chicken Biryani" in cart_page

    # Logout and login as a different customer: cart should be empty for them
    client.get("/auth/logout")
    resp = _login(client, "customer2@demo.com", "Customer@1234")
    assert resp.status_code in (302, 303)
    cart_page2 = client.get("/cart").data.decode("utf-8", errors="ignore")
    assert "Your cart is empty" in cart_page2

