import urllib.request
import urllib.parse
import json
import subprocess
import time
import os
import sys

def test_server():
    print("Testing portal server...")
    portal_dir = os.path.join(os.path.dirname(__file__), "..", "portal")
    launch_script = os.path.join(portal_dir, "launch_portal.py")
    
    port = 8999
    proc = subprocess.Popen(
        [sys.executable, launch_script, "--port", str(port), "--no-browser"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Give server time to spin up
        time.sleep(1.5)
        
        # Test 1: GET / -> sns_study_portal.html
        url_root = f"http://localhost:{port}/"
        with urllib.request.urlopen(url_root, timeout=5) as resp:
            content = resp.read().decode('utf-8')
            assert resp.status == 200, f"Expected status 200, got {resp.status}"
            assert "cycleChart" in content, "Cycle chart missing in served HTML"
            assert "dashboardPtlGrid" in content, "Picking station missing in served HTML"
            print(" [PASS] GET / serves upgraded sns_study_portal.html with 200 OK")

        # Test 2: GET /algorithms/randomizer.js
        url_rand = f"http://localhost:{port}/algorithms/randomizer.js"
        with urllib.request.urlopen(url_rand, timeout=5) as resp:
            js_content = resp.read().decode('utf-8')
            assert resp.status == 200
            assert "BalancedRandomizer" in js_content
            print(" [PASS] GET /algorithms/randomizer.js serves randomizer.js with 200 OK")

        # Test 3: POST /api/save_csv
        url_save = f"http://localhost:{port}/api/save_csv"
        post_data = json.dumps({
            "filename": "SNS_Study_Test.csv",
            "csv": "session_id,trial_id,role\nSESS-01,1,picker\n",
            "sessionId": "SESS-01",
            "operatorId": "OP-TEST"
        }).encode('utf-8')
        
        req = urllib.request.Request(
            url_save,
            data=post_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp_data = json.loads(resp.read().decode('utf-8'))
            assert resp_data["status"] == "success"
            assert os.path.exists(resp_data["filepath"])
            print(f" [PASS] POST /api/save_csv wrote {resp_data['filename']} successfully")
            
            # Clean up test file
            try:
                os.remove(resp_data["filepath"])
            except Exception:
                pass

        print("\nALL SERVER INTEGRATION TESTS PASSED!\n")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

if __name__ == "__main__":
    test_server()
