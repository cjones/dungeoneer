#!/usr/bin/env python
# vim:ft=python:sw=4:sts=4:ts=8:tw=0:et:sta:fileencoding=utf-8

import locale
locale.setlocale(locale.LC_ALL, '')
import traceback
import argparse
import sys

try:
    import curses
except ImportError:
    CURSES = False
else:
    CURSES = True

sys.dont_write_bytecode = True  # for great justice

from dungeoneer import log, core

DEVELOP = True
FOVBACKENDS = ['tcod']
BACKENDS = ['tcod']
if CURSES:
    BACKENDS.append('curses')
if DEVELOP:
    BACKENDS.append('dummy')


class HelpFormatter(argparse.HelpFormatter):

    _hijack = lambda f: property(f).setter(lambda *x: x)
    _max_help_position = _hijack(lambda x: x._action_max_length + 2)
    _width = _hijack(lambda x: 78)

    def _format_action_invocation(self, action, pad='    ', sep=' '):
        if action.option_strings:
            for option_string in action.option_strings:
                pad, sep = ('', sep) if len(option_string) == 2 else (pad, '=')
            out = pad + ', '.join(action.option_strings)
            if action.nargs != 0:
                out += sep + self._format_args(action, action.dest.upper())
            return out
        return super(HelpFormatter, self)._format_action_invocation(action)


def main(argv=None, engine=core.GameEngine):
    """command-line interface"""
    parser = argparse.ArgumentParser(
            formatter_class=HelpFormatter,
            description=__doc__,
            add_help=False,
            )

    options = parser.add_argument_group('options')
    _ = options.add_argument

    _('-h', '--help', action='help',
            help='show this help message and exit')
    _('-a', '--ascii-mode', default=False, action='store_true',
            help='use ascii characters for tiles')
    _('-d', '--debug-file', metavar='FILE', action=log.AddLogFileAction, logger=log.logger,
            help='enable debug logging to %(metavar)s')

    if len(BACKENDS) > 1:
        _('-m', '--game-mode', choices=BACKENDS, metavar='MODE',
            help='game render mode {%(choices)s} [%(default)s]')

    if len(FOVBACKENDS) > 1:
        _('-f', '--fov-mode', choices=FOVBACKENDS,
                help='select from available fov backends (default: %(default)s)')

    if CURSES:
        _ = options.add_mutually_exclusive_group().add_argument
        _('-c', '--console', dest='game_mode', action='store_const', const='curses',
                help='same as --game-mode=curses')
        _('-g', '--gui', dest='game_mode', action='store_const', const='tcod',
                help='same as --game-mode=tcod')

    parser.set_defaults(
            game_mode=BACKENDS[0],
            fov_mode=FOVBACKENDS[0],
            )

    try:
        opts = parser.parse_args(argv)
        if opts.game_mode == 'dummy':
            log.add_stream(sys.stderr)
            log.enable()
        if opts.game_mode == 'curses':
            opts.ascii_mode = True
        engine(**vars(opts)).run()
    except SystemExit, exc:
        return exc.code
    except KeyboardInterrupt:
        traceback.print_exc()
        return 130
    except:
        traceback.print_exc()
        return 1
    else:
        return 0

if __name__ == '__main__':
    #sys.argv[1:] = '-d debug.log -c'.split()
    sys.exit(main())
