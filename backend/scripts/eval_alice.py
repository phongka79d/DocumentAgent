"""Start backend server and run Alice evaluation."""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

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

SAFE_INSUFFICIENT_CONTEXT_MESSAGE = "The indexed documents do not contain enough information to answer this question."


def status_for_coverage(*, matched_groups: int, required_groups: int) -> str:
    if required_groups == 0:
        return "PASS"
    if matched_groups == required_groups:
        return "PASS"
    if matched_groups > 0:
        return "PARTIAL"
    return "FAIL"


def load_rubric(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_coverage_with_llm(
    answer: str,
    required_groups: list[dict],
    api_client: object,
    model: str,
) -> list[str]:
    prompt = (
        "You are an expert quality evaluator. Read the following RAG system answer and determine which "
        "of the required information items are present in the text.\n\n"
        f"Answer to evaluate:\n\"\"\"\n{answer}\n\"\"\"\n\n"
        "Required Items to check:\n"
        + "\n".join(f"- [{item['id']}]: {item['description']}" for item in required_groups)
        + "\n\nReturn strict JSON only with a 'matched_ids' string array containing only the IDs of items present in the text. "
        "Do not include items that are missing or only partially guessed without correct character mapping."
    )
    response = api_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    try:
        result = json.loads(response.choices[0].message.content)
        return list(result.get("matched_ids", []))
    except Exception:
        return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", choices=[item[0] for item in QUESTIONS])
    args = parser.parse_args()
    selected_questions = [
        item for item in QUESTIONS if args.question is None or item[0] == args.question
    ]

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.join(script_dir, "..")
    rubric_path = os.path.join(project_dir, "evaluation", "datasets", "alice_coverage_v1.json")
    rubric_data = load_rubric(rubric_path) if os.path.exists(rubric_path) else {}

    # Start server
    print("Starting backend server...")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for server
    for i in range(30):
        try:
            r = urllib.request.urlopen(f"{BACKEND}/api/health", timeout=2)
            print(f"Server ready: {r.read().decode()}")
            break
        except Exception:
            time.sleep(1)
    else:
        print("Server failed to start")
        server.terminate()
        sys.exit(1)

    # Also wait a bit more for lifespan to complete
    time.sleep(3)

    # Run each question
    results = []
    for num, question in selected_questions:
        print(f"\n{'='*60}")
        print(f"Q{num}: {question}")
        print(f"{'='*60}")

        body = json.dumps({"question": question, "document_ids": [ALICE_ID], "save_message": False}).encode()
        req = urllib.request.Request(
            f"{BACKEND}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            r = urllib.request.urlopen(req, timeout=180)
            resp = json.loads(r.read().decode())
            answer = resp.get("answer", "")
            sources = resp.get("sources", [])
            metrics = resp.get("retrieval_metrics", {})
            print(f"Answer ({len(answer)} chars): {answer[:600]}..." if len(answer) > 600 else f"Answer: {answer}")
            print(f"Sources: {len(sources)} chunks")
            for s in sources[:4]:
                score = s.get("rerank_score") or s.get("fusion_score") or s.get("qdrant_score") or ""
                heading = s.get("heading") or ""
                neighbor = " [neighbor]" if s.get("is_neighbor_context") else ""
                print(f"  chunk {s.get('chunk_index','')} score={score}{neighbor} heading={heading}")
            print(f"  metrics: {json.dumps(metrics, default=str)[:300]}")

            # Rubric-based scoring for questions with required groups
            question_rubric = rubric_data.get(num, {})
            required_groups = question_rubric.get("required_groups", [])
            is_positive = question_rubric.get("positive_question", True)

            if required_groups:
                from openai import OpenAI

                client = OpenAI(
                    base_url=os.environ.get("SHOPAIKEY_BASE_URL", "https://api.shopaikey.com/v1"),
                    api_key=os.environ.get("SHOPAIKEY_API_KEY", ""),
                )
                matched_ids = evaluate_coverage_with_llm(
                    answer,
                    required_groups,
                    client,
                    os.environ.get("SHOPAIKEY_CHAT_MODEL", "gpt-4o-mini"),
                )
                matched_count = len(matched_ids)
                required_count = len(required_groups)

                # SAFE_INSUFFICIENT_CONTEXT_MESSAGE is FAIL for positive questions
                if answer.strip() == SAFE_INSUFFICIENT_CONTEXT_MESSAGE and is_positive:
                    status = "FAIL"
                else:
                    status = status_for_coverage(
                        matched_groups=matched_count,
                        required_groups=required_count,
                    )
                print(f"  Rubric: {matched_count}/{required_count} groups matched -> {status}")
                print(f"  Matched groups: {matched_ids}")
                results.append({
                    "num": num,
                    "question": question,
                    "answer": answer,
                    "sources": sources,
                    "source_count": len(sources),
                    "status": status,
                    "matched_groups": matched_ids,
                    "required_groups": required_count,
                    "retrieval_metrics": metrics,
                })
            else:
                status = "UNSCORED"
                print(f"  Status: UNSCORED (no rubric)")
                results.append({
                    "num": num,
                    "question": question,
                    "answer": answer,
                    "sources": sources,
                    "source_count": len(sources),
                    "status": status,
                    "retrieval_metrics": metrics,
                })
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
    for r in results:
        status = r.get("status", "FAIL")
        detail = r.get("answer", "")[:80] if status != "FAIL" else r.get("error", "no answer")
        sources = r.get("source_count", 0)
        matched = r.get("matched_groups", [])
        rubric_info = f" [{len(matched)}/{r.get('required_groups', 0)}]" if matched else ""
        print(f"  Q{r['num']}: {status}{rubric_info} [{sources} src] {detail}...")


if __name__ == "__main__":
    main()
