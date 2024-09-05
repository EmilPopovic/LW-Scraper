import asyncio
import os
import json
from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup

from post import Post
from util import default_soup

config_path = os.path.join(os.path.dirname(__file__), '..', 'CONFIG.json')

with open(config_path, 'r') as config_file:
    CONFIG = json.load(config_file)


class Sequence:
    _instances: dict[str, 'Sequence'] = {}
    _titles: dict[str, str] = {}
    _soups: dict[str, BeautifulSoup] = {}

    def __new__(cls, sequence_id: str, *args, **kwargs) -> 'Sequence':
        if sequence_id in cls._instances:
            return cls._instances[sequence_id]
        instance = super().__new__(cls)
        cls._instances[sequence_id] = instance
        return instance

    def __init__(self, sequence_id: str, override_title: str = None) -> None:
        if not hasattr(self, '_initialized'):
            self._initialized = True

            self.id = sequence_id
            self.url = f'{CONFIG['lw_domain']}/s/{sequence_id}'

            self.post_urls: list[str] = []

            self.visited = False
            self.last_visited_at: datetime | None = None

            self.title = override_title if override_title else Sequence._titles[sequence_id]

    async  def visit(self, force_revisit: bool = False) -> None:
        print(f'Visiting {self}')
        self.visited = True
        self.last_visited_at = datetime.now()

        async with aiohttp.ClientSession(headers=CONFIG['headers']) as session:

            cached = Sequence._soups.get(self.id)
            soup = cached if cached and not force_revisit else await default_soup(session, self.url)

            sequence_page_content = soup.find('div', class_='SequencesPage-content')

            self.title = sequence_page_content.find('h1').text

            posts_div = sequence_page_content.find('div', class_='ChaptersItem-posts')
            posts = posts_div.find_all('span', class_='PostsTitle-eaTitleDesktopEllipsis')

            post_seq_urls = [post.find('a')['href'] for post in posts]

            tasks = [Post.get_real_url(session, link) for link in post_seq_urls]
            self.post_urls = await asyncio.gather(*tasks)

    def __eq__(self, other) -> bool:
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f'<Sequence [{self.title}]({self.id})>'
