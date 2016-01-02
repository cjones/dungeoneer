#!/usr/bin/env python

import locale
locale.setlocale(locale.LC_ALL, '')

from subprocess import Popen

import sqlite3 as sql
import traceback
import textwrap
import argparse
import logging
import shelve
import array
import math
import time
import sys
import abc
import os

sys.dont_write_bytecode = True  # for great justice

from backends import tcod

try:
    import curses.ascii
except ImportError:
    CURSES = False
else:
    CURSES = True

DEVELOP = True

BACKENDS = ['tcod']
if CURSES:
    BACKENDS.append('curses')
if DEVELOP:
    BACKENDS.append('dummy')

class Logger(logging.Logger):
    format = '%(asctime)s [%(levelname)s] %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'

    def __init__(self, *args, **kwargs):
        self._formatter = None
        super(Logger, self).__init__(*args, **kwargs)

    @property
    def formatter(self):
        if self._formatter is None:
            self._formatter = logging.Formatter(self.format, self.datefmt)
        return self._formatter

    def setLevel(self, level=None):
        if level is None:
            level = logging.INFO
        elif isinstance(level, basestring):
            level = level.upper()
        ret = super(Logger, self).setLevel(level)
        for handler in self.handlers:
            handler.setLevel(self.level)
        return ret

    def addHandler(self, handler):
        handler.setFormatter(self.formatter)
        handler.setLevel(self.level)
        return super(Logger, self).addHandler(handler)

    def make_handler(self, cls, arg, *extra):
        if arg is not None:
            return self.addHandler(cls(arg, *extra))

    def add_file(self, file, mode='a'):
        return self.make_handler(logging.FileHandler, file, mode)

    def add_stream(self, stream):
        return self.make_handler(logging.StreamHandler, stream)

    @classmethod
    def parse_string_format(cls, string):
        # returns an iterable that contains tuples of the form:
        # (literal_text, field_name, format_spec, conversion)
        # literal_text can be zero length
        # field_name can be None, in which case there's no
        #  object to format and output
        # if field_name is not None, it is looked up, formatted
        #  with format_spec and conversion and then used
        for literal_text, field_name, format_spec, conversion in str._formatter_parser(string):
            if field_name is not None:
                yield field_name
            if format_spec is not None:
                for nested_field_name in cls.parse_string_format(format_spec):
                    yield nested_field_name

    def _log(self, level, msg, args, **kwargs):
        extra = kwargs.pop('extra', None)
        exc_info = kwargs.pop('exc_info', None)
        if msg is not None:
            if args or kwargs:
                args = list(args)
                format_args = []
                format_kwargs = {}
                for field_name in self.parse_string_format(msg):
                    if field_name:
                        format_kwargs[field_name] = kwargs.pop(field_name, None)
                    elif args:
                        format_args.append(args.pop(0))
                try:
                    msg = msg.format(*format_args, **format_kwargs)
                except:
                    msg = 'format error: ' + repr((msg, format_args, format_kwargs))
                args = tuple(args)
            return super(Logger, self)._log(level, msg, args, extra=extra, exc_info=exc_info, **kwargs)

logging.setLoggerClass(Logger)
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.DEBUG)
logger.disabled = True


class CallbackAction(argparse.Action):

    def __init__(self, *args, **kwargs):
        self.__callback_func = kwargs.pop('callback', None)
        nargs = kwargs.pop('nargs', None)
        if nargs is None:
            nargs = 0
        if nargs == 0:
            kwargs['metavar'] = argparse.SUPPRESS
        super(CallbackAction, self).__init__(*args, **dict(kwargs,
            dest=argparse.SUPPRESS, default=argparse.SUPPRESS, nargs=nargs))

    def __call__(self, parser, namespace, values, option_string=None):
        self.__callback_func(*values)


class LoggingCallbackAction(CallbackAction):
    nargs = 0

    def __init__(self, *args, **kwargs):
        self._logger = kwargs.pop('logger', None)
        if self._logger is None:
            self._logger = logging.getLogger(None)
        super(LoggingCallbackAction, self).__init__(*args, **dict(kwargs, callback=self.callback, nargs=self.nargs))

    @abc.abstractmethod
    def callback(self, arg=None):
        raise NotImplementedError


class SetLogLevelAction(LoggingCallbackAction):
    choices = ('debug', 'info', 'warn', 'error')
    nargs = 1

    def __init__(self, *args, **kwargs):
        super(SetLogLevelAction, self).__init__(*args, **dict(kwargs, choices=self.choices))

    def callback(self, level):
        self._logger.setLevel(level)


class AddLogFileAction(LoggingCallbackAction):
    nargs = 1

    def callback(self, file):
        self._logger.add_file(file)
        self._logger.disabled = 0


class Colors(object):

    def __init__(self, engine):
        self.engine = engine

    def init_colors(self):
        logger.debug('initializing colors')
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


class GameData(object):

    def __init__(self, engine):
        self.engine = engine
        self.SHOW_PANEL         = False
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
        self.maplist =[]
        self.maplist.append('Intro')
        self.maplist.append('Brig')

        self.SCREEN_WIDTH       = 80  #SETS OVERALL SCREEN WIDTH. MUST BE > MAP_WIDTH
        self.SCREEN_HEIGHT      = 60  #SETS OVERALL SCREEN HEIGHT. MUST BE > MAP_HEIGHT
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


class Thing(object):

    def __init__(self, engine, x=0, y=0, char='?', name=None, color=None,
                 tilechar=None, blocks=False, id=None, dungeon_level=None,
                 always_visible=False, fighter=None, caster=None, ai=None,
                 item=None, equipment=None):
        self.engine = engine
        self.name = name
        self.blocks = blocks
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.always_visible = always_visible
        self.dungeon_level = dungeon_level
        if self.color is None:
            self.color = self.engine.col.WHITE
        self.tilechar = tilechar
        if self.tilechar is None:
            self.tilechar = self.char
        self.fighter = fighter
        if self.fighter:
            if type(fighter) is dict:
                self.fighter = Fighter(self.engine, **fighter)
            self.fighter.owner = self
        self.caster = caster
        if self.caster:
            if type(caster) is dict:
                self.caster = Caster(**caster)
            self.caster.owner = self
        self.ai = ai
        if self.ai:
            self.ai.owner = self
        self.item = item
        if self.item:
            if type(item) is dict:
                self.item = Item(self.engine, **item)
            self.item.owner = self
        self.equipment = equipment
        if self.equipment:
            if type(equipment) is dict:
                self.equipment = Equipment(self.engine, **equipment)
            self.equipment.owner = self
            self.item = Item(self.engine)
            self.item.owner = self

    def set_location(self, x, y):
        if not self.engine.is_blocked(x, y):
            self.x = x
            self.y = y
            return True
        else:
            return False

    def move(self, dx, dy):
        if not self.engine.is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy
            return True
        else:
            return False

    def move_random(self):
        self.move(random_int(0, -1, 1), random_int(0, -1, 1))

    def draw(self):
        if (self.engine.fovx.map_is_in_fov(self.engine.player.fighter.fov, self.x, self.y) or (self.always_visible and self.map[self.engine.dungeon_levelname].explored(self.x, self.y))):
            (x, y) = self.engine.to_camera_coordinates(self.x, self.y)
            if x is not None:
                if self.engine.ascii_mode:
                    thechar = self.char
                else:
                    thechar = self.tilechar
                self.engine.gui.print_char(self.engine.con, x, y, val=thechar, fg_color=self.color, bg_color=self.engine.color_ground)

    def clear(self):
        (x, y) = self.engine.to_camera_coordinates(self.x, self.y)
        if x is not None and self.engine.fovx.map_is_in_fov(self.engine.player.fighter.fov, self.x, self.y):
            self.engine.gui.print_char(self.engine.con, x, y, val=self.engine.dat.GROUND_CHAR, fg_color=self.engine.col.WHITE, bg_color=self.engine.dat.COLOR_LIGHT_GROUND)

    def move_away(self, target):
        if self.dungeon_level == target.dungeon_level:
            dx1 = target.x - self.x
            dy1 = target.y - self.y
            distance = get_distance(dx1, dy1)
            dx = -1*int(round(dx1 / distance))
            dy = -1*int(round(dy1 / distance))
            if not self.move(dx, dy):
                if dx1 != 0:
                    dx = -1 * abs(dx1) / dx1
                elif target.x < self.x:
                    dx = 1
                else:
                    dx = -1
                if dy1 != 0:
                    dy = -1*abs(dy1) / dy1
                elif target.y < self.y:
                    dy = 1
                else:
                    dy = -1
                self.move(dx, dy)

    def move_towards(self, target):
        if self.dungeon_level == target.dungeon_level:
            dx1 = target.x - self.x
            dy1 = target.y - self.y
            distance = get_distance(dx1, dy1)
            dx = int(round(dx1 / distance))
            dy = int(round(dy1 / distance))
            if not self.move(dx, dy):
                if dx1 != 0:
                    dx = abs(dx1) / dx1
                elif target.x < self.x:
                    dx = -1
                else:
                    dx = 1
                if dy1 != 0:
                    dy = abs(dy1) / dy1
                elif target.y < self.y:
                    dy = -1
                else:
                    dy = 1
                self.move(dx, dy)

    def distance_to(self, other):
        dx = other.x - self.x
        dy = other.y - self.y
        return get_distance(dx, dy)

    def distance(self, x, y):
        return get_distance(x - self.x, y - self.y)

    def send_to_back(self):
        self.engine.objects[self.engine.dungeon_levelname].remove(self)
        self.engine.objects[self.engine.dungeon_levelname].insert(0, self)


class Fighter(object):

    def __init__(self, engine, hp, defense, power, xp, clan=None, xpvalue=0,
                 alive=True, killed=False, xplevel=1, speed=None, regen=None,
                 death_function=None, buffs=None, inventory=None):
        self.engine = engine
        self.base_max_hp = hp
        self.hp = hp
        self.xp = xp
        self.base_defense = defense
        self.base_power = power
        self.death_function=death_function
        self.base_speed = speed
        self.speed_counter = 0
        self.base_regen = regen
        self.regen_counter = regen
        self.clan = clan
        self.xpvalue = xpvalue
        self.xplevel = xplevel
        self.alive = alive
        self.killed = killed
        if self.base_regen is None:
            self.base_regen = self.engine.dat.REGEN_DEFAULT
            self.regen_counter = self.engine.dat.REGEN_DEFAULT
        if self.base_speed is None:
            self.base_speed = self.engine.dat.SPEED_DEFAULT
        self.inventory = inventory
        if self.inventory:
            self.inventory.owner = self
        self.buffs = buffs
        if self.buffs:
            self.buffs.owner = self

    def recompute_fov(self):
        self.engine.fovx.map_compute_fov(self.fov, self.owner.x, self.owner.y, self.engine.dat.TORCH_RADIUS, self.engine.dat.FOV_LIGHT_WALLS, self.engine.dat.FOV_ALGO)
        return self.fov

    def add_item(self, item):
        if not self.inventory:
            self.inventory = []
        self.inventory.append(item)
        item.owner = self

    def remove_item(self, item):
        try:
            self.inventory.remove(item)
            item.owner = None
        except:
            logger.exception('error in remove_item: {}/{}', self.owner.name, item.name)

    def add_buff(self, buff):
        if not self.buffs:
            self.buffs = []
        self.buffs.append(buff)

    def remove_buff(self, buff):
        self.buffs.remove(buff)

    def regen(self):
        bonus = sum(equipment.regen_bonus for equipment in self.engine.get_all_equipped(self.owner))
        if self.buffs:
            bonus += sum(buff.regen_bonus for buff in self.buffs)
        return self.base_regen + bonus

    def speed(self):
        bonus = sum(equipment.speed_bonus for equipment in self.engine.get_all_equipped(self.owner))
        if self.buffs:
            bonus += sum(buff.speed_bonus for buff in self.buffs)
        return self.base_speed + bonus

    def power(self):
        bonus = sum(equipment.power_bonus for equipment in self.engine.get_all_equipped(self.owner))
        if self.buffs:
            bonus += sum(buff.power_bonus for buff in self.buffs)
        return self.base_power + bonus

    def defense(self):
        bonus = sum(equipment.defense_bonus for equipment in self.engine.get_all_equipped(self.owner))
        if self.buffs:
            bonus += sum(buff.defense_bonus for buff in self.buffs)
        return self.base_defense + bonus

    def max_hp(self):
        bonus = sum(equipment.max_hp_bonus for equipment in self.engine.get_all_equipped(self.owner))
        if self.buffs:
            bonus += sum(buff.max_hp_bonus for buff in self.buffs)
        return self.base_max_hp + bonus

    def heal(self, amount):
        self.hp += amount
        if self.hp > self.max_hp():
            self.hp = self.max_hp()

    def take_damage(self, attacker, damage):
        if damage > 0:
            self.hp -= damage
        if self.hp <= 0:
            function = self.death_function
            if function is not None:
                function(self.owner, attacker)

    def attack(self, target):
        damage = self.power() - target.fighter.defense()
        if damage > 0:
            if self is self.player:
                self.engine.message('You attack ' + target.name  + '!', self.col.YELLOW)
            elif entity_sees(self.player, self.owner):
                self.engine.message(self.owner.name.capitalize() + ' attacks ' + target.name, self.col.YELLOW)
            elif entity_sees(self.player, target):
                self.engine.message(target.name + ' has been attacked! ', self.col.YELLOW)
            target.fighter.take_damage(self.owner, damage)
        else:
            if self is self.player:
                self.engine.message('You tried to attack ' + target.name + ' but there is no effect.', self.col.WHITE)

    def entity_sees(self, entity, target):
        return self.engine.fovx.map_is_in_fov(entity.fighter.fov, target.x, target.y) and entity.dungeon_level == target.dungeon_level




class Ai(object):

    def __init__(self, ai):
        self.ai = ai
        self.ai.owner = self

    def take_turn(self):
        return self.ai.take_turn()


class Buff(object):

    def __init__(self, name, power_bonus=0, defense_bonus=0, max_hp_bonus=0, speed_bonus=0, regen_bonus=0, decay_rate=None, duration=None):
        self.name = name
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        self.max_hp_bonus = max_hp_bonus
        self.speed_bonus = speed_bonus
        self.regen_bonus = regen_bonus
        self.decay_rate = decay_rate #if 0, buff does not decay. use positive numbers to make buffs decrement
        if self.decay_rate is None:
            self.decay_rate = self.dat.BUFF_DECAYRATE
        self.duration = duration
        if self.duration is None:
            self.duration = self.dat.BUFF_DURATION


class Caster(object):

    def __init__(self, mp, spells=None):
        self.base_max_mp = mp
        self.mp = mp
        self.spells = spells
        if self.spells:
            self.spells.owner = self

    def learn_spell(self, spell):
        if not self.spells:
            self.spells = []
        self.spells.append(spell)

    def forget_spell(self, spell):
        self.spells.remove(spell)


class Item(object):

    def __init__(self, engine, use_function=None):
        self.engine = engine
        self.use_function = use_function

    def use(self, user):
        if self.owner.equipment:
            self.owner.equipment.toggle_equip(user)
            return
        if self.use_function is None:
            self.engine.message('The ' + self.owner.name + ' cannot be used.')
            return self.dat.STATE_NOACTION
        else:
            if self.use_function(user) != 'cancelled':
                if user.fighter:
                    user.fighter.remove_item(self.owner)
                self.fov_recompute = True
                return self.engine.dat.STATE_USED
            else:
                return self.engine.dat.STATE_NOACTION

    def pick_up(self, user):
        if len(user.fighter.inventory) >= 26:
            if user is self.player:
                self.engine.message('Your inventory is full! Cannot pick up ' + self.owner.name +'.', self.col.MAGENTA)
            retval = self.dat.STATE_NOACTION
        else:
            user.fighter.add_item(self.owner)
            self.engine.objects[self.engine.dungeon_levelname].remove(self.owner)
            if user is self.engine.player:
                name = 'You'
            else:
                name = user.name
            self.engine.message(name + ' picked up a ' + self.owner.name + '!', self.engine.col.GREEN, self.engine.isplayer(user))
            equipment = self.owner.equipment
            if equipment and self.engine.get_equipped_in_slot(equipment.slot, user) is None and self.engine.dat.AUTOEQUIP:
                equipment.equip(user)
            retval = self.engine.dat.STATE_PLAYING
        return retval

    def drop(self, user):
        self.objects[self.engine.dungeon_levelname].append(self.owner)
        user.fighter.remove_item(self.owner)
        self.owner.x = user.x
        self.owner.y = user.y
        self.owner.dungeon_level = self.dat.maplist.index(self.engine.dungeon_levelname)
        self.owner.send_to_back()
        if user is self.player:
            self.engine.message('You dropped a ' + self.owner.name + '.', self.col.YELLOW)
        if self.owner.equipment:
            self.owner.equipment.dequip(user)


class Equipment(object):

    def __init__(self, engine, slot, power_bonus=0, defense_bonus=0, max_hp_bonus=0, speed_bonus=0, regen_bonus=0):
        self.engine = engine
        self.slot = slot
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        self.max_hp_bonus = max_hp_bonus
        self.is_equipped = False
        self.speed_bonus = speed_bonus
        self.regen_bonus = regen_bonus

    def toggle_equip(self, user): #toggle equip/dequip status
        if self.is_equipped:
            self.dequip(user)
        else:
            self.equip(user)

    def equip(self, user):
        old_equipment = self.engine.get_equipped_in_slot(self.slot, user)
        if old_equipment is not None:
            old_equipment.dequip(user)
        self.is_equipped = True
        if self.engine.isplayer(user):
            name = 'You '
        else:
            name = user.name
        self.engine.message(name + ' equipped ' + self.owner.name + ' on ' + self.slot + '.', self.engine.col.LIGHT_GREEN, self.engine.isplayer(user))

    def dequip(self, user):
        if not self.is_equipped: return
        self.is_equipped = False
        if self.engine.isplayer(user):
            name = 'You '
        else:
            name = user.name
        self.engine.message(name + ' unequipped ' + self.owner.name + ' from ' + self.slot + '.', self.engine.col.LIGHT_GREEN)


class ConfusedMonster(object):

    def __init__(self, engine, old_ai, num_turns=None):
        self.engine = engine
        self.old_ai = old_ai
        self.num_turns = num_turns
        if self.num_turns is None:
            self.num_turns = self.engine.dat.CONFUSE_NUM_TURNS

    def take_turn(self):
        if self.num_turns > 0: #still confused
            self.owner.move(random_int(0, -1, 1), random_int(0, -1, 1))
            self.num_turns -= 1
            self.engine.message(self.owner.name + ' is STILL confused!', self.col.RED)
        else:
            self.owner.ai = self.old_ai
            self.engine.message(self.owner.name + ' is no longer confused', self.col.GREEN)
        if self.owner.fighter:
            return True
        else:
            return False


class BasicMonster(object):

    def __init__(self, engine):
        self.engine = engine

    def take_turn(self):
        useditem = None
        fight = True
        pickup = True
        monster = self.owner.owner
        nearest_nonclan = self.engine.closest_nonclan(self.engine.dat.TORCH_RADIUS, monster)
        nearest_item    = self.engine.closest_item(self.engine.dat.TORCH_RADIUS, monster)
        if nearest_nonclan is None:
            fight = False
        if nearest_item is None:
            pickup = False
        if fight and pickup:
            if monster.distance_to(nearest_nonclan) <= monster.distance_to(nearest_item):
                pickup = False
            else:
                fight = False
        if fight:
            if self.engine.fovx.map_is_in_fov(monster.fighter.fov, nearest_nonclan.x, nearest_nonclan.y): #nearest_nonclan ensures same level
                if monster.fighter.inventory:
                    index = random_int(0, 0, len(monster.fighter.inventory)-1)
                    item = monster.fighter.inventory[index].item
                    if not item.owner.equipment:
                        useditem = item.use(user=monster)
                if useditem is not self.engine.dat.STATE_USED:
                    if monster.distance_to(nearest_nonclan) >= 2:
                        monster.move_towards(nearest_nonclan)
                    elif nearest_nonclan.fighter.hp > 0:
                        monster.fighter.attack(nearest_nonclan)
        elif pickup:
            if nearest_item.x == monster.x and nearest_item.y == monster.y and nearest_item.item and nearest_item.dungeon_level == monster.dungeon_level:
                nearest_item.item.pick_up(monster)
            else:
                monster.move_towards(nearest_item)
                if nearest_item.x == monster.x and nearest_item.y == monster.y and nearest_item.item and nearest_item.dungeon_level == monster.dungeon_level:
                    nearest_item.item.pick_up(monster)
        else:
            monster.move_random()
        if monster.fighter.alive:
            return True
        else:
            return False


class EntityData(object):

    def __init__(self, engine):
        self.mobs = {
         'johnstein':      {'char':'j', 'color':engine.col.LIGHT_GREY,  'tilechar':engine.dat.TILE_SKEL_WHITE,   'fighter':{'hp':100 , 'defense':0 , 'power':20 , 'xp':0, 'xpvalue':20 , 'clan':'monster', 'death_function':engine.monster_death, 'speed':5}, 'caster':{'mp':10}},
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
        logger.error('error in func {}: wrong mode: {}', func, self.engine.fov_mode)


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


class Tile(object):

    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked
        self.explored = False
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight


class MenuOption(object):

    def __init__(self, text, color=None, char=None):
        self.text = text
        self.color = color
        self.char = char


class WindowProxy(object):
    last_seq = 0

    @classmethod
    def next_seq(cls):
        seq = cls.last_seq = cls.last_seq + 1
        return seq

    def __new__(cls, *args, **kwargs):
        instance = super(WindowProxy, cls).__new__(cls, *args, **kwargs)
        instance.seq = cls.next_seq()
        return instance

    def __init__(self, con, size):
        self.con = con
        self.size = size

    def __getattribute__(self, key):
        sup = super(WindowProxy, self).__getattribute__
        try:
            return sup(key)
        except AttributeError:
            exc_info = sys.exc_info()
            try:
                return getattr(sup('con'), key)
            except AttributeError:
                raise exc_info[0], exc_info[1], exc_info[2]

    def __str__(self):
        return '<Window #{}: {}x{}>'.format(self.seq, *self.size)

    __repr__ = __str__


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

    def fatal_error(self, message):
        raise RuntimeError(message)

    def isgameover(self):
        if self.engine.game_mode == 'tcod':
            return tcod.console_is_window_closed()
        elif self.engine.game_mode == 'curses':
            return False
        else:
            self.err_graphicsmode('isgameover')

    ## curses helper functions, not applicable to sdl backend

    def raise_window(self, win):
        pos = self.window_stack.index(win)
        self.window_stack.append(self.window_stack.pop(pos))

    def refresh(self, ontop=None):
        if ontop is not None:
            self.raise_window(ontop)
        for win in self.window_stack:
            win.noutrefresh()
        curses.doupdate()

    def clearall(self):
        for win in self.window_stack:
            win.clear()
        self.refresh()

    def delwin(self, win):
        win.clear()
        while win in self.window_stack:
            self.window_stack.remove(win)
        self.refresh()

    def newwin(self, height, width, ypos, xpos, box=False):
        window = curses.newwin(height, width, ypos, xpos)
        if box:
            window.box()
        self.window_stack.append(window)
        return window

    def new_window(self, nwidth, nheight, xpos=0, ypos=0):
        logger.debug('asked to create a new window {}x{}', nwidth, nheight)
        if self.engine.game_mode == 'tcod':
            con = tcod.console_new(nwidth, nheight)
        elif self.engine.game_mode == 'curses':
            con = self.newwin(nheight, nwidth, ypos, xpos, box=True)
            con = WindowProxy(con, (nwidth, nheight))
            self.refresh()
        else:
            self.err_graphicsmode('console')
            con = None
        logger.debug('asked to create a new window {}x{} at {},{}, returning {!r}', nwidth, nheight, xpos, ypos, con)
        return con

    def clear(self, con):
        logger.debug('asked to clear the window: {!r}', con)
        if self.engine.game_mode == 'tcod':
            tcod.console_clear(con)
        elif self.engine.game_mode == 'curses':
            con.clear()
            self.refresh()
        else:
            self.err_graphicsmode('clear')

    def draw_rect(self, con, xx, yy, nwidth, nheight, clear, bkg=tcod.BKGND_SCREEN, bg_color=None):
        logger.debug('asked to draw a box. not implemented in curses')
        if self.engine.game_mode == 'tcod':
            if bg_color:
                tcod.console_set_default_background(con, bg_color)
            tcod.console_rect(con, xx, yy, nwidth, nheight, clear, bkg)
        elif self.engine.game_mode == 'curses':
            pass
        else:
            self.err_graphicsmode('draw_rect')

    def print_rect(self, con, xx, yy, nwidth, nheight, val, bkg=tcod.BKGND_NONE, align=tcod.LEFT):
        logger.debug('asked to print string {!r} at {},{} of window {!r}', val, xx, yy, con)
        if self.engine.game_mode == 'tcod':
            tcod.console_print_rect_ex(con, xx, yy, nwidth, nheight, bkg, align, val)
        elif self.engine.game_mode == 'curses':
            con.addstr(yy, xx, val)
            self.refresh()
        else:
            self.err_graphicsmode('print_rect')

    def print_str(self, con, xx, yy, val, bkg=tcod.BKGND_NONE, align=tcod.LEFT):
        logger.debug('asked to print string {!r} to window {!r} at {},{}', val, con, xx, yy)
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
        logger.debug('asked to print char {!r} to window {!r} at {},{} with fg={!r}, bg={!r}',
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
            return 1 #XXX
        else:
            self.err_graphicsmode('get_height_rect')

    def prep_keyboard(self, delay, interval): #can this be combined with prep_console?
        if self.engine.game_mode == 'tcod':
            tcod.console_set_keyboard_repeat(delay, interval)

    def prep_console(self, con, nwidth, nheight):
        logger.debug('prepping console {!r}', con)
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
                print('waiting for key')
                key = tcod.console_wait_for_keypress(True)
            else:
                tcod.sys_check_for_event(tcod.EVENT_KEY_PRESS | tcod.EVENT_MOUSE, key, mouse)
            event = KeypressEvent(key.vk, key.c, chr(key.c), key.pressed, key.lalt, key.lctrl, key.ralt, key.rctrl, key.shift)
        elif self.engine.game_mode == 'curses':
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
            self.refresh()
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
            names = [obj.name for obj in self.engine.objects[self.engine.dungeon_levelname]
                if obj.x == x and obj.y == y and self.engine.fovx.map_is_in_fov(self.player.fighter.fov, obj.x, obj.y)]
            names = ', '.join(names) #join names separated by commas
            return names.capitalize()
        elif self.engine.game_mode == 'curses':
            return ''
        else:
            self.err_graphicsmode('get_names_under_mouse')

    def err_graphicsmode(self, func):
        if self.engine.game_mode != 'dummy':
            self.fatal_error('Error in ' + func + '. wrong GRAPHICSMODE: ' + self.engine.game_mode)


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


class SQLStats(object):

    def __init__(self, engine, dbtype):
        self.engine = engine
        self.index_counter = 0
        self.dbtype = dbtype
        if self.dbtype == self.engine.dat.ENTITY_DB:
            script="""
            CREATE TABLE IF NOT EXISTS entity_stats (
                game_id INT,
                entity_id INT,
                name TEXT,
                tick INT,
                hp INT,
                hp_max INT,
                power INT,
                power_base INT,
                defense INT,
                defense_base INT,
                xp INT,
                xp_level INT,
                speed_counter INT,
                regen_counter INT,
                alive_or_dead INT,
                dungeon_level INT,
                dungeon_levelname TEXT,
                x INT,
                y INT
            );
            CREATE INDEX IF NOT EXISTS game_idx ON entity_stats(game_id);
            CREATE INDEX IF NOT EXISTS entity_idx ON entity_stats(entity_id);
            """
        elif self.dbtype == self.engine.dat.MESSAGE_DB:
            script="""
            CREATE TABLE IF NOT EXISTS game_log (
                game_id INT,
                msg_id INT,
                name TEXT,
                tick INT,
                dungeon_levelname TEXT
            );
            CREATE INDEX IF NOT EXISTS game_idx ON game_log(game_id);
            CREATE INDEX IF NOT EXISTS msg_idx ON game_log(msg_id);
            """
        self.DB_FILE = self.dbtype  + '.db'
        self.conn = sql.connect(self.DB_FILE)
        self.cursor = self.conn.cursor()
        self.cursor.executescript(script)
        self.game_id = self.cursor.execute("SELECT IFNULL(MAX(game_id), 0) + 1 FROM " + self.dbtype).fetchone()[0]

    def log_entity(self, thing):
        if self.dbtype == self.engine.dat.ENTITY_DB:
            entity = thing
            if not hasattr(thing, 'entity_id'):
                self.index_counter += 1
                entity.entity_id = self.index_counter
        if self.dbtype == self.engine.dat.MESSAGE_DB:
            message = thing
            entity = thing
            if not hasattr(thing, 'msg_id'):
                self.index_counter += 1
                msg_id = self.index_counter
        if self.dbtype == self.engine.dat.ENTITY_DB:
            the_data = {
                "game_id": self.game_id,
                "entity_id": entity.entity_id,
                "name": entity.name,
                "tick": self.engine.tick,
                "hp": entity.fighter.hp,
                "hp_max": entity.fighter.max_hp(),
                "power": entity.fighter.power(),
                "power_base": entity.fighter.base_power,
                "defense": entity.fighter.defense(),
                "defense_base": entity.fighter.base_defense,
                "xp": entity.fighter.xp,
                "xp_level": entity.fighter.xplevel,
                "speed_counter": entity.fighter.speed_counter,
                "regen_counter": entity.fighter.regen_counter,
                "alive_or_dead": int(entity.fighter.alive),
                "dungeon_level": entity.dungeon_level,
                "dungeon_levelname": self.engine.dat.maplist[entity.dungeon_level],
                "x": entity.x,
                "y": entity.y
            }
        elif self.dbtype == self.engine.dat.MESSAGE_DB:
            the_data = {
                "game_id": self.game_id,
                "msg_id": msg_id,
                "name": message,
                "tick": self.engine.tick,
                "dungeon_levelname": self.engine.dungeon_levelname
            }
        dict_insert(self.cursor, self.dbtype, the_data)

    def log_event(self):
        pass

    def log_flush(self, force_flush=False):
        if self.engine.sql_commit_counter <= 0 or force_flush:
            self.conn.commit()
            if self.engine.sql_commit_counter <= 0:
                self.engine.sql_commit_counter = self.engine.dat.SQL_COMMIT_TICK_COUNT

    def export_csv(self):
        p = Popen("export_sql2csv.bat " + self.dbtype + ' ' + self.DB_FILE )
        p.communicate()


class Platform:
    WINDOWS = 'win32'
    OSX = 'darwin'
    LINUX = 'linux'
    OTHER = sys.platform


def reraise(exc_type, exc_value, exc_traceback):
    raise exc_type, exc_value, exc_traceback


def dict_insert(cursor, table, data):
    return # XXX what is going on here
    query = "INSERT INTO " + table + "(" + ", ".join(keys()) + ") VALUES (:" + ", :".join(keys()) + ")"
    try:
        return cursor.execute(query, data)
    except:
        logger.exception('query failure with query: {}', query)
        return None


def from_dungeon_level(table, dungeon_level):
    for (value, level) in reversed(table):
        if dungeon_level >= level:
            return value
    return 0


def flip_coin(rndgen=False):
    if not rndgen:
        rndgen = 0
    return (random_int(rndgen,0,1))


def random_choice(chances_dict):
    chances = chances_dict.values()
    strings = chances_dict.keys()
    return strings[random_choice_index(chances)]


def random_int(seed, min, max):
    return tcod.random_get_int(seed, min, max)


def random_choice_index(chances): #choose one option from list of chances. return index
    dice = random_int(0, 1, sum(chances))
    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w
        if dice <= running_sum:
            return choice
        choice +=1


def roll_dice(dicelist):
    dice=[]
    for [die_low, die_high] in dicelist:
        roll = random_int(0,die_low,die_high)
        dice.append(roll)
    return [sum(dice), dice]


def get_distance(dx, dy):
    return math.sqrt(dx ** 2 + dy ** 2)


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


class GameEngine(object):

    def __init__(self, game_mode, fov_mode, ascii_mode):
        self.game_msgs = []
        self.msg_history = []
        self.game_mode = game_mode
        self.fov_mode = fov_mode
        self.ascii_mode = ascii_mode
        self.stdscr = None

    @property
    def winsz(self):
        if self.stdscr is None:
            return 80, 25
        y, x = self.stdscr.getmaxyx()
        return x, y

    def _handle_window_resize(self, sig, frame):
        logger.warn('SIGWINCH event received')
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
                            logger.warn('new window size is {}x{}', w, h)

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
        self.keymap = KeyMap(self)
        self.col = Colors(self)
        self.col.init_colors()
        self.gui = GUI(self)
        self.fovx = FOV(self)
        self.dat = GameData(self)
        self.ent = EntityData(self)
        self.con = self.gui.new_window(self.dat.MAP_WIDTH, self.dat.MAP_HEIGHT)
        logger.debug('created base console: {!r}', self.con)
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
                    logger.exception('error saving game', exc_info=sys.exc_info())
                    self.msgbox(self.rootcon, 'Bye!', 24)
                break

    def next_level(self):
        self.message('You head down the stairs', self.col.RED)
        self.player.dungeon_level +=1
        self.dungeon_levelname = self.dat.maplist[self.player.dungeon_level]
        if not self.dungeon_levelname in self.map:
            self.make_map(self.player.dungeon_level, self.dungeon_levelname) #create fresh new level
        self.player.x = self.upstairs[self.dungeon_levelname].x
        self.player.y = self.upstairs[self.dungeon_levelname].y
        self.map[self.dungeon_levelname].initialize_fov()

    def prev_level(self):
        self.message('You head up the stairs', self.col.RED)
        self.player.dungeon_level -=1
        self.dungeon_levelname = self.dat.maplist[self.player.dungeon_level]
        if self.player.dungeon_level <= 0: #leave dungeon
            self.message('You\'ve left the dungeon!', self.col.RED)
            self.player.dungeon_level =1 #workaround to prevent game from complaining.
            return self.dat.STATE_EXIT
        else:
            if not self.dungeon_levelname in self.map:
                self.make_map() #create fresh new level
            self.player.x = self.downstairs[self.dungeon_levelname].x
            self.player.y = self.downstairs[self.dungeon_levelname].y
            self.map[self.dungeon_levelname].initialize_fov()

    def make_dungeon(self):
        for index,level in enumerate(self.dat.maplist):
            if index > 0: #skip intro level
                logger.info('MAPGEN: {}, {}, creating level {}', self.tick, self.dungeon_levelname, level)
                self.player.dungeon_level = index
                self.dungeon_levelname = level
                self.make_map(index, level)
        self.player.dungeon_level = 1
        self.dungeon_levelname = self.dat.maplist[self.player.dungeon_level]
        self.player.x = self.upstairs[self.dungeon_levelname].x
        self.player.y = self.upstairs[self.dungeon_levelname].y
        self.map[self.dungeon_levelname].initialize_fov()

    def make_map(self, levelnum, levelname):
        self.objects[self.dungeon_levelname] = [self.player]
        logger.info('MAPGEN: {}, {}, creating map: {}', self.tick, self.dungeon_levelname, self.dungeon_levelname)
        self.map[self.dungeon_levelname] = Maplevel(self.dat.MAP_HEIGHT, self.dat.MAP_WIDTH, levelnum, levelname, self.fovx)
        rooms = []
        num_rooms = 0
        for r in range(self.dat.MAX_ROOMS):
            w = random_int(0, self.dat.ROOM_MIN_SIZE, self.dat.ROOM_MAX_SIZE)
            h = random_int(0, self.dat.ROOM_MIN_SIZE, self.dat.ROOM_MAX_SIZE)
            x = random_int(0, self.dat.MAP_PAD_W, self.dat.MAP_WIDTH - w - self.dat.MAP_PAD_W)
            y = random_int(0, self.dat.MAP_PAD_H, self.dat.MAP_HEIGHT - h - self.dat.MAP_PAD_H)
            new_room = Rect(x, y, w, h)
            failed = False
            for other_room in rooms:
                if new_room.intersect(other_room):
                    failed = True
                    break
            if not failed:
                self.map[self.dungeon_levelname].create_room(new_room)
                (new_x, new_y) = new_room.center()
                self.place_objects(new_room)
                if num_rooms == 0:
                    self.player.x = new_x
                    self.player.y = new_y
                    self.upstairs[self.dungeon_levelname] = Thing(self, new_x, new_y, '<', 'upstairs', self.col.WHITE, always_visible = True)
                    self.objects[self.dungeon_levelname].append(self.upstairs[self.dungeon_levelname])
                    self.upstairs[self.dungeon_levelname].send_to_back() #so it's drawn below the monsters
                else:
                    (prev_x, prev_y) = rooms[num_rooms -1].center()
                    if flip_coin() == 1:
                        self.map[self.dungeon_levelname].create_h_tunnel(prev_x, new_x, prev_y)
                        self.map[self.dungeon_levelname].create_v_tunnel(prev_y, new_y, new_x)
                    else:
                        self.map[self.dungeon_levelname].create_v_tunnel(prev_y, new_y, prev_x)
                        self.map[self.dungeon_levelname].create_h_tunnel(prev_x, new_x, new_y)
                rooms.append(new_room)
                num_rooms +=1
        self.downstairs[self.dungeon_levelname] = Thing(self, new_x, new_y, '>', 'downstairs', self.col.WHITE, always_visible = True)
        self.objects[self.dungeon_levelname].append(self.downstairs[self.dungeon_levelname])
        self.downstairs[self.dungeon_levelname].send_to_back() #so it's drawn below the monsters
        self.map[self.dungeon_levelname].initialize_fov()

    def place_objects(self, room):
        nextid = 1
        max_monsters = from_dungeon_level([[10, 1], [40, 3], [50, 6], [70, 10]], self.dat.maplist.index(self.dungeon_levelname))
        num_monsters = random_int(0, 0, max_monsters)
        monster_chances = self.get_monster_chances()
        max_items = from_dungeon_level([[10, 1], [2, 4]], self.dat.maplist.index(self.dungeon_levelname))
        num_items = random_int(0, 0, max_items)
        item_chances = self.get_item_chances()
        for i in range(num_monsters):
            x =  random_int(0, room.x1 + 1, room.x2 - 1)
            y =  random_int(0, room.y1 + 1, room.y2 - 1)
            if not self.is_blocked(x, y):
                choice = random_choice(monster_chances)
                monster             = Thing(self, **self.ent.mobs[choice])
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
                logger.info('MAPGEN: {}, {}, made a monster {}', self.tick, self.dungeon_levelname, monster.name)
                if self.ent.mobitems[choice]:
                    for itemname in self.ent.mobitems[choice]:
                        item = Thing(self, **self.ent.items[itemname])
                        monster.fighter.add_item(item)
                monster.set_location(x, y)
                self.objects[self.dungeon_levelname].append(monster)
        for i in range(num_items):
            x = random_int(0, room.x1 + 1, room.x2 - 1)
            y = random_int(0, room.y1 + 1, room.y2 - 1)
            if not self.is_blocked(x, y):
                choice = random_choice(item_chances)
                item = Thing(self, **self.ent.items[choice])
                item.always_visible = True
                item.set_location(x, y)
                item.dungeon_level = self.dat.maplist.index(self.dungeon_levelname)
                self.objects[self.dungeon_levelname].append(item)
                item.send_to_back() #items appear below other objects

    def get_monster_chances(self):
        monster_chances = {}
        for mobname in self.ent.mobchances:
            monster_chances[mobname] = from_dungeon_level(self.ent.mobchances[mobname], self.dat.maplist.index(self.dungeon_levelname))
        return monster_chances

    def get_item_chances(self):
        item_chances = {}
        for itemname in self.ent.itemchances:
            item_chances[itemname] = from_dungeon_level(self.ent.itemchances[itemname], self.dat.maplist.index(self.dungeon_levelname))
        return item_chances

    def mapname(self):
        return(self.dat.maplist[self.player.dungeon_level])

    def message(self, new_msg, color = None, displaymsg=True):
        if color is None:
            color = self.col.WHITE
        if self.dat.PRINT_MESSAGES:
            if self.dat.FREE_FOR_ALL_MODE:
                self.message_db.log_entity(new_msg)
            logger.info('MSG: {}, {}, {}', self.tick, self.dungeon_levelname, new_msg)
        if displaymsg:
            turn = self.player.game_turns
            new_msg_lines = textwrap.wrap(new_msg, self.dat.MSG_WIDTH)
            for line in new_msg_lines:
                if len(self.game_msgs) == self.dat.MSG_HEIGHT:
                    del self.game_msgs[0]
                self.msg_history.append(MenuOption(str(turn) + ' : ' + line, color=color))
                self.game_msgs.append((line, color))

    def menu(self, rootcon, header, options, width, letterdelim=None):
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
        for obj in options:
            text = obj.text
            color = obj.color
            char = obj.char
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
        if not options:
            return
        goodchoice = False
        while not goodchoice:
            key = self.gui.getkey(self.con, self.mouse, self.key, wait=True)
            if key.pressed == False: continue
            index = key.charcode - ord('a')
            if index >= 0 and index < len(options):
                goodchoice = True
                retval = index
            elif key.keycode == self.keymap.ESC or key.keycode == self.keymap.SPACE:
                goodchoice = True
                retval = None
        if self.game_mode == 'curses':
            self.gui.delwin(window)
        self.gui.prep_keyboard(self.dat.KEYS_INITIAL_DELAY,self.dat.KEYS_INTERVAL)
        return retval

    def msgbox(self, rootcon, text, width=50):
        self.menu(rootcon, text, [], width)

    def inventory_menu(self, rootcon, header, user):
        if user.fighter:
            options = []
            if not len(user.fighter.inventory):
                obj = MenuOption('inventory is empty!', color=self.col.WHITE, char='?')
                options.append(obj)
            else:
                for item in user.fighter.inventory:
                    logger.debug('inventory item: {}', item)
                    text = item.name
                    if item.equipment and item.equipment.is_equipped:
                        text = text + ' (on ' + item.equipment.slot + ')'
                    obj = MenuOption(text, color=item.color, char=item.char)
                    options.append(obj)
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
            for object in self.objects[self.dungeon_levelname]:
                if object != self.player:
                    object.draw()
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
        for object in self.objects[self.dat.maplist[self.player.dungeon_level]]:
            if object.x == x and object.y == y and object.fighter:
                target = object
                break
        if target is not None:
            self.player.fighter.attack(target)
            self.player.game_turns +=1
            state = self.dat.STATE_PLAYING
        else:
            if self.player.move(dx, dy):
                self.player.game_turns +=1
                state = self.dat.STATE_PLAYING
                for object in self.objects[self.dat.maplist[self.player.dungeon_level]]: #look for items in the player's title
                    if object.x == self.player.x and object.y == self.player.y and object is not self.player:
                        self.message('* You see ' + object.name + ' at your feet *', self.col.YELLOW)
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
        buff_component = Buff('Super Strength', power_bonus=10)
        user.fighter.add_buff(buff_component)

    def use_blue_crystal(self, user):
        if user is self.player:
            self.message('You feel well-protected!', self.col.CYAN)
        else:
            self.message('The ' + user.name + ' looks well protected!', self.col.RED)
        buff_component = Buff('Super Defense', defense_bonus=10)
        user.fighter.add_buff(buff_component)

    def use_green_crystal(self, user):
        if user is self.player:
            self.message('You feel more resilient!', self.col.GREEN)
        else:
            self.message('The ' + user.name + ' feels more resilient!', self.col.RED)
        buff_component = Buff('Super Health', max_hp_bonus=50)
        user.fighter.add_buff(buff_component)
        user.fighter.hp = self.player.fighter.max_hp()

    def use_yellow_crystal(self, user):
        if user is self.player:
            self.message('You feel healthy!', self.col.YELLOW)
        else:
            self.message('The ' + user.name + ' looks healthier!', self.col.RED)
        buff_component = Buff('Super Regen', regen_bonus=-20)
        user.fighter.add_buff(buff_component)

    def use_orange_crystal(self, user):
        if user is self.player:
            self.message('You feel speedy!', self.col.CYAN)
        else:
            self.message('The ' + user.name + ' looks speedy!', self.col.CYAN)
        buff_component = Buff('Super Speed', speed_bonus=-3)
        user.fighter.add_buff(buff_component)

    def cast_confusion(self, user):
        target = None
        target = self.closest_nonclan(self.dat.TORCH_RADIUS, user)
        if user is self.player:
            self.message('Left-click an enemy to confuse. Right-click or ESC to cancel', self.col.LIGHT_CYAN)
            target = target_monster(self, self.dat.CONFUSE_RANGE)
            name = 'You'
        elif not target is None:
            target = self.closest_nonclan(self.dat.TORCH_RADIUS, user)
            name = user.name
        else:
            if user is self.player:
                self.message('Cancelling confuse', self.col.RED, False)
            else:
                self.message(user.name + ' cancels Confuse', self.col.RED, False)
            return self.dat.STATE_CANCELLED
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
            (x,y) = target_tile(self)
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
            theDmg = roll_dice([[self.dat.FIREBALL_DAMAGE/2, self.dat.FIREBALL_DAMAGE*2]])[0]
            fov_map_fireball = self.map[self.dungeon_levelname].fov_map
            self.fovx.map_compute_fov(fov_map_fireball, x, y, self.dat.FIREBALL_RADIUS, self.dat.FOV_LIGHT_WALLS, self.dat.FOV_ALGO)
            for obj in self.objects[self.dungeon_levelname]: #damage all fighters within range
                if self.fovx.map_is_in_fov(fov_map_fireball, obj.x, obj.y) and obj.fighter:
                    self.message('The fireball explodes', self.col.RED)
                    self.message(obj.name + ' is burned for '+ str(theDmg) + ' HP', self.col.RED)
                    obj.fighter.take_damage(user, theDmg)

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
            theDmg = roll_dice([[self.dat.LIGHTNING_DAMAGE/2, self.dat.LIGHTNING_DAMAGE]])[0]
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
            self.message(name + ' killed ' + monster.name + ' and gains ' + str(monster.fighter.xpvalue) + 'XP', self.col.YELLOW, self.engine.isplayer(killer))
            for equip in monster.fighter.inventory:
                equip.item.drop(self, monster)
            monster.char = '%'
            monster.color = self.col.MAGENTA
            monster.blocks = False
            monster.ai = None
            monster.always_visible = True
            monster.fighter.alive = False

    def get_equipped_in_slot(self, slot, user): #returns the equipment in a slot, or None if it's empty
        if user.fighter.inventory:
            for obj in user.fighter.inventory:
                if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
                    return obj.equipment
        return None

    def get_all_equipped(self, user): #returns list of equipped items
        equipped_list = []
        if user.fighter.inventory:
            for item in user.fighter.inventory:
                if item.equipment and item.equipment.is_equipped:
                    equipped_list.append(item.equipment)
            return equipped_list
        return [] #other self.objects[self.dungeon_levelname] have no equipment

    def target_monster(self, max_range = None):
        while True:
            (x, y) = target_tile(self, max_range)
            if x is None: #player cancelled
                return None
            for obj in self.objects[self.dungeon_levelname]:
                if obj.x == x and obj.y == y and obj.fighter and obj != self.player and obj.dungeon_level == self.player.dungeon_level:
                    return obj

    def closest_monster(self, max_range):
        closest_enemy = None
        closest_dist = max_range + 1 #start with slightly higher than max range
        for object in self.objects[self.dungeon_levelname]:
            if object.fighter and not object == self.player and self.fovx.map_is_in_fov(self.player.fighter.fov, object.x, object.y):
                dist = self.player.distance_to(object)
                if dist < closest_dist:
                    closest_enemy = object
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
        for object in self.objects[self.dungeon_levelname]:
            if object.item and self.fovx.map_is_in_fov(fov_map_dude, object.x, object.y) and object.dungeon_level == dude.dungeon_level:
                dist = dude.distance_to(object)
                if dist < closest_dist:
                    closest_item = object
                    closest_dist = dist
        return closest_item

    def closest_nonclan(self, max_range, dude):
        closest_nonclan = None
        closest_dist = max_range + 1 #start with slightly higher than max range
        if dude.fighter.fov is None:
            fov_map_dude = dude.fighter.set_fov(self)
        fov_map_dude = dude.fighter.recompute_fov()
        for object in self.objects[self.dungeon_levelname]:
            if object.fighter and  object.fighter.clan != dude.fighter.clan and self.fovx.map_is_in_fov(fov_map_dude, object.x, object.y) and object.dungeon_level == dude.dungeon_level and object.fighter.alive:
                dist = dude.distance_to(object)
                if dist < closest_dist:
                    closest_nonclan = object
                    closest_dist = dist
        return closest_nonclan

    def get_next_fighter(self):
        for index,level in enumerate(self.dat.maplist):
            if index > 0:
                for object in self.objects[self.dat.maplist[index]]:
                    if object.fighter:
                        return object

    def target_tile(self, max_range = None):
        while True:
            self.gui.flush()
            thekey = self.gui.getkey(self.con, self.mouse, self.key)
            self.render_all()
            (x, y) = (self.mouse.cx, self.mouse.cy)
            (x, y) = (self.engine.camera_x + x, self.engine.camera_y + y) #from screen to map coords
            if (self.mouse.lbutton_pressed and self.fovx.map_is_in_fov(self.player.fighter.fov, x, y) and (max_range is None or self.player.distance(x,y) <= max_range)):
                return (x, y)
            if self.mouse.rbutton_pressed or self.key.vk == ESC:
                return (None, None)

    def is_blocked(self, x, y):
        if self.map[self.dungeon_levelname].blocked(x,y):
            return True
        for object in self.objects[self.dungeon_levelname]:
            if object.blocks and object.x == x and object.y == y:
                return True
        return False

    def total_alive_entities(self):
        return [obj for obj in self.objects[self.dungeon_levelname]
                if obj.fighter and obj.fighter.hp > 0]

    def printstats(self, entity):
        self.message(entity.name, self.col.WHITE)
        self.message('Level =' + str(entity.fighter.xplevel), self.col.WHITE)
        self.message('XP =' + str(entity.fighter.xp), self.col.WHITE)
        self.message('HP =' + str(entity.fighter.hp) + '/' + str(entity.fighter.max_hp()), self.col.WHITE)
        self.message('power =' + str(entity.fighter.power(self)) + '/' + str(entity.fighter.base_power), self.col.WHITE)
        self.message('defense =' + str(entity.fighter.defense(self)) + '/' + str(entity.fighter.base_defense), self.col.WHITE)

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
                            MenuOption('Strength (+2 attack, from ' + str(self.player.fighter.power(self)) + ')', color=self.col.RED),
                            MenuOption('Defense (+2 defense, from ' + str(self.player.fighter.defense(self)) + ')', color=self.col.BLUE)], self.dat.LEVEL_SCREEN_WIDTH, letterdelim=')')
                else:
                    choice = random_int(0, 0, 2) #TODO: variablize this
                if choice == 0:
                    user.fighter.base_max_hp += 25
                elif choice == 1:
                    user.fighter.base_power += 2
                elif choice == 2:
                    user.fighter.base_defense += 2
                user.fighter.hp = user.fighter.max_hp()

    def handle_keys(self):
        thekey = self.gui.getkey(self.con, self.mouse, self.key)
        if thekey.keycode == self.keymap.ENTER and thekey.lalt:
            self.gui.toggle_fullscreen()
        elif thekey.keycode == self.keymap.ESC:
            return self.dat.STATE_EXIT #exit game
        if self.game_state == self.dat.STATE_PLAYING:
            if thekey.keycode == self.keymap.KPDEC or thekey.keycode == self.keymap.KP5:
                player_resting(self)
                self.fov_recompute = True
                pass
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
                    for object in self.objects[self.dat.maplist[self.player.dungeon_level]]: #look for items in the player's title on the same floor of the player
                        if object.x == self.player.x and object.y == self.player.y and object.item:
                            self.player.game_turns += 1
                            return object.item.pick_up(self.player)
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
                    level_up_xp = self.dat.LEVEL_UP_BASE + self.player.xplevel * self.dat.LEVEL_UP_FACTOR
                    self.msgbox(self.rootcon, 'Character Information\n\nLevel: ' + str(self.player.xplevel) + '\nExperience: ' + str(self.player.fighter.xp) +
                        '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(self.player.fighter.max_hp()) +
                        '\nAttack: ' + str(self.player.fighter.power()) + '\nDefense: ' + str(self.player.fighter.defense(self)), self.dat.CHARACTER_SCREEN_WIDTH)
                if thekey.keychar == 'x':
                    self.msgbox(self.rootcon, 'You start to meditate!', self.dat.CHARACTER_SCREEN_WIDTH)
                    level_up_xp = self.dat.LEVEL_UP_BASE + self.player.xplevel * self.dat.LEVEL_UP_FACTOR
                    self.player.fighter.xp = level_up_xp
                    self.check_level_up()
                    self.player.game_turns += 1
                if thekey.keychar == 'a':
                    self.msgbox(self.rootcon, 'You can smell them all!', self.dat.CHARACTER_SCREEN_WIDTH)
                    self.set_objects_visible()
                if thekey.keychar == 'q':
                    self.msgbox(self.rootcon, 'You feel your inner dwarf admiring the dungeon walls!', self.dat.CHARACTER_SCREEN_WIDTH)
                    self.map[self.dungeon_levelname].set_map_explored()
                    self.fov_recompute = True
                if thekey.keychar == 'z':
                    self.msgbox(self.rootcon, 'You start digging at your feet!', self.dat.CHARACTER_SCREEN_WIDTH)
                    map.next_level(self)
                if thekey.keychar == '>':
                    if self.downstairs[self.dat.maplist[self.player.dungeon_level]].x == self.player.x and self.downstairs[self.dat.maplist[self.player.dungeon_level]].y == self.player.y:
                        self.player.game_turns +=1
                        map.next_level(self)
                if thekey.keychar == '<':
                    if self.upstairs[self.dat.maplist[self.player.dungeon_level]].x == self.player.x and self.upstairs[self.dat.maplist[self.player.dungeon_level]].y == self.player.y:
                        self.player.game_turns +=1
                        map.prev_level(self)
                if thekey.keychar == 's': #general status key
                    self.msgbox(self.rootcon, 'You start digging above your head!', self.dat.CHARACTER_SCREEN_WIDTH)
                    map.prev_level(self)
                if thekey.keychar == 'p': #display log
                    width = self.dat.SCREEN_WIDTH
                    height = self.dat.SCREEN_HEIGHT
                    history = [[]]
                    count = 0
                    page = 1
                    numpages = int(float(len(self.msg_history))/self.dat.MAX_NUM_ITEMS + 1)
                    for thepage in range(numpages):
                        history.append([])
                    for obj in reversed(self.msg_history):
                        line = obj.text
                        color = obj.color
                        history[page].append(MenuOption(line, color = color))
                        count += 1
                        if count >= self.dat.MAX_NUM_ITEMS:
                            page +=1
                            count = 0
                    for thepage in range(numpages):
                        window = self.gui.new_window(width, height)
                        self.gui.print_rect(window, 0, 0, width, height, '')
                        self.gui.con_blit(window, 0, 0, width, height, 0, 0, 0, 1.0, 1)
                        menu(self.rootcon, 'Message Log: (Sorted by Most Recent Turn) Page ' + str(thepage+1) + '/' + str(numpages), history[thepage+1], self.dat.SCREEN_WIDTH, letterdelim=None)
                    self.fov_recompute = True
                if thekey.keychar == 'r':
                    logger.info('reloading game data')
                    reload(self.ent)
                    self.fov_recompute = True
                    self.gui.prep_keyboard(self.dat.KEYS_INITIAL_DELAY,self.dat.KEYS_INTERVAL)
                    buff_component = Buff('Super Strength', power_bonus=20)
                    self.player.fighter.add_buff(buff_component)
                    self.msgbox ('YOU ROAR WITH BERSERKER RAGE!', self.dat.CHARACTER_SCREEN_WIDTH)
                if thekey.keychar == 'w':
                    self.msgbox(self.rootcon, 'You fashion some items from the scraps at your feet', self.dat.CHARACTER_SCREEN_WIDTH)
                    give_items(self)
                return self.dat.STATE_NOACTION

    def give_items(self):
        x = 0
        y = 0
        for item in self.ent.items:
            theitem = Thing(self, **self.ent.items[item])
            theitem.always_visible = True
            self.player.fighter.add_item(theitem)

    def set_objects_visible(self):
        for object in self.objects[self.dat.maplist[self.player.dungeon_level]]:
            object.always_visible = True

    def save_final_sql_csv(self):
        if self.dat.FREE_FOR_ALL_MODE:
            for obj in self.objects[self.dungeon_levelname]:
                if obj.fighter:
                    self.entity_db.log_entity(obj)
            self.entity_db.log_flush(force_flush=True)
            self.message_db.log_flush(force_flush=True)
            self.entity_db.export_csv()
            self.message_db.export_csv()

    def save_game(self, filename='savegame'):
        logger.info('game saved')
        file = shelve.open(filename, 'n')
        file['map'] = self.map
        file['objects'] = self.objects[self.dungeon_levelname]
        file['player_index'] = self.objects[self.dungeon_levelname].index(self.player) #index of player in the objects list
        file['game_msgs'] = self.game_msgs
        file['msg_history'] = self.msg_history
        file['game_state'] = self.game_state
        file['stairs_index'] = self.objects[self.dungeon_levelname].index(self.stairs)
        file['dungeon_level'] = self.player.dungeon_level
        file.close()

    def load_game(self, filename='savegame'):
        file = shelve.open(filename, 'r')
        self.map = file['map']
        self.objects[self.dungeon_levelname] = file['objects']
        self.player = self.objects[self.dungeon_levelname][file['player_index']]  #get index of player in the objects list
        self.game_msgs = file['game_msgs']
        self.msg_history = file['msg_history']
        self.game_state = file['game_state']
        self.stairs = self.objects[self.dungeon_levelname][file['stairs_index']]
        self.player.dungeon_level = file['dungeon_level']
        file.close()
        self.map[self.dungeon_levelname].initialize_fov()

    def new_game(self):
        fighter_component = Fighter(self, hp=300, defense=10, power=20, xp=0, xpvalue=0, clan='monster', death_function=self.player_death, speed = 10)
        self.player = Thing(self, self.dat.SCREEN_WIDTH/2, self.dat.SCREEN_HEIGHT/2, '@', 'Roguetato', self.col.WHITE, tilechar=self.dat.TILE_MAGE, blocks=True, fighter=fighter_component)
        self.player.dungeon_level = 1
        self.game_state = self.dat.STATE_PLAYING
        self.player.game_turns = 0
        self.dungeon_levelname = self.dat.maplist[self.player.dungeon_level]
        self.map = {}
        self.objects = {}
        self.upstairs = {}
        self.downstairs = {}
        self.tick = 0
        if self.dat.FREE_FOR_ALL_MODE: #turn on SQL junk and kill player.
            self.entity_db = SQLStats(self, self.dat.ENTITY_DB)
            self.message_db = SQLStats(self, self.dat.MESSAGE_DB)
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
            obj = Thing(self, 0, 0, '-', 'wristguards of the whale', self.col.LIGHT_RED, equipment=equipment_component)
            obj.always_visible = True
            self.player.fighter.add_item(obj)
            equipment_component.equip(self.player)
            self.player.fighter.hp = self.player.fighter.max_hp()
        self.message('Welcome to MeFightRogues! Good Luck! Don\'t suck!', self.col.BLUE)
        self.gui.prep_keyboard(self.dat.KEYS_INITIAL_DELAY,self.dat.KEYS_INTERVAL)

    def play_game(self):
        self.player_action = None
        (self.camera_x, self.camera_y) = (0, 0)
        if self.dat.AUTOMODE:
            self.set_objects_visible()
            self.map[self.dungeon_levelname].set_map_explored()
            battleover = False
            self.fov_recompute = True
        while not self.gui.isgameover():
            if not self.player.fighter.alive: #this is sorta dumb and probably needs fixed.
                self.player.fighter.death_function(self.player, None)
            self.render_all() #TODO: probably need to do some surgery in gamestuff.render_all()
            if 0:
                for object in self.objects[self.dat.maplist[self.player.dungeon_level]]:
                    object.clear(self)
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
                    if index > 0: #skip intro level
                        for obj in self.objects[self.dungeon_levelname]:
                            if obj.fighter:
                                if obj.fighter.speed_counter <= 0 and obj.fighter.alive: #only allow a turn if the counter = 0.
                                    if obj.ai:
                                        if obj.ai.take_turn(): #only reset speed_counter if monster is still alive
                                            obj.fighter.speed_counter = obj.fighter.speed()
                                if obj.fighter.alive:
                                    if obj.fighter.regen_counter <= 0: #only regen if the counter = 0.
                                        obj.fighter.hp += int(obj.fighter.max_hp() * self.dat.REGEN_MULTIPLIER)
                                        obj.fighter.regen_counter = obj.fighter.regen(self)
                                    obj.fighter.regen_counter -= 1
                                    obj.fighter.speed_counter -= 1
                                    if obj.fighter.buffs:
                                        for buff in obj.fighter.buffs:
                                            buff.duration -= buff.decay_rate
                                            if buff.duration <= 0:
                                                self.message(obj.name + ' feels the effects of ' + buff.name + ' wear off!', self.col.LIGHT_RED)
                                                obj.fighter.remove_buff(buff)
                                    if obj.fighter.hp > obj.fighter.max_hp():
                                            obj.fighter.hp = obj.fighter.max_hp()
                                    self.check_level_up(obj)
                                if self.dat.FREE_FOR_ALL_MODE:
                                    self.entity_db.log_entity(obj)
                            elif obj.ai:
                                obj.ai.take_turn()
                if self.dat.FREE_FOR_ALL_MODE:
                    self.entity_db.log_flush()
                    self.message_db.log_flush()
                    self.sql_commit_counter -= 1
                if self.dat.AUTOMODE:
                    alive_entities = self.total_alive_entities()
                    if len(alive_entities) == 1:
                        message ('BATTLE ROYALE IS OVER! Winner is ', self.col.BLUE)
                        self.printstats(alive_entities[0])
                        self.dat.AUTOMODE = False
                        self.render_all()
                        chosen_item = self.inventory_menu(self.rootcon,'inventory for ' + alive_entities[0].name, alive_entities[0])
                        save_final_sql_csv(self)
                    if len(alive_entities) <=0:
                        message ('BATTLE ROYALE IS OVER! EVERYONE DIED! YOU ALL SUCK!', self.col.BLUE)
                        self.dat.AUTOMODE = False
                        save_final_sql_csv(self)
            self.dungeon_levelname = self.dat.maplist[self.player.dungeon_level]


def main(argv=None, engine=GameEngine):
    parser = argparse.ArgumentParser(
            formatter_class=argparse.HelpFormatter,
            description=__doc__,
            version=None,
            add_help=True,
            prog=None,
            )
    _ = parser.add_argument_group('game options').add_argument
    _('-m', '--game-mode', choices=BACKENDS, default=BACKENDS[0],
            help='select from available engine backends (default: %(default)s)')
    _('-f', '--fov-mode', choices=BACKENDS, default=BACKENDS[0],
            help='select from available fov backends (default: %(default)s)')
    _('-a', '--ascii-mode', default=False, action='store_true',
            help='use ascii mode for the tiles')
    _('-d', '--debug-file', metavar='FILE', action=AddLogFileAction, logger=logger,
            help='sets debug logging for %(metavar)s')
    try:
        opts = parser.parse_args(argv)
        if opts.game_mode == 'dummy':
            logger.add_stream(sys.stderr)
            logger.disabled = False
            logger.info('began logging for dummy mode')

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
    #sys.argv[1:] = ['-d', 'DEBUG.log', '-m', 'curses', '-a']
    sys.exit(main())
