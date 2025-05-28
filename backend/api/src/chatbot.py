from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
import boto3
import tempfile
import shutil

load_dotenv()

INDEX_PATH = "shared/index/"

S3_BUCKET = os.getenv("S3_BUCKET")
S3_PREFIX = "shared/index/"  # The folder in S3 where index files are stored

def download_index_from_s3():
    s3 = boto3.client('s3')
    temp_dir = tempfile.mkdtemp()
    
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = os.path.join(temp_dir, os.path.basename(key))
            s3.download_file(S3_BUCKET, key, filename)

    print("Got S3 BUCKET!!")
    print(temp_dir)

    return temp_dir

def load_chain():
    embeddings = OpenAIEmbeddings()
    index_dir = download_index_from_s3()

    db = FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)
    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 3})

    llm = ChatOpenAI(temperature=0, model_name="gpt-4.1-nano")

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True
    )
    return qa_chain

def load_chain_with_sources():
    embeddings = OpenAIEmbeddings()
    index_dir = download_index_from_s3()

    db = FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)
    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 3})

    llm = ChatOpenAI(temperature=0, model_name="gpt-4.1-nano")

    chain = load_qa_with_sources_chain(llm, chain_type="stuff")
    return chain, retriever

def chatbot_call():
    print("🗳️  Polígrafo Fact-Check Chatbot (type 'exit' to quit)\n")
    qa = load_chain()

    while True:
        query = input("You: ")
        if query.lower() in ["exit", "quit"]:
            break

        result = qa.invoke(query)
        answer = result["result"]
        sources = [doc.metadata['title'] for doc in result['source_documents']]

        print(f"\n🤖 Answer: {answer}\n")
        print(f"📚 Sources:")
        seen = set()
        for doc in result['source_documents']:
            title = doc.metadata['title']
            url = doc.metadata.get('source')
            if title not in seen:
                print(f"- {title} ({url})")
                seen.add(title)
        print("\n" + "-"*50)

def chatbot_call_with_sources():
    print("🗳️  Polígrafo Fact-Check Chatbot (type 'exit' to quit)\n")
    chain, retriever = load_chain_with_sources()

    while True:
        query = input("You: ")
        if query.lower() in ["exit", "quit"]:
            break

        docs = retriever.get_relevant_documents(query)
        result = chain.invoke({"input_documents": docs, "question": query})

        print(f"\n🤖 Answer: {result['output_text']}\n")

        print("📚 Retrieved Chunks Used:")
        seen = set()
        for doc in docs:
            src = doc.metadata['title']
            url = doc.metadata.get('source')
            if src not in seen:
                print(f"\n🔹 {src} ({url}):\n{doc.page_content[:300].strip()}...\n")
                seen.add(src)

        print("-" * 50)

def get_fact_check_response(prompt: str, threshold: float = None, k: int = 3) -> dict:
    chain, retriever = load_chain_with_sources()

    # Perform similarity search with scores
    results_with_scores = retriever.vectorstore.similarity_search_with_score(prompt, k=k)

    filtered_results = []
    for doc, score in results_with_scores:
        if threshold is None or score <= threshold:
            filtered_results.append((doc, score))

    # If no documents passed the threshold, fallback to the highest match
    if not filtered_results and results_with_scores:
        filtered_results = [results_with_scores[0]]

    docs = [doc for doc, _ in filtered_results]
    result = chain.invoke({"input_documents": docs, "question": prompt})

    sources = []
    chunks = []
    verdicts = []
    scores = []

    seen = set()

    for doc, score in filtered_results:
        title = doc.metadata.get("title", "Unknown Title")
        url = doc.metadata.get("source", "")
        verdict = doc.metadata.get("verdict", "Unknown")

        identifier = f"{title} ({url})"
        if identifier not in seen:
            sources.append({"title": title, "url": url})
            chunks.append(doc.page_content.strip())
            verdicts.append(verdict)
            scores.append(score)
            seen.add(identifier)

    return {
        "answer": result["output_text"],
        "sources": sources,
        "chunks": chunks,
        "verdicts": verdicts,
        "scores": scores
    }

def main():
    chatbot_call_with_sources()

if __name__ == "__main__":
    main()