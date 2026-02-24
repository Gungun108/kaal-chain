import hashlib
import json
import time
import os
import ecdsa
import urllib.parse
from pymongo import MongoClient
from urllib.parse import urlparse # Yeh sabse zaruri hai

class KaalChain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.difficulty = 2 
        
        mongo_uri = os.environ.get("MONGO_URI")
        
        try:
            if mongo_uri:
                # Password ko automatically "safe" banane ka logic
                parsed = urlparse(mongo_uri)
                if parsed.password:
                    safe_password = urllib.parse.quote_plus(parsed.password)
                    # Naya safe URI generate karna
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
            data = list(self.collection.find({}, {'_id': 0}).sort("index", 1))
            if data: self.chain = data
            else: self.create_genesis_block()
        except: self.create_genesis_block()

    # ... baaki ka mining aur block creation logic ...
    def create_block(self, proof, previous_hash):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': list(self.pending_transactions),
            'proof': proof,
            'previous_hash': previous_hash,
            'reward': 51
        }
        block['hash'] = hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()
        self.pending_transactions = []
        self.chain.append(block)
        try:
            self.collection.delete_many({})
            if self.chain: self.collection.insert_many(self.chain)
        except: pass
        return block

    def create_genesis_block(self):
        if not self.chain: self.create_block(proof=100, previous_hash='0')

    def mine_block(self, miner_address, proof):
        last_hash = self.chain[-1]['hash'] if self.chain else '0'
        self.pending_transactions.append({'sender': "KAAL_NETWORK", 'receiver': miner_address, 'amount': 51, 'timestamp': time.time()})
        return self.create_block(proof, last_hash)
