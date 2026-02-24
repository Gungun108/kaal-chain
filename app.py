from flask import Flask, jsonify, render_template, request
from blockchain import KaalChain
import os

# Flask app initialization
app = Flask(__name__)
kaal_chain = KaalChain()

@app.route('/')
def index():
    """Main Wallet Page load karne ke liye"""
    return render_template('index.html')

@app.route('/get_info', methods=['POST'])
def get_info():
    """Wallet ka balance aur last block ka proof lene ke liye"""
    data = request.get_json()
    addr = data.get('address')
    if not addr:
        return jsonify({'error': 'Address missing'}), 400
    
    return jsonify({
        'balance': kaal_chain.get_balance(addr),
        'last_proof': kaal_chain.chain[-1]['proof'] if kaal_chain.chain else 100,
        'difficulty': kaal_chain.difficulty
    }), 200

@app.route('/get_stats')
def get_stats():
    """Poore blockchain ki summary aur supply check karne ke liye"""
    return jsonify({
        'blocks': len(kaal_chain.chain),
        'chain': kaal_chain.chain[::-1], # Latest blocks upar dikhane ke liye
        'total_supply': sum(b.get('reward', 0) for b in kaal_chain.chain)
    })

@app.route('/add_tx', methods=['POST'])
def add_tx():
    """Naya transaction add karne ke liye"""
    data = request.get_json()
    # Transaction logic (sender, receiver, amount, signature)
    success, msg = kaal_chain.add_transaction(
        data.get('sender'), 
        data.get('receiver'), 
        data.get('amount'), 
        data.get('signature')
    )
    return jsonify({'message': 'Success' if success else f'Failed: {msg}'}), 200 if success else 400

@app.route('/mine', methods=['POST'])
def mine():
    """Mining success hone par naya block banane ke liye"""
    v = request.get_json()
    addr = v.get('address')
    proof = v.get('proof')
    
    if addr and proof:
        kaal_chain.mine_block(addr, proof)
        return jsonify({'message': 'Mined!'}), 200
    return jsonify({'message': 'Invalid data'}), 400

if __name__ == '__main__':
    # Render ke environment variable se port uthana
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
