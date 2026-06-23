"""Sample Alice chunks to understand story coverage."""
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()
client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
chunks = client.table("document_chunks").select("chunk_index, content, token_count, heading").eq("document_id", "9bbc4055-4532-47fa-8ba7-c84272cd3c4c").order("chunk_index").execute()

for c in chunks.data:
    idx = c["chunk_index"]
    content = c["content"][:200].replace("\n", " | ")
    if idx < 8 or (idx >= 30 and idx <= 35) or (idx >= 60 and idx <= 65) or (idx >= 100 and idx <= 108) or idx >= 114:
        print(f"Chunk {idx} ({c['token_count']}t): {content}")
        print()
