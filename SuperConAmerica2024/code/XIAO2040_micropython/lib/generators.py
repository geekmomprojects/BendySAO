import trickLED
from random import getrandbits 
try:
    from random import randrange
except ImportError:
    randrange = trickLED.randrange


def stepped_color_wheel(hue_stride=10, stripe_size=20, start_hue=0):
    """
    Generator that cycles through the color wheel creating stripes that fade to
    a slightly different hue.

    :param hue_stride: Number of steps on the color wheel to skip, negative will go in reverse.
    :param stripe_size: Size of fading stripe
    :param start_hue: Starting hue on color wheel
    :return: color generator
    """
    if hue_stride == 0:
        hue_stride = 1
    hue = start_hue

    ho = - hue_stride
    while True:
        brightness = trickLED.global_setings.get('brightness')
        db = brightness >> 2
        c1 = trickLED.color_wheel(hue, brightness)
        c2 = trickLED.color_wheel((hue - ho) % 255, db)
        inc = trickLED.step_inc(c1, c2, stripe_size - 1)
        for i in range(stripe_size):
            incs = [v * i for v in inc]
            yield tuple(map(trickLED.add8, c1, incs))
        hue = (hue + hue_stride) % 255


def striped_color_wheel(hue_stride=10, stripe_size=10, start_hue=0):
    """
    Generator that cycles through the color wheel creating stripes of the same color before moving to next hue.

    :param hue_stride: Number of steps on the color wheel to skip, negative will go in reverse.
    :param stripe_size: Number of times to repeat each color
    :param start_hue: Starting hue on color wheel
    :return: color generator
    """
    hue = start_hue
    if hue_stride == 0:
        hue_stride = 1
    while True:
        col = trickLED.color_wheel(hue, trickLED.global_setings.get('brightness'))
        for i in range(stripe_size):
            yield col
        hue = (hue + hue_stride) % 255


def fading_color_wheel(hue_stride=10, stripe_size=20, start_hue=0, mode=trickLED.FADE_OUT):
    """
    Cycle through color wheel while fading in and out before moving to next hue.

    :param hue_stride: Number of steps on the color wheel to skip. Negative will go in reverse
    :param strip_size: Length of the fade in, fade out cycle where hue remains the same
    :param start_hue: Location on color wheel to begin
    :param mode: Fade in, fade out, fade in then out
    :return: color generator
    """
    if stripe_size <= 1:
        raise ValueError('stripe_size must be > 1 to fade')
    hue = start_hue
    # calculate brightness values
    if mode == trickLED.FADE_IN_OUT:
        cs = 127.5 / (stripe_size - 1)
        co = 0
        bv = [2 + int(trickLED.sin8(co + i * cs) * 253) for i in range(stripe_size)]
    else:
        if mode == trickLED.FADE_IN:
            cs = 63.75 / (stripe_size - 1)
            co = 63.75
        else:
            cs = 63.75 / (stripe_size - 1)
            co = 0
        bv = [255 - int(trickLED.sin8(co + i * cs) * 253) for i in range(stripe_size)]
    if hue_stride == 0:
        hue_stride = 1
    while True:
        for i in range(stripe_size):
            yield trickLED.color_wheel(hue, bv[i])
        hue = (hue + hue_stride) % 255


def color_compliment(hue_stride=10, stripe_size=1, start_hue=0):
    """
    Step through color wheel alternating between a color and its compliment

    :param hue_stride:
    :param stripe_size: Number of times to repeat each color
    :param start_hue: Location on color wheel to begin
    :return color generator
    """
    hue = start_hue
    while True:
        col = trickLED.color_wheel(hue, trickLED.global_setings.get('brightness'))
        for i in range(stripe_size):
            yield col
        col = trickLED.color_wheel((hue + 127) % 255, trickLED.global_setings.get('brightness'))
        for i in range(stripe_size):
            yield col
        hue = (hue + hue_stride) % 255


def random_vivid():
    """
    Generate random vivid colors by filling only 2 channels.
    :return: color generator
    """
    shifts = ((16, 8),  # (p, s, 0)  red-yellow-green
              (8, 0),   # (0, p, s)  green-aqua-blue
              (0, 16))  # (s, 0, p)  blue-purple-red
    while True:
        brightness = trickLED.global_setings.get('brightness')
        cov = randrange(0, 2)
        prime = randrange(1, brightness)
        second = brightness - prime
        s = shifts[cov]
        val = prime << s[0] | second << s[1]
        yield tuple(val.to_bytes(3, 'big'))


def random_pastel(bpp=3, mask=None):
    """
    Generate random pastel colors.

    :param bpp: Bytes per pixel
    :param mask: Bit masks to control hue. (255, 0, 63) would give red to purple colors.
    :return: color generator
    """
    mi = 0
    bc = bpp * 8
    if mask:
        if bpp != len(mask):
            raise ValueError('The mask must contain the same number of items as bytes to be returned.')
        for i in range(bpp):
            mi = (mi << 8) | mask[i]
    else:
        mi = 2 ** bc - 1
    while True:
        val = getrandbits(bc) & mi
        yield tuple(val.to_bytes(bpp, 'big'))
