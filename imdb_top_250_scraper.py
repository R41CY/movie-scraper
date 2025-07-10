import requests
import requests.adapters
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
import re
import sys
from datetime import datetime

# Configuration constants
DEFAULT_TIMEOUT = 30
DEFAULT_SLEEP_INTERVAL = 0.5
PROGRESS_BAR_LENGTH = 50
CONNECTION_POOL_SIZE = 10
MAX_RETRIES = 3

# Configure request headers to mimic a browser
HEADERS = {
    'User-Agent': 'IMDb-Scraper/1.0 (Educational Purpose)',  # More ethical user agent
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Referer': 'https://www.imdb.com/',
    'Connection': 'keep-alive'
}

class ImdbScraper:
    def __init__(self, timeout=DEFAULT_TIMEOUT):
        self.base_url = 'https://www.imdb.com'
        self.top_movies_url = f"{self.base_url}/chart/top/"
        self.new_movies_url = f"{self.base_url}/chart/boxoffice/"  # Box office for latest movies
        self.newest_releases_url = f"{self.base_url}/chart/moviemeter/"  # Most popular current movies
        self.coming_soon_url = f"{self.base_url}/movies-coming-soon/"
        self.timeout = timeout
        self.sleep_interval = DEFAULT_SLEEP_INTERVAL
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        # Configure connection pooling for better performance
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=CONNECTION_POOL_SIZE,
            pool_maxsize=CONNECTION_POOL_SIZE * 2,
            max_retries=MAX_RETRIES
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def progress_bar(self, current, total, bar_length=PROGRESS_BAR_LENGTH, prefix=''):
        """Display a custom progress bar in the console"""
        progress = float(current) / float(total)
        arrow = '■' * int(round(progress * bar_length))
        spaces = ' ' * (bar_length - len(arrow))
        
        sys.stdout.write(f"\r{prefix}[{arrow}{spaces}] {int(progress * 100)}% ({current}/{total})")
        sys.stdout.flush()
    
    def get_top_movies(self):
        """Get the list of top movies from IMDb"""
        print("🏆 Fetching IMDb Top 250 movies list...")
        
        try:
            response = self.session.get(self.top_movies_url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all movie items
            movie_items = soup.select('li.ipc-metadata-list-summary-item')
            
            if not movie_items:
                print("❌ No top movie items found. IMDb may have changed their structure.")
                return []
            
            print(f"✅ Found {len(movie_items)} top-rated movies.")
            
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
                        'URL': movie_url,
                        'Type': 'Top Rated'
                    }
                    
                    movies.append(movie)
                    self.progress_bar(i, total, prefix='Top Movies: ')
                    
                except Exception as e:
                    print(f"\n❌ Error processing top movie #{i}: {str(e)}")
            
            print("\n✅ Top movies list retrieved.")
            return movies
            
        except (requests.RequestException, requests.Timeout) as e:
            print(f"❌ Network error fetching top movies: {str(e)}")
            return []
        except Exception as e:
            print(f"❌ Unexpected error fetching top movies: {str(e)}")
            return []
    
    def get_newest_movies(self):
        """Get the newest and trending movies from IMDb"""
        newest_movies = []
        
        # First try the Most Popular Movies list
        print("\n🔥 Fetching IMDb's Most Popular Movies (newest trending movies)...")
        
        try:
            response = self.session.get(self.newest_releases_url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all movie items
            movie_items = soup.select('li.ipc-metadata-list-summary-item')
            
            if not movie_items:
                print("⚠️ No newest movie items found. IMDb may have changed their structure.")
            else:
                print(f"✅ Found {len(movie_items)} popular/trending movies.")
                
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
                            'URL': movie_url,
                            'Type': 'Popular/Trending'
                        }
                        
                        newest_movies.append(movie)
                        self.progress_bar(i, total, prefix='Popular Movies: ')
                        
                    except Exception as e:
                        print(f"\n❌ Error processing popular movie #{i}: {str(e)}")
                
                print("\n✅ Popular movies list retrieved.")
        
        except (requests.RequestException, requests.Timeout) as e:
            print(f"❌ Network error fetching popular movies: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error fetching popular movies: {str(e)}")
        
        # Also get upcoming/coming soon movies
        print("\n🎬 Fetching IMDb's Coming Soon Movies...")
        
        try:
            # Get current month and year for the coming soon URL
            current_date = datetime.now()
            month_year = f"{current_date.year}-{current_date.month:02d}"
            coming_soon_url = f"{self.coming_soon_url}/{month_year}"
            
            response = self.session.get(coming_soon_url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all coming soon movie items
            movie_items = soup.select('div.list_item')
            
            if not movie_items:
                print("⚠️ No coming soon movie items found. Trying alternative selector...")
                movie_items = soup.select('div.nm-title-overview-widget-layout')
                
            if not movie_items:
                print("⚠️ No coming soon movies found. IMDb may have changed their structure.")
            else:
                print(f"✅ Found {len(movie_items)} coming soon movies.")
                
                total = len(movie_items)
                # Continue ranking from where popular movies left off
                current_rank = len([m for m in newest_movies if m['Type'] == 'Popular/Trending']) + 1
                
                for i, item in enumerate(movie_items, 1):
                    try:
                        # Extract movie details
                        title_elem = item.select_one('h4 a') or item.select_one('h3 a') or item.select_one('a.ipc-title-link-wrapper')
                        if not title_elem:
                            continue
                            
                        title = title_elem.text.strip()
                        
                        # Get release date if available
                        date_elem = item.select_one('div.list_item_date') or item.select_one('span.release_date')
                        release_date = date_elem.text.strip() if date_elem else "Coming Soon"
                        
                        # Get the movie URL for fetching additional details
                        movie_url = f"{self.base_url}{title_elem['href']}" if 'href' in title_elem.attrs else None
                        
                        # Build the movie object
                        movie = {
                            'Rank': current_rank,
                            'Title': title,
                            'Year': 'Coming Soon',
                            'Rating': 0.0,  # No rating yet for unreleased movies
                            'Genres': [],
                            'Director': "Unknown",
                            'Stars': [],
                            'URL': movie_url,
                            'Release Date': release_date,
                            'Type': 'Coming Soon'
                        }
                        
                        newest_movies.append(movie)
                        current_rank += 1
                        self.progress_bar(i, total, prefix='Coming Soon Movies: ')
                        
                    except Exception as e:
                        print(f"\n❌ Error processing coming soon movie #{i}: {str(e)}")
                
                print("\n✅ Coming soon movies list retrieved.")
        
        except (requests.RequestException, requests.Timeout) as e:
            print(f"❌ Network error fetching coming soon movies: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error fetching coming soon movies: {str(e)}")
        
        return newest_movies
    
    def enrich_movie_details(self, movies, limit=None):
        """Fetch additional details for each movie from their individual pages"""
        if not movies:
            return []
        
        total = len(movies) if limit is None else min(limit, len(movies))
        enriched_movies = []
        
        print(f"\n🔍 Fetching detailed information for {total} movies...")
        
        for i, movie in enumerate(movies[:total], 1):
            try:
                if not movie['URL']:
                    print(f"\n⚠️ No URL available for '{movie['Title']}'. Skipping details.")
                    enriched_movies.append(movie)
                    continue
                
                # Get the movie detail page
                response = self.session.get(movie['URL'], timeout=self.timeout)
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
                
                # Extract plot summary
                try:
                    plot_elem = soup.select_one('span[data-testid="plot-xl"]') or soup.select_one('span.GenresAndPlot__TextContainerBreakpointXL-cum89p-2')
                    if plot_elem:
                        movie['Plot'] = plot_elem.text.strip()
                except:
                    movie['Plot'] = "Plot not available"
                
                enriched_movies.append(movie)
                self.progress_bar(i, total, prefix='Fetching Details: ')
                
                # Sleep to avoid hitting rate limits
                time.sleep(self.sleep_interval)
                
            except Exception as e:
                print(f"\n❌ Error fetching details for '{movie['Title']}': {str(e)}")
                enriched_movies.append(movie)
        
        print("\n✅ Movie details successfully retrieved.")
        return enriched_movies
    
    def save_to_excel(self, top_movies, newest_movies, filename='imdb_movies.xlsx'):
        """Save movie data to an aesthetically pleasing Excel file with multiple sheets"""
        if not top_movies and not newest_movies:
            print("❌ No data to save.")
            return False
        
        print(f"\n💾 Saving movies to '{filename}'...")
        
        try:
            # Create Excel writer
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # Define common formats
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
                
                coming_soon_format = workbook.add_format({
                    'bold': True,
                    'font_color': '#9C27B0',  # Purple
                    'align': 'center',
                    'valign': 'vcenter',
                    'border': 1
                })
                
                # Add sheet for top movies if available
                if top_movies:
                    # Prepare the data for Excel
                    df_top = pd.DataFrame(top_movies)
                    
                    # Format the data
                    df_top['Genres'] = df_top['Genres'].apply(lambda x: ', '.join(x) if x else 'N/A')
                    df_top['Stars'] = df_top['Stars'].apply(lambda x: ', '.join(x) if x else 'N/A')
                    
                    # Select and order columns for display
                    display_columns = ['Rank', 'Title', 'Year', 'Rating', 'Genres', 'Director', 'Stars']
                    if 'Plot' in df_top.columns:
                        display_columns.append('Plot')
                    
                    df_top = df_top[display_columns]
                    
                    # Write to Excel
                    df_top.to_excel(writer, sheet_name='Top Movies', index=False)
                    worksheet = writer.sheets['Top Movies']
                    
                    # Add a title at the top
                    last_col_letter = chr(65 + len(display_columns) - 1)
                    worksheet.merge_range(f'A1:{last_col_letter}1', 'IMDb Top 250 Movies', title_format)
                    
                    # Write the headers in row 2
                    for col_num, value in enumerate(df_top.columns.values):
                        worksheet.write(1, col_num, value, header_format)
                    
                    # Write the data starting from row 3
                    for row_num, row in enumerate(df_top.itertuples(index=False), 2):
                        worksheet.write(row_num, 0, row.Rank, rank_format)
                        worksheet.write(row_num, 1, row.Title, title_cell_format)
                        worksheet.write(row_num, 2, row.Year, year_format)
                        worksheet.write(row_num, 3, row.Rating, rating_format)
                        worksheet.write(row_num, 4, row.Genres, text_format)
                        worksheet.write(row_num, 5, row.Director, text_format)
                        worksheet.write(row_num, 6, row.Stars, text_format)
                        if 'Plot' in df_top.columns:
                            worksheet.write(row_num, 7, getattr(row, 'Plot', ''), text_format)
                    
                    # Auto-adjust column widths
                    worksheet.set_column('A:A', 6)       # Rank
                    worksheet.set_column('B:B', 40)      # Title
                    worksheet.set_column('C:C', 8)       # Year
                    worksheet.set_column('D:D', 8)       # Rating
                    worksheet.set_column('E:E', 25)      # Genres
                    worksheet.set_column('F:F', 20)      # Director
                    worksheet.set_column('G:G', 30)      # Stars
                    if 'Plot' in df_top.columns:
                        worksheet.set_column('H:H', 50)  # Plot
                    
                    # Freeze panes (headers visible while scrolling)
                    worksheet.freeze_panes(2, 0)
                    
                    # Add autofilter for easy sorting/filtering
                    last_col = len(display_columns) - 1
                    worksheet.autofilter(1, 0, len(df_top) + 1, last_col)
                    
                    # Add alternate row coloring
                    for row_num in range(2, len(df_top) + 2):
                        if row_num % 2 == 0:
                            worksheet.set_row(row_num, None, None, {'level': 1, 'hidden': False})
                
                # Add sheet for newest movies if available
                if newest_movies:
                    # Split newest movies into Popular/Trending and Coming Soon
                    popular_movies = [m for m in newest_movies if m['Type'] == 'Popular/Trending']
                    coming_soon_movies = [m for m in newest_movies if m['Type'] == 'Coming Soon']
                    
                    # Process Popular/Trending movies
                    if popular_movies:
                        # Prepare the data for Excel
                        df_popular = pd.DataFrame(popular_movies)
                        
                        # Format the data
                        df_popular['Genres'] = df_popular['Genres'].apply(lambda x: ', '.join(x) if x else 'N/A')
                        df_popular['Stars'] = df_popular['Stars'].apply(lambda x: ', '.join(x) if x else 'N/A')
                        
                        # Select and order columns for display
                        display_columns = ['Rank', 'Title', 'Year', 'Rating', 'Genres', 'Director', 'Stars']
                        if 'Plot' in df_popular.columns:
                            display_columns.append('Plot')
                        
                        df_popular = df_popular[display_columns]
                        
                        # Write to Excel
                        df_popular.to_excel(writer, sheet_name='Popular Movies', index=False)
                        worksheet = writer.sheets['Popular Movies']
                        
                        # Add a title at the top
                        last_col_letter = chr(65 + len(display_columns) - 1)
                        worksheet.merge_range(f'A1:{last_col_letter}1', 'IMDb Most Popular Movies', title_format)
                        
                        # Write the headers in row 2
                        for col_num, value in enumerate(df_popular.columns.values):
                            worksheet.write(1, col_num, value, header_format)
                        
                        # Write the data starting from row 3
                        for row_num, row in enumerate(df_popular.itertuples(index=False), 2):
                            worksheet.write(row_num, 0, row.Rank, rank_format)
                            worksheet.write(row_num, 1, row.Title, title_cell_format)
                            worksheet.write(row_num, 2, row.Year, year_format)
                            worksheet.write(row_num, 3, row.Rating, rating_format)
                            worksheet.write(row_num, 4, row.Genres, text_format)
                            worksheet.write(row_num, 5, row.Director, text_format)
                            worksheet.write(row_num, 6, row.Stars, text_format)
                            if 'Plot' in df_popular.columns:
                                worksheet.write(row_num, 7, getattr(row, 'Plot', ''), text_format)
                        
                        # Auto-adjust column widths
                        worksheet.set_column('A:A', 6)       # Rank
                        worksheet.set_column('B:B', 40)      # Title
                        worksheet.set_column('C:C', 8)       # Year
                        worksheet.set_column('D:D', 8)       # Rating
                        worksheet.set_column('E:E', 25)      # Genres
                        worksheet.set_column('F:F', 20)      # Director
                        worksheet.set_column('G:G', 30)      # Stars
                        if 'Plot' in df_popular.columns:
                            worksheet.set_column('H:H', 50)  # Plot
                        
                        # Freeze panes (headers visible while scrolling)
                        worksheet.freeze_panes(2, 0)
                        
                        # Add autofilter for easy sorting/filtering
                        last_col = len(display_columns) - 1
                        worksheet.autofilter(1, 0, len(df_popular) + 1, last_col)
                        
                        # Add alternate row coloring
                        for row_num in range(2, len(df_popular) + 2):
                            if row_num % 2 == 0:
                                worksheet.set_row(row_num, None, None, {'level': 1, 'hidden': False})
                    
                    # Process Coming Soon movies
                    if coming_soon_movies:
                        # Prepare the data for Excel
                        df_coming_soon = pd.DataFrame(coming_soon_movies)
                        
                        # Format the data
                        df_coming_soon['Genres'] = df_coming_soon['Genres'].apply(lambda x: ', '.join(x) if x else 'N/A')
                        df_coming_soon['Stars'] = df_coming_soon['Stars'].apply(lambda x: ', '.join(x) if x else 'N/A')
                        
                        # Select and order columns for display
                        display_columns = ['Rank', 'Title', 'Release Date', 'Genres', 'Director', 'Stars']
                        if 'Plot' in df_coming_soon.columns:
                            display_columns.append('Plot')
                        
                        # Ensure all required columns exist
                        for col in display_columns:
                            if col not in df_coming_soon.columns:
                                df_coming_soon[col] = 'N/A'
                        
                        df_coming_soon = df_coming_soon[display_columns]
                        
                        # Write to Excel
                        df_coming_soon.to_excel(writer, sheet_name='Coming Soon', index=False)
                        worksheet = writer.sheets['Coming Soon']
                        
                        # Add a title at the top with custom color for Coming Soon
                        coming_soon_title_format = workbook.add_format({
                            'bold': True, 
                            'font_color': 'white',
                            'bg_color': '#6A1B9A',  # Dark Purple
                            'font_size': 14,
                            'align': 'center',
                            'valign': 'vcenter',
                            'border': 1
                        })
                        
                        coming_soon_header = workbook.add_format({
                            'bold': True,
                            'font_color': 'white',
                            'bg_color': '#9C27B0',  # Purple
                            'align': 'center',
                            'valign': 'vcenter',
                            'border': 1
                        })
                        
                        worksheet.merge_range(f'A1:{chr(65 + len(display_columns) - 1)}1', 'IMDb Coming Soon Movies', coming_soon_title_format)
                        
                        # Write the headers in row 2
                        for col_num, value in enumerate(df_coming_soon.columns.values):
                            worksheet.write(1, col_num, value, coming_soon_header)
                        
                        # Write the data starting from row 3
                        for row_num, row in enumerate(df_coming_soon.itertuples(index=False), 2):
                            worksheet.write(row_num, 0, row.Rank, rank_format)
                            worksheet.write(row_num, 1, row.Title, title_cell_format)
                            release_date = getattr(row, 'Release_Date', getattr(row, 'Release Date', 'TBD'))
                            worksheet.write(row_num, 2, release_date, coming_soon_format)
                            worksheet.write(row_num, 3, row.Genres, text_format)
                            worksheet.write(row_num, 4, row.Director, text_format)
                            worksheet.write(row_num, 5, row.Stars, text_format)
                            if 'Plot' in df_coming_soon.columns:
                                worksheet.write(row_num, 6, getattr(row, 'Plot', ''), text_format)
                        
                        # Auto-adjust column widths
                        worksheet.set_column('A:A', 6)       # Rank
                        worksheet.set_column('B:B', 40)      # Title
                        worksheet.set_column('C:C', 15)      # Release Date
                        worksheet.set_column('D:D', 25)      # Genres
                        worksheet.set_column('E:E', 20)      # Director
                        worksheet.set_column('F:F', 30)      # Stars
                        if 'Plot' in df_coming_soon.columns:
                            worksheet.set_column('G:G', 50)  # Plot
                        
                        # Freeze panes (headers visible while scrolling)
                        worksheet.freeze_panes(2, 0)
                        
                        # Add autofilter for easy sorting/filtering
                        last_col = len(display_columns) - 1
                        worksheet.autofilter(1, 0, len(df_coming_soon) + 1, last_col)
                        
                        # Add alternate row coloring
                        for row_num in range(2, len(df_coming_soon) + 2):
                            if row_num % 2 == 0:
                                worksheet.set_row(row_num, None, None, {'level': 1, 'hidden': False})
                
                # Add a Dashboard/Summary sheet
                worksheet = workbook.add_worksheet('Dashboard')
                
                # Create a title for the dashboard
                dashboard_title_format = workbook.add_format({
                    'bold': True,
                    'font_color': 'white',
                    'bg_color': '#1F305E',
                    'font_size': 16,
                    'align': 'center',
                    'valign': 'vcenter',
                    'border': 1
                })
                
                section_title_format = workbook.add_format({
                    'bold': True,
                    'font_color': 'white',
                    'bg_color': '#3A6FB7',
                    'font_size': 12,
                    'align': 'center',
                    'valign': 'vcenter',
                    'border': 1
                })
                
                item_format = workbook.add_format({
                    'font_size': 11,
                    'align': 'left',
                    'valign': 'vcenter',
                    'border': 1
                })
                
                value_format = workbook.add_format({
                    'font_size': 11,
                    'align': 'center',
                    'valign': 'vcenter',
                    'border': 1
                })
                
                # Set column widths for dashboard
                worksheet.set_column('A:A', 30)
                worksheet.set_column('B:B', 15)
                
                # Add Dashboard title
                worksheet.merge_range('A1:B1', 'IMDb Movie Data Dashboard', dashboard_title_format)
                
                # Add statistics
                row = 2
                worksheet.write(row, 0, 'Data Collection Summary', section_title_format)
                worksheet.write(row, 1, '', section_title_format)
                row += 1
                
                if top_movies:
                    worksheet.write(row, 0, 'Top Movies Count', item_format)
                    worksheet.write(row, 1, len(top_movies), value_format)
                    row += 1
                
                if newest_movies:
                    popular_count = len([m for m in newest_movies if m['Type'] == 'Popular/Trending'])
                    coming_soon_count = len([m for m in newest_movies if m['Type'] == 'Coming Soon'])
                    
                    worksheet.write(row, 0, 'Popular Movies Count', item_format)
                    worksheet.write(row, 1, popular_count, value_format)
                    row += 1
                    
                    worksheet.write(row, 0, 'Coming Soon Movies Count', item_format)
                    worksheet.write(row, 1, coming_soon_count, value_format)
                    row += 1
                
                total_movies = len(top_movies or []) + len(newest_movies or [])
                worksheet.write(row, 0, 'Total Movies Collected', item_format)
                worksheet.write(row, 1, total_movies, value_format)
                row += 1
                
                worksheet.write(row, 0, 'Data Collection Date', item_format)
                worksheet.write(row, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), value_format)
                
            print(f"✅ Excel file '{filename}' created successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error saving to Excel: {str(e)}")
            return False

    def run_scraper(self, include_details=True, details_limit=None):
        """Main method to run the complete scraping process"""
        print("🎬 Starting IMDb Movie Scraper...")
        print("=" * 60)
        
        # Get top movies
        top_movies = self.get_top_movies()
        
        # Get newest movies
        newest_movies = self.get_newest_movies()
        
        # Enrich with details if requested
        if include_details:
            if top_movies:
                print(f"\n🔍 Enriching top movies with detailed information...")
                top_movies = self.enrich_movie_details(top_movies, details_limit)
            
            if newest_movies:
                print(f"\n🔍 Enriching newest movies with detailed information...")
                newest_movies = self.enrich_movie_details(newest_movies, details_limit)
        
        # Save to Excel
        success = self.save_to_excel(top_movies, newest_movies)
        
        if success:
            print("\n🎉 Scraping completed successfully!")
            print(f"📊 Top movies collected: {len(top_movies or [])}")
            print(f"📊 Newest movies collected: {len(newest_movies or [])}")
        else:
            print("\n❌ Scraping completed with errors.")
        
        return top_movies, newest_movies


def main():
    """Main execution function"""
    scraper = ImdbScraper()
    
    try:
        # Run the scraper with details for first 50 movies of each type
        top_movies, newest_movies = scraper.run_scraper(
            include_details=True,
            details_limit=50
        )
        
    except KeyboardInterrupt:
        print("\n\n🛑 Scraping interrupted by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")


if __name__ == "__main__":
    main()