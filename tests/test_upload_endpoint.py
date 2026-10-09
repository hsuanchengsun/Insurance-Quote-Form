from __future__ import annotations

import io
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Quote, User
from app.schemas.quote import QuoteDraft
from app.services.auth_service import hash_password


@pytest.fixture
def test_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(
            username="testagent",
            password_hash=hash_password("demo1234"),
            display_name="Test Agent",
            email="agent@example.com",
            phone="555-0100",
            role="agent",
            active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        yield session, user
    Base.metadata.drop_all(engine)


def test_upload_pdf_requires_login():
    client = TestClient(app)
    response = client.post("/quotes/upload-pdf")
    # Redirects to login or 401
    assert response.status_code in (303, 307, 401) or response.url.path == "/login"


def test_upload_pdf_rejects_non_pdf(test_db_session):
    db, user = test_db_session

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        # Login first
        login_res = client.post(
            "/login",
            data={"username": "testagent", "password": "demo1234"},
            follow_redirects=False,
        )
        assert login_res.status_code == 303

        # Upload a text file as txt
        file_data = io.BytesIO(b"Hello world text")
        response = client.post(
            "/quotes/upload-pdf",
            files={"file": ("test.txt", file_data, "text/plain")},
            data={"locale": "zh-TW"},
        )
        assert response.status_code == 400
        assert "僅支援" in response.json().get("message", "")
    finally:
        app.dependency_overrides.clear()


def test_upload_pdf_success_creates_draft_and_redirects(test_db_session):
    db, user = test_db_session

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    mock_extracted_json = {
        "customer_name": "Evelyn Chen",
        "carrier_name": "Geico",
        "term_months": 6,
        "quote_date": "2026-08-10",
        "expiration_date": "2026-08-20",
        "vehicle_summary": "2022 Honda CR-V",
        "vehicle_count": 1,
        "driver_count": 1,
        "coverages": [
            {"standard_code": "bodily_injury", "value": "$50,000 / $100,000"},
            {"standard_code": "property_damage", "value": "$50,000"},
        ],
        "plans": [
            {"plan_code": "auto_only", "premium_total": "920.00"},
            {"plan_code": "auto_renters", "premium_total": "875.50", "recommended": True},
        ],
    }

    try:
        client = TestClient(app)
        client.post(
            "/login",
            data={"username": "testagent", "password": "demo1234"},
            follow_redirects=False,
        )

        dummy_pdf = io.BytesIO(b"%PDF-1.4 sample binary data")
        with patch("app.services.gemini_service.extract_raw_json_from_gemini", return_value=mock_extracted_json):
            response = client.post(
                "/quotes/upload-pdf",
                files={"file": ("quote_geico.pdf", dummy_pdf, "application/pdf")},
                data={"locale": "zh-TW"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "from_pdf=1" in data["redirect_url"]

        # Verify in DB
        quote = db.get(Quote, data["quote_id"])
        assert quote is not None
        assert quote.customer_name == "Evelyn Chen"
        assert quote.current_draft_json["policy"]["carrier"] == "Geico"
        assert quote.status == "Draft"
    finally:
        app.dependency_overrides.clear()
