from dock.__main__ import configure_app


def test_closing_settings_does_not_quit_the_app(qapp):
    previous = qapp.quitOnLastWindowClosed()
    try:
        configure_app(qapp)
        assert qapp.quitOnLastWindowClosed() is False
    finally:
        qapp.setQuitOnLastWindowClosed(previous)
