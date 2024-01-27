from fastapi import FastAPI, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from jwt import encode

from typing import Union

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/register")
async def register(
    id: Union[str, None] = Header(default=None),
    name: Union[str, None] = Header(default=None),
    password: Union[str, None] = Header(default=None)
):
    if id is None or name is None or password is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request")
    # TODO duplicate check and push to db
    return {"id": id, "name": name, "password": password}

@app.post("/login")
async def login(
    id: Union[str, None] = Header(default=None),
    password: Union[str, None] = Header(default=None)
):
    if id is None or password is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request")
    # TODO auth and get db info
    name = "test"
    return encode({"id": id, "name": name}, "A13E4E2D3A7651E5BBC6A1AAF9AD6")
