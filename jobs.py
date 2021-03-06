import logging
import time
from threading import Thread, Lock

from mcrcon import MCRcon

from atimer import AsyncCountdownTimer


class _RConsole:
    __lock_connection_action = Lock()
    __lock_auto_close_thread = Lock()

    __disconnect_seconds = 100

    def __init__(self, host, port: int, password, use_tls: bool = True):
        tls = {
            True: 1,
            False: 0
        }
        self.__auto_close_timer = AsyncCountdownTimer(self.__disconnect_seconds, self.__disconnect)
        self.__con = MCRcon(host, password, port, tls[use_tls])

    def execute(self, command: str, timeout: int = 0) -> str:
        """
        Execute a command, return its response. :param command: the command to be executed. :param timeout: timeout
        in seconds. If it is set to 0, the function waits until a response is received. If timed out,
        an `TimedOutException` will be thrown. :return: the response echo.
        """
        # check connection
        with self.__lock_connection_action:
            if not self.__con.socket:
                self.__con.connect()
        with self.__lock_auto_close_thread:
            self.__auto_close_timer.reset()
            self.__auto_close_timer = AsyncCountdownTimer(self.__disconnect_seconds, self.__disconnect)
            self.__auto_close_timer.start()

        # TODO: implement timeout
        if timeout:
            raise NotImplementedError("Sorry, timeout has not been implemented")

        # execute command
        logging.info(f'Execute command: {command}')
        return self.__con.command(command)

    def __del__(self):
        if self.__auto_close_timer:
            self.__auto_close_timer.reset()

    def __disconnect(self):
        disconnected = False
        with self.__lock_connection_action:
            if self.__con.socket:
                self.__con.disconnect()
                disconnected = True
        if disconnected:
            logging.info('Console is inactive. Disconnected from RCON server.')


class TimedOutException(Exception):
    pass


class BaseTask:

    def should_run(self, year: int, month: int, day: int, hour: int, minute: int, week_day: int) -> bool:
        # week_day: 1,2,3,4,5,6,7
        raise NotImplementedError("You have to override `should_run` before enabling your task.")

    def run(self, console: _RConsole) -> None:
        raise NotImplementedError("You have to override `run` method in order to implement your task.")


class TaskManager(Thread):
    __tasks = set()
    __running = True

    def __init__(self, host, port: int, password, use_tls: bool = True, poll_wait=0.5):
        self.__console = _RConsole(host, port, password, use_tls)
        self.__poll_wait = poll_wait
        super().__init__()

    def add_task(self, task: BaseTask):
        self.__tasks.add(task)

    def start(self) -> None:
        self.__running = True
        super().start()

    def stop(self):
        self.__running = False

    def run(self) -> None:
        while self.__running:
            tm = time.localtime()
            for task in self.__tasks:
                if isinstance(task, BaseTask) and \
                        task.should_run(tm.tm_year, tm.tm_mon, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_wday + 1):
                    task.run(self.__console)
            time.sleep(self.__poll_wait)
