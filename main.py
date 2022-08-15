"""
The Aleatoric Learning Channel video generator -
Generates new somewhat educational videos on random topics using images gathered from Google images,
videos gathered from YouTube, and an article grabbed from Wikipedia.
"""

# TODO:
#   - Fix ffmpeg errors, right now composing videos seems to randomly break sometimes with message
#     Can't get next frame, or read 0 bytes/##### something like that. Looks like we are reading past
#     the end of the file?
#   
#   - Skip age locked videos in YouTube
#   - More sound options? Add some random sounds
#   - Move audio stuff out of summarize
#   - Better article selection somehow?
#   - Different soundtracks to choose from
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
#  - Any python file named test_*.py will be excluded from the repo
#  - possible fun modules to play with:
#       - wave - read and write wav files
#       - tempfile - create temporary files (instead of managing manually)

from config import *
import os
import sys
import argparse
from rich.console import Console
#from rich.highlighter import RegexHighlighter
#console = Console(color_system="256")
import random
from version import __version__


# This is all we need if we want to just get --help or --version so check for those first
# args = [s.lower() for s in sys.argv[1:]]
# print(args)
# if not ("--help" in args or "-h" in args or "--version" in args or "-v" in args):

console = Console(color_system="256")
from summarize import *
from images import *
from video import *
from make_title import make_new_title


import shutil
import openai
from moviepy.editor import *
from decouple import UndefinedValueError, config

if USE_OPENAI:
    try:
        openai.api_key = config("OPENAI_API_KEY")
    except UndefinedValueError as e:
        console.print("[bold red]Error[/bold red]: Please set OPENAI_API_KEY in your .env file to use open ai")
        console.print(e)
        exit(0)
    


def make_video(use_article=None, args=None):
    # TALC video generator
    # Generate new random title
    with console.status("[bold green]Making new intro vid...",spinner=spinner_choice):
        make_new_title()

    # Narration
    title, wiki_page_title, wiki_page_content = get_article(use_article)
    keywords, summary, summary_hash_text = summarize_article(wiki_page_content)

    # Video clips
    console.print("[bold green]Getting video clips...")
    random_video_clips = get_random_clips(keywords, wiki_page_title)
    console.print("[bold green]Done![/bold green]")

    # Images
    images_list = get_images(keywords, wiki_page_title, passed_args=args)
    
    # summary = open_ai_jank_summary(summary)
    # console.print(summary)

    if args.use_openai:
        opening, closing = open_ai_stuff(wiki_page_title)
        narration_text = wiki_page_title + "," + opening + ", " + summary + ", " + closing + ", ," + summary_hash_text
    else:
        narration_text = wiki_page_title + ", " + summary + ", " + summary_hash_text

    make_narration(narration_text)
    soundfile_name = 'narration.wav'
    if not args.no_soundfx:
        add_audio_effects('narration.wav', 'narration_effected.wav')
        soundfile_name = 'narration_effected.wav'

    # Detect faces first since they won't be detectede if they are all glitched out first
    if not args.no_detect_faces:
        detect_and_sort_faces(images_list)

    if not args.no_glitch_images:
        glitch_images(images_list)

    # Semantic glitching
    if not args.no_semantic_glitches:
        detect_and_glitch_semantic(images_list)

    detect_and_make_masked_images(images_list)

    resize_images(images_list)

    movie_title = comp_video(images_list, random_video_clips, title, soundfile_name)
    generate_and_write_summary(movie_title, summary, keywords)
    console.print(f"Finished writing [bold green]{movie_title}[/bold green]")

            # console.print("Doing final glitching")
    
    unified_glitch_pass(f"finished/{movie_title}.mp4", f"finished/{movie_title}_glitched.mp4")
    # for i in range(5):
    #     console.print(f"[bold green]Attempting final glitching {i}/5...")
    #     try:
    #         unified_glitch_pass(f"finished/{movie_title}.mp4", f"finished/{movie_title}_glitched.mp4")
    #         break
    #     except:
    #         continue
    # else:
    #     console.print(f"[bold red]Error[/bold red]: Unable to glitch video")

    if not args.no_cleanup:
        console.print("Cleaning up images and audio...")
        cleanup()

    console.print(f"[bold green]Done!")
    console.rule()

def cleanup():

    reset_movie_data()

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
        # os.remove("narration.mp3")
        os.remove("narration.wav")
        os.remove("narration_effected.wav")
    except Exception as e:
        console.print("[bold red]Warning[/bold red]: Cannot remove narration.mp3")
        console.print(str(e))
    
    try:
        os.remove("title.mp4")
    except Exception as e:
        console.print("[bold red]Warning[/bold red]: Cannot remove title.mp4")


def open_ai_jank_summary(summary):
    openai.api_key = config("OPENAI_API_KEY")
    total_summary = []
    for sentence in track(summary.split("."), "[bold green]Generating openai banter...", refresh_per_second=1):
        if random.random() < 0.5:
            total_summary.append(sentence)
            continue
        if len(sentence) > 0:
            try:
                response = openai.Completion.create(engine="davinci", prompt=sentence, temperature=0.7, max_tokens=30,)
                # if response.status_code == 200:
                #     return response.result['choices'][0]['text']
            except Exception as e:
                console.print("[bold red]Warning[/bold red]: Cannot get open ai summary")
                console.print(str(e))
                return ""
            total_summary.append(sentence)
            total_summary.append(response.choices[0].text)
    return ".".join(total_summary)

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
        "--no_soundfx",
        "-x",
        help="Don't apply any sound fx to the narration",
        default=False,
        action="store_true",
    )
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
        default=DEFAULT_IMAGES_PER_SEARCH,
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
        version=f'{prog} - {author} - {__version__}',    
    )
    parser.add_argument(
        "--no_semantic_glitches",
        "-l",
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



    # today = datetime.now()
    # today_formatted = today.strftime("%Y-%m-%d")
    # console.print(f"{today_formatted}")
    # print(console.color_system)
    display_banner()
    for i, _ in enumerate(range(args.num_vids)):
        display_str = "Making video..." if args.num_vids == 1 else \
            f"Making video [bold green]{i+1}[/bold green]/[bold green]{args.num_vids}[/bold green]..."
        console.print(display_str)
        make_video(use_article=args.article, args=args)

def display_banner():
    # console.print(r".███████████   █████████   █████         █████████     █████   █████  ███      █████                 .", justify="center")
    # console.print(r"░█░░░███░░░█  ███░░░░░███ ░░███         ███░░░░░███   ░░███   ░░███  ░░░      ░░███                  .", justify="center")
    # console.print(r"░   ░███  ░  ░███    ░███  ░███        ███     ░░░     ░███    ░███  ████   ███████   ██████   ██████.", justify="center")
    # console.print(r".   ░███     ░███████████  ░███       ░███             ░███    ░███ ░░███  ███░░███  ███░░███ ███░░███", justify="center")
    # console.print(r".   ░███     ░███░░░░░███  ░███       ░███             ░░███   ███   ░███ ░███ ░███ ░███████ ░███ ░███", justify="center")
    # console.print(r".   ░███     ░███    ░███  ░███      █░░███     ███     ░░░█████░    ░███ ░███ ░███ ░███░░░  ░███ ░███", justify="center")
    # console.print(r".   █████    █████   █████ ███████████ ░░█████████        ░░███      █████░░████████░░██████ ░░██████.", justify="center")
    # console.print(r".  ░░░░░    ░░░░░   ░░░░░ ░░░░░░░░░░░   ░░░░░░░░░          ░░░      ░░░░░  ░░░░░░░░  ░░░░░░   ░░░░░░ .", justify="center")
    # console.print(r"                                                                                                      ", justify="center")
    # console.print(r"                                                                                                      ", justify="center")
    # console.print(r"                                                                                                      ", justify="center")
    # console.print(r".        █████████                                                    █████                          .", justify="center")
    # console.print(r".       ███░░░░░███                                                  ░░███                           .", justify="center")
    # console.print(r".      ███     ░░░   ██████  ████████    ██████  ████████   ██████   ███████    ██████  ████████     .", justify="center")
    # console.print(r".     ░███          ███░░███░░███░░███  ███░░███░░███░░███ ░░░░░███ ░░░███░    ███░░███░░███░░███    .", justify="center")
    # console.print(r".     ░███    █████░███████  ░███ ░███ ░███████  ░███ ░░░   ███████   ░███    ░███ ░███ ░███ ░░░     .", justify="center")
    # console.print(r".     ░░███  ░░███ ░███░░░   ░███ ░███ ░███░░░   ░███      ███░░███   ░███ ███░███ ░███ ░███         .", justify="center")
    # console.print(r".      ░░█████████ ░░██████  ████ █████░░██████  █████    ░░████████  ░░█████ ░░██████  █████        .", justify="center")
    # console.print(r".       ░░░░░░░░░   ░░░░░░  ░░░░ ░░░░░  ░░░░░░  ░░░░░      ░░░░░░░░    ░░░░░   ░░░░░░  ░░░░░         .", justify="center")
    # console.print("")                                                                    
    console.print(r". ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄            ▄▄▄▄▄▄▄▄▄▄▄       ▄               ▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄   ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄ .", justify="center")
    console.print(r".▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░▌          ▐░░░░░░░░░░░▌     ▐░▌             ▐░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░▌ ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌.", justify="center")
    console.print(r". ▀▀▀▀█░█▀▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌▐░▌          ▐░█▀▀▀▀▀▀▀▀▀       ▐░▌           ▐░▌  ▀▀▀▀█░█▀▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌.", justify="center")
    console.print(r".     ▐░▌     ▐░▌       ▐░▌▐░▌          ▐░▌                 ▐░▌         ▐░▌       ▐░▌     ▐░▌       ▐░▌▐░▌          ▐░▌       ▐░▌.", justify="center")
    console.print(r".     ▐░▌     ▐░█▄▄▄▄▄▄▄█░▌▐░▌          ▐░▌                  ▐░▌       ▐░▌        ▐░▌     ▐░▌       ▐░▌▐░█▄▄▄▄▄▄▄▄▄ ▐░▌       ▐░▌.", justify="center")
    console.print(r".     ▐░▌     ▐░░░░░░░░░░░▌▐░▌          ▐░▌                   ▐░▌     ▐░▌         ▐░▌     ▐░▌       ▐░▌▐░░░░░░░░░░░▌▐░▌       ▐░▌.", justify="center")
    console.print(r".     ▐░▌     ▐░█▀▀▀▀▀▀▀█░▌▐░▌          ▐░▌                    ▐░▌   ▐░▌          ▐░▌     ▐░▌       ▐░▌▐░█▀▀▀▀▀▀▀▀▀ ▐░▌       ▐░▌.", justify="center")
    console.print(r".     ▐░▌     ▐░▌       ▐░▌▐░▌          ▐░▌                     ▐░▌ ▐░▌           ▐░▌     ▐░▌       ▐░▌▐░▌          ▐░▌       ▐░▌.", justify="center")
    console.print(r".     ▐░▌     ▐░▌       ▐░▌▐░█▄▄▄▄▄▄▄▄▄ ▐░█▄▄▄▄▄▄▄▄▄             ▐░▐░▌        ▄▄▄▄█░█▄▄▄▄ ▐░█▄▄▄▄▄▄▄█░▌▐░█▄▄▄▄▄▄▄▄▄ ▐░█▄▄▄▄▄▄▄█░▌.", justify="center")
    console.print(r".     ▐░▌     ▐░▌       ▐░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌             ▐░▌        ▐░░░░░░░░░░░▌▐░░░░░░░░░░▌ ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌.", justify="center")
    console.print(r".      ▀       ▀         ▀  ▀▀▀▀▀▀▀▀▀▀▀  ▀▀▀▀▀▀▀▀▀▀▀               ▀          ▀▀▀▀▀▀▀▀▀▀▀  ▀▀▀▀▀▀▀▀▀▀   ▀▀▀▀▀▀▀▀▀▀▀  ▀▀▀▀▀▀▀▀▀▀▀ .", justify="center")
    console.print(r".                                                                                                                                .", justify="center")
    console.print(r".      ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄        ▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄       .", justify="center")
    console.print(r".     ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░▌      ▐░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌      .", justify="center")
    console.print(r".     ▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀▀▀▀▀▀ ▐░▌░▌     ▐░▌▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀█░▌ ▀▀▀▀█░█▀▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀█░▌      .", justify="center")
    console.print(r".     ▐░▌          ▐░▌          ▐░▌▐░▌    ▐░▌▐░▌          ▐░▌       ▐░▌▐░▌       ▐░▌     ▐░▌     ▐░▌       ▐░▌▐░▌       ▐░▌      .", justify="center")
    console.print(r".     ▐░▌ ▄▄▄▄▄▄▄▄ ▐░█▄▄▄▄▄▄▄▄▄ ▐░▌ ▐░▌   ▐░▌▐░█▄▄▄▄▄▄▄▄▄ ▐░█▄▄▄▄▄▄▄█░▌▐░█▄▄▄▄▄▄▄█░▌     ▐░▌     ▐░▌       ▐░▌▐░█▄▄▄▄▄▄▄█░▌      .", justify="center")
    console.print(r".     ▐░▌▐░░░░░░░░▌▐░░░░░░░░░░░▌▐░▌  ▐░▌  ▐░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌     ▐░▌     ▐░▌       ▐░▌▐░░░░░░░░░░░▌      .", justify="center")
    console.print(r".     ▐░▌ ▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀▀▀ ▐░▌   ▐░▌ ▐░▌▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀█░█▀▀ ▐░█▀▀▀▀▀▀▀█░▌     ▐░▌     ▐░▌       ▐░▌▐░█▀▀▀▀█░█▀▀       .", justify="center")
    console.print(r".     ▐░▌       ▐░▌▐░▌          ▐░▌    ▐░▌▐░▌▐░▌          ▐░▌     ▐░▌  ▐░▌       ▐░▌     ▐░▌     ▐░▌       ▐░▌▐░▌     ▐░▌        .", justify="center")
    console.print(r".     ▐░█▄▄▄▄▄▄▄█░▌▐░█▄▄▄▄▄▄▄▄▄ ▐░▌     ▐░▐░▌▐░█▄▄▄▄▄▄▄▄▄ ▐░▌      ▐░▌ ▐░▌       ▐░▌     ▐░▌     ▐░█▄▄▄▄▄▄▄█░▌▐░▌      ▐░▌       .", justify="center")
    console.print(r".     ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░▌      ▐░░▌▐░░░░░░░░░░░▌▐░▌       ▐░▌▐░▌       ▐░▌     ▐░▌     ▐░░░░░░░░░░░▌▐░▌       ▐░▌      .", justify="center")
    console.print(r".      ▀▀▀▀▀▀▀▀▀▀▀  ▀▀▀▀▀▀▀▀▀▀▀  ▀        ▀▀  ▀▀▀▀▀▀▀▀▀▀▀  ▀         ▀  ▀         ▀       ▀       ▀▀▀▀▀▀▀▀▀▀▀  ▀         ▀       .", justify="center")
                                                                                                                                
    today = datetime.now()
    today_formatted = today.strftime("%Y-%m-%d")
    console.print(f" Tyler Weston 2021/2022, today: {today_formatted}, version# {__version__}", justify="center")
    console.rule()


if __name__ == "__main__":
    main()
