"""
Tests for tasks API endpoints.
"""
import pytest


@pytest.fixture(autouse=True)
def clear_tasks():
    """Reset the in-memory task store before and after each test."""
    from main import user_tasks
    user_tasks.clear()
    yield
    user_tasks.clear()


@pytest.fixture
def created_task(client):
    """Create a task and return it."""
    response = client.post("/api/tasks", json={
        "title": "Review Q4 inventory levels",
        "priority": "high",
        "dueDate": "2026-08-01"
    })
    assert response.status_code == 200
    return response.json()


class TestTasksEndpoints:
    """Test suite for task-related endpoints."""

    def test_get_tasks_empty(self, client):
        """Test that the task list starts empty."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_task(self, client):
        """Test creating a task."""
        response = client.post("/api/tasks", json={
            "title": "Approve Tokyo warehouse orders",
            "priority": "medium",
            "dueDate": "2026-09-15"
        })
        assert response.status_code == 200

        task = response.json()
        assert task["title"] == "Approve Tokyo warehouse orders"
        assert task["priority"] == "medium"
        assert task["dueDate"] == "2026-09-15"
        assert task["status"] == "pending"
        assert isinstance(task["id"], int)

    def test_create_task_defaults_priority(self, client):
        """Test that priority defaults to medium when omitted."""
        response = client.post("/api/tasks", json={
            "title": "Check reorder points",
            "dueDate": "2026-09-15"
        })
        assert response.status_code == 200
        assert response.json()["priority"] == "medium"

    def test_create_task_strips_title(self, client):
        """Test that surrounding whitespace is stripped from the title."""
        response = client.post("/api/tasks", json={
            "title": "   Padded title   ",
            "priority": "low",
            "dueDate": "2026-09-15"
        })
        assert response.status_code == 200
        assert response.json()["title"] == "Padded title"

    def test_create_task_empty_title(self, client):
        """Test that a blank title is rejected."""
        response = client.post("/api/tasks", json={
            "title": "   ",
            "priority": "low",
            "dueDate": "2026-09-15"
        })
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_create_task_missing_field(self, client):
        """Test that a missing required field returns a validation error."""
        response = client.post("/api/tasks", json={"priority": "low"})
        assert response.status_code == 422

    def test_task_ids_avoid_mock_task_collision(self, client, created_task):
        """Test that API task ids start above the client's mock task ids."""
        # The client merges these with mock tasks that use ids 1, 2, 3...
        assert created_task["id"] >= 1000

    def test_task_ids_are_unique(self, client):
        """Test that sequential creates produce unique ids."""
        ids = []
        for i in range(3):
            response = client.post("/api/tasks", json={
                "title": f"Task {i}",
                "priority": "low",
                "dueDate": "2026-09-15"
            })
            ids.append(response.json()["id"])

        assert len(set(ids)) == 3

    def test_get_tasks_returns_newest_first(self, client):
        """Test that tasks are listed newest first."""
        for i in range(3):
            client.post("/api/tasks", json={
                "title": f"Task {i}",
                "priority": "low",
                "dueDate": "2026-09-15"
            })

        titles = [t["title"] for t in client.get("/api/tasks").json()]
        assert titles == ["Task 2", "Task 1", "Task 0"]

    def test_toggle_task_to_completed(self, client, created_task):
        """Test toggling a pending task marks it completed."""
        response = client.patch(f"/api/tasks/{created_task['id']}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    def test_toggle_task_is_reversible(self, client, created_task):
        """Test that toggling twice returns the task to pending."""
        task_id = created_task["id"]
        client.patch(f"/api/tasks/{task_id}")
        response = client.patch(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    def test_toggle_task_persists(self, client, created_task):
        """Test that a toggle is reflected in the task list."""
        client.patch(f"/api/tasks/{created_task['id']}")

        tasks = client.get("/api/tasks").json()
        assert tasks[0]["status"] == "completed"

    def test_toggle_nonexistent_task(self, client):
        """Test toggling a task that doesn't exist."""
        response = client.patch("/api/tasks/999999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_task(self, client, created_task):
        """Test deleting a task."""
        response = client.delete(f"/api/tasks/{created_task['id']}")
        assert response.status_code == 200
        assert response.json()["success"] is True

        assert client.get("/api/tasks").json() == []

    def test_delete_only_removes_target(self, client):
        """Test that deleting one task leaves the others intact."""
        ids = []
        for i in range(3):
            response = client.post("/api/tasks", json={
                "title": f"Task {i}",
                "priority": "low",
                "dueDate": "2026-09-15"
            })
            ids.append(response.json()["id"])

        client.delete(f"/api/tasks/{ids[1]}")

        remaining = [t["id"] for t in client.get("/api/tasks").json()]
        assert sorted(remaining) == sorted([ids[0], ids[2]])

    def test_delete_nonexistent_task(self, client):
        """Test deleting a task that doesn't exist."""
        response = client.delete("/api/tasks/999999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
