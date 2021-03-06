#standard imports
import libtcodpy as libtcod
from gamestuff import *
import data

#specific imports needed for this module
import entities
import entitydata


class Maplevel(object):
    def __init__(self, height, width, levelnum, levelname):
        self.levelnum = levelnum
        self.levelname = levelname
        self.height = height
        self.width = width

        self.map= [[ Tile(True)
            for y in range(self.height) ]
                for x in range(self.width) ]     

        self.fov_map = libtcod.map_new(self.width, self.height)
        self.fov_recompute = True

    #functions to create matp shapes and rooms
    def create_h_tunnel(self, x1, x2, y):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.map[x][y].blocked = False
            self.map[x][y].block_sight = False

    def create_v_tunnel(self, y1, y2, x):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.map[x][y].blocked = False
            self.map[x][y].block_sight = False

    def create_room(self, room):
        #go through tiles in rect to make them passable
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

    #map helper functions. create the fov map, go to next level, and lookup dungeon level percentages for objects
    def initialize_fov(self):
        self.fov_recompute = True

        for y in range(self.height):
            for x in range(self.width):
                libtcod.map_set_properties(self.fov_map, x, y, not self.block_sight(x, y), not self.blocked(x, y))


def next_level(Game):
    #advance to next level
    message('You head down the stairs', Game, libtcod.red)
    Game.player.dungeon_level +=1
    Game.dungeon_levelname = data.maplist[Game.player.dungeon_level]

    if not Game.dungeon_levelname in Game.map:
        make_map(Game, Game.player.dungeon_level, Game.dungeon_levelname) #create fresh new level

    Game.player.x = Game.upstairs[Game.dungeon_levelname].x
    Game.player.y = Game.upstairs[Game.dungeon_levelname].y
    Game.map[Game.dungeon_levelname].initialize_fov()

def prev_level(Game):
    #advance to next level
    message('You head up the stairs', Game, libtcod.red)
    Game.player.dungeon_level -=1
    Game.dungeon_levelname = data.maplist[Game.player.dungeon_level]

    if Game.player.dungeon_level <= 0: #leave dungeon      
        message('You\'ve left the dungeon!', Game, libtcod.red)
        Game.player.dungeon_level =1 #workaround to prevent game from complaining. 
        return data.STATE_EXIT
    else:
        #make_map(Game) #create fresh new level
        #assume map already made. bad long-term assumption
        if not Game.dungeon_levelname in Game.map:
            make_map(Game) #create fresh new level

        Game.player.x = Game.downstairs[Game.dungeon_levelname].x
        Game.player.y = Game.downstairs[Game.dungeon_levelname].y
        Game.map[Game.dungeon_levelname].initialize_fov()

def from_dungeon_level(table, dungeon_level):
        #returns a value that depends on level. table specifies what value occurs after each level. default = 0
        for (value, level) in reversed(table):
            if dungeon_level >= level:
                return value
        return 0

def make_dungeon(Game):
    for index,level in enumerate(data.maplist):
        if index > 0: #skip intro level
            print 'MAPGEN--\t ' + str(Game.tick) + '\t' + Game.dungeon_levelname + '\t' + ' creating level ' + level
            Game.player.dungeon_level = index
            Game.dungeon_levelname = level
            make_map(Game, index, level)

    Game.player.dungeon_level = 1
    Game.dungeon_levelname = data.maplist[Game.player.dungeon_level]

    Game.player.x = Game.upstairs[Game.dungeon_levelname].x
    Game.player.y = Game.upstairs[Game.dungeon_levelname].y
    Game.map[Game.dungeon_levelname].initialize_fov()

#Primary map generator and object placement routines.
def make_map(Game, levelnum, levelname):
    Game.objects[Game.dungeon_levelname] = [Game.player]
    #fill map with "blocked" tiles

    print 'MAPGEN--\t ' + str(Game.tick) + '\t' + Game.dungeon_levelname + '\t' + ' creating map:' + str(Game.dungeon_levelname)
    Game.map[Game.dungeon_levelname] = Maplevel(data.MAP_HEIGHT, data.MAP_WIDTH, levelnum, levelname)          

    rooms = []
    num_rooms = 0

    for r in range(data.MAX_ROOMS):
        #get random width/height
        w = libtcod.random_get_int(0, data.ROOM_MIN_SIZE, data.ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, data.ROOM_MIN_SIZE, data.ROOM_MAX_SIZE)
        #get random positions, but stay within map
        x = libtcod.random_get_int(0, data.MAP_PAD_W, data.MAP_WIDTH - w - data.MAP_PAD_W)
        y = libtcod.random_get_int(0, data.MAP_PAD_H, data.MAP_HEIGHT - h - data.MAP_PAD_H)

        new_room = Rect(x, y, w, h)

        #check for intersection with this room
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        if not failed:
            #no intersections

            Game.map[Game.dungeon_levelname].create_room(new_room)
            (new_x, new_y) = new_room.center()

            #add some contents to the room
            place_objects(new_room, Game)

            if num_rooms == 0:
                #first room. start player here
                Game.player.x = new_x
                Game.player.y = new_y
                #create upstairs at the center of the first room
                Game.upstairs[Game.dungeon_levelname] = entities.Object(new_x, new_y, '<', 'upstairs', libtcod.white, always_visible = True)
                Game.objects[Game.dungeon_levelname].append(Game.upstairs[Game.dungeon_levelname])
                Game.upstairs[Game.dungeon_levelname].send_to_back(Game) #so it's drawn below the monsters

            else:
                #for all other rooms, need to connect to previous room with a tunnel

                #get center coords of previous room
                (prev_x, prev_y) = rooms[num_rooms -1].center()

                #flip coin
                if flip_coin() == 1:
                    #move h then v
                    Game.map[Game.dungeon_levelname].create_h_tunnel(prev_x, new_x, prev_y)
                    Game.map[Game.dungeon_levelname].create_v_tunnel(prev_y, new_y, new_x)
                else:
                    #move v then h
                    Game.map[Game.dungeon_levelname].create_v_tunnel(prev_y, new_y, prev_x)
                    Game.map[Game.dungeon_levelname].create_h_tunnel(prev_x, new_x, new_y)
            
            #add to rooms list
            rooms.append(new_room)
            num_rooms +=1

    #create stairs at the center of the last room
    Game.downstairs[Game.dungeon_levelname] = entities.Object(new_x, new_y, '>', 'downstairs', libtcod.white, always_visible = True)
    Game.objects[Game.dungeon_levelname].append(Game.downstairs[Game.dungeon_levelname])
    Game.downstairs[Game.dungeon_levelname].send_to_back(Game) #so it's drawn below the monsters

    Game.map[Game.dungeon_levelname].initialize_fov()


def place_objects(room, Game):
    #choose random number of monsters
    #max number monsters per room
    nextid = 1
    max_monsters = from_dungeon_level([[10, 1], [40, 3], [50, 6], [70, 10]], data.maplist.index(Game.dungeon_levelname))
    num_monsters = libtcod.random_get_int(0, 0, max_monsters)
    monster_chances = get_monster_chances(Game)

    max_items = from_dungeon_level([[10, 1], [2, 4]], data.maplist.index(Game.dungeon_levelname))
    num_items = libtcod.random_get_int(0, 0, max_items)
    item_chances = get_item_chances(Game)

    for i in range(num_monsters):
        #choose random spot for this monster
        x =  libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y =  libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        if not entities.is_blocked(x, y, Game):
            #create a monster
            choice = random_choice(monster_chances)

            monster             = entities.Object(**entitydata.mobs[choice])
            monster.dungeon_level = data.maplist.index(Game.dungeon_levelname) 
            monster.blocks      = True        
            monster.ai          = entities.Ai(entities.BasicMonster())  #how do I set different ai?
            monster.ai.owner    = monster
            monster.id          = str(monster.dungeon_level) + '.' + str(nextid)
            monster.name        = choice + '(' + str(monster.id) + ')'
            if data.FREE_FOR_ALL_MODE:
                monster.fighter.clan        = monster.name
            nextid+=1
            monster.fighter.fov = Game.map[Game.dungeon_levelname].fov_map


            print 'MAPGEN--\t ' + str(Game.tick) + '\t' + Game.dungeon_levelname + '\t' + ' made a ' + monster.name

            #give monster items if they have them
            if entitydata.mobitems[choice]:
                for itemname in entitydata.mobitems[choice]:
                    item = entities.Object(**entitydata.items[itemname])
                    monster.fighter.add_item(item)

            monster.set_location(x, y, Game)
            Game.objects[Game.dungeon_levelname].append(monster)

    for i in range(num_items):
        #choose random spot for this item
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        #only place it if the tile is not blocked
        if not entities.is_blocked(x, y,Game):
            #create an item
            choice = random_choice(item_chances)

            item = entities.Object(**entitydata.items[choice])
            item.always_visible = True

            item.set_location(x, y, Game)
            item.dungeon_level = data.maplist.index(Game.dungeon_levelname)

            Game.objects[Game.dungeon_levelname].append(item)
            item.send_to_back(Game) #items appear below other objects

def get_monster_chances(Game):
    #chance of each monster
    monster_chances = {}

    for mobname in entitydata.mobchances:
        monster_chances[mobname] = from_dungeon_level(entitydata.mobchances[mobname], data.maplist.index(Game.dungeon_levelname))

    return monster_chances

def get_item_chances(Game):
    #chance of each monster
    item_chances = {}

    for itemname in entitydata.itemchances:
        item_chances[itemname] = from_dungeon_level(entitydata.itemchances[itemname], data.maplist.index(Game.dungeon_levelname))

    return item_chances
