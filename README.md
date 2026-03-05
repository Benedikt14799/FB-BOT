# Advanced Facebook Messenger Automation

Ein modulares, 2-Phasen Bot-System zur Automatisierung von Facebook Messenger Interaktionen mit Fokus auf Stealth, Anti-Sperr-Mechanismen und organisches Verhalten.

## Features

- **✅ Phase 1: LLM Engagement (Warming)**: Liest Gruppen-Feeds aus und interagiert vollautomatisch (Likes & Kommentare) unter Nutzung von `gpt-4o-mini`, um Trust Scores aufzubauen und Profile aufzuwärmen. Beinhaltet Post-Processing für "Tippfehler" und Em-Dash Bereinigung zur Vermeidung von KI-Detektion.
- **✅ Phase 2: Autonomous Scheduler Daemon**: Arbeitet Empfänger ab "warmem" Score (>= 40) im Hintergrund mit Zufallsverzögerungen (3-8 Minuten) ab. Beachtet strikt "Active Hours" (09:00 - 20:00).
- **✅ Stealth-Send Engine**: Nutzt Playwright mit `stealth` Plugins. Interpretiert E2EE (End-to-End Encryption) Checks automatisch. Simuliert exaktes menschliches Tippverhalten (Micro-Delays pro Tastendruck).
- **✅ Scoring & Blacklist-Logik**: Personen, die nach 24 Stunden nicht antworten, werden automatisch von der Supabase Datenbank auf die Blacklist gesetzt.
- **✅ Postgres / Supabase Backend**: Vollständiges Tracking über Cloud-DB für detailliertes Monitoring, Priorisierung anhand des Engagement-Scores.
- **✅ Dynamische Config**: Alle Konfigurationen wie Latenzen, Punkte, Limits und IDs sind dynamisch steuerbar über die `config.yaml`.

---

## Installation & Setup

1. **Abhängigkeiten installieren:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   pip install pyyaml openai
   playwright install chromium
   ```

2. **Supabase & OpenAI `.env` anlegen:**
   Erstelle eine Datei `.env` im Stammverzeichnis mit:
   ```env
   SUPABASE_URL="https://[YOUR_PROJECT_ID].supabase.co"
   SUPABASE_KEY="[YOUR_SERVICE_KEY]"
   OPENAI_API_KEY="sk-proj-..."
   ```

3. **Supabase Datenbank initialisieren:**
   Führe das beiliegende `supabase_schema.sql` Skript in deinem Supabase SQL Editor aus, um die erforderlichen Tabellen (`recipients` und `message_logs`) mit den neuen Scoring-Feldern zu erstellen.

4. **Konfiguration anpassen:**
   Öffne `config.yaml` und trage deine `group_id`, Timings und Punktelogiken ein.

---

## Bedienung (CLI)

Der Hauptzugriffspunkt ist `main.py`. Alle Befehle werden über dieses Script abgewickelt.

### 1. Einmaliger Login (Session speichern)
Startet Chrom und wartet auf deinen manuellen Facebook-Login, um Cookies und Session im Unterordner `/fb_profile/` abzuspeichern.
```powershell
python main.py login
```

### 2. Phase 1: LLM Feed Engagement
Startet die Feed-Analyse. Das Script scrollt durch die definierte Gruppe, übergibt Post-Inhalte an das gpt-4o-mini Sprachmodell, entscheidet über die Aktion (Like, Comment, Ignorieren) und iteriert entsprechend. Positive Reaktionen addieren den konfigurierbaren Punkte-Score für diesen Kontakt in Supabase.
```powershell
python main.py engage --limit 5
```

### 3. Phase 2: Lead Generation (Scraping)
Liest die Mitgliederzeilen in Facebook aus und pumpt neue Targets mit dem Basis-Score und einer niedrigen Priorität (2) in die Supabase Queue.
```powershell
python main.py scrape-group --limit 30
```

### 4. Phase 2: Daemon (Message Scheduler)
Startest du idealerweise im Hintergrund. Der Ablaufplaner liest alle 10 Sekunden, ob er dran ist. Falls noch keine Nachricht innerhalb des Zeitlimits versendet wurde, holt er den am höchsten priorisierten Empfänger _über dem minimalen Score-Threshold (ab 40)_ aus Supabase und versendet die dynamisch variierte Nachricht. Logs findest du im Ordner `/logs`. Das System geht automatisch um 20:00 in den Schlafmodus und wacht um 09:00 wieder auf.
```powershell
python main.py start-daemon
```

### 5. Single / Test Send
Wenn ein spezifischer User direkt angeschrieben werden soll (Umgehung von Scheduler und Score):
```powershell
python main.py send --contact "[FACEBOOK_ID_ODER_VANITY]" --message "Dein Test-Text hier"
```
