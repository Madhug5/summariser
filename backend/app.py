import os
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request
from dotenv import load_dotenv
from flask_cors import CORS

_ENV_FILE = Path(__file__).with_name(".env")
_ENV_EXAMPLE_FILE = Path(__file__).with_name(".env.example")
if _ENV_FILE.exists():
    load_dotenv(dotenv_path=_ENV_FILE)
elif _ENV_EXAMPLE_FILE.exists():
    load_dotenv(dotenv_path=_ENV_EXAMPLE_FILE)

from summarizer import (
    SummarizerError,
    summarize_uploaded_video,
    summarize_youtube_url,
    validate_upload_filename,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "200")) * 1024 * 1024
CORS(app)


def _error_response(message: str, status: int):
    return jsonify({"error": message}), status


@app.route("/")
def home():
    return jsonify(
        {
            "service": "SignalFrame Video Summarizer API",
            "status": "ok",
            "routes": {
                "health": "/api/health",
                "youtube": "/api/summarize/youtube",
                "upload": "/api/summarize/upload",
            },
        }
    )


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "2.0.0"})


@app.route("/api/summarize/youtube", methods=["POST"])
def summarize_youtube():
    data = request.get_json(silent=True) or {}
    youtube_url = data.get("url")
    focus = data.get("focus")
    length = data.get("length")

    if not youtube_url:
        return _error_response("No YouTube URL provided.", 400)

    try:
        return jsonify(summarize_youtube_url(youtube_url, length=length, focus=focus))
    except SummarizerError as exc:
        return _error_response(str(exc), exc.status_code)
    except Exception as exc:
        return _error_response(f"Unexpected server error: {exc}", 500)


@app.route("/api/summarize/upload", methods=["POST"])
def summarize_upload():
    uploaded_file = request.files.get("video")
    focus = request.form.get("focus")
    length = request.form.get("length")

    if uploaded_file is None or not uploaded_file.filename:
        return _error_response("Upload a media file using the 'video' field.", 400)

    try:
        validate_upload_filename(uploaded_file.filename)
    except SummarizerError as exc:
        return _error_response(str(exc), exc.status_code)

    temp_file_path = None
    try:
        suffix = Path(uploaded_file.filename).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            uploaded_file.save(temp_file.name)
            temp_file_path = temp_file.name

        result = summarize_uploaded_video(
            temp_file_path,
            uploaded_file.filename,
            length=length,
            focus=focus,
        )
        return jsonify(result)
    except SummarizerError as exc:
        return _error_response(str(exc), exc.status_code)
    except Exception as exc:
        return _error_response(f"Unexpected server error: {exc}", 500)
    finally:
        if temp_file_path:
            try:
                Path(temp_file_path).unlink(missing_ok=True)
            except OSError:
                pass

@app.route("/summarize", methods=["POST"])
def summarize():
    data = request.get_json(silent=True) or {}
    youtube_url = data.get("url")
    focus = data.get("focus")
    length = data.get("length")

    if not youtube_url:
        return _error_response("No URL provided.", 400)

    try:
        result = summarize_youtube_url(youtube_url, length=length, focus=focus)
        return jsonify(result)
    except SummarizerError as exc:
        return _error_response(str(exc), exc.status_code)
    except Exception as exc:
        return _error_response(f"Unexpected server error: {exc}", 500)


@app.errorhandler(413)
def file_too_large(_):
    return _error_response(
        "Uploaded file is too large. Increase MAX_UPLOAD_MB or upload a smaller file.",
        413,
    )

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    app.run(host="0.0.0.0", port=port)
