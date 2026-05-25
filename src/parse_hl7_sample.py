from dataclasses import dataclass


SAMPLE_HL7_MESSAGE = """MSH|^~\\&|EHR|HOSPITAL|LAB|REFERENCE|202605251200||ADT^A01|MSG00001|P|2.5
PID|1||123456^^^HOSPITAL^MR||Doe^Jane||19880115|F
PV1|1|I|ONC^201^1||||1234^Smith^John
"""


@dataclass
class ParsedHL7Patient:
    message_type: str
    patient_id: str
    first_name: str
    last_name: str
    birth_date: str
    gender: str


def parse_hl7_adt(message: str) -> ParsedHL7Patient:
    """Parse a minimal HL7 ADT message for local validation.

    This is intentionally lightweight and does not replace a production HL7 parser.
    """
    segments = [line.split("|") for line in message.strip().splitlines()]
    segment_map = {segment[0]: segment for segment in segments}

    msh = segment_map.get("MSH", [])
    pid = segment_map.get("PID", [])

    message_type = msh[8] if len(msh) > 8 else ""
    patient_id = pid[3].split("^")[0] if len(pid) > 3 else ""

    name_parts = pid[5].split("^") if len(pid) > 5 else []
    last_name = name_parts[0] if len(name_parts) > 0 else ""
    first_name = name_parts[1] if len(name_parts) > 1 else ""

    birth_date = pid[7] if len(pid) > 7 else ""
    gender = pid[8] if len(pid) > 8 else ""

    return ParsedHL7Patient(
        message_type=message_type,
        patient_id=patient_id,
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
        gender=gender,
    )


if __name__ == "__main__":
    print(parse_hl7_adt(SAMPLE_HL7_MESSAGE))
