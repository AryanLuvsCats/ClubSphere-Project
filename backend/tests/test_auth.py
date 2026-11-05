def test_register_student_success(client):
    payload = {
        "email": "newstudent@univ.edu",
        "password": "SecurePassword123!",
        "full_name": "New Student",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newstudent@univ.edu"
    assert data["role"] == "Student"
    assert data["is_active"] is True
    assert "user_id" in data


def test_register_duplicate_email_fails(client):
    payload = {
        "email": "duplicate@univ.edu",
        "password": "SecurePassword123!",
        "full_name": "Original Student",
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"]


def test_login_success_sets_httponly_refresh_cookie(client, student_user):
    payload = {
        "email": student_user.Email,
        "password": "Password@123",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" not in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "Student"

    set_cookie = response.headers.get("set-cookie", "")
    assert "clubsphere_refresh=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie


def test_login_invalid_password_fails(client, student_user):
    payload = {
        "email": student_user.Email,
        "password": "WrongPassword999",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_refresh_token_success_rotates_cookie(client, student_user):
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": student_user.Email, "password": "Password@123"},
    )
    assert login_res.status_code == 200
    old_refresh = client.cookies.get("clubsphere_refresh")
    assert old_refresh

    refresh_res = client.post("/api/v1/auth/refresh")
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data
    assert "refresh_token" not in data

    new_refresh = client.cookies.get("clubsphere_refresh")
    assert new_refresh
    assert new_refresh != old_refresh


def test_refresh_token_invalid_fails(client):
    client.cookies.set("clubsphere_refresh", "invalid-opaque-token")
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


def test_refresh_without_cookie_fails(client):
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


def test_auth_me_endpoint(client, student_token, student_user):
    headers = {"Authorization": f"Bearer {student_token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == student_user.Email
    assert data["full_name"] == student_user.FullName


def test_auth_me_unauthorized_fails(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
