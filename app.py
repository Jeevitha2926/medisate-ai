import streamlit as st
import requests
import re
from itertools import combinations

# ============================================================
# MEDISATE AI
# Medicine Information & Interaction Assistant
# ============================================================

st.set_page_config(
    page_title="MediSate AI",
    page_icon="💊",
    layout="wide"
)

# ============================================================
# CONFIGURATION
# ============================================================

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
OPENFDA_BASE = "https://api.fda.gov/drug/label.json"

REQUEST_TIMEOUT = 15


# ============================================================
# PAGE STYLE
# ============================================================

st.markdown(
    """
    <style>
    .main {
        max-width: 1100px;
        margin: auto;
    }

    .title {
        font-size: 46px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 18px;
        margin-bottom: 25px;
    }

    .section-title {
        font-size: 30px;
        font-weight: 750;
        margin-top: 30px;
        margin-bottom: 15px;
    }

    .medicine-title {
        font-size: 28px;
        font-weight: 750;
        margin-top: 25px;
        margin-bottom: 10px;
    }

    div.stButton > button {
        width: 100%;
        height: 50px;
        font-size: 17px;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# COMMON MEDICINE ALIASES
# ============================================================

MEDICINE_ALIASES = {
    "paracetamol": "acetaminophen",
    "acetaminol": "acetaminophen",
    "tylenol": "acetaminophen",

    "advil": "ibuprofen",
    "motrin": "ibuprofen",

    "acetylsalicylic acid": "aspirin",

    "aleve": "naproxen",

    "voltaren": "diclofenac",

    "zyrtec": "cetirizine",

    "claritin": "loratadine"
}


# ============================================================
# SESSION CACHE
# ============================================================

if "medicine_cache" not in st.session_state:
    st.session_state.medicine_cache = {}


# ============================================================
# BASIC TEXT CLEANING
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    if isinstance(value, list):
        value = " ".join(str(x) for x in value)

    value = str(value)

    value = value.replace("\n", " ")

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# DETECT DOSAGE FORM
# ============================================================

def extract_dosage_form(name):

    text = clean_text(name).lower()

    forms = [
        ("eye drops", "ophthalmic"),
        ("ophthalmic", "ophthalmic"),

        ("ear drops", "otic"),
        ("otic", "otic"),

        ("oral suspension", "oral suspension"),
        ("suspension", "suspension"),

        ("oral solution", "oral solution"),
        ("solution", "solution"),

        ("syrup", "syrup"),
        ("syrups", "syrup"),

        ("tablet", "tablet"),
        ("tablets", "tablet"),
        ("tab", "tablet"),
        ("tabs", "tablet"),

        ("capsule", "capsule"),
        ("capsules", "capsule"),
        ("cap", "capsule"),
        ("caps", "capsule"),

        ("injection", "injection"),
        ("injectable", "injection"),

        ("cream", "cream"),
        ("creams", "cream"),

        ("ointment", "ointment"),
        ("ointments", "ointment"),

        ("gel", "gel"),
        ("gels", "gel"),

        ("lotion", "lotion"),
        ("lotions", "lotion"),

        ("powder", "powder"),
        ("powders", "powder"),

        ("spray", "spray"),
        ("sprays", "spray"),

        ("inhaler", "inhaler"),
        ("inhalers", "inhaler"),

        ("patch", "patch"),
        ("patches", "patch"),

        ("lozenge", "lozenge"),
        ("lozenges", "lozenge"),

        ("mouthwash", "mouthwash")
    ]

    for keyword, normalized_form in forms:

        if re.search(
            rf"\b{re.escape(keyword)}\b",
            text
        ):
            return normalized_form

    return ""


# ============================================================
# NORMALIZE MEDICINE NAME
# ============================================================

def normalize_name(name):

    name = clean_text(name).lower()

    name = name.replace("-", " ")
    name = name.replace("_", " ")

    # Remove text inside brackets
    name = re.sub(
        r"\([^)]*\)",
        "",
        name
    )

    dosage_forms = [
        "oral suspension",
        "oral solution",
        "eye drops",
        "ear drops",
        "ophthalmic",
        "otic",

        "tablet",
        "tablets",
        "tab",
        "tabs",

        "capsule",
        "capsules",
        "cap",
        "caps",

        "syrup",
        "syrups",

        "suspension",
        "suspensions",

        "solution",
        "solutions",

        "drops",
        "drop",

        "injection",
        "injectable",

        "cream",
        "creams",

        "ointment",
        "ointments",

        "gel",
        "gels",

        "lotion",
        "lotions",

        "powder",
        "powders",

        "spray",
        "sprays",

        "inhaler",
        "inhalers",

        "patch",
        "patches",

        "lozenge",
        "lozenges",

        "granules",
        "granule",

        "mouthwash"
    ]

    for form in sorted(
        dosage_forms,
        key=len,
        reverse=True
    ):

        name = re.sub(
            rf"\b{re.escape(form)}\b",
            " ",
            name
        )

    # Remove concentrations such as:
    # 250mg/5ml
    # 100 mg / 5 ml

    name = re.sub(
        r"\b\d+(?:\.\d+)?\s*"
        r"(?:mg|mcg|g|ml)"
        r"\s*/\s*"
        r"\d+(?:\.\d+)?\s*"
        r"(?:mg|mcg|g|ml)\b",
        " ",
        name,
        flags=re.IGNORECASE
    )

    # Remove strengths such as:
    # 500mg
    # 5ml
    # 10mg

    name = re.sub(
        r"\b\d+(?:\.\d+)?\s*"
        r"(?:mg|mcg|g|kg|ml|iu|%)\b",
        " ",
        name,
        flags=re.IGNORECASE
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    )

    return name.strip()


# ============================================================
# GET CANONICAL MEDICINE NAME
# ============================================================

def get_canonical_name(name):

    normalized = normalize_name(name)

    normalized = re.sub(
        r"\b("
        r"tablet|tablets|tab|tabs|"
        r"capsule|capsules|cap|caps|"
        r"syrup|syrups|"
        r"suspension|suspensions|"
        r"solution|solutions|"
        r"drops|drop|"
        r"ophthalmic|otic|"
        r"injection|injectable|"
        r"cream|creams|"
        r"ointment|ointments|"
        r"gel|gels|"
        r"lotion|lotions|"
        r"powder|powders|"
        r"spray|sprays|"
        r"inhaler|inhalers|"
        r"patch|patches|"
        r"lozenge|lozenges|"
        r"granules|granule|"
        r"mouthwash"
        r")\b",
        " ",
        normalized,
        flags=re.IGNORECASE
    )

    normalized = re.sub(
        r"\b\d+(?:\.\d+)?\s*"
        r"(?:mg|mcg|g|kg|ml|iu|%)\b",
        " ",
        normalized,
        flags=re.IGNORECASE
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized
    ).strip()

    return MEDICINE_ALIASES.get(
        normalized,
        normalized
    )


# ============================================================
# RXNORM MEDICINE SEARCH
# ============================================================

@st.cache_data(
    ttl=86400,
    show_spinner=False
)
def get_rxnorm_rxcui(medicine):

    medicine = get_canonical_name(
        medicine
    )

    try:

        response = requests.get(
            f"{RXNORM_BASE}/rxcui.json",
            params={
                "name": medicine,
                "search": "2"
            },
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            return None

        data = response.json()

        ids = (
            data
            .get("idGroup", {})
            .get("rxnormId", [])
        )

        if not ids:
            return None

        return str(ids[0])

    except Exception:

        return None


# ============================================================
# RXNORM PROPERTIES
# ============================================================

@st.cache_data(
    ttl=86400,
    show_spinner=False
)
def get_rxnorm_properties(rxcui):

    if not rxcui:
        return {}

    try:

        response = requests.get(
            f"{RXNORM_BASE}/rxcui/{rxcui}/properties.json",
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            return {}

        return (
            response.json()
            .get("properties", {})
        )

    except Exception:

        return {}


# ============================================================
# CHOOSE BEST FDA LABEL
# ============================================================

def choose_best_fda_label(
    results,
    medicine,
    dosage_form=""
):

    medicine = normalize_name(
        medicine
    )

    scored = []

    for label in results:

        score = 0

        openfda = label.get(
            "openfda",
            {}
        )

        names = []

        for field in [
            "generic_name",
            "substance_name",
            "brand_name"
        ]:

            values = openfda.get(
                field,
                []
            )

            if not isinstance(
                values,
                list
            ):
                values = [values]

            for value in values:

                names.append(
                    clean_text(
                        value
                    ).lower()
                )

        combined_names = " ".join(
            names
        )

        normalized_names = normalize_name(
            combined_names
        )

        # Medicine name match
        if medicine in normalized_names:
            score += 30

        # Dosage form matching
        if dosage_form:

            form_keywords = {

                "ophthalmic": [
                    "ophthalmic",
                    "eye",
                    "eye drops"
                ],

                "otic": [
                    "otic",
                    "ear"
                ],

                "syrup": [
                    "syrup"
                ],

                "suspension": [
                    "suspension"
                ],

                "oral suspension": [
                    "oral suspension",
                    "suspension"
                ],

                "solution": [
                    "solution"
                ],

                "oral solution": [
                    "oral solution",
                    "solution"
                ],

                "tablet": [
                    "tablet"
                ],

                "capsule": [
                    "capsule"
                ],

                "injection": [
                    "injection",
                    "injectable"
                ],

                "cream": [
                    "cream"
                ],

                "ointment": [
                    "ointment"
                ],

                "gel": [
                    "gel"
                ],

                "inhaler": [
                    "inhaler"
                ],

                "spray": [
                    "spray"
                ],

                "patch": [
                    "patch"
                ]
            }

            keywords = form_keywords.get(
                dosage_form,
                [dosage_form]
            )

            label_text = clean_text(
                str(label)
            ).lower()

            matched = False

            for keyword in keywords:

                if keyword in combined_names:

                    score += 40
                    matched = True
                    break

            if not matched:

                for keyword in keywords:

                    if keyword in label_text:

                        score += 15
                        break

        scored.append(
            (
                score,
                label
            )
        )

    if not scored:
        return None

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return scored[0][1]


# ============================================================
# FETCH FDA INFORMATION
# ============================================================

@st.cache_data(
    ttl=21600,
    show_spinner=False
)
def get_fda_label(
    medicine,
    dosage_form=""
):

    canonical = get_canonical_name(
        medicine
    )

    searches = [
        f'openfda.generic_name:"{canonical}"',
        f'openfda.substance_name:"{canonical}"',
        f'openfda.brand_name:"{canonical}"'
    ]

    for search in searches:

        try:

            response = requests.get(
                OPENFDA_BASE,
                params={
                    "search": search,
                    "limit": 100
                },
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code != 200:
                continue

            results = (
                response.json()
                .get("results", [])
            )

            if results:

                return choose_best_fda_label(
                    results,
                    canonical,
                    dosage_form
                )

        except Exception:

            continue

    return None


# ============================================================
# GET FDA FIELD
# ============================================================

def get_label_field(
    label,
    field
):

    if not label:
        return ""

    return clean_text(
        label.get(field, "")
    )


# ============================================================
# EXTRACT ALL IMPORTANT FDA INFORMATION
# ============================================================

def extract_label_sections(label):

    if not label:

        return {
            "purpose": "",
            "indications": "",
            "warnings": "",
            "side_effects": "",
            "contraindications": "",
            "dosage": "",
            "interactions": "",
            "precautions": "",
            "populations": "",
            "pregnancy": "",
            "pediatric_use": "",
            "geriatric_use": "",
            "overdosage": "",
            "clinical_pharmacology": "",
            "description": "",
            "mechanism": ""
        }

    return {

        "purpose":
            get_label_field(
                label,
                "purpose"
            ),

        "indications":
            get_label_field(
                label,
                "indications_and_usage"
            ),

        "warnings":
            get_label_field(
                label,
                "warnings"
            ),

        "side_effects":
            get_label_field(
                label,
                "adverse_reactions"
            ),

        "contraindications":
            get_label_field(
                label,
                "contraindications"
            ),

        "dosage":
            get_label_field(
                label,
                "dosage_and_administration"
            ),

        "interactions":
            get_label_field(
                label,
                "drug_interactions"
            ),

        "precautions":
            get_label_field(
                label,
                "precautions"
            ),

        "populations":
            get_label_field(
                label,
                "use_in_specific_populations"
            ),

        "pregnancy":
            get_label_field(
                label,
                "pregnancy"
            ),

        "pediatric_use":
            get_label_field(
                label,
                "pediatric_use"
            ),

        "geriatric_use":
            get_label_field(
                label,
                "geriatric_use"
            ),

        "overdosage":
            get_label_field(
                label,
                "overdosage"
            ),

        "clinical_pharmacology":
            get_label_field(
                label,
                "clinical_pharmacology"
            ),

        "description":
            get_label_field(
                label,
                "description"
            ),

        "mechanism":
            get_label_field(
                label,
                "mechanism_of_action"
            )
    }


# ============================================================
# ANALYZE MEDICINE
# ============================================================

def analyze_medicine(
    user_medicine
):

    original = clean_text(
        user_medicine
    )

    dosage_form = extract_dosage_form(
        original
    )

    canonical = get_canonical_name(
        original
    )

    # Include dosage form in cache key.
    # This prevents tablet and eye-drop labels
    # from being mixed together.

    cache_key = (
        f"{canonical}|{dosage_form}"
    )

    if cache_key in st.session_state.medicine_cache:

        return (
            st.session_state
            .medicine_cache[cache_key]
        )

    # RxNorm
    rxcui = get_rxnorm_rxcui(
        canonical
    )

    properties = get_rxnorm_properties(
        rxcui
    )

    # FDA
    fda_label = get_fda_label(
        canonical,
        dosage_form
    )

    sections = extract_label_sections(
        fda_label
    )

    if properties:

        standard_name = clean_text(
            properties.get(
                "name",
                ""
            )
        )

    else:

        standard_name = (
            canonical.title()
        )

    result = {

        "input_name":
            original,

        "canonical_name":
            canonical,

        "dosage_form":
            dosage_form,

        "rxcui":
            rxcui,

        "standard_name":
            standard_name,

        "properties":
            properties,

        "fda_label":
            fda_label,

        "sections":
            sections,

        "identified":
            bool(
                rxcui or fda_label
            )
    }

    st.session_state.medicine_cache[
        cache_key
    ] = result

    return result


# ============================================================
# SEARCH FOR INTERACTION EVIDENCE
# ============================================================

def search_label_for_interaction(
    medicine_a,
    medicine_b
):

    canonical_a = get_canonical_name(
        medicine_a
    )

    canonical_b = get_canonical_name(
        medicine_b
    )

    dosage_form_a = extract_dosage_form(
        medicine_a
    )

    try:

        response = requests.get(
            OPENFDA_BASE,
            params={
                "search":
                    f'openfda.generic_name:"{canonical_a}"',
                "limit": 100
            },
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            return None

        results = (
            response.json()
            .get("results", [])
        )

        if not results:
            return None

        label = choose_best_fda_label(
            results,
            canonical_a,
            dosage_form_a
        )

        if not label:
            return None

        fields = [
            "drug_interactions",
            "warnings",
            "precautions",
            "contraindications",
            "adverse_reactions",
            "information_for_patients"
        ]

        text_parts = []

        for field in fields:

            value = label.get(
                field,
                ""
            )

            if isinstance(
                value,
                list
            ):

                text_parts.extend(
                    str(x)
                    for x in value
                )

            elif value:

                text_parts.append(
                    str(value)
                )

        text = " ".join(
            text_parts
        ).lower()

        terms = {
            canonical_b,
            clean_text(
                medicine_b
            ).lower()
        }

        for term in terms:

            if term and term in text:

                index = text.find(
                    term
                )

                start = max(
                    0,
                    index - 300
                )

                end = min(
                    len(text),
                    index + 700
                )

                return text[
                    start:end
                ]

    except Exception:

        return None

    return None


# ============================================================
# CHECK INTERACTIONS
# ============================================================

def check_interactions(
    medicines
):

    results = []

    for medicine_a, medicine_b in combinations(
        medicines,
        2
    ):

        evidence_a = (
            search_label_for_interaction(
                medicine_a,
                medicine_b
            )
        )

        evidence_b = (
            search_label_for_interaction(
                medicine_b,
                medicine_a
            )
        )

        if evidence_a or evidence_b:

            results.append(
                {
                    "medicine_a":
                        medicine_a,

                    "medicine_b":
                        medicine_b,

                    "found":
                        True,

                    "evidence":
                        evidence_a
                        if evidence_a
                        else evidence_b
                }
            )

        else:

            results.append(
                {
                    "medicine_a":
                        medicine_a,

                    "medicine_b":
                        medicine_b,

                    "found":
                        False,

                    "evidence":
                        ""
                }
            )

    return results


# ============================================================
# OPENAI CLIENT
# ============================================================

def get_openai_client():

    try:

        from openai import OpenAI

        api_key = ""

        try:

            api_key = st.secrets.get(
                "OPENAI_API_KEY",
                ""
            )

        except Exception:

            api_key = ""

        if not api_key:

            return None

        return OpenAI(
            api_key=api_key
        )

    except Exception:

        return None


# ============================================================
# AI MEDICINE SUMMARY
# ============================================================

def summarize_with_ai(
    medicine_result,
    interaction_evidence=""
):

    client = get_openai_client()

    if client is None:
        return None

    sections = (
        medicine_result["sections"]
    )

    source_information = f"""
Medicine:
{medicine_result["standard_name"]}

Active ingredient:
{medicine_result["canonical_name"]}

Dosage form:
{medicine_result["dosage_form"]}

Purpose:
{sections["purpose"]}

Indications:
{sections["indications"]}

Warnings:
{sections["warnings"]}

Contraindications:
{sections["contraindications"]}

Side effects:
{sections["side_effects"]}

Interaction information:
{sections["interactions"]}

Additional interaction evidence:
{interaction_evidence or "None found."}
"""

    prompt = f"""
You are the medicine-information
summarization component of MediSate AI.

The information below was retrieved
from medicine reference databases.

Create a very short,
patient-friendly summary.

IMPORTANT:

1. Use only information in the supplied data.
2. Do not invent medical facts.
3. Do not diagnose.
4. Do not prescribe.
5. Do not recommend starting or stopping medicine.
6. Do not recommend a dose.
7. Do not invent interactions.
8. Use short bullet points.
9. Maximum 5 side effects.
10. Maximum 4 warnings.
11. Maximum 4 caution points.
12. Keep the answer under 180 words.

Return:

### 🎯 Used for
- Short bullet
- Short bullet

### 🩺 Important side effects
- Short bullet
- Short bullet
- Short bullet

### ⚠️ Important warnings
- Short bullet
- Short bullet

### 🚫 Avoid / use caution
- Short bullet
- Short bullet

### 💡 Key takeaway
- One short sentence

Retrieved information:

{source_information}
"""

    try:

        response = client.responses.create(
            model="gpt-5.6-luna",
            input=prompt,
            max_output_tokens=450
        )

        answer = clean_text(
            response.output_text
        )

        if not answer:
            return None

        return answer

    except Exception:

        return None


# ============================================================
# FALLBACK SUMMARY
# ============================================================

def simple_fallback_summary(
    result
):

    sections = result[
        "sections"
    ]

    output = []

    # USED FOR
    output.append(
        "### 🎯 Used for"
    )

    purpose = (
        sections["purpose"]
        or
        sections["indications"]
    )

    if purpose:

        sentences = re.split(
            r'(?<=[.!?])\s+',
            purpose
        )

        text = " ".join(
            sentences[:2]
        )

        text = clean_text(
            text
        )

        if len(text) > 300:

            text = (
                text[:300]
                + "..."
            )

        output.append(
            f"- {text}"
        )

    else:

        output.append(
            "- No concise usage information was found."
        )

    # SIDE EFFECTS
    output.append(
        "### 🩺 Important side effects"
    )

    side_effect_text = (
        sections["side_effects"]
    )

    common_terms = [
        "headache",
        "dizziness",
        "nausea",
        "vomiting",
        "diarrhea",
        "diarrhoea",
        "abdominal pain",
        "rash",
        "fatigue",
        "insomnia",
        "drowsiness",
        "constipation",
        "stomach pain"
    ]

    found = []

    lower_text = (
        side_effect_text.lower()
    )

    for term in common_terms:

        if term in lower_text:

            found.append(
                term
            )

    if found:

        for item in list(
            dict.fromkeys(found)
        )[:5]:

            output.append(
                f"- {item.title()}"
            )

    else:

        output.append(
            "- Refer to the official label for complete information."
        )

    # WARNINGS
    output.append(
        "### ⚠️ Important warnings"
    )

    warning_text = (
        sections["warnings"]
    )

    if warning_text:

        sentences = re.split(
            r'(?<=[.!?])\s+',
            warning_text
        )

        count = 0

        for sentence in sentences:

            sentence = clean_text(
                sentence
            )

            if len(sentence) < 30:
                continue

            if len(sentence) > 170:

                sentence = (
                    sentence[:170]
                    + "..."
                )

            output.append(
                f"- {sentence}"
            )

            count += 1

            if count >= 4:
                break

    else:

        output.append(
            "- No concise warning information was found."
        )

    # CAUTIONS
    output.append(
        "### 🚫 Avoid / use caution"
    )

    contraindication_text = (
        sections["contraindications"]
    )

    if contraindication_text:

        sentences = re.split(
            r'(?<=[.!?])\s+',
            contraindication_text
        )

        count = 0

        for sentence in sentences:

            sentence = clean_text(
                sentence
            )

            if len(sentence) < 30:
                continue

            if len(sentence) > 170:

                sentence = (
                    sentence[:170]
                    + "..."
                )

            output.append(
                f"- {sentence}"
            )

            count += 1

            if count >= 4:
                break

    else:

        output.append(
            "- Ask a doctor or pharmacist if you are unsure."
        )

    # TAKEAWAY
    output.append(
        "### 💡 Key takeaway"
    )

    output.append(
        "- Use this information for education and verify it with a healthcare professional."
    )

    return "\n".join(
        output
    )


# ============================================================
# AI INTERACTION SUMMARY
# ============================================================

def summarize_interaction_with_ai(
    medicine_a,
    medicine_b,
    evidence
):

    client = get_openai_client()

    if client is None:
        return None

    prompt = f"""
You are MediSate AI's
interaction summarizer.

Medicines:
{medicine_a}
{medicine_b}

Retrieved label evidence:
{evidence}

Explain only what is supported
by the evidence.

Rules:

- Do not invent an interaction.
- Do not claim the medicines are definitely safe.
- Do not diagnose.
- Do not recommend changing medication.
- Use simple language.
- Keep under 100 words.

Return:

### 🔍 Interaction result
- One or two short sentences.

### ⚠️ What this means
- One or two short sentences.

### 👨‍⚕️ Safety
- One short sentence recommending professional verification.
"""

    try:

        response = client.responses.create(
            model="gpt-5.6-luna",
            input=prompt,
            max_output_tokens=250
        )

        answer = clean_text(
            response.output_text
        )

        if not answer:
            return None

        return answer

    except Exception:

        return None


# ============================================================
# DISPLAY MEDICINE
# ============================================================

def display_medicine(
    result,
    interaction_evidence=""
):

    st.markdown(
        f"""
        <div class="medicine-title">
        💊 {result["input_name"].title()}
        </div>
        """,
        unsafe_allow_html=True
    )

    if result["identified"]:

        st.success(
            "Medicine identified."
        )

    else:

        st.warning(
            "This medicine could not be confidently identified."
        )

    st.markdown(
        f"**Active ingredient:** "
        f"{result['canonical_name'].title()}"
    )

    if result["dosage_form"]:

        st.markdown(
            f"**Dosage form:** "
            f"{result['dosage_form'].title()}"
        )

    if result["rxcui"]:

        st.caption(
            f"RxNorm ID: {result['rxcui']}"
        )

    # AI SUMMARY
    with st.spinner(
        "Creating medicine summary..."
    ):

        summary = summarize_with_ai(
            result,
            interaction_evidence
        )

    if summary:

        st.markdown(
            "### 🤖 AI Summary"
        )

        st.markdown(
            summary
        )

    else:

        st.markdown(
            "### 📋 Medicine Summary"
        )

        st.markdown(
            simple_fallback_summary(
                result
            )
        )

    # FULL FDA INFORMATION
    with st.expander(
        "📚 Retrieved medicine database information"
    ):

        sections = result[
            "sections"
        ]

        fields = {

            "Purpose":
                sections["purpose"],

            "Indications":
                sections["indications"],

            "Warnings":
                sections["warnings"],

            "Side Effects":
                sections["side_effects"],

            "Contraindications":
                sections["contraindications"],

            "Dosage and Administration":
                sections["dosage"],

            "Drug Interactions":
                sections["interactions"],

            "Precautions":
                sections["precautions"],

            "Use in Specific Populations":
                sections["populations"],

            "Pregnancy":
                sections["pregnancy"],

            "Pediatric Use":
                sections["pediatric_use"],

            "Geriatric Use":
                sections["geriatric_use"],

            "Overdosage":
                sections["overdosage"],

            "Clinical Pharmacology":
                sections["clinical_pharmacology"],

            "Description":
                sections["description"],

            "Mechanism of Action":
                sections["mechanism"]
        }

        for title, value in fields.items():

            if value:

                st.markdown(
                    f"**{title}**"
                )

                st.write(
                    value
                )

                st.divider()

    # RXNORM
    with st.expander(
        "🔬 RxNorm information"
    ):

        if result["properties"]:

            st.json(
                result["properties"]
            )

        else:

            st.write(
                "No additional RxNorm information found."
            )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="title">💊 MediSate AI</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="subtitle">
    Medicine Information & Interaction Assistant
    </div>
    """,
    unsafe_allow_html=True
)

st.warning(
    "⚠️ Educational information only. "
    "This tool does not diagnose conditions, "
    "prescribe medicines, or replace a doctor or pharmacist."
)


# ============================================================
# MEDICINE INPUT
# ============================================================

st.markdown(
    '<div class="section-title">'
    '💊 Enter your medicines'
    '</div>',
    unsafe_allow_html=True
)

st.write(
    "Enter medicine names separated by commas."
)

medicine_input = st.text_input(
    "Medicine names",
    placeholder="Example: paracetamol, ibuprofen",
    label_visibility="collapsed"
)

analyze_button = st.button(
    "🔎 Analyze Medicines"
)


# ============================================================
# MAIN PROGRAM
# ============================================================

if analyze_button:

    if not medicine_input.strip():

        st.error(
            "Please enter at least one medicine name."
        )

        st.stop()

    # Split medicines
    medicines = [
        clean_text(x)
        for x in medicine_input.split(",")
        if clean_text(x)
    ]

    # Remove duplicates
    unique_medicines = []

    seen = set()

    for medicine in medicines:

        key = (
            get_canonical_name(
                medicine
            )
            + "|"
            + extract_dosage_form(
                medicine
            )
        )

        if key not in seen:

            seen.add(key)

            unique_medicines.append(
                medicine
            )

    medicines = unique_medicines

    st.success(
        f"Found {len(medicines)} medicine(s)"
    )

    # Retrieve medicine data
    with st.spinner(
        "Retrieving medicine information from databases..."
    ):

        analyzed = []

        for medicine in medicines:

            analyzed.append(
                analyze_medicine(
                    medicine
                )
            )

    # Interaction checking
    interaction_results = []

    if len(medicines) >= 2:

        with st.spinner(
            "Checking medicine interaction information..."
        ):

            interaction_results = (
                check_interactions(
                    medicines
                )
            )

    # ========================================================
    # MEDICINE SUMMARY
    # ========================================================

    st.markdown(
        '<div class="section-title">'
        '📋 Medicine Summary'
        '</div>',
        unsafe_allow_html=True
    )

    for result in analyzed:

        related_evidence = []

        for interaction in interaction_results:

            if not interaction["found"]:
                continue

            if (
                interaction["medicine_a"]
                == result["input_name"]
                or
                interaction["medicine_b"]
                == result["input_name"]
            ):

                related_evidence.append(
                    interaction["evidence"]
                )

        evidence_text = "\n".join(
            related_evidence
        )

        display_medicine(
            result,
            evidence_text
        )

        st.divider()

    # ========================================================
    # INTERACTION SCREENING
    # ========================================================

    st.markdown(
        '<div class="section-title">'
        '🔍 Interaction Screening'
        '</div>',
        unsafe_allow_html=True
    )

    if len(medicines) >= 2:

        st.info(
            "Interaction screening is based on "
            "retrieved drug-label information. "
            "No detected interaction does not prove "
            "that no interaction exists."
        )

        for interaction in interaction_results:

            pair_name = (
                f"{interaction['medicine_a'].title()} "
                f"+ "
                f"{interaction['medicine_b'].title()}"
            )

            st.markdown(
                f"### 💊 {pair_name}"
            )

            if interaction["found"]:

                st.warning(
                    "Interaction-related information "
                    "was found in the retrieved label data."
                )

                with st.spinner(
                    "Summarizing interaction evidence..."
                ):

                    summary = (
                        summarize_interaction_with_ai(
                            interaction["medicine_a"],
                            interaction["medicine_b"],
                            interaction["evidence"]
                        )
                    )

                if summary:

                    st.markdown(
                        summary
                    )

                else:

                    st.markdown(
                        "### 🔍 Interaction result"
                    )

                    st.write(
                        "Relevant interaction information "
                        "was found in the retrieved label."
                    )

                    st.write(
                        "Please verify the significance "
                        "with a doctor or pharmacist."
                    )

            else:

                st.success(
                    "No direct interaction reference "
                    "was found in the retrieved labels."
                )

                st.info(
                    "This does not prove that no interaction exists."
                )

    else:

        st.info(
            "Enter two or more medicines to perform "
            "interaction screening."
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "MediSate AI • Medicine information and "
    "interaction screening tool • Educational use only • "
    "Always verify medicine information with a qualified "
    "doctor or pharmacist."
)