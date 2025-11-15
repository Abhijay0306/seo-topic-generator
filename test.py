import os
import feedparser
from collections import Counter
import re
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from bs4 import BeautifulSoup
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize

# --- Download NLTK data (only needs to be done once) ---
try:
    stopwords.words('english')
except LookupError:
    print("Downloading NLTK stopwords...")
    nltk.download('stopwords')
    nltk.download('punkt')
# ---------------------------------------------------------

# ---------- CONFIGURATION ----------
FEEDS = [
    "https://blog.hubspot.com/marketing/rss.xml",
    "https://searchengineland.com/feed",
    "https://moz.com/blog/feed",
    "https://backlinko.com/blog/feed",
    "https://www.socialmediaexaminer.com/feed/",
    "https://contentmarketinginstitute.com/feed/",
    "https://neilpatel.com/blog/feed/"
]

COMPANY_BLOG_URL = "https://www.abacusdigital.net/blogs"

NUM_ARTICLES_TO_SCAN = 50
NUM_SUGGESTIONS = 15

# Email settings
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASS = os.getenv("SENDER_PASS")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

EXTRA_STOPWORDS = set([
    "with","from","that","this","have","will","your","their","about","into","more",
    "been","also","over","some","what","when","where","which","using","than","then",
    "each","only","very","just","them","they","such","while","there","here",
    "http","https","www","com","blog","like","get","make","use","new","year",
    "need","know","see","top","best","guide","how","why"
])
STOPWORDS = set(stopwords.words('english')).union(EXTRA_STOPWORDS)
# -------------------------------------

def clean_text(text):
    return re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

def get_existing_blog_keywords(url):
    """Optional weighting: keywords from your blog (not mandatory)."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        titles = [h2.get_text() for h2 in soup.select('h2.font-bold')]
        descriptions = [p.get_text() for p in soup.select('p.text-base')]
        full_text = " ".join(titles) + " ".join(descriptions)
        words = clean_text(full_text)
        return set([w for w in words if w not in STOPWORDS])
    except requests.exceptions.RequestException:
        return set()

def fetch_and_score_articles(feeds, company_keywords):
    """Fetch RSS and score based on market trend + optional company relevance."""
    articles = []
    for url in feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            try:
                published_dt = datetime(*entry.published_parsed[:6])
            except Exception:
                published_dt = datetime.now()

            text = entry.title + " " + entry.get("summary", "")
            words = clean_text(text)
            keywords = [w for w in words if w not in STOPWORDS]

            # Score: trending weight (keyword frequency) + overlap with company blog
            overlap_score = len(set(keywords).intersection(company_keywords)) if company_keywords else 0

            articles.append({
                "title": entry.title,
                "link": entry.link,
                "published": published_dt,
                "summary": entry.get("summary", "No summary available."),
                "keywords": keywords,
                "score": overlap_score
            })
    return sorted(articles, key=lambda x: (x["score"], x["published"]), reverse=True)

def suggest_seo_topics(articles):
    ideas = []
    question_starters = ["How to", "Why", "What is", "The Ultimate Guide to", "A Beginner's Guide to"]
    list_starters = ["Ways to", "Steps to", "Effective Strategies for", "Examples of"]

    for article in articles[:NUM_ARTICLES_TO_SCAN]:
        clean_title = article['title']

        # Idea from title itself
        if any(starter.lower() in clean_title.lower() for starter in question_starters + list_starters):
            ideas.append((clean_title, article['link']))

        # Idea from summary sentences
        try:
            sentences = sent_tokenize(article['summary'])
            for sent in sentences[:2]:
                if 8 < len(sent.split()) < 20:
                    idea = f"Why is {sent[0].lower() + sent[1:]} Important for Your Business?"
                    ideas.append((idea, article['link']))
        except Exception:
            pass

    # Return unique + ranked list
    unique_ideas = []
    seen = set()
    for idea, link in ideas:
        if idea not in seen:
            seen.add(idea)
            unique_ideas.append((idea, link))

    return unique_ideas[:NUM_SUGGESTIONS]

def build_email_content(seo_topics, trending_keywords):
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 700px; margin: auto; border: 1px solid #ddd; padding: 20px;">
    <h2 style="color: #1a73e8;">🚀 SEO Blog Topic Suggestions (Market Trends)</h2>
    <p>Here are SEO-friendly blog topics based on current industry content:</p>
    """

    html += "<h3 style='border-bottom: 2px solid #1a73e8; padding-bottom: 5px;'>🎯 Suggested Blog Titles & Topics</h3><ul>"
    for i, (t, link) in enumerate(seo_topics, 1):
        html += f"""
        <li style="margin-bottom: 15px;">
            <strong style="font-size: 1.1em;">{i}. {t}</strong><br>
            <a href="{link}" target="_blank" style="color:#1a73e8;">Read Source</a>
        </li>
        """
    html += "</ul>"

    html += "<h3 style='border-bottom: 2px solid #1a73e8; padding-bottom: 5px;'>🔥 Trending Keywords</h3><p>"
    html += ", ".join([f"<span style='background-color: #e8f0fe; padding: 3px 8px; border-radius: 5px; margin: 3px; display: inline-block;'>{word}</span>" for word, count in trending_keywords])
    html += "</p>"

    html += "<p style='margin-top:20px; font-size:12px; color:#888;'>Generated automatically on {}</p>".format(
        datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    html += "</body></html>"
    return html

def send_email(subject, body_html):
    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.send_message(msg)
        print("✅ HTML Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def main():
    print("Scraping your existing blog for optional keywords...")
    company_keywords = get_existing_blog_keywords(COMPANY_BLOG_URL)
    if company_keywords:
        print(f"Found {len(company_keywords)} keywords from your blog (used as extra weight).")
    else:
        print("No keywords found from your blog. Relying fully on market trend.")

    print("Fetching and scoring articles from RSS feeds...")
    scored_articles = fetch_and_score_articles(FEEDS, company_keywords)
    
    print("Generating SEO topic suggestions...")
    seo_topics = suggest_seo_topics(scored_articles)
    
    all_keywords = [kw for article in scored_articles[:NUM_ARTICLES_TO_SCAN] for kw in article['keywords']]
    trending_keywords = Counter(all_keywords).most_common(20)

    if not seo_topics:
        print("No SEO topics generated. Try adjusting the feeds.")
        return

    email_body = build_email_content(seo_topics, trending_keywords)
    subject = f"SEO Blog Topics - {datetime.now().strftime('%Y-%m-%d')}"
    
    send_email(subject, email_body)

if __name__ == "__main__":
    main()
