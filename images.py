from main import console, spinner_choice
from google_images_download import google_images_download
import random
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
from rich.progress import track
from pixellib.semantic import semantic_segmentation
import numpy as np
import cv2
from PIL import Image, ImageOps
from pixelsort import pixelsort
from glitch_this import ImageGlitcher
from config import size
import moviepy.video.fx.all as vfx

def get_images(keywords, wiki_page_title, passed_args):
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
            "limit": passed_args.images_per_search,
            "print_urls": False,
            "silent_mode": True,
        }
        # console.print(arguments)
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

def detect_and_make_masked_images(images_list):
    segment_image = semantic_segmentation()
    segment_image.load_pascalvoc_model("deeplabv3_xception_tf_dim_ordering_tf_kernels.h5")
    for img in track(images_list, "[bold green]Detecting and making masked image...", refresh_per_second=1):
        if random.random() < 0.7:
            continue
        image = cv2.imread(img)
        try:
            segvalues, segoverlay = segment_image.segmentAsPascalvoc(img)
        except ValueError as e:
            # Not enough values to unpack (expected 3, got 2)
            continue
        im_grey = cv2.cvtColor(segoverlay, cv2.COLOR_BGR2GRAY)
        ret, thresh = cv2.threshold(im_grey, 127, 255, 0)
        mask_image = Image.fromarray(thresh)

        second_image = random.choice(images_list)
        second_image = cv2.imread(second_image)
        # resize second_image to match mask_image
        try:
            second_image = cv2.resize(second_image, (mask_image.size[0], mask_image.size[1]))
        except cv2.error:
            # Problem with resizing one of the images, try the next one!
            continue
            
        if image is None or second_image is None:
            # Error grabbing images!
            # Who cares, just try again
            # console.print("[red]Warning[/red]: Either image or second_image was None")
            continue
        # masked_image = cv2.bitwise_and(second_image, image, mask=thresh) if random.random() < 0.5 else cv2.bitwise_and(image, second_image, mask=thresh)
        mask_funcs = [
            lambda arg1, arg2, mask: cv2.bitwise_and(arg1, arg2, mask),
            lambda arg1, arg2, mask: cv2.bitwise_and(arg2, arg1, mask),
            lambda arg1, arg2, mask: cv2.bitwise_or(arg1, arg2, mask),
            lambda arg1, arg2, mask: cv2.bitwise_or(arg2, arg1, mask),
            lambda arg1, arg2, mask: cv2.bitwise_xor(arg1, arg2, mask),
            lambda arg1, _, mask: cv2.bitwise_not(arg1, mask),
            lambda _, arg2, mask: cv2.bitwise_not(arg2, mask),
            lambda arg1, arg2, mask:
                cv2.bitwise_and(arg1, arg2, mask=cv2.bitwise_not(mask)) + 
                cv2.bitwise_and(arg1, arg2, mask=mask)
        ]
        f = random.choice(mask_funcs)
        masked_image = f(image, second_image, mask=thresh)
        if random.random() < 0.5:
            masked_image = masked_image + second_image
        # convert to PIL image
        masked_image = Image.fromarray(masked_image)
        # save the image
        masked_image.save(img)

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
            # # choose random x and y values that are within the size of the clip
            # x = random.randint(0, size[0] - 1)
            # y = random.randint(0, size[1] - 1)
            # # choose another set of random x and y values that are within the size of the clip
            # x2 = random.randint(0, size[0] - 1)
            # y2 = random.randint(0, size[1] - 1)
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
