from __future__ import annotations

import os
import time
import json
from typing import Any, Dict, List

import requests
import streamlit as st
import streamlit.components.v1 as components


def _get_api_base() -> str:
    # Prefer env var so we don't require secrets.toml to exist.
    env = os.getenv("API_BASE")
    if env:
        return env.rstrip("/")
    try:
        # st.secrets raises if there is no secrets file at all, so guard it.
        return str(st.secrets.get("API_BASE", "http://127.0.0.1:8000")).rstrip("/")
    except Exception:
        return "http://127.0.0.1:8000"


API_BASE = _get_api_base()


def _auth_headers() -> Dict[str, str]:
    token = st.session_state.get("auth_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def api_get(path: str) -> Dict[str, Any]:
    r = requests.get(f"{API_BASE}{path}", headers=_auth_headers(), timeout=60)
    r.raise_for_status()
    return r.json()


def api_post_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(f"{API_BASE}{path}", json=payload, headers=_auth_headers(), timeout=60)
    r.raise_for_status()
    return r.json()


def api_post_files(path: str, files: List[tuple]) -> Dict[str, Any]:
    r = requests.post(f"{API_BASE}{path}", files=files, headers=_auth_headers(), timeout=600)
    r.raise_for_status()
    return r.json()


st.set_page_config(page_title="Mixtape Automation", layout="wide")
st.title("Mixtape Automation")
st.caption("Create seamless mixtapes, optionally render a video, and upload to YouTube.")

# If redirected back from Google login or AI image upload with query params,
# capture values into session state.
def _consume_token_from_query() -> None:
    token: str | None = None
    bg_upload_id: str | None = None
    bg_filename: str | None = None

    try:
        qp = st.query_params  # type: ignore[attr-defined]
        token = qp.get("token")
        bg_upload_id = qp.get("bg_upload_id")
        bg_filename = qp.get("bg_filename")
    except Exception:
        qp = st.experimental_get_query_params()

        def _first(key: str) -> str | None:
            vals = qp.get(key, [])
            return vals[0] if vals else None

        token = _first("token")
        bg_upload_id = _first("bg_upload_id")
        bg_filename = _first("bg_filename")

    if token and not st.session_state.get("auth_token"):
        st.session_state["auth_token"] = token

    if bg_upload_id and bg_filename:
        upload_state = st.session_state.setdefault("uploads", {})
        upload_state["bg_image_upload_id"] = bg_upload_id
        upload_state["bg_filename"] = bg_filename

    # Clear query parameters after consuming any supported values.
    if any([token, bg_upload_id, bg_filename]):
        try:
            st.query_params.clear()  # type: ignore[attr-defined]
        except Exception:
            st.experimental_set_query_params()


_consume_token_from_query()

# -----------------
# Auth (passwordless)
# -----------------
st.session_state.setdefault("auth_token", None)

with st.sidebar:
    st.header("Login")
    if st.session_state.get("auth_token"):
        me = api_get("/auth/me")
        st.success(f"Logged in as {me['email']}")
        if st.button("Log out"):
            st.session_state["auth_token"] = None
            # Compatible rerun for new/old Streamlit versions.
            _rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
            if _rerun:
                _rerun()
    else:
        st.subheader("Sign in with Google")
        if st.button("Continue with Google"):
            try:
                resp = api_get("/auth/google/start")
                auth_url = resp["authorization_url"]
                # Auto-redirect the browser using a meta refresh, with a visible fallback link.
                st.markdown(
                    f"""
                    <meta http-equiv="refresh" content="0; url={auth_url}">
                    <p>Redirecting to Google... If you are not redirected automatically,
                    <a href="{auth_url}" target="_blank" rel="noopener noreferrer">continue to Google sign-in</a>.</p>
                    """,
                    unsafe_allow_html=True,
                )
                st.stop()
            except requests.HTTPError:
                # Show a friendly message instead of raw backend errors.
                st.error("Google sign-in failed. Please try again in a moment.")

    st.divider()
    st.header("Backend")
    st.caption("Connected to secure mixtape processing backend.")

    st.subheader("YouTube OAuth")
    if st.session_state.get("auth_token"):
        status = api_get("/youtube/oauth/status")
        st.write("Authorized:", status.get("authorized", False))
        if status.get("authorized", False):
            try:
                me = api_get("/youtube/me")
                # Only show the channel title to avoid exposing internal IDs.
                title = me.get("title") or "Unknown channel"
                st.caption(f"Connected channel: {title}")
            except Exception:
                st.caption("Connected, but could not fetch channel details.")
        if st.button("Connect YouTube account"):
            try:
                resp = api_post_json("/youtube/oauth/start", {})
                auth_url = resp["authorization_url"]
                # Auto-redirect to YouTube OAuth consent screen with a visible fallback link.
                st.markdown(
                    f"""
                    <meta http-equiv="refresh" content="0; url={auth_url}">
                    <p>Redirecting to Google for YouTube access... If you are not redirected automatically,
                    <a href="{auth_url}" target="_blank" rel="noopener noreferrer">continue to YouTube connect</a>.</p>
                    """,
                    unsafe_allow_html=True,
                )
                st.stop()
            except requests.HTTPError:
                st.error("Could not start YouTube connection. Please try again.")
    else:
        st.caption("Log in to connect YouTube.")

col1, col2 = st.columns(2, gap="large")

with col1:
    st.header("1) Choose tracks and artwork")
    if not st.session_state.get("auth_token"):
        st.info("Log in to upload tracks and start jobs.")
        st.stop()
    tracks = st.file_uploader(
        "Upload your music files",
        accept_multiple_files=True,
        type=["mp3", "wav", "flac", "m4a", "aac", "ogg"],
        help="Add two or more tracks to be mixed together.",
    )

    st.subheader("Background image")
    st.caption("Use AI to generate artwork, or upload your own image.")

    ai_tab, upload_tab = st.tabs(["Generate with AI", "Upload image"])

    # Limit AI generations per session to avoid accidental overuse.
    MAX_AI_IMAGE_TRIES = 5
    ai_state = st.session_state.setdefault("ai_image", {"tries": 0})

    with ai_tab:
        st.markdown("**Experimental:** AI-generated artwork is powered by a third-party service and may be rate limited. You can always switch to the **Upload image** tab.")
        prompt = st.text_input(
            "Describe the artwork you want",
            placeholder="e.g. Neon city skyline with DJ silhouette",
            key="ai_prompt",
        )
        remaining = max(0, MAX_AI_IMAGE_TRIES - int(ai_state.get("tries", 0)))
        st.caption(f"You can generate up to {MAX_AI_IMAGE_TRIES} images per session. Remaining: {remaining}.")

        generate_disabled = remaining <= 0 or not prompt
        if st.button("Generate and use as background", disabled=generate_disabled):
            ai_state["tries"] = int(ai_state.get("tries", 0)) + 1
            api_base_js = json.dumps(API_BASE)
            auth_token = st.session_state.get("auth_token") or ""
            auth_js = json.dumps(auth_token)
            prompt_js = json.dumps(prompt)
            html = f"""
            <div id="ai-image-container">
              <p>Generating image and uploading to backend...</p>
            </div>
            <script src="https://js.puter.com/v2/"></script>
            <script>
              (function() {{
                const container = document.getElementById("ai-image-container");
                const API_BASE = {api_base_js};
                const AUTH_TOKEN = {auth_js};
                const prompt = {prompt_js};

                if (!AUTH_TOKEN) {{
                  container.innerHTML = "<p style='color:red;'>You must be logged in before generating artwork.</p>";
                  return;
                }}

                container.innerHTML = "<p>Generating image for: <em>" + prompt + "</em></p>";
                puter.ai.txt2img(prompt, {{
                  // Use a free-tier image model for testing.
                  model: "black-forest-labs/FLUX.1-schnell-Free"
                }}).then(function(img) {{
                  // Draw image to a canvas so we can turn it into a Blob.
                  const canvas = document.createElement("canvas");
                  const w = img.naturalWidth || img.width;
                  const h = img.naturalHeight || img.height;
                  canvas.width = w;
                  canvas.height = h;
                  const ctx = canvas.getContext("2d");
                  ctx.drawImage(img, 0, 0, w, h);
                  canvas.toBlob(async function(blob) {{
                    if (!blob) {{
                      container.innerHTML = "<p style='color:red;'>Could not prepare image for upload.</p>";
                      return;
                    }}
                    try {{
                      const form = new FormData();
                      form.append("file", blob, "ai_background.png");
                      const resp = await fetch(API_BASE + "/uploads/image", {{
                        method: "POST",
                        headers: {{
                          "Authorization": "Bearer " + AUTH_TOKEN
                        }},
                        body: form
                      }});
                      if (!resp.ok) {{
                        const text = await resp.text();
                        console.error("Upload failed", text);
                        container.innerHTML = "<p style='color:red;'>Upload to backend failed. Please try again.</p>";
                        return;
                      }}
                      const data = await resp.json();
                      // Redirect back to Streamlit with bg upload info in query params
                      const url = new URL(window.location.href);
                      url.searchParams.set("bg_upload_id", data.upload_id);
                      url.searchParams.set("bg_filename", data.filename);
                      window.location.href = url.toString();
                    }} catch (err) {{
                      console.error(err);
                      container.innerHTML = "<p style='color:red;'>Upload to backend failed. Please try again.</p>";
                    }}
                  }}, "image/png");
                }}).catch(function(err) {{
                  console.error(err);
                  var msg = (err && err.message) ? err.message : String(err || "unknown error");
                  container.innerHTML = "<p style='color:red;'>Image generation failed: " + msg + "</p>";
                }});
              }})();
            </script>
            """
            components.html(html, height=500)

        if remaining <= 0:
            st.warning("You've reached the image generation limit for this session.")

    with upload_tab:
        bg = st.file_uploader(
            "Upload background image",
            accept_multiple_files=False,
            type=["png", "jpg", "jpeg", "webp"],
            help="This image will be used as the video background.",
        )

    upload_state = st.session_state.setdefault("uploads", {})

    if st.button(
        "Upload to backend",
        disabled=not tracks or not (bg or upload_state.get("bg_image_upload_id")),
    ):
        with st.spinner("Uploading tracks..."):
            files = [("files", (t.name, t.getvalue(), t.type or "application/octet-stream")) for t in tracks]
            tr = api_post_files("/uploads/tracks", files)

        # If a new image was uploaded here, send it; otherwise keep the one from AI.
        if bg is not None:
            with st.spinner("Uploading background image..."):
                img_files = [("file", (bg.name, bg.getvalue(), bg.type or "application/octet-stream"))]
                im = api_post_files("/uploads/image", img_files)
                upload_state["bg_image_upload_id"] = im["upload_id"]
                upload_state["bg_filename"] = im["filename"]

            upload_state["tracks_upload_id"] = tr["upload_id"]
            upload_state["tracks_files"] = tr["files"]
            st.success("Uploaded!")

    if upload_state:
        st.success("Files uploaded to backend.")
        with st.expander("Upload details", expanded=False):
            st.write(f"Tracks uploaded: {len(upload_state.get('tracks_files', []))}")
            st.write(f"Background image: {upload_state.get('bg_filename')}")

with col2:
    st.header("2) Configure and start job")
    mixtape_title = st.text_input("Mixtape title", value="Smooth Fade EDM Mixtape | Seamless Transitions")
    shuffle = st.checkbox("Shuffle tracks", value=True)
    transition_ms = st.number_input("Transition (ms)", min_value=0, max_value=30000, value=6000, step=500)
    make_video = st.checkbox("Render MP4 video", value=True)

    st.subheader("YouTube upload settings (optional)")
    do_upload = st.checkbox("Upload to YouTube when done", value=False)
    yt_title = st.text_input("YouTube title", value=mixtape_title)
    yt_privacy = st.selectbox("Privacy", ["unlisted", "public", "private"], index=0)
    yt_tags = st.text_input("Tags (comma-separated)", value="EDM, DJMix")

    job_state = st.session_state.setdefault("job", {})

    can_create = "tracks_upload_id" in upload_state and "bg_image_upload_id" in upload_state
    if st.button("Start mixing job", disabled=not can_create):
        payload: Dict[str, Any] = {
            "mixtape_title": mixtape_title,
            "shuffle": shuffle,
            "transition_ms": int(transition_ms),
            "tracks_upload_id": upload_state["tracks_upload_id"],
            "bg_image_upload_id": upload_state["bg_image_upload_id"],
            "make_video": make_video,
            "youtube": None,
        }
        if do_upload:
            payload["youtube"] = {
                "title": yt_title,
                "description": None,
                "tags": [t.strip() for t in yt_tags.split(",") if t.strip()],
                "privacy_status": yt_privacy,
            }
        resp = api_post_json("/jobs", payload)
        job_state.clear()
        job_state.update(resp)
        st.success(f"Job started: {resp['job_id']}")

    if job_state.get("job_id"):
        st.header("3) Monitor progress")
        job_id = job_state["job_id"]
        poll = st.checkbox("Auto-refresh", value=True)
        refresh_btn = st.button("Refresh now")

        if poll or refresh_btn:
            with st.spinner("Fetching status..."):
                job_state.update(api_get(f"/jobs/{job_id}"))

        status = job_state.get("status", "unknown")
        progress = int(job_state.get("progress", 0) or 0)
        stage = job_state.get("stage") or "starting"
        error = job_state.get("error")

        st.write(f"**Status:** {status.capitalize()} &nbsp;•&nbsp; **Stage:** {stage}")
        st.progress(min(max(progress, 0), 100) / 100.0)

        if error:
            st.error("The job failed.")
            with st.expander("Show error details", expanded=True):
                st.code(str(error))
                st.caption(
                    "Tip: On hosted platforms, audio/video processing often requires the `ffmpeg` binary. "
                    "If the error mentions ffmpeg/ffprobe, deploy with ffmpeg available (e.g. Docker) or run locally."
                )

        artifacts = job_state.get("artifacts") or {}
        st.subheader("Downloads")
        if artifacts.get("mix_mp3"):
            st.link_button("Download audio mix (MP3)", artifacts["mix_mp3"], type="primary")
        if artifacts.get("video_mp4"):
            st.link_button("Download video (MP4)", artifacts["video_mp4"])
        if artifacts.get("description_txt"):
            st.link_button("Download description text", artifacts["description_txt"])
        if artifacts.get("thumbnail"):
            st.link_button("Download thumbnail image", artifacts["thumbnail"])

        if job_state.get("youtube_url"):
            st.subheader("YouTube")
            st.write(job_state["youtube_url"])

        if poll:
            time.sleep(2.0)
            _rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
            if _rerun:
                _rerun()


