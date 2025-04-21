import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
import re
import sys

# Configure request headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Referer': 'https://www.imdb.com/',
    'Connection': 'keep-alive'
}

class ImdbScraper:
    def __init__(self):
        self.base_url = 'https://www.imdb.com'
        self.top_movies_url = f"{self.base_url}/chart/top/"
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def progress_bar(self, current, total, bar_length=50):
        """Display a custom progress bar in the console"""
        progress = float(current) / float(total)
        arrow = '■' * int(round(progress * bar_length))
        spaces = ' ' * (bar_length - len(arrow))
        
        sys.stdout.write(f"\r[{arrow}{spaces}] {int(progress * 100)}% ({current}/{total})")
        sys.stdout.flush()
    
    def get_top_movies(self):
        """Get the list of top movies from IMDb"""
        print("🎬 Fetching IMDb Top 250 movies list...")
        
        try:
            response = self.session.get(self.top_movies_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all movie items
            movie_items = soup.select('li.ipc-metadata-list-summary-item')
            
            if not movie_items:
                print("❌ No movie items found. IMDb may have changed their structure.")
                return []
            
            print(f"✅ Found {len(movie_items)} movies.")
            
            movies = []
            total = len(movie_items)
            
            for i, item in enumerate(movie_items, 1):
                try:
                    # Extract movie details
                    title_elem = item.select_one('h3.ipc-title__text')
                    full_title = title_elem.text.strip() if title_elem else "Unknown Title"
                    title = re.sub(r'^\d+\.\s+', '', full_title)  # Remove the ranking number
                    
                    # Find all metadata items (year, runtime, rating)
                    metadata_items = item.select('span.cli-title-metadata-item')
                    year = metadata_items[0].text.strip() if metadata_items else "Unknown"
                    
                    # Extract rating
                    rating_elem = item.select_one('span.ipc-rating-star--imdb')
                    rating = 0.0
                    if rating_elem:
                        rating_text = rating_elem.text.strip()
                        rating_match = re.search(r'([\d.]+)', rating_text)
                        if rating_match:
                            rating = float(rating_match.group(1))
                    
                    # Get the movie URL for fetching additional details
                    link_elem = item.select_one('a.ipc-title-link-wrapper')
                    movie_url = f"{self.base_url}{link_elem['href']}" if link_elem and 'href' in link_elem.attrs else None
                    
                    # Build the movie object
                    movie = {
                        'Rank': i,
                        'Title': title,
                        'Year': int(year) if year.isdigit() else year,
                        'Rating': rating,
                        'Genres': [],
                        'Director': "Unknown",
                        'Stars': [],
                        'URL': movie_url
                    }
                    
                    movies.append(movie)
                    self.progress_bar(i, total)
                    
                except Exception as e:
                    print(f"\n❌ Error processing movie #{i}: {str(e)}")
            
            print("\n✅ Basic movie list retrieved. Now fetching detailed information...")
            return movies
            
        except Exception as e:
            print(f"❌ Error fetching top movies: {str(e)}")
            return []
    
    def enrich_movie_details(self, movies, limit=None):
        """Fetch additional details for each movie from their individual pages"""
        if not movies:
            return []
        
        total = len(movies) if limit is None else min(limit, len(movies))
        enriched_movies = []
        
        print(f"🔍 Fetching detailed information for {total} movies...")
        
        for i, movie in enumerate(movies[:total], 1):
            try:
                if not movie['URL']:
                    print(f"\n⚠️ No URL available for '{movie['Title']}'. Skipping details.")
                    enriched_movies.append(movie)
                    continue
                
                # Get the movie detail page
                response = self.session.get(movie['URL'])
                if response.status_code != 200:
                    print(f"\n⚠️ Failed to fetch details for '{movie['Title']}'. Status code: {response.status_code}")
                    enriched_movies.append(movie)
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract genres
                genres_section = soup.select('div.ipc-chip-list a.ipc-chip')
                movie['Genres'] = [g.text.strip() for g in genres_section if g.text.strip()]
                
                # Extract director
                try:
                    director_section = soup.select('a.ipc-metadata-list-item__list-content-item')
                    for director in director_section:
                        if "nm" in director.get('href', ''):  # Check if it's a name link
                            movie['Director'] = director.text.strip()
                            break
                except:
                    pass
                
                # Extract stars
                try:
                    stars_section = soup.select('div[data-testid="title-cast-item"]')
                    movie['Stars'] = [star.select_one('a[data-testid="title-cast-item__actor"]').text.strip() 
                                    for star in stars_section[:3] if star.select_one('a[data-testid="title-cast-item__actor"]')]
                except:
                    pass
                
                enriched_movies.append(movie)
                self.progress_bar(i, total)
                
                # Sleep to avoid hitting rate limits
                time.sleep(0.5)
                
            except Exception as e:
                print(f"\n❌ Error fetching details for '{movie['Title']}': {str(e)}")
                enriched_movies.append(movie)
        
        print("\n✅ Movie details successfully retrieved.")
        return enriched_movies
    
    def save_to_excel(self, movies, filename='imdb_top_250.xlsx'):
        """Save movie data to an aesthetically pleasing Excel file"""
        if not movies:
            print("❌ No data to save.")
            return False
        
        print(f"💾 Saving {len(movies)} movies to '{filename}'...")
        
        try:
            # Prepare the data for Excel
            df = pd.DataFrame(movies)
            
            # Format the data
            df['Genres'] = df['Genres'].apply(lambda x: ', '.join(x) if x else 'N/A')
            df['Stars'] = df['Stars'].apply(lambda x: ', '.join(x) if x else 'N/A')
            
            # Select and order columns for display
            display_columns = ['Rank', 'Title', 'Year', 'Rating', 'Genres', 'Director', 'Stars']
            df = df[display_columns]
            
            # Create Excel writer
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                # Write data without index
                df.to_excel(writer, sheet_name='Top Movies', index=False)
                
                # Get workbook and worksheet objects
                workbook = writer.book
                worksheet = writer.sheets['Top Movies']
                
                # Define formats
                title_format = workbook.add_format({
                    'bold': True, 
                    'font_color': 'white',
                    'bg_color': '#1F305E',  # Dark blue
                    'font_size': 14,
                    'align': 'center',
                    'valign': 'vcenter',
                    'border': 1
                })
                
                header_format = workbook.add_format({
                    'bold': True,
                    'font_color': 'white',
                    'bg_color': '#3A6FB7',  # Medium blue
                    'align': 'center',
                    'valign': 'vcenter',
                    'border': 1
                })
                
                rank_format = workbook.add_format({
                    'align': 'center',
                    'valign': 'vcenter',
                    'bg_color': '#E8EBF7',  # Light blue
                    'border': 1
                })
                
                title_cell_format = workbook.add_format({
                    'font_color': '#1F305E',  # Dark blue
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'border': 1
                })
                
                year_format = workbook.add_format({
                    'align': 'center',
                    'valign': 'vcenter',
                    'border': 1
                })
                
                rating_format = workbook.add_format({
                    'num_format': '0.0',
                    'align': 'center',
                    'valign': 'vcenter',
                    'bg_color': '#FFF4CC',  # Light yellow
                    'border': 1
                })
                
                text_format = workbook.add_format({
                    'text_wrap': True,
                    'valign': 'top',
                    'border': 1
                })
                
                # Add a title at the top
                worksheet.merge_range('A1:G1', 'IMDb Top 250 Movies', title_format)
                
                # Write the headers in row 2
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(1, col_num, value, header_format)
                
                # Write the data starting from row 3
                for row_num, row in enumerate(df.itertuples(index=False), 2):
                    worksheet.write(row_num, 0, row.Rank, rank_format)
                    worksheet.write(row_num, 1, row.Title, title_cell_format)
                    worksheet.write(row_num, 2, row.Year, year_format)
                    worksheet.write(row_num, 3, row.Rating, rating_format)
                    worksheet.write(row_num, 4, row.Genres, text_format)
                    worksheet.write(row_num, 5, row.Director, text_format)
                    worksheet.write(row_num, 6, row.Stars, text_format)
                
                # Auto-adjust column widths with some minimum sizes
                worksheet.set_column('A:A', 6)       # Rank
                worksheet.set_column('B:B', 40)      # Title
                worksheet.set_column('C:C', 8)       # Year
                worksheet.set_column('D:D', 8)       # Rating
                worksheet.set_column('E:E', 25)      # Genres
                worksheet.set_column('F:F', 20)      # Director
                worksheet.set_column('G:G', 30)      # Stars
                
                # Freeze panes (headers visible while scrolling)
                worksheet.freeze_panes(2, 0)
                
                # Add autofilter for easy sorting/filtering
                worksheet.autofilter(1, 0, len(df) + 1, len(display_columns) - 1)
                
                # Add alternate row coloring
                for row_num in range(2, len(df) + 2):
                    if row_num % 2 == 0:
                        worksheet.set_row(row_num, None, None, {'level': 1, 'hidden': False})
            
            print(f"✅ Successfully saved data to '{filename}'")
            return True
            
        except Exception as e:
            print(f"❌ Error saving to Excel: {str(e)}")
            return False

# Main execution
if __name__ == "__main__":
    print("🎬 IMDb Top 250 Movies Scraper 🎬")
    print("================================")
    
    scraper = ImdbScraper()
    
    # Get the list of top movies
    movies = scraper.get_top_movies()
    
    if movies:
        # Get detailed information for each movie
        enriched_movies = scraper.enrich_movie_details(movies)
        
        # Save to Excel
        scraper.save_to_excel(enriched_movies)
        
        print("\n🎉 All done! Your IMDb Top 250 list has been created with style!")
    else:
        print("\n❌ Failed to retrieve movies. Please check your internet connection or if IMDb has changed their website structure.")