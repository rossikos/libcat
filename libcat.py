# !/usr/bin/env python

import logging
import os
import time
import argparse
import tomllib
import sqlite3
from sys import argv
from pathlib import Path
import shutil

def get_user_data_dir():
    home = Path.home()
    data_dir = home / ".libcat"
    data_dir.mkdir(exist_ok=True)
    return data_dir

DATA_DIR = get_user_data_dir()
CONFIG_FILE = DATA_DIR / "config.toml"

if not CONFIG_FILE.exists():
    shutil.copy(os.path.abspath('config.toml'), CONFIG_FILE)

with open(CONFIG_FILE, "rb") as f:
    CFG = tomllib.load(f)

from match import match_lcc, match_isbn, match_ddc
import scan
import search
import dbviewer

def search_catalogs(
    wait: int, 
    retries: int, 
    timeout: int,
    languages: list, 
    altisbns: str, 
    maxalts: int, 
    classifiers: list, 
    id_type: str, 
    id_data: dict={}
) -> dict:
    def process(_id, currentalt=''):
        nonlocal data
        nonlocal alt_isbns
        classifiers = [k for k, v in data.items() if not v]

        for catalog in args.catalogs:
            classifiers = [k for k, v in data.items() if not v]
            logger.info(f"\tsearching {catalog} catalog with {_id} {currentalt} for {classifiers}")
            cdict = CFG['catalogs'][catalog]
            search_class = getattr(search, cdict['cclass'])
            search_obj = search_class(wait, retries, timeout, _id, id_type, languages, classifiers, cdict)
            search_result = search_obj.main()

            for k, v in search_result.items():
                if v and not data[k]:
                    logger.info(f'\t\t{k} found')
                    data[k] = v
                    supp_data['catalog'] = catalog
                    supp_data[id_type] = _id

                    if k == 'record':
                        supp_data['recordtype'] = cdict['recordtype']
            
            # return if data is full
            if not any(i is None for i in data.values()):
                return True
        
        # fetch alts
        if id_type == 'isbn' and altisbns == 'yes' and not alt_isbns:
            logger.info('\tfetching alternative editions...')

            
            search_obj = search.fetch_openl_alt(wait, retries, timeout, _id, id_type, languages, classifiers, None)
            alt_isbns, alt_lccs, alt_ddcs = search_obj.main()

            if alt_lccs:
                logging.info('\talt lccs found')
                data['lcc'] = search.get_most_common_lcc(alt_lccs)
            if alt_ddcs:
                logging.info('\talt ddcs found')
                data['ddc'] = search.get_most_common_ddc(alt_ddcs)
            
            if not any(i is None for i in data.values()):
                return True

            print(alt_isbns, alt_lccs, alt_ddcs)
            if languages and alt_isbns:
                search_obj = search.fetch_openl_alt_filtered(wait, retries, timeout, _id, id_type, languages, classifiers, None)
                alt_isbns, _, _ = search_obj.main()

            if not alt_isbns:
                logging.info('\tno alt isbns found')
                return
            
            # loop through alts
            for idi, i in enumerate(alt_isbns):
                if idi == maxalts:
                    return

                currentalt = f"{idi+1}/{len(alt_isbns)}"
                run = process(i, currentalt)
                if run:
                    return
                time.sleep(wait)

    data = {k: None for k in classifiers} # to search for
    supp_data = {'catalog': None} # to search with + other info
    for k, v in id_data.items():
        if k in data: data[k] = v
        else: supp_data[k] = v

    alt_isbns = []
    
    if id_type and any(i is None for i in data.values()):
        _id = id_data[id_type]
        process(_id)

    final_data = {**supp_data, **data}

    logger.log(STDINFO, '\n'.join(f'{k}{" "*(20-len(k))}{v}' for k, v in final_data.items() if k != 'record'))
    return final_data

def parse_file(file: str, parsefor: list, parseall: str) -> dict:
    parsed = {}
    for i in parsefor:
        parsed_id = scan.main(file, getattr(scan, f'match_{i}'))
        parsed[i] = parsed_id
        if parsed_id:
            logger.info(f'{i} found in file')
            if parseall == 'no':
                return parsed
        else: logger.info(f'{i} not found in file')
    return parsed
    
def do_job(args, cur):
    def do_directory(directory):
        cur.execute("INSERT INTO jobs (jobtype, file_or_dir) VALUES (?, ?)", ('dir_marker', directory))
        parentid = cur.execute("SELECT id FROM jobs WHERE rowid = (SELECT MAX(rowid) FROM jobs)").fetchone()[0]
        count = 1
        for subdir, dirs, files in os.walk(directory):
            files = [f for f in files if (f.endswith(i) for i in args.filetypes)]
            for f in files:
                logger.info(f"-------------------- \n [{count}]: {f}")
                fpath = os.path.join(subdir, f)
                logger.debug('file path: ', fpath)
                do_file(fpath, parentid)
                count += 1

        query = f"SELECT file_or_dir, catalog, lcc, ddc FROM jobs WHERE parentid = {parentid}"
        logger.log(STDINFO, '===============\n    SUMMARY    \n===============')
        dbviewer.print_sql_query(query, cur)     

    def do_file(file, parentid=None):
        fullpath = os.path.abspath(file)
        basepath = os.path.basename(fullpath)

        for i in cur.execute("SELECT file_or_dir FROM jobs").fetchall():
            if basepath == i[0]: 
                logger.info('already in DB, skipping..')
                return

        parsed = parse_file(fullpath, args.parsefor, args.parseall)
        logger.debug(parsed)

        if all(i is None for i in parsed.values()):
            logger.info('no identifiers found in file')
            return

        def get_at(lst, idx):
            return lst[idx] if idx < len(lst) else None
        
        id_type = get_at([i for i in parsed if i not in ('lcc', 'ddc') and parsed[i]], 0)
        data = search_catalogs(args.wait, args.retries, args.timeout, args.languages, args.altisbns, args.maxalts, args.classifiers, id_type, parsed)
        
        columns = ('jobtype', 'file_or_dir', 'fullpath', 'parentid') + tuple(k for k in data.keys())
        jobtype = {True: 'dir_file', False: 'file'}
        values = (jobtype[bool(parentid)], basepath, fullpath, parentid) + tuple(v for v in data.values())

        placeholders = ', '.join('?' for _ in columns)
        cur.execute(f"INSERT INTO jobs {columns} VALUES ({placeholders})", values)
        cur.execute("COMMIT")

    def do_isbn(isbn, parentid=None):
        data = search_catalogs(args.wait, args.retries, args.timeout, args.languages, args.altisbns, args.maxalts, args.classifiers, 'isbn', {'isbn': isbn})
        columns = ('jobtype', 'parentid') + tuple(k for k in data.keys())
        jobtype = {True: 'list_isbn', False: 'isbn'}
        values = (jobtype[bool(parentid)], parentid) + tuple(v for v in data.values())

        placeholders = ', '.join('?' for _ in columns)
        cur.execute(f"INSERT INTO jobs {columns} VALUES ({placeholders})", values)
        cur.execute("COMMIT")

    def do_isbn_list(self, list_file):
        cur.execute("INSERT INTO jobs (jobtype, file_or_dir) VALUES (?, ?)", ('isbn_list', list_file))
        parentid = cur.execute("SELECT id FROM jobs WHERE rowid = (SELECT MAX(rowid) FROM jobs)").fetchone()[0]

        with open(list_file) as f:
            for line in f:
                isbn = line.replace('-', '').strip()
                do_isbn(isbn, parentid)

    if os.path.isdir(args.input):
        do_directory(args.input)
        return

    if os.path.isfile(args.input):
        if any(args.input.endswith(i) for i in args.filetypes):
            do_file(args.input) 
        elif args.input.endswith('.txt'):
            do_isbn_list(args.input)
        else:
            logger.info(f"no files of type {args.filetypes}, txt")
        return

    try: 
        isbn = int(args.input.replace('-', ''))
    except ValueError:
        logger.info("please provide a file, directory, or isbn")
        return
    else:
        do_isbn(isbn)
        return


def main():
    con = sqlite3.connect(DATA_DIR / "libcat.db")
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        record TEXT,
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        jobtype TEXT,
        parentid,
        file_or_dir TEXT,
        fullpath TEXT,
        catalog TEXT,
        isbn TEXT,
        lcc TEXT,
        ddc TEXT,
        lcsh TEXT,
        recordtype TEXT
    )
    """)

    do_job(args, cur)

logger = logging.getLogger(__name__)
STDINFO = 25
logging.addLevelName(STDINFO, "STDINFO")

logging.basicConfig(level=25, format='%(message)s')


if __name__ == '__main__':
    if len(argv) > 1 and argv[1] == 'db':
        dbviewer.main(argv[2:])
        exit()

    class CustomHelpFormatter(argparse.HelpFormatter):
        def _format_action_invocation(self, action):
            if not action.option_strings or action.nargs == 0:
                return super()._format_action_invocation(action)
            default = self._get_default_metavar_for_optional(action)
            args_string = self._format_args(action, default)
            return ', '.join(action.option_strings) + ' ' + args_string
        def __init__(self, prog):
            super().__init__(prog, max_help_position=40, width=80)

    fmt = lambda prog: CustomHelpFormatter(prog)

    parser = argparse.ArgumentParser(prog="LibCat", formatter_class=fmt)

    parser.add_argument("input", default='none', nargs='?', help="file, directory, isbn, or 'db' to enter the database viewer")
    parser.add_argument('-t', "--filetypes", metavar='{.pdf, .epub}', nargs='+', choices=['.pdf', '.epub'], default=CFG['filetypes'], help="file types to parse if file or dir specified")
    parser.add_argument('-m', "--metadata", type=int, choices=[0, 1, 2], default=CFG['metadata'], help="search file metadata for identifiers (requires exiftool). 1 - before file content, 2 - after")
    parser.add_argument('-l', "--languages", metavar="<lang>", nargs='+', default=CFG['languages'], help="only return / search records in specific languages. Language codes: https://www.loc.gov/marc/languages/language_code.html")
    parser.add_argument('-pf', "--parsefor", metavar='<identifier>', nargs='+', choices=['lcc', 'lccn', 'isbn', 'ddc'], default=CFG['parsefor'], help="the identifiers to parse for in the file before searching catalogs")
    parser.add_argument('-pa', "--parseall", choices=['yes', 'no'], default=CFG['parseall'], help="extract all ids in parsefor from file as opposed to moving on with first id found")
    parser.add_argument('-c', "--catalogs", metavar='<shortcode>', nargs='+', choices=CFG['catalogs'].keys(), default=CFG['order'], help=f"the catalogs to use and order in which they are searched: {list(CFG['catalogs'].keys())}")
    parser.add_argument('-w', "--wait", type=int, metavar='<seconds>', default=CFG['wait'], help="number of seconds to wait after a failed request before retrying") # convert to float after
    parser.add_argument('-r', "--retries", type=int, metavar='<count>', default=CFG['retries'], help="number of retries when a request fails")
    parser.add_argument("--timeout", type=int, metavar='<seconds>', default=CFG['timeout'], help="number of seconds to wait for a response from server") # convert to float after
    parser.add_argument('-cl', "--classifiers", nargs='+', choices=['record', 'lcc', 'ddc', 'lcsh', 'isbn'], default=CFG['classifiers'], help="classifiers to retrieve from catalogs")
    parser.add_argument('-alt', "--altisbns", choices=['yes', 'no'], default=CFG['altisbns'], help="if original isbn returns no results, try using a work's alternative isbns")
    parser.add_argument('-ma', "--maxalts", metavar="<count>", type=int, default=50, help="maximum number of alternative isbns to consider before aborting")
    parser.add_argument('-v', '--verbose', action='count', default=0, help="verbosity of logging. -v: info, -vv: debug")
    parser.add_argument('--version', action='version', version='%(prog)s 0.1.0')

    args = parser.parse_args()

    logger.setLevel(max(0, 25 - args.verbose * 10))

    main()
