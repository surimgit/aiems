import requests
import time

BASE_URL = "http://localhost:8080/api/edges"
EDGE_ID = "solar-edge-test"

def test_api():
    print("=== 1. Add New Edge ===")
    payload = {
        "edge_id": EDGE_ID,
        "edge_type": "solar",
        "plant_id": "TEST-PLANT"
    }
    res = requests.post(BASE_URL, json=payload)
    print(f"POST {BASE_URL} -> Status: {res.status_code}")
    print(f"Response: {res.text}")
    
    # 컨테이너가 구동될 시간을 잠시 대기
    time.sleep(3)
    
    print("\n=== 2. Add Device ===")
    device_url = f"{BASE_URL}/{EDGE_ID}/devices"
    device_payload = {
        "device_id": "solar-test-01",
        "device_type": "solar",
        "capacity_kw": 100
    }
    res = requests.post(device_url, json=device_payload)
    print(f"POST {device_url} -> Status: {res.status_code}")
    print(f"Response: {res.text}")

    print("\n=== 3. Verify Edge Status ===")
    res = requests.get(BASE_URL)
    if res.status_code == 200:
        edges = res.json()
        for e in edges:
            if e['edge_id'] == EDGE_ID:
                print(f"Found Edge: {e['edge_id']}, Status: {e['status']}, Devices: {e.get('devices_count')}")

    print("\n=== 4. Remove Edge ===")
    delete_url = f"{BASE_URL}/{EDGE_ID}"
    res = requests.delete(delete_url)
    print(f"DELETE {delete_url} -> Status: {res.status_code}")
    print(f"Response: {res.text}")

if __name__ == "__main__":
    test_api()
