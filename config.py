import random
# TODO: Get this outta here!
spinner_choice = random.choice(['aesthetic', 'arc', 'arrow3', 'betaWave', 'balloon',
'bounce', 'bouncingBar', 'circle', 'dots', 'line', 'squish', 'toggle10', 'pong'])

# TODO: Replace these removed soundtracks
soundtrack_files = [
    "talc_soundtrack.mp3",
    "talc_soundtrack2.mp3",
    "talc_soundtrack3.mp3",
    "talc_soundtrack4.mp3",
    # "talc_soundtrack5.mp3",
]

prog = "TALC"
author = "Tyler Weston"
# version = '0.0.5'

size = 1280, 720

USE_PROMPTS = False
USE_OPENAI = False
DETECT_FACES = True
# noise_glitching = False

NUM_SMMRY_SENTENCES = 8
MINIMUM_ARTICLE_LENGTH = 10000

# GLITCH_VIDEOS = False
# GLITCH_VIDEOS_PERCENT = 0.3
USE_MOVIEPY_VIDEO_FX = True
MOVIEPY_VIDEO_FX_PERCENT = 0.9

DEFAULT_IMAGES_PER_SEARCH = 3

CLEANUP_ON_FINISH = True