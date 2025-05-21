import requests
from bs4 import BeautifulSoup
import re
import urllib.parse

def duckduckgo_search_and_summarize(query):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        search_url = f"https://duckduckgo.com/html/?q={requests.utils.quote(query)}"
        resp = requests.get(search_url, headers=headers, timeout=8)
        soup = BeautifulSoup(resp.text, 'html.parser')
        results = soup.select('.result__a')
        if not results:
            return None
        top_link = results[0]['href']
        m = re.search(r"uddg=([^&]+)", top_link)
        if m:
            top_link = urllib.parse.unquote(m.group(1))
        page_resp = requests.get(top_link, headers=headers, timeout=8)
        page_soup = BeautifulSoup(page_resp.text, 'html.parser')
        paragraphs = page_soup.find_all('p')
        for p in paragraphs:
            text = p.get_text().strip()
            if len(text) > 60:
                return f"{text}\n(Source: {top_link})"
        title = page_soup.title.string if page_soup.title else top_link
        return f"{title}\n(Source: {top_link})"
    except Exception as e:
        print(f"DuckDuckGo search failed: {e}")
        return None
