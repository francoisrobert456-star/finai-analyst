import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from datetime import datetime, timezone
import plotly.graph_objects as go

st.set_page_config(page_title="FinAI Analyst", page_icon="📈", layout="wide")

# ---------- Style ----------
st.markdown("""
<style>
.block-container {padding-top: 1.6rem; max-width: 1400px;}
div[data-testid="stMetric"] {background: rgba(100,120,160,.08); border: 1px solid rgba(130,145,170,.22); padding: 14px; border-radius: 12px;}
.small-muted {color: #8b95a7; font-size: .85rem;}
</style>
""", unsafe_allow_html=True)

st.title("📈 FinAI Analyst")
st.caption("Analyse financière • Valorisation explicable • Prototype gratuit")

with st.sidebar:
    st.header("Paramètres")
    isin = st.text_input("ISIN", value="NL0009805522", help="Exemple : NL0009805522 (Nebius)")
    strategy = st.selectbox("Stratégie", [
        "Value Investing",
        "Growth Investing",
        "Dividend Yield Investing",
        "Buy & Hold / Gestion indicielle"
    ])
    horizon = st.selectbox("Horizon", ["1 à 3 ans", "3 à 5 ans", "5 ans et plus"], index=1)
    currency = st.selectbox("Devise d'affichage", ["USD", "EUR", "GBP"], index=0)
    manual_ticker = st.text_input("Ticker Yahoo Finance (facultatif)", value="", help="À renseigner si la recherche ISIN ne trouve pas le bon titre, ex. NBIS.")
    run = st.button("Analyser le titre", type="primary", use_container_width=True)
    st.divider()
    st.caption("Les données de marché proviennent de Yahoo Finance via yfinance. Couverture et délais variables.")

def openfigi_lookup(isin_value):
    """Attempt a public OpenFIGI mapping without credentials; limits may apply."""
    try:
        r = requests.post(
            "https://api.openfigi.com/v3/mapping",
            json=[{"idType": "ID_ISIN", "idValue": isin_value.strip().upper()}],
            timeout=12,
        )
        if r.ok:
            data = r.json()
            if data and isinstance(data, list):
                items = data[0].get("data", []) or []
                # Prefer common-stock / equity-like mappings where possible.
                for item in items:
                    ticker = item.get("ticker")
                    if ticker:
                        return ticker, item, "OpenFIGI"
        return None, None, f"OpenFIGI returned HTTP {r.status_code}"
    except Exception as e:
        return None, None, f"OpenFIGI lookup unavailable: {e}"

def yahoo_search(query):
    try:
        result = yf.Search(query, max_results=10, news_count=0)
        quotes = getattr(result, "quotes", []) or []
        for q in quotes:
            symbol = q.get("symbol")
            if symbol:
                return symbol, q
    except Exception:
        pass
    return None, None

def choose_ticker(isin_value, manual):
    if manual.strip():
        return manual.strip().upper(), {"symbol": manual.strip().upper(), "shortname": "Ticker saisi manuellement"}, "Saisie utilisateur"
    ticker, meta, source = openfigi_lookup(isin_value)
    if ticker:
        return ticker, meta, source
    ticker2, meta2 = yahoo_search(isin_value.strip().upper())
    if ticker2:
        return ticker2, meta2, "Recherche Yahoo Finance par ISIN (à vérifier)"
    return None, None, source

def fmt_num(value, currency_symbol="$", decimals=2):
    try:
        if value is None or pd.isna(value) or np.isinf(value):
            return "Indisponible"
        return f"{currency_symbol}{value:,.{decimals}f}"
    except Exception:
        return "Indisponible"

def fmt_large(value, currency_symbol="$"):
    try:
        if value is None or pd.isna(value):
            return "Indisponible"
        av = abs(float(value))
        if av >= 1e12:
            return f"{currency_symbol}{value/1e12:.2f} T"
        if av >= 1e9:
            return f"{currency_symbol}{value/1e9:.2f} Md"
        if av >= 1e6:
            return f"{currency_symbol}{value/1e6:.2f} M"
        return f"{currency_symbol}{value:,.0f}"
    except Exception:
        return "Indisponible"

def get_fx(from_ccy, to_ccy):
    if from_ccy == to_ccy:
        return 1.0, "Aucune conversion nécessaire"
    pair = f"{from_ccy}{to_ccy}=X"
    try:
        fx = yf.Ticker(pair).history(period="5d", auto_adjust=False)
        if not fx.empty:
            return float(fx["Close"].dropna().iloc[-1]), f"Yahoo Finance ({pair}), dernière observation disponible"
    except Exception:
        pass
    return None, f"Taux de change indisponible pour {from_ccy}/{to_ccy}"

def safe_get(info, key):
    value = info.get(key)
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) and not np.isfinite(value):
            return None
    except Exception:
        pass
    return value

def analyze():
    isin_clean = isin.strip().upper()
    if not isin_clean:
        st.error("Saisis un ISIN.")
        return

    with st.spinner("Recherche de l'identité et récupération des données financières..."):
        ticker_symbol, mapping, mapping_source = choose_ticker(isin_clean, manual_ticker)
        if not ticker_symbol:
            st.error("Impossible de retrouver automatiquement un ticker. Essaie de saisir le ticker dans le champ facultatif de la barre latérale, puis relance l'analyse.")
            st.info(f"Détail de la recherche : {mapping_source}. La correspondance ISIN/ticker doit être vérifiée avant toute décision d'investissement.")
            return

        try:
            stock = yf.Ticker(ticker_symbol)
            info = stock.get_info()
            hist = stock.history(period="1y", auto_adjust=False)
        except Exception as e:
            st.error(f"Impossible de récupérer les données pour {ticker_symbol}: {e}")
            return

    name = safe_get(info, "longName") or safe_get(info, "shortName") or (mapping or {}).get("name") or ticker_symbol
    quote_ccy = safe_get(info, "currency") or "USD"
    price = safe_get(info, "currentPrice")
    if price is None and not hist.empty:
        price = float(hist["Close"].dropna().iloc[-1])
    if price is None:
        st.error("Aucun cours disponible. Vérifie le ticker ou réessaie plus tard.")
        return

    fx, fx_source = get_fx(quote_ccy, currency)
    if fx is None:
        display_price = None
        st.warning(f"Le taux de change vers {currency} n'a pas pu être récupéré. Les valeurs seront affichées dans la devise de cotation {quote_ccy}.")
        display_currency = quote_ccy
        fx = 1.0
    else:
        display_price = float(price) * fx
        display_currency = currency

    symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(display_currency, display_currency + " ")
    market_cap = safe_get(info, "marketCap")
    revenue = safe_get(info, "totalRevenue")
    gross_profit = safe_get(info, "grossProfits")
    ebitda = safe_get(info, "ebitda")
    net_income = safe_get(info, "netIncomeToCommon")
    cash = safe_get(info, "totalCash")
    debt = safe_get(info, "totalDebt")
    shares = safe_get(info, "sharesOutstanding")
    forward_pe = safe_get(info, "forwardPE")
    trailing_pe = safe_get(info, "trailingPE")
    ps = safe_get(info, "priceToSalesTrailing12Months")
    dividend_yield = safe_get(info, "dividendYield")
    beta = safe_get(info, "beta")
    target = safe_get(info, "targetMeanPrice")
    exchange = safe_get(info, "exchange")
    sector = safe_get(info, "sector")
    website = safe_get(info, "website")
    timestamp = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M %Z")

    st.subheader(name)
    st.caption(f"{ticker_symbol} • ISIN saisi : {isin_clean} • Place : {exchange or 'Indisponible'} • Secteur : {sector or 'Indisponible'}")
    st.warning("Vérification requise : le ticker trouvé n'est pas une preuve suffisante que l'ISIN correspond exactement à ce titre. Confirme l'identité auprès de l'émetteur ou d'une source réglementaire.")
    st.caption(f"Correspondance obtenue via : {mapping_source}. Données récupérées le {timestamp}. Cours potentiellement retardé.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Cours ({display_currency})", fmt_num(display_price, symbol) if display_price is not None else fmt_num(price, {"USD":"$","EUR":"€","GBP":"£"}.get(quote_ccy, quote_ccy+" ")))
    c2.metric("Capitalisation", fmt_large(market_cap, "$" if quote_ccy == "USD" else quote_ccy+" "))
    c3.metric("CA 12 mois", fmt_large(revenue, "$" if quote_ccy == "USD" else quote_ccy+" "))
    c4.metric("PER prévisionnel", f"{forward_pe:.1f}×" if forward_pe is not None else "Indisponible")

    st.divider()
    st.subheader("Cours sur 1 an")
    if not hist.empty:
        chart = go.Figure()
        chart.add_trace(go.Scatter(x=hist.index, y=hist["Close"], mode="lines", name=f"Cours ({quote_ccy})"))
        chart.update_layout(height=350, margin=dict(l=10,r=10,t=20,b=10), xaxis_title="", yaxis_title=f"Cours en {quote_ccy}", template="plotly_dark")
        st.plotly_chart(chart, use_container_width=True)
        st.caption("Source : Yahoo Finance via yfinance. Historique ajusté selon le fournisseur; les prix peuvent être retardés ou corrigés.")
    else:
        st.info("Historique de cours indisponible.")

    st.subheader("Fondamentaux disponibles")
    rows = [
        ("Chiffre d'affaires TTM", fmt_large(revenue, quote_ccy+" ")),
        ("Bénéfice net", fmt_large(net_income, quote_ccy+" ")),
        ("EBITDA", fmt_large(ebitda, quote_ccy+" ")),
        ("Trésorerie", fmt_large(cash, quote_ccy+" ")),
        ("Dette totale", fmt_large(debt, quote_ccy+" ")),
        ("Actions en circulation", f"{shares:,.0f}" if shares else "Indisponible"),
        ("PER historique", f"{trailing_pe:.1f}×" if trailing_pe else "Indisponible"),
        ("Ratio cours/chiffre d'affaires", f"{ps:.1f}×" if ps else "Indisponible"),
        ("Rendement du dividende", f"{dividend_yield*100:.2f}%" if dividend_yield else "Indisponible"),
        ("Bêta", f"{beta:.2f}" if beta else "Indisponible"),
        ("Objectif moyen des analystes", fmt_num(target, "$" if quote_ccy=="USD" else quote_ccy+" ") if target else "Indisponible"),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Indicateur", "Valeur"]), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Valorisation indicative")
    st.caption("Les scénarios ci-dessous sont des calculs simplifiés fondés sur les données disponibles et des hypothèses modifiables. Ils ne constituent pas une recommandation financière.")

    colA, colB = st.columns([1, 1])
    with colA:
        if strategy == "Value Investing":
            st.markdown("**Hypothèses Value Investing**")
            growth = st.slider("Croissance annuelle du CA sur 5 ans (%)", -10, 60, 20, 1)
            exit_multiple = st.slider("Multiple cours/CA terminal", 1.0, 30.0, 8.0, 0.5)
            margin = st.slider("Marge de sécurité souhaitée (%)", 0, 50, 25, 5)
            if revenue and shares and shares > 0:
                future_revenue = revenue * (1 + growth/100)**5
                # Simplified equity proxy; not a DCF. Net cash/debt adjustment omitted.
                enterprise_value_proxy = future_revenue * exit_multiple
                estimated_price_quote = enterprise_value_proxy / shares
                # If current price quote is in local currency, scenario price is also in local currency.
                buy_price_quote = estimated_price_quote * (1 - margin/100)
                st.markdown(f"**Valeur théorique simplifiée à 5 ans :** {fmt_num(estimated_price_quote, {'USD':'$','EUR':'€','GBP':'£'}.get(quote_ccy, quote_ccy+' '))}")
                st.markdown(f"**Prix d'achat avec {margin}% de marge :** {fmt_num(buy_price_quote, {'USD':'$','EUR':'€','GBP':'£'}.get(quote_ccy, quote_ccy+' '))}")
                if estimated_price_quote > 0:
                    implied_upside = (estimated_price_quote / float(price) - 1) * 100
                    if implied_upside > 20:
                        verdict = "Potentiellement sous-évaluée selon ces hypothèses"
                    elif implied_upside < -20:
                        verdict = "Potentiellement surévaluée selon ces hypothèses"
                    else:
                        verdict = "Proche de la valeur estimée selon ces hypothèses"
                    st.info(f"**Verdict indicatif :** {verdict}. Potentiel théorique par rapport au cours : {implied_upside:+.1f}%.")
                st.caption("Attention : ce calcul est un multiple de chiffre d'affaires futur, pas une valeur intrinsèque DCF. Il omet dette nette, dilution, besoins de financement, évolution des marges et valeur temps de l'argent.")
            else:
                st.warning("Données de chiffre d'affaires ou d'actions indisponibles : impossible de calculer ce scénario.")
        elif strategy == "Growth Investing":
            st.markdown("**Cadre Growth Investing**")
            growth = st.slider("Croissance annuelle du CA attendue (%)", -10, 80, 30, 1)
            margin_target = st.slider("Marge bénéficiaire cible (%)", -10, 40, 15, 1)
            pe_target = st.slider("PER cible à maturité", 5, 80, 30, 1)
            if revenue and shares and net_income is not None:
                future_revenue = revenue * (1 + growth/100)**5
                future_profit = future_revenue * margin_target/100
                theoretical = future_profit * pe_target / shares
                st.markdown(f"**Valeur théorique simplifiée à 5 ans :** {fmt_num(theoretical, {'USD':'$','EUR':'€','GBP':'£'}.get(quote_ccy, quote_ccy+' '))}")
                st.caption("Scénario très sensible aux marges et au multiple final; pas une prévision garantie.")
            else:
                st.warning("Données insuffisantes pour calculer le scénario Growth.")
        elif strategy == "Dividend Yield Investing":
            st.markdown("**Cadre Dividend Yield**")
            required_yield = st.slider("Rendement minimum recherché (%)", 1.0, 12.0, 4.0, 0.5)
            dividend_rate = safe_get(info, "dividendRate")
            if dividend_rate:
                fair_value = dividend_rate / (required_yield/100)
                st.markdown(f"**Prix indicatif à rendement cible :** {fmt_num(fair_value, {'USD':'$','EUR':'€','GBP':'£'}.get(quote_ccy, quote_ccy+' '))}")
                st.caption("Calcul = dividende annuel par action / rendement cible. Vérifier la couverture du dividende et sa pérennité.")
            else:
                st.warning("Le fournisseur ne fournit pas de dividende annuel par action. Aucun prix cible n'est calculé.")
        else:
            st.markdown("**Cadre Buy & Hold**")
            st.write("Pour une analyse Buy & Hold robuste, privilégier la qualité des bénéfices, la génération de trésorerie, l'endettement, la résilience du modèle économique et la diversification. L'analyse automatisée reste partielle.")
            st.metric("Bêta indicatif", f"{beta:.2f}" if beta is not None else "Indisponible")

    with colB:
        st.markdown("**Données de marché complémentaires**")
        st.write(f"- PER historique : {trailing_pe:.1f}×" if trailing_pe else "- PER historique : indisponible")
        st.write(f"- Cours/chiffre d'affaires : {ps:.1f}×" if ps else "- Cours/chiffre d'affaires : indisponible")
        st.write(f"- Rendement du dividende : {dividend_yield*100:.2f}%" if dividend_yield else "- Rendement du dividende : indisponible")
        st.write(f"- Trésorerie : {fmt_large(cash, quote_ccy+' ')}")
        st.write(f"- Dette totale : {fmt_large(debt, quote_ccy+' ')}")
        st.write(f"- Site de l'entreprise : {website}" if website else "- Site de l'entreprise : indisponible")

    st.divider()
    st.subheader("Risques à examiner")
    st.markdown("""
    - **Qualité des données :** les agrégateurs peuvent être retardés, incomplets ou incorrects.
    - **Valorisation :** les résultats changent fortement lorsque les hypothèses de croissance ou de multiples changent.
    - **Dette et dilution :** vérifier les rapports officiels, les besoins d'investissement et les actions dilutives.
    - **Événements futurs :** ce prototype ne prétend pas détecter de façon exhaustive les catalyseurs futurs. Les dates doivent être confirmées auprès des sources officielles.
    """)
    st.subheader("Sources et traçabilité")
    st.markdown(f"- Données de marché : [Yahoo Finance](https://finance.yahoo.com/quote/{ticker_symbol}/) — ticker `{ticker_symbol}`.")
    st.markdown(f"- Mapping ISIN : {mapping_source}. [OpenFIGI](https://www.openfigi.com/) — si utilisé.")
    st.markdown("- Déclarations officielles américaines : [SEC EDGAR](https://www.sec.gov/edgar/search/) (à consulter séparément pour confirmer les états financiers).")
    st.caption(f"Application exécutée le {timestamp}. Ce prototype ne fournit pas de conseil financier personnalisé. Vérifie l'identité du titre et les chiffres avant toute décision.")

if run:
    analyze()
else:
    st.info("Saisis un ISIN et clique sur « Analyser le titre ». Si la correspondance automatique échoue, indique le ticker dans le champ facultatif.")
    st.markdown("### Inclus dans cette première version")
    st.markdown("- Résolution ISIN/ticker avec vérification requise")
    st.markdown("- Cours et historique de marché si disponibles")
    st.markdown("- Fondamentaux et ratios récupérés auprès du fournisseur")
    st.markdown("- Cadre de valorisation paramétrable pour quatre stratégies")
    st.markdown("- Sources, limites et avertissements explicites")
