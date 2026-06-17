import sys
from pathlib import Path
from uuid import uuid4
from types import SimpleNamespace

# Add parent path to import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services import shopaikey_service
from app.core.config import get_settings

def main():
    settings = get_settings()
    print("API Key:", settings.shopaikey_api_key[:10] + "..." if settings.shopaikey_api_key else "None")
    print("Base URL:", settings.shopaikey_base_url)
    print("Rerank Model:", settings.shopaikey_rerank_model)
    print("Rerank Enabled:", settings.enable_rerank)

    # Prepare mock candidates
    c1 = SimpleNamespace(
        chunk_id=uuid4(),
        content="General policy background about company rules.",
        semantic_similarity=0.5,
    )
    c2 = SimpleNamespace(
        chunk_id=uuid4(),
        content="Refunds are available for 30 days if you provide the original receipt.",
        semantic_similarity=0.4,
    )
    c3 = SimpleNamespace(
        chunk_id=uuid4(),
        content="Shipping terms are listed in a separate document.",
        semantic_similarity=0.3,
    )

    candidates = [c1, c2, c3]
    question = "What is the refund period and what proof is required?"
    top_n = 2

    print(f"\nQuestion: {question}")
    print("Candidates before reranking:")
    for idx, c in enumerate(candidates):
        print(f"  {idx+1}. ID: {c.chunk_id} | Content: {c.content}")

    try:
        result = shopaikey_service.rerank_candidates(
            question=question,
            candidates=candidates,
            top_n=top_n
        )
        print("\nCandidates after reranking:")
        for idx, c in enumerate(result):
            print(f"  {idx+1}. ID: {c.chunk_id} | Content: {c.content}")
    except Exception as e:
        print(f"\nError occurred during reranking: {e}")

if __name__ == "__main__":
    main()
