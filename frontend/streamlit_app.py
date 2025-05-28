import streamlit as st
import requests
import os

hide_streamlit_style = """
    <style>
    .stAppToolbar {visibility: hidden;}
    </style>
"""





API_URL = os.getenv("API_URL") + "ask"

st.set_page_config(page_title="Polígrafo Fact-Check Chatbot", page_icon="🗳️")

st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title("🗳️ Polígrafo Fact-Check Chatbot")
st.markdown("Ask a question and get a verified response based on real fact-checked articles from Polígrafo.")

# Input box
query = st.text_input("Enter your question here", placeholder="e.g. O Chega ganhou mesmo em 60 concelhos?")

if st.button("Ask") and query:
    with st.spinner("Consulting Polígrafo..."):
        try:
            response = requests.post(API_URL, json={"query": query, "source_threshold": 0.8})
            if response.status_code == 200:
                data = response.json()

                # Display answer
                st.subheader("🤖 Answer")
                st.write(data["answer"])

                # Display sources
                st.subheader("📚 Sources")
                for src in data["sources"]:
                    if "(" in src and src.endswith(")"):
                        title, url = src.rsplit("(", 1)
                        url = url.rstrip(")")
                        st.markdown(f"- [{title.strip()}]({url})")
                    else:
                        st.markdown(f"- {src}")

                # Display retrieved chunks (optional)
                with st.expander("🔍 Show retrieved article snippets"):
                    for src, score in zip(data["sources"], data["scores"]):
                        if "(" in src and src.endswith(")"):
                            title, url = src.rsplit("(", 1)
                            url = url.rstrip(")")
                            st.markdown(f"- [{title.strip()}]({url}) — **Score:** {1 - score:.2f}")

            else:
                st.error(f"Error from API: {response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"Request failed: {e}")