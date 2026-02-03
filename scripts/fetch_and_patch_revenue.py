import pandas as pd
import numpy as np
import yfinance as yf
import time

REPORTS_PATH = "data/annual_reports_rows (1).csv"
COMPANIES_PATH = "data/companies_rows (1).csv"
OUTPUT_PATH = "data/annual_reports_patched.csv"


def fetch_and_patch():
    print("Loading CSVs...")
    try:
        df_reports = pd.read_csv(REPORTS_PATH)
        df_companies = pd.read_csv(COMPANIES_PATH)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print(
            "Make sure both 'annual_reports_rows (1).csv' and 'companies_rows (1).csv' are in 'data/' folder."
        )
        return

    # Merge to get Ticker
    # Assuming company_id (in reports) maps to id (in companies)
    print("Merging with Companies to get Tickers...")
    # Rename id in companies to match foreign key if needed
    if "id" in df_companies.columns:
        df_companies = df_companies.rename(columns={"id": "company_id_temp"})

    # We join on company_id
    # Check column names
    # reports: company_id
    # companies: company_id_temp (was id)

    # Create a lookup dictionary for efficient mapping
    comp_map = dict(zip(df_companies["company_id_temp"], df_companies["ticker"]))

    df_reports["ticker"] = df_reports["company_id"].map(comp_map)

    # Filter rows with missing revenue
    missing_mask = df_reports["revenue"].isnull()
    missing_count = missing_mask.sum()
    print(f"Found {missing_count} rows with missing revenue.")

    if missing_count == 0:
        print("No missing revenue to patch!")
        return

    # Iterate and fetch
    # We group by Ticker to minimize API calls
    df_missing = df_reports[missing_mask].copy()
    unique_tickers = df_missing["ticker"].unique()

    print(f"Fetching data for {len(unique_tickers)} unique tickers from yfinance...")

    updated_rows = 0

    for ticker in unique_tickers:
        if not isinstance(ticker, str):
            continue

        print(f"\nProcessing {ticker}...")
        try:
            yt = yf.Ticker(ticker)
            financials = yt.income_stmt
            if financials is None or financials.empty:
                print(f"  No financials found for {ticker}")
                continue

            # Financials columns are dates (e.g. 2023-09-30)
            # We need to match with fiscal_year in our DB

            # Helper to get year from column name (Timestamp)
            financials.columns = [col.year for col in financials.columns]

            # Get missing rows for this ticker
            ticker_rows = df_missing[df_missing["ticker"] == ticker]

            for idx, row in ticker_rows.iterrows():
                year = row["fiscal_year"]

                # Check if we have this year in yfinance data
                if year in financials.columns:
                    try:
                        # Try 'Total Revenue' or 'Operating Revenue'
                        rev = None
                        if "Total Revenue" in financials.index:
                            rev = financials.loc["Total Revenue", year]
                        elif "Operating Revenue" in financials.index:
                            rev = financials.loc["Operating Revenue", year]

                        if rev is not None and not pd.isna(rev):
                            df_reports.at[idx, "revenue"] = rev
                            print(f"  [PATCHED] Year {year}: {rev}")
                            updated_rows += 1
                        else:
                            print(
                                f"  [MISSING] Year {year}: Key found but value is NaN"
                            )
                    except Exception as e:
                        print(f"  Error extracting year {year}: {e}")
                else:
                    print(
                        f"  [SKIP] Year {year} not in yfinance columns {financials.columns.tolist()}"
                    )

        except Exception as e:
            print(f"  API Error for {ticker}: {e}")

        time.sleep(0.5)  # respectful delay

    print(f"\nTotal rows patched: {updated_rows}")

    # Save
    # Remove the temporary ticker column before saving
    if "ticker" in df_reports.columns:
        df_reports = df_reports.drop(columns=["ticker"])

    df_reports.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved patched data to {OUTPUT_PATH}")


if __name__ == "__main__":
    fetch_and_patch()
