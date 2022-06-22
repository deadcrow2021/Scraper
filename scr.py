#!/usr/bin/python3

import logging.config
import logging
import hashlib
import argparse
import time
import json
import sys
import csv
import os
import re

import concurrent.futures

import requests
from pprint import pprint
from bs4 import BeautifulSoup

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
                        nargs=1, required=True)
arg_parser.add_argument("--empty", help="Find empty pages "
                        "by the inputted class of HTML tag.")
arg_parser.add_argument("-d", "--duplicate", help="Find"
                        "duplicated pages on self.",
                        default=False, action="store_true")
arg_parser.add_argument("--exdir", help="Excludes the page and the "
                        "directory of nested pages.", nargs="+", default=[])
arg_parser.add_argument("--expage", help="Excludes the specified page.",
                        nargs="+", default=[])
args = arg_parser.parse_args()

exdir_list = args.exdir
expage_list = args.expage
docs_formats = [
                '.doc', '.dot', '.od', '.pdf', '.csv', '.rtf', '.PDF',
                '.RTF', '.txt', '.wps', '.xml', '.dbf', '.dif',
                '.prn', '.slk', '.xl', '.xps', '.pot', '.pp'
                ]

start_time = time.time()
dirName = 'log'

requests.packages.urllib3.disable_warnings()


class ProcessSite():

    root = args.url[0]
    # url = '/'
    links = []
    pages = ['/']
    index = 0
    number_of_pages = 0
    pages_duplicates = {}
    # internal_docs = 0
    # internal_links = 0
    # external_links = 0

    def add_slash(self, string):
        if string[-1] != '/':
            return string + '/'
        return string


    def redefine_input_url(self):
        '''Redefine url input parameter'''
        self.root = self.add_slash(self.root)
        self.root = self.root[0:(self.root.find('/', 8))]


    def process_page(self):
        for i in self.pages:
            page = ProcessPage(self.root, i)
            page.page_parsing()
            # print(page.page_links_objects[list(page.page_links_objects.keys())[0]].link)

    #     site = ProcessSite()

    #     # Setup logger config file
    #     setup_logging()
        
    #     site.pages.append(site.url)

    #     site.redefine_input_url()


    #     while site.index == 0 or site.index < number_of_pages:
    #         page = ProcessPage(site.pages[site.index])
    #         print(site.pages[site.index], site.pages[:5], site.index)
    #         page.page_parsing()
    #         if site.index == len(site.pages):
    #             break

    #         if args.pages == 0 and not args.onepage:
    #             number_of_pages = len(site.pages)

    #     if args.map:
    #         add_to_sitemap_file(self.pages)
    #     add_links_to_csv(self.links)
    #     add_to_debug_file(self.links)
    #     if args.statistics:
            # get_statistics(self.pages, self.internal_docs, self.internal_links, self.external_links)



class ProcessPage():

    page_links_objects = {}

    def __init__(self, root, page):
        self.root = root
        self.page = page

    def exclusion(self, page):
        '''Excludes a cpecific page out of parsing'''
        global expage_list
        expage_list_element = 0
        if expage_list == []:
            return False
        if not isinstance(expage_list, list):
            expage_list = expage_list.split(sep=' ')
        for expage in expage_list:
            if expage[0] != '/':
                expage = '/' + expage
            if expage[-1] != '/':
                expage = expage + '/'
            expage_list[expage_list_element] = expage
            expage_list_element += 1
        if page[0] != '/':
            page = '/' + page
        if page[-1] != '/':
            page = page + '/'
        return any(i == page for i in expage_list)


    def find_duplicates(self, page_code, page):
        '''Find duplicated pages on self'''
        hash = hashlib.sha256()
        hash.update(f'{page_code}'.encode())
        hash = hash.hexdigest()
        if hash in self.pages_duplicates.values():
            existing_page = list(self.pages_duplicates.keys())[list(self.pages_duplicates \
                                .values()).index(hash)]
            return logger.warning(f'Page {page} is duplicate of page {existing_page}')
        self.pages_duplicates.update({page: hash})


    def find_empty_pages(self, page_code):
        '''Find out if page is empty'''
        empty_page = page_code.find_all(class_=args.empty)
        if len(empty_page) == 0:
            logger.warning('Page is empty or this class is not exist')


    def delete_from_pages(self, page):
        '''Deletes page from self pages list

        Attributes
        ----------
        page: str
            internal page to parse
        '''
        if self.pages != [] and page in self.pages:
            self.index -= 1
            self.pages.remove(page)


    def get_number_of_pages(self):
        '''Get amount of pages to parse'''
        if args.onepage:
            self.page_parsing(self.url)
            self.number_of_pages = len(self.pages)
        else:
            self.number_of_pages = args.pages


    def page_parsing(self):
        '''This function finds and processes all
        links (including documents) on the self.

        Links are divided into internal and external,
        and added to the links dictionary.

        The internal ones are added separately to the pages list

        Attributes
        ----------
        root : str
            user-defined source page
        page : str
            internal page to parse
        index : int
            integer used to define what
            page from pages list to parse
        error_message : str
            error message received when requesting a page
        status : int
            HTTP status code from request
        link : str
            link found on the page
        '''
        logger.info("Processing " + self.page)
        error_message = None

        try:
            response = requests.get(self.root + self.page, verify=False)
            status = response.status_code
            # self.index += 1

        except Exception as exc:
            status = 400
            error_message = exc
            logger.error(f'{exc}')
        # if self.index > 1:
        #     self.add_to_links(self.page, 0, status, error_message)

        if status > 399:
            self.delete_from_pages(self.page)

        try:
            page_html = BeautifulSoup(response.text, 'lxml')
            a_tags = page_html.find_all('a')

            if args.duplicate:
                self.find_duplicates(page_html, self.page)

            if args.empty:
                self.find_empty_pages(page_html)

            self.page_links_objects = {lnk.get('href'): ProcessLink(self.root, self.page, lnk.get('href')) for lnk in a_tags}
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                for page_link in self.page_links_objects:
                    futures.append(executor.submit(self.page_links_objects[page_link].check_link, page=self.page, link=page_link))
                for future in concurrent.futures.as_completed(futures):
                    future.result()

        except Exception as exc:
            logger.error('System Error: ' + f'{exc}')



class ProcessLink():

    links_on_page = {}
    internal_links = []

    def __init__(self, root, page, link):
        self.root = root
        self.page = page
        self.link = link
        # link_type
        # link_status
        # is_document
        # error_message


    def add_to_pages(self, page):
        '''Add self page in pages list

        Attributes
        ----------
        page: str
            internal page to parse
        pages: list
            list of self pages
        '''
        if page in self.pages or any(exclusion in page for exclusion in exdir_list):
            return
        if self.exclusion(page):
            return
        self.pages.append(page)


    def add_to_links(self, link, link_type, link_status=None, page=None,
                    is_document=False, error_message=None):
        '''Add to links dictionary information
        about self links and documents

        Attributes
        ----------
        internal_links : int
            Number of internal links on the self
        external_links : int
            Number of external links on the self
        '''
        if link_type == 1:
            if link_status > 0:
                self.links_on_page.update({link: [link_type, link_status, [page],
                            is_document, error_message]})
                # self.external_links += 1
            elif page not in self.links_on_page[link][2]:
                self.links_on_page[link][2].append(page)
        else:
            if link not in self.links_on_page:
                self.links_on_page.update({link: [link_type, link_status, [page],
                            is_document, error_message]})
                # self.internal_links += 1
            elif link_status > 0 and self.links_on_page[link][1] == 0:
                self.links_on_page[link][1] = link_status
            elif page not in self.links_on_page[link][2] and page is not None:
                self.links_on_page[link][2].append(page)
        if self.links_on_page[link][1] == 0:
            self.links_on_page[link][1] = requests.get(self.root + page, verify=False).status_code


    def check_link(self, page, link):
        regex1 = re.compile(r'#\w*')
        regex2 = re.compile(r'\+\d+')
        status = 0
        is_document = False
        error_message = None

        if link is None or link == '' \
            or (link in self.links_on_page and page in self.links_on_page[link][2]):
            return

        if link[:4] == 'tel:' or link[:4] == 'fax:' \
            or 'mailto' in link or 'maito' in link \
            or regex2.search(link) or regex1.search(link) or link[-4:] == '.jpg':
            return

        if any(doc_format in link for doc_format in docs_formats):
            is_document = True
        if self.root in link:
            link = link.replace(self.root, '')

        if 'http' in link:
            if link not in self.links_on_page.keys():
                try:
                    request = requests.get(link, verify=False, timeout=4)
                    request.raise_for_status()
                    status = request.status_code

                except requests.exceptions.HTTPError as err:
                    status = 404
                    error_message = err
                except requests.exceptions.SSLError as err:
                    status = 495
                    error_message = err
                except requests.exceptions.Timeout as err:
                    status = 408
                    error_message = err
                except requests.exceptions.TooManyRedirects as err:
                    status = 302
                    error_message = err
                except requests.exceptions.RequestException as err:
                    status = 400
                    error_message = err
            self.add_to_links(link, 1, status, page, is_document, error_message)
        else:
            # if link[0] != '/' and page[-1] != '/':
            #     link = page + '/' + link
            if is_document is False:
                # self.add_to_pages(link)
                self.internal_links.append(link)
            else:
                # self.internal_docs += 1
                try:
                    request = requests.get(self.root + link,
                                            verify=False, timeout=4)
                    status = request.status_code
                except Exception as err:
                    error_message = err
            self.add_to_links(link, 0, status, page, is_document, error_message)
# Link
######

def add_to_sitemap_file(pages):
    '''Add to file list of internal pages'''
    with open('sitemap.csv', 'w') as file:
        writer = csv.writer(file)
        writer.writerow(['page'])
        for page in sorted(pages):
            writer.writerow([page])


def add_to_debug_file(links):
    '''Add to file all self links.

    Output format
    -------------
    {link: [link_type, link_status, [page], is_document, error_message], ...}
    '''
    orig_stdout = sys.stdout
    f = open('debug.txt', 'w')
    sys.stdout = f
    pprint(links)
    sys.stdout = orig_stdout
    f.close()


def add_links_to_csv(links):
    '''Add to csv file errors on self'''
    with open('links.csv', 'w') as file:
        link_log = []
        writer = csv.writer(file, delimiter=';')
        writer.writerow(['page', 'link', 'link_status', 'link_type',
                         'is_document', 'error_message'])

        for link, link_properties in links.items():
            if link_properties[1] < 400 and args.errors:
                continue
            for page in link_properties[2]:
                link_log.append([page, link, link_properties[1],
                                 link_properties[0], link_properties[3],
                                 link_properties[4]])
        link_log.sort(key=lambda x: x[0])
        writer.writerows(link_log)
    file.close()


def get_statistics(pages, internal_docs, internal_links, external_links):
    '''Get statistics of executed program in console'''
    logger.info('Links in pages: {}'.format(len(pages)))
    logger.info('Internal documents: {}'.format(internal_docs))
    logger.info('Internal links: {}'.format(internal_links))
    logger.info('External links: {}'.format(external_links))
    logger.info('Code execution time: {} seconds'
                .format("%.2f" % (time.time() - start_time)))


def setup_logging(default_path='logging.json',
                  default_level=logging.INFO, env_key='LOG_CFG'):
    """Setup logging configuration"""
    global logger
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
    logger = logging.getLogger('File logger')


def main():
    # global index, number_of_pages
    setup_logging()

    site = ProcessSite()
    site.process_page()


    # self.pages.append(self.url)
    # if args.pages > 1 and not args.onepage:
    #     self.page_parsing(self.pages[0])
    # self.get_number_of_pages()
    # self.redefine_input_url()

    # while self.index == 0 or self.index < number_of_pages:
    #     page = ProcessPage(self.pages[self.index])
    #     print(self.pages[self.index], self.pages[:5], self.index)
    #     page.page_parsing()
    #     if self.index == len(self.pages):
    #         break

    #     if args.pages == 0 and not args.onepage:
    #         number_of_pages = len(self.pages)

    # if args.map:
    #     add_to_sitemap_file(self.pages)
    # add_links_to_csv(self.links)
    # add_to_debug_file(self.links)
    # if args.statistics:
    #     get_statistics(self.pages, self.internal_docs, self.internal_links, self.external_links)


if __name__ == '__main__':
    main()
