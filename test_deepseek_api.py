#!/usr/bin/env python3
"""
Test DeepSeek API response time
"""
import time
import requests
import json

API_KEY = "sk-7b642bafd33846758519704596d25ea8"
API_URL = "https://api.deepseek.com/v1/chat/completions"

def test_deepseek_api():
    """Test DeepSeek API with a simple request"""
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'Hello' in one word."}
        ],
        "temperature": 0.7,
        "max_tokens": 10
    }
    
    print("[TEST] Testing DeepSeek API...")
    print(f"[INFO] API URL: {API_URL}")
    print(f"[INFO] Model: deepseek-chat")
    print(f"[INFO] Test message: Simple 1-word response request")
    print("-" * 60)
    
    try:
        start_time = time.time()
        print(f"[{time.strftime('%H:%M:%S')}] Sending request...")
        
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=60  # 60 second timeout for testing
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"[{time.strftime('%H:%M:%S')}] Response received!")
        print(f"[TIMING] Total time: {elapsed_time:.2f} seconds")
        print(f"[STATUS] HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("[SUCCESS] API is working!")
            print(f"[RESPONSE] {json.dumps(result, indent=2)}")
            
            # Extract usage info if available
            if 'usage' in result:
                usage = result['usage']
                print("\n[USAGE INFO]")
                print(f"  - Prompt tokens: {usage.get('prompt_tokens', 'N/A')}")
                print(f"  - Completion tokens: {usage.get('completion_tokens', 'N/A')}")
                print(f"  - Total tokens: {usage.get('total_tokens', 'N/A')}")
            
            return True
        else:
            print(f"[ERROR] API returned error status: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"[TIMEOUT] Request timed out after {elapsed_time:.2f} seconds")
        print("[WARNING] DeepSeek API is responding very slowly or not at all")
        return False
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request failed: {e}")
        return False
        
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False


def test_with_longer_prompt():
    """Test with a longer prompt similar to trading agent"""
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # Simulate a trading prompt
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system", 
                "content": "You are a stock trading assistant. Analyze market data and make trading decisions."
            },
            {
                "role": "user", 
                "content": "Please analyze today's (2025-10-23) market conditions for NVDA, MSFT, AAPL. What should I do?"
            }
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    print("\n" + "=" * 60)
    print("[TEST 2] Testing with trading-like prompt...")
    print("-" * 60)
    
    try:
        start_time = time.time()
        print(f"[{time.strftime('%H:%M:%S')}] Sending request...")
        
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"[{time.strftime('%H:%M:%S')}] Response received!")
        print(f"[TIMING] Total time: {elapsed_time:.2f} seconds")
        print(f"[STATUS] HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("[SUCCESS] Trading-like prompt works!")
            
            # Show response preview
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0].get('message', {}).get('content', '')
                preview = content[:200] + "..." if len(content) > 200 else content
                print(f"[RESPONSE PREVIEW] {preview}")
            
            return True
        else:
            print(f"[ERROR] API returned error: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"[TIMEOUT] Request timed out after {elapsed_time:.2f} seconds")
        return False
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("DeepSeek API Health Check")
    print("=" * 60)
    
    # Test 1: Simple request
    test1_success = test_deepseek_api()
    
    # Test 2: Trading-like request (only if first test passed)
    if test1_success:
        test2_success = test_with_longer_prompt()
        
        print("\n" + "=" * 60)
        print("[SUMMARY]")
        print("=" * 60)
        if test1_success and test2_success:
            print("[OK] DeepSeek API is responding normally")
            print("[TIP] The timeout in your trading system might be too aggressive")
            print("[TIP] Consider keeping timeout at 120 seconds or higher")
        elif test1_success:
            print("[WARNING] Simple requests work but complex ones may timeout")
            print("[TIP] Increase timeout or simplify prompts")
        else:
            print("[ERROR] DeepSeek API has issues")
    else:
        print("\n[ERROR] DeepSeek API is not responding properly")
        print("[TIP] Check:")
        print("  1. API key validity")
        print("  2. Network connection")
        print("  3. DeepSeek service status")

