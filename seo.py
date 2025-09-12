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
# Feeds focused on digital marketing, SEO, and business growth
FEEDS = [
    "https://blog.hubspot.com/marketing/rss.xml",
    "https://searchengineland.com/feed",
    "https://moz.com/blog/feed",
    "https://backlinko.com/blog/feed",
    "https://www.socialmediaexaminer.com/feed/",
    "https://contentmarketinginstitute.com/feed/",
    "https://neilpatel.com/blog/feed/"
]
# Your company's blog URL
COMPANY_BLOG_URL = "https://www.abacusdigital.net/blogs"

NUM_ARTICLES_TO_SCAN = 50 # Scan more articles for better trend analysis
NUM_SUGGESTIONS = 15 # Generate more topic suggestions

# Email settings (replace with your details)
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASS = os.getenv("SENDER_PASS")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Expanded stopwords list for better keyword extraction
EXTRA_STOPWORDS = set([
    "with","from","that","this","have","will","your","their","about","into","more",
    "been","also","over","some","what","when","where","which","using","than","then",
    "each","into","only","very","just","them","they","such","while","there","here",
    "http","https","www","com","blog", "like", "get", "make", "use", "new", "year",
    "need", "know", "see", "top", "best", "guide", "how", "why"
])
STOPWORDS = set(stopwords.words('english')).union(EXTRA_STOPWORDS)
# -------------------------------------

def clean_text(text):
    """Cleans text by removing non-alphabetic characters and converting to lowercase."""
    return re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

def get_existing_blog_keywords(url):
    """Scrapes your blog to find existing keywords from titles and descriptions."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all blog post titles and descriptions (selectors might need adjustment for your site)
        # Based on inspection of abacusdigital.net/blogs
        titles = [h2.get_text() for h2 in soup.select('h2.font-bold')]
        descriptions = [p.get_text() for p in soup.select('p.text-base')]

        full_text = " ".join(titles) + " ".join(descriptions)
        words = clean_text(full_text)
        return set([w for w in words if w not in STOPWORDS])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching your blog URL: {e}")
        return set() # Return an empty set on failure

def fetch_and_score_articles(feeds, company_keywords):
    """Fetches articles and scores them based on relevance to your existing keywords."""
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

            # Score article based on keyword overlap
            score = len(set(keywords).intersection(company_keywords))

            articles.append({
                "title": entry.title,
                "link": entry.link,
                "published": published_dt,
                "summary": entry.get("summary", "No summary available."),
                "keywords": keywords,
                "score": score
            })
    # Sort by relevance score first, then by date
    return sorted(articles, key=lambda x: (x["score"], x["published"]), reverse=True)

def suggest_seo_topics(articles):
    """Generates SEO-friendly blog topic ideas from the most relevant articles."""
    ideas = []
    question_starters = ["How to", "Why", "What is", "The Ultimate Guide to", "A Beginner's Guide to"]
    list_starters = ["Ways to", "Steps to", "Effective Strategies for", "Examples of"]

    for article in articles[:NUM_ARTICLES_TO_SCAN]:
        # Idea 1: Rephrase titles as questions or lists
        clean_title = article['title']
        if any(starter.lower() in clean_title.lower() for starter in question_starters + list_starters):
             ideas.append(clean_title)

        # Idea 2: Turn high-value sentences into questions
        try:
            sentences = sent_tokenize(article['summary'])
            for sent in sentences[:2]: # Check first two sentences of summary
                if len(sent.split()) > 8 and len(sent.split()) < 20: # Good sentence length
                    ideas.append(f"Why is {sent[0].lower() + sent[1:]} Important for Your Business?")
        except Exception as e:
            print(f"Could not tokenize summary for '{article['title']}': {e}")


    # Return a unique, ranked list of the most frequent ideas
    return [p for p, _ in Counter(ideas).most_common(NUM_SUGGESTIONS)]


def build_email_content(seo_topics, trending_keywords):
    """Builds the HTML for the email report."""
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 700px; margin: auto; border: 1px solid #ddd; padding: 20px;">
    <h2 style="color: #1a73e8;">🚀 SEO Blog Topic Suggestions for Abacus Digital</h2>
    <p>Here are your SEO-friendly blog topics for the week, based on trending content related to your current strategy:</p>
    """

    html += "<h3 style='border-bottom: 2px solid #1a73e8; padding-bottom: 5px;'>🎯 Suggested Blog Titles & Topics</h3><ul>"
    for i, t in enumerate(seo_topics, 1):
        html += f"""
        <li style="margin-bottom: 15px;">
            <strong style="font-size: 1.1em;">{i}. {t}</strong>
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
    """Sends the email report."""
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
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Failed to send email. Check SENDER_EMAIL and SENDER_PASS. Error: {e}")
    except Exception as e:
        print(f"❌ An error occurred while sending the email: {e}")

def main():
    print("Scraping your existing blog for keywords...")
    company_keywords = get_existing_blog_keywords(COMPANY_BLOG_URL)
    if not company_keywords:
        print("Warning: Could not fetch keywords from your blog. Suggestions may be less relevant.")
    else:
        print(f"Found {len(company_keywords)} unique keywords from your blog.")

    print("Fetching and scoring articles from RSS feeds...")
    scored_articles = fetch_and_score_articles(FEEDS, company_keywords)
    
    print("Generating SEO topic suggestions...")
    seo_topics = suggest_seo_topics(scored_articles)
    
    # Extract trending keywords from the top scored articles
    all_keywords = [kw for article in scored_articles[:NUM_ARTICLES_TO_SCAN] for kw in article['keywords']]
    trending_keywords = Counter(all_keywords).most_common(20)

    if not seo_topics:
        print("Could not generate any SEO topics. Try adjusting the feeds or checking the blog URL.")
        return

    email_body = build_email_content(seo_topics, trending_keywords)
    subject = f"SEO Blog Topics for Abacus Digital - {datetime.now().strftime('%Y-%m-%d')}"
    
    send_email(subject, email_body)

if __name__ == "__main__":
    main()
