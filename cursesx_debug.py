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
        for key, val in list(context.iteritems()):
            if inspect.isroutine(val) and 'curses' in val.__module__ and __name__ not in val.__module__:
                def wrap(wrapped, funcname, _debug=logger.debug):
                    _funcname = funcname
                    @functools.wraps(wrapped)
                    def wrapper(*args, **kwargs):
                        try:
                            ret = wrapped(*args, **kwargs)
                        except:
                            exc = sys.exc_info()
                            ret = None
                        else:
                            exc = None
                            if _funcname == 'newwin':
                                proxied = ret
                                class Proxy(object):
                                    def __getattribute__(self, key):
                                        val = getattr(proxied, key)
                                        if inspect.isroutine(val):
                                            def wrapmethod(wrappedmethod, _methname):
                                                @functools.wraps(wrappedmethod)
                                                def methodwrapper(*methargs, **methkwargs):
                                                    try:
                                                        methret = wrappedmethod(*methargs, **methkwargs)
                                                    except:
                                                        methexc = sys.exc_info()
                                                        methret = None
                                                    else:
                                                        methexc = None
                                                    _debug('window.{}(*{!r}, **{!r}) -> {})'.format(
                                                        _methname, methargs, methkwargs,
                                                        repr(methret) if methexc is None else methexc[1]),
                                                        exc_info=methexc)
                                                    if methexc is None:
                                                        return methret
                                                    reraise(*methexc)
                                                methodwrapper.wrappedmethod = wrappedmethod
                                                return methodwrapper
                                            val = wrapmethod(val, _methname=key)
                                        return val
                                ret = Proxy()
                        _debug('curses.{}(*{!r}, **{!r}) -> {})'.format(
                            _funcname, args, kwargs,
                            repr(ret) if exc is None else exc[1]), exc_info=exc)
                        if exc is None:
                            return ret
                        reraise(*exc)
                    wrapper.wrapped = wrapped
                    return wrapper
                context[key] = wrap(val, key)

