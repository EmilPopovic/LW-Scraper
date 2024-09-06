import os
import json
import asyncio
from datetime import datetime

import aiohttp
from bs4 import BeautifulSoup

from util import default_soup

config_path = os.path.join(os.path.dirname(__file__), '..', 'CONFIG.json')

with open(config_path, 'r') as config_file:
    CONFIG = json.load(config_file)


class Post:
    _instances: dict[str, 'Post'] = {}
    _titles: dict[str, str] = {}
    _soups: dict[str, BeautifulSoup] = {}

    def __new__(cls, post_id: str, *args, **kwargs) -> 'Post':
        if post_id in cls._instances:
            return cls._instances[post_id]
        instance = super().__new__(cls)
        cls._instances[post_id] = instance
        return instance

    def __init__(self, post_id: str, override_title: str = None) -> None:
        if not hasattr(self, '_initialized'):
            self._initialized = True

            self.id = post_id
            self.url = f'{CONFIG['lw_domain']}/posts/{post_id}'

            self.outgoing_post_urls: list[str] = []
            self.incoming_post_urls: list[str] = []
            self.outgoing_sequence_urls: list[str] = []

            self.sequence_title: str | None = None
            self.sequence_url: str | None = None
            self.sequence_prev_url: str | None = None
            self.sequence_next_url: str | None = None

            self.is_curated = False

            self.visited = False
            self.last_visited_at: datetime | None = None

            self.title = override_title if override_title else Post._titles[post_id]

    @staticmethod
    async def prefetch_url(session: aiohttp.ClientSession, url: str) -> str:
        # add https://www.lesswrong.com to start if not present
        full_url = url if url.startswith(CONFIG['lw_domain']) else f'{CONFIG['lw_domain']}{url}'

        # is a link to a sequence
        if '/s/' in full_url and '/p/' not in full_url:
            return full_url

        # load url from parameter
        soup = await default_soup(session, full_url)

        print(f'Prefetching <URL {full_url}>')

        # try to find title object
        post_title = soup.find('a', class_='PostsPageTitle-link')

        if post_title:
            # this is a normal post
            real_url = Post.strip_title_from_url(f'{CONFIG['lw_domain']}{post_title['href']}')
        else:
            # this is a post with a fancy heading
            # make url where the last element is the post id
            url_without_title = full_url if '/s/' in full_url else Post.strip_title_from_url(full_url)
            parsed_id = Post.id_from_url(url_without_title)

            real_url = f'{CONFIG["lw_domain"]}/posts/{parsed_id}'
            post_title = soup.find('h1', class_='PostsPageSplashHeader-title')

        post_id = Post.id_from_url(real_url)
        Post._titles[post_id] = post_title.text
        Post._soups[post_id] = soup

        return real_url

    @staticmethod
    def strip_title_from_url(url: str) -> str:
        return '/'.join(url.split('/')[:-1])

    @staticmethod
    def id_from_url(url: str) -> str:
        return url.split('/')[-1]

    async def visit(self, force_revisit: bool = False) -> None:
        print(f'Visiting {self}')
        self.visited = True
        self.last_visited_at = datetime.now()

        async with aiohttp.ClientSession(headers=CONFIG['headers']) as session:

            cached = Post._soups.get(self.id)
            soup = cached if cached and not force_revisit else await default_soup(session, self.url)

            post_body = soup.find('div', class_='InlineReactSelectionWrapper-root')

            lw_links = [link['href'].split('?')[0].split('#')[0]
                        for paragraph in post_body.find_all('p')
                        for link in paragraph.find_all('a')
                        if link.get('href')
                        and any(link['href'].startswith(p)
                                for p in [f'{CONFIG['lw_domain']}', '/posts/', '/s/', '/lw/'])
                        and all(elem not in link
                                for elem in ['/comment/', '/tag/', '/user/'])]

            tasks = [Post.prefetch_url(session, link) for link in lw_links]
            results = await asyncio.gather(*tasks)

            self.outgoing_post_urls = [link for link in results
                                       if ('/posts/' in link or ('/s/' in link and '/p/' in link) or '/lw/' in link)]

            self.outgoing_sequence_urls = [link for link in lw_links if '/s/' in link and '/p/' not in link]

            pingbacks_div = soup.find('div', class_='PingbacksList-list')

            if pingbacks_div:
                pingbacks = [f'{CONFIG.get('lw_domain')}{pingback.get('href')}'
                             for pingback in pingbacks_div.find_all('a')]

                tasks = [Post.prefetch_url(session, link) for link in pingbacks]
                results = await asyncio.gather(*tasks)

                self.incoming_post_urls = [link for link in results
                                           if '/posts/' in link or ('/s/' in link and '/p/' in link)]

            sequence = soup.find('div', class_='PostsTopSequencesNav-title')

            if sequence:
                sequence_title_a = soup.find('a')
                self.sequence_title = sequence_title_a.text
                self.sequence_url = f'{CONFIG['lw_domain']}{sequence_title_a['href']}'

            sequence_nav = soup.find('div', class_='BottomNavigation-root')

            if sequence_nav:
                prev_post = sequence_nav.find('a', class_='BottomNavigation-post BottomNavigation-prevPost')
                next_post = sequence_nav.find('a', class_='BottomNavigation-post BottomNavigation-nextPost')

                if prev_post:
                    self.sequence_prev_url = Post.prefetch_url(session, prev_post['href'])

                if next_post:
                    self.sequence_next_url = Post.prefetch_url(session, next_post['href'])

    def __eq__(self, other) -> bool:
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f'<Post [{self.title}]({self.url})>'
