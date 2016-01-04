
import textwrap
import shelve
import array
import sys
import os

from dungeoneer import tcod, curses, config, interface, log, rng, stats
from dungeoneer.entity import Equipment, Fighter, Entity, BasicMonster, Ai, Buff, ConfusedMonster


class Rect(object):

    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        center_x = (self.x1 + self.x2)/2
        center_y = (self.y1 + self.y2)/2
        return (center_x, center_y)

    def intersect(self, other):
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)


class MenuOption(object):

    def __init__(self, text, color=None, char=None):
        self.text = text
        self.color = color
        self.char = char


class Tile(object):

    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked
        self.explored = False
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight


class Maplevel(object):

    def __init__(self, height, width, levelnum, levelname, fov):
        self.levelnum = levelnum
        self.levelname = levelname
        self.height = height
        self.width = width
        self.fov   = fov
        self.map= [[ Tile(True)
            for y in range(self.height) ]
                for x in range(self.width) ]
        self.fov_map = fov.fovmap(self.width, self.height)
        self.fov_recompute = True

    def create_h_tunnel(self, x1, x2, y):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.map[x][y].blocked = False
            self.map[x][y].block_sight = False

    def create_v_tunnel(self, y1, y2, x):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.map[x][y].blocked = False
            self.map[x][y].block_sight = False

    def create_room(self, room):
        for x in range(room.x1 + 1, room.x2):
            for y in range(room.y1 + 1, room.y2):
                    self.map[x][y].blocked = False
                    self.map[x][y].block_sight = False

    def blocked(self, x, y):
        return self.map[x][y].blocked

    def block_sight(self, x, y):
        return self.map[x][y].block_sight

    def explored(self, x, y):
        return self.map[x][y].explored

    def set_explored(self, x, y):
        self.map[x][y].explored = True

    def set_map_explored(self):
        for y in range(self.height):
            for x in range(self.width):
                self.map[x][y].explored = True

    def initialize_fov(self):
        self.fov_recompute = True
        for y in range(self.height):
            for x in range(self.width):
                self.fov.map_set_properties(self.fov_map, x, y, not self.block_sight(x, y), not self.blocked(x, y))


class GameEngine(object):

    def __init__(self, game_mode, fov_mode, ascii_mode):
        if game_mode == 'curses' and curses is None:
            raise RuntimeError('cannot create curses modee, the library was not found')
        self.game_msgs = []
        self.msg_history = []
        self.game_mode = game_mode
        self.fov_mode = fov_mode
        self.ascii_mode = ascii_mode
        self.stdscr = None
        self.player = None

    @property
    def winsz(self):
        if self.stdscr is None:
            return 80, 25
        y, x = self.stdscr.getmaxyx()
        return x, y

    def _handle_window_resize(self, sig, frame):
        log.warn('SIGWINCH event received')
        import signal, termios, fcntl, array, errno
        saved = signal.getsignal(sig)
        try:
            signal.signal(sig, signal.SIG_IGN)
            fd = os.open(os.ctermid(), os.O_RDWR)
            try:
                if os.isatty(fd):
                    buf = array.array('H', [0, 0, 0, 0])
                    if fcntl.ioctl(fd, termios.TIOCGWINSZ, buf, 1) == 0:
                        h, w, y, x = buf
                        if h > 0 and w > 0:
                            self.new_winsz = w, h
                            log.warn('new window size is {}x{}', w, h)

            finally:
                os.close(fd)

        finally:
            signal.signal(sig, saved)

    def init_engine(self):
        if self.game_mode == 'curses':
            self.stdscr = curses.initscr()
            curses.noecho()
            curses.cbreak()
            self.stdscr.keypad(1)
            curses.curs_set(0)
            try:
                curses.start_color()
            except:
                pass
            try:
                import signal
                self._old_winch_handler = signal.getsignal(signal.SIGWINCH)
                signal.signal(signal.SIGWINCH, self._handle_window_resize)
            except:
                pass

    def teardown_engine(self, exc_type=None, exc_value=None, exc_traceback=None):
        if self.game_mode == 'curses':
            if self.stdscr is not None:
                self.stdscr.keypad(0)
            curses.echo()
            curses.nocbreak()
            curses.endwin()
            curses.curs_set(1)
        elif self.game_mode == 'tcod':
            pass  # any libtcod specific teardown stuff? the game doesn't seem to exit cleanly, so probably

    def run(self, *args, **kwargs):
        exc_info = ()
        try:
            self.init_engine()
            return self.run_unchecked(*args, **kwargs)
        except:
            exc_info = sys.exc_info()
            raise
        finally:
            self.teardown_engine(*exc_info)

    def run_unchecked(self):
        self.keymap = config.KeyMap(self)
        self.col = config.Colors(self)
        self.col.init_colors()
        self.gui = interface.GUI(self)
        self.fovx = interface.FOV(self)
        self.dat = config.GameData(self)
        self.ent = config.EntityData(self)
        self.con = self.gui.new_window(self.dat.MAP_WIDTH, self.dat.MAP_HEIGHT)
        log.debug('created base console: {!r}', self.con)
        self.mouse, self.key, self.rootcon = self.gui.prep_console(self.con, self.dat.MAP_WIDTH, self.dat.MAP_HEIGHT)
        if self.game_mode == 'curses':
            self.panel = self.gui.new_window(self.dat.SCREEN_WIDTH, self.dat.PANEL_HEIGHT, 0, self.dat.PANEL_Y)
        else:
            self.panel = self.gui.new_window(self.dat.SCREEN_WIDTH, self.dat.PANEL_HEIGHT)
        self.color_wall = None
        self.color_ground = None
        self.fov_wall_ground = None
        self.main_menu()

    def main_menu(self):
        while not self.gui.isgameover():
            img = self.gui.load_image(self.dat.MAIN_MENU_BKG, self.dat.MAIN_MENU_BKG_ASCII)
            self.gui.img_blit2x(img, self.rootcon, 0, 0) #display image at 2x
            self.gui.set_default_color(self.rootcon, fg_color=self.col.LIGHT_YELLOW)
            self.gui.print_str(self.rootcon, self.dat.SCREEN_WIDTH/2, self.dat.SCREEN_HEIGHT/2 - 4, 'MeFightRogues!')
            self.gui.print_str(self.rootcon, self.dat.SCREEN_WIDTH/2, self.dat.SCREEN_HEIGHT - 2 , 'by johnstein!')
            choice = self.menu(
                    rootcon=self.rootcon,
                    header='',
                    options=[
                        MenuOption('Play a new game'),
                        MenuOption('Battle Royale!'),
                        MenuOption('Continue last game'),
                        MenuOption('Quit'),
                        ],
                    width=24,
                    letterdelim=')',
                    )
            if choice == 0: #new game
                self.dat.FREE_FOR_ALL_MODE = False
                self.dat.AUTOMODE = False
                self.new_game()
                self.play_game()
            if choice == 1: #new game
                self.dat.AUTOMODE = True
                self.new_game()
                self.play_game()
            if choice == 2: #load last game
                try:
                    self.load_game()
                except:
                    self.msgbox(self.rootcon, '\n No saved game to load. \n', 24)
                    continue
                self.play_game()
            elif choice == 3: #quit
                try:
                    self.save_game()
                except:
                    log.exception('error saving game', exc_info=sys.exc_info())
                self.msgbox(self.rootcon, 'Bye!', 24, wait=False, keep=True)
                break

    def next_level(self):
        self.message('You head down the stairs', self.col.RED)
        #print self.dat.maplist
        #print self.player.dungeon_level
        #print self.dungeon_levelname
        self.player.dungeon_level += 1
        try:
            self.dungeon_levelname = self.dat.maplist[self.player.dungeon_level]
        except IndexError:
            self.dungeon_levelname = 'Level {}'.format(self.player.dungeon_level)
            self.dat.maplist.append(self.dungeon_levelname)

        if self.dungeon_levelname not in self.map:
            self.make_map(self.player.dungeon_level, self.dungeon_levelname) #create fresh new level
        self.player.x = self.upstairs[self.dungeon_levelname].x
        self.player.y = self.upstairs[self.dungeon_levelname].y

        if self.dungeon_levelname not in self.map:
            self.make_map(self.player.dungeon_level, self.dungeon_levelname) #create fresh new level
        self.player.x = self.upstairs[self.dungeon_levelname].x
        self.player.y = self.upstairs[self.dungeon_levelname].y
        self.map[self.dungeon_levelname].initialize_fov()

    def prev_level(self):
        self.message('You head up the stairs', self.col.RED)
        self.player.dungeon_level -=1
        self.dungeon_levelname = self.dat.maplist[self.player.dungeon_level]
        if self.player.dungeon_level < 0: #leave dungeon
            self.message('You\'ve left the dungeon!', self.col.RED)
            self.player.dungeon_level = 0 #workaround to prevent game from complaining.
            return self.dat.STATE_EXIT
        else:
            if not self.dungeon_levelname in self.map:
                self.make_map() #create fresh new level
            self.player.x = self.downstairs[self.dungeon_levelname].x
            self.player.y = self.downstairs[self.dungeon_levelname].y
            self.map[self.dungeon_levelname].initialize_fov()

    def make_dungeon(self):
        for index,level in enumerate(self.dat.maplist):
            #if index > 0: #skip intro level
            log.info('MAPGEN: {}, {}, creating level {}', self.tick, self.dungeon_levelname, level)
            self.player.dungeon_level = index
            self.dungeon_levelname = level
            self.make_map(index, level)
        self.player.dungeon_level = 0
        self.dungeon_levelname = self.dat.maplist[self.player.dungeon_level]
        self.player.x = self.upstairs[self.dungeon_levelname].x
        self.player.y = self.upstairs[self.dungeon_levelname].y
        self.map[self.dungeon_levelname].initialize_fov()

    def make_map(self, levelnum, levelname):
        self.entities[self.dungeon_levelname] = [self.player]
        log.info('MAPGEN: {}, {}, creating map: {}', self.tick, self.dungeon_levelname, self.dungeon_levelname)
        self.map[self.dungeon_levelname] = Maplevel(self.dat.MAP_HEIGHT, self.dat.MAP_WIDTH, levelnum, levelname, self.fovx)
        rooms = []
        num_rooms = 0
        for r in range(self.dat.MAX_ROOMS):
            w = rng.random_int(0, self.dat.ROOM_MIN_SIZE, self.dat.ROOM_MAX_SIZE)
            h = rng.random_int(0, self.dat.ROOM_MIN_SIZE, self.dat.ROOM_MAX_SIZE)
            x = rng.random_int(0, self.dat.MAP_PAD_W, self.dat.MAP_WIDTH - w - self.dat.MAP_PAD_W)
            y = rng.random_int(0, self.dat.MAP_PAD_H, self.dat.MAP_HEIGHT - h - self.dat.MAP_PAD_H)
            new_room = Rect(x, y, w, h)
            failed = False
            for other_room in rooms:
                if new_room.intersect(other_room):
                    failed = True
                    break
            if not failed:
                self.map[self.dungeon_levelname].create_room(new_room)
                (new_x, new_y) = new_room.center()
                self.place_entities(new_room)
                if num_rooms == 0:
                    self.player.x = new_x
                    self.player.y = new_y
                    self.upstairs[self.dungeon_levelname] = Entity(self, new_x, new_y, '<', 'upstairs', self.col.WHITE, always_visible = True)
                    self.entities[self.dungeon_levelname].append(self.upstairs[self.dungeon_levelname])
                    self.upstairs[self.dungeon_levelname].send_to_back() #so it's drawn below the monsters
                else:
                    (prev_x, prev_y) = rooms[num_rooms -1].center()
                    if rng.flip_coin() == 1:
                        self.map[self.dungeon_levelname].create_h_tunnel(prev_x, new_x, prev_y)
                        self.map[self.dungeon_levelname].create_v_tunnel(prev_y, new_y, new_x)
                    else:
                        self.map[self.dungeon_levelname].create_v_tunnel(prev_y, new_y, prev_x)
                        self.map[self.dungeon_levelname].create_h_tunnel(prev_x, new_x, new_y)
                rooms.append(new_room)
                num_rooms +=1
        self.downstairs[self.dungeon_levelname] = Entity(self, new_x, new_y, '>', 'downstairs', self.col.WHITE, always_visible = True)
        self.entities[self.dungeon_levelname].append(self.downstairs[self.dungeon_levelname])
        self.downstairs[self.dungeon_levelname].send_to_back() #so it's drawn below the monsters
        self.map[self.dungeon_levelname].initialize_fov()

    def place_entities(self, room):
        nextid = 1
        max_monsters = self.from_dungeon_level([[10, 1], [40, 3], [50, 6], [70, 10]], self.dat.maplist.index(self.dungeon_levelname))
        num_monsters = rng.random_int(0, 0, max_monsters)
        monster_chances = self.get_monster_chances()
        max_items = self.from_dungeon_level([[10, 1], [2, 4]], self.dat.maplist.index(self.dungeon_levelname))
        num_items = rng.random_int(0, 0, max_items)
        item_chances = self.get_item_chances()
        for i in range(num_monsters):
            x =  rng.random_int(0, room.x1 + 1, room.x2 - 1)
            y =  rng.random_int(0, room.y1 + 1, room.y2 - 1)
            if not self.is_blocked(x, y):
                choice = rng.random_choice(monster_chances)
                monster             = Entity(self, **self.ent.mobs[choice])
                monster.dungeon_level = self.dat.maplist.index(self.dungeon_levelname)
                monster.blocks      = True
                monster.ai          = Ai(BasicMonster(self))  #how do I set different ai?
                monster.ai.owner    = monster
                monster.id          = str(monster.dungeon_level) + '.' + str(nextid)
                monster.name        = choice + '(' + str(monster.id) + ')'
                if self.dat.FREE_FOR_ALL_MODE:
                    monster.fighter.clan        = monster.name
                nextid+=1
                monster.fighter.fov = self.map[self.dungeon_levelname].fov_map
                log.info('MAPGEN: {}, {}, made a monster {}', self.tick, self.dungeon_levelname, monster.name)
                if self.ent.mobitems[choice]:
                    for itemname in self.ent.mobitems[choice]:
                        item = Entity(self, **self.ent.items[itemname])
                        monster.fighter.add_item(item)
                monster.set_location(x, y)
                self.entities[self.dungeon_levelname].append(monster)
        for i in range(num_items):
            x = rng.random_int(0, room.x1 + 1, room.x2 - 1)
            y = rng.random_int(0, room.y1 + 1, room.y2 - 1)
            if not self.is_blocked(x, y):
                choice = rng.random_choice(item_chances)
                item = Entity(self, **self.ent.items[choice])
                item.always_visible = True
                item.set_location(x, y)
                item.dungeon_level = self.dat.maplist.index(self.dungeon_levelname)
                self.entities[self.dungeon_levelname].append(item)
                item.send_to_back() #items appear below other entities

    def get_monster_chances(self):
        monster_chances = {}
        for mobname in self.ent.mobchances:
            monster_chances[mobname] = self.from_dungeon_level(self.ent.mobchances[mobname], self.dat.maplist.index(self.dungeon_levelname))
        return monster_chances

    def from_dungeon_level(self, table, dungeon_level):
        for (value, level) in reversed(table):
            if dungeon_level >= level:
                return value
        return 0

    def get_item_chances(self):
        item_chances = {}
        for itemname in self.ent.itemchances:
            item_chances[itemname] = self.from_dungeon_level(self.ent.itemchances[itemname], self.dat.maplist.index(self.dungeon_levelname))
        return item_chances

    def mapname(self):
        return(self.dat.maplist[self.player.dungeon_level])

    def message(self, new_msg, color = None, displaymsg=True):
        if color is None:
            color = self.col.WHITE
        if self.dat.PRINT_MESSAGES:
            if self.dat.FREE_FOR_ALL_MODE:
                self.message_db.log_entity(new_msg)
            log.info('MSG: {}, {}, {}', self.tick, self.dungeon_levelname, new_msg)
        if displaymsg:
            turn = self.player.game_turns
            new_msg_lines = textwrap.wrap(new_msg, self.dat.MSG_WIDTH)
            for line in new_msg_lines:
                if len(self.game_msgs) == self.dat.MSG_HEIGHT:
                    del self.game_msgs[0]
                self.msg_history.append(MenuOption(str(turn) + ' : ' + line, color=color))
                self.game_msgs.append((line, color))

    def menu(self, rootcon, header, options, width, letterdelim=None, keep=False, wait=True):
        if len(options) > self.dat.MAX_NUM_ITEMS:
            self.message('Cannot have a menu with more than ' + str(self.dat.MAX_NUM_ITEMS) + ' options.')
        header_height = self.gui.get_height_rect(self.con, 0, 0, width, self.dat.SCREEN_HEIGHT, header)
        if header == '':
            header_height = 0
        height = len(options) + header_height
        if self.game_mode == 'curses':
            # accomodate for the ascii line box
            width += 2
            height += 2
            xoffset = 1
            yoffset = 1
        else:
            xoffset = 0
            yoffset = 0
        if self.game_mode == 'curses':
            real_width, real_height = self.winsz
            xpad = (real_width - width) / 2
            ypad = (real_height - height) / 2
        else:
            xpad = ypad = 0

        window = self.gui.new_window(width, height, xpad, ypad)
        self.gui.set_default_color(window, fg_color=self.col.WHITE)
        self.gui.print_rect(window, xoffset, yoffset, width, height, header)
        y = header_height
        letter_index = ord('a')
        for opt in options:
            text = opt.text
            color = opt.color
            char = opt.char
            if color is None: color = self.col.WHITE
            if char is None: char = ''
            if letterdelim is None:
                letterchar = ''
            else:
                letterchar = chr(letter_index) + letterdelim
            self.gui.set_default_color(window, fg_color=color)
            self.gui.print_str(window, xoffset, y + yoffset, letterchar + ' ' + char + ' ' + text)
            y += 1
            letter_index += 1
        x = self.dat.SCREEN_WIDTH / 2 - width / 2
        y = self.dat.SCREEN_HEIGHT / 2 - height / 2
        self.gui.con_blit(window, 0, 0, width, height, rootcon, x, y, 1.0, 0.7)
        self.gui.flush(rootcon)
        self.gui.prep_keyboard(0, 0)
        retval = None
        while True:
            key = self.gui.getkey(self.con, self.mouse, self.key, wait=wait)
            if key.pressed:
                if not options or key.keycode in {self.keymap.ESC, self.keymap.SPACE}:
                    break
                index = key.charcode - ord('a')
                if index >= 0 and index < len(options):
                    retval = index
                    break
                if self.game_mode == 'curses' and self.dat.BEEP_OK:
                    curses.beep()
            elif not wait:
                break
        if self.game_mode == 'curses' and not keep:
            self.gui.delwin(window)
        self.gui.prep_keyboard(self.dat.KEYS_INITIAL_DELAY,self.dat.KEYS_INTERVAL)
        return retval

    def msgbox(self, rootcon, text, width=50, keep=False, wait=True):
        return self.menu(rootcon, text, [], width, keep=keep, wait=wait)

    def inventory_menu(self, rootcon, header, user):
        if user.fighter:
            options = []
            if not len(user.fighter.inventory):
                opt = MenuOption('inventory is empty!', color=self.col.WHITE, char='?')
                options.append(opt)
            else:
                for item in user.fighter.inventory:
                    log.debug('inventory item: {}', item)
                    text = item.name
                    if item.equipment and item.equipment.is_equipped:
                        text = text + ' (on ' + item.equipment.slot + ')'
                    opt = MenuOption(text, color=item.color, char=item.char)
                    options.append(opt)
            index = self.menu(rootcon, header, options, self.dat.INVENTORY_WIDTH, letterdelim='')
            if (index is None or len(user.fighter.inventory) == 0) or index == 'ESC':
                return None
            else:
                return user.fighter.inventory[index].item
        else:
            return None

    def render_all(self):
        self.move_camera(self.player.x, self.player.y)
        if self.fov_recompute:
            self.fov_recompute = False
            self.player.fighter.recompute_fov()
            self.gui.clear(self.con)
            for y in range(self.dat.CAMERA_HEIGHT):
                for x in range(self.dat.CAMERA_WIDTH):
                    (map_x, map_y) = (self.camera_x + x, self.camera_y + y)
                    visible = self.fovx.map_is_in_fov(self.player.fighter.fov, map_x, map_y)
                    wall = self.map[self.dungeon_levelname].block_sight(map_x, map_y)
                    if self.ascii_mode:
                        thewallchar  = self.dat.WALL_CHAR
                        thegroundchar = self.dat.GROUND_CHAR
                    else:
                        thewallchar  = self.dat.TILE_WALL
                        thegroundchar = self.dat.TILE_GROUND
                    if not visible:
                        if wall:
                            color_wall_ground = self.dat.COLOR_DARK_WALL
                            char_wall_ground = thewallchar
                            self.color_wall = color_wall_ground
                        else:
                            color_wall_ground = self.dat.COLOR_DARK_GROUND
                            char_wall_ground = thegroundchar
                            self.color_ground = color_wall_ground
                        fov_wall_ground = self.col.DARK_GREY
                    else:
                        self.map[self.dungeon_levelname].set_explored(map_x, map_y)
                        if wall:
                            color_wall_ground = self.dat.COLOR_LIGHT_WALL
                            char_wall_ground = thewallchar
                            self.color_wall = color_wall_ground
                        else:
                            color_wall_ground = self.dat.COLOR_LIGHT_GROUND
                            char_wall_ground = thegroundchar
                            self.color_ground = color_wall_ground
                        fov_wall_ground = self.col.WHITE
                    self.fov_wall_ground = fov_wall_ground
                    if self.map[self.dungeon_levelname].explored(map_x, map_y):
                        self.gui.print_char(self.con, x, y, val=char_wall_ground, fg_color=fov_wall_ground, bg_color=color_wall_ground)
            for entity in self.entities[self.dungeon_levelname]:
                if entity != self.player:
                    entity.draw()
            self.player.draw()
            self.gui.con_blit(self.con, 0, 0, self.dat.SCREEN_WIDTH, self.dat.SCREEN_HEIGHT, self.rootcon, 0, 0)
            self.gui.clear(self.panel)
            self.render_bar(1, 1, self.dat.BAR_WIDTH, 'HP', self.player.fighter.hp, self.player.fighter.max_hp(), self.col.LIGHT_RED, self.col.RED)
            self.gui.set_default_color(self.panel, fg_color=self.col.WHITE, bg_color=self.col.BLACK)
            self.gui.print_str(self.panel, 1, 3, self.dungeon_levelname)
            self.gui.print_str(self.panel, 1, 4, 'Dungeon level: ' + str(self.player.dungeon_level))
            self.gui.print_str(self.panel, 1, 5, 'Turn: ' + str(self.player.game_turns) + ' (' + str(self.tick) +')')
            y = 1
            for (line, color) in self.game_msgs:
                self.gui.set_default_color(self.panel, fg_color=color)
                self.gui.print_str(self.panel, self.dat.MSG_X, y, line)
                y += 1
            self.gui.set_default_color(self.panel, fg_color=self.col.LIGHT_GREY)
            self.gui.print_str(self.panel, 1, 0, self.gui.get_names_under_mouse())
            if self.dat.SHOW_PANEL:
                self.gui.con_blit(self.panel, 0, 0, self.dat.SCREEN_WIDTH, self.dat.PANEL_HEIGHT, self.rootcon, 0, self.dat.PANEL_Y)
            self.gui.flush(self.con)

    def render_bar(self, x, y, total_width, name, value, maximum, bar_color, back_color):
        bar_width = int(float(value) / maximum * total_width)
        self.gui.draw_rect(self.panel, x, y, total_width, 1, False, bg_color=back_color)
        if bar_width > 0:
            self.gui.draw_rect(self.panel, x, y, bar_width, 1, False, bg_color=bar_color)
        self.gui.set_default_color(self.panel, fg_color=self.col.WHITE)
        self.gui.print_str(self.panel, x + total_width/2, y, name + ': ' + str(value) + '/' + str(maximum), align=tcod.CENTER)

    def player_move_or_attack(self, dx, dy):
        x = self.player.x + dx
        y = self.player.y + dy
        target = None
        for entity in self.entities[self.dat.maplist[self.player.dungeon_level]]:
            if entity.x == x and entity.y == y and entity.fighter:
                target = entity
                break
        if target is not None:
            self.player.fighter.attack(target)
            self.player.game_turns +=1
            state = self.dat.STATE_PLAYING
        else:
            if self.player.move(dx, dy):
                self.player.game_turns +=1
                state = self.dat.STATE_PLAYING
                for entity in self.entities[self.dat.maplist[self.player.dungeon_level]]: #look for items in the player's title
                    if entity.x == self.player.x and entity.y == self.player.y and entity is not self.player:
                        self.message('* You see ' + entity.name + ' at your feet *', self.col.YELLOW)
            else:
                state = self.dat.STATE_NOACTION
        self.fov_recompute = True
        return state

    def player_resting(self):
        self.player.game_turns += 1

    def move_camera(self, target_x, target_y):
        x = target_x - self.dat.CAMERA_WIDTH / 2  #coordinates so that the target is at the center of the screen
        y = target_y - self.dat.CAMERA_HEIGHT / 2
        if x < 0: x = 0
        if y < 0: y = 0
        if x > self.dat.MAP_WIDTH - self.dat.CAMERA_WIDTH - 1: x = self.dat.MAP_WIDTH - self.dat.CAMERA_WIDTH - 1
        if y > self.dat.MAP_HEIGHT - self.dat.CAMERA_HEIGHT - 1: y = self.dat.MAP_HEIGHT - self.dat.CAMERA_HEIGHT - 1
        if x != self.camera_x or y != self.camera_y: self.fov_recompute = True
        (self.camera_x, self.camera_y) = (x, y)

    def to_camera_coordinates(self, x, y):
        (x, y) = (x - self.camera_x, y - self.camera_y)
        if (x < 0 or y < 0 or x >= self.dat.CAMERA_WIDTH or y >= self.dat.CAMERA_HEIGHT):
            return (None, None)  #if it's outside the view, return nothing
        return (x, y)

    def use_red_crystal(self, user):
        if user is self.player:
            self.message('You become ENRAGED!', self.col.RED)
        else:
            self.message('The ' + user.name + ' beomes ENRAGED!', self.col.RED)
        buff_component = Buff(self, 'Super Strength', power_bonus=10)
        user.fighter.add_buff(buff_component)

    def use_blue_crystal(self, user):
        if user is self.player:
            self.message('You feel well-protected!', self.col.CYAN)
        else:
            self.message('The ' + user.name + ' looks well protected!', self.col.RED)
        buff_component = Buff(self, 'Super Defense', defense_bonus=10)
        user.fighter.add_buff(buff_component)

    def use_green_crystal(self, user):
        if user is self.player:
            self.message('You feel more resilient!', self.col.GREEN)
        else:
            self.message('The ' + user.name + ' feels more resilient!', self.col.RED)
        buff_component = Buff(self, 'Super Health', max_hp_bonus=50)
        user.fighter.add_buff(buff_component)
        user.fighter.hp = self.player.fighter.max_hp()

    def use_yellow_crystal(self, user):
        if user is self.player:
            self.message('You feel healthy!', self.col.YELLOW)
        else:
            self.message('The ' + user.name + ' looks healthier!', self.col.RED)
        buff_component = Buff(self,'Super Regen', regen_bonus=-20)
        user.fighter.add_buff(buff_component)

    def use_orange_crystal(self, user):
        if user is self.player:
            self.message('You feel speedy!', self.col.CYAN)
        else:
            self.message('The ' + user.name + ' looks speedy!', self.col.CYAN)
        buff_component = Buff(self, 'Super Speed', speed_bonus=-3)
        user.fighter.add_buff(buff_component)

    def cast_confusion(self, user):
        target = self.closest_nonclan(self.dat.TORCH_RADIUS, user)
        if user is self.player:
            self.message('Left-click an enemy to confuse. Right-click or ESC to cancel', self.col.LIGHT_CYAN)
            target = self.target_monster(self.dat.CONFUSE_RANGE)
            name = 'You'
        elif target is not None:
            target = self.closest_nonclan(self.dat.TORCH_RADIUS, user)
            name = user.name
        else:
            if user is self.player:
                self.message('Cancelling confuse', self.col.RED, False)
            else:
                self.message(user.name + ' cancels Confuse', self.col.RED, False)
            return self.dat.STATE_CANCELLED
        if target is None:
            return
        if target.ai:
            old_ai = target.ai
        else:
            old_ai = None
        target.ai = ConfusedMonster(self, old_ai)
        target.ai.owner = target #tell the new component who owns it
        if user is self.player:
            self.message('You confused ' + target.name + '!', self.col.LIGHT_GREEN)
        else:
            self.message(name + ' confused  ' + target.name + '!', self.col.LIGHT_GREEN, self.isplayer(user))

    def cast_fireball(self, user):
        (x,y) = (None, None)
        target = self.closest_nonclan(self.dat.TORCH_RADIUS, user)
        if user is self.player:
            self.message('Left-click a target tile for the fireball. Right-Click or ESC to cancel', self.col.LIGHT_CYAN)
            (x,y) = self.target_tile()
        elif target:
            if self.fovx.map_is_in_fov(user.fighter.fov, target.x, target.y) and target.dungeon_level == user.dungeon_level:
                (x,y) = (target.x, target.y)
        if x is None or y is None:
            if user is self.player:
                self.message('Cancelling fireball', self.col.RED)
            else:
                self.message(user.name + ' cancels Fireball', self.col.RED, False)
            return self.dat.STATE_CANCELLED
        else:
            theDmg = rng.roll_dice([[self.dat.FIREBALL_DAMAGE/2, self.dat.FIREBALL_DAMAGE*2]])[0]
            fov_map_fireball = self.map[self.dungeon_levelname].fov_map
            self.fovx.map_compute_fov(fov_map_fireball, x, y, self.dat.FIREBALL_RADIUS, self.dat.FOV_LIGHT_WALLS, self.dat.FOV_ALGO)
            for entity in self.entities[self.dungeon_levelname]: #damage all fighters within range
                if self.fovx.map_is_in_fov(fov_map_fireball, entity.x, entity.y) and entity.fighter:
                    self.message('The fireball explodes', self.col.RED)
                    self.message(entity.name + ' is burned for '+ str(theDmg) + ' HP', self.col.RED)
                    entity.fighter.take_damage(user, theDmg)

    def cast_heal(self, user):
        if user.fighter.hp == user.fighter.max_hp():
            if user is self.player:
                self.message('You are already at full health.', self.col.RED)
            else:
                self.message(user.name + ' cancels Heal', self.col.RED, False)
            return self.dat.STATE_CANCELLED
        if user is self.player:
            self.message('You feel better', self.col.LIGHT_CYAN)
        else:
            self.message(user.name + ' looks healthier!', self.col.RED)
        user.fighter.heal(self.dat.HEAL_AMOUNT)

    def cast_push(self, user):
        self.push(user, 3)

    def cast_bigpush(self, user):
        self.push(user, 5)

    def push(self, user, numpushes):
        target = None
        if user is self.player:
            target = self.closest_monster(self.dat.TORCH_RADIUS)
        else:
            target = self.closest_nonclan(self.dat.TORCH_RADIUS, user)
        if target is None:
            if user is self.player:
                self.message('No enemy is close enough to push', self.col.RED)
            else:
                self.message(user.name + ' cancels Push', self.col.RED, False)
            return 'cancelled'
        else:
            dist = user.distance_to(target)
            if dist < 1.5: #adjacent
                if user is self.player:
                    self.message('You pushed the ' + target.name + '!', self.col.MAGENTA)
                else:
                    self.message(user.name + ' pushed ' + target.name + '!', self.col.MAGENTA)
                for times in range(numpushes-1):
                    target.move_away(user)
                target.move_random()
            else:
                if user is self.player:
                    self.message(target.name + ' is too far away to push!', self.col.RED)
                else:
                    self.message(target.name + ' is too far away for ' + user.name + ' to push!', self.col.RED, False)
                return 'cancelled'

    def cast_lightning(self, user):
        target = None
        target = self.closest_nonclan(self.dat.LIGHTNING_RANGE, user)
        if user is self.player:
            target = self.closest_monster(self.dat.LIGHTNING_RANGE)
        elif target:
            if not (self.fovx.map_is_in_fov(user.fighter.fov, target.x, target.y) and target.dungeon_level == user.dungeon_level):
                target = None
        if target is None:
            if user is self.player:
                self.message('No enemy is close enough to strike', self.col.RED)
            else:
                self.message(user.name + ' cancels Lightning', self.col.RED, False)
            return 'cancelled'
        else:
            theDmg = rng.roll_dice([[self.dat.LIGHTNING_DAMAGE/2, self.dat.LIGHTNING_DAMAGE]])[0]
            if user is self.player:
                self.message('Your lightning bolt strikes the ' + target.name + '!  DMG = ' + str(theDmg) + ' HP.', self.col.LIGHT_BLUE)
            else:
                self.message(user.name + '\'s lightning bolt strikes the ' + target.name + '!  DMG = ' + str(theDmg) + ' HP.', self.col.LIGHT_BLUE)
            target.fighter.take_damage(user, theDmg)

    def player_death(self, player, killer):
        if killer:
            if killer.fighter:
                killer.fighter.xp += player.fighter.xpvalue
                self.message(killer.name + ' killed you! New xp = ' + str(killer.fighter.xp)  + '(' + player.name + ')', self.col.RED, self.engine.isplayer(killer))
        if not self.player.fighter.killed:
            self.player.char = '%'
            self.player.color = self.col.MAGENTA
            self.player.blocks = False
            self.player.ai = None
            self.player.always_visible = True
            self.player.fighter.killed = False
            self.player.send_to_back()
            if not self.dat.AUTOMODE:
                self.message('YOU DIED! YOU SUCK!', self.col.RED)
                self.game_state = self.dat.STATE_DEAD

    def monster_death(self, monster, killer):
        if monster.fighter.alive:
            if killer is self.player:
                name = 'You'
            else:
                name = killer.name
            self.message(monster.name.capitalize() + ' is DEAD! (killed by ' + name + ')', self.col.YELLOW)
            self.printstats(monster)
            monster.send_to_back()
            if killer.fighter:
                killer.fighter.xp += monster.fighter.xpvalue
            self.message(name + ' killed ' + monster.name + ' and gains ' + str(monster.fighter.xpvalue) + 'XP', self.col.YELLOW, self.isplayer(killer))
            for equip in monster.fighter.inventory:
                equip.item.drop(monster)
            monster.char = '%'
            monster.color = self.col.MAGENTA
            monster.blocks = False
            monster.ai = None
            monster.always_visible = True
            monster.fighter.alive = False

    def get_equipped_in_slot(self, slot, user): #returns the equipment in a slot, or None if it's empty
        if user.fighter.inventory:
            for entity in user.fighter.inventory:
                if entity.equipment and entity.equipment.slot == slot and entity.equipment.is_equipped:
                    return entity.equipment
        return None

    def get_all_equipped(self, user): #returns list of equipped items
        equipped_list = []
        if user.fighter.inventory:
            for item in user.fighter.inventory:
                if item.equipment and item.equipment.is_equipped:
                    equipped_list.append(item.equipment)
            return equipped_list
        return [] #other self.entities[self.dungeon_levelname] have no equipment

    def target_monster(self, max_range=None):
        while True:
            (x, y) = self.target_tile(max_range)
            if x is None: #player cancelled
                return None
            for entity in self.entities[self.dungeon_levelname]:
                if entity.x == x and entity.y == y and entity.fighter and entity != self.player and entity.dungeon_level == self.player.dungeon_level:
                    return entity

    def closest_monster(self, max_range):
        closest_enemy = None
        closest_dist = max_range + 1 #start with slightly higher than max range
        for entity in self.entities[self.dungeon_levelname]:
            if entity.fighter and not entity == self.player and self.fovx.map_is_in_fov(self.player.fighter.fov, entity.x, entity.y):
                dist = self.player.distance_to(entity)
                if dist < closest_dist:
                    closest_enemy = entity
                    closest_dist = dist
        return closest_enemy

    def fov_map(self, max_range, dude):
        fov_map_dude = self.fov.fovmap(self.dat.MAP_WIDTH, self.dat.MAP_HEIGHT)
        for yy in range(self.dat.MAP_HEIGHT):
            for xx in range(self.dat.MAP_WIDTH):
                self.fov.map_set_properties(fov_map_dude, xx, yy, not self.map[self.dungeon_levelname].block_sight(xx, yy), not self.map[self.dungeon_levelname].blocked(xx, yy))
        self.fovx.map_compute_fov(fov_map_dude, dude.x, dude.y, max_range, self.dat.FOV_LIGHT_WALLS, self.dat.FOV_ALGO)
        return fov_map_dude

    def closest_item(self, max_range, dude):
        closest_item = None
        closest_dist = max_range + 1 #start with slightly higher than max range
        if dude.fighter.fov is None:
            fov_map_dude = self.map[self.dungeon_levelname].fov_map
        fov_map_dude = dude.fighter.recompute_fov()
        for entity in self.entities[self.dungeon_levelname]:
            if entity.item and self.fovx.map_is_in_fov(fov_map_dude, entity.x, entity.y) and entity.dungeon_level == dude.dungeon_level:
                dist = dude.distance_to(entity)
                if dist < closest_dist:
                    closest_item = entity
                    closest_dist = dist
        return closest_item

    def closest_nonclan(self, max_range, dude):
        closest_nonclan = None
        closest_dist = max_range + 1 #start with slightly higher than max range
        if dude.fighter.fov is None:
            fov_map_dude = dude.fighter.set_fov() # XXX where is this method?
        fov_map_dude = dude.fighter.recompute_fov()
        for entity in self.entities[self.dungeon_levelname]:
            if entity.fighter and  entity.fighter.clan != dude.fighter.clan and self.fovx.map_is_in_fov(fov_map_dude, entity.x, entity.y) and entity.dungeon_level == dude.dungeon_level and entity.fighter.alive:
                dist = dude.distance_to(entity)
                if dist < closest_dist:
                    closest_nonclan = entity
                    closest_dist = dist
        return closest_nonclan

    def get_next_fighter(self):
        for index,level in enumerate(self.dat.maplist):
            #if index > 0:
            for entity in self.entities[self.dat.maplist[index]]:
                if entity.fighter:
                    return entity

    def target_tile(self, max_range = None):
        while True:
            self.gui.flush(self.rootcon)
            thekey = self.gui.getkey(self.con, self.mouse, self.key)
            self.render_all()
            (x, y) = (self.mouse.cx, self.mouse.cy)
            (x, y) = (self.camera_x + x, self.camera_y + y) #from screen to map coords
            if (self.mouse.lbutton_pressed and self.fovx.map_is_in_fov(self.player.fighter.fov, x, y) and (max_range is None or self.player.distance(x,y) <= max_range)):
                return (x, y)
            if self.mouse.rbutton_pressed or self.key.vk == self.keymap.ESC:
                return (None, None)

    def is_blocked(self, x, y):
        if self.map[self.dungeon_levelname].blocked(x,y):
            return True
        for entity in self.entities[self.dungeon_levelname]:
            if entity.blocks and entity.x == x and entity.y == y:
                return True
        return False

    def total_alive_entities(self):
        return [entity for entity in self.entities[self.dungeon_levelname]
                if entity.fighter and entity.fighter.hp > 0]

    def printstats(self, entity):
        self.message(entity.name, self.col.WHITE)
        self.message('Level =' + str(entity.fighter.xplevel), self.col.WHITE)
        self.message('XP =' + str(entity.fighter.xp), self.col.WHITE)
        self.message('HP =' + str(entity.fighter.hp) + '/' + str(entity.fighter.max_hp()), self.col.WHITE)
        self.message('power =' + str(entity.fighter.power()) + '/' + str(entity.fighter.base_power), self.col.WHITE)
        self.message('defense =' + str(entity.fighter.defense()) + '/' + str(entity.fighter.base_defense), self.col.WHITE)

    def isplayer(self, entity):
        if entity is self.player:
            return True
        else:
            return False

    def check_level_up(self, user):
        level_up_xp = self.dat.LEVEL_UP_BASE + user.fighter.xplevel * self.dat.LEVEL_UP_FACTOR
        if user.fighter.xp >= level_up_xp:
            user.fighter.xplevel += 1
            user.fighter.xp -= level_up_xp
            if user is self.player:
                self.message('You have reached level ' + str(user.fighter.xplevel) + '!', self.col.YELLOW)
            else:
                self.message(user.name + ' has reached level ' + str(user.fighter.xplevel) + '!', self.col.YELLOW)
            choice = None
            if user is self.player:
                while choice == None: #keep asking till a choice is made
                    choice = self.menu(self.rootcon, 'Level up! Choose a stat to raise:\n',
                            [MenuOption('Constitution (+25 HP, from ' + str(self.player.fighter.max_hp()) + ')',color=self.col.GREEN),
                                MenuOption('Strength (+2 attack, from ' + str(self.player.fighter.power()) + ')', color=self.col.RED),
                                MenuOption('Defense (+2 defense, from ' + str(self.player.fighter.defense()) + ')', color=self.col.BLUE)], self.dat.LEVEL_SCREEN_WIDTH, letterdelim=')')
            else:
                choice = rng.random_int(0, 0, 2) #TODO: variablize this
            if choice == 0:
                user.fighter.base_max_hp += 25
            elif choice == 1:
                user.fighter.base_power += 2
            elif choice == 2:
                user.fighter.base_defense += 2
            user.fighter.hp = user.fighter.max_hp()

    def handle_keys(self):
        wait = not self.dat.AUTOMODE
        while 1:
            thekey = self.gui.getkey(self.con, self.mouse, self.key, wait=wait)
            if thekey.pressed:
                break
            if not wait:
                return self.dat.STATE_NOACTION

        if thekey.keycode == self.keymap.ENTER and thekey.lalt:
            self.gui.toggle_fullscreen()
        elif thekey.keycode == self.keymap.ESC or thekey.keychar == '\x1b':
            return self.dat.STATE_EXIT #exit game
        if self.game_state == self.dat.STATE_PLAYING:
            if thekey.keycode == self.keymap.KPDEC or thekey.keycode == self.keymap.KP5 or thekey.keychar == '.':
                self.player_resting()
                self.fov_recompute = True
            elif thekey.keycode == self.keymap.UP or thekey.keychar == 'k' or thekey.keycode == self.keymap.KP8:
                return self.player_move_or_attack(0, -1)
            elif thekey.keycode == self.keymap.DOWN or thekey.keychar == 'j' or thekey.keycode == self.keymap.KP2:
                return self.player_move_or_attack(0, 1)
            elif thekey.keycode == self.keymap.LEFT or thekey.keychar == 'h' or thekey.keycode == self.keymap.KP4:
                return self.player_move_or_attack(-1, 0)
            elif thekey.keycode == self.keymap.RIGHT or thekey.keychar == 'l' or thekey.keycode == self.keymap.KP6:
                return self.player_move_or_attack(1, 0)
            elif thekey.keychar == 'y' or thekey.keycode == self.keymap.KP7:
                return self.player_move_or_attack(-1, -1)
            elif thekey.keychar == 'u' or thekey.keycode == self.keymap.KP9:
                return self.player_move_or_attack(1, -1)
            elif thekey.keychar == 'n' or thekey.keycode == self.keymap.KP3:
                return self.player_move_or_attack(1, 1)
            elif thekey.keychar == 'b' or thekey.keycode == self.keymap.KP1:
                return self.player_move_or_attack(-1, 1)
            else:
                if thekey.keychar == 'g':
                    for entity in self.entities[self.dat.maplist[self.player.dungeon_level]]: #look for items in the player's title on the same floor of the player
                        if entity.x == self.player.x and entity.y == self.player.y and entity.item:
                            self.player.game_turns += 1
                            return entity.item.pick_up(self.player)
                if thekey.keychar == 'i':
                    chosen_item = self.inventory_menu(self.rootcon, 'Press the key next to an item to use it. \nPress ESC to return to game\n', self.player)
                    if chosen_item is not None:
                        self.player.game_turns += 1
                        return chosen_item.use(user=self.player)
                if thekey.keychar == 'd':
                    chosen_item = self.inventory_menu(self.rootcon, 'Press the key next to the item to drop. \nPress ESC to return to game\n', self.player)
                    if chosen_item is not None:
                        self.player.game_turns += 1
                        chosen_item.drop(self.player)
                if thekey.keychar == 'c':
                    level_up_xp = self.dat.LEVEL_UP_BASE + self.player.fighter.xplevel * self.dat.LEVEL_UP_FACTOR
                    self.msgbox(self.rootcon, 'Character Information\n\nLevel: ' + str(self.player.fighter.xplevel) + '\nExperience: ' + str(self.player.fighter.xp) +
                        '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(self.player.fighter.max_hp()) +
                        '\nAttack: ' + str(self.player.fighter.power()) + '\nDefense: ' + str(self.player.fighter.defense()), self.dat.CHARACTER_SCREEN_WIDTH)
                if thekey.keychar == 'x':
                    self.msgbox(self.rootcon, 'You start to meditate!', self.dat.CHARACTER_SCREEN_WIDTH)
                    level_up_xp = self.dat.LEVEL_UP_BASE + self.player.fighter.xplevel * self.dat.LEVEL_UP_FACTOR
                    self.player.fighter.xp = level_up_xp
                    self.check_level_up(self.player)
                    self.player.game_turns += 1
                if thekey.keychar == 'a':
                    self.msgbox(self.rootcon, 'You can smell them all!', self.dat.CHARACTER_SCREEN_WIDTH)
                    self.set_entities_visible()
                if thekey.keychar == 'q':
                    self.msgbox(self.rootcon, 'You feel your inner dwarf admiring the dungeon walls!', self.dat.CHARACTER_SCREEN_WIDTH)
                    self.map[self.dungeon_levelname].set_map_explored()
                    self.fov_recompute = True
                if thekey.keychar == 'z':
                    self.msgbox(self.rootcon, 'You start digging at your feet!', self.dat.CHARACTER_SCREEN_WIDTH)
                    self.next_level()
                if thekey.keychar == '>':
                    if self.downstairs[self.dat.maplist[self.player.dungeon_level]].x == self.player.x and self.downstairs[self.dat.maplist[self.player.dungeon_level]].y == self.player.y:
                        self.player.game_turns +=1
                        self.next_level()
                if thekey.keychar == '<':
                    if self.upstairs[self.dat.maplist[self.player.dungeon_level]].x == self.player.x and self.upstairs[self.dat.maplist[self.player.dungeon_level]].y == self.player.y:
                        self.player.game_turns +=1
                        self.prev_level()
                if thekey.keychar == 's': #general status key
                    self.msgbox(self.rootcon, 'You start digging above your head!', self.dat.CHARACTER_SCREEN_WIDTH)
                    self.prev_level()
                if thekey.keychar == 'p': #display log
                    width = self.dat.SCREEN_WIDTH
                    height = self.dat.SCREEN_HEIGHT
                    history = [[]]
                    count = 0
                    page = 1
                    numpages = int(float(len(self.msg_history))/self.dat.MAX_NUM_ITEMS + 1)
                    for thepage in range(numpages):
                        history.append([])
                    for msg in reversed(self.msg_history):
                        line = msg.text
                        color = msg.color
                        history[page].append(MenuOption(line, color = color))
                        count += 1
                        if count >= self.dat.MAX_NUM_ITEMS:
                            page +=1
                            count = 0
                    # XXX this is problematic for curses
                    for thepage in range(numpages):
                        window = self.gui.new_window(width, height)
                        self.gui.print_rect(window, 0, 0, width, height, '')
                        self.gui.con_blit(window, 0, 0, width, height, 0, 0, 0, 1.0, 1)
                        self.menu(self.rootcon, 'Message Log: (Sorted by Most Recent Turn) Page ' + str(thepage+1) + '/' + str(numpages), history[thepage+1], self.dat.SCREEN_WIDTH, letterdelim=None)
                    self.fov_recompute = True
                if thekey.keychar == 'r':
                    log.info('reloading game data')
                    reload(self.ent)
                    self.fov_recompute = True
                    self.gui.prep_keyboard(self.dat.KEYS_INITIAL_DELAY,self.dat.KEYS_INTERVAL)
                    buff_component = Buff(self, 'Super Strength', power_bonus=20)
                    self.player.fighter.add_buff(buff_component)
                    self.msgbox ('YOU ROAR WITH BERSERKER RAGE!', self.dat.CHARACTER_SCREEN_WIDTH)
                if thekey.keychar == 'w':
                    self.msgbox(self.rootcon, 'You fashion some items from the scraps at your feet', self.dat.CHARACTER_SCREEN_WIDTH)
                    self.give_items()
                return self.dat.STATE_NOACTION

    def give_items(self):
        x = 0
        y = 0
        for item in self.ent.items:
            theitem = Entity(self, **self.ent.items[item])
            theitem.always_visible = True
            self.player.fighter.add_item(theitem)

    def set_entities_visible(self):
        for entity in self.entities[self.dat.maplist[self.player.dungeon_level]]:
            entity.always_visible = True

    def save_final_sql_csv(self):
        if self.dat.FREE_FOR_ALL_MODE:
            for entity in self.entities[self.dungeon_levelname]:
                if entity.fighter:
                    self.entity_db.log_entity(entity)
            self.entity_db.log_flush(force_flush=True)
            self.message_db.log_flush(force_flush=True)
            self.entity_db.export_csv()
            self.message_db.export_csv()

    def save_game(self, filename='savegame'):
        log.info('game saved')
        file = shelve.open(filename, 'n')
        file['map'] = self.map
        file['entities'] = self.entities[self.dungeon_levelname]
        file['player_index'] = self.entities[self.dungeon_levelname].index(self.player) #index of player in the entities list
        file['game_msgs'] = self.game_msgs
        file['msg_history'] = self.msg_history
        file['game_state'] = self.game_state
        file['stairs_index'] = self.entities[self.dungeon_levelname].index(self.stairs)
        file['dungeon_level'] = self.player.dungeon_level
        file.close()

    def load_game(self, filename='savegame'):
        file = shelve.open(filename, 'r')
        self.map = file['map']
        self.entities[self.dungeon_levelname] = file['entities']
        self.player = self.entities[self.dungeon_levelname][file['player_index']]  #get index of player in the entities list
        self.game_msgs = file['game_msgs']
        self.msg_history = file['msg_history']
        self.game_state = file['game_state']
        self.stairs = self.entities[self.dungeon_levelname][file['stairs_index']]
        self.player.dungeon_level = file['dungeon_level']
        file.close()
        self.map[self.dungeon_levelname].initialize_fov()

    def new_game(self):
        fighter_component = Fighter(self, hp=300, defense=10, power=20, xp=0, xpvalue=0, clan='monster', death_function=self.player_death, speed = 10)
        self.player = Entity(self, self.dat.SCREEN_WIDTH/2, self.dat.SCREEN_HEIGHT/2, '@', 'Roguetato', self.col.WHITE, tilechar=self.dat.TILE_MAGE, blocks=True, fighter=fighter_component)
        self.player.dungeon_level = 0
        self.game_state = self.dat.STATE_PLAYING
        self.player.game_turns = 0
        self.dungeon_levelname = self.dat.maplist[self.player.dungeon_level]
        self.map = {}
        self.entities = {}
        self.upstairs = {}
        self.downstairs = {}
        self.tick = 0
        if self.dat.FREE_FOR_ALL_MODE: #turn on SQL junk and kill player.
            self.entity_db = stats.SQLStats(self, self.dat.ENTITY_DB)
            self.message_db = stats.SQLStats(self, self.dat.MESSAGE_DB)
            self.sql_commit_counter = self.dat.SQL_COMMIT_TICK_COUNT
            self.player.fighter.alive = False
            self.player.fighter.hp = 0
        self.make_dungeon()
        self.tick = 1
        self.fov_recompute = True
        self.player.fighter.fov = self.map[self.dungeon_levelname].fov_map
        self.gui.clear(self.con)
        if not self.dat.AUTOMODE:
            equipment_component = Equipment(self, slot='wrist', max_hp_bonus = 5)
            entity = Entity(self, 0, 0, '-', 'wristguards of the whale', self.col.LIGHT_RED, equipment=equipment_component)
            entity.always_visible = True
            self.player.fighter.add_item(entity)
            equipment_component.equip(self.player)
            self.player.fighter.hp = self.player.fighter.max_hp()
        self.message('Welcome to MeFightRogues! Good Luck! Don\'t suck!', self.col.BLUE)
        self.gui.prep_keyboard(self.dat.KEYS_INITIAL_DELAY,self.dat.KEYS_INTERVAL)

    def play_game(self):
        self.player_action = None
        (self.camera_x, self.camera_y) = (0, 0)
        if self.dat.AUTOMODE:
            self.set_entities_visible()
            self.map[self.dungeon_levelname].set_map_explored()
            battleover = False
            self.fov_recompute = True
        while not self.gui.isgameover():
            if not self.player.fighter.alive: #this is sorta dumb and probably needs fixed.
                self.player.fighter.death_function(self.player, None)
            self.render_all() #TODO: probably need to do some surgery in gamestuff.render_all()
            if 0:
                for entity in self.entities[self.dat.maplist[self.player.dungeon_level]]:
                    entity.clear()
            self.dungeon_levelname = self.dat.maplist[self.player.dungeon_level]
            if not self.dat.AUTOMODE:
                if (self.player.fighter.speed_counter <= 0 and not self.player.ai) or self.game_state == self.dat.STATE_DEAD: #player can take a turn-based unless it has an AI
                    self.player_action = self.handle_keys()
                    if self.player_action != self.dat.STATE_NOACTION:
                        self.player.fighter.speed_counter = self.player.fighter.speed()
            if self.player_action == self.dat.STATE_EXIT:
                break
            if self.game_state == self.dat.STATE_PLAYING and self.player_action != self.dat.STATE_NOACTION:
                self.tick += 1
                self.fov_recompute = True
                for index,self.dungeon_levelname in enumerate(self.dat.maplist):
                    #if index > 0: #skip intro level
                    for entity in self.entities[self.dungeon_levelname]:
                        if entity.fighter:
                            if entity.fighter.speed_counter <= 0 and entity.fighter.alive: #only allow a turn if the counter = 0.
                                if entity.ai:
                                    if entity.ai.take_turn(): #only reset speed_counter if monster is still alive
                                        entity.fighter.speed_counter = entity.fighter.speed()
                            if entity.fighter.alive:
                                if entity.fighter.regen_counter <= 0: #only regen if the counter = 0.
                                    entity.fighter.hp += int(entity.fighter.max_hp() * self.dat.REGEN_MULTIPLIER)
                                    entity.fighter.regen_counter = entity.fighter.regen()
                                entity.fighter.regen_counter -= 1
                                entity.fighter.speed_counter -= 1
                                if entity.fighter.buffs:
                                    for buff in entity.fighter.buffs:
                                        buff.duration -= buff.decay_rate
                                        if buff.duration <= 0:
                                            self.message(entity.name + ' feels the effects of ' + buff.name + ' wear off!', self.col.LIGHT_RED)
                                            entity.fighter.remove_buff(buff)
                                if entity.fighter.hp > entity.fighter.max_hp():
                                        entity.fighter.hp = entity.fighter.max_hp()
                                self.check_level_up(entity)
                            if self.dat.FREE_FOR_ALL_MODE:
                                self.entity_db.log_entity(entity)
                        elif entity.ai:
                            entity.ai.take_turn()
                if self.dat.FREE_FOR_ALL_MODE:
                    self.entity_db.log_flush()
                    self.message_db.log_flush()
                    self.sql_commit_counter -= 1
                if self.dat.AUTOMODE:
                    alive_entities = self.total_alive_entities()
                    if len(alive_entities) == 1:
                        self.message('BATTLE R, OYALE IS OVER! Winner is ', self.col.BLUE)
                        self.printstats(alive_entities[0])
                        self.dat.AUTOMODE = False
                        self.render_all()
                        chosen_item = self.inventory_menu(self.rootcon,'inventory for ' + alive_entities[0].name, alive_entities[0])
                        self.save_final_sql_csv()
                    if len(alive_entities) <=0:
                        self.message('BATTLE ROYALE IS OVER! EVERYONE DIED! YOU ALL SUCK!', self.col.BLUE)
                        self.dat.AUTOMODE = False
                        self.save_final_sql_csv()
            self.dungeon_levelname = self.dat.maplist[self.player.dungeon_level]
