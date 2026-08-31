"""Demo mock API tests (P9-002)."""


def test_login_success(client):
    r = client.post("/api/demo-api/login", json={"username": "testuser", "password": "Test@1234"})
    assert r.status_code == 200
    assert "token" in r.json()


def test_login_wrong_password_401(client):
    r = client.post("/api/demo-api/login", json={"username": "testuser", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["message"] == "用户名或密码错误"


def test_login_missing_param_400(client):
    r = client.post("/api/demo-api/login", json={"username": "testuser"})
    assert r.status_code == 400
    assert r.json()["message"] == "参数缺失"


def test_tasks_authorized(client):
    r = client.get("/api/demo-api/tasks", headers={"Authorization": "Bearer token-1"})
    assert r.status_code == 200
    assert r.json() == {"tasks": []}


def test_tasks_unauthorized_401(client):
    assert client.get("/api/demo-api/tasks").status_code == 401
