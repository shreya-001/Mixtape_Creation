# Youtube Mixtape Creation

## Deploy (Render)

This repo contains:
- **Backend API**: FastAPI (`backend/app/main.py`)
- **Frontend UI**: Streamlit (`frontend/streamlit_app.py`)

### Backend (FastAPI) Render settings
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/healthz`

**Required env vars**:
- `JWT_SECRET`: random secret used to sign login tokens (JWT)
- `TOKENS_ENCRYPTION_KEY`: Fernet key used to encrypt stored OAuth tokens

**Recommended env vars**:
- `CORS_ALLOW_ORIGINS`: comma-separated list of allowed browser origins for the Streamlit app (e.g. `https://your-streamlit.onrender.com`)
- `MIXTAPE_STORAGE_ROOT`: path for SQLite DB + uploads/artifacts (use a persistent disk if you want data to survive redeploys)

**OAuth URLs (set these for production)**:
- `GOOGLE_OAUTH_REDIRECT_URI`: e.g. `https://your-api.onrender.com/auth/google/callback`
- `YOUTUBE_OAUTH_REDIRECT_URI`: e.g. `https://your-api.onrender.com/youtube/oauth/callback`
- `STREAMLIT_REDIRECT_BASE`: e.g. `https://your-streamlit.onrender.com`

**Secret file**:
- Upload `client_secrets.json` as a Render Secret File and set:
  - `YOUTUBE_CLIENT_SECRETS=/etc/secrets/client_secrets.json`

### Frontend (Streamlit) Render settings
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `streamlit run frontend/streamlit_app.py --server.address 0.0.0.0 --server.port $PORT`

**Required env vars**:
- `API_BASE`: your backend URL (e.g. `https://your-api.onrender.com`)

