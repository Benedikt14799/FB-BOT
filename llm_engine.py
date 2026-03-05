"""
llm_engine.py – GPT-4o-mini Interaktion & Sentiment Analysis (Phase 1)

Generiert menschlich wirkende Kommentare basierend auf Facebook Posts
und entscheidet über die Aktion (like, comment, add_friend).
"""

import json
import random
from openai import OpenAI

from config import OPENAI_API_KEY, GROUP_NAME
from utils import logger


# Initialisiere OpenAI Client
if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-proj-..."):
    logger.warning("OPENAI_API_KEY fehlt oder ist Dummy. LLM Engine offline.")
    client = None
else:
    client = OpenAI(api_key=OPENAI_API_KEY)


SYSTEM_PROMPT = f"""Du bist ein echter Nutzer der Facebook-Gruppe '{GROUP_NAME}'.

DEIN STIL:
- Schreib kurz und direkt – 1-2 Sätze reichen oft.
- Nutze die Sprache und Begriffe, die in dieser Gruppe üblich sind.
- Sei manchmal zustimmend, manchmal skeptisch, manchmal neugierig.
- Stell gelegentlich eine echte Rückfrage.
- Erwähne manchmal eigene Erfahrungen mit "Ich hab..." oder "Bei mir war...".
- Zeig manchmal Unsicherheit: "Bin kein Experte aber...".

VERBOTEN:
- Em-Dashes (—)
- Einstieg mit Floskeln wie "Genau!", "Toller Beitrag!", "Spot on!", "Das sehe ich auch so!"
- Perfekte Grammatik bei jedem Kommentar.
- Immer nur positive Aussagen.
- Generische Kommentare, die zu jedem Post passen.
- Validation Sandwich (Zustimmung -> Kritik -> Zustimmung).

AUFGABE:
Analysiere den übergebenen Post und entscheide strategisch über die beste Aktion.
Gib deine Antwort AUSSCHLIESSLICH im folgenden JSON Format zurück:
{{
    "action": "like" | "comment" | "add_friend" | "ignore",
    "reasoning": "Kurze Erklärung für die Wahl",
    "comment_text": "Der generierte Kommentartext (leer falls action != comment oder add_friend)"
}}
"""


def _post_processing(text: str) -> str:
    """Implementiert die menschlichen 'Verräter-Signale' laut wissenschaftlicher KI-Detektion."""
    if not text:
        return text
        
    # 1. Entferne Em-Dashes (—) und ersetze durch Komma oder Leerzeichen
    text = text.replace("—",",").replace(" - ", " - ")
    
    # 2. Wahrscheinlichkeit für fehlende Großschreibung am Anfang
    if random.random() < 0.15 and text[0].isalpha():
        text = text[0].lower() + text[1:]
        
    # 3. Tippfehler injizieren (ca. 20% der Fälle)
    if random.random() < 0.20 and len(text) > 10:
        # Einfacher Transpositions-Fehler (z.B. ie -> ei)
        idx = random.randint(1, len(text) - 2)
        chars = list(text)
        # Tausche zwei Buchstaben
        chars[idx], chars[idx+1] = chars[idx+1], chars[idx]
        text = "".join(chars)
        
    # 4. Zufällige Satzzeichen-Inkonsistenz am Ende
    if text.endswith(".") and random.random() < 0.3:
        text = text[:-1]  # Punkt weglassen
        
    return text


def evaluate_post(post_text: str, author_name: str, interaction_history: str = "Keine") -> dict:
    """
    Übergibt einen Feed-Post an das LLM und erhält eine strukturierte Handlungsempfehlung.
    """
    if not client:
        return {"action": "ignore", "reasoning": "OpenAI not configured", "comment_text": ""}

    logger.info(f"Analysiere Post von {author_name} via LLM: {post_text[:30]}...")

    user_prompt = f"""POST-INHALT VON {author_name}: {post_text}
BISHERIGE INTERAKTION MIT DIESER PERSON: {interaction_history}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={ "type": "json_object" },
            temperature=0.8,
            max_tokens=250
        )
        
        result_json = response.choices[0].message.content
        data = json.loads(result_json)
        
        # Post-Processing
        if data.get("comment_text"):
            original = data["comment_text"]
            data["comment_text"] = _post_processing(original)
            
        logger.info(f"LLM Aktion: {data.get('action')} - Reason: {data.get('reasoning')}")
        
        return data

    except Exception as e:
        logger.error(f"Fehler bei LLM Engine Ausführung: {e}")
        return {"action": "ignore", "reasoning": "LLM Error", "comment_text": ""}


def generate_message_for_stage(stage: str, contact_name: str, group_name: str, conversation_history: list = None) -> str:
    """
    Generiert die passende Nachricht für den 3-stufigen Conversation Funnel.
    stage: 'msg1' (Einstieg), 'msg2' (Vertrauen aufbauen), 'msg3' (Angebot)
    """
    if not client:
        return f"Fallback Nachricht für {stage} (OpenAI offline)"
        
    history_str = "Keine vorherigen Nachrichten."
    if conversation_history:
        history_str = "\n".join([f"[{m.get('sender')}]: {m.get('text')}" for m in conversation_history[-5:]])

    prompts = {
        "msg1": f"""Du bist ein normaler Facebook-Nutzer. Schreib eine kurze, lockere Erstnachricht an {contact_name}.
Ihr seid beide in der Gruppe '{group_name}'.
KEIN Angebot. Kein Spam. Maximal 2-3 Sätze. Menschlich, nicht werblich.
Frage nach einer gemeinsamen Erfahrung aus der Gruppe.""",

        "msg2": f"""Du führst ein Gespräch mit {contact_name}. Ihr seid beide in '{group_name}'.
Bisheriger Verlauf: {history_str}
Schreib eine natürliche Folgeantwort, die auf {contact_name}'s letzte Nachricht eingeht.
Baue Vertrauen auf. Stelle eine echte, vertiefende Rückfrage. Noch kein Angebot! Maximal 3 Sätze.""",

        "msg3": f"""Du führst ein Gespräch mit {contact_name}.
Bisheriger Verlauf: {history_str}
Jetzt ist der richtige Moment für ein sanftes Angebot bezüglich der Themen aus '{group_name}'.
Kein harter Verkauf. Natürlich einleiten (z.B. "Ich hab da übrigens was, das dir helfen könnte...").
Maximal 3 Sätze."""
    }
    
    selected_prompt = prompts.get(stage)
    if not selected_prompt:
        logger.error(f"Unbekannte Funnel-Stage: {stage}")
        return ""

    logger.info(f"LLM generiert Nachricht für Funnel-Stage: {stage} (Kontakt: {contact_name})")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Du schreibst chat-Nachrichten wie ein echter Mensch auf Facebook. Halte dich exakt an die Post-Processing Regeln (keine perfekten Sätze, kleinschreibung oft bevorzugt, absolut keine Em-Dashes oder corporate Speech)."},
                {"role": "user", "content": selected_prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        raw_text = response.choices[0].message.content
        return _post_processing(raw_text)

    except Exception as e:
        logger.error(f"Fehler bei LLM Engine (generate_message): {e}")
        return ""
