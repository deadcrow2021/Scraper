
Scraper
=======

Scraper is a lightweight application for site parsing.

An advantage of the application is that you can
get a list of all bad links on the site and a
statistics about how much internal
or external links and documents you find.

How is it going:
![alt-Block-Scheme](http://gitea.wss-15.lan/saraf.a/scraper/src/branch/master/Scraper-block-scheme-en.png "Block-Scheme")

----

Parameters
----------

```no-highlight
  -p, --pages           Number of pages to parse, default is all pages.
  -s, --statistics      Add statistics of program execution at the end of output.
  -m, --map             Add sitemap file 'sitemap.csv' to the current folder.
  -o, --onepage         Parse only one page and all links on it. If this argument is included, --page will be ignored.
  -e, --errors          Outputs errors on site into file 'links.csv'.
  -u URL, --url         Add site url you want to parse. Required argument. Example: https://example.com.
  --empty               Find empty pages by the inputted class of HTML tag.
  -d, --duplicate       Findduplicated pages on site.
  --exdir               Excludes pages program donot need to parse.
  --expage              Excludes the specified page.
```

----

Installing
----------

Clone repository:

```text
$git clone http://gitea.wss-15.lan/saraf.a/scraper.git
```

Move to the folder.
Example:

```text
$cd /home/user/Desktop/scraper/
```

Install required packages:

```text
$pip3 install -r requirements.txt
```

----

How to run
----------

Print for help:

```text
$python3 scraper.py --help
```

Run example:

```text
$python3 scraper.py -u https://www.python.org -s -p 3
*
INFO - Processing /
INFO - Processing /psf-landing/
INFO - Processing /jobs/
INFO - Links in pages: 299
INFO - Internal documents: 0
INFO - Internal links: 299
INFO - External links: 60
INFO - Code execution time: 139.99 seconds
```

----

Output
------

links.csv

```text
page;link;link_status;link_type;is_document;error_message
/;/;200;0;False;
/;/psf-landing/;200;0;False;
/;https://docs.python.org;200;1;False;
```

links.csv (If "-e" tag was used)

```text
page;link;link_status;link_type;is_document;error_message
/;http://www.saltstack.com;403;1;False;
```

sitemap.csv

```text
page
page1
page2
```

log/std.log
(If errors are detected)

```text
2021-07-01 12:27:16,622 - ERROR - 168 - HTTPSConnectionPool(host='www.python.org', port=443): Max retries exceeded with url: / (Caused by NewConnectionError('<urllib3.connection.HTTPSConnection object at 0x7fdfd5d10be0>: Failed to establish a new connection: [Errno -2] Name or service not known'))
2021-07-01 12:27:16,622 - ERROR - 242 - System Error: local variable 'response' referenced before assignment
```

----

Deleting
--------

```text
$rm -r Desktop/scraper/
```
