#!/usr/bin/env python3
"""Validate static guide structure and internal links without network access."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT=Path(__file__).resolve().parents[1]
class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.tags=Counter(); self.ids=[];self.hrefs=[];self.lang=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);self.tags[tag]+=1
        if 'id' in a:self.ids.append(a['id'])
        if 'href' in a:self.hrefs.append(a['href'])
        if tag=='html':self.lang=a.get('lang')

pages={}
for suffix,lang in [('', 'pt-BR'),('en','en'),('es','es')]:
    path=ROOT/'guia'/suffix/'index.html';data=path.read_text()
    assert '{{' not in data, f'Placeholder in {path}'
    p=Page();p.feed(data);assert p.lang==lang
    assert len(p.ids)==len(set(p.ids)), f'Duplicate IDs in {path}'
    for href in p.hrefs:
        url=urlparse(href)
        if url.scheme or url.netloc:continue
        target=path.parent/unquote(url.path) if url.path else path
        if target.is_dir():target=target/'index.html'
        assert target.is_file(),f'Missing link {path}: {href}'
        if url.fragment:
            other=Page();other.feed(target.read_text());assert url.fragment in other.ids
    pages[suffix]=p
for suffix in ('en','es'):
    assert pages[suffix].tags==pages[''].tags,f'Unequal structure: {suffix}'
    assert pages[suffix].ids==pages[''].ids,f'Unequal IDs: {suffix}'
print('PASS: PT/EN/ES, matching structure and valid local links.')
