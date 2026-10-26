import struct
from typing import Dict, List, Tuple

from wand.image import Image

from win2xcur.cursor import CursorFrame, CursorImage
from win2xcur.parser.base import BaseParser


class CURParser(BaseParser):
    MAGIC = b'\0\0\02\0'
    ICO_TYPE_ICO = 1
    ICO_TYPE_CUR = 2
    ICON_DIR = struct.Struct('<HHH')
    ICON_DIR_ENTRY = struct.Struct('<BBBBHHII')
    PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
    BMP_BIT_COUNT = struct.Struct('<H')
    BMP_BIT_COUNT_OFFSET = 14

    @classmethod
    def can_parse(cls, blob: bytes) -> bool:
        return blob[:len(cls.MAGIC)] == cls.MAGIC

    def __init__(self, blob: bytes) -> None:
        super().__init__(blob)
        self._image = Image(blob=blob, format='cur')
        entries = self._parse_header()

        # Windows cursors may store the same size at several colour depths, but Xcursor would treat
        # images of the same size as animation frames, so keep only the deepest image of each size.
        best: Dict[Tuple[int, int], Tuple[int, CursorImage]] = {}
        for image, (hotspot, bit_count) in zip(self._image.sequence, entries):
            size = (image.width, image.height)
            if size not in best or bit_count > best[size][0]:
                best[size] = (bit_count, CursorImage(image, hotspot, image.width))

        self.frames = [CursorFrame([cursor for _, cursor in best.values()])]

    def _parse_header(self) -> List[Tuple[Tuple[int, int], int]]:
        reserved, ico_type, image_count = self.ICON_DIR.unpack(self.blob[:self.ICON_DIR.size])
        if reserved != 0:
            raise ValueError(f'Unexpected reserved field in icon directory: {reserved}')
        if ico_type not in (self.ICO_TYPE_ICO, self.ICO_TYPE_CUR):
            raise ValueError(f'Unexpected icon directory type: {ico_type}')
        if image_count != len(self._image.sequence):
            raise ValueError(f'Icon directory lists {image_count} images, but {len(self._image.sequence)} were read')

        offset = self.ICON_DIR.size
        entries = []
        for i in range(image_count):
            width, height, palette, reserved, hx, hy, size, file_offset = self.ICON_DIR_ENTRY.unpack(
                self.blob[offset:offset + self.ICON_DIR_ENTRY.size])
            if ico_type == self.ICO_TYPE_ICO:
                # Icons have no hotspot fields; Windows puts the hotspot of an icon at its centre.
                hx, hy = (width or 256) // 2, (height or 256) // 2
            entries.append(((hx, hy), self._bit_count(file_offset)))
            offset += self.ICON_DIR_ENTRY.size

        return entries

    def _bit_count(self, file_offset: int) -> int:
        if self.blob[file_offset:file_offset + len(self.PNG_SIGNATURE)] == self.PNG_SIGNATURE:
            return 32
        start = file_offset + self.BMP_BIT_COUNT_OFFSET
        bit_count: int = self.BMP_BIT_COUNT.unpack(self.blob[start:start + self.BMP_BIT_COUNT.size])[0]
        return bit_count
