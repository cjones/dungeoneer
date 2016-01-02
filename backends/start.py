#!/usr/bin/env python

import sys

from utils import Platform, get_platform, get_input
import gamedata

sys.dont_write_bytecode = True

def main():
    print('Dungoneer! by johnstein')
    print('-----------------------')
    while True:
        print('    Play!               ')
        print('1. Dungeoneer (graphics)')
        print('2. Dungeoneer (ASCII)   ')
        print('3. Rogue-Life           ')
        choice = get_input()
        if choice == '1':
            game = 'Dungeoneer'
            backend = 'sdl'
        elif choice == '2':
            game = 'Dungeoneer'
            backend = 'curses'
        elif choice == '3':
            game = 'life'
            backend = 'curses'
        else:
            continue
        if backend == 'sdl':
            gamedata.GRAPHICSMODE = 'tcod'
            gamedata.ASCIIMODE = False
        else:
            gamedata.GRAPHICSMODE = 'curses'
            gamedata.ASCIIMODE = True
        return __import__(game).main()

if __name__ == '__main__':
    sys.exit(main())
