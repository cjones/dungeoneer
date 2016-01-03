"""
a super basic geometry manager. maybe todo: discrete Point and Size
objects to compse Rect with.
"""

class Rect(object):
    __slots__ = ('width', 'height', 'x', 'y')

    @property
    def __values__(self):
        return [getattr(self, slot) for slot in self.__slots__]

    def asdict(self):
        return dict(zip(self.__slots__, self.__values__))

    def __init__(self, width, height, x=0, y=0):
        self.width = width
        self.height = height
        self.x = x
        self.y = y

    def __getitem__(self, key):
        if key not in self.__slots__:
            raise KeyError(key)
        return getattr(self, key)

    def __setitem__(self, key, val):
        if key not in self.__slots__:
            raise KeyError(key)
        setattr(self, key, val)

    @property
    def size(self):
        return self.width, self.height

    @size.setter
    def size(self, size):
        self.width, self.height = size

    @property
    def pos(self):
        return self.x, self.y

    @pos.setter
    def pos(self, pos):
        self.x, self.y = pos

    def __str__(self):
        return '({})'.format(', '.join(
            map('{}={!r}'.format, self.__slots__, self.__values__)))

    def __repr__(self):
        return type(self).__name__ + self.__str__()

bounded = lambda val, lower, upper: max([min([val, upper]), lower])
bounded.__doc__ = 'ensure lower <= val <= upper'
