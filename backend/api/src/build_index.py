import json
import os
import tempfile
import boto3
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client("s3")
S3_BUCKET = os.getenv("S3_BUCKET", "your-bucket-name")
S3_ARTICLES_KEY = "data/articles.json"
S3_INDEX_KEY_PREFIX = "index/"
S3_URLS_KEY = f"{S3_INDEX_KEY_PREFIX}indexed_urls.json"

def load_from_s3(key):
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except s3.exceptions.NoSuchKey:
        return []
    except Exception as e:
        print(f"⚠️ Error loading {key} from S3: {e}")
        return []

def save_to_s3(data, key):
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    )

def load_documents():
    raw_docs = load_from_s3(S3_ARTICLES_KEY)
    documents = []
    for item in raw_docs:
        metadata = {
            "source": item["url"],
            "title": item["title"],
            "verdict": item["verdict"]
        }
        documents.append(Document(
            page_content=item["content"],
            metadata=metadata
        ))
    return documents

def upload_faiss_index(local_path, s3_prefix):
    for root, _, files in os.walk(local_path):
        for fname in files:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, local_path)
            s3_key = os.path.join(s3_prefix, rel_path)
            s3.upload_file(full_path, S3_BUCKET, s3_key)

def download_faiss_index(local_path, s3_prefix):
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=S3_BUCKET, Prefix=s3_prefix)
    for page in pages:
        for obj in page.get('Contents', []):
            s3_key = obj['Key']
            rel_path = os.path.relpath(s3_key, s3_prefix)
            full_path = os.path.join(local_path, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            s3.download_file(S3_BUCKET, s3_key, full_path)

def build_index():
    docs = load_documents()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    split_docs = splitter.split_documents(docs)
    embeddings = OpenAIEmbeddings()

    indexed_urls = set(load_from_s3(S3_URLS_KEY))
    all_new_chunks = []
    new_urls = set()

    for doc in split_docs:
        url = doc.metadata.get("source")
        if url and url not in indexed_urls:
            all_new_chunks.append(doc)
            new_urls.add(url)

    with tempfile.TemporaryDirectory() as tmpdir:
        index_path = os.path.join(tmpdir, "faiss")

        index_exists = False
        try:
            download_faiss_index(index_path, S3_INDEX_KEY_PREFIX)
            index_exists = True
        except Exception as e:
            print(f"ℹ️ No existing FAISS index found in S3: {e}")

        index_file = os.path.join(index_path, "index.faiss")
        pkl_file = os.path.join(index_path, "index.pkl")
        index_exists = os.path.exists(index_file) and os.path.exists(pkl_file)

        if index_exists:
            print("🔁 Existing index found. Merging new documents...")
            db = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)

            if all_new_chunks:
                db.add_documents(all_new_chunks)
                db.save_local(index_path)
                upload_faiss_index(index_path, S3_INDEX_KEY_PREFIX)
                save_to_s3(sorted(indexed_urls.union(new_urls)), S3_URLS_KEY)
                print(f"✅ Added {len(new_urls)} new source URLs.")
            else:
                print("ℹ️ No new documents to add.")
        else:
            print("📦 No existing index. Creating new one...")
            db = FAISS.from_documents(all_new_chunks, embeddings)
            db.save_local(index_path)
            upload_faiss_index(index_path, S3_INDEX_KEY_PREFIX)
            save_to_s3(sorted(new_urls), S3_URLS_KEY)
            print(f"✅ Index created with {len(new_urls)} source URLs.")

if __name__ == "__main__":
    build_index()