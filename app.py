"""
ScholarNest — Notes Sharing Platform
Developed by: Simran Rani
Run: python app.py
"""

import os, json, uuid, sqlite3, hashlib, urllib.parse, urllib.request
from datetime import datetime
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, send_from_directory, g, abort)

# ─────────────────────────────────────────────────────────────────────────────
#  App Setup
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'scholarnest-simranrani-2024-secret')

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, 'instance', 'scholarnest.db')
UPLOAD_DIR  = os.path.join(BASE_DIR, 'uploads')
MAX_MB      = 20
ALLOWED_EXT = {'pdf'}
YOUTUBE_API = os.environ.get('YOUTUBE_API_KEY', '')  # Optional: set for real results

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
#  Database Schema
# ─────────────────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    email       TEXT    UNIQUE NOT NULL,
    password    TEXT    NOT NULL,
    role        TEXT    DEFAULT 'student',
    avatar_color TEXT   DEFAULT '#6C63FF',
    bio         TEXT,
    created     TEXT    DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS notes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    title        TEXT    NOT NULL,
    subject      TEXT    NOT NULL,
    description  TEXT,
    tags         TEXT    DEFAULT '[]',
    filename     TEXT    NOT NULL,
    original_name TEXT   NOT NULL,
    file_size    INTEGER DEFAULT 0,
    downloads    INTEGER DEFAULT 0,
    views        INTEGER DEFAULT 0,
    share_token  TEXT    UNIQUE,
    created      TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS bookmarks (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    note_id INTEGER NOT NULL,
    created TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, note_id)
);
CREATE TABLE IF NOT EXISTS recent_views (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    note_id INTEGER NOT NULL,
    viewed  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS notifications (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT    NOT NULL,
    icon    TEXT    DEFAULT 'bell',
    read    INTEGER DEFAULT 0,
    created TEXT    DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS subjects (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    icon TEXT DEFAULT '📚'
);
"""

SEED_SUBJECTS = [
    ('Mathematics', '📐'), ('Physics', '⚡'), ('Chemistry', '🧪'),
    ('Computer Science', '💻'), ('Data Structures', '🌳'), ('DBMS', '🗄️'),
    ('Operating Systems', '🖥️'), ('Networks', '🌐'), ('Web Development', '🕸️'),
    ('Machine Learning', '🤖'), ('English', '📝'), ('Economics', '📊'),
]

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    cur = conn.cursor()
    # Seed subjects
    for name, icon in SEED_SUBJECTS:
        cur.execute("INSERT OR IGNORE INTO subjects(name,icon) VALUES(?,?)", (name, icon))
    # Admin account
    cur.execute("SELECT id FROM users WHERE email='admin@scholarnest.app'")
    if not cur.fetchone():
        pw = generate_password_hash('admin@123')
        cur.execute("INSERT INTO users(name,email,password,role,avatar_color) VALUES(?,?,?,?,?)",
                    ('Admin', 'admin@scholarnest.app', pw, 'admin', '#FF6B6B'))
    # Demo student
    cur.execute("SELECT id FROM users WHERE email='simran@scholarnest.app'")
    if not cur.fetchone():
        pw = generate_password_hash('simran@123')
        cur.execute("INSERT INTO users(name,email,password,role,avatar_color,bio) VALUES(?,?,?,?,?,?)",
                    ('Simran Rani', 'simran@scholarnest.app', pw, 'student',
                     '#6C63FF', 'CS Student | Note enthusiast 📚'))
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers & Decorators
# ─────────────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def deco(*a, **kw):
        if 'user_id' not in session:
            flash('Please sign in to continue.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*a, **kw)
    return deco

def admin_required(f):
    @wraps(f)
    def deco(*a, **kw):
        if not session.get('is_admin'):
            flash('Admin access required.', 'danger')
            return redirect(url_for('home'))
        return f(*a, **kw)
    return deco

def allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def get_user():
    if 'user_id' in session:
        return get_db().execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    return None

def notif(uid, msg, icon='bell'):
    db = get_db()
    db.execute("INSERT INTO notifications(user_id,message,icon) VALUES(?,?,?)", (uid, msg, icon))
    db.commit()

def human_size(n):
    for u in ('B','KB','MB'):
        if n < 1024: return f"{n:.0f} {u}"
        n /= 1024
    return f"{n:.1f} GB"

def time_ago(dt_str):
    try:
        dt = datetime.strptime(dt_str[:19], '%Y-%m-%d %H:%M:%S')
        diff = datetime.now() - dt
        s = int(diff.total_seconds())
        if s < 60: return 'just now'
        if s < 3600: return f"{s//60}m ago"
        if s < 86400: return f"{s//3600}h ago"
        if s < 604800: return f"{s//86400}d ago"
        return dt.strftime('%b %d')
    except:
        return dt_str[:10]

app.jinja_env.filters['human_size'] = human_size
app.jinja_env.filters['time_ago'] = time_ago

@app.context_processor
def inject_globals():
    user = get_user()
    nc = 0
    subjects = []
    if user:
        db = get_db()
        nc = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND read=0",
                        (user['id'],)).fetchone()[0]
        subjects = db.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    elif 'user_id' not in session:
        db = get_db()
        subjects = db.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    return dict(current_user=user, notif_count=nc, all_subjects=subjects,
                app_name="ScholarNest", developer="Simran Rani")

# ─────────────────────────────────────────────────────────────────────────────
#  Public Routes
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/')
def home():
    db = get_db()
    featured = db.execute(
        "SELECT n.*,u.name as author,u.avatar_color FROM notes n "
        "JOIN users u ON n.user_id=u.id ORDER BY n.downloads DESC LIMIT 6").fetchall()
    recent = db.execute(
        "SELECT n.*,u.name as author,u.avatar_color FROM notes n "
        "JOIN users u ON n.user_id=u.id ORDER BY n.created DESC LIMIT 6").fetchall()
    subjects = db.execute(
        "SELECT s.*, COUNT(n.id) as note_count FROM subjects s "
        "LEFT JOIN notes n ON n.subject=s.name GROUP BY s.name ORDER BY note_count DESC LIMIT 8").fetchall()
    stats = {
        'notes':   db.execute("SELECT COUNT(*) FROM notes").fetchone()[0],
        'users':   db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'dl':      db.execute("SELECT SUM(downloads) FROM notes").fetchone()[0] or 0,
        'subjects':db.execute("SELECT COUNT(DISTINCT subject) FROM notes").fetchone()[0],
    }
    return render_template('home.html', featured=featured, recent=recent,
                           subjects=subjects, stats=stats)

@app.route('/explore')
def explore():
    db  = get_db()
    q   = request.args.get('q', '').strip()
    sub = request.args.get('subject', '')
    srt = request.args.get('sort', 'newest')
    pg  = max(1, int(request.args.get('page', 1)))
    per = 12
    off = (pg - 1) * per

    sql = "SELECT n.*,u.name as author,u.avatar_color FROM notes n JOIN users u ON n.user_id=u.id WHERE 1=1"
    params = []
    if q:
        sql += " AND (n.title LIKE ? OR n.description LIKE ? OR n.tags LIKE ? OR n.subject LIKE ?)"
        params += [f'%{q}%'] * 4
    if sub:
        sql += " AND n.subject=?"
        params.append(sub)

    order = {'newest':'n.created DESC','popular':'n.downloads DESC','az':'n.title ASC'}.get(srt,'n.created DESC')
    sql += f" ORDER BY {order}"

    total = db.execute(f"SELECT COUNT(*) FROM ({sql})", params).fetchone()[0]
    notes = db.execute(sql + f" LIMIT {per} OFFSET {off}", params).fetchall()
    subjects = db.execute("SELECT * FROM subjects ORDER BY name").fetchall()

    bm_ids = []
    if 'user_id' in session:
        bm_ids = [r[0] for r in db.execute("SELECT note_id FROM bookmarks WHERE user_id=?",
                                            (session['user_id'],)).fetchall()]

    pages = (total + per - 1) // per
    return render_template('explore.html', notes=notes, subjects=subjects,
                           q=q, subject=sub, sort=srt,
                           page=pg, pages=pages, total=total, bm_ids=bm_ids)

@app.route('/note/<int:nid>')
def note_detail(nid):
    db = get_db()
    note = db.execute(
        "SELECT n.*,u.name as author,u.avatar_color,u.bio FROM notes n "
        "JOIN users u ON n.user_id=u.id WHERE n.id=?", (nid,)).fetchone()
    if not note: abort(404)

    # Track view
    db.execute("UPDATE notes SET views=views+1 WHERE id=?", (nid,))
    if 'user_id' in session:
        db.execute("DELETE FROM recent_views WHERE user_id=? AND note_id=?",
                   (session['user_id'], nid))
        db.execute("INSERT INTO recent_views(user_id,note_id) VALUES(?,?)",
                   (session['user_id'], nid))
    db.commit()

    related = db.execute(
        "SELECT n.*,u.name as author FROM notes n JOIN users u ON n.user_id=u.id "
        "WHERE n.subject=? AND n.id!=? ORDER BY n.downloads DESC LIMIT 4",
        (note['subject'], nid)).fetchall()
    tags = json.loads(note['tags']) if note['tags'] else []
    bookmarked = False
    if 'user_id' in session:
        bookmarked = bool(db.execute("SELECT id FROM bookmarks WHERE user_id=? AND note_id=?",
                                     (session['user_id'], nid)).fetchone())
    share_url = request.host_url.rstrip('/') + url_for('note_by_token', token=note['share_token'])
    return render_template('note_detail.html', note=note, tags=tags,
                           related=related, bookmarked=bookmarked, share_url=share_url)

@app.route('/share/<token>')
def note_by_token(token):
    db = get_db()
    note = db.execute("SELECT id FROM notes WHERE share_token=?", (token,)).fetchone()
    if not note: abort(404)
    return redirect(url_for('note_detail', nid=note['id']))

@app.route('/download/<int:nid>')
@login_required
def download(nid):
    db = get_db()
    note = db.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()
    if not note: abort(404)
    db.execute("UPDATE notes SET downloads=downloads+1 WHERE id=?", (nid,))
    db.commit()
    return send_from_directory(UPLOAD_DIR, note['filename'],
                               as_attachment=True, download_name=note['original_name'])

@app.route('/view/<int:nid>')
@login_required
def view_pdf(nid):
    db = get_db()
    note = db.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()
    if not note: abort(404)
    return send_from_directory(UPLOAD_DIR, note['filename'])

# ─────────────────────────────────────────────────────────────────────────────
#  Auth Routes
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        pw    = request.form.get('password','')
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user['password'], pw):
            session.update({'user_id': user['id'], 'user_name': user['name'],
                            'is_admin': user['role'] == 'admin'})
            notif(user['id'], f"Welcome back, {user['name']}! 👋", 'log-in')
            flash(f"Welcome back, {user['name']}!", 'success')
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name  = request.form.get('name','').strip()
        email = request.form.get('email','').strip().lower()
        pw    = request.form.get('password','')
        pw2   = request.form.get('password2','')
        if not all([name, email, pw]):
            flash('All fields required.', 'danger')
        elif len(pw) < 6:
            flash('Password must be at least 6 characters.', 'danger')
        elif pw != pw2:
            flash('Passwords do not match.', 'danger')
        else:
            db = get_db()
            if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
                flash('Email already registered.', 'danger')
            else:
                colors = ['#6C63FF','#FF6584','#43AA8B','#F9C74F','#4CC9F0','#F77F00']
                color = colors[hash(email) % len(colors)]
                hpw = generate_password_hash(pw)
                db.execute("INSERT INTO users(name,email,password,avatar_color) VALUES(?,?,?,?)",
                           (name, email, hpw, color))
                db.commit()
                user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                session.update({'user_id': user['id'], 'user_name': user['name'], 'is_admin': False})
                notif(user['id'], f"Welcome to ScholarNest, {name}! 🎉 Start uploading notes.", 'star')
                flash(f'Account created! Welcome, {name}!', 'success')
                return redirect(url_for('dashboard'))
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out. See you soon!', 'info')
    return redirect(url_for('home'))

# ─────────────────────────────────────────────────────────────────────────────
#  Dashboard Routes
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    db  = get_db()
    uid = session['user_id']
    my_notes = db.execute(
        "SELECT * FROM notes WHERE user_id=? ORDER BY created DESC", (uid,)).fetchall()
    bookmarks = db.execute(
        "SELECT n.*,u.name as author FROM notes n JOIN users u ON n.user_id=u.id "
        "JOIN bookmarks b ON b.note_id=n.id WHERE b.user_id=? ORDER BY b.created DESC LIMIT 6",
        (uid,)).fetchall()
    recent = db.execute(
        "SELECT n.*,u.name as author FROM notes n JOIN users u ON n.user_id=u.id "
        "JOIN recent_views rv ON rv.note_id=n.id WHERE rv.user_id=? "
        "GROUP BY n.id ORDER BY rv.viewed DESC LIMIT 6", (uid,)).fetchall()
    notifs = db.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created DESC LIMIT 8", (uid,)).fetchall()
    db.execute("UPDATE notifications SET read=1 WHERE user_id=?", (uid,))
    db.commit()
    total_dl = sum(n['downloads'] for n in my_notes)
    total_views = sum(n['views'] for n in my_notes)
    return render_template('dashboard.html', my_notes=my_notes, bookmarks=bookmarks,
                           recent=recent, notifs=notifs, total_dl=total_dl,
                           total_views=total_views)

@app.route('/upload', methods=['GET','POST'])
@login_required
def upload():
    db = get_db()
    subjects = db.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    if request.method == 'POST':
        title   = request.form.get('title','').strip()
        subject = request.form.get('subject','').strip()
        desc    = request.form.get('description','').strip()
        tags    = request.form.get('tags','').strip()
        file    = request.files.get('file')

        if not all([title, subject, file]):
            flash('Title, subject and file are required.', 'danger')
            return render_template('upload.html', subjects=subjects)
        if not allowed(file.filename):
            flash('Only PDF files are allowed.', 'danger')
            return render_template('upload.html', subjects=subjects)

        # Size check
        file.seek(0, 2); size = file.tell(); file.seek(0)
        if size > MAX_MB * 1024 * 1024:
            flash(f'File exceeds {MAX_MB}MB limit.', 'danger')
            return render_template('upload.html', subjects=subjects)

        ext      = 'pdf'
        fname    = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, fname)
        file.save(filepath)
        tags_json = json.dumps([t.strip() for t in tags.split(',') if t.strip()])
        token = uuid.uuid4().hex[:12]

        db.execute("""INSERT INTO notes(user_id,title,subject,description,tags,
                      filename,original_name,file_size,share_token)
                      VALUES(?,?,?,?,?,?,?,?,?)""",
                   (session['user_id'], title, subject, desc, tags_json,
                    fname, secure_filename(file.filename), size, token))
        db.commit()
        notif(session['user_id'], f'Your note "{title}" was published! 📄', 'upload')
        flash('Note uploaded and published!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('upload.html', subjects=subjects)

@app.route('/note/delete/<int:nid>', methods=['POST'])
@login_required
def delete_note(nid):
    db = get_db()
    note = db.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()
    if not note: abort(404)
    if note['user_id'] != session['user_id'] and not session.get('is_admin'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    fp = os.path.join(UPLOAD_DIR, note['filename'])
    if os.path.exists(fp): os.remove(fp)
    db.execute("DELETE FROM bookmarks WHERE note_id=?", (nid,))
    db.execute("DELETE FROM recent_views WHERE note_id=?", (nid,))
    db.execute("DELETE FROM notes WHERE id=?", (nid,))
    db.commit()
    flash('Note deleted.', 'info')
    return redirect(url_for('dashboard') if not session.get('is_admin') else url_for('admin'))

@app.route('/bookmark/<int:nid>', methods=['POST'])
@login_required
def toggle_bookmark(nid):
    db = get_db()
    uid = session['user_id']
    bm = db.execute("SELECT id FROM bookmarks WHERE user_id=? AND note_id=?", (uid, nid)).fetchone()
    if bm:
        db.execute("DELETE FROM bookmarks WHERE user_id=? AND note_id=?", (uid, nid))
        saved = False
    else:
        db.execute("INSERT INTO bookmarks(user_id,note_id) VALUES(?,?)", (uid, nid))
        saved = True
    db.commit()
    return jsonify({'saved': saved})

# ─────────────────────────────────────────────────────────────────────────────
#  AI & API Routes
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/ai-answer', methods=['POST'])
@login_required
def ai_answer():
    """Simple AI Q&A using Anthropic API or fallback."""
    data = request.get_json()
    question = (data or {}).get('question', '').strip()
    if not question:
        return jsonify({'error': 'No question provided'}), 400

    # Try Anthropic API
    try:
        import urllib.request, json
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 400,
            "messages": [{"role": "user", "content":
                f"You are an academic tutor. Answer this question clearly and concisely for a college student: {question}"}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type": "application/json",
                     "anthropic-version": "2023-06-01"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            answer = result['content'][0]['text']
            return jsonify({'answer': answer, 'source': 'ai'})
    except:
        pass

    # Smart fallback with subject-aware canned responses
    q_lower = question.lower()
    if any(w in q_lower for w in ['what is','define','definition of','explain']):
        topic = question.split('is')[-1].strip().split('of')[-1].strip().rstrip('?')
        answer = (f"**{topic.title()}** is a fundamental concept in academic studies. "
                  f"To understand it deeply, consider reviewing your course notes and textbook chapters on this topic. "
                  f"Key aspects typically include: core definitions, practical applications, and related theories.")
    elif any(w in q_lower for w in ['how to','how does','how can']):
        answer = ("Great question! Here's a step-by-step approach:\n\n"
                  "1. **Understand the fundamentals** — Review basic concepts first\n"
                  "2. **Break it down** — Divide the problem into smaller parts\n"
                  "3. **Apply concepts** — Use formulas or methods systematically\n"
                  "4. **Verify your answer** — Check with examples or edge cases\n\n"
                  "Search for related notes on ScholarNest for detailed examples!")
    elif any(w in q_lower for w in ['difference between','compare','vs']):
        answer = ("When comparing concepts, focus on:\n\n"
                  "• **Definition** — What each term means individually\n"
                  "• **Key properties** — How they behave or function\n"
                  "• **Use cases** — When to use each one\n"
                  "• **Advantages/Disadvantages** — Trade-offs\n\n"
                  "Check the subject notes on ScholarNest for detailed comparisons!")
    else:
        answer = ("That's an interesting academic question! Here are some study strategies:\n\n"
                  "📖 **Review** relevant chapters and lecture notes\n"
                  "🔍 **Search** ScholarNest for notes on this topic\n"
                  "💡 **Practice** with past exam questions\n"
                  "👥 **Discuss** with classmates for different perspectives\n\n"
                  "Upload your notes to help others too!")
    return jsonify({'answer': answer, 'source': 'fallback'})

@app.route('/api/youtube', methods=['POST'])
@login_required
def youtube_search():
    """YouTube video recommendations for a query."""
    data = request.get_json()
    query = (data or {}).get('query', '').strip()
    if not query:
        return jsonify({'videos': []})

    if YOUTUBE_API:
        try:
            encoded = urllib.parse.quote(query + ' lecture tutorial')
            url = (f"https://www.googleapis.com/youtube/v3/search"
                   f"?part=snippet&q={encoded}&type=video"
                   f"&maxResults=4&key={YOUTUBE_API}")
            with urllib.request.urlopen(url, timeout=8) as r:
                result = json.loads(r.read())
            videos = []
            for item in result.get('items', []):
                vid_id = item['id']['videoId']
                snip   = item['snippet']
                videos.append({'id': vid_id, 'title': snip['title'],
                               'channel': snip['channelTitle'],
                               'thumb': snip['thumbnails']['medium']['url'],
                               'url': f"https://youtu.be/{vid_id}"})
            return jsonify({'videos': videos, 'source': 'api'})
        except:
            pass

    # Deterministic mock results based on query
    topics = [
        ('Introduction to ' + query, 'AcademicTube', 'dQw4w9WgXcQ'),
        (query + ' — Full Course', 'EduLearn', 'jNQXAC9IVRw'),
        ('Master ' + query + ' in 1 Hour', 'TechGuru', 'kJQP7kiw5Fk'),
        (query + ' Explained Simply', 'StudyHive', 'OPf0YbXqDm0'),
    ]
    videos = [{'id': vid, 'title': title, 'channel': ch,
               'thumb': f"https://img.youtube.com/vi/{vid}/mqdefault.jpg",
               'url': f"https://youtu.be/{vid}"}
              for title, ch, vid in topics]
    return jsonify({'videos': videos, 'source': 'mock'})

@app.route('/api/search-suggest')
def search_suggest():
    q = request.args.get('q', '').strip()
    if len(q) < 2: return jsonify([])
    db = get_db()
    rows = db.execute(
        "SELECT title FROM notes WHERE title LIKE ? LIMIT 6", (f'%{q}%',)).fetchall()
    return jsonify([r[0] for r in rows])

# ─────────────────────────────────────────────────────────────────────────────
#  Admin Routes
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/admin')
@login_required
@admin_required
def admin():
    db = get_db()
    users = db.execute(
        "SELECT u.*,(SELECT COUNT(*) FROM notes WHERE user_id=u.id) as nc FROM users u ORDER BY u.created DESC").fetchall()
    notes = db.execute(
        "SELECT n.*,u.name as author FROM notes n JOIN users u ON n.user_id=u.id ORDER BY n.created DESC").fetchall()
    subjects = db.execute("SELECT * FROM subjects ORDER BY name").fetchall()
    stats = {
        'users':    db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'notes':    db.execute("SELECT COUNT(*) FROM notes").fetchone()[0],
        'dl':       db.execute("SELECT SUM(downloads) FROM notes").fetchone()[0] or 0,
        'bookmarks':db.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0],
    }
    return render_template('admin.html', users=users, notes=notes,
                           subjects=subjects, stats=stats)

@app.route('/admin/delete-user/<int:uid>', methods=['POST'])
@login_required
@admin_required
def admin_del_user(uid):
    if uid == session['user_id']:
        flash('Cannot delete your own account.', 'danger')
        return redirect(url_for('admin'))
    db = get_db()
    notes = db.execute("SELECT filename FROM notes WHERE user_id=?", (uid,)).fetchall()
    for n in notes:
        fp = os.path.join(UPLOAD_DIR, n['filename'])
        if os.path.exists(fp): os.remove(fp)
    for tbl in ['bookmarks','recent_views','notifications','notes']:
        db.execute(f"DELETE FROM {tbl} WHERE user_id=?", (uid,))
    db.execute("DELETE FROM users WHERE id=?", (uid,))
    db.commit()
    flash('User removed.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/add-subject', methods=['POST'])
@login_required
@admin_required
def admin_add_subject():
    name = request.form.get('name','').strip()
    icon = request.form.get('icon','📚').strip() or '📚'
    if name:
        db = get_db()
        db.execute("INSERT OR IGNORE INTO subjects(name,icon) VALUES(?,?)", (name, icon))
        db.commit()
        flash(f'Subject "{name}" added.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/delete-subject/<int:sid>', methods=['POST'])
@login_required
@admin_required
def admin_del_subject(sid):
    db = get_db()
    db.execute("DELETE FROM subjects WHERE id=?", (sid,))
    db.commit()
    flash('Subject removed.', 'info')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
