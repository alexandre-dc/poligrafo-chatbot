import requests
from bs4 import BeautifulSoup
import json
import os
import time
import datetime
from datetime import datetime
import boto3
from io import BytesIO

S3_BUCKET = os.getenv("S3_BUCKET", "your-s3-bucket-name")
S3_PREFIX = "data"
s3 = boto3.client("s3")

PT_MONTHS = {
    "janeiro": "01",
    "fevereiro": "02",
    "março": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12"
}

BASE_URL = 'https://poligrafo.sapo.pt/fact-checks/'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

SHARED_DIR = os.getenv(
    "SHARED_DATA_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared', 'data'))
)

# Paths used throughout the app
OUTPUT_FILE = os.path.join(SHARED_DIR, 'data/articles.json')
META_FILE = os.path.join(SHARED_DIR, 'data/last_run.json')


def parse_portuguese_datetime(text):
    """
    Converts '26 de Maio de 2025 às 11:00' into datetime object.
    """
    try:
        parts = text.lower().split(" de ")
        day = parts[0].strip()
        month = PT_MONTHS[parts[1].strip()]
        year_time = parts[2].split(" às ")
        year = year_time[0].strip()
        time_str = year_time[1].strip()
        datetime_str = f"{day}.{month}.{year} {time_str}"
        return datetime.strptime(datetime_str, "%d.%m.%Y %H:%M")
    except Exception as e:
        print(f"⚠️ Failed to parse date '{text}': {e}")
        return datetime.now()


def load_last_run():
    key = f"{S3_PREFIX}/last_run.json"
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        content = obj['Body'].read().decode('utf-8')
        return datetime.fromisoformat(json.loads(content)["last_seen"])
    except s3.exceptions.NoSuchKey:
        return None

def save_last_run(timestamp):
    key = f"{S3_PREFIX}/last_run.json"
    payload = json.dumps({"last_seen": timestamp.isoformat()})
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=payload.encode("utf-8"))

def fetch_article_links(page_url):
    response = requests.get(page_url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Failed to retrieve {page_url}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    articles = soup.find_all('article')
    links = []

    for article in articles:
        link_tag = article.find('a', href=True)
        if link_tag:
            full_url = link_tag['href']
            if not full_url.startswith('http'):
                full_url = BASE_URL.rstrip('/') + full_url
            links.append(full_url)

    return links

def scrape_article_content(article_url):
    response = requests.get(article_url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Failed to retrieve {article_url}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    title_tag = soup.find('h1')
    title = title_tag.get_text(strip=True) if title_tag else "No title"

    content_div = soup.find('div', class_='elementor-widget-theme-post-content')
    paragraphs = content_div.find_all('p') if content_div else []
    content = "\n\n".join(p.get_text(strip=True) for p in paragraphs)

    verdict_container = soup.find('div', class_='fact-check-result')
    verdict_tag = verdict_container.find('span') if verdict_container else None
    verdict = verdict_tag.get_text(strip=True) if verdict_tag else "Unknown"

    # Get publication time from custom class
    pub_tag = soup.find(class_="custom-post-date-time")
    published = parse_portuguese_datetime(pub_tag.get_text(strip=True)) if pub_tag else datetime.now()

    return {
        'url': article_url,
        'title': title,
        'verdict': verdict,
        'content': content,
        'published': published.isoformat()
    }

def append_article_to_json(article, key=f"{S3_PREFIX}/articles.json"):
    data = []
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        data = json.loads(obj['Body'].read().decode('utf-8'))
    except s3.exceptions.NoSuchKey:
        data = []
    except json.JSONDecodeError:
        print("Warning: JSON file was malformed. Starting fresh.")

    if not any(existing['url'] == article['url'] for existing in data):
        data.append(article)
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        )
        print(f"✅ Saved: {article['title']}")
        return True
    else:
        print(f"⚠️ Skipped duplicate: {article['url']}")
        return False

def data_collect():
    last_run = load_last_run()
    newest_article_time = None
    stop_scraping = False

    page_number = 1
    while page_number < 2:
        page_url = f"{BASE_URL}" if page_number == 1 else f"{BASE_URL}{page_number}/"
        print(f"\n🔎 Processing page: {page_url}")
        article_links = fetch_article_links(page_url)

        if not article_links:
            print("🚫 No more articles found.")
            break

        for link in article_links:
            article = scrape_article_content(link)
            if not article:
                continue

            article_time = datetime.fromisoformat(article['published'])

            if not newest_article_time or article_time > newest_article_time:
                newest_article_time = article_time

            if last_run and article_time <= last_run:
                print("🛑 Reached previously scraped content. Stopping.")
                stop_scraping = True
                break

            if append_article_to_json(article):
                time.sleep(2)

        if stop_scraping:
            break

        page_number += 1

    if newest_article_time:
        save_last_run(newest_article_time)
        print(f"\n🕒 Last run timestamp updated: {newest_article_time.isoformat()}")

if __name__ == "__main__":
    data_collect()