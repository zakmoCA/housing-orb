import requests
from bs4 import BeautifulSoup
import csv
import re

# URL constants
BASE_URL = "https://www.yourinvestmentpropertymag.com.au/top-suburbs/qld/"
ROOT_URL = "https://www.yourinvestmentpropertymag.com.au"

# HTTP headers to mimic a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
}

# Postcode range for Brisbane
BRISBANE_POSTCODE_MIN = 4000
BRISBANE_POSTCODE_MAX = 4207

def fetch_suburb_links(session):
    """Fetch all suburb page links from the base Queensland suburb listing page."""
    suburb_links = []
    response = session.get(BASE_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    suburb_list_section = soup.select_one('div.suburb-list')
    if not suburb_list_section:
        print("Error: Could not find suburb list section.")
        return []
    suburb_anchors = suburb_list_section.select('a')
    for a_tag in suburb_anchors:
        href = a_tag.get('href')
        if href and href.startswith('/top-suburbs/qld/'):
            suburb_links.append(ROOT_URL + href)
    return suburb_links

def is_brisbane_suburb(suburb_url):
    """Check if a given suburb URL belongs to Brisbane based on postcode range."""
    match = re.search(r'/qld/(\d+)-([\w-]+)', suburb_url)
    if not match:
        return False
    postcode = int(match.group(1))
    return BRISBANE_POSTCODE_MIN <= postcode <= BRISBANE_POSTCODE_MAX

def extract_owner_occupier_and_income_from_paragraphs(soup):
    """Extract owner-occupier rates (2011, 2016) and median household income ($) from body text."""
    owner_rate_2011 = None
    owner_rate_2016 = None
    median_household_income = None
    paragraphs = soup.select('div#pills-tabContent p')
    for p in paragraphs:
        text = p.get_text(strip=True).lower()
        if 'owner-occupied' in text:
            matches = re.findall(r'(\d{1,2}\.\d{1,2})%', text)
            if len(matches) >= 2:
                owner_rate_2011 = matches[0] + "%"
                owner_rate_2016 = matches[1] + "%"
            elif len(matches) == 1:
                owner_rate_2011 = matches[0] + "%"

        if 'median household income' in text and not median_household_income:
            match = re.search(r'\$([\d,]+)', text)
            if match:
                median_household_income = match.group(1).replace(',', '')

    return owner_rate_2011, owner_rate_2016, median_household_income

def clean_percentage(value_str):
    if not value_str:
        return None
    try:
        cleaned = value_str.replace('%', '').replace('+', '').strip()
        return float(cleaned)
    except:
        return None

def scrape_suburb_data(session, suburb_url):
    try:
        response = session.get(suburb_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        match = re.search(r'/qld/(\d+)-([\w-]+)', suburb_url)
        postcode, suburb_name = match.groups() if match else ('', '')

        suburb_data = {
            'Suburb Name': suburb_name.replace('-', ' ').title(),
            'Postcode': postcode,
            'Owner Occupier Rate 2011': None,
            'Owner Occupier Rate 2016': None,
            'Median House Price': None,
            'Annual Growth (%)': None,
            'Median Rent ($/wk)': None,
            'Avg Days on Market (12m)': None,
            'Total Population 2011': None,
            'Total Population 2016': None,
            'Population Growth (5y %) At 2011': None,
            'Population Growth (5y %) At 2016': None,
            'Median Household Income 2011': None,
            'Median Household Income 2016': None,
            'Household Income Growth (5y %) At 2011': None,
            'Household Income Growth (5y %) At 2016': None,
            'Median Age 2011': None,
            'Median Age 2016': None
        }

        owner_rate_2011, owner_rate_2016, median_income = extract_owner_occupier_and_income_from_paragraphs(soup)
        suburb_data['Owner Occupier Rate 2011'] = owner_rate_2011
        suburb_data['Owner Occupier Rate 2016'] = owner_rate_2016

        market_section = soup.select_one('div.key-market-data')
        if market_section:
            for row in market_section.select('table tbody tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    house_value_1 = cells[1].get_text(strip=True)
                    if 'median price' in label:
                        suburb_data['Median House Price'] = house_value_1
                    if 'average annual growth' in label:
                        suburb_data['Annual Growth (%)'] = house_value_1
                    if 'weekly median rent' in label:
                        suburb_data['Median Rent ($/wk)'] = house_value_1
                    if 'avg. days on market' in label or 'average days on market' in label:
                        suburb_data['Avg Days on Market (12m)'] = house_value_1

        demo_section = soup.select_one('div.key-demographics')
        if demo_section:
            for row in demo_section.select('table tbody tr'):
                cells = row.find_all('td')
                if len(cells) >= 3:
                    label = cells[0].get_text(strip=True).lower()
                    value_1 = cells[1].select_one('span').get_text(strip=True) if cells[1].select_one('span') else ''
                    value_2 = cells[2].select_one('span').get_text(strip=True) if cells[2].select_one('span') else ''

                    if 'total population' in label:
                        suburb_data['Total Population 2011'] = value_1
                        suburb_data['Total Population 2016'] = value_2
                    if 'population change' in label:
                        suburb_data['Population Growth (5y %) At 2011'] = clean_percentage(value_1)
                        suburb_data['Population Growth (5y %) At 2016'] = clean_percentage(value_2)
                    if 'household income change' in label:
                        suburb_data['Household Income Growth (5y %) At 2011'] = clean_percentage(value_1)
                        suburb_data['Household Income Growth (5y %) At 2016'] = clean_percentage(value_2)
                    if 'median household income' in label:
                        suburb_data['Median Household Income 2011'] = value_1.replace('$', '').replace(',', '')
                        suburb_data['Median Household Income 2016'] = value_2.replace('$', '').replace(',', '')
                    if 'median age' in label:
                        suburb_data['Median Age 2011'] = value_1
                        suburb_data['Median Age 2016'] = value_2

        return suburb_data
    except Exception as e:
        print(f"Error scraping {suburb_url}: {e}")
        return None

def parse_owner_rate(rate_str):
    if not rate_str:
        return 0.0
    try:
        return float(rate_str.replace('%', '').strip())
    except:
        return 0.0

def main():
    print("Beginning scrape...")
    session = requests.Session()
    session.headers.update(HEADERS)
    suburb_links = fetch_suburb_links(session)
    brisbane_suburb_links = [link for link in suburb_links if is_brisbane_suburb(link)]
    all_suburb_data = []

    for link in brisbane_suburb_links:
        data = scrape_suburb_data(session, link)
        if data:
            all_suburb_data.append(data)

    all_suburb_data.sort(key=lambda x: parse_owner_rate(x['Owner Occupier Rate 2016']), reverse=True)

    if all_suburb_data:
        csv_filename = "testing_v2_fix2_BNE.csv"
        keys = all_suburb_data[0].keys()
        with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_suburb_data)
        print("✅ Completed scrape and wrote to CSV!")

if __name__ == "__main__":
    main()
