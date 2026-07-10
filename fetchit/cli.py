import argparse
import asyncio
import logging
import subprocess
import os
from .crawler import Crawler

def start_background_compilation():
    """Starts the C++ compilation in the background."""
    try:
        # Run make in the background. Output is redirected to avoid cluttering CLI.
        subprocess.Popen(
            ["make"], 
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        pass

def main():
    start_background_compilation()
    
    parser = argparse.ArgumentParser(description="Fetch It! - A highly concurrent web crawler and markdown extractor.")
    parser.add_argument("url", help="The base URL to crawl (e.g. https://developer.android.com/compose)")
    parser.add_argument("-o", "--output", default="output.md", help="Output markdown file name")
    parser.add_argument("-c", "--concurrency", type=int, default=10, help="Maximum concurrent requests")
    parser.add_argument("-r", "--retries", type=int, default=3, help="Number of retries for failed requests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logging.info(f"Starting Fetch It! on {args.url}")
    logging.info(f"Output will be written to {args.output}")
    logging.info(f"Concurrency: {args.concurrency}, Retries: {args.retries}")

    crawler = Crawler(
        base_url=args.url,
        output_file=args.output,
        max_concurrency=args.concurrency,
        retries=args.retries
    )

    try:
        asyncio.run(crawler.crawl())
    except KeyboardInterrupt:
        logging.info("Crawling interrupted by user. Saving progress...")
        crawler._generate_output()
        logging.info("Progress saved.")

if __name__ == "__main__":
    main()
