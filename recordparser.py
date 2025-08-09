# !/usr/bin/env python

import logging
from selectolax.lexbor import LexborHTMLParser
import json

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')

def get_at(lst, idx):
    return lst[idx] if idx < len(lst) else None

def try_method(method):
    try:
        return method()
    except:
        return None

def tidy(text, a=0):
    # if not text: return ''
    if a == 0:
        for i in ('[', ']', ',', '.', ':', '/', ';'):
            if text.endswith(i):
                text = text.replace(i, '')

    text = text.replace("\\'", "'").replace("'", "\\'").strip()
    text = text.replace("\\'", "'")

    return text

def to_str(items, delim):
    return delim.join(i for i in items) if isinstance(items, list) else items

class marcxml_record():
    def __init__(self, marcxml):
        self.marcxml = marcxml
        self.tree = LexborHTMLParser(marcxml)

    def get_field(self, tree=None, tag='', ind1='', ind2='', codes=(), first=True):
        if not tree: tree = self.tree

        dattrs = [('tag', tag), ('ind1', ind1), ('ind2', ind2)]
        datafield = ''.join(f'[{a}="{v}"]' for a, v in dattrs if v)
        subfields = f""":is({','.join(f'[code="{c}"]' for c in codes)})""" if codes else None
        selector = ' > '.join(i for i in (datafield, subfields) if i)
        # selector = '[tag="650"]'
        logger.debug('css selector:', selector)   

        result = tree.css_first(selector) if first else tree.css(selector)
        # print(type(result))
        return result


    def get_record(self):
        return self.marcxml

    def get_title(self, split=False):
        title = self.get_field(tag='245', codes=('a', 'b'), first=False)

        if split:
            titlea = get_at(title, 0)
            titleb = get_at(title, 1)
            return tidy(titlea.text()) if titlea else '', tidy(titleb.text()) if titleb else ''
        
        return tidy(''.join(i.text() for i in title))

    def get_series(self):
        series = self.get_field(tag='490', codes=['a']) or self.get_field(tag='440', codes=['a'])
        return tidy(series.text(), 0)
        # none case?

    def get_place(self):
        place = self.get_field(tag='260', codes=['a']) or self.get_field(tag='264', codes=['a'])
        return tidy(place.text())
        # none case?

    def get_publisher(self):
        publisher = self.get_field(tag='260', codes=['b']) or self.get_field(tag='264', codes=['b'])
        return tidy(publisher.text())

    def get_date(self):
        date = self.get_field(tag='260', codes=['c']) or self.get_field(tag='264', codes=['c'])
        return tidy(date.text())
        # tidy beginning [?

    def get_isbn(self) -> list:
        isbns = self.get_field(tag='020', codes=['a'], first=False)
        return [i.text() for i in isbns]

    def get_lcc(self, split=False) -> str or tuple:
        lcc = self.get_field(tag='050', codes=('a', 'b'), first=False)
        class_no = get_at(lcc, 0)
        if class_no: class_no = class_no.text()
        item_no = get_at(lcc, 1)
        if item_no: item_no = item_no.text()

        if split:
            return class_no, item_no
        return class_no + ' ' + (item_no or '')

    def get_ddc(self) -> str:
        ddc = self.get_field(tag='082', codes=('a'))
        return ddc.text()

    def get_lcsh(self):
        datafields = self.get_field(tag='650', first=False) or []
        headings = []
        for i in datafields:
            subdivisions = self.get_field(tree=i, codes=('a', 'v', 'x', 'y', 'z'), first=False)
            heading = tidy('--'.join(j.text(strip=True) for j in subdivisions))
            headings.append(heading)
        return to_str(headings, ' | ')

    def get_summary(self):
        summary = self.get_field(tag='520', codes=['a'])
        return tidy(summary.text(), 1) if summary else ''

    def get_author(self):
        author = self.get_field(tag="100", codes=['a'])
        return author.text()
        # case for None
        # tidy as well?

    def get_contributors(self) -> list:
        contributors = self.get_field(tag='700', codes=['a'], first=False) or []
        contributors = [i.text() for i in contributors]
        return contributors
        # not checking for editor vs translator?

    def get_language(self):
        language = self.get_field(tag="008").text()[35:38]
        return language


class openl_record():
    def __init__(self, array):
        self.array = array['details']['details'] if array.get('details') else array
        self.data = array.get('data')

    def get_works(self):
        return self.array['works'][0]

    def get_title(self):
        return self.array['title']

    def get_publishers(self):
        return self.array['publishers'][0]

    def get_date(self):
        return self.array['publish_date']

    def get_isbn(self) -> list:
        return (self.array.get('isbn_13') or []) + (self.array.get('isbn_10') or [])

    # def get_contributors(self):
    def get_lcc(self):
        lcc = self.array.get('lc_classifications') or []
        if lcc:
            return lcc[0]
        return None

    def get_ddc(self):
        ddc = self.array.get('dewey_decimal_class') or []
        if ddc:
            return ddc[0]
        return None

    def get_language(self):
        lang = self.array.get('languages') or []
        if lang and 'key' in lang[0]:
            return lang[0]['key'][-3:]
        return None

    def get_author(self):
        return self.data.get('authors')[0]['name']



    

        