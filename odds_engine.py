class OddsEngine:
    @staticmethod
    def calculate_implied_probability(odd: float) -> float:
        if odd <= 1.0:
            return 0.0
        return 1.0 / odd
