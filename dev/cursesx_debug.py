#!/usr/bin/env python

import gamedata

if gamedata.GRAPHICSMODE == 'curses':
    try:
        from curses import *
        import curses.ascii as ascii
    except:
        print('Error importing curses!')
        raise ImportError('curses module not available!')

# if set, intercept every curses function call and log it transparently
# don't leave this on, it will fill up disk, and slow the game down to a.. CRAWL.
if gamedata.DEBUGLOG:
    import logging, functools, inspect, sys

    class Logger(logging.Logger):
        formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S')
        def setup(self, file=None, stream=None, level=None):
            self.add_file(file)
            self.add_stream(stream)
            self.setLevel(level)
        def addHandler(self, handler):
            handler.setFormatter(self.formatter)
            handler.setLevel(self.level)
            super(Logger, self).addHandler(handler)
        def add_file(self, path, mode='a'):
            if path is not None:
                self.addHandler(logging.FileHandler(path, mode))
        def add_stream(self, stream):
            if stream is not None:
                self.addHandler(logging.StreamHandler(stream))
        def setLevel(self, level):
            if level is None:
                level = logging.INFO
            elif isinstance(level, basestring):
                level = level.upper()
            super(Logger, self).setLevel(level)
            for handler in self.handlers:
                handler.setLevel(self.level)

    logging.setLoggerClass(Logger)
    logger = logging.getLogger(__name__)
    logger.setup(file=gamedata.DEBUGLOG, level='debug')

    try:
        1 / 0
    except ZeroDivisionError:
        frame = sys.exc_info()[2].tb_frame
        context = frame.f_globals

        def reraise(x, y, z):
            raise x, y, z

        def wrap(wrapped, ns=None, name=None, postprocess=None,
                _debug=logger.debug, _error=logger.error, _reraise=reraise):
            _name = wrapped.__name__ if name is None else name

            @functools.wraps(wrapped)
            def wrapper(*args, **kwargs):
                try:
                    ret = wrapped(*args, **kwargs)
                except:
                    exc = sys.exc_info()
                    ret = None
                else:
                    exc = None
                x = map(repr, args)
                y = map('{}={!r}'.format, *zip(*sorted(kwargs.iteritems()))) if kwargs else []
                if exc is None:
                    log = _debug
                    r = repr(ret)
                    if callable(postprocess):
                        ret = postprocess(ret)
                        r += ' (-> {!r})'.format(ret)
                else:
                    log = _error
                    r = '(raised {})'.format(exc[0].__name__)
                log('{}({}) -> {}'.format(
                    _name if ns is None else
                    '{}.{}'.format(ns, _name),
                    ', '.join(x + y), r), exc_info=exc)
                if exc is None:
                    return ret
                _reraise(*exc)
            return wrapper

        def wrapwin(win, _wrap=wrap):
            class Proxy(object):
                def __getattribute__(self, key):
                    val = getattr(win, key)
                    if inspect.isroutine(val):
                        val = _wrap(val, 'window', key)
                    return val
            return Proxy()

        for key, val in list(context.iteritems()):
            if inspect.isroutine(val) and 'curses' in val.__module__ and __name__ not in val.__module__:
                context[key] = wrap(val, 'curses', key, wrapwin if key == 'newwin' else None)

