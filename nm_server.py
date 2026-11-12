from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
import random
import os
import pyotp
import time
import asyncio
from typing import List

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

SECRET_KEY = "nm_protocol_singularity_omni_5300"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

app = FastAPI(title="Nm Protocol Singularity Omni-Verse v530.0", version="530.0")

SQLALCHEMY_DATABASE_URL = "sqlite:///./nm_protocol.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- ডেটাবেজ টেবিল স্ট্রাকচার ---
class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, default="user@nmprotocol.com")
    hashed_password = Column(String)
    totp_secret = Column(String, default=pyotp.random_base32())
    role = Column(String, default="user")
    balance_usdt = Column(Float, default=40000.0)
    balance_nm = Column(Float, default=3000000.0)
    staked_nm = Column(Float, default=1000000.0)
    web3_wallet = Column(String, default="Not Connected")

class TransactionDB(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    tx_type = Column(String)
    amount = Column(Float)
    asset = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# --- কোয়ান্টাম লেজার কোর (আপনার আগের লেজার লজিক) ---
class QuantumBlock:
    def __init__(self, index, previous_hash, transactions, timestamp=None):
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.timestamp = timestamp or time.time()
        self.nonce = 0
        self.hash = self.compute_hash()

    def compute_hash(self):
        block_string = json_dumps = f"{self.index}-{self.previous_hash}-{self.transactions}-{self.timestamp}-{self.nonce}"
        return hashlib.sha256(block_string.encode()).hexdigest()

import hashlib
import json

# জেনেসিস ব্লক ইনিশিয়ালাইজেশন
blockchain = [QuantumBlock(0, "0", "Genesis Block - Nm Protocol Singularity")]

# --- ব্যাকগ্রাউন্ড স্টাকিং রিওয়ার্ড ইঞ্জিন ---
async def background_engine():
    while True:
        await asyncio.sleep(15)
        db = SessionLocal()
        try:
            users = db.query(UserDB).all()
            for u in users:
                if u.staked_nm > 0:
                    u.balance_nm += u.staked_nm * 0.0002
            db.commit()
        except Exception:
            pass
        finally:
            db.close()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_engine())

# --- সিকিউরিটি ফায়ারওয়াল ও রেট লিমিটার ---
REQUEST_LOGS = {}
@app.middleware("http")
async def quantum_firewall_rate_limiter(request: Request, call_next):
    client_ip = request.client.host
    current_time = time.time()
    if client_ip not in REQUEST_LOGS:
        REQUEST_LOGS[client_ip] = []
    REQUEST_LOGS[client_ip] = [t for t in REQUEST_LOGS[client_ip] if current_time - t < 10]
    if len(REQUEST_LOGS[client_ip]) > 60:
        return JSONResponse(status_code=429, content={"detail": "Omni-Verse Firewall: Rate limit exceeded."})
    REQUEST_LOGS[client_ip].append(current_time)
    response = await call_next(request)
    return response

# --- WebSocket ম্যানেজার ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

# --- Pydantic স্কিমা ---
class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str
    totp_code: str

class Web3ConnectReq(BaseModel):
    wallet_address: str

class SwapReq(BaseModel):
    from_asset: str
    to_asset: str
    amount: float

# --- হেল্পার ফাংশন ---
def get_password_hash(password: str): return pwd_context.hash(password)
def verify_password(plain, hashed): return pwd_context.verify(plain, hashed)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db = Depends(get_db)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user = db.query(UserDB).filter(UserDB.username == payload.get("sub")).first()
        if not user: raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.PyJWTError: raise HTTPException(status_code=401, detail="Invalid token")

# --- রাউটস ও এন্ডপয়েন্টস ---
@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    if not os.path.exists("index.html"):
        return HTMLResponse(content="<h2 style='color:red;'>Error: index.html missing! Place nm_server.py and index.html in the SAME folder.</h2>", status_code=404)
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/register")
async def register(user: UserRegister, db = Depends(get_db)):
    if db.query(UserDB).filter(UserDB.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username taken")
    secret = pyotp.random_base32()
    db.add(UserDB(username=user.username, email=user.email, hashed_password=get_password_hash(user.password), totp_secret=secret))
    db.commit()
    return {"message": f"Registered Successfully! Google Auth Secret: {secret}"}

@app.post("/login")
async def login(user: UserLogin, db = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    totp = pyotp.TOTP(db_user.totp_secret)
    if not totp.verify(user.totp_code):
        raise HTTPException(status_code=401, detail="Invalid TOTP Code")
    token = jwt.encode({"sub": user.username, "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/wallet/balance")
async def get_balance(current_user: UserDB = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "email": current_user.email,
        "usdt": current_user.balance_usdt,
        "nm": current_user.balance_nm,
        "staked_nm": current_user.staked_nm,
        "web3_wallet": current_user.web3_wallet,
        "totp_secret": current_user.totp_secret,
        "blockchain_height": len(blockchain)
    }

@app.post("/wallet/web3-connect")
async def web3_connect(req: Web3ConnectReq, current_user: UserDB = Depends(get_current_user), db = Depends(get_db)):
    current_user.web3_wallet = req.wallet_address
    db.commit()
    return {"message": f"Web3 Wallet connected successfully: {req.wallet_address[:6]}...{req.wallet_address[-4:]}"}

@app.post("/dex/swap")
async def dex_swap(req: SwapReq, current_user: UserDB = Depends(get_current_user), db = Depends(get_db)):
    if req.from_asset.upper() == "USDT" and req.to_asset.upper() == "NM":
        cost_usdt = req.amount
        earned_nm = req.amount * 45.0
        if current_user.balance_usdt < cost_usdt:
            raise HTTPException(status_code=400, detail="Insufficient USDT balance for swap")
        current_user.balance_usdt -= cost_usdt
        current_user.balance_nm += earned_nm
    elif req.from_asset.upper() == "NM" and req.to_asset.upper() == "USDT":
        cost_nm = req.amount
        earned_usdt = req.amount / 45.0
        if current_user.balance_nm < cost_nm:
            raise HTTPException(status_code=400, detail="Insufficient NM balance for swap")
        current_user.balance_nm -= cost_nm
        current_user.balance_usdt += earned_usdt
    else:
        raise HTTPException(status_code=400, detail="Invalid trading pair")

    tx = TransactionDB(username=current_user.username, tx_type=f"DEX SWAP {req.from_asset} -> {req.to_asset}", amount=req.amount, asset=req.from_asset.upper())
    db.add(tx)
    db.commit()
    return {"message": f"Successfully swapped {req.amount} {req.from_asset} via DEX pool!"}

@app.get("/wallet/ledger")
async def get_ledger(current_user: UserDB = Depends(get_current_user), db = Depends(get_db)):
    txs = db.query(TransactionDB).filter(TransactionDB.username == current_user.username).order_by(TransactionDB.timestamp.desc()).all()
    return [{"id": t.id, "type": t.tx_type, "amount": t.amount, "asset": t.asset, "time": t.timestamp.strftime("%Y-%m-%d %H:%M:%S")} for t in txs]

@app.get("/oracle/prices")
async def get_oracle_prices():
    nm_val = 30.5 + random.uniform(-0.2, 0.2)
    ai_prediction = "BULLISH 🚀 (Expected +14.2% surge in next 1H)" if random.random() > 0.4 else "STABLE 📊 (Consolidation phase active)"
    return {
        "BTC_USDT": round(105000.00 + random.uniform(-100, 100), 2),
        "ETH_USDT": round(4200.50 + random.uniform(-20, 20), 2),
        "NM_USDT": round(nm_val, 4),
        "ai_signal": ai_prediction,
        "oracle_source": "Omni-Verse AI Feed v530.0"
    }

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast({"sender": "OmniAI", "message": data, "time": datetime.utcnow().strftime("%H:%M:%S")})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
