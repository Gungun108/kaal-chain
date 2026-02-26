from flask import Flask, jsonify, render_template, request
from blockchain import KaalChain # Blockchain file se dimag uthana
import os
import requests # Networking ke liye zaruri hai

# Server ko shuru karna aur blockchain ko loading par lagana
app = Flask(__name__)
kaal_chain = KaalChain()

@app.route('/')
def index():
    # ✅ Auto-Discovery: Jab koi page load kare, uska IP nodes mein register kar lo
    client_ip = request.remote_addr
    if client_ip and client_ip != "127.0.0.1":
        # Render ya Local dono ke liye registration logic
        kaal_chain.register_node(f"http://{client_ip}:5000")
    return render_template('index.html')

# ✅ Route: Doosre Miners/Nodes ko list mein joddna
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    data = request.get_json()
    nodes = data.get('nodes') # Example: ["192.168.1.5:5000"]
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400
    for node in nodes:
        kaal_chain.register_node(node)
    
    # Sabhi nodes ko ek doosre ki khabar dena (Gossip logic)
    return jsonify({
        'message': 'Naye nodes jodd diye gaye hain', 
        'total_nodes': list(kaal_chain.nodes)
    }), 201

# ✅ Route: Network se sabse lambi chain mangwana (Consensus)
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    # Sabse lambi aur valid chain ko apnana
    replaced = kaal_chain.resolve_conflicts()
    if replaced:
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
    
    kaal_chain.load_chain_from_db() 
    return jsonify({
        'balance': kaal_chain.get_balance(pata),
        'last_proof': kaal_chain.chain[-1]['proof'] if kaal_chain.chain else 100,
        'difficulty': kaal_chain.difficulty
    }), 200

@app.route('/get_stats')
def get_stats():
    try:
        kaal_chain.load_chain_from_db()
        clean_chain = []
        for block in kaal_chain.chain:
            b = block.copy()
            if '_id' in b: del b['_id']
            clean_chain.append(b)
            
        return jsonify({
            'blocks': len(clean_chain),
            'chain': clean_chain[::-1],
            'total_supply': sum(b.get('reward', 0) for b in clean_chain),
            'nodes': list(kaal_chain.nodes), # ✅ Wallet par Nodes count dikhane ke liye
            'difficulty': kaal_chain.difficulty,
            'halving_interval': kaal_chain.HALVING_INTERVAL # Explorer ki halving calculation ke liye
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_tx', methods=['POST'])
def add_tx():
    data = request.get_json()
    kaal_chain.load_chain_from_db() 
    success, msg = kaal_chain.add_transaction(
        data.get('sender'), 
        data.get('receiver'), 
        data.get('amount'), 
        data.get('signature')
    )
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

    # Block mine karo
    kaal_chain.mine_block(pata, proof)
    
    # ✅ P2P Sync: Mine karne ke baad network se check karo taaki koi fork na bane
    kaal_chain.resolve_conflicts() 
    
    kaal_chain.load_chain_from_db() 

    return jsonify({
        'message': 'Mined Success & Network Synced', 
        'new_balance': kaal_chain.get_balance(pata)
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # '0.0.0.0' taaki global network se connections mil sakein
    app.run(host='0.0.0.0', port=port)
