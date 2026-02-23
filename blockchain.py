<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>🔱 KAAL WALLET</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/elliptic/6.5.4/elliptic.min.js"></script>
    <style>
        :root { --kaal: #ff4500; --bg: #f8f9fa; --card: #ffffff; --border: #e0e0e0; }
        body { background: var(--bg); font-family: 'Segoe UI', sans-serif; margin: 0; padding: 15px; }
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 20px; padding: 25px; margin-bottom: 20px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        .bal-text { font-size: 48px; font-weight: 900; color: var(--kaal); margin: 10px 0; }
        .addr-box { font-size: 11px; color: #008000; background: #eaffea; padding: 12px; border-radius: 12px; border: 1px dashed #4caf50; word-break: break-all; cursor: pointer; }
        .btn { background: var(--kaal); color: white; border: none; padding: 16px; border-radius: 14px; font-weight: bold; width: 100%; margin-top: 15px; cursor: pointer; }
        .btn-outline { background: white; color: #222; border: 2px solid var(--border); }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); z-index: 2000; overflow-y: auto; }
        .history-item { display: flex; justify-content: space-between; padding: 14px; background: #fafafa; border-radius: 12px; margin-bottom: 10px; border-left: 4px solid var(--kaal); }
    </style>
</head>
<body>
    <div class="card">
        <h2 style="color:var(--kaal); margin:0;">🔱 KAAL WALLET</h2>
        <div id="bal" class="bal-text">0.00</div>
        <div class="addr-box" id="addrDisp" onclick="copyText()">Loading...</div>
        <button class="btn" id="mineBtn" onclick="toggleMining()">⚡ START MINING</button>
        <button class="btn btn-outline" onclick="openModal('sendModal')">📤 SEND COINS</button>
        <button class="btn btn-outline" onclick="openModal('recModal')">📥 RECEIVE COINS</button>
    </div>

    <div class="card">
        <h4 style="text-align:left;">📜 Activity</h4>
        <div id="historyList" style="font-size: 13px;">Syncing...</div>
    </div>

    <div id="sendModal" class="modal">
        <div class="card" style="width:85%; margin:40px auto;">
            <h3>Send Funds</h3>
            <div id="reader"></div>
            <button class="btn btn-outline" onclick="startScan()">📸 Scan QR</button>
            <input type="text" id="to" placeholder="Receiver Address" style="width:90%; padding:10px; margin-top:10px;">
            <input type="number" id="amt" placeholder="Amount" style="width:90%; padding:10px; margin-top:10px;">
            <button class="btn" onclick="sendTx()">Confirm</button>
            <button class="btn btn-outline" onclick="closeModal('sendModal')">Cancel</button>
        </div>
    </div>

    <div id="recModal" class="modal">
        <div class="card" style="width:85%; margin:40px auto;">
            <h3>Receive</h3>
            <div id="qrcode" style="background:white; padding:10px; display:inline-block;"></div>
            <p id="recAddr" style="font-size:10px; word-break:break-all;"></p>
            <button class="btn btn-outline" onclick="closeModal('recModal')">Close</button>
        </div>
    </div>

    <script>
        const ec = new (elliptic.ec)('secp256k1');
        let mining = false, pub, priv, html5QrCode;

        function openModal(id) { document.getElementById(id).style.display = 'block'; }
        function closeModal(id) { document.getElementById(id).style.display = 'none'; if(html5QrCode) html5QrCode.stop(); }

        async function init() {
            pub = localStorage.getItem('kaal_pub');
            priv = localStorage.getItem('kaal_priv');
            if (!pub) {
                const key = ec.genKeyPair();
                priv = key.getPrivate('hex');
                pub = "KAAL" + ec.hash().update(key.getPublic('hex', true)).digest('hex').substring(0, 40).toUpperCase();
                localStorage.setItem('kaal_pub', pub); localStorage.setItem('kaal_priv', priv);
            }
            document.getElementById('addrDisp').innerText = pub;
            document.getElementById('recAddr').innerText = pub;
            new QRCode(document.getElementById("qrcode"), { text: pub, width: 160, height: 160 });
            sync(); setInterval(sync, 10000);
        }

        async function sync() {
            try {
                const info = await fetch('/get_info', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({address: pub}) }).then(r => r.json());
                document.getElementById('bal').innerText = info.balance.toFixed(2);
                window.last_proof = info.last_proof || 100;
                window.diff = info.difficulty || 2;

                const stats = await fetch('/get_stats').then(r => r.json());
                let html = '';
                stats.chain.forEach(b => b.transactions.forEach(tx => {
                    if (tx.sender === pub || tx.receiver === pub) {
                        let isIN = tx.receiver === pub;
                        html += `<div class="history-item">
                            <div><b>${tx.sender === "KAAL_NETWORK" ? "⚡ Reward" : "Transfer"}</b></div>
                            <div style="color:${isIN ? 'green' : 'red'}">${isIN ? '+' : '-'}${tx.amount}</div>
                        </div>`;
                    }
                }));
                document.getElementById('historyList').innerHTML = html || 'No activity yet.';
            } catch(e) {}
        }

        async function toggleMining() {
            mining = !mining;
            document.getElementById('mineBtn').innerText = mining ? "🛑 STOP" : "⚡ START";
            if(mining) mineLoop();
        }

        async function mineLoop() {
            let n = Math.floor(Math.random() * 10000);
            while(mining) {
                n++;
                if(n % 500 === 0) await new Promise(r => setTimeout(r, 50));
                const msg = window.last_proof + "" + n;
                const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(msg));
                const hex = Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2,'0')).join('');
                if(hex.startsWith('0'.repeat(window.diff))) {
                    await fetch('/mine', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({address: pub, proof: n}) });
                    sync(); break;
                }
            }
        }

        async function startScan() {
            html5QrCode = new Html5Qrcode("reader");
            html5QrCode.start({ facingMode: "environment" }, { fps: 10, qrbox: 250 }, (text) => {
                document.getElementById('to').value = text;
                html5QrCode.stop();
            });
        }

        async function sendTx() {
            const to = document.getElementById('to').value, amt = document.getElementById('amt').value;
            const key = ec.keyFromPrivate(priv), msg = pub + to + amt, sig = key.sign(msg);
            const signature = sig.r.toString(16).padStart(64, '0') + sig.s.toString(16).padStart(64, '0');
            const res = await fetch('/add_tx', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({sender: pub, receiver: to, amount: amt, signature: signature}) }).then(r => r.json());
            alert(res.message); if(res.message === "Success") closeModal('sendModal'); sync();
        }

        function copyText() { navigator.clipboard.writeText(pub); alert("Copied!"); }
        window.onload = init;
    </script>
</body>
</html>
