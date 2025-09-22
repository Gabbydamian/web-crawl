import requests
from bs4 import BeautifulSoup
import os
import telegram
import asyncio
import json
from datetime import datetime
from urllib.parse import urljoin

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

# Upstash Redis REST API credentials
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

# URLs to scrape
SCRAPER_URLS = {
    "jobberman": "https://www.jobberman.com/jobs?experience=graduate-trainee",
    "careers24": "https://www.careers24.com/jobs/lc-nigeria/"
}

# Redis key for storing sent jobs
SENT_JOBS_KEY = "job_scraper:sent_jobs"

def upstash_redis_request(command, *args):
    """Makes a REST API request to Upstash Redis."""
    if not UPSTASH_REDIS_REST_URL or not UPSTASH_REDIS_REST_TOKEN:
        return None
    
    url = f"{UPSTASH_REDIS_REST_URL}/{command}"
    if args:
        url += "/" + "/".join(str(arg) for arg in args)
    
    headers = {
        "Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Upstash Redis API error: {e}")
        return None

def test_redis_connection():
    """Tests the Upstash Redis connection."""
    if not UPSTASH_REDIS_REST_URL or not UPSTASH_REDIS_REST_TOKEN:
        print("Warning: No Upstash Redis credentials found. Using fallback local storage.")
        return False
    
    try:
        # Test with a simple PING command
        result = upstash_redis_request("ping")
        if result and result.get("result") == "PONG":
            print("Successfully connected to Upstash Redis!")
            return True
        else:
            print(f"Upstash Redis connection test failed: {result}")
            return False
    except Exception as e:
        print(f"Error testing Upstash Redis connection: {e}")
        return False

def load_sent_jobs():
    """Loads a dictionary of job links that have already been sent from Upstash Redis."""
    if not test_redis_connection():
        # Fallback to JSON file if Redis is unavailable
        return load_sent_jobs_fallback()
    
    try:
        # Get the JSON string from Redis using REST API
        result = upstash_redis_request("get", SENT_JOBS_KEY)
        
        if result and result.get("result"):
            return json.loads(result["result"])
        else:
            print("No sent jobs found in Redis, starting fresh.")
            return {}
    except Exception as e:
        print(f"Error loading sent jobs from Upstash Redis: {e}")
        return load_sent_jobs_fallback()

def load_sent_jobs_fallback():
    """Fallback method to load sent jobs from JSON file."""
    sent_jobs_file = "sent_jobs.json"
    if os.path.exists(sent_jobs_file):
        try:
            with open(sent_jobs_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print("Warning: Could not load sent jobs file, starting fresh.")
    return {}

def save_sent_jobs(sent_jobs_data):
    """Saves the sent jobs dictionary to Upstash Redis."""
    if not test_redis_connection():
        # Fallback to JSON file if Redis is unavailable
        return save_sent_jobs_fallback(sent_jobs_data)
    
    try:
        # Convert dict to JSON string and save to Redis using REST API
        sent_jobs_json = json.dumps(sent_jobs_data)
        result = upstash_redis_request("set", SENT_JOBS_KEY, sent_jobs_json)
        
        if result and result.get("result") == "OK":
            print(f"Saved {len(sent_jobs_data)} sent jobs to Upstash Redis.")
            return True
        else:
            print(f"Failed to save to Upstash Redis: {result}")
            return save_sent_jobs_fallback(sent_jobs_data)
    except Exception as e:
        print(f"Error saving sent jobs to Upstash Redis: {e}")
        return save_sent_jobs_fallback(sent_jobs_data)

def save_sent_jobs_fallback(sent_jobs_data):
    """Fallback method to save sent jobs to JSON file."""
    try:
        with open("sent_jobs.json", 'w') as f:
            json.dump(sent_jobs_data, f, indent=2)
        print(f"Saved {len(sent_jobs_data)} sent jobs to fallback file.")
        return True
    except Exception as e:
        print(f"Error saving sent jobs to fallback file: {e}")
        return False

def add_sent_job(sent_jobs_data, job_link, source, title):
    """Adds a new job to the sent jobs dictionary."""
    sent_jobs_data[job_link] = {
        "source": source,
        "title": title,
        "sent_date": datetime.now().isoformat()
    }

async def send_telegram_message(message):
    """Sends a message to the specified Telegram channel."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("Error: Missing Telegram bot token or channel ID.")
        return False

    try:
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        
        # Split message if it's too long (Telegram limit is 4096 characters)
        if len(message) > 4000:  # Leave some buffer
            messages = split_message(message)
            for msg in messages:
                await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=msg, parse_mode='HTML')
                await asyncio.sleep(1)  # Small delay between messages
        else:
            await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message, parse_mode='HTML')
        
        print(f"Message(s) successfully sent to Telegram.")
        return True
    except Exception as e:
        print(f"Failed to send message to Telegram: {e}")
        return False

def split_message(message, max_length=4000):
    """Splits a long message into smaller chunks."""
    messages = []
    current_message = ""
    
    lines = message.split('\n')
    
    for line in lines:
        if len(current_message + line + '\n') > max_length:
            if current_message:
                messages.append(current_message.strip())
                current_message = ""
        current_message += line + '\n'
    
    if current_message.strip():
        messages.append(current_message.strip())
    
    return messages

def scrape_jobberman():
    """Scrapes job listings from Jobberman."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(SCRAPER_URLS["jobberman"], headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        job_listings = soup.find_all('div', attrs={'data-cy': 'listing-cards-components'})
        
        scraped_data = []

        for job_container in job_listings:
            try:
                title_link_tag = job_container.find('a', attrs={'data-cy': 'listing-title-link'})
                if not title_link_tag:
                    continue
                
                title = title_link_tag.find('p').get_text(strip=True) if title_link_tag.find('p') else "No Title"
                link = urljoin(SCRAPER_URLS["jobberman"], title_link_tag['href'])

                company_tag = job_container.find('p', class_='text-sm text-link-500 text-loading-animate inline-block mt-3')
                company = company_tag.get_text(strip=True) if company_tag else "No Company"

                details_container = job_container.find('div', class_='flex flex-wrap mt-3 text-sm text-gray-500 md:py-0')
                details = [span.get_text(strip=True) for span in details_container.find_all('span', class_='bg-brand-secondary-100')] if details_container else []

                formatted_details = ", ".join(details)
                
                scraped_data.append({
                    'title': title,
                    'company': company,
                    'link': link,
                    'details': formatted_details,
                    'source': 'Jobberman'
                })
            except Exception as e:
                print(f"Failed to parse a Jobberman job listing: {e}")
                continue

        print(f"Scraped {len(scraped_data)} jobs from Jobberman")
        return scraped_data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Jobberman page: {e}")
        return []

def scrape_careers24():
    """Scrapes job listings from Careers24."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(SCRAPER_URLS["careers24"], headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        job_listings = soup.find_all('div', class_='job-card')
        
        scraped_data = []

        for job_container in job_listings:
            try:
                # Extract job title and link
                title_link_tag = job_container.find('a', attrs={'data-control': 'vacancy-title'})
                if not title_link_tag:
                    continue
                
                title = title_link_tag.find('h2').get_text(strip=True) if title_link_tag.find('h2') else "No Title"
                link = urljoin(SCRAPER_URLS["careers24"], title_link_tag['href'])

                # Extract job details from the left column
                job_card_left = job_container.find('div', class_='job-card-left')
                details = []
                
                if job_card_left:
                    list_items = job_card_left.find_all('li')
                    for li in list_items:
                        # Clean up the text and handle badges
                        text = li.get_text(separator=' ', strip=True)
                        # Remove extra whitespace
                        text = ' '.join(text.split())
                        if text:
                            details.append(text)

                formatted_details = " | ".join(details)
                
                scraped_data.append({
                    'title': title,
                    'company': 'Not specified',  # Careers24 doesn't show company in the card structure provided
                    'link': link,
                    'details': formatted_details,
                    'source': 'Careers24'
                })
            except Exception as e:
                print(f"Failed to parse a Careers24 job listing: {e}")
                continue

        print(f"Scraped {len(scraped_data)} jobs from Careers24")
        return scraped_data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Careers24 page: {e}")
        return []

def scrape_all_jobs():
    """Scrapes jobs from all configured sources."""
    all_jobs = []
    
    # Scrape Jobberman
    jobberman_jobs = scrape_jobberman()
    all_jobs.extend(jobberman_jobs)
    
    # Scrape Careers24
    careers24_jobs = scrape_careers24()
    all_jobs.extend(careers24_jobs)
    
    return all_jobs

def format_jobs_for_telegram(jobs):
    """Formats the list of jobs into messages for Telegram."""
    if not jobs:
        return ["No new job listings found."]

    # Group jobs by source
    jobs_by_source = {}
    for job in jobs:
        source = job.get('source', 'Unknown')
        if source not in jobs_by_source:
            jobs_by_source[source] = []
        jobs_by_source[source].append(job)

    messages = []
    
    for source, source_jobs in jobs_by_source.items():
        message = f"<b>🚀 New Job Listings from {source}:</b>\n\n"
        
        for job in source_jobs:
            job_message = f"<b>Title:</b> {job['title']}\n"
            if job['company'] and job['company'] != 'Not specified':
                job_message += f"<b>Company:</b> {job['company']}\n"
            if job['details']:
                job_message += f"<b>Details:</b> <i>{job['details']}</i>\n"
            job_message += f"<b>Link:</b> <a href='{job['link']}'>Apply Here</a>\n\n"
            
            # Check if adding this job would exceed message limit
            if len(message + job_message) > 3800:  # Leave buffer for header
                messages.append(message.strip())
                message = f"<b>🚀 More from {source}:</b>\n\n" + job_message
            else:
                message += job_message
        
        if message.strip():
            messages.append(message.strip())
    
    return messages

async def main():
    """Main function to run the scraper and send messages."""
    print("Starting job scraping from multiple sources...")
    
    # Load previously sent jobs
    sent_jobs_data = load_sent_jobs()
    print(f"Loaded {len(sent_jobs_data)} previously sent jobs")
    
    # Scrape new jobs from all sources
    all_jobs = scrape_all_jobs()
    print(f"Found {len(all_jobs)} total jobs")

    # Filter out jobs that have already been sent
    new_jobs_to_send = []
    for job in all_jobs:
        if job['link'] not in sent_jobs_data:
            new_jobs_to_send.append(job)

    print(f"Found {len(new_jobs_to_send)} new jobs to send")

    if new_jobs_to_send:
        # Format and send the messages for the new jobs
        messages = format_jobs_for_telegram(new_jobs_to_send)
        
        success = True
        for message in messages:
            if not await send_telegram_message(message):
                success = False
                break
            await asyncio.sleep(2)  # Delay between messages
        
        # Only save sent jobs if messages were sent successfully
        if success:
            for job in new_jobs_to_send:
                add_sent_job(sent_jobs_data, job['link'], job['source'], job['title'])
            
            if save_sent_jobs(sent_jobs_data):
                print(f"Successfully sent and saved {len(new_jobs_to_send)} new jobs")
            else:
                print(f"Sent {len(new_jobs_to_send)} jobs but failed to save to storage")
        else:
            print("Failed to send messages, not updating sent jobs list")
    else:
        print("No new jobs to send.")

if __name__ == '__main__':
    # Run the main asynchronous function
    asyncio.run(main())