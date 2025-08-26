"""
Test script to manually trigger option chain start
Run this after ensuring you have a primary account set up
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"

def test_option_chain_trigger():
    """Test manual option chain trigger"""
    
    print("Testing Option Chain Manual Trigger")
    print("-" * 40)
    
    # First, we need to login (you'll need to update credentials)
    print("\n1. Login required - Please login via browser first")
    print("   Go to: http://localhost:8000/auth/login")
    print("   Then check the status at: http://localhost:8000/api/option-chain/status")
    
    print("\n2. To manually start option chains:")
    print("   Make a POST request to: http://localhost:8000/api/option-chain/start")
    print("   (Must be logged in)")
    
    print("\n3. Alternative - Use the browser console:")
    print("   Open browser DevTools (F12)")
    print("   Go to Console tab")
    print("   Run this JavaScript:")
    print("""
    fetch('/api/option-chain/start', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        }
    })
    .then(response => response.json())
    .then(data => console.log('Option chains started:', data))
    .catch(error => console.error('Error:', error));
    """)
    
    print("\n4. Check status:")
    print("""
    fetch('/api/option-chain/status')
    .then(response => response.json())
    .then(data => console.log('Status:', data))
    .catch(error => console.error('Error:', error));
    """)

if __name__ == "__main__":
    test_option_chain_trigger()