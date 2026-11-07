import http.server
import json
import sqlite3
import hashlib
import secrets

PORT = 8080
DB_FILE = "nm_protocol.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS accounts 
                 (username TEXT PRIMARY KEY, balance REAL, points REAL, pub_address TEXT, priv_key TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stats 
                 (key TEXT PRIMARY KEY, value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, receiver TEXT, amount REAL, fee REAL, type TEXT)''')
    
    # আপনার বরাদ্দ ১,৫০১,০০০ NM এবং মাইনিং পুল ৫০০,০০০ NM
    c.execute("SELECT * FROM accounts WHERE username='Nizam'")
    if not c.fetchone():
        priv = secrets.token_hex(32)
        pub = "0x" + hashlib.sha256(priv.encode()).hexdigest()[:40]
        c.execute("INSERT INTO accounts VALUES ('Nizam', 1501000, 0, ?, ?)", (pub, priv))
        c.execute("INSERT INTO accounts VALUES ('MiningPool', 500000, 0, '0xMiningPoolSmartContract', 'N/A')", ())
        
        c.execute("INSERT INTO stats VALUES ('total_burned', 0)")
        c.execute("INSERT INTO stats VALUES ('total_txs', 1)")
        c.execute("INSERT INTO transactions (sender, receiver, amount, fee, type) VALUES ('Genesis System', 'Nizam', 1501000, 0, 'Founder Allocation')")
        conn.commit()
    conn.close()

init_db()

class TokenHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ["/api/data", "/index.html", "/"]:
            if self.path in ["/", "/index.html"]:
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(HTML_CONTENT.encode("utf-8"))
                return
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT username, balance, points, pub_address FROM accounts")
            accounts = {row[0]: {"balance": row[1], "points": row[2], "address": row[3]} for row in c.fetchall()}
            
            c.execute("SELECT key, value FROM stats")
            stats = {row[0]: row[1] for row in c.fetchall()}
            
            c.execute("SELECT sender, receiver, amount, fee, type FROM transactions ORDER BY id DESC LIMIT 20")
            txs = [{"sender": row[0], "receiver": row[1], "amount": row[2], "fee": row[3], "type": row[4]} for row in c.fetchall()]
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"balances": accounts, "stats": stats, "transactions": txs}).encode("utf-8"))
        else:
            return super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        req = json.loads(post_data.decode("utf-8"))
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        if self.path == "/api/create-wallet":
            username = req.get("username")
            c.execute("SELECT * FROM accounts WHERE username=?", (username,))
            if c.fetchone():
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Username taken!"}).encode("utf-8"))
                conn.close()
                return
            
            priv = secrets.token_hex(32)
            pub = "0x" + hashlib.sha256(priv.encode()).hexdigest()[:40]
            c.execute("INSERT INTO accounts VALUES (?, 0, 0, ?, ?)", (username, pub, priv))
            conn.commit()
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "address": pub, "private_key": priv}).encode("utf-8"))
            return

        elif self.path == "/api/mine-points":
            username = req.get("username")
            c.execute("SELECT * FROM accounts WHERE username=?", (username,))
            if not c.fetchone():
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "User not found!"}).encode("utf-8"))
                conn.close()
                return
            
            earned_points = 3.0  # দৈনিক বা সেশনের জন্য নির্ধারিত ৩ পয়েন্ট
            c.execute("UPDATE accounts SET points = points + ? WHERE username=?", (earned_points, username))
            conn.commit()
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "points": earned_points}).encode("utf-8"))
            return

        elif self.path == "/api/claim-tokens":
            username = req.get("username")
            c.execute("SELECT points FROM accounts WHERE username=?", (username,))
            row = c.fetchone()
            if not row or row[0] < 10000:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Minimum 10,000 points required to claim 1 NM!"}).encode("utf-8"))
                conn.close()
                return
            
            user_points = row[0]
            conversion_rate = 10000.0  # ১০,০০০ পয়েন্ট = ১ NM
            tokens_to_claim = user_points // conversion_rate  # পূর্ণাঙ্গ টোকেন হিসাব
            points_deducted = tokens_to_claim * conversion_rate

            if tokens_to_claim <= 0:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Not enough points for 1 NM!"}).encode("utf-8"))
                conn.close()
                return

            c.execute("SELECT balance FROM accounts WHERE username='MiningPool'")
            pool_row = c.fetchone()
            if not pool_row or pool_row[0] < tokens_to_claim:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Mining pool exhausted!"}).encode("utf-8"))
                conn.close()
                return

            c.execute("UPDATE accounts SET balance = balance - ? WHERE username='MiningPool'", (tokens_to_claim,))
            c.execute("UPDATE accounts SET balance = balance + ?, points = points - ? WHERE username=?", (tokens_to_claim, points_deducted, username))
            c.execute("UPDATE stats SET value = value + 1 WHERE key='total_txs'")
            c.execute("INSERT INTO transactions (sender, receiver, amount, fee, type) VALUES ('MiningPool', ?, ?, 0, 'Point Claim')", (username, tokens_to_claim))
            conn.commit()
            conn.close()

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "claimed": tokens_to_claim}).encode("utf-8"))
            return

        conn.close()
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"success": True}).encode("utf-8"))

HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nm Protocol Mining & Claim</title>
    <style>
        body { font-family: sans-serif; background: #0b0e11; color: #eaecef; padding: 15px; margin: 0; }
        .container { max-width: 500px; margin: auto; background: #181a20; padding: 20px; border-radius: 12px; border: 1px solid #2b313a; }
        h2 { color: #f0b90b; text-align: center; }
        .box { background: #2b313a; padding: 12px; margin-bottom: 12px; border-radius: 8px; }
        input, button { width: 100%; padding: 10px; margin-top: 8px; border-radius: 6px; border: none; box-sizing: border-box; }
        input { background: #0b0e11; color: #fff; border: 1px solid #474d57; }
        button { background: #f0b90b; font-weight: bold; cursor: pointer; }
        .claim-btn { background: #0ecb81; color: #000; }
        .tx-list { font-size: 12px; max-height: 120px; overflow-y: auto; padding-left: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>⚡ Nm Protocol Mining & Claim</h2>
        <div class="box" id="stats">Loading Stats...</div>
        
        <button onclick="createWallet()" style="background:#22252a; color:#f0b90b; border:1px solid #f0b90b;">🔑 Create Miner Account</button>
        
        <div class="box" style="margin-top:12px;">
            <h3>⛏️ Miner Dashboard & Points</h3>
            <input type="text" id="minerName" placeholder="Enter Your Username">
            <button onclick="startMining()" style="background:#f6465d; color:#fff;">Daily Check-in (+3 Points)</button>
            <button class="claim-btn" onclick="claimTokens()" style="margin-top:8px;">Claim NM (10,000 Pts = 1 NM)</button>
        </div>

        <div class="box">
            <h3>Accounts & Balances</h3>
            <div id="balances"></div>
        </div>

        <div class="box">
            <h3>Ledger History</h3>
            <ul class="tx-list" id="txs"></ul>
        </div>
    </div>
    <script>
        async function load() {
            let res = await fetch('/api/data');
            let d = await res.json();
            document.getElementById('stats').innerHTML = `🔥 Total Burned: <b>${d.stats.total_burned.toFixed(2)} NM</b> | Txs: <b>${d.stats.total_txs}</b>`;
            
            let b = ''; 
            for(let u in d.balances) {
                b += `<div><b>${u}</b> ➔ Balance: <span style="color:#f0b90b">${d.balances[u].balance} NM</span> | Points: <span style="color:#0ecb81">${d.balances[u].points} Pts</span></div><hr style="border-color:#363c4e">`;
            }
            document.getElementById('balances').innerHTML = b;
            
            let t = ''; 
            d.transactions.forEach(x => t += `<li>[${x.type}] ${x.sender} ➔ ${x.receiver}: ${x.amount} NM</li>`);
            document.getElementById('txs').innerHTML = t;
        }

        async function createWallet() {
            let u = prompt("Enter Miner Username:"); if(!u) return;
            let res = await fetch('/api/create-wallet', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:u})});
            let d = await res.json();
            if(res.ok) alert("Account Created! Address: " + d.address); else alert(d.error);
            load();
        }

        async function startMining() {
            let username = document.getElementById('minerName').value;
            if(!username) return alert("Enter your username first!");
            let res = await fetch('/api/mine-points', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username})});
            let d = await res.json();
            if(res.ok) alert("Success! Earned 3 Points."); else alert(d.error);
            load();
        }

        async function claimTokens() {
            let username = document.getElementById('minerName').value;
            if(!username) return alert("Enter your username first!");
            let res = await fetch('/api/claim-tokens', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username})});
            let d = await res.json();
            if(res.ok) alert(`Successfully Claimed ${d.claimed} NM!`); else alert(d.error);
            load();
        }

        load(); setInterval(load, 4000);
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    server = http.server.HTTPServer(("127.0.0.1", PORT), TokenHandler)
    print(f"Mining Server running at http://127.0.0.1:{PORT}")
    server.serve_forever()
