"""Texts the user sees, from strings_<lang>.json beside this file (default Estonian).

    from texts import TEXT
    TEXT['title'].format(name='Logo')

Set STITCH_LANG=<lang> to use strings_<lang>.json instead.
"""
import json
import os

LANGUAGE = os.environ.get('STITCH_LANG', 'et')
_HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_HERE, f'strings_{LANGUAGE}.json'), encoding='utf-8') as _file:
    TEXT = json.load(_file)
