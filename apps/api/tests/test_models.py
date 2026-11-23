from sqlalchemy import inspect

from app.database import engine
from app.models import Agent, Task, TaskStatus

EXPECTED_TABLES = {
    "users", "agents", "conversations", "messages", "memories", "tasks",
    "task_steps", "projects", "clients", "files", "reports", "integrations",
    "permissions", "approvals", "activity_logs", "scheduled_jobs",
}


def test_all_tables_exist():
    assert EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names()))


def test_agents_seeded(db):
    keys = {a.key for a in db.query(Agent).all()}
    assert {"master", "research", "tasks", "communication", "clients", "business",
            "developer", "finance", "marketing", "projects", "reporting"} <= keys


def test_task_create_read_roundtrip(db):
    task = Task(
        description="Research this business idea",
        title="Research",
        agent_key="research",
        logs=[{"ts": "t0", "level": "info", "message": "created"}],
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    assert task.id
    assert task.status == TaskStatus.PENDING
    assert task.started_at is None and task.completed_at is None

    fetched = db.query(Task).filter_by(id=task.id).one()
    assert fetched.description == "Research this business idea"
    assert fetched.logs[0]["message"] == "created"

    fetched.status = TaskStatus.COMPLETED
    fetched.result = "done"
    db.commit()
    assert db.query(Task).filter_by(id=task.id).one().result == "done"
