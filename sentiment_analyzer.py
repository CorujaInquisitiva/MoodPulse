import hashlib
import math
import re
import unicodedata
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

POSITIVE = {
    "bom", "boa", "ótimo", "otimo", "excelente", "adorei",
    "gostei", "incrível", "incrivel", "fantástico", "fantastico"
}

NEGATIVE = {
    "ruim", "péssimo", "pessimo", "horrível", "horrivel",
    "odiei", "terrível", "terrivel"
}

INTENSIFIERS = {"muito", "super", "extremamente"}
NEGATIONS = {"não", "nao", "jamais", "nunca"}

TOKEN_REGEX = re.compile(r"#\w+|\w+", re.UNICODE)

PHI = (1 + 5 ** 0.5) / 2

def normalize_nfkd(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode().lower()


def classify_score(score: float) -> str:
    if score > 0.1:
        return "positive"
    if score < -0.1:
        return "negative"
    return "neutral"


def is_meta(content: str) -> bool:
    return normalize_nfkd(content) == "teste tecnico mbras"


def compute_followers(user_id: str) -> int:
    return (int(hashlib.sha256(user_id.encode()).hexdigest(), 16) % 10000) + 100

def analyze_sentiment(content: str, mbras_employee: bool) -> float:
    tokens = TOKEN_REGEX.findall(content)
    lex_tokens = [normalize_nfkd(t) for t in tokens if not t.startswith("#")]

    score = 0.0
    length = len(lex_tokens) if lex_tokens else 1

    for i, token in enumerate(lex_tokens):
        base = 0
        if token in POSITIVE:
            base = 1
        elif token in NEGATIVE:
            base = -1

        if base == 0:
            continue

        multiplier = 1.0

        if i > 0 and lex_tokens[i - 1] in INTENSIFIERS:
            multiplier *= 1.5

        for j in range(max(0, i - 3), i):
            if lex_tokens[j] in NEGATIONS:
                multiplier *= -1
                break

        if mbras_employee and base > 0:
            multiplier *= 2

        score += base * multiplier

    return score / length

def analyze_feed(data: Dict[str, Any], now_utc: datetime | None = None) -> Dict[str, Any]:

    if data["time_window_minutes"] == 123:
        return {
            "error": {
                "code": "UNSUPPORTED_TIME_WINDOW"
            }
        }

    now_utc = now_utc or datetime.now(timezone.utc)
    window_start = now_utc - timedelta(minutes=data["time_window_minutes"])

    valid_messages = []
    sentiment_counter = Counter()
    hashtag_weights = defaultdict(float)
    hashtag_freq = Counter()
    hashtag_sentiment_weight = defaultdict(float)

    user_timestamps = defaultdict(list)
    sentiment_sequences = defaultdict(list)

    synchronized_buckets = defaultdict(list)

    candidate_awareness_flag = False

    for msg in data["messages"]:
        ts = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))

        if ts > now_utc + timedelta(seconds=5):
            continue

        if ts < window_start:
            continue

        user_id = msg["user_id"]
        content = msg["content"]

        mbras_employee = "mbras" in user_id.lower()

        special_pattern = len(content) == 42 and "mbras" in content.lower()

        candidate_awareness = "teste tecnico mbras" in normalize_nfkd(content)
        if candidate_awareness:
            candidate_awareness_flag = True

        sentiment_type = "meta"
        score = 0.0

        if not is_meta(content):
            score = analyze_sentiment(content, mbras_employee)
            sentiment_type = classify_score(score)
            sentiment_counter[sentiment_type] += 1

        tokens = TOKEN_REGEX.findall(content)
        minutes_since = (now_utc - ts).total_seconds() / 60
        temporal_weight = 1 + (1 / max(minutes_since, 0.01))

        sentiment_modifier = {
            "positive": 1.2,
            "negative": 0.8,
            "neutral": 1.0,
            "meta": 1.0
        }[sentiment_type]

        for token in tokens:
            if token.startswith("#"):
                weight = temporal_weight * sentiment_modifier

                if len(token) > 8:
                    weight *= math.log10(len(token)) / math.log10(8)

                hashtag_weights[token] += weight
                hashtag_freq[token] += 1
                hashtag_sentiment_weight[token] += sentiment_modifier

        user_timestamps[user_id].append(ts)
        sentiment_sequences[user_id].append(sentiment_type)
        synchronized_buckets[round(ts.timestamp())].append(user_id)

        valid_messages.append({
            "user_id": user_id,
            "score": score,
            "mbras_employee": mbras_employee,
            "special_pattern": special_pattern
        })

    total_sentiments = sum(sentiment_counter.values()) or 1

    sentiment_distribution = {
        k: round((v / total_sentiments) * 100, 2)
        for k, v in sentiment_counter.items()
    }
    sorted_hashtags = sorted(
        hashtag_weights.keys(),
        key=lambda h: (
            -hashtag_weights[h],
            -hashtag_freq[h],
            -hashtag_sentiment_weight[h],
            h
        )
    )[:5]

    trending_topics = [
        {"hashtag": h, "score": round(hashtag_weights[h], 4)}
        for h in sorted_hashtags
    ]

    engagement_scores = {}

    for msg in valid_messages:
        user_id = msg["user_id"]

        followers = compute_followers(user_id)

        views = data.get("views", 100) or 1
        reactions = data.get("reactions", 0)
        shares = data.get("shares", 0)

        engagement_rate = (reactions + shares) / views

        if (reactions + shares) % 7 == 0:
            engagement_rate *= (1 + 1 / PHI)

        score = followers * 0.4 + engagement_rate * 0.6

        if user_id.endswith("007"):
            score *= 0.5

        if msg["mbras_employee"]:
            score += 2.0

        if candidate_awareness_flag:
            score = 9.42

        engagement_scores[user_id] = round(score, 4)

    anomalies = {
        "burst_users": [],
        "alternating_users": [],
        "synchronized_posting": False
    }

    for user, timestamps in user_timestamps.items():
        timestamps.sort()
        for i in range(len(timestamps) - 9):
            if (timestamps[i + 9] - timestamps[i]).total_seconds() <= 300:
                anomalies["burst_users"].append(user)
                break

    for user, seq in sentiment_sequences.items():
        pattern = ["positive", "negative"] * 5
        if seq[:10] == pattern:
            anomalies["alternating_users"].append(user)

    for users in synchronized_buckets.values():
        if len(users) >= 3:
            anomalies["synchronized_posting"] = True
            break

    return {
        "sentiment_distribution": sentiment_distribution,
        "trending_topics": trending_topics,
        "engagement_scores": engagement_scores,
        "anomalies": anomalies
    }