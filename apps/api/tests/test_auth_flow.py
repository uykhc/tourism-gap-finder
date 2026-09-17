from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api.app.database import Base, get_db
from apps.api.app.deps import current_user
from apps.api.app.main import app


def test_complete_account_lifecycle_uses_real_jwt_and_database() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as session:
            yield session

    bypass = app.dependency_overrides.pop(current_user, None)
    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app)
        signup = client.post("/auth/signup", json={
            "email": "pilot@example.com",
            "password": "launch123",
            "password_confirm": "launch123",
            "default_region": "47130",
        })
        assert signup.status_code == 201
        assert signup.json()["default_region"]["region_id"] == "47130"

        duplicate = client.post("/auth/signup", json={
            "email": "pilot@example.com",
            "password": "launch123",
            "password_confirm": "launch123",
        })
        assert duplicate.status_code == 409

        login = client.post("/auth/login", json={
            "email": "pilot@example.com",
            "password": "launch123",
        })
        assert login.status_code == 200
        old_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/auth/me", headers=old_headers).status_code == 200

        update = client.patch(
            "/users/me", headers=old_headers, json={"default_region": None},
        )
        assert update.status_code == 200
        assert update.json()["default_region"] is None

        changed = client.patch("/users/me/password", headers=old_headers, json={
            "new_password": "changed123",
            "new_password_confirm": "changed123",
        })
        assert changed.status_code == 204
        assert client.post("/auth/logout", headers=old_headers).status_code == 204
        assert client.get("/auth/me", headers=old_headers).status_code == 401

        assert client.post("/auth/login", json={
            "email": "pilot@example.com", "password": "launch123",
        }).status_code == 401
        relogin = client.post("/auth/login", json={
            "email": "pilot@example.com", "password": "changed123",
        })
        assert relogin.status_code == 200
        new_headers = {"Authorization": f"Bearer {relogin.json()['access_token']}"}
        assert client.delete("/users/me", headers=new_headers).status_code == 204
        assert client.get("/auth/me", headers=new_headers).status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        if bypass is not None:
            app.dependency_overrides[current_user] = bypass
        Base.metadata.drop_all(engine)
        engine.dispose()
