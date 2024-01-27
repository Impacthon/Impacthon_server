from hashlib import sha256 as _sha256
from os import environ
from typing import Union

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from jwt import InvalidTokenError, decode, encode
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

# from hmac import new as hmac

load_dotenv()


class Environment:
    def __init__(self):
        self.client = AsyncIOMotorClient(environ["mongo_uri"])
        self.db = self.client[environ["mongo_db"]]
        self.secret_key = environ["secret_key"]


class User(BaseModel):
    user_id: str
    name: str
    gender: str
    password: Union[str, None]
    hashtags: list[str]
    description: str


class Post(BaseModel):
    title: str
    user: User
    post_id: str
    image: str


env = Environment()
app = FastAPI()


def sha256(s: str) -> str:
    return _sha256(f"{s}:{env.secret_key}".encode()).hexdigest()


def unwrap(*args):
    for i in args:
        if i is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request"
            )


def validate_token(token: str) -> bool:
    try:
        decode(token, env.secret_key, ["HS256"])
    except InvalidTokenError:
        return False
    return True


app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.post("/register")
async def register(
    user_id: Union[str, None] = Header(default=None, alias="id"),
    name: Union[str, None] = Header(default=None),
    password: Union[str, None] = Header(default=None),
    gender: Union[str, None] = Header(default=None),
    hashtags: Union[str, None] = Header(default=None),
    description: Union[str, None] = Header(default=None),
) -> User:
    unwrap(user_id, name, password, gender, hashtags, description)
    hashtags = hashtags.split(",")
    pw = sha256(password)
    if await env.db.members.find_one({"user_id": user_id}) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflict")
    await env.db.members.insert_one(
        {
            "user_id": user_id,
            "name": name,
            "password": pw,
            "gender": gender,
            "description": description,
            "hashtags": hashtags,
        }
    )
    return User(
        user_id=user_id,
        name=name,
        password=None,
        gender=gender,
        hashtags=hashtags,
        description=description,
    )


@app.post("/login")
async def login(
    user_id: Union[str, None] = Header(default=None, alias="id"),
    password: Union[str, None] = Header(default=None),
) -> str:
    unwrap(user_id, password)
    user = await env.db.members.find_one(
        {"user_id": user_id, "password": sha256(password)}
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
    return encode({"user_id": user_id, "name": user["name"]}, env.secret_key)


@app.post("/registerExpert")
async def register_expert(
    user_id: Union[str, None] = Header(default=None, alias="id"),
    detail_data: Union[str, None] = Header(default=None, alias="detail"),
):
    unwrap(user_id, detail_data)
    if await env.db.experts.find_one({"user_id": user_id}) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflict")
    await env.db.experts.insert_one({"user_id": user_id, "detail": detail_data})
    return {"user_id": user_id, "detail": detail_data}


@app.post("/post/new")
async def new_post(
    authjwt: Union[str, None] = Header(default=None),
    title: Union[str, None] = Header(default=None),
    image: Union[str, None] = Header(default=None),
) -> Post:
    unwrap(authjwt, title, image)
    if not validate_token(authjwt):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
    _user = decode(authjwt, env.secret_key, ["HS256"])
    user = await env.db.members.find_one({"user_id": _user["user_id"]})
    unwrap(user)
    res = await env.db.posts.insert_one(
        {"title": title, "user_id": _user["user_id"], "image": image}
    )
    user["password"] = None
    return Post(title=title, user=user, post_id=str(res.inserted_id), image=image)


@app.get("/post")
async def get_post(
    authjwt: Union[str, None] = Header(default=None),
    post_id: str = Header(default=None),
) -> Post:
    unwrap(authjwt, post_id)
    if not validate_token(authjwt):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
    _user = decode(authjwt, env.secret_key, ["HS256"])
    user = await env.db.members.find_one({"user_id": _user["user_id"]})
    unwrap(user)
    post = await env.db.posts.find_one({"_id": ObjectId(post_id)})
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    return Post(title=post["title"], user=user, post_id=post_id, image=post["image"])


@app.get("/posts")
async def get_posts(
    authjwt: Union[str, None] = Header(default=None), length: int = Header(default=100)
) -> list[Post]:
    unwrap(authjwt)
    if not validate_token(authjwt):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
    _user = decode(authjwt, env.secret_key, ["HS256"])
    user = await env.db.members.find_one({"user_id": _user["user_id"]})
    unwrap(user)
    posts = []
    for post in await env.db.posts.find({}).to_list(length=length):
        posts.append(
            Post(
                title=post["title"],
                user=await env.db.members.find_one({"user_id": _user["user_id"]}),
                post_id=str(post["_id"]),
                image=post["image"],
            )
        )
    return list(posts)
