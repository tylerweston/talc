from PIL import Image
import numpy as np
from moviepy.editor import *
import random

last_frame_xor = np.empty([0])
def xor_frameglitch(clip):
    
    def fl(gf, t):
        global last_frame_xor
        frame = gf(t)
        if last_frame_xor.any():
            lfx = last_frame_xor.copy()
            np.random.shuffle(lfx)
            frame = frame * lfx
        last_frame_xor = frame
        return frame
    return clip.fl(fl)

def shuffle_img(clip):
    def fl(gf, t):
        frame = gf(t)
        if random.random() < 0.9:
            return frame
        nf = frame.copy()
        chunk = random.randint(80000, 160000)
        while True:
            try:
                nf = nf.reshape(-1,chunk)
                break
            except:
                chunk = random.randint(80000, 160000)
        np.random.shuffle(nf)
        nf = nf.reshape(frame.shape)
        return nf
    return clip.fl(fl)

def make_new_title():
    video_title = TextClip(
        "the aleatoric\nlearning channel", 
        font='Amiri-Bold', 
        # fontsize=70, 
        color='white',
        stroke_color='black',
        stroke_width=2, 
        method='label', 
        align='Center', 
        size=(1280, 720)
    )
    video_title_glitched = TextClip(
        "the aleatoric\nlearning channel", 
        font='Amiri-Bold', 
        # fontsize=70, 
        color='white',
        stroke_color='black',
        stroke_width=2, 
        method='label', 
        align='Center', 
        size=(1280, 720)
    )

    video_title.duration = 0.5
    video_title_glitched = video_title_glitched.fx(xor_frameglitch).fx(shuffle_img) #.fx(vfx.fadein, 2.5)
    video_title_glitched.duration = 1.5
    title_comped = concatenate_videoclips([video_title, video_title_glitched, video_title], method="compose")
    title_comped.write_videofile("title.mp4", fps=24, codec='libx264', audio=False, logger=None)

