from engine.check_rules import main

def test_check_rules_passes():
    assert main() == 0
