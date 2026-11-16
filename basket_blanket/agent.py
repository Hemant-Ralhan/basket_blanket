import os, re, urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Literal
from google import genai
from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

SWIGGY_IM_MCP_URL = "https://mcp.swiggy.com/im"
GEMINI_MODEL = "gemini-3.5-flash-lite"

ProfileType = Literal["type_1_diabetes", "lactating_mother"]
VerdictLevel = Literal["GREEN", "AMBER", "RED"]

@dataclass
class RuleTrigger:
    ingredient: str
    severity: VerdictLevel
    reason: str

@dataclass
class SafetyVerdict:
    product_name: str
    profile: ProfileType
    verdict: VerdictLevel
    triggers: List[RuleTrigger]
    summary: str

PROFILE_RULES: Dict[ProfileType, List[Dict[str, str]]] = {
    "type_1_diabetes": [
        {"pattern": r"\b(sugar|sucrose|glucose|dextrose|fructose|corn syrup|hfcs|invert sugar|jaggery|cane sugar)\b", "severity": "RED", "reason": "Direct simple sugar; causes rapid post-prandial glycemic spike."},
        {"pattern": r"\b(maltodextrin|corn starch|tapioca starch|modified starch|rice syrup|maltose)\b", "severity": "RED", "reason": "High-glycemic carbohydrate/starch; raises blood glucose rapidly."},
        {"pattern": r"\b(honey|maple syrup|date syrup|agave|fruit juice concentrate)\b", "severity": "AMBER", "reason": "Concentrated natural sugars; must be counted in carb/insulin dosing."},
        {"pattern": r"\b(maltitol|sorbitol|xylitol|erythritol|stevia|sucralose|aspartame)\b", "severity": "AMBER", "reason": "Sugar alcohol / non-nutritive sweetener; check maltitol glycemic impact."},
    ],
    "lactating_mother": [
        {"pattern": r"\b(alcohol|ethanol|wine|rum|brandy)\b", "severity": "RED", "reason": "Alcohol transfers into breast milk."},
        {"pattern": r"\b(caffeine|guarana|yerba mate|green tea extract|coffee extract|taurine)\b", "severity": "AMBER", "reason": "Stimulant/caffeine source; excess intake can pass into breast milk."},
        {"pattern": r"\b(saccharin|acesulfame|cyclamate)\b", "severity": "AMBER", "reason": "Artificial sweetener; clinical guidance often advises limiting during lactation."},
        {"pattern": r"\b(ashwagandha|ginseng|kava|senna|sage extract|parsley extract)\b", "severity": "RED", "reason": "Concentrated botanical/herb with limited lactation safety data."},
    ],
}

def extract_ingredients_from_label(image_url: str, mime_type: str = "image/jpeg") -> Dict[str, Any]:
    """Read a back-of-pack product image URL using Gemini 3.8 Flash vision."""
    try:
        req = urllib.request.Request(image_url, headers={"User-Agent": "BasketBlanket/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            image_bytes = resp.read()
            detected_mime = resp.headers.get_content_type() or mime_type
        client = genai.Client()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=detected_mime),
                "Extract the exact Ingredients list as a single comma-separated string. If not visible, reply: NOT_VISIBLE",
            ],
        )
        extracted = (response.text or "").strip()
        if not extracted or extracted == "NOT_VISIBLE":
            return {"status": "not_found", "ingredients_text": ""}
        return {"status": "ok", "ingredients_text": extracted}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "ingredients_text": ""}

def evaluate_ingredients(product_name: str, ingredients_text: str, profile: ProfileType) -> Dict[str, Any]:
    """Evaluate a product's ingredient list against 'type_1_diabetes' or 'lactating_mother'."""
    triggers: List[RuleTrigger] = []
    seen = set()
    text_lower = ingredients_text.lower()
    for rule in PROFILE_RULES.get(profile, []):
        for match in re.finditer(rule["pattern"], text_lower):
            term = match.group(0)
            key = (term, rule["severity"])
            if key not in seen:
                seen.add(key)
                triggers.append(RuleTrigger(ingredient=term, severity=rule["severity"], reason=rule["reason"]))
    if any(t.severity == "RED" for t in triggers):
        verdict, summary = "RED", f"Flagged for {profile.replace('_', ' ')}: {len(triggers)} trigger(s)."
    elif any(t.severity == "AMBER" for t in triggers):
        verdict, summary = "AMBER", f"Caution for {profile.replace('_', ' ')}: {len(triggers)} ingredient(s)."
    else:
        verdict, summary = "GREEN", f"No flagged triggers found for {profile.replace('_', ' ')}."
    return asdict(SafetyVerdict(product_name=product_name, profile=profile, verdict=verdict, triggers=triggers, summary=summary))

swiggy_token = os.environ.get("SWIGGY_MCP_ACCESS_TOKEN", "")
instamart_mcp_tools = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=SWIGGY_IM_MCP_URL,
        headers={"Authorization": f"Bearer {swiggy_token}"} if swiggy_token else {},
    ),
    tool_filter=["get_addresses", "search_products", "your_go_to_items", "get_cart", "update_cart"],
)

root_agent = LlmAgent(
    name="basket_blanket_agent",
    model=GEMINI_MODEL,
    instruction=(
        "You are Basket Blanket, an ingredient-safety shopping agent on Swiggy Instamart. "
        "1) Call get_addresses first, pick the user's requested or default addressId, and reuse that exact addressId for ALL downstream calls (get_cart, search_products, update_cart). "
        "2) Use get_cart to inspect the live basket. "
        "3) Use extract_ingredients_from_label on label images when needed, then always call evaluate_ingredients before issuing a RED/AMBER/GREEN/UNKNOWN verdict. Never issue GREEN without verified ingredients. "
        "4) Call search_products at most once per turn with a specific query using the same addressId. Only suggest or pass skuId and spinId returned from that same addressId. "
        "5) Never call update_cart without explicit user confirmation. Immediately after update_cart, call get_cart with the same addressId to verify the live cart updated."
    ),
    tools=[extract_ingredients_from_label, evaluate_ingredients, instamart_mcp_tools],
)
