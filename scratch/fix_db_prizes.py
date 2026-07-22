"""
fix_db_prizes.py — Sanitize all prize_pool fields in MongoDB Atlas.
"""
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eventradar import db

def clean_prize(val):
    if not val:
        return None
    s = str(val).strip()
    if not s or s.lower() == "none":
        return None
    if s.startswith("{") or "cash" in s.lower():
        try:
            # Replaces None/True/False string keywords if needed for ast.literal_eval
            s_clean = s.replace("None", "None").replace("True", "True").replace("False", "False")
            d = ast.literal_eval(s_clean)
            if isinstance(d, dict):
                cash = d.get("cash") or d.get("amount")
                curr = str(d.get("currency") or "").lower()
                curr_sym = "₹" if "rupee" in curr or "inr" in curr or not curr else "$"
                if cash:
                    return f"{curr_sym}{int(float(cash)):,}"
                elif d.get("others"):
                    return str(d["others"])[:100]
        except Exception:
            pass

        # Regex fallbacks
        match = re.search(r"['\"]?cash['\"]?\s*:\s*(\d+)", s, re.I)
        if match:
            return f"₹{int(match.group(1)):,}"
        match_amt = re.search(r"(\d[\d,]{3,})", s)
        if match_amt:
            amt_clean = match_amt.group(1).replace(",", "")
            return f"₹{int(amt_clean):,}"
        return None
    return s


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    col = db.get_events_col()
    updated = 0
    total = 0
    for doc in col.find({}):
        total += 1
        old_prize = doc.get("prize_pool")
        new_prize = clean_prize(old_prize)
        if old_prize != new_prize:
            col.update_one({"_id": doc["_id"]}, {"$set": {"prize_pool": new_prize}})
            updated += 1
            print(f"Updated '{doc.get('title', '')[:30]}': {repr(old_prize)[:40]} -> {repr(new_prize)}")

    print(f"\nDone! Scanned {total} documents, updated {updated} documents in MongoDB Atlas.")


if __name__ == "__main__":
    main()
