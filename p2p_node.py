import socket
import threading
import json
from blockchain import KaalChain # Teri purani file

class KaalP2PNode:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.chain = KaalChain()
        self.peers = set() # Saare jude huye doston ki list

    def start_node(self):
        # Doosre miners ke liye rasta kholna (Listening)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.host, self.port))
        server.listen(5)
        print(f"📡 KAAL Node LIVE on {self.host}:{self.port}")
        
        while True:
            conn, addr = server.accept()
            # Har naye connection ke liye alag thread
            threading.Thread(target=self.handle_miner, args=(conn, addr)).start()

    def handle_miner(self, conn, addr):
        # Jab koi doosra miner data bheje (Block ya Tx)
        data = conn.recv(1024*1024).decode()
        if data:
            msg = json.loads(data)
            if msg['type'] == 'NEW_BLOCK':
                print(f"📦 Received Block from {addr}")
                # Block ko validate karke add karne ka logic
                self.chain.add_external_block(msg['block'])
        conn.close()