import os
import json
import aiohttp
from bs4 import BeautifulSoup


config_path = os.path.join(os.path.dirname(__file__), '..', 'CONFIG.json')

with open(config_path, 'r') as config_file:
    CONFIG = json.load(config_file)


async def fetch(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url) as response:
        return await response.text()


async def default_soup(session: aiohttp.ClientSession, url: str) -> BeautifulSoup:
    return BeautifulSoup(await fetch(session, url), CONFIG['parser'])
