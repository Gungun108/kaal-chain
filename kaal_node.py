# Nayi file: kaal_node.py
import socket
import threading
import json
from blockchain import KaalChain

class KaalNode:
    def __init__(self, port):
        self.blockchain = KaalChain()
        self.peers = set()
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):
        # 1. Listening for other miners
        self.socket.bind(('0.0.0.0', self.port))
        self.socket.listen(5)
        threading.Thread(target=self.accept_connections).start()
        print(f"🔱 KAAL Node running on port {self.port}")

    def accept_connections(self):
        while True:
            conn, addr = self.socket.accept()
            threading.Thread(target=self.handle_peer, args=(conn, addr)).start()

    def handle_peer(self, conn, addr):
        # Jab koi naya block ya transaction aaye
        data = conn.recv(1024*1024).decode()
        if data:
            message = json.loads(data)
            if message['type'] == 'BLOCK':
                self.blockchain.add_block_from_network(message['data'])
            elif message['type'] == 'SYNC':
                conn.send(json.dumps(self.blockchain.chain).encode())
        conn.close()

    def broadcast(self, msg_type, data):
        """Saare jude huye peers ko message bhejna"""
        message = json.dumps({'type': msg_type, 'data': data})
        for peer in self.peers:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(peer)
                s.send(message.encode())
                s.close()
            except:
                pass # Peer offline hai