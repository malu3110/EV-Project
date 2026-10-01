"""Build the publishable, anonymised survey file from the raw Google Forms export.

Run once, locally, by the survey owner:

    python scripts/anonymise_survey.py

Input  : data/raw/EV Adoption Survey (Responses).xlsx   (gitignored, never published)
Output : data/survey_anonymised.csv                      (published)

What this does to protect respondents
-------------------------------------
* Drops the response timestamp (it orders responses and links them to the
  moment a specific person was sent the form).
* Drops every free-text field. "Where do you currently reside?" was free text
  and included village names and what looks like a building name; it is
  replaced by a coarse region (Kerala / Tamil Nadu / Other Indian state /
  India, unspecified / Gulf / Other abroad). Free-text "Other" answers in
  multi-select questions are dropped; only the predefined options survive,
  as 0/1 flags.
* Replaces nationality with residential status (Indian resident / NRI /
  foreign national). Nationality had cells of 2 and 3 people.
* Coarsens age (55+ merged), income (top four bands merged into >Rs 5 lakh),
  education (3 levels) and employment (Employed / Homemaker / Student /
  Not working), folding free-text variants into those categories.
* Removes the one respondent who reported being under 18 (see README).
* Applies local suppression: if a respondent's combination of
  (age band, gender, lives in India, region, employment) is shared by fewer
  than K respondents, employment, then region, then age band are replaced by
  "Suppressed" until every combination has at least K members. (Two
  respondents who chose "Prefer not to say" for gender end up with every
  identifier suppressed; they are accepted as-is.)
* Shuffles row order and assigns a random respondent id.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "EV Adoption Survey (Responses).xlsx"
OUT = ROOT / "data" / "survey_anonymised.csv"
K = 3
SEED = 2025

# Raw question text -> short column name
RENAME = {
    "What is your age group?": "age_raw",
    "What is your gender?": "gender",
    "What is your nationality?": "nationality",
    "What is your residential status?( for Indian nationals)": "status_raw",
    "Where do you currently reside?": "location_raw",
    "What type of area do you live in?": "area_type",
    "What is your highest level of education?": "education_raw",
    "What is your current employment status?": "employment_raw",
    "What is your average monthly personal income (in INR)?": "income_raw",
    "How would you describe your financial situation?": "financial_situation",
    "Do you currently own any personal vehicle(s)?": "owns_vehicle",
    "What type of vehicle(s) do you own? (Select all that apply)": "vehicles_raw",
    "How old is your primary vehicle?": "vehicle_age",
    "What is your average monthy travel distance with your personal vehicle?": "monthly_distance",
    "How familiar are you with electric vehicle ( EVs)": "familiarity",
    "What is your overall opinion of EVs?": "opinion",
    "Where did you first hear about EVs? (Select all that apply)": "source_raw",
    "What benefits do you associate with EVs? ( Select all that apply)": "benefits_raw",
    "What concerns or drawbacks do you associate with EVs? ( Select all that apply)": "concerns_raw",
    "Do you feel EVs are suitable for your area?": "suitable_for_area",
    "Are you aware of any government policies or incentives for EV adoption in your country?": "policy_awareness",
    "How likely are you to recommend an EV to someone else?": "recommend",
    "How likely are you to purchase an electric vehicle as your next vehicle?": "purchase_intent",
    "What would motivate you to consider switching to an EV? (Select all that apply)": "motivators_raw",
    "Where would you prefer to charge your EV?": "charging_raw",
    "What charging time would be acceptable to you?": "charging_time",
    "Would you be willing to pay extra for faster charging?": "pay_extra_fast_charging",
}

AGE = {
    "18–24": "18–24", "25–34": "25–34", "35–44": "35–44", "45–54": "45–54",
    "55–64": "55+", "65 and above": "55+", "Under 18": None,
}

STATUS = {
    "Indian Resident": "Indian resident",
    "Non - Resident Indian ( NRI)": "NRI",
    "Not Applicable": "Foreign national",
}

LOCATION = {
    "Kerala": ["kerala", "thrissur", "trichur", "trivandrum", "thiruvananthapuram", "tvm",
               "kochi", "kozhikode", "alleppey"],
    "Tamil Nadu": ["tamil nadu", "chennai", "coimbatore", "karur"],
    "Other Indian state": ["pune", "mumbai", "bangalore", "karnataka", "hyderabad", "delhi",
                           "gurgaon", "indore", "andhra pradesh", "nellore"],
    "Gulf": ["qatar", "doha", "dubai", "uae", "united arab emirates", "abu dhabi", "oman"],
    "Other abroad": ["usa", "us", "united states", "canada", "europe", "austria",
                     "netherlands", "switzerland", "australia", "sydney", "moldova",
                     "kuala lumpur"],
    "India, unspecified": ["india", "indian", "indian soil"],
}
# Small localities named by respondents are mapped in a gitignored file next to
# the raw data, so that publishing this script does not reveal them.
OVERRIDES = ROOT / "data" / "raw" / "location_overrides.json"
if OVERRIDES.exists():
    for region, places in json.loads(OVERRIDES.read_text()).items():
        LOCATION[region].extend(places)

INDIA_REGIONS = {"Kerala", "Tamil Nadu", "Other Indian state", "India, unspecified"}

EDUCATION = {
    "Undergraduate degree": "Undergraduate", "Graduate": "Undergraduate",
    "Bachelor of Engineering": "Undergraduate", "Bachelor of engineering": "Undergraduate",
    "Bachelors": "Undergraduate", "Engineering graduate": "Undergraduate",
    "B. Ed": "Undergraduate",
    "Postgraduate degree": "Postgraduate or doctoral", "Doctoral degree": "Postgraduate or doctoral",
    "High school or equivalent": "School or diploma", "Diploma": "School or diploma",
    "School Student": "School or diploma", "No formal education": "School or diploma",
}

EMPLOYMENT = {
    "Employed – Private sector": "Employed", "Employed – Government sector": "Employed",
    "Self-employed / Business owner": "Employed", "Business": "Employed",
    "Homemaker": "Homemaker",
    "Student": "Student",
    "Unemployed – Seeking job": "Not working", "resigned": "Not working",
    "Quit the job for support family": "Not working",
    "Retired – Without pension": "Not working", "Retired – With pension": "Not working",
}

INCOME = {
    "Less than ₹20,000": "<20k",
    "₹20,000 – ₹50,000": "20k–50k",
    "₹50,001 – ₹1,00,000": "50k–1L",
    "₹1,00,001 – ₹2,00,000": "1L–2L",
    "₹2,00,001 – ₹5,00,000": "2L–5L",
    "₹5,00,001": ">5L", "₹10,00,001": ">5L", "₹20,00,001": ">5L",
    "₹80,00,001": ">5L", "More than ₹1,00,00,000": ">5L",
    "Prefer not to say": "Prefer not to say",
}

# Predefined options of each multi-select question -> flag suffix
MULTI = {
    "vehicles_raw": ("owns", {
        "Car ( Petrol)": "car_petrol", "Car ( Diesel)": "car_diesel",
        "Car ( Electric)": "car_electric", "Two - wheeler (Petrol)": "2w_petrol",
        "Two - wheeler (Diesel)": "2w_diesel", "Two - wheeler ( Electric)": "2w_electric",
    }),
    "source_raw": ("heard", {
        "Social media": "social_media", "Friends/ Family": "friends_family",
        "Advertisements( TV, print, etc)": "advertising", "News/ Articles": "news",
        "Car dealerships / Auto expos": "dealers_expos",
        "Educational Institutions": "education", "Government Promotions/ Schemes": "government",
    }),
    "benefits_raw": ("benefit", {
        "Lower fuel / energy cost": "lower_running_cost",
        "Reduced environmental pollution": "less_pollution",
        "Silent / smooth driving experience": "smooth_drive",
        "Government subsidies and tax benefits": "subsidies",
        "Lower maintenance": "lower_maintenance", "Trendy / modern image": "modern_image",
        "None/ not sure": "none_not_sure",
    }),
    "concerns_raw": ("concern", {
        "Lack of charging infrastructure": "charging_infra", "High initial cost": "upfront_cost",
        "Battery replacement cost": "battery_cost", "Limited driving range": "range",
        "Long charging time": "charging_time", "Unsure about resale value": "resale_value",
        "Safety doubts": "safety", "Performance concerns": "performance",
        "Not sure/ no concerns": "none_not_sure",
    }),
    "motivators_raw": ("motivator", {
        "Better charging infrastructure": "better_charging", "Environmental impact": "environment",
        "Lower purchase cost": "lower_price", "Faster charging times": "faster_charging",
        "Higher fuel prices for traditional vehicles": "fuel_prices",
        "More government incentives": "incentives", "Peer influence / social trend": "peers",
    }),
    "charging_raw": ("charge_at", {
        "Home": "home", "Office / Workplace": "work", "Public charging stations": "public",
        "Malls /  Supermarkets / Highways": "malls_highways", "Any of the above": "anywhere",
    }),
}


def map_prefix(value, mapping):
    """Map a raw answer via exact match, else via the first key it starts with."""
    v = str(value).strip()
    if v in mapping:
        return mapping[v]
    for key, out in mapping.items():
        if v.startswith(key):
            return out
    raise ValueError(f"Unmapped answer: {v!r}")


def map_location(value):
    v = str(value).strip().lower()
    # Most specific first: a string mentioning a city and "India" is that city.
    for region in ["Kerala", "Tamil Nadu", "Other Indian state", "Gulf", "Other abroad"]:
        for token in LOCATION[region]:
            if token in ("us", "uae", "tvm"):
                if token in v.replace(",", " ").split():
                    return region
            elif token in v:
                return region
    if v in LOCATION["India, unspecified"]:
        return "India, unspecified"
    return "Unclear"  # includes small localities if the overrides file is absent


def flags(series, options):
    text = series.fillna("").astype(str)
    # Options themselves contain commas, so match on substring rather than split.
    return pd.DataFrame({name: text.str.contains(opt, regex=False).astype(int)
                         for opt, name in options.items()})


def suppress(df, qi, k):
    """Local suppression: blank out the most specific QIs for rows in small cells."""
    df = df.copy()
    # Moving a row out of a cell can shrink that cell below k, so repeat to a fixed point.
    for _ in range(10):
        before = df[qi].copy()
        for col in ["employment", "region", "age_band"]:
            sizes = df.groupby(qi)[qi[0]].transform("size")
            df.loc[sizes < k, col] = "Suppressed"
        if df[qi].equals(before):
            break
    sizes = df.groupby(qi)[qi[0]].transform("size")
    # A suppressed value is a wildcard. For a row whose age, region and
    # employment are all suppressed, the anonymity set is every respondent with
    # the same gender and India/abroad flag, not just exact matches. The two
    # "Prefer not to say" gender rows disclose nothing beyond India/abroad.
    fully = df[["employment", "region", "age_band"]].eq("Suppressed").all(axis=1)
    wildcard_sizes = df.groupby(["gender", "lives_in_india"])["gender"].transform("size")
    ok = (sizes >= k) | (fully & ((wildcard_sizes >= k) | df["gender"].eq("Prefer not to say")))
    if not ok.all():
        raise RuntimeError("Suppression did not reach k-anonymity; coarsen further.")
    return df


def main():
    raw = pd.read_excel(RAW)
    raw.columns = raw.columns.str.replace(r"\s+", " ", regex=True).str.strip()
    raw = raw.rename(columns=RENAME)
    for c in raw.select_dtypes(["object", "string"]):
        raw[c] = raw[c].str.strip()

    out = pd.DataFrame(index=raw.index)
    out["age_band"] = raw["age_raw"].map(AGE)
    out["gender"] = raw["gender"]
    out["residential_status"] = raw["status_raw"].map(STATUS)
    out["region"] = raw["location_raw"].map(map_location)
    out["lives_in_india"] = out["region"].isin(INDIA_REGIONS).astype(int)
    out["area_type"] = raw["area_type"]
    out["education"] = raw["education_raw"].map(EDUCATION)
    out["employment"] = raw["employment_raw"].map(EMPLOYMENT)
    out["income_band"] = raw["income_raw"].map(lambda v: map_prefix(v, INCOME))
    for col in ["financial_situation", "owns_vehicle", "vehicle_age", "monthly_distance",
                "familiarity", "opinion", "suitable_for_area", "policy_awareness",
                "recommend", "purchase_intent", "charging_time", "pay_extra_fast_charging"]:
        out[col] = raw[col]
    # Shorten the long Likert labels to their leading phrase
    for col in ["familiarity", "opinion", "financial_situation"]:
        out[col] = out[col].str.split(r" [-–] ", n=1, regex=True).str[0].str.strip()
    for col, (prefix, options) in MULTI.items():
        f = flags(raw[col], options)
        f.columns = [f"{prefix}_{c}" for c in f.columns]
        out = pd.concat([out, f], axis=1)

    assert out.drop(columns="age_band").notna().all().all(), "unmapped category"

    n_minor = out["age_band"].isna().sum()
    out = out[out["age_band"].notna()]

    qi = ["age_band", "gender", "lives_in_india", "region", "employment"]
    before = (out.groupby(qi)[qi[0]].transform("size") < K).sum()
    out = suppress(out, qi, K)
    n_emp = (out["employment"] == "Suppressed").sum()
    n_reg = (out["region"] == "Suppressed").sum()
    n_age = (out["age_band"] == "Suppressed").sum()

    out = out.sample(frac=1, random_state=SEED).reset_index(drop=True)
    out.insert(0, "respondent_id", [f"R{i:03d}" for i in range(1, len(out) + 1)])
    out.to_csv(OUT, index=False)

    print(f"Raw rows: {len(raw)}; removed under-18: {n_minor}; published rows: {len(out)}")
    print(f"Rows in QI cells smaller than k={K} before suppression: {before}")
    print(f"Suppressed employment in {n_emp} rows, region in {n_reg} rows, age band in {n_age} rows")
    print(f"Wrote {OUT.relative_to(ROOT)} with {out.shape[1]} columns")


if __name__ == "__main__":
    main()
