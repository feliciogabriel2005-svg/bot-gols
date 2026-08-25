class EdgeEngine:
    @staticmethod
    def calculate_edge(prob_estimated: float, prob_implied: float) -> float:
        return prob_estimated - prob_implied

    @staticmethod
    def calculate_ev(prob_estimated: float, odd: float) -> float:
        if odd <= 1.0:
            return -1.0
        return (prob_estimated * odd) - 1.0
