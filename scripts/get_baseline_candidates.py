import os
import json
import re
from pathlib import Path

def main():
    vault = Path("/Users/lbq/Desktop/c c/知识库/wiki")
    entities_dir = vault / "entities"
    baseline_dir = vault / "raw/ifind-baseline"
    payloads_dir = vault / "raw/entity-delta-backfill"

    print("Scanning entity delta payloads...")
    hit_counts = {}
    company_info = {}

    for p in payloads_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for item in data.get("updates", []):
                comp = item.get("company")
                if not comp:
                    continue
                hit_counts[comp] = hit_counts.get(comp, 0) + 1
                info = company_info.setdefault(comp, {
                    "tiers": set(),
                    "graph_only": True,
                    "exposure_only": True,
                    "reports": set()
                })
                info["tiers"].add(item.get("tier", "related"))
                if not item.get("graph_only", False):
                    info["graph_only"] = False
                if not item.get("exposure_only", False):
                    info["exposure_only"] = False
                info["reports"].add(data.get("source_name", ""))
        except Exception as e:
            print(f"Error parsing payload {p.name}: {e}")

    print(f"Found {len(hit_counts)} companies in payloads.")

    print("Scanning entities directory...")
    candidates = []
    
    # Pre-load existing individual baseline names to make checking fast
    existing_baselines = {p.stem for p in baseline_dir.glob("*.json") if not p.name.startswith("baseline-updates-")}
    print(f"Loaded {len(existing_baselines)} existing baseline companies.")

    entities_scanned = 0
    for p in entities_dir.glob("*.md"):
        entities_scanned += 1
        company_name = p.stem
        if company_name in existing_baselines:
            continue

        # Check if they have an A-share ticker in frontmatter
        text = p.read_text(encoding="utf-8", errors="ignore")
        
        # Regex search for tickers
        m = re.search(r"tickers:\s*\[\"?(\d{6})\"?\]", text)
        code = m.group(1) if m else ""
        if not code:
            m2 = re.search(r"code:\s*\"?(\d{6})\"?", text)
            code = m2.group(1) if m2 else ""
            
        if not code or len(code) != 6:
            continue

        # Get details from payloads
        hits = hit_counts.get(company_name, 0)
        info = company_info.get(company_name, {
            "tiers": {"related"},
            "graph_only": False,
            "exposure_only": False,
            "reports": set()
        })

        is_core = "core" in info["tiers"]
        graph_only = info["graph_only"]
        exposure_only = info["exposure_only"]

        # Scoring
        score = 0
        if is_core:
            score += 100
        if not graph_only:
            score += 50
        if not exposure_only:
            score += 30
        score += hits * 10
        score += len(info["reports"]) * 5

        # Also check if they are mentioned in report_contexts.json
        candidates.append({
            "name": company_name,
            "code": code,
            "score": score,
            "hits": hits,
            "reports": sorted(list(info["reports"])),
            "tiers": sorted(list(info["tiers"])),
            "graph_only": graph_only,
            "exposure_only": exposure_only
        })

    print(f"Scanned {entities_scanned} entities. Found {len(candidates)} candidates.")
    
    # Sort candidates by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Print top 30 candidates to a file and stdout
    output_path = Path("/Users/lbq/Desktop/c c/金融/scripts/top_candidates.json")
    output_path.write_text(json.dumps(candidates[:30], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Top 30 candidates saved to {output_path}")

    # Output to stdout
    print(json.dumps(candidates[:20], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
