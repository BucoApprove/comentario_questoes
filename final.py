import streamlit as st
import os
import time
import json
import pandas as pd
import datetime

# GOOGLE SHEETS
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# OPENAI BETA ASSISTANTS
from openai import OpenAI

# Carrega variáveis de ambiente

# ------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ------------------------------------------------
st.set_page_config(page_title="Agente Chat Odontologia Login", layout="wide")

# ------------------------------------------------
# PARÂMETROS DA PLANILHA GOOGLE
# ------------------------------------------------
SPREADSHEET_ID = "1EuycUTyio3Mx2a8zyizez8O6hxOpCdR1QXX9hdfYrvI"
SHEET_NAME = "SALVO"

# ------------------------------------------------
# FUNÇÕES AUXILIARES - GOOGLE SHEETS
# ------------------------------------------------
def get_gsheets_credentials():
    """
    Retorna as credenciais do Google Sheets a partir de st.secrets["google_service_account"].
    """
    service_account_info = st.secrets["google_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    return creds

def append_row_to_sheet(spreadsheet_id, sheet_name, row_data, credentials):
    """
    Adiciona row_data (lista) como nova linha no Google Sheets.
    Iniciamos a partir da segunda linha (A2) para preservar cabeçalho na linha 1.
    """
    service = build("sheets", "v4", credentials=credentials)
    range_ = f"{sheet_name}!A2"
    body = {"values": [row_data]}
    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=range_,
            valueInputOption="USER_ENTERED",
            body=body,
        )
        .execute()
    )
    return result

# ------------------------------------------------
# FUNÇÕES DO ASSISTANT (SEU SCRIPT ORIGINAL)
# ------------------------------------------------

client = OpenAI(api_key=st.secrets["openai"]["api_key"])
assist_name = "Copy of BucoApp IA"

def fetch_assistant_by_name(data, assist_name):
    for assistant in data:
        if assistant.name == assist_name:
            return assistant
    return None

def initiate_assistant():
    system_msg = '''
    # Prompt para Agente Especialista em Odontologia

    Você é um agente especializado em responder dúvidas sobre odontologia e cirurgia bucomaxilofacial. Seu objetivo é esclarecer dúvidas com precisão, utilizando como base sua **Vector Store**, que contém informações detalhadas extraídas de livros e materiais confiáveis relacionados a estas áreas.

    ---

    ## Instruções para Respostas

    ### 1. Identificação da Dúvida
    - Leia e interprete cuidadosamente a dúvida apresentada pelo usuário.
    - Se necessário, reformule a dúvida para esclarecer seu escopo antes de respondê-la.

    ### 2. Fundamentação
    - Baseie todas as respostas em informações retiradas da Vector Store, priorizando a **clareza** e a **precisão**.
    - Sempre que possível, referencie o livro e a edição que embasaram a resposta.

    ### 3. Estilo de Resposta
    - As respostas devem ser **didáticas** e **objetivas**, adequadas para estudantes e profissionais da área odontológica.
    - Utilize linguagem técnica, mas certifique-se de que seja compreensível, explicando conceitos quando necessário.

    ### 4. Estrutura da Resposta
    A resposta deve ser organizada em uma estrutura clara, contendo:

    1. **Resposta direta à dúvida**.
    2. **Explicação detalhada**, incluindo conceitos relevantes.
    3. **Referências aos livros** (título e, quando disponível, edição) da Vector Store que embasaram a resposta.

    #### Exemplo de Estrutura:
    - **Resposta:** [Forneça uma resposta objetiva à pergunta].
    - **Comentário:** [Apresente uma explicação detalhada que justifique a resposta, incluindo a base teórica ou prática].
    - **Fonte:** [Título do livro e edição].

    ### 5. Análise Crítica e Alternativas
    - Caso existam diferentes abordagens ou controvérsias na literatura, destaque-as, mencionando os livros que sustentam cada ponto de vista.
    - Indique qual abordagem é mais aceita na prática clínica e explique o porquê.

    ### 6. Respostas Inconclusivas
    - Se a dúvida não puder ser respondida com base nas informações disponíveis:
      - Explique por que não é possível fornecer uma resposta definitiva.
      - Sugira possíveis recursos ou caminhos para esclarecer a questão.

    ### 7. Evitar Repetições
    - Não repita a dúvida na íntegra na resposta, a menos que seja necessário para contextualizar o usuário.

    ### 8. Restrições de Conteúdo
    - Não insira códigos, scripts, links ou conteúdo não relacionado à dúvida apresentada.
    - Mantenha as respostas focadas em odontologia e cirurgia bucomaxilofacial.

    ---

    ## Nota Final
    Ao responder, busque sempre:
    1. Promover o aprendizado do usuário.
    2. Garantir que as informações fornecidas sejam confiáveis e atualizadas.
    3. Oferecer respostas que sejam úteis tanto para estudantes quanto para profissionais.

    **Tome um fôlego e aborde a dúvida de maneira clara, fundamentada e passo a passo.**

    '''

    my_assistants = client.beta.assistants.list(order="desc", limit="5")
    result = fetch_assistant_by_name(my_assistants.data, assist_name)
    if result is None:
        my_assistant = client.beta.assistants.create(
            instructions=system_msg,
            name=assist_name,
            tools={
                "type": "file_search",
                "vector_store_id": "vs_ryOfIVIPUi66k3G34SCxexNv"
            },
            model="gpt-4o-mini",
        )
    else:
        my_assistant = client.beta.assistants.retrieve(result.id)
    return my_assistant

def open_thread():
    new_thread = client.beta.threads.create()
    return new_thread

def add_query(thread_id, query):
    thread_message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=query,
    )
    return thread_message

def callTools(tool_calls):
    tool_outputs = []
    for t in tool_calls:
        functionName = t.function.name
        attributes = json.loads(t.function.arguments)
        args = list(attributes.values())
        function = globals().get(functionName)
        try:
            if args:
                functionResponse = function(*args)
            else:
                functionResponse = function()
        except Exception as e:
            functionResponse = {
                "status": 'Error in function call ' + functionName + '(' + t.function.arguments + ')',
                "error": str(e)
            }
        tool_outputs.append({"tool_call_id": t.id, "output": json.dumps(functionResponse)})
    return tool_outputs

def runOpenai(thread_id, assistant_id):
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )
    while True:
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        print(run.status)
        if run.status == 'completed':
            break
        elif run.status == 'requires_action':
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            tool_outputs = callTools(tool_calls)
            run = client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )
        time.sleep(.5)
    return run

# ------------------------------------------------
# TELA DE LOGIN
# ------------------------------------------------
def login_screen():
    st.title("Login - Acesso ao Agente Chat Odontologia")

    with st.form(key="login_form"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submit_button = st.form_submit_button(label="Entrar")

    if submit_button:
        stored_username = st.secrets["credentials"]["user"]
        stored_password = st.secrets["credentials"]["password"]

        if username == stored_username and password == stored_password:
            st.session_state["logged_in"] = True
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos!")

# ------------------------------------------------
# APLICAÇÃO DE CHAT
# ------------------------------------------------
def chat_app():
    st.title("Chat com AGENTE para Comentetário de Questões")

    # Garante que o DF exista
    if "df" not in st.session_state:
        st.session_state["df"] = pd.DataFrame(columns=["DataHora", "Questão", "Comentário"])

    # Garante que o Assistant e Thread existam
    if "assistant_id" not in st.session_state:
        my_assistant = initiate_assistant()
        st.session_state["assistant_id"] = my_assistant.id
        thread = open_thread()
        st.session_state["thread_id"] = thread.id

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Exibe o histórico
    for role, content in st.session_state["chat_history"]:
        if role == "user":
            # Caixa em tom de azul (usuário)
            st.markdown(f"""
            <div style="border:1px solid #B3D7FF; background-color:#E8F4FF; 
                        border-radius:5px; padding:10px; margin-bottom:10px;">
              <strong>Você:</strong> {content}
            </div>
            """, unsafe_allow_html=True)
        else:
            # Caixa em tom de verde (assistente)
            st.markdown("""
            <div style="border:1px solid #D1FFD1; background-color:#F0FFF0; 
                        border-radius:5px; padding:10px; margin-bottom:10px;">
              <strong>Assistente:</strong>
            </div>
            """, unsafe_allow_html=True)
            st.code(content, language=None)  # com botão de "copiar"

    # Campo de texto fixo ao rodapé (requer Streamlit >= 1.25)
    user_input = st.chat_input("Digite sua pergunta:")
    if user_input:
        thread_id = st.session_state["thread_id"]
        assistant_id = st.session_state["assistant_id"]

        # Adiciona pergunta ao histórico
        st.session_state["chat_history"].append(("user", user_input))

        # Spinner "PENSANDO..."
        with st.spinner("PENSANDO..."):
            add_query(thread_id, user_input)
            runOpenai(thread_id, assistant_id)

        # Obtém a resposta mais recente
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        response = messages.data[0].content[0].text.value

        # Armazena no DataFrame
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state["df"].loc[len(st.session_state["df"])] = [
            now_str, user_input, response
        ]

        # Salva no Google Sheets
        creds = get_gsheets_credentials()
        row_data = [now_str, user_input, response]
        append_row_to_sheet(SPREADSHEET_ID, SHEET_NAME, row_data, creds)

        # Armazena no histórico
        st.session_state["chat_history"].append(("assistant", response))

        # Rerun para atualizar chat
        st.rerun()

# ------------------------------------------------
# FUNÇÃO PRINCIPAL
# ------------------------------------------------
def main():
    # Inicializa a flag de login, se ainda não existir
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        login_screen()   # exibe tela de login
    else:
        chat_app()       # exibe o chat

if __name__ == "__main__":
    main()
