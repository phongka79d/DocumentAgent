"""Query Supabase for documents, find Alice document."""
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
client = create_client(url, key)

# List all documents
data = client.table("documents").select("id, title, file_name, status, total_chunks, indexed_at, total_pages, file_size, mime_type").execute()
print(f"Total documents: {len(data.data)}")
for d in data.data:
    print(f"  ID={d['id']} | title={d['title']} | file={d['file_name']} | status={d['status']} | chunks={d['total_chunks']} | pages={d['total_pages']}")

# Find Alice document
alice = None
for d in data.data:
    t = (d.get("title") or "").lower()
    f = (d.get("file_name") or "").lower()
    if "alice" in t or "alice" in f:
        alice = d
        print(f"\n*** ALICE DOCUMENT FOUND ***")
        print(f"  ID: {d['id']}")
        print(f"  Title: {d['title']}")
        print(f"  File: {d['file_name']}")
        print(f"  Status: {d['status']}")
        print(f"  Chunks: {d['total_chunks']}")
        print(f"  Pages: {d['total_pages']}")
        print(f"  MIME: {d['mime_type']}")
        print(f"  Indexed: {d['indexed_at']}")
        break

if alice:
    # Get chunks for Alice
    doc_id = alice['id']
    chunks = client.table("document_chunks").select("chunk_index, content, token_count, heading, page_start, page_end, chunk_type").eq("document_id", doc_id).order("chunk_index").execute()
    print(f"\nTotal chunks: {len(chunks.data)}")
    # Print first 3 and last 2 chunks to understand content
    for c in chunks.data[:5]:
        preview = c['content'][:200] if c['content'] else ""
        print(f"\n  Chunk {c['chunk_index']} ({c['token_count']} tokens, {c['chunk_type']}):")
        print(f"    Heading: {c['heading']}")
        print(f"    Preview: {preview}...")
else:
    print("\nNo Alice document found. All documents listed above.")
    # Print first chunk of each document to help identify content
    for d in data.data[:3]:
        first_chunks = client.table("document_chunks").select("chunk_index, content").eq("document_id", d['id']).limit(1).execute()
        if first_chunks.data:
            print(f"\n  Doc {d['file_name']} preview: {first_chunks.data[0]['content'][:150]}...")
