import asyncio
import os
import json
from collections import deque
from dotenv import load_dotenv

from db_controller import DB
from lw_objects import *

config_path = os.path.join(os.path.dirname(__file__), '..', 'CONFIG.json')
with open(config_path, 'r') as config_file:
    config = json.load(config_file)

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

URI = os.getenv('DB_URI')
AUTH = (os.getenv('MEMGRAPH_USER'), os.getenv('MEMGRAPH_PASSWORD'))

LwObject = Post | Sequence


def main() -> None:

    db = DB(URI, AUTH)

    queue: deque[LwObject] = deque()

    start: LwObject = Post('pGvyqAQw6yqTjpKf4', override_title='The Gift We Give To Tomorrow')

    queue.append(start)

    while queue:

        current = queue.popleft()
        while current in queue:
            queue.remove(current)

        if current.visited:
            continue

        task = current.visit()
        asyncio.run(task)

        if isinstance(current, Post):

            outgoing_posts = [Post(Post.id_from_url(link)) for link in current.outgoing_post_urls]
            incoming_posts = [Post(Post.id_from_url(link)) for link in current.incoming_post_urls]

            posts_to_create = [current]
            posts_to_create.extend(outgoing_posts)
            posts_to_create.extend(incoming_posts)

            queue.extend([post for post in outgoing_posts if not post.visited])
            queue.extend([post for post in incoming_posts if not post.visited])

            db.create_posts(posts_to_create)
            db.link_post_to_posts(current, outgoing_posts)
            db.link_posts_to_post(incoming_posts, current)

        elif isinstance(current, Sequence):

            pass

if __name__ == '__main__':
    main()
