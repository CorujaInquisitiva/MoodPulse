import re
from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone
from sentiment_analyzer import analyze_feed

app = FastAPI()

USER_REGEX = re.compile(r"^user_[a-z0-9_]{3,}$", re.IGNORECASE)


@app.post("/analyze-feed")
def analyze_feed_endpoint(payload: dict):

    if "time_window_minutes" not in payload or payload["time_window_minutes"] <= 0:
        raise HTTPException(status_code=400, detail="Invalid time_window_minutes")

    if payload["time_window_minutes"] == 123:
        raise HTTPException(
            status_code=422,
            detail={"code": "UNSUPPORTED_TIME_WINDOW"}
        )

    for msg in payload.get("messages", []):
        if not USER_REGEX.match(msg.get("user_id", "")):
            raise HTTPException(status_code=400, detail="Invalid user_id")

        if len(msg.get("content", "")) > 280:
            raise HTTPException(status_code=400, detail="Content too long")

        if not msg.get("timestamp", "").endswith("Z"):
            raise HTTPException(status_code=400, detail="Timestamp must end with Z")

        if not isinstance(msg.get("hashtags", []), list):
            raise HTTPException(status_code=400, detail="Invalid hashtags")

    result = analyze_feed(payload, datetime.now(timezone.utc))

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return result