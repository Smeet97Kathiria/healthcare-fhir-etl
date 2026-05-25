from src.analytics import print_analytics
from src.extract_fhir import run_extract
from src.load_sqlite import run_load
from src.transform import run_transform


def main() -> None:
    print("Starting Healthcare FHIR ETL pipeline...")

    extract_stats = run_extract()
    print(f"Extract complete: {extract_stats}")

    transform_stats = run_transform()
    print(f"Transform complete: {transform_stats}")

    load_stats = run_load(extract_stats)
    print(f"Load complete: {load_stats}")

    print_analytics()
    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()
