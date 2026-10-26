import codecs
import csv
import ntpath
import re
from configparser import ConfigParser, ParsingError, SectionProxy
from itertools import chain
from pathlib import Path
from typing import Any, Optional

from win2xcur.parser import open_blob
from win2xcur.theme import CursorTheme, WIN_CURSORS

reexpand = re.compile(r'%(\w*)%')

SCHEME_KEYS = {
    'hkcu': 'control panel\\cursors\\schemes',
    'hklm': 'software\\microsoft\\windows\\currentversion\\control panel\\cursors\\schemes',
}


class INFParser(ConfigParser):
    def __init__(self) -> None:
        # Registry lines are keys without values, and may contain ':' (drive letters) or '%' (string references).
        super().__init__(allow_no_value=True, strict=False, delimiters=('=',), interpolation=None)

    def optionxform(self, optionstr: str) -> str:
        # Keep the case of registry lines, so that theme names written inline are preserved.
        return optionstr


def read_inf_text(inf: Path) -> str:
    data = inf.read_bytes()
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode('utf-16')
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode('utf-8')
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return data.decode('cp1252')


def unquote_string(value: str) -> str:
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        value = value[1:-1].replace('""', '"')
    return value.replace('%%', '%')


def expand_registry(text: str, names: dict[str, str]) -> str:
    def replacer(match: re.Match[str]) -> str:
        name = match.group(1)
        if not name:
            return '%'
        elif name.casefold() in names:
            return names[name.casefold()]
        else:
            return match.group(0)

    return reexpand.sub(replacer, text)


def get_key(section: SectionProxy, key: str) -> Optional[str]:
    for name, value in section.items():
        if name.casefold() == key.casefold():
            return value
    return None


def parse_inf(inf: Path) -> CursorTheme:
    parser = INFParser()

    try:
        parser.read_string(read_inf_text(inf), source=str(inf))
    except ParsingError as e:
        raise ValueError(e.args[0])

    # INF section and key names are case-insensitive.
    sections = {name.casefold(): parser[name] for name in parser.sections()}

    add_reg = get_key(sections['defaultinstall'], 'AddReg') if 'defaultinstall' in sections else None
    if not add_reg:
        raise ValueError('Unable to find registry update section in INF')

    try:
        updates = list(chain.from_iterable(list(sections[section.strip().casefold()])
                                           for section in add_reg.split(',')))
    except KeyError as e:
        raise ValueError(f'Registry update section does not exist in INF: {e.args[0]}')

    rows = [row for row in csv.reader(updates, skipinitialspace=True)
            if len(row) >= 2 and SCHEME_KEYS.get(row[0].strip().casefold()) == row[1].strip().casefold()]

    if len(rows) == 0:
        raise ValueError('No cursor installs found in INF')
    elif len(rows) > 1:
        raise ValueError('Multiple cursor installs found in INF')

    strings = {}
    if 'strings' in sections:
        strings = {key.casefold(): unquote_string(value) for key, value in sections['strings'].items()
                   if value is not None}

    parsed = dict(zip(['root', 'path', 'name', 'flags', 'value'], rows[0]))

    params: dict[str, Any] = {'name': expand_registry(parsed.get('name', ''), strings)}
    cursor_paths = expand_registry(parsed.get('value', ''), strings).split(',')

    casefolded = {file.name.casefold(): file for file in inf.parent.iterdir() if file.is_file()}

    for name, filename in zip(WIN_CURSORS, cursor_paths):
        filename = filename.strip()
        if not filename:
            continue

        basename = ntpath.basename(filename)
        try:
            path = casefolded[basename.casefold()]
        except KeyError:
            raise ValueError(f'Expected cursor file in same directory as INF: {basename}')

        with open(path, 'rb') as f:
            params[name] = open_blob(f.read())

    return CursorTheme(**params)
