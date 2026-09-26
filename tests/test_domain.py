import unittest
from server.domain import statistics, validate_shots, report


def shot(ident='1', outcome='made', reviewed=True, release=2):
    return dict(id=ident,start=release-1,release=release,end=release+1,outcome=outcome,reviewed=reviewed,note='')


class TrainingRules(unittest.TestCase):
    def test_pending_and_uncertain_are_not_misses(self):
        stats=statistics([shot(),shot('2','missed'),shot('3','made',False),shot('4','unknown')])
        self.assertEqual(stats,dict(attempts=2,made=1,pending=2,percentage=50.0))

    def test_no_confirmed_data_has_no_rate(self):
        self.assertIsNone(statistics([shot(reviewed=False)])['percentage'])

    def test_rejects_duplicates_nonfinite_and_out_of_range(self):
        invalid=[[shot(),shot()], [shot(release=float('nan'))], [shot(release=10)], [dict(shot(),reviewed='yes')]]
        for shots in invalid:
            with self.subTest(shots=shots), self.assertRaises(ValueError): validate_shots(shots,10)

    def test_chronological_results(self):
        values=validate_shots([shot('later',release=8),shot('earlier',release=2)],10)
        self.assertEqual([s['id'] for s in values],['earlier','later'])

    def test_report_does_not_invent_mechanical_defects(self):
        text=report(dict(title='训练',date='2026-09-26',shots=[shot(outcome='missed')]))
        self.assertIn('仅凭命中率不能判断动作缺陷',text)
        self.assertIn('0.0%',text)
        self.assertIn('120 次',text)


if __name__=='__main__': unittest.main()
