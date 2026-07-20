from __future__ import annotations

import unittest

from src.fetchers.congress import CongressionalFiling
from src.fetchers.congress import parse_house_option_description
from src.fetchers.congress import parse_house_ptr_text


def _filing() -> CongressionalFiling:
    return CongressionalFiling(
        source="house_financial_disclosure",
        chamber="House",
        prefix="Hon.",
        last_name="Pelosi",
        first_name="Nancy",
        suffix="",
        filing_type="Periodic Transaction Report",
        state_district="CA11",
        year="2026",
        filing_date="2026-06-23",
        document_id="20034836",
        source_url="https://example.test/20034836.pdf",
    )


class HousePtrParserTest(unittest.TestCase):
    def test_parses_option_transactions_and_contract_details(self) -> None:
        text = """
        ID Owner Asset Transaction
        Type Date Notification Date Amount
        SP Intel Corporation - Common Stock
        (INTC) [OP]
        P 05/29/202605/29/2026$1,000,001 -
        $5,000,000
        Filing Status: New
        Description: Purchased 200 call options with a strike price of $50 and an expiration date of 3/19/27.
        SP Uber Technologies, Inc. Common
        Stock (UBER) [OP]
        P 05/29/2026 05/29/2026 $500,001 - $1,000,000
        Description: Purchased 200 call options with a strike price of $50 and an expiration date of 3/19/27.
        """

        transactions = parse_house_ptr_text(_filing(), text)

        self.assertEqual(len(transactions), 2)
        self.assertEqual(transactions[0].ticker, "INTC")
        self.assertEqual(transactions[0].asset_type, "期权")
        self.assertEqual(transactions[0].transaction_date, "2026-05-29")
        self.assertEqual(transactions[0].option_quantity, 200)
        self.assertEqual(transactions[0].option_type, "Call")
        self.assertEqual(transactions[0].option_strike, "$50")
        self.assertEqual(transactions[0].option_expiration, "2027-03-19")
        self.assertEqual(
            transactions[0].option_contract,
            "200 contracts | Call | strike $50 | expires 2027-03-19",
        )
        self.assertEqual(transactions[0].estimated_value_usd, 3_000_000.5)

    def test_parses_common_stock_transaction_variant(self) -> None:
        text = """
        JT Example Corp Class A
        (EXM) [ST]
        S 6/1/2026 6/12/2026 $15,001 - $50,000
        Description: Sold shares.
        """

        transactions = parse_house_ptr_text(_filing(), text)

        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].owner, "JT")
        self.assertEqual(transactions[0].ticker, "EXM")
        self.assertEqual(transactions[0].asset_type, "股票")
        self.assertEqual(transactions[0].action_text, "卖出")
        self.assertEqual(transactions[0].transaction_date, "2026-06-01")
        self.assertEqual(transactions[0].notification_date, "2026-06-12")
        self.assertEqual(transactions[0].description, "Sold shares.")
        self.assertEqual(transactions[0].option_contract, "")

    def test_structures_option_description(self) -> None:
        details = parse_house_option_description(
            "Purchased 1,250 put options with a strike price of $12.50 and an expiration date of 01/16/2028."
        )

        self.assertEqual(details["quantity"], "1250")
        self.assertEqual(details["option_type"], "Put")
        self.assertEqual(details["strike"], "$12.50")
        self.assertEqual(details["expiration"], "2028-01-16")


if __name__ == "__main__":
    unittest.main()
