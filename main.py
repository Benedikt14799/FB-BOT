"""
main.py – CLI-Einstiegspunkt für den FB Messenger Bot.

Verwendung:
  python main.py login --account 1              → Einmaliger Login-Setup
  python main.py send --contact ID --message "Text"  → Einzelne Nachricht (Test)
  python main.py send-all                       → Alle Kontakte aus config.py (Test)
  python main.py send-all --dry-run             → Vorschau ohne Senden
  python main.py run                            → Startet den Always On Bot
"""

import sys
import argparse
import time

from utils import logger, human_delay
from config import RECIPIENTS, BULK_DELAY_MIN, BULK_DELAY_MAX


def cmd_login(args) -> int:
    """Führt den manuellen Login-Flow aus."""
    from login import run_login
    account_id = getattr(args, "account", 1)
    run_login(account_id)
    return 0


def cmd_send(args) -> int:
    """Sendet eine einzelne Nachricht."""
    from send_message import send_message
    success = send_message(args.contact, args.message)
    return 0 if success else 1


def cmd_send_all(args) -> int:
    """
    Sendet Nachrichten an alle Empfänger aus config.py.
    Mit Rate-Limiting zwischen den Nachrichten.
    """
    if not RECIPIENTS:
        logger.error("Keine Empfänger in config.py definiert (RECIPIENTS ist leer).")
        return 1

    # Filter heraus: Platzhalter-IDs
    valid_recipients = [
        r for r in RECIPIENTS if r.get("id") and r["id"] != "YOUR_CONTACT_ID_HERE"
    ]

    if not valid_recipients:
        logger.error(
            "Kein gültiger Empfänger in RECIPIENTS gefunden. "
            "Bitte config.py anpassen und echte IDs eintragen."
        )
        return 1

    if args.dry_run:
        logger.info("=== DRY RUN – keine Nachrichten werden gesendet ===")
        for i, r in enumerate(valid_recipients, 1):
            logger.info(f"  [{i}] Kontakt: {r['id']} | Nachricht: {r['message'][:40]}...")
        return 0

    logger.info(f"Starte Bulk-Send: {len(valid_recipients)} Empfänger")
    logger.info(f"Rate-Limiting: {BULK_DELAY_MIN}–{BULK_DELAY_MAX}s zwischen Nachrichten")

    from send_message import send_message

    results = {"ok": 0, "fail": 0}

    for i, recipient in enumerate(valid_recipients, 1):
        contact_id = recipient["id"]
        message = recipient["message"]

        logger.info(f"\n[{i}/{len(valid_recipients)}] Kontakt: {contact_id}")

        success = send_message(contact_id, message)

        if success:
            results["ok"] += 1
        else:
            results["fail"] += 1
            logger.warning(f"Fehlgeschlagen für: {contact_id}")

        # Rate-Limiting: Pause zwischen Nachrichten (außer nach der letzten)
        if i < len(valid_recipients):
            delay = human_delay.__wrapped__(BULK_DELAY_MIN, BULK_DELAY_MAX) if hasattr(human_delay, '__wrapped__') else None
            import random
            wait = random.uniform(BULK_DELAY_MIN, BULK_DELAY_MAX)
            logger.info(f"Warte {wait:.0f}s bis zur nächsten Nachricht...")
            time.sleep(wait)

    # Zusammenfassung
    logger.info("\n" + "=" * 40)
    logger.info(f"Abgeschlossen: {results['ok']} ✅  {results['fail']} ❌")
    logger.info("=" * 40)

    return 0 if results["fail"] == 0 else 1


def cmd_run(args) -> int:
    """Startet den asynchronen Always On Daemon für alle Accounts."""
    import asyncio
    from account_manager import start_all_accounts
    
    try:
        asyncio.run(start_all_accounts())
    except KeyboardInterrupt:
        logger.info("Daemon durch Benutzer abgebrochen.")
    return 0


def cmd_scrape_group(args) -> int:
    """Liest neue Mitglieder aus der Gruppe ein und speichert sie in der Datenbank."""
    import asyncio
    from targeting import scrape_group_members
    from account_manager import run_single_account_task
    
    limit = getattr(args, "limit", 50)
    account_id = getattr(args, "account", 1)
    
    try:
        asyncio.run(run_single_account_task(account_id, scrape_group_members, max_extract=limit))
    except KeyboardInterrupt:
        logger.info("Scraping durch Benutzer abgebrochen.")
    return 0


def cmd_engage(args) -> int:
    """Startet Phase 1: Organische LLM Feed-Interaktion (Likes, Kommentare)."""
    import asyncio
    from targeting import engage_with_feed
    from account_manager import run_single_account_task
    
    limit = getattr(args, "limit", 5)
    account_id = getattr(args, "account", 1)
    
    try:
        asyncio.run(run_single_account_task(account_id, engage_with_feed, max_posts=limit))
    except KeyboardInterrupt:
        logger.info("Engagement durch Benutzer abgebrochen.")
    return 0


def cmd_warmup(args) -> int:
    """Simuliert menschliches Surfen für den Account-Trust."""
    import asyncio
    from warmup import perform_warmup
    from account_manager import run_single_account_task
    
    account_id = getattr(args, "account", 1)
    
    try:
        asyncio.run(run_single_account_task(account_id, perform_warmup))
    except KeyboardInterrupt:
        logger.info("Warmup durch Benutzer abgebrochen.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="fb-bot",
        description="FB Messenger Bot – Facebook Messenger UI-Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Beispiele:
  python main.py login --account 1
  python main.py run
''',
    )

    subparsers = parser.add_subparsers(dest="command", metavar="BEFEHL")
    subparsers.required = True

    # ── login ──────────────────────────────────────────────────────
    login_parser = subparsers.add_parser(
        "login",
        help="Einmaliger manueller Login-Setup (Chrome öffnet sich)",
    )
    login_parser.add_argument(
        "--account",
        type=int,
        default=1,
        help="Für welchen Account (1-6) der Login durchgeführt werden soll (Standard: 1)",
    )

    # ── send ───────────────────────────────────────────────────────
    send_parser = subparsers.add_parser(
        "send",
        help="Einzelne Nachricht an einen Kontakt senden",
    )
    send_parser.add_argument(
        "--contact",
        required=True,
        metavar="ID",
        help="Facebook User-ID oder Vanity-Name",
    )
    send_parser.add_argument(
        "--message",
        required=True,
        metavar="TEXT",
        help='Nachrichtentext (in Anführungszeichen: "Hallo!")',
    )
    # ── send-all ───────────────────────────────────────────────────
    send_all_parser = subparsers.add_parser(
        "send-all",
        help="Nachrichten an alle Empfänger aus config.py senden",
    )
    send_all_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur Vorschau: zeigt was gesendet würde, sendet aber nichts",
    )

    # ── run ───────────────────────────────────────────────
    daemon_parser = subparsers.add_parser(
        "run",
        help="Startet den Always On Hintergrund-Service für alle Accounts",
    )

    # ── scrape-group ───────────────────────────────────────────────
    scrape_parser = subparsers.add_parser(
        "scrape-group",
        help="Liest neue Facebook-Gruppenmitglieder in die Datenbank ein",
    )
    scrape_parser.add_argument(
        "--account",
        type=int,
        default=1,
        help="Welcher Account (1-6) benutzt werden soll (Standard: 1)",
    )
    scrape_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximale Anzahl auszulesender Profile (Standard: 50)",
    )

    # ── engage ─────────────────────────────────────────────────────
    engage_parser = subparsers.add_parser(
        "engage",
        help="Phase 1: Liest den Feed, analysiert Posts per LLM und interagiert organisch",
    )
    engage_parser.add_argument(
        "--account",
        type=int,
        default=1,
        help="Welcher Account (1-6) benutzt werden soll (Standard: 1)",
    )
    engage_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximale Anzahl an Posts, mit denen interagiert werden soll (Standard: 5)",
    )

    # ── warmup ─────────────────────────────────────────────────────
    warmup_parser = subparsers.add_parser(
        "warmup",
        help="Surft für den Account 1-3 Minuten organisch auf FB rum",
    )
    warmup_parser.add_argument(
        "--account",
        type=int,
        default=1,
        help="Welcher Account (1-6) benutzt werden soll (Standard: 1)",
    )

    args = parser.parse_args()

    command_map = {
        "login": cmd_login,
        "send": cmd_send,
        "send-all": cmd_send_all,
        "run": cmd_run,
        "scrape-group": cmd_scrape_group,
        "engage": cmd_engage,
        "warmup": cmd_warmup,
    }

    exit_code = command_map[args.command](args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
