import os
import sqlite3
import json
import time
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'hub.db')
DAILY_FACT_PATH = os.path.join(os.path.dirname(__file__), 'data', 'daily_fact.json')
CHALLENGES_PATH      = os.path.join(os.path.dirname(__file__), 'challenges.json')
CHALLENGES_CACHE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'challenges_cache.json')

TWIN1_NAME = os.getenv('TWIN1_NAME', 'Lumi')
TWIN2_NAME = os.getenv('TWIN2_NAME', 'Sloany')
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
                    'Give me one surprising, wild, or funny pop culture fact that a 12-year-old '
                    'middle schooler would find genuinely interesting — about a trending meme, '
                    'a popular video game, a viral moment, a celebrity, a movie, or social media. '
                    'Keep it current and age-appropriate. One sentence only, no intro, no quotes.'
                )
            }]
        )
        fact = msg.content[0].text.strip()
    except Exception:
        fact = (
            'Minecraft has sold over 300 million copies, making it the best-selling video game '
            'of all time — more than GTA V, Tetris, and Fortnite combined.'
        )

    with open(DAILY_FACT_PATH, 'w') as f:
        json.dump({'fact': fact, 'timestamp': time.time()}, f)


def get_challenges():
    os.makedirs(os.path.dirname(CHALLENGES_CACHE_PATH), exist_ok=True)

    if os.path.exists(CHALLENGES_CACHE_PATH):
        with open(CHALLENGES_CACHE_PATH) as f:
            cached = json.load(f)
        if time.time() - cached.get('timestamp', 0) < 86400:
            return cached['challenges']

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=600,
            messages=[{
                'role': 'user',
                'content': (
                    'Generate 20 fun, creative challenges for two 6th-grade girls (age 11-12). '
                    'Mix it up: singing, dancing, drawing, writing, trivia, dares, games, '
                    'impressions, storytelling, TikTok-style challenges — things tweens actually love. '
                    'Keep every challenge short (under 12 words), action-oriented, and age-appropriate. '
                    'Return ONLY a JSON array of strings, no numbering, no extra text. Example: '
                    '["Do your best Sabrina Carpenter impression", "Draw your dream bedroom in 60 seconds"]'
                )
            }]
        )
        raw = msg.content[0].text.strip()
        # parse just the array
        start, end = raw.index('['), raw.rindex(']') + 1
        titles = json.loads(raw[start:end])
        challenges = [{'id': i + 1, 'title': t} for i, t in enumerate(titles[:20])]
    except Exception:
        with open(CHALLENGES_PATH) as f:
            challenges = json.load(f)

    with open(CHALLENGES_CACHE_PATH, 'w') as f:
        json.dump({'challenges': challenges, 'timestamp': time.time()}, f)

    return challenges


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

    return render_template('index.html',
        twin1=TWIN1_NAME,
        twin2=TWIN2_NAME,
        notes_1=notes_1,
        notes_2=notes_2,
        fact=get_daily_fact(),
        challenges=get_challenges()
    )


TWIN_CONFIG = {
    'lumi': {
        'name': 'Lumi',
        'beats': 'Looms Beats',
        'p':  '#a78bfa',
        'p2': '#c084fc',
        'p3': '#7c3aed',
        'pg': 'rgba(167,139,250,0.28)',
        'pd': '#090614',
    },
    'sloany': {
        'name': 'Sloany',
        'beats': "Sloany's Beats",
        'p':  '#60a5fa',
        'p2': '#38bdf8',
        'p3': '#1d4ed8',
        'pg': 'rgba(96,165,250,0.28)',
        'pd': '#010b18',
    },
}


def _pedal_ctx(who):
    cfg = TWIN_CONFIG[who]
    author = TWIN1_NAME if who == 'lumi' else TWIN2_NAME
    with get_db() as conn:
        notes = conn.execute(
            'SELECT * FROM notes WHERE author = ? ORDER BY timestamp DESC LIMIT 30',
            (author,)
        ).fetchall()
    return dict(cfg=cfg, who=who, author=author, notes=notes,
                challenges=get_challenges(), fact=get_daily_fact())


@app.route('/lumi')
def lumi():
    return render_template('pedal.html', **_pedal_ctx('lumi'))


@app.route('/sloany')
def sloany():
    return render_template('pedal.html', **_pedal_ctx('sloany'))


@app.route('/post', methods=['POST'])
def post_note():
    author = request.form.get('author', '').strip()
    content = request.form.get('content', '').strip()
    back   = request.form.get('back', '/')
    if author in [TWIN1_NAME, TWIN2_NAME] and content:
        with get_db() as conn:
            conn.execute('INSERT INTO notes (author, content) VALUES (?, ?)', (author, content))
            conn.commit()
    return redirect(back)


@app.route('/clear', methods=['POST'])
def clear_notes():
    back = request.form.get('back', '/')
    if request.form.get('password', '') == DAD_PASSWORD:
        with get_db() as conn:
            conn.execute('DELETE FROM notes')
            conn.commit()
    return redirect(back)


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


@app.route('/admin/refresh-challenges', methods=['POST'])
def refresh_challenges():
    if os.path.exists(CHALLENGES_CACHE_PATH):
        os.remove(CHALLENGES_CACHE_PATH)
    return jsonify({'challenges': get_challenges()})


if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5567))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') != 'production')
