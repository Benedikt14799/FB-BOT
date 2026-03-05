"""
targeting.py – Lead-Generierung & Phase 1 Engagement

Scrapet die FB Gruppe (Members & Feed).
Phase 1: Interagiert organisch mit dem Feed (Likes, Kommentare generiert via LLM).
Phase 2: Speichert "warme" Profile in der `pending` Queue der Supabase-Datenbank.
"""

import time
import random
import asyncio
import random
from playwright.async_api import Page, TimeoutError

from database import add_pending_recipient, supabase
from llm_engine import evaluate_post
from utils import logger
from config import GROUP_ID, SCORE_POINTS

async def _human_delay(min_s: float, max_s: float):
    await asyncio.sleep(random.uniform(min_s, max_s))

async def _random_scroll(page: Page):
    scroll_amount = random.randint(80, 450)
    await page.mouse.wheel(0, scroll_amount)
    await _human_delay(0.4, 1.2)
    if random.random() > 0.6:
        await page.mouse.wheel(0, -random.randint(30, 150))
        await _human_delay(0.3, 0.8)

async def _type_like_human(page: Page, selector: str, text: str):
    box = page.locator(selector).first
    if await box.is_visible():
        await box.click()
        for char in text:
            await page.keyboard.press(char)
            await asyncio.sleep(random.uniform(0.05, 0.15))

STEALTH_INIT_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['de-DE', 'de', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
"""

def extract_id_from_url(url: str) -> str:
    """Extrahiert die Nutzer-ID oder den Vanity-Namen aus der Profil-URL."""
    if not url: return ""
    if "/user/" in url:
        return url.split("/user/")[1].strip("/").split("?")[0]
    if "facebook.com/" in url:
        parts = url.split("facebook.com/")
        if len(parts) > 1:
            if "profile.php?id=" in parts[1]:
                return parts[1].split("id=")[1].split("&")[0]
            return parts[1].strip("/").split("?")[0]
    return ""

def _is_login_page(page: Page) -> bool:
    # Playwright async is slightly different but for a simple quick test we just return False
    # and let the TimeoutError handle broken sessions
    return False

# ─────────────────────────────────────────────
# 1. Phase 1: Organisches Feed-Engagement
# ─────────────────────────────────────────────

async def engage_with_feed(page: Page, account_id: int, max_posts: int = 5):
    """
    Scrollt durch den Gruppen-Feed, analysiert Posts per LLM und interagiert
    authentisch, um den Trust-Score des Accounts zu steigern und Leads aufzuwärmen.
    """
    if not GROUP_ID or GROUP_ID == "YOUR_GROUP_ID_HERE":
        logger.error(f"[Acc {account_id}] GROUP_ID fehlt in der Konfiguration!")
        return

    feed_url = f"https://www.facebook.com/groups/{GROUP_ID}/"
    logger.info("=" * 60)
    logger.info(f"[Acc {account_id}] Phase 1: Organisches Feed-Engagement")
    logger.info("=" * 60)

    engaged_count = 0

    try:
        await page.goto(feed_url, wait_until="domcontentloaded", timeout=40_000)
        await _human_delay(3.0, 5.0)

        logger.info(f"[Acc {account_id}] Scrolle durch den Feed...")
        for _ in range(3):
            await _random_scroll(page)
            await _human_delay(1.5, 3.0)

        posts = await page.locator('div[role="article"]').all()
        
        for post in posts:
            if engaged_count >= max_posts:
                break
                
            try:
                inner_text = await post.inner_text()
                if "Gesponsert" in inner_text or "Sponsored" in inner_text:
                    continue
                    
                post_text = inner_text.split("Gefällt mir")[0][:500].strip()
                if not post_text or len(post_text) < 20: 
                    continue

                links = await post.locator('a[role="link"]').all()
                author_name = "Ein Gruppenmitglied"
                author_id = ""
                for link in links:
                    href = await link.get_attribute("href")
                    if href and "/user/" in href:
                        author_name = await link.text_content()
                        author_name = author_name.strip()
                        author_id = extract_id_from_url(href)
                        break
                
                if not author_id:
                    continue
                    
                logger.info(f"[Acc {account_id}] Post gefunden von {author_name}")
                
                llm_decision = evaluate_post(post_text, author_name)
                action = llm_decision.get("action", "ignore")
                
                if action == "ignore":
                    continue
                    
                logger.info(f"[Acc {account_id}] LLM Aktion: {action.upper()} - führe aus...")
                
                add_pending_recipient(facebook_id=author_id, name=author_name, priority=1, person_score=SCORE_POINTS["kommentar_erhalten"], common_groups=[GROUP_ID])
                
                if action == "like":
                    like_btn = post.locator('div[aria-label="Gefällt mir"], div[aria-label="Like"]').first
                    if await like_btn.is_visible():
                        await like_btn.click()
                        logger.info(f"[Acc {account_id}] -> Gefällt mir geklickt.")
                        await _human_delay(1.0, 3.0)
                        
                elif action == "comment" and llm_decision.get("comment_text"):
                    comment_text = llm_decision["comment_text"]
                    
                    like_btn = post.locator('div[aria-label="Gefällt mir"], div[aria-label="Like"]').first
                    if await like_btn.is_visible():
                        await like_btn.click()
                        await _human_delay(1.0, 2.0)
                        
                    comment_btn = post.locator('div[aria-label="Kommentieren"], div[aria-label="Comment"]').first
                    if await comment_btn.is_visible():
                        await comment_btn.click()
                        await _human_delay(1.0, 2.0)
                        await _type_like_human(post, 'div[contenteditable="true"][role="textbox"]', comment_text)
                        await _human_delay(0.5, 1.0)
                        await page.keyboard.press("Enter")
                        logger.info(f"[Acc {account_id}] -> Kommentiert: '{comment_text}'")
                
                engaged_count += 1
                await _human_delay(5.0, 15.0)

            except Exception as ex:
                logger.error(f"[Acc {account_id}] Fehler bei Post-Verarbeitung: {ex}")
                continue

    except Exception as e:
        logger.error(f"[Acc {account_id}] Kritischer Fehler im Engage Modul: {e}")


# ─────────────────────────────────────────────
# 2. Phase 2: Members Scraping (Lead Gen)
# ─────────────────────────────────────────────

async def scrape_group_members(page: Page, account_id: int, max_extract: int = 50):
    """
    Sucht neue Mitglieder in der konfigurierten Facebook-Gruppe und 
    legt sie in der Datenbank ab (inkl. account_id Bindung temporär oder Global).
    """
    if not GROUP_ID or GROUP_ID == "YOUR_GROUP_ID_HERE":
        logger.error(f"[Acc {account_id}] GROUP_ID fehlt in der Konfiguration!")
        return

    members_url = f"https://www.facebook.com/groups/{GROUP_ID}/members"
    logger.info("=" * 60)
    logger.info(f"[Acc {account_id}] Phase 2 Targeting: Scrape Gruppe {GROUP_ID}")
    logger.info("=" * 60)

    found_count = 0
    added_to_db = 0

    try:
        await page.goto(members_url, wait_until="domcontentloaded", timeout=40_000)
        await _human_delay(3.0, 5.0)

        for _ in range(4):
            await _random_scroll(page)
            await _human_delay(1.5, 3.0)

        links = await page.locator('a[href*="/user/"], a[role="link"]:has-text("")').all()
        
        for link in links:
            if found_count >= max_extract:
                break
                
            try:
                href = await link.get_attribute("href")
                if not href: continue
                    
                name = await link.text_content()
                name = name.strip()
                if not name or "\n" in name: 
                    name = await link.get_attribute("aria-label") or ""
                
                name = name.strip()
                if not name: continue
                    
                member_id = extract_id_from_url(href)
                if member_id and not member_id.isdigit() and "." not in member_id:
                    found_count += 1
                    
                    # Score: 10 für Gemeinsame Gruppe. Prio: 2 (Normal)
                    if add_pending_recipient(facebook_id=member_id, name=name, priority=2, person_score=SCORE_POINTS["gemeinsame_gruppe"], common_groups=[GROUP_ID]):
                        added_to_db += 1
                        logger.info(f"[Acc {account_id}] Neu hinzugefügt: {name} ({member_id}) -> pending queue")
                        
            except Exception:
                pass

        logger.info(f"[Acc {account_id}] Scraping beendet: {found_count} gelesen, davon {added_to_db} NEU ins System.")
            
    except Exception as e:
        logger.error(f"[Acc {account_id}] Fehler beim Scraping: {e}")
