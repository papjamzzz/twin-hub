import os
import sqlite3
import json
import time
import hashlib
import random
from flask import Flask, render_template, request, redirect, url_for, jsonify, session

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'twin-hub-secret-2025-papito')

DB_PATH               = os.path.join(os.path.dirname(__file__), 'data', 'hub.db')
JOKES_CACHE_PATH      = os.path.join(os.path.dirname(__file__), 'data', 'jokes_cache.json')
CHALLENGES_CACHE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'challenges_cache.json')
CHALLENGES_PATH       = os.path.join(os.path.dirname(__file__), 'challenges.json')

TWIN1_NAME     = os.getenv('TWIN1_NAME', 'Lumi')
TWIN2_NAME     = os.getenv('TWIN2_NAME', 'Sloany')
ADMIN_PASSWORD = os.getenv('DAD_PASSWORD', 'papa')
LUMI_SPOTIFY   = os.getenv('LUMI_SPOTIFY_PLAYLIST',  '2ujmymS9QJEMwHmcNXH2hn')
SLOANY_SPOTIFY = os.getenv('SLOANY_SPOTIFY_PLAYLIST', '37i9dQZF1DX9tPFwDMOaN1')

JOKE_CACHE_TTL  = 900   # 15 minutes
NOTE_CATEGORIES = ['School', 'People', 'Family', 'Me']

CONTACTS = [
    {'name': 'Mama',        'number': '6177553846', 'emoji': '💕'},
    {'name': 'Papi',        'number': '4138345062', 'emoji': '⚡'},
    {'name': 'Auntie Jennie', 'number': '6039233640', 'emoji': '✨'},
    {'name': 'Uncle Lysha', 'number': '4133256381', 'emoji': '🎸'},
]

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


def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                author    TEXT NOT NULL,
                content   TEXT NOT NULL,
                category  TEXT NOT NULL DEFAULT 'School',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try:
            conn.execute("ALTER TABLE notes ADD COLUMN category TEXT NOT NULL DEFAULT 'School'")
        except Exception:
            pass
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                who              TEXT PRIMARY KEY,
                me_password_hash TEXT,
                me_hint          TEXT
            )
        ''')
        conn.commit()


def get_jokes():
    os.makedirs(os.path.dirname(JOKES_CACHE_PATH), exist_ok=True)
    if os.path.exists(JOKES_CACHE_PATH):
        with open(JOKES_CACHE_PATH) as f:
            cached = json.load(f)
        if time.time() - cached.get('timestamp', 0) < JOKE_CACHE_TTL:
            return cached['jokes']

    fallback = [
        "Why did the math book look so sad? Because it had too many problems.",
        "What do you call a fake noodle? An impasta.",
        "Why don't scientists trust atoms? Because they make up everything.",
        "What do you call cheese that isn't yours? Nacho cheese.",
        "Why did the scarecrow win an award? He was outstanding in his field.",
        "What do you call a sleeping dinosaur? A dino-snore.",
        "Why can't you give Elsa a balloon? She'll let it go.",
        "What do you call a fish without eyes? A fsh.",
    ]

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=400,
            messages=[{
                'role': 'user',
                'content': (
                    'Generate 8 funny age-appropriate jokes for 6th-grade girls (age 11-12). '
                    'Mix puns, school humor, pop culture, absurd humor. '
                    'Each joke 1-2 sentences max. '
                    'ONLY return a JSON array of strings, no numbering, no extra text.'
                )
            }]
        )
        raw = msg.content[0].text.strip()
        start, end = raw.index('['), raw.rindex(']') + 1
        jokes = json.loads(raw[start:end])
        if not isinstance(jokes, list) or len(jokes) == 0:
            raise ValueError('bad jokes response')
    except Exception:
        jokes = fallback

    with open(JOKES_CACHE_PATH, 'w') as f:
        json.dump({'jokes': jokes, 'timestamp': time.time()}, f)
    return jokes


def get_challenges():
    os.makedirs(os.path.dirname(CHALLENGES_CACHE_PATH), exist_ok=True)

    if os.path.exists(CHALLENGES_CACHE_PATH):
        with open(CHALLENGES_CACHE_PATH) as f:
            cached = json.load(f)
        if time.time() - cached.get('timestamp', 0) < 86400:
            return cached['challenges']

    with open(CHALLENGES_PATH) as f:
        static_pool = json.load(f)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=600,
            messages=[{
                'role': 'user',
                'content': (
                    'Generate 30 fun, creative challenges for two 6th-grade girls (age 11-12). '
                    'Mix singing, dancing, drawing, writing, trivia, dares, games, impressions, '
                    'storytelling, TikTok-style challenges. '
                    'Keep every challenge short (under 12 words), action-oriented, age-appropriate. '
                    'Return ONLY a JSON array of strings, no numbering, no extra text.'
                )
            }]
        )
        raw = msg.content[0].text.strip()
        start, end = raw.index('['), raw.rindex(']') + 1
        titles = json.loads(raw[start:end])
        max_id = max(c['id'] for c in static_pool)
        extra = [{'id': max_id + i + 1, 'title': t} for i, t in enumerate(titles[:30])]
        combined = static_pool + extra
    except Exception:
        combined = static_pool

    random.shuffle(combined)

    with open(CHALLENGES_CACHE_PATH, 'w') as f:
        json.dump({'challenges': combined, 'timestamp': time.time()}, f)
    return combined


def _pedal_ctx(who):
    cfg    = TWIN_CONFIG[who]
    author = TWIN1_NAME if who == 'lumi' else TWIN2_NAME
    spotify = LUMI_SPOTIFY if who == 'lumi' else SLOANY_SPOTIFY
    return dict(
        cfg=cfg,
        who=who,
        author=author,
        challenges=get_challenges(),
        jokes=get_jokes(),
        contacts=CONTACTS,
        spotify_id=spotify,
    )


# ── Main routes ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    with get_db() as conn:
        notes_1 = conn.execute(
            "SELECT * FROM notes WHERE author=? AND category!='Me' ORDER BY timestamp DESC LIMIT 20",
            (TWIN1_NAME,)
        ).fetchall()
        notes_2 = conn.execute(
            "SELECT * FROM notes WHERE author=? AND category!='Me' ORDER BY timestamp DESC LIMIT 20",
            (TWIN2_NAME,)
        ).fetchall()
    return render_template('index.html',
        twin1=TWIN1_NAME, twin2=TWIN2_NAME,
        notes_1=notes_1, notes_2=notes_2,
        jokes=get_jokes(),
        challenges=get_challenges()
    )


@app.route('/lumi')
def lumi():
    return render_template('pedal.html', **_pedal_ctx('lumi'))


@app.route('/sloany')
def sloany():
    return render_template('pedal.html', **_pedal_ctx('sloany'))


# ── Legacy routes (index.html compat) ─────────────────────────────────────────

@app.route('/post', methods=['POST'])
def post_note():
    author  = request.form.get('author', '').strip()
    content = request.form.get('content', '').strip()
    back    = request.form.get('back', '/')
    if author in [TWIN1_NAME, TWIN2_NAME] and content:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO notes (author, content, category) VALUES (?, ?, 'School')",
                (author, content)
            )
            conn.commit()
    return redirect(back)


@app.route('/clear', methods=['POST'])
def clear_notes():
    back = request.form.get('back', '/')
    if request.form.get('password', '') == ADMIN_PASSWORD:
        with get_db() as conn:
            conn.execute('DELETE FROM notes')
            conn.commit()
    return redirect(back)


# ── Notes API ──────────────────────────────────────────────────────────────────

@app.route('/api/notes/<who>/<category>')
def api_get_notes(who, category):
    if who not in ('lumi', 'sloany'):
        return jsonify({'error': 'unknown user'}), 400
    if category == 'Me':
        if not session.get(f'{who}_me_unlocked'):
            return jsonify({'error': 'locked'}), 403
    author = TWIN1_NAME if who == 'lumi' else TWIN2_NAME
    with get_db() as conn:
        notes = conn.execute(
            'SELECT id, content, timestamp FROM notes WHERE author=? AND category=? ORDER BY timestamp DESC LIMIT 100',
            (author, category)
        ).fetchall()
    return jsonify([{
        'id':        n['id'],
        'content':   n['content'],
        'timestamp': n['timestamp'][:16] if n['timestamp'] else ''
    } for n in notes])


@app.route('/api/notes/<who>', methods=['POST'])
def api_post_note(who):
    if who not in ('lumi', 'sloany'):
        return jsonify({'error': 'unknown user'}), 400
    data     = request.get_json(force=True) or {}
    content  = (data.get('content') or '').strip()
    category = data.get('category', 'School')
    if category not in NOTE_CATEGORIES:
        return jsonify({'error': 'bad category'}), 400
    if not content:
        return jsonify({'error': 'empty content'}), 400
    if category == 'Me':
        if not session.get(f'{who}_me_unlocked'):
            return jsonify({'error': 'locked'}), 403
    author = TWIN1_NAME if who == 'lumi' else TWIN2_NAME
    with get_db() as conn:
        cur = conn.execute(
            'INSERT INTO notes (author, content, category) VALUES (?, ?, ?)',
            (author, content, category)
        )
        conn.commit()
        note_id = cur.lastrowid
    return jsonify({'id': note_id, 'content': content, 'timestamp': 'just now'})


@app.route('/api/notes/<int:note_id>/delete', methods=['POST'])
def api_delete_note(note_id):
    data = request.get_json(force=True) or {}
    who  = data.get('who', '')
    if who not in ('lumi', 'sloany'):
        return jsonify({'error': 'unknown user'}), 400
    author = TWIN1_NAME if who == 'lumi' else TWIN2_NAME
    with get_db() as conn:
        conn.execute('DELETE FROM notes WHERE id=? AND author=?', (note_id, author))
        conn.commit()
    return jsonify({'ok': True})


# ── Me journal API ─────────────────────────────────────────────────────────────

@app.route('/api/me/status/<who>')
def api_me_status(who):
    if who not in ('lumi', 'sloany'):
        return jsonify({'error': 'unknown user'}), 400
    with get_db() as conn:
        row = conn.execute('SELECT me_password_hash FROM user_settings WHERE who=?', (who,)).fetchone()
    has_pw  = bool(row and row['me_password_hash'])
    unlocked = bool(session.get(f'{who}_me_unlocked'))
    return jsonify({'has_password': has_pw, 'unlocked': unlocked})


@app.route('/api/me/check-password/<who>', methods=['POST'])
def api_me_check_password(who):
    if who not in ('lumi', 'sloany'):
        return jsonify({'error': 'unknown user'}), 400
    data = request.get_json(force=True) or {}
    pw   = data.get('password', '')
    with get_db() as conn:
        row = conn.execute('SELECT me_password_hash, me_hint FROM user_settings WHERE who=?', (who,)).fetchone()
    if row and row['me_password_hash'] == hash_pw(pw):
        session[f'{who}_me_unlocked'] = True
        return jsonify({'ok': True})
    hint = row['me_hint'] if row else ''
    return jsonify({'ok': False, 'hint': hint or ''}), 401


@app.route('/api/me/set-password/<who>', methods=['POST'])
def api_me_set_password(who):
    if who not in ('lumi', 'sloany'):
        return jsonify({'error': 'unknown user'}), 400
    data = request.get_json(force=True) or {}
    pw   = data.get('password', '')
    hint = data.get('hint', '')
    if not pw:
        return jsonify({'error': 'password required'}), 400
    with get_db() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO user_settings (who, me_password_hash, me_hint) VALUES (?, ?, ?)',
            (who, hash_pw(pw), hint)
        )
        conn.commit()
    session[f'{who}_me_unlocked'] = True
    return jsonify({'ok': True})


@app.route('/api/me/lock/<who>', methods=['POST'])
def api_me_lock(who):
    if who not in ('lumi', 'sloany'):
        return jsonify({'error': 'unknown user'}), 400
    session.pop(f'{who}_me_unlocked', None)
    return jsonify({'ok': True})


# ── Jokes API ──────────────────────────────────────────────────────────────────

@app.route('/api/jokes')
def api_jokes():
    return jsonify(get_jokes())


# ── Admin ──────────────────────────────────────────────────────────────────────

@app.route('/admin')
def admin():
    if request.args.get('key') != ADMIN_PASSWORD:
        return '<h2 style="font-family:monospace;padding:2rem">403 — Access denied. Use /admin?key=yourpassword</h2>', 403
    with get_db() as conn:
        notes_lumi = conn.execute(
            "SELECT * FROM notes WHERE author=? AND category!='Me' ORDER BY timestamp DESC LIMIT 100",
            (TWIN1_NAME,)
        ).fetchall()
        notes_sloany = conn.execute(
            "SELECT * FROM notes WHERE author=? AND category!='Me' ORDER BY timestamp DESC LIMIT 100",
            (TWIN2_NAME,)
        ).fetchall()
        settings_lumi   = conn.execute('SELECT * FROM user_settings WHERE who=?', ('lumi',)).fetchone()
        settings_sloany = conn.execute('SELECT * FROM user_settings WHERE who=?', ('sloany',)).fetchone()
    return render_template('admin.html',
        notes_lumi=notes_lumi,
        notes_sloany=notes_sloany,
        settings={'lumi': settings_lumi, 'sloany': settings_sloany},
        twin1=TWIN1_NAME,
        twin2=TWIN2_NAME,
        admin_key=ADMIN_PASSWORD,
        contacts=CONTACTS,
        anthropic_key_set=bool(os.getenv('ANTHROPIC_API_KEY')),
    )


@app.route('/admin/reset-me-password/<who>', methods=['POST'])
def admin_reset_me_password(who):
    if request.form.get('admin_password') != ADMIN_PASSWORD:
        return 'Unauthorized', 403
    new_pw = request.form.get('new_password', '')
    hint   = request.form.get('hint', '')
    if who in ('lumi', 'sloany') and new_pw:
        with get_db() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO user_settings (who, me_password_hash, me_hint) VALUES (?, ?, ?)',
                (who, hash_pw(new_pw), hint)
            )
            conn.commit()
    return redirect(url_for('admin', key=ADMIN_PASSWORD))


@app.route('/admin/refresh-challenges', methods=['POST'])
def refresh_challenges():
    if os.path.exists(CHALLENGES_CACHE_PATH):
        os.remove(CHALLENGES_CACHE_PATH)
    return jsonify({'challenges': get_challenges()})


@app.route('/admin/refresh-jokes', methods=['POST'])
def refresh_jokes():
    if os.path.exists(JOKES_CACHE_PATH):
        os.remove(JOKES_CACHE_PATH)
    return jsonify({'jokes': get_jokes()})


@app.route('/visualizer')
def visualizer():
    return render_template('visualizer.html', twin1=TWIN1_NAME, twin2=TWIN2_NAME)


init_db()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5567))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') != 'production')
