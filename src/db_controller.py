from multipledispatch import dispatch
from neo4j import GraphDatabase

from lw_objects.post import Post
from lw_objects.sequence import Sequence


class DB:

    def __init__(self, uri: str = '', auth: tuple[str, str] = ('', '')) -> None:
        self.uri = uri
        self.auth = auth

    def num_of_nodes(self) -> int:
        with GraphDatabase.driver(self.uri, auth=self.auth) as client:
            client.verify_connectivity()

            query = 'MATCH (n) RETURN count(n) AS num_of_nodes'
            # noinspection PyTypeChecker
            records, summary, keys = client.execute_query(query)

            return sum(map(lambda x: x['num_of_nodes'], records))

    @dispatch(str, str)
    def create_post(self, post_title: str, post_id: str) -> bool:
        with GraphDatabase.driver(self.uri, auth=self.auth) as client:
            query = '''
            MERGE (n:Post {id: $post_id})
            ON MATCH SET n.title = $title
            ON CREATE SET n.title = $title
            RETURN CASE WHEN n.title = $title THEN true ELSE false END AS was_created
            '''
            # noinspection PyTypeChecker
            records, _, _ = client.execute_query(query, title=post_title, post_id=post_id)
            return records[0]['was_created']

    @dispatch(Post)
    def create_post(self, p: Post) -> None:
        return self.create_post(p.title, p.id)

    def create_posts(self, posts: list[Post]) -> None:
        with GraphDatabase.driver(self.uri, auth=self.auth) as client:
            query = '''
            UNWIND $posts AS post
            MERGE (n:Post {id: post.id})
            ON CREATE SET n.title = post.title
            '''
            posts_dict = [{'title': p.title, 'id': p.id} for p in posts]
            # noinspection PyTypeChecker
            client.execute_query(query, posts=posts_dict)

    @dispatch(str, list)
    def link_post_to_posts(self, origin_post_id: str, destination_post_ids: list[str]) -> None:
        with GraphDatabase.driver(self.uri, auth=self.auth) as client:
            query = '''
            MATCH (origin:Post {id: $origin_id})
            UNWIND $destinations AS destination_id
            MATCH (destination:Post {id: destination_id})
            MERGE (origin)-[:LINKS_TO]->(destination)
            '''
            # noinspection PyTypeChecker
            client.execute_query(query, origin_id=origin_post_id, destinations=destination_post_ids)

    @dispatch(Post, list)
    def link_post_to_posts(self, origin_post: Post, destination_posts: list[Post]) -> None:
        self.link_post_to_posts(origin_post.id, list(map(lambda p: p.id, destination_posts)))

    @dispatch(list, str)
    def link_posts_to_post(self, origin_post_ids: list[str], destination_post_id: str) -> None:
        with GraphDatabase.driver(self.uri, auth=self.auth) as client:
            query = '''
            MATCH (destination:Post {id: $dest_id})
            UNWIND $origins AS origin_id
            MATCH (origin:Post {id: origin_id})
            MERGE (origin)-[:LINKS_TO]->(destination)
            '''
            # noinspection PyTypeChecker
            client.execute_query(query, dest_id=destination_post_id, origins=origin_post_ids)

    @dispatch(list, Post)
    def link_posts_to_post(self, origin_posts: list[Post], destination_post: Post) -> None:
        self.link_posts_to_post(list(map(lambda p: p.id, origin_posts)), destination_post.id)

    @dispatch(str, str)
    def create_sequence(self, sequence_title: str, sequence_id: str) -> None:
        with GraphDatabase.driver(self.uri, auth=self.auth) as client:
            query = '''
            MERGE (s:Sequence {id: &id})
            ON CREATE SET s.title = $sequence_title
            '''
            # noinspection PyTypeChecker
            client.execute_query(query, title=sequence_title, id=sequence_id)

    @dispatch(Sequence)
    def create_sequence(self, sequence: Sequence) -> None:
        self.create_sequence(sequence.title, sequence.id)

    def link_sequence_chapters(self, sequence: Sequence, chapters: list[Post]) -> None:
        with GraphDatabase.driver(self.uri, auth=self.auth) as client:
            query = '''
            UNWIND $chapters AS chapter
            MERGE (c:Post {id: chapter.id})
            ON CREATE SET c.title = chapter.title
            WITH c, chapter.order AS order
            ORDER BY order
            WITH COLLECT(c) AS sortedChapters
            WITH sortedChapters, sortedChapters[0] AS firstChapter, sortedChapters[-1] AS lastChapter
            MERGE (s:Sequence {id: $sequence_id})
            MERGE (s)-[:BEGINS_WITH]->(firstChapter)
            SET firstChapter:SequenceStart
            MERGE (s)-[:ENDS_WITH]->(lastChapter)
            SET lastChapter:SequenceEnd
            FOREACH (i IN RANGE(0, SIZE(sortedChapters) - 2) |
                MERGE (sortedChapters[i])-[:CONTINUES_TO]->(sortedChapters[i + 1])
            )
            '''
            # noinspection PyTypeChecker
            client.execute_query(query,
                                 sequence_id=sequence.id,
                                 chapters=[{"id": chapter.id, "order": i, "title": chapter.title}
                                           for i, chapter in enumerate(chapters)])

    def link_sequences(self, sequence1: Sequence, sequence2: Sequence) -> None:
        with GraphDatabase.driver(self.uri, auth=self.auth) as client:
            query = '''
            MATCH (s1:Sequence {id: $sequence1_id})-[:ENDS_WITH]->(lastPost:Post)
            MATCH (s2:Sequence {id: $sequence2_id})-[:BEGINS_WITH]->(firstPost:Post)
            MERGE (lastPost)-[:CONTINUES_TO]->(firstPost)
            '''
            # noinspection PyTypeChecker
            client.execute_query(query, sequence1_id=sequence1.id, sequence2_id=sequence2.id)
