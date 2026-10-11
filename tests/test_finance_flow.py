import os
import re


def _make_app():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True, ANTI_SCAM_GEO_CHECKS=False)
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
        data={"csrf_token": token, "email": email, "password": password},
        follow_redirects=False,
    )


def test_upi_payment_required_then_settled_on_delivery():
    app = _make_app()
    client = app.test_client()

    # customer login
    r = _login(client, "customer@demo.com", "Customer@1234")
    assert r.status_code in (302, 303)

    # add item to cart
    html = client.get("/r/1").data.decode("utf-8", errors="ignore")
    token = _extract_csrf(html)
    r = client.post("/cart/add/1", data={"csrf_token": token}, follow_redirects=False)
    assert r.status_code in (302, 303)

    # checkout with upi -> should redirect to pay page
    html = client.get("/checkout").data.decode("utf-8", errors="ignore")
    token = _extract_csrf(html)
    r = client.post(
        "/checkout",
        data={
            "csrf_token": token,
            "delivery_address": "Test Address",
            "delivery_lat": "12.98",
            "delivery_lng": "77.60",
            "notes": "",
            "payment_method": "upi",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert "/orders/" in r.headers["Location"] and "/pay" in r.headers["Location"]

    # pay now
    pay_url = r.headers["Location"]
    html = client.get(pay_url).data.decode("utf-8", errors="ignore")
    token = _extract_csrf(html)
    r2 = client.post(pay_url, data={"csrf_token": token, "upi_id": "demo@upi"}, follow_redirects=False)
    assert r2.status_code in (302, 303)
    order_url = r2.headers["Location"]
    order_id = int(order_url.rstrip("/").split("/")[-1])

    # owner accepts and marks ready
    client.get("/auth/logout")
    r = _login(client, "owner@demo.com", "Owner@1234")
    assert r.status_code in (302, 303)

    dash = client.get("/restaurant/dashboard").data.decode("utf-8", errors="ignore")
    token = _extract_csrf(dash)
    client.post(f"/restaurant/orders/{order_id}/accept", data={"csrf_token": token}, follow_redirects=False)
    dash = client.get("/restaurant/dashboard").data.decode("utf-8", errors="ignore")
    token = _extract_csrf(dash)
    client.post(f"/restaurant/orders/{order_id}/ready", data={"csrf_token": token}, follow_redirects=False)

    # rider accepts, pickup, deliver -> settlement should become earned
    client.get("/auth/logout")
    r = _login(client, "rider@demo.com", "Rider@1234")
    assert r.status_code in (302, 303)

    dash = client.get("/delivery/dashboard").data.decode("utf-8", errors="ignore")
    token = _extract_csrf(dash)
    client.post(f"/delivery/orders/{order_id}/accept", data={"csrf_token": token}, follow_redirects=False)
    order = client.get(f"/delivery/orders/{order_id}").data.decode("utf-8", errors="ignore")
    token = _extract_csrf(order)
    client.post(f"/delivery/orders/{order_id}/pickup", data={"csrf_token": token}, follow_redirects=False)
    order = client.get(f"/delivery/orders/{order_id}").data.decode("utf-8", errors="ignore")
    token = _extract_csrf(order)
    client.post(f"/delivery/orders/{order_id}/deliver", data={"csrf_token": token}, follow_redirects=False)

    # verify earned shown
    order = client.get(f"/delivery/orders/{order_id}").data.decode("utf-8", errors="ignore")
    assert "Settlement: earned" in order
