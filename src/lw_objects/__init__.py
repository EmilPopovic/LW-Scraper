from .post import Post
from .sequence import Sequence
from .tag import Tag
from .user import User

LwObject = Post | Sequence | Tag | User
