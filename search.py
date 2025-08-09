# !/usr/bin/env python

import logging
import tomllib
import time
import requests
import re
import json
from selectolax.lexbor import LexborHTMLParser

import recordparser

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(message)s')

class Search():
    def __init__(self, wait, retries, timeout, _id, id_type, langs, classifiers, cdict):
        self.wait = wait
        self.retries = retries
        self.timeout = timeout
        self._id = _id
        self.id_type = id_type
        self.langs = langs
        self.classifiers = classifiers
        self.cdict = cdict

    def extract_fields(self, record) -> dict:
        recordObj = getattr(recordparser, f"{self.cdict['recordtype']}_record")(record)

        # check language
        if self.langs:
            for l in self.langs:
                if l == recordObj.get_language():
                    continue
                else:
                    logger.info(f"\t\tskipping: language not in {self.langs}")
                    return {}

        fields = {}
        for cl in self.classifiers:
            try:
                fields[cl] = getattr(recordObj, f'get_{cl}')()
            except:
                continue
    
        return fields
        
    def request_or_retry(self, request, retry=0):
        max_retries = self.retries
        # logger.info(self.url)

        if retry == max_retries:
            return None, None
        
        try:
            return request()
        except Exception as e:
            e = str(e)
            logger.debug(f'{e}')
            logger.info(f"\t\t{(e[:28] + '..') if len(e) > 28 else e} attempt: {retry}")
            retry += 1
            time.sleep(self.wait)
            callnums = self.request_or_retry(request, retry)
            return callnums

class SRU(Search):
    def __init__(self, wait, retries, timeout, _id, id_type, langs, classifiers, cdict):
        super().__init__(wait, retries, timeout, _id, id_type, langs, classifiers, cdict)
        self.base_url = self.cdict['base_url']
        self.query = cdict['query']
        self.srumain = "?operation=searchRetrieve&version=1.2&maximumRecords=1&recordSchema=marcxml&query="
        self.url = f"{self.base_url}{self.srumain}{self.query}={self._id}"

    def request(self):
        # logger.info(self.url)
        print(self.url)
        r = requests.get(self.url, timeout = self.timeout)

        tree = LexborHTMLParser(r.content)

        if tree.css_first('record'):
            return tree, r

        # check number of records
        numrecs = tree.css_first('zs\\:numberOfRecords, numberOfRecords')
        if numrecs:
            if numrecs.text() == '0':
                logger.info('\t\tno records in catalog')   
                return None, None  
         
        raise Exception(f"\t\terror, {tree.css_first('title').text()}")

    def main(self):
        tree, r = super().request_or_retry(self.request)
        return super().extract_fields(r.content) if tree else {}
        
class Alma(SRU):
    def __init__(self, wait, retries, timeout, _id, id_type, langs, classifiers, cdict):
        super().__init__(wait, retries, timeout, _id, id_type, langs, classifiers, cdict)
        self.inst_code = self.cdict['inst_code']
        self.url = f"https://{self.base_url}/view/sru/{self.inst_code}{self.srumain}alma.isbn={_id}"
    
    def main(self):
        callnums = super().main()
        return callnums

class Hathi(Search):
    def __init__(self, wait, retries, timeout, _id, id_type, langs, classifiers, cdict):
        super().__init__(wait, retries, timeout, _id, id_type, langs, classifiers, cdict)
        self.url = f"https://catalog.hathitrust.org/api/volumes/full/isbn/{self._id}.json"

    def request(self):
        logger.debug(self.url)
        print(self.url)
        # logger.info(self.url)
        r = requests.get(self.url, timeout = self.timeout)
        array = json.loads(r.content)
        if len(array['records']) == 0:
            return None, None
        a = list(array['records'].keys())
        a = a[0]

        marcxml = array['records'][a]['marc-xml']
        tree = LexborHTMLParser(marcxml)
        return tree, marcxml

    def main(self):
        tree, marcxml = super().request_or_retry(self.request)
        return super().extract_fields(marcxml) if tree else {}

class Openl(Search):
    def __init__(self, wait, retries, timeout, _id, id_type, langs, classifiers, cdict):
        super().__init__(wait, retries, timeout, _id, id_type, langs, classifiers, cdict)
        self.base_url = self.cdict['base_url']
        self.url = f"https://{self.base_url}/{self._id}.json"

    def request(self):
        logger.debug(self.url)
        print(self.url)
        r = requests.get(self.url, timeout = self.timeout)
        array = json.loads(r.content)
        if array == []: return None
        record = array['records']
        a = list(record)[0]
        return record[a]

    def main(self):
        array = super().request_or_retry(self.request)
        return super().extract_fields(array) if array else {}

class Bdirect(Search):
    def __init__(self, wait, retries, timeout, _id, id_type, langs, classifiers, cdict):
        super().__init__(wait, retries, timeout, _id, id_type, langs, classifiers, cdict)
        self.url = f"https://borrowdirect.reshare.indexdata.com/api/v1/search?type=AllFields&field[]=fullRecord&lookfor={self._id}"

    def request(self):
        logger.debug(self.url)
        print(self.url)
        r = requests.get(self.url, timeout = self.timeout)

        array = json.loads(r.content)
        if array['resultCount'] == 0:
            return None, None
        marcxml = array['records'][0]['fullRecord']
        tree = LexborHTMLParser(marcxml)

        return tree, marcxml
    
    def main(self):
        tree, marcxml = super().request_or_retry(self.request)
        return super().extract_fields(marcxml) if tree else {}

class fetch_openl_alt(Search):
    def __init__(self, wait, retries, timeout, _id, id_type, langs, classifiers, cdict):
        super().__init__(wait, retries, timeout, _id, id_type, langs, classifiers, cdict)
        self.url = f"https://openlibrary.org/search.json?q=isbn={self._id}&fields=isbn,lcc,ddc"

    def request(self):
        # logger.info(self.url)
        print(self.url)
        r = requests.get(self.url, timeout = self.timeout)
        return json.loads(r.content)['docs']

    def main(self):
        array = super().request_or_retry(self.request)
        if array:
            alt_isbns = array[0].get('isbn')
            alt_lcc = array[0].get('lcc')
            alt_ddc = array[0].get('ddc')

            return alt_isbns, alt_lcc, alt_ddc
        return None, None, None

class fetch_openl_alt_filtered(Search):
    def __init__(self, wait, retries, timeout, _id, id_type, langs, classifiers, cdict):
        super().__init__(wait, retries, timeout, _id, id_type, langs, classifiers, cdict)

    def request_1(self):
        self.url = f"https://openlibrary.org/isbn/{self._id}.json"
        # logger.debug(self.url)
        print(self.url)
        r = requests.get(self.url, timeout = self.timeout)
        array = json.loads(r.content)
        work = array['works'][0]['key']
        return work

    def request_2(self):
        self.url = f"https://openlibrary.org{self.work}/editions.json?limit=100&offset={self.offset}"
        # logger.debug(url)
        print(self.url)
        r = requests.get(self.url, timeout = self.timeout)
        array = json.loads(r.content)
        entries = array['entries']
        return entries

    def main(self):
        self.work = super().request_or_retry(self.request_1)

        alt_isbns = []
        alt_lccs = []
        alt_ddcs = []
        entries = True
        self.offset = 0
        while entries:
            entries = super().request_or_retry(self.request_2)
            for i in entries:
                rec = recordparser.openl_record(i)

                lang = rec.get_language()
                if lang not in self.langs:
                    continue
                
                isbns = rec.get_isbn()
                if isbns: alt_isbns.extend(isbns)

                lcc = rec.get_lcc()
                if lcc: alt_lccs.append(lcc)

                ddc = rec.get_ddc()
                if ddc: alt_ddcs.append(ddc)
                
            self.offset += 100
        
        return alt_isbns, alt_lccs, alt_ddcs

def get_most_common_lcc(a: list) -> str:
    a = [i.split(' ')[0] for i in a]
    a = [(i, a.count(i)) for i in a]
    a = list(set(a))
    a.sort(key = lambda x: x[1])
    return a[-1][0].replace('.00000000', '').replace('-000', '').replace('-00', '').replace('-0', '').replace('-', '')

def get_most_common_ddc(a: list) -> str:
  a = [i[:5] for i in a]
  a = [(i, a.count(i)) for i in a]
  a = list(set(a))
  a.sort(key = lambda x: x[1])
  return a[-1][0]