import chromadb
from chromadb.config import Settings
import os
import shutil

print("=" * 80)
print("DIRECT ChromaDB TEST")
print("=" * 80)

# Disable telemetry
os.environ["ANONYMIZED_TELEMETRY"] = "False"

# Create client
client = chromadb.PersistentClient(
    path="./test_chroma_debug",
    settings=Settings(anonymized_telemetry=False, allow_reset=True)
)

print("\n✅ ChromaDB client created")

# Create collection
collection = client.create_collection("test")
print("✅ Collection created")

# TEST 1: Add with valid metadata
print("\n" + "=" * 80)
print("TEST 1: Valid metadata (NO embeddings)")
print("=" * 80)
try:
    collection.add(
        documents=["test document"],
        metadatas=[{"type": "readme", "source": "test.md"}],
        ids=["doc1"]
    )
    print("✅ SUCCESS with valid metadata!")
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()

# TEST 2: Add with embeddings
print("\n" + "=" * 80)
print("TEST 2: Valid metadata WITH embeddings")
print("=" * 80)
try:
    collection.add(
        documents=["test document 2"],
        metadatas=[{"type": "readme", "source": "test2.md"}],
        ids=["doc2"],
        embeddings=[[0.1] * 384]  # 384 dims for MiniLM
    )
    print("✅ SUCCESS with embeddings!")
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()

# TEST 3: Add with EMPTY metadata
print("\n" + "=" * 80)
print("TEST 3: EMPTY metadata (should fail)")
print("=" * 80)
try:
    collection.add(
        documents=["test document 3"],
        metadatas=[{}],  # EMPTY!
        ids=["doc3"],
        embeddings=[[0.2] * 384]
    )
    print("✅ SUCCESS with empty metadata (unexpected!)")
except Exception as e:
    print(f"❌ FAILED as expected: {e}")

# Query count
print("\n" + "=" * 80)
print(f"FINAL: Collection count: {collection.count()}")
print("=" * 80)

# Cleanup
try:
    client.delete_collection("test")
    print("\n✅ Collection deleted")
except:
    pass

try:
    if os.path.exists("./test_chroma_debug"):
        shutil.rmtree("./test_chroma_debug")
        print("✅ Test folder deleted")
except:
    print("⚠️ Could not delete test folder (file in use)")

print("\n✅ Test complete!")