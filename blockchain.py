import hashlib
import json
import time
import os
import urllib.parse
from pymongo import MongoClient
from urllib.parse import urlparse

class KaalChain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.difficulty = 3 #
        
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
            self.load_chain_from_db()
            print("✅ Database Connected Successfully!")
        except Exception as e:
            print(f"❌ DB Error: {e}")
            self.create_genesis_block()

    def load_chain_from_db(self):
        try:
            # Atomic Load: Pehle data variable mein lo, fir memory update karo
            db_data = list(self.collection.find({}, {'_id': 0}).sort("index", 1))
            if db_data and len(db_data) > 0:
                self.chain = db_data
                self.difficulty = 3 + (len(self.chain) // 10000) * 0.5
            elif not self.chain:
                self.create_genesis_block()
        except Exception as e:
            print(f"Sync Error: {e}")

    def create_genesis_block(self):
        if not self.chain: 
            self.create_block(proof=100, previous_hash='0')

    def create_block(self, proof, previous_hash):
        self.difficulty = 3 + (len(self.chain) // 10000) * 0.5
        
        # Max Supply 51M logic
        current_supply = sum(b.get('reward', 0) for b in self.chain)
        max_supply = 51000000
        block_reward = 40 if current_supply + 40 <= max_supply else 0
        
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': list(self.pending_transactions),
            'proof': proof,
            'previous_hash': previous_hash,
            'reward': block_reward #
        }
        
        encoded_block = json.dumps(block, sort_keys=True).encode()
        block['hash'] = hashlib.sha256(encoded_block).hexdigest()
        
        self.pending_transactions = []
        self.chain.append(block)
        
        try:
            # FIX: Pura delete karne ke bajaye sirf naya block insert karo
            self.collection.insert_one(block)
        except: 
            pass
        return block

    def get_balance(self, address):
        if not self.chain: return 0.0
        bal = 0
        for block in self.chain:
            for tx in block.get('transactions', []):
                if tx['sender'] == address: 
                    bal -= float(tx['amount'])
                if tx['receiver'] == address: 
                    bal += float(tx['amount'])
        return round(bal, 2)

    def add_transaction(self, sender, receiver, amount, signature):
        # Double Entry Check
        for tx in self.pending_transactions:
            if tx['signature'] == signature:
                return False, "Double transaction!"

        # Balance Check
        if sender != "KAAL_NETWORK":
            current_balance = self.get_balance(sender)
            if current_balance < float(amount):
                return False, "Low Balance!"

        self.pending_transactions.append({
            'sender': sender, 
            'receiver': receiver, 
            'amount': float(amount), 
            'timestamp': time.time(), 
            'signature': signature
        })
        return True, "Success"

    def mine_block(self, miner_address, proof):
        # Naya block mine karne se pehle fresh sync
        self.load_chain_from_db()
        pichla_hash = self.chain[-1]['hash'] if self.chain else '0'
        
        current_supply = sum(b.get('reward', 0) for b in self.chain)
        if current_supply + 40 <= 51000000:
            # 40 KAAL reward logic
            self.add_transaction("KAAL_NETWORK", miner_address, 40, "NETWORK_SIG")
        
        return self.create_block(proof, pichla_hash)
