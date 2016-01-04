
from dungeoneer import curses, tcod, log

class Colors(object):

    def __init__(self, engine):
        self.engine = engine

    def init_colors(self):
        log.debug('initializing colors')
        if self.engine.game_mode == 'tcod':
            self.BLACK   = tcod.black
            self.RED     = tcod.red
            self.GREEN   = tcod.green
            self.YELLOW  = tcod.yellow
            self.BLUE    = tcod.blue
            self.MAGENTA = tcod.magenta
            self.CYAN    = tcod.cyan
            self.WHITE   = tcod.white
            self.DARK_GREY     = tcod.dark_grey
            self.LIGHT_RED     = tcod.light_red
            self.LIGHT_GREEN   = tcod.light_green
            self.LIGHT_YELLOW  = tcod.light_yellow
            self.LIGHT_BLUE    = tcod.light_blue
            self.LIGHT_MAGENTA = tcod.light_magenta
            self.LIGHT_CYAN    = tcod.light_cyan
            self.LIGHT_GREY    = tcod.light_grey
            self.DARK_SEPIA    = tcod.dark_sepia
            self.SEPIA         = tcod.sepia
        elif self.engine.game_mode == 'curses':
            for col in range(1,8):
                curses.init_pair(col, col, curses.COLOR_BLACK)
            self.BLACK   = curses.color_pair(0)
            self.RED     = curses.color_pair(1)
            self.GREEN   = curses.color_pair(2)
            self.YELLOW  = curses.color_pair(3)
            self.BLUE    = curses.color_pair(4)
            self.MAGENTA = curses.color_pair(5)
            self.CYAN    = curses.color_pair(6)
            self.WHITE   = curses.color_pair(7)
            self.DARK_GREY     = curses.color_pair(0) | curses.A_BOLD
            self.LIGHT_RED     = curses.color_pair(1) | curses.A_BOLD
            self.LIGHT_GREEN   = curses.color_pair(2) | curses.A_BOLD
            self.LIGHT_YELLOW  = curses.color_pair(3) | curses.A_BOLD
            self.LIGHT_BLUE    = curses.color_pair(4) | curses.A_BOLD
            self.LIGHT_MAGENTA = curses.color_pair(5) | curses.A_BOLD
            self.LIGHT_CYAN    = curses.color_pair(6) | curses.A_BOLD
            self.LIGHT_GREY    = curses.color_pair(7) | curses.A_BOLD
            self.DARK_SEPIA    = self.MAGENTA
            self.SEPIA         = self.LIGHT_YELLOW
        else:
            self.BLACK         = 0
            self.RED           = 0
            self.GREEN         = 0
            self.YELLOW        = 0
            self.BLUE          = 0
            self.MAGENTA       = 0
            self.CYAN          = 0
            self.WHITE         = 0
            self.DARK_GREY     = 0
            self.LIGHT_RED     = 0
            self.LIGHT_GREEN   = 0
            self.LIGHT_YELLOW  = 0
            self.LIGHT_BLUE    = 0
            self.LIGHT_MAGENTA = 0
            self.LIGHT_CYAN    = 0
            self.LIGHT_GREY    = 0
            self.DARK_SEPIA    = 0
            self.SEPIA         = 0


class EntityData(object):

    def __init__(self, engine):
        self.mobs = {
         'johnstein':      {'char':'j', 'color':engine.col.LIGHT_GREY,  'tilechar':engine.dat.TILE_SKEL_WHITE,   'fighter':{'hp':200 , 'defense':0 , 'power':20 , 'xp':0, 'xpvalue':20 , 'clan':'monster', 'death_function':engine.monster_death, 'speed':5}, 'caster':{'mp':10}},
         'greynaab':       {'char':'g', 'color':engine.col.LIGHT_BLUE,  'tilechar':engine.dat.TILE_SKEL_RED  ,   'fighter':{'hp':200 , 'defense':1 , 'power':40 , 'xp':0, 'xpvalue':40 , 'clan':'monster', 'death_function':engine.monster_death, 'speed':5}},
         'jerbear':        {'char':'j', 'color':engine.col.GREEN,       'tilechar':engine.dat.TILE_SKEL_BLUE ,   'fighter':{'hp':250 , 'defense':1 , 'power':50 , 'xp':0, 'xpvalue':50 , 'clan':'monster', 'death_function':engine.monster_death, 'speed':5}},
         'zombiesheep':    {'char':'z', 'color':engine.col.YELLOW,      'tilechar':engine.dat.TILE_SKEL_GREEN,   'fighter':{'hp':300 , 'defense':2 , 'power':60 , 'xp':0, 'xpvalue':60 , 'clan':'monster', 'death_function':engine.monster_death, 'speed':5}},
         'pushy':          {'char':'p', 'color':engine.col.MAGENTA,     'tilechar':engine.dat.TILE_SKEL_MAGENTA, 'fighter':{'hp':400 , 'defense':2 , 'power':00 , 'xp':0, 'xpvalue':100, 'clan':'monster', 'death_function':engine.monster_death, 'speed':5}},
         'JOHNSTEIN':      {'char':'J', 'color':engine.col.BLACK,       'tilechar':engine.dat.TILE_SKEL_WHITE,   'fighter':{'hp':1000 , 'defense':3, 'power':5 , 'xp':0, 'xpvalue':200 , 'clan':'monster', 'death_function':engine.monster_death, 'speed':1}},
         'GREYNAAB':       {'char':'G', 'color':engine.col.RED,         'tilechar':engine.dat.TILE_SKEL_RED  ,   'fighter':{'hp':2000 , 'defense':6, 'power':10, 'xp':0, 'xpvalue':400 , 'clan':'monster', 'death_function':engine.monster_death, 'speed':3}},
         'JERBEAR':        {'char':'J', 'color':engine.col.BLUE,        'tilechar':engine.dat.TILE_SKEL_BLUE ,   'fighter':{'hp':2500 , 'defense':9, 'power':15, 'xp':0, 'xpvalue':500 , 'clan':'monster', 'death_function':engine.monster_death, 'speed':5}},
         'ZOMBIESHEEP':    {'char':'Z', 'color':engine.col.GREEN,       'tilechar':engine.dat.TILE_SKEL_GREEN,   'fighter':{'hp':3000 , 'defense':12,'power':20, 'xp':0, 'xpvalue':600 , 'clan':'monster', 'death_function':engine.monster_death, 'speed':7}},
         'PUSHY':          {'char':'P', 'color':engine.col.MAGENTA,     'tilechar':engine.dat.TILE_SKEL_MAGENTA, 'fighter':{'hp':5000 , 'defense':20,'power':0 , 'xp':0, 'xpvalue':1000 ,'clan':'monster', 'death_function':engine.monster_death, 'speed':1}},
        }
        self.mobitems = {
            'johnstein':   ['heal', 'fireball', 'lightning', 'confuse', 'push', 'bigpush'],
            'greynaab':    ['fireball', 'fireball', 'fireball'],
            'jerbear':     ['fireball', 'fireball', 'fireball'],
            'zombiesheep': ['fireball','fireball','fireball','fireball'],
            'pushy':       ['push','push','push','push','push','push','push','push','push','push','push','push','push','push','push','push','push','push'],
            'JOHNSTEIN':   ['heal', 'heal', 'heal', 'heal'],
            'GREYNAAB':    ['fireball', 'heal', 'fireball'],
            'JERBEAR':     ['confuse', 'heal', 'heal'],
            'ZOMBIESHEEP': ['lightning','lightning','heal', 'lightning'],
            'PUSHY':       ['bigpush','bigpush','bigpush','bigpush','bigpush','bigpush','bigpush','bigpush','bigpush','bigpush','bigpush','bigpush','bigpush','bigpush','bigpush','bigpush','bigpush','bigpush']
        }
        self.mobchances = {
            'johnstein':    [[10, 1], [50, 3]],
            'greynaab':     [[10, 2], [25, 3]],
            'jerbear':      [[10, 2], [25, 3]],
            'zombiesheep':  [[10, 2], [25, 3]],
            'pushy'      :  [[10, 2], [50,3]],
            'JOHNSTEIN':    [[10, 3], [35, 5]],
            'GREYNAAB':     [[10, 3], [35, 5]],
            'JERBEAR':      [[10, 3], [30, 5]],
            'ZOMBIESHEEP':  [[10, 3], [25, 5]],
            'PUSHY':        [[10, 3], [50, 5]]
        }
        self.items = {
            'heal':       {'name':'healing potion',           'char':'!', 'color':engine.col.RED,           'item':{'use_function': engine.cast_heal}},
            'lightning':  {'name':'scroll of lightning bolt', 'char':'?', 'color':engine.col.YELLOW,        'item':{'use_function': engine.cast_lightning}},
            'fireball':   {'name':'scroll of fireball',       'char':'?', 'color':engine.col.RED,           'item':{'use_function': engine.cast_fireball}},
            'confuse':    {'name':'scroll of confusion',      'char':'?', 'color':engine.col.LIGHT_RED,     'item':{'use_function': engine.cast_confusion}},
            'push'   :    {'name':'scroll of push',           'char':'?', 'color':engine.col.MAGENTA,       'item':{'use_function': engine.cast_push}},
            'bigpush':    {'name':'scroll of bigpush',        'char':'?', 'color':engine.col.LIGHT_MAGENTA, 'item':{'use_function': engine.cast_bigpush}},
            'sword':      {'name':'sword',  'char':'/', 'color':engine.col.CYAN,           'equipment':{'slot':'right hand' ,   'power_bonus'  :5  }},
            'shield':     {'name':'shield', 'char':'[', 'color':engine.col.LIGHT_GREEN,    'equipment':{'slot':'left hand'  ,   'defense_bonus':3  }},
            'blue_crystal':     {'name':'blue power crystal',    'char':'$', 'color':engine.col.CYAN,         'item':{'use_function': engine.use_blue_crystal}},
            'red_crystal':      {'name':'red power crystal',     'char':'$', 'color':engine.col.RED,          'item':{'use_function': engine.use_red_crystal}},
            'green_crystal':    {'name':'green power crystal',   'char':'$', 'color':engine.col.GREEN,        'item':{'use_function': engine.use_green_crystal}},
            'yellow_crystal':   {'name':'yellow power crystal',  'char':'$', 'color':engine.col.YELLOW,       'item':{'use_function': engine.use_yellow_crystal}},
            'orange_crystal':   {'name':'orange power crystal',  'char':'$', 'color':engine.col.LIGHT_YELLOW, 'item':{'use_function': engine.use_orange_crystal}}
        }
        self.itemchances = {
            'heal':          [[50,1]],
            'lightning':     [[20, 1], [25, 3], [50, 5]],
            'fireball':      [[20, 1], [25, 3], [50, 5]],
            'confuse':       [[20, 1], [25, 3], [50, 5]],
            'sword':         [[20, 1], [25, 3], [50, 5]],
            'shield':        [[20, 1], [25, 3], [50, 5]],
            'blue_crystal':  [[10, 1], [30, 3], [50, 5]],
            'red_crystal':   [[10, 1], [30, 3], [50, 5]],
            'green_crystal': [[10, 1], [30, 3], [50, 5]],
            'yellow_crystal':[[10, 1], [30, 3], [50, 5]],
            'orange_crystal':[[10, 1], [30, 3], [50, 5]]
        }


class GameData(object):

    def __init__(self, engine):
        self.engine = engine
        self.SHOW_PANEL         = True
        self.WALL_CHAR          = 'X'
        self.GROUND_CHAR        = ' '
        self.COLOR_DARK_WALL    = self.engine.col.DARK_GREY
        self.COLOR_LIGHT_WALL   = self.engine.col.LIGHT_GREY
        self.COLOR_DARK_GROUND  = self.engine.col.DARK_SEPIA
        self.COLOR_LIGHT_GROUND = self.engine.col.SEPIA
        self.FOV_ALGO           = 2 #FOV ALGORITHM. values = 0 to 4
        self.FOV_LIGHT_WALLS    = True
        self.TORCH_RADIUS       = 80 #AFFECTS FOV RADIUS
        self.TILE_WALL          = 256  #first tile in the first row of tiles
        self.TILE_GROUND        = 256 + 1
        self.TILE_MAGE          = 256 + 32  #first tile in the 2nd row of tiles
        self.TILE_SKEL_WHITE    = 256 + 32 + 1  #2nd tile in the 2nd row of tiles
        self.TILE_SKEL_RED      = 256 + 32 + 2  #2nd tile in the 2nd row of tiles
        self.TILE_SKEL_BLUE     = 256 + 32 + 3  #2nd tile in the 2nd row of tiles
        self.TILE_SKEL_GREEN    = 256 + 32 + 4  #2nd tile in the 2nd row of tiles
        self.TILE_SKEL_ORANGE   = 256 + 32 + 5  #2nd tile in the 2nd row of tiles
        self.TILE_SKEL_MAGENTA  = 256 + 32 + 6  #2nd tile in the 2nd row of tiles
        self.TILE_SKEL_TEAL     = 256 + 32 + 7  #2nd tile in the 2nd row of tiles
        self.TILE_SKEL_YELLOW   = 256 + 32 + 8  #2nd tile in the 2nd row of tiles
        self.TILE_SKEL_PURPLE   = 256 + 32 + 9  #2nd tile in the 2nd row of tiles
        self.maplist = ['Intro', 'Brig']

        self.SCREEN_WIDTH       = 80
        self.SCREEN_HEIGHT      = 60
        self.CAMERA_WIDTH       = 80
        self.CAMERA_HEIGHT      = 40
        self.MAP_WIDTH          = 100
        self.MAP_HEIGHT         = 60

        if engine.game_mode == 'curses':
            self.TERM_WIDTH, self.TERM_HEIGHT = engine.winsz
            #self.PANEL_HEIGHT = 10

            self.SCREEN_WIDTH = min([self.TERM_WIDTH, self.SCREEN_WIDTH])
            self.SCREEN_HEIGHT = min([self.TERM_HEIGHT, self.SCREEN_HEIGHT])

            self.CAMERA_WIDTH       = self.SCREEN_WIDTH
            self.CAMERA_HEIGHT      = self.SCREEN_HEIGHT - 15

            self.MAP_WIDTH          = 100
            self.MAP_HEIGHT         = 60

        self.MAP_PAD_W          = self.CAMERA_WIDTH  / 2  #don't allow rooms to touch edges. ideally also don't get close enough to edge of map to stop the scrolling effect
        self.MAP_PAD_H          = self.CAMERA_HEIGHT / 2
        self.ROOM_MAX_SIZE      = 25
        self.ROOM_MIN_SIZE      = 25
        self.MAX_ROOMS          = ((self.MAP_WIDTH - self.CAMERA_WIDTH) + (self.MAP_HEIGHT - self.CAMERA_HEIGHT)) / 3
        self.MAX_ROOMS = 2
        self.ENTITY_DB          = 'entity_stats'
        self.MESSAGE_DB         = 'game_log'
        self.SQL_COMMIT_TICK_COUNT = 5
        self.LEVEL_UP_BASE     = 2
        self.LEVEL_UP_FACTOR   = 2
        self.AUTOEQUIP         = True #ARE ITEMS AUTO-EQUIPPED ON PICKUP?
        self.AUTOMODE          = False
        self.FREE_FOR_ALL_MODE = True  #if true, all monsters on diffent clans by default
        self.PRINT_MESSAGES      = True  #if true, print messages to log
        self.TURNBASED         = True #not working yet
        self.SPEED_DEFAULT     = 5  # speed delay. higher = slower. How many game ticks to wait between turns
        self.REGEN_DEFAULT     = 100000  # regen delay. higher = slower. How many game ticks to wait between regeneration
        self.REGEN_MULTIPLIER  = 0.00001 # % of life to regen
        self.KEYS_INITIAL_DELAY= 0
        self.KEYS_INTERVAL     = 0
        self.BUFF_DECAYRATE    = 1  #amount to reduce per tick
        self.BUFF_DURATION     = 30 #in game ticks
        self.MAX_NUM_ITEMS     = 26
        self.INVENTORY_WIDTH   = 50
        self.CHARACTER_SCREEN_WIDTH = 30  #WIDTH USED IN MSGBOX DISPLAYING MESSAGES TO PLAYER
        self.LEVEL_SCREEN_WIDTH     = 40  #WIDTH USED IN MSGBOX FOR LEVEL UP
        self.LIMIT_FPS              = 20  #LIMITS FPS TO A REASONABLE AMOUNT
        self.BAR_WIDTH         = 20
        self.PANEL_HEIGHT      = self.SCREEN_HEIGHT - self.CAMERA_HEIGHT
        self.PANEL_Y           = self.SCREEN_HEIGHT - self.PANEL_HEIGHT
        self.MSG_X             = self.BAR_WIDTH + 2
        self.MSG_WIDTH         = self.SCREEN_WIDTH - self.BAR_WIDTH - 2
        self.MSG_HEIGHT        = self.PANEL_HEIGHT - 1
        self.MAIN_MENU_BKG     = 'resources/menu_background.png'
        self.MAIN_MENU_BKG_ASCII = 'resources/menu_background'
        self.STATE_PLAYING     = 'playing'
        self.STATE_NOACTION    = 'no_action'
        self.STATE_DEAD        = 'dead'
        self.STATE_EXIT        = 'exit'
        self.STATE_USED        = 'used'
        self.STATE_CANCELLED   = 'cancelled'
        self.HEAL_AMOUNT = 50
        self.LIGHTNING_DAMAGE = 25
        self.LIGHTNING_RANGE = 5
        self.FIREBALL_DAMAGE = 25
        self.FIREBALL_RADIUS = 3
        self.CONFUSE_NUM_TURNS = 10
        self.CONFUSE_RANGE = 8


class KeyMap(object):

    def __init__(self, engine):
        if engine.game_mode == 'tcod' or engine.game_mode == 'dummy':
            self.ESC  = tcod.KEY_ESCAPE
            self.TAB  = tcod.KEY_TAB
            self.UP   = tcod.KEY_UP
            self.DOWN = tcod.KEY_DOWN
            self.RIGHT= tcod.KEY_RIGHT
            self.LEFT = tcod.KEY_LEFT
            self.KP1  = tcod.KEY_KP1
            self.KP2  = tcod.KEY_KP2
            self.KP3  = tcod.KEY_KP3
            self.KP4  = tcod.KEY_KP4
            self.KP5  = tcod.KEY_KP5
            self.KP6  = tcod.KEY_KP6
            self.KP7  = tcod.KEY_KP7
            self.KP8  = tcod.KEY_KP8
            self.KP9  = tcod.KEY_KP9
            self.KPDEC= tcod.KEY_KPDEC
            self.ENTER= tcod.KEY_ENTER
            self.SPACE= tcod.KEY_SPACE
        elif engine.game_mode == 'curses':
            self.ESC  = 27
            self.TAB  = ord('\t')
            self.UP   = curses.KEY_UP
            self.DOWN = curses.KEY_DOWN
            self.RIGHT= curses.KEY_RIGHT
            self.LEFT = curses.KEY_LEFT
            self.KP1  = curses.KEY_C1
            self.KP2  = curses.KEY_DOWN
            self.KP3  = curses.KEY_C3
            self.KP4  = curses.KEY_LEFT
            self.KP5  = curses.KEY_B2
            self.KP6  = curses.KEY_RIGHT
            self.KP7  = curses.KEY_A1
            self.KP8  = curses.KEY_UP
            self.KP9  = curses.KEY_A3
            self.KPDEC= curses.KEY_DC
            self.ENTER= curses.KEY_ENTER
            self.SPACE= ' '
        else:
            raise RuntimeError

