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


# exdir_list = args.exdir
# expage_list = args.expage
docs_formats = [
                '.doc', 'docx', '.dot', '.od', '.pdf', '.csv', '.rtf', '.PDF',
                '.RTF', '.txt', '.wps', '.xml', '.dbf', '.dif',
                '.prn', '.slk', '.xl', '.xps', '.pot', '.pp'
                ]

start_time = time.time()
dirName = 'log'

requests.packages.urllib3.disable_warnings()


class ScrappedSite():

    unique_links_objects = {} # unique Links objects on all Site
    pages = ['/'] # link urls of internal links
    pages_objects = [] # Page objects of Site
    # index = 0
    number_of_pages = 0
    pages_duplicates = {}
    settings = None
    # internal_docs = 0
    # internal_links = 0
    # external_links = 0

    all_site_links = {}

    def __init__(self, root):
        self.__root = root


    def __add_slash(self, url):
        if url[-1] != '/':
            return url + '/'
        return url


    def __redefine_input_url(self):
        '''Redefine url input parameter'''
        self.__root = self.__add_slash(self.__root)
        self.__root = self.__root[0:(self.__root.find('/', 8))]


    def process(self):
        # for internal_link in self.internal_links:
        #     internal_link.process()


        for i in self.pages:
            page = ScrappedPage(self.__root, i)
            page.page_parsing()

            for page_obj in page.page_links_objects:
                if page.page_links_objects[page_obj].link_type == 0 \
                    and page.page_links_objects[page_obj].link not in self.pages \
                        and page.page_links_objects[page_obj].is_document is False:
                    self.pages.append(page.page_links_objects[page_obj].link)
                    # print(page.page_links_objects[page_obj].link)

                if page.page_links_objects[page_obj].link_type is not None \
                    and page.page_links_objects[page_obj].link not in self.unique_links_objects:
                    self.unique_links_objects[page.page_links_objects[page_obj].link] = page.page_links_objects[page_obj]
            self.pages_objects.append(page)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for page_link in self.unique_links_objects:
                futures.append(executor.submit(self.unique_links_objects[page_link].make_request))
            for future in concurrent.futures.as_completed(futures):
                future.result()
        # l = [x.link for x in self.unique_links_objects.values() if x.link_type == 0 and x.is_document is False]
        # print((l)[:5]) # internal links 56
        # print(len([x for x in self.unique_links_objects.values()])) # unique links objects 188
        
        # # all links on one page object 74
        # print(([x.link for x in list(self.pages_objects[1].page_links_objects.values())][:5]))
        with open('links.csv', 'w') as file:
            writer = csv.writer(file, delimiter=';')
            writer.writerow(['page', 'link', 'link_status', 'link_type',
                            'is_document', 'error_message'])
            for page_obj in self.pages_objects:
                page_links_objects = list(page_obj.page_links_objects.values())
                for link_obj in page_links_objects:
                    if link_obj.status == 0 and any(link == link_obj.link for link in list(self.unique_links_objects.keys())):
                        link_obj.status = self.unique_links_objects[link_obj.link].status
                        link_obj.link_type = self.unique_links_objects[link_obj.link].link_type
                        link_obj.is_document = self.unique_links_objects[link_obj.link].is_document
                        link_obj.error_message = self.unique_links_objects[link_obj.link].error_message
                    # if link_obj.link in list(self.unique_links_objects.keys()):
                    writer.writerow([page_obj.page, link_obj.link, link_obj.status, link_obj.link_type, link_obj.is_document, link_obj.error_message])

                # self.all_site_links[page_obj.page] = [link for link in page_obj.page_links_objects.values()]
            # link_log.sort(key=lambda x: x[0])
            # writer.writerows(link_log)
            
            



    #     site = ScrappedSite()

    #     # Setup logger config file
    #     setup_logging()
        
    #     site.pages.append(site.url)

    #     site.redefine_input_url()


    #     while site.index == 0 or site.index < number_of_pages:
    #         page = ScrappedPage(site.pages[site.index])
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

# class ScrappedLinks():
    

# class ScrappedInternalLinks(ScrappedLinks):
#    external_links = []

# class ScrappedExternalLinks(ScrappedLinks):
#   internal_links = []


class ScrappedPage():

    page_links_objects = {}
    status = 0
    link_type = 0
    error_message = ''

    def __init__(self, __root, page):
        self.__root = __root
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


    # def find_empty_pages(self, page_code):
    #     '''Find out if page is empty'''
    #     empty_page = page_code.find_all(class_=args.empty)
    #     if len(empty_page) == 0:
    #         logger.warning('Page is empty or this class is not exist')


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


    # def get_number_of_pages(self):
    #     '''Get amount of pages to parse'''
    #     if args.onepage:
    #         self.page_parsing(self.url)
    #         self.number_of_pages = len(self.pages)
    #     else:
    #         self.number_of_pages = args.pages


    def page_parsing(self):
        '''This function finds and processes all
        links (including documents) on the self.

        Links are divided into internal and external,
        and added to the links dictionary.

        The internal ones are added separately to the pages list

        Attributes
        ----------
        __root : str
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
        # error_message = None

        try:
            response = requests.get(self.__root + self.page, verify=False)
            self.status = response.status_code
            # self.index += 1

        except Exception as exc:
            self.status = 404
            self.error_message = exc
            logger.error(f'{exc}')
            return
        # if self.index > 1:
        #     self.add_to_links(self.page, 0, status, error_message)

        # if self.status > 399:
        #     return
            # self.delete_from_pages(self.page)

        try:
            page_html = BeautifulSoup(response.text, 'lxml')
            a_tags = page_html.find_all('a')

            # if args.duplicate:
            #     self.find_duplicates(page_html, self.page)

            # if args.empty:
            #     self.find_empty_pages(page_html)

            self.page_links_objects = {lnk.get('href'): ScrappedLink(self.__root, self.page, lnk.get('href')) for lnk in a_tags}
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                for page_link in self.page_links_objects:
                    futures.append(executor.submit(self.page_links_objects[page_link].check_link))#, page=self.page, link=page_link))
                for future in concurrent.futures.as_completed(futures):
                    future.result()

        except Exception as exc:
            logger.error('System Error: ' + f'{exc}')



class ScrappedLink():

    links_on_page = {}
    # internal_links = []
    link_type = None
    # link_status = 0
    is_document = False
    error_message = ''
    status = 0

    def __init__(self, __root, page, link):
        self.__root = __root
        self.page = page
        self.link = link


    def add_to_pages(self, page):
        '''Add self page in pages list

        Attributes
        ----------
        page: str
            internal page to parse
        pages: list
            list of self pages
        '''
        # if page in self.pages or any(exclusion in page for exclusion in exdir_list):
        #     return
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
            self.links_on_page[link][1] = requests.get(self.__root + page, verify=False).status_code


    def check_link(self):
        regex1 = re.compile(r'#\w*')
        regex2 = re.compile(r'\+\d+')
        # status = 0
        # is_document = False
        # error_message = None

        if self.link is None or self.link == '' \
            or (self.link in self.links_on_page and self.page in self.links_on_page[self.link][2]):
            return

        if self.link[:4] == 'tel:' or self.link[:4] == 'fax:' \
            or 'mailto' in self.link or 'maito' in self.link \
            or regex2.search(self.link) or regex1.search(self.link) or self.link[-4:] == '.jpg':
            return

        if any(doc_format in self.link for doc_format in docs_formats):
            self.is_document = True
        if self.__root in self.link:
            self.link = self.link.replace(self.__root, '')

            if self.link[-1] != '/':
                self.link = self.link + '/'
            if self.link[0] != '/':
                self.link = '/' + self.link

        if 'http' in self.link:
            self.link_type = 1
            if self.link not in self.links_on_page.keys():
                try:
                    pass
                    # request = requests.get(link, verify=False, timeout=4)
                    # request.raise_for_status()
                    # status = request.status_code

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
            # self.add_to_links(link, 1, status, page, is_document, error_message)
        else:
            self.link_type = 0
            # if link[0] != '/' and page[-1] != '/':
            #     link = page + '/' + link
            if self.is_document is False:
                # self.add_to_pages(link)
                # self.internal_links.append(link)
                pass
            else:
                # self.internal_docs += 1
                try:
                    pass
                    # request = requests.get(self.__root + link,
                    #                         verify=False, timeout=4)
                    # status = request.status_code
                except Exception as err:
                    error_message = err
            # self.add_to_links(link, 0, status, page, is_document, error_message)

    
    def make_request(self):
        if self.link_type == 1:
            try:
                request = requests.get(self.link, verify=False, timeout=4)
                request.raise_for_status()
                self.status = request.status_code

            except requests.exceptions.HTTPError as err:
                self.status = 404
                self.error_message = err
            except requests.exceptions.SSLError as err:
                self.status = 495
                self.error_message = err
            except requests.exceptions.Timeout as err:
                self.status = 408
                self.error_message = err
            except requests.exceptions.TooManyRedirects as err:
                self.status = 302
                self.error_message = err
            except requests.exceptions.RequestException as err:
                self.status = 400
                self.error_message = err
            
        if self.link_type == 0:
            try:
                request = requests.get(self.__root + self.link,
                                       verify=False, timeout=4)
                self.status = request.status_code
            except Exception as err:
                self.error_message = err


        
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
            # if link_properties[1] < 400 and args.errors:
            #     continue
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


#######

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

# def init_settings():
#     return True

def main():
    # global index, number_of_pages
    global logger

    # logger = setup_logging()
    # if (logger is None):
    #     return

    # settings = None
    # if (not init_settings()):
    #     logger.exception("not valid settings")
    #     return
    logger = setup_logging()
    settings = define_args()
    site = ScrappedSite(settings.url)
    site.settings = settings
    # site.logger = logger
    # site.settings = settings
    #site.setup_args()
    site.process()


    # self.pages.append(self.url)
    # if args.pages > 1 and not args.onepage:
    #     self.page_parsing(self.pages[0])
    # self.get_number_of_pages()
    # self.redefine_input_url()

    # while self.index == 0 or self.index < number_of_pages:
    #     page = ScrappedPage(self.pages[self.index])
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
