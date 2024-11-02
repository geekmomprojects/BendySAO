import machine
import time
import sys

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

import trickLED
import animations
import generators


#------------- Default Code --------------------

## HAL / devices here

from machine import I2C, Pin
import time

PETAL_ADDRESS      = 0x00
TOUCHWHEEL_ADDRESS = 0x54

# Testing options
bootLED = Pin("LED", Pin.OUT)
bootLED.on()

## buttons
buttonA = Pin(8, Pin.IN, Pin.PULL_UP)
buttonB = Pin(9, Pin.IN, Pin.PULL_UP)
buttonC = Pin(28, Pin.IN, Pin.PULL_UP)

## GPIOs
gpio11 = Pin(7, Pin.OUT)
gpio12 = Pin(6, Pin.OUT)

gpio21 = Pin(5, Pin.OUT)
gpio22 = Pin(4, Pin.OUT)

gpio31 = Pin(3, Pin.OUT)
gpio32 = Pin(2, Pin.OUT)

gpio41 = Pin(22, Pin.OUT)
gpio42 = Pin(21, Pin.OUT)

gpio51 = Pin(20, Pin.OUT)
gpio52 = Pin(19, Pin.OUT)

gpio61 = Pin(18, Pin.OUT)
gpio62 = Pin(17, Pin.OUT)

GPIOs = [ [gpio11, gpio12], [gpio21, gpio22], [gpio31, gpio32], [gpio41, gpio42],  [gpio51, gpio52], [gpio61, gpio62] ]


## GPIOs

## Initialize I2C peripherals
i2c0 = I2C(0, sda=Pin(0), scl=Pin(1), freq=400_000)
i2c1 = I2C(1, sda=Pin(26), scl=Pin(27), freq=400_000)

def which_bus_has_device_id(i2c_id, debug=False):
    '''Returns a list of i2c bus objects that have the requested id on them.
    Note this can be of length 0, 1, or 2 depending on which I2C bus the id is found'''

    i2c0_bus = i2c0.scan() 
    if debug:
        print("Bus 0: ")
        print(str([hex(x) for x in i2c0_bus]))

    i2c1_bus = i2c1.scan()
    if debug:
        print("Bus 1: ")
        print(str([hex(x) for x in i2c1_bus]))

    busses = []
    if i2c_id in i2c0_bus:
        busses.append(i2c0)
    if i2c_id in i2c1_bus:
        busses.append(i2c1)

    return(busses)


def petal_init(bus):
    """configure the petal SAO"""
    bus.writeto_mem(PETAL_ADDRESS, 0x09, bytes([0x00]))  ## raw pixel mode (not 7-seg) 
    bus.writeto_mem(PETAL_ADDRESS, 0x0A, bytes([0x09]))  ## intensity (of 16) 
    bus.writeto_mem(PETAL_ADDRESS, 0x0B, bytes([0x07]))  ## enable all segments
    bus.writeto_mem(PETAL_ADDRESS, 0x0C, bytes([0x81]))  ## undo shutdown bits 
    bus.writeto_mem(PETAL_ADDRESS, 0x0D, bytes([0x00]))  ##  
    bus.writeto_mem(PETAL_ADDRESS, 0x0E, bytes([0x00]))  ## no crazy features (default?) 
    bus.writeto_mem(PETAL_ADDRESS, 0x0F, bytes([0x00]))  ## turn off display test mode 

## can't use scan logic for petal b/c it's at address 0
## so wrapping the init routine it try: blocks should also work
## later on can test if petal_bus is None
petal_bus = None
try:
    petal_init(i2c0)
    petal_bus = i2c0
except: 
    pass
try:
    petal_init(i2c1)
    petal_bus = i2c1
except:
    pass
if not petal_bus:
    print(f"Warning: Petal not found.")


## waiting for wheel with a yellow light
if petal_bus:
    petal_bus.writeto_mem(PETAL_ADDRESS, 3, bytes([0x80]))
    petal_bus.writeto_mem(PETAL_ADDRESS, 2, bytes([0x80]))

## touchwheel last, with a wait loop,  b/c it doesn't init until animation is over
## probably need to implement a timeout here?
touchwheel_bus = None
touchwheel_counter = 0
while not touchwheel_bus:
    try:
        touchwheel_bus =  which_bus_has_device_id(0x54)[0]
    except:
        pass
    time.sleep_ms(100)
    touchwheel_counter = touchwheel_counter + 1
    if touchwheel_counter > 50:
        break
if not touchwheel_bus:
    print(f"Warning: Touchwheel not found.")


def touchwheel_read(bus):
    """Returns 0 for no touch, 1-255 clockwise around the circle from the south"""
    return(touchwheel_bus.readfrom_mem(84, 0, 1)[0])

def touchwheel_rgb(bus, r, g, b):
    """RGB color on the central display.  Each 0-255"""
    touchwheel_bus.writeto_mem(84, 15, bytes([r]))
    touchwheel_bus.writeto_mem(84, 16, bytes([g]))
    touchwheel_bus.writeto_mem(84, 17, bytes([b]))


## goes green if wheel configured
if touchwheel_bus and petal_bus:
    petal_bus.writeto_mem(PETAL_ADDRESS, 3, bytes([0x00]))
if petal_bus:
    petal_bus.writeto_mem(PETAL_ADDRESS, 2, bytes([0x80]))
    time.sleep_ms(200)
    petal_bus.writeto_mem(PETAL_ADDRESS, 2, bytes([0x00]))





#------------- End Default Code ----------------




def play(animation, n_frames, **kwargs):
    try:
        asyncio.run(animation.play(n_frames, **kwargs))
    finally:
        # needed to reset state otherwise the animations will get all jumbled when ended with CTRL+C
        asyncio.new_event_loop()
        animation.leds.fill((0,0,0))
        animation.leds.write()
        time.sleep(1)


def demo_animations(leds, n_frames=200):
    print('Demonstrating animations press CTRL+C to cancel... or wait about 2 minutes.')
    # store repeat_n so we can set it back if we change it
    leds_repeat_n = leds.repeat_n
    # LitBits
    ani = animations.LitBits(leds)
    print('LitBits settings: default')
    play(ani, n_frames)
    print('LitBits settings: lit_percent=50')
    play(ani, n_frames, lit_percent=50)
    
    # NextGen
    ani = animations.NextGen(leds)
    print('NextGen settings: default')
    play(ani, n_frames)
    print('NextGen settings: blanks=2, interval=150')
    play(ani, n_frames, blanks=2, interval=150)
    
    # Jitter
    ani = animations.Jitter(leds)
    print('Jitter settings: default')
    play(ani, n_frames)
    print('Jitter settings: background=0x020212, fill_mode=FILL_MODE_SOLID')
    ani.generator = generators.random_vivid()
    play(ani, n_frames, background=0x020212, fill_mode=trickLED.FILL_MODE_SOLID)
    
    # SideSwipe
    ani = animations.SideSwipe(leds)
    print('SideSwipe settings: default')
    play(ani, n_frames)

    # Divergent
    ani = animations.Divergent(leds)
    print('Divergent settings: default')
    play(ani, n_frames)
    print('Divergent settings: fill_mode=FILL_MODE_MULTI')
    play(ani, n_frames, fill_mode=trickLED.FILL_MODE_MULTI)

    # Convergent
    ani = animations.Convergent(leds)
    print('Convergent settings: default')
    play(ani, n_frames)
    print('Convergent settings: fill_mode=FILL_MODE_MULTI')
    play(ani, n_frames, fill_mode=trickLED.FILL_MODE_MULTI)

    if leds.n > 60 and leds.repeat_n is None:
        print('Setting leds.repeat_n = 40, set it back to {} if you cancel the demo'.format(leds_repeat_n))
        leds.repeat_n = 40

    if 'trickLED.animations32' in sys.modules:
        # Fire
        ani = animations32.Fire(leds)
        print('Fire settings: default')
        play(ani, n_frames)

        # Conjuction
        ani = animations32.Conjunction(leds)
        print('Conjuction settings: default')
        play(ani, n_frames)
    
    if leds.repeat_n != leds_repeat_n:
        leds.repeat_n = leds_repeat_n

def demo_generators(leds, n_frames=200):
    print('Demonstrating generators:')
    # stepped_color_wheel  
    print('stepped_color_wheel')
    ani = animations.NextGen(leds, generator = generators.stepped_color_wheel())
    play(ani, n_frames)
    
    # striped_color_wheel
    print('stepped_color_wheel')
    ani.generator = generators.striped_color_wheel()
    play(ani, n_frames)
    print('stepped_color_wheel(stripe_size=1)')
    ani.generator = generators.striped_color_wheel(stripe_size=1)
    play(ani, n_frames)
    
    #fading_color_wheel
    print('fading_color_wheel(mode=FADE_OUT) (default)')
    ani.generator = generators.fading_color_wheel()
    play(ani, n_frames)
    print('fading_color_wheel(mode=FADE_IN)')
    ani.generator = generators.fading_color_wheel(mode=trickLED.FADE_IN)
    play(ani, n_frames)
    print('fading_color_wheel(mode=FADE_IN_OUT)')
    ani.generator = generators.fading_color_wheel(mode=trickLED.FADE_IN_OUT)
    play(ani, n_frames)
    
    # color_compliment
    print('color_compliment()')
    ani.generator = generators.color_compliment(stripe_size=10)
    play(ani, n_frames)
    
    # random_vivid
    print('random_vivid()')
    ani.generator = generators.random_vivid()
    play(ani, n_frames)
    
    # random_pastel
    print('random_pastel()')
    ani.generator = generators.random_pastel()
    play(ani, n_frames)
    print('random_pastel(mask=(127, 0, 31))')
    ani.generator = generators.random_pastel(mask=(127, 0, 31))
    play(ani, n_frames)
    print('random_pastel(mask=(0, 63, 63))')
    ani.generator = generators.random_pastel(mask=(0, 63, 63))
    play(ani, n_frames)


led_pin = gpio11
tl = trickLED.TrickLED(led_pin, 12)

while True:
    demo_animations(tl, 300)
    demo_generators(tl, 150)


