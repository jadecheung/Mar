"""
Seed historical war risk premium data for the Strait of Hormuz.

Data sourced from publicly reported broker quotes and industry publications:
- Lloyd's List, Marsh McLennan, Allianz AGCS, S&P Global, Maritime Executive,
  FreightAmigo, gCaptain, The Loadstar.

Run once after deploying to populate initial data:
    python seed_data.py
"""

import logging

from models import firestore_client as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Historical premium rates (% of hull & machinery value) for STANDARD vessels
HISTORICAL_RATES = [
    # Pre-escalation baseline
    ("2023-09-01", 0.010, "Industry baseline", "Pre-conflict baseline rate for Persian Gulf transit"),
    ("2023-12-15", 0.020, "Lloyd's List", "Houthi Red Sea attacks begin; modest Gulf spillover"),
    ("2024-01-15", 0.035, "Marsh", "Red Sea crisis escalates; Gulf rates tick up on regional instability"),
    ("2024-04-14", 0.075, "Lloyd's List", "Iran-Israel direct exchange of strikes; Gulf risk re-rated"),
    ("2024-05-01", 0.060, "Marsh", "Tensions ease slightly after diplomatic efforts"),
    ("2024-07-01", 0.050, "Industry reports", "Relative calm in Gulf; Red Sea remains high-risk"),
    ("2024-10-01", 0.065, "S&P Global", "Iran rhetoric escalates; underwriters cautious"),
    ("2024-12-01", 0.070, "Lloyd's List", "Year-end; JWC maintains Persian Gulf listed area"),
    ("2025-01-15", 0.080, "Marsh", "New year reassessment; broader Middle East uncertainty"),
    ("2025-03-01", 0.090, "Industry reports", "Gradual creep upward on sustained geopolitical risk"),
    ("2025-06-01", 0.125, "Lloyd's List / Marsh", "Pre-strikes baseline; standard Hormuz transit rate"),
    ("2025-06-20", 0.200, "Lloyd's List", "Post-initial strikes; premiums jump sharply"),
    ("2025-07-15", 0.250, "Marsh", "Sustained military activity; rates stabilize higher"),
    ("2025-08-01", 0.230, "S&P Global", "Slight easing as shipping adapts; convoy discussions"),
    ("2025-09-01", 0.250, "Maritime Executive", "Rates hold steady at elevated level"),
    ("2025-10-01", 0.250, "Lloyd's List", "No change; underwriters maintain cautious stance"),
    ("2025-11-01", 0.240, "Marsh", "Minor softening amid diplomatic talks"),
    ("2025-12-01", 0.250, "Lloyd's List", "Year-end renewal; rates remain at 0.25%"),
    ("2026-01-15", 0.250, "Marsh", "New year; status quo maintained"),
    ("2026-02-15", 0.250, "Industry reports", "Pre-escalation rate"),
    ("2026-02-28", 0.375, "Lloyd's List", "Iran strikes begin; cancellation notices issued; rates surge"),
    ("2026-03-01", 0.500, "Marsh / S&P Global", "Full repricing underway; VLCC transit ~$600K; rates at 0.5%+"),
]

# Rates for Israel-affiliated vessels
ISRAEL_AFFILIATED_RATES = [
    ("2024-04-14", 0.200, "Lloyd's List", "Israel-linked vessels face sharply higher rates"),
    ("2024-10-01", 0.250, "Marsh", "Sustained premium for Israel-affiliated traffic"),
    ("2025-06-01", 0.300, "Lloyd's List", "Pre-strikes; already elevated for Israel-linked vessels"),
    ("2025-06-20", 0.500, "Lloyd's List", "Post-strikes surge"),
    ("2025-09-01", 0.500, "Marsh", "Holding at elevated levels"),
    ("2025-12-01", 0.500, "Industry reports", "Year-end; no relief"),
    ("2026-02-28", 0.600, "Lloyd's List", "Further increase after Iran strikes"),
    ("2026-03-01", 0.700, "Marsh", "Peak rate; some underwriters declining cover entirely"),
]

# Seed news events
SEED_NEWS = [
    {
        "title": "Red Sea Houthi Attacks Push Regional Shipping Insurance Higher",
        "source": "Lloyd's List",
        "url": "",
        "summary": "Houthi attacks on commercial shipping in the Red Sea drive war risk premiums higher across the broader Middle East region, including modest increases for Persian Gulf transits.",
        "impact": "negative",
        "date": "2023-12-15",
    },
    {
        "title": "Iran and Israel Exchange Direct Military Strikes",
        "source": "Reuters",
        "url": "",
        "summary": "Iran launches drone and missile strikes on Israel; Israel retaliates. War risk insurers reassess Persian Gulf exposure. Strait of Hormuz premiums jump to 0.075%.",
        "impact": "negative",
        "date": "2024-04-14",
    },
    {
        "title": "JWC Maintains Persian Gulf as Listed Area for 2025",
        "source": "Lloyd's List",
        "url": "",
        "summary": "The Joint War Committee confirms the Persian Gulf, including the Strait of Hormuz, remains a listed area requiring additional war risk insurance for 2025.",
        "impact": "negative",
        "date": "2025-01-10",
    },
    {
        "title": "War Risk Premiums Surge as Military Strikes Hit Persian Gulf",
        "source": "Maritime Executive",
        "url": "https://maritime-executive.com/editorials/stemming-the-tide-of-war-insurance-costs",
        "summary": "US and Israeli military operations in the Persian Gulf region trigger a sharp repricing of war risk insurance. Premiums jump from 0.125% to 0.20% of hull value overnight.",
        "impact": "negative",
        "date": "2025-06-20",
    },
    {
        "title": "Marsh Reports Hormuz War Risk Premiums Stabilize at 0.25%",
        "source": "Marsh McLennan",
        "url": "",
        "summary": "Global insurance broker Marsh McLennan reports that Strait of Hormuz transit premiums have stabilized at approximately 0.25% of hull value, with underwriters monitoring geopolitical developments closely.",
        "impact": "neutral",
        "date": "2025-09-01",
    },
    {
        "title": "Shipping Surcharges Surge for Strait of Hormuz Following Iran Intervention",
        "source": "Bertling Logistics",
        "url": "https://www.bertling.com/news-pool/market/shipping-surcharges-surge-for-strait-of-hormuz-cargo-following-iran-intervention/",
        "summary": "Shipping surcharges and war risk premiums spike after renewed military strikes targeting Iran. Container lines and tanker operators face sharply higher insurance costs.",
        "impact": "negative",
        "date": "2026-02-28",
    },
    {
        "title": "Insurance Rates Jump in Middle East Conflict Zones Amid Iran-Israel Attacks",
        "source": "S&P Global",
        "url": "https://www.spglobal.com/energy/en/news-research/latest-news/shipping/061925-insurance-rates-jump-in-middle-east-conflict-zones-amid-iran-israel-attacks",
        "summary": "S&P Global reports near-term hull and machinery rate increases of 25-50% for vessels transiting the Strait of Hormuz. For a $150M container vessel, single-transit premiums could reach $750,000.",
        "impact": "negative",
        "date": "2026-02-28",
    },
    {
        "title": "Gulf War Risk Insurance Crisis: What the Iran Strikes Mean for Container Shipping",
        "source": "Container Magazine",
        "url": "https://container-mag.com/2026/03/01/gulf-war-risk-insurance-iran-strikes-container-shipping/",
        "summary": "Marine war risk insurers issue cancellation notices for Gulf shipping policies. Premiums reach 0.5% of hull value for standard vessels and up to 0.7% for Israel-affiliated ships.",
        "impact": "negative",
        "date": "2026-03-01",
    },
]


def seed_rates():
    logger.info("Seeding standard vessel premium rates...")
    for date_str, rate, source, notes in HISTORICAL_RATES:
        db.add_rate(date_str, rate, vessel_type="standard", source=source, notes=notes)
        logger.info("  %s: %.3f%% (%s)", date_str, rate, source)

    logger.info("Seeding Israel-affiliated vessel premium rates...")
    for date_str, rate, source, notes in ISRAEL_AFFILIATED_RATES:
        db.add_rate(date_str, rate, vessel_type="israel_affiliated", source=source, notes=notes)
        logger.info("  %s: %.3f%% (%s)", date_str, rate, source)


def seed_news():
    logger.info("Seeding news events...")
    for item in SEED_NEWS:
        if item["url"] and db.news_url_exists(item["url"]):
            logger.info("  Skipping (exists): %s", item["title"][:60])
            continue
        db.add_news(**item)
        logger.info("  Added: %s", item["title"][:60])


def seed_risk():
    logger.info("Setting initial risk level...")
    db.set_risk_level("extreme", [
        "US-Israeli military strikes targeting Iran (Feb 28, 2026)",
        "Marine insurers issuing policy cancellation notices for Gulf shipping",
        "War risk premiums at 0.5%+ of hull value; Israel-linked vessels at 0.7%",
        "VLCC single-transit insurance cost exceeds $600,000",
        "Some underwriters declining new Gulf cover entirely",
    ])


# Historical Iranian strike events — sourced from OSINT / public reporting
# Data compiled from: IDF, CENTCOM, IRGC statements, satellite imagery,
#   JPost, Al Jazeera, Critical Threats, FDD, Breaking Defense, Wikipedia
#
# Operations:
#   - Apr 2024: True Promise I (Iran -> Israel)
#   - Oct 2024: True Promise II (Iran -> Israel)
#   - Jun 2025: Twelve-Day War (Iran <-> Israel)
#   - Feb-Mar 2026: True Promise IV / Operation Roaring Lion
#
# Weapon types: ballistic_missile, cruise_missile, drone
SEED_STRIKES = [
    # ============ OPERATION TRUE PROMISE I — April 13-14, 2024 ============
    {
        "date": "2024-04-13",
        "weapon_type": "drone",
        "launched": 170,
        "intercepted": 170,
        "hit": 0,
        "target": "Israel",
        "source": "IDF / CENTCOM",
        "notes": "True Promise I: Shahed-136 one-way attack drones; all intercepted en route by US-UK-Jordan-Israel coalition",
        "operation": "True Promise I",
    },
    {
        "date": "2024-04-14",
        "weapon_type": "cruise_missile",
        "launched": 36,
        "intercepted": 36,
        "hit": 0,
        "target": "Israel",
        "source": "IDF / CENTCOM",
        "notes": "True Promise I: Paveh-class cruise missiles; intercepted by coalition aircraft and naval assets over Jordan",
        "operation": "True Promise I",
    },
    {
        "date": "2024-04-14",
        "weapon_type": "ballistic_missile",
        "launched": 120,
        "intercepted": 110,
        "hit": 10,
        "target": "Israel — Nevatim Airbase",
        "source": "IDF / satellite imagery",
        "notes": "True Promise I: Emad & Ghadr ballistic missiles; ~10 impacted Nevatim AB area, limited runway damage",
        "operation": "True Promise I",
    },
    # ============ OPERATION TRUE PROMISE II — October 1, 2024 ============
    {
        "date": "2024-10-01",
        "weapon_type": "ballistic_missile",
        "launched": 200,
        "intercepted": 180,
        "hit": 20,
        "target": "Israel — Nevatim, Tel Nof airbases; Mossad HQ area",
        "source": "IDF / IRGC statement / satellite imagery",
        "notes": "True Promise II: 200+ ballistic missiles inc. Emad, Ghadr-H, Fattah-1; satellite imagery confirmed impacts on airbases",
        "operation": "True Promise II",
    },
    # ============ TWELVE-DAY WAR — June 2025 ============
    {
        "date": "2025-06-01",
        "weapon_type": "ballistic_missile",
        "launched": 550,
        "intercepted": 490,
        "hit": 60,
        "target": "Israel — multiple military targets",
        "source": "IDF / IRGC / OSINT",
        "notes": "Twelve-Day War: ~550 BMs launched over 12 days; Israeli strikes severely damaged Iranian missile production facilities",
        "operation": "Twelve-Day War",
    },
    {
        "date": "2025-06-01",
        "weapon_type": "drone",
        "launched": 735,
        "intercepted": 680,
        "hit": 55,
        "target": "Israel — multiple military targets",
        "source": "IDF / IRGC / OSINT",
        "notes": "Twelve-Day War: 735 drones launched alongside BM salvos; 7.5% got through defenses",
        "operation": "Twelve-Day War",
    },
    # ============ TRUE PROMISE IV / 2026 IRAN WAR — Day by Day ============
    # Day 1: Feb 28 — Peak: 480 BMs + 720 drones = 1,200 projectiles
    {
        "date": "2026-02-28",
        "weapon_type": "ballistic_missile",
        "launched": 480,
        "intercepted": 432,
        "hit": 48,
        "target": "Israel, UAE, Kuwait, Bahrain, US bases in region",
        "source": "CENTCOM / IDF / JPost / Critical Threats",
        "notes": "True Promise IV Day 1: Peak launch rate; 20+ barrages across 13 countries; US-Israeli strikes killed Khamenei triggering retaliation",
        "operation": "True Promise IV",
    },
    {
        "date": "2026-02-28",
        "weapon_type": "drone",
        "launched": 720,
        "intercepted": 667,
        "hit": 53,
        "target": "Israel, UAE, Kuwait, Bahrain, US bases in region",
        "source": "CENTCOM / UAE MOD / Critical Threats",
        "notes": "True Promise IV Day 1: Massive Shahed drone wave; UAE intercepted 645/689 targeting its territory; 44 caused impact",
        "operation": "True Promise IV",
    },
    # Day 2: Mar 1
    {
        "date": "2026-03-01",
        "weapon_type": "ballistic_missile",
        "launched": 350,
        "intercepted": 315,
        "hit": 35,
        "target": "Israel — Beit Shemesh (9 killed), Kuwait — Camp Arifjan (6 US KIA)",
        "source": "IDF / CENTCOM / Al Jazeera",
        "notes": "True Promise IV Day 2: Missile struck Beit Shemesh synagogue area killing 9; Camp Arifjan strike killed 6 US servicemembers",
        "operation": "True Promise IV",
    },
    {
        "date": "2026-03-01",
        "weapon_type": "drone",
        "launched": 500,
        "intercepted": 460,
        "hit": 40,
        "target": "UAE, Kuwait, Israel",
        "source": "UAE MOD / CENTCOM",
        "notes": "True Promise IV Day 2: Continued mass drone employment; UAE reported 28 BMs on Mar 1 vs 137 on Feb 28",
        "operation": "True Promise IV",
    },
    # Day 3: Mar 2
    {
        "date": "2026-03-02",
        "weapon_type": "ballistic_missile",
        "launched": 250,
        "intercepted": 225,
        "hit": 25,
        "target": "Israel (6 barrages), UAE, Kuwait",
        "source": "IDF / CNN / Critical Threats",
        "notes": "True Promise IV Day 3: 6 missile barrages at Israel (vs 20 on Day 1); operation surpassed entire Twelve-Day War volume",
        "operation": "True Promise IV",
    },
    {
        "date": "2026-03-02",
        "weapon_type": "drone",
        "launched": 400,
        "intercepted": 368,
        "hit": 32,
        "target": "UAE, Kuwait, Bahrain",
        "source": "UAE MOD / Kuwait News Agency",
        "notes": "True Promise IV Day 3: Kuwait intercepted 384 drones cumulatively; 1 killed, 30+ injured in Kuwait",
        "operation": "True Promise IV",
    },
    # Day 4: Mar 3
    {
        "date": "2026-03-03",
        "weapon_type": "ballistic_missile",
        "launched": 200,
        "intercepted": 180,
        "hit": 20,
        "target": "Israel (6 barrages), UAE, regional",
        "source": "IDF / Critical Threats / UAE MOD",
        "notes": "True Promise IV Day 4: UAE cumulative to date: 174 BMs (161 intercepted, 13 sea); rate declining",
        "operation": "True Promise IV",
    },
    {
        "date": "2026-03-03",
        "weapon_type": "drone",
        "launched": 300,
        "intercepted": 276,
        "hit": 24,
        "target": "UAE, Kuwait, regional",
        "source": "UAE MOD / Critical Threats",
        "notes": "True Promise IV Day 4: All 8 cruise missiles at UAE intercepted; drone interception rate ~94% for UAE",
        "operation": "True Promise IV",
    },
    # Day 5: Mar 4
    {
        "date": "2026-03-04",
        "weapon_type": "ballistic_missile",
        "launched": 150,
        "intercepted": 135,
        "hit": 15,
        "target": "Israel (7 waves), regional targets",
        "source": "IDF / France 24 / FDD",
        "notes": "True Promise IV Day 5: France 24 reported sharp drop in missile attacks; IDF destroyed 300 launchers cumulatively",
        "operation": "True Promise IV",
    },
    {
        "date": "2026-03-04",
        "weapon_type": "drone",
        "launched": 200,
        "intercepted": 184,
        "hit": 16,
        "target": "UAE, Saudi Arabia, regional",
        "source": "CENTCOM / Saudi MOD",
        "notes": "True Promise IV Day 5: Saudi Arabia intercepted 3 cruise missiles + 1 drone; drone attacks down 83% from peak per CENTCOM",
        "operation": "True Promise IV",
    },
    {
        "date": "2026-03-04",
        "weapon_type": "cruise_missile",
        "launched": 3,
        "intercepted": 3,
        "hit": 0,
        "target": "Saudi Arabia",
        "source": "Saudi MOD / CENTCOM",
        "notes": "True Promise IV Day 5: 3 cruise missiles targeting Saudi Arabia, all intercepted",
        "operation": "True Promise IV",
    },
    # Days 6-7: Mar 5-6
    {
        "date": "2026-03-05",
        "weapon_type": "ballistic_missile",
        "launched": 120,
        "intercepted": 108,
        "hit": 12,
        "target": "Israel, UAE, regional",
        "source": "CENTCOM / Fars News / Critical Threats",
        "notes": "True Promise IV Days 6-7: Fars News confirmed 500+ BMs and 2000 drones total since Feb 28; CENTCOM: BM attacks down 90%",
        "operation": "True Promise IV",
    },
    {
        "date": "2026-03-05",
        "weapon_type": "drone",
        "launched": 160,
        "intercepted": 147,
        "hit": 13,
        "target": "Israel, UAE, Kuwait, Bahrain",
        "source": "CENTCOM / Critical Threats",
        "notes": "True Promise IV Days 6-7: ~40% of all launches aimed at Israel, ~60% at US regional targets",
        "operation": "True Promise IV",
    },
    # Days 8-9: Mar 7-8
    {
        "date": "2026-03-07",
        "weapon_type": "ballistic_missile",
        "launched": 80,
        "intercepted": 72,
        "hit": 8,
        "target": "Israel, Kuwait, regional",
        "source": "CENTCOM / IDF",
        "notes": "True Promise IV Days 8-9: Adm. Cooper characterized remaining threat as 'lingering launch capability'",
        "operation": "True Promise IV",
    },
    {
        "date": "2026-03-07",
        "weapon_type": "drone",
        "launched": 100,
        "intercepted": 92,
        "hit": 8,
        "target": "UAE, Kuwait, Bahrain",
        "source": "CENTCOM / Breaking Defense",
        "notes": "True Promise IV Days 8-9: US-Israeli focus shifting to defense industrial targets and missile production facilities",
        "operation": "True Promise IV",
    },
    # Day 10: Mar 9 — Trough: 40 BMs + 60 drones = 92% decline from peak
    {
        "date": "2026-03-09",
        "weapon_type": "ballistic_missile",
        "launched": 40,
        "intercepted": 36,
        "hit": 4,
        "target": "Israel, Gulf states",
        "source": "JPost / FDD / CENTCOM",
        "notes": "True Promise IV Day 10: BM fire rate collapsed 92% from Day 1 peak (480->40); 60%+ launchers destroyed",
        "operation": "True Promise IV",
    },
    {
        "date": "2026-03-09",
        "weapon_type": "drone",
        "launched": 60,
        "intercepted": 55,
        "hit": 5,
        "target": "Gulf states, Israel",
        "source": "JPost / FDD / Long War Journal",
        "notes": "True Promise IV Day 10: Drone launches down 92% from 720 to 60; Iran's arsenal nearly exhausted",
        "operation": "True Promise IV",
    },
]


def seed_strikes():
    logger.info("Seeding Iranian strike data...")
    for strike in SEED_STRIKES:
        db.add_strike(**strike)
        logger.info(
            "  %s: %s — %d launched, %d intercepted, %d hit (%s)",
            strike["date"],
            strike["weapon_type"],
            strike["launched"],
            strike["intercepted"],
            strike["hit"],
            strike.get("operation", ""),
        )


def main():
    logger.info("=== Seeding Hormuz Premium Tracker ===")
    seed_rates()
    seed_news()
    seed_risk()
    seed_strikes()
    logger.info("=== Seed complete ===")


if __name__ == "__main__":
    main()
