#!/usr/bin/python3

import logging.config
import logging
import hashlib
import asyncio
import argparse
import time
import json
import sys
import csv
import os
import re

import requests
from pprint import pprint
from bs4 import BeautifulSoup

arg_parser = argparse.ArgumentParser(description='A program for site parsing.')
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
arg_parser.add_argument("-e", "--errors", help="Outputs errors on site into "
                        "file 'links.csv'.", default=False,
                        action="store_true")
arg_parser.add_argument("-u", "--url", help="Add site url you "
                        "want to parse. Required argument. "
                        "Example: https://example.com.",
                        nargs=1, required=True)
arg_parser.add_argument("--empty", help="Find empty pages "
                        "by the inputted class of HTML tag.")
arg_parser.add_argument("-d", "--duplicate", help="Find"
                        "duplicated pages on site.",
                        default=False, action="store_true")
arg_parser.add_argument("--exdir", help="Excludes the page and the "
                        "directory of nested pages.", nargs="+", default=[])
arg_parser.add_argument("--expage", help="Excludes the specified page.",
                        nargs="+", default=[])
args = arg_parser.parse_args()

exdir_list = args.exdir
expage_list = args.expage
root = args.url[0]
docs_formats = [
                '.doc', '.dot', '.od', '.pdf', '.csv', '.rtf',
                '.RTF', '.txt', '.wps', '.xml', '.dbf', '.dif',
                '.prn', '.slk', '.xl', '.xps', '.pot', '.pp'
                ]
links = {}
url = "/"
pages = [url]
used_pages = []
pages_duplicates = {}
is_document = False
internal_docs = 0
internal_links = 0
external_links = 0
start_time = time.time()
dirName = 'log'

requests.packages.urllib3.disable_warnings()


def add_slash(string):
    if string[-1] != '/':
        return string + '/'
    return string


async def add_to_links(link, link_type, link_status=None, page=None,
                 is_document=False, error_message=None):
    '''Add to links dictionary information
       about site links and documents

    Attributes
    ----------
    internal_links : int
        Number of internal links on the site
    external_links : int
        Number of external links on the site
    '''
    global internal_links, external_links
    if link_type == 1:
        if link_status > 0:
            links.update({link: [link_type, link_status, [page],
                          is_document, error_message]})
            external_links += 1
        else:
            if page not in links[link][2]:
                links[link][2].append(page)
    else:
        if link not in links:
            links.update({link: [link_type, link_status, [page],
                          is_document, error_message]})
            internal_links += 1
        elif link_status > 0 and links[link][1] == 0:
            links[link][1] = link_status
        elif page not in links[link][2] and page is not None:
            links[link][2].append(page)
    if links[link][1] == 0:
        links[link][1] = requests.get(root + page, verify=False).status_code


async def exclusion(page):
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


async def add_to_pages(page):
    '''Add site page in pages list

    Attributes
    ----------
    page: str
        internal page to parse
    pages: list
        list of site pages
    '''
    if page in pages or any(exclusion in page for exclusion in exdir_list):
        return
    if await exclusion(page):
        return
    pages.append(page)

    if args.onepage or len(pages) <= 1:
        return
    if len(used_pages) >= args.pages and args.pages > 0:
        return

    tasks = [asyncio.create_task(page_parsing(page))]
    await asyncio.gather(*tasks)


async def delete_from_pages(page):
    '''Deletes page from site pages list

    Attributes
    ----------
    page: str
        internal page to parse
    '''
    if pages != [] and page in pages:
        pages.remove(page)


async def find_duplicates(page_code, page):
    '''Find duplicated pages on site'''
    hash = hashlib.sha256()
    hash.update(f'{page_code}'.encode())
    hash = hash.hexdigest()
    if hash in pages_duplicates.values():
        existing_page = list(pages_duplicates.keys())[list(pages_duplicates \
                             .values()).index(hash)]
        return logger.warning(f'Page {page} is duplicate of page {existing_page}')
    pages_duplicates.update({page: hash})


async def find_empty_pages(page_code):
    '''Find out if page is empty'''
    empty_page = page_code.find_all(class_=args.empty)
    if len(empty_page) == 0:
        logger.warning('Page is empty or this class is not exist')


async def page_parsing(page):
    '''This function finds and processes all
       links (including documents) on the site.

       Links are divided into internal and external,
       and added to the links dictionary.

       The internal ones are added separately to the pages list

    Attributes
    ----------
    root : str
        user-defined source page
    page : str
        internal page to parse
    internal_docs : int
        counter for determining the number
        of internal documents found
    error_message : str
        error message received when requesting a page
    status : int
        HTTP status code from request
    is_document : bool
        define is current link is document or not
    link : str
        link found on the page
    '''
    global internal_docs
    logger.info("Processing " + page)
    error_message = ''
    used_pages.append(page)

    try:
        response = requests.get(root+page, verify=False)
        status = response.status_code

    except Exception as exc:
        status = 400
        error_message = exc
        logger.error(f'{exc}')
    await add_to_links(page, 0, status, error_message)

    if status > 399:
        await delete_from_pages(page)

    try:
        page_html = BeautifulSoup(response.text, 'lxml')
        a_tags = page_html.find_all('a')

        if args.duplicate:
            await find_duplicates(page_html, page)

        if args.empty:
            await find_empty_pages(page_html)

        for a_tag in a_tags:
            status = 0
            regex1 = re.compile(r'#\w*')
            regex2 = re.compile(r'\+\d+')
            is_document = False
            error_message = ''
            link = a_tag.get('href')
            if link is None or link == '' \
               or (link in links and page in links[link][2]):
                continue

            if link[:4] == 'tel:' or link[:4] == 'fax:' \
               or 'mailto' in link or 'maito' in link \
               or regex2.search(link) or regex1.search(link) or link[-4:] == '.jpg':
                continue

            if any(doc_format in link for doc_format in docs_formats):
                is_document = True
            if root in link:
                link = link.replace(root, '')

            if 'http' in link:
                if link not in links.keys():
                    try:
                        request = requests.get(link, verify=False, timeout=10)
                        status = request.status_code

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
                    except requests.exceptions.HTTPError as err:
                        status = 404
                        error_message = err
                    except Exception as err:
                        status = request.status_code
                        error_message = err
                await add_to_links(link, 1, status, page, is_document, error_message)
            else:
                if link[0] != '/' and page[-1] != '/':
                    link = page + '/' + link
                if is_document is False:
                    await add_to_pages(link)
                else:
                    internal_docs += 1
                    try:
                        request = requests.get(root + link,
                                               verify=False, timeout=10)
                        status = request.status_code
                    except Exception as err:
                        error_message = err
                await add_to_links(link, 0, status, page, is_document, error_message)
    except Exception as exc:
        logger.error('System Error: ' + f'{exc}')


def add_to_sitemap_file():
    '''Add to file list of internal pages'''
    with open('sitemap.csv', 'w', encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(['page'])
        for page in sorted(pages):
            writer.writerow([page])


def add_to_debug_file():
    '''Add to file all site links.

    Output format
    -------------
    {link: [link_type, link_status, [page], is_document, error_message], ...}
    '''
    orig_stdout = sys.stdout
    f = open('debug.txt', 'w', encoding="utf-8")
    sys.stdout = f
    pprint(links)
    sys.stdout = orig_stdout
    f.close()


def add_links_to_csv():
    '''Add to csv file errors on site'''
    with open('links.csv', 'w', encoding="utf-8") as file:
        link_log = []
        writer = csv.writer(file, delimiter=';')
        writer.writerow(['page', 'link', 'link_status', 'link_type',
                         'is_document', 'error_message'])

        for link, link_properties in links.items():
            if link_properties[1] < 400 and args.errors:
                continue
            for page in link_properties[2]:
                if None not in link_properties:
                    link_log.append([page, link, link_properties[1],
                                    link_properties[0], link_properties[3],
                                    link_properties[4]])
        link_log.sort(key=lambda x: x[0])
        writer.writerows(link_log)
    file.close()


def redefine_input_url():
    '''Redefine url input parameter'''
    global root
    root = add_slash(root)
    root = root[0:(root.find('/', 8))]


def get_statistics():
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


async def main():

    # Setup logger config file
    setup_logging()

    redefine_input_url()
    await page_parsing(url)

    if args.onepage:
        tasks = []
        for page in pages:
            tasks.append(asyncio.create_task(page_parsing(page)))
        await asyncio.gather(*tasks)

    if args.map:
        add_to_sitemap_file()
    add_links_to_csv()
    add_to_debug_file()
    if args.statistics:
        get_statistics()


if __name__ == '__main__':
    asyncio.run(main())