import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test_taskflow.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def register_user(username, email, password, role="employee", qualification_level=3):
    return client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "role": role,
            "qualification_level": qualification_level,
        },
    )


def login_user(username, password):
    return client.post("/auth/login", data={"username": username, "password": password})


def auth_headers(username, password):
    response = login_user(username, password)
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_user():
    response = register_user("alice", "alice@example.com", "password123")
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert data["qualification_level"] == 3


def test_register_duplicate_username():
    register_user("alice", "alice@example.com", "password123")
    response = register_user("alice", "alice2@example.com", "password123")
    assert response.status_code == 400


def test_register_duplicate_email():
    register_user("alice", "alice@example.com", "password123")
    response = register_user("alice2", "alice@example.com", "password123")
    assert response.status_code == 400


def test_login():
    register_user("bob", "bob@example.com", "securepass")
    response = login_user("bob", "securepass")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    register_user("charlie", "charlie@example.com", "correctpass")
    response = login_user("charlie", "wrongpass")
    assert response.status_code == 401


def test_login_nonexistent_user():
    response = login_user("ghost", "pass")
    assert response.status_code == 401


def test_get_users_requires_auth():
    response = client.get("/users/")
    assert response.status_code == 401


def test_get_users_authenticated():
    register_user("dave", "dave@example.com", "pass123")
    headers = auth_headers("dave", "pass123")
    response = client.get("/users/", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) == 1


def test_get_me():
    register_user("myself", "myself@example.com", "pass123")
    headers = auth_headers("myself", "pass123")
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["username"] == "myself"


def test_get_user_by_id():
    register_user("eve", "eve@example.com", "pass123")
    headers = auth_headers("eve", "pass123")
    me = client.get("/users/me", headers=headers).json()
    response = client.get(f"/users/{me['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["username"] == "eve"


def test_get_user_not_found():
    register_user("finder", "finder@example.com", "pass123")
    headers = auth_headers("finder", "pass123")
    response = client.get("/users/99999", headers=headers)
    assert response.status_code == 404


def test_update_own_user():
    register_user("frank", "frank@example.com", "pass123")
    headers = auth_headers("frank", "pass123")
    me = client.get("/users/me", headers=headers).json()
    response = client.put(f"/users/{me['id']}", json={"qualification_level": 4}, headers=headers)
    assert response.status_code == 200
    assert response.json()["qualification_level"] == 4


def test_update_other_user_forbidden():
    register_user("user1", "user1@example.com", "pass123")
    register_user("user2", "user2@example.com", "pass123")
    headers2 = auth_headers("user2", "pass123")
    user1 = client.get("/users/me", headers=auth_headers("user1", "pass123")).json()
    response = client.put(f"/users/{user1['id']}", json={"qualification_level": 5}, headers=headers2)
    assert response.status_code == 403


def test_create_task():
    register_user("taskowner", "taskowner@example.com", "pass123")
    headers = auth_headers("taskowner", "pass123")
    response = client.post(
        "/tasks/",
        json={"title": "Fix bug", "description": "Critical fix", "priority": "high", "required_qualification": 2},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Fix bug"
    assert data["status"] == "pending"
    assert data["priority"] == "high"


def test_create_task_requires_auth():
    response = client.post("/tasks/", json={"title": "Unauthorized Task", "required_qualification": 1})
    assert response.status_code == 401


def test_list_tasks():
    register_user("lister", "lister@example.com", "pass123")
    headers = auth_headers("lister", "pass123")
    client.post("/tasks/", json={"title": "Task A", "required_qualification": 1}, headers=headers)
    client.post("/tasks/", json={"title": "Task B", "required_qualification": 2}, headers=headers)
    response = client.get("/tasks/", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_tasks_filter_by_priority():
    register_user("filterer", "filterer@example.com", "pass123")
    headers = auth_headers("filterer", "pass123")
    client.post("/tasks/", json={"title": "Low task", "required_qualification": 1, "priority": "low"}, headers=headers)
    client.post("/tasks/", json={"title": "High task", "required_qualification": 1, "priority": "high"}, headers=headers)
    response = client.get("/tasks/?priority=high", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["priority"] == "high"


def test_get_task():
    register_user("getter", "getter@example.com", "pass123")
    headers = auth_headers("getter", "pass123")
    task_id = client.post("/tasks/", json={"title": "My Task", "required_qualification": 1}, headers=headers).json()["id"]
    response = client.get(f"/tasks/{task_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == task_id


def test_get_task_not_found():
    register_user("notfound", "notfound@example.com", "pass123")
    headers = auth_headers("notfound", "pass123")
    response = client.get("/tasks/99999", headers=headers)
    assert response.status_code == 404


def test_update_task():
    register_user("updater", "updater@example.com", "pass123")
    headers = auth_headers("updater", "pass123")
    task_id = client.post("/tasks/", json={"title": "Old Title", "required_qualification": 1}, headers=headers).json()["id"]
    response = client.put(f"/tasks/{task_id}", json={"title": "New Title", "status": "completed"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"
    assert response.json()["status"] == "completed"


def test_update_task_forbidden():
    register_user("owner", "owner@example.com", "pass123")
    register_user("intruder", "intruder@example.com", "pass123")
    owner_headers = auth_headers("owner", "pass123")
    intruder_headers = auth_headers("intruder", "pass123")
    task_id = client.post("/tasks/", json={"title": "Owned Task", "required_qualification": 1}, headers=owner_headers).json()["id"]
    response = client.put(f"/tasks/{task_id}", json={"title": "Hacked"}, headers=intruder_headers)
    assert response.status_code == 403


def test_delete_task():
    register_user("deleter", "deleter@example.com", "pass123")
    headers = auth_headers("deleter", "pass123")
    task_id = client.post("/tasks/", json={"title": "To Delete", "required_qualification": 1}, headers=headers).json()["id"]
    response = client.delete(f"/tasks/{task_id}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/tasks/{task_id}", headers=headers).status_code == 404


def test_auto_assign_task():
    register_user("manager", "manager@example.com", "pass123", role="employee", qualification_level=1)
    register_user("worker1", "worker1@example.com", "pass123", role="employee", qualification_level=3)
    register_user("worker2", "worker2@example.com", "pass123", role="employee", qualification_level=4)

    manager_headers = auth_headers("manager", "pass123")
    task_id = client.post(
        "/tasks/",
        json={"title": "Auto Assign Task", "required_qualification": 3, "priority": "high"},
        headers=manager_headers,
    ).json()["id"]

    response = client.post(f"/tasks/{task_id}/auto-assign", headers=manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data["assigned_to"]["qualification_level"] >= 3
    assert data["score"] >= 0


def test_auto_assign_workload_balance():
    register_user("supervisor", "supervisor@example.com", "pass123", qualification_level=1)
    register_user("emp1", "emp1@example.com", "pass123", qualification_level=3)
    register_user("emp2", "emp2@example.com", "pass123", qualification_level=3)

    sup_headers = auth_headers("supervisor", "pass123")

    t1_id = client.post("/tasks/", json={"title": "Task1", "required_qualification": 3, "priority": "critical"}, headers=sup_headers).json()["id"]
    client.post(f"/tasks/{t1_id}/auto-assign", headers=sup_headers)

    t2_id = client.post("/tasks/", json={"title": "Task2", "required_qualification": 3, "priority": "low"}, headers=sup_headers).json()["id"]
    response = client.post(f"/tasks/{t2_id}/auto-assign", headers=sup_headers)
    assert response.status_code == 200

    emp1_data = client.get("/users/me", headers=auth_headers("emp1", "pass123")).json()
    emp2_data = client.get("/users/me", headers=auth_headers("emp2", "pass123")).json()

    t1_assignee = client.get(f"/tasks/{t1_id}", headers=sup_headers).json()["assignee_id"]
    t2_assignee = client.get(f"/tasks/{t2_id}", headers=sup_headers).json()["assignee_id"]
    assert t1_assignee != t2_assignee


def test_auto_assign_no_suitable_candidates():
    register_user("requester", "requester@example.com", "pass123", qualification_level=3)
    headers = auth_headers("requester", "pass123")
    task_id = client.post(
        "/tasks/",
        json={"title": "Expert Task", "required_qualification": 5, "priority": "critical"},
        headers=headers,
    ).json()["id"]
    response = client.post(f"/tasks/{task_id}/auto-assign", headers=headers)
    assert response.status_code == 404


def test_auto_assign_already_assigned():
    register_user("assigner", "assigner@example.com", "pass123", qualification_level=1)
    register_user("emp", "emp@example.com", "pass123", qualification_level=2)
    headers = auth_headers("assigner", "pass123")
    task_id = client.post("/tasks/", json={"title": "Once Task", "required_qualification": 2}, headers=headers).json()["id"]
    client.post(f"/tasks/{task_id}/auto-assign", headers=headers)
    response = client.post(f"/tasks/{task_id}/auto-assign", headers=headers)
    assert response.status_code == 400


def test_list_assignments():
    register_user("hist_user", "hist@example.com", "pass123", qualification_level=1)
    register_user("hist_emp", "hist_emp@example.com", "pass123", qualification_level=3)
    headers = auth_headers("hist_user", "pass123")
    task_id = client.post("/tasks/", json={"title": "Assigned Task", "required_qualification": 1}, headers=headers).json()["id"]
    client.post(f"/tasks/{task_id}/auto-assign", headers=headers)
    response = client.get("/assignments/", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_assignment_by_id():
    register_user("a_user", "auser@example.com", "pass123", qualification_level=1)
    register_user("a_emp", "aemp@example.com", "pass123", qualification_level=2)
    headers = auth_headers("a_user", "pass123")
    task_id = client.post("/tasks/", json={"title": "A Task", "required_qualification": 1}, headers=headers).json()["id"]
    client.post(f"/tasks/{task_id}/auto-assign", headers=headers)
    assignments = client.get("/assignments/", headers=headers).json()
    assignment_id = assignments[0]["id"]
    response = client.get(f"/assignments/{assignment_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == assignment_id


def test_get_assignment_not_found():
    register_user("searcher", "searcher@example.com", "pass123")
    headers = auth_headers("searcher", "pass123")
    response = client.get("/assignments/99999", headers=headers)
    assert response.status_code == 404
