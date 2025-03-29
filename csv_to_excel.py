import pandas as pd

# Load CSV file
csv_file = "/home/syedkhizer/Documents/WebScraping/instant_relief/for pakistan/physio_chiro_pakistan_fb_groups_20250330_022323.csv"  # Replace with your CSV file path
df = pd.read_csv(csv_file)

# Convert to Excel
excel_file = "/home/syedkhizer/Documents/WebScraping/instant_relief/for pakistan/physio_chiro_pakistan_fb_groups.xlsx"  # Name of the Excel file
df.to_excel(excel_file, index=False, engine="openpyxl")

print(f"CSV file converted to Excel: {excel_file}")
