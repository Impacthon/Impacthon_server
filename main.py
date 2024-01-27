from hashlib import sha256
from os import environ
from typing import Union

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from jwt import encode
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
    password: Union[str, None]


env = Environment()
app = FastAPI()

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.post("/register")
async def register(
    user_id: Union[str, None] = Header(default=None, alias="id"),
    name: Union[str, None] = Header(default=None),
    password: Union[str, None] = Header(default=None),
) -> User:
    pw = sha256(password).hexdigest()
    if user_id is None or name is None or password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request"
        )
    if await env.db.members.find_one({"user_id": user_id, "password": pw}) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflict")
    await env.db.members.insert_one({"user_id": user_id, "name": name, "password": pw})
    return User(user_id, name, None)


@app.post("/login")
async def login(
    user_id: Union[str, None] = Header(default=None, alias="id"),
    password: Union[str, None] = Header(default=None),
) -> str:
    if id is None or password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request"
        )
    user = await env.db.members.find_one(
        {"user_id": user_id, "password": sha256(password).hexdigest()}
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
    return encode({"user_id": user_id, "name": user.name}, env.secret_key)


@app.post("/registerExpert")
async def register_export(
    user_id: Union[str, None] = Header(default=None, alias="id"),
    detail_data: Union[str, None] = Header(default=None, alias="detail"),
):
    if user_id is None or detail_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request"
        )
    if await env.db.experts.find_one({"user_id": user_id}) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflict")
    await env.db.experts.insert_one({"user_id": user_id, "detail": detail_data})
    return {"user_id": user_id, "detail": detail_data}
