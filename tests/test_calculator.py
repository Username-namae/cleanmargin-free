import unittest

from calculator import CompanySettings, JobConditions, calculate_quote, simulate_offer

class CalculatorTests(unittest.TestCase):
    def test_basic_quote(self):
        services = [{
            "quantity": 1,
            "standard_person_hours": 2.0,
            "material_cost_yen": 500,
            "public_price_reference_yen": 10000,
        }]
        settings = CompanySettings(
            labor_cost_per_person_hour=2000,
            vehicle_cost_per_km=30,
            monthly_fixed_cost=30000,
            monthly_job_count=30,
            minimum_margin=0.15,
            target_margin=0.30,
            minimum_charge=0,
        )
        conditions = JobConditions(
            occupancy_multiplier=1.0,
            dirt_multiplier=1.0,
            pet_additional_person_hours=0,
            crew_size=1,
            one_way_minutes=30,
            one_way_km=10,
        )
        result = calculate_quote(services, settings, conditions)
        self.assertAlmostEqual(result["total_person_hours"], 3.0)
        self.assertAlmostEqual(result["labor_cost"], 6000)
        self.assertAlmostEqual(result["vehicle_cost"], 600)
        self.assertAlmostEqual(result["fixed_cost_allocation"], 1000)
        self.assertEqual(result["target_price"] % 100, 0)
        self.assertGreaterEqual(result["target_price"], result["total_cost"])

    def test_discount_judgement(self):
        sim = simulate_offer(20000, 15000, 0.20)
        self.assertTrue(sim["acceptable"])
        sim2 = simulate_offer(16000, 15000, 0.20)
        self.assertFalse(sim2["acceptable"])

if __name__ == "__main__":
    unittest.main()
