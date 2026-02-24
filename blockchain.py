import hashlib
import json
import time
import os
import ecdsa
import urllib.parse
from pymongo import MongoClient
from urllib.parse import urlparse # Database ka link tod-marod kar sahi karne ke liye

class KaalChain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.difficulty = 2 
        
        # Cloud (Render) se database ka link uthana
        mongo_uri = os.environ.get("MONGO_URI")
        try:
            if mongo_uri:
                # Password ko safe banane ka system taaki crash na ho
                parsed = urlparse(mongo_uri)
                if parsed.password:
                    safe_password = urllib.parse.quote_plus(parsed.password)
                    mongo_uri = parsed._replace(
                        netloc=f"{parsed.username}:{safe_password}@{parsed.hostname}"
                    ).geturl()
            
            # Database se judna aur ledger collection ko pakadna
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
            # Database se saare blocks ko unke number (index) ke hisaab se mangwana
            data = list(self.collection.find({}, {'_id': 0}).sort("index", 1))
            if data: 
                self.chain = data
            else: 
                self.create_genesis_block() # Agar database khali hai toh naya block banao
        except: 
            self.create_genesis_block()

    def create_genesis_block(self):
        # Pehla block jiska proof 100 aur pichla hash '0' hota hai
        if not self.chain: 
            self.create_block(proof=100, previous_hash='0')

    def create_block(self, proof, previous_hash):
        # 0.5 badhane ka logic: 3 se shuru aur har 10k blocks pe +0.5
        # Formula: Initial(3) + (Blocks / 10000) * 0.5
        self.difficulty = 3 + (len(self.chain) // 10000) * 0.5
        
        # Baaki ka block data wahi rahega
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
        # ... hashing aur saving code ...
        
        # ... baaki ka hashing aur saving code wahi rahega ...
        
        # Block ki saari jaankari ko mix karke uska ek unique ID (hash) banana
        encoded_block = json.dumps(block, sort_keys=True).encode()
        block['hash'] = hashlib.sha256(encoded_block).hexdigest()
        
        # Pending list khali karke chain mein naya block jodna
        self.pending_transactions = []
        self.chain.append(block)
        
        # Database mein save karna taaki refresh pe balance na ude
        try:
            self.collection.delete_many({}) # Purana temporary data saaf karna
            if self.chain: 
                self.collection.insert_many(self.chain)
        except: 
            pass
        return block

    def get_balance(self, address):
        bal = 0
        for block in self.chain:
            for tx in block.get('transactions', []):
                # Agar address bhejne wala hai toh balance kam karo
                if tx['sender'] == address: 
                    bal -= float(tx['amount'])
                # Agar address paane wala hai toh balance badhao
                if tx['receiver'] == address: 
                    bal += float(tx['amount'])
        return round(bal, 2)

    def add_transaction(self, sender, receiver, amount, signature):
        # Nayi transaction ki kacchi entry banana
        naya_tx = {
            'sender': sender,
            'receiver': receiver,
            'amount': float(amount),
            'timestamp': time.time(),
            'signature': signature
        }
        # Is entry ko pending list mein daal dena
        self.pending_transactions.append(naya_tx)
        return True, "Success"

    def mine_block(self, miner_address, proof):
        pichla_hash = self.chain[-1]['hash'] if self.chain else '0'
        
        # Supply check yahan bhi (Double protection)
        current_supply = sum(b.get('reward', 0) for b in self.chain)
        if current_supply + 40 <= 51000000:
            self.add_transaction("KAAL_NETWORK", miner_address, 40, "NETWORK_SIG")
        
        return self.create_block(proof, pichla_hash)                
