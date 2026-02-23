from flask import Flask, jsonify, render_template, request
from blockchain import KaalChain
import os

app = Flask(__name__)
kaal_chain = KaalChain()

@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/explorer')
def explorer(): 
    return render_template('explorer.html')

@app.route('/get_info', methods=['POST'])
def get_info():
    data = request.get_json()
    addr = data.get('address')
    return jsonify({
        'balance': kaal_chain.get_balance(addr),
        'last_proof': kaal_chain.chain[-1]['proof'] if kaal_chain.chain else 100,
        'difficulty': kaal_chain.difficulty,
        'peers': list(kaal_chain.nodes)
    }), 200

@app.route('/get_stats')
def get_stats():
    return jsonify({
        'blocks': len(kaal_chain.chain),
        'chain': kaal_chain.chain[::-1],
        'total_supply': sum(b.get('reward', 0) for b in kaal_chain.chain)
    })

# --- EK HI BAAR RAKHNA HAI ISKO ---
@app.route('/mine', methods=['POST'])
def mine():
    v = request.get_json()
    kaal_chain.mine_block(v.get('address'), v.get('proof'))
    return jsonify({'message': 'Mined!'}), 200

@app.route('/add_tx', methods=['POST'])
def add_transaction():
    values = request.get_json()
    tx_data = values.get('tx', values)
    
    success, msg = kaal_chain.add_transaction(
        sender=tx_data.get('sender'),
        receiver=tx_data.get('receiver'),
        amount=tx_data.get('amount'),
        signature=tx_data.get('signature')
    )

    if success:
        return jsonify({'message': 'Success: Transaction added to pool!'}), 200
    else:
        return jsonify({'message': f'Failed: {msg}'}), 400

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)