import streamlit as st
import pandas as pd
import requests

FILE = "RatingsList.xlsx"

raw_df = pd.read_excel(FILE, sheet_name="Ratings")

st.title("🍻 Drink Ratings App")

# -----------------------
# NEXT PURCHASER
# -----------------------

NAME_MAP = {
    "TW": "Trev",
    "SK": "Scott",
    "MC": "MC",
    "MJ": "MJ",
    "BG": "Brando",
    "KG": "Karl",
    "AO": "Amer",
    "EM": "EM",
    "CG": "CG",
    "BH": "BH",
    "RA": "RA",
    "PIT/BS/AF": "PIT/BS/AF",
    "b": "b",
}

hiatus_entries = raw_df[raw_df["Purchaser"].str.contains("On Hiatus", na=False)]["Purchaser"].tolist()
on_hiatus = set()
for entry in hiatus_entries:
    on_hiatus.add(entry.replace("(On Hiatus)", "").strip())

purchase_df = raw_df[
    raw_df["Alcohol:"].notna() &
    raw_df["Purchaser"].notna() &
    ~raw_df["Purchaser"].str.contains("Hiatus", na=False)
].copy()
purchase_sequence = purchase_df["Purchaser"].str.strip().tolist()

def get_rotation_order(sequence):
    unique_purchasers = []
    seen = set()
    for p in reversed(sequence):
        if p not in seen:
            unique_purchasers.insert(0, p)
            seen.add(p)
    return unique_purchasers

def get_next_buyer(rotation, last_buyer, skip):
    if not rotation or last_buyer not in rotation:
        return rotation[0] if rotation else None
    idx = rotation.index(last_buyer)
    for i in range(1, len(rotation) + 1):
        candidate = rotation[(idx + i) % len(rotation)]
        if candidate not in skip:
            return candidate
    return None

rotation = get_rotation_order(purchase_sequence)
last_buyer = purchase_sequence[-1] if purchase_sequence else None
next_buyer = get_next_buyer(rotation, last_buyer, on_hiatus)

st.header("🛒 Who's Buying Next?")

col1, col2 = st.columns(2)
with col1:
    st.metric("Last Purchaser", NAME_MAP.get(last_buyer, last_buyer) if last_buyer else "—")
with col2:
    st.metric("🎯 Next Up", NAME_MAP.get(next_buyer, next_buyer) if next_buyer else "Unknown")

if on_hiatus:
    hiatus_names = [NAME_MAP.get(p, p) for p in on_hiatus]
    st.info(f"🏖️ Currently on hiatus: **{', '.join(hiatus_names)}**")

all_active = [p for p in rotation if p not in on_hiatus]
active_names = [NAME_MAP.get(p, p) for p in all_active]
on_leave_this_week = st.multiselect(
    "Mark someone as away this week (temporarily skipped):",
    options=active_names,
    default=[]
)
if on_leave_this_week:
    reverse_map = {v: k for k, v in NAME_MAP.items()}
    temp_skip = on_hiatus | set(reverse_map.get(n, n) for n in on_leave_this_week)
    adjusted_next = get_next_buyer(rotation, last_buyer, temp_skip)
    adjusted_name = NAME_MAP.get(adjusted_next, adjusted_next) if adjusted_next else "Unknown"
    st.success(f"✅ With {', '.join(on_leave_this_week)} away — next buyer is: **{adjusted_name}**")

st.divider()

# -----------------------
# MAIN TABLE
# -----------------------

st.header("📋 All Drinks")

rater_cols = ["Mike", "Amer", "Trev", "Scott", "Karl", "Aywin", "Brando", "Bradman", "Vanyel", "MJ", "RA"]

cutoff = raw_df[raw_df["Alcohol:"].str.contains("Appleton", na=False)].index[0]
df = raw_df.loc[:cutoff].copy()

df = df[
    df["Alcohol:"].notna() &
    ~df["Purchaser"].str.contains("Hiatus", na=False)
].copy()

for col in ["Average", "$ Per SD", "$ Per Score", "Standard Drinks", "Price (Ex. Delivery/Discount)"] + rater_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

display_cols = ["Alcohol:", "Type", "Purchaser", "Price (Ex. Delivery/Discount)", "Standard Drinks"] + \
               [c for c in rater_cols if c in df.columns] + \
               ["Average", "$ Per SD", "Notes"]
display_cols = [c for c in display_cols if c in df.columns]

display_df = df[display_cols].copy()
display_df = display_df.rename(columns={"Price (Ex. Delivery/Discount)": "Price", "Alcohol:": "Drink"})

sort_options = {
    "Entry Order (default)": None,
    "Average Rating (high → low)": ("Average", False),
    "Best Value ($ per SD)": ("$ Per SD", True),
    "Price (low → high)": ("Price", True),
    "Name (A → Z)": ("Drink", True),
}

sort_choice = st.selectbox("Sort by:", list(sort_options.keys()))

if sort_options[sort_choice]:
    col_name, ascending = sort_options[sort_choice]
    display_df = display_df.sort_values(col_name, ascending=ascending, na_position="last")

st.dataframe(
    display_df.reset_index(drop=True),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Average": st.column_config.NumberColumn("Average", format="%.2f"),
        "$ Per SD": st.column_config.NumberColumn("$ Per SD", format="$%.2f"),
        "Price": st.column_config.NumberColumn("Price", format="$%.0f"),
    }
)

st.divider()

# -----------------------
# AI DRINK SUGGESTIONS
# -----------------------

st.header("🤖 AI Drink Suggestions")
st.write("Based on your group's ratings, get AI-powered suggestions for drinks you haven't tried yet.")

drink_types = sorted(display_df["Type"].dropna().unique().tolist())
suggestion_type = st.selectbox(
    "Filter suggestions by type (optional):",
    ["Any"] + drink_types
)

budget = st.slider("Max price per bottle ($)", min_value=20, max_value=200, value=80, step=5)

if st.button("🍾 Get Suggestions"):
    already_tried = display_df["Drink"].dropna().astype(str).tolist()

    # Build a taste profile from top-rated drinks
    top_drinks = display_df.dropna(subset=["Average"]).sort_values("Average", ascending=False).head(10)
    top_list = "\n".join(
        f"- {row['Drink']} ({row['Type']}, avg rating: {row['Average']:.1f})"
        for _, row in top_drinks.iterrows()
    )

    type_filter = f"Focus only on {suggestion_type} type drinks." if suggestion_type != "Any" else ""

    prompt = f"""You are a drinks expert helping a group of mates in Perth, Australia find new drinks to try at their weekly tasting session.

Here are their top-rated drinks so far:
{top_list}

Here is the full list of drinks they've already tried (do NOT suggest any of these):
{chr(10).join('- ' + d for d in already_tried)}

Based on their taste profile, suggest 5 drinks they would enjoy that are NOT on their tried list.
{type_filter}
Keep suggestions within a budget of ${budget} AUD per bottle.
Prefer drinks that are reasonably available in Australia.

For each suggestion provide:
- Name of the drink
- Type (e.g. Scotch Whisky, Bourbon, Rum, etc.)
- Why they'd like it based on their taste profile
- Approximate price in AUD
- Where to buy it in Australia (e.g. Dan Murphy's, BWS, specialist liquor stores)

Format each suggestion clearly with a heading for the drink name."""

    with st.spinner("Consulting the drinks oracle..."):
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": st.secrets["ANTHROPIC_API_KEY"],
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            data = response.json()
            if "error" in data:
                st.error(f"API error: {data['error'].get('message', data['error'])}")
            else:
                full_text = "\n".join(
                    block["text"] for block in data.get("content", [])
                    if block.get("type") == "text"
                )
                if full_text:
                    st.markdown(full_text)
                else:
                    st.error(f"No text returned. Raw response: {data}")
        except Exception as e:
            st.error(f"Error getting suggestions: {e}")
