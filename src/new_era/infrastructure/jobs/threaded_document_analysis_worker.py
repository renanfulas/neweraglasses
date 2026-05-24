from __future__ import annotations

from dataclasses import dataclass, field
from queue import Empty, Queue
from threading import Event as ThreadingEvent
from threading import Lock, Thread
from time import monotonic, sleep

from new_era.application.use_cases import RunDocumentAnalysisJob


@dataclass(slots=True)
class ThreadedDocumentAnalysisJobWorker:
    runner: RunDocumentAnalysisJob
    poll_interval_seconds: float = 0.05
    _queue: Queue[str] = field(default_factory=Queue, init=False, repr=False)
    _stop_event: ThreadingEvent = field(default_factory=ThreadingEvent, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _queued_or_running: set[str] = field(default_factory=set, init=False, repr=False)
    _active_count: int = field(default=0, init=False, repr=False)
    _thread: Thread | None = field(default=None, init=False, repr=False)

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = Thread(
                target=self._run_loop,
                name="new-era-document-analysis-worker",
                daemon=True,
            )
            self._thread.start()

    def enqueue(self, job_id: str) -> None:
        self.start()
        with self._lock:
            if job_id in self._queued_or_running:
                return
            self._queued_or_running.add(job_id)
        self._queue.put(job_id)

    def run_once(self, job_id: str):
        return self.runner.execute(job_id=job_id)

    def stop(self, *, timeout_seconds: float = 1.0) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout_seconds)

    def wait_until_idle(self, *, timeout_seconds: float = 2.0) -> bool:
        deadline = monotonic() + timeout_seconds
        while monotonic() < deadline:
            with self._lock:
                is_idle = self._active_count == 0 and not self._queued_or_running
            if is_idle and self._queue.empty():
                return True
            sleep(self.poll_interval_seconds)
        return False

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                job_id = self._queue.get(timeout=self.poll_interval_seconds)
            except Empty:
                continue

            with self._lock:
                self._active_count += 1
            try:
                self.runner.execute(job_id=job_id)
            finally:
                with self._lock:
                    self._active_count -= 1
                    self._queued_or_running.discard(job_id)
                self._queue.task_done()
