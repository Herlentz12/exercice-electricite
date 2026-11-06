from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

DOSSIER = Path(__file__).parent / "donnees"

st.set_page_config(page_title="L'électricité dans 12 quartiers", page_icon="⚡", layout="wide")

st.title("L'électricité dans 12 quartiers")
st.caption("Relevés mensuels de janvier 2024 à décembre 2025. Données fictives.")


@st.cache_data
def charger_donnees() -> pd.DataFrame:
	return pd.read_csv(DOSSIER / "consommation_propre.csv")


donnees = charger_donnees()
st.write(
	"Ce tableau de bord analyse les relevés de consommation, les heures de courant et la météo. "
	"Les données ont été nettoyées et enrichies dans le notebook d'exploration."
)
st.write(
	"Les indicateurs suivent les filtres choisis; les comparaisons de tendance et de corrélation "
	"portent sur les deux années disponibles."
)

communes = sorted(donnees["commune"].dropna().unique().tolist())
annees = sorted(donnees["annee"].dropna().unique().tolist())
with st.sidebar:
	st.header("Filtres")
	communes_choisies = st.multiselect("Communes", communes, default=communes)
	annee_defaut = annees.index(2025) if 2025 in annees else len(annees) - 1
	annee_choisie = st.selectbox("Année", annees, index=annee_defaut)

if not communes_choisies:
	st.info("Choisissez au moins une commune pour afficher les résultats.")
	st.stop()

donnees_communes = donnees[donnees["commune"].isin(communes_choisies)].copy()
donnees_filtrees = donnees_communes[donnees_communes["annee"] == annee_choisie].copy()

total_kwh = donnees_filtrees["kwh"].sum()
moyenne_par_abonne = donnees_filtrees["kwh_par_abonne"].mean()
moyenne_heures = donnees_filtrees["heures_courant"].mean()
indicateurs = st.columns(3)
indicateurs[0].metric("Consommation totale", f"{total_kwh / 1_000_000:.2f} M kWh")
indicateurs[1].metric("Consommation moyenne par abonné", f"{moyenne_par_abonne:.1f} kWh")
indicateurs[2].metric("Courant disponible par jour", f"{moyenne_heures:.1f} h")

onglet_quartiers, onglet_evolution, onglet_chaleur, onglet_coupures, onglet_records = st.tabs(
	[
		"Par abonné",
		"Évolution",
		"Chaleur ou courant ?",
		"Coupures",
		"Relevés extrêmes",
	]
)

with onglet_quartiers:
	st.subheader("Quels quartiers consomment le plus par abonné ?")
	classement = (
		donnees_filtrees.groupby("quartier")["kwh_par_abonne"]
		.mean()
		.sort_values(ascending=False)
	)
	figure, axe = plt.subplots(figsize=(8, 5))
	classement.sort_values().plot.barh(ax=axe, color="#277c74")
	axe.set_xlim(left=0)
	axe.set_xlabel("kWh par abonné")
	axe.set_ylabel("")
	axe.set_title("Consommation moyenne par abonné, par quartier")
	figure.tight_layout()
	st.pyplot(figure)
	plt.close(figure)
	if not classement.empty:
		st.write(
			f"En {annee_choisie}, {classement.index[0]} arrive en tête avec "
			f"{classement.iloc[0]:.1f} kWh par abonné."
		)

with onglet_evolution:
	st.subheader("Comment la consommation évolue-t-elle, commune par commune ?")
	totaux_annuels = donnees_communes.groupby(["commune", "annee"])["kwh"].sum().unstack()
	st.bar_chart(totaux_annuels / 1_000_000)
	if {2024, 2025}.issubset(totaux_annuels.columns):
		evolution = ((totaux_annuels[2025] / totaux_annuels[2024] - 1) * 100).sort_values(
			ascending=False
		)
		premiere = evolution.index[0]
		st.write(
			f"Sur les deux années, {premiere} progresse le plus ({evolution.iloc[0]:.1f} %); "
			f"{evolution.index[-1]} progresse le moins ({evolution.iloc[-1]:.1f} %)."
		)
	mensuel = (
		donnees_communes.groupby(["mois", "commune"], as_index=False)["kwh_par_abonne"]
		.mean()
		.pivot(index="mois", columns="commune", values="kwh_par_abonne")
	)
	st.line_chart(mensuel)

with onglet_chaleur:
	st.subheader("La consommation suit-elle la chaleur, ou les heures de courant ?")
	residentiel = donnees_communes[donnees_communes["type"] == "Résidentiel"]
	if residentiel.empty:
		st.info("Aucun quartier résidentiel dans les communes sélectionnées.")
	else:
		correlation_heures = residentiel["kwh_par_abonne"].corr(residentiel["heures_courant"])
		correlation_temperature = residentiel["kwh_par_abonne"].corr(residentiel["temperature_c"])
		mesures = st.columns(2)
		mesures[0].metric("Corrélation avec les heures de courant", f"{correlation_heures:.2f}")
		mesures[1].metric("Corrélation avec la température", f"{correlation_temperature:.2f}")
		figure, axe = plt.subplots()
		axe.scatter(residentiel["heures_courant"], residentiel["kwh_par_abonne"], alpha=0.65)
		axe.set_xlabel("Heures de courant par jour")
		axe.set_ylabel("kWh par abonné")
		axe.set_title("Quartiers résidentiels, 2024-2025")
		st.pyplot(figure)
		plt.close(figure)
		st.write(
			f"La relation avec les heures de courant ({correlation_heures:.2f}) est plus forte "
			f"qu'avec la température ({correlation_temperature:.2f}); une corrélation ne prouve pas une causalité."
		)

with onglet_coupures:
	st.subheader("Où les coupures sont-elles les plus longues ?")
	quantiles = donnees_filtrees.groupby("commune")["heures_courant"].agg(
		mediane="median",
		q1=lambda valeurs: valeurs.quantile(0.25),
		q3=lambda valeurs: valeurs.quantile(0.75),
	).round(1)
	st.dataframe(quantiles, width="stretch")
	cap_haïtien = donnees_filtrees.loc[
		donnees_filtrees["commune"] == "Cap-Haïtien", "heures_courant"
	]
	if not cap_haïtien.empty:
		figure, axe = plt.subplots()
		axe.hist(cap_haïtien, bins=10, edgecolor="white")
		axe.set_xlabel("Heures de courant par jour")
		axe.set_ylabel("Nombre de relevés")
		axe.set_title(f"Cap-Haïtien, {annee_choisie}")
		st.pyplot(figure)
		plt.close(figure)
	faibles = donnees_filtrees[donnees_filtrees["heures_courant"] < 8]
	st.write(f"{len(faibles)} relevé(s) de {annee_choisie} ont moins de 8 heures de courant par jour.")
	if not faibles.empty:
		st.dataframe(faibles[["mois", "quartier", "heures_courant"]], hide_index=True)

with onglet_records:
	st.subheader("Quels relevés sortent du lot ?")
	records = donnees_communes.nlargest(3, "kwh")[["mois", "quartier", "type", "kwh"]]
	figure, axe = plt.subplots()
	etiquettes = records["mois"] + " - " + records["quartier"]
	axe.bar(etiquettes, records["kwh"], color="#d58b38")
	axe.set_ylabel("kWh")
	axe.set_title("Les trois plus grosses consommations")
	axe.tick_params(axis="x", labelrotation=25)
	figure.tight_layout()
	st.pyplot(figure)
	plt.close(figure)
	st.dataframe(records, hide_index=True)
	if not records.empty:
		premier = records.iloc[0]
		st.write(
			f"Le plus gros relevé est celui de {premier['quartier']} en {premier['mois']} : "
			f"{premier['kwh']:,.0f} kWh."
		)

st.markdown(
	"### Conclusion\n\n"
	"Dans les quartiers résidentiels, la consommation par abonné est plus fortement associée "
	"aux heures de courant (0,76) qu'à la température (-0,15). "
	"Cette association ne démontre pas un lien de cause à effet et d'autres facteurs peuvent intervenir."
)

with st.expander("Afficher les données filtrées"):
	st.dataframe(donnees_filtrees, hide_index=True, width="stretch")
