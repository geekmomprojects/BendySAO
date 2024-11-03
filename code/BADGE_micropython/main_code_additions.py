### Add the following lines of code to "main.py" on the badge to run
### animations in a background thread

###-------- Add Import Statements to top of main.py ----------------

### Bendy SAO Imports ###
import machine
import time
import sys
import _thread

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

import trickLED
import animations
import generators

#--- Specify the LED signal pin for the Bendy SAO
# Assumes Bendy SAO is on the first badge spoke, but 
# if you want to put it on port X, set led_pin = gpioX1
led_pin = gpio11
tl = trickLED.TrickLED(led_pin, 12)

### End Bendy SAO Imports ###

### End Bendy SAO Imports

###--------- Add code below to main.py (before main loop if there is one)
### Bendy SAO Animation Functions (taken with minor changes from https://gitlab.com/scottrbailey/trickLED)
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

def repeat_animations(leds, reps=200):
    demo_animations(leds, reps)
    demo_generators(leds, reps)


# Create thread to run animations in the background 
_thread.start_new_thread(repeat_animations, [tl])

###---- End bendy SAO Animations

# no functionality in while loop yet, but there could be
while True:
    time.sleep(1)
    pass