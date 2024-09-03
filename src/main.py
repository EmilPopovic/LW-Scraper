import asyncio
import os
import json
from collections import deque

from post import Post


config_path = os.path.join(os.path.dirname(__file__), '..', 'CONFIG.json')

with open(config_path, 'r') as config_file:
    config = json.load(config_file)


def main() -> None:

    queue: deque[Post] = deque()
    visited: set[Post] = set()

    start_post = Post('pGvyqAQw6yqTjpKf4', override_title='The Gift We Give To Tomorrow')

    queue.append(start_post)

    while queue:

        current = queue.popleft()

        if current.visited:
            continue

        task = current.visit()
        asyncio.run(task)

        queue.extend(Post(Post.id_from_url(link)) for link in current.outgoing_posts)

        visited.add(current)

if __name__ == '__main__':
    main()
