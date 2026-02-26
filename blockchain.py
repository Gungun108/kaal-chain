import hashlib
import json
import time
import os
import urllib.parse
import requests
from pymongo import MongoClient
from urllib.parse import urlparse

class KaalChain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.difficulty = 3 
        self.nodes = set() # P2P Peers ki list
        # Line 15: self.nodes = set() # P2P Peers ki list
        self.nodes.add("kaal-chain.onrender.com") # ✅ Ye line jodd de
        
        # Bitcoin Logic Constants
        self.TARGET_BLOCK_TIME = 420  
        self.HALVING_INTERVAL = 300000  
        self.INITIAL_REWARD = 40      
        
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
            db_data = list(self.collection.find({}, {'_id': 0}).sort("index", 1))
            if db_data and len(db_data) > 0:
                self.chain = db_data
                if 'difficulty' in self.chain[-1]:
                    self.difficulty = self.chain[-1]['difficulty']
                else:
                    self.difficulty = 3 + (len(self.chain) // 10000) * 0.5
            elif not self.chain:
                self.create_genesis_block()
        except Exception as e:
            print(f"Sync Error: {e}")

    # ✅ P2P: Naye Node ko register karna
    def register_node(self, address):
    """Naye node ko list mein joddna aur duplicate hatana"""
        if "onrender.com" in address:
        self.nodes.add("kaal-chain.onrender.com")
        else:
        # IP ya URL format sahi karke save karna
        parsed_url = urlparse(address)
        node_address = parsed_url.netloc if parsed_url.netloc else parsed_url.path
            if node_address:
               self.nodes.add(node_address)

    # ✅ P2P: Consensus Algorithm (Sabse lambi chain jeetegi)
    def resolve_conflicts(self):
        """Duniya bhar ke nodes se chain check karke sabse lambi wali apnana"""
        neighbours = self.nodes
        new_chain = None
        max_length = len(self.chain)

        for node in neighbours:
            try:
                response = requests.get(f'http://{node}/get_stats', timeout=5)
                if response.status_code == 200:
                    length = response.json()['blocks']
                    chain = response.json()['chain'][::-1] # Reverse kyunki stats desc deta hai

                    if length > max_length and self.is_chain_valid(chain):
                        max_length = length
                        new_chain = chain
            except:
                continue

        if new_chain:
            self.chain = new_chain
            # Optional: Yahan DB update logic daal sakte ho
            return True
        return False

    # ✅ P2P: Chain validity check karna
    def is_chain_valid(self, chain):
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != last_block['hash']:
                return False
            if not block['hash'].startswith('0' * int(block.get('difficulty', 3))):
                return False
            last_block = block
            current_index += 1
        return True

    def create_genesis_block(self):
        if not self.chain: 
            self.create_block(proof=100, previous_hash='0')

    def create_block(self, proof, previous_hash):
        if len(self.chain) > 0:
            last_block = self.chain[-1]
            time_taken = time.time() - last_block['timestamp']
            
            if time_taken < self.TARGET_BLOCK_TIME:
                self.difficulty += 0.05
            else:
                self.difficulty = max(3, self.difficulty - 0.05)
        
        halvings = len(self.chain) // self.HALVING_INTERVAL
        block_reward = self.INITIAL_REWARD / (2 ** halvings)
        
        current_supply = sum(b.get('reward', 0) for b in self.chain)
        max_supply = 51000000
        if current_supply + block_reward > max_supply:
            block_reward = 0
        
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': list(self.pending_transactions),
            'proof': proof,
            'previous_hash': previous_hash,
            'reward': block_reward,
            'difficulty': self.difficulty 
        }
        
        encoded_block = json.dumps(block, sort_keys=True).encode()
        block['hash'] = hashlib.sha256(encoded_block).hexdigest()
        
        self.pending_transactions = []
        self.chain.append(block)
        
        try:
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
        for tx in self.pending_transactions:
            if tx['signature'] == signature:
                return False, "Double transaction!"

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
        self.load_chain_from_db()
        # Mining se pehle ek baar network sync karlo
        self.resolve_conflicts()
        
        pichla_hash = self.chain[-1]['hash'] if self.chain else '0'
        
        halvings = len(self.chain) // self.HALVING_INTERVAL
        current_reward = self.INITIAL_REWARD / (2 ** halvings)
        
        self.add_transaction("KAAL_NETWORK", miner_address, current_reward, "NETWORK_SIG")
        
        return self.create_block(proof, pichla_hash)



