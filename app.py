import streamlit as st
import pandas as pd
import os
import json
import toml
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import altair as alt
from datetime import datetime
from login import login # Assuming this is your custom login module

# --- 3. PAGE CONFIGURATION & INITIAL SETUP ---
st.set_page_config(
    page_title="📊 Job Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)


# --- 1. LOGIN & ACCESS CONTROL ---
# Stop the app if login fails
username = login()
if not username:
    st.warning("Please log in to see the dashboard.")
    st.stop()

# Place this code near the top of your app, after the login check
if st.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# --- 2. CACHE DATA ---
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data():
    """Fetch data from Google Sheets once and cache it."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Load JSON credentials from secrets
        creds_dict = st.secrets["google_sheets_credentials"]
        
        # The creds_dict is already a dictionary-like object,
        # so pass it directly to the credential creation function.
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

        client = gspread.authorize(creds)
        sheet = client.open("Copy of Job & Reciept Full Data").worksheet("Combined Data")
        data = sheet.get_all_values()

        header = data[2]
        df_data = data[3:]
        
        # --- NEW CODE: Clean and deduplicate headers ---
        cleaned_header = []
        seen_headers = {}
        for h in header:
            h_stripped = h.strip()  # Trim leading/trailing whitespace
            # Handle empty headers
            if h_stripped == '':
                h_stripped = f'Unnamed_Col_{len(cleaned_header)}'
            # Handle duplicates by adding a suffix
            if h_stripped in seen_headers:
                seen_headers[h_stripped] += 1
                cleaned_header.append(f'{h_stripped}_{seen_headers[h_stripped]}')
            else:
                seen_headers[h_stripped] = 0
                cleaned_header.append(h_stripped)
        
        df = pd.DataFrame(df_data, columns=cleaned_header).dropna(how='all')
        
        return df
    except Exception as e:
        st.error(f"Failed to load data from Google Sheets: {e}")
        return pd.DataFrame()

st.title(f"📊 Job Dashboard")
st.write(f"Welcome, {username}")

# Load data and apply initial user filter
df_full = load_data()

# Handle case where data loading failed
if df_full.empty:
    st.info("No data available to display.")
    st.stop()

# --- 1. Rename columns for consistency and easier use ---
# Assuming column renaming is handled implicitly or not strictly required for this fix.
# If you had explicit renames, they would go here.

# --- 2. Clean and convert data types on the renamed columns ---
df_full["Email"] = df_full["Email"].astype(str).str.strip().str.lower()
df_full["Month Year"] = pd.to_datetime(df_full["Month Year"], errors="coerce")

# Convert key columns to numeric. Use .get() to avoid errors if a column is missing.
df_full["Total Sales"] = pd.to_numeric(df_full.get("CHARGE TO CLIENT/ TOTAL SALES", 0), errors='coerce')
df_full["Gross Profit"] = pd.to_numeric(df_full.get("GROSS PROFIT", 0), errors='coerce')
df_full["VAT"] = pd.to_numeric(df_full.get("VAT", 0), errors='coerce')
df_full["Gross Sales"] = pd.to_numeric(df_full.get("Gross Sales", 0), errors='coerce')
if "% GROSS PROFIT" in df_full.columns:
    df_full["% GROSS PROFIT"] = pd.to_numeric(
        df_full["% GROSS PROFIT"].str.strip().str.replace(',', ''), # Clean any commas or spaces
        errors='coerce'
    )
else:
    # Handle the case where the column is missing
    df_full["% GROSS PROFIT"] = 0
df_full["FCL Expense"] = pd.to_numeric(df_full.get("FCL EXPENSE", 0), errors='coerce')
df_full["Shortage"] = pd.to_numeric(df_full.get("SHORTAGE", 0), errors='coerce')

# Clean other text columns
df_full["Job Type"] = df_full["JOB TYPE"].fillna("Unknown").str.strip()
df_full["Job Status"] = df_full["JOB STATUS"].fillna("Unknown").str.strip().str.lower()
df_full["Profitability"] = df_full["THRESHOLD PROFITABILITY"].fillna("Unknown").str.strip().str.lower()

# --- 3. Apply the initial user filter ---
df_user = df_full[df_full["Email"] == username].copy()

if df_user.empty:
    st.info("No data found for the current user.")
    st.stop()

# --- 5. SIDEBAR FILTERS ---
st.sidebar.header("Filters")
df_user["YearMonth"] = df_user["Month Year"].dt.to_period("M")
month_year_options = sorted(df_user["YearMonth"].dropna().unique(), reverse=True)
current_period = pd.Period.now("M")

selected_month_year = st.sidebar.selectbox(
    "Select Month & Year",
    options=month_year_options,
    index=month_year_options.index(current_period) if current_period in month_year_options else 0,
    format_func=lambda x: x.strftime("%B %Y")
)

allowed_profitability = ["loss", "underquoted", "profitable"]
selected_profitability = st.sidebar.multiselect(
    "Select Profitability",
    options=allowed_profitability,
    default=allowed_profitability
)

job_type_options = sorted(df_user["Job Type"].dropna().unique())
selected_job_types = st.sidebar.multiselect(
    "Select Job Types",
    options=job_type_options,
    default=job_type_options
)

# --- 6. APPLY ALL FILTERS TO THE USER'S DATA ---
df_filtered = df_user[
    (df_user["YearMonth"] == selected_month_year) &
    (df_user["Job Type"].isin(selected_job_types))
]

if df_filtered.empty:
    st.warning("No data matches the selected filters.")
    st.stop()


st.markdown("""
    <style>
    /* Reduce font size of metric values on smaller screens */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem; /* Default size */
    }
    @media (max-width: 1200px) {
        [data-testid="stMetricValue"] {
            font-size: 1.2rem;
        }
    }
    @media (max-width: 800px) {
        [data-testid="stMetricValue"] {
            font-size: 1rem;
        }
    }
    </style>
""", unsafe_allow_html=True)

# Calculate commission based on monthly Gross Profit
monthly_gross_profit = df_filtered["Gross Profit"].sum()
commission = 0

if monthly_gross_profit > 1000000:
    commission = monthly_gross_profit * 0.065 # 6.5%
elif monthly_gross_profit > 800000:
    commission = monthly_gross_profit * 0.035 # 3.5%



# --- SCORECARDS (KPIs) ---
if "JOB STATUS" in df_filtered.columns:
    df_filtered["JOB STATUS"] = df_filtered["JOB STATUS"].str.strip().str.lower()

    closed_jobs = df_filtered[df_filtered["Job Status"] == "closed"]
    open_jobs = df_filtered[df_filtered["Job Status"] != "closed"]
    closed_count = len(closed_jobs)
    open_count = len(open_jobs)
else:
    st.warning("🚨 'JOB STATUS' column not found in data.")
    closed_count, open_count = 0, 0



total_jobs = len(df_filtered)
total_sales = closed_jobs["Total Sales"].sum()
gross_profit = closed_jobs["Gross Profit"].sum()
vat = closed_jobs["VAT"].sum()
gross_sales = closed_jobs["Gross Sales"].sum()
fcl_expense = closed_jobs["FCL Expense"].sum()
avg_profit_pct = closed_jobs["% GROSS PROFIT"].mean()
gross_profit_per = closed_jobs["Gross Profit"].sum() / closed_jobs["Gross Sales"].sum() * 100 

# KPIs - will wrap to multiple rows if screen size is small
kpi_values = [
    ("Total Sales", f"KES {total_sales:,.0f}"),
    ("FCL Expense", f"KES {fcl_expense:,.0f}"),
    ("Total VAT", f"KES {vat:,.0f}"),
    ("Gross Sales", f"KES {gross_sales:,.2f}"),
    ("Gross Profit", f"KES {gross_profit:,.0f}"),
    ("Total Jobs", total_jobs),
    ("Completed Jobs", closed_count),
    ("Incomplete Jobs", open_count),
    ("💰 Commission", f"KES {commission:,.0f}"),
    ("📉 Gross Profit %", f"{gross_profit_per:.2f}%")
]

# Create flexible layout that wraps on small screens
cols = st.columns(3)  # Start with 3 per row (adjustable)
for i, (label, value) in enumerate(kpi_values):
    cols[i % 3].metric(label, value)


# Add Altair charts in a new row
st.write("Profitability Breakdown")
# --- Responsive styling for chart titles ---
st.markdown("""
    <style>
    /* Adjust plotly chart titles & axis labels */
    .js-plotly-plot .plotly .gtitle {
        font-size: 1.2rem;
    }
    @media (max-width: 1200px) {
        .js-plotly-plot .plotly .gtitle {
            font-size: 1rem;
        }
    }
    @media (max-width: 800px) {
        .js-plotly-plot .plotly .gtitle {
            font-size: 0.9rem;
        }
    }
    </style>
""", unsafe_allow_html=True)

# --- 8. CHARTS ---
st.header("Charts & Analysis")
sales_by_type = df_filtered.groupby("Job Type")["Total Sales"].sum().reset_index()

# --- 2. Number of Completed Jobs by Job Type ---
gross_sales_by_type = df_filtered.groupby("Job Type")["Gross Sales"].sum().reset_index()

# Prepare data for the new "Jobs by Job Type" chart
jobs_by_type_count = df_filtered["Job Type"].value_counts().reset_index()
jobs_by_type_count.columns = ['Job Type', 'Number of Jobs']

orange_color = [
    "#FFA500"]
# Custom orange/brown shades
orange_brown_palette = [
    "#FFA500",  # Orange
    "#FF8C00",  # Dark Orange
    "#E07B39",  # Burnt Orange
    "#D2691E",  # Chocolate
    "#8B4513",  # Saddle Brown
    "#A0522D",  # Sienna
]

# List of Plotly charts (updated to include the new bar chart)
charts_plotly = [
    ("Total Sales by Job Type", 
     px.bar(sales_by_type, x="Job Type", y="Total Sales", text_auto=True, color_discrete_sequence=orange_color)),
    
    ("Completed Jobs by Job Type", 
     px.bar(gross_sales_by_type, x="Job Type", y="Gross Sales", text_auto=True, color_discrete_sequence=orange_color)),
    
    # NEW CHART: Jobs by Job Type (Bar Chart)
    ("Number of Jobs by Job Type",
     px.bar(jobs_by_type_count, x="Job Type", y="Number of Jobs", text_auto=True, color_discrete_sequence=orange_color))
]


# Display responsive layout for Plotly charts
cols = st.columns(3)  # 3 per row by default
for i, (title, fig) in enumerate(charts_plotly):
    fig.update_layout(title=dict(text=title, x=0.5))
    cols[i % 3].plotly_chart(fig, use_container_width=True)


# --- Calculate % of MOS for each category ---
mos_categories = ["LABOUR", "MATERIALS", "TRANSPORT", "TECHNICAL", "OTHERS"]

# Convert to numeric
for col in mos_categories + ["TOTAL MOS COSTS"]:
    if col in df_filtered.columns:
        df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce')
    else:
        st.warning(f"Column '{col}' not found in data.")
        df_filtered[col] = 0

# Group by Job Type and sum
df_mos = df_filtered.groupby("Job Type")[mos_categories + ["TOTAL MOS COSTS"]].sum().reset_index()

# Calculate percentages
for col in mos_categories:
    # Ensure TOTAL MOS COSTS is not zero to avoid division by zero
    # Replace division by zero results with 0 or NaN, then handle with dropna
    df_mos[f"{col} %"] = df_mos.apply(
        lambda row: (row[col] / row["TOTAL MOS COSTS"]) * 100 if row["TOTAL MOS COSTS"] != 0 else 0,
        axis=1
    )


# Melt for easier plotting in Altair
df_mos_melt = df_mos.melt(id_vars="Job Type", 
                          value_vars=[f"{c} %" for c in mos_categories],
                          var_name="Category", 
                          value_name="Percentage")

# Clean category names
df_mos_melt["Category"] = df_mos_melt["Category"].str.replace(" %", "", regex=False)

# Drop rows where Percentage is NaN or inf, which can occur from division by zero,
# although the apply function above should minimize this.
df_mos_melt = df_mos_melt.replace([float('inf'), -float('inf')], pd.NA).dropna(subset=['Percentage'])


# --- MOS Category % Chart ---
st.write("### Job Type Breakdown by MOS Categories (%)")

# Modified Altair chart for grouped bars - removed 'band' from XOffset
mos_chart = alt.Chart(df_mos_melt).mark_bar().encode(
    x=alt.X("Job Type:N", title="Job Type"),
    y=alt.Y("Percentage:Q", title="Percentage of Total MOS", axis=alt.Axis(format=".1f", tickCount=5)),
    color=alt.Color("Category:N", title="Category"),
    # Use xOffset to create grouped bars
    xOffset=alt.XOffset("Category:N"), 
    tooltip=["Job Type", "Category", alt.Tooltip("Percentage:Q", format=".2f")]
).properties(
    title="MOS Category Share by Job Type (Grouped Bar Chart)",
    height=400
)

# Add text labels to the MOS chart bars
mos_chart_text = mos_chart.mark_text(
    align='center',
    baseline='bottom',
    dy=-5 # Position text slightly above the bar
).encode(
    text=alt.Text("Percentage:Q", format=".1f"), # Display percentage with one decimal place
    color=alt.value("black"), # Text color
    x=alt.X("Job Type:N"), # Ensure x and xOffset are consistent
    xOffset=alt.XOffset("Category:N"),
    y=alt.Y("Percentage:Q") # Position text on the y-axis
)

st.altair_chart(mos_chart + mos_chart_text, use_container_width=True)

text_offset = 15
st.write("### Profitability Breakdown")
df_filtered["Profitability"] = df_filtered["Profitability"].str.strip().str.lower()

# Define the order mapping for profitability
profitability_order_map = {'profitable': 0, 'under quoted': 1, 'loss': 2}
# Apply this order to create a new numerical column for sorting
df_filtered['profitability_order'] = df_filtered['Profitability'].map(profitability_order_map)

# Define the color scale with explicit domain and range
color_scale = alt.Scale(
    domain=['profitable', 'under quoted', 'loss'], # Desired order: profitable, underquoted, loss
    range=['green', 'orange', 'red'] # Corresponding colors for the desired order
)

# Create columns for the profitability charts
profitability_cols = st.columns(3)

# --- Jobs by Profitability Chart ---
with profitability_cols[0]:
    # Base chart for bars (STACKED)
    threshold_chart_bars = alt.Chart(df_filtered).mark_bar().encode(
        x=alt.X('Job Type:N', title="Job Type"),
        y=alt.Y('count():Q', title="Number of Jobs"),
        color=alt.Color('Profitability:N', title="Profitability", scale=color_scale), 
        order=alt.Order('profitability_order:Q', sort='descending'), # Use the new numerical order column
        tooltip=['Job Type', 'Profitability', 'count()']
    ).properties(title="Jobs by Profitability")
    
    # Text layer for counts
    threshold_chart_text = threshold_chart_bars.mark_text(
        align='center',
        # Changed baseline to 'middle' and removed dy for stacked bar positioning
    ).encode(
        text=alt.Text('count()', format=',.0f'),  # Formats the number with commas
        color=alt.value('black'),
        x=alt.X('Job Type:N'),
        y=alt.Y('count():Q', stack=True), # Apply stack=True for y-encoding of text
        order=alt.Order('profitability_order:Q', sort='descending') # Use the new numerical order column
    )
    
    st.altair_chart(threshold_chart_bars + threshold_chart_text, use_container_width=True)

# --- Sales Chart ---
with profitability_cols[1]:
    # Base chart for bars (STACKED)
    sales_chart_bars = alt.Chart(df_filtered).mark_bar().encode(
        x=alt.X('Job Type:N', title="Job Type"),
        y=alt.Y('Total Sales:Q', title="Total Sales"),
        color=alt.Color('Profitability:N',
                        title="Profitability", 
                        scale=color_scale), # Color encoding handles sort
        order=alt.Order('profitability_order:Q', sort='descending'), # Use the new numerical order column
        tooltip=['Job Type', 'Profitability', 'sum(Total Sales)']
    ).properties(title="Total Sales by Profitability")
    
    # Text layer for total sales
    sales_chart_text = sales_chart_bars.mark_text(
        align='center',
        # Changed baseline to 'middle' and removed dy for stacked bar positioning
    ).encode(
        text=alt.Text('Total Sales:Q', aggregate='sum', format=',.0f'),
        color=alt.value('black'),
        x=alt.X('Job Type:N'),
        y=alt.Y('Total Sales:Q', aggregate='sum', stack=True), # Apply stack=True for y-encoding of text
        order=alt.Order('profitability_order:Q', sort='descending') # Use the new numerical order column
    )
    st.altair_chart(sales_chart_bars + sales_chart_text, use_container_width=True)


# --- Shortage Chart ---
with profitability_cols[2]:
    # Base chart for bars (STACKED)
    shortage_chart_bars = alt.Chart(df_filtered).mark_bar().encode(
        x=alt.X('Job Type:N', title="Job Type"),
        y=alt.Y('Shortage:Q', title="Shortage"),
        color=alt.Color('Profitability:N',
                        title="Profitability",
                        scale=color_scale), # Color encoding handles sort
        order=alt.Order('profitability_order:Q', sort='ascending'), # Use the new numerical order column
        tooltip=['Job Type', 'Profitability', 'sum(Shortage)']
    ).properties(title="Total Shortage by Profitability")
    
    # Text layer for shortage
    shortage_chart_text = shortage_chart_bars.mark_text(
        align='center',
        # Changed baseline to 'middle' and removed dy for stacked bar positioning
    ).encode(
        text=alt.Text('Shortage:Q', aggregate='sum', format=',.0f'),
        color=alt.value('black'),
        x=alt.X('Job Type:N'),
        y=alt.Y('Shortage:Q', aggregate='sum', stack=True), # Apply stack=True for y-encoding of text
        order=alt.Order('profitability_order:Q', sort='ascending') # Use the new numerical order column
    )
    st.altair_chart(shortage_chart_bars + shortage_chart_text, use_container_width=True)

# Display the filtered DataFrame
st.write(f"📅 Showing data for {selected_month_year.strftime('%B %Y')}")
st.dataframe(df_filtered)
