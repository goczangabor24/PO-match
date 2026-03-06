import json
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


def normalize_po_list(text: str):
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_fc_po_month(path_text: str):
    fc_match = re.search(r"\b([A-Z]{3})\b", path_text)
    fc = fc_match.group(1) if fc_match else ""

    po_match = re.search(r"\b(1\d{6}|4\d{9})\b", path_text)
    po = po_match.group(1) if po_match else ""

    month = ""
    suffix = ""

    month_names = {
        "jan": "01", "january": "01",
        "feb": "02", "february": "02",
        "mar": "03", "march": "03",
        "apr": "04", "april": "04",
        "may": "05",
        "jun": "06", "june": "06",
        "jul": "07", "july": "07",
        "aug": "08", "august": "08",
        "sep": "09", "sept": "09", "september": "09",
        "oct": "10", "october": "10",
        "nov": "11", "november": "11",
        "dec": "12", "december": "12",
    }

    if fc:
        fc_positions = [m.start() for m in re.finditer(rf"\b{re.escape(fc)}\b", path_text)]

        for fc_pos in fc_positions or [path_text.find(fc)]:
            if fc_pos < 0:
                continue

            window_start = max(0, fc_pos - 80)
            window_end = min(len(path_text), fc_pos + 80)
            window_text = path_text[window_start:window_end]

            month_num_match = re.search(r"\b(0[1-9]|1[0-2])\b", window_text)
            if month_num_match:
                month = month_num_match.group(1)
                break

            month_name_match = re.search(
                r"\b(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\b",
                window_text,
                flags=re.IGNORECASE,
            )
            if month_name_match:
                month = month_names[month_name_match.group(1).lower()]
                break

    if po:
        suffix_match = re.search(rf"\b{re.escape(po)}\b\s+([a-z]+)\b", path_text)
        if suffix_match:
            suffix = suffix_match.group(1)

    return fc, po, month, suffix


def build_result_dataframes(insider_text, vim_text, paths_text):
    insider_pos = normalize_po_list(insider_text)
    vim_pos = normalize_po_list(vim_text)

    insider_rows = [{"PO Number": po} for po in insider_pos]
    vim_rows = [{"PO Number": po} for po in vim_pos]

    fc_po_map = {}

    for line in paths_text.splitlines():
        line = line.strip().strip('"')
        if not line:
            continue

        fc, po, month, suffix = extract_fc_po_month(line)

        if not fc or not po:
            continue

        fc_po_map.setdefault(fc, {})
        fc_po_map[fc][po] = (month, suffix)

    fcs = sorted(fc_po_map.keys())

    for rows in [insider_rows, vim_rows]:
        for row in rows:
            po = row["PO Number"]

            for fc in fcs:
                if po in fc_po_map[fc]:
                    month, suffix = fc_po_map[fc][po]

                    text = f"DN available in {month}" if month else "DN available"
                    if suffix:
                        text += f" ({suffix})"

                    row[fc] = text
                else:
                    row[fc] = ""

    cols = ["PO Number"] + fcs

    insider_df = pd.DataFrame(insider_rows, columns=cols)
    vim_df = pd.DataFrame(vim_rows, columns=cols)

    if fcs:
        insider_df = insider_df[insider_df[fcs].replace("", pd.NA).notna().any(axis=1)]
        vim_df = vim_df[vim_df[fcs].replace("", pd.NA).notna().any(axis=1)]

    return insider_df, vim_df


def render_interactive_table(df, table_name):
    fc_cols = [c for c in df.columns if c != "PO Number"]

    totals = {
        c: int(df[c].fillna("").astype(str).str.startswith("DN available").sum())
        for c in fc_cols
    }

    payload = json.dumps({
        "columns": list(df.columns),
        "rows": df.fillna("").to_dict("records"),
        "totals": totals,
        "table_name": table_name,
    })

    html = f"""
    <html>
    <head>
    <style>
        html, body {{
            margin: 0;
            padding: 0;
            font-family: Arial, Helvetica, sans-serif;
            font-size: 14px;
        }}

        .wrapper {{
            font-family: Arial, Helvetica, sans-serif;
            font-size: 14px;
            color: #222;
        }}

        table {{
            border-collapse: collapse;
            width: 100%;
            font-family: Arial, Helvetica, sans-serif;
            font-size: 14px;
        }}

        th, td {{
            border: 1px solid #ddd;
            padding: 6px 8px;
            text-align: left;
            vertical-align: top;
            font-family: Arial, Helvetica, sans-serif;
            font-size: 14px;
            font-weight: 400;
        }}

        th {{
            background: #f2f2f2;
            font-weight: 700;
        }}

        .sub {{
            display: block;
            margin-top: 2px;
            color: #666;
            font-size: 12px;
            font-weight: 400;
        }}

        td.green {{
            background: #c6efce;
            color: #006100;
            font-weight: 700;
        }}
    </style>
    </head>
    <body>
        <div class="wrapper">
            <table id="t"></table>
        </div>

        <script>
            const data = {payload};
            const t = document.getElementById("t");

            function build() {{
                let h = "<tr>";
                data.columns.forEach(c => {{
                    if (c === "PO Number") {{
                        h += `<th>${{c}}</th>`;
                    }} else {{
                        h += `<th>${{c}}<span class="sub" id="count_${{c}}"></span></th>`;
                    }}
                }});
                h += "</tr>";
                t.innerHTML = h;

                data.rows.forEach(r => {{
                    let row = "<tr>";
                    data.columns.forEach(c => {{
                        let v = r[c] || "";

                        if (v.startsWith("DN available")) {{
                            row += `<td class="green" data-fc="${{c}}">${{v}}</td>`;
                        }} else {{
                            row += `<td>${{v}}</td>`;
                        }}
                    }});
                    row += "</tr>";
                    t.innerHTML += row;
                }});

                update();
            }}

            function update() {{
                Object.keys(data.totals).forEach(fc => {{
                    let total = data.totals[fc];
                    let done = document.querySelectorAll(`td.green[data-fc='${{fc}}']`).length;
                    const el = document.getElementById("count_" + fc);
                    if (el) {{
                        el.innerText = `${{done}}/${{total}} completed`;
                    }}
                }});
            }}

            build();
        </script>
    </body>
    </html>
    """

    components.html(html, height=600, scrolling=True)


st.set_page_config(page_title="PO Match", page_icon="📋", layout="wide")

st.title("PO Match")

col1, col2 = st.columns(2)

with col1:
    insider_input = st.text_area(
        "INSIDER POs",
        height=200,
        placeholder="1700001\n1700002\n4000000001"
    )

with col2:
    vim_input = st.text_area(
        "VIM POs",
        height=200,
        placeholder="1701001\n1701002\n4000000002"
    )

paths_input = st.text_area(
    "File paths",
    height=220,
    placeholder='"C:\\Users\\zp3539\\Zooplus SE\\ORY - collaboration site - ORY 2026\\ORY 03\\PO 1670529 dmg.pdf"'
)

insider_df, vim_df = build_result_dataframes(insider_input, vim_input, paths_input)

st.header("Result")

if insider_df.empty and vim_df.empty:
    st.info("Paste POs and file paths to see matches.")
else:
    if not insider_df.empty:
        st.subheader("INSIDER")
        render_interactive_table(insider_df, "INSIDER")

    if not vim_df.empty:
        st.subheader("VIM")
        render_interactive_table(vim_df, "VIM")

    csv_parts = []

    if not insider_df.empty:
        csv_parts.append("INSIDER\n" + insider_df.to_csv(index=False))

    if not vim_df.empty:
        csv_parts.append("VIM\n" + vim_df.to_csv(index=False))

    csv = "\n".join(csv_parts)

    st.download_button(
        "Download CSV",
        csv.encode("utf-8"),
        "po_dn_status.csv",
        "text/csv"
    )
