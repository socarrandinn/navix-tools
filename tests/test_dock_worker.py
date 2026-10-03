import threading

from dock.worker import run_async


def test_run_async_delivers_on_gui_thread(qtbot):
    main = threading.get_ident()
    seen = {}

    def work():
        seen["worker"] = threading.get_ident()
        return 42

    def done(value):
        seen["value"] = value
        seen["callback"] = threading.get_ident()

    run_async(work, done, lambda exc: None)
    qtbot.waitUntil(lambda: "value" in seen, timeout=3000)
    assert seen["value"] == 42
    assert seen["worker"] != main
    assert seen["callback"] == main


def test_run_async_reports_errors_on_gui_thread(qtbot):
    main = threading.get_ident()
    seen = {}

    def work():
        raise RuntimeError("falló")

    def failed(exc):
        seen["exc"] = exc
        seen["callback"] = threading.get_ident()

    run_async(work, lambda value: None, failed)
    qtbot.waitUntil(lambda: "exc" in seen, timeout=3000)
    assert str(seen["exc"]) == "falló"
    assert seen["callback"] == main
