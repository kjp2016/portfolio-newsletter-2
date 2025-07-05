#!/usr/bin/env python3
"""
Simple test to check OpenAI API connectivity and quota status.
"""

import os
import sys
import toml
from openai import OpenAI

def test_openai_api():
    """Test basic OpenAI API connectivity."""
    
    # Load API key from secrets
    try:
        secrets_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
        secrets = toml.load(secrets_path)
        api_key = secrets.get("OPENAI_API_KEY")
        print(f"✅ API key loaded from secrets")
    except Exception as e:
        print(f"❌ Error loading secrets: {e}")
        return False
    
    # Initialize client
    client = OpenAI(api_key=api_key)
    
    print("🔄 Testing basic OpenAI API connectivity...")
    
    try:
        # Try a simple chat completion first (no web search)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'Hello, API is working!'"}],
            max_tokens=10
        )
        
        print(f"✅ Basic API test successful: {response.choices[0].message.content}")
        
        # Now try web search
        print("🔄 Testing web search capability...")
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "What is the current stock price of AAPL?"}],
            tools=[{
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for current information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }],
            tool_choice={"type": "function", "function": {"name": "web_search"}}
        )
        
        print(f"✅ Web search test successful: {response.choices[0].message.content[:100]}...")
        return True
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        
        # Check if it's a quota issue
        if "quota" in str(e).lower() or "insufficient" in str(e).lower():
            print("\n💡 This appears to be a quota/billing issue.")
            print("   - Check your OpenAI billing page: https://platform.openai.com/account/billing")
            print("   - Ensure your payment method is set up")
            print("   - Wait a few minutes if you just added a card")
        elif "rate" in str(e).lower():
            print("\n💡 This appears to be a rate limiting issue.")
            print("   - Wait a few minutes and try again")
            print("   - Check your usage limits in the OpenAI dashboard")
        else:
            print(f"\n💡 Unknown error type: {type(e).__name__}")
        
        return False

if __name__ == "__main__":
    print("🧪 Simple OpenAI API Test")
    print("=" * 40)
    
    success = test_openai_api()
    
    if success:
        print("\n🎉 API is working correctly!")
    else:
        print("\n💥 API test failed. Check the error messages above.")
        sys.exit(1) 