"""Start backend server and run Alice evaluation."""
import subprocess
import urllib.request
import json
import time
import sys
import os
import signal

BACKEND = "http://localhost:8000"
ALICE_ID = "9bbc4055-4532-47fa-8ba7-c84272cd3c4c"

QUESTIONS = [
    ("1", "What did Alice find inside the tiny door after she drank from the bottle labeled DRINK ME?"),
    ("2", "Who did Alice meet sitting on a mushroom smoking a hookah, and what question did this character keep asking her?"),
    ("3", "What happened to Alice every time she ate a piece of the cake or drank from a bottle in the story?"),
    ("4", "What rules did the Queen of Hearts enforce during the croquet game, and what was unusual about the equipment used?"),
    ("5", "Which characters sat at the Mad Hatter's tea party, and why was Time stuck at 6 o'clock?"),
    ("6", "What was the exact evidence presented against the Knave of Hearts during his trial?"),
    ("7", "Which characters threatened off with their head and who specifically did each target?"),
    ("8", "What songs or poems appear in Alice's Adventures in Wonderland, and which character recited each one?"),
    ("9", "How does Alice's size and confidence change from her arrival in Wonderland to her final confrontation with the Queen?"),
    ("10", "What did the Mock Turtle describe as the subjects taught at his school, and what was the Drawling-master pattern?"),
]

# Start server
print("Starting backend server...")
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    cwd=os.path.join(os.path.dirname(__file__), ".."),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

# Wait for server
for i in range(30):
    try:
        r = urllib.request.urlopen(f"{BACKEND}/api/health", timeout=2)
        print(f"Server ready: {r.read().decode()}")
        break
    except:
        time.sleep(1)
else:
    print("Server failed to start")
    server.terminate()
    sys.exit(1)

# Also wait a bit more for lifespan to complete
time.sleep(3)

# Run each question
results = []
for num, question in QUESTIONS:
    print(f"\n{'='*60}")
    print(f"Q{num}: {question}")
    print(f"{'='*60}")
    
    body = json.dumps({"question": question, "document_ids": [ALICE_ID], "save_message": False}).encode()
    req = urllib.request.Request(
        f"{BACKEND}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        r = urllib.request.urlopen(req, timeout=180)
        resp = json.loads(r.read().decode())
        answer = resp.get("answer", "")
        sources = resp.get("sources", [])
        print(f"Answer ({len(answer)} chars): {answer[:600]}..." if len(answer) > 600 else f"Answer: {answer}")
        print(f"Sources: {len(sources)} chunks")
        for s in sources[:4]:
            score = s.get("rerank_score") or s.get("fusion_score") or s.get("qdrant_score") or ""
            heading = s.get("heading") or ""
            neighbor = " [neighbor]" if s.get("is_neighbor_context") else ""
            print(f"  chunk {s.get('chunk_index','')} score={score}{neighbor} heading={heading}")
        results.append({"num": num, "question": question, "answer": answer, "sources": sources, "source_count": len(sources)})
    except Exception as e:
        print(f"FAILED: {e}")
        results.append({"num": num, "question": question, "error": str(e)})

# Stop server
server.terminate()
server.wait()

# Summary
print(f"\n\n{'='*60}")
print("EVALUATION SUMMARY")
print(f"{'='*60}")
passed = sum(1 for r in results if r.get("answer") and len(r.get("answer","")) > 20)
total = len(results)
print(f"Score: {passed}/{total}")
for r in results:
    status = "PASS" if r.get("answer") and len(r.get("answer","")) > 20 else "FAIL"
    detail = r.get("answer","")[:80] if status == "PASS" else r.get("error","no answer")
    sources = r.get("source_count", 0)
    print(f"  Q{r['num']}: {status} [{sources} src] {detail}...")
