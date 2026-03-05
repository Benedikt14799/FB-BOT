"""
natural_behavior.py – Simulation menschlichen Verhaltens auf Facebook "Always On"

Ersetzt das alte warmup.py und targeting.py.
Scrollt den Feed, verteilt dynamisch Likes/Kommentare basierend auf Account-Alter,
besucht Profile und scrapt nebenbei in den zugewiesenen Gruppen nach Leads.
"""

import time
import random
import asyncio
from datetime import datetime
from playwright.async_api import Page, TimeoutError

from utils import logger
from llm_engine import evaluate_post
from database import get_account_age_days, add_pending_recipient, is_already_contacted
from config import SCORE_POINTS

# In-Memory Tracking für die "Always On" Daemon Schleife
# Structure: {account_id: {"date": "YYYY-MM-DD", "likes": 0, "comments": 0}}
daily_stats = {}

def get_stats(account_id: int):
    today = datetime.now().strftime("%Y-%m-%d")
    if account_id not in daily_stats or daily_stats[account_id]["date"] != today:
        daily_stats[account_id] = {"date": today, "likes": 0, "comments": 0}
    return daily_stats[account_id]

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

def extract_id_from_url(url: str) -> str:
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


async def scroll_feed(page: Page, account_id: int, seconds: int):
    """Simuliert das Scrollen durch den Haupt-Newsfeed."""
    logger.info(f"[Acc {account_id}] Scrolle den Haupt-Feed für ~{seconds} Sekunden...")
    try:
        start_time = time.time()
        await page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=40000)
        await _human_delay(3.0, 6.0)
        
        while (time.time() - start_time) < seconds:
            await _random_scroll(page)
            await _human_delay(2.0, 5.0)
    except Exception as e:
        logger.error(f"[Acc {account_id}] Fehler beim Feed Scrollen: {e}")

async def browse_profiles(page: Page, account_id: int, count: int):
    """Klickt sich durch zufällige Profile oder die Friends-Page."""
    logger.info(f"[Acc {account_id}] Schaue {count} zufällige Seiten/Profile an...")
    targets = [
        "https://www.facebook.com/friends/", 
        "https://www.facebook.com/watch/",
        "https://www.facebook.com/marketplace/"
    ]
    try:
        for _ in range(count):
            await page.goto(random.choice(targets), wait_until="domcontentloaded", timeout=40000)
            await _human_delay(3.0, 8.0)
            for _ in range(random.randint(2, 5)):
                 await _random_scroll(page)
                 await _human_delay(1.0, 4.0)
    except Exception as e:
        logger.error(f"[Acc {account_id}] Fehler beim Profile browsen: {e}")


async def engage_with_groups(page: Page, account_id: int, account: dict, max_posts: int = 3):
    """Liest Posts in zugewiesenen Gruppen, liked und kommentiert (mit Limits)."""
    age = get_account_age_days(account_id)
    stats = get_stats(account_id)
    groups = account.get("groups", [])
    
    if not groups:
        logger.warning(f"[Acc {account_id}] Keine Gruppen in config zugewiesen für Engagement.")
        return

    group = random.choice(groups)
    group_id = group.get("id")
    group_name = group.get("name")
    
    logger.info(f"[Acc {account_id}] Besuche Gruppe '{group_name}' für Engagement...")
    
    try:
        await page.goto(f"https://www.facebook.com/groups/{group_id}/", wait_until="domcontentloaded", timeout=40000)
        await _human_delay(4.0, 8.0)

        for _ in range(3):
            await _random_scroll(page)
            await _human_delay(1.5, 3.0)

        engaged = 0
        posts = await page.locator('div[role="article"]').all()
        
        for post in posts:
            if engaged >= max_posts: break
            
            try:
                inner_text = await post.inner_text()
                if "Gesponsert" in inner_text or "Sponsored" in inner_text: continue
                
                post_text = inner_text.split("Gefällt mir")[0][:500].strip()
                if not post_text or len(post_text) < 20: continue

                llm_decision = evaluate_post(post_text, "Ein Mitglied")
                action = llm_decision.get("action", "ignore")

                if action == "ignore": continue

                # Liken (ab Tag 1, max 5/Tag)
                if action == "like" and stats["likes"] < 5:
                    like_btn = post.locator('div[aria-label="Gefällt mir"], div[aria-label="Like"]').first
                    if await like_btn.is_visible():
                        await like_btn.click()
                        stats["likes"] += 1
                        engaged += 1
                        logger.info(f"[Acc {account_id}] Post geliked. ({stats['likes']}/5 heute)")
                        await _human_delay(2.0, 5.0)

                # Kommentieren (ab Tag 4, max 2/Tag)
                elif action == "comment" and age >= 4 and stats["comments"] < 2:
                    if random.random() < 0.3: # 30% Chance pro Session
                        comment_text = llm_decision.get("comment_text")
                        if comment_text:
                            comment_btn = post.locator('div[aria-label="Kommentieren"], div[aria-label="Comment"]').first
                            if await comment_btn.is_visible():
                                await comment_btn.click()
                                await _human_delay(1.0, 3.0)
                                await _type_like_human(post, 'div[contenteditable="true"][role="textbox"]', comment_text)
                                await _human_delay(1.0, 2.0)
                                await page.keyboard.press("Enter")
                                stats["comments"] += 1
                                engaged += 1
                                logger.info(f"[Acc {account_id}] Post kommentiert: '{comment_text}' ({stats['comments']}/2 heute)")
                                await _human_delay(4.0, 10.0)

            except Exception as e:
                logger.debug(f"[Acc {account_id}] Post übersprungen (Fehler): {e}")
                continue

    except Exception as e:
        logger.error(f"[Acc {account_id}] Fehler beim Group Engagement: {e}")


async def scrape_targets(page: Page, account_id: int, account: dict, limit: int = 10):
    """Sucht in den zugewiesenen Gruppen nach neuen Leads und prüft Global auf Duplikate."""
    groups = account.get("groups", [])
    if not groups:
        return

    group = random.choice(groups)
    group_id = group.get("id")
    members_url = f"https://www.facebook.com/groups/{group_id}/members"
    
    logger.info(f"[Acc {account_id}] Scrape {limit} Targets in Gruppe {group_id}...")
    
    try:
        await page.goto(members_url, wait_until="domcontentloaded", timeout=40000)
        await _human_delay(3.0, 5.0)

        for _ in range(4):
            await _random_scroll(page)
            await _human_delay(1.5, 3.0)

        links = await page.locator('a[href*="/user/"], a[role="link"]:has-text("")').all()
        found = 0
        added = 0
        
        for link in links:
            if found >= limit: break
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
                    found += 1
                    
                    # Global Duplicate Check
                    if not is_already_contacted(member_id):
                        if add_pending_recipient(facebook_id=member_id, name=name, priority=2, person_score=SCORE_POINTS["gemeinsame_gruppe"], common_groups=[group_id]):
                            added += 1
                            logger.info(f"[Acc {account_id}] Neues Target erfasst: {name}")
            except Exception:
                pass
                
        logger.info(f"[Acc {account_id}] Scraping beendet: {added} neue Leads dem Pool hinzugefügt.")
    except Exception as e:
        logger.error(f"[Acc {account_id}] Fehler beim Scraping: {e}")

async def run_session(page: Page, account_id: int, account: dict):
    """Der Kern eines isolierten 'Always On' Aufrufs. Führt natürliches Verhalten aus."""
    age = get_account_age_days(account_id)
    
    # 1. Feed scrollen (immer)
    await scroll_feed(page, account_id, seconds=int(random.uniform(60, 180)))
    
    # 2. Gruppen browsen & interagieren (Liken, Kommentieren)
    await engage_with_groups(page, account_id, account, max_posts=random.randint(1, 3))
    
    # 3. Profile anschauen
    await browse_profiles(page, account_id, count=random.randint(2, 5))
    
    # 4. Scraping (nur wenn Account alt genug, Tag 4)
    if age >= 4:
        await scrape_targets(page, account_id, account, limit=10)
        
    # Noch ein bisschen Abschluss-Scrollen
    await scroll_feed(page, account_id, seconds=int(random.uniform(30, 90)))
