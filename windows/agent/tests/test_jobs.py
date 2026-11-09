# -*- coding: utf-8 -*-
"""JobStore testleri (HTTP olmadan)."""

from __future__ import annotations

import pytest

from agent.errors import Conflict, NotFound
from agent.jobs import JobStore, new_job_id


@pytest.fixture()
def store(tmp_path) -> JobStore:
    return JobStore(tmp_path / "jobs.db")


def make_job(store: JobStore, **overrides):
    source = store._path.parent / "job.txt"
    source.write_text("test", encoding="utf-8")
    values = dict(
        job_id=new_job_id(),
        job_name="Test",
        filename="a.txt",
        kind="text",
        content_type="text/plain",
        options={"copies": 1},
        file_path=str(source),
    )
    values.update(overrides)
    return store.create(**values)


def test_create_and_get(store):
    job = make_job(store)
    assert job.status == "queued"
    fetched = store.get(job.id)
    assert fetched is not None and fetched.id == job.id
    assert store.queue_depth() == 1


def test_get_missing(store):
    assert store.get("job_yok") is None
    with pytest.raises(NotFound):
        store.require("job_yok")


def test_update_and_list(store):
    first = make_job(store)
    second = make_job(store)
    store.update(first.id, status="done", printed_pages=2, pages=2)

    jobs = store.list(limit=10)
    assert len(jobs) == 2
    assert {j.id for j in jobs} == {first.id, second.id}
    assert store.get(first.id).status == "done"


def test_next_queued_is_fifo(store):
    first = make_job(store)
    make_job(store)
    assert store.next_queued().id == first.id
    store.update(first.id, status="done")
    assert store.next_queued().id != first.id


def test_idempotency(store):
    job = make_job(store, idempotency_key="abc")
    assert store.by_idempotency("abc").id == job.id
    assert store.by_idempotency("yok") is None


def test_fail_stale(store):
    job = make_job(store)
    store.update(job.id, status="printing")
    assert store.fail_stale() == 1
    failed = store.get(job.id)
    assert failed.status == "failed"
    assert failed.error_code == "agent_restarted"


def test_retry_only_failed(store):
    job = make_job(store)
    with pytest.raises(Conflict):
        store.retry(job.id)

    store.update(job.id, status="failed")
    clone = store.retry(job.id)
    assert clone.id != job.id
    assert clone.status == "queued"
    assert clone.file_path == job.file_path
