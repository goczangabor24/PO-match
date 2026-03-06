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
        window = path_text[max(0, path_text.find(fc)-80):path_text.find(fc)+80]

        m = re.search(r"\b(0[1-9]|1[0-2])\b", window)
        if m:
            month = m.group(1)
        else:
            m = re.search(
                r"\b(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\b",
                window,
                re.IGNORECASE
            )
            if m:
                month = month_names[m.group(1).lower()]

    if po:
        m = re.search(rf"{po}\s+([a-z]+)", path_text)
        if m:
            suffix = m.group(1)

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


def render_interactive_table(df):

    fc_cols = [c for c in df.columns if c != "PO Number"]

    totals = {
        c: int(df[c].fillna("").str.startswith("DN available").sum())
        for c in fc_cols
    }

    payload = json.dumps({
        "columns": list(df.columns),
        "rows": df.fillna("").to_dict("records"),
        "totals": totals
    })

    html = f"""
    <html>
    <style>
    table {{border-collapse:collapse;width:100%;}}
    th,td {{border:1px solid #ddd;padding:6px;}}
    th {{background:#f2f2f2}}
    td.green {{background:#c6efce;color:#006100;font-weight:bold}}
    </style>

    <table id="t"></table>

    <script>
    const data = {payload};
    const t = document.getElementById("t");

    function build(){{
        let h = "<tr>";
        data.columns.forEach(c=>h+=`<th>${{c}}<br><span id='count_${{c}}'></span></th>`);
        h+="</tr>";
        t.innerHTML=h;

        data.rows.forEach(r=>{{
            let row="<tr>";
            data.columns.forEach(c=>{{
                let v=r[c]||"";
                if(v.startsWith("DN available"))
                    row+=`<td onclick="toggle(this,'${{c}}')" data-fc="${{c}}">${{v}}</td>`;
                else
                    row+=`<td>${{v}}</td>`;
            }});
            row+="</tr>";
            t.innerHTML+=row;
        }});

        update();
    }}

    function toggle(cell,fc){{
        cell.classList.toggle("green");
        update();
    }}

    function update(){{
        Object.keys(data.totals).forEach(fc=>{{
            let total=data.totals[fc];
            let done=document.querySelectorAll(`td.green[data-fc='${{fc}}']`).length;
            document.getElementById("count_"+fc).innerText=`${{done}}/${{total}} completed`;
        }});
    }}

    build();
    </script>
    </html>
    """

    components.html(html, height=600, scrolling=True)


st.set_page_config(page_title="PO Collector", page_icon="📋", layout="wide")

st.title("PO Collector")

col1, col2 = st.columns(2)

with col1:
    insider_input = st.text_area("INSIDER POs", height=200)

with col2:
    vim_input = st.text_area("VIM POs", height=200)

paths_input = st.text_area("File paths", height=200)

insider_df, vim_df = build_result_dataframes(
    insider_input,
    vim_input,
    paths_input
)

st.header("Result")

if not insider_df.empty:
    st.subheader("INSIDER")
    render_interactive_table(insider_df)

if not vim_df.empty:
    st.subheader("VIM")
    render_interactive_table(vim_df)


# SAFE CSV EXPORT
if not insider_df.empty or not vim_df.empty:

    csv = ""

    if not insider_df.empty:
        csv += "INSIDER\n" + insider_df.to_csv(index=False) + "\n"

    if not vim_df.empty:
        csv += "VIM\n" + vim_df.to_csv(index=False)

    st.download_button(
        "Download CSV",
        csv.encode(),
        "po_dn_status.csv",
        "text/csv"
    )
