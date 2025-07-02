#market_recap.py
import logging
import traceback
import os
from datetime import datetime, timedelta
from typing import List # Added for type hinting
from openai import OpenAI
import streamlit as st


# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
# -----------------------------

# ---------- CONFIG ----------
OPENAI_MODEL = "gpt-4.1" # Keeping as gpt-4.1 as per original file for web_search
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
# -----------------------------


def build_recap_prompt(portfolio_tickers: List[str]) -> str:
    """Builds the prompt for the OpenAI Responses API to generate a focused market highlights section."""
    today = datetime.utcnow()
    one_week_ago = today - timedelta(days=7)
    date_range_str = f"between {one_week_ago.strftime('%Y-%m-%d')} ({one_week_ago.strftime('%A')}) and {today.strftime('%Y-%m-%d')} ({today.strftime('%A')})"
    
    tickers_str = ", ".join(portfolio_tickers)

    return (
        f"You are a financial news analyst. Your task is to create a concise 'Weekly Market Update' "
        f"section covering significant market activities and news from the past week, specifically {date_range_str}.\n"
        f"The section should be **no more than 5 bullet points** and focus on macroeconomic events, political news, "
        f"or broad market trends that have likely impacted, or are relevant to, a portfolio holding these tickers: **{tickers_str}**.\n"
        f"For each point, briefly explain the event and its potential relevance to these holdings or their sectors.\n"
        f"Examples of what to look for:\n"
        f"  - Major economic data releases (e.g., inflation, employment, GDP) and their implications for these stocks.\n"
        f"  - Central bank policy shifts (e.g., Federal Reserve, ECB) affecting market sentiment towards these assets.\n"
        f"  - Significant geopolitical events with broad market impact or specific sector relevance to the given tickers.\n"
        f"  - Noteworthy movements in major indices (S&P 500, Nasdaq) if they reflect a trend impacting the portfolio.\n"
        f"  - Key commodity price changes (e.g., oil, gold) if relevant to any of the specified tickers.\n"
        f"Prioritize information that would help an investor understand the context for their portfolio's performance.\n"
        f"Use **credible, cited news sources** found via the web search tool for your information.\n"
        f"**Crucially, incorporate inline URL citations (e.g., [Source URL])** within each relevant bullet point "
        f"or at the end of the sentence explaining the highlight.\n\n"
        f"---\n"
        f"Return *only* the 'Weekly Market Update' section as a list of bullet points, ready for publication. "
        f"Aim for clarity and conciseness, suitable for a client newsletter."
    )


def generate_market_recap_with_search(portfolio_tickers: List[str]) -> str:
    """
    Uses OpenAI's web search to fetch market info relevant to portfolio_tickers and generate a summary.
    """
    prompt = build_recap_prompt(portfolio_tickers)
    logging.info(f"[GPT] Generating focused market highlights for tickers: {', '.join(portfolio_tickers)}. Prompt snippet: '{prompt[:250]}...'")

    try:
        # Assuming client.responses.create is the intended method for models with web_search_preview
        # If using a different client structure (e.g. client.chat.completions.create with tools for gpt-4-turbo)
        # this part might need adjustment. The original code used client.responses.create.
        response = client.responses.create( # This API might be specific or deprecated.
                                           # Standard way for newer models is client.chat.completions.create
            model=OPENAI_MODEL,
            tools=[{"type": "web_search_preview"}], # web_search_preview tool
            input=prompt, # 'input' is typical for client.responses.create
        )
        recap_text = response.output_text.strip()

        if not recap_text:
            logging.warning("[GPT] API call for market recap returned an empty response.")
            return "⚠️ Market recap generation returned an empty response. Key events could not be summarized at this time."
        return recap_text
    except Exception as e:
        logging.error(f"[GPT] API call for market recap failed: {e}")
        logging.debug(traceback.format_exc())
        # Specific error handling from original code
        if "model_not_found" in str(e).lower() and "Responses API" in str(e).lower(): # Check error message content
             return (f"⚠️ Market Recap GPT API call failed: {e}. The model '{OPENAI_MODEL}' may not be "
                     f"supported with the Responses API and web_search_preview tool. "
                     f"Consider using 'gpt-4.1' or newer chat models with appropriate tool configuration.")
        elif "Rate limit" in str(e):
            return "⚠️ Market recap generation failed due to API rate limits. Please try again later."
        return f"⚠️ Market recap generation failed due to an API error: {e}"


def main():  # Example usage
    if not client.api_key:
        error_msg = (
            "OpenAI API key not found. "
            "Add it to st.secrets (or set the OPENAI_API_KEY env var)."
        )
        logging.error(error_msg)
        print(f"\n🚨 {error_msg}")
        return

    # Example tickers for testing market_recap.py directly
    example_tickers = ["AAPL", "MSFT", "GOOGL"]
    print(f"\n🔄 Generating Weekly Market Highlights for {', '.join(example_tickers)} using OpenAI Web Search...\n")
    summary = generate_market_recap_with_search(example_tickers)

    print("📊 Weekly Market Highlights (AI-generated with Web Search)\n")
    print(summary)

if __name__ == "__main__":
    main()