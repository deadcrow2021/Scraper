from urllib.parse import urlparse
from bs4 import BeautifulSoup
from datetime import datetime
from pprint import pprint

import concurrent.futures
import logging.config
import requests
import argparse
import logging
import hashlib
import time
import json
import sys
import csv
import os
import re



docs_formats = [
                '.doc', 'docx', '.dot', '.od', '.pdf', '.csv',
                '.rtf', '.txt', '.wps', '.xml', '.dbf', '.dif',
                '.prn', '.slk', '.xl', '.xps', '.pot', '.pp'
                ]
docs_formats += [f.upper() for f in docs_formats]
dirName = 'log'
requests.packages.urllib3.disable_warnings()




class ScrappedSite():
    # pages = []
    links = []
    settings = None
    logger = None

    def __init__(self, url):
        #if (!is_valid(url))
        #    return
        # self.logger = logger
        self.url = url
        self.site_name = urlparse(url).netloc
        self.origin = urlparse(url).scheme + '://' + self.site_name


    def get_origin(self):
        return self.origin


    def crawl_links(self):
        first_link = ScrappedInternalLink(self.url, self.origin, self.logger)
        first_link.get_link_time = datetime.now()
        self.links.append(first_link)
        for link in self.links:
            error_message = ''

            if link.link_type != 1 or link.document_type is not None:
                continue

            # related_link_urls = 
            # link.get_request()
            # link.parse_text()
            # if len(link.related_link_urls) == 0:
            #     continue

            response = link.get_request() # page links
            if response.status_code >= 400:
                continue

            url = response.url
            if url in [link.final_url for link \
                    in self.links if (type(link).__name__ == 'ScrappedInternalLink' \
                    and link.document_type is None)] \
                    and len(self.links) > 1:
                # self.links.remove(link)
                error_message = 'An empty url path. The URL may be repeated. Check link.'
                link.error_message = error_message
                continue

            link.final_url = response.url
            link.parse_text(response.text)
            self.add_new_links(link, link.related_link_urls)


    def add_new_links(self, instance, urls):
        for url in urls:
            error_message = ''
            new_link = None
            
            if url == None:
                continue

            if ' ' in url:
                url = url.replace(' ', '')
                error_message = 'A whitespace in the url adress.'

            if url in [link.url for link in self.links]:
                continue

            #
            if (re.compile(r'#\w*')).search(url) or urlparse(url).fragment:
                continue
            # tel
            if (re.compile(r'\+\d+')).search(url) or 'tel' in url:
                new_link = ScrappedLink(url, 5)

            # mail
            elif 'mailto' in url:
                new_link = ScrappedLink(url, 4)

            # external
            elif self.site_name not in url and 'http' in url:
                
                new_link = ScrappedExternalLink(url, self.logger)
                if any(doc_format in url for doc_format in docs_formats):
                    new_link.document_type = 2
            
            # internal 
            elif (urlparse(url).netloc == '' or self.site_name in url):
                link_url_path = urlparse(url).path
                # if link_url_path in ('', '/'):
                #     error_message = 'An empty url path. The URL may be repeated. Check link.'
                #     continue
                if link_url_path in [link.url for link in self.links]:
                    continue
                
                new_link = ScrappedInternalLink(url, self.origin, self.logger)
                if any(doc_format in url for doc_format in docs_formats):
                    new_link.document_type = 2
            else:
                continue

            new_link.get_link_time = instance.get_link_time
            new_link.error_message = error_message
            self.links.append(new_link)


    def do_requests(self):
        print(len([x.url for x in self.links if type(x).__name__ == 'ScrappedInternalLink' and x.document_type != 2]))
        not_requested_links = ([x for x in self.links if type(x).__name__ == 'ScrappedExternalLink' \
            or (type(x).__name__ == 'ScrappedInternalLink' and x.document_type is not None)])
        print(len(not_requested_links))
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for url in not_requested_links:
                futures.append(executor.submit(url.get_request))
            for future in concurrent.futures.as_completed(futures):
                future.result()


    def write_results(self):
        with open('links.csv', 'w') as file:
            writer = csv.writer(file, delimiter=';')
            writer.writerow(['page', 'link', 'link_status', 'link_type',
                            'is_document', 'error_message'])
            for page in self.links:
                writer.writerow([page.url, '', page.http_status, page.link_type, page.document_type, page.error_message])
                if page.link_type == 1 and page.document_type is None:
                    for link in page.related_link_urls:
                        for link_obj in self.links:
                            if link == link_obj.url:
                                writer.writerow([page.url, link, link_obj.http_status, link_obj.link_type, link_obj.document_type, link_obj.error_message])
            print('done')



            # for url in related_link_urls:
            #     link_type = self.check_link(url)
            #     if link_type == 1:
            #         url = ScrappedInternalLink(url)
            #         url.

            #         #link <-> url
            #         pass
            #     elif link_type == 2:
            #         url = ScrappedExternalLink(url)

            #         pass
            #     else:
            #         url = ScrappedLink(url)

            #     self.links.append(url)
            #     ... 



    # def crawl_links(self):
    #     # if (not self.__is_valid):
    #     #     self.logger.write("")
    #     #     return

    #     self.__redefine_input_url()
    #     for link in self.links: # link = ScrappedLink(self.__root)
    #         link.process()

    #         link.check_link()
    #         # if link.link_type == 1:
    #         #     internal_link = 


    def __add_slash(self, url):
        if url[-1] != '/':
            return url + '/'
        return url


    def __redefine_input_url(self):
        '''Redefine url input parameter'''
        self.__root = self.__add_slash(self.__root)
        self.__root = self.__root[0:(self.__root.find('/', 8))]




class ScrappedLink():
    protocol = None
    # link_type = None # 0 not defined 1 internal 2 external 3 anchor 4 email 5 phone
    http_status = None
    document_type = None # 0 not defined 1 page 2 doc or pdf document 3 css 4 js 5 img ... 
    error_message = ''
    related_link_urls = []
    get_link_time = ''
    request_link_time = ''
    process_link_time = ''

    def __init__(self, url, link_type):
        self.url = url
        self.link = urlparse(url).path
        self.link_type = link_type
        # self.url = url # https://www.example.com/page1
        # self.__root = urlparse(url).scheme + '://' + urlparse(url).netloc # https://www.example.com
        # self.site_name = urlparse(url).netloc # www.example.com

    def get_request(self):
        self.logger.info("Processing " + self.url)

        self.request_link_time = datetime.now()
        response = requests.models.Response()
        try:
            if urlparse(self.url).netloc == '':
                response = requests.get(self.origin + self.url, verify=False, timeout=4)
            else:
                response = requests.get(self.url, verify=False, timeout=4)

        except requests.exceptions.HTTPError as exc:
            response.status_code = 404
            response.reason = exc
        except requests.exceptions.SSLError as exc:
            response.status_code = 495
            response.reason = exc
        except requests.exceptions.Timeout as exc:
            response.status_code = 408
            response.reason = exc
        except requests.exceptions.TooManyRedirects as exc:
            response.status_code = 302
            response.reason = exc
        except requests.exceptions.RequestException as exc:
            response.status_code = 400
            response.reason = exc
        except Exception as exc:
            response.status_code = 400
            response.reason = exc
            self.logger.error(f'{exc}')

        self.http_status = response.status_code
        if (self.http_status > 399):
            self.error_message = str(response.reason) + ' | ' + str(self.error_message)

        self.process_link_time = datetime.now()
        return response




class ScrappedInternalLink(ScrappedLink):
    link_type = 1
    # page_text_hash = ''
    final_url = ''

    def __init__(self, url, origin, logger):
        self.url = url
        self.origin = origin
        self.logger = logger

        # if self.index > 1:
        #     self.add_to_links(self.page, 0, status, error_message)

        # if self.status > 399:
        #     return
            # self.delete_from_pages(self.page)



    def parse_text(self, response_text):
        try:
            page_html = BeautifulSoup(response_text, 'lxml')
            a_tags = page_html.find_all('a')

            # if args.duplicate:
            #     self.find_duplicates(page_html, self.page)

            # if args.empty:
            #     self.find_empty_pages(page_html)

            self.related_link_urls = [link.get('href') for link in a_tags]
            self.process_link_time = datetime.now()

        except Exception as exc:
            self.logger.error('System Error: ' + f'{exc}')


    # def _encode_page(self, page_code):
    #     hash = (hashlib.sha256())
    #     hash.update((f'{page_code}').encode())
    #     hash = hash.hexdigest()
    #     return hash




class ScrappedExternalLink(ScrappedLink):
    link_type = 2
    def __init__(self, url, logger):
        self.url = url
        self.logger = logger





def define_args():
    arg_parser = argparse.ArgumentParser(description='A program for self parsing.')
    arg_parser.add_argument("-p", "--pages", help="Number of pages to parse, "
                            "default is all pages.", default=0, type=int)
    arg_parser.add_argument("-s", "--statistics", help="Add statistics of program "
                            "execution at the end of output.",
                            default=False, action="store_true")
    arg_parser.add_argument("-m", "--map", help="Add sitemap file 'sitemap.csv' "
                            "to the current folder.", default=False,
                            action="store_true")
    arg_parser.add_argument("-o", "--onepage", help="Parse only one page and "
                            "all links on it. If this argument is included, "
                            "--page is ignored.", default=False,
                            action="store_true")
    arg_parser.add_argument("-e", "--errors", help="Outputs errors on self into "
                            "file 'links.csv'.", default=False,
                            action="store_true")
    arg_parser.add_argument("-u", "--url", help="Add self url you "
                            "want to parse. Required argument. "
                            "Example: https://example.com.",
                            type=str, required=True)
    arg_parser.add_argument("--empty", help="Find empty pages "
                            "by the inputted class of HTML tag.")
    arg_parser.add_argument("-d", "--duplicate", help="Find"
                            "duplicated pages on self.",
                            default=False, action="store_true")
    arg_parser.add_argument("--exdir", help="Excludes the page and the "
                            "directory of nested pages.", nargs="+", default=[])
    arg_parser.add_argument("--expage", help="Excludes the specified page.",
                            nargs="+", default=[])
    return arg_parser.parse_args()


def setup_logging(default_path='logging.json',
                  default_level=logging.INFO, env_key='LOG_CFG'):
    """Setup logging configuration"""
    # global logger
    path = default_path
    value = os.getenv(env_key, None)

    # Creating folder for log files, if not exist
    if not os.path.isdir(dirName):
        os.mkdir(dirName)

    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = json.load(f)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)
    return logging.getLogger('File logger')


def main():
    logger = setup_logging()
    if not logger:
        return

    settings = None
    settings = define_args()
    if not settings:
        logger.exception("not valid settings")
        return
 
    site = ScrappedSite(settings.url)
    site.settings = settings
    site.logger = logger
    site.crawl_links()
    site.do_requests()
    site.write_results()


if __name__ == '__main__':
    main()
