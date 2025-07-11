#!/usr/bin/env python3
"""
Performance Benchmark Script for IMDb Scrapers

This script compares the performance between the original and optimized scrapers.
"""

import asyncio
import time
import psutil
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any, List


class PerformanceMonitor:
    """Monitor system resources and performance metrics"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.peak_memory = None
        self.cpu_usage = []
        self.process = psutil.Process()
        
    def start_monitoring(self):
        """Start performance monitoring"""
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak_memory = self.start_memory
        self.cpu_usage = []
        
    async def monitor_during_execution(self):
        """Monitor CPU and memory during execution"""
        while self.start_time and not self.end_time:
            try:
                cpu_percent = self.process.cpu_percent()
                memory_mb = self.process.memory_info().rss / 1024 / 1024
                
                self.cpu_usage.append(cpu_percent)
                if memory_mb > self.peak_memory:
                    self.peak_memory = memory_mb
                    
                await asyncio.sleep(1)  # Monitor every second
            except:
                break
                
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.end_time = time.time()
        
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        if not self.start_time or not self.end_time:
            return {}
            
        return {
            'duration_seconds': (self.end_time - self.start_time) if self.end_time and self.start_time else 0,
            'memory_start_mb': self.start_memory or 0,
            'memory_peak_mb': self.peak_memory or 0,
            'memory_delta_mb': (self.peak_memory - self.start_memory) if self.peak_memory and self.start_memory else 0,
            'cpu_avg_percent': sum(self.cpu_usage) / len(self.cpu_usage) if self.cpu_usage else 0,
            'cpu_max_percent': max(self.cpu_usage) if self.cpu_usage else 0
        }


@asynccontextmanager
async def benchmark_context(test_name: str):
    """Context manager for benchmarking operations"""
    monitor = PerformanceMonitor()
    monitor.start_monitoring()
    
    # Start monitoring task
    monitor_task = asyncio.create_task(monitor.monitor_during_execution())
    
    print(f"\n🚀 Starting benchmark: {test_name}")
    print("=" * 60)
    
    try:
        yield monitor
    finally:
        monitor.stop_monitoring()
        monitor_task.cancel()
        
        # Get and display metrics
        metrics = monitor.get_metrics()
        print(f"\n📊 Benchmark Results for {test_name}:")
        print(f"  Duration: {metrics.get('duration_seconds', 0):.2f} seconds")
        print(f"  Memory Start: {metrics.get('memory_start_mb', 0):.1f} MB")
        print(f"  Memory Peak: {metrics.get('memory_peak_mb', 0):.1f} MB")
        print(f"  Memory Delta: {metrics.get('memory_delta_mb', 0):.1f} MB")
        print(f"  CPU Average: {metrics.get('cpu_avg_percent', 0):.1f}%")
        print(f"  CPU Peak: {metrics.get('cpu_max_percent', 0):.1f}%")


async def benchmark_optimized_scraper(limit: int = 25):
    """Benchmark the optimized async scraper"""
    async with benchmark_context("Optimized Async Scraper") as monitor:
        try:
            # Import here to avoid import issues if dependencies are missing
            from imdb_scraper_optimized import PerformanceOptimizedScraper
            
            async with PerformanceOptimizedScraper(concurrent_requests=10) as scraper:
                top_movies = await scraper.get_top_movies()
                top_movies = top_movies[:limit]  # Limit for benchmark
                
                if top_movies:
                    enriched_movies = await scraper.enrich_movies_concurrent(top_movies, limit)
                    print(f"✅ Processed {len(enriched_movies)} movies with async scraper")
                    
                    # Log scraper metrics
                    scraper_metrics = scraper.metrics
                    print(f"  Requests Made: {scraper_metrics['requests_made']}")
                    print(f"  Cache Hits: {scraper_metrics['cache_hits']}")
                    print(f"  Errors: {scraper_metrics['errors']}")
                else:
                    print("❌ No movies fetched")
                    
        except ImportError as e:
            print(f"❌ Could not import optimized scraper: {e}")
        except Exception as e:
            print(f"❌ Error in optimized scraper benchmark: {e}")


def benchmark_original_scraper(limit: int = 25):
    """Benchmark the original synchronous scraper"""
    print(f"\n🐌 Starting benchmark: Original Synchronous Scraper")
    print("=" * 60)
    
    monitor = PerformanceMonitor()
    monitor.start_monitoring()
    
    try:
        # Import here to avoid import issues if dependencies are missing
        from imdb_top_250_scraper import ImdbScraper
        
        scraper = ImdbScraper()
        top_movies = scraper.get_top_movies()
        top_movies = top_movies[:limit]  # Limit for benchmark
        
        if top_movies:
            enriched_movies = scraper.enrich_movie_details(top_movies, limit)
            print(f"✅ Processed {len(enriched_movies)} movies with original scraper")
        else:
            print("❌ No movies fetched")
            
    except ImportError as e:
        print(f"❌ Could not import original scraper: {e}")
    except Exception as e:
        print(f"❌ Error in original scraper benchmark: {e}")
    finally:
        monitor.stop_monitoring()
        
        # Get and display metrics
        metrics = monitor.get_metrics()
        print(f"\n📊 Benchmark Results for Original Synchronous Scraper:")
        print(f"  Duration: {metrics.get('duration_seconds', 0):.2f} seconds")
        print(f"  Memory Start: {metrics.get('memory_start_mb', 0):.1f} MB")
        print(f"  Memory Peak: {metrics.get('memory_peak_mb', 0):.1f} MB")
        print(f"  Memory Delta: {metrics.get('memory_delta_mb', 0):.1f} MB")
        print(f"  CPU Average: {metrics.get('cpu_avg_percent', 0):.1f}%")
        print(f"  CPU Peak: {metrics.get('cpu_max_percent', 0):.1f}%")


async def run_full_benchmark():
    """Run complete performance comparison"""
    print("🏁 IMDb Scraper Performance Benchmark")
    print("=" * 80)
    print("This benchmark compares the original and optimized scrapers.")
    print("Note: Limited to 25 movies per test for reasonable execution time.")
    print("=" * 80)
    
    # Test with limited sample for reasonable benchmark time
    limit = 25
    
    # Run original scraper benchmark (synchronous)
    benchmark_original_scraper(limit)
    
    # Small delay between tests
    await asyncio.sleep(2)
    
    # Run optimized scraper benchmark (asynchronous)
    await benchmark_optimized_scraper(limit)
    
    print("\n🎯 Benchmark Complete!")
    print("=" * 80)
    print("Key Improvements in Optimized Version:")
    print("• ⚡ Concurrent HTTP requests for faster data fetching")
    print("• 💾 Built-in caching to reduce redundant requests")
    print("• 🔧 Better error handling and retry logic")
    print("• 📊 Performance metrics tracking")
    print("• 🏗️ Structured data types for better memory efficiency")
    print("• 🔄 Async/await pattern for non-blocking operations")


def check_dependencies():
    """Check if required dependencies are available"""
    missing_deps = []
    
    try:
        import aiohttp
    except ImportError:
        missing_deps.append("aiohttp")
    
    try:
        import pandas
    except ImportError:
        missing_deps.append("pandas")
        
    try:
        import psutil
    except ImportError:
        missing_deps.append("psutil")
    
    if missing_deps:
        print("❌ Missing dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nInstall missing dependencies with:")
        print("pip install " + " ".join(missing_deps))
        return False
    
    return True


if __name__ == "__main__":
    if not check_dependencies():
        sys.exit(1)
    
    # Run the benchmark
    try:
        asyncio.run(run_full_benchmark())
    except KeyboardInterrupt:
        print("\n🛑 Benchmark interrupted by user.")
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")