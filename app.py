import os
import secrets
from flask import Flask, request, jsonify
from sqlalchemy import create_engine, text

app = Flask(__name__)

# --- CONFIGURATION ---
# DATABASE_URL must be the SAME as in the User repo
DB_URL = os.environ.get("DATABASE_URL")

# --- DATABASE CONNECTION ---
if DB_URL:
    if DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DB_URL)
else:
    engine = create_engine("sqlite:///temp_admin.db")

# --- DATABASE INITIALIZATION ---
def init_db():
    with engine.connect() as conn:
        # Admin creates the tables that User needs
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS licenses (
                key_code TEXT PRIMARY KEY,
                status TEXT DEFAULT 'unused',
                duration_hours INT DEFAULT 24
            );
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS file_registry (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                gdrive_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        conn.commit()

with app.app_context():
    init_db()

# --- ROUTES ---

@app.route('/')
def home():
    return "Admin Dashboard Ready."

@app.route('/admin')
def admin_ui():
    return """
    <html><body style="font-family:sans-serif; padding: 20px; max-width: 800px; margin: auto;">
        <h1>🛠️ Admin Dashboard</h1>
        
        <div style="background:#f4f4f4; padding:15px; border-radius:8px; margin-bottom:20px;">
            <h2>📂 Manage Files</h2>
            <input type="text" id="fname" placeholder="File Name (e.g., app_v1)" style="width: 200px; padding: 5px;">
            <input type="text" id="fid" placeholder="GDrive ID" style="width: 300px; padding: 5px;">
            <button onclick="addFile()" style="padding: 5px 15px;">Add File</button>
            <div id="fileList" style="margin-top:10px; font-family:monospace; font-size:12px;"></div>
        </div>

        <div style="background:#eef; padding:15px; border-radius:8px;">
            <h2>🔑 License Generator</h2>
            <input type="number" id="hr" value="24" style="padding: 10px;"> hours<br><br>
            <button onclick="genKey()" style="padding: 10px 20px;">Generate Key</button>
            <h2 id="res" style="color: green; font-family: monospace;"></h2>
        </div>

        <script>
            loadFiles();
            async function loadFiles() {
                const res = await fetch('/admin/get_files');
                const data = await res.json();
                const list = data.files;
                let html = '<strong>Registered Files:</strong><ul>';
                list.forEach(f => { html += `<li><b>${f.name}</b>: ${f.gdrive_id}</li>`; });
                html += '</ul>';
                document.getElementById('fileList').innerHTML = html;
            }
            async function addFile() {
                const name = document.getElementById('fname').value;
                const id = document.getElementById('fid').value;
                if(!name || !id) return alert("Fill both fields");
                await fetch('/admin/add_file', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: name, gdrive_id: id}) });
                document.getElementById('fname').value = ''; document.getElementById('fid').value = '';
                loadFiles();
            }
            async function genKey() {
                const res = await fetch('/admin/create', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({duration: parseInt(document.getElementById('hr').value)}) });
                const d = await res.json();
                document.getElementById('res').innerText = d.key;
            }
        </script>
    </body></html>
    """

@app.route('/admin/get_files', methods=['GET'])
def get_files():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name, gdrive_id FROM file_registry ORDER BY id DESC")).fetchall()
        files = [{"name": r[0], "gdrive_id": r[1]} for r in rows]
        return jsonify({"files": files})

@app.route('/admin/add_file', methods=['POST'])
def add_file():
    data = request.json
    try:
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO file_registry (name, gdrive_id) VALUES (:n, :g)"), {"n": data.get('name'), "g": data.get('gdrive_id')})
            conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/admin/create', methods=['POST'])
def create_key():
    data = request.json or {}
    key = secrets.token_hex(8)
    duration = data.get('duration', 24)
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO licenses (key_code, duration_hours) VALUES (:k, :d)"), {"k": key, "d": duration})
        conn.commit()
    return jsonify({"key": key, "duration": duration})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
