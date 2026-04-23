import os
import re
import anthropic
import pandas as pd
import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────
FILE_PATH = "RatingsList.xlsx"
RATER_COLS = ["Mike", "Amer", "Trev", "Scott", "Karl", "Aywin",
              "Brando", "Bradman", "Vanyel", "MJ", "RA"]
COL_MAP = {
    "Alcohol:": "Drink Name",
    "Price (Ex. Delivery/Discount)": "Price",
    "Purchaser": "Buyer",
}

st.set_page_config(page_title="Drinks Tracker", page_icon="🍻", layout="wide")
st.title("🍻 Drinks Tracker")

# ── Load & clean ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_excel(path, header=0)
    # Keep only rows that look like real drinks
    df = df[df["Alcohol:"].notna() & df["Type"].notna()
            & (df["Alcohol:"].astype(str).str.len() > 2)].copy()
    df = df.rename(columns=COL_MAP)
    df = df.drop(columns=["Unnamed: 0", "Unnamed: 6", "Unnamed: 21"], errors="ignore")
    for col in ["Price", "Standard Drinks", "Average", "$ Per Score", "$ Per SD"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.reset_index(drop=True)


if "df" not in st.session_state:
    st.session_state.df = load_data(FILE_PATH)

df = st.session_state.df

# ── Sidebar navigation ────────────────────────────────────────────────────────
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["📋 Drinks List", "📅 Timeline", "🔮 Next Buyer", "💰 Value Ranking",
     "📊 Ratings", "🤖 AI Suggestions"],
)
st.sidebar.divider()

# ── Helper: buyer rotation ────────────────────────────────────────────────────
def get_rotation(df):
    if "Buyer" not in df.columns:
        return [], None
    buyers = df["Buyer"].dropna()
    people = buyers.unique().tolist()
    if not people:
        return [], None
    last = buyers.iloc[-1]
    idx = people.index(last) if last in people else -1
    nxt = people[(idx + 1) % len(people)]
    return people, nxt


def buy_counts(df):
    if "Buyer" not in df.columns:
        return pd.Series(dtype=int)
    return df["Buyer"].dropna().value_counts()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Drinks List
# ══════════════════════════════════════════════════════════════════════════════
if page == "📋 Drinks List":
    st.subheader("Drinks List (Editable)")
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    if st.button("💾 Save Changes", type="primary"):
        # Rename back to original Excel column names before saving
        save_df = edited.rename(columns={v: k for k, v in COL_MAP.items()})
        save_df.to_excel(FILE_PATH, index=False)
        st.session_state.df = edited
        load_data.clear()
        st.success("Saved successfully!")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total drinks", len(df))
    c2.metric("Unique types", df["Type"].nunique() if "Type" in df.columns else 0)
    avg = df["Average"].mean() if "Average" in df.columns else 0
    c3.metric("Avg rating", f"{avg:.2f}" if avg else "—")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Timeline
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📅 Timeline":
    st.subheader("Drink Purchase Timeline")

    if "Buyer" in df.columns and "Drink Name" in df.columns:
        bought = df[df["Buyer"].notna()].copy()

        cols = [c for c in ["Buyer", "Drink Name", "Type", "Standard Drinks", "Price", "Average"]
                if c in bought.columns]
        st.dataframe(bought[cols], use_container_width=True)

        st.divider()
        st.subheader("Buys per person")
        counts = buy_counts(df).reset_index()
        counts.columns = ["Buyer", "Times Bought"]
        st.bar_chart(counts.set_index("Buyer"))
    else:
        st.info("No Buyer or Drink Name column found.")

    st.subheader("🆕 Drinks Not Yet Bought")
    if "Buyer" in df.columns:
        not_bought = df[df["Buyer"].isna()]
        if not not_bought.empty:
            st.dataframe(not_bought, use_container_width=True)
        else:
            st.success("All drinks have been bought!")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Next Buyer
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔮 Next Buyer":
    st.subheader("🔮 Who Should Buy Next?")

    people, nxt = get_rotation(df)

    if nxt:
        st.success(f"Next round: **{nxt}** 🍺")

        # Away toggle
        st.divider()
        st.markdown("**Mark who's away this week** — they'll be skipped in the rotation.")
        away = []
        cols = st.columns(4)
        for i, person in enumerate(people):
            with cols[i % 4]:
                if st.checkbox(person, key=f"away_{person}"):
                    away.append(person)

        available = [p for p in people if p not in away]
        if available:
            counts = buy_counts(df)
            # Find person with fewest buys among available
            fewest = min(available, key=lambda p: counts.get(p, 0))
            st.info(f"Skipping away people → **{fewest}** has the fewest buys and is available.")
        else:
            st.warning("Everyone is marked away!")

        st.divider()
        st.subheader("Full rotation queue")
        counts = buy_counts(df)
        rotation_df = pd.DataFrame({
            "Person": people,
            "Times Bought": [counts.get(p, 0) for p in people],
        }).sort_values("Times Bought")
        rotation_df["Status"] = rotation_df["Person"].apply(
            lambda p: "🏖 Away" if p in away else ("⬅ Next up" if p == fewest else "In queue")
        )
        st.dataframe(rotation_df, use_container_width=True, hide_index=True)
    else:
        st.info("No buyer data found yet.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Value Ranking
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💰 Value Ranking":
    st.subheader("💰 Best Value Drinks")

    if "$ Per SD" in df.columns:
        value = df.copy()
        value["$ Per SD"] = pd.to_numeric(value["$ Per SD"], errors="coerce")
        value = value.dropna(subset=["$ Per SD"]).sort_values("$ Per SD")

        cols = [c for c in ["Drink Name", "Type", "Price", "Standard Drinks",
                             "Average", "$ Per Score", "$ Per SD"] if c in value.columns]

        # Budget filter
        max_price = float(df["Price"].max()) if "Price" in df.columns else 200.0
        budget = st.slider("Max price ($)", 0, int(max_price) + 10, int(max_price) + 10)
        if "Price" in value.columns:
            value = value[value["Price"] <= budget]

        st.dataframe(value[cols], use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Avg $ per standard drink by type")
        if "Type" in value.columns:
            by_type = (value.groupby("Type")["$ Per SD"]
                       .mean().sort_values().reset_index())
            by_type.columns = ["Type", "Avg $ per SD"]
            st.bar_chart(by_type.set_index("Type"))
    else:
        st.info("No '$ Per SD' column found.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Ratings
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Ratings":
    st.subheader("📊 Ratings Breakdown")

    if "Average" in df.columns and "Drink Name" in df.columns:
        col1, col2 = st.columns(2)
        with col1:
            type_filter = st.multiselect(
                "Filter by type",
                options=sorted(df["Type"].dropna().astype(str).unique()) if "Type" in df.columns else [],
            )
        with col2:
            min_rating = st.slider("Min average rating", 0.0, 10.0, 0.0, 0.5)

        filtered = df[df["Average"].notna()].copy()
        if type_filter:
            filtered = filtered[filtered["Type"].isin(type_filter)]
        filtered = filtered[filtered["Average"] >= min_rating]
        filtered = filtered.sort_values("Average", ascending=False)

        display_cols = [c for c in ["Drink Name", "Type", "Price", "Average",
                                    "$ Per Score", "Buyer", "Notes"] if c in filtered.columns]
        st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Average rating by type")
        if "Type" in filtered.columns:
            by_type = (filtered.groupby("Type")["Average"]
                       .mean().sort_values(ascending=False).reset_index())
            by_type.columns = ["Type", "Avg Rating"]
            st.bar_chart(by_type.set_index("Type"))

        st.divider()
        st.subheader("Individual rater scores")
        rater_cols = [c for c in RATER_COLS if c in df.columns]
        if rater_cols and "Drink Name" in df.columns:
            rater_data = df[["Drink Name"] + rater_cols].copy()
            for c in rater_cols:
                rater_data[c] = pd.to_numeric(rater_data[c], errors="coerce")
            means = rater_data[rater_cols].mean().sort_values(ascending=False).reset_index()
            means.columns = ["Rater", "Avg Score Given"]
            st.dataframe(means, use_container_width=True, hide_index=True)
    else:
        st.info("No Average rating column found.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: AI Suggestions
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🤖 AI Suggestions":
    st.subheader("🤖 AI Drink Suggestions")
    st.caption(
        "Claude searches Dan Murphy's and other Australian retailers in real time, "
        "then recommends bottles your group hasn't tried yet."
    )

    model = st.selectbox(
        "Model",
        ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
    )

    col1, col2 = st.columns(2)
    with col1:
        budget = st.slider("Max price per bottle ($)", 30, 250, 100)
    with col2:
        num_suggestions = st.slider("Number of suggestions", 3, 10, 6)

    type_pref = st.multiselect(
        "Preferred spirit types (leave empty for any)",
        options=sorted(df["Type"].dropna().astype(str).unique()) if "Type" in df.columns else [],
    )

    retailers = st.multiselect(
        "Search these retailers",
        ["danmurphys.com.au", "bws.com.au", "liquorland.com.au", "thewhiskyclub.com.au"],
        default=["danmurphys.com.au", "bws.com.au"],
    )

    if st.button("✨ Get suggestions", type="primary"):
        top = (df[df["Average"].notna()]
               .sort_values("Average", ascending=False)
               .head(10))
        tried = df["Drink Name"].dropna().tolist() if "Drink Name" in df.columns else []

        top_summary = (
            top[["Drink Name", "Type", "Price", "Average"]].to_string(index=False)
            if not top.empty else "No rated drinks yet."
        )

        retailer_list = ", ".join(retailers) if retailers else "danmurphys.com.au"

        system = """You are a knowledgeable spirits sommelier helping an Australian drinks \
group discover great new bottles. You have access to a web_search tool — use it to find \
real, current products on Australian retail websites before making recommendations.

When searching:
- Search each retailer site directly (e.g. "site:danmurphys.com.au bourbon under $100")
- Verify the product is actually listed and in stock if possible
- Include the direct product URL from the retailer in your response

Format each recommendation as:
**[Drink Name]** — [Type]
- Price: ~$XX (at [Retailer])
- Link: [URL]
- Why you'd love it: [1-2 sentences tied to the group's taste history]
"""

        user_msg = (
            f"Our drinks group has rated these highly:\n\n{top_summary}\n\n"
            f"Already tried ({len(tried)} drinks): {', '.join(tried[:40])}.\n\n"
            f"Budget: under ${budget} per bottle.\n"
            + (f"Preferred spirit types: {', '.join(type_pref)}.\n" if type_pref else "")
            + f"Search these Australian retailers: {retailer_list}.\n\n"
            f"Find {num_suggestions} bottles we haven't tried. "
            "Search the retailer websites first, then recommend only products you can "
            "confirm are listed there. Include the product URL for each."
        )

        with st.spinner("Claude is searching retailers and finding recommendations…"):
            try:
                client = anthropic.Anthropic()
                output_box = st.empty()
                status_box = st.empty()
                full_text = ""
                messages = [{"role": "user", "content": user_msg}]

                # Agentic loop — keep going until no more tool use
                while True:
                    response = client.messages.create(
                        model=model,
                        max_tokens=4000,
                        system=system,
                        tools=[{"type": "web_search_20250305", "name": "web_search"}],
                        messages=messages,
                    )

                    # Show any text blocks as they come in
                    for block in response.content:
                        if block.type == "text":
                            full_text += block.text
                            output_box.markdown(full_text)
                        elif block.type == "tool_use" and block.name == "web_search":
                            query = block.input.get("query", "")
                            status_box.info(f"🔍 Searching: _{query}_")

                    # Append assistant turn
                    messages.append({"role": "assistant", "content": response.content})

                    # If Claude wants to use tools, feed results back and continue
                    if response.stop_reason == "tool_use":
                        tool_results = []
                        for block in response.content:
                            if block.type == "tool_use":
                                # web_search results are returned automatically by the API
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": "Search completed.",
                                })
                        messages.append({"role": "user", "content": tool_results})
                    else:
                        break

                status_box.empty()
                output_box.markdown(full_text)

            except anthropic.AuthenticationError:
                st.error("Set your ANTHROPIC_API_KEY environment variable to use AI suggestions.")
            except Exception as e:
                st.error(f"API error: {e}")
