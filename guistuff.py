import libtcod
try:
    import curses
except ImportError:
    print 'curses not available'

#TODO replace with select case
#TODO specifically require con for things that need it. don't save it. could get messy. See the flush() for example.
class Guistuff(object):
    def __init__(self, graphicsmode):
        self.graphicsmode = graphicsmode
        
    def isgameover(self):
        if self.graphicsmode == 'libtcod': 
            return libtcod.console_is_window_closed()
        elif self.graphicsmode == 'curses':
            return False
        else:
            self.err_graphicsmode('isgameover')
            return False

    def console(self, nwidth, nheight):
        if self.graphicsmode == 'libtcod':
            con = libtcod.console_new(nwidth, nheight)
        elif self.graphicsmode == 'curses':
            con = curses.newwin(nheight, nwidth)
        else:
            self.err_graphicsmode('console')
            return False
        return con

    def clear(self, con):
        if self.graphicsmode == 'libtcod':
            libtcod.console_clear(con)
        elif self.graphicsmode == 'curses':
            con.clear()
        else:
            self.err_graphicsmode('clear')

    def print_rect(self, con, xx, yy, nwidth, nheight, bkg=libtcod.BKGND_NONE, align=libtcod.LEFT, val=''):
        if self.graphicsmode == 'libtcod':
            libtcod.console_print_rect_ex(con, xx, yy, nwidth, nheight, bkg, align, val)
        elif self.graphicsmode == 'curses':
            try:
                print('curses!') #not sure how to do this yet
            except curses.error:
                pass
        else:
            self.err_graphicsmode('print_rect')

    def print_str(self, con, xx, yy, bkg=libtcod.BKGND_NONE, align=libtcod.LEFT, val='', my_color=None):
        if self.graphicsmode == 'libtcod':
            libtcod.console_set_default_foreground(con, my_color)
            libtcod.console_print_ex(con, xx, yy, bkg, align, val)
        elif self.graphicsmode == 'curses':
            try:
                con.addstr(yy, xx, val, my_color)
            except curses.error:
                pass
        else:
            self.err_graphicsmode('print_str')

    def prep_keyboard(self, delay, interval): #can this be combined with prep_console?
        if self.graphicsmode == 'libtcod':
            libtcod.console_set_keyboard_repeat(delay, interval)
        elif self.graphicsmode == 'curses':
            print('curses keyboard!')
        else:
            self.err_graphicsmode('prep_keyboard')      

    def prep_console(self, con, nwidth, nheight):
        if self.graphicsmode == 'libtcod':
            libtcod.console_set_custom_font('oryx_tiles3.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD, 32, 12)
            libtcod.console_init_root(nwidth, nheight, 'johnstein\'s Game of RogueLife!', False, libtcod.RENDERER_SDL)
            libtcod.sys_set_fps(30)

            libtcod.console_map_ascii_codes_to_font(256   , 32, 0, 5)  #map all characters in 1st row
            libtcod.console_map_ascii_codes_to_font(256+32, 32, 0, 6)  #map all characters in 2nd row

            mouse = libtcod.Mouse()
            key = libtcod.Key()  
        elif self.graphicsmode == 'curses':
            con.nodelay(1)
            con.keypad(1)
            mouse = None
            key = None
        else:
            self.err_graphicsmode('prep_console')
        return mouse,key

    def getkey(self, con, mouse, key):
        if self.graphicsmode == 'libtcod':
            libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
            thekey = key.vk
            key_char = chr(key.c)
        elif self.graphicsmode == 'curses':
            thekey = con.getch()
            key_char = con.getch()
        else:
            self.err_graphicsmode('getkey')
        return thekey, key_char

    def flush(self,con):
        if self.graphicsmode == 'libtcod':
            libtcod.console_flush()
        elif self.graphicsmode == 'curses':
            con.refresh()
        else:
            self.err_graphicsmode('flush')

    def con_blit(self, con, xx, yy, nwidth, nheight, dest, dest_xx, dest_yy, ffade=1.0, bfade=1.0): 
        if self.graphicsmode == 'libtcod':
            libtcod.console_blit(con, xx, yy, nwidth, nheight, dest, dest_xx, dest_yy, ffade, bfade)
        elif self.graphicsmode == 'curses':
            print('curses!') #not sure what the equiv is yet
        else:
            self.err_graphicsmode('con_blit')
            
    def img_blit2x(self, img, con, xx, yy):
        if self.graphicsmode == 'libtcod':
            libtcod.image_blit_2x(img, con, xx, yy)
        elif self.graphicsmode == 'curses':
            print(img) #not sure what the equiv is yet
        else:
            self.err_graphicsmode('img_blit2x')

    def load_image(self, img, img_ascii):
        if self.graphicsmode == 'libtcod':
            return libtcod.image_load(img)
        elif self.graphicsmode == 'curses':
            return img_ascii #not sure what the equiv is yet
        else:
            self.err_graphicsmode('load_image')

    def err_graphicsmode(self, func):
        print('Error in guistuff.' + func + '. wrong GRAPHICSMODE: ' + self.graphicsmode)
