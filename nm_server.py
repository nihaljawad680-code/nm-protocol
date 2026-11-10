from fastapi import FastAPI, HTTPException, Depends, Request
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
import hashlib
import json
from typing import List, Optional

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# --- Post-Quantum Core Ledger (SHA-3 Keccak-256) ---
class QuantumBlock:
    def __init__(self, index, previous_hash, transactions, timestamp=None):
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.timestamp = timestamp or time.time()
        self.nonce = 0
        self.hash = self.compute_hash()

    def compute_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "previous_hash": self.previous_hash,
            "transactions": self.transactions,
            "timestamp": self.timestamp,
            "nonce": self.nonce
        }, sort_keys=True).encode()
        return hashlib.sha3_256(block_string).hexdigest()

    def mine_block(self, difficulty):
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()
        return self.hash

class QuantumBlockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]
        self.difficulty = 3

    def create_genesis_block(self):
        return QuantumBlock(0, "0", {
            "message": "Nm Protocol Genesis - Super-App Omni-Verse v630.0",
            "security": "Post-Quantum SHA-3 & Multi-Feature Engine"
        })

    def add_block(self, new_transactions):
        latest = self.chain[-1]
        new_block = QuantumBlock(
            index=latest.index + 1,
            previous_hash=latest.hash,
            transactions=new_transactions
        )
        new_block.mine_block(self.difficulty)
        self.chain.append(new_block)
        return new_block

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i-1]
            if current.hash != current.compute_hash() or current.previous_hash != previous.hash:
                return False
        return True

# --- Database & Setup ---
SECRET_KEY = "nm_protocol_singularity_omni_6300"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

app = FastAPI(
    title="Nm Protocol Singularity Omni-Verse v630.0",
    version="630.0",
    description="Enterprise-Grade Web3 Super-App (Surpassing Standard Exchanges)"
)

SQLALCHEMY_DATABASE_URL = "sqlite:///./nm_protocol_superapp.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

quantum_chain = QuantumBlockchain()

DAO_PROPOSALS = [
    {"id": 1, "title": "Increase Staking APY to 15%", "votes_yes": 620, "votes_no": 15, "status": "Active"},
    {"id": 2, "title": "Launch Global Crypto Debit Card", "votes_yes": 1250, "votes_no": 42, "status": "Active"}
]

NFT_MARKET = [
    {"id": 1, "name": "Omni-Genesis Node #1", "price": 500.0, "currency": "NSDT", "owner": "NmFoundation"},
    {"id": 2, "name": "Quantum Cyber Pass #42", "price": 1200.0, "currency": "NSDT", "owner": "NizamUddin"}
]

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, default="user@nmprotocol.com")
    hashed_password = Column(String)
    totp_secret = Column(String, default=pyotp.random_base32())
    wallet_address = Column(String, default="Not Connected")
    balance_usdt = Column(Float, default=50000.0)
    balance_nm = Column(Float, default=2100000.0)
    balance_nsdt = Column(Float, default=25000.0)
    staked_nm = Column(Float, default=500000.0)
    referral_code = Column(String, default="NM-NIZAM-99")
    referral_earnings = Column(Float, default=150.0)

Base.metadata.create_all(bind=engine)

# Schemas
class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str
    totp_code: str

class AdvancedSwapReq(BaseModel):
    from_asset: str
    to_asset: str
    amount: float
    target_chain: str = "Ethereum/Polygon"

class WalletConnectReq(BaseModel):
    wallet_address: str

class BuyNftReq(BaseModel):
    nft_id: int

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

@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    if not os.path.exists("index.html"):
        return HTMLResponse(content="<h2 style='color:red;'>Error: index.html missing!</h2>", status_code=404)
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/register")
async def register(user: UserRegister, db = Depends(get_db)):
    if db.query(UserDB).filter(UserDB.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username taken")
    secret = pyotp.random_base32()
    db.add(UserDB(username=user.username, email=user.email, hashed_password=get_password_hash(user.password), totp_secret=secret))
    db.commit()
    return {"message": f"Super-App Registered Successfully! Secret: {secret}"}

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
        "usdt": current_user.balance_usdt,
        "nsdt": current_user.balance_nsdt,
        "nm": current_user.balance_nm,
        "staked": current_user.staked_nm,
        "wallet": current_user.wallet_address,
        "referral_code": current_user.referral_code,
        "referral_earnings": current_user.referral_earnings
    }

@app.post("/wallet/connect-metamask")
async def connect_metamask(req: WalletConnectReq, current_user: UserDB = Depends(get_current_user), db = Depends(get_db)):
    current_user.wallet_address = req.wallet_address
    db.commit()
    return {"message": f"Successfully connected Web3 Wallet: {req.wallet_address[:6]}...{req.wallet_address[-4:]}"}

@app.post("/dex/advanced-swap")
async def advanced_swap(req: AdvancedSwapReq, current_user: UserDB = Depends(get_current_user), db = Depends(get_db)):
    from_c = req.from_asset.upper()
    to_c = req.to_asset.upper()
    amt = req.amount
    if amt <= 0: raise HTTPException(status_code=400, detail="Invalid amount")

    if from_c == "NSDT" and to_c == "NM":
        if current_user.balance_nsdt < amt: raise HTTPException(status_code=400, detail="Insufficient NSDT")
        current_user.balance_nsdt -= amt
        current_user.balance_nm += amt * 45.0
    elif from_c == "NM" and to_c == "NSDT":
        if current_user.balance_nm < amt: raise HTTPException(status_code=400, detail="Insufficient NM")
        current_user.balance_nm -= amt
        current_user.balance_nsdt += amt / 45.0
    elif from_c == "USDT" and to_c == "NSDT":
        if current_user.balance_usdt < amt: raise HTTPException(status_code=400, detail="Insufficient USDT")
        current_user.balance_usdt -= amt
        current_user.balance_nsdt += amt
    else:
        raise HTTPException(status_code=400, detail="Unsupported pair")

    db.commit()
    quantum_chain.add_block({
        "user": current_user.username,
        "action": f"Super-Swap {amt} {from_c} -> {to_c}",
        "bridge": req.target_chain,
        "security": "SHA-3 Keccak-256"
    })
    return {"message": f"Successfully executed Super-Swap of {amt} {from_c} to {to_c}!"}

@app.get("/nft/market")
async def get_nft_market(current_user: UserDB = Depends(get_current_user)):
    return {"nfts": NFT_MARKET}

@app.post("/nft/buy")
async def buy_nft(req: BuyNftReq, current_user: UserDB = Depends(get_current_user), db = Depends(get_db)):
    nft = next((n for n in NFT_MARKET if n["id"] == req.nft_id), None)
    if not nft: raise HTTPException(status_code=404, detail="NFT not found")
    if current_user.balance_nsdt < nft["price"]:
        raise HTTPException(status_code=400, detail="Insufficient NSDT balance to buy NFT")
    current_user.balance_nsdt -= nft["price"]
    nft["owner"] = current_user.username
    db.commit()
    return {"message": f"Successfully purchased NFT: {nft['name']} for {nft['price']} NSDT!"}

@app.get("/chain/quantum-ledger")
async def get_quantum_chain():
    return {
        "length": len(quantum_chain.chain),
        "valid": quantum_chain.is_chain_valid(),
        "chain": [
            {
                "index": b.index,
                "timestamp": b.timestamp,
                "transactions": b.transactions,
                "hash": b.hash,
                "previous_hash": b.previous_hash
            } for b in quantum_chain.chain
        ]
    }
