
import math

from dungeoneer import rng, log


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
            log.exception('error in remove_item: {}/{}', self.owner.name, item.name)

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
            if self is self.engine.player:
                self.engine.message('You attack ' + target.name  + '!', self.engine.col.YELLOW)
            elif self.entity_sees(self.engine.player, self.owner):
                self.engine.message(self.owner.name.capitalize() + ' attacks ' + target.name, self.engine.col.YELLOW)
            elif self.entity_sees(self.engine.player, target):
                self.engine.message(target.name + ' has been attacked! ', self.engine.col.YELLOW)
            target.fighter.take_damage(self.owner, damage)
        else:
            if self is self.engine.player:
                self.engine.message('You tried to attack ' + target.name + ' but there is no effect.', self.engine.col.WHITE)

    def entity_sees(self, entity, target):
        return self.engine.fovx.map_is_in_fov(entity.fighter.fov, target.x, target.y) and entity.dungeon_level == target.dungeon_level


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
            if user is self.engine.player:
                self.engine.message('Your inventory is full! Cannot pick up ' + self.owner.name +'.', self.col.MAGENTA)
            retval = self.dat.STATE_NOACTION
        else:
            user.fighter.add_item(self.owner)
            self.engine.entities[self.engine.dungeon_levelname].remove(self.owner)
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
        self.engine.entities[self.engine.dungeon_levelname].append(self.owner)
        user.fighter.remove_item(self.owner)
        self.owner.x = user.x
        self.owner.y = user.y
        self.owner.dungeon_level = self.engine.dat.maplist.index(self.engine.dungeon_levelname)
        self.owner.send_to_back()
        if user is self.engine.player:
            self.engine.message('You dropped a ' + self.owner.name + '.', self.engine.col.YELLOW)
        if self.owner.equipment:
            self.owner.equipment.dequip(user)


class Entity(object):

    if 0:
        def __new__(cls, *args, **kwargs):
            instance = super(Entity, cls).__new__(cls, *args, **kwargs)
            instance._dungeon_level = None
            return instance

        @property
        def dungeon_level(self):
            if self is self.engine.player:
                print 'asked about level, returning', repr(self._dungeon_level)
            return self._dungeon_level

        @dungeon_level.setter
        def dungeon_level(self, lvl):
            if self is self.engine.player:
                print 'someone is setting level to', repr(lvl)
            self._dungeon_level = lvl

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
        self.move(rng.random_int(0, -1, 1), rng.random_int(0, -1, 1))

    def draw(self):
        if (self.engine.fovx.map_is_in_fov(self.engine.player.fighter.fov, self.x, self.y) or (self.always_visible and self.engine.map[self.engine.dungeon_levelname].explored(self.x, self.y))):
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
        self.engine.entities[self.engine.dungeon_levelname].remove(self)
        self.engine.entities[self.engine.dungeon_levelname].insert(0, self)


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
                    index = rng.random_int(0, 0, len(monster.fighter.inventory)-1)
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


class Ai(object):

    def __init__(self, ai):
        self.ai = ai
        self.ai.owner = self

    def take_turn(self):
        return self.ai.take_turn()


class Buff(object):

    def __init__(self, engine, name, power_bonus=0, defense_bonus=0, max_hp_bonus=0, speed_bonus=0, regen_bonus=0, decay_rate=None, duration=None):
        self.engine = engine
        self.name = name
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        self.max_hp_bonus = max_hp_bonus
        self.speed_bonus = speed_bonus
        self.regen_bonus = regen_bonus
        self.decay_rate = decay_rate #if 0, buff does not decay. use positive numbers to make buffs decrement
        if self.decay_rate is None:
            self.decay_rate = self.engine.dat.BUFF_DECAYRATE
        self.duration = duration
        if self.duration is None:
            self.duration = self.engine.dat.BUFF_DURATION


class ConfusedMonster(object):

    def __init__(self, engine, old_ai, num_turns=None):
        self.engine = engine
        self.old_ai = old_ai
        self.num_turns = num_turns
        if self.num_turns is None:
            self.num_turns = self.engine.dat.CONFUSE_NUM_TURNS

    def take_turn(self):
        if self.num_turns > 0: #still confused
            self.owner.move(rng.random_int(0, -1, 1), rng.random_int(0, -1, 1))
            self.num_turns -= 1
            self.engine.message(self.owner.name + ' is STILL confused!', self.engine.col.RED)
        else:
            self.owner.ai = self.old_ai
            self.engine.message(self.owner.name + ' is no longer confused', self.engine.col.GREEN)
        if self.owner.fighter:
            return True
        else:
            return False


def get_distance(dx, dy):
    return math.sqrt(dx ** 2 + dy ** 2)

