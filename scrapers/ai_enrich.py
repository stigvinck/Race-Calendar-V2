"""
AI Enrichment — Uses Claude API to clean up and enhance scraped race data.
Processes races in batches to extract better:
  - English name (from Thai-only names)
  - Race type classification
  - Province detection
  - Distance extraction
  - Deduplication hints

Requires ANTHROPIC_API_KEY environment variable.
Costs ~$0.01-0.05 per scrape cycle.
"""

import os
import json
import urllib.request
import re

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
API_URL = "https://api.anthropic.com/v1/messages"
BATCH_SIZE = 30  # Races per API call (keeps tokens manageable)

# Valid values for type field
VALID_TYPES = ["run", "trail", "triathlon", "cycling", "swim", "obstacle", "other"]


def is_available():
    """Check if AI enrichment is available (API key set)."""
    return bool(API_KEY)


def enrich_batch(races):
    """Send a batch of races to Claude for enrichment.
    Returns enriched race list with improved fields."""

    if not races:
        return races

    # Build a compact representation for the prompt
    race_summaries = []
    for i, r in enumerate(races):
        summary = {
            "i": i,
            "name": r.get("name", ""),
            "date": r.get("date", ""),
            "type": r.get("type", ""),
            "province": r.get("province", ""),
            "location": r.get("location", ""),
            "distances": r.get("distances", []),
        }
        race_summaries.append(summary)

    prompt = """You are a race data enrichment assistant. I have scraped race data from Thai running/endurance event websites. Many entries have Thai-only names, missing types, wrong provinces, or no distances extracted.

For each race below, return a JSON array with improved data. For each race:
1. "name_en": If the name is in Thai, provide a good English translation/transliteration. If already English, return it as-is. Keep the name natural, don't over-translate.
2. "type": Classify as exactly one of: run, trail, triathlon, cycling, swim, obstacle, other
3. "province": The Thai province. Use standard English names (e.g., "Chiang Mai", "Bangkok", "Phuket"). If you can infer from the name/location, do so. Otherwise keep current value.
4. "distances": Array of distance strings like ["5K", "10K", "21K", "42K"]. Extract from the name if present. Keep compact.
5. "is_duplicate_of": If this race looks like a duplicate of another race in this batch (same event, different source/slightly different name), put the index number of the other race. Otherwise null.

IMPORTANT: Return ONLY a JSON array, no markdown, no explanation. Each element must have keys: i, name_en, type, province, distances, is_duplicate_of

Here are the races:
""" + json.dumps(race_summaries, ensure_ascii=False)

    try:
        body = json.dumps({
            "model": MODEL,
            "max_tokens": 4000,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }).encode("utf-8")

        req = urllib.request.Request(API_URL, data=body, headers={
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
        })

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # Extract text from response
        text = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                text += block["text"]

        # Parse JSON response
        # Strip markdown fences if present
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
        text = text.strip()

        enriched = json.loads(text)

        if not isinstance(enriched, list):
            print("    [AI] Unexpected response format, skipping batch")
            return races

        # Apply enrichments back to races
        enrichment_map = {item["i"]: item for item in enriched if isinstance(item, dict)}

        for i, race in enumerate(races):
            if i in enrichment_map:
                e = enrichment_map[i]

                # Update name if we got a better English version
                name_en = e.get("name_en", "")
                if name_en and len(name_en) > 3:
                    # Only replace if current name is Thai-heavy
                    current = race.get("name", "")
                    thai_chars = sum(1 for c in current if '\u0e00' <= c <= '\u0e7f')
                    if thai_chars > len(current) * 0.3:
                        # Store original Thai name, use English as primary
                        race["nameTh"] = current
                        race["name"] = name_en

                # Update type if valid
                new_type = e.get("type", "")
                if new_type in VALID_TYPES:
                    race["type"] = new_type

                # Update province if provided and not "Unknown"
                new_province = e.get("province", "")
                if new_province and new_province != "Unknown" and len(new_province) > 2:
                    race["province"] = new_province

                # Update distances if we got better ones
                new_distances = e.get("distances", [])
                if new_distances and isinstance(new_distances, list):
                    if not race.get("distances") or len(new_distances) > len(race["distances"]):
                        race["distances"] = new_distances

                # Mark duplicates
                dup_of = e.get("is_duplicate_of")
                if dup_of is not None and isinstance(dup_of, int):
                    race["_duplicate_of"] = dup_of

        return races

    except Exception as e:
        print("    [AI] API error: %s" % e)
        return races


def enrich_all(races):
    """Enrich all races in batches, then deduplicate."""
    if not is_available():
        print("    [AI] ANTHROPIC_API_KEY not set — skipping enrichment")
        return races

    print("    [AI] Enriching %d races in batches of %d..." % (len(races), BATCH_SIZE))
    total_enriched = 0

    # Process in batches
    for start in range(0, len(races), BATCH_SIZE):
        batch = races[start:start + BATCH_SIZE]
        enriched = enrich_batch(batch)

        # Count how many were actually enriched
        for i, r in enumerate(enriched):
            if r.get("nameTh") or r.get("_duplicate_of") is not None:
                total_enriched += 1

        # Write back to main list
        races[start:start + BATCH_SIZE] = enriched

    # Remove duplicates flagged by AI
    deduped = []
    dup_indices = set()
    for i, r in enumerate(races):
        dup_of = r.pop("_duplicate_of", None)
        if dup_of is not None and isinstance(dup_of, int):
            # Keep the one with more data
            if dup_of < len(races):
                other = races[dup_of]
                # Keep whichever has more distances or a better URL
                this_score = len(r.get("distances", [])) + (1 if r.get("url") else 0)
                other_score = len(other.get("distances", [])) + (1 if other.get("url") else 0)
                if this_score <= other_score:
                    dup_indices.add(i)
                    continue

    for i, r in enumerate(races):
        if i not in dup_indices:
            r.pop("_duplicate_of", None)
            deduped.append(r)

    removed = len(races) - len(deduped)
    print("    [AI] Enriched %d races, removed %d duplicates" % (total_enriched, removed))
    return deduped
