from urllib.parse import urlparse, unquote
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
    links = []
    settings = None
    logger = None
    statistics = {
        'internal_links': 0,
        'internal_docs': 0,
        'external_links': 0,
        'external_docs': 0,
        'other_links': 0
    }

    def __init__(self, url, logger, settings):
        self.logger = logger
        self.settings = settings
        self.url = url
        self.start_time = time.time()
        if 'http' not in self.url:
            self.url = 'https://' + self.url
        self.parsed_url = urlparse(self.url)
        self.site_name = self.parsed_url.netloc
        self.origin = self.parsed_url.scheme + '://' + self.site_name
        if self.parsed_url.path == '':
            url_path = '/'
            self.first_link = ScrappedInternalLink(
                url_path, self.logger, self.settings, self.origin)
        else:
            self.first_link = ScrappedInternalLink(
                self.parsed_url.path, self.logger, self.settings, self.origin)

    def get_origin(self):
        return self.origin


    def crawl_links(self):
        self.links.append(self.first_link)
        self.statistics['internal_links'] += 1
        number_of_pages = self.settings.pages
        number_of_parsed_pages = 0

        for link in self.links:

            if link.link_type != 1 or link.document_type is not None:
                continue

            response = link.get_request()
            if response.status_code >= 400:
                continue

            if self.settings.exparams and \
                any(param.lower() in urlparse(link.final_url).query.lower() for param in self.settings.exparams):
                continue

            number_of_parsed_pages += 1
            url = response.url
            url_parsed = urlparse(url)
            if url in [link.final_url for link
                       in self.links if (type(link).__name__ == 'ScrappedInternalLink'
                                         and link.document_type is None)] \
                    and len(self.links) > 1:
                link.error_message += 'The URL may be repeated.'
                if url_parsed.path in ('', '/'):
                    link.error_message += 'An empty URL path.'
                continue

            link.final_url = url
            link.size_of_request = len(response.content)
            link.parse_text(response.text)
            link.process_link_time = datetime.now()
            self.add_new_links(link.related_link_urls)
            self.statistics['internal_links'] += 1

            if self.settings.onepage:
                links_to_process = [link for link in self.links if type(link).__name__ != 'ScrappedLink'][1:]
                for onepage_link in links_to_process:
                    response = onepage_link.get_request()
                    if response.status_code >= 400:
                        continue
                    onepage_link.final_url = response.url
                    onepage_link.size_of_request = len(response.content)
                    onepage_link.process_link_time = datetime.now()
                break

            if number_of_pages and number_of_parsed_pages >= number_of_pages:
                break


    def add_new_links(self, urls):
        for url in [link[0] for link in urls]:
            error_message = ''
            new_link = None

            if url is None:
                continue

            if ' ' in url:
                url = url.replace(' ', '')
                error_message += 'A whitespace in the url adress.'

            if url in [link.url for link in self.links]:
                continue

            #
            if (re.compile(r'#\w*')).search(url) or urlparse(url).fragment:
                continue

            # tel
            if (re.compile(r'\+\d+')).search(url) or 'tel' in url:
                new_link = ScrappedLink(url, self.logger, self.settings)
                new_link.link_type = 5

            # mail
            elif 'mailto' in url:
                new_link = ScrappedLink(url, self.logger, self.settings)
                new_link.link_type = 4

            # external
            elif self.site_name not in url and 'http' in url:
                new_link = ScrappedExternalLink(url, self.logger, self.settings)
                if any(doc_format in url for doc_format in docs_formats):
                    new_link.document_type = 2

            # internal
            elif (urlparse(url).netloc == '' or self.site_name in url):
                if urlparse(url).path in [link.url for link in self.links]:
                    continue
                if self.site_name in url:
                    error_message += 'Site name in link.'

                new_link = ScrappedInternalLink(url, self.logger, self.settings, self.origin)
                if any(doc_format in url for doc_format in docs_formats):
                    new_link.document_type = 2
            else:
                continue

            new_link.error_message = error_message
            self.links.append(new_link)


    def do_requests(self):
        not_requested_links = ([x for x in self.links if type(x).__name__ == 'ScrappedExternalLink' or (
            type(x).__name__ == 'ScrappedInternalLink' and x.document_type is not None)])
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
                if page.link_type == 1 and page.document_type is None:
                    for link in [link[0] for link in page.related_link_urls]:
                        for link_obj in self.links:
                            if link == link_obj.url:
                                if '%' in link:
                                    link = unquote(link)
                                writer.writerow([page.url,
                                                 link,
                                                 link_obj.http_status,
                                                 link_obj.link_type,
                                                 link_obj.document_type,
                                                 link_obj.error_message])


    def get_statistics(self):
        self.logger.info(f'Time: {time.time() - self.start_time} s')

        for link_obj in self.links:
            if link_obj.link_type == 1:
                if link_obj.document_type is not None:
                    self.statistics['internal_docs'] += 1
            elif link_obj.link_type == 2:
                if link_obj.document_type is None:
                    self.statistics['external_links'] += 1
                else:
                    self.statistics['external_docs'] += 1
            else:
                self.statistics['other_links'] += 1

        self.logger.info(f'Internal links: {self.statistics["internal_links"]}')
        self.logger.info(f'Internal documents: {self.statistics["internal_docs"]}')
        self.logger.info(f'External links: {self.statistics["external_links"]}')
        self.logger.info(f'External documents: {self.statistics["external_docs"]}')
        self.logger.info(f'Other links: {self.statistics["other_links"]}')


    def write_sitemap(self):
        with open('sitemap.csv', 'w') as file:
            writer = csv.writer(file, delimiter=';')
            writer.writerow(['page'])
            for page in self.links:
                if page.link_type == 1 and page.document_type is None:
                    if page.final_url == '':
                        continue
                    writer.writerow([page.final_url.replace(self.origin, '')]) 



class ScrappedLink():
    protocol = None
    link_type = None # 0 not defined 1 internal 2 external 3 anchor 4 email 5 phone
    http_status = None # 0 not defined 1 page 2 doc or pdf document 3 css 4 js 5 img ...
    document_type = None
    error_message = ''
    related_link_urls = []
    size_of_request = 0
    request_link_time = ''
    process_link_time = ''
    page_hash = ''

    def __init__(self, url, logger, settings):
        self.url = url
        self.logger = logger
        self.settings = settings
        self.get_link_time = datetime.now()

    def get_request(self):
        self.logger.info("Processing " + self.url)
        self.request_link_time = datetime.now()
        response = requests.models.Response()
        try:
            if urlparse(self.url).netloc == '':
                response = requests.get(
                    self.origin + self.url, verify=False, timeout=4)
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
            self.error_message = str(response.reason) + \
                ' | ' + str(self.error_message)

        self.process_link_time = datetime.now()
        return response


class ScrappedInternalLink(ScrappedLink):
    link_type = 1
    final_url = ''

    def __init__(self, url, logger, settings, site_url):
        super().__init__(url, logger, settings)
        self.origin = site_url

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

            self.related_link_urls = [
                [link.get('href'), link.text] for link in a_tags]
            self.encode_page(response_text)

        except Exception as exc:
            self.logger.error('System Error: ' + f'{exc}')

    
    def encode_page(self, page_text):
        page_html = BeautifulSoup(page_text, 'lxml')
        if self.settings.hash:
            for tag in ['div', 'section', 'body']:
                content = page_html.find_all(tag, class_=f'{self.settings.hash}')
                if content:
                    content = content[0]
                    break
        else:
            content = page_text


        hash = hashlib.sha256()
        hash.update(f'{content}'.encode())
        self.page_hash = hash.hexdigest()



class ScrappedExternalLink(ScrappedLink):
    link_type = 2

    def __init__(self, url, logger, settings):
        super().__init__(url, logger, settings)



def define_args():
    arg_parser = argparse.ArgumentParser(
        description='A program for self parsing.')
    arg_parser.add_argument(
        "-p", "--pages",
        help="Number of pages to parse, "
        "default is all pages.",
        default=0, type=int)
    arg_parser.add_argument(
        "-m",
        "--map",
        help="Add sitemap file 'sitemap.csv' "
        "to the current folder.",
        default=False,
        action="store_true")
    arg_parser.add_argument(
        "-o", "--onepage",
        help="Parse only one page and "
        "all links on it. If this argument is included, "
        "--page is ignored.", default=False,
        action="store_true")
    arg_parser.add_argument(
        "-e",
        "--errors",
        help="Outputs errors on self into "
        "file 'links.csv'.",
        default=False,
        action="store_true")
    arg_parser.add_argument(
        "-u", "--url", help="Add self url you "
        "want to parse. Required argument. "
        "Example: https://example.com.",
        type=str, required=True)
    arg_parser.add_argument(
        "--empty", help="Find empty pages "
        "by the inputted class of HTML tag.")
    arg_parser.add_argument(
        "--hash", help="Find html tag's "
        "content by class name and encode it.",
        type=str, default='')
    arg_parser.add_argument(
        "-d", "--duplicate", help="Find"
        "duplicated pages on self.",
        default=False, action="store_true")
    arg_parser.add_argument(
        "--exdir",
        help="Excludes the page and the "
        "directory of nested pages.",
        nargs="+",
        default=[])
    arg_parser.add_argument(
        "--expage", help="Excludes the specified page.",
        nargs="+", default=[])
    arg_parser.add_argument("--exparams", help="Excludes the specified url "
                        "parameters out of parsing.", nargs="+", default=[])
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

    site = ScrappedSite(settings.url, logger, settings)
    site.crawl_links()
    site.do_requests()
    site.write_results()
    site.get_statistics()
    site.write_sitemap()


if __name__ == '__main__':
    main()
