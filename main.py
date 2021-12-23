# TODO:
#   - More sound options? Add some random sounds
#   - Better article selection somehow?
#   - Voice glitches
#   - Different soundtracks to choose from
#   - Get different voices?
#   - Refactor code out of one giant script
#   - Organize files
#   - More soundtracks
#   - Strip out invalid filename characters such as :, ?, *, and others
#   - How to add some more sound fx to the videos
#       - https://freesound.org/docs/api/overview.html
#       - Needs to be less specific, maybe only search ONE keyword at a time?
#       - If the API doesn't return anything, ON TO THE NEXT
#   - Do some video glitching / overlay sort of stuff? Look into pixellib
#       - Semantic segmentation to remove video foreground and overlay over
#         some other clip we have?

import os
import sys
import argparse
from rich.console import Console

# This is all we need if we want to just get --help or --version so check for those first
args = [s.lower() for s in sys.argv[1:]]
if not ("--help" in args or "-h" in args or "--version" in args or "-v" in args):


    import json
    import random
    import re
    import math
    import shutil
    import urllib.parse
    import urllib.request
    from hashlib import sha1
    from datetime import datetime
    import nltk

    # import glitchart

    import numpy as np
    import pyttsx3
    import pytube
    import requests
    import openai
    import cv2

    from PIL import Image, ImageOps
    from bs4 import BeautifulSoup
    from glitch_this import ImageGlitcher
    from google_images_download import google_images_download
    from moviepy.audio import fx
    # from moviepy.decorators import audio_video_fx
    from moviepy.editor import *
    import moviepy.video.fx.all as vfx
    from pixelsort import pixelsort
    from decouple import UndefinedValueError, config

    from rich.progress import track
    # Suppress tensorflow warnings, tf is imported by pixellib
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    from pixellib.semantic import semantic_segmentation
    from nltk.corpus import wordnet
    from nltk.corpus import stopwords


USE_PROMPTS = False
USE_OPENAI = False
NUM_SMMRY_SENTENCES = 12
CLEANUP_ON_FINISH = True
MINIMUM_ARTICLE_LENGTH = 10000
GLITCH_VIDEOS = False
GLITCH_VIDEOS_PERCENT = 0.3
DETECT_FACES = True
USE_MOVIEPY_VIDEO_FX = True
noise_glitching = False
MOVIEPY_VIDEO_FX_PERCENT = 0.7

spinner_choice = random.choice(['aesthetic', 'arc', 'arrow3', 'betaWave', 'balloon',
'bounce', 'bouncingBar', 'circle', 'dots', 'line', 'squish', 'toggle10', 'pong'])

size = 1280, 720
console = Console()
__prog__ = "TALC"
__author__ = "Tyler Weston"
__version__ = '0.0.5'

if USE_OPENAI:
    try:
        openai.api_key = config("OPENAI_API_KEY")
    except UndefinedValueError as e:
        console.print("[bold red]Error[/bold red]: Please set OPENAI_API_KEY in your .env file to use open ai")
        console.print(e)
        exit(0)

soundtrack_files = [
    "talc_soundtrack.mp3",
    "talc_soundtrack2.mp3",
    "talc_soundtrack3.mp3",
    "talc_soundtrack4.mp3",
    "talc_soundtrack5.mp3",
]




def audio_noiseglitch(clip):
    def glitching(gf, t):
        global noise_glitching
        gft = gf(t)

        if noise_glitching:
            if random.random() < 0.2:
                noise_glitching = False

        if not noise_glitching:
            if random.random() < 0.1:
                noise_glitching = True

        if noise_glitching:
            return random.random() * 2 - 1
        else:
            return gft

    return clip.fl(glitching, keep_duration=True)


# def audio_fuzz(clip):
#
#     def fuzzing(gf, t):
#         gft = gf(t)
#         if random.random() < 0.5:
#             if gft < -0.7:
#                 gft = -1
#             if gft > 0.7:
#                 gft = 1
#         return gft
#
#     return clip.fl(fuzzing, keep_duration=True)


def get_article(use_article=None):
    # print("Finding random Wikipedia article", end="")
    with console.status("[bold green]Finding random Wikipedia article...",spinner=spinner_choice):
        while True:
            if use_article is None:
                # Get random wikipedia page
                wiki_page = requests.get(
                    "https://en.wikipedia.org/api/rest_v1/page/random/html"
                )
                soup = BeautifulSoup(wiki_page.content, "html.parser")
                # Extract title
                # TODO: Sometimes this will fail? Just grab a new random html!
                page_link = soup.find("link", href=True)["href"]
                title = page_link.split("/")[-1]
            else:
                title = use_article

            # Get text content of page
            text_content = requests.get(
                f"https://en.wikipedia.org/w/api.php?action=query&origin=*&prop=extracts&explaintext&titles={title}&format=json"
            )
            text_json = json.loads(text_content.content)
            wiki_page_content = text_json["query"]["pages"]
            _, value = list(wiki_page_content.items())[0]
            try:
                wiki_page_title = value["title"]
                wiki_page_content = value["extract"]
            except KeyError as ke:
                console.print("[bold red]Warning[/bold red]: Problem getting article, trying again")
                console.print(str(ke))
                console.print(value)
                continue
            # Remove everything after == References ==
            wiki_page_content = wiki_page_content.split("== References ==")[0].strip()
            # TODO: Refactor, this logic below is confusing
            if use_article is None and len(wiki_page_content) < MINIMUM_ARTICLE_LENGTH:
                # this article is too short, but we can ignore this if we've provided the article.
                continue
            else:
                # We have a good article, either it's the right length or we're using a provided article
                if USE_PROMPTS:
                    console.print(f"\naccept article {wiki_page_title}? y/n:", end='')
                    res = input()
                    if res.lower() == 'n':
                        continue
                break

    # TODOne? Remove bad punctuation from wiki_page_title!
    # wiki_page_title = re.sub(r'[\W\s]+', '', wiki_page_title)
    console.print(f"\nFound article [bold green]{wiki_page_title}")

    # Remove headers
    wiki_page_content = re.sub("===.*===", "", wiki_page_content)
    wiki_page_content = re.sub("==.*==", "", wiki_page_content)

    return title, wiki_page_title, wiki_page_content

def summarize_article(wiki_page_content):
    # Summarize

    # • SM_API_KEY=N	            Required, your API key.
    # • SM_URL=X	                Optional, the webpage to summarize.
    # • SM_LENGTH=N	                Optional, the number of sentences returned, default 7.
    # • SM_KEYWORD_COUNT=N	        Optional, N the number of keywords to return.
    # • SM_WITH_BREAK	            Optional, inserts the string [BREAK] between sentences.
    # • SM_WITH_ENCODE	            Optional, converts HTML entities to their applicable chars.
    # • SM_IGNORE_LENGTH	        Optional, returns summary regardless of quality or length.
    # • SM_QUOTE_AVOID	            Optional, sentences with quotations will be excluded.
    # • SM_QUESTION_AVOID	        Optional, sentences with question will be excluded.
    # • SM_EXCLAMATION_AVOID	    Optional, sentences with exclamation marks will be excluded.

    API_ENDPOINT = "https://api.smmry.com"
    try:
        API_KEY = config("SMMRY_API_KEY")
    except UndefinedValueError as e:
        console.print("[bold red]Error[/bold red]: Please set SMMRY_API_KEY in your .env file to use smmry")
        console.print(e)
        exit(0)


    data = {"sm_api_input": wiki_page_content}
    params = {
        "SM_API_KEY": API_KEY,
        "SM_LENGTH": NUM_SMMRY_SENTENCES,
        "SM_KEYWORD_COUNT": 14,
        # "SM_QUOTE_AVOID": True,
        # "SM_QUESTION_AVOID": True,
    }
    header_params = {"Expect": "100-continue"}
    smmry_response = requests.post(
        url=API_ENDPOINT, params=params, data=data, headers=header_params
    )

    smmry_json = json.loads(smmry_response.content)
    try:
        summary = smmry_json["sm_api_content"]
        keywords = smmry_json["sm_api_keyword_array"]
    except KeyError as e:
        console.print("[bold red]Error[/bold red]: Problem with results from smmry API!")
        console.print(str(e))
        exit(1)
    
    keywords = [urllib.parse.unquote(k) for k in keywords]
   
    # # Read in remove keywords from file
    # with open("remove_keywords") as f:
    #     content = f.readlines()
    # remove_keywords_list = [x.strip() for x in content]
    remove_keywords_list = list(set(stopwords.words("english")))

    # Remove not useful keywords
    keywords = [k for k in keywords if k.lower() not in remove_keywords_list]
    for _ in range(5):
        syn = get_synonyms(random.choice(keywords))
        if len(syn) == 0:
            continue
        new_syn = random.choice(syn)
        keywords.append(new_syn)
    
    # remove duplicates
    keywords = list(set(keywords))

    # Generate summary hash, use first 12 hex digits of a
    # SHA1 hash generated from the summary text
    summary_hash = sha1()
    summary_hash.update(summary.encode("utf-8"))
    summary_hash_text = str(summary_hash.hexdigest())[:12]
    console.print(f"Got hash: [bold green]{summary_hash_text}")

    # remove all angle brackets from summary, youtube descriptions don't like them
    summary = re.sub(r'(<*>*)*', '', summary)
    return keywords, summary, summary_hash_text

def get_synonyms(word):
    # Get synonyms
    synonyms = []
    for syn in wordnet.synsets(word):
        for l in syn.lemmas():
            synonyms.append(l.name())

    syns = list(set(synonyms))
    # for each word in syns, replace _ with space
    syns = [re.sub("_", " ", s) for s in syns]
    return syns

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
            try:
                video_ids = re.findall(r"watch\?v=(\S{11})", html.decode())
                if len(video_ids) == 0:
                    continue
                # print(f"Found videos: {video_ids}")
            except:
                continue
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
                for i in range(0, 2):

                    start_time = random.randint(0, min(1, youtube.length - 10))
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
                        ]    
                        random_func = random.choice(video_fx_funcs)
                        random_youtube_subclip = random_func(random_youtube_subclip)
                    random_video_clips.append(random_youtube_subclip)
            else:
                console.print("[red]Warning[/red]: Couldn't get video")
                continue

    console.print(f"Got [bold green]{len(random_video_clips)}[/bold green] videos")
    return random_video_clips

def apply_moviefx(clip):

    pass

def get_images(keywords, wiki_page_title, args=args):
    # Get images based on keywords
    with console.status("[bold green]Getting random images...",spinner=spinner_choice):
        response = google_images_download.googleimagesdownload()

        # make most of the keywords based on the article title
        img_search_keywords = [wiki_page_title + " " + k for k in keywords]
        # Some based on the first keyword
        for _ in range(6):
            img_search_keywords.append(keywords[0] + " " + random.choice(keywords))
        # and some a bit more random
        for _ in range(6):
            img_search_keywords.append(
                random.choice(keywords) + " " + random.choice(keywords)
            )

        # remove duplicates
        img_search_keywords = list(set(img_search_keywords))

        keywords_str = ",".join(img_search_keywords)
        keywords_str = keywords_str.replace(':', '')
        arguments = {
            "keywords": keywords_str,
            "limit": args.images_per_search,
            "print_urls": False,
            "silent_mode": True,
        }
        paths = response.download(arguments)
        image_paths = paths  # Our list of all images we've downloaded
        images_list = []
        for _, v in image_paths[0].items():
            images_list.extend(v)
        random.shuffle(images_list)

        # Only keep .jpeg or .jpg images
        images_list = [i for i in images_list if ".jp" in i]
    console.print(f"Got [bold green]{len(images_list)}[/bold green] images")
    return images_list

def get_audio():
    # TODO: get random audio clips to splice into video
    pass

def detect_and_glitch_semantic(images_list):
    # with console.status("[bold green]Performing semantic glitching...",spinner=spinner_choice):
    segment_image = semantic_segmentation()
    segment_image.load_pascalvoc_model("deeplabv3_xception_tf_dim_ordering_tf_kernels.h5")
    interval_func_choices = ["random", "edges", "threshold", "waves"]
    sorting_func_choices = [
        "lightness",
        "hue",
        "saturation",
        "intensity",
        "minimum",
    ]
    # Detect points of interest in an image and glitch them
    for img in track(images_list, "[bold green]Performing semantic glitching...", refresh_per_second=1):
        if random.random() < 0.8:
            continue
        try:
            image = cv2.imread(img)
            segvalues, segoverlay = segment_image.segmentAsPascalvoc(img)
            im_grey = cv2.cvtColor(segoverlay, cv2.COLOR_BGR2GRAY)
            ret, thresh = cv2.threshold(im_grey, 127, 255, 0)

            mask_image = Image.fromarray(thresh)
            if random.random() < 0.9:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            if random.random() < 0.1:
                image =cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
            original_image = Image.fromarray(image)
            # pixelsort image with generated mask
            rand_angle = random.randint(0, 360)
            rand_sort_amt = random.randint(0, 75)
            original_image = pixelsort(
                original_image,
                mask_image,
                randomness=rand_sort_amt,
                sorting_function=random.choice(sorting_func_choices),
                interval_function=random.choice(interval_func_choices),
                angle=rand_angle,
            )
            original_image = original_image.convert("RGB")
            # original_image.show()
            # Now, we need to write original_image over the one we have stored
            original_image.save(img)
        except Exception as e:
            # console.print("\n[red]Warning[/red]: Problem with semantic detection")
            # console.print(e)
            continue


    # # delete test_seg.jpg
    # try:
    #     os.remove("test_seg.jpg")
    # except:
    #     pass

def detect_and_sort_faces(images_list):
    detect_str = f"[bold green]Detecting faces ({len(images_list)})..."
    # with console.status(detect_str, spinner=spinner_choice):
    interval_func_choices = ["random", "edges", "threshold", "waves"]
    sorting_func_choices = [
        "lightness",
        "hue",
        "saturation",
        "intensity",
        "minimum",
    ]

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    for img in track(images_list, detect_str, refresh_per_second=1):

        if random.random() < 0.8:
            continue
        image = cv2.imread(img)

        if image is None:
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.3, minNeighbors=3, minSize=(30, 30)
        )
        if len(faces) == 0:
            continue

        mask = np.zeros(shape=[image.shape[0], image.shape[1], 2], dtype=np.uint8)

        # faces is a list of rectangles of form Rect(x, y, w, h)
        # create mask image
        for (x, y, w, h) in faces:
            rand_float = random.uniform(0.4, 0.8)
            cv2.circle(
                mask,
                (int(x + w / 2), int(y + h / 2)),
                int(min(w, h) * rand_float),
                (255, 255, 255),
                -1,
            )
            # sometimes we can also do a bit more!!
            if random.random() < 0.2:
                # create a box from left to right
                cv2.rectangle(
                    mask,
                    (0, y),
                    (mask.shape[0], y + h),
                    (255, 255, 255),
                    -1,
                )
            if random.random() < 0.2:
                # create a box from top to bottom
                cv2.rectangle(
                    mask,
                    (x, 0),
                    (x + w, mask.shape[1]),
                    (255, 255, 255),
                    -1,
                )

        mask_image = Image.fromarray(mask)
        if random.random() < 0.9:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        if random.random() < 0.1:
            image =cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        original_image = Image.fromarray(image)
        # pixelsort image with generated mask
        rand_angle = random.randint(0, 360)
        rand_sort_amt = random.randint(0, 75)
        original_image = pixelsort(
            original_image,
            mask_image,
            randomness=rand_sort_amt,
            sorting_function=random.choice(sorting_func_choices),
            interval_function=random.choice(interval_func_choices),
            angle=rand_angle,
        )
        original_image = original_image.convert("RGB")

        # Now, we need to write original_image over the one we have stored
        original_image.save(img)

def glitch_images(images_list):
    with console.status("[bold green]Glitching images...",spinner=spinner_choice):
        glitcher = ImageGlitcher()
        images_to_glitch = len(images_list) // 5
        for _ in range(images_to_glitch):
            try:
                random_image = random.choice(images_list)
                img = Image.open(random_image)
                img = glitcher.glitch_image(
                    img,
                    random.random() * 10.0,
                    color_offset=random.choice([True, False]),
                )
                img.save(random_image)

            except:
                pass

def resize_images(images_list):
    # 1280 x 720
    # TODO: Sometimes this still kicks out bad images?!
    target_width, target_height = size
    with console.status("[bold green]Resizing images...",spinner=spinner_choice):
        for image_file in images_list:
            try:
                # if ".webp" in image_file or ".svg" in image_file or ".gif" in image_file:
                #     raise Exception
                img = Image.open(image_file)

                # Test code to make sure greyscale images are RGB
                # to allow compose to work properly later
                formatter = {"PNG": "RGBA", "JPEG": "RGB"}
                rgbimg = Image.new(formatter.get(img.format, "RGB"), img.size)
                rgbimg.paste(img)
                # Figure out if image is wider of taller
                img_width, img_height = rgbimg.size

                if img_width < img_height:
                    # stretch height to max and scale width accordingly
                    img_width = int(img_width * (target_height / img_height))
                    img_height = target_height
                else:
                    # stretch width to max and scale height accordingly
                    img_height = int(img_height * (target_width / img_width))
                    img_width = target_width
                # Thumbnail will only shrink images, not expand them. We need to expand images!
                # rgbimg.thumbnail(size, resample=Image.LANCZOS)
                rgbimg = rgbimg.resize((img_width, img_height), resample=Image.LANCZOS)
                rgbimg = ImageOps.pad(rgbimg, size)
                rgbimg.save(image_file, format=img.format)
            except:
                images_list.remove(image_file)

def make_narration(text):
    with console.status("[bold green]Making narration...",spinner=spinner_choice):
        # Convert to speech
        speech_engine = pyttsx3.init()
        # Get list of all available voices and choose a random one
        voices = speech_engine.getProperty("voices")
        speech_engine.setProperty("voice", random.choice(voices).id)
        speech_engine.setProperty("rate", 175)
        speech_engine.save_to_file(
            text,
            "narration.mp3",
        )
        speech_engine.runAndWait()

def apply_image_fx(frames):
    # Note we can abstract this a bit since this is repeated code from what we do in video glitches
    # so bounce this out to another function that takes ANY clip, applies a random fx, and then returns that clip
    # Run through three times so some images get even extra glitched
    return_frames = []
    for _ in range(3):
        for frame in frames:
            if (random.random() < 0.8):
                return_frames.append(frame)
                continue
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
                # lambda clip: clip.fx(vfx.freeze, total_duration=param1),
                # lambda clip: clip.fx(vfx.freeze_region, t=param1, region=(x, y , x2, y2)),
                lambda clip: clip.fx(vfx.gamma_corr, gamma=param1),
                lambda clip: clip.fx(vfx.invert_colors),
                lambda clip: clip.fx(vfx.mirror_x),
                lambda clip: clip.fx(vfx.mirror_y),
                lambda clip: clip.fx(vfx.painting, 1+(param1/2),param2/ 100.0),
                # lambda clip: clip.fx(vfx.speedx, factor=param1*2),
                # lambda clip: clip.fx(vfx.supersample, d=int((param1+1) * 10), nframes=int((param2+1) * 30)),               
                # lambda clip: clip.fx(vfx.time_mirror),
                # lambda clip: clip.fx(vfx.time_symmetrize),
            ]    
            random_func = random.choice(video_fx_funcs)
            frame = random_func(frame)
            return_frames.append(frame)
    return return_frames

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
            ]
            # frame = zoom_in_effect(frame, zoom_ratio=zoom_ratio)
            random_func = random.choice(video_motion_fx)
            frame = random_func(frame)
            return_frames.append(frame)
    return return_frames

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

def comp_video(images_list, random_video_clips, title, summary):
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
        narration_clip = AudioFileClip("narration.mp3")

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

def make_video(use_article=None, args=None):
    # TALC video generator

    # Narration
    title, wiki_page_title, wiki_page_content = get_article(use_article)
    keywords, summary, summary_hash_text = summarize_article(wiki_page_content)

    if args.use_openai:
        opening, closing = open_ai_stuff(wiki_page_title)
        narration_text = wiki_page_title + "," + opening + ", " + summary + ", " + closing + ", ," + summary_hash_text
    else:
        narration_text = wiki_page_title + ", " + summary + ", " + summary_hash_text

    make_narration(narration_text)

    # Images
    images_list = get_images(keywords, wiki_page_title, args=args)

    # Detect faces first since they won't be detectede if they are all glitched out first
    if not args.no_detect_faces:
        detect_and_sort_faces(images_list)

    if not args.no_glitch_images:
        glitch_images(images_list)

    # Semantic glitching
    if not args.no_semantic_glitches:
        detect_and_glitch_semantic(images_list)

    resize_images(images_list)

    # Video clips
    random_video_clips = get_random_clips(keywords, wiki_page_title)

    movie_title = comp_video(images_list, random_video_clips, title, summary)
    generate_and_write_summary(movie_title, summary, keywords)

    if not args.no_cleanup:
        console.print("Cleaning up images and audio...")
        cleanup()

    console.print(f"[bold green]Done!")

def generate_and_write_summary(movie_title, summary, keywords):
    summary_text = f"{movie_title}:\n{summary}\n\nkeywords: {', '.join(keywords)}\n\n"
    # get todays date and format it
    today = datetime.now()
    # today_formatted = today.strftime("%Y-%m-%d")
    summary_text += f"the aleatoric learning channel\n{today}\n"
    with open(
        f"finished/{movie_title}.txt", "w", encoding="utf-8"
    ) as summary_text_file:
        summary_text_file.write(summary_text)

def cleanup():
    try:
        shutil.rmtree("downloads")
    except Exception as e:
        console.print("[bold red]Warning[/bold red]: Cannot remove downloads folder")
        console.print(str(e))


    try:
        shutil.rmtree("videos")
    except Exception as e:
        console.print("[bold red]Warning[/bold red]: Cannot remove videos folder")
        console.print(str(e))

    try:
        os.remove("narration.mp3")
    except Exception as e:
        console.print("[bold red]Warning[/bold red]: Cannot remove narration.mp3")
        console.print(str(e))

def open_ai_stuff(topic):
    topic.strip()
    # # list engines
    # engines = openai.Engine.list()
    #
    # # print the first engine's id
    # print(engines.data[0].id)
    opening = None
    closing = None
    accepted_opening = False
    while not accepted_opening:
        # create a completion
        open_line = openai.Completion.create(
            engine="davinci",
            prompt=f"A witty, one sentence introductory remark about the topic of {topic}:",
            temperature=0.8,
            max_tokens=20,
            stop=["\n"],
        )

        # # print the completion
        opening = open_line.choices[0].text
        if USE_PROMPTS:
            console.print(f"Proposed opening: {opening}\nAccept? y/n:", end='')
            res = input('')
            if res.lower() == 'y':
                accepted_opening = True
        else:
            accepted_opening = True

    accepted_closing = False
    while not accepted_closing:
        close_line = openai.Completion.create(
            engine="davinci",
            prompt=f"A witty, one sentence concluding remark about the topic of {topic}:",
            temperature=0.85,
            max_tokens=40,
            stop=["\n"],
        )

        # # print the completion
        closing = close_line.choices[0].text
        if USE_PROMPTS:
            console.print(f"Proposed closing: {closing}\nAccept? y/n:", end='')
            res = input('')
            if res.lower() == 'y':
                accepted_closing = True
        else:
            accepted_closing = True

    # opening = re.sub(r"\W+", "", opening)
    # closing = re.sub(r"\W+", "", closing)
    return opening, closing

def main():
    parser = argparse.ArgumentParser(description="TALC video generator")
    parser.add_argument(
        "--article",
        "-a",
        help="The article to use",
        default=None,
        type=str,
    )
    parser.add_argument(
        "--use_openai",
        "-o",
        help="Use OpenAI prompts",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--no_glitch_images",
        "-g",
        help="Don't glitch images",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--no_detect_faces",
        "-f",
        help="Detect faces",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--no_cleanup",
        "-c",
        help="Don't cleanup on finish",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--num_vids",
        "-n",
        help="Number of videos to make",
        default=1,
        type=int,
    )
    parser.add_argument(
        "--images_per_search",
        "-i",
        help="Number of images to search for per keyword",
        default=4,
        type=int,
    )
    parser.add_argument(
        "--silent_mode",
        "-s",
        help="Suppress all output to screen",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--version",
        "-v",
        help="Print version",
        action='version',
        version=f'{__prog__} - {__author__} - {__version__}',    
    )
    parser.add_argument(
        "--no_semantic_glitches",
        "-x",
        help="Don't glitch semantic",
        default=False,
        action="store_true",
    )
    args = parser.parse_args()
    if args.article and args.num_vids > 1:
        console.print("[bold red]Error[/bold red]: Cannot use --article and --num_vids together")
        console.print("Just supply an an article name to make a single video")
        exit()

    if args.silent_mode:
        console.quiet = True

    with console.status("[bold green]Loading nltk...", spinner=spinner_choice):
        nltk.download('wordnet', quiet=True)
        nltk.download('omw-1.4', quiet=True)

    # today = datetime.now()
    # today_formatted = today.strftime("%Y-%m-%d")
    # console.print(f"{today_formatted}")
    for i, _ in enumerate(range(args.num_vids)):
        display_str = "Making video..." if args.num_vids == 1 else \
            f"Making video [bold green]{i+1}[/bold green]/[bold green]{args.num_vids}[/bold green]..."
        console.print(display_str)
        make_video(use_article=args.article, args=args)

if __name__ == "__main__":
    main()
