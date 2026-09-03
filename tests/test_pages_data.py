import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from scripts import research_feeds as feeds
from scripts import build_pages_data as builder

NOW = datetime(2026, 9, 4, 12, tzinfo=timezone.utc)


class ResearchFeedTests(unittest.TestCase):
    def test_market_change_uses_previous_exchange_session(self):
        current = datetime(2026, 9, 4, 14, tzinfo=timezone.utc)
        yesterday = int(datetime(2026, 9, 3, 20, tzinfo=timezone.utc).timestamp())
        response = {'meta': {'regularMarketPrice': 102, 'regularMarketTime': current.timestamp(), 'exchangeTimezoneName': 'America/New_York'}, 'timestamp': [yesterday, current.timestamp()], 'indicators': {'quote': [{'close': [100, 102]}]}}
        with patch.object(feeds, 'yahoo_result', return_value=response):
            result = feeds.market_metric('DX-Y.NYB', current)
        self.assertEqual(result['change'], 2)

    def test_calendar_rejects_ambiguous_floating_times(self):
        text = 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20260904T083000\nSUMMARY:Employment Situation\nEND:VEVENT\nEND:VCALENDAR'
        self.assertEqual(feeds.calendar_parse(text, NOW), [])

    def test_h15_separates_nominal_from_real_yield(self):
        text = '<table><tr><th>Instruments</th><th>2026 Sep 1</th><th>2026 Sep 2</th></tr><tr><td>Nominal</td></tr><tr><td>10-year</td><td>4.7</td><td>4.8</td></tr><tr><td>Inflation indexed</td></tr><tr><td>10-year</td><td>2.4</td><td>2.5</td></tr></table>'
        result = feeds.h15_parse(text, NOW)
        self.assertEqual(result['nominal10y']['value'], 4.8)
        self.assertEqual(result['real10y']['value'], 2.5)

    def test_fred_uses_dated_finite_observations(self):
        row = feeds.fred_parse('observation_date,DFII10\n2026-09-01,2.0\n2026-09-02,.\n2026-09-03,2.1\n2027-01-01,99\n', 'DFII10', NOW)
        self.assertEqual(row['value'], 2.1)
        self.assertEqual(row['change'], 0.1)
        self.assertEqual(row['observed_at'], '2026-09-03T00:00:00Z')

    def test_cpi_requires_same_month_last_year(self):
        text = 'observation_date,CPIAUCSL\n2025-07-01,100\n2026-07-01,103\n'
        self.assertEqual(feeds.fred_parse(text, 'CPIAUCSL', NOW)['value'], 3)
        with self.assertRaises(ValueError):
            feeds.fred_parse('observation_date,CPIAUCSL\n2026-07-01,103\n', 'CPIAUCSL', NOW)

    def test_cftc_contract_and_category_alignment(self):
        text = ('Disaggregated Commitments of Traders-All Futures Combined Positions as of August 25, 2026\n'
                'GOLD - COMMODITY EXCHANGE INC.\nCFTC Code #088691 Open Interest is 1,000\n'
                ': Positions :\n: 1 2 3 4 5 600 200 8 9 10 11 :\n')
        result = feeds.cftc_parse(text, NOW)
        self.assertEqual((result['long'], result['short'], result['net']), (600, 200, 400))
        with self.assertRaises(ValueError):
            feeds.cftc_parse(text.replace('088691', '088695'), NOW)

    def test_rss_rejects_future_and_non_official_urls(self):
        text = '<rss><channel><item><title>Official test</title><link>https://www.federalreserve.gov/example</link><pubDate>Thu, 3 Sep 2026 12:30:00 GMT</pubDate></item><item><title>Bad</title><link>https://example.com</link><pubDate>Thu, 3 Sep 2026 12:30:00 GMT</pubDate></item></channel></rss>'
        self.assertEqual(len(feeds.news_parse(text, NOW)), 1)

    def test_calendar_applies_dst(self):
        text = 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART;TZID=America/New_York:20260904T083000\nSUMMARY:Employment Situation\nEND:VEVENT\nEND:VCALENDAR'
        self.assertEqual(feeds.calendar_parse(text, NOW)[0]['scheduled_at'], '2026-09-04T12:30:00Z')

    def test_unavailable_sources_are_explicit(self):
        with patch.object(feeds, 'fetch_text', side_effect=OSError('offline')):
            result = feeds.collect(NOW)
        self.assertEqual(result['positioning']['status'], 'unavailable')
        self.assertNotIn('value', result['real10y'])

    def test_rsi_flat_and_one_way(self):
        self.assertEqual(builder._rsi([5]*30), 50)
        self.assertEqual(builder._rsi(list(range(1, 40))), 100)
        self.assertEqual(builder._rsi(list(range(40, 0, -1))), 0)

    def test_h4_omits_incomplete_groups(self):
        rows = [builder.Candle(i*3600, 10, 11, 9, 10) for i in range(7)]
        self.assertEqual(len(builder._h4(rows)), 1)

    def test_missing_quote_and_liquidity_veto(self):
        result = builder.risk_gate({}, NOW)
        self.assertEqual(result['verdict'], 'VETO')
        self.assertIn('calendar_gap', result['reasons'])

    def test_builder_survives_outages_without_stale_report(self):
        with patch.object(builder, 'fetch_live_quote', side_effect=OSError()), patch.object(builder, '_history', side_effect=OSError()), patch.object(builder, 'collect', return_value={}):
            result = builder.build_payload()
        self.assertIsNone(result['quote'])
        self.assertIsNone(result['liquidity'])
        self.assertEqual(result['schema_version'], 2)
        self.assertEqual(result['decision'], 'WAIT')
        self.assertFalse(result['trade_execution'])
