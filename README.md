# 📚 ScholarNest — Notes Sharing Platform

> **Developed by: Simran Rani**  
> *"This system improves collaboration among students and creates a centralized learning resource platform."*

---

## ✨ Overview

ScholarNest is a full-stack web application designed for college students to upload, discover, share, and download study notes. Built with a modern glassmorphism UI, it features an AI-powered study assistant, YouTube video recommendations, real-time search, and a complete admin panel.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install flask werkzeug
```

### 2. Run the App
```bash
python app.py
```

### 3. Open in Browser
```
http://localhost:5000
```

---

## 🔐 Demo Accounts

| Role    | Email                        | Password     |
|---------|------------------------------|--------------|
| Admin   | admin@scholarnest.app        | admin@123    |
| Student | simran@scholarnest.app       | simran@123   |

---

## 📁 Project Structure

```
scholarnest/
├── app.py                    # Main Flask backend (all routes, DB, helpers)
├── requirements.txt          # Python dependencies (flask, werkzeug)
├── README.md                 # This file
│
├── instance/
│   └── scholarnest.db        # SQLite database (auto-created on first run)
│
├── uploads/                  # Uploaded PDF files (auto-created)
│
├── templates/
│   ├── base.html             # Base layout: navbar, theme, alerts, footer
│   ├── home.html             # Landing page: hero, stats, featured notes
│   ├── explore.html          # Search & filter all notes
│   ├── note_detail.html      # Note view: PDF preview, share, AI assistant
│   ├── dashboard.html        # User dashboard: notes, bookmarks, AI, notifs
│   ├── upload.html           # Upload PDF form
│   ├── login.html            # Sign in page
│   ├── signup.html           # Register page
│   └── admin.html            # Admin panel: users, notes, subjects
│
└── static/                   # (CSS/JS embedded in templates for portability)
```

---

## 🗄️ Database Schema

```sql
users        (id, name, email, password, role, avatar_color, bio, created)
notes        (id, user_id, title, subject, description, tags,
              filename, original_name, file_size, downloads, views,
              share_token, created)
bookmarks    (id, user_id, note_id, created)
recent_views (id, user_id, note_id, viewed)
notifications(id, user_id, message, icon, read, created)
subjects     (id, name, icon)
```

---

## ✅ Feature Checklist

### Authentication
- [x] Signup / Login / Logout
- [x] Password hashing (PBKDF2-SHA256 via Werkzeug)
- [x] Session management
- [x] Role-based access: Student & Admin

### Notes Management
- [x] Upload PDF notes (max 20MB)
- [x] Title, Subject, Description, Tags
- [x] Secure server-side file storage with UUID filenames
- [x] Card-based browse layout
- [x] In-browser PDF viewer (iframe)
- [x] One-click download + download counter
- [x] View counter
- [x] Delete notes (owner or admin)

### Search & Discovery
- [x] Full-text search (title, description, tags, subject)
- [x] Filter by subject (sidebar)
- [x] Sort: Newest / Most Popular / A–Z
- [x] Pagination (12 per page)
- [x] Live search suggestions (autocomplete)
- [x] Related notes on detail page

### Sharing
- [x] Unique shareable token per note
- [x] Share via WhatsApp, Telegram, Email
- [x] Copy link button

### User Dashboard
- [x] Stats: uploads, downloads, views
- [x] My Notes table with delete
- [x] Bookmarks / Saved notes
- [x] Recently viewed history
- [x] Notification feed
- [x] AI Study Assistant tab
- [x] YouTube Video Finder

### AI Features
- [x] AI Question Assistant (Claude API with intelligent fallback)
- [x] YouTube video recommendations (API or mock)
- [x] Smart subject-aware responses

### Admin Panel
- [x] View all users (with note counts)
- [x] Delete users (and all their data/files)
- [x] View & delete all notes
- [x] Manage subjects (add/remove)
- [x] Platform statistics

### UI/UX
- [x] Glassmorphism dark/light design
- [x] Dark/Light mode toggle (persists)
- [x] Responsive mobile layout
- [x] Animated page transitions
- [x] Smooth hover effects on cards
- [x] Password strength meter
- [x] Drag & drop file upload
- [x] Upload progress bar
- [x] Auto-dismissing toast notifications
- [x] Gradient text & brand accents

---

## 🔒 Security

- Passwords hashed with PBKDF2-SHA256 (never stored plain)
- File type validation: PDF only
- Filenames sanitized with `secure_filename`
- UUID-based stored filenames (original name preserved for download)
- File size enforced (20MB max)
- `@login_required` decorator on all protected routes
- `@admin_required` decorator on admin routes
- Admin cannot delete their own account

---

## 🌐 Environment Variables

| Variable        | Default                          | Description               |
|-----------------|----------------------------------|---------------------------|
| SECRET_KEY      | `scholarnest-simranrani-2024-...`| Flask session secret key  |
| YOUTUBE_API_KEY | *(empty)*                        | YouTube Data API v3 key   |

Set before running:
```bash
export SECRET_KEY="your-super-secret-key"
export YOUTUBE_API_KEY="your-youtube-api-key"  # optional
python app.py
```

---

## 🚀 Deploy to Render

```bash
# Install gunicorn
pip install gunicorn
echo "gunicorn" >> requirements.txt

# Procfile
echo "web: gunicorn app:app --bind 0.0.0.0:\$PORT" > Procfile

# Push to GitHub, connect Render, set SECRET_KEY env var
```

---

## 🎨 Design Choices

- **Font**: Syne (display/headings) + Nunito (body) — distinctive, academic feel
- **Theme**: Glassmorphism with deep navy background, purple+pink gradient accents
- **Cards**: Hover lift with gradient top border reveal animation
- **Color system**: CSS variables for seamless dark/light theming

---

## 👤 Developer

**Simran Rani**  
Full-Stack Web Developer & CS Student  
*ScholarNest — Built with Flask, SQLite, HTML/CSS/JS*

---

© 2024 ScholarNest by Simran Rani · All rights reserved
