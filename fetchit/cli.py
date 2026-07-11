import argparse
import asyncio
import logging
import subprocess
import os
import sys
from importlib.metadata import version, PackageNotFoundError
from .crawler import Crawler

try:
    __version__ = version("fetchit")
except PackageNotFoundError:
    __version__ = "unknown"

class TqdmLoggingHandler(logging.Handler):
    """Custom logging handler that plays nicely with tqdm progress bars."""
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            import tqdm
            msg = self.format(record)
            tqdm.tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)

def setup_logging(verbose: bool):
    """Configures logging to use the TqdmLoggingHandler."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        
    handler = TqdmLoggingHandler()
    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    logger.addHandler(handler)

def start_background_compilation():
    """Starts the C++ compilation in the background to avoid blocking."""
    try:
        subprocess.Popen(
            ["make"], 
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        pass

def main():
    """Main entrypoint for the FetchIt CLI."""
    start_background_compilation()
    
    parser = argparse.ArgumentParser(description="Fetch It! - A highly concurrent web crawler and markdown extractor.")
    parser.add_argument("url", nargs="?", help="The base URL to crawl (e.g. https://developer.android.com/compose)")
    parser.add_argument("-o", "--output", default="output.md", help="Output file or directory name (if --tree is used)")
    parser.add_argument("-c", "--concurrency", type=int, default=10, help="Maximum concurrent requests")
    parser.add_argument("-r", "--retries", type=int, default=3, help="Number of retries for failed requests")
    parser.add_argument("--no-images", action="store_true", help="Skip downloading images and link them directly")
    parser.add_argument("--tree", action="store_true", help="Save output as a directory tree of markdown files instead of a single file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}", help="Print version information")

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    if not args.url:
        parser.print_help(sys.stderr)
        sys.exit(1)

    setup_logging(args.verbose)

    logging.info(f"Starting Fetch It! on {args.url}")
    logging.info(f"Output will be written to {args.output}")
    logging.info(f"Concurrency: {args.concurrency}, Retries: {args.retries}")

    crawler = Crawler(
        base_url=args.url,
        output_file=args.output,
        max_concurrency=args.concurrency,
        retries=args.retries,
        skip_images=args.no_images,
        tree_output=args.tree
    )

    try:
        asyncio.run(crawler.crawl())
    except KeyboardInterrupt:
        logging.info("Crawling interrupted by user. Saving progress...")
        if args.tree:
            crawler._generate_tree_output()
        else:
            crawler._generate_output()
        logging.info("Progress saved.")

if __name__ == "__main__":
    main()
