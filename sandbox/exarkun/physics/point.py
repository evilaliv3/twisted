
import numarray as N

G = 6.667e-11

_V_DIMS = 7
_MASS = 0
_POSITION = slice(1, 4)
_VELOCITY = slice(4, 7)

class Space(object):
    def __init__(self):
        self.contents = N.array((), type='d')
        self.freelist = []
        self._accel = N.zeros(3, typecode='d')

    def getNewHandle(self):
        if self.freelist:
            return self.freelist.pop()
        n = len(self.contents)
        m = int((n * 1.1) + 10)
        self.contents.resize((m, _V_DIMS))
        self.freelist.extend(range(m - 1, n, -1))
        return n

    def freeHandle(self, n):
        self.freelist.append(n)
        self.contents[n] = [0] * _V_DIMS

    def update(self):
        self._updatePosition()
        self._updateVelocity()

    def _updatePosition(self):
        # Add velocity to position to get new positions
        # Do it in place for speeeed
        N.add(self.contents[:,_POSITION], self.contents[:,_VELOCITY], self.contents[:,_POSITION])

    def _updateVelocity(self, sum=N.sum, add=N.add, _M=_MASS, _P=_POSITION, _V=_VELOCITY):
        # Adjust velocities for gravitational effects
        accel = self._accel
        for a in self.contents:
            mass = a[_M]
            if not mass:
                continue
            accel[:] = 0
            for b in self.contents:
                deltas = b[_P] - a[_P]
                delta2 = deltas * deltas
                distance2 = sum(delta2)
                if distance2:
                    distance = distance2 ** 0.5
                    unit = deltas / distance
                    force = G * mass * b[_M] / distance2
                    deltaA = unit * force / mass
                    add(accel, deltaA, accel)
            velocity = a[_V]
            add(velocity, accel, velocity)

class Body(object):
    __slots__ = ["_space", "_handle", "mass", "position", "velocity"]

    def mass():
        def get(self):
            return self._space.contents[self._handle][_MASS]
        def set(self, value):
            self._space.contents[self._handle][_MASS] = value
        doc = "Mass, in kilograms, of this body"
        return (get, set, None, doc)
    mass = property(*mass())

    def position():
        def get(self):
            return tuple(self._space.contents[self._handle][_POSITION])
        def set(self, pos):
            self._space.contents[self._handle][_POSITION] = pos
        doc = "XYZ coordinates of this body"
        return (get, set, None, doc)
    position = property(*position())

    def velocity():
        def get(self):
            return tuple(self._space.contents[self._handle][_VELOCITY])
        def set(self, vel):
            self._space.contents[self._handle][_VELOCITY] = vel
        doc = "XYZ velocity, in kilometers/second, of this body"
        return (get, set, None, doc)
    velocity = property(*velocity())

    def __init__(self, space, mass, position, velocity=(0, 0, 0)):
        self._space = space
        self._handle = space.getNewHandle()
        self.mass = mass
        self.position = position
        self.velocity = velocity