file_path ="/Users/beppe2hd/My Drive/CNR/Corsi/Master_Prompting/data_analysys_CPPAI/agents/inventory_events_100.csv"

question = "calcola i guadagni totali relativi alla vendita di ogni singolo prodotto della colonna category per le action sale"

######################################

import pandas as pd

df = pd.read_csv(file_path)
schema=df.columns

model = "openai:gpt-4o-mini"

############
import aisuite as ai
import json
import re

client = ai.Client(
    {
        "openai":{
            "timeout": 100,
            "api_key": "YOUR_OPENAI_API_KEY"
        }   
    }
)

def generate_pp(client: ai.Client, question: str, file_path: str, schema: str, model: str) -> str:
    
    prompt = f"""
    You are a Python and Pandas assistant. Given the schema of a DataFrame and the user's question, write a Python code using pandas to process the DataFrame.

    Schema:
    {schema}

    User question:
    {question}

    file_path: 
    {file_path}

    Store the output in a result variable. Do not print the result. 
    
    Respond with the python only.
    Return your answer *strictly* in this format:

    <execute_python>
    # valid python code here
    </execute_python>

    Do not add explanations, only the tags and the code.
    """

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=1,
    )
    return response.choices[0].message.content.strip()

script = generate_pp(client, question, file_path, schema, model)

match = re.search(r"<execute_python>([\s\S]*?)</execute_python>", script)
ns = {} 
if match:
    script_filtered = match.group(1).strip()
    #print(script_filtered)
    #print("--"*10)
    exec(script_filtered, ns)  # Execute the generated script
    output = ns["result"]
    #print(output)
else:
    print("No Python code found in the response.")
#print(script)
#print(output)

################# controllo con secondo modello

def refine_script_external_feedback(
    question: str,
    script: str,
    output: str,
    schema: str,
    model: str,
) -> tuple[str, str]:
    """
    Reflect on whether a script's *shown output* answers the question,
    and propose an improved version if needed.
    Returns (feedback, refined_code).
    """
    prompt = f"""
You are a python (pandas) reviewer and refiner.

User asked:
{question}

Original python script:
{script}

Data Frame Columns:
{schema}

Python script OUTPUT:
{output}

Step 1: Briefly evaluate if the python script OUTPUT fully answers the user's question.
Step 2: If improvement is needed, provide a refined python script.
If the original python script is already correct, return it unchanged.

Return STRICT JSON with two fields:
{{
  "feedback": "<1-3 sentences explaining the gap or confirming correctness. DO not include code here>",
  "refined_pypandas": "<final python script to run> Respond with the python only.
                   Return your answer *strictly* in this format:
                     <execute_python>
                     # valid python code here
                     </execute_python>"
}}
"""
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=1,
    )

    content = response.choices[0].message.content

    try:
        obj = json.loads(content)
        feedback = str(obj.get("feedback", "")).strip()
        refined_script = str(obj.get("refined_pypandas", script)).strip()
        if not refined_script:
            refined_script = script
    except Exception:
        # Fallback if model doesn't return valid JSON
        feedback = content.strip()
        refined_script = script

    return feedback, refined_script

model = "openai:gpt-5.6-sol"

print("sto ricontrollando lo script")

feedback, refined_script = refine_script_external_feedback(
    question,
    script,
    output,
    schema,
    model,
)

match = re.search(r"<execute_python>([\s\S]*?)</execute_python>", refined_script)
ns = {} 
if match:
    #print("Found Python code:")
    script_filtered = match.group(1).strip()
    #print(script_filtered)
    #print("--"*10)
    exec(script_filtered, ns)  # Execute the generated script
    output = ns["result"]
    #print(output)
else:
    print("No Python code found in the response.")

print(f"l'output finale è: \n {output}")