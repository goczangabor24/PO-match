import html
import json
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# --- helper functions ---
def normalize_po_list(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_fc_po_month(path_text: str) -> tuple[str, str, str]:
    fc_match = re.search(r"\b([A-Z]{3})\b", path_text)
    fc = fc_match.group(1) if fc_match else ""

    po_match = re.search(r"\b(1\d{6}|4\d{9})\b", path_text)
    po = po_match.group(1) if po_match else ""

    month = ""
    month_names = {
        "january": "01", "jan": "01",
        "february": "02", "feb": "02",
        "march": "03", "mar": "03",
        "april": "04", "apr": "04",
        "may": "05",
        "june": "06", "jun": "06",
        "july": "07", "jul": "07",
        "august": "08", "aug": "08",
        "september": "09", "sep": "09", "sept": "09",
        "october": "10", "oct": "10",
        "november": "11", "nov": "11",
        "december": "12", "dec": "12",
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
                r"\b(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|sep|october|oct|november|nov|december|dec)\b",
                window_text,
                flags=re.IGNORECASE,
            )
            if month_name_match:
                month = month_names[month_name_match.group(1).lower()]
                break

    return fc, po, month


def build_result_dataframe(insider_text: str, vim_text: str, paths_text: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    insider_pos = normalize_po_list(insider_text)
    vim_pos = normalize_po_list(vim_text)

    insider_rows: list[dict[str, str]] = [{"PO Number": po} for po in insider_pos]
    vim_rows: list[dict[str, str]] = [{"PO Number": po} for po in vim_pos]

    path_lines = [line.strip().strip('"') for line in paths_text.splitlines() if line.strip()]
    fc_po_map: dict[str, dict[str, str]] = {}

    for path_line in path_lines:
        fc, po, month = extract_fc_po_month(path_line)
        if not fc or not po:
            continue
        if fc not in fc_po_map:
            fc_po_map[fc] = {}
        fc_po_map[fc][po] = month

    sorted_fcs = sorted(fc_po_map.keys())

    for row in insider_rows:
        po = row["PO Number"]
        for fc in sorted_fcs:
            if po in fc_po_map[fc]:
                month = fc_po_map[fc][po]
                row[fc] = f"DN available in {month}" if month else "DN available"
            else:
                row[fc] = ""

    for row in vim_rows:
        po = row["PO Number"]
        for fc in sorted_fcs:
            if po in fc_po_map[fc]:
                month = fc_po_map[fc][po]
                row[fc] = f"DN available in {month}" if month else "DN available"
            else:
                row[fc] = ""

    columns = ["PO Number"] + sorted_fcs
    insider_df = pd.DataFrame(insider_rows, columns=columns)
    vim_df = pd.DataFrame(vim_rows, columns=columns)

    # keep only rows where there is at least one DN match
    fc_columns = sorted_fcs
    if fc_columns:
        insider_df = insider_df[insider_df[fc_columns].replace("", pd.NA).notna().any(axis=1)]
        vim_df = vim_df[vim_df[fc_columns].replace("", pd.NA).notna().any(axis=1)]

    return insider_df, vim_df


def render_interactive_dn_table(df: pd.DataFrame) -> None:
    fc_columns = [col for col in df.columns if col != "PO Number"]
    match_totals = {
        col: int(df[col].fillna("").astype(str).str.startswith("DN available").sum())
        for col in fc_columns
    }

    payload_json = json.dumps({
        "columns": list(df.columns),
        "rows": df.fillna("").astype(str).to_dict(orient="records"),
        "match_totals": match_totals,
    })

    html_block = """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <style>
        body {
          font-family: Arial, sans-serif;
          margin: 0;
          padding: 0.5rem;
          background: white;
        }
        .hint {
          margin: 0 0 12px 0;
          font-size: 14px;
          color: #333;
        }
        .table-wrap {
          overflow-x: auto;
          border: 1px solid #d9d9d9;
          border-radius: 10px;
        }
        table {
          border-collapse: collapse;
          width: 100%;
          min-width: 900px;
        }
        th, td {
          border: 1px solid #e6e6e6;
          padding: 8px 10px;
          text-align: left;
          white-space: nowrap;
          font-size: 14px;
        }
        th {
          background: #f7f7f7;
          font-weight: 700;
          position: sticky;
          top: 0;
          z-index: 1;
          vertical-align: top;
        }
        .header-main {
          display: block;
          font-weight: 700;
        }
        .header-sub {
          display: block;
          margin-top: 2px;
          font-size: 12px;
          color: #666;
          font-weight: 400;
        }
        td.dn-cell {
          cursor: pointer;
          user-select: none;
        }
        td.dn-cell.selected {
          outline: 2px solid #1f77ff;
          outline-offset: -2px;
          background: #eaf2ff;
        }
        td.dn-cell.green {
          background: #c6efce;
          color: #006100;
          font-weight: 700;
        }
      </style>
    </head>
    <body>
      <div class="hint"><strong>How to use:</strong> click one <em>DN available</em> cell to select it, then press <strong>Ctrl + Enter</strong> to toggle green.</div>
      <div class="table-wrap">
        <table id="dnTable"></table>
      </div>

      <script>
        const payload = __PAYLOAD_JSON__;
        const table = document.getElementById('dnTable');

        function escapeHtml(value) {
          return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#039;');
        }

        function updateHeaderCounts() {
          payload.columns.forEach(col => {
            const header = document.querySelector(`th[data-col="${col}"] .header-sub`);
            if (!header) return;
            const total = Number(payload.match_totals[col] || 0);
            const completed = document.querySelectorAll(`td.dn-cell.green[data-fc="${col}"]`).length;
            header.textContent = `${completed}/${total} completed`;
          });
        }

        function buildTable() {
          const thead = document.createElement('thead');
          const headRow = document.createElement('tr');
          payload.columns.forEach(col => {
            const th = document.createElement('th');
            th.dataset.col = col;

            const main = document.createElement('span');
            main.className = 'header-main';
            main.innerHTML = escapeHtml(col);
            th.appendChild(main);

            if (col !== 'PO Number') {
              const sub = document.createElement('span');
              sub.className = 'header-sub';
              const total = Number(payload.match_totals[col] || 0);
              sub.textContent = `0/${total} completed`;
              th.appendChild(sub);
            }

            headRow.appendChild(th);
          });
          thead.appendChild(headRow);
          table.appendChild(thead);

          const tbody = document.createElement('tbody');
          payload.rows.forEach((row) => {
            const tr = document.createElement('tr');
            payload.columns.forEach((col) => {
              const td = document.createElement('td');
              const value = String(row[col] ?? '');
              td.innerHTML = escapeHtml(value);

              if (value.startsWith('DN available')) {
                td.classList.add('dn-cell');
                td.dataset.fc = col;
                td.addEventListener('click', () => {
                  document.querySelectorAll('td.dn-cell.selected').forEach(c => c.classList.remove('selected'));
                  td.classList.add('selected');
                });
              }

              tr.appendChild(td);
            });
            tbody.appendChild(tr);
          });
          table.appendChild(tbody);
          updateHeaderCounts();
        }

        document.addEventListener('keydown', (event) => {
          if (event.ctrlKey && event.key === 'Enter') {
            event.preventDefault();
            const cell = document.querySelector('td.dn-cell.selected');
            if (!cell) return;
            cell.classList.toggle('green');
            updateHeaderCounts();
          }
        });

        buildTable();
      </script>
    </body>
    </html>
    """

    html_block = html_block.replace("__PAYLOAD_JSON__", payload_json)
    components.html(html_block, height=600, scrolling=True)


st.set_page_config(page_title="PO Collector", page_icon="📋", layout="wide")

st.title("PO Collector")

col1, col2 = st.columns(2)

with col1:
    st.markdown("## **INSIDER**")
    insider_input = st.text_area(
        "Paste Insider PO numbers (one per line)",
        height=220,
        placeholder="1700001\n1700002\n4000000001",
    )

with col2:
    st.markdown("## **VIM**")
    vim_input = st.text_area(
        "Paste VIM PO numbers (one per line)",
        height=220,
        placeholder="1701001\n1701002\n4000000002",
    )

st.markdown("## **FILE PATHS**")
paths_input = st.text_area(
    "Paste file paths (one per line)",
    height=220,
    placeholder='"C:\\Users\\zp3539\\Zooplus SE\\ORY - collaboration site - ORY 2026\\ORY 03\\PO 1670529 GEORGIAN.pdf"',
)

insider_df, vim_df = build_result_dataframe(insider_input, vim_input, paths_input)

st.markdown("## **INTERACTIVE RESULT**")
if insider_df.empty and vim_df.empty:
    st.info("Paste PO numbers and/or file paths to see the matched result automatically.")
else:
    if not insider_df.empty:
        st.markdown("### **INSIDER**")
        render_interactive_dn_table(insider_df)

    if not vim_df.empty:
        st.markdown("### **VIM**")
        render_interactive_dn_table(vim_df)

    csv_parts = []
if not insider_df.empty:
    csv_parts.append("INSIDER\n" + insider_df.to_csv(index=False))
if not vim_df.empty:
    csv_parts.append("VIM\n" + vim_df.to_csv(index=False))

csv_data = ("\n".join(csv_parts)).encode("utf-8")

st.download_button(
    label="Download CSV",
    data=csv_data,
    file_name="po_dn_status_by_fc.csv",
    mime="text/csv",
)

