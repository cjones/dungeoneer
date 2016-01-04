#!/usr/bin/env python

if __name__ == '__main__':
    import sys
    sys.dont_write_bytecode = True
    from dungeoneer import main
    sys.exit(main())
