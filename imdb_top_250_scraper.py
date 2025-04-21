import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
import re

# Configure request headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Referer': 'https://www.imdb.com/',
    'Connection': 'keep-alive'
}

def get_imdb_top_movies():
    print("Starting IMDb scraping process...")
    url = 'https://www.imdb.com/chart/top/'
    
    try:
        # Get the main page
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()  # Check for HTTP errors
        
        # Parse the response
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for the data in JSON format (IMDb now uses client-side rendering)
        scripts = soup.find_all('script')
        data_json = None
        
        # Find the script containing the data
        for script in scripts:
            if script.string and 'IMDbReactInitialState.push' in script.string:
                json_str = re.search(r'IMDbReactInitialState\.push\((.*?)\);', script.string, re.DOTALL)
                if json_str:
                    try:
                        data_json = json.loads(json_str.group(1))
                        break
                    except json.JSONDecodeError:
                        continue
        
        if not data_json:
            # Fallback to direct HTML parsing if JSON data isn't found
            return scrape_html_fallback(soup)
        
        # Extract the movie data from the JSON
        movie_data = []
        
        # Navigate the JSON structure to find the movie list
        titles_data = None
        if 'chartTitles' in data_json:
            titles_data = data_json['chartTitles'].get('titles', [])
        elif 'pageProps' in data_json:
            titles_data = data_json['pageProps'].get('titles', [])
        
        if not titles_data:
            print("Could not locate movie data in JSON. Falling back to HTML parsing...")
            return scrape_html_fallback(soup)
        
        print(f"Found {len(titles_data)} movies. Processing...")
        
        for i, movie in enumerate(titles_data, 1):
            try:
                title = movie.get('titleText', {}).get('text', 'Unknown Title')
                year_text = movie.get('releaseYear', {}).get('year', 'Unknown Year')
                year = int(year_text) if str(year_text).isdigit() else year_text
                
                rating_value = movie.get('ratingsSummary', {}).get('aggregateRating', 0)
                try:
                    rating = float(rating_value)
                except (ValueError, TypeError):
                    rating = 0.0
                
                # Get genres
                genres = []
                if 'genres' in movie:
                    genres = [genre.get('text') for genre in movie.get('genres', [])]
                
                movie_data.append({
                    'Title': title,
                    'Year': year,
                    'Rating': rating,
                    'Genres': ', '.join(genres) if genres else 'Unknown'
                })
                
                if i % 10 == 0:
                    print(f"Processed {i}/{len(titles_data)} movies...")
                
            except Exception as e:
                print(f"Error processing movie #{i}: {str(e)}")
        
        return movie_data
    
    except Exception as e:
        print(f"Error during main scraping process: {str(e)}")
        return []

def scrape_html_fallback(soup):
    """Fallback method to scrape directly from HTML if JSON extraction fails"""
    print("Using HTML fallback method for scraping...")
    movie_data = []
    
    # Find all movie items
    movie_items = soup.select('li.ipc-metadata-list-summary-item')
    
    if not movie_items:
        print("No movie items found with current selector. Site structure may have changed.")
        return []
    
    print(f"Found {len(movie_items)} movies in HTML. Processing...")
    
    for i, item in enumerate(movie_items, 1):
        try:
            # Extract title
            title_elem = item.select_one('h3.ipc-title__text')
            title = re.sub(r'^\d+\.\s+', '', title_elem.text.strip()) if title_elem else "Unknown Title"
            
            # Extract year
            year_elem = item.select_one('span.cli-title-metadata-item')
            year_text = year_elem.text.strip() if year_elem else "Unknown Year"
            year = int(year_text) if year_text.isdigit() else year_text
            
            # Extract rating
            rating_elem = item.select_one('span.ipc-rating-star--rating')
            rating = 0.0
            if rating_elem:
                rating_match = re.search(r'([\d.]+)', rating_elem.text.strip())
                if rating_match:
                    rating = float(rating_match.group(1))
            
            # Get genres - detailed page needed but we'll skip for fallback method
            movie_data.append({
                'Title': title,
                'Year': year,
                'Rating': rating,
                'Genres': 'Not available in fallback mode'
            })
            
            if i % 10 == 0:
                print(f"Processed {i}/{len(movie_items)} movies in fallback mode...")
                
        except Exception as e:
            print(f"Error processing movie #{i} in fallback mode: {str(e)}")
    
    return movie_data

def save_to_excel(data, filename='imdb_top_250.xlsx'):
    """Save the movie data to an Excel file with formatting"""
    if not data:
        print("No data to save. Exiting.")
        return False
    
    try:
        df = pd.DataFrame(data)
        
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            # Write data to Excel
            df.to_excel(writer, sheet_name='Top 250', index=False)
            
            # Get workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets['Top 250']
            
            # Define formats
            header_format = workbook.add_format({
                'bold': True,
                'font_color': 'white',
                'bg_color': '#333399',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })
            
            cell_format = workbook.add_format({
                'align': 'left',
                'valign': 'top',
                'text_wrap': True,
                'border': 1
            })
            
            # Apply formats
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Set column widths
            worksheet.set_column('A:A', 40)  # Title
            worksheet.set_column('B:B', 10)  # Year
            worksheet.set_column('C:C', 10)  # Rating
            worksheet.set_column('D:D', 30)  # Genres
            
            # Freeze the top row
            worksheet.freeze_panes(1, 0)
        
        print(f"Successfully saved {len(data)} movies to {filename}")
        return True
    
    except Exception as e:
        print(f"Error saving to Excel: {str(e)}")
        return False

# Main execution
if __name__ == "__main__":
    print("IMDb Top 250 Movie Scraper")
    print("--------------------------")
    
    movie_data = get_imdb_top_movies()
    
    if movie_data:
        print(f"Successfully retrieved {len(movie_data)} movies")
        save_to_excel(movie_data)
    else:
        print("Failed to retrieve movie data. Please check your internet connection or if IMDb has changed their website structure.")