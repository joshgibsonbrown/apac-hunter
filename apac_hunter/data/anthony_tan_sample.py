"""
Anthony Tan / Grab Holdings — primary filing data
Sources:
  FY2023: Form 20-F filed Mar 28 2024, ref Mar 1 2024
  FY2024: Form 20-F filed Mar 14 2025, ref Feb 15 2025
  FY2025: Form 20-F filed Mar 6 2026, ref Jan 31 2026 + Form 3 Mar 18 2026
  Post-EGM: EGM 6-K Mar 24 2026 (85.9% approved, votes 45→90, proxy terminated)
"""

ANTHONY_PERIODS = [
    {
        "label": "FY2023",
        "source": "Form 20-F filed Mar 28 2024 (Item 7)",
        "reference_date": "2024-03-01",
        "class_a_outstanding": 3813340767,
        "class_b_outstanding": 120402284,
        "votes_per_class_a": 1,
        "votes_per_class_b": 45,
        "share_price_usd": 3.40,
        "holders": [
            {"name": "Anthony Tan", "class_a": 0, "class_b": 65966461},
            {"name": "Hibiscus Worldwide (AT)", "class_a": 0, "class_b": 19492330},
            {"name": "Hooi Ling Tan", "class_a": 0, "class_b": 22873300},
            {"name": "Ming Maa", "class_a": 0, "class_b": 11995011},
        ],
        "notes": "AT controls all Class B via irrevocable proxies from HL & Maa."
    },
    {
        "label": "FY2024",
        "source": "Form 20-F filed Mar 14 2025 (Item 7)",
        "reference_date": "2025-02-15",
        "class_a_outstanding": 3950498976,
        "class_b_outstanding": 119798676,
        "votes_per_class_a": 1,
        "votes_per_class_b": 45,
        "share_price_usd": 4.20,
        "holders": [
            {"name": "Anthony Tan", "class_a": 0, "class_b": 65966461},
            {"name": "Hibiscus Worldwide (AT)", "class_a": 0, "class_b": 19492330},
            {"name": "Hooi Ling Tan", "class_a": 0, "class_b": 22873300},
            {"name": "Ming Maa", "class_a": 0, "class_b": 11995011},
        ],
        "notes": "Structure unchanged from FY2023. AT still reliant on HL & Maa proxies."
    },
    {
        "label": "FY2025",
        "source": "Form 20-F filed Mar 6 2026 (Item 7) + Form 3 Mar 18 2026",
        "reference_date": "2026-01-31",
        "class_a_outstanding": 3972725983,
        "class_b_outstanding": 127755800,
        "votes_per_class_a": 1,
        "votes_per_class_b": 45,
        "share_price_usd": 3.78,
        "holders": [
            {"name": "Anthony Tan", "class_a": 0, "class_b": 77425133},
            {"name": "Hibiscus Worldwide (AT)", "class_a": 0, "class_b": 19492330},
            {"name": "Hooi Ling Tan", "class_a": 0, "class_b": 16147952},
            {"name": "Ming Maa", "class_a": 0, "class_b": 9904354},
            {"name": "Other KEs", "class_a": 0, "class_b": 1111904},
            {"name": "Non-proxy Class B", "class_a": 0, "class_b": 3674127},
        ],
        "notes": "HL & Maa converting to Class A. Form 3 shows AT direct up to 77.4M (RSA vesting)."
    },
    {
        "label": "Post-EGM",
        "source": "EGM 6-K Mar 24 2026 + Form 3 Mar 18 2026",
        "reference_date": "2026-03-24",
        "class_a_outstanding": 3972725983 + (127755800 - 96917463),
        "class_b_outstanding": 96917463,
        "votes_per_class_a": 1,
        "votes_per_class_b": 90,
        "share_price_usd": 3.78,
        "holders": [
            {"name": "Anthony Tan", "class_a": 0, "class_b": 77425133},
            {"name": "Hibiscus Worldwide (AT)", "class_a": 0, "class_b": 19492330},
            # HL and Maa converted to Class A — no longer in Class B
        ],
        "notes": "85.9% approved. Class B votes: 45→90. Proxy terminated. AT standalone ~75% voting control."
    },
]

ANTHONY_ALIGNED = ["Anthony Tan", "Hibiscus Worldwide (AT)"]
