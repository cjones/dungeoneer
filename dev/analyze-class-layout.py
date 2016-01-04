#!/usr/bin/env python

"""Show the compositional relationship between classes in a python file.

This is orthogonal to how classes relate via object inheritence, if they do at
all. It works by analyzing the bytcode for each class to see what other classes
it might refer to directly by name -- and thus, presumably, instantiateing an
instance of, though this isn't promised. It could be accessing a class variable
or something even weirder, but generally this will still make sense.

Also note that this won't catch classes that are composed by reference. That
is, it is passed a class as a parameter and then calls that, we won't see it.
It must be named explicitly.

This is intended as a crude tool to help make sense of a large, unfamiliar
project or as an aid to restructuring a project. The output should not be
treated as anything more than hints.
"""

import argparse
import tempfile
import opcode
import sys
import os

__version__ = '0.1'
__author__ = 'Chris Jones <cjones@gmail.com>'
__license__ = 'BSD (2-clause)'
__all__ = ['analyze_class_layout']


def _module_from_code(code, file):
    fd, empty_file = tempfile.mkstemp(suffix='.py', prefix='tmp', dir=os.getcwd(), text=True)
    try:
        empty_name = os.path.splitext(os.path.basename(empty_file))[0]
        sys.dont_write_bytecode = True
        empty_mod = __import__(empty_name)
        mod_type = type(empty_mod)
        empty_context = vars(empty_mod)
    finally:
        for func, arg in [(os.close, fd), (os.unlink, empty_file)]:
            try:
                func(arg)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                pass
    name = os.path.splitext(os.path.basename(file))[0]
    context = dict(empty_context, __name__=name or 'module', __file__=file)
    exec code in context
    module = mod_type(file)
    module.__dict__.update(context)
    return module


def _run_code(code, entry='main', *args):
    module = module_from_code(code, code.co_filename)
    argv = sys.argv[:]
    sys.argv[:] = [module.__file__] + list(args)
    try:
        getattr(module, entry)()
    finally:
        sys.argv[:] = argv


def disco(co, r=None, first=True, curcls=None):
    if first:
        if r is None:
            r = {'class_code': {}}
    else:
        r.setdefault('class_refs', {})
        if curcls is None:
            for clsname, clsco in r['class_code'].iteritems():
                if clsco is co:
                    curcls = clsname
                    break
    t = type(co)
    c = co.co_code
    n = len(c)
    i = x = f = 0
    m = None
    while i < n:
        o = ord(c[i])
        i += 1
        if o >= opcode.HAVE_ARGUMENT:
            v = ord(c[i]) + (ord(c[i + 1]) << 8) + x
            i += 2
            if o == opcode.EXTENDED_ARG:
                k, v = 'extend', (v << 16)
                x = v
            else:
                x = 0
                if o in opcode.hasname:
                    v = co.co_names[v]
                    if first and f == 1 and opcode.opname[o] == 'STORE_NAME':
                        f, r['class_code'][v] = 0, m
                elif o in opcode.hasconst:
                    v = co.co_consts[v]
                    if isinstance(v, t):
                        disco(v, r, first, curcls)
                        m = v
                elif o in opcode.haslocal:
                    v = co.co_varnames[v]
                elif o in opcode.hasfree:
                    v = (co.co_cellvars + co.co_freevars)[v]
                else:
                    pass
            if not first and v in r['class_code'] and curcls is not None and v != curcls:
                r['class_refs'].setdefault(curcls, set()).add(v)
        if first and opcode.opname[o] == 'BUILD_CLASS':
            f = 1
    return r


def analyze_class_layout(input=None, output=None):
    if input is None:
        input = sys.stdin
    if output is None:
        output = sys.stdout
    file = getattr(input, 'name', None) or ''
    if file and os.path.isfile(file):
        file = os.path.abspath(file)
    try:
        code = compile(''.join(input), file, 'exec')
    except SyntaxError, exc:
        print >> sys.stderr, 'there is a syntax error in your code, please do better'
        return 1
    by_referer = disco(code, first=0, r=disco(code))['class_refs']
    by_referent = {}
    for key, vals in by_referer.iteritems():
        for val in vals:
            by_referent.setdefault(val, set()).add(key)
    splits, rows, addsep = [], [], lambda: splits.append(len(rows))
    addsep()
    for key, vals in sorted(by_referer.iteritems()):
        for i, val in enumerate(sorted(vals)):
            rows.append((key if i == 0 else '', 'REFERS TO' if i == 0 else '',  val))
    addsep()
    singles = []
    for key, vals in sorted(by_referent.iteritems()):
        dst, text = (singles, 'ONLY REFFED BY') if len(vals) == 1 else (rows, 'MULTIPLY REFFED BY')
        for i, val in enumerate(sorted(vals)):
            dst.append((key if i == 0 else '', text if i == 0 else '', val))
    if singles:
        addsep()
        rows.extend(singles)
    addsep()
    cols = zip(*rows)
    fmt = '| {} |'.format(' | '.join('{{:{:s}{:d}s}}'.format(j,
        max(map(len, c))) for c, j in zip(cols, '<<<'))).format
    sep = reduce(lambda x, y: x.replace(*y), (' -', '|+'), fmt(*[''] * len(cols)))
    if cols:
        lines = map(fmt, *cols)
        for split in sorted(splits, reverse=True):
            lines.insert(split, sep)
        print >> output, os.linesep.join(lines)
        return 0
    else:
        print >> sys.stderr, 'nothing to analyze or no class relationships found'
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, version=__version__)
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), default='-')
    parser.add_argument('input', type=argparse.FileType('r'), default='-', nargs='?')
    opts = parser.parse_args(argv)
    return analyze_class_layout(**vars(opts))

if __name__ == '__main__':
    #sys.argv[1:] = ['dungeoneer.py']
    sys.exit(main())
