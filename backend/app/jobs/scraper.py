import httpx
from bs4 import BeautifulSoup

async def scrape_job_url(url: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            return {"title": "Scraped Job", "company": "", "text": ""}

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        title = soup.find("h1")
        title_text = title.get_text().strip() if title else "Job Posting"
        body_text = soup.get_text(separator="\n").strip()
        lines = [line.strip() for line in body_text.splitlines() if line.strip()]
        return {
            "title": title_text,
            "company": "Extracted from web",
            "text": "\n".join(lines[:200])
        }
