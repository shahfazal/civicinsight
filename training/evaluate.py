import re

"""
Evaluation pipeline for CivicInsight.
Measures how accurately the model extracts numbers from civic dashboards.
"""


def normalize_number(text):
    """
    Convert a single number token to a plain float.
    Examples: "14.6M" -> 14600000.0, "€40K" -> 40000.0, "2.3%" -> 0.023
    """
    # Strip currency prefixes
    text = text.replace("€", "").replace("$", "").replace("£", "").strip()

    multipliers = {
        "K": 1_000,
        "M": 1_000_000,
        "B": 1_000_000_000,
        "T": 1_000_000_000_000,
        "%": 0.01,
        "":  1,
    }

    # Split into number part and unit part
    # (\d[\d,]*\.?\d*) captures integers and decimals, including comma-formatted (40,000)
    # ([KMBT%]?)       captures the optional suffix
    match = re.match(r"(\d[\d,]*\.?\d*)([KMBT%]?)$", text.strip(), re.IGNORECASE)
    if not match:
        return None

    num_str, unit = match.group(1), match.group(2).upper()

    # Remove thousands commas before converting: "40,000" -> "40000"
    num = float(num_str.replace(",", ""))

    return num * multipliers.get(unit, 1)


def extract_numbers(text):
    """
    Find all number tokens in a text string and return as a list of floats.
    Handles: 14.6M, 14,600,000, €40K, 2.3%, 0.65
    """
    # Match optional currency prefix + number + optional suffix
    pattern = r"[€$£]?\d[\d,]*\.?\d*[KMBT%]?"
    tokens = re.findall(pattern, text, re.IGNORECASE)

    results = []
    for token in tokens:
        normalized = normalize_number(token)
        if normalized is not None:
            results.append(normalized)

    return results


def calculate_accuracy(generated_numbers, ground_truth_numbers):
    """
    What fraction of ground truth numbers appear in the generated output.
    Both inputs are lists of floats (already normalized).
    Returns a float between 0.0 and 1.0.
    """
    if not ground_truth_numbers:
        return 0.0

    matched = sum(1 for n in ground_truth_numbers if n in generated_numbers)
    return matched / len(ground_truth_numbers)


# --- Manual tests --- run with: python training/evaluate.py

if __name__ == "__main__":
    # Test normalize_number
    assert normalize_number("14.6M") == 14_600_000.0,  "14.6M failed"
    assert normalize_number("€40K")  == 40_000.0,      "€40K failed"
    assert normalize_number("2.3%")  == 0.023,          "2.3% failed"
    assert normalize_number("40,000") == 40_000.0,     "40,000 failed"
    assert normalize_number("0.65")  == 0.65,           "0.65 failed"
    print("✅ normalize_number: all tests passed")

    # Test extract_numbers
    text = "This dashboard shows 14.6M visitors, a 2.3% increase. Revenue was €40K."
    numbers = extract_numbers(text)
    assert 14_600_000.0 in numbers, "14.6M not extracted"
    assert 0.023        in numbers, "2.3% not extracted"
    assert 40_000.0     in numbers, "€40K not extracted"
    print(f"✅ extract_numbers: {numbers}")

    # Test calculate_accuracy
    generated    = [14_600_000.0, 0.023, 40_000.0, 999.0]  # 999 is a hallucination
    ground_truth = [14_600_000.0, 0.023, 40_000.0]
    accuracy = calculate_accuracy(generated, ground_truth)
    assert accuracy == 1.0, f"Expected 1.0, got {accuracy}"
    print(f"✅ calculate_accuracy: {accuracy:.0%} — perfect match")

    # Test with a miss
    generated_partial = [14_600_000.0, 0.023]  # missing €40K
    accuracy_partial  = calculate_accuracy(generated_partial, ground_truth)
    assert round(accuracy_partial, 2) == 0.67, f"Expected 0.67, got {accuracy_partial}"
    print(f"✅ calculate_accuracy: {accuracy_partial:.0%} — partial match (2 of 3)")

    print("\n✅ All tests passed")
