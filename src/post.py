import os
import json
import asyncio

import aiohttp
from bs4 import BeautifulSoup

config_path = os.path.join(os.path.dirname(__file__), '..', 'CONFIG.json')

with open(config_path, 'r') as config_file:
    CONFIG = json.load(config_file)


class Post:
    _instances = {}
    _titles = {}

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

            self.outgoing_posts: list[str] = []
            self.incoming_posts: list[str] = []
            self.outgoing_sequences: list[str] = []

            self.visited = False

            self.title = override_title if override_title else Post._titles.get(post_id)

    @staticmethod
    async def fetch(session: aiohttp.ClientSession, url: str) -> str:
        async with session.get(url) as response:
            return await response.text()

    @staticmethod
    async def get_real_url(session: aiohttp.ClientSession, url: str) -> str:
        # add https://www.lesswrong.com to start if not present
        full_url = url if url.startswith(CONFIG['lw_domain']) else f'{CONFIG['lw_domain']}{url}'

        # already is real url
        if '/posts/' in full_url:
            return Post.strip_title_from_url(full_url)

        # is a link to a sequence
        elif '/s/' in full_url and '/p/' not in full_url:
            return full_url

        # get real url from link in title
        page_content = await Post.fetch(session, full_url)
        soup = BeautifulSoup(page_content, 'html.parser')
        post_title = soup.find('a', class_='PostsPageTitle-link')

        real_url = Post.strip_title_from_url(f'{CONFIG['lw_domain']}{post_title['href']}')
        post_id = Post.id_from_url(real_url)
        Post._titles[post_id] = post_title.text

        return real_url

    @staticmethod
    def strip_title_from_url(url: str) -> str:
        return '/'.join(url.split('/')[:-1])

    @staticmethod
    def id_from_url(url: str) -> str:
        return url.split('/')[-1]

    async def visit(self) -> dict[str, list[str]]:
        print(f'Visiting {self}')
        self.visited = True

        async with aiohttp.ClientSession(headers=CONFIG['headers']) as session:

            page_content = await self.fetch(session, self.url)

            soup = BeautifulSoup(page_content, 'html.parser')
            post_body = soup.find('div', class_='InlineReactSelectionWrapper-root')

            paragraphs = post_body.find_all('p')

            lw_links = [link['href'].split('?')[0].split('#')[0]
                        for paragraph in paragraphs
                        for link in paragraph.find_all('a')
                        if link.get('href') and (link['href'].startswith(f'{CONFIG['lw_domain']}')
                                                 or link['href'].startswith('/posts/')
                                                 or link['href'].startswith('/s/')
                                                 or link['href'].startswith('/lw/'))]

            tasks = [Post.get_real_url(session, link) for link in lw_links]
            results = await asyncio.gather(*tasks)

            self.outgoing_posts = [link for link in results
                                   if ('/posts/' in link or '/s/' in link and '/p/' in link or '/lw/' in link)
                                   and '/comment/' not in link]

            self.outgoing_sequences = [link for link in lw_links if '/s/' in link and '/p/' not in link]

            pingbacks_div = soup.find('div', class_='PingbacksList-list')

            if pingbacks_div:
                pingbacks = [f'{CONFIG.get('lw_domain')}{pingback.get('href')}'
                             for pingback in pingbacks_div.find_all('a')]

                tasks = [Post.get_real_url(session, link) for link in pingbacks]
                results = await asyncio.gather(*tasks)

                self.incoming_posts = [link for link in results
                                       if '/posts/' in link or '/s/' in link and '/p/' in link]

            return {
                'outgoing_links': self.outgoing_posts,
                'incoming_links': self.incoming_posts,
                'outgoing_sequences': self.outgoing_sequences
            }

    def __eq__(self, other) -> bool:
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f'<Post [{self.title}]({self.url})>'
