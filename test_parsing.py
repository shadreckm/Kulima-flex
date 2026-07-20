"""Unit test suite for safe_float and parse_qualitative_score."""

from kulima.scoring import safe_float, parse_qualitative_score

def run_tests():
    print("Running tests for safe_float and parse_qualitative_score...")

    # Test safe_float
    assert safe_float(85) == 85.0
    assert safe_float(42.5) == 42.5
    assert safe_float("42.5") == 42.5
    assert safe_float("85%") == 85.0
    assert safe_float(" -12.34 ") == -12.34
    assert safe_float("abc", 10.0) == 10.0
    assert safe_float(None, 5.0) == 5.0
    print("- safe_float tests passed.")

    # Test parse_qualitative_score: Risk (is_risk=True)
    assert parse_qualitative_score("Low", is_risk=True) == 20.0
    assert parse_qualitative_score("Medium", is_risk=True) == 50.0
    assert parse_qualitative_score("High", is_risk=True) == 75.0
    assert parse_qualitative_score("Very High", is_risk=True) == 90.0
    assert parse_qualitative_score("Critical", is_risk=True) == 95.0
    
    # Substring matching for risk
    assert parse_qualitative_score("High risk alert", is_risk=True) == 75.0
    assert parse_qualitative_score("Low severity", is_risk=True) == 20.0
    print("- Risk qualitative score tests passed.")

    # Test parse_qualitative_score: General (is_risk=False)
    assert parse_qualitative_score("Low", is_risk=False) == 20.0
    assert parse_qualitative_score("Medium", is_risk=False) == 50.0
    assert parse_qualitative_score("High", is_risk=False) == 80.0
    assert parse_qualitative_score("Very High", is_risk=False) == 95.0
    assert parse_qualitative_score("Critical", is_risk=False) == 20.0
    
    # Substring matching for general
    assert parse_qualitative_score("High quality", is_risk=False) == 80.0
    print("- General qualitative score tests passed.")

    # Test parse_qualitative_score: Numeric strings, percentages, fallbacks
    assert parse_qualitative_score("85", is_risk=True) == 85.0
    assert parse_qualitative_score("42.5%", is_risk=False) == 42.5
    assert parse_qualitative_score("85%", is_risk=True) == 85.0
    assert parse_qualitative_score(None, is_risk=True, default=50.0) == 50.0
    assert parse_qualitative_score("invalid value", is_risk=False, default=45.0) == 45.0
    print("- Numeric, percentage, and fallback tests passed.")

    print("\nALL PARSING TESTS PASSED!")

if __name__ == "__main__":
    run_tests()
