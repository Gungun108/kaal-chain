from flask import Flask, jsonify, render_template, request
from blockchain import KaalChain # Blockchain file se dimag uthana
import os

# Server ko shuru karna aur blockchain ko loading par lagana
app = Flask(__name__)
kaal_chain = KaalChain()

@app.route('/')
def index():
    # Pehla page jo wallet kholte hi dikhega
    return render_template('index.html')

@app.route('/get_info', methods=['POST'])
def get_info():
    # Wallet se address mangwana
    data = request.get_json()
    pata = data.get('address')
    
    if not pata:
        return jsonify({'error': 'Address gayab hai'}), 400
    
    # Har refresh par balance ko fresh load karna zaruri hai
    kaal_chain.load_chain_from_db() 
    
    return jsonify({
        'balance': kaal_chain.get_balance(pata), # Naya balance
        'last_proof': kaal_chain.chain[-1]['proof'] if kaal_chain.chain else 100,
        'difficulty': kaal_chain.difficulty
    }), 200

@app.route('/get_stats')
def get_stats():
    try:
        # Har baar fresh data load karo
        kaal_chain.load_chain_from_db()
        
        clean_chain = []
        for block in kaal_chain.chain:
            b = block.copy()
            if '_id' in b: del b['_id']
            clean_chain.append(b)
            
        return jsonify({
            'blocks': len(clean_chain),
            'chain': clean_chain[::-1], # Naya block upar
            'total_supply': sum(b.get('reward', 0) for b in clean_chain)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_tx', methods=['POST'])
def add_tx():
    data = request.get_json()
    # Transaction add karne se pehle ek baar DB se sync kar lo
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
    
    # Mining ke turant baad balance fresh dikhane ke liye DB refresh zaruri hai
    # Par humne load_chain ko "safe" bana diya hai, toh ab 0 nahi hoga
    kaal_chain.load_chain_from_db() 

    return jsonify({'message': 'Mined Success', 'new_balance': kaal_chain.get_balance(pata)}), 200
        
    kaal_chain.mine_block(pata, proof)
    return jsonify({'message': 'Mined'}), 200

if __name__ == '__main__':
    # Render ke liye port set karna
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)



