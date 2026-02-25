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
        self.difficulty = 3 # 3 se shuruwat
        
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
            # 1. Pehle database se data ek temporary variable mein lo
            db_data = list(self.collection.find({}, {'_id': 0}).sort("index", 1))
            
            if db_data:
                # 2. Jab data mil jaye, tabhi purani chain ko badlo
                # Isse balance kabhi 0 nahi dikhayega beech mein
                self.chain = db_data
                self.difficulty = 3 + (len(self.chain) // 10000) * 0.5
            else:
                # Agar DB bilkul khali hai, tabhi genesis banao
                if not self.chain:
                    self.create_genesis_block()
        except Exception as e:
            print(f"Sync Error: {e}")

    def create_genesis_block(self):
        if not self.chain: 
            self.create_block(proof=100, previous_hash='0')

    def create_block(self, proof, previous_hash):
        # 10,000 blocks par 0.5 difficulty badhana
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
            'reward': block_reward
        }
        
        encoded_block = json.dumps(block, sort_keys=True).encode()
        block['hash'] = hashlib.sha256(encoded_block).hexdigest()
        
        self.pending_transactions = []
        self.chain.append(block)
        
        try:
            # Pura data refresh karne ke liye delete then insert
            self.collection.delete_many({}) 
            if self.chain: 
                self.collection.insert_many(self.chain)
        except: 
            pass
        return block

    def get_balance(self, address):
        bal = 0
        for block in self.chain:
            # Reward logic mining se
            for tx in block.get('transactions', []):
                if tx['sender'] == address: 
                    bal -= float(tx['amount'])
                if tx['receiver'] == address: 
                    bal += float(tx['amount'])
        return round(bal, 2)

    def add_transaction(self, sender, receiver, amount, signature):
        # 1. Double Entry Check
        for tx in self.pending_transactions:
            if tx['signature'] == signature:
                return False, "Double transaction!"

        # 2. Balance Check (Minus hone se rokne ke liye)
        if sender != "KAAL_NETWORK":
            current_balance = self.get_balance(sender)
            if current_balance < float(amount):
                return False, "Low Balance!"

        self.pending_transactions.append({
            'sender': sender, 'receiver': receiver, 
            'amount': float(amount), 'timestamp': time.time(), 'signature': signature
        })
        return True, "Success"

        self.pending_transactions.append({
            'sender': sender, 
            'receiver': receiver, 
            'amount': float(amount), 
            'timestamp': time.time(), 
            'signature': signature
        })
        return True, "Transaction success wait for next mined block"

    def mine_block(self, miner_address, proof):
        pichla_hash = self.chain[-1]['hash'] if self.chain else '0'
        
        current_supply = sum(b.get('reward', 0) for b in self.chain)
        if current_supply + 40 <= 51000000:
            self.add_transaction("KAAL_NETWORK", miner_address, 40, "NETWORK_SIG") # 40 KAAL reward
        
        return self.create_block(proof, pichla_hash)



