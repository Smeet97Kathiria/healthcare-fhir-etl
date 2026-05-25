from scripts.generate_synthetic_hl7 import main as generate_hl7
from src.load_hl7 import run_hl7_load


def main() -> None:
    print("Generating and loading synthetic HL7 v2 messages...")
    generate_hl7()
    stats = run_hl7_load()
    print(f"HL7 v2 load complete: {stats}")


if __name__ == "__main__":
    main()
