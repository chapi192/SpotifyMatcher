import argparse

from web.catalog import initialize_catalog, recover_interrupted_sync_runs
from web.routes.enrichment import run_full_enrichment_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill cached feature data for a local catalog user.")
    parser.add_argument("user_id", help="Spotify user ID stored in the local catalog")
    args = parser.parse_args()
    initialize_catalog()
    recover_interrupted_sync_runs()
    run_full_enrichment_pipeline(args.user_id)


if __name__ == "__main__":
    main()
