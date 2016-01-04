"""project-wide logging setup """

import argparse
import logging
import abc


class BaseLogger(logging.Logger):
    """some improvements and helper funcions to the library base logger"""

    _format = '%(asctime)s [%(levelname)s] %(message)s'
    _datefmt = '%Y-%m-%d %H:%M:%S'

    def __init__(self, *args, **kwargs):
        self._formatter = None
        super(BaseLogger, self).__init__(*args, **kwargs)

    @property
    def formatter(self):
        if self._formatter is None:
            self._formatter = logging.Formatter(self._format, self._datefmt)
        return self._formatter

    def setLevel(self, level=None):
        if level is None:
            level = logging.INFO
        elif isinstance(level, basestring):
            level = level.upper()
        ret = super(BaseLogger, self).setLevel(level)
        for handler in self.handlers:
            handler.setLevel(self.level)
        return ret

    set_level = setLevel

    def addHandler(self, handler):
        handler.setFormatter(self.formatter)
        handler.setLevel(self.level)
        return super(BaseLogger, self).addHandler(handler)

    def make_handler(self, cls, arg, *extra):
        if arg is not None:
            return self.addHandler(cls(arg, *extra))

    def add_file(self, file, mode='a'):
        return self.make_handler(logging.FileHandler, file, mode)

    def add_stream(self, stream):
        return self.make_handler(logging.StreamHandler, stream)

    def enable(self, enabled=True):
        self.disabled = not enabled

    def disable(self, disabled=True):
        self.disabled = disabled


class ExtendedLogger(BaseLogger):
    """
    Detect and render new-style string formatting. in retrospect, this should
    be a custom Formatter, but whatever, it works.
    """

    @classmethod
    def parse_string_format(cls, string):
        for literal_text, field_name, format_spec, conversion in str._formatter_parser(string):
            if field_name is not None:
                yield field_name
            if format_spec is not None:
                for nested_field_name in cls.parse_string_format(format_spec):
                    yield nested_field_name

    def _log(self, level, msg, args, **kwargs):
        extra = kwargs.pop('extra', None)
        exc_info = kwargs.pop('exc_info', None)
        if msg is not None:
            if args or kwargs:
                args = list(args)
                format_args = []
                format_kwargs = {}
                for field_name in self.parse_string_format(msg):
                    if field_name:
                        format_kwargs[field_name] = kwargs.pop(field_name, None)
                    elif args:
                        format_args.append(args.pop(0))
                try:
                    msg = msg.format(*format_args, **format_kwargs)
                except:
                    msg = 'format error: ' + repr((msg, format_args, format_kwargs))
                args = tuple(args)
            return super(ExtendedLogger, self)._log(level, msg, args, extra=extra, exc_info=exc_info, **kwargs)


class CallbackAction(argparse.Action):
    """extension action for argparse that allows a simple callback like optparse used to do"""

    def __init__(self, *args, **kwargs):
        self.__callback_func = kwargs.pop('callback', None)
        nargs = kwargs.pop('nargs', None)
        if nargs is None:
            nargs = 0
        if nargs == 0:
            kwargs['metavar'] = argparse.SUPPRESS
        super(CallbackAction, self).__init__(*args, **dict(kwargs,
            dest=argparse.SUPPRESS, default=argparse.SUPPRESS, nargs=nargs))

    def __call__(self, parser, namespace, values, option_string=None):
        self.__callback_func(*values)


class LoggingCallbackAction(CallbackAction):
    """abstract base class for loging config callbacks"""
    nargs = 0

    def __init__(self, *args, **kwargs):
        self._logger = kwargs.pop('logger', None)
        if self._logger is None:
            self._logger = getLogger(None)
        super(LoggingCallbackAction, self).__init__(*args, **dict(kwargs,
            callback=self.callback, nargs=self.nargs))

    @abc.abstractmethod
    def callback(self, arg=None):
        raise NotImplementedError


class SetLogLevelAction(LoggingCallbackAction):
    """argparse action that sets the log level directly"""
    choices = ('debug', 'info', 'warn', 'error')
    nargs = 1

    def __init__(self, *args, **kwargs):
        super(SetLogLevelAction, self).__init__(*args, **dict(kwargs,
            choices=self.choices))

    def callback(self, level):
        self._logger.setLevel(level)
        self._logger.enable()


class AddLogFileAction(LoggingCallbackAction):
    """argparse action that adds a logfile directly"""
    nargs = 1

    def callback(self, file):
        self._logger.add_file(file)
        self._logger.enable()


# use this instead of instantiating Logger's directly so it gets registered in
# the logging hierarchy and managed properly.
logging.setLoggerClass(ExtendedLogger)

# initialize an application-wide logger
logger = logging.getLogger(__name__)
logger.set_level(logging.DEBUG)

# this is for silencing warnings if the user of this module chooses not to
# configure logging. see module docs for discussion about this.
logger.addHandler(logging.NullHandler())

# start out disabled. regular users don't need debug spam.
logger.disable()

# expose log methods so one can do "import log" then log.debug(...) from any
# file in the project without more setup.
debug = logger.debug
info = logger.info
warn = logger.warn
error = logger.error
exception = logger.exception

# exported for initial setup
add_stream = logger.add_stream
add_file = logger.add_file
set_level = logger.setLevel
enable = logger.enable
disable = logger.disable
