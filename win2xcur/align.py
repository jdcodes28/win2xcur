import bisect
from typing import Dict, List, Optional

from wand.color import Color

from win2xcur.cursor import CursorFrame, CursorImage

SIZES = [32, 48, 64, 96, 128, 256]


def aligned_size(cursor: CursorImage) -> Optional[int]:
    size_index = bisect.bisect_left(SIZES, max(cursor.image.width, cursor.image.height))
    return SIZES[size_index] if size_index < len(SIZES) else None


def apply_to_frames(frames: List[CursorFrame]) -> None:
    for frame in frames:
        # When several images align to the same size, keep the largest, which needs the least padding.
        best: Dict[int, CursorImage] = {}
        for cursor in frame:
            size = aligned_size(cursor)
            if size is not None and (size not in best or
                                     cursor.image.width * cursor.image.height >
                                     best[size].image.width * best[size].image.height):
                best[size] = cursor

        kept = {id(cursor) for cursor in best.values()}
        frame.images = [cursor for cursor in frame if aligned_size(cursor) is None or id(cursor) in kept]

        for size, cursor in best.items():
            if cursor.image.width != size or cursor.image.height != size:
                cursor.image.background_color = Color('transparent')
                cursor.image.extent(width=size, height=size)
