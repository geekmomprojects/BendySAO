"""
Animations that are CPU and memory intensive and only run on the ESP32.
"""

from . import trickLED
from . import generators

from .animations import AnimationBase, getrandbits, randrange

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


class MappedAnimationBase(AnimationBase):
    """ Animations that use metadata on each pixel and map that to a color. """
    def __init__(self, leds, **kwargs):
        super().__init__(leds, **kwargs)
        # bit shift if we need to map 0-255 values to a smaller palette size of 128, 64 or 32
        self.settings['palette_shift'] = 0
        self.pixel_meta = trickLED.ByteMap(self.calc_n, 1)
        self._ordered_palette = None

    def set_ordered_palette(self):
        """ Convert RGB palette to byte order of our strip.  """
        pal = self.palette
        if self._ordered_palette is None or pal.n != self._ordered_palette.n:
            self._ordered_palette = trickLED.ByteMap(pal.n, pal.bpi)
        op = self._ordered_palette
        for i in range(pal.n):
            op[i] = pal.get_ordered_item(i)

    def colorize(self):
        """ Convert pixel meta data to colors.  To improve speed:
        1) We write directly to the leds buffer
        2) Pre-convert the palette from RGB to strip byte order (probably GRB)
        """
        buf = bytearray()
        pal = self._ordered_palette
        meta = self.pixel_meta
        shift = self.settings.get('palette_shift', 0)
        zero = bytearray([0,0,0])
        bpi = pal.bpi
        for m in meta:
            if m:
                i = (m >> shift) * bpi
                buf += pal.buf[i:i+bpi]
            else:
                buf += zero
        if len(self.leds.buf) == len(buf):
            self.leds.buf = buf
        else:
            raise Exception('buffer length changed')


class Fire(MappedAnimationBase):
    """
    Simulate fire.
    """
    def __init__(self, leds, sparking=64, cooling=15, scroll_speed=1, hotspots=1, **kwargs):
        """
        :param leds: TrickLED object
        :param sparking: Odds / 255 of generating a new spark
        :param cooling: How much the flames are cooled.
        :param scroll_speed: Speed and direction that flames move.
        :param hotspots: Number of spark locations. One will always be placed on the edge.
        :param kwargs:
        """
        super().__init__(leds, **kwargs)
        # Blend map keeps track of which positions need blended
        self._blend_map = trickLED.BitMap(self.calc_n)
        self.settings['sparking'] = sparking
        self.settings['cooling'] = cooling
        self.settings['scroll_speed'] = int(scroll_speed)
        self.settings['hotspots'] = max(hotspots, 1)
        # we map 256 heat levels to a palette of 64, 128 or 256, calculated in setup()
        self.settings['palette_shift'] = 0
        self._flash_points = None
        if 'palette' in kwargs:
            if len(kwargs['palette']) >= 64:
                self.palette = kwargs['palette']
            else:
                raise ValueError('Palette length should be at least 64')
        else:
            self.palette = trickLED.ByteMap(64, bpi=3)
            for i in range(64):
                self.palette[i] = trickLED.heat_color(i * 4)

    def setup(self):
        self.set_ordered_palette()
        self.pixel_meta.fill(0)
        # add insertion points and calculate ranges to blend
        self._flash_points = set()
        if self.settings['scroll_speed'] > 0:
            # fire ascending
            self._flash_points.add(0)
            bmin = 0
            bmax = 11
        elif self.settings['scroll_speed'] < 0:
            # fire descending
            self._flash_points.add(self.calc_n - 1)
            bmin = -10
            bmax = 1
        else:
            self._flash_points.add(randrange(0, self.calc_n - 1))
            bmin = -5
            bmax = 6

        sect_size = self.calc_n // self.settings['hotspots']
        for i in range(1, self.settings['hotspots']):
            # add additional flash_points with some randomness so they are not exactly evenly spaced
            rn = getrandbits(4) - 8
            ip = sect_size * i + rn
            if not 0 < ip < self.calc_n:
                ip = min(max(ip, 0), self.calc_n - 1)
            self._flash_points.add(ip)

        # calculate blend_map
        self._blend_map.repeat(0)
        for fp in self._flash_points:
            for i in range(fp + bmin, fp + bmax):
                if 0 <= i < self.calc_n and i not in self._flash_points:
                    self._blend_map[i] = 1

        # determine if we are mapping 256 levels of heat to 64, 128 or 256 colors
        if len(self.palette) >= 256:
            self.settings['palette_shift'] = 0
        elif len(self.palette) >= 128:
            self.settings['palette_shift'] = 1
        else:
            self.settings['palette_shift'] = 2

    def calc_frame(self):
        uint8 = trickLED.uint8
        cn = self.calc_n
        mi = cn - 1
        if self.settings['scroll_speed'] != 0:
            self.pixel_meta.scroll(self.settings['scroll_speed'])

        # calculate sparks at insertion points
        for ip in self._flash_points:
            spark = getrandbits(8)
            if spark <= self.settings['sparking']:
                # add a spark at insert_point with random heat between 192 and 255
                val = 192 + (spark & 63)
            else:
                val = (spark & 127) | 64
            self.pixel_meta[ip] = val

        # blend - copy heat map so we don't "cool" as we are blending
        heat_map = trickLED.ByteMap(self.calc_n, bpi=1)
        heat_map.buf = self.pixel_meta.buf[:]
        for i in range(self.calc_n):
            if self._blend_map[i]:
                if 0 < i < mi:
                    val = sum(heat_map[i-1:i+2]) / 3
                elif i == 0:
                    val = sum(heat_map[0:2]) / 2
                else:
                    val = sum(heat_map[-2:]) / 2
                self.pixel_meta[i] = uint8(val)
        # cool
        self.pixel_meta.sub(self.settings.get('cooling'))
        self.colorize()


class Conjunction(MappedAnimationBase):
    """ Colors grow out and fade in both directions from random points 32 pixels apart. When the colors touch
        they are cleared and the cycle starts over.
    """
    def __init__(self, leds, **kwargs):
        super().__init__(leds, **kwargs)
        if not self.generator:
            # in this animation the generator will be used to fill the palette each cycle
            self.generator = generators.fading_color_wheel(hue_stride=25, stripe_size=16, mode=trickLED.FADE_OUT)
        self.palette = trickLED.ByteMap(33, bpi=3)

    def setup(self):
        self.state = {'step': 0, 'insert_points': []}
        self._ordered_palette = trickLED.ByteMap(self.palette.n, self.palette.bpi)
        self.start_cycle()

    def start_cycle(self):
        self.pixel_meta.fill(0)
        self.leds.fill(0)
        self.palette.fill_gen(self.generator, start_pos=1, direction=-1)
        self.palette[0] = trickLED.colval(0)
        self.set_ordered_palette()
        self.state['step'] = 0
        rn = getrandbits(5) # 0-31
        self.state['insert_points'] = [rn - 32, rn]
        while rn < self.calc_n:
            rn += 32
            self.state['insert_points'].append(rn)

    def calc_frame(self):
        step = self.state['step']
        self.state['step'] += 1
        pixel_meta = self.pixel_meta
        if step >= 16:
            self.start_cycle()
            return
        # "fade" colors by 1
        pixel_meta.sub(1)

        j = 0
        for ip in self.state['insert_points']:
            ni = ip - step
            pi = ip + step
            if 0 <= ni < self.calc_n:
                cv = [15, 31][j % 2]
                pixel_meta[ni] = cv
            if 0 <= pi < self.calc_n:
                cv = [31, 15][j % 2]
                pixel_meta[pi] = cv
            j += 1
        self.colorize()
