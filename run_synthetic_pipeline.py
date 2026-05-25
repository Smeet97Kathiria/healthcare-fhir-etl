from src.load_synthetic_fhir import run_synthetic_load


def main() -> None:
    print("Loading local synthetic FHIR bundles...")
    stats = run_synthetic_load()
    print(f"Synthetic FHIR load complete: {stats}")


if __name__ == "__main__":
    main()
