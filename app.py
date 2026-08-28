import streamlit as st
import requests
import re
from urllib.parse import quote
from itertools import combinations

# ============================================================
# MEDISATE AI
# Exact medicine identification + FDA label + interaction check
# ============================================================

st.set_page_config(
    page_title="MediSate AI",
    page_icon="💊",
    layout="wide"
)

# ------------------------------------------------------------
# Styling
# ------------------------------------------------------------

st.markdown("""
<style>
    .main {
        max-width: 1100px;
        margin: auto;
    }

    .title {
        font-size: 48px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 18px;
        margin-bottom: 30px;
    }

    .section-title {
        font-size: 32px;
        font-weight: 750;
        margin-top: 35px;
        margin-bottom: 15px;
    }

    .medicine-title {
        font-size: 30px;
        font-weight: 750;
        margin-top: 30px;
    }

    .card {
        padding: 20px;
        border-radius: 12px;
        margin: 12px 0;
    }

    .warning-card {
        padding: 18px;
        border-radius: 12px;
        margin: 15px 0;
    }

    .small-text {
        font-size: 15px;
        opacity: 0.85;
    }

    div.stButton > button {
        width: 100%;
        height: 50px;
        font-size: 17px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# CONFIGURATION
# ============================================================

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
OPENFDA_BASE = "https://api.fda.gov/drug/label.json"

REQUEST_TIMEOUT = 12


# ============================================================
# COMMON MEDICINE ALIASES
# ============================================================

# These are important because users may enter either generic
# or commonly used alternative names.

MEDICINE_ALIASES = {
    "paracetamol": "acetaminophen",
    "acetaminol": "acetaminophen",
    "tylenol": "acetaminophen",

    "ibuprofen": "ibuprofen",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",

    "aspirin": "aspirin",
    "acetylsalicylic acid": "aspirin",

    "naproxen": "naproxen",
    "aleve": "naproxen",

    "diclofenac": "diclofenac",
    "voltaren": "diclofenac",

    "cetirizine": "cetirizine",
    "zyrtec": "cetirizine",

    "loratadine": "loratadine",
    "claritin": "loratadine",

    "amoxicillin": "amoxicillin",
    "azithromycin": "azithromycin",

    "omeprazole": "omeprazole",
    "pantoprazole": "pantoprazole",

    "metformin": "metformin",

    "atorvastatin": "atorvastatin",

    "paracetamol 500": "acetaminophen",
    "acetaminophen 500": "acetaminophen",
}


# ============================================================
# KNOWN INGREDIENT RXCUI VALUES
# ============================================================

# Ingredient-level RxNorm IDs.
# Using these prevents RxNorm from choosing combination products.

KNOWN_RXCUI = {
    "acetaminophen": "161",
    "ibuprofen": "5640",
    "aspirin": "1191",
    "naproxen": "7258",
    "diclofenac": "3355",
    "cetirizine": "2678",
    "loratadine": "153165",
    "amoxicillin": "723",
    "azithromycin": "18631",
    "omeprazole": "7646",
    "pantoprazole": "40790",
    "metformin": "6809",
    "atorvastatin": "83367",
}


# ============================================================
# SESSION CACHE
# ============================================================

if "medicine_cache" not in st.session_state:
    st.session_state.medicine_cache = {}


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def clean_text(value):
    """Clean text safely."""
    if value is None:
        return ""

    if isinstance(value, list):
        value = " ".join(str(x) for x in value)

    value = str(value)

    value = value.replace("\n", " ")
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_name(name):
    """Normalize medicine names for comparison."""
    name = clean_text(name).lower()

    name = name.replace("-", " ")
    name = re.sub(r"\([^)]*\)", "", name)

    # Remove strength information.
    name = re.sub(
        r"\b\d+(?:\.\d+)?\s*(mg|mcg|g|ml|iu|%)\b",
        "",
        name
    )

    name = re.sub(r"\s+", " ", name)

    return name.strip()


def get_canonical_name(user_name):
    """Convert brand/synonym to generic ingredient."""
    normalized = normalize_name(user_name)

    if normalized in MEDICINE_ALIASES:
        return MEDICINE_ALIASES[normalized]

    return normalized


# ============================================================
# RXNORM FUNCTIONS
# ============================================================

@st.cache_data(ttl=86400, show_spinner=False)
def get_rxnorm_rxcui(medicine):
    """
    Get an ingredient-level RxCUI.

    IMPORTANT:
    We deliberately avoid selecting the first approximate result
    because that can return combination products such as:
        famotidine + ibuprofen
        acetaminophen + aspirin + caffeine
    """

    medicine = get_canonical_name(medicine)

    # --------------------------------------------------------
    # First: use our known ingredient map
    # --------------------------------------------------------

    if medicine in KNOWN_RXCUI:
        return KNOWN_RXCUI[medicine]

    # --------------------------------------------------------
    # Second: exact RxNorm lookup
    # --------------------------------------------------------

    try:
        url = f"{RXNORM_BASE}/rxcui.json"

        response = requests.get(
            url,
            params={
                "name": medicine,
                "search": "2"
            },
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            return None

        data = response.json()

        ids = data.get("idGroup", {}).get("rxnormId", [])

        if not ids:
            return None

        # Try every candidate and select an ingredient concept.
        for rxcui in ids:

            try:
                props_url = f"{RXNORM_BASE}/rxcui/{rxcui}/properties.json"

                props_response = requests.get(
                    props_url,
                    timeout=REQUEST_TIMEOUT
                )

                if props_response.status_code != 200:
                    continue

                props = props_response.json().get(
                    "properties",
                    {}
                )

                name = clean_text(
                    props.get("name", "")
                ).lower()

                tty = clean_text(
                    props.get("tty", "")
                ).upper()

                # Ingredient concept types:
                # IN  = Ingredient
                # PIN = Precise Ingredient
                if tty in ("IN", "PIN"):

                    if normalize_name(name) == medicine:
                        return str(rxcui)

            except Exception:
                continue

        # Last safe fallback:
        # only use first ID if it is not obviously a combination.
        for rxcui in ids:

            try:
                props_url = f"{RXNORM_BASE}/rxcui/{rxcui}/properties.json"

                props_response = requests.get(
                    props_url,
                    timeout=REQUEST_TIMEOUT
                )

                if props_response.status_code != 200:
                    continue

                props = props_response.json().get(
                    "properties",
                    {}
                )

                name = clean_text(
                    props.get("name", "")
                ).lower()

                tty = clean_text(
                    props.get("tty", "")
                ).upper()

                if tty in ("IN", "PIN"):

                    # Don't accept an obviously different name.
                    if medicine in normalize_name(name):
                        return str(rxcui)

            except Exception:
                continue

    except Exception:
        return None

    return None


@st.cache_data(ttl=86400, show_spinner=False)
def get_rxnorm_properties(rxcui):
    """Get properties for an RxCUI."""

    if not rxcui:
        return {}

    try:
        url = f"{RXNORM_BASE}/rxcui/{rxcui}/properties.json"

        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            return {}

        return response.json().get(
            "properties",
            {}
        )

    except Exception:
        return {}


@st.cache_data(ttl=86400, show_spinner=False)
def get_rxnorm_related(rxcui):
    """
    Retrieve related RxNorm concepts.

    This is used only for information.
    We DO NOT replace the ingredient RxCUI with a combination product.
    """

    if not rxcui:
        return []

    try:
        url = f"{RXNORM_BASE}/rxcui/{rxcui}/allrelated.json"

        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            return []

        data = response.json()

        groups = data.get(
            "allRelatedGroup",
            {}
        ).get(
            "conceptGroup",
            []
        )

        results = []

        for group in groups:

            tty = group.get("tty", "")

            for concept in group.get("conceptProperties", []):

                results.append({
                    "rxcui": concept.get("rxcui"),
                    "name": concept.get("name"),
                    "tty": tty
                })

        return results

    except Exception:
        return []


# ============================================================
# FDA LABEL FUNCTIONS
# ============================================================

@st.cache_data(ttl=21600, show_spinner=False)
def get_fda_label(medicine):
    """
    Retrieve FDA label information.

    Search is based on the generic ingredient rather than a
    random product returned by RxNorm.
    """

    canonical = get_canonical_name(medicine)

    search_fields = [
        f'openfda.generic_name:"{canonical}"',
        f'openfda.substance_name:"{canonical}"',
        f'openfda.brand_name:"{canonical}"'
    ]

    for search in search_fields:

        try:

            response = requests.get(
                OPENFDA_BASE,
                params={
                    "search": search,
                    "limit": 10
                },
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code != 200:
                continue

            data = response.json()

            results = data.get("results", [])

            if results:
                return choose_best_fda_label(
                    results,
                    canonical
                )

        except Exception:
            continue

    return None


def choose_best_fda_label(results, medicine):
    """
    Choose the most relevant FDA label.

    Avoid combination products when possible.
    """

    medicine = normalize_name(medicine)

    scored = []

    for label in results:

        score = 0

        generic_names = label.get(
            "openfda",
            {}
        ).get(
            "generic_name",
            []
        )

        substances = label.get(
            "openfda",
            {}
        ).get(
            "substance_name",
            []
        )

        brands = label.get(
            "openfda",
            {}
        ).get(
            "brand_name",
            []
        )

        all_names = []

        for item in generic_names:
            all_names.append(clean_text(item).lower())

        for item in substances:
            all_names.append(clean_text(item).lower())

        for item in brands:
            all_names.append(clean_text(item).lower())

        combined = " ".join(all_names)

        normalized_combined = normalize_name(combined)

        # Exact ingredient match gets highest priority.
        if medicine in normalized_combined:
            score += 20

        # Penalize common combination products.
        combination_terms = [
            " and ",
            "/",
            "+",
            "acetaminophen/aspirin",
            "aspirin/caffeine",
            "famotidine/ibuprofen",
            "hydrochlorothiazide",
            "amlodipine",
            "caffeine"
        ]

        for term in combination_terms:
            if term in combined:
                score -= 10

        scored.append(
            (score, label)
        )

    if not scored:
        return None

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return scored[0][1]


# ============================================================
# EXTRACT FDA INFORMATION
# ============================================================

def get_label_field(label, field):
    """Safely get FDA label field."""

    if not label:
        return ""

    value = label.get(field, "")

    return clean_text(value)


def extract_label_sections(label):
    """Extract useful FDA sections."""

    if not label:
        return {
            "purpose": "",
            "indications": "",
            "warnings": "",
            "side_effects": "",
            "contraindications": "",
            "dosage": ""
        }

    return {
        "purpose": get_label_field(
            label,
            "purpose"
        ),

        "indications": get_label_field(
            label,
            "indications_and_usage"
        ),

        "warnings": get_label_field(
            label,
            "warnings"
        ),

        "side_effects": get_label_field(
            label,
            "adverse_reactions"
        ),

        "contraindications": get_label_field(
            label,
            "contraindications"
        ),

        "dosage": get_label_field(
            label,
            "dosage_and_administration"
        )
    }


# ============================================================
# MEDICINE ANALYSIS
# ============================================================

def analyze_medicine(user_medicine):

    original = clean_text(user_medicine)

    canonical = get_canonical_name(original)

    # --------------------------------------------------------
    # Cache
    # --------------------------------------------------------

    cache_key = canonical

    if cache_key in st.session_state.medicine_cache:
        return st.session_state.medicine_cache[cache_key]

    # --------------------------------------------------------
    # RxNorm
    # --------------------------------------------------------

    rxcui = get_rxnorm_rxcui(canonical)

    properties = get_rxnorm_properties(rxcui)

    # --------------------------------------------------------
    # FDA
    # --------------------------------------------------------

    fda_label = get_fda_label(canonical)

    sections = extract_label_sections(
        fda_label
    )

    # --------------------------------------------------------
    # Standard name
    # --------------------------------------------------------

    if properties:
        standard_name = clean_text(
            properties.get("name", "")
        )
    else:
        standard_name = canonical.title()

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result = {
        "input_name": original,
        "canonical_name": canonical,
        "rxcui": rxcui,
        "standard_name": standard_name,
        "properties": properties,
        "fda_label": fda_label,
        "sections": sections,
        "identified": bool(rxcui or fda_label)
    }

    st.session_state.medicine_cache[cache_key] = result

    return result


# ============================================================
# INTERACTION CHECK
# ============================================================

def search_label_for_interaction(medicine_a, medicine_b):
    """
    Search FDA labels for explicit references to the other medicine.
    """

    canonical_a = get_canonical_name(medicine_a)
    canonical_b = get_canonical_name(medicine_b)

    try:

        response = requests.get(
            OPENFDA_BASE,
            params={
                "search": (
                    f'openfda.generic_name:"{canonical_a}"'
                ),
                "limit": 10
            },
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            return None

        data = response.json()

        results = data.get(
            "results",
            []
        )

        if not results:
            return None

        label = choose_best_fda_label(
            results,
            canonical_a
        )

        if not label:
            return None

        # Search all relevant sections.
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

            if isinstance(value, list):
                text_parts.extend(value)
            elif value:
                text_parts.append(str(value))

        text = " ".join(
            text_parts
        ).lower()

        # Search generic and original names.
        possible_terms = {
            canonical_b,
            clean_text(medicine_b).lower()
        }

        for term in possible_terms:

            if term and term in text:

                # Return only a relevant excerpt.
                index = text.find(term)

                start = max(
                    0,
                    index - 250
                )

                end = min(
                    len(text),
                    index + 600
                )

                return text[start:end]

    except Exception:
        return None

    return None


def check_interactions(medicines):

    results = []

    for medicine_a, medicine_b in combinations(
        medicines,
        2
    ):

        evidence_a = search_label_for_interaction(
            medicine_a,
            medicine_b
        )

        evidence_b = search_label_for_interaction(
            medicine_b,
            medicine_a
        )

        if evidence_a or evidence_b:

            evidence = (
                evidence_a
                if evidence_a
                else evidence_b
            )

            results.append({
                "medicine_a": medicine_a,
                "medicine_b": medicine_b,
                "found": True,
                "evidence": evidence
            })

        else:

            results.append({
                "medicine_a": medicine_a,
                "medicine_b": medicine_b,
                "found": False,
                "evidence": ""
            })

    return results


# ============================================================
# DISPLAY HELPERS
# ============================================================

def display_text(text, max_chars=6000):

    if not text:
        return

    text = clean_text(text)

    if len(text) > max_chars:
        text = text[:max_chars] + "..."

    st.write(text)


def display_medicine(result):

    name = result["input_name"]

    st.markdown(
        f'<div class="medicine-title">💊 {name.title()}</div>',
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # Identification status
    # --------------------------------------------------------

    if result["identified"]:
        st.success("Medicine identified.")
    else:
        st.warning(
            "This medicine could not be confidently identified."
        )

    # --------------------------------------------------------
    # Canonical ingredient
    # --------------------------------------------------------

    canonical = result["canonical_name"]

    if canonical:
        st.markdown(
            f"**Active ingredient:** {canonical.title()}"
        )

    # --------------------------------------------------------
    # Standard name
    # --------------------------------------------------------

    standard_name = result["standard_name"]

    if standard_name:
        st.markdown(
            f"**Standard name:** {standard_name}"
        )

    # --------------------------------------------------------
    # RxNorm
    # --------------------------------------------------------

    if result["rxcui"]:

        st.markdown(
            f"**RxNorm ID:** {result['rxcui']}"
        )

    else:

        st.info(
            "No exact RxNorm ingredient ID was found."
        )

    # --------------------------------------------------------
    # FDA label
    # --------------------------------------------------------

    sections = result["sections"]

    if result["fda_label"]:

        st.success(
            "Official drug-label information found."
        )

        # Purpose
        if sections["purpose"]:

            st.markdown(
                "### 🎯 What is it used for?"
            )

            display_text(
                sections["purpose"]
            )

        elif sections["indications"]:

            st.markdown(
                "### 🎯 What is it used for?"
            )

            display_text(
                sections["indications"]
            )

        # Warnings
        if sections["warnings"]:

            st.markdown(
                "### ⚠️ Important warnings"
            )

            st.warning(
                clean_text(
                    sections["warnings"]
                )
            )

        # Contraindications
        if sections["contraindications"]:

            st.markdown(
                "### 🚫 When should it be avoided?"
            )

            display_text(
                sections["contraindications"]
            )

        # Side effects
        if sections["side_effects"]:

            st.markdown(
                "### 🩺 Possible side effects"
            )

            display_text(
                sections["side_effects"]
            )

        # Dosage
        if sections["dosage"]:

            st.markdown(
                "### 💊 Dosage information"
            )

            display_text(
                sections["dosage"]
            )

    else:

        st.warning(
            "Detailed FDA label information was not found for this medicine."
        )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="title">💊 MediSate AI</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    "Understand your medicines, their common uses, effects, "
    "warnings and potential interactions."
    "</div>",
    unsafe_allow_html=True
)

st.warning(
    "⚠️ Educational information only. This tool does not diagnose "
    "conditions, prescribe medicines, or replace a doctor or pharmacist."
)


# ============================================================
# INPUT
# ============================================================

st.markdown(
    '<div class="section-title">💊 Enter your medicines</div>',
    unsafe_allow_html=True
)

st.write(
    "Enter medicine names separated by commas"
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
# ANALYSIS
# ============================================================

if analyze_button:

    if not medicine_input.strip():

        st.error(
            "Please enter at least one medicine name."
        )

        st.stop()

    # --------------------------------------------------------
    # Split input
    # --------------------------------------------------------

    medicines = [
        clean_text(x)
        for x in medicine_input.split(",")
        if clean_text(x)
    ]

    # Remove duplicates while preserving order.
    unique_medicines = []

    seen = set()

    for medicine in medicines:

        key = normalize_name(medicine)

        if key not in seen:

            seen.add(key)
            unique_medicines.append(medicine)

    medicines = unique_medicines

    st.success(
        f"Found {len(medicines)} medicine(s)"
    )

    # --------------------------------------------------------
    # Analyze each medicine
    # --------------------------------------------------------

    analyzed = []

    with st.spinner(
        "Analyzing medicines..."
    ):

        for medicine in medicines:

            result = analyze_medicine(
                medicine
            )

            analyzed.append(result)

    # --------------------------------------------------------
    # Display medicine information
    # --------------------------------------------------------

    for result in analyzed:

        display_medicine(
            result
        )

        st.divider()

    # ========================================================
    # INTERACTION CHECK
    # ========================================================

    if len(medicines) >= 2:

        st.markdown(
            '<div class="section-title">🔍 Interaction Check</div>',
            unsafe_allow_html=True
        )

        st.info(
            "This is a label-based screening tool. "
            "It is not a complete drug-interaction checker."
        )

        with st.spinner(
            "Checking available drug-label information..."
        ):

            interaction_results = check_interactions(
                medicines
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
                    "A reference to the other medicine was found "
                    "in the retrieved drug-label information."
                )

                if interaction["evidence"]:

                    with st.expander(
                        "View label evidence"
                    ):

                        st.write(
                            interaction["evidence"]
                        )

            else:

                st.success(
                    "No direct interaction reference was found "
                    "in the retrieved labels."
                )

                st.info(
                    "No direct interaction reference was detected "
                    "in the retrieved labels. This does NOT prove "
                    "that no interaction exists."
                )

    # ========================================================
    # SINGLE MEDICINE
    # ========================================================

    else:

        st.markdown(
            '<div class="section-title">🔍 Interaction Check</div>',
            unsafe_allow_html=True
        )

        st.info(
            "Enter two or more medicines to perform "
            "a label-based interaction screening."
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "MediSate AI • Educational medicine information tool • "
    "Always verify medicine information with a qualified "
    "doctor or pharmacist."
)