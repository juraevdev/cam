"""Quick unit checks for plate cleaning (no camera / OCR required)."""

from plate_utils import clean_plate_text, extract_best_plate


def test_clean_and_extract() -> None:
    assert clean_plate_text(" 01 a 123 aa ") == "01A123AA"
    assert clean_plate_text("01А123АА") == "01A123AA"  # Cyrillic lookalikes

    plate = extract_best_plate(["Region", "01A", "123AA", "Gate"])
    assert plate == "01A123AA"

    plate2 = extract_best_plate(["noise", "01 A 123 AA", "x"])
    assert plate2 == "01A123AA"

    print("plate_utils OK")


if __name__ == "__main__":
    test_clean_and_extract()
