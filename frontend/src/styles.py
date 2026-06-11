def inject_global_styles(st):
    st.markdown(
        """
        <style>
        :root {
            --primary: #2563eb;
            --primary-soft: #eff4ff;
            --text: #172033;
            --muted: #64748b;
            --border: rgba(15, 23, 42, 0.12);
            --danger: #dc2626;
            --success: #059669;
            --warning: #b7791f;
        }

        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
            max-width: 1500px;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%);
        }

        .dashboard-hero {
            padding: 1.25rem 1.5rem;
            border: 1px solid var(--border);
            border-radius: 24px;
            background:
                radial-gradient(circle at top left, rgba(37, 99, 235, 0.14), transparent 28rem),
                #ffffff;
            box-shadow: 0 18px 50px rgba(15, 23, 42, 0.06);
            margin-bottom: 1rem;
        }

        .dashboard-hero h1 {
            font-size: clamp(2rem, 5vw, 4rem);
            line-height: 0.95;
            letter-spacing: -0.06em;
            margin: 0;
            color: var(--text);
        }

        .dashboard-hero p {
            color: var(--muted);
            font-size: 1.02rem;
            line-height: 1.6;
            margin: 0.85rem 0 0;
            max-width: 900px;
        }

        .eyebrow {
            color: var(--primary);
            text-transform: uppercase;
            font-size: 0.75rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            margin-bottom: 0.35rem;
        }

        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.45rem 0.7rem;
            border-radius: 999px;
            border: 1px solid var(--border);
            background: #ffffff;
            font-weight: 800;
            font-size: 0.82rem;
            color: var(--muted);
        }

        .status-dot {
            width: 0.55rem;
            height: 0.55rem;
            border-radius: 999px;
            background: currentColor;
            display: inline-block;
        }

        .status-good { color: var(--success); }
        .status-warn { color: var(--warning); }
        .status-bad { color: var(--danger); }

        .info-card {
            border: 1px solid var(--border);
            border-radius: 20px;
            background: #ffffff;
            padding: 1rem;
            box-shadow: 0 18px 50px rgba(15, 23, 42, 0.05);
            height: 100%;
        }

        .info-card h3 {
            margin: 0 0 0.45rem;
            color: var(--text);
            letter-spacing: -0.035em;
        }

        .info-card p {
            margin: 0;
            color: var(--muted);
            line-height: 1.5;
        }

        .formula-pill {
            display: inline-flex;
            padding: 0.5rem 0.7rem;
            margin-top: 0.85rem;
            border-radius: 12px;
            background: var(--primary-soft);
            color: var(--primary);
            font-weight: 900;
            font-size: 0.88rem;
        }

        .notice-box {
            border: 1px solid rgba(183, 121, 31, 0.25);
            background: #fffbeb;
            padding: 0.85rem 1rem;
            border-radius: 16px;
            color: #7c4a03;
            line-height: 1.5;
            margin-bottom: 1rem;
        }

        .danger-box {
            border: 1px solid rgba(220, 38, 38, 0.25);
            background: #fff5f5;
            padding: 0.85rem 1rem;
            border-radius: 16px;
            color: #991b1b;
            line-height: 1.5;
            margin-bottom: 1rem;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--border);
            padding: 1rem;
            border-radius: 18px;
            box-shadow: 0 16px 45px rgba(15, 23, 42, 0.05);
        }

        div[data-testid="stMetricLabel"] {
            color: var(--muted);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 999px;
            padding: 0.5rem 1rem;
            background: #ffffff;
            border: 1px solid var(--border);
        }

        .stTabs [aria-selected="true"] {
            background: var(--primary-soft);
            color: var(--primary);
            font-weight: 800;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_pill(label: str, status: str = "warn") -> str:
    status_class = {
        "good": "status-good",
        "warn": "status-warn",
        "bad": "status-bad",
    }.get(status, "status-warn")

    return (
        f'<span class="status-pill {status_class}">'
        f'<span class="status-dot"></span>'
        f'{label}'
        f'</span>'
    )
