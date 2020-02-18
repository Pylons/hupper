from __future__ import print_function
import sys

from .interfaces import ILogger


class LogLevel:
    ERROR = 0
    INFO = 1
    DEBUG = 2


class DefaultLogger(ILogger):
    def __init__(self, level):
        self.level = level

    def _out(self, level, msg):
        if level <= self.level:
            print(msg, file=sys.stderr)

    def error(self, msg):
        self._out(LogLevel.ERROR, '[ERROR] ' + msg)

    def info(self, msg):
        self._out(LogLevel.INFO, msg)

    def debug(self, msg):
        self._out(LogLevel.DEBUG, '[DEBUG] ' + msg)


class SilentLogger(ILogger):
    def error(self, msg):
        pass

    def info(self, msg):
        pass

    def debug(self, msg):
        pass
