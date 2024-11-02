import time
import trickLED
import generators
from random import getrandbits

try:
    from random import randrange
except ImportError:
    randrange = trickLED.randrange

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


def default_palette(n, brightness=200):
    """ Generate a color palette by stepping through the color wheel """
    rn = getrandbits(8)
    pal = trickLED.ByteMap(n, 3)
    sa = min(255 // n, 30)
    for i in range(n):
        pal[i] = trickLED.color_wheel((rn + sa * i) % 255, brightness)
    return pal


class AnimationBase:
    """ Animation base class. """

    def __init__(self, leds, interval=50, palette=None, generator=None, brightness=200, **kwargs):
        """
        :param leds: TrickLED object
        :param interval: millisecond pause between each frame
        :param palette: color palette
        :param generator: color generator
        :param brightness: set brightness 0-255
        :param kwargs: additional keywords will be saved to self.settings
        """
        if not isinstance(leds, trickLED.TrickLED):
            raise ValueError('leds must be an instance of TrickLED')
        self.leds = leds
        self.frame = 0
        self.palette = palette
        self.generator = generator
        # configuration values can also be set as keyword arguments to __init__ or run
        self.settings = {'interval': int(interval), 'stripe_size': int(1),
                         'scroll_speed': int(1), 'brightness': trickLED.uint8(brightness)}
        # stores run time information needed for the animation
        self.state = {}
        # number of pixels to calculate before copying from buffer
        if self.leds.repeat_n:
            self.calc_n = self.leds.repeat_n
        else:
            self.calc_n = self.leds.n
        for kw in kwargs:
            self.settings[kw] = kwargs[kw]

    @property
    def palette(self):
        return self.__palette

    @palette.setter
    def palette(self, val):
        bpp = self.leds.bpp
        if val is None:
            self.__palette = None
            return
        if isinstance(val, trickLED.ByteMap):
            # passed ByteMap
            pal = val
        elif isinstance(val, (tuple, list)):
            if isinstance(val[0], int) and val[0] < 255:
                # passed a single color
                values = trickLED.colval(val)
            else:
                # passed a
                values = [vi for color in val for vi in color]
            pal = trickLED.ByteMap(0, bpp)
            pal.extend(values)
        elif isinstance(val, int) and val > 255:
            pal = trickLED.ByteMap(1, bpp)
            pal[0] = trickLED.colval(val, bpp)
        else:
            raise ValueError('Invalid type for palette {}'.format(val.__class__.__name__))
        self.__palette = pal

    def setup(self):
        """ Called once at the start of animation.  """
        pass

    def calc_frame(self):
        """ Called before rendering each frame """
        pass
    
    def setup_frame(self, max_iterations=0, **kwargs):
        """ Call this before playing an animation using play_frame """
        for kw in kwargs:
            self.settings[kw] = kwargs[kw]
        self.leds.fill((0,0,0))
        self.setup()
        self.frame = 0        
        #ival = self.settings['interval']
        self.state['start_ticks'] = time.ticks_ms()       
    
    def play_frame(self):
        if time.ticks_diff(time.ticks_ms(), self.state['start_ticks']) < self.settings['interval']*self.frame:
            return
        try:
            self.frame += 1
            self.calc_frame()
            self.leds.write()
        except KeyboardInterrupt:
            self._print_fps()
            return

    async def play(self, max_iterations=0, **kwargs):
        """
        Plays animation
        :param max_iterations: Number of frames to render
        :param kwargs: Any keys in the settings dictionary can be set by passing as keyword arguments
        """
        for kw in kwargs:
            self.settings[kw] = kwargs[kw]
        self.leds.fill((0,0,0))
        self.setup()
        self.frame = 0        
        ival = self.settings['interval']
        self.state['start_ticks'] = time.ticks_ms()
        try:
            while max_iterations == 0 or self.frame < max_iterations:
                self.frame += 1
                self.calc_frame()
                self.leds.write()
                await asyncio.sleep_ms(ival)
            self._print_fps()
        except KeyboardInterrupt:
            self._print_fps()
            return

    def _print_fps(self):
        st = self.state.get('start_ticks')
        if st is None:
            return
        et = time.ticks_ms()
        ival = self.settings.get('interval')
        fps = self.frame / time.ticks_diff(et, st) * 1000
        ifps = 1000 / ival if ival > 0 else 1000
        print('Actual fps: {:0.02f} - interval fps: {:0.02f}\n'.format(fps, ifps))


class NextGen(AnimationBase):
    """ Simple animation that animates a color generator by scrolling and
        feeding a new color in one frame at a time.
        Setting "blanks" will insert n blank pixels between each lit one.
    """
    def __init__(self, leds, generator=None, blanks=0, scroll_speed=1, **kwargs):
        """
        :param leds: TrickLED object
        :param generator: Color generator
        :param blanks: Number of blanks to insert between colors
        :param scroll_speed: 1 to scroll forward, -1 to scroll back
        :param kwargs:
        """
        if generator is None:
            generator = generators.striped_color_wheel(hue_stride=10, stripe_size=1)
        super().__init__(leds, generator=generator, **kwargs)
        self.settings['blanks'] = int(blanks)
        self.settings['scroll_speed'] = int(scroll_speed)

    def setup(self):
        self.leds.fill((0,0,0))
        stripe_size = self.settings.get('stripe_size', 1)
        blanks = self.settings['blanks']
        # limit scrolling to either 1 or -1
        if self.settings['scroll_speed'] not in (-1, 1):
            self.settings['scroll_speed'] = min(max(self.settings['scroll_speed'], -1), 1) or 1
        # pre-fill the strip. Go in the opposite direction we are scrolling
        if self.settings['scroll_speed'] < 0:
            self.state['insert_point'] = self.calc_n - 1
            for i in range(0, self.calc_n, blanks + 1):
                self.leds[i] = next(self.generator)
        else:
            self.state['insert_point'] = 0
            for i in range(self.calc_n - 1, -1,  -1):
                self.leds[i] = next(self.generator)

    def calc_frame(self):
        self.leds.scroll(self.settings['scroll_speed'])
        if self.settings.get('blanks'):
            cl = self.settings.get('blanks') + 1
            if self.frame % cl == 0:
                col = next(self.generator)
            else:
                col = 0
        else:
            col = next(self.generator)
        self.leds[self.state['insert_point']] = col


class LitBits(AnimationBase):
    """ Animation where only some pixels are lit.  You can scroll the colors and lit_bits independently at different
        speeds or in different directions. If you set lit_percent the lit pixels will be random instead of a
        repeating pattern.
    """
    def __init__(self, leds, scroll_speed=1, lit_scroll_speed=-1, lit_percent=None, **kwargs):
        """
        :param leds: TrickLED
        :param scroll_speed: Set speed and direction of color scroll.
        :param lit_scroll_speed: Set speed and direction of lit_bits.
        :param lit_percent: Approx percent of leds that will be lit when calling lit_bits.randomize().
                            If set lit_bits will be randomized instead of having a repeating pattern.
        :param kwargs:
        """
        super().__init__(leds, **kwargs)
        self.settings['scroll_speed'] = int(scroll_speed)
        self.settings['lit_scroll_speed'] = int(lit_scroll_speed)
        self.settings['lit_percent'] = lit_percent
        # controls which leds are lit and which are off
        self.lit = trickLED.BitMap(self.calc_n)
        if not self.settings['lit_percent']:
            self.lit.repeat(119)  # three on one off

    def setup(self):
        if self.palette is None:
            self.palette = default_palette(20, self.settings.get('brightness', 200))
        if self.settings.get('lit_percent'):
            self.lit.pct = self.settings.get('lit_percent')
            self.lit.randomize()

    def calc_frame(self):
        if self.settings['lit_percent'] and self.frame % 30 == 0:
            self.lit.randomize()
        pl = len(self.palette)
        for i in range(self.calc_n):
            if self.lit[i] == 1:
                col = self.palette[i % pl]
            else:
                col = 0
            self.leds[i] = col
        self.palette.scroll(self.settings.get('scroll_speed', 1))
        self.lit.scroll(self.settings.get('lit_scroll_speed', -1))


class Jitter(LitBits):
    """ Light random pixels and slowly fade them. This would be a great music reactive animation. """
    def __init__(self, leds, fade_percent=40, sparking=25, background=0x0a0a0a,
                 lit_percent=15, fill_mode=None, **kwargs):
        """
        :param leds: TrickLED
        :param fade_percent: Percent to fade colors each cycle
        :param sparking: Odds / 255 of sparking more pixels
        :param background: Background color of unsparked pixels
        :param lit_percent: Approximate percent of pixels to be lit when sparking
        :param fill_mode: fill sparked with either same color (solid)
                   or generate new color for each (multi).
        :param kwargs:
        """
        super().__init__(leds, **kwargs)
        self.settings['fade_percent'] = fade_percent
        self.settings['sparking'] = sparking
        self.settings['background'] = background
        self.settings['lit_percent'] = lit_percent
        self.settings['fill_mode'] = fill_mode or trickLED.FILL_MODE_MULTI

    def setup(self):
        self.lit.pct = self.settings['lit_percent']
        self.settings['background'] = trickLED.colval(self.settings['background'])
        if not self.generator:
            self.generator = generators.random_pastel(bpp=self.leds.bpp)

    def calc_frame(self):
        bg = self.settings.get('background')
        fade_percent = self.settings.get('fade_percent')
        rv = getrandbits(8)
        fill_mode = self.settings.get('fill_mode')
        if rv < self.settings.get('sparking'):
            # sparking
            self.lit.randomize()
            spark_col = next(self.generator)
            for i in range(self.calc_n):
                if self.lit[i]:
                    if fill_mode == trickLED.FILL_MODE_SOLID:
                        col = spark_col
                    else:
                        col = next(self.generator)
                    self.leds[i] = col
                else:
                    col = self.leds[i]
                    if col != bg:
                        col = trickLED.blend(col, bg, fade_percent)
                        self.leds[i] = col
        else:
            # not sparking
            for i in range(self.calc_n):
                if self.lit[i]:
                    col = trickLED.blend(self.leds[i], bg, fade_percent)
                else:
                    col = bg
                self.leds[i] = col


class SideSwipe(AnimationBase):
    """ Step back and forth through pixels while cycling through color generators at each direction change."""
    def __init__(self, leds, color_generators=None, **kwargs):
        super().__init__(leds, **kwargs)
        if color_generators:
            self.generators = color_generators
        else:
            self.generators = []
            self.generators.append(generators.random_vivid())
            self.generators.append(generators.striped_color_wheel(hue_stride=20, stripe_size=10))

    def setup(self):
        self.state['cycle'] = 0
        self.state['direction'] = 1
        self.state['loc'] = 0
        self.state['gen_idx'] = 0
        
    def calc_frame(self):
        gen = self.generators[self.state['gen_idx']]
        self.leds[self.state['loc']] = next(gen)
        nloc = self.state['loc'] + self.state['direction']
        if 0 <= nloc < self.calc_n:
            self.state['loc'] = nloc
        else:
            # reached the end increment cycle and reverse direction
            self.state['cycle'] += 1
            self.state['gen_idx'] = self.state['cycle'] % len(self.generators)
            self.state['direction'] *= -1


class Convergent(AnimationBase):
    """ Light marches two at a time and meets in the middle """
    def __init__(self, leds, fill_mode=None, **kwargs):
        super().__init__(leds, **kwargs)
        if self.palette is None:
            self.palette = default_palette(20)
        self.settings['fill_mode'] = fill_mode or trickLED.FILL_MODE_SOLID

    def setup(self):
        if self.generator is not None:
            self.palette.fill_gen(self.generator)
        self.state['insert_points'] = [0, self.calc_n - 1]
        self.state['palette_idx'] = 0
        self.start_cycle()

    def start_cycle(self):
        self.state['movers'] = self.state['insert_points'][:]
        self.leds.fill((0,0,0))
        self.state['palette_idx'] = (self.state['palette_idx'] + 1) % len(self.palette)
        self.state['color'] = self.palette[self.state['palette_idx']]
        for ip in self.state['insert_points']:
            self.leds[ip] = self.state['color']

    def calc_frame(self):
        idir = 1
        mvr = []
        new_insert = False
        new_cycle = False
        for mv in self.state['movers']:
            ni = mv + idir
            idir *= -1
            if 0 <= ni < self.calc_n:
                if not any(self.leds[ni]):
                    self.leds[ni] = self.leds[mv]
                    self.leds[mv] = 0
                    mvr.append(ni)
                elif mv in self.state['insert_points']:
                    new_cycle = True
                else:
                    new_insert = True
            else:
                print("{} + {} out of range".format(mv, idir))
        if new_cycle:
            self.start_cycle()
            return
        if new_insert:
            if self.settings['fill_mode'] == trickLED.FILL_MODE_MULTI:
                self.state['palette_idx'] = (self.state['palette_idx'] + 1) % len(self.palette)
                self.state['color'] = self.palette[self.state['palette_idx']]
            for ip in self.state['insert_points']:
                self.leds[ip] = self.state['color']
            mvr = self.state['insert_points'][:]
        self.state['movers'] = mvr


class Divergent(AnimationBase):
    """ Like Convergent, but not """
    def __init__(self, leds, fill_mode=None, **kwargs):
        super().__init__(leds, **kwargs)
        if self.palette is None:
            self.palette = default_palette(20)
        self.settings['fill_mode'] = fill_mode or trickLED.FILL_MODE_SOLID

    def setup(self):
        if self.generator is not None:
            self.palette.fill_gen(self.generator)
        hwp = self.calc_n // 2
        self.state['insert_points'] = [hwp, hwp+1]
        self.state['palette_idx'] = 0
        self.start_cycle()

    def start_cycle(self):
        self.state['movers'] = self.state['insert_points'][:]
        self.leds.fill((0,0,0))
        self.state['palette_idx'] = (self.state['palette_idx'] + 1) % len(self.palette)
        self.state['color'] = self.palette[self.state['palette_idx']]
        for ip in self.state['insert_points']:
            self.leds[ip] = self.state['color']

    def calc_frame(self):
        idir = -1
        mvr = []
        new_insert = False
        new_cycle = False
        for mv in self.state['movers']:
            ni = mv + idir
            idir *= -1
            if 0 <= ni < self.calc_n:
                if not any(self.leds[ni]):
                    self.leds[ni] = self.leds[mv]
                    self.leds[mv] = 0
                    mvr.append(ni)
                elif mv in self.state['insert_points']:
                    new_cycle = True
                else:
                    new_insert = True
            else:
                new_insert = True
        if new_cycle:
            self.start_cycle()
            return
        if new_insert:
            if self.settings['fill_mode'] == trickLED.FILL_MODE_MULTI:
                self.state['palette_idx'] = (self.state['palette_idx'] + 1) % len(self.palette)
                self.state['color'] = self.palette[self.state['palette_idx']]
            for ip in self.state['insert_points']:
                self.leds[ip] = self.state['color']
            mvr = self.state['insert_points'][:]
        self.state['movers'] = mvr
