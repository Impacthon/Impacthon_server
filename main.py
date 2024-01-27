import asyncio
from hashlib import sha256
from os import environ
from typing import Union

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from jwt import decode, encode
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

load_dotenv(verbose=True)


class Environment:
    def __init__(self):
        self.client = AsyncIOMotorClient(
            environ["mongo_uri"], tls=True, tlsAllowInvalidCertificates=True
        )
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


@app.get("/search")
async def search(query: Union[str, None] = Header(default=None)):
    if query is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request"
        )
    return await env.db.experts.find({"detail": {"$regex": query}}).to_list(None)


@app.get("/chatlist")
async def chatlist(
    user_id: Union[str, None] = Header(default=None, alias="id")
) -> list:
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request"
        )
    return await env.db.chat.find(
        ({"$or": [{"chat1": user_id}, {"chat2": user_id}]})
    ).to_list(None)


@app.post(
    "/chat/create",
    description="""
chat_id: 채팅 아이디(UUID4)\n
chat1: 채팅 참가자 1 아이디(로그인 시 아이디 입력)\n
chat2: 채팅 참가자 2 아이디(로그인 시 아이디 입력)
""",
)
async def create_chat(chat_id: str, chat1: str, chat2: str):
    """
    chat_id: str
    chat1: str
    chat2: str
    """
    await env.db.chat.insert_one(
        {
            "_id": chat_id,
            "chat1": chat1,
            "chat2": chat2,
            "history": [],
        }
    )
    return {
        "chat_id": chat_id,
        "chat1": chat1,
        "chat2": chat2,
        "history": [],
    }


@app.websocket("/chat/{chat_id}/{user_id}")
async def chat_ws(websocket: WebSocket, chat_id: str, user_id: str):
    await websocket.accept()
    chat = await env.db.chat.find_one({"_id": chat_id})
    chat_history = chat["history"]
    if chat is None:
        await env.db.chat.insert_one({"_id": chat_id, "history": []})
        chat = await env.db.chat.find_one({"_id": chat_id})
        chat_history = chat["history"]
    else:
        if (chat["chat1"] != user_id) and (chat["chat2"] != user_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
            )
    await websocket.send_text(str(chat_history))
    while True:
        _new_chat_history = (await env.db.chat.find_one({"_id": chat_id}))["history"]
        if chat_history != _new_chat_history:
            chat_history = _new_chat_history
            await websocket.send_text(str(chat_history[-1]))

        try:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=10)
            await env.db.chat.update_one(
                {"_id": chat_id},
                {"$push": {"history": {"user_id": user_id, "data": data}}},
            )
            chat_history = (await env.db.chat.find_one({"_id": chat_id}))["history"]
        except asyncio.TimeoutError:
            pass
