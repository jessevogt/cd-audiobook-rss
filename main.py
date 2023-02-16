from flask import Flask, render_template_string, send_file, Response, request
import os
import re
from typing import NamedTuple, Pattern, Dict, Any, Callable
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
from urllib.parse import urlparse

app = Flask(__name__)


class FilenameParser(NamedTuple):
    pattern: Pattern
    transform_mapping: Dict[str, Callable]
    sorter: Callable

    def transform(self, key, value):
        transformer = self.transform_mapping.get(key)
        return transformer(value) if transformer else value


class Book(NamedTuple):
    name: str
    author: str
    directory: str
    parser: FilenameParser


THE_SPLENDID_AND_THE_VILE = Book(
    name="The Splendid and the Vile",
    author="Erik Lawson",
    directory="media/the_splendid_and_the_vile",
    parser=FilenameParser(
        pattern=re.compile(r""".+(?P<section_type>Chapter|Epilogue|End\ Credits)\s*
                               (?P<chapter>\d*)
                               (?P<subchapter>.*)
                               \.m.+""", re.X),
        transform_mapping={
            "chapter": lambda x: int(x) if x else None,
            "subchapter": lambda x: x.lower() if x else None,
        },
        sorter=lambda x: [
            {
                "Chapter": 0,
                "Epilogue": 1,
                "End Credits": 2,
            }[x.props["section_type"]],
            x.props["chapter"],
            x.props["subchapter"],
        ]
    )
)

THE_STAND = Book(
    name="The Stand",
    author="Stephen King",
    directory="media/the_stand",
    parser=FilenameParser(
        pattern=re.compile(r""".+\[Disc\ (?P<disc>\d+)\]/
                               (\d+-)?(?P<track>\d+).+""", re.X | re.I),
        transform_mapping={
            "disc": lambda x: int(x, 10),
            "track": lambda x: int(x, 10),
        },
        sorter=lambda x: [x.props["disc"], x.props["track"]],
    )
)


class File(NamedTuple):
    path: str
    props: Dict[str, Any]


@app.route("/f/<path:file_path>")
def download(file_path):
    print(file_path)
    return send_file(file_path)


@app.route("/p/<bookname>")
def home(bookname):
    book = THE_STAND
    host = "http://192.168.102.223:8000"
    pub_date = datetime(2023, 1, 1)
    
    body = render_template_string(
        """<?xml version="1.0" encoding="UTF-8" ?>
    <rss xmlns:googleplay="http://www.google.com/schemas/play-podcasts/1.0"
         xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
         xmlns:atom="http://www.w3.org/2005/Atom"
         xmlns:rawvoice="http://www.rawvoice.com/rawvoiceRssModule/"
         xmlns:content="http://purl.org/rss/1.0/modules/content/"
         version="2.0">
  <channel>
    <title>{{ book.name }}</title>
    <author>{{ book.author }}</author>
    <image>
      <url></url>
      <title>{{ book.name }}</title>
      <link></link>
    </image>
    <copyright></copyright>
    <description></description>
    <language>en-us</language>
    <pubDate>{{ pub_date.strftime("%a, %d %b %Y %H:%M:%S UTC") }}</pubDate>
    <link></link>
    {% for file in files %}
        <item>
          <author>{{ book.author }}</author>
          <title>{{ file.path.stem }}</title>
          <pubDate>
            {{ (pub_date + timedelta(minutes=loop.index))
                .strftime("%a, %d %b %Y %H:%M:%S UTC") }}
          </pubDate>
          <enclosure
            url="{{ url.scheme }}://{{ url.netloc }}/f/{{ file.path }}"
            type="audio/mpeg" length="0" />
          <itunes:duration>00:00</itunes:duration>
          <guid isPermaLink="false">{{ hashlib.sha256(
                bytes(str(file.path), encoding="utf8")
               ).hexdigest() }}</guid>
          <description></description>
        </item>
    {% endfor %}
  </channel>
</rss>""",
        files=collect_files(),
        host=host,
        book=book,
        pub_date=pub_date,
        timedelta=timedelta,
        hashlib=hashlib,
        bytes=bytes,
        str=str,
        url=urlparse(request.base_url),
    )
    response = Response(body)
    response.headers["mimetype"] = "text/xml"
    response.headers["content-type"] = "text/xml"
    return response


def collect_files(book=THE_STAND):

    collected = []

    for root, subdirs, files in os.walk(book.directory):
        for f in files:
            if f == ".DS_Store":
                continue
            file_path = os.path.join(root, f)
            m = book.parser.pattern.match(file_path)
            collected.append(
                File(
                    path=Path(file_path),
                    props={
                        k: book.parser.transform(k, v)
                        for k, v in m.groupdict().items()
                    },
                )
            )

    return sorted(collected, key=book.parser.sorter)

if __name__ == "__main__":
    for x in collect_files():
        print(x)

