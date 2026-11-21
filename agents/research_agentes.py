import requests
import os
import re
import json
import getpass
from collections import Counter
from pathlib import Path
import pandas as pd
import aisuite as ai


OPENALEX_BASE = "https://api.openalex.org"
openalex_session = requests.Session()
openalex_session.headers.update({
    "User-Agent": "ResearchAgentTeachingNotebook/1.0 (educational use)"
})
def ask_llm(messages, client, MODEL):
    """Piccolo wrapper per mantenere coerenti modello e parametri."""
    #options = dict(LLM_OPTIONS)
    #options.update(extra_options)
    return client.chat.completions.create(
        model=MODEL,
        messages=messages
    )

def reconstruct_abstract(inverted_index):
    """Ricostruisce il testo da abstract_inverted_index di OpenAlex."""
    if not inverted_index:
        return None
    positions = {}
    for word, indexes in inverted_index.items():
        for index in indexes:
            positions[index] = word
    if not positions:
        return None
    return " ".join(positions[i] for i in sorted(positions))


def openalex_search_documents(query: str, max_results: int = 5) -> str:
    """Cerca lavori accademici in OpenAlex.

    Args:
        query (str): Query testuale in inglese o italiano.
        max_results (int): Numero massimo di record (massimo 25 in questa demo).

    Returns:
        Stringa JSON con metadati e abstract quando disponibili.
    """
    params = {
        "search": query,
        "per_page": max(1, min(int(max_results), 25)),
        "select": "id,doi,title,publication_year,authorships,abstract_inverted_index,type,is_retracted"
    }
    response = openalex_session.get(
        f"{OPENALEX_BASE}/works",
        params=params,
        timeout=30
    )
    response.raise_for_status()
    payload = response.json()

    results = []
    for work in payload.get("results", []):
        authors = []
        for authorship in work.get("authorships", []):
            author_name = authorship.get("author", {}).get("display_name")
            if author_name:
                authors.append(author_name)
        results.append({
            "id": work.get("id"),
            "title": work.get("title"),
            "year": work.get("publication_year"),
            "doi": work.get("doi"),
            "authors": authors[:8],
            "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
            "type": work.get("type"),
            "is_retracted": work.get("is_retracted")
        })
    return json.dumps(results, ensure_ascii=False)


def openalex_read_document(document_id: str) -> str:
    """Recupera un singolo record OpenAlex a partire dal suo ID.

    Args:
        document_id (str): URL o identificativo OpenAlex di un work.

    Returns:
        Stringa JSON con metadati e abstract disponibili.
    """
    work_id = document_id.rstrip("/").split("/")[-1]
    if not re.fullmatch(r"W[0-9]+", work_id, flags=re.IGNORECASE):
        return json.dumps({"error": "ID OpenAlex non valido"}, ensure_ascii=False)

    response = openalex_session.get(
        f"{OPENALEX_BASE}/works/{work_id}",
        timeout=30
    )
    response.raise_for_status()
    work = response.json()
    authors = [
        a.get("author", {}).get("display_name")
        for a in work.get("authorships", [])
        if a.get("author", {}).get("display_name")
    ]
    result = {
        "id": work.get("id"),
        "title": work.get("title"),
        "year": work.get("publication_year"),
        "doi": work.get("doi"),
        "authors": authors,
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "type": work.get("type"),
        "is_retracted": work.get("is_retracted"),
        "primary_landing_page": (
            (work.get("primary_location") or {}).get("landing_page_url")
        )
    }
    return json.dumps(result, ensure_ascii=False)

def create_research_plan(question, topic, client, MODEL) -> str:
    """Crea un piano di ricerca a partire da una domanda."""
    messages = [
        {
            "role": "system",
            "content": (
                f"Sei un assistente che pianifica una ricerca in {topic} "
                "Non rispondere ancora alla domanda. "
                "Produci: obiettivo, 3-5 sotto-domande, parole chiave in italiano "
                "e inglese, informazioni da cercare, limiti e possibili fattori "
                "confondenti. Usa formulazioni prudenti e non causali."
            )
        },
        {"role": "user", "content": question}
    ]
    response = ask_llm(messages, client, MODEL)
    return response.choices[0].message.content or "[Il modello non ha restituito testo]"

def run_research_agent(question: str, research_plan: str, client, MODEL) -> str:
    """Esegue la ricerca usando i tool del corpus locale."""
    system_prompt = """
Sei un Research Agent per un laboratorio didattico di psicologia e scienze sociali.

Hai a disposizione questi strumenti per accedere alle risorse di OpenAlex:
- openalex_search_documents: cerca per parole chiave;
- openalex_read_document: legge un record completo.

Procedura:
1. Leggi il piano di ricerca.
2. Elenca o cerca i documenti pertinenti.
3. Leggi i documenti più utili prima di formulare conclusioni.
4. Confronta i contenuti e segnala eventuali differenze.
5. Produci un rapporto con: domanda, metodo di consultazione, risultati,
   interpretazione prudente, limiti e conclusione provvisoria.

Regole obbligatorie:
- Cita gli id per ogni affermazione derivata dal corpus.
- Non inventare autori, DOI, riviste, campioni o risultati.
- Non trasformare associazioni ipotetiche in causalità.
- Non formulare diagnosi né valutazioni cliniche.
- Se il corpus non permette di rispondere, dichiaralo.

Formattazione della risposta:
- Usa un formato LaTeX minimale per il rapporto finale.
- Includi un elenco numerato dei documenti consultati con id OpenAlex.
"""


    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Domanda di ricerca:\n{question}\n\n"
                f"Piano:\n{research_plan}\n\n"
                "Conduci la ricerca nel corpus e redigi il rapporto."
            )
        }
    ]

    output = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=[openalex_search_documents, openalex_read_document],
        max_turns=8,
        #**LLM_OPTIONS
    )
    return output.choices[0].message.content or "[Il modello non ha restituito testo]"

#################
RESEARCH_QUESTION = (
    "In che modo l'esposizione a contenuti sui social network può essere "
    "associata alla percezione dell'immagine corporea negli adolescenti?"
)
topic = "psicologia e scienze sociali"
MODEL = "openai:gpt-4o-mini"
#################

client = ai.Client(
    {
        "openai":{
            "timeout": 100,
            "api_key": ""
            
        }   
    }
)
print("sto creando il piano di ricerca...")
piano_di_ricerca = create_research_plan(RESEARCH_QUESTION, topic, client, MODEL)
print("sto creando il risultato della ricerca...")
risultato_della_ricerca = run_research_agent(RESEARCH_QUESTION, piano_di_ricerca, client, MODEL)



report_path = Path("risultati.tex")
report_path.write_text(risultato_della_ricerca, encoding="utf-8")
   # "# Report del Research Agent \n\n"
   # f"## Domanda\n{RESEARCH_QUESTION}\n\n"
    #f"## Rapporto\n{risultato_della_ricerca}\n\n",
    #encoding="utf-8"
#)
print("Report salvato in:", report_path.resolve())