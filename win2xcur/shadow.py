from typing import List

from wand.color import Color
from wand.image import BaseImage, COMPOSITE_OPERATORS, Image

from win2xcur.cursor import CursorFrame

if 'copy_opacity' in COMPOSITE_OPERATORS:
    COPY_ALPHA = 'copy_opacity'  # ImageMagick 6 name
    NEEDS_NEGATE = False
else:
    COPY_ALPHA = 'copy_alpha'  # ImageMagick 7 name
    NEEDS_NEGATE = True


def apply_to_image(image: BaseImage, *, color: str, radius: float, sigma: float, xoffset: float,
                   yoffset: float, opacity: float = 50) -> Image:
    xoffset = round(xoffset * image.width)
    yoffset = round(yoffset * image.height)
    new_width = image.width + 3 * xoffset
    new_height = image.height + 3 * yoffset

    if NEEDS_NEGATE:
        channel = image.channel_images['opacity'].clone()
        channel.negate()
    else:
        channel = image.channel_images['opacity']

    alpha = Image(width=new_width, height=new_height, pseudo='xc:white')
    alpha.composite(channel, left=xoffset, top=yoffset)
    alpha.gaussian_blur(radius * image.width, sigma * image.width)
    alpha.negate()
    alpha.modulate(opacity)

    shadow = Image(width=new_width, height=new_height, pseudo='xc:' + color)
    shadow.composite(alpha, operator=COPY_ALPHA)

    result = Image(width=new_width, height=new_height, pseudo='xc:transparent')
    result.composite(shadow)
    result.composite(image)

    trimmed = result.clone()
    trimmed.trim(color=Color('transparent'))
    result.crop(width=max(image.width, trimmed.page_x + trimmed.width),
                height=max(image.height, trimmed.page_y + trimmed.height))
    return result


def apply_to_frames(frames: List[CursorFrame], *, color: str, radius: float,
                    sigma: float, xoffset: float, yoffset: float, opacity: float = 50) -> None:
    for frame in frames:
        for cursor in frame:
            cursor.image = apply_to_image(cursor.image, color=color, radius=radius,
                                          sigma=sigma, xoffset=xoffset, yoffset=yoffset, opacity=opacity)
