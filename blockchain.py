import hashlib
import json
import time
import os
import urllib.parse
import requests
import sqlite3
from pymongo import MongoClient
from urllib.parse import urlparse

class KaalChain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.difficulty = 3 
        self.nodes = set()
        self.utxo_set = {}
        self.socketio = None 
        
        self.init_local_db()
        
        # ✅ KAAL CORE: Bootnodes (Networking entry points)
        self.bootnodes = ["kaal-chain.onrender.com"]
        for node in self.bootnodes:
            self.nodes.add(node)

        self.TARGET_BLOCK_TIME = 420  
        self.HALVING_INTERVAL = 300000  
        self.INITIAL_REWARD = 40      
        
        # ✅ Bitcoin Style: Har 2016 blocks ke baad difficulty badlegi
        self.ADJUSTMENT_WINDOW = 2016 
        
        mongo_uri = os.environ.get("MONGO_URI")
        try:
            if mongo_uri:
                parsed = urlparse(mongo_uri)
                if parsed.password:
                    safe_password = urllib.parse.quote_plus(parsed.password)
                    mongo_uri = parsed._replace(
                        netloc=f"{parsed.username}:{safe_password}@{parsed.hostname}"
                    ).geturl()
            
            self.mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.db = self.mongo_client.kaal_db
            self.collection = self.db.ledger
            
            self.load_chain_from_local_db()
            self.sync_with_mongodb()
            
            # ✅ KAAL CORE: Startup par Gossip chalao (With Safety Check)
            try:
                print("⏳ Starting Peer Discovery...")
                self.gossip_with_peers()
            except Exception as gossip_err:
                print(f"⚠️ Gossip delayed: {gossip_err}")
            
            print("✅ KAAL CHAIN: Bitcoin Style Epoch & P2P Core Active!")
        except Exception as e:
            print(f"❌ DB Error: {e}")
            if not self.chain:
                self.load_chain_from_local_db()
                if not self.chain:
                    self.create_genesis_block()

    # ✅ KAAL CORE: Gossip Protocol (Peer Discovery)
    def gossip_with_peers(self):
        """P2P: Bina cloud ke naye nodes dhoondna"""
        new_peers = set()
        for peer in list(self.nodes):
            try:
                url = f"https://{peer}/get_stats" if "onrender.com" in peer else f"http://{peer}/get_stats"
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    peers_from_node = data.get('nodes', [])
                    for p in peers_from_node:
                        if p not in self.nodes:
                            new_peers.add(p)
            except:
                continue
        self.nodes.update(new_peers)
        if new_peers:
            print(f"🔱 Gossip: {len(new_peers)} naye peers mile!")

    # ✅ KAAL CORE: Direct P2P Broadcast
    def broadcast_block(self, block):
        """Naya block saare padosi nodes ko direct bhejna"""
        for peer in list(self.nodes):
            if "onrender.com" in peer: continue 
            try:
                url = f"http://{peer}/add_block_p2p"
                requests.post(url, json=block, timeout=2)
            except:
                continue

    def init_local_db(self):
        self.conn = sqlite3.connect('kaalchain_local.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('CREATE TABLE IF NOT EXISTS blocks (idx INTEGER PRIMARY KEY, data TEXT NOT NULL)')
        self.conn.commit()

    def load_chain_from_local_db(self):
        self.cursor.execute('SELECT data FROM blocks ORDER BY idx ASC')
        rows = self.cursor.fetchall()
        if rows:
            self.chain = [json.loads(row[0]) for row in rows]
            if 'difficulty' in self.chain[-1]:
                self.difficulty = self.chain[-1]['difficulty']
            self.rebuild_utxo_set()
            print(f"✅ {len(self.chain)} Blocks loaded from Local Disk.")
        else:
            print("ℹ️ Local DB is empty.")

    def sync_with_mongodb(self):
        """Two-Way Smart Sync"""
        try:
            db_data = list(self.collection.find({}, {'_id': 0}).sort("index", 1))
            if db_data and len(db_data) > len(self.chain):
                if self.is_chain_valid(db_data):
                    for block in db_data:
                        self.save_block_locally(block)
                    self.chain = db_data
                    self.rebuild_utxo_set()
            elif len(self.chain) > len(db_data):
                missed_blocks = self.chain[len(db_data):]
                for b in missed_blocks:
                    self.collection.insert_one(b.copy())
            elif not self.chain and not db_data:
                self.create_genesis_block()
        except Exception as e:
            print(f"Sync Error: {e}")

    def save_block_locally(self, block):
        block_json = json.dumps(block)
        self.cursor.execute('INSERT OR REPLACE INTO blocks (idx, data) VALUES (?, ?)', 
                           (block['index'], block_json))
        self.conn.commit()

    def rebuild_utxo_set(self):
        self.utxo_set = {}
        for block in self.chain:
            reward_id = f"REWARD_BLOCK_{block['index']}_{block['timestamp']}"
            miner_addr = "GENESIS"
            for tx in block.get('transactions', []):
                if tx['sender'] == "KAAL_NETWORK":
                    miner_addr = tx['receiver']
                    break
            if block.get('reward', 0) > 0:
                self.utxo_set[reward_id] = {'receiver': miner_addr, 'amount': float(block['reward'])}
            for tx in block.get('transactions', []):
                if tx['sender'] == "KAAL_NETWORK": continue
                tx_id = tx.get('signature', f"TX_{tx['timestamp']}")
                self.utxo_set[tx_id] = {'receiver': tx['receiver'], 'amount': float(tx['amount'])}
                spent_key = f"SPENT_{tx_id}_{tx['sender']}"
                self.utxo_set[spent_key] = {'receiver': tx['sender'], 'amount': -float(tx['amount'])}

    def register_node(self, address):
        if not address: return
        parsed_url = urlparse(address)
        node_address = parsed_url.netloc if parsed_url.netloc else parsed_url.path
        if node_address and node_address != "kaal-chain.onrender.com":
            self.nodes.add(node_address)

    def resolve_conflicts(self):
        neighbours = self.nodes
        new_chain = None
        max_length = len(self.chain)
        for node in neighbours:
            try:
                url = f"https://{node}/get_stats" if "onrender.com" in node else f"http://{node}/get_stats"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    length = data['blocks']
                    chain = data['chain'][::-1] 
                    if length > max_length and self.is_chain_valid(chain):
                        max_length = length
                        new_chain = chain
            except: continue
        if new_chain:
            self.chain = new_chain
            for block in self.chain: self.save_block_locally(block)
            self.rebuild_utxo_set()
            return True
        return False

    def hash_block(self, block):
        verified_block = {k: v for k, v in block.items() if k not in ['hash', '_id']}
        encoded_block = json.dumps(verified_block, sort_keys=True).encode()
        return hashlib.sha256(encoded_block).hexdigest()

    def is_chain_valid(self, chain):
        """Hard Integrity Check: Admin tamper-proof"""
        if not chain: return False
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != last_block['hash']: return False
            if block['hash'] != self.hash_block(block): return False
            if not block['hash'].startswith('0' * int(block.get('difficulty', 3))): return False
            last_block = block
            current_index += 1
        return True

    def create_genesis_block(self):
        if not self.chain: 
            self.add_transaction("KAAL_NETWORK", "GENESIS", 0, "🔱 KAAL CHAIN: The Era of KaaL Begins")
            self.create_block(proof=100, previous_hash='0')

    def create_block(self, proof, previous_hash):
        # ✅ Bitcoin Style Adjustment: Har 2016 blocks par
        if len(self.chain) > 0 and len(self.chain) % self.ADJUSTMENT_WINDOW == 0:
            start_block = self.chain[-self.ADJUSTMENT_WINDOW]
            last_block = self.chain[-1]
            actual_time = last_block['timestamp'] - start_block['timestamp']
            expected_time = self.ADJUSTMENT_WINDOW * self.TARGET_BLOCK_TIME
            
            if actual_time < expected_time / 2:
                self.difficulty += 1
            elif actual_time > expected_time * 2:
                self.difficulty = max(3, self.difficulty - 1)
            print(f"🔱 Difficulty Epoch Reached: New Difficulty {self.difficulty}")

        halvings = len(self.chain) // self.HALVING_INTERVAL
        block_reward = self.INITIAL_REWARD / (2 ** halvings)
        
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': list(self.pending_transactions),
            'proof': proof,
            'previous_hash': previous_hash,
            'reward': block_reward,
            'difficulty': self.difficulty 
        }
        
        block['hash'] = self.hash_block(block)
        self.pending_transactions = []
        
        self.save_block_locally(block)
        self.chain.append(block)
        self.rebuild_utxo_set()
        
        if self.socketio:
            self.socketio.emit('new_block', {'index': block['index'], 'hash': block['hash']}, broadcast=True)
        
        # ✅ KAAL CORE: Direct P2P Broadcast (MongoDB bypass)
        self.broadcast_block(block)
        
        try:
            self.collection.insert_one(block.copy())
        except: pass
        return block

    def get_balance(self, address):
        bal = 0
        for tx_id, output in self.utxo_set.items():
            if output['receiver'] == address:
                bal += output['amount']
        return round(bal, 2)

    def add_transaction(self, sender, receiver, amount, signature):
        if signature in [tx['signature'] for tx in self.pending_transactions]:
            return False, "Double transaction!"
        if sender != "KAAL_NETWORK":
            if self.get_balance(sender) < float(amount):
                return False, "Low Balance!"
        
        self.pending_transactions.append({
            'sender': sender, 'receiver': receiver, 'amount': float(amount), 
            'timestamp': time.time(), 'signature': signature
        })
        return True, "Success"

    def mine_block(self, miner_address, proof):
        pichla_hash = self.chain[-1]['hash'] if self.chain else '0'
        halvings = len(self.chain) // self.HALVING_INTERVAL
        current_reward = self.INITIAL_REWARD / (2 ** halvings)
        reward_sig = f"REWARD_{int(time.time())}_{miner_address[:8]}"
        self.add_transaction("KAAL_NETWORK", miner_address, current_reward, reward_sig)
        return self.create_block(proof, pichla_hash)
