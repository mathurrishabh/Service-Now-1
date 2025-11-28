"""Knowledge-Base Agent

Responsibilities:
- Load local KB export (`kb_articles_export.json`) or query ServiceNow KB table
- Provide `search_kb(query, top_k=3)` returning ranked matches with article text
"""
from pathlib import Path
import json
from typing import List, Dict


BASE = Path(__file__).parent


def load_local_kb() -> List[Dict]:
    f = BASE / 'kb_articles_export.json'
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text())
    except Exception:
        return []


def _score_query_against_text(query: str, text: str) -> float:
    q = query.lower()
    tokens = [t for t in q.split() if len(t) > 3]
    if not tokens:
        return 0.0
    text_l = text.lower()
    score = sum(1 for t in tokens if t in text_l)
    return score / len(tokens)


def search_kb(query: str, top_k: int = 3, threshold: float = 0.2) -> List[Dict]:
    """Return list of matches: {incident_number, article_sys_id, title, body, score}
    Uses local `kb_articles_export.json` as the KB source.
    """
    kb = load_local_kb()
    matches = []
    for e in kb:
        art = e.get('article', {})
        text = (art.get('text') or '') + ' ' + (art.get('short_description') or '')
        score = _score_query_against_text(query, text)
        if score >= threshold:
            matches.append({
                'incident_number': e.get('incident_number'),
                'article_sys_id': e.get('article_sys_id'),
                'title': art.get('short_description'),
                'body': art.get('text'),
                'score': score,
            })
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches[:top_k]


if __name__ == '__main__':
    print('KB Agent loaded. Local KB entries:', len(load_local_kb()))
