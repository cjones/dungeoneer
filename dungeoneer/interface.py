
import sys
import os

from dungeoneer import CURSES, tcod, log

if CURSES:
    import curses.ascii
else:
    curses = None


class KeypressEvent(object):

    def __init__(self, keycode, charcode, keychar, pressed=False, lalt=False,
                 lctrl=False, ralt=False, rctrl=False, shift=False):
        self.keycode = keycode
        self.charcode= charcode
        self.keychar = keychar
        self.pressed = pressed
        self.lalt    = lalt
        self.lctrl   = lctrl
        self.ralt    = ralt
        self.rctrl   = rctrl
        self.shift   = shift


class GUI(object):
    seq = 0

    def __init__(self, engine):
        self.engine = engine
        self.window_stack = [engine.stdscr]
        self.curses_needs_flush = False

    def fatal_error(self, message):
        raise RuntimeError(message)

    def isgameover(self):
        if self.engine.game_mode == 'tcod':
            return tcod.console_is_window_closed()
        elif self.engine.game_mode == 'curses':
            return False
        else:
            self.err_graphicsmode('isgameover')

    # curses helper functions, not applicable to sdl backend these need to move
    # into their own backend support module similar to tbod.py... later

    def raise_window(self, win):
        try:
            pos = self.window_stack.index(win)
        except ValueError:
            log.warn('window not found {!r}', win)
        else:
            self.window_stack.append(self.window_stack.pop(pos))

    def refresh(self, ontop=None, flush=False):
        if ontop is not None:
            self.raise_window(ontop)
        if flush:
            self.curses_console_flush(force=True)
        else:
            self.curses_needs_flush = True

    def curses_console_flush(self, force=False):
        if self.window_stack and (force or self.curses_needs_flush):
            self.curses_needs_flush = False
            for win in self.window_stack:
                win.noutrefresh()
            curses.doupdate()

    def clearall(self):
        for win in self.window_stack:
            win.clear()
        self.refresh()

    def delwin(self, win):
        win.clear()
        win.refresh()
        while win in self.window_stack:
            self.window_stack.remove(win)
        for win in self.window_stack:
            win.touchwin()
            win.refresh()

    def newwin(self, height, width, ypos, xpos, box=False):
        window = curses.newwin(height, width, ypos, xpos)
        if box:
            window.box()
        self.window_stack.append(window)
        return window

    def new_window(self, nwidth, nheight, xpos=0, ypos=0):
        log.debug('asked to create a new window {}x{}', nwidth, nheight)
        if self.engine.game_mode == 'tcod':
            con = tcod.console_new(nwidth, nheight)
        elif self.engine.game_mode == 'curses':
            con = self.newwin(nheight, nwidth, ypos, xpos, box=True)
            self.refresh()
        else:
            self.err_graphicsmode('console')
            con = None
        log.debug('asked to create a new window {}x{} at {},{}, returning {!r}', nwidth, nheight, xpos, ypos, con)
        return con

    def clear(self, con):
        log.debug('asked to clear the window: {!r}', con)
        if self.engine.game_mode == 'tcod':
            tcod.console_clear(con)
        elif self.engine.game_mode == 'curses':
            con.clear()
            self.refresh()
        else:
            self.err_graphicsmode('clear')

    def draw_rect(self, con, xx, yy, nwidth, nheight, clear, bkg=tcod.BKGND_SCREEN, bg_color=None):
        log.debug('asked to draw a box. not implemented in curses')
        if self.engine.game_mode == 'tcod':
            if bg_color:
                tcod.console_set_default_background(con, bg_color)
            tcod.console_rect(con, xx, yy, nwidth, nheight, clear, bkg)
        elif self.engine.game_mode == 'curses':
            pass
        else:
            self.err_graphicsmode('draw_rect')

    def print_rect(self, con, xx, yy, nwidth, nheight, val, bkg=tcod.BKGND_NONE, align=tcod.LEFT):
        log.debug('asked to print string {!r} at {},{} of window {!r}', val, xx, yy, con)
        if self.engine.game_mode == 'tcod':
            tcod.console_print_rect_ex(con, xx, yy, nwidth, nheight, bkg, align, val)
        elif self.engine.game_mode == 'curses':
            lines = val.splitlines()
            for offset, line in enumerate(lines):
                yodawg = yy + offset
                try:
                    con.addstr(yodawg, xx, line)
                except:
                    log.exception('failed to write {!r} to {!r} at ({},{})', line, con, xx, yodawg)
                else:
                    self.refresh()
        else:
            self.err_graphicsmode('print_rect')

    def print_str(self, con, xx, yy, val, bkg=tcod.BKGND_NONE, align=tcod.LEFT):
        log.debug('asked to print string {!r} to window {!r} at {},{}', val, con, xx, yy)
        if self.engine.game_mode == 'tcod':
            tcod.console_print_ex(con, xx, yy, bkg, align, val)
        elif self.engine.game_mode == 'curses':
            con.addstr(yy, xx, val)
            self.refresh()
        elif self.engine.game_mode == 'dummy':
            print val
        else:
            self.err_graphicsmode('print_str')

    def print_char(self, con, xx, yy, val, bkg=tcod.BKGND_NONE, align=tcod.LEFT, fg_color=None, bg_color=None):
        log.debug('asked to print char {!r} to window {!r} at {},{} with fg={!r}, bg={!r}',
                     val, con, xx, yy, fg_color, bg_color)
        if self.engine.game_mode == 'tcod':
            tcod.console_put_char_ex(con, xx, yy, val, fg_color, bg_color)
        elif self.engine.game_mode == 'curses':
            con.addstr(yy, xx, val, fg_color)
            self.refresh()
        else:
            self.err_graphicsmode('print_char')

    def get_height_rect(self, con, xx, yy, nwidth, nheight, val):
        if self.engine.game_mode == 'tcod':
            return tcod.console_get_height_rect(con, xx, yy, nwidth, nheight, val)
        elif self.engine.game_mode == 'curses':
            return len(val.splitlines())
        else:
            self.err_graphicsmode('get_height_rect')

    def prep_keyboard(self, delay, interval): #can this be combined with prep_console?
        if self.engine.game_mode == 'tcod':
            tcod.console_set_keyboard_repeat(delay, interval)

    def prep_console(self, con, nwidth, nheight):
        log.debug('prepping console {!r}', con)
        if self.engine.game_mode == 'tcod':
            tcod.console_set_custom_font('resources/oryx_tiles3.png',
                    tcod.FONT_TYPE_GREYSCALE | tcod.FONT_LAYOUT_TCOD, 32, 12)
            tcod.console_init_root(nwidth, nheight, 'johnstein\'s self of RogueLife!', False, tcod.RENDERER_SDL)
            tcod.sys_set_fps(30)
            rootcon = 0
            tcod.console_map_ascii_codes_to_font(256   , 32, 0, 5)  #map all characters in 1st row
            tcod.console_map_ascii_codes_to_font(256+32, 32, 0, 6)  #map all characters in 2nd row
            mouse = tcod.Mouse()
            key = tcod.Key()
        elif self.engine.game_mode == 'curses':
            mouse = None
            key = None
            rootcon = con
        else:
            mouse = key = rootcon = None
            self.err_graphicsmode('prep_console')
        return mouse, key, rootcon

    def dummy_getkey(self, timeout=None, bufsize=4096):
        # note: this won't work on windows. the modules themself won't even exist
        import termios, tty, select, errno
        fd = os.open(os.ctermid(), os.O_RDWR)
        try:
            if os.isatty(fd):
                attr = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    while True:
                        try:
                            readable = select.select([fd], [], [], timeout)[0]
                            if not readable:
                                # timeout
                                return
                            if fd not in readable:
                                # this shouldn't happen..
                                raise IOError(errno.EIO, 'poll error')
                            # read bufsize from termianl. despite the name
                            # "getkey", we want to capture multi-byte "keys"
                            # such as escape sequences generated by arrow keys,
                            # etc. this will read as much as is available at
                            # that instant in the read buffer, and return it as
                            # is. usually this will be a single keypress. note
                            # that this does NOT try to make sense out of
                            # multi-byte keypress events and return a single
                            # logical value the way curses does. you just get
                            # multiple bytes.
                            read = os.read(fd, bufsize)
                            if not read:
                                # socket/stream/file reached eof or otherwise cloosed. not good for a terminal!
                                raise IOError(errno.EIO, 'terminal received eof during read')
                            if read.startswith('\x03'):
                                # allow user to send SIGINT even in raw mode
                                raise KeyboardInterrupt
                            return read
                        except (OSError, IOError, select.error), exc:
                            if exc.args[0] == errno.EIO:
                                # subtle distinction here: timeout returns
                                # None, a closed stream returns ''. this allows
                                # the caller to make some distinction between
                                # the two if they choose, without bothering
                                # them with an exception
                                return ''
                            # these are "normal" errors when blockign on I/O. they indicate that system
                            # call was interrupted by a signal that needs to be handled, and are transient, i.e.
                            # you should try again without alerting that there is an error.
                            if exc.args[0] not in {errno.EINTR, errno.EAGAIN}:
                                raise
                finally:
                    termios.tcsetattr(fd, termios.TCSAFLUSH, attr)
        finally:
            os.close(fd)

    def getkey(self, con, mouse, key, wait=False):
        if self.engine.game_mode == 'tcod':
            if wait:
                key = tcod.console_wait_for_keypress(True)
            else:
                tcod.sys_check_for_event(tcod.EVENT_KEY_PRESS | tcod.EVENT_MOUSE, key, mouse)
            event = KeypressEvent(key.vk, key.c, chr(key.c), key.pressed, key.lalt, key.lctrl, key.ralt, key.rctrl, key.shift)
        elif self.engine.game_mode == 'curses':
            if wait:
                con.timeout(-1)
            else:
                con.timeout(0)
            while True:
                key = con.getch()
                if key == curses.ERR:
                    if wait:
                        continue
                    pressed, keychar = False, ''
                else:
                    pressed, keychar = True, (chr(key) if curses.ascii.isascii(key) else '')
                if keychar == '!':
                    curses.def_prog_mode()
                    curses.endwin()
                    from IPython.Shell import IPShellEmbed as S
                    sys.argv[:] = ['ipython']
                    S()()
                    curses.reset_prog_mode()
                    curses.refresh()


                event = KeypressEvent(key, key, keychar, pressed, False, False, False, False, False)
                break
            con.timeout(-1)
        elif self.engine.game_mode == 'dummy':
            sys.stdout.write('waiting for a keypress: ')
            sys.stdout.flush()
            while True:
                keyseq = self.dummy_getkey(timeout=1.0)
                if keyseq is None:
                    if wait:
                        continue
                    key = 0
                    keychar = ''
                    pressed = False
                else:
                    print keyseq
                    keychar = keyseq[0]
                    key = ord(keychar)
                    pressed = True
                event = KeypressEvent(key, key, chr(key), pressed, False, False,False, False, False)
                break
        else:
            self.err_graphicsmode('getkey')
        return event

    def flush(self,con):
        if self.engine.game_mode == 'tcod':
            tcod.console_flush()
        elif self.engine.game_mode == 'curses':
            self.curses_console_flush()
        else:
            self.err_graphicsmode('flush')

    def con_blit(self, con, xx, yy, nwidth, nheight, dest, dest_xx, dest_yy, ffade=1.0, bfade=1.0):
        if self.engine.game_mode == 'tcod':
            tcod.console_blit(con, xx, yy, nwidth, nheight, dest, dest_xx, dest_yy, ffade, bfade)
        elif self.engine.game_mode == 'curses':
            pass
        else:
            self.err_graphicsmode('con_blit')

    def img_blit2x(self, img, con, xx, yy):
        if self.engine.game_mode == 'tcod':
            tcod.image_blit_2x(img, con, xx, yy)
        elif self.engine.game_mode == 'curses':
            pass
        else:
            self.err_graphicsmode('img_blit2x')

    def load_image(self, img, img_ascii):
        if self.engine.game_mode == 'tcod':
            return tcod.image_load(img)
        elif self.engine.game_mode == 'curses':
            pass
        else:
            self.err_graphicsmode('load_image')

    def toggle_fullscreen(self):
        if self.engine.game_mode == 'tcod':
            tcod.console_set_fullscreen(not tcod.console_is_fullscreen())
        elif self.engine.game_mode == 'curses':
            pass
        else:
            self.err_graphicsmode('toggle_fullscreen')

    def set_default_color(self, con, fg_color=None, bg_color=None):
        if self.engine.game_mode == 'tcod':
            if fg_color is not None:
                tcod.console_set_default_foreground(con, fg_color)
            if bg_color is not None:
                tcod.console_set_default_background(con, bg_color)
        elif self.engine.game_mode == 'curses':
            pass
        else:
            self.err_graphicsmode('set_default_color')

    def get_names_under_mouse(self):
        if self.engine.game_mode == 'tcod':
            (x, y) = (self.engine.mouse.cx, self.engine.mouse.cy)
            (x, y) = (self.engine.camera_x + x, self.engine.camera_y + y)  #from screen to map coords
            names = [entity.name for entity in self.engine.entities[self.engine.dungeon_levelname]
                if entity.x == x and entity.y == y and self.engine.fovx.map_is_in_fov(self.engine.player.fighter.fov, entity.x, entity.y)]
            names = ', '.join(names) #join names separated by commas
            return names.capitalize()
        elif self.engine.game_mode == 'curses':
            return ''
        else:
            self.err_graphicsmode('get_names_under_mouse')

    def err_graphicsmode(self, func):
        if self.engine.game_mode != 'dummy':
            self.fatal_error('Error in ' + func + '. wrong GRAPHICSMODE: ' + self.engine.game_mode)


class FOV(object):

    def __init__(self, engine):
        self.engine = engine

    def fovmap(self, nwidth, nheight):
        if self.engine.fov_mode == 'tcod':
            return tcod.map_new(nwidth, nheight)
        else:
            self.err_mode('fovmap')

    def map_set_properties(self, fovmap, xx, yy, block_sight, blocked):
        if self.engine.fov_mode == 'tcod':
            tcod.map_set_properties(fovmap, xx, yy, block_sight, blocked)
        else:
            self.err_mode('set_map_properties')

    def map_is_in_fov(self, fovmap, xx, yy):
        if self.engine.fov_mode == 'tcod':
            return tcod.map_is_in_fov(fovmap, xx, yy)
        else:
            self.err_mode('map_is_in_fov')

    def map_compute_fov(self, fovmap, xx, yy, radius, light_walls, algo):
        if self.engine.fov_mode == 'tcod':
            return tcod.map_compute_fov(fovmap, xx, yy, radius, light_walls, algo)
        else:
            self.err_mode('map_compute_fov')

    def err_mode(self, func):
        log.error('error in func {}: wrong mode: {}', func, self.engine.fov_mode)

