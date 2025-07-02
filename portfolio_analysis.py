import logging
import traceback
import os
import pandas as pd
import yfinance as yf
from openai import OpenAI
from typing import Dict, Any

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
# -----------------------------

# ---------- CONFIG (for standalone testing of this module) ----------
TICKERS_STANDALONE_TEST = [
    "AMZN", "AVGO", "BMY", "NVDA",
    "MSFT", "AAPL"
]
# -----------------------------

def yahoo_friendly(tkr: str) -> str:
    return tkr.replace("/", "-").replace(".", "-")

def company_name(ticker: str) -> str:
    try:
        info = yf.Ticker(yahoo_friendly(ticker)).info or {}
        return info.get("longName") or info.get("shortName") or ticker
    except Exception as e:
        logging.warning(f"Could not fetch company name for {ticker}: {e}")
        return ticker

def get_price_performance(ticker: str, start_date: pd.Timestamp, end_date: pd.Timestamp, period_name: str = "period") -> Dict[str, Any]:
    yf_ticker = yahoo_friendly(ticker)
    
    df = yf.download(
        yf_ticker,
        start=start_date - pd.Timedelta(days=7),
        end=end_date + pd.Timedelta(days=1),
        progress=False,
        auto_adjust=True,
    )

    if df.empty:
        raise ValueError(f"No price data returned by yfinance for {ticker} in the initial wide fetch.")

    if df.index.tz is None:
        logging.debug(f"DataFrame index for {ticker} is timezone-naive. Localizing to UTC.")
        try:
            df.index = df.index.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')
        except Exception as e_localize:
            logging.error(f"Failed to localize naive index for {ticker} to UTC: {e_localize}")
            raise ValueError(f"Timezone localization failed for {ticker}") from e_localize
    elif df.index.tz.zone != 'UTC':
        df.index = df.index.tz_convert('UTC')

    df_after_start = df[df.index >= start_date.normalize()]
    if df_after_start.empty:
        raise ValueError(f"No data available for {ticker} on or after {start_date.normalize().date()}")
    first_row = df_after_start.iloc[0]
    actual_start_date_ts = first_row.name

    df_before_end = df[df.index <= end_date]
    if df_before_end.empty:
        if actual_start_date_ts <= end_date:
            last_row = first_row
        else:
            raise ValueError(f"No data available for {ticker} on or before {end_date.date()} after filtering from start.")
    else:
        last_row = df_before_end.iloc[-1]
    actual_end_date_ts = last_row.name
    
    first_close_raw = first_row["Close"]
    last_close_raw = last_row["Close"]

    # --- Ensure first_close and last_close are scalars ---
    if isinstance(first_close_raw, pd.Series):
        if first_close_raw.empty:
            raise ValueError(f"Extracted 'Close' Series is empty for first price point for {ticker}")
        first_close = first_close_raw.item()
    else:
        first_close = first_close_raw

    if isinstance(last_close_raw, pd.Series):
        if last_close_raw.empty:
            raise ValueError(f"Extracted 'Close' Series is empty for last price point for {ticker}")
        last_close = last_close_raw.item()
    else:
        last_close = last_close_raw
    
    # Convert to float for consistent type handling, especially before pd.isna
    try:
        first_close = float(first_close)
        last_close = float(last_close)
    except (ValueError, TypeError) as e_conv:
        # This handles cases where conversion to float fails (e.g., None, non-numeric string if not caught by .item())
        logging.error(f"Cannot convert price to float for {ticker}. First raw: '{first_close_raw}', Last raw: '{last_close_raw}'. Error: {e_conv}")
        raise ValueError(f"Non-numeric or unconvertible price found for {ticker}") from e_conv

    if pd.isna(first_close) or pd.isna(last_close):
        raise ValueError(f"NaN price found for {ticker}. Processed First: {first_close}, Processed Last: {last_close} (Raw First: {first_close_raw}, Raw Last: {last_close_raw})")

    abs_change = last_close - first_close
    pct_change = (abs_change / first_close) * 100 if first_close != 0 else 0.0

    return {
        "ticker": ticker.upper(),
        "period_name": period_name,
        "first_date": actual_start_date_ts.date().isoformat(),
        "last_date": actual_end_date_ts.date().isoformat(),
        "first_close": round(first_close, 2),
        "last_close": round(last_close, 2),
        "abs_change": round(abs_change, 2),
        "pct_change": round(pct_change, 2),
    }

def build_prompt_for_holding(price_block: dict, long_name: str) -> str:
    period_desc = price_block.get('period_name', 'recent performance')
    direction = "up" if price_block['pct_change'] >= 0 else "down"
    
    return (
        f"Create a bullet-point analysis for a client newsletter about {long_name} ({price_block['ticker']}).\n"
        f"The stock is {direction} ${abs(price_block['abs_change'])} ({price_block['pct_change']}%) for the {period_desc}.\n\n"
        f"Format your response as exactly 3-4 bullet points using this structure:\n"
        f"• **Performance**: [One sentence about the price movement and percentage change]\n"
        f"• **Key Driver**: [Main factor or news that influenced this performance, with cited source]\n"
        f"• **Additional Context**: [Secondary factor, analyst opinion, or sector trend, with cited source]\n"
        f"• **Outlook**: [Brief forward-looking sentiment or upcoming catalyst]\n\n"
        f"Requirements:\n"
        f"- Use **credible, cited news sources** found via web search\n"
        f"- Include inline URL citations (e.g., [Source URL]) for any news mentioned\n"
        f"- Keep each bullet point to 1-2 sentences maximum\n"
        f"- Use clear, professional language without jargon\n"
        f"- Focus on information from the past month\n\n"
        f"Return ONLY the bullet points, no introduction or conclusion."
    )

def gpt_paragraph_for_holding(price_block: dict, long_name: str, openai_client: OpenAI, model_name: str) -> str:
    try:
        prompt = build_prompt_for_holding(price_block, long_name)
        logging.info(f"[GPT - {price_block['ticker']}] Generating holding analysis. Prompt: '{prompt[:150]}...'")
        
        response = openai_client.responses.create(
            model=model_name,
            tools=[{"type": "web_search_preview"}],
            input=prompt,
        )
        analysis = response.output_text.strip()
        if not analysis:
            logging.warning(f"[GPT - {price_block['ticker']}] API call returned an empty response for holding analysis.")
            return f"⚠️ GPT could not generate a summary for {price_block['ticker']} at this time."
        return analysis
    except Exception as e:
        logging.error(f"[GPT - {price_block['ticker']}] API call for holding analysis failed: {e}")
        logging.debug(traceback.format_exc())
        if "model_not_found" in str(e).lower() and "Responses API" in str(e).lower():
             return (f"⚠️ GPT API call failed for {price_block['ticker']}: {e}. The model '{model_name}' may not be "
                     f"supported with the Responses API and web_search_preview. "
                     f"Consider 'gpt-4.1' or ensure the model supports this endpoint.")
        return f"⚠️ GPT call failed for {price_block['ticker']}: {e}"


def main(): # For standalone testing of portfolio_analysis.py
    test_api_key = os.environ.get("OPENAI_API_KEY")
    if not test_api_key:
        logging.error("OpenAI API key not found (OPENAI_API_KEY env var). Aborting test.")
        return
        
    test_client = OpenAI(api_key=test_api_key)
    test_model = "gpt-4.1-mini"

    print("\n🔍 Portfolio Analysis Test Output (Standalone)\n")
    today = pd.Timestamp.utcnow()
    
    print("\n--- YTD Performance Test ---")
    ytd_start = today.replace(month=1, day=1).normalize()
    for tkr in TICKERS_STANDALONE_TEST[:2]:
        try:
            ytd_perf = get_price_performance(tkr, ytd_start, today, period_name="year-to-date")
            logging.info(
                f"[{tkr}] YTD: {ytd_perf['first_date']} (${ytd_perf['first_close']}) -> "
                f"{ytd_perf['last_date']} (${ytd_perf['last_close']}) | Δ {ytd_perf['pct_change']:.2f}%"
            )
        except Exception as err:
            logging.error(f"[{tkr}] YTD Test Error: {err}")
            logging.debug(traceback.format_exc())

    print("\n--- GPT Holding Analysis (Month-to-Date Example) ---")
    mtd_start = today.replace(day=1).normalize()
    for tkr in TICKERS_STANDALONE_TEST[:1]:
        try:
            price_data_mtd = get_price_performance(tkr, mtd_start, today, period_name="month-to-date")
            c_name = company_name(tkr)
            analysis = gpt_paragraph_for_holding(price_data_mtd, c_name, test_client, test_model)
            print(f"\n📄 Newsletter analysis for {tkr} ({c_name}):\n{analysis}\n")
        except Exception as err:
            logging.error(f"[{tkr}] GPT Analysis Test Error: {err}")
            logging.debug(traceback.format_exc())

if __name__ == "__main__":
    main()