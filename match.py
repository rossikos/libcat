# !/usr/bin/env python

import regex as re

def match_lcc(x):
    a = re.compile(r"""
            (?P<class>(\b)([A-Z](?:\s?)){1,3}) # main and sub class
            (?P<div>\d{1,4}) # subclass division
            (?P<ext>.\d{1,3})? # optional subclass division extensionl
            (?P<date>[A-Za-z0-9]{1,4})? #what?
            (\s?[\s\.](?P<c1>[A-Z][0-9]{1,4})) # cutter number, added ?
            (\ (?P<c1d>[A-Za-z0-9]{0,4}))?
            (\.?(?P<c2>[A-Z][0-9]{1,4}))?
            (\ (?P<e8>\w*)\ ?)?
            (\ (?P<e9>\w*)\ ?)?
            (\ (?P<e10>\w*)\ ?)?
            """, re.VERBOSE)

    if a.search(x):
        result = a.search(x).group(0)
        result = re.sub(r"(?<=[A-Z])\s", '', result)
        return result
    else: return None

def match_ddc(x):
    a = re.compile(r"(\d{3}['′]?\.[\d'′ ]*[-–—]{1,2}dc\s?2[12])")

    result = a.search(x)
    return result.group(0).strip() if result else None

def match_isbn(x):
    isbn13 = re.compile(r"""
    (?<=(ISBN|isbn)(.*))?
    (978|979) [-– ]?
    (?P<reggrp>\d{1,5}) [-– ]?
    (?P<registrant>\d{0,7}) [-– ]?
    (?P<pub>\d{0,6}) [-– ]?
    (?P<chkdig>\d|X|x)
    """, re.VERBOSE)

    isbn10 = re.compile(r"""
    (?<=(ISBN|isbn)(.*))
    (?P<country>\d{1,5}) [-– ]?
    (?P<pub>\d{1,7}) [-– ]?
    (?P<title>\d{1,6}) [-– ]?
    (?P<chkdig>\d|X|x) [-– ]?
    """, re.VERBOSE)

    result = isbn13.search(x) or isbn10.search(x)
    return re.sub('[-– ]', '', result.group(0)) if result and (len(result) >= 10) else None

def match_issn(x):
    issn = re.compile(r'[0-9]{4}-[0-9]{3}[0-9X]')

    result = issn.search(x)
    return result.group(0) if result else None