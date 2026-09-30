"""Validate extracted answers in one batched Gemini call."""
import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))

MODEL = os.environ.get("GEMINI_VALIDATION_MODEL", "gemini-3.5-flash-lite")
SCORE_THRESHOLD = 60


BATCH_VALIDATE_PROMPT = """You are a strict input-validation engine for a fashion kiosk.

Below is a list of question-answer pairs the customer just gave. Score EACH one
independently from 0 to 100 on how well it validly answers its own question:
- 90-100: clearly correct, matches an option or a sane value, no contradiction.
- 60-89: acceptable but slightly vague, partial, or loosely related.
- 0-59: wrong question type, contradicts a previous answer, empty/nonsense, or unrelated.

SPECIAL RULE for "colour" question: a specific color name (gold, blue, maroon,
navy, pastel pink, etc.) is a VALID answer even if it doesn't match any option
label word-for-word (Warm tones, Cool tones, Neutrals, etc.) — score it 80-95.
Only score low if colour answer is empty, contradicts a prior colour choice, or
totally unrelated to colour.

STRICT OPTION MATCHING (default rule, applies to EVERY OTHER question that has
a fixed "options" list — occasion, style, fit, gender, size, intent, budget, etc.):
The answer must be either:
  (a) an exact option string, or
  (b) a clear, unambiguous synonym/paraphrase of ONE specific option
      (e.g. "reception party" -> "Wedding / Reception" is fine,
       "puja at home" -> "Festival / Puja" is fine).
If the answer does NOT map to any specific option — it names something outside
the option list entirely (e.g. "annual day", "sports day", "graduation" when
options are Wedding/Festival/Party/Office/Casual/Photoshoot/Travel/Religious/
Birthday/Other) — this is NOT a valid answer for that question. Score it 0-30
and it must be REJECTED, regardless of how confident, well-formed, or
"occasion-sounding" the phrase is. Being a plausible real-world event is not
enough — it must correspond to one of the offered options. Do NOT be lenient
just because the answer sounds specific or genuine.

CATCH-ALL OPTION RULE: if that question's option list contains a literal
catch-all option (e.g. "Other / Tell me", "Other", "Not sure"), then:
  - If the user's answer directly names or clearly means that catch-all itself
    (e.g. says "other", "something else", "not sure", "tell you later") ->
    this IS an exact match to that option (case (a) above) -> score 90-100,
    ACCEPT. Do NOT reject this and do NOT generate a rephrase for it.
  - If the user's answer is some other unmatched-but-plausible value (e.g. an
    event/style/etc. not covered by any option) -> it MAY map to the catch-all
    option instead of being fully rejected, score 60-75, ACCEPT.
Only use the second case when the fallback option is present in THAT
question's own options — never invent or borrow a catch-all from a different
question.

STYLE-SPECIFIC EXAMPLES (style question options: Traditional/Classic ethnic,
Indo-western, Modern/Minimal ethnic, Trendy/Bold, Comfortable first,
Premium/Luxury, Cute/Feminine):
- "something nice", "whatever looks good", "you decide", "anything stylish"
  -> VAGUE, does not map to any specific option -> score 10-30, REJECT.
- "royal look", "rich and expensive" -> maps to "Premium / Luxury" -> score 80-90, ACCEPT.
- "mixed western-indian look" -> maps to "Indo-western" -> score 85-95, ACCEPT.
- "simple, not too much" -> maps to "Modern / Minimal ethnic" -> score 75-85, ACCEPT.

NO-CATCH-ALL QUESTIONS: many questions (e.g. gender, options: "Myself (woman)",
"Myself (man)", "My child") have NO "Other"/"Not sure" fallback option at all.
For these, a vague or unmatched answer (e.g. "other", "not sure", "whatever")
is REJECTED (score 0-30) exactly like any other unmatched answer — there is no
option to fall back onto. The rephrase must still be generated, and must list
out THIS question's actual own options plainly so the user can choose one.
Example: user said "other" for gender (options: Myself (woman), Myself (man),
My child) -> score 10, REJECT -> rephrase: "Just to confirm — is this outfit
for a woman, a man, or for your child?"
Example: user said "not sure" for fit (options: Flowy & relaxed, Balanced,
Structured & fitted) -> score 15, REJECT -> rephrase: "No worries! Would you
prefer something flowy and relaxed, balanced, or more structured and fitted?"

BUDGET-SPECIFIC EXAMPLE (budget question options: Under 1000, 1000-2500,
2500-5000, 5000-10000, 10000+): the rephrase must reference these actual
money ranges — never invent an unrelated qualitative question (e.g. do NOT
ask "is this a special occasion or everyday purchase", "is this a gift or for
yourself" — that is NOT one of the options and is off-topic).
Example: user said "not too expensive" for budget -> score 20, REJECT ->
rephrase: "No problem — roughly what range works? Under 1000, 1000 to 2500,
2500 to 5000, 5000 to 10000, or above 10000?"
Example: user said "no budget in mind" for budget -> score 15, REJECT ->
rephrase: "That's okay! Just pick a rough range — under 1000, 1000-2500,
2500-5000, 5000-10000, or 10000 and above?"

Previously confirmed answers (for contradiction check across ALL items): {known_state}

Question-Answer pairs to score:
{pairs_json}

For EACH pair, give a score and ONE short reason (max 8 words).

REPHRASE ON REJECT: if score < 60, also generate a short, friendly follow-up
question that references what they said, to avoid sounding repetitive.
CRITICAL: the rephrase MUST stay strictly about THIS SAME question and MUST
ONLY reference options from THIS question's own "options" list — never mention
or ask about any other question's topic (e.g. if this is the occasion
question, never ask about gender/size/style/budget; only ask them to choose
among occasion's own options like wedding, festival, party, etc.). Ground the
rephrase's option suggestions in the literal "options" list provided for that
pair — do not invent categories that aren't in that list.
Example: user said "annual day" for occasion (options include Wedding,
Festival, Party, Office, Casual, Photoshoot, Travel, Religious, Birthday,
Other) -> rephrase: "Got it, an annual day event! Is this more like a
wedding, festival, party, or something else?"
Example: user said "gothic vampire look" for style (options include
Trendy/Bold, Premium/Luxury, etc.) -> rephrase: "I like the creative vibe!
Would you say that's closer to Trendy/Bold, or Premium/Luxury?"

Respond ONLY with a JSON array, no markdown, same order as input, one object per pair:
[
  {{"question_id": "<id>", "score": <int 0-100>, "reason": "<short reason>",
    "rephrase": "<if score<60, a natural follow-up question referencing their answer,
    grounded only in THIS question's own options, else null>"}},
  ...
]
"""


def validate_batch(extracted: dict, remaining_questions: list, known_state: dict = None) -> dict:
    """
    extracted: {qid: value, ...} — ALL answers to validate (merged extracted+raw_extracted)
    remaining_questions: [{"id","text","type","options"}, ...] eligible questions
    known_state: current confirmed answers, for contradiction check

    Returns:
      {
        "accepted": {qid: value, ...},
        "rejected": {qid: {"value":..., "score":..., "reason":...}, ...}
      }
    """
    known_state = known_state or {}
    question_map = {q["id"]: q for q in remaining_questions}

    # build pairs list, skip anything not an eligible question
    pairs = []
    for qid, value in extracted.items():
        question = question_map.get(qid)
        if not question:
            continue
        pairs.append({
            "question_id": qid,
            "question_text": question.get("text", ""),
            "question_type": question.get("type", ""),
            "options": question.get("options", []) or "free text",
            "answer": value,
        })

    if not pairs:
        return {"accepted": {}, "rejected": {}}

    prompt = BATCH_VALIDATE_PROMPT.format(
        known_state=json.dumps(known_state),
        pairs_json=json.dumps(pairs, indent=2),
    )

    scores_by_qid = {}
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        raw = (response.text or "").strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError("Expected a JSON array of answer scores")
        for item in parsed:
            scores_by_qid[item["question_id"]] = {
                "score": int(item.get("score", 0)),
                "reason": item.get("reason", ""),
                "rephrase": item.get("rephrase"),
            }
    except Exception as e:
        print(f"[gemini_validator] batch scoring failed: {e}")
        for p in pairs:
            scores_by_qid[p["question_id"]] = {"score": 0, "reason": "validation_call_failed", "rephrase": None}

    accepted = {}
    rejected = {}
    for qid, value in extracted.items():
        if qid not in question_map:
            continue
        result = scores_by_qid.get(qid, {"score": 0, "reason": "no_score_returned"})
        if result["score"] >= SCORE_THRESHOLD:
            accepted[qid] = value
        else:
            rejected[qid] = {
                "value": value,
                "score": result["score"],
                "reason": result["reason"],
                "rephrase": result.get("rephrase"),
            }

    return {"accepted": accepted, "rejected": rejected}