# !/usr/bin/env python

import logging
import pymupdf
import subprocess

from libcat import CFG
from match import match_lcc, match_isbn, match_issn, match_ddc

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')

def parse_meta(fpath, match_func):
    result = subprocess.run([CFG['exiftoolpath'], fpath], capture_output=True)
    meta = str(result.stdout)
    match = match_func(meta)
    return match
    
def parse_pdf(fpath, match_func):
    with pymupdf.open(fpath) as doc:
        for page in range(min(10, doc.page_count)):
            ptext = doc[page].get_text() + "\n"
            match = match_func(ptext)
            if match: return match
            
        for page in range(max(0, doc.page_count - 10), doc.page_count):
            ptext = doc[page].get_text() + "\n"
            match = match_func(ptext)
            if match: return match
    return None

def parse_epub(fpath, match_func):
    def scan_ch_pages(chapters):
        for i in chapters:
            logger.debug('chapter: ', i)
            chpagecount = doc.chapter_page_count(i)
            logger.debug('pg:', chpagecount)
            for j in range(chpagecount):
                page = doc[(i,j)]
                ptext = page.get_text() + '\n'
                match = match_func(ptext)
                if match: 
                    logger.debug(f"found in page {j} in chapter {i}")
                    return match

    EPUB_FILE_SCANS = [(15, 10, 5),
                    (10, 6, 4),
                    (6, 4, 2),
                    (3, 2, 1),
                    (2, 1, 1),
                    (1, 1, 0)]
                    
    with pymupdf.open(fpath) as doc:
        chapcount = doc.chapter_count
        logger.debug('chapcount: ', chapcount)

        for min_files, front_count, rear_count in EPUB_FILE_SCANS:
            if chapcount >= min_files:
                first_files = range(front_count)
                last_files = []
                if rear_count != 0:
                    last_files = range(chapcount - rear_count, chapcount)
                middle_files = []
                if chapcount - min_files > 0:
                    middle_files = range(front_count, chapcount - rear_count)
                break
        
        logger.debug("first chs: %s, last chs: %s, middle chs: %s" % (first_files, last_files, middle_files))

        logger.debug('scanning first files')
        result = scan_ch_pages(first_files)
        if result: return result

        logger.debug('scanning last files')
        result = scan_ch_pages(last_files)
        if result: return result

        logger.debug('scanning middle files')
        result = scan_ch_pages(middle_files)
        if result: return result
    
    print(type(result))
    return result

def mupdfepub2(fpath, match_func):
    with pymupdf.open(fpath) as doc:
        chapcount = doc.chapter_count
        for i in range(chapcount):
            chpagecount = doc.chapter_page_count(i)
            for j in range(chpagecount):
                page = doc[(i,j)]
                ptext = page.get_text()
                match = match_func(ptext)
                if match: return match
    return None

def main(fpath, match_func, meta=0):
    """ parses parses metadata before or after parsing file content for pdf and epub """
    if meta == 1:
        match = parse_meta(fpath, match_func)
        if match: return match
    if fpath.endswith('.pdf'):
        match = parse_pdf(fpath, match_func)
        if match: return match
    if fpath.endswith('.epub'):
        match = parse_epub(fpath, match_func)
        if match: return match
    if meta == 2:
        match = parse_meta(fpath, match_func)
        if match: return match
    return None