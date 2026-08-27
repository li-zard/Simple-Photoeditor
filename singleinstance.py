"""Одноэкземплярность приложения (этап 5.2 роадмапа).

Предпосылка для ассоциаций файлов: двойной щелчок по файлу в Проводнике
должен открывать его в уже работающем окне, а не запускать новый процесс.

Механизм (стандартный для Qt):
- при старте процесс пытается подключиться QLocalSocket'ом к серверу
  с именем "SimplePhotoEditor";
- если сервер отвечает — процесс не первый: он отправляет путь к файлу
  и завершается (activate() возвращает False);
- если сервера нет — процесс создаёт QLocalServer и слушает; сигнал
  fileOpened(str) выстреливает для каждого принятого пути.

Крах предыдущего экземпляра обработан через QLocalServer.removeServer():
остаточный сокет удаляется перед listen(), поэтому «мёртвый» сервер
не блокирует запуск нового экземпляра.
"""

import logging

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtNetwork import QLocalSocket, QLocalServer

logger = logging.getLogger("photoeditor.singleinstance")

SERVER_NAME = "SimplePhotoEditor"


class SingleInstance(QObject):
    """Гарантирует единственный экземпляр приложения.

    Использование в main.py:

        single = SingleInstance()
        if not single.activate(sys.argv[1] if len(sys.argv) > 1 else ""):
            sys.exit(0)  # путь отправлен работающему экземпляру
        ...
        single.fileOpened.connect(window.openFile)
    """

    #: Выстреливает с путём к файлу, присланным вторым экземпляром.
    fileOpened = pyqtSignal(str)

    def __init__(self, parent=None, server_name=SERVER_NAME):
        super().__init__(parent)
        self.server_name = server_name
        self._server = None

    # ------------------------------------------------------------------
    # Первый/второй экземпляр
    # ------------------------------------------------------------------

    def activate(self, file_path=""):
        """Попытаться стать единственным экземпляром приложения.

        Возвращает True, если мы первые (нужно продолжать запуск) и
        False, если путь отправлен работающему экземпляру (нужно выйти).
        При невозможности поднять сервер (неожиданная ошибка) возвращает
        True — приложение работает без одноэкземплярности.
        """
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if socket.waitForConnected(200):
            payload = (file_path or "").encode("utf-8")
            socket.write(payload)
            socket.waitForBytesWritten(200)
            socket.disconnectFromServer()
            logger.debug("Path forwarded to running instance: %r", file_path)
            return False

        # Мы первые. removeServer() вычищает сокет, оставшийся от
        # рухнувшего предыдущего экземпляра (иначе listen() провалится).
        QLocalServer.removeServer(self.server_name)
        self._server = QLocalServer(self)
        if not self._server.listen(self.server_name):
            logger.error("Cannot listen on local server %r: %s",
                         self.server_name, self._server.errorString())
            self._server = None
            return True  # продолжаем без одноэкземплярности

        self._server.newConnection.connect(self._on_new_connection)
        logger.debug("Listening as the single instance (%s)", self.server_name)
        return True

    def shutdown(self):
        """Остановить сервер (используется в тестах)."""
        if self._server is not None:
            self._server.close()
            self._server = None

    # ------------------------------------------------------------------
    # Приём путей от вторых экземпляров
    # ------------------------------------------------------------------

    def _on_new_connection(self):
        """Принять входящее соединение и подписаться на данные."""
        connection = self._server.nextPendingConnection()
        if connection is None:
            return
        connection.readyRead.connect(
            lambda c=connection: self._read_path(c))

    def _read_path(self, connection):
        """Прочитать путь из соединения и выстрелить fileOpened."""
        data = bytes(connection.readAll())
        path = data.decode("utf-8", errors="replace").strip("\x00")
        if path:
            logger.debug("Received path from second instance: %r", path)
            self.fileOpened.emit(path)
        connection.disconnectFromServer()
        connection.deleteLater()
