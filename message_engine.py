"""
message_engine.py – Dynamische Personalisierung und Nachrichten-Rotation

Stellt sicher, dass das Facebook Anti-Spam-System keine identischen Nachrichten
in Folge bemerkt, indem es durch einen Pool iteriert.
"""

import random
from utils import logger
from database import supabase

# Vordefinierte Varianten mit Platzhaltern (Absolut Anti-Spam / Kein Validation-Sandwich, keine Floskeln am Anfang)
VARIANTS = [
    {
        "id": 1,
        "text": "hab dich in {group} gesehen, {name}. {hook}",
        "tone": "casual",
        "length": "short"
    },
    {
        "id": 2,
        "text": "wir sind ja in der gleichen Gruppe ({group}). {hook}",
        "tone": "direct",
        "length": "short"
    },
    {
        "id": 3,
        "text": "{name}, kurze Frage zu {group}. {hook}",
        "tone": "curious",
        "length": "short"
    },
    {
        "id": 4,
        "text": "bin grad über dein Profil hier in {group} gestolpert. {hook}",
        "tone": "casual",
        "length": "medium"
    },
    {
        "id": 5,
        "text": "falls du eh grad online bist wg {group} - {hook}",
        "tone": "casual",
        "length": "medium"
    },
    {
        "id": 6,
        "text": "hoffe das is ok wenn ich einfach so schreibe {name}. bin auch bei {group} dabei. {hook}",
        "tone": "polite",
        "length": "long"
    },
    {
        "id": 7,
        "text": "sind ja im selben {group} netzwerk. {hook}",
        "tone": "direct",
        "length": "short"
    },
    {
        "id": 8,
        "text": "hi {name}, wollte dich bzgl {group} was fragen, {hook}",
        "tone": "direct",
        "length": "medium"
    },
    {
        "id": 9,
        "text": "kennen uns zwar noch nich persönlich, aber wegen {group}: {hook}",
        "tone": "polite",
        "length": "long"
    },
    {
        "id": 10,
        "text": "du bist ja scheinbar auch bei {group} aktiv. {hook}",
        "tone": "casual",
        "length": "medium"
    }
]

# Standard Hooks (natürlich, mit Tippfehlern / Umgangssprache)
DEFAULT_HOOKS = [
    "bist du da momentan auch verletzt oder ist das schon länger her?",
    "mich würd mal interessieren ob du da auch grade probleme hast?",
    "machst du grad ne behandlung mit oder versuchst dus so hinzukriegen?",
    "hatte da auch meine probleme, vielleicht kann man sich mal austauschen",
    "bin mir nich sicher ob ich ne op machen soll, wie liefs bei dir?"
]

def get_next_message(recipient_name: str, group_name: str, custom_hook: str = None, previous_variant_id: int = None) -> tuple[int, str]:
    """
    Wählt eine zufällige Nachricht aus, die NICHT der vorherigen entspricht.
    Füllt die Platzhalter mit den gegebenen Werten ab.
    
    Gibt ein Tuple zurück: (Variant-ID, Finaler Nachrichtentext)
    """
    
    # Filtern, damit die vorherige Variante (die zuletzt einem User gesendet wurde) nicht direkt nochmal genutzt wird
    available_variants = [v for v in VARIANTS if previous_variant_id is None or v["id"] != previous_variant_id]
    
    # Fallback, falls irgendwas schief geht (sollte bei >1 Variante nie passieren)
    if not available_variants:
         available_variants = VARIANTS
         
    selected_variant = random.choice(available_variants)
    hook = custom_hook if custom_hook else random.choice(DEFAULT_HOOKS)
    
    # Vornamen extrahieren
    first_name = recipient_name.split(" ")[0] if recipient_name else ""
    
    # Platzhalter ersetzen
    final_text = selected_variant["text"].replace("{name}", first_name)
    final_text = final_text.replace("{group}", group_name)
    final_text = final_text.replace("{hook}", hook)
    
    # Leichte natürliche Inkonsistenz im Leerzeichen/Satzzeichen-Bereich hinzufügen
    if random.random() > 0.8:
        final_text = final_text + " " # Manchmal ein versehentliches Leerzeichen am Ende
        
    return selected_variant["id"], final_text

