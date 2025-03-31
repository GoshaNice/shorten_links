import pytest
from datetime import datetime, timedelta
from fastapi import status
from httpx import AsyncClient


@pytest.mark.anyio
async def test_links(client: AsyncClient):
    # Комментарий от меня : у меня ломается если бить на разные тесты,
    # так что я объединил в один - время уже 2 ночи, я очень хочу спать((

    # Сначала неавторизованный пользователь

    link_data = {
        "original_url": "https://example.com/",
        "expires_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
    }
    response = await client.post("/links/shorten", json=link_data)
    assert response.status_code == status.HTTP_201_CREATED
    short_code = response.json()["short_code"]

    response = await client.get(f"/links/{short_code}", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers.get("location") == "https://example.com/"

    # Регистрируемся

    new_unique_email = f"{datetime.utcnow().timestamp()}@test.com"
    password = "default"
    response = await client.post(
        "/auth/register", json={"email": new_unique_email, "password": password}
    )
    assert response.status_code == 201

    response = await client.post(
        "/auth/jwt/login",
        data={"username": new_unique_email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Тестируем /links/shorten

    payload = {
        "original_url": "https://example.com",
    }
    response = await client.post("/links/shorten", json=payload)
    assert response.status_code == 201

    payload = {
        "original_url": "https://example.com",
        "alias": "invalid alias!",
        "expires_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
    }
    response = await client.post("/links/shorten", json=payload)
    assert response.status_code == 400

    payload = {
        "original_url": "https://example.org",
        "alias": "shorten",  # reserved
        "expires_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
    }
    response = await client.post("/links/shorten", json=payload, headers=headers)
    assert response.status_code == 400

    new_unique_alias = f"testalias_{int(datetime.utcnow().timestamp())}"
    payload = {
        "original_url": "https://example.org",
        "alias": new_unique_alias,
        "expires_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
    }
    response = await client.post("/links/shorten", json=payload, headers=headers)
    assert response.status_code == 201
    short_code = response.json()["short_code"]

    payload = {
        "original_url": "https://example1.org",
        "alias": new_unique_alias,  # already exists
    }
    response = await client.post("/links/shorten", json=payload, headers=headers)
    assert response.status_code == 400

    # Тестируем /links/{short_code}/stats

    stats = await client.get(f"/links/{short_code}/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["click_count"] == 0

    await client.get(f"/links/{short_code}", headers=headers, follow_redirects=False)

    stats2 = await client.get(f"/links/{short_code}/stats", headers=headers)
    assert stats2.status_code == 200
    assert stats2.json()["click_count"] >= 1, stats2.json()["click_count"]

    # Тестируем put /links/{short_code}

    new_url = "https://example.org/updated"
    response = await client.put(
        f"/links/{short_code}", json={"original_url": new_url}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["original_url"] == new_url

    # Тестируем delete /links/{short_code}

    response = await client.delete(f"/links/{short_code}", headers=headers)
    assert response.status_code == 204

    response = await client.get(f"/links/{short_code}", follow_redirects=False)
    assert response.status_code == 404
