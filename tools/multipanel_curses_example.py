#!/usr/bin/env python

import curses.panel
import sys

def main():
    stdscr = None
    try:
        optimal_map_width = 50
        optimal_map_height = 20
        optimal_status_bar_height = 4

        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(1)
        curses.start_color()
        curses.curs_set(0)
        stdscr.timeout(10000)
        stack = [stdscr]

        def newwin(*args):
            win = curses.newwin(*args)
            win.box()
            stack.append(win)
            return win

        def refresh(ontop=None):
            if ontop is not None:
                pos = stack.index(ontop)
                stack.append(stack.pop(pos))
            for win in stack:
                win.noutrefresh()
            curses.doupdate()

        def clearall():
            for win in stack:
                win.clear()
            refresh()

        def domenu(*options):
            keys, lines = zip(*options)
            need_height = len(options) + 2
            need_width = max(map(len, lines)) + 5
            width_offset = (avail_width - need_width) / 2
            height_offset = (avail_height - need_height) / 2
            menu = newwin(need_height, need_width, height_offset, width_offset)
            for i, (key, line) in enumerate(options):
                menu.addstr(i + 1, 1, '{}) {}'.format(key, line))
            refresh()
            while 1:
                c = menu.getch()
                if c & 0xff == c:
                    c = chr(c)
                if c in keys:
                    menu.clear()
                    refresh()
                    return c
                curses.beep()

        winsz = maxheight, maxwidth = stdscr.getmaxyx()
        frame = newwin(maxheight, maxwidth, 0, 0)
        sbar_height = 8
        sbar_height_offset = maxheight - sbar_height
        sbar = newwin(sbar_height, maxwidth, sbar_height_offset, 0)
        avail_height = maxheight - sbar_height
        avail_width = maxwidth
        map_width = min([avail_width, optimal_map_width])
        map_height = min([avail_height, optimal_map_height])
        height_padding = (avail_height - map_height) / 2
        width_padding = (avail_width - map_width) / 2
        mapbox = newwin(map_height, map_width, height_padding, width_padding)
        refresh()
        while True:
            option = domenu(('a', 'start game'), ('b', 'battle royale'), ('l', 'load game'), ('q', 'quit'))
            if option == 'q':
                break
            sbar.addstr(1, 1, ' Game started.. hjkl to move, i to view items, q to quit')
            refresh()
            avail_map_width = map_width - 2
            avail_map_height = map_height - 2
            posx = oldx = avail_map_width / 2
            posy = oldy = avail_map_height / 2
            while True:
                mapbox.addstr(oldy + 1, oldx + 1, ' ')
                mapbox.addstr(posy + 1, posx + 1, '@')
                refresh()
                oldx = posx
                oldy = posy
                ch = mapbox.getch()
                if ch & 0xff == ch:
                    ch = chr(ch)
                if ch == 'q':
                    break
                if ch == 'h':
                    posx -= 1
                elif ch == 'j':
                    posy += 1
                elif ch == 'k':
                    posy -= 1
                elif ch == 'l':
                    posx += 1
                elif ch == 'i':
                    mapbox.clear()
                    mapbox.box()
                    mapbox.addstr(2, 2, 'Inventory:')
                    mapbox.addstr(4, 2, '1. Pocket Lint')
                    mapbox.addstr(5, 2, '2. Packet of Peauts')
                    mapbox.addstr(6, 2, '3. Skeleton Arm')
                    mapbox.addstr(8, 2, 'Press the Any Key to return')
                    refresh()
                    mapbox.getch()
                    mapbox.clear()
                    mapbox.box()
                    continue
                else:
                    curses.beep()
                    continue
                posx = posx % avail_map_width
                posy = posy % avail_map_height
                sbar.addstr(2, 1, ' x = {} y = {}'.format(posx, posy).ljust(maxwidth - 2))
                refresh()
        clearall()
    finally:
        if stdscr is not None:
            stdscr.keypad(0)
        curses.echo()
        curses.nocbreak()
        curses.endwin()
        curses.curs_set(1)
    return 0

if __name__ == '__main__':
    sys.exit(main())
