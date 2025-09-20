import requests
from bs4 import BeautifulSoup
import os
import telegram
import asyncio

# --- IMPORTANT: CONFIGURATION ---
# These values should be set as environment variables on Railway for security.
# Example: TELEGRAM_BOT_TOKEN = "your-bot-token"
# Example: TELEGRAM_CHANNEL_ID = "@your_channel_username"
# If running locally, you can create a .env file or set them manually.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

# The URL to scrape. This is a placeholder and may need to be modified.
SCRAPER_URL = "https://www.jobberman.com/jobs?experience=graduate-trainee"
SENT_JOBS_FILE = "sent_jobs.txt"

def load_sent_jobs():
    """Loads a set of job links that have already been sent."""
    if os.path.exists(SENT_JOBS_FILE):
        with open(SENT_JOBS_FILE, 'r') as f:
            return set(line.strip() for line in f)
    return set()

def save_sent_jobs(job_links):
    """Saves a list of job links to a file."""
    with open(SENT_JOBS_FILE, 'a') as f:
        for link in job_links:
            f.write(f"{link}\n")

async def send_telegram_message(message):
    """Sends a message to the specified Telegram channel."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("Error: Missing Telegram bot token or channel ID.")
        return

    try:
        # Create the bot instance
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        # Send the message
        await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=message, parse_mode='HTML')
        print(f"Message successfully sent to Telegram.")
    except Exception as e:
        print(f"Failed to send message to Telegram: {e}")

def scrape_jobs():
    """
    Scrapes job listings from the specified URL based on the provided HTML structure.
    """
    try:
        # Use a user-agent to mimic a real browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        response = requests.get(SCRAPER_URL, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all job listing containers using the data-cy attribute
        job_listings = soup.find_all('div', attrs={'data-cy': 'listing-cards-components'})
        
        scraped_data = []

        for job_container in job_listings:
            try:
                # Extract job title and link
                title_link_tag = job_container.find('a', attrs={'data-cy': 'listing-title-link'})
                if not title_link_tag:
                    continue
                
                title = title_link_tag.find('p').get_text(strip=True) if title_link_tag.find('p') else "No Title"
                link = requests.compat.urljoin(SCRAPER_URL, title_link_tag['href'])

                # Extract the company name
                company_tag = job_container.find('p', class_='text-sm text-link-500 text-loading-animate inline-block mt-3')
                company = company_tag.get_text(strip=True) if company_tag else "No Company"

                # Extract job details like location, type, salary
                details_container = job_container.find('div', class_='flex flex-wrap mt-3 text-sm text-gray-500 md:py-0')
                details = [span.get_text(strip=True) for span in details_container.find_all('span', class_='bg-brand-secondary-100')] if details_container else []

                # Join the details into a single string for the message
                formatted_details = ", ".join(details)
                
                scraped_data.append({
                    'title': title,
                    'company': company,
                    'link': link,
                    'details': formatted_details
                })
            except Exception as e:
                print(f"Failed to parse a job listing: {e}")
                continue

        return scraped_data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching the page: {e}")
        return []

def format_jobs_for_telegram(jobs):
    """Formats the list of jobs into a single message for Telegram."""
    if not jobs:
        return "No new job listings found."

    message = "<b>🚀 New Job Listings from Jobberman:</b>\n\n"
    for job in jobs:
        message += f"<b>Title:</b> {job['title']}\n"
        message += f"<b>Company:</b> {job['company']}\n"
        message += f"<b>Details:</b> <i>{job['details']}</i>\n"
        message += f"<b>Link:</b> <a href='{job['link']}'>Apply Here</a>\n\n"
    
    return message

async def main():
    """Main function to run the scraper and send the message."""
    print("Starting job scraping...")
    
    # Load previously sent jobs
    sent_jobs = load_sent_jobs()
    
    # Scrape new jobs
    jobs = scrape_jobs()

    new_jobs_to_send = []
    new_job_links_to_save = []

    for job in jobs:
        if job['link'] not in sent_jobs:
            new_jobs_to_send.append(job)
            new_job_links_to_save.append(job['link'])

    if new_jobs_to_send:
        # Format and send the message for the new jobs
        message = format_jobs_for_telegram(new_jobs_to_send)
        await send_telegram_message(message)
        
        # Save the links of the newly sent jobs
        save_sent_jobs(new_job_links_to_save)
    else:
        print("No new jobs to send.")

if __name__ == '__main__':
    # Run the main asynchronous function
    asyncio.run(main())
