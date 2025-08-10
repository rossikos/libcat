# LibCat

LibCat is a command-line program to assist with copy-cataloging. The central objective is to make it easy to retrieve a work's library classifications such as the Library of Congress or Dewey Decimal classifications and subject headings. LibCat is determined in this endeavor, searching multiple library catalogs and alternative editions until all desired classification information is found.

## Installation

This project will soon become available on the Python Package Index (PyPi)

## Usage

`$ libcat <input> [MAIN OPTIONS]`

Where `input` can be an isbn (hyphenated or not), path to a text file with a list of isbns, path to a PDF or EPUB file, path to a directory, or 'db' followed by the arguments for the database viewer (see below).

In this documentation, _identifiers_ are parsed from files or used in a catalog search and _classifiers_ are retrieved from a catalog search.

### Example usage

`$ libcat 9780060929879 -c loc bdirect k10 openl -cl record lcc ddc lcsh`

will search the Library of Congress, Borrow Direct, K10plus, and Open Library catalogs in that order for the bibliographic record (usually in marcxml fomat), Library of Congress Classification, Dewey Decimal Classification, and Library of Congress Subject Headings. 

If, after searching all four catalogs, we still lack one of the four classifiers, the program will attempt to retrieve the most common LCC or DDC of alternative editions from Open Library. If classifiers are still missing, the program will search the specified catalogs with alternative editions fetched from Open Library.

This process ensures a high probability that classifiers will be found.

Each search 'job' is stored in a sqlite database in folder .libcat in the user's home directory. Incidentally, this folder also has a config.toml file which can be edited to change default options among other settings. 

The database can be easily accessed using `libcat db ARG [OPTIONS]`.

For example, to perform a search and then show data from the last job:

`libcat 9780060929879; libcat db sh -l`

### File operations

When specifying a PDF or EPUB file, LibCat parses the file for identifiers (e.g. lcc, ddc, or isbn) and then searches catalogs with isbn for missing classifiers. When a directory is specified, LibCat performs the file action on PDF and/or EPUBs in that directory and its subdirectories.


## Main Options
```
options:
  -h, --help                            show this help message and exit
  -t, --filetypes {.pdf, .epub} [{.pdf, .epub} ...]
                                        file types to parse if file or dir
                                        specified
  -m, --metadata {0,1,2}                search file metadata for identifiers
                                        (requires exiftool). 1 - before file
                                        content, 2 - after
  -l, --languages <lang> [<lang> ...]   only return / search records in specific
                                        languages. Language codes: https://www.l
                                        oc.gov/marc/languages/language_code.html
  -pf, --parsefor <identifier> [<identifier> ...]
                                        the identifiers to parse for in the file
                                        before searching catalogs
  -pa, --parseall {yes,no}              extract all ids in parsefor from file as
                                        opposed to moving on with first id found
  -c, --catalogs <shortcode> [<shortcode> ...]
                                        the catalogs to use and order in which
                                        they are searched: ['loc', 'k10',
                                        'bdirect', 'hathi', 'openl', 'ucs',
                                        'carli', 'mit', 'nyu']
  -w, --wait <seconds>                  number of seconds to wait after a failed
                                        request before retrying
  -r, --retries <count>                 number of retries when a request fails
  --timeout <seconds>                   number of seconds to wait for a response
                                        from server
  -cl, --classifiers {record,lcc,ddc,lcsh,isbn} [{record,lcc,ddc,lcsh,isbn} ...]
                                        classifiers to retrieve from catalogs
  -alt, --altisbns {yes,no}             if original isbn returns no results, try
                                        using a work's alternative isbns
  -ma, --maxalts <count>                maximum number of alternative isbns to
                                        consider before aborting
  -v, --verbose                         verbosity of logging. -v: info, -vv:
                                        debug
  --version                             show program's version number and exit
```

## Database Parameters and Options

```
positional arguments:
    show (sh)           show jobs
        -h, --help            show this help message and exit
        -a, --all             show all
        -r, --recent          show ten most recent jobs
        -j, --jobtype <jobtype> [jobtype ...]
                              show by job type; can be any or several of: 
                              isbn/i, file/f, dir_marker/dm, dir_file/df
        -i, --ids <id> [id ...]
                              show full entries for given ids
        -l, --last            show last job
        -e, --exit            exit after completing actions
    delete (del)        delete jobs
        -h, --help            show this help message and exit
        --everything          delete everything in the database
        -i, --ids <id> [id ...]
                              delete jobs by id
        -e, --exit            exit after completing actions
    tozotero (zot)      add bibliographic entries to Zotero (requires 
                        better bibtex debug bridge)
        -h, --help            show this help message and exit
        -i, --ids <id> [id ...]
                              add by id
        -l, --last            add the last job
        -e, --exit            exit after completing actions
    tocsv (csv)         export database to csv
        -h, --help            show this help message and exit
        -a, --all
        -o, --outpath <path>
        -e, --exit            exit after completing actions

options:
  -h, --help            show this help message and exit
```