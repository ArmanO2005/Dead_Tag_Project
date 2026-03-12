import os
import json
import re
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
from openai import OpenAI

# -----------------------
# Credentials
# -----------------------
with open("credentials.json", "r") as f:
    creds = json.load(f)

username = creds["username"]
password = creds["password"]

# -----------------------
# Load data
# -----------------------
dead_card_names = pd.read_csv("output/unique_collectors.csv")["0"].dropna()

# -----------------------
# Name parsing helpers
# -----------------------
_TITLES = {
    "dr", "mr", "mrs", "ms", "miss", "brother", "sister", "prof", "professor",
    "coll", "collector", "collectors"
}
_SUFFIXES = {"md", "m.d", "jr", "sr", "ii", "iii", "iv"}

_ORG_HINTS = {
    "ucbg", "uc", "dept", "department", "staff", "exp", "exped", "expedition",
    "museum", "university", "ave", "st", "street", "hotel", "calif", "california",
    "peru", "kenya", "ethiopia", "taiwan", "england", "davis", "smithsonian",
    "gns", "gdns"
}

_PARTICLES = {"von", "van", "der", "den", "de", "del", "da", "di", "la", "le", "du", "st", "st."}

def _is_code_like(s: str) -> bool:
    t = re.sub(r"[^A-Za-z0-9]", "", s)
    return bool(re.fullmatch(r"[A-Z]{2,}\d*", t))

def _clean_text(s: str) -> str:
    s = str(s).strip()
    s = s.translate(str.maketrans({c: " " for c in "[]=:()"}))
    s = s.replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*&\s*", " & ", s)
    return s.strip()

def _looks_like_person_chunk(chunk: str) -> bool:
    c = chunk.strip()
    if not c:
        return False
    if re.search(r"\d", c):
        return False
    if not re.search(r"[A-Za-z]", c):
        return False

    if re.search(r"\b[A-Za-z](?:\.)\b", c) or re.search(r"\b[A-Za-z](?:\s+[A-Za-z])+\b", c):
        return True

    toks = c.split()
    if len(toks) == 1 and re.fullmatch(r"[A-Za-z][A-Za-z\.'’-]{2,}", toks[0]):
        return True
    if len(toks) == 2 and re.fullmatch(r"[A-Za-z][A-Za-z\.'’-]{2,}", toks[-1]):
        return True
    return False

def _split_people(raw: str) -> list[str]:
    """
    Split a record into likely person chunks.
    Handles:
      - '&', 'and', '+', 'with'
      - comma-separated collector lists vs name+address
    """
    s = raw
    s = re.sub(r"\b(and|with)\b", "&", s, flags=re.IGNORECASE)
    s = re.sub(r"\+", "&", s)
    s = re.sub(r"\s*&\s*", " & ", s)

    people = []
    for part in [p.strip() for p in s.split("&") if p.strip()]:
        if "," in part:
            chunks = [c.strip() for c in part.split(",") if c.strip()]
            if len(chunks) >= 2 and all(_looks_like_person_chunk(c) for c in chunks[: min(3, len(chunks))]):
                people.extend(chunks[:3])
            else:
                people.append(chunks[0])
        else:
            people.append(part)
    return people

def _extract_lastname_from_person(person: str) -> str | None:
    p = _clean_text(person)
    if not p:
        return None
    if p.lower() in {"unknown", "unk"}:
        return None
    if _is_code_like(p):
        return None

    # Keep only first comma chunk (usually name)
    if "," in p:
        p = p.split(",", 1)[0].strip()

    tokens = [t for t in p.split() if re.search(r"[A-Za-z]", t)]
    if not tokens:
        return None

    while tokens and re.sub(r"[^\w]", "", tokens[0]).lower().rstrip(".") in _TITLES:
        tokens.pop(0)
    if not tokens:
        return None

    while tokens:
        tail = re.sub(r"[^\w]", "", tokens[-1]).lower()
        if tail in _SUFFIXES:
            tokens.pop()
        else:
            break
    if not tokens:
        return None

    tokens = [t for t in tokens if re.sub(r"[^\w]", "", t).lower() not in _ORG_HINTS]
    if not tokens:
        return None

    def is_initial(tok: str) -> bool:
        t = tok.replace(".", "")
        return bool(re.fullmatch(r"[A-Za-z]{1,2}", t))

    tokens_no_initials = [t for t in tokens if not is_initial(t)]
    tokens = tokens_no_initials if tokens_no_initials else tokens
    if not tokens:
        return None

    last_tok = tokens[-1]
    last_tok_clean = re.sub(r"[^A-Za-z\.'’]", "", last_tok)
    if not last_tok_clean:
        return None

    if "." in last_tok_clean:
        parts = [pp for pp in last_tok_clean.split(".") if pp]
        if parts:
            last_tok_clean = parts[-1]

    if len(tokens) >= 2:
        prev = re.sub(r"[^A-Za-z\.]", "", tokens[-2]).lower().rstrip(".")
        if prev in _PARTICLES:
            return f"{tokens[-2].strip('.')} {last_tok_clean}"

    return last_tok_clean

def parse_last_names(name: str) -> list[str]:
    raw = _clean_text(name)
    if not raw:
        return []
    if raw.lower() in {"unknown", "unk"} or _is_code_like(raw):
        return []

    out = []
    for person in _split_people(raw):
        ln = _extract_lastname_from_person(person)
        if ln:
            out.append(ln)
    return out



client = OpenAI(api_key="")

collector_names_checked = {'original_name': [], "matched_name": [], "in_db": []}

count = 0

for original_name in dead_card_names:
    collector_names_checked['original_name'].append(original_name)

    parsed_lastnames = parse_last_names(original_name)

    # include combined search + individual lastnames
    combined = ",".join(parsed_lastnames)
    search_terms = [combined] + parsed_lastnames if combined else parsed_lastnames

    db_options: list[str] = []

    for term in search_terms:
        # Use params so requests URL-encodes correctly
        url = "https://ucbg.collectionspace.org/cspace-services/orgauthorities/2a6f6156-2a66-4928-a0d2/items"
        resp = requests.get(url, params={"kw": term}, auth=HTTPBasicAuth(username, password))
        if resp.status_code != 200:
            print(f"Failed to fetch for kw={term!r}: {resp.status_code}")
            continue

        name_list = re.findall(r"<termDisplayName>(.*?)</termDisplayName>", resp.text)
        db_options.extend(name_list)

    db_options = sorted(set(db_options))

    prompt = (
        f"Original name: {original_name}\n"
        f"Database name options: {db_options}\n"
    )

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You receive an original collector name derived from optical character recognition and try to match it up with a name "
                    "in the provided name list.\n"
                    "Names must be formatted as:\n"
                    "- 'Lastname, F.' for one person\n"
                    "- 'Lastname, F. & F. Lastname' for two people\n"
                    "- 'Lastname, F., F. Lastname, & F. Lastname' for three people\n"
                    "This is a strict requirement, only return a name if it follows the formatting.\n"
                    "If there is a name in the list that matches, return that valid name.\n"
                    "Else construct a correctly formatted name from the original name.\n"
                    "If the original name is not a person or seems to be in error just return the original name.\n"
                    "you should only ever return a name and nothing else. Do not explain your reasoning."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=150,
        temperature=0.5,
    )

    collector_names_checked["matched_name"].append(completion.choices[0].message.content.strip())
    collector_names_checked["in_db"].append(collector_names_checked["matched_name"][-1] in db_options)
    print(count)
    count += 1

output_df = pd.DataFrame(collector_names_checked)
output_df.to_csv("output/collector_name_matching_gpt.csv", index=False)