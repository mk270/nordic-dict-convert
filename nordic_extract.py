#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# nordic_extract.py, by Martin Keegan
# A tool for extracting nordic dictionary entries from a database and dumping
# them to XML.
#
# Copyright (C) 2019, Open Book Publishers
#
# To the extent that this work is covered by copyright, you may redistribute
# and/or modify it under the terms of the Apache Software Licence v2.0
#
# For an example of a website built from the same data, see also:
#   https://www.dhi.ac.uk/lmnl/nordicheadword/displayPage/200
#
# Known bugs:
#   some queries need SQL ORDER clauses

import sys
import argparse
from named_temp import named_temp
import lxml.etree
import lxml.builder
import lxml.html
import html
import database

E        = lxml.builder.ElementMaker()

# The names on the right hand side below, e.g., "E.nordic_headword", are used
# as the tag names in the generated XML, i.e.,
#   <nordic_headword>...</nordic_headword>
ROOT         = E.nordic_headwords
HEADWORD     = E.nordic_headword
NAME         = E.name
POS          = E.type
LANG         = E.language
COMPARISONS  = E.comparisons
COMPARISON   = E.comparison
ALTERNATIVES = E.alternatives
ALTERNATIVE  = E.alternative
ALT_NAME     = E.alternative_name
ALT_LANG     = E.alternative_lang
TRANSLATIONS = E.translations
TRANSLATION  = E.translation
ENG_HEADWORD = E.english_headword
EVIDENCE     = E.evidence
LAW          = E.law
SURROGATE    = E.id

def get_all_headwords(db):
    return database.run_query(db, database.main_query, [])

def fixup_text(text):
    """Return None or the fixed-up version of TEXT.  Fixed-up means that
       the <span> tags and various attributes have been stripped from the
       XML material in TEXT."""
    if text is None:
        return None
    if text == "":
        return None

    fixed = html.unescape(text)
    if "<" not in text:
        assert fixed == text
        return fixed.strip()

    frags = lxml.html.fromstring("""<div>""" + fixed + """</div>""")

    lxml.etree.strip_tags(frags, 'span')
    for elt in frags.iterdescendants():
        for a in elt.attrib.keys():
            elt.attrib.pop(a)

    return frags

def transform(db, headword):
    """Transform a tuple comprising information about a HEADWORD, and return
       appropriately-structured XML about it."""
    assert 7 == len(tuple(headword))

    def make_translation(t):
        results = [
            ENG_HEADWORD(t["english_name"]),
        ]
        lang = t["lang_short_name"]
        if lang is not None:
            results.append(LANG(lang))

        law = t["law_short_name"]
        if law is not None:
            results.append(LAW(law))

        evidence_text = fixup_text(t["evidence"])
        if evidence_text is not None:
            results.append(EVIDENCE(evidence_text))

        return TRANSLATION(
            *results
        )

    def make_alternative(a):
        results = [
            ALT_NAME(a["alternative_name"]),
            ALT_LANG(a["short_name"])
        ]

        return ALTERNATIVE(
            *results
        )

    def make_comparison(c):
        results = [
            NAME(c["name"]),
            SURROGATE(str(c["nordic_headword2_id"]))
        ]
        return COMPARISON(
            *results
        )

    _related_tables = {
        "comparisons":  (database.comparisons_query,  make_comparison),
        "translations": (database.translations_query, make_translation),
        "alternatives": (database.alternatives_query, make_alternative)
    }

    def related_tables():
        for table_name, table_handlers in _related_tables.items():
            query, handler = table_handlers
            ii = database.run_query(db, query, (headword["nhw_id"],))
            yield table_name, [ handler(i) for i in ii ]

    related = dict([ (name, data) for name, data in related_tables() ])

    args = [
        NAME(headword['nordic_headword_name']),
        POS(headword['part_of_speech']),
        LANG(headword['language_code']),
        COMPARISONS(*related["comparisons"]),
        TRANSLATIONS(*related["translations"]),
        ALTERNATIVES(*related["alternatives"]),
        SURROGATE(str(headword['nhw_id']))
    ]

    attributes = ['article', 'refs', 'expressions']
    for a in attributes:
        a_text = fixup_text(headword[a])
        if a_text is not None:
            args.append(E.__getattr__(a)(a_text))

    return HEADWORD(*args)

def pretty_format_xml(root):
    return lxml.etree.tostring(root, pretty_print=True, encoding='UTF-8')

def run(args, tmp_path):
    db = database.get_db_handle(args, tmp_path)
    headwords = [ transform(db, hw) for hw in get_all_headwords(db) ]

    the_doc = ROOT(*headwords)
    xml_text = pretty_format_xml(the_doc)
    sys.stdout.buffer.write(xml_text)

def process_args():
    a = argparse.ArgumentParser()
    a.add_argument("--filename",
                   default="live.db",
                   help="Database filename to use instead of live.db")
    args = a.parse_args()
    with named_temp() as tmp_path:
        return run(args, tmp_path)

if __name__ == '__main__':
    exit(process_args())
