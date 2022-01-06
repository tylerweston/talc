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
console = Console()
import random
from config import *

spinner_choice = random.choice(['aesthetic', 'arc', 'arrow3', 'betaWave', 'balloon',
'bounce', 'bouncingBar', 'circle', 'dots', 'line', 'squish', 'toggle10', 'pong'])

# This is all we need if we want to just get --help or --version so check for those first
args = [s.lower() for s in sys.argv[1:]]
if not ("--help" in args or "-h" in args or "--version" in args or "-v" in args):

    from summarize import *
    from images import *
    from video import *

    import shutil
    import openai
    from moviepy.editor import *
    from decouple import UndefinedValueError, config

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
def make_video(use_article=None, args=None):
    # TALC video generator

    # Narration
    title, wiki_page_title, wiki_page_content = get_article(use_article)
    keywords, summary, summary_hash_text = summarize_article(wiki_page_content)

    # summary = open_ai_jank_summary(summary)
    # console.print(summary)

    if args.use_openai:
        opening, closing = open_ai_stuff(wiki_page_title)
        narration_text = wiki_page_title + "," + opening + ", " + summary + ", " + closing + ", ," + summary_hash_text
    else:
        narration_text = wiki_page_title + ", " + summary + ", " + summary_hash_text

    make_narration(narration_text)

    # Images
    images_list = get_images(keywords, wiki_page_title, passed_args=args)

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

    # Video clips
    random_video_clips = get_random_clips(keywords, wiki_page_title)

    movie_title = comp_video(images_list, random_video_clips, title, summary)
    generate_and_write_summary(movie_title, summary, keywords)
    console.print(f"Finished writing [bold green]{movie_title}[/bold green]")

    if not args.no_cleanup:
        console.print("Cleaning up images and audio...")
        cleanup()

    console.print(f"[bold green]Done!")

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
