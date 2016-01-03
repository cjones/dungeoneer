def __boot(ctx):

    '''
    To use this, drop it in place of a moudle, and add a leading underscore to
    the real module. This will act as proxy and log all calls to the real
    module, including parameters, return values and exceptions raised.

    This is not suitable for benchmarking/profiling.
    '''

    import logging, sys

    class Proxy(object):
        __slots__ = ('backing', 'name', 'log', 'ns')

        def __init__(self, backing, name, log, ns):
            self.backing = backing
            self.name = name
            self.log = log
            self.ns = ns

        def __call__(self, *args, **kwargs):
            try:
                ret = self.backing(*args, **kwargs)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                exc = sys.exc_info()
                ret = None
            else:
                exc = None
            if kwargs:
                keys, vals = zip(*sorted(kwargs.iteritems()))
            else:
                keys = vals = []
            self.log.debug('{}.{}({}){}'.format(self.ns, self.name, ', '.join(
                map(repr, args) + map('{}={!r}'.format, keys, vals)),
                '  # -> {!r}'.format(ret) if (exc is None and ret is not None)
                else '', exc_info=exc))
            if exc:
                raise exc[0], exc[1], exc[2]
            return ret

    name = ctx.get('__name__', __name__)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(message)s')
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    handler.setLevel(logger.level)
    logger.addHandler(handler)
    handler = logging.FileHandler(name + '-call.log', 'a')
    handler.setFormatter(formatter)
    handler.setLevel(logger.level)
    logger.addHandler(handler)
    pkg = name.split('.')
    _name = '_' + pkg.pop()

    ctx.update({k: Proxy(v, k, logger, name) if callable(v) else v
                for k, v in vars(getattr(__import__(
                '.'.join(pkg), fromlist=[_name]), _name)).iteritems()})


try:
    __boot(globals())
finally:
    del __boot
