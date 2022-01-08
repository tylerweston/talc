import json
import requests
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup
from decouple import UndefinedValueError, config
import re
import nltk
from nltk.corpus import wordnet
from nltk.corpus import stopwords
import random
from hashlib import sha1
from datetime import datetime
from main import console, spinner_choice
from config import *
import pyttsx3

from pathlib import Path

from TTS.config import load_config
from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer

def coqui_tts(text_to_synthesize, output_file):
    # ..\wikivids\venv\Lib\site-packages\TTS
    # TODO: The user\AppData\Local\tts folder is getting BIG! Should we maybe delete this folder when we're done with it?!
    # But we don't want to redownload the models every time we run it either. Hmmm.
    voices = [
    r"tts_models/en/ek1/tacotron2",
    r"tts_models/en/ljspeech/tacotron2-DDC",
    r"tts_models/en/ljspeech/tacotron2-DDC_ph",
    r"tts_models/en/ljspeech/glow-tts",
    r"tts_models/en/ljspeech/tacotron2-DCA",
    # r"tts_models/en/ljspeech/speedy-speech-wn",
    # r"tts_models/en/ljspeech/vits",
    # r"tts_models/en/vctk/sc-glow-tts",
    r"tts_models/en/vctk/vits",
    ]
    # tacotron2 + wavegrad = hangs?
    voice=random.choice(voices)
    path = Path(__file__).parent / r"venv/Lib/site-packages/TTS/.models.json"
    print(path)
    manager = ModelManager(path)
    model_path, config_path, model_item = manager.download_model(voice)
    vocoder_name = model_item["default_vocoder"]
    vocoder_path, vocoder_config_path, _ = manager.download_model(vocoder_name)
    speakers_file_path = None

    #  load models
    synthesizer = Synthesizer(
        tts_checkpoint=model_path,
        tts_config_path=config_path,
        tts_speakers_file=speakers_file_path,
        tts_languages_file=None,
        vocoder_checkpoint=vocoder_path,
        vocoder_config=vocoder_config_path,
        encoder_checkpoint="",
        encoder_config="",
        use_cuda=False,

    )
    # use_multi_speaker = hasattr(synthesizer.tts_model, "num_speakers") and synthesizer.tts_model.num_speakers > 1
    # speaker_manager = getattr(synthesizer.tts_model, "speaker_manager", None)
    # print(speaker_manager)
    # print(speaker_manager.speaker_ids)
    # # TODO: set this from SpeakerManager
    # use_gst = synthesizer.tts_config.get("use_gst", False)
    # text = "A quick little demo to see if we can get TTS up and running."
    speaker_idx = ""
    style_wav = ""
    wavs = synthesizer.tts(text_to_synthesize, speaker_name=speaker_idx, style_wav=style_wav)
    # out = io.BytesIO()
    synthesizer.save_wav(wavs, output_file)

with console.status("[bold green]Loading nltk...", spinner=spinner_choice):
    nltk.download('wordnet', quiet=True)
    nltk.download('omw-1.4', quiet=True)

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
        "SM_KEYWORD_COUNT": 10,
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

    # Generate some new keywords based on synonyms for existing keywords
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

def generate_and_write_summary(movie_title, summary, keywords):
    summary_text = f"{movie_title}:\n{summary}\n\nkeywords: {', '.join(keywords)}\n\n"
    today = datetime.now()
    summary_text += f"the aleatoric learning channel\n{today}\n"
    with open(
        f"finished/{movie_title}.txt", "w", encoding="utf-8"
    ) as summary_text_file:
        summary_text_file.write(summary_text)

def pyttsx(text, file):
        # Convert to speech
        speech_engine = pyttsx3.init()
        # Get list of all available voices and choose a random one
        voices = speech_engine.getProperty("voices")
        speech_engine.setProperty("voice", random.choice(voices).id)
        speech_engine.setProperty("rate", 175)
        speech_engine.save_to_file(
            text,
            file,
        )
        speech_engine.runAndWait()


def make_narration(text):
    with console.status("[bold green]Making narration...",spinner=spinner_choice):
        if (random.randint(0,1) == 0):
            coqui_tts(text, "narration.mp3")
        else:
            pyttsx(text, "narration.mp3")
    # TODO: Add any audio effects to narration.mp3 here!
    return


