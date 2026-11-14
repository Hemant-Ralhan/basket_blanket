# Basket Blanket — Ingredient-Safety Shopping Agent for Quick Commerce

**Basket Blanket** is an AI shopping layer built on **Swiggy's live Instamart MCP server** (`https://mcp.swiggy.com/im`), **Google ADK**, and **Gemini 3.5 Flash**. It audits live grocery carts and searched SKUs for shoppers with strict dietary or medical constraints—starting with **Type 1 Diabetes** and **Lactating Mothers**—flags trigger ingredients before checkout, and proposes 1-tap in-stock swaps.

## Why This Matters for Quick Commerce

Shoppers managing chronic conditions or postpartum nutrition often hesitate or abandon packaged-food carts on 10-minute delivery apps because checking tiny back-of-pack ingredient labels breaks the speed of quick commerce.

Basket Blanket solves this inside the ordering flow:
- **Higher Cart Conversion:** Replaces label anxiety with an instant `RED` / `AMBER` / `GREEN` verdict and plain-English reasoning.
- **In-Flow Recovery (No Dead Ends):** Instead of just warning the user away from a SKU, the agent searches the same dark store (`addressId`) for compliant alternatives and swaps the item in-cart (`update_cart`) upon confirmation.
- **Zero-Hallucination Guardrails:** Health verdicts are computed by a deterministic rule engine (`evaluate_ingredients`), not unconstrained LLM text generation.

## Architecture & MCP Integration

    User Prompt (e.g., "Check my Instamart cart for a Type 1 diabetic")
       │
       ▼
    Google ADK Agent (Gemini 3.5 Flash)
       ├──► Swiggy Instamart MCP (Streamable HTTP + OAuth 2.1 PKCE)
       │      ├── get_addresses      → Resolves delivery addressId
       │      ├── get_cart           → Pulls live basket SKUs & prices
       │      ├── search_products    → Finds in-stock safer alternatives
       │      └── update_cart        → Swaps flagged items after confirmation
       │
       ├──► extract_ingredients_from_label (Gemini Vision)
       │      └── OCRs back-of-pack label images when catalog text omits ingredients
       │
       └──► evaluate_ingredients (Deterministic Rule Engine)
              └── Flags triggers for Type 1 Diabetes & Lactation → RED / AMBER / GREEN

### Key Engineering Decisions
1. **Hybrid Rules + LLM:** Deterministic regex/clinical rules catch hard triggers (such as added sugars, dextrose, and maltodextrin for Type 1 diabetes; alcohol, stimulants, and restricted botanicals for lactation), while the LLM handles orchestration and concise user explanations.
2. **Scoped MCP Tooling:** Uses ADK's `McpToolset` with `tool_filter` to expose only the 5 Instamart tools needed for discovery, cart inspection, and confirmed swaps—keeping latency low and preventing accidental checkouts.
3. **Multimodal Label Fallback:** Quick-commerce catalog endpoints return product names, pack sizes, and prices rather than full medical ingredient tables. `extract_ingredients_from_label` bridges that gap directly from product label images.

## Quickstart (Local)

### 1. Install dependencies

    pip install -r requirements.txt

### 2. Get your Swiggy Instamart MCP Bearer token
Swiggy MCP uses **OAuth 2.1 with PKCE** (no static API key required for `localhost` development per the [Swiggy Builders Club](https://mcp.swiggy.com/builders/) docs). Run the included helper:

    python3 swiggy_oauth.py

Complete the Swiggy phone + OTP login in your browser, then copy the printed token.

### 3. Configure `.env` and run `adk web`

    cp basket_blanket/.env.example basket_blanket/.env
    # Add your GEMINI_API_KEY (Google AI Studio) and SWIGGY_MCP_ACCESS_TOKEN
    adk web

Open `http://127.0.0.1:8000`, select `basket_blanket`, and test:
- *"Check my Instamart cart for a Type 1 diabetic and suggest safer swaps."*
- *"Search Instamart for protein bars at my address and check if they're safe for a lactating mother."*

## Repository Structure

    basket_blanket/
    ├── basket_blanket/
    │   ├── __init__.py
    │   ├── .env.example
    │   └── agent.py          # Google ADK agent, MCP toolset, OCR & deterministic rules
    ├── swiggy_oauth.py       # OAuth 2.1 PKCE + Dynamic Client Registration helper
    ├── requirements.txt
    └── README.md

## Roadmap
- **SKU-to-Ingredient Cache:** Store verified OCR/Open Food Facts ingredient strings keyed by Swiggy `spin_id` to cut latency to sub-second.
- **Expanded Cohorts:** Add rulesets for Renal/CKD, Celiac (gluten-free), Hypertension (sodium caps), and Pediatric allergies.
- **Per-User Production OAuth:** Add `/auth/login` and `/auth/callback` routes on Cloud Run once Swiggy Builders Club production redirect URIs are allowlisted.

---
*Built by [Hemant Ralhan](https://github.com/Hemant-Ralhan) · Powered by [Google ADK](https://adk.dev/tools-custom/mcp-tools/) and [Swiggy Builders Club](https://mcp.swiggy.com/builders/).*
