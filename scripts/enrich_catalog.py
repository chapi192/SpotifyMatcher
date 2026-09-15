import argparse

from web.catalog import initialize_catalog, recover_interrupted_sync_runs
from web.routes.enrichment import run_full_enrichment_pipeline, run_retry_enrichment_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill cached feature data for a local catalog user.")
    parser.add_argument("user_id", help="Spotify user ID stored in the local catalog")
    parser.add_argument(
        "--retry-unsuccessful", action="store_true",
        help="Retry cached missing, review, and error results while preserving successful results.",
    )
    args = parser.parse_args()
    initialize_catalog()
    recover_interrupted_sync_runs()
    pipeline = run_retry_enrichment_pipeline if args.retry_unsuccessful else run_full_enrichment_pipeline
    pipeline(args.user_id)


if __name__ == "__main__":
    main()
