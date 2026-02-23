import hashlib
import json
import time
import os
import ecdsa
from pymongo import MongoClient

class KaalChain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.difficulty = 2 # Render par mining fast karne ke liye
        
        # MONGO_URI environment variable se aayega
        mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
        
        try:
            # 5 second ka timeout taaki Render atke nahi
            self.mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.db = self.mongo_client.kaal_db
            self.collection = self.db.ledger
            self.load_chain_from_db()
        except Exception as e:
            print(f"DB Error: {e}")
            self.create_genesis_block()

    def verify_transaction_signature(self, sender_pub_hex, signature_hex, message):
        if sender_pub_hex == "KAAL_NETWORK": return True
        try:
            pub_hex = sender_pub_hex.replace("KAAL", "")
            vk = ecdsa.VerifyingKey.from_string(bytes.fromhex(pub_hex), curve=ecdsa.SECP256k1)
            return vk.verify(bytes.fromhex(signature_hex), message.encode())
        except: return False

    def get_balance(self, address):
        bal = 0
        for block in self.chain:
            for tx in block.get('transactions', []):
                if tx['sender'] == address: bal -= float(tx['amount'])
                if tx['receiver'] == address: bal += float(tx['amount'])
        return round(bal, 2)

    def add_transaction(self, sender, receiver, amount, signature=None):
        if sender != "KAAL_NETWORK":
            if not signature: return False, "Signature missing!"
            msg = f"{sender}{receiver}{amount}"
            if not self.verify_transaction_signature(sender, signature, msg):
                return False, "Invalid Signature!"
            if self.get_balance(sender) < float(amount):
                return False, "Low balance!"

        self.pending_transactions.append({
            'sender': sender, 'receiver': receiver, 'amount': float(amount),
            'timestamp': time.time(), 'signature': signature
        })
        return True, "Success"

    def create_block(self, proof, previous_hash):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': self.pending_transactions,
            'proof': proof,
            'previous_hash': previous_hash,
            'reward': 51
        }
        block['hash'] = hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()
        self.pending_transactions = []
        self.chain.append(block)
        self.save_chain_to_db()
        return block

    def save_chain_to_db(self):
        try:
            self.collection.delete_many({})
            if self.chain: self.collection.insert_many(self.chain)
        except: pass

    def load_chain_from_db(self):
        try:
            data = list(self.collection.find({}, {'_id': 0}).sort("index", 1))
            if data: self.chain = data
            else: self.create_genesis_block()
        except: self.create_genesis_block()

    def create_genesis_block(self):
        if not self.chain: self.create_block(proof=100, previous_hash='0')

    def mine_block(self, miner_address, proof):
        last_hash = self.chain[-1]['hash'] if self.chain else '0'
        # Miner reward
        self.add_transaction("KAAL_NETWORK", miner_address, 51)
        return self.create_block(proof, last_hash)