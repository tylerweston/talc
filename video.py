import random
import math
from PIL import Image
from main import console, spinner_choice
from moviepy.editor import *
import moviepy.video.fx.all as vfx
import pytube
import urllib.parse
import urllib.request
import numpy as np
from moviepy.audio import fx
from config import *
from images import apply_image_fx
import re
import os


def apply_motion(frames):
    # Note we can abstract this a bit since this is repeated code from what we do in video glitches
    # so bounce this out to another function that takes ANY clip, applies a random fx, and then returns that clip
    # Run through three times so some images get even extra glitched
    return_frames = []

    for _ in range(3):
        for frame in frames:
            if (random.random() < 0.8):
                return_frames.append(frame)
                continue
            zoom_ratio = random.random() / 20.0
            video_motion_fx = [
                lambda clip: zoom_out_effect(clip, zoom_ratio=zoom_ratio),
                lambda clip: zoom_in_effect(clip, zoom_ratio=zoom_ratio),
                lambda clip: oneminusglitch(clip),
                lambda clip: pixellate_in_effect(clip),
                lambda clip: pixellate_out_effect(clip),
            ]
            random_func = random.choice(video_motion_fx)
            frame = random_func(frame)
            return_frames.append(frame)
    return return_frames

def oneminusglitch(clip):
    def fl(gf, t):
        frame = gf(t)
        frame = 1 - frame;
        return frame
    return clip.fl(fl)

def zoom_out_effect(clip, zoom_ratio=0.04):
    def effect(get_frame, t):
        img = Image.fromarray(get_frame(t))
        base_size = img.size

        new_size = [
            # if this doesn't work, change 0.8 to 1.2?
            math.ceil(img.size[0] / (0.8 + (zoom_ratio * t))),
            math.ceil(img.size[1] / (0.8 + (zoom_ratio * t)))
        ]

        # The new dimensions must be even.
        new_size[0] = new_size[0] + (new_size[0] % 2)
        new_size[1] = new_size[1] + (new_size[1] % 2)

        img = img.resize(new_size, Image.LANCZOS)

        x = math.ceil((new_size[0] - base_size[0]) / 2)
        y = math.ceil((new_size[1] - base_size[1]) / 2)

        img = img.crop([
            x, y, new_size[0] - x, new_size[1] - y
        ]).resize(base_size, Image.LANCZOS)

        result = np.array(img)
        img.close()

        return result

    return clip.fl(effect)

def zoom_in_effect(clip, zoom_ratio=0.04):
    # From: https://gist.github.com/mowshon/2a0664fab0ae799734594a5e91e518d5
    # Thank you, mowshon!
    def effect(get_frame, t):
        img = Image.fromarray(get_frame(t))
        base_size = img.size

        new_size = [
            math.ceil(img.size[0] * (1 + (zoom_ratio * t))),
            math.ceil(img.size[1] * (1 + (zoom_ratio * t)))
        ]

        # The new dimensions must be even.
        new_size[0] = new_size[0] + (new_size[0] % 2)
        new_size[1] = new_size[1] + (new_size[1] % 2)

        img = img.resize(new_size, Image.LANCZOS)

        x = math.ceil((new_size[0] - base_size[0]) / 2)
        y = math.ceil((new_size[1] - base_size[1]) / 2)

        img = img.crop([
            x, y, new_size[0] - x, new_size[1] - y
        ]).resize(base_size, Image.LANCZOS)

        result = np.array(img)
        img.close()

        return result
    return clip.fl(effect)

def pixellate_in_effect(clip):
    # From: https://stackoverflow.com/questions/47143332/how-to-pixelate-a-square-image-to-256-big-pixels-with-python
    # Thanks Mark Setchell
    def fl(gf, t):
        frame = gf(t)
        target = int(16 * ((t + 1) * 8))
        img = Image.fromarray(frame)
        img_small = img.resize((target,target),resample=Image.BILINEAR)
        res = img_small.resize(img.size, Image.NEAREST)
        return np.array(res)
    return clip.fl(fl)

def pixellate_out_effect(clip):
    # From: https://stackoverflow.com/questions/47143332/how-to-pixelate-a-square-image-to-256-big-pixels-with-python
    # Thanks Mark Setchell
    def fl(gf, t):
        frame = gf(t)
        target = 32 + int(16 + (t * 32))
        img = Image.fromarray(frame)
        img_small = img.resize((target,target),resample=Image.BILINEAR)
        res = img_small.resize(img.size, Image.NEAREST)
        return np.array(res)
    return clip.fl(fl)

def comp_video(images_list, random_video_clips, title, soundfile_name):
    # Create video
    with console.status("[bold green]Creating video...", spinner=spinner_choice):
        title_card_clip = ImageClip("title_card.png", duration=2)
        # frames = [title_card_clip]
        frames = []
        for f in images_list:
            try:
                new_clip = ImageClip(f, duration=random.random() * 2.5)
                new_clip.set_fps(24)
                frames.append(new_clip)
            except:
                continue
        # apply some random video fx to frames
        frames = apply_image_fx(frames)
        frames = apply_motion(frames)

        frames.extend(random_video_clips)
        random.shuffle(frames)
        # TextClip.list('font')
        video_title = TextClip(
            title, 
            font='Amiri-Bold', 
            # fontsize=70, 
            color='white',
            stroke_color='black',
            stroke_width=2, 
            method='label', 
            align='Center', 
            size=(1280, 720)
        )
        title_duration = random.random() * 2.5 + 1
        video_clip = random.choice(frames)
        video_clip = video_clip.set_duration(title_duration)
        video_title = video_title.set_duration(title_duration)
        video_comped = CompositeVideoClip([video_clip, video_title.set_pos(("center", "bottom"))])
        video_comped = video_comped.set_duration(title_duration)

        frames = [title_card_clip, video_comped] + frames
        visual_clip = concatenate_videoclips(frames, method="compose")

        # Add some silence to end of narration
        narration_clip = AudioFileClip(soundfile_name)

        def silence_function(x):
            return 0

        silence_clip = AudioClip(make_frame=silence_function, duration=3)
        composite_narration_clip = concatenate_audioclips([narration_clip, silence_clip])

        # Generate soundtrack
        chosen_soundtrack = "soundtracks/" + random.choice(soundtrack_files)
        console.print(f"Using soundtrack: [bold green]{chosen_soundtrack}")
        soundtrack_clip = AudioFileClip(chosen_soundtrack)
        soundtrack_start_point = random.randint(
            0, int(soundtrack_clip.duration - composite_narration_clip.duration)
        )
        soundtrack_clip = soundtrack_clip.subclip(
            soundtrack_start_point,
            soundtrack_start_point + composite_narration_clip.duration,
        )

        # Hack for now:
        if (
            chosen_soundtrack == "soundtracks/talc_soundtrack3.wav"
            or chosen_soundtrack == "soundtracks/talc_soundtrack5.wav"
        ):
            soundtrack_clip = soundtrack_clip.volumex(0.08)
        else:
            soundtrack_clip = soundtrack_clip.volumex(0.15)

        soundtrack_clip = fx.all.audio_fadein(soundtrack_clip, 2)
        soundtrack_clip = fx.all.audio_fadeout(soundtrack_clip, 2)

        # soundtrack_clip = soundtrack_clip.fl(audio_noiseglitch)
        # soundtrack_clip = soundtrack_clip.fl(audio_fuzz)

        # Compose narration and sountrack
        composite_narration_clip = CompositeAudioClip(
            [composite_narration_clip, soundtrack_clip]
        )
        composite_narration_clip = fx.all.audio_fadeout(composite_narration_clip, 2)

        # Trim clip and export
        visual_clip = visual_clip.set_end(int(narration_clip.duration) + 1)
        visual_clip = visual_clip.set_audio(composite_narration_clip)
        movie_title = urllib.parse.unquote(title)
        movie_title = "".join(ch for ch in movie_title if (ch.isalnum() or ch in "._- "))
        visual_clip.write_videofile(
            f"finished/{movie_title}.mp4",
            codec="libx264",
            audio_codec="aac",
            temp_audiofile="temp-audio.m4a",
            remove_temp=True,
            fps=24,
            logger=None,
        )

        # print("Glitching video...")
        # glitchart.mp4(f"finished/{movie_title}.mp4")
        # print("Done glitching video...")
        # # TODO:
        # # Now, we have a glitched copy and a regular copy, we should splice MOSTLY the unglitched copy,
        # # but also, a little bit of the glitched copy together, add the audio back in, and press it one
        # # more time?
        for f in frames:
            try:
                f.close()
            except:
                pass
    return movie_title

def get_random_clips(keywords, wiki_page_title):
    # Grab random youtube video clips
    random_video_clips = []
    number_of_random_videos_to_get = 25
    number_got = 0

    try:
        os.mkdir("videos")
    except FileExistsError:
        # directory already exists
        pass

    # TODO:
    #   - Keep track of number of tries / keyword combos checked, once exhausted, if we don't have enough
    #   videos, just keep going with whatever we have.

    with console.status("[bold green]Getting random videos...", spinner=spinner_choice):
        while number_got < number_of_random_videos_to_get:
            # Search for list of videos
            random_keyword_combo = None
            if random.random() < 0.75:
                random_keyword_combo = wiki_page_title + " " + random.choice(keywords)
            else:
                random_keyword_combo = (
                    random.choice(keywords) + " " + random.choice(keywords)
                )
            # print(f"Keywords: {random_keyword_combo}")
            query = urllib.parse.quote(random_keyword_combo)
            url = "https://www.youtube.com/results?search_query=" + query
            response = urllib.request.urlopen(url)
            html = response.read()
            # try:
            video_ids = re.findall(r"watch\?v=(\S{11})", html.decode())
            if len(video_ids) == 0:
                continue
                # print(f"Found videos: {video_ids}")
            # except:
            #     continue
            # video_ids now contains the files we can download
            # so choose a random one and download it

            # Make a few tries from each collection
            video_tries = 0
            need_retry = True
            while video_tries < 10 and need_retry:
                rand_vid_id = random.choice(video_ids)
                url = f"https://www.youtube.com/watch?v={rand_vid_id}"
                try:
                    youtube = pytube.YouTube(url)
                    if youtube.length > 600 or youtube.length < 5:
                        # print("Video too long")
                        video_tries += 1
                        continue
                    else:
                        need_retry = False
                except TypeError:
                    video_tries += 1
                    continue

            if need_retry:
                continue

            try:
                # video = youtube.streams.filter(res="720p").first()

                video = youtube.streams.filter(mime_type="video/mp4").first()
            except Exception as e:
                console.print("[red]Warning[/red]: Can't get video of correct resolution")
                console.print(str(e))
                continue

            if video is not None:
                path_to_download = f"videos/{video.default_filename}"
                try:
                    video.download("videos")
                except urllib.error.HTTPError as e:
                    console.print("[red]Warning[/red]: Error downloading video clips")
                    console.print(str(e))
                    continue
                original_clip = VideoFileClip(path_to_download)

                # # TODO: This hangs when we try to compose the video later
                # if GLITCH_VIDEOS:
                #     if random.random() <= GLITCH_VIDEOS_PERCENT:
                #         console.print("Glitching video...")
                #         glitchart.mp4(f'"{path_to_download}"', inplace=True)
                #         console.print("Done glitching video...")
                # # # TODO:
                # # # Now, we have a glitched copy and a regular copy, we should splice MOSTLY the unglitched copy,
                # # # but also, a little bit of the glitched copy together, add the audio back in, and press it one
                # # # more time?

                number_got += 1
                # Grab a few snippets from the video
                for _ in range(0, 2):

                    start_time = random.randint(0, max(1, youtube.length - 10))
                    end_time = min(youtube.length, start_time + random.randint(1, 3))
                    random_youtube_subclip = original_clip.subclip(start_time, end_time)
                    random_youtube_subclip = random_youtube_subclip.set_fps(24)
                    random_youtube_subclip = random_youtube_subclip.resize(newsize=size)
                    # sometimes apply a moviepy vfx
                    if USE_MOVIEPY_VIDEO_FX and random.random() <= MOVIEPY_VIDEO_FX_PERCENT:
                        # choose a random effect from all available moviepy vfx
                        param1 = random.random()
                        param2 = random.random()
                        # choose random x and y values that are within the size of the clip
                        x = random.randint(0, size[0] - 1)
                        y = random.randint(0, size[1] - 1)
                        # choose another set of random x and y values that are within the size of the clip
                        x2 = random.randint(0, size[0] - 1)
                        y2 = random.randint(0, size[1] - 1)
                        video_fx_funcs = [
                            lambda clip: clip.fx(vfx.accel_decel, new_duration=None, abruptness=param1, soonness=param2),
                            lambda clip: clip.fx(vfx.blackwhite),
                            lambda clip: clip.fx(vfx.blackwhite, RGB='CRT_phosphor'),
                            lambda clip: clip.fx(vfx.colorx, param1),
                            lambda clip: clip.fx(vfx.freeze, total_duration=param1),
                            lambda clip: clip.fx(vfx.freeze_region, t=param1, region=(x, y , x2, y2)),
                            lambda clip: clip.fx(vfx.gamma_corr, gamma=param1),
                            lambda clip: clip.fx(vfx.invert_colors),
                            lambda clip: clip.fx(vfx.mirror_x),
                            lambda clip: clip.fx(vfx.mirror_y),
                            lambda clip: clip.fx(vfx.painting, 1+(param1/2),param2/ 100.0),
                            lambda clip: clip.fx(vfx.speedx, factor=param1*2),
                            lambda clip: clip.fx(vfx.supersample, d=int((param1+1) * 10), nframes=int((param2+1) * 30)),               
                            lambda clip: clip.fx(vfx.time_mirror),
                            lambda clip: clip.fx(vfx.time_symmetrize),
                            lambda clip: clip.fx(oneminusglitch),
                        ]    
                        random_func = random.choice(video_fx_funcs)
                        random_youtube_subclip = random_func(random_youtube_subclip)
                    random_video_clips.append(random_youtube_subclip)
            else:
                console.print("[red]Warning[/red]: Couldn't get video")
                continue

    console.print(f"Got [bold green]{len(random_video_clips)}[/bold green] videos")
    return random_video_clips
