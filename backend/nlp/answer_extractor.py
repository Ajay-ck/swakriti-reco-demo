
import re
import json


# ---------- Voice/text parsing ----------
PARSE_PROMPT = """A customer is speaking to a fashion kiosk voice assistant.

They just said: "{transcript}"

The question currently shown on screen is: {current_question}
This is the PRIMARY target — if the statement is short, vague, or only makes
sense as an answer to one question, assume it answers this one first.

The kiosk still needs answers to these questions ONLY (in this exact order,
only ask what isn't answered yet — do NOT invent or infer any question not
listed here, even if it seems related):
{remaining_questions}

Task:
- Extract every answer you can confidently infer from what they said, even if
  it answers a question that isn't the very next one in line — but ONLY from
  the question list above, nothing else.
- CRITICAL: A single sentence often answers MULTIPLE questions at once. Scan the
  ENTIRE sentence against EVERY question in the remaining_questions list before
  responding — do not stop after finding one match. Example:
  "I want a wedding saree for my sister's wedding party under 5000" answers
  occasion (wedding), budget (5000 max), AND category (saree) simultaneously —
  extract all three, not just one.
- Once a question is answered in extracted or raw_extracted, the kiosk will NOT
  ask it again — so err on the side of extracting more, not less, when the
  transcript clearly contains that information.
- Handle paraphrase, synonyms, and negation correctly
  (e.g. "not black, something lighter" means Black & Dark is REJECTED, not selected).
- GENDER INFERENCE: if remaining_questions includes a gender question, use your
  general knowledge of Indian fashion garments (not just exact word matching)
  to classify the category mentioned:
  * Garments worn almost exclusively by women — saree/sari, half-saree,
    kanjivaram, salwar kameez, salwar suit, salwar set, kurti/kurthi, lehenga,
    chaniya choli, anarkali, gown, dupatta, blouse, dress, wrap dress ->
    infer "Myself (woman)", do NOT ask gender.
  * Unisex garments — shirt, kurta, trouser, dhoti, cape set, jacket, sweater,
    t-shirt -> ambiguous, DO ask gender, do not guess.
  * If category is unclear or not mentioned -> ask gender normally.
  Recognize spelling variants and regional names even if not listed above.
  When you infer gender this way, put it in "extracted" with the exact option
  string, same as any other confident match.
- SIZE INFERENCE: if remaining_questions includes a size question, check the
  category first. Draped/free-size garments — saree/sari, half-saree, dupatta,
  stole, mundu, shawl, chunni — do NOT use S/M/L/XL sizing. Do NOT ask size for
  these; instead put the exact "Free size" option string from that question's
  option list into "extracted". For any other category, ask size normally.
- SIZE ANSWER STRICTNESS: for "size" specifically, extract ONLY the exact size
  token — one of: XS, S, M, L, XL, XXL, 3XL, small, medium, large, extra small,
  extra large, not sure, free size — NEVER the surrounding sentence. This rule
  is MANDATORY even when size is mentioned at the end of a long multi-topic
  sentence.
  Example: "I want a wedding kurti for my sister's wedding party, budget 5000,
  my size is medium" -> raw_extracted['size'] = "medium" ONLY, absolutely NOT
  the full sentence. Strip everything except the size word itself.
  If you cannot isolate a single clean size word/phrase, leave "size" out
  entirely rather than returning any sentence fragment longer than 2 words.
- INTENT STRICTNESS: for the "intent" question specifically, ONLY extract a value if
  the user explicitly names one of its exact options or a clear direct synonym
  (e.g. "just a top" -> "Top / kurti only", "full outfit" -> "Complete outfit",
  "just looking around" -> "Just exploring"). Do NOT extract intent from a general
  product mention alone (e.g. "I want a saree" does NOT set intent, category/product
  words alone are not an intent signal). If no intent option is clearly and directly
  implied, LEAVE "intent" OUT ENTIRELY — never return the raw transcript sentence,
  a paraphrase, or any free text as the intent value. intent must always be one of
  its exact option strings, nothing else.
  - SUB-DETAIL QUESTION STRICTNESS: for any question whose id contains "_detail_"
  (e.g. occasion_detail_wedding), or any other single-select question with a
  fixed options list, ONLY extract a value if the user's words clearly map to
  ONE of that question's exact options or a direct synonym of one option.
  Do NOT extract the full sentence or a paraphrase as the answer just because
  the sentence is loosely on-topic. If the user's statement doesn't name a
  specific option (e.g. general wedding-related sentence with no mention of
  "reception", "sangeet", "mehendi" etc.), LEAVE that question out entirely —
  do not put the raw transcript into raw_extracted for it either.
  Example: "I want a wedding saree for my sister's wedding party under 5000"
  -> occasion_detail_wedding has NO specific sub-event named -> leave it out
  completely, do not extract anything for that question.
- PRODUCT CATEGORY EXTRACTION: separately from intent, if the user mentions a
  specific garment/product name (saree, kurta, lehenga, dress, dupatta, blouse,
  anarkali, kurti, salwar suit, gown, etc.) ANYWHERE in their statement, always
  capture it under "raw_extracted['product_category']" as the raw product word(s)
  mentioned — even if intent, occasion, or other fields are also being extracted
  from the same sentence. This is independent of intent and never blocks or
  replaces it. Do NOT put product names into intent.
- COLOR EXTRACTION: If the user mentions ANY color words (e.g. 'blue', 'white',
  'red', 'green', 'pink', 'navy', 'maroon', 'gold', 'silver', 'beige', etc.)
  anywhere in their statement, extract those exact color terms under the 'colour'
  question as raw_extracted, even if the colors are not in the predefined options.
  Examples: "my colour is blue and white" → raw_extracted['colour'] = 'blue and white',
  "I love gold" → raw_extracted['colour'] = 'gold',
  "blue saree" → raw_extracted['colour'] = 'blue'.
  Do NOT force-match to option labels like 'Warm tones' or 'Cool tones' unless
  the user explicitly says those exact phrases.
- Use EXACT option strings from each question's option list when the user answer matches an option.
- If the user's answer clearly belongs to a question but is not one of the provided options,
  return the raw text under "raw_extracted" for that question.
- If the answer is related to a question but does not contain one of the exact option phrases,
  prefer raw text in "raw_extracted" instead of forcing it into an option label.
- For multi-select questions, return an array of matched options or an array of raw values.
- For single-select questions, return a single option string or a raw answer string.
- For any question whose type is "slider" or "numeric" (e.g. budget), do NOT
  force-match to option labels unless the answer clearly matches one of those labels.
  Instead, if the utterance expresses a numeric budget range or limit, return that as
  "numeric_values": {{"<question_id>": {{"value": <int>, "modifier": "max"|"min"|"around"|null}}}}.
  Example:
    - "under 5000" => {{"value": 5000, "modifier": "max"}}
    - "maximum 5000" => {{"value": 5000, "modifier": "max"}}
    - "2500 to 5000" => return the exact option label "2500-5000" if possible.
    - "10000 or more" => return the exact option label "10000+" if possible.
- If nothing confidently matches a question from the list above, leave it out entirely.
- If the transcript is unclear, garbled, or unrelated to any listed question,
  return empty "extracted", "raw_extracted", and "rejected" objects — do not guess.

Respond ONLY with JSON, no markdown, no explanation:
{{
  "extracted": {{"<question_id>": "<option>" or ["<option>", ...]}},
  "raw_extracted": {{"<question_id>": "<raw answer>" or ["<raw answer>", ...]}},
  "rejected": {{"<question_id>": ["<option>", ...]}},
  "numeric_values": {{"<question_id>": {{"value": <int>, "modifier": "max"|"min"|"around"|null}}}}
}}
"""


def normalize_money_value(value):
    if isinstance(value, str):
        value = value.strip().lower().replace("₹", "").replace(",", "")
        value = value.replace("k", "000")
        try:
            return int(value)
        except ValueError:
            return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


SIZE_WORDS_PATTERN = r"\b(extra small|extra large|double extra large|small|medium|large|not sure|free size|xs|s|m|l|xl|xxl|2xl|3xl)\b"

SIZE_ALIASES = {
    "extra small": "XS", "xs": "XS",
    "small": "S", "s": "S",
    "medium": "M", "m": "M", "mid": "M",
    "large": "L", "l": "L",
    "extra large": "XL", "xl": "XL",
    "double extra large": "XXL", "xxl": "XXL", "2xl": "XXL", "3xl": "XXL",
    "free size": "Free", "free": "Free", "one size": "Free",
    "not sure": "Not sure",
}

FEMALE_ONLY_CATEGORY_KEYWORDS = [
    "saree", "sari", "half saree", "half-saree", "kanjivaram",
    "salwar kameez", "salwar suit", "salwar set", "kurti", "kurthi",
    "lehenga", "chaniya choli", "anarkali", "gown", "dupatta",
    "blouse", "wrap dress", "dress",
]

AMBIGUOUS_GENDER_CATEGORY_KEYWORDS = [
    "shirt", "kurta", "trouser", "pant", "dhoti", "cape set",
    "jacket", "blazer", "sweater", "t-shirt", "tshirt",
]

FREE_SIZE_CATEGORY_KEYWORDS = [
    "saree", "sari", "half saree", "half-saree", "dupatta",
    "stole", "mundu", "shawl", "chunni",
]

COLOUR_LABEL_TO_FAMILY = {
    "Warm tones": "warm",
    "Cool tones": "cool",
    "Neutrals": "neutral",
    "Pastels": "muted_pastel",
    "Bold & rich": "neon",
}


def normalize_size_text(raw_text):
    if not raw_text:
        return None
    text = raw_text.strip().lower()
    return SIZE_ALIASES.get(text)


def extract_size_from_text(transcript):
    if not transcript:
        return None
    match = re.search(SIZE_WORDS_PATTERN, transcript.lower())
    if match:
        return normalize_size_text(match.group(1))
    return None


def parse_budget_value(transcript):
    transcript = transcript.lower()
    transcript = transcript.replace("rs", "").replace("inr", "").strip()
    transcript = transcript.replace(",", "")

    if not transcript:
        return (None, None, None)

    ranges = re.findall(r"(\d{2,6})\s*(?:to|\-|and)\s*(\d{2,6})", transcript)
    if ranges:
        low, high = ranges[0]
        return (normalize_money_value(low), normalize_money_value(high), "range")

    max_match = re.search(r"(?:maximum|max|under|below|less than).*?(\d{2,6})", transcript)
    if max_match:
        return (None, normalize_money_value(max_match.group(1)), "max")

    min_match = re.search(r"(?:minimum|min|at least|over|more than).*?(\d{2,6})", transcript)
    if min_match:
        return (normalize_money_value(min_match.group(1)), None, "min")

    plus_match = re.search(r"(\d{2,6})\s*\+", transcript)
    if plus_match:
        return (normalize_money_value(plus_match.group(1)), None, "min")

    single_match = re.search(r"\b(\d{2,6})\b", transcript)
    if single_match:
        value = normalize_money_value(single_match.group(1))
        if value is not None:
            return (0, value, "max")

    return (None, None, None)


def option_text_in_transcript(option, transcript):
    if not transcript:
        return False
    norm = lambda text: re.sub(r"[^a-z0-9 ]", " ", text.lower())
    transcript_words = set(norm(transcript).split())
    option_words = [w for w in norm(option).split() if len(w) > 2]
    return any(word in transcript_words for word in option_words)


def sanitize_extracted_options(extracted, raw_extracted, remaining_questions, transcript):
    question_map = {q["id"]: q for q in remaining_questions}
    for qid, value in list(extracted.items()):
        q = question_map.get(qid)
        if not q or "options" not in q:
            continue

        if isinstance(value, str):
            if not option_text_in_transcript(value, transcript):
                raw_extracted.setdefault(qid, transcript)
                extracted.pop(qid, None)
        elif isinstance(value, list):
            valid_values = [item for item in value if option_text_in_transcript(item, transcript)]
            if valid_values:
                extracted[qid] = valid_values
            else:
                raw_extracted.setdefault(qid, transcript)
                extracted.pop(qid, None)
    return extracted, raw_extracted


def find_exact_option(remaining_questions, question_id, *candidates):
    q = next((q for q in remaining_questions if q["id"] == question_id), None)
    if not q or "options" not in q:
        return None
    lowered_candidates = [c.strip().lower() for c in candidates]
    for opt in q["options"]:
        if opt.strip().lower() in lowered_candidates:
            return opt
    return None


def apply_category_overrides(transcript, extracted, raw_extracted, remaining_questions, known_state=None):
    known_state = known_state or {}

    known_text_parts = [transcript]
    for key in ("category", "intent", "raw_category", "product_type"):
        value = known_state.get(key)
        if not value:
            continue
        if isinstance(value, list):
            known_text_parts.extend(str(v) for v in value)
        else:
            known_text_parts.append(str(value))

    text = " ".join(known_text_parts).lower()
    valid_ids = {q["id"] for q in remaining_questions}

    if "gender" in valid_ids and "gender" not in extracted:
        is_female_only = any(k in text for k in FEMALE_ONLY_CATEGORY_KEYWORDS)
        is_ambiguous = any(k in text for k in AMBIGUOUS_GENDER_CATEGORY_KEYWORDS)
        if is_female_only and not is_ambiguous:
            opt = find_exact_option(remaining_questions, "gender", "Myself (woman)")
            if opt:
                extracted["gender"] = opt
                raw_extracted.pop("gender", None)

    if "size" in valid_ids and "size" not in extracted:
        if any(k in text for k in FREE_SIZE_CATEGORY_KEYWORDS):
            opt = find_exact_option(
                remaining_questions, "size",
                "Free", "Free size", "One size", "One Size", "Not sure"
            )
            if opt:
                extracted["size"] = opt
                raw_extracted.pop("size", None)

    return extracted, raw_extracted


def bucket_numeric(question_id, value, modifier, remaining_questions):
    q = next((q for q in remaining_questions if q["id"] == question_id), None)
    if not q or "options" not in q:
        return None

    ceilings = {
        "Under 1000": 1000,
        "1000-2500": 2500,
        "2500-5000": 5000,
        "5000-10000": 10000,
        "10000+": float("inf"),
    }
    candidates = [(label, ceilings.get(label, float("inf"))) for label in q["options"]]
    candidates.sort(key=lambda x: x[1])

    if modifier == "max":
        for label, ceiling in candidates:
            if value <= ceiling:
                return label
        return candidates[-1][0]

    if modifier == "min":
        for label, ceiling in candidates:
            if ceiling >= value:
                return label
        return candidates[-1][0]

    # If modifier is around/null, choose the bucket that best contains the value.
    for label, ceiling in candidates:
        if value <= ceiling:
            return label
    return candidates[-1][0]


def extract_answers(client, transcript, remaining_questions, current_question_id, known_state):
    """
    Full pipeline: call Gemini with PARSE_PROMPT, then sanitize/normalize/
    bucket the result. Returns (extracted, raw_extracted, rejected,
    low_confidence, product_category).
    """
    valid_ids = {q["id"] for q in remaining_questions}

    current_q_text = next(
        (q["text"] for q in remaining_questions if q["id"] == current_question_id),
        "none specified"
    )

    prompt = PARSE_PROMPT.format(
        transcript=transcript,
        current_question=current_q_text,
        remaining_questions=json.dumps(remaining_questions, indent=2)
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt
    )

    raw = response.text.strip().replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"extracted": {}, "raw_extracted": {}, "rejected": {}, "numeric_values": {}}

    extracted = parsed.get("extracted", {})
    raw_extracted = parsed.get("raw_extracted", {})
    rejected = parsed.get("rejected", {})

    extracted, raw_extracted = sanitize_extracted_options(extracted, raw_extracted, remaining_questions, transcript)
    extracted, raw_extracted = apply_category_overrides(
        transcript, extracted, raw_extracted, remaining_questions, known_state=known_state
    )

    if "size" in raw_extracted:
        normalized_size = extract_size_from_text(raw_extracted["size"])
        if normalized_size:
            extracted["size"] = normalized_size
            raw_extracted.pop("size", None)
        else:
            raw_extracted.pop("size", None)

    for qid, nv in parsed.get("numeric_values", {}).items():
        if qid not in valid_ids:
            continue

        value = nv.get("value")
        modifier = nv.get("modifier")

        if value is None:
            continue

        if qid == "budget":
            if modifier == "max":
                extracted["budget"] = {"min": 0, "max": value}
                raw_extracted.pop("budget", None)
                continue
            elif modifier == "min":
                extracted["budget"] = {"min": value}
                raw_extracted.pop("budget", None)
                continue
            # modifier == "around" or None falls through to bucket_numeric below

        try:
            bucketed = bucket_numeric(qid, value, modifier, remaining_questions)
        except (KeyError, TypeError):
            bucketed = None
        if bucketed:
            extracted[qid] = bucketed
            raw_extracted.pop(qid, None)

    if current_question_id == "budget":
        low, high, modifier = parse_budget_value(transcript)
        if modifier is not None:
            if modifier == "range" and low is not None and high is not None:
                extracted["budget"] = {"min": low, "max": high}
                raw_extracted.pop("budget", None)
            elif modifier == "max" and high is not None:
                extracted["budget"] = {"min": 0, "max": high}
                raw_extracted.pop("budget", None)
            elif modifier == "min" and low is not None:
                extracted["budget"] = {"min": low}
                raw_extracted.pop("budget", None)
            elif modifier == "exact" and low is not None and high is not None:
                extracted["budget"] = {"min": low, "max": high}
                raw_extracted.pop("budget", None)

    product_category = raw_extracted.pop("product_category", None)

    extracted = {k: v for k, v in extracted.items() if k in valid_ids}
    raw_extracted = {k: v for k, v in raw_extracted.items() if k in valid_ids and k not in extracted}
    rejected = {k: v for k, v in rejected.items() if k in valid_ids}
    # Temporary test mode: use Gemini's extracted answers directly.
    # Keep the return shape expected by the existing frontend.
    extracted.update(raw_extracted)
    raw_extracted = {}
    low_confidence = {}

    print(f"\n{'='*80}")
    print(f"[QUERY_1] FRONTEND VOICE QUERY (original transcript):")
    print(f"  {transcript!r}")
    print(f"{'='*80}")
    print(f"[parse-answer] heard: {transcript!r} -> extracted: {extracted} raw_extracted: {raw_extracted} rejected: {rejected}")

    return extracted, raw_extracted, rejected, low_confidence, product_category