import asyncio
import aiohttp
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
import re
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
import os

# Configuration constants
DEFAULT_TIMEOUT = 30
DEFAULT_SLEEP_INTERVAL = 0.1  # Reduced for async operations
PROGRESS_BAR_LENGTH = 50
CONNECTION_POOL_SIZE = 20  # Increased for async operations
MAX_RETRIES = 3
CONCURRENT_REQUESTS = 10  # Number of concurrent requests
CHUNK_SIZE = 25  # Process movies in chunks
CACHE_ENABLED = True
CACHE_DURATION = 3600  # 1 hour cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('imdb_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure request headers to mimic a browser
HEADERS = {
    'User-Agent': 'IMDb-Scraper/2.0 (Educational Purpose)',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Referer': 'https://www.imdb.com/',
    'Connection': 'keep-alive',
    'Accept-Encoding': 'gzip, deflate, br'
}

@dataclass
class Movie:
    """Movie data structure for better performance and type safety"""
    rank: int
    title: str
    year: Union[int, str]
    rating: float
    genres: List[str]
    director: str
    stars: List[str]
    url: Optional[str]
    movie_type: str
    plot: str = ""
    release_date: str = ""

class PerformanceOptimizedScraper:
    def __init__(self, timeout=DEFAULT_TIMEOUT, concurrent_requests=CONCURRENT_REQUESTS):
        self.base_url = 'https://www.imdb.com'
        self.top_movies_url = f"{self.base_url}/chart/top/"
        self.newest_releases_url = f"{self.base_url}/chart/moviemeter/"
        self.coming_soon_url = f"{self.base_url}/movies-coming-soon/"
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.concurrent_requests = concurrent_requests
        self.cache = {}
        self.session = None
        
        # Performance metrics
        self.metrics = {
            'requests_made': 0,
            'cache_hits': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(
            limit=CONNECTION_POOL_SIZE * 2,
            limit_per_host=CONNECTION_POOL_SIZE,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        self.session = aiohttp.ClientSession(
            headers=HEADERS,
            timeout=self.timeout,
            connector=connector
        )
        self.metrics['start_time'] = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with proper cleanup"""
        if self.session:
            await self.session.close()
        self.metrics['end_time'] = time.time()
        self._log_performance_metrics()
    
    def _log_performance_metrics(self):
        """Log performance metrics"""
        if self.metrics['start_time'] and self.metrics['end_time']:
            duration = self.metrics['end_time'] - self.metrics['start_time']
            logger.info(f"Performance Metrics:")
            logger.info(f"  Total Duration: {duration:.2f}s")
            logger.info(f"  Requests Made: {self.metrics['requests_made']}")
            logger.info(f"  Cache Hits: {self.metrics['cache_hits']}")
            logger.info(f"  Errors: {self.metrics['errors']}")
            logger.info(f"  Avg Request Time: {duration/max(1, self.metrics['requests_made']):.2f}s")
    
    def progress_bar(self, current, total, bar_length=PROGRESS_BAR_LENGTH, prefix=''):
        """Display a custom progress bar in the console"""
        progress = float(current) / float(total)
        arrow = '■' * int(round(progress * bar_length))
        spaces = ' ' * (bar_length - len(arrow))
        
        sys.stdout.write(f"\r{prefix}[{arrow}{spaces}] {int(progress * 100)}% ({current}/{total})")
        sys.stdout.flush()
    
    async def _fetch_with_retry(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """Fetch URL with retry logic and caching"""
        # Check cache first
        if CACHE_ENABLED and url in self.cache:
            cache_time, content = self.cache[url]
            if time.time() - cache_time < CACHE_DURATION:
                self.metrics['cache_hits'] += 1
                return content
        
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(url) as response:
                    self.metrics['requests_made'] += 1
                    if response.status == 200:
                        content = await response.text()
                        # Cache the result
                        if CACHE_ENABLED:
                            self.cache[url] = (time.time(), content)
                        return content
                    elif response.status == 429:  # Rate limited
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited. Waiting {wait_time}s before retry {attempt + 1}")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout for {url} (attempt {attempt + 1})")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                self.metrics['errors'] += 1
                await asyncio.sleep(1)
        
        return None
    
    async def get_top_movies(self) -> List[Movie]:
        """Get the list of top movies from IMDb using async requests"""
        logger.info("🏆 Fetching IMDb Top 250 movies list...")
        
        content = await self._fetch_with_retry(self.top_movies_url, self.session)
        if not content:
            logger.error("Failed to fetch top movies page")
            return []
        
        soup = BeautifulSoup(content, 'html.parser')
        movie_items = soup.select('li.ipc-metadata-list-summary-item')
        
        if not movie_items:
            logger.error("No top movie items found. IMDb may have changed their structure.")
            return []
        
        logger.info(f"✅ Found {len(movie_items)} top-rated movies.")
        
        movies = []
        for i, item in enumerate(movie_items, 1):
            try:
                movie = self._parse_movie_item(item, i, 'Top Rated')
                if movie:
                    movies.append(movie)
                self.progress_bar(i, len(movie_items), prefix='Top Movies: ')
            except Exception as e:
                logger.error(f"Error processing top movie #{i}: {str(e)}")
        
        print("\n✅ Top movies list retrieved.")
        return movies
    
    async def get_newest_movies(self) -> List[Movie]:
        """Get the newest and trending movies from IMDb"""
        logger.info("🔥 Fetching IMDb's Most Popular Movies...")
        
        content = await self._fetch_with_retry(self.newest_releases_url, self.session)
        if not content:
            logger.error("Failed to fetch newest movies page")
            return []
        
        soup = BeautifulSoup(content, 'html.parser')
        movie_items = soup.select('li.ipc-metadata-list-summary-item')
        
        if not movie_items:
            logger.warning("No newest movie items found.")
            return []
        
        logger.info(f"✅ Found {len(movie_items)} popular/trending movies.")
        
        movies = []
        for i, item in enumerate(movie_items, 1):
            try:
                movie = self._parse_movie_item(item, i, 'Popular/Trending')
                if movie:
                    movies.append(movie)
                self.progress_bar(i, len(movie_items), prefix='Popular Movies: ')
            except Exception as e:
                logger.error(f"Error processing popular movie #{i}: {str(e)}")
        
        print("\n✅ Popular movies list retrieved.")
        return movies
    
    def _parse_movie_item(self, item, rank: int, movie_type: str) -> Optional[Movie]:
        """Parse a movie item from the list page"""
        try:
            # Extract movie details
            title_elem = item.select_one('h3.ipc-title__text')
            full_title = title_elem.text.strip() if title_elem else "Unknown Title"
            title = re.sub(r'^\d+\.\s+', '', full_title)
            
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
            
            # Get the movie URL
            link_elem = item.select_one('a.ipc-title-link-wrapper')
            movie_url = f"{self.base_url}{link_elem['href']}" if link_elem and 'href' in link_elem.attrs else None
            
            return Movie(
                rank=rank,
                title=title,
                year=int(year) if year.isdigit() else year,
                rating=rating,
                genres=[],
                director="Unknown",
                stars=[],
                url=movie_url,
                movie_type=movie_type
            )
        except Exception as e:
            logger.error(f"Error parsing movie item: {str(e)}")
            return None
    
    async def _enrich_movie_details(self, movie: Movie) -> Movie:
        """Fetch additional details for a single movie"""
        if not movie.url:
            return movie
        
        content = await self._fetch_with_retry(movie.url, self.session)
        if not content:
            return movie
        
        soup = BeautifulSoup(content, 'html.parser')
        
        try:
            # Extract genres
            genres_section = soup.select('div.ipc-chip-list a.ipc-chip')
            movie.genres = [g.text.strip() for g in genres_section if g.text.strip()]
            
            # Extract director
            director_section = soup.select('a.ipc-metadata-list-item__list-content-item')
            for director in director_section:
                if "nm" in director.get('href', ''):
                    movie.director = director.text.strip()
                    break
            
            # Extract stars
            stars_section = soup.select('div[data-testid="title-cast-item"]')
            movie.stars = [
                star.select_one('a[data-testid="title-cast-item__actor"]').text.strip() 
                for star in stars_section[:3] 
                if star.select_one('a[data-testid="title-cast-item__actor"]')
            ]
            
            # Extract plot summary
            plot_elem = soup.select_one('span[data-testid="plot-xl"]')
            if plot_elem:
                movie.plot = plot_elem.text.strip()
            
        except Exception as e:
            logger.error(f"Error enriching movie details for '{movie.title}': {str(e)}")
        
        return movie
    
    async def enrich_movies_concurrent(self, movies: List[Movie], limit: Optional[int] = None) -> List[Movie]:
        """Enrich movie details using concurrent requests"""
        if not movies:
            return []
        
        movies_to_process = movies[:limit] if limit else movies
        total = len(movies_to_process)
        
        logger.info(f"🔍 Fetching detailed information for {total} movies concurrently...")
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.concurrent_requests)
        
        async def enrich_with_semaphore(movie):
            async with semaphore:
                return await self._enrich_movie_details(movie)
        
        # Process movies in chunks to avoid overwhelming the server
        enriched_movies = []
        
        for i in range(0, total, CHUNK_SIZE):
            chunk = movies_to_process[i:i + CHUNK_SIZE]
            logger.info(f"Processing chunk {i//CHUNK_SIZE + 1}/{(total + CHUNK_SIZE - 1)//CHUNK_SIZE}")
            
            # Process chunk concurrently
            tasks = [enrich_with_semaphore(movie) for movie in chunk]
            chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle results and exceptions
            for j, result in enumerate(chunk_results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing movie {i+j}: {str(result)}")
                    enriched_movies.append(chunk[j])  # Add original movie
                else:
                    enriched_movies.append(result)
            
            # Progress update
            self.progress_bar(min(i + CHUNK_SIZE, total), total, prefix='Fetching Details: ')
            
            # Small delay between chunks
            if i + CHUNK_SIZE < total:
                await asyncio.sleep(0.5)
        
        print("\n✅ Movie details successfully retrieved.")
        return enriched_movies
    
    def save_to_excel_optimized(self, top_movies: List[Movie], newest_movies: List[Movie], filename='imdb_movies_optimized.xlsx'):
        """Save movie data to Excel with optimized performance"""
        if not top_movies and not newest_movies:
            logger.error("No data to save.")
            return False
        
        logger.info(f"💾 Saving movies to '{filename}'...")
        
        try:
            # Convert Movie objects to dictionaries for pandas
            def movies_to_df(movies: List[Movie]) -> pd.DataFrame:
                data = []
                for movie in movies:
                    data.append({
                        'Rank': movie.rank,
                        'Title': movie.title,
                        'Year': movie.year,
                        'Rating': movie.rating,
                        'Genres': ', '.join(movie.genres) if movie.genres else 'N/A',
                        'Director': movie.director,
                        'Stars': ', '.join(movie.stars) if movie.stars else 'N/A',
                        'Plot': movie.plot or 'N/A'
                    })
                return pd.DataFrame(data)
            
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # Define formats
                title_format = workbook.add_format({
                    'bold': True, 'font_color': 'white', 'bg_color': '#1F305E',
                    'font_size': 14, 'align': 'center', 'valign': 'vcenter', 'border': 1
                })
                
                header_format = workbook.add_format({
                    'bold': True, 'font_color': 'white', 'bg_color': '#3A6FB7',
                    'align': 'center', 'valign': 'vcenter', 'border': 1
                })
                
                # Save top movies
                if top_movies:
                    df_top = movies_to_df(top_movies)
                    df_top.to_excel(writer, sheet_name='Top Movies', index=False, startrow=1)
                    
                    worksheet = writer.sheets['Top Movies']
                    worksheet.merge_range('A1:H1', 'IMDb Top 250 Movies (Optimized)', title_format)
                    
                    # Apply header formatting
                    for col_num, value in enumerate(df_top.columns.values):
                        worksheet.write(1, col_num, value, header_format)
                    
                    # Auto-adjust column widths
                    worksheet.set_column('A:A', 6)   # Rank
                    worksheet.set_column('B:B', 40)  # Title
                    worksheet.set_column('C:C', 8)   # Year
                    worksheet.set_column('D:D', 8)   # Rating
                    worksheet.set_column('E:E', 25)  # Genres
                    worksheet.set_column('F:F', 20)  # Director
                    worksheet.set_column('G:G', 30)  # Stars
                    worksheet.set_column('H:H', 50)  # Plot
                
                # Save newest movies
                if newest_movies:
                    df_newest = movies_to_df(newest_movies)
                    df_newest.to_excel(writer, sheet_name='Popular Movies', index=False, startrow=1)
                    
                    worksheet = writer.sheets['Popular Movies']
                    worksheet.merge_range('A1:H1', 'IMDb Popular Movies (Optimized)', title_format)
                    
                    # Apply header formatting
                    for col_num, value in enumerate(df_newest.columns.values):
                        worksheet.write(1, col_num, value, header_format)
                    
                    # Auto-adjust column widths
                    worksheet.set_column('A:A', 6)   # Rank
                    worksheet.set_column('B:B', 40)  # Title
                    worksheet.set_column('C:C', 8)   # Year
                    worksheet.set_column('D:D', 8)   # Rating
                    worksheet.set_column('E:E', 25)  # Genres
                    worksheet.set_column('F:F', 20)  # Director
                    worksheet.set_column('G:G', 30)  # Stars
                    worksheet.set_column('H:H', 50)  # Plot
                
                # Add performance metrics sheet
                metrics_sheet = workbook.add_worksheet('Performance')
                metrics_sheet.write(0, 0, 'Performance Metrics', title_format)
                
                metrics_data = [
                    ['Total Duration (seconds)', self.metrics.get('end_time', 0) - self.metrics.get('start_time', 0)],
                    ['Requests Made', self.metrics['requests_made']],
                    ['Cache Hits', self.metrics['cache_hits']],
                    ['Errors', self.metrics['errors']],
                    ['Top Movies Count', len(top_movies)],
                    ['Popular Movies Count', len(newest_movies)],
                    ['Total Movies', len(top_movies) + len(newest_movies)],
                    ['Generated At', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                ]
                
                for i, (label, value) in enumerate(metrics_data, 1):
                    metrics_sheet.write(i, 0, label)
                    metrics_sheet.write(i, 1, value)
            
            logger.info(f"✅ Excel file '{filename}' created successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Error saving to Excel: {str(e)}")
            return False
    
    async def run_optimized_scraper(self, include_details=True, details_limit=50):
        """Main method to run the optimized scraping process"""
        logger.info("🎬 Starting Optimized IMDb Movie Scraper...")
        logger.info("=" * 60)
        
        try:
            # Get movies concurrently
            top_movies_task = self.get_top_movies()
            newest_movies_task = self.get_newest_movies()
            
            top_movies, newest_movies = await asyncio.gather(
                top_movies_task, newest_movies_task, return_exceptions=True
            )
            
            # Handle exceptions and ensure correct types
            if isinstance(top_movies, Exception):
                logger.error(f"Error fetching top movies: {top_movies}")
                top_movies = []
            elif not isinstance(top_movies, list):
                top_movies = []
            
            if isinstance(newest_movies, Exception):
                logger.error(f"Error fetching newest movies: {newest_movies}")
                newest_movies = []
            elif not isinstance(newest_movies, list):
                newest_movies = []
            
            # Enrich with details if requested
            if include_details:
                if top_movies:
                    top_movies = await self.enrich_movies_concurrent(top_movies, details_limit)
                
                if newest_movies:
                    newest_movies = await self.enrich_movies_concurrent(newest_movies, details_limit)
            
            # Save to Excel
            success = self.save_to_excel_optimized(top_movies, newest_movies)
            
            if success:
                logger.info("🎉 Optimized scraping completed successfully!")
                logger.info(f"📊 Top movies collected: {len(top_movies)}")
                logger.info(f"📊 Newest movies collected: {len(newest_movies)}")
            else:
                logger.error("Scraping completed with errors.")
            
            return top_movies, newest_movies
            
        except Exception as e:
            logger.error(f"Unexpected error in main scraper: {str(e)}")
            return [], []

async def main():
    """Main execution function with proper async context management"""
    try:
        async with PerformanceOptimizedScraper(concurrent_requests=15) as scraper:
            await scraper.run_optimized_scraper(
                include_details=True,
                details_limit=100  # Increased limit due to performance improvements
            )
    except KeyboardInterrupt:
        logger.info("🛑 Scraping interrupted by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    # Check if running in an event loop
    try:
        asyncio.get_running_loop()
        logger.warning("Already running in an event loop. Use await main() instead.")
    except RuntimeError:
        asyncio.run(main())