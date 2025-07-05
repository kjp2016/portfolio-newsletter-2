#!/usr/bin/env python3
"""
Test to check if quota issue is model-specific.
"""

import os
import toml
from openai import OpenAI

def test_different_models():
    """Test different OpenAI models to isolate the issue."""
    
    # Load API key
    secrets_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
    secrets = toml.load(secrets_path)
    api_key = secrets.get("OPENAI_API_KEY")
    
    client = OpenAI(api_key=api_key)
    
    models_to_test = [
        "gpt-3.5-turbo",
        "gpt-4o-mini", 
        "gpt-4o"
    ]
    
    print("🧪 Testing Different OpenAI Models")
    print("=" * 40)
    
    for model in models_to_test:
        print(f"\n🔄 Testing {model}...")
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say 'Hello'"}],
                max_tokens=5
            )
            print(f"✅ {model}: {response.choices[0].message.content}")
        except Exception as e:
            print(f"❌ {model}: {str(e)[:100]}...")

if __name__ == "__main__":
    test_different_models() 