'''Create and export an index manifest.'''
import concurrent.futures
import json
import os
import re
import time

from typing import Any, Dict, List, Tuple, Optional

from mut.index.utils.Logger import log_unsuccessful
from mut.index.utils.ProgressBar import ProgressBar
from mut.index.Document import Document

BLACKLIST = set([
    '401',
    '403',
    '404',
    '410',
    'genindex',
    'faq',
    'search',
    'contents'
])

FileInfo = Tuple[str, str, str]


class Manifest:
    '''Manifest of index results.'''
    def __init__(self, url: str, globally: bool) -> None:
        self.url = url
        self.globally = globally
        self.documents = []  # type: List[Dict[str, Any]]

    def add_document(self, document: Dict[str, Any]) -> None:
        '''Adds a document to the manifest.'''
        self.documents.append(document)

    def json(self) -> str:
        '''Return the manifest as json.'''
        manifest = {
            'url': self.url,
            'includeInGlobalSearch': self.globally,
            'documents': self.documents
        }
        return json.dumps(manifest, indent=4)


def generate_manifest(url: str, root_dir: str, globally: bool, show_progress: bool) -> str:
    '''Build the index and compile a manifest.'''
    start_time = time.time()
    manifest = Manifest(url, globally)
    html_path_info = _get_html_path_info(root_dir, url)
    if not html_path_info:
        raise NothingIndexedError()
    num_documents = len(html_path_info)
    if show_progress:
        progress_bar = ProgressBar(start_time=start_time,
                                   num_documents=num_documents)
    else:
        progress_bar = None
    _process_html_files(html_path_info, manifest, progress_bar)
    _summarize_build(num_documents, start_time)
    return manifest.json()


def _get_html_path_info(root_dir: str, url: str) -> List[FileInfo]:
    '''Return a list of parsed path_info for html files.'''
    def should_index(file) -> bool:
        '''Returns True the file should be indexed.'''
        match = re.search(r'([^./]+)(?:/index)?.html$', file)
        return match is not None and match.group(1) not in BLACKLIST

    path_info = []
    root_dir = root_dir.lstrip('/') + '/'
    for root, _, files in os.walk(root_dir):
        path_info.extend([(root_dir, os.path.join(root, file), url)
                          for file in files
                          if should_index(os.path.join(root, file))])
    return path_info


def _parse_html_file(path_info: FileInfo):
    '''Open the html file with the given path then parse the file.'''
    root_dir, path, url = path_info
    with open(path, 'r') as html:
        try:
            document = Document(url, root_dir, html).export()
            return document
        except Exception as ex:
            message = 'Problem parsing file ' + path
            log_unsuccessful('parse')(message=message,
                                      exception=ex)


def _process_html_files(html_path_info: List[FileInfo], manifest: Manifest, progress_bar: Optional[ProgressBar]=None):
    '''Apply a function to a list of .html file paths in parallel.'''
    with concurrent.futures.ProcessPoolExecutor() as executor:
        for document in executor.map(_parse_html_file, html_path_info):
            manifest.add_document(document)
            if progress_bar:
                progress_bar.update(document['slug'])


def _summarize_build(num_documents: int, start_time: float) -> None:
    summary = ('\nFinished indexing!\n'
               'Indexed {num_docs} documents in {time} seconds.')
    summary = summary.format(num_docs=num_documents,
                             time=str(time.time() - start_time))
    print(summary)


class NothingIndexedError(Exception):
    def __init__(self) -> None:
        message = 'No documents were found.'
        log_unsuccessful('index')(message=message,
                                  exception=None)
