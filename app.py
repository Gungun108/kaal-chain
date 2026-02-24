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
    
    # Balance aur mining ke liye zaruri data wapas bhejna
    return jsonify({
        'balance': kaal_chain.get_balance(pata), # Naya balance
        'last_proof': kaal_chain.chain[-1]['proof'] if kaal_chain.chain else 100,
        'difficulty': kaal_chain.difficulty
    }), 200

@app.route('/get_stats')
def get_stats():
    try:
        kaal_chain.load_chain_from_db()
        clean_chain = []
        for block in kaal_chain.chain:
            # MongoDB ki '_id' field ko hata rahe hain taaki error na aaye
            b = block.copy()
            if '_id' in b: del b['_id']
            clean_chain.append(b)
            
        return jsonify({
            'blocks': len(clean_chain),
            'chain': clean_chain[::-1],
            'total_supply': sum(b.get('reward', 0) for b in clean_chain)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_tx', methods=['POST'])
def add_tx():
    # Nayi transaction ko kacchi list mein dalne ke liye
    data = request.get_json()
    success, msg = kaal_chain.add_transaction(data.get('sender'), data.get('receiver'), data.get('amount'), data.get('signature'))
    return jsonify({'message': msg}), 200 if success else 400

@app.route('/explorer')
def explorer():
    return render_template('explorer.html')

@app.route('/mine', methods=['POST'])
@app.route('/mine', methods=['POST'])
def mine():
    data = request.get_json()
    proof = data.get('proof')
    
    # Agar ye proof pichle block ka hi hai toh reject karo
    if kaal_chain.chain and proof == kaal_chain.chain[-1]['proof']:
        return jsonify({'message': 'Purana proof hai bhai'}), 400
        
    kaal_chain.mine_block(data.get('address'), proof)
    return jsonify({'message': 'Mined'}), 200
    return jsonify({'message': 'Data galat hai'}), 400

if __name__ == '__main__':
    # Render ke liye port set karna, varna local pe 5000 chalega
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

