import requests
from config import Config

# Test CompreFace connection
COMPREFACE_BASE_URL = f"{Config.COMPREFACE_URL}/api/v1"
HEADERS = {
    'x-api-key': Config.COMPREFACE_API_KEY
}

print(f"Testing CompreFace connection...")
print(f"URL: {COMPREFACE_BASE_URL}")
print(f"API Key: {Config.COMPREFACE_API_KEY}")

try:
    # Test getting subjects
    response = requests.get(
        f"{COMPREFACE_BASE_URL}/recognition/subjects",
        headers=HEADERS,
        timeout=10
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("\n✅ Connection successful!")
        subjects = response.json().get('subjects', [])
        print(f"Current subjects: {subjects}")
    elif response.status_code == 401:
        print("\n❌ Authentication failed! Check your API key.")
    else:
        print(f"\n❌ Unexpected response: {response.status_code}")
        
except Exception as e:
    print(f"\n❌ Connection failed: {str(e)}")
    print("Make sure CompreFace is running and accessible.")