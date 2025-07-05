#!/usr/bin/env python3
"""
Test script to see what the actual AI responses look like for holding analysis
"""

import logging
import pandas as pd
from openai import OpenAI
import streamlit as st
from portfolio_analysis import build_prompt_for_holding

# Set up logging
logging.basicConfig(level=logging.INFO)

def test_analysis_format():
    """Test what the AI actually returns for holding analysis"""
    print("=== Testing AI Analysis Format ===")
    
    # Mock price block for testing
    price_block = {
        'ticker': 'AMZN',
        'pct_change': 1.83,
        'abs_change': 4.02,
        'period_name': 'weekly'
    }
    
    long_name = "Amazon.com Inc."
    
    # Build the prompt
    prompt = build_prompt_for_holding(price_block, long_name)
    print(f"\nPrompt:\n{prompt}")
    
    # Get the response
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            tools=[{"type": "web_search_preview"}],
            input=prompt
        )
        
        output_text = response.output_text
        print(f"\n=== ACTUAL AI RESPONSE ===")
        print(output_text)
        print(f"\n=== RESPONSE LENGTH: {len(output_text)} ===")
        
        # Check what's in the response
        print(f"\n=== ANALYSIS ===")
        print(f"Contains '•': {'•' in output_text}")
        print(f"Contains '*': {'*' in output_text}")
        print(f"Contains '-': {'-' in output_text}")
        print(f"Contains 'Performance:': {'Performance:' in output_text}")
        print(f"Contains 'Key Driver:': {'Key Driver:' in output_text}")
        print(f"Contains 'Additional Context:': {'Additional Context:' in output_text}")
        print(f"Contains 'Outlook:': {'Outlook:' in output_text}")
        
        # Check for any bullet-like patterns
        lines = output_text.split('\n')
        bullet_lines = [line for line in lines if any(char in line for char in ['•', '*', '-'])]
        print(f"\nBullet lines found: {len(bullet_lines)}")
        for i, line in enumerate(bullet_lines[:3]):  # Show first 3
            print(f"  {i+1}: {line.strip()}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_analysis_format() 