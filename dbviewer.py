# !/usr/bin/env python

import logging
import sqlite3
import argparse
from selectolax.lexbor import LexborHTMLParser
import json
import requests
import tomllib
import csv

import recordparser
from libcat import DATA_DIR, CFG

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')

def print_sql_query(query, cur):
    def addwhspace(item, maxlen):
        item = str(item)
        itemlen = len(item)
        if itemlen > 49:
            item = item[:46] + '...'
            itemlen = 49
        result = ' '*(maxlen - itemlen) + item
        return result

    df = cur.execute(query).fetchall()

    desc = []
    for i in cur.description:
        desc.append((i[0], len(i[0])))

    maxlens = []
    for did, d in enumerate(desc):
        maxlen = d[1]
        for i in df:
            l = len(str(i[did]))
            if 49 > l > maxlen:
                maxlen = l
            if l > 49:
                maxlen = 49
        maxlens.append(maxlen)

    headers = ""
    for idi, i in enumerate(maxlens):
        item = addwhspace(desc[idi][0], i)
        headers += '  ' + item
    logger.info(headers)

    for i in df:
        line = ""
        for idj, j in enumerate(maxlens):
            item = addwhspace(i[idj], j)
            line += '  ' + item
        logger.info(line)

def main(input_args=''):
    def show_func(args):
        if args.all:
            query = "SELECT timestamp, id, file_or_dir, jobtype, catalog, isbn, lcc, ddc, recordtype FROM jobs"
            print_sql_query(query, cur)
            return
        if args.recent:
            query = "SELECT timestamp, id, file_or_dir, jobtype, catalog, isbn, lcc, ddc, recordtype FROM jobs ORDER BY timestamp DESC LIMIT 10"
            print_sql_query(query, cur)
            return
        if args.last:
            i = cur.execute("SELECT id FROM jobs WHERE jobtype in ('file', 'isbn', 'dir_marker', 'isbn_list') ORDER BY timestamp DESC LIMIT 1").fetchone()[0]
            if cur.execute(f"SELECT jobtype FROM jobs WHERE id = {i}").fetchone()[0] == 'dir_marker':
                query = f"SELECT timestamp, id, file_or_dir, jobtype, catalog, isbn, lcc, ddc, recordtype FROM jobs WHERE parentid = {i}"
                print_sql_query(query, cur)
                return
            query = f"SELECT * FROM jobs WHERE id = {i}"
            a = cur.execute(query).fetchall()
            b = cur.description
            for idi, i in enumerate(a[0]):
                if i:
                    if b[idi][0] == 'record':
                        i = str(i).replace('\\n', '\n')
                    print(f"{b[idi][0]}: {i}")
            print('\n')
        if args.jobtype:
            a = {
                'i': 'isbn',
                'isbn': 'isbn',
                'f': 'file',
                'file': 'file',
                'df': 'dir_file',
                'dir_file': 'dir_file',
                'd': 'dir_marker',
                'dir_marker': 'dir_marker',
                '': ''
            }

            n = dict(enumerate(args.jobtype))
            s = a[n.get(0, '')], a[n.get(1, '')], a[n.get(2, '')], a[n.get(3, '')]
            query = f"SELECT id, timestamp, jobtype, catalog, isbn, lcc, ddc, file_or_dir, FROM jobs WHERE jobtype in {s}"
            print_sql_query(query, cur)
        if args.ids:
            for i in args.ids:
                if cur.execute(f"SELECT jobtype FROM jobs WHERE id = {i}").fetchone()[0] == 'dir_marker':
                    query = f"SELECT timestamp, id, file_or_dir, jobtype, catalog, isbn, lcc, ddc, fullpath FROM jobs WHERE parentid = {i}"
                    print_sql_query(query, cur)
                    continue
                query = f"SELECT * FROM jobs WHERE id = {i}"
                a = cur.execute(query).fetchall()
                b = cur.description
                for idi, i in enumerate(a[0]):
                    if i:
                        if b[idi][0] == 'record':
                            i = str(i).replace('\\n', '\n')
                        print(f"{b[idi][0]}: {i}")
                print('\n')
            return

    def del_func(args):
        if args.everything:
            confirm = input('delete everything from the database? (Y/n)')
            if confirm == 'n':
                return
            tables = cur.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
            print(tables)
            for i in tables:
                cur.execute(f"DROP TABLE {i[0]}")
            cur.execute("COMMIT")
            logger.info("database emptied")
        if args.ids:
            confirm = input(f"delete {args.ids} (Y/n): ")
            if confirm == 'n':
                logger.info('cancelled')
                return
            for i in args.ids:
                cur.execute(f"DELETE FROM jobs WHERE id = {i}")
                cur.execute(f"DELETE FROM jobs WHERE parentid = {i}")
                cur.execute("COMMIT")
            logger.info(f"{args.ids} deleted")
            
    def zot_func(args):
        if args.ids:
            for i in args.ids:
                tozotero(i, cur, con)
        if args.last:
            last_id = cur.execute(f"SELECT id FROM jobs WHERE jobtype IN ('file', 'isbn', 'dir_marker') ORDER BY timestamp DESC LIMIT 1").fetchone()[0]
            tozotero(last_id, cur, con)

    def csv_func(args):
        if args.all:
            cur.execute("SELECT * FROM jobs")

            with open(DATA_DIR / 'libcat.csv', 'w', newline='') as f:
                writer = csv.writer(f)
                column_names = [desc[0] for desc in cur.description]
                writer.writerow(column_names)
                writer.writerows(cur.fetchall())

            print(F"Data exported to {DATA_DIR / 'libcat.csv'}")


    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers()
    parser_sh = subparsers.add_parser('show', help="show jobs", aliases=['sh'])
    parser_sh.add_argument('-a', '--all', action='store_true', help="show all")
    parser_sh.add_argument('-r', '--recent', action='store_true', help="show ten most recent jobs")
    parser_sh.add_argument('-j', '--jobtype', metavar='jobtype', nargs='+', choices=['i', 'isbn', 'f', 'file', 'd', 'dir_marker', 'df', 'dir_file'], help="show by job type; can be any or several of: isbn/i, file/f, dir_marker/dm, dir_file/df")
    parser_sh.add_argument('-i', '--ids', nargs='+', type=int, help="show full entries for given ids")
    parser_sh.add_argument('-l', '--last', action='store_true', help="show last job")
    parser_sh.add_argument('-e', '--exit', action='store_true', help="exit after completing actions")
    parser_sh.set_defaults(func=show_func)

    parser_del = subparsers.add_parser('delete', help="delete jobs", aliases=['del'])
    parser_del.add_argument('--everything', action='store_true', help="delete everything in the database")
    parser_del.add_argument('-i', '--ids', nargs='+', type=int, help="delete jobs by id")
    parser_del.add_argument('-e', '--exit', action='store_true', help="exit after completing actions")
    parser_del.set_defaults(func=del_func)

    parser_zot = subparsers.add_parser('tozotero', aliases=['zot'], help="add bibliographic entries to Zotero (requires better bibtex debug bridge)")
    parser_zot.add_argument('-i', '--ids', nargs='+', type=int, help="add by id")
    parser_zot.add_argument('-l', '--last', action='store_true', help="add the last job")
    parser_zot.add_argument('-e', '--exit', action='store_true', help="exit after completing actions")
    parser_zot.set_defaults(func=zot_func)

    parser_csv = subparsers.add_parser('tocsv', aliases=['csv'], help="export database to csv")
    parser_csv.add_argument('-a', '--all', action='store_true', default=True)
    parser_csv.add_argument('-o', '--outpath', type=str)
    parser_csv.add_argument('-e', '--exit', action='store_true', help="exit after completing actions")
    parser_csv.set_defaults(func=csv_func)

    if not input_args:
        input_args = input(">>> ").split()
        if input_args == []: return

    args = parser.parse_args(input_args)

    con = sqlite3.connect(DATA_DIR / "libcat.db")
    cur = con.cursor()

    args.func(args)

    con.commit()

    if args.exit:
        return
    
    try: 
        main()
    except:
        main()

    # con.close()

def process_marcxml(record, recordtype):
    fields = {}
    creators = []

    rec = getattr(recordparser, f'{recordtype}_record')(record)

    titlea, titleb = rec.get_title(split=True)
    fields['title'] = titlea + ' ' + titleb
    fields['shortTitle'] = titlea
    fields['series'] = rec.get_series()
    fields['place'] = rec.get_place()
    fields['publisher'] = rec.get_publisher()
    fields['date'] = rec.get_date()
    fields['ISBN'] = ', '.join(i for i in rec.get_isbn())
    fields['abstractNote'] = rec.get_summary()

    author = rec.get_author()
    if author: 
        author = author.split(', ')
        alast, afirst = recordparser.get_at(author, 0), recordparser.get_at(author, 1)
        author = f"{{firstName: '{afirst}', lastName: '{alast}', creatorType: 'author'}}"
        creators.append(author)

    contributors = rec.get_field(tag='700', first=False)
    for i in contributors:
        cname = rec.get_field(tree=i, codes=("a"))
        cname = cname.text().split(', ')
        last, first = recordparser.get_at(cname, 0), recordparser.get_at(cname, 1)

        ctype = rec.get_field(tree=i, codes=("e"))
        
        if ctype:
            ctype = ctype.text().lower()
            if ctype == 'translator':
                ctype = 'translator'
            if ctype == 'editor':
                ctype = 'editor'
        else: ctype = 'contributor'

        if author:
            if last == alast and first == afirst:
                continue

        contributor = {"firstName": first, "lastName": last, "creatorType": ctype}
        creators.append(contributor)

    return fields, creators


def tozotero(i, cur, con):
    def JSscript(fields: dict, creators: list) -> str:
        sfields = ""
        for i in fields:
            sfields += f"\nitem.setField('{i}', '{fields[i]}');"

        screators = "["
        for i in creators:
            screators += str(i) + ','
        screators += "]"

        item_type = 'book'

        content = f"""var item = new Zotero.Item('{item_type}');\nitem.setCreators({screators});{sfields}\nvar itemID = await item.saveTx();\nreturn itemID;"""
        return content

    a = cur.execute(f"SELECT catalog, record, recordtype, lcc, ddc, lcsh FROM jobs WHERE id = {i}").fetchall()
    for i in a:
        catalog = i[0]
        record = i[1]
        recordtype = i[2]
        if not record:
            logger.info('no record, skipping')
            continue

        
        fields, creators = process_marcxml(record, recordtype)

        fields['extra'] = '\\n'.join(f"tex.{['lcc', 'ddc', 'lcsh'][idi]}: {i}" for idi, i in enumerate(i[3:]))

        fields['libraryCatalog'] = catalog

        script = JSscript(fields, creators)
        logger.debug(script)

        token = CFG['tokens']['bbt_debug_bridge']
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'text/plain'
        }

        response = requests.post('http://127.0.0.1:23119/debug-bridge/execute', headers=headers, data=script.encode('utf-8'))

        logger.info(f'Status code\t{response.status_code}')
        logger.info(f'Zotero ID\t{response.text}')