from __future__ import annotations

from PySide6.QtNetwork import QLocalServer, QLocalSocket


def acquire_single_instance(name: str) -> QLocalServer | None:
    socket = QLocalSocket()
    socket.connectToServer(name)
    if socket.waitForConnected(200):
        socket.disconnectFromServer()
        return None
    QLocalServer.removeServer(name)
    server = QLocalServer()
    if not server.listen(name):
        return None
    return server
