from os import path
import re

def clean_filename(filename):
    """
    take in a filename and return a sanitized filename
    We don't really care about handling all valid filenames, just want them to be "valid enough"
    so in this case, just allow letters and numbers in out filenames
    """
    fname, ext = path.splitext(filename)
    clean_fname = ''.join([ch for ch in fname if ch.isalnum()])
    return clean_fname + ext


def fix_abbreviations(text):
    """
    replace some common abbreviations to make the computer pronunciation a bit better
    No. -> number
    RAF -> R.A.F.
    TODO: We should assume that ANY word of the format UPPERCASE 3+ letters is an abbreviation and insert . between
    letters to allow our robot friend to pronounce it more easily
    """
    replacements = {
        r'\bNo\.': "number",
        r'\bRAF\b': "R.A.F",
        r'\bEU\b': "E.U.",
        r'\bII\b': "two",
        r'\bIII\b': "three",
        r'\bIV\b': "four",
    }
    for word, replacement in replacements.items():
        text = re.sub(word, replacement, text)
    return text