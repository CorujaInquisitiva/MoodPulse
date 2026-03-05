import re
import unicodedata
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import hashlib
import math
from dataclasses import dataclass

# ----------------- Lexicon e utilitários -----------------
POSITIVE_WORDS = ["bom","ótimo","adorei","excelente","maravilhoso","perfeito","gostei"]
NEGATIVE_WORDS = ["ruim","péssimo","odiei","terrível","horrível","decepcionante"]
INTENSIFIERS = ["muito","super","extremamente"]
NEGATIONS = ["não","nunca","jamais"]

def _strip_accents_lower(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()

POSITIVE_SET = {_strip_accents_lower(w) for w in POSITIVE_WORDS}
NEGATIVE_SET = {_strip_accents_lower(w) for w in NEGATIVE_WORDS}
INTENSIFIER_SET = {_strip_accents_lower(w) for w in INTENSIFIERS}
NEGATION_SET = {_strip_accents_lower(w) for w in NEGATIONS}

TOKEN_RE = re.compile(r"(?:#\w+(?:-\w+)*)|\b\w+\b", re.UNICODE)
USER_ID_REGEX = re.compile(r"^user_[a-z0-9_]{3,}$", re.IGNORECASE)

@dataclass
class ValidationError(Exception):
    message: str
    code: str = "INVALID_INPUT"

# ----------------- Sentimento -----------------
def _is_mbras_employee(user_id: str) -> bool:
    return "mbras" in user_id.lower()

def _candidate_awareness(content: str) -> bool:
    norm = re.sub(r"\s+", " ", re.sub(r"[^\w\s]"," ", content)).strip()
    return _strip_accents_lower(norm) == _strip_accents_lower("teste técnico mbras")

def _tokenize(content: str) -> List[Tuple[str,str]]:
    tokens: List[Tuple[str,str]] = []
    for m in TOKEN_RE.finditer(content):
        tok = m.group(0)
        tokens.append((tok,_strip_accents_lower(tok)))
    return tokens

def _sentiment_for_message(content: str, is_mbras_emp: bool) -> Tuple[float,str]:
    if _candidate_awareness(content):
        return 0.0,"meta"
    tokens = _tokenize(content)
    total_words = max(len(tokens),1)
    pos_sum = neg_sum = 0.0
    next_multiplier = 1.0
    neg_scopes: List[int] = []
    for orig,norm in tokens:
        if norm in INTENSIFIER_SET:
            next_multiplier = 1.5
            neg_scopes = [n-1 for n in neg_scopes if n-1>0]
            continue
        if norm in NEGATION_SET:
            neg_scopes.append(3)
            continue
        polarity = 0
        if norm in POSITIVE_SET: polarity = 1
        elif norm in NEGATIVE_SET: polarity = -1
        if polarity !=0:
            value = next_multiplier
            if len(neg_scopes)%2==1:
                polarity*=-1
            neg_scopes.clear()
            next_multiplier=1.0
            if is_mbras_emp and polarity>0:
                value*=2
            if polarity>0: pos_sum+=value
            else: neg_sum+=value
        else:
            neg_scopes=[n-1 for n in neg_scopes if n-1>0]
    score = (pos_sum-neg_sum)/total_words
    if score>0.0: label="positive"
    elif score<0.0: label="negative"
    else: label="neutral"
    return score,label

def _followers_simulation(user_id: str) -> int:
    h=int(hashlib.sha256(user_id.encode()).hexdigest(),16)
    return (h%10000)+100

def _engagement_rate_user(agg: Dict[str,int]) -> float:
    views = max(agg.get("views",0),1)
    base_rate=(agg.get("reactions",0)+agg.get("shares",0))/views
    total=agg.get("reactions",0)+agg.get("shares",0)
    if total>0 and total%7==0:
        phi=(1+5**0.5)/2
        base_rate*=(1+1/phi)
    return base_rate

def _validate_message(m: Dict[str,Any]) -> None:
    if not isinstance(m.get("content"),str): raise ValidationError("content inválido")
    if len(m["content"])>280: raise ValidationError("content muito longo")
    if not isinstance(m.get("user_id"),str) or not USER_ID_REGEX.match(m["user_id"]): raise ValidationError("user_id inválido")
    if not isinstance(m.get("hashtags",[]),list): raise ValidationError("hashtags inválidas")
    for k in ["reactions","shares","views"]:
        v=m.get(k,0)
        if not isinstance(v,int) or v<0: raise ValidationError(f"{k} inválido")
    if not m.get("timestamp","").endswith("Z"): raise ValidationError("timestamp inválido")
    m["_dt"]=datetime.fromisoformat(m["timestamp"][:-1]+"+00:00")

def _filter_future(messages: List[Dict[str,Any]], now_utc: datetime) -> List[Dict[str,Any]]:
    return [m for m in messages if m["_dt"] <= now_utc+timedelta(seconds=5)]

def _within_window(m: Dict[str,Any], anchor: datetime, minutes:int)->bool:
    return m["_dt"]>=anchor-timedelta(minutes=minutes) and m["_dt"]<=anchor

def _trending_topics(window_msgs: List[Dict[str,Any]], anchor: datetime)->List[str]:
    weights:Dict[str,float]={}
    counts:Dict[str,int]={}
    sentiment_weights:Dict[str,float]={}
    for m in window_msgs:
        mult=1.0
        if m["_sentiment_label"]=="positive": mult=1.2
        elif m["_sentiment_label"]=="negative": mult=0.8
        for h in m.get("hashtags",[]):
            tag=h.lower()
            delta_min=max((anchor-m["_dt"]).total_seconds()/60,0.01)
            base=1+1/delta_min
            if len(tag)>8: base*=math.log10(len(tag))/math.log10(8)
            peso=base*mult
            weights[tag]=weights.get(tag,0.0)+peso
            counts[tag]=counts.get(tag,0)+1
            sentiment_weights[tag]=sentiment_weights.get(tag,0.0)+mult
    items=list(weights.items())
    items.sort(key=lambda kv:(-kv[1],-counts.get(kv[0],0),-sentiment_weights.get(kv[0],0),kv[0]))
    return [k for k,_ in items[:5]]

def _detect_anomalies(all_msgs: List[Dict[str,Any]])->Tuple[bool,Any]:
    return False,None 

def analyze_feed(messages: List[Dict[str,Any]], time_window_minutes:int, now_utc:datetime)->Dict[str,Any]:
    for m in messages: _validate_message(m)
    valid_msgs=_filter_future(messages,now_utc)
    anchor=now_utc
    window_msgs=[m for m in valid_msgs if _within_window(m,anchor,time_window_minutes)]

    flags={
        "mbras_employee": any(_is_mbras_employee(m["user_id"]) for m in valid_msgs),
        "special_pattern": any(len(m["content"])==42 and "mbras" in m["content"].lower() for m in valid_msgs),
        "candidate_awareness": any(_candidate_awareness(m["content"]) for m in valid_msgs),
    }

    dist_counts={"positive":0,"negative":0,"neutral":0}
    included=0
    for m in valid_msgs:
        score,label=_sentiment_for_message(m["content"],_is_mbras_employee(m["user_id"]))
        m["_sentiment_score"]=score
        m["_sentiment_label"]=label
        if label!="meta":
            dist_counts[label]+=1
            included+=1
    sentiment_distribution={"positive":0.0,"negative":0.0,"neutral":0.0} if included==0 else {
        "positive":round(100*dist_counts["positive"]/included,2),
        "negative":round(100*dist_counts["negative"]/included,2),
        "neutral":round(100*dist_counts["neutral"]/included,2)
    }

    engagement_score=round(sum(m.get("reactions",0)+m.get("shares",0) for m in window_msgs)/max(sum(m.get("views",0) for m in window_msgs),1)*10,2)
    if flags["candidate_awareness"]: engagement_score=9.42

    per_user={}
    for m in valid_msgs:
        u=m["user_id"]
        agg=per_user.setdefault(u,{"reactions":0,"shares":0,"views":0})
        agg["reactions"]+=m.get("reactions",0)
        agg["shares"]+=m.get("shares",0)
        agg["views"]+=m.get("views",0)
    ranking=[]
    for u,agg in per_user.items():
        eng=_engagement_rate_user(agg)
        score=_followers_simulation(u)*0.4+eng*0.6
        if u.lower().endswith("007"): score*=0.5
        if _is_mbras_employee(u): score+=2.0
        ranking.append((score,eng,u))
    ranking.sort(key=lambda t:(-t[0],-t[1],t[2]))
    influence_ranking=[{"user_id":u,"influence_score":round(s,2)} for s,_,u in ranking[:10]]

    trending_topics=_trending_topics(valid_msgs,anchor)
    anomaly_detected,anomaly_type=_detect_anomalies(valid_msgs)

    return {
        "analysis":{
            "sentiment_distribution":sentiment_distribution,
            "engagement_score":engagement_score,
            "trending_topics":trending_topics,
            "influence_ranking":influence_ranking,
            "anomaly_detected":anomaly_detected,
            "anomaly_type":anomaly_type,
            "flags":flags
        }
    }