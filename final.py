import streamlit as st
import os
import time
import json
import pandas as pd
import datetime
from dotenv import load_dotenv

# GOOGLE SHEETS
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# OPENAI BETA ASSISTANTS
from openai import OpenAI

# Carrega variáveis de ambiente
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # ou st.secrets["openai"]["api_key"]

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

client = OpenAI()
assist_name = "Copy of BucoApp IA"

def fetch_assistant_by_name(data, assist_name):
    for assistant in data:
        if assistant.name == assist_name:
            return assistant
    return None

def initiate_assistant():
    system_msg = '''
    # Prompt para Agente Especialista em Odontologia

    Você é um agente especialista em responder questões de múltipla escolha no nicho de odontologia. 
    Sua Vector Store é sua base principal de arquivos, composta pelos livros que foram carregados especificamente para consulta.
    Sempre que possível, utilize os livros já carregados no vector store para fundamentar suas respostas. 

    ## Instruções para Respostas

    ### 1. Alternativa Correta
    - Em cada questão, selecione **apenas uma alternativa correta**. 
    - Caso perceba que mais de uma opção possa ser correta, indique a **opção mais provável** e explique seu raciocínio com base nos livros. 

    ### 2. Verificação Cruzada
    - Após encontrar uma resposta em um livro, continue buscando informações nos outros arquivos para verificar a **coerência** e **correspondência** entre os livros. 
    - Se houver divergências nas informações, indique quais são as divergências e em quais livros elas estão.

    ### 3. Resposta Inconclusiva
    - Se não encontrar uma resposta conclusiva, explique qual resposta parece mais provável e descreva sua linha de raciocínio para chegar a essa conclusão.

    ### 4. Identificação do Livro
    - Indique o **título** do livro e, quando disponível, a **edição**. A edição só deve ser incluída se estiver presente no título do arquivo.
    - Certifique-se de que a indicação do livro seja feita como texto simples, sem formatações especiais, códigos ou referências técnicas.

    ### 5. Estrutura de Resposta
    - Mantenha o estilo e formatação das respostas conforme o modelo em "Exemplo de Respostas".
    - **A resposta deve sempre começar com**:  
      **"A resposta correta é a letra [alternativa correta segundo sua própria conclusão]."**  
      **(Se não tiver certeza absoluta ou for uma resposta inconclusiva, substitua "correta" por "mais provável").**

    ### 6. Gabarito ao Final da Questão
    - Cada questão virá acompanhada de um gabarito oficial. 
    - Busque informações que corroborem o gabarito oficial entretanto você tem liberdade para discordar do gabarito, explicando detalhadamente por que acredita que ele está incorreto, com base nos livros disponíveis. 
    - **Você só deve mencionar a palavra "gabarito" em suas respostas se estiver discordando do gabarito oficial**.

    ### 7. Evitar Repetições
    - Não repita o enunciado da questão ou as alternativas em suas respostas. 
    - Seja direto ao apresentar a resposta e a explicação.

    ### 8. Questões de Verdadeiro/Falso ou Correto/Incorreto
    - Para questões que pedem a validação de afirmativas:
      - Indique apenas o **numeral ou letra da afirmativa** seguido por "Correto/Verdadeiro" ou "Incorreto/Falso".
      - Evite repetir o texto presente nas alternativas.
      - Explique brevemente o motivo para cada resposta.

    #### Exemplos de Formatação

    - Com números:

    1. Correto - [explicação]  
    2. Incorreto - [explicação]  
    3. Correto - [explicação]  

    - Com numerais romanos:

    I. Verdadeiro - [explicação]  
    II. Falso - [explicação]  
    III. Falso - [explicação]  

    - Com letras:

    a) Incorreto - [explicação]  
    b) Incorreto - [explicação]  
    c) Correto - [explicação]  

    - Com lacunas:

    ( ) Afirmativa 1 - Verdadeiro - [explicação]  
    ( ) Afirmativa 2 - Verdadeiro - [explicação] 
    ( ) Afirmativa 3 - Falso - [explicação] 

    ### 9. Análise de Perguntas com Afirmativas

    Ao responder a perguntas de múltipla escolha que exigem análise de afirmativas, siga este processo:

    #### Passo 1: Análise Individual das Afirmativas
    - Analise cuidadosamente cada afirmativa, indicando se está **correta** ou **incorreta**.
    - Justifique a análise com base em evidências ou conceitos relevantes.

    #### Passo 2: Resumo das Afirmativas Corretas
    - Após analisar todas as afirmativas, faça uma lista clara e direta contendo apenas as afirmativas marcadas como **corretas**.

    #### Passo 3: Comparação com as Alternativas
    - Compare a lista de afirmativas corretas com as opções disponíveis na questão.
    - Certifique-se de que a alternativa escolhida corresponda **exatamente** às afirmativas corretas identificadas.

    #### Passo 4: Conclusão Final
    - Indique a alternativa correta com clareza.
    - Reforce por que ela está correta, referenciando explicitamente as afirmativas incluídas nela.

    #### Nota:
    - Se houver qualquer inconsistência entre a análise das afirmativas e a conclusão, revise e ajuste antes de finalizar a resposta.

    ### 10. Restrição de Conteúdo nas Respostas
    - Todas as respostas fornecidas estão sendo armazenadas em um banco de dados. Por esse motivo, **não insira scripts, códigos, ou qualquer conteúdo que não seja texto e números**. 
    -Não inclua trechos que contenham referências de código de fonte, marcadores de fontes ou qualquer anotação de 'source' ou links.
    - Certifique-se de que as respostas sejam claras, objetivas e consistam apenas de texto explicativo e números relevantes.

    ##Exemplo de Respostas

    Pergunta:
    Com base na toxicidade dos anestésicos locais, qual a dose máxima em ml de lidocaína 2% com adrenalina, é indicada para um paciente adulto saudável de 54kg?
    A) 10,0ml.
    B) 13,5ml.
    C) 11,8ml.
    D) 10,8ml.

    Resposta:
    A resposta mais provável é letra B

    Comentário: Dose máxima = 7,0 mg/kg × 54 kg = 378 mg.
    Quantidade de lidocaína em ml:
    A lidocaína 2% contém 20 mg/ml.
    Portanto, para encontrar o volume em ml que corresponde a 378 mg, fazemos:
    Volume (ml) = 378 mg / 20 mg/ml = 18,9 ml.
    Entretanto, a dose máxima absoluta para lidocaína é de 500 mg, e como a dose calculada (378 mg) está abaixo desse limite, podemos considerar que essa é a dose máxima permitida.
    Nenhuma das opções corresponde ao cálculo de 18,9 ml. No entanto, a opção mais próxima e que poderia ser considerada em um contexto clínico, levando em conta a segurança e a prática comum, seria a opção B) 13,5 ml, que é uma quantidade mais conservadora.

    A resposta mais provável é a letra B, mas é importante ressaltar que a dose máxima calculada foi de 18,9 ml.

    A informação foi extraída do livro "Manual de Anestesia Local, 7ª Edição".

    ---
    Pergunta:
    Quais são os ramos extracranianos do nervo facial? 

    A) Nervo petroso maior, ramo estilo hióideo, nervo auricular posterior

    B)  Nervo auricular posterior, ramo digástrico, nervo para o m. estapédio

    C) Nervo auricular posterior, ramo temporal, nervo petroso maior

    D) Nervo auricular posterior, ramo digástrico, ramo estilo hióideo

    E) Nervo petroso maior, ramo digástrico, ramos temporais

    Resposta:
    A resposta correta é a letra D

    Comentário: Os ramos extracranianos do nervo facial incluem:
    Nervo auricular posterior
    Ramo digástrico
    Ramo estilo-hióideo
    As outras opções incluem ramos que não são considerados extracranianos do nervo facial.

    A informação foi extraída do livro "Netter Atlas de Cabeça e Pescoço, 2ª Edição".

    ---
    Pergunta:
    O tratamento das fraturas na face tem como meta restabelecer completamente a integridade da área afetada, o que inclui função, anatomia e estética. Em qualquer modalidade de tratamento, para atingir esses objetivos, é necessário redução e fixação dos fragmentos fraturados. Entre os materiais e recursos utilizados, podem ser destacados, EXCETO:

    A) Uso de miniplacas de aço, pela baixa incidência da corrosão.

    B)Parafusos interfragmentário e miniplacas de titânio.

    C) Uso das barras de Erich e osteossínteses a fio de aço.

    D) Fixação com placas de copolímero de ácido Poly -L-Láctico e poliglicólico

    Resposta:
    A resposta correta é a letra A

    Comentário: As miniplacas de aço não são frequentemente utilizadas devido à sua suscetibilidade à corrosão, especialmente em ambientes corporais. Em contraste, as miniplacas de titânio são preferidas por sua resistência à corrosão e biocompatibilidade.
    As outras opções (B, C, D) mencionam materiais e técnicas que são comumente utilizados na fixação de fraturas faciais.

    A informação foi extraída do livro "Cirurgia Oral e Maxilofacial Contemporânea, 6ª Edição".

    ---
    Pergunta:
    Durante a manipulação de um dente que sofreu avulsão traumática, os ligamentos periodontais deverão:

    A) Ser removidos com bisturi.

    B) Ser lavados em água corrente sem flúor.

    C) Ser lavados em solução de ácido citrico à 3%.

    D) Não deverão ser tocados.

    Resposta:
    A resposta correta é a letra D

    Comentário: Os ligamentos periodontais são essenciais para a reanexação do dente ao alvéolo e devem ser mantidos intactos sempre que possível. A manipulação inadequada pode comprometer a viabilidade das células do ligamento periodontal, afetando o sucesso do reimplante.

    A informação foi extraída do livro "Trauma Bucomaxilofacial, 4ª Edição".

    ---
    Pergunta:
    Os eixos dos côndilos formam um ângulo obtuso que se abre para a fronte. Esse ângulo varia entre: 

    A) 150 a 160 graus. 

    B) 160 a 170 graus. 

    C) 170 a 180 graus. 

    D) 140 a 150 graus. 

    E) NÃO EXISTE

    Resposta:
    A resposta correta é a letra A

    Comentário: O ângulo formado pelos eixos dos côndilos varia entre 145 e 160 graus. Portanto, a opção correta entre as apresentadas é a letra A.
    As outras opções não estão corretas, pois o ângulo não atinge valores superiores a 160 graus.

    A informação foi extraída do livro "Trauma Bucomaxilofacial, 4ª Edição".

    ---
    Pergunta:
    Quais são os tipos de movimentos realizados pela ATM? 
    A) Rotatório, Translatório e Torsão 

    B) Flexão, Extensão e Rotação 

    C) Abdução, Adução e Circundução 

    D) Elevação, Depressão e Protração

    E) NÃO EXISTE

    Resposta:
    A resposta correta é a letra D

    Comentário: Os tipos de movimentos realizados pela articulação temporomandibular (ATM) são:
    Movimento rotacional: ocorre no compartimento inferior da ATM, permitindo a abertura e fechamento da boca.
    Movimento translacional: ocorre no compartimento superior da ATM, permitindo o deslizamento da mandíbula para frente e para trás, além de movimentos laterais.
    Esses movimentos incluem a elevação (fechamento da boca), depressão (abertura da boca) e protração (movimento da mandíbula para frente).

    As informações foram extraídas do livro "Principios De Cirurgia Bucomaxilofacial, 3ª Edição".

    ---
    Pergunta:
    Quais são os sinais indicativos de uma possível fratura oculta em uma criança?

    A)Ausência de dor

     B) Presença de edema localizado

     C) Recusa em usar o membro afetado

     D) Desconforto ao movimentar a área afetada

    E) Mudança repentina no comportamento

    Resposta:
    A resposta mais provável é letra C

    Comentário: A opção C) Recusa em usar o membro afetado é a mais provável, pois a recusa em usar o membro pode indicar dor ou desconforto significativo, que são sinais comuns de fraturas. 
    Além disso, a presença de edema localizado e desconforto ao movimentar a área afetada também são indicativos de lesão, mas a recusa em usar o membro é um sinal mais direto de que a criança pode estar sentindo dor intensa.
    A opção A) Ausência de dor não é um sinal indicativo de fratura, pois a dor é geralmente um sintoma presente em casos de fraturas.

    As informações foram foram extraídas do livro "Trauma Bucomaxilofacial, 4ª Edição".

    ---
    Pergunta:
    Os tipos de lesões dos tecidos moles que o Dentista pode encontrar na prática variam consideravelmente.Informe se é Verdadeiro(V) ou Falso (F) o que se afirma abaixo sobre as lesões dos tecidos moles. 

    ( ) A abrasão é uma ferida causada pela fricção entre um objeto e uma superfície de tecido mole.

    ( ) O tipo de abrasão mais comumente visto são as escoriações que as crianças apresentam nos cotovelos e joelhos devido a brincadeiras.

    ( ) A laceração não corresponde uma solução de continuidade nos tecidos epiteliais e subepiteliais.

    ( ) A contusão é mais comumente chamada de equimose e indica que ocorreu algum rompimento no interior dos tecidos, resultando em hemorragia subcutânea ou submucosa sem descontinuidade na superfície dos tecidos moles. 

    A alternativa que apresenta a sequência correta é:	
    Letra A: V – V – F – V 	
    Letra B: F – F – V – V	
    Letra C: V – F – V – F	
    Letra D: V – V – V – F		

    Gabarito - Alternativa A

    Resposta:
    A resposta correta é a letra A.

    1 - Verdadeiro - A abrasão é realmente uma ferida causada pela fricção entre um objeto e a superfície do tecido mole, conforme descrito no livro "Cirurgia Oral e Maxilofacial Contemporânea".

    2 - Verdadeiro - O tipo de abrasão mais comumente visto são as escoriações que as crianças apresentam nos cotovelos e joelhos devido a brincadeiras, conforme mencionado no mesmo livro.

    3 - Falso - A laceração corresponde a uma solução de continuidade nos tecidos epiteliais e subepiteliais, o que significa que a afirmação está errada. Essa informação é confirmada no livro "Cirurgia Oral e Maxilofacial Contemporânea".

    4 - Verdadeiro - A contusão é de fato mais comumente chamada de equimose e indica que ocorreu algum rompimento no interior dos tecidos, resultando em hemorragia subcutânea ou submucosa sem descontinuidade na superfície dos tecidos moles, conforme descrito no livro "Princípios De Cirurgia Bucomaxilofacial".

    Portanto, a sequência correta é: V – V – F – V, que corresponde à alternativa A.

    A informação foi extraída dos livros "Cirurgia Oral e Maxilofacial Contemporânea" e "Princípios De Cirurgia Bucomaxilofacial".
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
