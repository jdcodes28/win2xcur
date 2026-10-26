from typing import List

from win2xcur.cursor import CursorFrame


def apply_to_frames(frames: List[CursorFrame], *, scale: float) -> None:
    for frame in frames:
        for cursor in frame:
            width = max(1, round(cursor.image.width * scale))
            height = max(1, round(cursor.image.height * scale))
            cursor.image.scale(width, height)

            hx, hy = cursor.hotspot
            cursor.hotspot = (min(round(hx * scale), width - 1), min(round(hy * scale), height - 1))
