# New Vision Academy – Turso (libSQL) Setup

This project is now configured to use **Turso** as the primary database.

## Why Turso?
- Serverless / edge-friendly (perfect for Vercel)
- SQLite-compatible (existing models & migrations work)
- Free tier generous, low latency in Asia regions

## Quick Setup

### 1. Install Turso CLI
```bash
curl -sSfL https://get.tur.so/install.sh | bash
```

### 2. Login & create database
```bash
turso auth login
turso db create newvisionacademy
turso db show --url newvisionacademy
turso db tokens create newvisionacademy
```

### 3. Set environment variables (Vercel + local `.env`)

```env
TURSO_DATABASE_URL=libsql://newvisionacademy-xxxxx.aws-ap-south-1.turso.io
TURSO_AUTH_TOKEN=eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9...
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Run locally
```bash
python app.py
```

On first run the app will:
- Create all tables
- Run lightweight schema migrations
- Seed default admin + school profile + content

### Vercel
Add the same two variables in **Vercel → Project → Settings → Environment Variables**:
- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`

Also keep `SECRET_KEY`, Cloudinary, and mail variables.

## Fallback
If `TURSO_DATABASE_URL` is not set, the app falls back to:
1. `DATABASE_URL` (Postgres / Neon) – legacy
2. Local `sqlite:///school.db` (development only)

## Notes
- All models use standard SQLAlchemy types → fully compatible with libSQL
- `ensure_schema()` uses `ALTER TABLE ... ADD COLUMN` which Turso supports
- No Postgres-specific features are used
