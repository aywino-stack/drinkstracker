import streamlit as st
import pandas as pd
import random

FILE = "RatingsList.xlsx"

df = pd.read_excel(FILE, sheet_name="Ratings")

st.title("🍻 Drink Ratings App")

# Remove blank rows
df = df[df["Alcohol:"].notna()]

# Convert columns to numeric (fixes sorting error)
df["Average"] = pd.to_numeric(df["Average"], errors="coerce")
df["$ Per SD"] = pd.to_numeric(df["$ Per SD"], errors="coerce")
df["Standard Drinks"] = pd.to_numeric(df["Standard Drinks"], errors="coerce")

# -----------------------
# TOP RATED DRINKS
# -----------------------

st.header("🏆 Top Rated Drinks")

top = df.sort_values("Average", ascending=False)

st.dataframe(
    top[["Alcohol:", "Type", "Average", "Price (Ex. Delivery/Discount)", "Standard Drinks"]]
)

# -----------------------
# BEST VALUE DRINKS
# -----------------------

st.header("💰 Best Value ($ Per Standard Drink)")

value = df.sort_values("$ Per SD", ascending=True)

st.dataframe(
    value[["Alcohol:", "$ Per SD", "Standard Drinks", "Average"]]
)

# -----------------------
# RANDOM DRINK PICKER
# -----------------------

st.header("🎲 Random Drink Picker")

if st.button("Pick Tonight's Drink"):
    drink = df.sample(1)["Alcohol:"].iloc[0]
    st.success(f"Tonight's drink: {drink}")

# -----------------------
# DRINK SUGGESTION
# -----------------------

st.header("🍺 Suggest a New Drink")

drink_types = df["Type"].dropna().unique()

selected_type = st.selectbox("Drink Type", drink_types)

existing = df[df["Type"] == selected_type]["Alcohol:"]

suggestions = [
    "Asahi Super Dry",
    "Peroni",
    "Balter XPA",
    "Stone & Wood",
    "Little Creatures Pale Ale",
    "Guinness"
]

new_options = [d for d in suggestions if d not in existing.values]

if len(new_options) > 0:
    st.success(random.choice(new_options))
else:
    st.write("All suggestions already tried!")