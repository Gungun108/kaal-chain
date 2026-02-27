from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit # ✅ Real-time sync
from blockchain import KaalChain 
import os
import requests

# Server ko shuru karna
app = Flask(__name__)

# ✅ WebSocket Setup
socketio = SocketIO(app, cors_allowed_origins="*")

# Blockchain instance banana aur socketio link karna
kaal_chain = KaalChain()
kaal_chain.socketio = socketio 

@app.route('/')
def index():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip and client_ip != "127.0.0.1":
        actual_ip = client_ip.split(',')[0].strip()
        kaal_chain.register_node(f"http://{actual_ip}:5000")
    return render_template('index.html')

# ✅ KAAL CORE: P2P Block Receiver Endpoint
@app.route('/add_block_p2p', methods=['POST'])
def add_block_p2p():
    block = request.get_json()
    if not block:
        return jsonify({"message": "Invalid block data"}), 400
    
    last_block = kaal_chain.chain[-1]
    if block['previous_hash'] == last_block['hash'] and \
       block['index'] == last_block['index'] + 1:
        
        if kaal_chain.hash_block(block) == block['hash']:
            kaal_chain.save_block_locally(block)
            kaal_chain.chain.append(block)
            kaal_chain.rebuild_utxo_set()
            
            socketio.emit('new_block', {'index': block['index'], 'hash': block['hash']}, broadcast=True)
            return jsonify({"message": "Block accepted via P2P"}), 201
            
    return jsonify({"message": "Block rejected"}), 400

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    data = request.get_json()
    nodes = data.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400
    for node in nodes:
        kaal_chain.register_node(node)
    
    return jsonify({
        'message': 'Naye nodes jodd diye gaye hain', 
        'total_nodes': list(kaal_chain.nodes)
    }), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = kaal_chain.resolve_conflicts()
    if replaced:
        socketio.emit('network_update', {'message': 'Chain Updated!'}, broadcast=True)
        return jsonify({
            'message': 'Chain update ho gayi (Lambi chain mili)', 
            'new_chain': kaal_chain.chain
        }), 200
    return jsonify({
        'message': 'Hamari chain hi sabse lambi aur sahi hai', 
        'chain': kaal_chain.chain
    }), 200

@app.route('/get_info', methods=['POST'])
def get_info():
    data = request.get_json()
    pata = data.get('address')
    if not pata:
        return jsonify({'error': 'Address gayab hai'}), 400
    
    if not kaal_chain.chain:
        kaal_chain.load_chain_from_local_db() 
    
    kaal_chain.rebuild_utxo_set() 
    
    return jsonify({
        'balance': kaal_chain.get_balance(pata),
        'last_proof': kaal_chain.chain[-1]['proof'] if kaal_chain.chain else 100,
        'difficulty': kaal_chain.difficulty
    }), 200

@app.route('/get_stats')
def get_stats():
    """✅ OPTIMIZED: Mobile Timeout Fix aur Pagination"""
    try:
        # Har baar heavy sync karne ki bajaye gossip ko fast rakho
        # taaki Render server timeout na ho jaye
        
        clean_chain = []
        # ✅ FIX: Explorer ke liye sirf aakhri 20 blocks bhejo (Pagination)
        display_limit = 20
        recent_blocks = kaal_chain.chain[-display_limit:] if len(kaal_chain.chain) > display_limit else kaal_chain.chain
        
        for block in recent_blocks:
            b = block.copy()
            if '_id' in b: del b['_id']
            clean_chain.append(b)
            
        return jsonify({
            'blocks': len(kaal_chain.chain),
            'chain': clean_chain[::-1],
            'total_supply': sum(b.get('reward', 0) for b in kaal_chain.chain),
            'nodes': list(kaal_chain.nodes),
            'difficulty': kaal_chain.difficulty,
            'halving_interval': kaal_chain.HALVING_INTERVAL
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_tx', methods=['POST'])
def add_tx():
    data = request.get_json()
    kaal_chain.rebuild_utxo_set()
    
    success, msg = kaal_chain.add_transaction(
        data.get('sender'), 
        data.get('receiver'), 
        data.get('amount'), 
        data.get('signature')
    )
    
    if success:
        socketio.emit('new_tx', {'sender': data.get('sender'), 'amount': data.get('amount')}, broadcast=True)
        
    return jsonify({'message': msg}), 200 if success else 400

@app.route('/explorer')
def explorer():
    return render_template('explorer.html')

@app.route('/mine', methods=['POST'])
def mine():
    data = request.get_json()
    pata = data.get('address')
    proof = data.get('proof')

    if not pata or not proof:
        return jsonify({'message': 'Data miss hai'}), 400

    block = kaal_chain.mine_block(pata, proof)
    kaal_chain.rebuild_utxo_set()
    
    socketio.emit('new_block', {'index': block['index'], 'miner': pata}, broadcast=True)
    
    # Mining ke waqt cloud/network sync background mein chalao
    kaal_chain.resolve_conflicts() 
    kaal_chain.sync_with_mongodb()

    return jsonify({
        'message': 'Mined Success & Network Synced', 
        'new_balance': kaal_chain.get_balance(pata)
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
