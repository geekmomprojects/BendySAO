import math
import struct

from random import getrandbits
from neopixel import NeoPixel
from micropython import const

BITS_LOW = const(15)             # 00001111
BITS_MID = const(60)             # 00111100
BITS_HIGH = const(240)           # 11110000
BITS_EVEN = const(85)            # 01010101
BITS_ODD = const(170)            # 10101010
BITS_NONE = const(0)             # 00000000
BITS_ALL = const(255)            # 11111111
BITS_ALL_32 = const(1 << 32 - 1)  # 32 1s
FADE_IN = const(1)
FADE_OUT = const(2)
FADE_IN_OUT = const(3)
FILL_MODE_MULTI = const(4)
FILL_MODE_SOLID = const(5)

global_setings = {
    'brightness': 200,
    'interval': 60,
    'palette': None,
    'animation': None
}

global_state = {
    'audio_intensity': None,
    'audio_peak': None,
}


def blend(col1, col2, pct=50):
    """
    Blend color 1 with percentage of color 2

    :param col1: Color 1
    :param col2: Color 2
    :param pct: Percentage of color 2
    :return: color tuple
    """
    if 0 <= pct <= 100:      
        result = [0, 0, 0]
        for i in range(len(col1)):
            result[i] = uint8(col1[i] + (col2[i] - col1[i]) / 100 * pct)
        return tuple(result)
    else:
        return col1
    

def step_inc(c1, c2, steps):
    """ Calculate step increment to blend colors in n steps """
    return tuple((c2[i] - c1[i]) / steps for i in range(len(c1)))  


def uint8(val):
    if 0 <= val <= 255:
        return int(val)
    if val < 0:
        return 0
    else:
        return 255


def add8(a, b):
    return uint8(a + b)


def mult8(a, b):
    return uint8(a * b)


def sin8(v):
    """ Sin in 255 "degrees" """
    vr = v / 127.5 * math.pi
    return math.sin(vr)


def cos8(v):
    """ Cos in 255 "degrees" """
    vr = v / 127.5 * math.pi
    return math.cos(vr)


def color_wheel(hue, val=255):
    """ 255 degree color wheel. HSV but all at full saturation. """
    hue = uint8(hue) % 255
    pa = hue % 85
    ss = val / 85
    ci = uint8(ss * pa)
    cd = uint8(val) - ci
    if hue < 85:
        return cd, ci, 0
    elif hue < 170:
        return 0, cd, ci
    else:
        return ci, 0, cd


def heat_color(temp):
    """ Return loose approximation of black body radiation. """
    # normalizing to 191 and using last 6 bits of that for heat_ramp was borrowed from FastLED
    t191 = temp * 191 // 255
    heat_ramp = (t191 & 63) << 2
    if t191 < 64:
        return heat_ramp, 0, 0
    elif t191 < 128:
        return 255, heat_ramp, 0
    else:
        return 255, 255, heat_ramp


def rand32(pct):
    """ Return a random 32 bit int with approximate percentage of ones."""
    # grb = random.getrandbits() ~ 50% 1's
    grb = getrandbits
    if pct < 1:
        return 0
    elif pct <= 6:
        return grb(32) & grb(32) & grb(32) & grb(32)
    elif pct <= 19:
        return grb(32) & grb(32) & grb(32)
    elif pct <= 31:
        return grb(32) & grb(32)
    elif pct <= 44:
        return grb(32) & (grb(32) | grb(32))
    elif pct <= 56:
        return grb(32)
    elif pct <= 69:
        return grb(32) | (grb(32) & grb(32))
    elif pct <= 81:
        return grb(32) | grb(32)
    elif pct <= 94:
        return grb(32) | grb(32) | grb(32)
    elif pct >= 100:
        return 2 ** 32 - 1
    else:
        return grb(32) | grb(32) | grb(32) | grb(32)


def randrange(low, high):
    # esp8266 port doesn't have randrange (or bit_length)
    d = high - low
    bl = len(bin(d)) - 2
    rn = getrandbits(bl) + low
    if low <= rn <= high:
        return rn
    rv = rn & high
    if low <= rv <= high:
        return rv
    rv = rn | low 
    if low <= rv <= high:
        return rv
    return high
      

def colval(val, bpp=3):
    """ allow the input of color values as ints (including hex) and None/0 for black """
    if not val:
        val = (0,) * bpp
    elif isinstance(val, int):
        val = tuple(val.to_bytes(bpp, 'big'))
    return val


def shift_bits(val, shift):
    # shift bits left if shift is positive, right if negative
    if shift > 0:
        return val << shift
    if shift < 0:
        return val >> -shift
    return val


class BitMap:
    """ Helper class to keep track of metadata about our pixels as a bit in a bytearray
        The values automatically wrap around instead of throwing an index error.
    """
    def __init__(self, n, pct=50):
        self.n = n
        # number of 32-bit words
        self.wc = math.ceil(n / 32)
        self._mi = self.wc * 32
        # Hamming weight, rough percentage of ones when randomizing
        self.pct = pct
        self.buf = bytearray(self.wc * 4)
        self._po = 0

    def bit(self, idx, val=None):
        """ Get or set a single bit """
        if self._po:
            idx = (idx + self._po) % self.n 
        byte_idx = idx // 8
        bit_idx = idx % 8
        mask = 1 << bit_idx
        if val is None:
            return (self.buf[byte_idx] & mask) >> bit_idx
        if val == 0:
            self.buf[byte_idx] &= ~mask
        elif val == 1:
            self.buf[byte_idx] |= mask

    def __getitem__(self, i):
        if 0 <= i < self.n:
            return self.bit(i)
        else:
            raise IndexError('index out of range')

    def __setitem__(self, i, val):
        if 0 <= i < self._mi:
            #
            self.bit(i, val)
        else:
            raise IndexError('index out of range')

    def scroll(self, steps):
        self._po = (self._po - steps) % self.n
                  
    def randomize(self, pct=None):
        """ fill buffer with random 1s and 0s. Use pct to control the approx percent of 1s """
        self._po = 0
        if pct is None:
            pct = self.pct
        buf = bytearray()
        for i in range(self.wc):
            buf += struct.pack('I', rand32(pct))
        self.buf = buf

    def repeat(self, val):
        """ fill buffer by repeating val """
        self._po = 0
        if not isinstance(val, int) or val >= 1 << 32:
            raise ValueError('Value error must be int')
        if val < 256:
            n = self.wc * 4
            v = val
            self.buf = bytearray([v] * n)
            return
        elif val < 1 << 16:
            n = self.wc * 2
            v = val.to_bytes(2, 'little')
        elif val < 1 << 24:
            n = math.ceil(self.wc * 4 / 3)
            v = val.to_bytes(3, 'little')
        else:
            n = self.wc
            v = struct.pack('I', val)

        buf = bytearray()
        for i in range(n):
            buf += v
        self.buf = buf[0:self.wc * 4]

    def print(self):
        p = '{:4d} | {:08b} {:08b} {:08b} {:08b} | {:4d}'
        print('     | ' + '76543210 ' * 4 + '|     ')
        print('-' * 49)
        for i in range(0, self.wc * 4, 4):
            bts = list(reversed(self.buf[i:i+4]))
            vals =[i * 8 + 31] + bts + [i * 8]
            print(p.format(*vals))


class ByteMap:
    """
    Map some number of bytes to items. Values automatically wrap around instead of throwing index errors.
    Use for color palettes or keeping track of things like temperature during animations.
    """
    def __init__(self, n, bpi=3, order=(1,0,2)):
        """
        :param n: Number of items
        :param bpi: bytes per item
        """
        self.n = n
        self.bpi = bpi
        self.buf = bytearray(n * bpi)
        self.order = order

    def __setitem__(self, key, value):
        value = bytes(colval(value, self.bpi))
        idx = key * self.bpi
        if 0 <= key < self.n:
            self.buf[idx:idx + self.bpi] = value
        elif key == self.n:
            self.buf += value
            self.n += 1
        else:
            raise IndexError('index out of range')

    def __getitem__(self, key):
        if isinstance(key, int):
            if 0 <= key < self.n:
                si = key * self.bpi
            elif -self.n < key < 0:
                si = (key + self.n) * self.bpi
            else:
                raise IndexError('index out of range')
            if self.bpi > 1:
                return tuple(self.buf[si: si + self.bpi])
            else:
                return self.buf[si]
        elif isinstance(key, slice):
            si = (key.start if key.start else 0) * self.bpi
            ei = (key.stop if key.stop else self.n) * self.bpi
            if key.step and (key.step < -1 or key.step > 1):
                step = key.step * self.bpi
            else:
                step = key.step
            return self.buf[si:ei:step]

    def get_ordered_item(self, key):
        # get item in proper order to write to led buffer
        si = key * self.bpi
        return bytearray(self.buf[si + i] for i in self.order)

    def __len__(self):
        return self.n

    def append(self, val):
        self.buf.append(val)
        self.n += 1

    def extend(self, vals):
        self.buf.extend(vals)
        self.n = len(self.buf) // self.bpi

    def add(self, val):
        if isinstance(val, (list, tuple)):
            if len(val) < self.bpi:
                raise ValueError('Length of value to add must match byte size.')
            self.buf = bytearray([uint8(self.buf[i] + val[i % self.bpi]) for i in range(self.n * self.bpi)])
        else:
            self.buf = bytearray([uint8(v + val) for v in self.buf])

    def sub(self, val):
        if isinstance(val, (list, tuple)):
            if len(val) < self.bpi:
                raise ValueError('Length of value to sub must match byte size.')
            self.buf = bytearray([uint8(self.buf[i] - val[i % self.bpi]) for i in range(self.n * self.bpi)])
        else:
            self.buf = bytearray([uint8(v - val) for v in self.buf])

    def mul(self, val):
        if isinstance(val, (list, tuple)):
            if len(val) < self.bpi:
                raise ValueError('Length of value to multiply must match byte size.')
            self.buf = bytearray([uint8(self.buf[i] * val[i % self.bpi]) for i in range(self.n * self.bpi)])
        else:
            self.buf = bytearray([uint8(v * val) for v in self.buf])

    def div(self, val):
        if isinstance(val, (list, tuple)):
            if len(val) < self.bpi:
                raise ValueError('Length of value to divide must match byte size.')
            self.buf = bytearray([uint8(self.buf[i] // val[i % self.bpi]) for i in range(self.n * self.bpi)])
        else:
            self.buf = bytearray([uint8(v // val) for v in self.buf])

    def scroll(self, step=1):
        cut = self.bpi * -step
        self.buf = self.buf[cut:] + self.buf[:cut]

    def fill(self, val, start_pos=0, end_pos=None):
        val = colval(val, self.bpi)
        if end_pos is None or end_pos >= self.n:
            end_pos = self.n - 1
        for i in range(start_pos, end_pos + 1):
            self[i] = val

    def fill_gradient(self, v1, v2, start_pos=0, end_pos=None):
        if end_pos is None or end_pos >= self.n:
            end_pos = self.n - 1
        steps = end_pos - start_pos
        v1 = colval(v1, self.bpi)
        v2 = colval(v2, self.bpi)
        inc = step_inc(v1, v2, steps)
        for i in range(steps):
            val = tuple(uint8(v1[n] + inc[n] * i) for n in range(self.bpi))
            self[start_pos + i] = val
        self[end_pos] = v2

    def fill_gen(self, gen, start_pos=0, end_pos=None, direction=1):
        if end_pos is None or end_pos >= self.n:
            end_pos = self.n - 1
        if direction > 0:
            for i in range(start_pos, end_pos + 1):
                self[i] = next(gen)
        else:
            for i in range(end_pos, start_pos - 1, -1):
                self[i] = next(gen)


class TrickLED(NeoPixel):
    """ NeoPixels with benefits to aid in creating animations.
    """
    # repeat section 0-n, 0-n, 0-n
    REPEAT_MODE_STRIPE = const(1)
    # repeat section alternating backward and forward 0-n, n-0, 0-n
    REPEAT_MODE_MIRROR = const(2)

    def __init__(self, pin, n, repeat_n=None, repeat_mode=None, **kwargs):
        """
        :param pin: Data pin
        :param n: number of pixels
        :param repeat_n: If set, the first n pixels will be repeated across the rest of the strip 
        :param repeat_mode: Controls if section is repeated or mirrored (alternating between forward and reversed)
        :param kwargs: bpp, timing
        """
        super().__init__(pin, n, **kwargs)
        self.repeat_n = repeat_n
        self.repeat_mode = repeat_mode if repeat_mode else TrickLED.REPEAT_MODE_STRIPE

    def __setitem__(self, i, val):
        if 0 <= i < self.n:
            val = colval(val, self.bpp)
            super().__setitem__(i, val)
        else:
            raise IndexError('Assignment index out of range')

    def _rgb_to_order(self, col):
        """ Convert RGB value to byte order of LEDs """
        return [col[self.ORDER[i]] for i in range(self.bpp)]

    def scroll(self, step=1):
        """ Scroll the pixels some number of steps in the given direction.

        :param step: Number and direction to shift pixels
        """
        cut = self.bpp * -step
        self.buf = self.buf[cut:] + self.buf[:cut]

    def fill_solid(self, color, start_pos=0, end_pos=None):
        """
        Fill strip with a solid color from start position to end position

        :param color: Color to fill
        :param start_pos: Start position, defaults to beginning of strip
        :param end_pos: End position, defaults to end of strip
        """
        if end_pos is None or end_pos >= self.n:
            end_pos = (self.repeat_n or self.n) - 1
        for i in range(start_pos, end_pos + 1):
            self[i] = color

    def fill_gradient(self, col1, col2, start_pos=0, end_pos=None):
        """
        Fill strip with a gradient from col1 to col2. If positions are not given, the entire strip will be filled.

        :param col1: Starting color
        :param col2: Ending color
        :param start_pos: Start position, defaults to beginning of strip
        :param end_pos: End position, defaults to end of strip
        """
        if end_pos is None or end_pos >= self.n:
            end_pos = (self.repeat_n or self.n) - 1
        steps = end_pos - start_pos
        col1 = colval(col1, self.bpp)
        col2 = colval(col2, self.bpp)
        inc = step_inc(col1, col2, steps)
        for i in range(steps):
            col = tuple(uint8(col1[n] + inc[n] * i) for n in range(len(col1)))
            self[start_pos + i] = col
        self[end_pos] = col2

    def fill_gen(self, gen, start_pos=0, end_pos=None, direction=1):
        """
        Fill strip with with colors from a generator.
        :param gen: Color generator
        :param start_pos: Start position, defaults to beginning of strip
        :param end_pos: End position, defaults to end of strip
        :param direction:
        """
        if end_pos is None or end_pos >= self.n:
            end_pos = (self.repeat_n or self.n) - 1
        if direction > 0:
            for i in range(start_pos, end_pos + 1):
                self[i] = next(gen)
        else:
            for i in range(end_pos, start_pos - 1, -1):
                self[i] = next(gen)

    def blend_to_color(self, color=0, pct=50, start_pos=0, end_pos=None):
        """
         Blend each pixel with color from start position to end position.

        :param color: Color to blend
        :param pct: Percentage of new color vs existing color
        :param start_pos: Start position, defaults to beginning of strip
        :param end_pos: End position
        """
        color = colval(color, self.bpp)
        last_col = (0,) * self.bpp
        blend_col = (0,) * self.bpp
        if end_pos is None:
            end_pos = (self.repeat_n or self.n) - 1
        for i in range(start_pos, end_pos + 1):
            if self[i] == blend_col:
                continue
            elif self[i] == last_col:
                self[i] = blend_col
            else:
                last_col = self[i]
                blend_col = blend(self[i], color, pct)
                self[i] = blend_col

    def add(self, val):
        bpp = self.bpp
        mi = self.repeat_n or self.n
        if isinstance(val, (list, tuple)):
            if len(val) < bpp:
                raise ValueError('Length of value to add must match bpp')
            # convert RGB to string byte order
            val = self._rgb_to_order(val)
            self.buf = bytearray([uint8(self.buf[i] + val[i % bpp]) for i in range(mi * bpp)])
        else:
            self.buf = bytearray([uint8(self.buf[i] + val) for i in range(mi * bpp)])

    def sub(self, val):
        bpp = self.bpp
        mi = self.repeat_n or self.n
        if isinstance(val, (list, tuple)):
            if len(val) < bpp:
                raise ValueError('Length of value to subtract must match bpp')
            # convert RGB to string byte order
            val = self._rgb_to_order(val)
            self.buf = bytearray([uint8(self.buf[i] - val[i % bpp]) for i in range(mi * bpp)])
        else:
            self.buf = bytearray([uint8(self.buf[i] - val) for i in range(mi * bpp)])

    def mul(self, val):
        bpp = self.bpp
        mi = self.repeat_n or self.n
        if isinstance(val, (list, tuple)):
            if len(val) < bpp:
                raise ValueError('Length of value to multiply must match bpp')
            # convert RGB to string byte order
            val = self._rgb_to_order(val)
            self.buf = bytearray([uint8(self.buf[i] * val[i % bpp]) for i in range(mi * bpp)])
        else:
            self.buf = bytearray([uint8(self.buf[i] * val) for i in range(mi * bpp)])

    def div(self, val):
        bpp = self.bpp
        mi = self.repeat_n or self.n
        if isinstance(val, (list, tuple)):
            if len(val) < bpp:
                raise ValueError('Length of value to multiply must match bpp')
            # convert RGB to string byte order
            val = self._rgb_to_order(val)
            self.buf = bytearray([uint8(self.buf[i] / val[i % bpp]) for i in range(mi * bpp)])
        else:
            self.buf = bytearray([uint8(self.buf[i] / val) for i in range(mi * bpp)])

    def _repeat_stripe(self, n=None):
        """
        Copy the first n pixels and repeat them over the rest of the strip

        :param n: Number of pixels to copy (not the zero-based index!)
        """
        if n is None:
            n = self.repeat_n
        loc = jump = n * self.bpp
        end = self.n * self.bpp
        section = self.buf[0:jump]
        while loc + jump <= end:
            self.buf[loc:loc + jump] = section
            loc += jump
        if loc < end:
            self.buf[loc:end] = section[:(end - loc)]

    def _repeat_mirror(self, n=None):
        """ Copy the first n pixels and repeat them alternating directions """
        if n is None:
            n = self.repeat_n
        rl = n - 1
        d = -1
        setitem = super().__setitem__
        for i in range(n, self.n):
            setitem(i, self[rl])
            if 0 < rl < n:
                rl += 1 * d
            elif rl == 0:
                d = 1
            else:
                d = -1

    def write(self):
        if self.repeat_n:
            if self.repeat_mode == TrickLED.REPEAT_MODE_STRIPE:
                self._repeat_stripe()
            elif self.repeat_mode == TrickLED.REPEAT_MODE_MIRROR:
                self._repeat_mirror()
        super().write()


class TrickMatrix(NeoPixel):
    # All rows run in the same direction
    LAYOUT_STRAIGHT = const(1)
    # Direction of rows alternate from right to left
    LAYOUT_SNAKE = const(2)
    
    def __init__(self, pin, width, height, shape=None, **kwargs):
        if shape is None:
            self.shape = self.LAYOUT_SNAKE
        else:
            self.shape = shape
        self.width = width
        self.height = height
        super().__init__(pin, width * height, **kwargs)    
    
    def _idx(self, x, y):
        """ Return the index of the x, y coordinate """
        if x >= self.width or y >= self.height:
            raise IndexError('Out of bounds error. Dimensions are %d x %d' % (self.width, self.height))
        if y % 2 == 0 or self.shape == self.LAYOUT_STRAIGHT:
            return self.width * y + x
        else:
            return self.width * (y + 1) - x - 1          
        
    def pixel(self, x, y, color=None):
        """
        Get or set the color of pixel at x,y coordinate
        """
        idx = self._idx(x, y)
        if color is None:
            return self[idx]
        else:
            if isinstance(color, int):
                color = color.to_bytes(self.bpp, 'big')
            self[idx] = color
            
    def hline(self, x, y, width, color):
        for ix in range(x, x + width):
            self.pixel(ix, y, color)
    
    def vline(self, x, y, height, color):
        for iy in range(y, y + height):
            self.pixel(x, iy, color)
    
    def fill_rect(self, x, y, width, height, color):
        for iy in range(y, y + height):
            for ix in range(x, x + width):
                self.pixel(ix, iy, color)
    
    def hscroll(self, step):
        """ TODO: implement matrix scrolling """
        pass

    def vscroll(self, step):
        """ TODO: implement matrix scrolling """
        pass
