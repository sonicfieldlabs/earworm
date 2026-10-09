"""The heavy lease says how long a holder waited for it (24 September 2026)."""

import threading
import time

from akousma import resource_admission as admission


def test_the_wait_behind_another_holder_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv("LISTENINGSTACK_RESOURCE_DIR", str(tmp_path))
    held = threading.Event()
    release = threading.Event()

    def holder():
        with admission.heavy_lease("oida", "generate"):
            held.set()
            release.wait(5)

    thread = threading.Thread(target=holder)
    thread.start()
    held.wait(5)
    threading.Timer(0.4, release.set).start()
    with admission.heavy_lease("germ", "generate"):
        waited = admission.last_wait_seconds()
    thread.join()
    assert waited is not None and 0.3 < waited < 3
    with admission.heavy_lease("germ", "generate"):
        assert admission.last_wait_seconds() < 0.3, "an uncontested lease records almost no wait"


def test_a_thread_that_never_waited_has_no_record():
    result = {}
    thread = threading.Thread(target=lambda: result.update(value=admission.last_wait_seconds()))
    thread.start()
    thread.join()
    assert result["value"] is None
