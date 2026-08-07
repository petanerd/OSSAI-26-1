from scripts.run_open_cqa_judge import required_requests


def test_two_trials_and_two_orders_need_four_calls_per_pair() -> None:
    assert required_requests(5) == 20
    assert required_requests(30) == 120
