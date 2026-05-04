import os
import sqlite3
import json
import time
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'hub.db')
DAILY_FACT_PATH = os.path.join(os.path.dirname(__file__), 'data', 'daily_fact.json')
CHALLENGES_PATH = os.path.join(os.path.dirname(__file__), 'challenges.json')

TWIN1_NAME = os.getenv('TWIN1_NAME', 'Aria')
TWIN2_NAME = os.getenv('TWIN2_NAME', 'Zara')
DAD_PASSWORD = os.getenv('DAD_PASSWORD', 'dad')


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()


def get_daily_fact():
    os.makedirs(os.path.dirname(DAILY_FACT_PATH), exist_ok=True)

    if os.path.exists(DAILY_FACT_PATH):
        with open(DAILY_FACT_PATH) as f:
            cached = json.load(f)
        if time.time() - cached.get('timestamp', 0) < 86400:
            return cached['fact']

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=120,
            messages=[{
                'role': 'user',
                'content': (
                    'Give me one surprising, delightful fact about Hamilton the musical — '
                    'something even a superfan might not know. One sentence only, no intro, no quotes.'
                )
            }]
        )
        fact = msg.content[0].text.strip()
    except Exception:
        fact = (
            'Lin-Manuel Miranda wrote the first Hamilton song in 2008 while on vacation '
            'reading Ron Chernow\'s biography — seven years before it hit Broadway.'
        )

    with open(DAILY_FACT_PATH, 'w') as f:
        json.dump({'fact': fact, 'timestamp': time.time()}, f)

    return fact


@app.route('/')
def index():
    with get_db() as conn:
        notes_1 = conn.execute(
            'SELECT * FROM notes WHERE author = ? ORDER BY timestamp DESC LIMIT 20',
            (TWIN1_NAME,)
        ).fetchall()
        notes_2 = conn.execute(
            'SELECT * FROM notes WHERE author = ? ORDER BY timestamp DESC LIMIT 20',
            (TWIN2_NAME,)
        ).fetchall()

    fact = get_daily_fact()

    with open(CHALLENGES_PATH) as f:
        challenges = json.load(f)

    return render_template('index.html',
        twin1=TWIN1_NAME,
        twin2=TWIN2_NAME,
        notes_1=notes_1,
        notes_2=notes_2,
        fact=fact,
        challenges=challenges
    )


@app.route('/post', methods=['POST'])
def post_note():
    author = request.form.get('author', '').strip()
    content = request.form.get('content', '').strip()
    if author in [TWIN1_NAME, TWIN2_NAME] and content:
        with get_db() as conn:
            conn.execute('INSERT INTO notes (author, content) VALUES (?, ?)', (author, content))
            conn.commit()
    return redirect(url_for('index'))


@app.route('/clear', methods=['POST'])
def clear_notes():
    if request.form.get('password', '') == DAD_PASSWORD:
        with get_db() as conn:
            conn.execute('DELETE FROM notes')
            conn.commit()
    return redirect(url_for('index'))


@app.route('/visualizer')
def visualizer():
    return render_template('visualizer.html', twin1=TWIN1_NAME, twin2=TWIN2_NAME)


@app.route('/admin')
def admin():
    return render_template('admin.html', fact=get_daily_fact(), twin1=TWIN1_NAME, twin2=TWIN2_NAME)


@app.route('/admin/refresh-fact', methods=['POST'])
def refresh_fact():
    if os.path.exists(DAILY_FACT_PATH):
        os.remove(DAILY_FACT_PATH)
    return jsonify({'fact': get_daily_fact()})


if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5567))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') != 'production')
